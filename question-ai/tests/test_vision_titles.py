import pymupdf

from qgen import llm
from qgen.ingest import load_chunks, parse_lectures
from qgen.ingest import vision_titles as vt
from qgen.ingest.pdf_parser import Page, ParseReport, parse_pdf


def _report(flags: list[bool], titles: list[str] | None = None) -> ParseReport:
    titles = titles or [f"T{i}" if f else "" for i, f in enumerate(flags, start=1)]
    return ParseReport(file="lec.pdf", pages=[
        Page(file="lec.pdf", page=i, text="본문 " * 10, title=t, title_from_text=f)
        for i, (f, t) in enumerate(zip(flags, titles), start=1)])


def _shape_title_pdf(path, n: int = 3):
    """제목이 글자가 아닌(도형) 교안 흉내: 위쪽에 글자 없이 본문만."""
    doc = pymupdf.open()
    for i in range(n):
        doc.new_page().insert_text((50, 400), f"Body text of slide {i + 1} with enough characters.", fontsize=12)
    doc.save(path)
    return path


def test_needs_vision_only_when_most_titles_missing():
    assert vt.needs_vision(_report([False, False, True]))       # 2/3 못 뽑음
    assert not vt.needs_vision(_report([True, True, False]))    # 1/3
    md = ParseReport(file="a.md", pages=[Page(file="a.md", page=1, text="x")])
    assert not vt.needs_vision(md)                              # PDF만


def test_apply_titles_priority_and_inherit():
    r = _report([True, False, False, True], ["Text1", "", "", "Text4"])
    vt.apply_titles(r, {1: "", 2: "Read2", 4: "Read4"})
    # 읽은 제목 > 글자 제목 > 앞 제목 이어받기
    assert [p.title for p in r.pages] == ["Text1", "Read2", "Read2", "Read4"]


def test_read_titles_cleans_and_drops_non_titles(tmp_path, monkeypatch):
    pdf = _shape_title_pdf(tmp_path / "lec.pdf")
    answers = iter(["  Half   Adder ", "1 + 0 = 1", ""])
    seen = []

    def fake_call(role, prompt, schema, images=None, **kw):
        seen.append((role, images[0][1], images[0][0][:4]))
        return schema(title=next(answers))

    monkeypatch.setattr(llm, "call", fake_call)
    assert vt.read_titles(pdf, [1, 2, 3], verbose=False) == {1: "Half Adder", 2: "", 3: ""}
    assert all(r == vt.ROLE and m == "image/png" and b == b"\x89PNG" for r, m, b in seen)


def test_title_strip_is_top_zone(tmp_path):
    pdf = _shape_title_pdf(tmp_path / "lec.pdf", 1)
    pix = pymupdf.Pixmap(vt.title_strip(pdf, 1, dpi=72))
    page = pymupdf.open(pdf)[0].rect
    assert abs(pix.height - page.height * vt.TITLE_ZONE) <= 2 and abs(pix.width - page.width) <= 2


def test_saved_titles_roundtrip_and_used_by_load_chunks(tmp_path, monkeypatch):
    """build_index가 저장한 titles.json을 출제 쪽(load_chunks)도 그대로 쓴다 → 인덱스와 청크 제목이 같다."""
    course = tmp_path / "c1"
    (course / "lectures").mkdir(parents=True)
    _shape_title_pdf(course / "lectures" / "lec.pdf")
    index_dir = tmp_path / "index"
    vt.save(index_dir, {"lec.pdf": {1: "Boolean Algebra", 3: "Half Adder"}}, "m")
    assert vt.load_saved(index_dir) == {"lec.pdf": {1: "Boolean Algebra", 3: "Half Adder"}}

    monkeypatch.setattr("qgen.ingest.default_index_dir", lambda course_id: index_dir)
    monkeypatch.setattr(llm, "call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("모델을 부르면 안 됨")))
    assert [p.title for p in parse_lectures(course, verbose=False)[0].pages] == \
        ["Boolean Algebra", "Boolean Algebra", "Half Adder"]
    assert [c.title for c in load_chunks(course, verbose=False)] == ["Boolean Algebra", "Boolean Algebra", "Half Adder"]


def test_parse_pdf_marks_title_from_text(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 60), "Web Caching", fontsize=24)
    doc.new_page().insert_text((50, 400), "only body text here, long enough", fontsize=12)
    doc.save(tmp_path / "t.pdf")
    p1, p2 = parse_pdf(tmp_path / "t.pdf").pages
    assert p1.title_from_text and not p2.title_from_text and p2.title == "Web Caching"
