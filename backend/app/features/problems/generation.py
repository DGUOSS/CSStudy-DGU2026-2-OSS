"""Replenish a user's unanswered quiz pool using feat/question-generator agents."""

import logging
import re
from threading import Lock

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.features.exams.router import exam_style_examples
from app.models import Attempt, Chapter, Concept, Material, Problem, ProblemConcept
from app.qgen import agents, checks
from app.qgen.ingest import Retriever, topic_list
from app.qgen.schemas import Chunk, ExamProfile, PlannedItem, SourceRef

log = logging.getLogger(__name__)

LOW_STOCK = 2
REFILL_SIZE = 5
_locks_guard = Lock()
_course_locks: dict[int, Lock] = {}


def unanswered_count(session: Session, course_id: int, user_id: int) -> int:
    ids = list(
        session.exec(
            select(Problem.id)
            .join(Chapter, Problem.chapter_id == Chapter.id)
            .where(Chapter.course_id == course_id, Problem.qtype == "mcq")
        ).all()
    )
    if not ids:
        return 0
    answered = set(
        session.exec(
            select(Attempt.problem_id).where(
                Attempt.user_id == user_id,
                Attempt.problem_id.in_(ids),  # type: ignore[attr-defined]
            )
        ).all()
    )
    return sum(problem_id not in answered for problem_id in ids)


def schedule_if_low(
    background_tasks: BackgroundTasks, session: Session, course_id: int, user_id: int
) -> None:
    if settings.anthropic_api_key and unanswered_count(session, course_id, user_id) <= LOW_STOCK:
        background_tasks.add_task(_replenish_background, course_id, user_id)


def _lock_for(course_id: int) -> Lock:
    with _locks_guard:
        return _course_locks.setdefault(course_id, Lock())


def _replenish_background(course_id: int, user_id: int) -> None:
    # One process on the current Render service. The DB count is rechecked after
    # acquiring the lock, so repeated requests do not start repeated generations.
    with _lock_for(course_id):
        try:
            with Session(engine) as session:
                if unanswered_count(session, course_id, user_id) <= LOW_STOCK:
                    generate_for_course(session, course_id, user_id)
        except Exception:
            log.exception("Automatic problem generation failed for course %s", course_id)


def _lecture_chunks(material: Material, course_id: int) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"material-{material.id}-p{page}",
            course_id=str(course_id),
            text=text[:3000],
            source=SourceRef(file=f"material-{material.id}", page=page),
        )
        for page, text in enumerate(material.pages, start=1)
        if len(text.strip()) >= 20
    ]


def _source_material(session: Session, chapter: Chapter) -> Material | None:
    if chapter.material_id is not None:
        material = session.get(Material, chapter.material_id)
        if (
            material is not None
            and material.course_id == chapter.course_id
            and material.kind == "lecture"
            and material.status == "approved"
        ):
            return material
    return session.exec(
        select(Material)
        .where(
            Material.course_id == chapter.course_id,
            Material.kind == "lecture",
            Material.status == "approved",
            Material.replaced_by.is_(None),  # type: ignore[union-attr]
        )
        .order_by(Material.id.desc())
    ).first()


def _target(
    session: Session, course_id: int, user_id: int
) -> tuple[Chapter, Material, list[Chunk]] | None:
    chapters = list(
        session.exec(
            select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.order)
        ).all()
    )
    if not chapters:
        return None
    answered = set(session.exec(select(Attempt.problem_id).where(Attempt.user_id == user_id)).all())
    ranked = []
    for chapter in chapters:
        material = _source_material(session, chapter)
        if material is None:
            continue
        chunks = _lecture_chunks(material, course_id)
        if not chunks:
            continue
        ids = session.exec(
            select(Problem.id).where(Problem.chapter_id == chapter.id, Problem.qtype == "mcq")
        ).all()
        ranked.append(
            (sum(pid not in answered for pid in ids), chapter.order, chapter, material, chunks)
        )
    if not ranked:
        return None
    _, _, chapter, material, chunks = min(ranked, key=lambda row: (row[0], row[1]))
    return chapter, material, chunks


def generate_for_course(session: Session, course_id: int, user_id: int) -> int:
    """Generate and save reviewed MCQs. Returns the number actually saved."""
    target = _target(session, course_id, user_id)
    if target is None:
        log.info("No usable lecture/chapter for course %s", course_id)
        return 0
    chapter, material, chunks = target
    profile = ExamProfile(
        course=str(course_id),
        format_ratio={"객관식": 1.0},
        num_questions=REFILL_SIZE,
        detail_level="중간",
        difficulty="보통",
        recurring_patterns=[],
        phrasing_examples=[],
        emphasized_topics=[],
        notes=chapter.title,
    )
    examples = "\n\n".join(exam_style_examples(session, user_id, course_id))[:3000]
    retriever = Retriever(chunks)
    topics = topic_list(chunks)
    existing = {
        p.strip()
        for p in session.exec(
            select(Problem.question).where(Problem.chapter_id == chapter.id)
        ).all()
    }
    concepts = list(session.exec(select(Concept).where(Concept.chapter_id == chapter.id)).all())
    saved = 0
    for i in range(REFILL_SIZE):
        topic = topics[i % len(topics)]
        item = PlannedItem(
            item_id=f"q{i + 1}",
            qtype="객관식",
            topic=topic,
            bloom_level="이해",
            difficulty="보통",
            points=1,
            rationale="미풀이 문제 자동 보충",
        )
        context = retriever.search(topic, k=4)
        try:
            question = agents.generator(item, context, profile, examples)
            for _ in range(3):
                issues = checks.run(question, item, context)
                if not issues:
                    break
                question = agents.generator(
                    item, context, profile, examples, prev=question, feedback="\n".join(issues)
                )
            if checks.run(question, item, context):
                continue
            solved = agents.solver(question, context)
            review = agents.reviewer(question, solved, item, context, profile)
            if (
                review.verdict != "pass"
                or review.answer_match != "일치"
                or not review.grounded
                or not review.profile_fit
                or solved.is_ambiguous
            ):
                continue
            answer = question.answer.strip()
            if not re.fullmatch(r"[1-5]", answer):
                continue
            if question.stem.strip() in existing:
                continue
            source = next(
                (
                    s
                    for s in question.sources
                    if s.file == f"material-{material.id}" and 1 <= s.page <= len(material.pages)
                ),
                None,
            )
            if source is None or question.evidence.strip() not in material.pages[source.page - 1]:
                continue
            problem = Problem(
                chapter_id=chapter.id,
                question=question.stem.strip(),
                choices=question.choices or [],
                answer_index=int(answer) - 1,
                explanation=question.explanation.strip(),
                evidence=question.evidence.strip(),
                source_material_id=material.id,
                source_page=source.page,
                origin="llm",
                qtype="mcq",
            )
            session.add(problem)
            session.flush()
            matched = [
                concept
                for concept in concepts
                if concept.name in question.stem or concept.name in question.explanation
            ]
            for concept in matched or concepts[:1]:
                session.add(ProblemConcept(problem_id=problem.id, concept_id=concept.id))
            existing.add(problem.question)
            saved += 1
        except Exception:
            log.exception("Question generation failed for course %s, item %s", course_id, i + 1)
    session.commit()
    return saved
