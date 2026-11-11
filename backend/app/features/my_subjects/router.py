"""내 과목: 사용자가 수강했거나 수강 중인 과목. 등록한 과목의 강좌에만 들어갈 수 있다(관리자는 예외).

지금은 사용자가 목록에서 직접 고른다(source=manual). 엔드림스 연동이 생기면 같은 테이블에
source=ndrims로 넣기만 하면 된다.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.models import Course, Subject, User, UserSubject

router = APIRouter(tags=["my-subjects"])

Status = Literal["current", "taken"]


class MySubjectOut(BaseModel):
    subject_id: int
    name: str
    code: str | None
    status: str
    semester: str | None
    source: str
    created_at: datetime


class MySubjectIn(BaseModel):
    status: Status = "current"
    semester: str | None = None


def has_subject_access(session: Session, user: User, subject_id: int) -> bool:
    if user.role == "admin":
        return True
    return session.get(UserSubject, (user.id, subject_id)) is not None


def require_subject_access(session: Session, user: User, subject_id: int) -> None:
    if not has_subject_access(session, user, subject_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "내 과목에 등록한 과목만 들어갈 수 있습니다")


def require_course_access(session: Session, user: User, course: Course) -> None:
    require_subject_access(session, user, course.subject_id)


def _out(us: UserSubject, s: Subject) -> MySubjectOut:
    return MySubjectOut(
        subject_id=s.id,
        name=s.name,
        code=s.code,
        status=us.status,
        semester=us.semester,
        source=us.source,
        created_at=us.created_at,
    )


@router.get("/me/subjects")
def list_my_subjects(session: SessionDep, user: CurrentUser) -> list[MySubjectOut]:
    rows = session.exec(
        select(UserSubject, Subject)
        .join(Subject, Subject.id == UserSubject.subject_id)
        .where(UserSubject.user_id == user.id)
        .order_by(Subject.name)
    ).all()
    return [_out(us, s) for us, s in rows]


@router.put("/me/subjects/{subject_id}")
def add_my_subject(
    subject_id: int, body: MySubjectIn, session: SessionDep, user: CurrentUser
) -> MySubjectOut:
    """내 과목에 넣는다. 이미 있으면 상태(수강 중/수강함)와 학기만 바꾼다."""
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "과목이 없습니다")
    us = session.get(UserSubject, (user.id, subject_id))
    if us is None:
        us = UserSubject(user_id=user.id, subject_id=subject_id)
    us.status = body.status
    us.semester = (body.semester or "").strip() or None
    session.add(us)
    session.commit()
    session.refresh(us)
    return _out(us, subject)


@router.delete("/me/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_my_subject(subject_id: int, session: SessionDep, user: CurrentUser) -> Response:
    us = session.get(UserSubject, (user.id, subject_id))
    if us is not None:
        session.delete(us)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
