from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.mastery.service import concept_states
from app.features.my_subjects.router import require_course_access
from app.models import Chapter, Concept

router = APIRouter(tags=["mastery"])


class ConceptMasteryOut(BaseModel):
    concept_id: int
    name: str
    mastery: float  # 0~1, 알고 있을 확률
    attempts: int
    correct: int


class ChapterMasteryOut(BaseModel):
    chapter_id: int
    order: int
    title: str
    concepts: list[ConceptMasteryOut]


@router.get("/courses/{course_id}/mastery")
def course_mastery(
    course_id: int, session: SessionDep, user: CurrentUser
) -> list[ChapterMasteryOut]:
    require_course_access(session, user, get_course_or_404(session, course_id))
    chapters = session.exec(
        select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.order)
    ).all()
    concepts = session.exec(
        select(Concept).where(Concept.chapter_id.in_([c.id for c in chapters])).order_by(Concept.id)
    ).all()
    states = concept_states(session, user.id, [c.id for c in concepts])
    return [
        ChapterMasteryOut(
            chapter_id=ch.id,
            order=ch.order,
            title=ch.title,
            concepts=[
                ConceptMasteryOut(
                    concept_id=c.id,
                    name=c.name,
                    mastery=states[c.id].mastery,
                    attempts=states[c.id].attempts,
                    correct=states[c.id].correct,
                )
                for c in concepts
                if c.chapter_id == ch.id
            ],
        )
        for ch in chapters
    ]
