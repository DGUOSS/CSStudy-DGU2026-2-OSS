from pathlib import Path

import pymupdf

from qgen.ingest.pdf_parser import parse_file, parse_pdf

TEXT = "HTTP persistent connection keeps the TCP connection open for multiple requests."


def _image_rect(page: pymupdf.Page, ratio: float) -> pymupdf.Rect:
    """쪽 면적의 ratio만큼 차지하는 사각형 (가로세로 같은 비율로 줄임)."""
    s = ratio ** 0.5
    w, h = page.rect.width * s, page.rect.height * s
    return pymupdf.Rect(10, 10, 10 + w, 10 + h)


def _make_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
    pix.set_rect(pix.irect, (200, 30, 30))

    p1 = doc.new_page()  # 1: 글만
    p1.insert_text((50, 100), TEXT)
    doc.new_page()  # 2: 빈 쪽 (스캔본처럼 글자 없음)
    p3 = doc.new_page()  # 3: 큰 그림 + 짧은 제목
    p3.insert_text((50, 40), "Pipelining diagram")
    p3.insert_image(_image_rect(p3, 0.6), pixmap=pix, keep_proportion=False)  # 칸을 꽉 채움
    p4 = doc.new_page()  # 4: 글 + 작은 아이콘 여러 개 (글머리 기호처럼)
    p4.insert_text((50, 100), TEXT)
    for k in range(5):
        p4.insert_image(pymupdf.Rect(20, 200 + k * 30, 30, 210 + k * 30), pixmap=pix)
    doc.save(path)
    return path


def test_flags_and_warnings(tmp_path):
    rep = parse_pdf(_make_pdf(tmp_path / "lec.pdf"))
    p1, p2, p3, p4 = rep.pages
    assert [p.page for p in rep.pages] == [1, 2, 3, 4]
    assert not p1.has_figure and not p1.low_text and not p1.needs_image
    assert p2.low_text and p2.needs_image
    assert p3.has_figure and p3.figure_heavy and p3.image_ratio >= 0.5
    # 작은 아이콘은 무시: 이미지가 여러 개여도 그림 쪽이 아니다
    assert not p4.has_figure and p4.image_ratio == 0
    # 빈 쪽(2)과 제목만 있는 그림 쪽(3)이 '글자 부족'으로 함께 경고된다
    assert len(rep.warnings) == 1 and "[2, 3]" in rep.warnings[0]


def test_render_only_pages_that_need_image(tmp_path):
    out = tmp_path / "pages"
    rep = parse_pdf(_make_pdf(tmp_path / "lec.pdf"), render_dir=out)
    rendered = {p.page for p in rep.pages if p.image_path}
    assert rendered == {2, 3}
    assert all(Path(p.image_path).exists() for p in rep.pages if p.image_path)


def test_title_is_largest_font_not_page_number(tmp_path):
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((550, 20), "7", fontsize=9)  # 쪽 번호가 글 순서상 먼저 나와도
    p.insert_text((50, 60), "Web Caching", fontsize=24)
    p.insert_text((50, 120), "A cache stores copies of responses to reuse them later.", fontsize=14)
    doc.save(tmp_path / "t.pdf")
    assert parse_pdf(tmp_path / "t.pdf").pages[0].title == "Web Caching"


def test_scanned_pdf_warns(tmp_path):
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    doc.save(tmp_path / "scan.pdf")
    rep = parse_pdf(tmp_path / "scan.pdf")
    assert len(rep.warnings) == 1 and "스캔 PDF" in rep.warnings[0]


def test_markdown_split_keeps_old_behavior(tmp_path):
    f = tmp_path / "lec.md"
    f.write_text("## A\n첫 슬라이드 내용입니다. 충분히 길게 씁니다.\n\n## B\n두 번째 슬라이드 내용입니다. 이것도 길게.\n---\n세 번째 구간은 구분선 다음입니다. 길게 씁니다.\n",
                 encoding="utf-8")
    pages = parse_file(f).pages
    assert [p.text.splitlines()[0] for p in pages] == ["## A", "## B", "세 번째 구간은 구분선 다음입니다. 길게 씁니다."]
