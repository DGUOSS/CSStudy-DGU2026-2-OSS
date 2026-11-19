"""강의자료 읽기: PDF는 쪽별 텍스트 + 그림·글자 부족 표시, .md/.txt는 구분선·제목으로 쪽을 나눈다.

그림 판단 기준은 실제 교안(26-CSC4016-01, 슬라이드 111쪽)을 보고 정했다.
- 쪽마다 작은 이미지가 10~20개씩 있는데 대부분 글머리 기호·로고다. 그래서 '이미지 개수'가 아니라
  '쪽 면적의 2% 이상인 이미지의 면적 합'으로 본다.
- 도식이 벡터(선·상자)로 그려진 쪽도 있어 도형 개수도 함께 본다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 이 면적 비율보다 작은 이미지는 글머리 기호·로고로 보고 무시
TINY_IMAGE_RATIO = 0.02
# 큰 이미지 면적 합이 이 비율 이상이거나 도형이 이만큼 있으면 '그림 있음'
FIGURE_IMAGE_RATIO = 0.15
FIGURE_DRAWINGS = 15
# 큰 이미지 면적 합이 이 비율 이상이면 '그림 위주' → 쪽을 PNG로 남긴다
FIGURE_HEAVY_RATIO = 0.40
# 글자가 이보다 적으면 '글자 부족'(스캔본이거나 그림만 있는 쪽) → PNG로 남기고 경고
LOW_TEXT_CHARS = 20


@dataclass
class Page:
    file: str
    page: int  # 1부터
    text: str
    title: str = ""  # PDF는 가장 큰 글씨 줄, 없으면 chunker가 첫 줄로 정함
    image_ratio: float = 0.0  # 큰 이미지 면적 합 / 쪽 면적 (최대 1)
    drawings: int = 0
    has_figure: bool = False
    figure_heavy: bool = False
    low_text: bool = False
    image_path: str | None = None  # PNG로 남긴 경우 경로 (image_base가 있으면 그 기준 상대 경로, '/' 구분)

    @property
    def needs_image(self) -> bool:
        """텍스트만으로는 내용이 부족해 쪽 이미지가 필요한지."""
        return self.low_text or self.figure_heavy


@dataclass
class ParseReport:
    file: str
    pages: list[Page] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        low = [p.page for p in self.pages if p.low_text]
        if not self.pages:
            return [f"{self.file}: 쪽이 없습니다."]
        if len(low) == len(self.pages):
            return [f"{self.file}: 모든 쪽에 글자가 없습니다. 스캔 PDF로 보입니다. 텍스트로는 문제를 만들 수 없습니다."]
        if low:
            return [f"{self.file}: 글자가 거의 없는 쪽 {len(low)}개 {low} — 그림만 있거나 스캔된 쪽일 수 있습니다."]
        return []


def _image_ratio(page) -> float:
    import pymupdf

    area = page.rect.width * page.rect.height
    if area <= 0:
        return 0.0
    total = 0.0
    for info in page.get_image_info():
        r = (pymupdf.Rect(info["bbox"]) & page.rect).get_area() / area
        if r >= TINY_IMAGE_RATIO:
            total += r
    return min(total, 1.0)


def _largest_font_title(page, max_len: int = 80) -> str:
    """쪽에서 가장 큰 글씨의 글을 위→아래, 왼→오른 순서로 이어 붙인다 (슬라이드 제목).

    텍스트를 그냥 뽑으면 첫 줄이 쪽 번호('3')나 날짜가 되는 교안이 있어 글씨 크기로 찾는다.
    """
    spans = [(s["size"], s["bbox"][1], s["bbox"][0], s["text"].strip())
             for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"]
             if s["text"].strip()]
    if not spans:
        return ""
    top = max(s[0] for s in spans)
    parts = sorted((s for s in spans if s[0] >= top - 0.5), key=lambda s: (round(s[1] / 5), s[2]))
    return " ".join(p[3] for p in parts)[:max_len].strip()


def rel_path(path: Path, base: Path | None) -> str:
    """base 기준 상대 경로('/' 구분). 다른 컴퓨터·서버로 옮겨도 맞도록 절대 경로를 저장하지 않는다."""
    if base is None:
        return path.as_posix()
    return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()


def parse_pdf(path: Path, render_dir: Path | None = None, dpi: int = 110,
              image_base: Path | None = None) -> ParseReport:
    """PDF를 쪽별로 읽는다. render_dir가 있으면 그림 위주·글자 부족 쪽을 PNG로 저장한다.

    image_base: image_path를 이 폴더 기준 상대 경로로 남긴다 (보통 과목 폴더 data/<과목>/).
    """
    import pymupdf

    report = ParseReport(file=path.name)
    with pymupdf.open(path) as doc:
        for i, pg in enumerate(doc, start=1):
            text = pg.get_text().strip()
            ratio = _image_ratio(pg)
            drawings = len(pg.get_drawings())
            p = Page(
                file=path.name, page=i, text=text, title=_largest_font_title(pg),
                image_ratio=round(ratio, 3), drawings=drawings,
                has_figure=ratio >= FIGURE_IMAGE_RATIO or drawings >= FIGURE_DRAWINGS,
                figure_heavy=ratio >= FIGURE_HEAVY_RATIO,
                low_text=len(text) < LOW_TEXT_CHARS,
            )
            if render_dir is not None and p.needs_image:
                render_dir.mkdir(parents=True, exist_ok=True)
                out = render_dir / f"{path.stem}-p{i}.png"
                pg.get_pixmap(dpi=dpi).save(out)
                p.image_path = rel_path(out, image_base)
            report.pages.append(p)
    return report


def parse_text(path: Path) -> ParseReport:
    """.md/.txt: '---' 줄 또는 '## ' 제목을 쪽 경계로 본다 (기존 동작 유지)."""
    text = path.read_text(encoding="utf-8")
    parts = [p.strip() for p in re.split(r"\n-{3,}\n|\n(?=## )", text) if p.strip()]
    report = ParseReport(file=path.name)
    for i, part in enumerate(parts, start=1):
        report.pages.append(Page(file=path.name, page=i, text=part, low_text=len(part) < LOW_TEXT_CHARS))
    return report


SUPPORTED = (".pdf", ".md", ".txt")


def parse_file(path: Path, render_dir: Path | None = None, image_base: Path | None = None) -> ParseReport:
    if path.suffix.lower() == ".pdf":
        return parse_pdf(path, render_dir=render_dir, image_base=image_base)
    return parse_text(path)
