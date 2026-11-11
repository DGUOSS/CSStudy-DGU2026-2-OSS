"""챕터 목록, 문제 출제, 채점."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.mastery.service import concept_states
from app.models import Attempt, Chapter, Concept, Material, Problem, ProblemConcept

router = APIRouter(tags=["problems"])


class ChapterOut(BaseModel):
    id: int
    order: int
    title: str
    concepts: list[str]
    problem_count: int


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


def _concepts_of(session: SessionDep, problem_ids: list[int]) -> dict[int, list[Concept]]:
    rows = session.exec(
        select(ProblemConcept.problem_id, Concept)
        .join(Concept, Concept.id == ProblemConcept.concept_id)
        .where(ProblemConcept.problem_id.in_(problem_ids))
    ).all()
    out: dict[int, list[Concept]] = {pid: [] for pid in problem_ids}
    for pid, concept in rows:
        out[pid].append(concept)
    return out


@router.get("/courses/{course_id}/chapters")
def list_chapters(course_id: int, session: SessionDep) -> list[ChapterOut]:
    get_course_or_404(session, course_id)
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
    counts = dict(
        session.exec(
            select(Problem.chapter_id, func.count())
            .where(Problem.chapter_id.in_(ids))
            .group_by(Problem.chapter_id)
        ).all()
    )
    return [
        ChapterOut(
            id=ch.id,
            order=ch.order,
            title=ch.title,
            concepts=names[ch.id],
            problem_count=counts.get(ch.id, 0),
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
    if session.get(Chapter, chapter_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "챕터가 없습니다")
    problems = session.exec(select(Problem).where(Problem.chapter_id == chapter_id)).all()
    if not problems:
        return []
    concepts = _concepts_of(session, [p.id for p in problems])
    concept_ids = sorted({c.id for cs in concepts.values() for c in cs})
    states = concept_states(session, user.id, concept_ids)
    solved = set(
        session.exec(
            select(Attempt.problem_id).where(
                Attempt.user_id == user.id, Attempt.problem_id.in_([p.id for p in problems])
            )
        ).all()
    )

    def priority(p: Problem) -> tuple:
        cs = concepts[p.id]
        has_unseen = any(states[c.id].attempts == 0 for c in cs)
        lowest = min((states[c.id].mastery for c in cs), default=1.0)
        return (not has_unseen, p.id in solved, lowest, p.id)

    picked: list[Problem] = []
    seen_now: set[int] = set()
    # 한 번에 고를 때도 아직 안 나온 개념이 골고루 들어가도록 한 문제씩 고른다
    pool = sorted(problems, key=priority)
    while pool and len(picked) < count:
        best = next(
            (
                p
                for p in pool
                if any(c.id not in seen_now and states[c.id].attempts == 0 for c in concepts[p.id])
            ),
            pool[0],
        )
        picked.append(best)
        pool.remove(best)
        seen_now.update(c.id for c in concepts[best.id])

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
