"""강의자료/기출 읽기 + 청크 + 검색 (M1).

pipeline·agents가 쓰는 이름(load_chunks, load_text_dir, Retriever, format_chunks, topic_list)은
예전 ingest.py와 같게 유지한다.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..schemas import Chunk
from .chunker import chunk_pages, title_of
from .index import BM25, EmbeddingIndex, Retriever, default_index_dir, fingerprint, st_encoder
from .pdf_parser import SUPPORTED, Page, ParseReport, parse_file

__all__ = [
    "BM25", "EmbeddingIndex", "Page", "ParseReport", "Retriever", "chunk_pages", "default_index_dir",
    "fingerprint", "format_chunks", "load_chunks", "load_text_dir", "parse_file", "parse_lectures",
    "MAX_SOURCE_TITLES", "search_queries", "st_encoder", "topic_list",
]


def parse_lectures(course_dir: Path, render_dir: Path | None = None, verbose: bool = True) -> list[ParseReport]:
    """lectures/ 안의 강의자료를 읽는다. render_dir가 있으면 그림 위주·글자 부족 쪽을 PNG로 남긴다."""
    lec = course_dir / "lectures"
    if not lec.exists():
        return []
    reports = []
    for f in sorted(lec.iterdir()):
        if f.suffix.lower() not in SUPPORTED:
            if verbose and f.is_file():
                print(f"[ingest] 지원하지 않는 형식이라 건너뜀: {f.name} (지원: {', '.join(SUPPORTED)})")
            continue
        r = parse_file(f, render_dir=render_dir)
        if verbose:
            for w in r.warnings:
                print(f"[ingest] 경고: {w}")
        reports.append(r)
    return reports


def load_chunks(course_dir: Path, render_dir: Path | None = None, verbose: bool = True) -> list[Chunk]:
    """강의자료 → 청크. PNG는 만들지 않고, build_index가 만들어 둔 PNG가 있으면 경로만 붙인다."""
    reports = parse_lectures(course_dir, render_dir=render_dir, verbose=verbose)
    pages_dir = render_dir or (default_index_dir(course_dir.name) / "pages")
    pages: list[Page] = []
    for r in reports:
        for p in r.pages:
            if p.image_path is None and p.needs_image:
                png = pages_dir / f"{Path(p.file).stem}-p{p.page}.png"
                if png.exists():
                    p.image_path = str(png)
            pages.append(p)
    return chunk_pages(pages, course_dir.name)


def load_text_dir(d: Path) -> str:
    """기출 등 폴더 안 문서를 한 글로 이어 붙인다 (Analyst·Generator 예시용)."""
    if not d.exists():
        return ""
    out = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in SUPPORTED:
            out.append(f"### {f.name}\n" + "\n".join(p.text for p in parse_file(f).pages))
    return "\n\n".join(out)


def format_chunks(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{c.source.file} p.{c.source.page}]\n{c.text}" for c in chunks)


_REF_SUFFIX = re.compile(r"\s*\([^()]*\.(?:pdf|md|txt) p\.\d+\)\s*$", re.I)


MAX_SOURCE_TITLES = 3  # config.yaml pipeline.max_source_titles로 바꿀 수 있음


def search_queries(topic: str, source_titles: list[str], chunks: list[Chunk],
                   max_titles: int = MAX_SOURCE_TITLES) -> tuple[list[str], list[str]]:
    """문항의 검색어 목록을 정한다 → (검색어들, 경고들).

    교안 언어와 검색어 언어가 다르면 검색이 부정확해지므로(한국어 검색어 + 영어 교안), Planner가 목록에서
    그대로 복사한 source_titles를 검색어로 쓴다. 목록에 없는 제목(번역·오타)은 버리고, 하나도 안 남으면 topic으로 검색한다.
    """
    known = {c.title or title_of(c.text) for c in chunks}
    queries: list[str] = []
    warns: list[str] = []
    for raw in source_titles:
        t = _REF_SUFFIX.sub("", raw or "").strip()
        if not t or t in queries:
            continue
        if t not in known:
            warns.append(f"source_titles의 '{t}'이 강의자료 제목 목록에 없어 뺍니다.")
            continue
        queries.append(t)
    if len(queries) > max_titles:
        warns.append(f"제목이 {len(queries)}개라 앞의 {max_titles}개만 씁니다: {queries[max_titles:]} 제외")
        queries = queries[:max_titles]
    if not queries:
        if source_titles:
            warns.append("쓸 수 있는 제목이 없어 topic으로 검색합니다.")
        queries = [topic]
    return queries, warns


def topic_list(chunks: list[Chunk]) -> list[str]:
    """쪽마다 제목 한 줄 (한 쪽이 여러 청크로 나뉘어도 한 번만)."""
    seen: set[tuple[str, int]] = set()
    out = []
    for c in chunks:
        key = (c.source.file, c.source.page)
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{c.title or title_of(c.text)} ({c.source.file} p.{c.source.page})")
    return out
