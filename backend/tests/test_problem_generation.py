"""자동 문제 보충. 실제 모델은 부르지 않는다(_parse를 가짜로 바꾼다)."""

import importlib

import pytest
from fastapi import BackgroundTasks
from qgen.schemas import Chunk, ExamProfile, PlannedItem, Review, SolverOutput, SourceRef
from sqlmodel import select

from app.core.config import settings
from app.features.problems import generation as g
from app.features.problems.generation import (
    SiteQuestion,
    generate_for_course,
    normalize,
    schedule_if_low,
    site_issues,
    unanswered_count,
)
from app.models import Attempt, Material, Problem, ProblemConcept

PAGE = "포인터의 개념\n포인터는 메모리 주소를 저장하는 변수이다. 역참조 연산자로 해당 주소의 값을 읽는다."
EVIDENCE = "포인터는 메모리 주소를 저장하는 변수이다."
# 가짜 출제가 문항마다 다른 근거를 쓰도록(같은 근거 재사용은 탈락) 쪽에 번호 붙은 문장을 더 둔다
RULES = [f"포인터 규칙 {k}번은 주소 연산을 설명한다." for k in range(1, 21)]
PAGE += "\n" + "\n".join(RULES)


def _qgen_llm_importable() -> bool:
    """question-ai가 설정·프롬프트를 패키지 데이터로 넣기 전에는 git 설치본에서 qgen.llm import가 실패한다."""
    try:
        importlib.import_module("qgen.llm")
    except Exception:
        return False
    return True


needs_qgen_prompts = pytest.mark.skipif(
    not _qgen_llm_importable(),
    reason="qgen.llm을 불러올 수 없음(question-ai 패키지 데이터 수정 전)",
)


def test_replenishment_threshold_counts_distinct_user_attempts(
    session, course_with_problems, monkeypatch
):
    data = course_with_problems
    course_id, ch = data["course"].id, data["chapter"].id
    user_id = 42
    _link_lecture(session, data)
    assert unanswered_count(session, course_id, user_id, ch) == 3
    tasks = BackgroundTasks()
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    schedule_if_low(tasks, session, course_id, user_id, ch)
    assert len(tasks.tasks) == 0

    for _ in range(2):  # 같은 문제를 두 번 풀어도 한 문제
        session.add(
            Attempt(
                user_id=user_id, problem_id=data["problems"][0].id, chosen_index=0, correct=False
            )
        )
    session.commit()
    assert unanswered_count(session, course_id, user_id, ch) == 2
    schedule_if_low(tasks, session, course_id, user_id, ch)
    assert len(tasks.tasks) == 1


def _link_lecture(session, data):
    """챕터에 승인 교안을 붙인다(보충은 교안이 연결된 단원만)."""
    from app.models import Material

    m = Material(
        course_id=data["course"].id,
        kind="lecture",
        title="교안",
        filename="l.pdf",
        page_count=1,
        pages=["포인터 설명"],
        status="approved",
    )
    session.add(m)
    session.flush()
    ch = data["chapter"]
    ch.material_id = m.id
    session.add(ch)
    session.commit()
    return m


def test_chapter_runs_out_while_course_has_many_left(session, course_with_problems, monkeypatch):
    """강좌 전체에 안 푼 문제가 많아도, 푸는 단원이 떨어지면 그 단원을 보충한다(예전 버그)."""
    from app.models import Chapter, Concept, Problem, ProblemConcept

    data = course_with_problems
    cid, ch = data["course"].id, data["chapter"]
    _link_lecture(session, data)
    other = Chapter(course_id=cid, order=2, title="다른 단원")
    session.add(other)
    session.flush()
    k = Concept(chapter_id=other.id, name="Z")
    session.add(k)
    session.flush()
    for i in range(10):  # 다른 단원에 안 푼 문제 10개
        p = Problem(
            chapter_id=other.id,
            question=f"q{i}",
            choices=["1", "2", "3", "4"],
            answer_index=1,
            explanation="e",
        )
        session.add(p)
        session.flush()
        session.add(ProblemConcept(problem_id=p.id, concept_id=k.id))
    session.add(
        Attempt(user_id=42, problem_id=data["problems"][0].id, chosen_index=0, correct=False)
    )
    session.commit()
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    assert unanswered_count(session, cid, 42) == 12  # 강좌 전체로는 많음
    tasks = BackgroundTasks()
    schedule_if_low(tasks, session, cid, 42, ch.id)
    assert len(tasks.tasks) == 1 and tasks.tasks[0].args == (cid, 42, ch.id)
    tasks2 = BackgroundTasks()
    schedule_if_low(tasks2, session, cid, 42, other.id)  # 다른 단원은 아직 충분 + 교안 없음
    assert len(tasks2.tasks) == 0


def test_chapter_without_lecture_does_not_reserve(session, course_with_problems, monkeypatch):
    data = course_with_problems
    cid, ch = data["course"].id, data["chapter"].id
    for p in data["problems"]:
        session.add(Attempt(user_id=42, problem_id=p.id, chosen_index=0, correct=False))
    session.commit()
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    tasks = BackgroundTasks()
    schedule_if_low(tasks, session, cid, 42, ch)
    assert len(tasks.tasks) == 0 and ch not in g._guards


def test_initial_fill_only_empty_chapters_with_cap(session, course_with_problems, monkeypatch):
    from app.models import Chapter

    data = course_with_problems
    cid = data["course"].id
    empty = Chapter(course_id=cid, order=2, title="빈 단원")
    session.add(empty)
    session.commit()
    calls = []

    class Rep:
        saved = 3

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(
        g, "generate_for_course", lambda s, c, u, ch, n: calls.append((ch, n)) or Rep()
    )
    assert g.fill_new_chapters(session.get_bind(), [data["chapter"].id, empty.id]) == 3
    assert calls == [(empty.id, g.INITIAL_SIZE)]  # 문제가 이미 있는 단원은 건너뜀
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert g.fill_new_chapters(session.get_bind(), [empty.id]) == 0  # 키 없으면 안 돎


# ---------- 생성 흐름(가짜 모델) ----------


def _with_material(session, data):
    material = Material(
        course_id=data["course"].id,
        kind="lecture",
        title="포인터 교안",
        filename="pointer.pdf",
        pages=[PAGE],
    )
    session.add(material)
    session.flush()
    data["chapter"].material_id = material.id
    session.add(data["chapter"])
    session.commit()
    return material


def _question(n: int, concepts: list[str], evidence: str | None = None) -> SiteQuestion:
    evidence = RULES[(n - 1) % len(RULES)] if evidence is None else evidence
    return SiteQuestion(
        item_id="x",
        qtype="객관식",
        stem=f"포인터에 대한 설명 {n}은?",
        choices=["주소를 저장한다", "파일을 저장한다", "프로세스를 저장한다", "없다"],
        answer="1",
        explanation="포인터는 주소를 저장한다.",
        evidence=evidence,
        concepts=concepts,
        sources=[SourceRef(file="pointer.pdf", page=1)],
    )


class FakeModel:
    """schema별로 응답을 돌려주고, 받은 프롬프트를 기록한다(services/llm._parse 자리)."""

    def __init__(self, questions, verdict="pass"):
        self.questions = questions  # n(몇 번째 출제) -> SiteQuestion
        self.verdict = verdict
        self.prompts: list[tuple[str, str]] = []
        self.generated = 0

    def __call__(self, system, prompt, schema, model=None):
        self.prompts.append((schema.__name__, prompt))
        if schema is SiteQuestion:
            self.generated += 1
            return self.questions(self.generated)
        if schema is SolverOutput:
            return SolverOutput(
                item_id="x", reasoning="교안", answer="1", confidence=1.0, is_ambiguous=False
            )
        return Review(
            item_id="x",
            verdict=self.verdict,
            answer_match="일치",
            grounded=True,
            profile_fit=True,
            issues=[] if self.verdict == "pass" else ["근거 없음"],
            feedback="",
        )


@pytest.fixture
def fake_prompts(monkeypatch):
    """qgen.llm 없이도 돌도록 원래 프롬프트 자리를 표시만 한다."""
    monkeypatch.setattr(g, "render_prompt", lambda name, **v: f"<{name}>{v.get('revise', '')}")

    def solver(q, chunks):  # qgen.agents.strip_answer 도 qgen.llm 을 불러서 대신한다
        s = g._call("solver", "<solver>", SolverOutput)
        s.item_id = q.item_id
        return s

    monkeypatch.setattr(g, "solver", solver)


def test_generation_saves_reviewed_questions_with_source_and_concept(
    session, course_with_problems, monkeypatch, fake_prompts
):
    data = course_with_problems
    material = _with_material(session, data)
    model = FakeModel(lambda n: _question(n, ["B"]))
    monkeypatch.setattr(g, "_parse", model)

    report = generate_for_course(session, data["course"].id, 42)

    assert report.saved == 5, [it.reason for it in report.items]
    generated = session.exec(select(Problem).where(Problem.origin == "llm")).all()
    assert len(generated) == 5
    assert all(p.source_material_id == material.id and p.source_page == 1 for p in generated)
    assert all(p.answer_index == 0 and p.evidence in RULES for p in generated)
    assert len({p.evidence for p in generated}) == 5  # 문항마다 다른 근거
    for p in generated:
        links = session.exec(select(ProblemConcept).where(ProblemConcept.problem_id == p.id)).all()
        assert [link.concept_id for link in links] == [data["b"].id]  # 첫 번째 개념(A)이 아님
    # 같은 순서: 출제 → 블라인드 풀이 → 검토. 원래 프롬프트 뒤에 사이트 지시가 붙는다
    assert [name for name, _ in model.prompts[:3]] == ["SiteQuestion", "SolverOutput", "Review"]
    gen_prompt = model.prompts[0][1]
    assert gen_prompt.startswith("<generator>") and "개념 목록:\n- A\n- B" in gen_prompt
    assert model.prompts[2][1].startswith("<reviewer>") and "concepts" in model.prompts[2][1]


def test_unlisted_concept_is_sent_back_for_revision(
    session, course_with_problems, monkeypatch, fake_prompts
):
    data = course_with_problems
    _with_material(session, data)
    # 홀수 번째 출제는 목록에 없는 이름, 그 수정본은 정확한 이름
    model = FakeModel(lambda n: _question(n, ["포인터 개념"] if n % 2 else ["B"]))
    monkeypatch.setattr(g, "_parse", model)

    report = generate_for_course(session, data["course"].id, 42)

    assert report.saved == 5
    assert all(it.history == ["규칙위반(1)", "pass(일치)"] for it in report.items)
    revise = [p for name, p in model.prompts if name == "SiteQuestion" and "수정 모드" in p]
    assert revise and "개념 목록에 없는 이름" in revise[0]


def test_never_valid_concept_is_not_saved(session, course_with_problems, monkeypatch, fake_prompts):
    data = course_with_problems
    _with_material(session, data)
    monkeypatch.setattr(g, "_parse", FakeModel(lambda n: _question(n, [])))

    report = generate_for_course(session, data["course"].id, 42)

    assert report.saved == 0
    assert all("concepts가 비어 있음" in it.reason for it in report.items)
    assert session.exec(select(Problem).where(Problem.origin == "llm")).all() == []


def test_reviewer_reject_is_not_saved(session, course_with_problems, monkeypatch, fake_prompts):
    data = course_with_problems
    _with_material(session, data)
    monkeypatch.setattr(g, "_parse", FakeModel(lambda n: _question(n, ["A"]), verdict="reject"))

    report = generate_for_course(session, data["course"].id, 42)

    assert report.saved == 0
    assert all(it.history == ["reject(일치)", "reject(일치)"] for it in report.items)  # 재출제 1번
    assert all(it.reason.startswith("검토 reject") for it in report.items)


def test_model_failure_is_reported(session, course_with_problems, monkeypatch, fake_prompts):
    data = course_with_problems
    _with_material(session, data)
    monkeypatch.setattr(g, "_parse", lambda *a, **k: None)

    report = generate_for_course(session, data["course"].id, 42)

    assert report.saved == 0
    assert all("모델 응답 없음" in it.reason for it in report.items)


def test_chapter_without_linked_material_is_skipped(session, course_with_problems):
    data = course_with_problems
    session.add(
        Material(
            course_id=data["course"].id,
            kind="lecture",
            title="다른 교안",
            filename="other.pdf",
            pages=[PAGE],
        )
    )
    session.commit()  # 강좌에 교안은 있지만 챕터에 연결되지 않음

    report = generate_for_course(session, data["course"].id, 42)

    assert report.saved == 0 and report.chapter_id is None


# ---------- 사이트 추가 검사 ----------


def _chunk() -> Chunk:
    return Chunk(
        chunk_id="p1", course_id="1", text=PAGE, source=SourceRef(file="pointer.pdf", page=1)
    )


def test_evidence_ignores_spacing_and_punctuation():
    assert normalize("포인터는 메모리주소를 저장하는 변수이다") in normalize(PAGE)
    assert normalize("포인터는  메모리 주소를, 저장하는 변수이다!") in normalize(PAGE)
    assert normalize("포인터는 파일을 저장한다") not in normalize(PAGE)
    assert normalize("  ...  ") == ""
    q = _question(1, ["A"], evidence="포인터는, 메모리 주소를 저장하는 변수이다!!")
    assert site_issues(q, [_chunk()], ["A", "B"]) == []


def test_paraphrased_or_short_evidence_is_rejected():
    q = _question(1, ["A"], evidence="포인터는 주소를 담는 변수다.")
    assert any("강의자료에 없음" in i for i in site_issues(q, [_chunk()], ["A"]))
    q = _question(1, ["A"], evidence="포인터")
    assert any("너무 짧음" in i for i in site_issues(q, [_chunk()], ["A"]))


def test_same_evidence_or_stem_as_existing_is_rejected():
    q = _question(1, ["A"], evidence=EVIDENCE)
    existing = [("다른 문제", normalize("포인터는 메모리 주소를, 저장하는 변수이다"))]
    assert any("같은 근거 문장" in i for i in site_issues(q, [_chunk()], ["A"], existing))
    existing = [(q.stem, normalize("다른 근거 문장입니다"))]
    assert "이미 있는 문항과 본문이 같음" in site_issues(q, [_chunk()], ["A"], existing)
    assert site_issues(q, [_chunk()], ["A"], [("다른 문제", normalize(RULES[5]))]) == []


def test_latex_dollar_is_rejected():
    q = _question(1, ["A"])
    q.choices = ["$\\%c$ - 문자", "%s - 문자열", "%d - 정수", "%f - 실수"]
    assert any("LaTeX" in i for i in site_issues(q, [_chunk()], ["A"]))


def test_seed_problem_evidence_blocks_repeat(
    session, course_with_problems, monkeypatch, fake_prompts
):
    """챕터의 기존 문제와 같은 근거로 낸 문항은 수정 요청을 받고, 프롬프트에 기존 문항이 보인다."""
    data = course_with_problems
    _with_material(session, data)
    data["problems"][0].evidence = RULES[0]
    session.add(data["problems"][0])
    session.commit()
    model = FakeModel(lambda n: _question(n, ["A"]))
    monkeypatch.setattr(g, "_parse", model)

    report = generate_for_course(session, data["course"].id, 42)

    assert report.items[0].history[0] == "규칙위반(1)"  # 1번째 출제가 RULES[0]을 씀
    assert RULES[0] not in {
        p.evidence for p in session.exec(select(Problem).where(Problem.origin == "llm"))
    }
    assert "## 이미 있는 문항" in model.prompts[0][1] and "- q" in model.prompts[0][1]


def test_evidence_page_must_be_cited():
    q = _question(1, ["A"])
    q.sources = [SourceRef(file="pointer.pdf", page=2)]
    assert "evidence가 있는 쪽이 sources에 없음" in site_issues(q, [_chunk()], ["A"])


def test_concepts_must_match_list_exactly():
    chunk = _chunk()
    assert any("목록에 없는" in i for i in site_issues(_question(1, ["a"]), [chunk], ["A"]))
    assert any("목록에 없는" in i for i in site_issues(_question(1, ["A "]), [chunk], ["A"]))
    assert any("중복" in i for i in site_issues(_question(1, ["A", "A"]), [chunk], ["A"]))
    assert site_issues(_question(1, ["A", "B"]), [chunk], ["A", "B"]) == []


def test_qgen_rule_checks_still_apply():
    item = PlannedItem(
        item_id="x",
        qtype="객관식",
        topic="포인터",
        bloom_level="이해",
        difficulty="보통",
        points=1,
        rationale="t",
    )
    q = _question(1, ["A"])
    q.choices = ["a", "a", "b", "c"]  # qgen.checks.run 이 잡는 규칙
    assert "중복된 선지가 있음" in g.all_issues(q, item, [_chunk()], ["A"])


@needs_qgen_prompts
def test_real_qgen_prompts_get_site_instructions(monkeypatch):
    item = g.plan_items(["A", "B"], "포인터", 1)[0]
    profile = ExamProfile(
        course="1",
        format_ratio={"객관식": 1.0},
        num_questions=1,
        detail_level="중간",
        difficulty="보통",
        recurring_patterns=[],
        phrasing_examples=[],
        emphasized_topics=[],
    )
    model = FakeModel(lambda n: _question(n, ["A"]))
    monkeypatch.setattr(g, "_parse", model)

    q = g.generator(item, [_chunk()], profile, "", ["A", "B"])
    g.solver(q, [_chunk()])

    gen_prompt, solver_prompt = model.prompts[0][1], model.prompts[1][1]
    assert "너는 출제자다" in gen_prompt and "개념 목록:\n- A\n- B" in gen_prompt
    question_part = solver_prompt.split("## 강의자료")[0]
    assert (
        EVIDENCE not in question_part and '"answer"' not in question_part
    )  # 풀이자에게 정답·근거 없음


# ---------- 비용 상한 ----------


def _low_stock(session, data, user_id=42):
    _link_lecture(session, data)
    for p in data["problems"][:1]:
        session.add(Attempt(user_id=user_id, problem_id=p.id, chosen_index=0, correct=False))
    session.commit()


def test_cost_guard_cooldown_gap_and_daily_limit(session, course_with_problems, monkeypatch):
    """실패하면 1시간 쉬고, 성공해도 10분 간격, 하루 5번까지만 생성을 시작한다."""
    data = course_with_problems
    cid, ch = data["course"].id, data["chapter"].id
    _low_stock(session, data)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    clock = {"t": 1_795_568_400.0}  # 2026-11-25 01:00 UTC(하루 안에서 시험)
    monkeypatch.setattr(g, "_now", lambda: clock["t"])

    def start():
        tasks = BackgroundTasks()
        schedule_if_low(tasks, session, cid, 42, ch)
        return len(tasks.tasks)

    assert start() == 1
    assert start() == 0  # 실행 중이면 또 시작하지 않음
    g._release(ch, 0)  # 저장 0개로 끝남(실패)
    clock["t"] += 30 * 60
    assert start() == 0  # 실패 후 1시간 안 됨
    clock["t"] += 31 * 60
    assert start() == 1  # 1시간 지나면 다시 시도
    g._release(ch, 3)  # 성공
    clock["t"] += 5 * 60
    assert start() == 0  # 성공해도 10분 간격
    for _ in range(3):  # 오늘 3번 더(합계 5번)
        clock["t"] += 11 * 60
        assert start() == 1
        g._release(ch, 2)
    clock["t"] += 11 * 60
    assert start() == 0  # 단원 하루 5번 한도
    clock["t"] += 24 * 60 * 60
    assert start() == 1  # 날이 바뀌면 다시


def test_background_failure_counts_as_failure(session, course_with_problems, monkeypatch):
    """생성 중 예외가 나도 실패로 기록해 1시간 쉰다(바로 다시 돌지 않는다)."""
    data = course_with_problems
    cid, ch = data["course"].id, data["chapter"].id
    _low_stock(session, data)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(g, "engine", session.get_bind())
    monkeypatch.setattr(
        g, "generate_for_course", lambda *a: (_ for _ in ()).throw(RuntimeError("x"))
    )
    tasks = BackgroundTasks()
    schedule_if_low(tasks, session, cid, 42, ch)
    g._replenish_background(cid, 42, ch)
    assert g._guards[ch].last_saved == 0 and g._guards[ch].running is False
    clock = g._guards[ch].last_at
    monkeypatch.setattr(g, "_now", lambda: clock + 20 * 60)
    tasks2 = BackgroundTasks()
    schedule_if_low(tasks2, session, cid, 42, ch)
    assert len(tasks2.tasks) == 0


def test_code_check_from_question_ai_blocks_wrong_answer():
    """question-ai의 코드 검산이 사이트 규칙 검사에도 들어간다: 적어 둔 계산 정답이 틀리면 규칙 위반."""
    from qgen import verify
    from qgen.schemas import Verification

    from app.features.problems import generation as g

    v_ok = Verification(kind="int_repr", value="-3", bits=8, repr="2s", expected="11111101")
    v_bad = Verification(kind="int_repr", value="-3", bits=8, repr="2s", expected="11111100")
    assert verify.run(_q_with([v_ok])).issues == []
    assert verify.run(_q_with([v_bad])).issues
    assert any("코드 검산" in i for i in g.qgen_verify.run(_q_with([v_bad])).issues)


def _q_with(vs):
    from qgen.schemas import Question

    return Question(
        item_id="1",
        qtype="mcq",
        stem="-3을 8비트 2의 보수로?",
        choices=["a", "b", "c", "d"],
        answer="1",
        sources=[],
        verifications=vs,
    )


def test_course_daily_cap_across_chapters(monkeypatch):
    """단원마다 따로 세도 강좌 전체 하루 한도(COURSE_DAILY_RUNS)는 넘지 않는다."""
    g.reset_guards()
    monkeypatch.setattr(g, "_now", lambda: 1_795_568_400.0)
    started = sum(g._reserve(7, chapter) for chapter in range(1, g.COURSE_DAILY_RUNS + 6))
    assert started == g.COURSE_DAILY_RUNS
