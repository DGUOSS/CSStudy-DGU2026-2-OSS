"""쪽 → 검색용 청크. 슬라이드 1장 = 기본 1청크, 긴 쪽은 문단(없으면 줄) 단위로 나누고 각 조각 앞에 제목을 붙인다."""
from __future__ import annotations

import re
from pathlib import Path

from ..schemas import Chunk, SourceRef
from .pdf_parser import LOW_TEXT_CHARS, Page

MAX_CHARS = 1200  # 청크 하나의 최대 글자 수 (슬라이드는 보통 300~500자라 대부분 나뉘지 않음)


_NOISE_LINE = re.compile(r"^(\d{1,4}|\d{4}[-./]\d{1,2}[-./]\d{1,2})$")  # 쪽 번호, 날짜


def title_of(text: str) -> str:
    """첫 번째 의미 있는 줄을 제목으로 본다 (마크다운 '#'은 떼고, 쪽 번호·날짜만 있는 줄은 건너뜀)."""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not _NOISE_LINE.match(line):
            return line[:80]
    return ""


def _split(text: str, max_chars: int) -> list[str]:
    """빈 줄로 나눈 문단을 max_chars 안에서 이어 붙인다. 문단 하나가 너무 길면 줄 단위로, 줄도 너무 길면 글자 수로 자른다."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) == 1:
        paras = [ln for ln in text.splitlines() if ln.strip()]
    pieces: list[str] = []
    for p in paras:
        while len(p) > max_chars:
            pieces.append(p[:max_chars])
            p = p[max_chars:]
        pieces.append(p)
    parts: list[str] = []
    cur = ""
    for p in pieces:
        if cur and len(cur) + 1 + len(p) > max_chars:
            parts.append(cur)
            cur = p
        else:
            cur = f"{cur}\n{p}" if cur else p
    if cur:
        parts.append(cur)
    return parts


def _has_formula(text: str) -> bool:
    return "$" in text or "=" in text


def chunk_pages(pages: list[Page], course_id: str, max_chars: int = MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for pg in pages:
        text = pg.text.strip()
        if len(text) < LOW_TEXT_CHARS:  # 글자 부족 쪽은 검색할 글이 없어 건너뜀 (pdf_parser가 경고)
            continue
        stem = Path(pg.file).stem
        title = pg.title or title_of(text)
        common = dict(course_id=course_id, source=SourceRef(file=pg.file, page=pg.page),
                      has_figure=pg.has_figure, image_path=pg.image_path, title=title)
        if len(text) <= max_chars:
            chunks.append(Chunk(chunk_id=f"{stem}-p{pg.page}", text=text, has_formula=_has_formula(text), **common))
            continue
        for k, part in enumerate(_split(text, max_chars - len(title) - 3), start=1):
            if k > 1 and title and not part.startswith(title):
                part = f"[{title}]\n{part}"  # 뒷조각에도 어느 슬라이드인지 알 수 있게 제목을 붙인다
            chunks.append(Chunk(chunk_id=f"{stem}-p{pg.page}-{k}", text=part, has_formula=_has_formula(part), **common))
    return chunks
