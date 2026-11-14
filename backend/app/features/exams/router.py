"""족보(자료 종류 exam): 목록, 좋아요/싫어요, 문제 풀이 전 족보 선택.

고른 족보는 문제 생성 때 출제 스타일 예시로 넘어간다(exam_style_examples → services/llm.generate_problems).
문제 생성은 아직 연결 전이다.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import require_course_access
from app.models import Course, ExamSelection, Material, MaterialVote, User

router = APIRouter(tags=["exams"])


class ExamOut(BaseModel):
    id: int
    course_id: int
    title: str
    filename: str
    page_count: int
    uploader_name: str | None
    created_at: datetime
    likes: int
    dislikes: int
    my_vote: int  # 1 | -1 | 0(안 누름)
    selected: bool


class VoteIn(BaseModel):
    value: Literal[1, -1, 0]  # 0이면 취소


class VoteOut(BaseModel):
    material_id: int
    likes: int
    dislikes: int
    my_vote: int


class SelectionIn(BaseModel):
    material_ids: list[int]


def _latest_exams(session: Session, course_id: int) -> list[Material]:
    return list(
        session.exec(
            select(Material)
            .where(
                Material.course_id == course_id,
                Material.kind == "exam",
                Material.replaced_by.is_(None),  # type: ignore[union-attr]
            )
            .order_by(Material.created_at, Material.id)
        ).all()
    )


def vote_counts(session: Session, material_ids: list[int]) -> dict[int, tuple[int, int]]:
    """{자료 id: (좋아요 수, 싫어요 수)}"""
    if not material_ids:
        return {}
    rows = session.exec(
        select(MaterialVote.material_id, MaterialVote.value, func.count())
        .where(MaterialVote.material_id.in_(material_ids))  # type: ignore[attr-defined]
        .group_by(MaterialVote.material_id, MaterialVote.value)
    ).all()
    out = {mid: (0, 0) for mid in material_ids}
    for mid, value, n in rows:
        likes, dislikes = out[mid]
        out[mid] = (likes + n, dislikes) if value > 0 else (likes, dislikes + n)
    return out


def _my_votes(session: Session, user_id: int, material_ids: list[int]) -> dict[int, int]:
    if not material_ids:
        return {}
    rows = session.exec(
        select(MaterialVote.material_id, MaterialVote.value).where(
            MaterialVote.user_id == user_id,
            MaterialVote.material_id.in_(material_ids),  # type: ignore[attr-defined]
        )
    ).all()
    return dict(rows)


def _course_access(session: Session, user: User, course_id: int) -> Course:
    course = get_course_or_404(session, course_id)
    require_course_access(session, user, course)
    return course


@router.get("/courses/{course_id}/exams")
def list_exams(course_id: int, session: SessionDep, user: CurrentUser) -> list[ExamOut]:
    """족보 목록(최신판). 좋아요-싫어요가 큰 순."""
    _course_access(session, user, course_id)
    exams = _latest_exams(session, course_id)
    ids = [m.id for m in exams]
    counts = vote_counts(session, ids)
    mine = _my_votes(session, user.id, ids)
    selected = set(
        session.exec(
            select(ExamSelection.material_id).where(
                ExamSelection.user_id == user.id, ExamSelection.course_id == course_id
            )
        ).all()
    )
    names = {
        u.id: u.name
        for u in session.exec(
            select(User).where(User.id.in_({m.uploader_id for m in exams if m.uploader_id}))  # type: ignore[union-attr]
        ).all()
    }
    out = [
        ExamOut(
            id=m.id,
            course_id=m.course_id,
            title=m.title,
            filename=m.filename,
            page_count=m.page_count,
            uploader_name=names.get(m.uploader_id),
            created_at=m.created_at,
            likes=counts[m.id][0],
            dislikes=counts[m.id][1],
            my_vote=mine.get(m.id, 0),
            selected=m.id in selected,
        )
        for m in exams
    ]
    return sorted(out, key=lambda e: e.likes - e.dislikes, reverse=True)


@router.put("/materials/{material_id}/vote")
def vote_exam(material_id: int, body: VoteIn, session: SessionDep, user: CurrentUser) -> VoteOut:
    m = session.get(Material, material_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "자료가 없습니다")
    if m.kind != "exam":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "족보에만 좋아요/싫어요를 누를 수 있습니다"
        )
    _course_access(session, user, m.course_id)
    vote = session.get(MaterialVote, (user.id, material_id))
    if body.value == 0:
        if vote is not None:
            session.delete(vote)
    else:
        vote = vote or MaterialVote(user_id=user.id, material_id=material_id, value=body.value)
        vote.value = body.value
        session.add(vote)
    session.commit()
    likes, dislikes = vote_counts(session, [material_id])[material_id]
    return VoteOut(material_id=material_id, likes=likes, dislikes=dislikes, my_vote=body.value)


@router.put("/courses/{course_id}/exam-selection")
def select_exams(
    course_id: int, body: SelectionIn, session: SessionDep, user: CurrentUser
) -> list[ExamOut]:
    """문제 풀이 전에 참고할 족보를 고른다(이전 선택을 통째로 바꾼다). 빈 목록이면 선택 해제."""
    _course_access(session, user, course_id)
    valid = {m.id for m in _latest_exams(session, course_id)}
    wanted = set(body.material_ids)
    if not wanted <= valid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "이 강좌의 족보(최신판)만 고를 수 있습니다"
        )
    for old in session.exec(
        select(ExamSelection).where(
            ExamSelection.user_id == user.id, ExamSelection.course_id == course_id
        )
    ).all():
        session.delete(old)
    session.flush()
    for mid in sorted(wanted):
        session.add(ExamSelection(user_id=user.id, material_id=mid, course_id=course_id))
    session.commit()
    return list_exams(course_id, session, user)


def exam_style_examples(
    session: Session, user_id: int, course_id: int, max_chars: int = 6000
) -> list[str]:
    """사용자가 고른 족보의 본문(앞부분)을 돌려준다. 문제 생성의 style_examples로 넘긴다."""
    rows = session.exec(
        select(Material)
        .join(ExamSelection, ExamSelection.material_id == Material.id)
        .where(ExamSelection.user_id == user_id, ExamSelection.course_id == course_id)
        .order_by(Material.id)
    ).all()
    return ["\n".join(m.pages)[:max_chars] for m in rows]
