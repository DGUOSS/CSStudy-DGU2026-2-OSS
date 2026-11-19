"""강의자료/기출 읽기 + 간단한 키워드(BM25) 검색.

프로토타입: 임베딩(e5) 대신 의존성 없는 BM25(문자 bigram)를 쓴다. 이후 index.py로 교체 예정.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from .schemas import Chunk, SourceRef


def read_pages(path: Path) -> list[str]:
    """PDF는 페이지별 텍스트, .md/.txt는 '---' 줄 또는 '## ' 제목을 페이지 경계로 본다."""
    if path.suffix.lower() == ".pdf":
        import fitz

        with fitz.open(path) as doc:
            return [p.get_text() for p in doc]
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"\n-{3,}\n|\n(?=## )", text)
    return [p.strip() for p in parts if p.strip()]


def load_chunks(course_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for f in sorted((course_dir / "lectures").iterdir()):
        if f.suffix.lower() not in (".pdf", ".md", ".txt"):
            continue
        for i, page in enumerate(read_pages(f), start=1):
            if len(page) < 20:
                continue
            chunks.append(Chunk(
                chunk_id=f"{f.stem}-p{i}", course_id=course_dir.name, text=page[:3000],
                source=SourceRef(file=f.name, page=i),
                has_formula="$" in page or "=" in page,
            ))
    return chunks


def load_text_dir(d: Path) -> str:
    if not d.exists():
        return ""
    out = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in (".pdf", ".md", ".txt"):
            out.append(f"### {f.name}\n" + "\n".join(read_pages(f)))
    return "\n\n".join(out)


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[가-힣]+|[a-zA-Z]+|\d+", text.lower())
    toks = list(words)
    for w in words:  # 한국어 조사 대응용 문자 bigram
        toks += [w[i:i + 2] for i in range(len(w) - 1)]
    return toks


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.docs = [Counter(_tokens(c.text)) for c in chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - v + 0.5) / (v + 0.5)) for t, v in df.items()}

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        q = _tokens(query)
        scores = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf[t] * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * self.lens[i] / self.avg))
            scores.append(s)
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [self.chunks[i] for i in order[:k]]


def format_chunks(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{c.source.file} p.{c.source.page}]\n{c.text}" for c in chunks)


def topic_list(chunks: list[Chunk]) -> list[str]:
    """각 청크의 첫 줄(슬라이드 제목)을 주제 목록으로."""
    return [f"{c.text.splitlines()[0].strip('# ').strip()[:80]} ({c.source.file} p.{c.source.page})" for c in chunks]
