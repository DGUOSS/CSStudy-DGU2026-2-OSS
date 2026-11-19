"""Replenish unanswered quiz questions using the shared question-ai package."""

import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock

from fastapi import BackgroundTasks
from pydantic import BaseModel
from qgen import agents, checks
from qgen.ingest import Retriever, topic_list
from qgen.schemas import Chunk, ExamProfile, PlannedItem, SourceRef
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.features.exams.router import exam_style_examples
from app.models import Attempt, Chapter, Concept, Material, Problem, ProblemConcept
from app.services.llm import LLMNotConfigured, _parse

log = logging.getLogger(__name__)

LOW_STOCK = 2
REFILL_SIZE = 5
_locks_guard = Lock()
_course_locks: dict[int, Lock] = {}

# ---------- 비용 상한(강좌별) ----------
# 생성이 실패(저장 0개)해도 '부족' 상태가 그대로라, 막지 않으면 문제를 풀 때마다 다시 생성한다.
# 시작 전에 아래를 확인하고 하나라도 걸리면 생성하지 않는다. 기록은 서버 메모리(재시작하면 초기화).
FAIL_COOLDOWN_SEC = 60 * 60  # 저장 0개로 끝났으면 1시간 쉼
MIN_GAP_SEC = 10 * 60  # 성공했어도 다음 시도까지 10분
DAILY_RUNS = 5  # 강좌별 하루(UTC) 최대 시도 횟수 → 하루 최대 5 × REFILL_SIZE 문항


@dataclass
class _Guard:
    day: date
    runs: int = 0
    last_at: float = 0.0
    last_saved: int | None = (
        None  # 마지막 시도에서 저장한 개수(None = 아직 없음 / 부족하지 않아 건너뜀)
    )
    running: bool = False


_guards: dict[int, _Guard] = {}
_guard_lock = Lock()


def _now() -> float:  # 테스트에서 바꿔 끼운다
    return time.time()


def _today() -> date:
    return datetime.fromtimestamp(_now(), UTC).date()


def reset_guards() -> None:
    with _guard_lock:
        _guards.clear()


def _reserve(course_id: int) -> bool:
    """생성을 시작해도 되면 자리를 잡고 True. 실행 중·실패 후 쉬는 중·간격 미달·하루 한도면 False."""
    now, today = _now(), _today()
    with _guard_lock:
        g = _guards.setdefault(course_id, _Guard(day=today))
        if g.day != today:
            g.day, g.runs = today, 0
        if g.running:
            return False
        since = now - g.last_at
        if g.last_saved == 0 and since < FAIL_COOLDOWN_SEC:
            return False
        if g.last_at and since < MIN_GAP_SEC:
            return False
        if g.runs >= DAILY_RUNS:
            log.info("Course %s reached the daily generation limit", course_id)
            return False
        g.running = True
        g.runs += 1
        g.last_at = now
        return True


def _release(course_id: int, saved: int | None) -> None:
    with _guard_lock:
        g = _guards.get(course_id)
        if g:
            g.running = False
            g.last_saved = saved
            g.last_at = _now()


def _site_runner(role: str, prompt: str, schema: type[BaseModel], seed: int = 0):
    del seed
    result = _parse(
        f"You are the {role} agent in a Korean university quiz generation system. Return only grounded Korean JSON.",
        prompt,
        schema,
        model=settings.qgen_model,
    )
    if result is None:
        raise LLMNotConfigured(f"Question generator {role} did not return a valid response")
    return result


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
    if not settings.anthropic_api_key:
        return
    if unanswered_count(session, course_id, user_id) > LOW_STOCK:
        return
    if _reserve(course_id):
        background_tasks.add_task(_replenish_background, course_id, user_id)


def _lock_for(course_id: int) -> Lock:
    with _locks_guard:
        return _course_locks.setdefault(course_id, Lock())


def _replenish_background(course_id: int, user_id: int) -> None:
    # One process on the current Render service. The DB count is rechecked after
    # acquiring the lock, so repeated requests do not start repeated generations.
    saved: int | None = None
    with _lock_for(course_id):
        try:
            with Session(engine) as session:
                if unanswered_count(session, course_id, user_id) <= LOW_STOCK:
                    saved = generate_for_course(session, course_id, user_id)
        except Exception:
            saved = 0  # 예외도 실패로 보고 쉬게 한다
            log.exception("Automatic problem generation failed for course %s", course_id)
        finally:
            _release(course_id, saved)


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
        if session.exec(select(Concept.id).where(Concept.chapter_id == chapter.id)).first() is None:
            continue
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
    # Database pages are already parsed; avoid loading the standalone tool's
    # on-disk embedding index for an unrelated course with the same identifier.
    retriever = Retriever(chunks, index_dir=Path(__file__).parent / "_no_index", verbose=False)
    topics = topic_list(chunks)
    existing = {
        p.strip()
        for p in session.exec(
            select(Problem.question).where(Problem.chapter_id == chapter.id)
        ).all()
    }
    concepts = list(session.exec(select(Concept).where(Concept.chapter_id == chapter.id)).all())
    if not concepts:
        log.info("No concepts to attach generated problems to in chapter %s", chapter.id)
        return 0
    concept_names = [concept.name for concept in concepts]
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
            question = agents.generator(
                item, context, profile, examples, runner=_site_runner, concept_names=concept_names
            )
            for _ in range(3):
                issues = checks.run(question, item, context, set(concept_names))
                if not issues:
                    break
                question = agents.generator(
                    item, context, profile, examples, prev=question, feedback="\n".join(issues),
                    runner=_site_runner, concept_names=concept_names,
                )
            if checks.run(question, item, context, set(concept_names)):
                continue
            solved = agents.solver(question, context, runner=_site_runner)
            review = agents.reviewer(question, solved, item, context, profile, runner=_site_runner)
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
            evidence = checks.normalize_evidence(question.evidence)
            if (
                source is None
                or not evidence
                or evidence not in checks.normalize_evidence(material.pages[source.page - 1])
            ):
                continue
            selected = [concept for concept in concepts if concept.name in question.concepts]
            if not selected or len(selected) != len(set(question.concepts)):
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
            for concept in selected:
                session.add(ProblemConcept(problem_id=problem.id, concept_id=concept.id))
            existing.add(problem.question)
            saved += 1
        except Exception:
            log.exception("Question generation failed for course %s, item %s", course_id, i + 1)
    session.commit()
    return saved
