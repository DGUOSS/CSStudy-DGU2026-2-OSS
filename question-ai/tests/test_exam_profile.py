import json
from pathlib import Path

import pymupdf
import pytest

from qgen import exam_profile, llm
from qgen.exam_profile import build_input, default_profile, validate
from qgen.schemas import ExamProfile


def _profile(**kw) -> ExamProfile:
    base = dict(course="c", format_ratio={"객관식": 0.5, "서술형": 0.5}, num_questions=4, detail_level="중간",
                difficulty="보통", recurring_patterns=[], phrasing_examples=[], emphasized_topics=[], evidence=[])
    return ExamProfile(**{**base, **kw})


def _photo(path: Path, w: int = 3000, h: int = 2000) -> Path:
    """큰 '휴대폰 사진' 흉내 (빨간 사각형 PNG)."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
    pix.set_rect(pix.irect, (220, 40, 40))
    pix.save(path)
    return path


@pytest.fixture
def course(tmp_path):
    d = tmp_path / "c1"
    (d / "past_exams").mkdir(parents=True)
    (d / "past_exams" / "a.md").write_text("중간고사\n\n1. (객관식, 5점) HTTP는?\n2. (서술형, 15점) 쿠키와 세션 비교\n",
                                           encoding="utf-8")
    (d / "notes.md").write_text("- 서술형 비중 큼\n\n- 계산 문제 없음\n", encoding="utf-8")
    return d


def test_numbering(course):
    inp = build_input(course)
    assert "[E1.1] 중간고사" in inp.past_text and "[E1.3] 2. (서술형, 15점)" in inp.past_text
    assert inp.notes_text.splitlines() == ["[M1] - 서술형 비중 큼", "[M2] - 계산 문제 없음"]
    assert inp.valid_ids == {"E1.1", "E1.2", "E1.3", "M1", "M2"}
    assert inp.has_data and inp.images == []


def test_photo_exam_is_sent_as_small_jpeg(course):
    _photo(course / "past_exams" / "b.png")
    (course / "past_exams" / "Thumbs.db").write_bytes(b"x")  # 무시
    (course / "past_exams" / "c.hwp").write_bytes(b"x")  # 지원 안 함 → 경고
    inp = build_input(course)
    assert inp.image_ids == ["E2.p1"] and "E2.p1" in inp.valid_ids
    data, mime = inp.images[0]
    assert mime == "image/jpeg" and data[:2] == b"\xff\xd8"  # JPEG
    with pymupdf.open(stream=data, filetype="jpeg") as d:
        assert max(d[0].rect.width, d[0].rect.height) <= exam_profile.MAX_SIDE + 1
    assert len(inp.warnings) == 1 and "c.hwp" in inp.warnings[0]


def test_pdf_page_with_figure_or_no_text_becomes_image(course):
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 80), "1. (객관식) Which status code means Not Found?", fontsize=12)
    doc.new_page()  # 스캔본처럼 글자 없는 쪽
    doc.save(course / "past_exams" / "b.pdf")
    inp = build_input(course)
    assert inp.image_ids == ["E2.p2"]
    assert any(i.startswith("E2.") and not i.startswith("E2.p") for i in inp.valid_ids)  # 1쪽 글자 줄 번호


def test_max_images(course):
    for k in range(4):
        _photo(course / "past_exams" / f"p{k}.png", 50, 50)
    inp = build_input(course, max_images=2)
    assert len(inp.images) == 2 and inp.image_ids == ["E2.p1", "E3.p1"]
    assert "E4.p1" not in inp.valid_ids and "2장만" in inp.warnings[-1]


def test_no_data_uses_default_without_llm(tmp_path, monkeypatch):
    from qgen import agents

    monkeypatch.setattr(agents, "analyst", lambda *a, **k: pytest.fail("LLM을 부르면 안 됨"))
    (tmp_path / "empty" / "lectures").mkdir(parents=True)
    prof, issues, inp = exam_profile.make(tmp_path / "empty", "empty")
    assert not inp.has_data and issues == []
    assert prof.format_ratio == {"객관식": 0.4, "단답형": 0.2, "서술형": 0.4} and prof.num_questions == 10
    assert prof.evidence == [] and prof.emphasized_topics == []


def test_validate_evidence_ids(course):
    inp = build_input(course)
    ok = _profile(evidence=["[E1.3] 서술형 15점", "[M1][M2] 서술형 비중, 계산 없음",
                            "[E1.2, E1.3] 한 괄호에 여러 번호 (실제 Gemini 출력 형식)"])
    assert validate(ok, inp) == []
    # 근거 번호가 아닌 대괄호(예: 문항 속 [보기])는 번호로 치지 않는다
    assert exam_profile.evidence_ids("[보기] 참고, [M1] 메모") == ["M1"]
    bad = _profile(evidence=["기출 3번: 서술형", "[E1.9] 없는 줄", "[M7] 없는 메모"])
    issues = validate(bad, inp)
    assert any("번호가 없는" in i for i in issues)
    assert any("E1.9" in i for i in issues) and any("M7" in i for i in issues)
    assert any("비어 있음" in i for i in validate(_profile(evidence=[]), inp))


def test_validate_ratio_and_counts():
    assert validate(_profile()) == []
    issues = validate(_profile(format_ratio={"객관식": 0.5, "OX": 0.3}, num_questions=0))
    assert any("알 수 없는 유형" in i for i in issues)
    assert any("합이 0.80" in i for i in issues)
    assert any("1~50" in i for i in issues)
    # 기출·메모 없이 근거를 지어낸 경우
    empty = exam_profile.AnalystInput()
    assert any("지어낸 근거" in i for i in validate(_profile(evidence=["[E1.1] x"]), empty))
    assert validate(default_profile("c")) == []


def test_llm_image_message_and_cache_key():
    text_msgs = [{"role": "user", "content": llm.user_content("문제", None)}]
    assert text_msgs[0]["content"] == "문제"  # 이미지 없으면 예전과 같은 메시지 → 기존 캐시 유지
    assert llm._cache_view(text_msgs) == text_msgs
    content = llm.user_content("문제", [(b"\xff\xd8abc", "image/jpeg")])
    assert content[0] == {"type": "text", "text": "문제"}
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    view = llm._cache_view([{"role": "user", "content": content}])
    s = json.dumps(view)
    assert "base64" not in s and "image_sha256" in s
