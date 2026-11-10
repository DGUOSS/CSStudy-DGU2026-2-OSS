"""없는 과목·강좌 추가 요청 → 관리자 승인.

- 사용자는 과목명·교수명(·학기·메모)과 교안 PDF(선택, '교안 없음' 가능)를 내서 요청한다.
- 이미 있는 강좌면 요청 대신 그 강좌를 알려 준다(409, 자료는 강좌 페이지에서 올린다).
- 같은 과목·교수의 대기 중 요청이 있으면 새로 만들지 않는다(409).
- 관리자가 승인하면 과목·교수·강좌를 만들고(있으면 그대로 쓰고), 교안이 있으면 판 관리 규칙으로 자료에 붙인다.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import AdminUser, CurrentUser
from app.features.courses.router import ensure_course
from app.features.materials.router import read_pdf
from app.features.materials.versioning import add_material
from app.models import Course, CourseRequest, Professor, Subject, User

router = APIRouter(tags=["course-requests"])

Status = Literal["pending", "approved", "rejected"]


class CourseRequestOut(BaseModel):
    id: int
    requester_name: str | None
    subject_name: str
    subject_code: str | None
    professor_name: str
    semester: str | None
    note: str
    has_material: bool
    material_title: str | None
    material_page_count: int
    status: str
    reject_reason: str | None
    course_id: int | None
    created_at: datetime
    reviewed_at: datetime | None


class ApproveIn(BaseModel):
    """관리자가 승인하면서 이름을 고칠 수 있다(오타, 표기 통일)."""

    subject_name: str | None = Field(default=None, min_length=1, max_length=100)
    subject_code: str | None = Field(default=None, max_length=20)
    professor_name: str | None = Field(default=None, min_length=1, max_length=50)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def _out(session: SessionDep, r: CourseRequest) -> CourseRequestOut:
    requester = session.get(User, r.requester_id)
    return CourseRequestOut(
        id=r.id,
        requester_name=requester.name if requester else None,
        subject_name=r.subject_name,
        subject_code=r.subject_code,
        professor_name=r.professor_name,
        semester=r.semester,
        note=r.note,
        has_material=bool(r.material_pages or r.material_filename),
        material_title=r.material_title,
        material_page_count=len(r.material_pages),
        status=r.status,
        reject_reason=r.reject_reason,
        course_id=r.course_id,
        created_at=r.created_at,
        reviewed_at=r.reviewed_at,
    )


def _find_course(session: SessionDep, subject_name: str, professor_name: str) -> Course | None:
    subject = session.exec(select(Subject).where(Subject.name == subject_name)).first()
    professor = session.exec(select(Professor).where(Professor.name == professor_name)).first()
    if subject is None or professor is None:
        return None
    return session.exec(
        select(Course).where(Course.subject_id == subject.id, Course.professor_id == professor.id)
    ).first()


def _get_request_or_404(session: SessionDep, request_id: int) -> CourseRequest:
    r = session.get(CourseRequest, request_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "요청이 없습니다")
    return r


@router.post("/course-requests", status_code=status.HTTP_201_CREATED)
async def create_request(
    session: SessionDep,
    user: CurrentUser,
    subject_name: Annotated[str, Form(min_length=1, max_length=100)],
    professor_name: Annotated[str, Form(min_length=1, max_length=50)],
    subject_code: Annotated[str | None, Form(max_length=20)] = None,
    semester: Annotated[str | None, Form(max_length=20)] = None,
    note: Annotated[str, Form(max_length=1000)] = "",
    material_title: Annotated[str | None, Form(max_length=200)] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> CourseRequestOut:
    """file을 안 보내면 '교안 없음' 요청이다."""
    subject_name, professor_name = subject_name.strip(), professor_name.strip()
    existing = _find_course(session, subject_name, professor_name)
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"이미 있는 강좌입니다 (course_id={existing.id}). 교안은 강좌 페이지에서 올려 주세요",
        )
    dup = session.exec(
        select(CourseRequest).where(
            CourseRequest.subject_name == subject_name,
            CourseRequest.professor_name == professor_name,
            CourseRequest.status == "pending",
        )
    ).first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "같은 강좌 요청이 이미 대기 중입니다")
    filename, pages = (await read_pdf(file)) if file is not None and file.filename else (None, [])
    r = CourseRequest(
        requester_id=user.id,
        subject_name=subject_name,
        subject_code=(subject_code or "").strip() or None,
        professor_name=professor_name,
        semester=(semester or "").strip() or None,
        note=note.strip(),
        material_title=((material_title or "").strip() or filename) if pages else None,
        material_filename=filename,
        material_pages=pages,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return _out(session, r)


@router.get("/course-requests/mine")
def my_requests(session: SessionDep, user: CurrentUser) -> list[CourseRequestOut]:
    rows = session.exec(
        select(CourseRequest)
        .where(CourseRequest.requester_id == user.id)
        .order_by(CourseRequest.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    return [_out(session, r) for r in rows]


@router.get("/admin/course-requests")
def list_requests(
    session: SessionDep,
    _: AdminUser,
    status_: Annotated[Status | None, Query(alias="status")] = None,
) -> list[CourseRequestOut]:
    q = select(CourseRequest).order_by(CourseRequest.created_at)
    if status_:
        q = q.where(CourseRequest.status == status_)
    return [_out(session, r) for r in session.exec(q).all()]


@router.post("/admin/course-requests/{request_id}/approve")
def approve_request(
    request_id: int, session: SessionDep, admin: AdminUser, body: ApproveIn | None = None
) -> CourseRequestOut:
    r = _get_request_or_404(session, request_id)
    if r.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 처리된 요청입니다")
    body = body or ApproveIn()
    subject_name = (body.subject_name or r.subject_name).strip()
    professor_name = (body.professor_name or r.professor_name).strip()
    course, _ = ensure_course(
        session,
        subject_name=subject_name,
        subject_code=body.subject_code or r.subject_code,
        professor_name=professor_name,
        created_by=r.requester_id,
    )
    if r.material_pages:
        add_material(  # 결과(대체 여부 등)는 강좌 자료 목록에 반영된다
            session,
            course_id=course.id,
            uploader_id=r.requester_id,
            kind="lecture",
            title=r.material_title or r.material_filename or "교안",
            filename=r.material_filename or "upload.pdf",
            pages=r.material_pages,
        )
        r.material_pages = []  # 자료로 옮겼으니 요청에는 남기지 않는다
    r.subject_name, r.professor_name = subject_name, professor_name
    r.status, r.course_id = "approved", course.id
    r.reviewed_by, r.reviewed_at = admin.id, datetime.now(UTC)
    session.add(r)
    session.commit()
    session.refresh(r)
    return _out(session, r)


@router.post("/admin/course-requests/{request_id}/reject")
def reject_request(
    request_id: int, body: RejectIn, session: SessionDep, admin: AdminUser
) -> CourseRequestOut:
    r = _get_request_or_404(session, request_id)
    if r.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 처리된 요청입니다")
    r.status, r.reject_reason = "rejected", body.reason.strip()
    r.reviewed_by, r.reviewed_at = admin.id, datetime.now(UTC)
    r.material_pages = []  # 반려된 교안 본문은 지운다
    session.add(r)
    session.commit()
    session.refresh(r)
    return _out(session, r)
