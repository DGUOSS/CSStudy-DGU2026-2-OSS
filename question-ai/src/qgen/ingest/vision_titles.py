"""제목이 도형·그림으로 들어가 글자로 못 뽑는 교안: 쪽 위쪽 띠를 이미지 모델로 읽는다.

- 대상: PDF 중 위쪽 글자에서 제목을 못 뽑은 쪽이 NEED_RATIO 이상인 파일만 (컴퓨터구성 교안 4개는 100%,
  나머지 교안은 0~6%). 대상 파일은 모든 쪽을 읽는다.
- build_index 때만 모델을 부르고 결과를 index/titles.json에 저장한다. 출제(pipeline)의 load_chunks는
  이 파일만 읽어서 쓰므로 출제 중에는 제목 때문에 모델을 부르지 않는다 (인덱스 청크와 제목이 같게 유지).
- 띠 OCR 비교(2026-11-19, 10장): Gemini 10/10, PaddleOCR 6/10, EasyOCR 3/10 → Gemini.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .pdf_parser import TITLE_ZONE, ParseReport, clean_title_text, is_title_like

ROLE = "title_reader"  # config.yaml models.title_reader
TITLES_FILE = "titles.json"
NEED_RATIO = 0.5  # 글자로 제목을 못 뽑은 쪽이 이 비율 이상인 파일만 이미지로 읽는다
STRIP_DPI = 110


class SlideTitle(BaseModel):
    title: str = Field(description="슬라이드 제목. 이미지 글자 그대로(번역 금지). 없으면 빈 문자열")


def needs_vision(report: ParseReport) -> bool:
    if not report.file.lower().endswith(".pdf") or not report.pages:
        return False
    missing = sum(not p.title_from_text for p in report.pages)
    return missing / len(report.pages) >= NEED_RATIO


def title_strip(pdf_path: Path, page_no: int, dpi: int = STRIP_DPI) -> bytes:
    """page_no(1부터) 쪽의 위쪽 TITLE_ZONE 띠를 PNG 바이트로."""
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        pg = doc[page_no - 1]
        r = pg.rect
        clip = pymupdf.Rect(r.x0, r.y0, r.x1, r.y0 + r.height * TITLE_ZONE)
        return pg.get_pixmap(dpi=dpi, clip=clip).tobytes("png")


def read_titles(pdf_path: Path, page_nos: list[int], verbose: bool = True) -> dict[int, str]:
    """쪽 번호 → 모델이 읽은 제목 (읽을 수 없으면 ""). 같은 이미지는 llm 캐시로 다시 부르지 않는다."""
    from .. import llm

    prompt = llm.render_prompt("title_reader")
    out: dict[int, str] = {}
    for n in page_nos:
        r = llm.call(ROLE, prompt, SlideTitle, images=[(title_strip(pdf_path, n), "image/png")])
        t = clean_title_text(r.title)
        out[n] = t[:80] if is_title_like(t) else ""
        if verbose:
            print(f"    [title] {pdf_path.name} p.{n}: {out[n] or '(없음)'}")
    return out


def apply_titles(report: ParseReport, titles: dict[int, str]) -> None:
    """읽은 제목 > 글자로 뽑은 제목 > 같은 파일의 앞 제목 순으로 다시 정한다."""
    last = ""
    for p in report.pages:
        t = titles.get(p.page) or (p.title if p.title_from_text else "") or last
        p.title = t
        last = t or last


def load_saved(index_dir: Path) -> dict[str, dict[int, str]]:
    f = index_dir / TITLES_FILE
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {file: {int(k): v for k, v in pages.items()} for file, pages in data.get("files", {}).items()}


def save(index_dir: Path, titles: dict[str, dict[int, str]], model: str) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    data = {"model": model, "files": {f: {str(k): v for k, v in sorted(p.items())} for f, p in sorted(titles.items())}}
    (index_dir / TITLES_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
