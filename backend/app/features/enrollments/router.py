"""내 수강 기록: 엔드림스에서 가져오기, 내 강좌 목록, 지난 수업 강좌 열기 요청.

가져오기는 학생 브라우저(엔드림스 창의 즐겨찾기 버튼)가 보낸 기록을 받는다. 우리 서버는 엔드림스에
접속하지 않고 비밀번호도 받지 않는다. 기록은 과목을 찾는 칸만 저장한다(성적·개인 정보는 버린다).
"""

from collections import defaultdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.course_requests.router import create_keyed_request
from app.features.enrollments.service import current_term, norm_code, resolve, term_label
from app.models import Course, CourseRequest, Enrollment, Professor, Subject

router = APIRouter(tags=["enrollments"])

Code = Annotated[str, Field(min_length=1, max_length=20)]


class RecordIn(BaseModel):
    """엔드림스 수강신청내역(OPEN_YY·OPEN_SEM_CD…) 또는 전체성적조회(YY·SEM_CD…·EMP_NM) 한 줄."""

    year: str = Field(pattern=r"^\d{4}$")
    sem_cd: Code
    sbj_no: Code
    sbj_nm: str = Field(min_length=1, max_length=200)
    dvcls: str = Field(default="", max_length=10)
    emp_nm: str | None = Field(default=None, max_length=50)
    # 이번 학기 수업은 즐겨찾기가 종합강의시간표에서 찾아 붙여 보낸다
    emp_no: str | None = Field(default=None, max_length=20)


class ImportIn(BaseModel):
    records: list[RecordIn] = Field(max_length=500)


class MyCourseOut(BaseModel):
    course_id: int
    subject_name: str
    sbj_no: str | None
    professor_name: str
    status: str  # current(이번 학기) | taken(지난 학기)
    terms: list[str]


class WaitingOut(BaseModel):
    """수강 기록은 있지만 사이트에 아직 열린 강좌가 없는 수업."""

    enrollment_id: int
    sbj_no: str
    sbj_nm: str
    professor_name: str | None
    status: str
    term: str
    request: str  # none | mine(내가 요청함) | others(다른 사람이 요청함)
    request_count: int


class MyCoursesOut(BaseModel):
    current_term: str | None
    record_count: int
    imported_at: datetime | None
    courses: list[MyCourseOut]
    waiting: list[WaitingOut]


class ImportOut(MyCoursesOut):
    received: int
    added: int


def _my_courses(session, user) -> MyCoursesOut:
    cur = current_term(session)
    rows = session.exec(
        select(Enrollment)
        .where(Enrollment.user_id == user.id)
        .order_by(
            Enrollment.year.desc(),
            Enrollment.sem_cd.desc(),  # type: ignore[attr-defined]
        )
    ).all()
    is_cur = lambda e: cur is not None and (e.year, e.sem_cd) == cur  # noqa: E731
    by_course: dict[int, list[Enrollment]] = defaultdict(list)
    waiting: dict[tuple, Enrollment] = {}
    for e in rows:
        if e.course_id:
            by_course[e.course_id].append(e)
        else:
            waiting.setdefault((e.sbj_no, e.emp_no or e.emp_nm), e)  # 가장 최근 학기 하나만
    courses = []
    for cid, es in by_course.items():
        c = session.get(Course, cid)
        s, p = session.get(Subject, c.subject_id), session.get(Professor, c.professor_id)
        courses.append(
            MyCourseOut(
                course_id=cid,
                subject_name=s.name,
                sbj_no=s.code,
                professor_name=p.name,
                status="current" if any(is_cur(e) for e in es) else "taken",
                terms=[term_label(e.year, e.sem_cd) for e in es],
            )
        )
    courses.sort(key=lambda x: (x.status != "current", x.subject_name))
    pending = session.exec(select(CourseRequest).where(CourseRequest.status == "pending")).all()
    out_wait = []
    for e in waiting.values():
        same = [
            r
            for r in pending
            if r.subject_code == norm_code(e.sbj_no)
            and (r.professor_emp_no == e.emp_no if e.emp_no else r.professor_name == e.emp_nm)
        ]
        mine = any(r.requester_id == user.id for r in same)
        out_wait.append(
            WaitingOut(
                enrollment_id=e.id,
                sbj_no=e.sbj_no,
                sbj_nm=e.sbj_nm,
                professor_name=e.emp_nm,
                status="current" if is_cur(e) else "taken",
                term=term_label(e.year, e.sem_cd),
                request="mine" if mine else ("others" if same else "none"),
                request_count=len(same),
            )
        )
    out_wait.sort(key=lambda x: (x.status != "current", x.sbj_nm))
    return MyCoursesOut(
        current_term=term_label(*cur) if cur else None,
        record_count=len(rows),
        imported_at=max((e.created_at for e in rows), default=None),
        courses=courses,
        waiting=out_wait,
    )


@router.get("/me/courses")
def my_courses(session: SessionDep, user: CurrentUser) -> MyCoursesOut:
    return _my_courses(session, user)


@router.post("/me/ndrims/import")
def import_records(body: ImportIn, session: SessionDep, user: CurrentUser) -> ImportOut:
    """엔드림스 수강 기록을 받아 저장하고 강좌와 잇는다. 같은 수업을 다시 보내면 덮어쓴다."""
    added = 0
    for rec in body.records:
        key = (rec.year, rec.sem_cd.strip(), norm_code(rec.sbj_no), rec.dvcls.strip())
        e = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.year == key[0],
                Enrollment.sem_cd == key[1],
                Enrollment.sbj_no == key[2],
                Enrollment.dvcls == key[3],
            )
        ).first()
        if e is None:
            e = Enrollment(
                user_id=user.id, year=key[0], sem_cd=key[1], sbj_no=key[2], dvcls=key[3], sbj_nm=""
            )
            added += 1
        e.sbj_nm = rec.sbj_nm.strip()
        if rec.emp_nm:
            e.emp_nm = rec.emp_nm.strip()
        if rec.emp_no:
            e.emp_no = rec.emp_no.strip()
        e.course_id = resolve(session, e)
        session.add(e)
    session.commit()
    return ImportOut(
        **_my_courses(session, user).model_dump(), received=len(body.records), added=added
    )


@router.post("/me/enrollments/{enrollment_id}/request", status_code=status.HTTP_201_CREATED)
def request_from_record(enrollment_id: int, session: SessionDep, user: CurrentUser) -> MyCoursesOut:
    """내 수강 기록의 수업을 열어 달라고 요청한다(지난 학기에만 열린 수업도 가능)."""
    e = session.get(Enrollment, enrollment_id)
    if e is None or e.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "수강 기록이 없습니다")
    if e.course_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 열린 강좌입니다")
    create_keyed_request(
        session,
        user,
        source="record",
        sbj_no=e.sbj_no,
        sbj_nm=e.sbj_nm,
        emp_no=e.emp_no,
        emp_nm=e.emp_nm,
        semester=term_label(e.year, e.sem_cd),
    )
    session.commit()
    return _my_courses(session, user)
