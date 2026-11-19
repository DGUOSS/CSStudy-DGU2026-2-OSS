"""Automatic quiz replenishment without live LLM calls."""

from fastapi import BackgroundTasks
from qgen.checks import normalize_evidence
from qgen.checks import run as check_question
from qgen.schemas import Chunk, PlannedItem, Question, Review, SolverOutput, SourceRef
from sqlmodel import select

from app.core.config import settings
from app.features.problems.generation import (
    generate_for_course,
    schedule_if_low,
    unanswered_count,
)
from app.models import Attempt, Material, Problem, ProblemConcept


def test_replenishment_threshold_counts_distinct_user_attempts(
    session, course_with_problems, monkeypatch
):
    data = course_with_problems
    course_id = data["course"].id
    user_id = 42
    assert unanswered_count(session, course_id, user_id) == 3
    tasks = BackgroundTasks()
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    schedule_if_low(tasks, session, course_id, user_id)
    assert len(tasks.tasks) == 0

    for _ in range(2):
        session.add(
            Attempt(
                user_id=user_id,
                problem_id=data["problems"][0].id,
                chosen_index=0,
                correct=False,
            )
        )
    session.commit()
    assert unanswered_count(session, course_id, user_id) == 2
    schedule_if_low(tasks, session, course_id, user_id)
    assert len(tasks.tasks) == 1


def test_generation_saves_reviewed_questions_with_source(
    session, course_with_problems, monkeypatch
):
    from app.features.problems import generation

    data = course_with_problems
    chapter = data["chapter"]
    material = Material(
        course_id=data["course"].id,
        kind="lecture",
        title="포인터 교안",
        filename="pointer.pdf",
        pages=[
            "포인터는 메모리 주소를 저장하는 변수이다. 역참조 연산자로 해당 주소의 값을 읽는다."
        ],
    )
    session.add(material)
    session.flush()
    chapter.material_id = material.id
    session.add(chapter)
    session.commit()

    calls = 0

    def fake_generator(item, chunks, profile, examples, **kwargs):
        nonlocal calls
        calls += 1
        return Question(
            item_id=item.item_id,
            qtype="객관식",
            stem=f"포인터에 대한 설명 {calls}은?",
            choices=["주소를 저장한다", "파일을 저장한다", "프로세스를 저장한다", "없다"],
            answer="1",
            explanation="포인터는 주소를 저장한다.",
            evidence="포인터는 메모리 주소를 저장하는 변수이다.",
            concepts=["B"],
            sources=[SourceRef(file=f"material-{material.id}", page=1)],
        )

    monkeypatch.setattr(generation.agents, "generator", fake_generator)
    monkeypatch.setattr(
        generation.agents,
        "solver",
        lambda q, chunks, **kwargs: SolverOutput(
            item_id=q.item_id,
            answer="1",
            reasoning="교안",
            confidence=1.0,
            is_ambiguous=False,
        ),
    )
    monkeypatch.setattr(
        generation.agents,
        "reviewer",
        lambda q, s, item, chunks, profile, **kwargs: Review(
            item_id=q.item_id,
            verdict="pass",
            answer_match="일치",
            grounded=True,
            profile_fit=True,
            issues=[],
            feedback="",
        ),
    )

    assert generate_for_course(session, data["course"].id, 42) == 5
    generated = session.exec(select(Problem).where(Problem.origin == "llm")).all()
    assert len(generated) == 5
    assert all(p.source_material_id == material.id and p.source_page == 1 for p in generated)
    assert all(p.answer_index == 0 and p.evidence in material.pages[0] for p in generated)
    links = session.exec(
        select(ProblemConcept).where(ProblemConcept.problem_id == generated[0].id)
    ).all()
    assert len(links) == 1
    assert links[0].concept_id == data["b"].id


def _low_stock(session, data, user_id=42):
    for p in data["problems"][:1]:
        session.add(Attempt(user_id=user_id, problem_id=p.id, chosen_index=0, correct=False))
    session.commit()


def test_cost_guard_cooldown_gap_and_daily_limit(session, course_with_problems, monkeypatch):
    """실패하면 1시간 쉬고, 성공해도 10분 간격, 하루 5번까지만 생성을 시작한다."""
    from app.features.problems import generation as g

    data = course_with_problems
    cid = data["course"].id
    _low_stock(session, data)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    clock = {"t": 1_795_568_400.0}  # 2026-11-25 01:00 UTC(하루 안에서 시험)
    monkeypatch.setattr(g, "_now", lambda: clock["t"])

    def start():
        tasks = BackgroundTasks()
        schedule_if_low(tasks, session, cid, 42)
        return len(tasks.tasks)

    assert start() == 1
    assert start() == 0  # 실행 중이면 또 시작하지 않음
    g._release(cid, 0)  # 저장 0개로 끝남(실패)
    clock["t"] += 30 * 60
    assert start() == 0  # 실패 후 1시간 안 됨
    clock["t"] += 31 * 60
    assert start() == 1  # 1시간 지나면 다시 시도
    g._release(cid, 3)  # 성공
    clock["t"] += 5 * 60
    assert start() == 0  # 성공해도 10분 간격
    for _ in range(3):  # 오늘 3번 더(합계 5번)
        clock["t"] += 11 * 60
        assert start() == 1
        g._release(cid, 2)
    clock["t"] += 11 * 60
    assert start() == 0  # 하루 5번 한도
    clock["t"] += 24 * 60 * 60
    assert start() == 1  # 날이 바뀌면 다시


def test_background_failure_counts_as_failure(session, course_with_problems, monkeypatch):
    """생성 중 예외가 나도 실패로 기록해 1시간 쉰다(바로 다시 돌지 않는다)."""
    from app.features.problems import generation as g

    data = course_with_problems
    cid = data["course"].id
    _low_stock(session, data)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(g, "engine", session.get_bind())
    monkeypatch.setattr(
        g, "generate_for_course", lambda *a: (_ for _ in ()).throw(RuntimeError("x"))
    )
    tasks = BackgroundTasks()
    schedule_if_low(tasks, session, cid, 42)
    g._replenish_background(cid, 42)
    assert g._guards[cid].last_saved == 0 and g._guards[cid].running is False
    clock = g._guards[cid].last_at
    monkeypatch.setattr(g, "_now", lambda: clock + 20 * 60)
    tasks2 = BackgroundTasks()
    schedule_if_low(tasks2, session, cid, 42)
    assert len(tasks2.tasks) == 0


def test_evidence_ignores_spacing_and_punctuation():
    _norm = normalize_evidence

    page = "포인터는 메모리 주소를 저장하는 변수이다. 역참조 연산자로 값을 읽는다."
    assert _norm("포인터는 메모리주소를 저장하는 변수이다") in _norm(page)
    assert _norm("포인터는  메모리 주소를, 저장하는 변수이다!") in _norm(page)
    assert _norm("포인터는 파일을 저장한다") not in _norm(page)
    assert _norm("  ...  ") == ""


def test_generator_rejects_missing_or_unlisted_concepts():
    source = SourceRef(file="lecture", page=1)
    chunk = Chunk(chunk_id="one", course_id="1", text="A pointer stores a memory address.", source=source)
    item = PlannedItem(
        item_id="one", qtype="객관식", topic="pointers", bloom_level="이해",
        difficulty="보통", points=1, rationale="practice",
    )
    question = Question(
        item_id="one", qtype="객관식", stem="What does a pointer store?",
        choices=["A memory address", "A file", "A process", "Nothing"],
        answer="1", explanation="It stores an address.",
        evidence="A pointer stores a memory address.", sources=[source],
        concepts=["not a chapter concept"],
    )
    assert any("개념" in issue for issue in check_question(question, item, [chunk], {"B"}))
    question.concepts = []
    assert any("개념" in issue for issue in check_question(question, item, [chunk], {"B"}))
    question.concepts = ["B"]
    assert not check_question(question, item, [chunk], {"B"})
