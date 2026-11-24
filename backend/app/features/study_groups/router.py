from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import update
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.enrollments.service import can_enter
from app.features.mastery.service import weak_concepts_by_user
from app.models import Course, StudyApplication, StudyGroup, StudyMessage, Subject, User, _now

router = APIRouter(tags=["study-groups"])


class StudyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=3000)
    capacity: int = Field(ge=0, le=20)

    @field_validator("capacity")
    @classmethod
    def valid_capacity(cls, value):
        if value == 1:
            raise ValueError("인원은 0(제한 없음) 또는 2~20명입니다")
        return value

    mode: Literal["online", "offline", "hybrid"]
    schedule: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2, max_length=200)

    @field_validator("title", "description", "schedule", "location", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class StudyOut(StudyCreate):
    id: int
    subject_id: int
    owner_name: str
    is_mine: bool
    created_at: datetime
    closed_at: datetime | None
    participant_count: int
    pending_count: int | None
    my_application: Literal["pending", "approved", "rejected", "cancelled"] | None
    # 나와 이 스터디(개설자·승인된 참여자)의 약점이 겹치는 개념 이름. 다른 사람의 점수나 누구의 약점인지는 주지 않는다
    shared_weak: list[str] = []


class StudyList(BaseModel):
    items: list[StudyOut]
    total: int
    my_weak: list[str] = []  # 이 과목에서 내 약점 개념(추천 기준)


def output(session, row, owner_name, user_id):
    approved = session.exec(
        select(func.count())
        .select_from(StudyApplication)
        .where(StudyApplication.group_id == row.id, StudyApplication.status == "approved")
    ).one()
    pending = (
        session.exec(
            select(func.count())
            .select_from(StudyApplication)
            .where(StudyApplication.group_id == row.id, StudyApplication.status == "pending")
        ).one()
        if row.owner_id == user_id
        else None
    )
    mine = session.exec(
        select(StudyApplication).where(
            StudyApplication.group_id == row.id, StudyApplication.user_id == user_id
        )
    ).first()
    return StudyOut(
        **row.model_dump(exclude={"owner_id"}),
        owner_name=owner_name,
        is_mine=row.owner_id == user_id,
        participant_count=1 + approved,
        pending_count=pending,
        my_application=mine.status if mine else None,
    )


def require_subject_access(session, user, subject_id):
    if session.get(Subject, subject_id) is None:
        raise HTTPException(404, "과목을 찾을 수 없습니다")
    courses = session.exec(select(Course).where(Course.subject_id == subject_id)).all()
    if user.role != "admin" and not any(can_enter(session, user, course) for course in courses):
        raise HTTPException(403, "이 과목의 수강 기록 또는 공용 강좌 접근 권한이 필요합니다")


@router.get("/subjects/{subject_id}/study-groups")
def list_groups(
    subject_id: int,
    session: SessionDep,
    user: CurrentUser,
    state: Literal["all", "open", "closed"] = "open",
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    sort: Literal["recommended", "recent"] = "recommended",
) -> StudyList:
    require_subject_access(session, user, subject_id)
    conditions = [StudyGroup.subject_id == subject_id]
    if state == "open":
        conditions.append(StudyGroup.closed_at.is_(None))
    elif state == "closed":
        conditions.append(StudyGroup.closed_at.is_not(None))
    total = session.exec(select(func.count()).select_from(StudyGroup).where(*conditions)).one()
    rows = session.exec(
        select(StudyGroup, User.name)
        .join(User, User.id == StudyGroup.owner_id)
        .where(*conditions)
        .order_by(StudyGroup.created_at.desc(), StudyGroup.id.desc())
    ).all()
    members = _members(session, [r.id for r, _ in rows])
    weak = weak_concepts_by_user(
        session, [user.id, *{u for ids in members.values() for u in ids}], subject_id
    )
    mine = weak.get(user.id, set())
    shared = {
        r.id: sorted(mine & set().union(*(weak.get(u, set()) for u in members[r.id] - {user.id})))
        for r, _ in rows
    }
    if sort == "recommended":
        # 약점이 많이 겹치는 스터디가 위로(같으면 최신순). 정렬이 안정적이라 최신순이 유지된다
        rows = sorted(rows, key=lambda rn: -len(shared[rn[0].id]))
    page = rows[offset : offset + limit]
    return StudyList(
        items=[
            output(session, r, name, user.id).model_copy(update={"shared_weak": shared[r.id]})
            for r, name in page
        ],
        total=total,
        my_weak=sorted(mine),
    )


def _members(session, group_ids: list[int]) -> dict[int, set[int]]:
    """스터디별 개설자 + 승인된 참여자."""
    out: dict[int, set[int]] = {g: set() for g in group_ids}
    if not group_ids:
        return out
    for gid, owner in session.exec(
        select(StudyGroup.id, StudyGroup.owner_id).where(StudyGroup.id.in_(group_ids))
    ).all():
        out[gid].add(owner)
    for gid, uid in session.exec(
        select(StudyApplication.group_id, StudyApplication.user_id).where(
            StudyApplication.group_id.in_(group_ids), StudyApplication.status == "approved"
        )
    ).all():
        out[gid].add(uid)
    return out


@router.post("/subjects/{subject_id}/study-groups", status_code=201)
def create_group(
    subject_id: int, body: StudyCreate, session: SessionDep, user: CurrentUser
) -> StudyOut:
    require_subject_access(session, user, subject_id)
    row = StudyGroup(**body.model_dump(), subject_id=subject_id, owner_id=user.id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return output(session, row, user.name, user.id)


@router.post("/subjects/{subject_id}/study-groups/{group_id}/close")
def close_group(subject_id: int, group_id: int, session: SessionDep, user: CurrentUser) -> StudyOut:
    row = lock_group(session, subject_id, group_id)
    if row is None or row.subject_id != subject_id:
        raise HTTPException(404, "스터디를 찾을 수 없습니다")
    if row.owner_id != user.id:
        raise HTTPException(403, "개설자만 모집을 종료할 수 있습니다")
    # 수강 연결이 사라져도 자신의 모집은 종료 가능. 중복 요청은 최초 종료 시각을 유지한다.
    session.execute(
        update(StudyGroup)
        .where(StudyGroup.id == group_id, StudyGroup.closed_at.is_(None))
        .values(closed_at=_now())
    )
    session.execute(
        update(StudyApplication)
        .where(StudyApplication.group_id == group_id, StudyApplication.status == "pending")
        .values(status="rejected", updated_at=_now())
    )
    session.commit()
    session.refresh(row)
    return output(session, row, user.name, user.id)


# All membership mutations take a write lock on the parent before reading counts.
# UPDATE serializes both PostgreSQL row writers and SQLite writers.
def lock_group(session, subject_id, group_id):
    changed = session.execute(
        update(StudyGroup)
        .where(StudyGroup.id == group_id, StudyGroup.subject_id == subject_id)
        .values(capacity=StudyGroup.capacity)
    )
    if not changed.rowcount:
        raise HTTPException(404, "스터디를 찾을 수 없습니다")
    row = session.get(StudyGroup, group_id)
    session.refresh(row)
    return row


class ApplicationOut(BaseModel):
    id: int
    name: str
    status: Literal["pending", "approved", "rejected", "cancelled"]
    created_at: datetime


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]


@router.get("/subjects/{subject_id}/study-groups/{group_id}/applications")
def applications(
    subject_id: int, group_id: int, session: SessionDep, user: CurrentUser
) -> list[ApplicationOut]:
    group = session.get(StudyGroup, group_id)
    if not group or group.subject_id != subject_id:
        raise HTTPException(404, "스터디를 찾을 수 없습니다")
    if group.owner_id != user.id:
        raise HTTPException(403, "개설자만 신청 명단을 볼 수 있습니다")
    rows = session.exec(
        select(StudyApplication, User.name)
        .join(User, User.id == StudyApplication.user_id)
        .where(StudyApplication.group_id == group_id)
        .order_by(StudyApplication.created_at, StudyApplication.id)
    ).all()
    return [
        ApplicationOut(id=a.id, name=name, status=a.status, created_at=a.created_at)
        for a, name in rows
    ]


@router.post("/subjects/{subject_id}/study-groups/{group_id}/apply")
def apply(subject_id: int, group_id: int, session: SessionDep, user: CurrentUser) -> dict[str, str]:
    require_subject_access(session, user, subject_id)
    group = lock_group(session, subject_id, group_id)
    if group.owner_id == user.id:
        raise HTTPException(409, "개설자는 이미 참여 인원에 포함됩니다")
    if group.closed_at:
        raise HTTPException(409, "모집이 종료되었습니다")
    record = session.exec(
        select(StudyApplication).where(
            StudyApplication.group_id == group_id, StudyApplication.user_id == user.id
        )
    ).first()
    if record and record.status in ("pending", "approved"):
        raise HTTPException(409, "이미 신청했거나 참여 중입니다")
    n = session.exec(
        select(func.count())
        .select_from(StudyApplication)
        .where(StudyApplication.group_id == group_id, StudyApplication.status == "approved")
    ).one()
    if group.capacity and n + 1 >= group.capacity:
        raise HTTPException(409, "정원이 찼습니다")
    record = record or StudyApplication(group_id=group_id, user_id=user.id)
    record.status = "pending"
    record.created_at = record.updated_at = _now()
    session.add(record)
    session.commit()
    return {"status": "pending"}


@router.post("/subjects/{subject_id}/study-groups/{group_id}/cancel")
def cancel(
    subject_id: int, group_id: int, session: SessionDep, user: CurrentUser
) -> dict[str, str]:
    lock_group(session, subject_id, group_id)
    record = session.exec(
        select(StudyApplication).where(
            StudyApplication.group_id == group_id, StudyApplication.user_id == user.id
        )
    ).first()
    if record is None:
        raise HTTPException(404, "본인의 신청 내역이 없습니다")
    if record.status not in ("pending", "approved", "cancelled"):
        raise HTTPException(409, "취소할 수 없는 신청입니다")
    record.status = "cancelled"
    record.updated_at = _now()
    session.add(record)
    session.commit()
    return {"status": "cancelled"}


@router.post(
    "/subjects/{subject_id}/study-groups/{group_id}/applications/{application_id}/decision"
)
def decide(
    subject_id: int,
    group_id: int,
    application_id: int,
    body: DecisionIn,
    session: SessionDep,
    user: CurrentUser,
) -> dict[str, str]:
    group = lock_group(session, subject_id, group_id)
    if group.owner_id != user.id:
        raise HTTPException(403, "개설자만 승인 또는 거절할 수 있습니다")
    record = session.get(StudyApplication, application_id)
    if not record or record.group_id != group_id:
        raise HTTPException(404, "신청을 찾을 수 없습니다")
    if record.status != "pending":
        raise HTTPException(409, "이미 처리된 신청입니다. 목록을 새로 확인해 주세요")
    if body.decision == "approved":
        if group.closed_at:
            raise HTTPException(409, "모집이 종료되었습니다")
        n = session.exec(
            select(func.count())
            .select_from(StudyApplication)
            .where(StudyApplication.group_id == group_id, StudyApplication.status == "approved")
        ).one()
        if group.capacity and n + 1 >= group.capacity:
            raise HTTPException(409, "정원이 찼습니다")
    record.status = body.decision
    record.updated_at = _now()
    session.add(record)
    session.commit()
    return {"status": record.status}


class StudySpaceOut(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    title: str
    is_owner: bool


def require_member(session, group_id: int, user) -> tuple[StudyGroup, bool]:
    """스터디 공간에 들어갈 수 있는지(개설자 또는 승인된 참여자). (스터디, 개설자인가)"""
    group = session.get(StudyGroup, group_id)
    if group is None:
        raise HTTPException(404, "스터디를 찾을 수 없습니다")
    is_owner = group.owner_id == user.id
    approved = session.exec(
        select(StudyApplication.id).where(
            StudyApplication.group_id == group_id,
            StudyApplication.user_id == user.id,
            StudyApplication.status == "approved",
        )
    ).first()
    if not is_owner and approved is None:
        raise HTTPException(403, "개설자와 승인된 참여자만 입장할 수 있습니다")
    return group, is_owner


@router.get("/study-groups/{group_id}/space")
def study_space(group_id: int, session: SessionDep, user: CurrentUser) -> StudySpaceOut:
    group, is_owner = require_member(session, group_id, user)
    subject = session.get(Subject, group.subject_id)
    return StudySpaceOut(
        id=group.id,
        subject_id=group.subject_id,
        subject_name=subject.name,
        title=group.title,
        is_owner=is_owner,
    )


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class MessageOut(BaseModel):
    id: int
    user_name: str
    is_mine: bool
    is_owner: bool  # 보낸 사람이 개설자인가
    body: str
    created_at: datetime


MESSAGE_PAGE = 50
CHAT_WINDOW_SEC, CHAT_MAX_IN_WINDOW = 10, 5


@router.get("/study-groups/{group_id}/messages")
def list_messages(
    group_id: int,
    session: SessionDep,
    user: CurrentUser,
    after_id: int = Query(0, ge=0),
) -> list[MessageOut]:
    """채팅. after_id가 0이면 최근 50개, 아니면 그 뒤에 온 메시지(새로 고칠 때). 오래된 것부터 준다."""
    group, _ = require_member(session, group_id, user)
    q = (
        select(StudyMessage, User.name)
        .join(User, User.id == StudyMessage.user_id)
        .where(StudyMessage.group_id == group_id)
    )
    if after_id:
        q = q.where(StudyMessage.id > after_id).order_by(StudyMessage.id).limit(200)
        rows = session.exec(q).all()
    else:
        rows = session.exec(q.order_by(StudyMessage.id.desc()).limit(MESSAGE_PAGE)).all()[::-1]
    return [
        MessageOut(
            id=m.id,
            user_name=name,
            is_mine=m.user_id == user.id,
            is_owner=m.user_id == group.owner_id,
            body=m.body,
            created_at=m.created_at,
        )
        for m, name in rows
    ]


@router.post("/study-groups/{group_id}/messages", status_code=201)
def send_message(
    group_id: int, body: MessageIn, session: SessionDep, user: CurrentUser
) -> MessageOut:
    group, is_owner = require_member(session, group_id, user)
    # 도배 막기: 한 사람이 10초에 5개까지
    since = _now() - timedelta(seconds=CHAT_WINDOW_SEC)
    recent = session.exec(
        select(func.count())
        .select_from(StudyMessage)
        .where(
            StudyMessage.group_id == group_id,
            StudyMessage.user_id == user.id,
            StudyMessage.created_at >= since,
        )
    ).one()
    if recent >= CHAT_MAX_IN_WINDOW:
        raise HTTPException(429, "메시지를 너무 빨리 보내고 있어요. 잠시 후 다시 보내 주세요")
    m = StudyMessage(group_id=group_id, user_id=user.id, body=body.body)
    session.add(m)
    session.commit()
    session.refresh(m)
    return MessageOut(
        id=m.id,
        user_name=user.name,
        is_mine=True,
        is_owner=is_owner,
        body=m.body,
        created_at=m.created_at,
    )
