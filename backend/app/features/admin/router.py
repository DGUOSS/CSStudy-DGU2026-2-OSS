"""관리자: 과목·강좌·자료를 직접 만들고 고치고 지운다.

- 새 강좌 만들기: 과목명·교수명과 교안 PDF 여러 개를 한 번에. 교안은 판 관리 규칙(versioning)으로 붙는다.
- 고치기: 과목명·학수번호, 강좌의 교수명, 자료 제목·종류.
- 지우기 (화면에서 한 번 더 확인받는다)
  - 과목: 딸린 강좌 전부와 '내 과목' 등록까지 함께 지운다.
  - 강좌: 딸린 자료·챕터·개념·문제·풀이 기록·족보 평가와 선택을 함께 지운다. 추가 요청은 연결만 끊는다.
  - 자료: 최신판을 지우면 바로 이전 판들이 다시 최신판이 되고, 이 자료를 근거로 쓰던 문제는
    근거 문장을 남은 자료에서 다시 찾는다(못 찾으면 근거 쪽만 비운다). 챕터 연결은 이전 판으로 옮긴다.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import AdminUser
from app.features.courses.router import CourseOut, SubjectOut, _course_out, ensure_course
from app.features.materials.router import MaterialOut, UploadOut, _out, read_pdf
from app.features.materials.versioning import add_material, relink_problems
from app.models import (
    Attempt,
    Chapter,
    Concept,
    Course,
    CourseRequest,
    Enrollment,
    ExamSelection,
    Material,
    MaterialVote,
    Problem,
    ProblemConcept,
    Professor,
    Subject,
)

router = APIRouter(prefix="/admin", tags=["admin"])

Kind = Literal["lecture", "exam", "note"]


class AdminCourseCreated(BaseModel):
    course: CourseOut
    created: bool  # False면 이미 있던 강좌에 자료만 붙였다
    uploads: list[UploadOut]


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=20)


class CourseAdminUpdate(BaseModel):
    professor_name: str | None = Field(default=None, min_length=1, max_length=50)
    is_public: bool | None = None


class MaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Kind | None = None


async def _add_files(
    session: SessionDep, course_id: int, uploader_id: int, kind: str, files: list[UploadFile]
) -> list[UploadOut]:
    results = []
    for f in files:
        if not f.filename:
            continue
        filename, pages = await read_pdf(f)
        title = filename.rsplit(".", 1)[0]
        m, action, moved, d = add_material(
            session,
            course_id=course_id,
            uploader_id=uploader_id,
            kind=kind,
            title=title,
            filename=filename,
            pages=pages,
        )
        session.flush()
        results.append(
            UploadOut(
                **_out(session, m).model_dump(),
                action=action,
                relinked_problems=moved,
                pages_same=d.same,
                pages_modified=d.modified,
                pages_new=d.new,
                replaced_ids=[] if action == "duplicate" else d.replaced,
            )
        )
    return results


@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def admin_create_course(
    session: SessionDep,
    admin: AdminUser,
    response: Response,
    subject_name: Annotated[str, Form(min_length=1, max_length=100)],
    professor_name: Annotated[str, Form(min_length=1, max_length=50)],
    subject_code: Annotated[str | None, Form(max_length=20)] = None,
    kind: Annotated[Kind, Form()] = "lecture",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> AdminCourseCreated:
    """과목·교수·강좌를 만들고(있으면 그대로 쓰고) 자료 PDF를 여러 개 붙인다. 파일 없이도 된다."""
    course, created = ensure_course(
        session,
        subject_name=subject_name.strip(),
        subject_code=(subject_code or "").strip() or None,
        professor_name=professor_name.strip(),
        created_by=admin.id,
    )
    uploads = await _add_files(session, course.id, admin.id, kind, files or [])
    session.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return AdminCourseCreated(course=_course_out(session, course), created=created, uploads=uploads)


@router.patch("/subjects/{subject_id}")
def admin_update_subject(
    subject_id: int, body: SubjectUpdate, session: SessionDep, _: AdminUser
) -> SubjectOut:
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "과목이 없습니다")
    if body.name is not None:
        name = body.name.strip()
        other = session.exec(select(Subject).where(Subject.name == name)).first()
        if other and other.id != subject.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "같은 이름의 과목이 이미 있습니다")
        subject.name = name
    if body.code is not None:
        subject.code = body.code.strip() or None
    session.add(subject)
    session.commit()
    n = session.exec(
        select(func.count()).select_from(Course).where(Course.subject_id == subject.id)
    ).one()
    return SubjectOut(id=subject.id, name=subject.name, code=subject.code, course_count=n)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_subject(subject_id: int, session: SessionDep, _: AdminUser) -> None:
    subject = session.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "과목이 없습니다")
    for course in session.exec(select(Course).where(Course.subject_id == subject_id)).all():
        _purge_course(session, course)
    session.delete(subject)
    session.commit()


@router.patch("/courses/{course_id}")
def admin_update_course(
    course_id: int, body: CourseAdminUpdate, session: SessionDep, _: AdminUser
) -> CourseOut:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "강좌가 없습니다")
    if body.professor_name is not None:
        name = body.professor_name.strip()
        professor = session.exec(select(Professor).where(Professor.name == name)).first()
        if professor is None:
            professor = Professor(name=name)
            session.add(professor)
            session.flush()
        dup = session.exec(
            select(Course).where(
                Course.subject_id == course.subject_id, Course.professor_id == professor.id
            )
        ).first()
        if dup and dup.id != course.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "같은 과목에 그 교수님 강좌가 이미 있습니다"
            )
        course.professor_id = professor.id
    if body.is_public is not None:
        course.is_public = body.is_public
    session.add(course)
    session.commit()
    return _course_out(session, course)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_course(course_id: int, session: SessionDep, _: AdminUser) -> None:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "강좌가 없습니다")
    _purge_course(session, course)
    session.commit()


def _delete_all(session, rows) -> None:
    for r in rows:
        session.delete(r)
    session.flush()


def _purge_course(session, course: Course) -> None:
    """강좌와 딸린 것 전부를 지운다(커밋은 부르는 쪽에서)."""
    cid = course.id
    for r in session.exec(select(CourseRequest).where(CourseRequest.course_id == cid)).all():
        r.course_id = None
        session.add(r)
    # 수강 기록은 남기고 강좌 연결만 끊는다(다시 열리면 다시 이어진다)
    for e in session.exec(select(Enrollment).where(Enrollment.course_id == cid)).all():
        e.course_id = None
        session.add(e)
    chapters = session.exec(select(Chapter).where(Chapter.course_id == cid)).all()
    ch_ids = [c.id for c in chapters]
    problems = (
        session.exec(select(Problem).where(Problem.chapter_id.in_(ch_ids))).all()  # type: ignore[attr-defined]
        if ch_ids
        else []
    )
    p_ids = [p.id for p in problems]
    if p_ids:
        _delete_all(
            session, session.exec(select(Attempt).where(Attempt.problem_id.in_(p_ids))).all()
        )  # type: ignore[attr-defined]
        _delete_all(
            session,
            session.exec(select(ProblemConcept).where(ProblemConcept.problem_id.in_(p_ids))).all(),  # type: ignore[attr-defined]
        )
    _delete_all(session, problems)
    if ch_ids:
        _delete_all(
            session, session.exec(select(Concept).where(Concept.chapter_id.in_(ch_ids))).all()
        )  # type: ignore[attr-defined]
    _delete_all(session, chapters)
    _delete_all(
        session, session.exec(select(ExamSelection).where(ExamSelection.course_id == cid)).all()
    )
    materials = session.exec(select(Material).where(Material.course_id == cid)).all()
    m_ids = [m.id for m in materials]
    if m_ids:
        _delete_all(
            session,
            session.exec(select(MaterialVote).where(MaterialVote.material_id.in_(m_ids))).all(),  # type: ignore[attr-defined]
        )
    for m in materials:  # 판 연결부터 끊고 지운다
        m.replaced_by = None
        session.add(m)
    session.flush()
    _delete_all(session, materials)
    session.delete(course)
    session.flush()


@router.patch("/materials/{material_id}")
def admin_update_material(
    material_id: int, body: MaterialUpdate, session: SessionDep, _: AdminUser
) -> MaterialOut:
    m = session.get(Material, material_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "자료가 없습니다")
    if body.title is not None:
        m.title = body.title.strip()
    if body.kind is not None:
        m.kind = body.kind
    session.add(m)
    session.commit()
    return _out(session, m)


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_material(material_id: int, session: SessionDep, _: AdminUser) -> None:
    m = session.get(Material, material_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "자료가 없습니다")
    # 이 자료가 대체했던 이전 판들을 다시 최신판으로
    restored = session.exec(select(Material).where(Material.replaced_by == m.id)).all()
    for old in restored:
        old.replaced_by = m.replaced_by  # 지운 자료도 옛 판이었으면 그 새 판을 가리키게
        session.add(old)
    # 이 자료를 가리키던 문제: 근거 문장을 남은 최신 자료에서 다시 찾는다
    probs = session.exec(select(Problem).where(Problem.source_material_id == m.id)).all()
    for p in probs:
        p.source_material_id, p.source_page = None, None
        session.add(p)
    session.flush()
    latest = session.exec(
        select(Material).where(
            Material.course_id == m.course_id,
            Material.id != m.id,
            Material.replaced_by.is_(None),  # type: ignore[union-attr]
        )
    ).all()
    orphan = {p.id for p in probs}
    for other in latest:
        relink_problems(session, m.course_id, other, only=orphan)
    # 챕터가 이 자료를 가리키면 되살아난 이전 판으로(없으면 연결만 끊는다)
    for ch in session.exec(select(Chapter).where(Chapter.material_id == m.id)).all():
        ch.material_id = restored[0].id if restored else None
        session.add(ch)
    _delete_all(
        session, session.exec(select(MaterialVote).where(MaterialVote.material_id == m.id)).all()
    )
    _delete_all(
        session, session.exec(select(ExamSelection).where(ExamSelection.material_id == m.id)).all()
    )
    session.delete(m)
    session.commit()
