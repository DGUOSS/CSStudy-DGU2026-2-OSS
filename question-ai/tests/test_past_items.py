import pymupdf

from qgen import exam_profile as ep
from qgen.schemas import ExamProfile, PastItem, PlannedItem

EXAM = """중간고사 (풀이 과정 필수)
1. 다음 부울식을 간소화하시오. (10%)
F = A'B + AB
2. 아래 상태도를 보고 JK 플립플롭으로 회로를 설계하시오. (20%)
단, 최소 비용의 식이어야 함.
3. RAM과 flash memory의 차이점을 세 가지 기술하시오. (6%)
"""


def _course(tmp_path, with_image: bool = False):
    d = tmp_path / "c1"
    (d / "past_exams").mkdir(parents=True)
    (d / "past_exams" / "a.md").write_text(EXAM, encoding="utf-8")
    if with_image:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40), False)
        pix.set_rect(pix.irect, (10, 10, 200))
        pix.save(d / "past_exams" / "b.png")
    return d


def _profile(items: list[PastItem]) -> ExamProfile:
    return ExamProfile(course="c", format_ratio={"계산형": 0.5, "서술형": 0.5}, num_questions=3,
                       detail_level="중간", difficulty="보통", recurring_patterns=[], phrasing_examples=[],
                       emphasized_topics=[], evidence=["[E1.2] 간소화"], past_items=items)


def _item(qtype: str, refs: list[str] | None = None) -> PlannedItem:
    return PlannedItem(item_id="q1", qtype=qtype, topic="t", bloom_level="적용", difficulty="보통", points=10,
                       rationale="r", past_refs=refs or [])


P1 = PastItem(item_id="P1", number="1", qtype="계산형", topic="부울식 간소화", points="10%", refs=["E1.2", "E1.3"])
P2 = PastItem(item_id="P2", number="2", qtype="계산형", topic="JK 플립플롭 설계", points="20%", refs=["E1.4", "E1.5"])
P3 = PastItem(item_id="P3", number="3", qtype="서술형", topic="RAM과 flash", points="6%", refs=["E1.6"])


def test_text_is_cut_from_original_lines(tmp_path):
    inp = ep.build_input(_course(tmp_path))
    assert ep.past_item_text(P2, inp) == "2. 아래 상태도를 보고 JK 플립플롭으로 회로를 설계하시오. (20%)\n단, 최소 비용의 식이어야 함."
    assert ep.past_item_text(P3, inp) == "3. RAM과 flash memory의 차이점을 세 가지 기술하시오. (6%)"
    # 범위가 지나치게 크면 상한까지만
    huge = P1.model_copy(update={"refs": ["E1.1", "E1.999"]})
    assert len(ep.past_item_text(huge, inp).splitlines()) == 6  # 실제 줄은 6개뿐 (없는 번호는 건너뜀)


def test_validate_catches_bad_refs_and_duplicate_ids(tmp_path):
    inp = ep.build_input(_course(tmp_path))
    assert ep.validate(_profile([P1, P2, P3]), inp) == []
    bad = PastItem(item_id="P1", number="9", qtype="서술형", topic="x", refs=["E1.99"])
    issues = ep.validate(_profile([P1, bad]), inp)
    assert any("겹침" in i for i in issues) and any("E1.99" in i for i in issues)
    assert any("비어" in i for i in ep.past_item_issues(_profile([bad.model_copy(update={"refs": []})]), inp))


def test_select_prefers_planner_refs_then_same_type():
    prof = _profile([P1, P2, P3])
    assert ep.select_past_items(_item("서술형", ["P2"]), prof) == ([P2], [])
    chosen, warns = ep.select_past_items(_item("계산형", ["P9"]), prof)
    assert chosen == [P1, P2] and "P9" in warns[0]  # 없는 번호 → 같은 유형
    assert ep.select_past_items(_item("계산형", ["P1", "P2", "P3"]), prof)[0] == [P1, P2]  # 최대 2개
    assert ep.select_past_items(_item("객관식"), prof)[0] == []


def test_format_examples_attaches_figure_images(tmp_path):
    inp = ep.build_input(_course(tmp_path, with_image=True))
    assert inp.image_ids == ["E2.p1"]
    p2 = P2.model_copy(update={"refs": ["E1.4", "E1.5", "E2.p1"]})
    text, images = ep.format_past_examples([p2, P3], inp)
    assert text.startswith("### 기출 2번 (계산형, 20%) — JK 플립플롭 설계\n2. 아래 상태도")
    assert "이미지 1장을 첨부" in text and "### 기출 3번 (서술형, 6%)" in text
    assert len(images) == 1 and images[0][1] == "image/jpeg"


def test_old_profile_without_past_items_still_loads():
    old = '{"course":"c","format_ratio":{"서술형":1.0},"num_questions":1,"detail_level":"중간","difficulty":"보통",' \
          '"recurring_patterns":[],"phrasing_examples":[],"emphasized_topics":[]}'
    assert ExamProfile.model_validate_json(old).past_items == []


def test_copy_issues_catches_copied_sentences_only():
    from qgen.checks import copy_issues, overlap
    from qgen.schemas import Question, SourceRef

    past = [("3번", "3. RAM과 flash memory의 차이점을 세 가지 기술하시오. (6%)")]

    def q(stem):
        return Question(item_id="q1", qtype="서술형", stem=stem, answer="a", sources=[SourceRef(file="a.pdf", page=1)])

    copied = q("RAM과 flash memory의 차이점을 세 가지 기술하시오.")
    other = q("캐시 메모리의 쓰기 정책 두 가지를 비교하고 장단점을 설명하시오.")
    assert overlap(copied.stem, past[0][1]) > 0.9
    assert copy_issues(copied, past) and "기출 3번" in copy_issues(copied, past)[0]
    assert copy_issues(other, past) == []
    assert copy_issues(copied, []) == []  # 기출 문항 목록이 없으면 검사 안 함


def test_reviewer_gets_past_examples_appended(monkeypatch):
    from qgen import agents, llm
    from qgen.schemas import Question, Review, SolverOutput, SourceRef

    seen = []
    monkeypatch.setattr(llm, "call", lambda role, p, schema, **k: seen.append(p) or Review(
        item_id="", verdict="pass", answer_match="일치", grounded=True, profile_fit=True, issues=[], feedback=""))
    q = Question(item_id="q1", qtype="서술형", stem="s", answer="a", sources=[SourceRef(file="a.pdf", page=1)])
    s = SolverOutput(item_id="q1", reasoning="r", answer="a", confidence=0.9, is_ambiguous=False)
    agents.reviewer(q, s, _item("서술형"), [], _profile([]), past_examples="### 기출 6번\n원문")
    agents.reviewer(q, s, _item("서술형"), [], _profile([]))
    assert seen[0].endswith("### 기출 6번\n원문") and "기출 예시 (출제자가" not in seen[1]
    assert "{{" not in seen[0]
