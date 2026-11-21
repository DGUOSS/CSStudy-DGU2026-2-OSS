"""검색: e5 임베딩 인덱스(기본) + BM25(인덱스가 없거나 오래됐을 때 대신).

- e5 규칙: 문서는 "passage: ", 검색어는 "query: " 접두어 (명세 §5).
- 인덱스는 data/<과목>/index/ 에 embeddings.npy + meta.json으로 저장 (git 제외).
- meta.json의 fingerprint(청크 id·본문 해시)가 지금 청크와 다르면 오래된 인덱스로 보고 쓰지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np

from ..schemas import Chunk

Encoder = Callable[[list[str]], np.ndarray]  # 글 목록 → (개수, 차원) 정규화된 벡터

_MODELS: dict[str, object] = {}


def search_text(c: Chunk) -> str:
    """검색에 쓰는 글: 본문에 제목이 없으면 제목을 앞에 붙인다.

    제목이 도형인 교안(컴퓨터구성 Chap1-2 등)은 본문에 제목 글자가 없어서, 이미지로 읽은 제목을 붙여야
    'Half Adder' 같은 제목 검색어로 그 쪽을 찾는다.
    """
    if c.title and c.title.lower() not in c.text.lower():
        return f"{c.title}\n{c.text}"
    return c.text


def fingerprint(chunks: list[Chunk]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(b"\0")
        h.update(search_text(c).encode())
        h.update(b"\0")
    return h.hexdigest()


def st_encoder(model_name: str, batch_size: int = 16) -> Encoder:
    """sentence-transformers 인코더. 모델은 처음 쓸 때 한 번만 불러온다 (CPU, 작은 배치: 8GB RAM 대응)."""

    def encode(texts: list[str]) -> np.ndarray:
        if model_name not in _MODELS:
            from sentence_transformers import SentenceTransformer

            _MODELS[model_name] = SentenceTransformer(model_name, device="cpu")
        model = _MODELS[model_name]
        return np.asarray(model.encode(texts, batch_size=batch_size, normalize_embeddings=True,  # type: ignore[attr-defined]
                                       show_progress_bar=False), dtype=np.float32)

    return encode


class EmbeddingIndex:
    def __init__(self, vectors: np.ndarray, meta: dict):
        self.vectors = vectors
        self.meta = meta

    @classmethod
    def build(cls, chunks: list[Chunk], encoder: Encoder, model_name: str) -> "EmbeddingIndex":
        vecs = encoder([f"passage: {search_text(c)}" for c in chunks])
        meta = {"model": model_name, "count": len(chunks), "dim": int(vecs.shape[1]),
                "fingerprint": fingerprint(chunks), "chunk_ids": [c.chunk_id for c in chunks]}
        return cls(vecs, meta)

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "embeddings.npy", self.vectors)
        (index_dir / "meta.json").write_text(json.dumps(self.meta, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, index_dir: Path) -> "EmbeddingIndex | None":
        vf, mf = index_dir / "embeddings.npy", index_dir / "meta.json"
        if not (vf.exists() and mf.exists()):
            return None
        return cls(np.load(vf), json.loads(mf.read_text(encoding="utf-8")))

    def scores(self, query: str, encoder: Encoder) -> np.ndarray:
        q = encoder([f"query: {query}"])[0]
        return self.vectors @ q  # 정규화된 벡터라 내적 = 코사인 유사도


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[가-힣]+|[a-zA-Z]+|\d+", text.lower())
    toks = list(words)
    for w in words:  # 한국어 조사 대응용 문자 bigram
        toks += [w[i:i + 2] for i in range(len(w) - 1)]
    return toks


class BM25:
    """의존성 없는 키워드 검색 (문자 bigram). 임베딩 인덱스가 없을 때 쓴다."""

    def __init__(self, chunks: list[Chunk]):
        self.docs = [Counter(_tokens(search_text(c))) for c in chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - v + 0.5) / (v + 0.5)) for t, v in df.items()}

    def scores(self, query: str) -> list[float]:
        q = _tokens(query)
        out = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf[t] * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * self.lens[i] / self.avg))
            out.append(s)
        return out


def default_index_dir(course_id: str) -> Path:
    from .. import llm

    return llm.ROOT / llm.CFG["retrieval"]["index_dir"].format(course=course_id)


class Retriever:
    """pipeline이 쓰는 검색기. 맞는 임베딩 인덱스가 있으면 임베딩, 없으면 BM25."""

    def __init__(self, chunks: list[Chunk], index_dir: Path | None = None, encoder: Encoder | None = None,
                 verbose: bool = True):
        self.chunks = chunks
        self.mode = "bm25"
        self.index: EmbeddingIndex | None = None
        self.encoder = encoder
        self.bm25 = BM25(chunks)
        if not chunks:
            return
        index_dir = index_dir or default_index_dir(chunks[0].course_id)
        idx = EmbeddingIndex.load(index_dir)
        if idx is None:
            msg = f"임베딩 인덱스 없음({index_dir}) → BM25 사용. 만들려면: python scripts/build_index.py --course {chunks[0].course_id}"
        elif idx.meta.get("fingerprint") != fingerprint(chunks):
            msg = f"임베딩 인덱스가 지금 강의자료와 다름(자료가 바뀜) → BM25 사용. build_index.py를 다시 실행하세요."
        else:
            self.index, self.mode = idx, "embedding"
            if self.encoder is None:
                from .. import llm

                self.encoder = st_encoder(idx.meta["model"], llm.CFG["retrieval"].get("batch_size", 16))
            msg = f"임베딩 인덱스 사용 ({idx.meta['model']}, 청크 {idx.meta['count']}개)"
        if verbose:
            print(f"[retrieval] {msg}")

    def _ranked(self, query: str) -> list[int]:
        if self.mode == "embedding" and self.index is not None and self.encoder is not None:
            scores = list(self.index.scores(query, self.encoder))
        else:
            scores = self.bm25.scores(query)
        return sorted(range(len(scores)), key=lambda i: -scores[i])

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        return [self.chunks[i] for i in self._ranked(query)[:k]]

    def search_many(self, queries: list[str], k: int = 4, exclude: set[str] | None = None) -> list[Chunk]:
        """검색어마다 순위를 매긴 뒤 번갈아 하나씩 뽑아 k개를 채운다 (중복 제외).

        한 검색어가 자리를 독차지하지 않게: 검색어 2개면 2쪽씩, 3개면 2·1·1쪽.
        exclude: 빼고 뽑을 chunk_id ("지엽적" 출제에서 앞 문항이 이미 쓴 쪽).
        """
        if not queries:
            return []
        ex = exclude or set()
        ranked = [[i for i in self._ranked(q) if self.chunks[i].chunk_id not in ex] for q in queries]
        pos = [0] * len(ranked)
        picked: list[int] = []
        while len(picked) < min(k, len(self.chunks)):
            moved = False
            for r, lst in enumerate(ranked):
                while pos[r] < len(lst) and lst[pos[r]] in picked:
                    pos[r] += 1
                if pos[r] < len(lst) and len(picked) < k:
                    picked.append(lst[pos[r]])
                    pos[r] += 1
                    moved = True
            if not moved:
                break
        return [self.chunks[i] for i in picked]
