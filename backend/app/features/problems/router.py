"""챕터 목록, 문제 출제, 채점."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import require_course_access
from app.features.mastery.service import concept_states
from app.features.problems.service import concepts_of, pick_problems
from app.models import Attempt, Chapter, Concept, Material, Problem

router = APIRouter(tags=["problems"])


class ChapterOut(BaseModel):
    id: int
    order: int
    title: str
    concepts: list[str]
    problem_count: int  # 객관식(퀴즈에 나오는 것)
    essay_count: int  # 서술형(종이 시험에만)


class ConceptRef(BaseModel):
    id: int
    name: str


class ProblemOut(BaseModel):
    """풀이 화면용. 정답은 넣지 않는다."""

    id: int
    chapter_id: int
    question: str
    choices: list[str]
    concepts: list[ConceptRef]
    origin: str


class AttemptIn(BaseModel):
    chosen_index: int


class SourceOut(BaseModel):
    material_id: int
    title: str
    page: int | None


class MasteryChange(BaseModel):
    concept_id: int
    name: str
    before: float
    after: float


class AttemptResult(BaseModel):
    correct: bool
    answer_index: int
    explanation: str
    evidence: str | None
    source: SourceOut | None
    mastery: list[MasteryChange]


_concepts_of = concepts_of


@router.get("/courses/{course_id}/chapters")
def list_chapters(course_id: int, session: SessionDep, user: CurrentUser) -> list[ChapterOut]:
    require_course_access(session, user, get_course_or_404(session, course_id))
    chapters = session.exec(
        select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.order)
    ).all()
    ids = [ch.id for ch in chapters]
    # 챕터마다 따로 조회하면 DB 왕복이 챕터 수만큼 늘어나서 한 번에 모아 온다
    names: dict[int, list[str]] = {i: [] for i in ids}
    for chapter_id, name in session.exec(
        select(Concept.chapter_id, Concept.name)
        .where(Concept.chapter_id.in_(ids))
        .order_by(Concept.id)
    ).all():
        names[chapter_id].append(name)
    counts: dict[tuple[int, bool], int] = {}
    for chapter_id, qtype, n in session.exec(
        select(Problem.chapter_id, Problem.qtype, func.count())
        .where(Problem.chapter_id.in_(ids))
        .group_by(Problem.chapter_id, Problem.qtype)
    ).all():
        key = (chapter_id, qtype == "mcq")
        counts[key] = counts.get(key, 0) + n
    return [
        ChapterOut(
            id=ch.id,
            order=ch.order,
            title=ch.title,
            concepts=names[ch.id],
            problem_count=counts.get((ch.id, True), 0),
            essay_count=counts.get((ch.id, False), 0),
        )
        for ch in chapters
    ]


@router.get("/chapters/{chapter_id}/problems")
def next_problems(
    chapter_id: int,
    session: SessionDep,
    user: CurrentUser,
    count: int = Query(default=5, ge=1, le=20),
) -> list[ProblemOut]:
    """다음에 풀 문제를 고른다.

    우선순위: ① 아직 한 번도 안 나온 개념이 들어간 문제 ② 아직 안 푼 문제
    ③ 숙련도가 낮은 개념의 문제. 같으면 id 순.
    """
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "챕터가 없습니다")
    require_course_access(session, user, get_course_or_404(session, chapter.course_id))
    problems = session.exec(
        select(Problem).where(Problem.chapter_id == chapter_id, Problem.qtype == "mcq")
    ).all()  # 퀴즈는 객관식만(서술형은 종이 시험에서)
    picked = pick_problems(session, user.id, list(problems), count)
    concepts = _concepts_of(session, [p.id for p in picked])

    return [
        ProblemOut(
            id=p.id,
            chapter_id=p.chapter_id,
            question=p.question,
            choices=p.choices,
            concepts=[ConceptRef(id=c.id, name=c.name) for c in concepts[p.id]],
            origin=p.origin,
        )
        for p in picked
    ]


@router.post("/problems/{problem_id}/attempts")
def submit_attempt(
    problem_id: int, body: AttemptIn, session: SessionDep, user: CurrentUser
) -> AttemptResult:
    problem = session.get(Problem, problem_id)
    if problem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "문제가 없습니다")
    chapter = session.get(Chapter, problem.chapter_id)
    require_course_access(session, user, get_course_or_404(session, chapter.course_id))
    if not 0 <= body.chosen_index < len(problem.choices):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "보기 번호가 잘못됐습니다")

    concepts = _concepts_of(session, [problem.id])[problem.id]
    ids = [c.id for c in concepts]
    before = concept_states(session, user.id, ids)

    correct = body.chosen_index == problem.answer_index
    session.add(
        Attempt(
            user_id=user.id, problem_id=problem.id, chosen_index=body.chosen_index, correct=correct
        )
    )
    session.commit()
    after = concept_states(session, user.id, ids)

    source = None
    if problem.source_material_id:
        material = session.get(Material, problem.source_material_id)
        if material:
            source = SourceOut(
                material_id=material.id, title=material.title, page=problem.source_page
            )

    return AttemptResult(
        correct=correct,
        answer_index=problem.answer_index,
        explanation=problem.explanation,
        evidence=problem.evidence,
        source=source,
        mastery=[
            MasteryChange(
                concept_id=c.id, name=c.name, before=before[c.id].mastery, after=after[c.id].mastery
            )
            for c in concepts
        ],
    )
