"""그림 위주·글자 부족 쪽: 쪽 이미지를 이미지 모델로 읽어 본문 뒤에 붙인다 (문제사항 R-03, R-04).

- 대상: Page.needs_image (글자 20자 미만이거나 큰 그림이 쪽의 40% 이상) — build_index가 PNG로 남기는 쪽과 같다.
  컴퓨터구성 30쪽(검색에서 아예 빠져 있었음), 컴퓨터네트워크 13쪽.
- build_index 때만 모델을 부르고 결과를 index/page_texts.json에 저장한다. 출제(load_chunks)는 이 파일만 읽는다
  → 출제 중 추가 호출 없음, 인덱스 청크와 같은 글 (vision_titles와 같은 방식).
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .pdf_parser import LOW_TEXT_CHARS, ParseReport

ROLE = "page_reader"  # config.yaml models.page_reader
PAGE_TEXTS_FILE = "page_texts.json"
PAGE_DPI = 110
MARK = "[이미지에서 읽은 내용]"


class PageReading(BaseModel):
    text: str = Field(description="쪽 내용을 글로 옮긴 것. 보이는 글자는 그대로(번역 금지), 없으면 빈 문자열")


def targets(report: ParseReport) -> list[int]:
    """이미지로 읽을 쪽 번호."""
    if not report.file.lower().endswith(".pdf"):
        return []
    return [p.page for p in report.pages if p.needs_image]


def page_image(pdf_path: Path, page_no: int, dpi: int = PAGE_DPI) -> bytes:
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        return doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")


def read_pages(pdf_path: Path, page_nos: list[int], verbose: bool = True) -> dict[int, str]:
    """쪽 번호 → 이미지에서 읽은 글 (읽을 내용이 없으면 ""). 같은 이미지는 llm 캐시로 다시 부르지 않는다."""
    from .. import llm

    prompt = llm.render_prompt("page_reader")
    out: dict[int, str] = {}
    for n in page_nos:
        r = llm.call(ROLE, prompt, PageReading, images=[(page_image(pdf_path, n), "image/png")])
        out[n] = r.text.strip()
        if verbose:
            head = " ".join(out[n].split())[:70]
            print(f"    [page] {pdf_path.name} p.{n}: {len(out[n])}자 {head}")
    return out


def apply_page_texts(report: ParseReport, texts: dict[int, str]) -> None:
    """읽은 글을 본문 뒤에 붙이고, 글자 부족 표시를 다시 정한다 (붙인 뒤 충분하면 청크가 만들어짐)."""
    for p in report.pages:
        t = texts.get(p.page, "").strip()
        if not t or MARK in p.text:
            continue
        p.text = f"{p.text.strip()}\n\n{MARK}\n{t}".strip()
        p.low_text = len(p.text) < LOW_TEXT_CHARS


def load_saved(index_dir: Path) -> dict[str, dict[int, str]]:
    f = index_dir / PAGE_TEXTS_FILE
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {file: {int(k): v for k, v in pages.items()} for file, pages in data.get("files", {}).items()}


def save(index_dir: Path, texts: dict[str, dict[int, str]], model: str) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    data = {"model": model, "files": {f: {str(k): v for k, v in sorted(p.items())} for f, p in sorted(texts.items())}}
    (index_dir / PAGE_TEXTS_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
