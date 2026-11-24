from pathlib import Path

import pymupdf

from qgen.ingest.pdf_parser import clean_title_text, is_title_like, parse_file, parse_pdf

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
    out = tmp_path / "index" / "pages"
    rep = parse_pdf(_make_pdf(tmp_path / "lec.pdf"), render_dir=out, image_base=tmp_path)
    rendered = {p.page for p in rep.pages if p.image_path}
    assert rendered == {2, 3}
    for p in rep.pages:
        if p.image_path:
            # 과목 폴더 기준 상대 경로, '/' 구분 → 다른 컴퓨터·서버에서도 같은 값
            assert p.image_path.startswith("index/pages/") and not Path(p.image_path).is_absolute()
            assert (tmp_path / p.image_path).exists()


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


def test_title_only_from_top_zone_and_inherits_previous(tmp_path):
    """가운데 큰 진리표·수식은 제목이 아니다. 위쪽에 제목이 없으면 앞 쪽 제목을 이어받는다."""
    doc = pymupdf.open()
    p1 = doc.new_page()  # 1: 위쪽 제목 + 가운데 더 큰 글씨
    p1.insert_text((50, 60), "Full Adder", fontsize=24)
    p1.insert_text((50, 420), "A B Cin S Cout", fontsize=32)
    p2 = doc.new_page()  # 2: 제목이 그림이라 위쪽에 글자 없음, 가운데에만 큰 글씨
    p2.insert_text((50, 420), "Truth Table", fontsize=32)
    p3 = doc.new_page()  # 3: 위쪽 큰 글씨가 기호·숫자뿐 → 제목 아님, 작은 글씨 제목을 쓴다
    p3.insert_text((50, 50), "1 = 0 + 1", fontsize=40)
    p3.insert_text((50, 110), "Half Adder", fontsize=20)
    p4 = doc.new_page()  # 4: 위쪽 글자가 기호뿐 → 앞 제목(Half Adder) 이어받기
    p4.insert_text((50, 60), "= + - 1 0", fontsize=30)
    doc.save(tmp_path / "t.pdf")
    titles = [p.title for p in parse_pdf(tmp_path / "t.pdf").pages]
    assert titles == ["Full Adder", "Full Adder", "Half Adder", "Half Adder"]


def test_title_keeps_short_parts_inside_title(tmp_path):
    """제목 안의 '1', 'S' 같은 짧은 조각은 지우지 않는다."""
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((50, 60), "Chapter", fontsize=24)
    p.insert_text((150, 60), "1", fontsize=24)
    doc.save(tmp_path / "t.pdf")
    assert parse_pdf(tmp_path / "t.pdf").pages[0].title == "Chapter 1"


def test_clean_title_text_removes_bullet_font_chars():
    assert clean_title_text("  Cache   Memory") == "Cache Memory"
    assert not is_title_like("12 - 3 = 9") and is_title_like("버스 구조")
