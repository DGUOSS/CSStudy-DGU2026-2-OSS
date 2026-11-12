"""없는 강좌 열기 요청 → 관리자 승인.

- 요청 근거는 두 가지다(구조는 docs/NDRIMS.md).
  - catalog: 이번 학기 개설 목록에서 고른 강좌(학수번호·교원번호가 정확하다)
  - record: 내 수강 기록(지난 학기에만 열린 수업도 들었던 사람이 열 수 있게)
  - (manual: 과목명·교수명을 직접 적던 예전 방식. 화면에서는 더 쓰지 않는다)
- 강좌는 교안이 있어야 열린다. 요청자나 관리자가 교안을 붙인 뒤에 승인할 수 있다.
- 같은 강좌를 여러 명이 요청하면 각각 남고, 하나를 승인하면 같은 강좌의 대기 요청이 함께 승인된다.
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
from app.features.enrollments.service import ensure_course_by_keys, norm_code, relink_unlinked
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
    material_count: int
    material_filenames: list[str]
    material_page_count: int  # 모든 파일 쪽 수 합계
    source: str
    professor_emp_no: str | None
    same_pending_count: int  # 같은 강좌를 기다리는 대기 요청 수(이 요청 포함)
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


def _files(r: CourseRequest) -> list[dict]:
    """요청에 딸린 교안 파일들. 예전 단일 파일 칸도 하나의 파일로 본다."""
    files = list(r.material_files or [])
    if r.material_filename:
        files.insert(
            0,
            {
                "filename": r.material_filename,
                "page_count": len(r.material_pages),
                "pages": r.material_pages,
            },
        )
    return files


def _same_course(q, r: CourseRequest):
    """같은 강좌(학수번호 + 교원번호, 교원번호가 없으면 교수명)를 가리키는 요청만 고른다."""
    if r.subject_code:
        q = q.where(CourseRequest.subject_code == r.subject_code)
    else:
        q = q.where(CourseRequest.subject_name == r.subject_name)
    if r.professor_emp_no:
        return q.where(CourseRequest.professor_emp_no == r.professor_emp_no)
    return q.where(CourseRequest.professor_name == r.professor_name)


def _pending_same(session, r: CourseRequest) -> list[CourseRequest]:
    q = select(CourseRequest).where(CourseRequest.status == "pending")
    return list(session.exec(_same_course(q, r)).all())


def _out(session: SessionDep, r: CourseRequest) -> CourseRequestOut:
    requester = session.get(User, r.requester_id)
    files = _files(r)
    return CourseRequestOut(
        id=r.id,
        requester_name=requester.name if requester else None,
        subject_name=r.subject_name,
        subject_code=r.subject_code,
        professor_name=r.professor_name,
        semester=r.semester,
        note=r.note,
        has_material=bool(files),
        material_count=len(files),
        material_filenames=[f["filename"] for f in files],
        material_page_count=sum(f.get("page_count") or len(f.get("pages", [])) for f in files),
        source=r.source,
        professor_emp_no=r.professor_emp_no,
        same_pending_count=len(_pending_same(session, r)) if r.status == "pending" else 0,
        status=r.status,
        reject_reason=r.reject_reason,
        course_id=r.course_id,
        created_at=r.created_at,
        reviewed_at=r.reviewed_at,
    )


def _drop_pages(r: CourseRequest) -> None:
    """파일 이름과 쪽 수만 남기고 본문은 지운다."""
    r.material_files = [
        {"filename": f["filename"], "page_count": f.get("page_count") or len(f.get("pages", []))}
        for f in r.material_files or []
    ]
    r.material_pages = []


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
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> CourseRequestOut:
    """교안 PDF를 여러 개 낼 수 있다(files). 안 보내면 '교안 없음' 요청이다.
    자료 제목은 사용자가 정하지 않는다. 승인할 때 '과목명 교안 번호' 규칙으로 붙는다."""
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
    material_files = []
    for f in files or []:
        if f.filename:
            filename, pages = await read_pdf(f)
            material_files.append({"filename": filename, "page_count": len(pages), "pages": pages})
    r = CourseRequest(
        requester_id=user.id,
        subject_name=subject_name,
        subject_code=(subject_code or "").strip() or None,
        professor_name=professor_name,
        semester=(semester or "").strip() or None,
        note=note.strip(),
        material_files=material_files,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return _out(session, r)


def create_keyed_request(
    session,
    user: User,
    *,
    source: str,
    sbj_no: str,
    sbj_nm: str,
    emp_no: str | None,
    emp_nm: str | None,
    semester: str | None,
) -> CourseRequest:
    """개설 목록이나 수강 기록에서 고른 강좌의 열기 요청을 만든다(commit은 부르는 쪽에서)."""
    if not emp_nm:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "교수 정보를 알 수 없습니다. 관리자가 이번 학기 개설 목록을 가져온 뒤 다시 요청해 주세요",
        )
    r = CourseRequest(
        requester_id=user.id,
        subject_name=sbj_nm.strip(),
        subject_code=norm_code(sbj_no),
        professor_name=emp_nm.strip(),
        professor_emp_no=emp_no or None,
        semester=semester,
        source=source,
    )
    if any(x.requester_id == user.id for x in _pending_same(session, r)):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 요청한 강좌입니다")
    session.add(r)
    session.flush()
    return r


@router.post("/course-requests/{request_id}/files")
async def attach_files(
    request_id: int,
    session: SessionDep,
    user: CurrentUser,
    files: Annotated[list[UploadFile], File()],
) -> CourseRequestOut:
    """대기 중인 요청에 교안 PDF를 붙인다(요청한 사람 또는 관리자). 교안이 있어야 승인할 수 있다."""
    r = _get_request_or_404(session, request_id)
    if user.role != "admin" and r.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "내 요청에만 교안을 붙일 수 있습니다")
    if r.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 처리된 요청입니다")
    added = list(r.material_files or [])
    for f in files:
        if f.filename:
            filename, pages = await read_pdf(f)
            added.append({"filename": filename, "page_count": len(pages), "pages": pages})
    r.material_files = added
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
    siblings = [x for x in _pending_same(session, r) if x.id != r.id]
    files = [f for x in (r, *siblings) for f in _files(x) if f.get("pages")]
    if not files:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "교안이 있어야 강좌를 열 수 있습니다. 교안을 먼저 붙여 주세요",
        )
    subject_name = (body.subject_name or r.subject_name).strip()
    professor_name = (body.professor_name or r.professor_name).strip()
    if r.subject_code and r.source in ("catalog", "record"):
        course, _ = ensure_course_by_keys(
            session,
            sbj_no=r.subject_code,
            sbj_nm=subject_name,
            emp_no=r.professor_emp_no,
            emp_nm=professor_name,
            created_by=r.requester_id,
        )
    else:
        course, _ = ensure_course(
            session,
            subject_name=subject_name,
            subject_code=body.subject_code or r.subject_code,
            professor_name=professor_name,
            created_by=r.requester_id,
        )
    for f in files:
        if f.get("pages"):
            add_material(  # 제목은 '과목명 교안 번호'로 자동, 중복·새 판은 판 관리 규칙대로
                session,
                course_id=course.id,
                uploader_id=r.requester_id,
                kind="lecture",
                title=f["filename"],
                filename=f["filename"],
                pages=f["pages"],
            )
            session.flush()
    now = datetime.now(UTC)
    for x in (r, *siblings):  # 같은 강좌를 기다리던 요청도 함께 승인
        _drop_pages(x)  # 자료로 옮겼으니 요청에는 본문을 남기지 않는다
        x.status, x.course_id = "approved", course.id
        x.reviewed_by, x.reviewed_at = admin.id, now
        session.add(x)
    r.subject_name, r.professor_name = subject_name, professor_name
    session.flush()
    relink_unlinked(session)  # 이 강좌를 기다리던 수강 기록을 잇는다
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
    _drop_pages(r)  # 반려된 교안 본문은 지운다
    session.add(r)
    session.commit()
    session.refresh(r)
    return _out(session, r)
