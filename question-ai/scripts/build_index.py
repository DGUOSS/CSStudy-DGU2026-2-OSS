"""강의자료 → 청크 → e5 임베딩 인덱스 만들기.

    python scripts/build_index.py --course 26-CSC4016-01
    python scripts/build_index.py --course demo --query "라운드 로빈" --query "호위 효과"

결과: data/<과목>/index/ (embeddings.npy, meta.json, chunks.json, pages/*.png) — git에 올라가지 않음.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # 설치된 qgen이 다른 폴더를 가리켜도 이 저장소 코드를 쓰게
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")  # Windows 콘솔 한글·기호 출력

from qgen import llm  # noqa: E402
from qgen.ingest import (  # noqa: E402
    BM25, EmbeddingIndex, Retriever, chunk_pages, default_index_dir, parse_lectures, st_encoder,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--query", action="append", default=[], help="만든 뒤 바로 검색해 볼 검색어 (여러 번 가능)")
    ap.add_argument("-k", type=int, default=5)
    a = ap.parse_args()

    course_dir = ROOT / "data" / a.course
    if not (course_dir / "lectures").exists():
        raise SystemExit(f"{course_dir / 'lectures'} 폴더가 없습니다.")
    cfg = llm.CFG["retrieval"]
    index_dir = default_index_dir(a.course)
    t0 = time.time()

    reports = parse_lectures(course_dir, render_dir=index_dir / "pages")
    pages = [p for r in reports for p in r.pages]
    chunks = chunk_pages(pages, a.course)
    if not chunks:
        raise SystemExit("청크가 없습니다. 강의자료에 읽을 수 있는 글자가 있는지 확인하세요.")
    print(f"[parse] 파일 {len(reports)}개, 쪽 {len(pages)}개 → 청크 {len(chunks)}개 "
          f"(그림 있음 {sum(p.has_figure for p in pages)}쪽, PNG 저장 {sum(p.image_path is not None for p in pages)}쪽)")

    encoder = st_encoder(cfg["embedding_model"], cfg.get("batch_size", 16))
    idx = EmbeddingIndex.build(chunks, encoder, cfg["embedding_model"])
    idx.save(index_dir)
    (index_dir / "chunks.json").write_text(
        json.dumps([c.model_dump() for c in chunks], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[index] {index_dir} 저장 (차원 {idx.meta['dim']}, {time.time() - t0:.1f}s)")

    if a.query:
        emb = Retriever(chunks, index_dir=index_dir, encoder=encoder)
        bm25 = BM25(chunks)
        for q in a.query:
            print(f"\n## {q}")
            hits = emb.search(q, k=a.k)
            s = bm25.scores(q)
            bm_top = [chunks[i] for i in sorted(range(len(s)), key=lambda i: -s[i])[: a.k]]
            print("  임베딩: " + ", ".join(f"{c.source.file} p.{c.source.page}" for c in hits))
            print("  BM25  : " + ", ".join(f"{c.source.file} p.{c.source.page}" for c in bm_top))


if __name__ == "__main__":
    main()
