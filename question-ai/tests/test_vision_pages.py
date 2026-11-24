import pymupdf

from qgen import llm
from qgen.ingest import load_chunks, parse_lectures
from qgen.ingest import vision_pages as vp
from qgen.ingest.pdf_parser import parse_pdf

BODY = "Half adder adds two bits and produces sum and carry outputs."


def _pdf(path):
    """1: 글 충분, 2: 글자 없음(그림 쪽 흉내), 3: 글 충분."""
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 100), BODY)
    doc.new_page()
    doc.new_page().insert_text((50, 100), BODY)
    doc.save(path)
    return path


def test_targets_are_pages_that_need_image(tmp_path):
    rep = parse_pdf(_pdf(tmp_path / "a.pdf"))
    assert vp.targets(rep) == [2]


def test_apply_appends_and_unblocks_low_text_page(tmp_path):
    rep = parse_pdf(_pdf(tmp_path / "a.pdf"))
    assert rep.pages[1].low_text
    vp.apply_page_texts(rep, {2: "Half Adder\nx y | c s\n0 0 | 0 0", 3: ""})
    p2 = rep.pages[1]
    assert p2.text.startswith(vp.MARK) and "x y | c s" in p2.text and not p2.low_text
    assert vp.MARK not in rep.pages[2].text  # 빈 결과는 붙이지 않음
    vp.apply_page_texts(rep, {2: "Half Adder\nx y | c s\n0 0 | 0 0"})
    assert p2.text.count(vp.MARK) == 1  # 두 번 붙이지 않음


def test_read_pages_sends_full_page_png(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path / "a.pdf")
    seen = []

    def fake(role, prompt, schema, images=None, **k):
        seen.append((role, images[0][1], images[0][0][:4]))
        return schema(text="  State Table\nA B | A+ B+  ")

    monkeypatch.setattr(llm, "call", fake)
    assert vp.read_pages(pdf, [2], verbose=False) == {2: "State Table\nA B | A+ B+"}
    assert seen == [(vp.ROLE, "image/png", b"\x89PNG")]


def test_saved_page_texts_make_chunks_in_load_chunks(tmp_path, monkeypatch):
    """build_index가 저장한 page_texts.json을 출제 쪽(load_chunks)도 써서, 빠져 있던 쪽이 청크가 된다."""
    course = tmp_path / "c1"
    (course / "lectures").mkdir(parents=True)
    _pdf(course / "lectures" / "a.pdf")
    index_dir = tmp_path / "index"
    monkeypatch.setattr("qgen.ingest.default_index_dir", lambda course_id: index_dir)
    monkeypatch.setattr(llm, "call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("모델을 부르면 안 됨")))

    assert [c.source.page for c in load_chunks(course, verbose=False)] == [1, 3]  # 읽기 전: 2쪽 없음
    vp.save(index_dir, {"a.pdf": {2: "State Assignment\nS0 = 00, S1 = 01, S2 = 10"}}, "m")
    assert vp.load_saved(index_dir) == {"a.pdf": {2: "State Assignment\nS0 = 00, S1 = 01, S2 = 10"}}
    chunks = load_chunks(course, verbose=False)
    assert [c.source.page for c in chunks] == [1, 2, 3]
    assert "S1 = 01" in chunks[1].text
    assert parse_lectures(course, verbose=False, page_texts={})[0].pages[1].low_text  # 빈 dict를 주면 적용 안 함
