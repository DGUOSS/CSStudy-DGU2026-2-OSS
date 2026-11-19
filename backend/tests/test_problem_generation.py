"""Automatic quiz replenishment without live LLM calls."""

from fastapi import BackgroundTasks
from sqlmodel import select

from app.core.config import settings
from app.features.problems.generation import (
    generate_for_course,
    schedule_if_low,
    unanswered_count,
)
from app.models import Attempt, Material, Problem, ProblemConcept
from app.qgen.schemas import Question, Review, SolverOutput, SourceRef


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
            sources=[SourceRef(file=f"material-{material.id}", page=1)],
        )

    monkeypatch.setattr(generation.agents, "generator", fake_generator)
    monkeypatch.setattr(
        generation.agents,
        "solver",
        lambda q, chunks: SolverOutput(
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
        lambda q, s, item, chunks, profile: Review(
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
    assert session.exec(
        select(ProblemConcept).where(ProblemConcept.problem_id == generated[0].id)
    ).all()
