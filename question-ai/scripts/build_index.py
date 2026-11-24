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
from qgen.ingest import vision_pages as vp  # noqa: E402
from qgen.ingest import vision_titles as vt  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--query", action="append", default=[], help="만든 뒤 바로 검색해 볼 검색어 (여러 번 가능)")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--no-vision-titles", action="store_true",
                    help="제목이 그림인 교안을 이미지 모델로 읽지 않는다 (이미 저장된 titles.json은 그대로 씀)")
    ap.add_argument("--reread-titles", action="store_true", help="저장된 titles.json을 무시하고 다시 읽는다")
    ap.add_argument("--no-vision-pages", action="store_true",
                    help="그림 위주·글자 부족 쪽을 이미지 모델로 읽지 않는다 (이미 저장된 page_texts.json은 그대로 씀)")
    ap.add_argument("--reread-pages", action="store_true", help="저장된 page_texts.json을 무시하고 다시 읽는다")
    a = ap.parse_args()

    course_dir = ROOT / "data" / a.course
    if not (course_dir / "lectures").exists():
        raise SystemExit(f"{course_dir / 'lectures'} 폴더가 없습니다.")
    cfg = llm.CFG["retrieval"]
    index_dir = default_index_dir(a.course)
    t0 = time.time()

    saved = {} if a.reread_titles else vt.load_saved(index_dir)
    saved_pages = {} if a.reread_pages else vp.load_saved(index_dir)
    reports = parse_lectures(course_dir, render_dir=index_dir / "pages", titles=saved, page_texts=saved_pages)
    todo = [r for r in reports if vt.needs_vision(r) and r.file not in saved]
    if todo and not a.no_vision_titles:
        model = llm.CFG["models"][vt.ROLE]
        print(f"[title] 제목이 그림인 교안 {len(todo)}개 → {model}로 위쪽 띠 읽기 "
              f"({sum(len(r.pages) for r in todo)}쪽, 처음 한 번만 — 결과는 {vt.TITLES_FILE}에 저장)")
        for r in todo:
            saved[r.file] = vt.read_titles(course_dir / "lectures" / r.file, [p.page for p in r.pages])
            vt.apply_titles(r, saved[r.file])
            vt.save(index_dir, saved, model)  # 파일마다 저장 (중간에 멈춰도 읽은 만큼 남게)
    elif todo:
        print(f"[title] 제목이 그림인 교안 {len(todo)}개를 건너뜀 (--no-vision-titles): {[r.file for r in todo]}")

    page_todo = {r.file: [n for n in vp.targets(r) if n not in saved_pages.get(r.file, {})] for r in reports}
    page_todo = {f: ns for f, ns in page_todo.items() if ns}
    n_pages = sum(len(ns) for ns in page_todo.values())
    if page_todo and not a.no_vision_pages:
        model = llm.CFG["models"][vp.ROLE]
        print(f"[page] 그림 위주·글자 부족 쪽 {n_pages}개 → {model}로 쪽 이미지 읽기 (처음 한 번만 — 결과는 {vp.PAGE_TEXTS_FILE}에 저장)")
        by_file = {r.file: r for r in reports}
        for f, ns in page_todo.items():
            got = vp.read_pages(course_dir / "lectures" / f, ns)
            saved_pages.setdefault(f, {}).update(got)
            vp.apply_page_texts(by_file[f], got)
            vp.save(index_dir, saved_pages, model)  # 파일마다 저장
    elif page_todo:
        print(f"[page] 그림 위주·글자 부족 쪽 {n_pages}개를 건너뜀 (--no-vision-pages)")
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
