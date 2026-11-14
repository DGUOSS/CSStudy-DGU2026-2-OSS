"""과목 → 교수(강좌) → 강좌 정보."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import AdminUser, CurrentUser
from app.features.enrollments.service import can_enter, relink_course, require_course_access
from app.models import Chapter, Course, Material, Problem, Professor, Subject

router = APIRouter(tags=["courses"])


class SubjectOut(BaseModel):
    id: int
    name: str
    code: str | None
    course_count: int


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=20)


class CourseOut(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    professor_id: int
    professor_name: str
    info: str
    exam_info: str
    material_count: int
    problem_count: int
    accessible: bool = True  # 이 사용자가 들어갈 수 있는가(수강 기록이 있거나 공용 강좌)
    is_public: bool = False


class CourseIn(BaseModel):
    subject_id: int
    professor_name: str = Field(min_length=1, max_length=50)
    info: str = ""
    exam_info: str = ""


class CourseUpdate(BaseModel):
    info: str | None = None
    exam_info: str | None = None


def _course_out(session: SessionDep, course: Course) -> CourseOut:
    subject = session.get(Subject, course.subject_id)
    professor = session.get(Professor, course.professor_id)
    material_count = session.exec(
        select(func.count()).select_from(Material).where(Material.course_id == course.id)
    ).one()
    problem_count = session.exec(
        select(func.count())
        .select_from(Problem)
        .join(Chapter, Chapter.id == Problem.chapter_id)
        .where(Chapter.course_id == course.id)
    ).one()
    return CourseOut(
        id=course.id,
        subject_id=subject.id,
        subject_name=subject.name,
        professor_id=professor.id,
        professor_name=professor.name,
        info=course.info,
        is_public=course.is_public,
        exam_info=course.exam_info,
        material_count=material_count,
        problem_count=problem_count,
    )


def get_course_or_404(session: SessionDep, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "강좌가 없습니다")
    return course


def ensure_course(
    session: SessionDep,
    *,
    subject_name: str,
    subject_code: str | None,
    professor_name: str,
    created_by: int | None,
) -> tuple[Course, bool]:
    """과목·교수·강좌를 찾고 없으면 만든다. (강좌, 새로 만들었는지). commit은 하지 않는다."""
    subject = session.exec(select(Subject).where(Subject.name == subject_name)).first()
    if subject is None:
        subject = Subject(name=subject_name, code=subject_code or None)
        session.add(subject)
        session.flush()
    elif subject_code and not subject.code:
        subject.code = subject_code
        session.add(subject)
    professor = session.exec(select(Professor).where(Professor.name == professor_name)).first()
    if professor is None:
        professor = Professor(name=professor_name)
        session.add(professor)
        session.flush()
    course = session.exec(
        select(Course).where(Course.subject_id == subject.id, Course.professor_id == professor.id)
    ).first()
    if course is not None:
        return course, False
    course = Course(subject_id=subject.id, professor_id=professor.id, created_by=created_by)
    session.add(course)
    session.flush()
    return course, True


@router.get("/subjects")
def list_subjects(session: SessionDep) -> list[SubjectOut]:
    rows = session.exec(
        select(Subject, func.count(Course.id))
        .join(Course, Course.subject_id == Subject.id, isouter=True)
        .group_by(Subject.id)
        .order_by(Subject.name)
    ).all()
    return [SubjectOut(id=s.id, name=s.name, code=s.code, course_count=n) for s, n in rows]


@router.post("/subjects", status_code=status.HTTP_201_CREATED)
def create_subject(body: SubjectIn, session: SessionDep, _: AdminUser) -> SubjectOut:
    """관리자 전용. 일반 사용자는 POST /course-requests로 요청한다."""
    name = body.name.strip()
    if session.exec(select(Subject).where(Subject.name == name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 있는 과목입니다")
    subject = Subject(name=name, code=body.code)
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return SubjectOut(id=subject.id, name=subject.name, code=subject.code, course_count=0)


@router.get("/subjects/{subject_id}/courses")
def list_courses(subject_id: int, session: SessionDep, user: CurrentUser) -> list[CourseOut]:
    if session.get(Subject, subject_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "과목이 없습니다")
    # 목록은 보여 주되, 수강 기록이 없는 교수님 강좌는 잠겨 있다고 표시한다
    courses = session.exec(select(Course).where(Course.subject_id == subject_id)).all()
    out = [
        _course_out(session, c).model_copy(update={"accessible": can_enter(session, user, c)})
        for c in courses
    ]
    return sorted(out, key=lambda c: (not c.accessible, c.professor_name))


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(body: CourseIn, session: SessionDep, user: AdminUser) -> CourseOut:
    """관리자 전용. 일반 사용자는 POST /course-requests로 요청하고 관리자가 승인한다."""
    if session.get(Subject, body.subject_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "과목이 없습니다")
    name = body.professor_name.strip()
    professor = session.exec(select(Professor).where(Professor.name == name)).first()
    if professor is None:
        professor = Professor(name=name)
        session.add(professor)
        session.flush()
    exists = session.exec(
        select(Course).where(
            Course.subject_id == body.subject_id, Course.professor_id == professor.id
        )
    ).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 있는 강좌입니다")
    course = Course(
        subject_id=body.subject_id,
        professor_id=professor.id,
        info=body.info,
        exam_info=body.exam_info,
        created_by=user.id,
    )
    session.add(course)
    session.flush()
    relink_course(session, course)  # 이 강좌를 기다리던 수강 기록을 잇는다
    session.commit()
    session.refresh(course)
    return _course_out(session, course)


@router.get("/courses/{course_id}")
def get_course(course_id: int, session: SessionDep, user: CurrentUser) -> CourseOut:
    course = get_course_or_404(session, course_id)
    require_course_access(session, user, course)
    return _course_out(session, course)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int, body: CourseUpdate, session: SessionDep, _: AdminUser
) -> CourseOut:
    """강좌 정보·시험 정보는 강좌마다 하나인 공용 안내라서 관리자만 고친다."""
    course = get_course_or_404(session, course_id)
    if body.info is not None:
        course.info = body.info
    if body.exam_info is not None:
        course.exam_info = body.exam_info
    session.add(course)
    session.commit()
    session.refresh(course)
    return _course_out(session, course)
