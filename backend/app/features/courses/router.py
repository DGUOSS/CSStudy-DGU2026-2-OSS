"""과목 → 교수(강좌) → 강좌 정보."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
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
        exam_info=course.exam_info,
        material_count=material_count,
        problem_count=problem_count,
    )


def get_course_or_404(session: SessionDep, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "강좌가 없습니다")
    return course


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
def create_subject(body: SubjectIn, session: SessionDep, _: CurrentUser) -> SubjectOut:
    name = body.name.strip()
    if session.exec(select(Subject).where(Subject.name == name)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 있는 과목입니다")
    subject = Subject(name=name, code=body.code)
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return SubjectOut(id=subject.id, name=subject.name, code=subject.code, course_count=0)


@router.get("/subjects/{subject_id}/courses")
def list_courses(subject_id: int, session: SessionDep) -> list[CourseOut]:
    if session.get(Subject, subject_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "과목이 없습니다")
    courses = session.exec(select(Course).where(Course.subject_id == subject_id)).all()
    out = [_course_out(session, c) for c in courses]
    return sorted(out, key=lambda c: c.professor_name)


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(body: CourseIn, session: SessionDep, user: CurrentUser) -> CourseOut:
    """없는 강좌를 사용자가 추가한다. 지금은 자동 승인."""
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
    session.commit()
    session.refresh(course)
    return _course_out(session, course)


@router.get("/courses/{course_id}")
def get_course(course_id: int, session: SessionDep) -> CourseOut:
    return _course_out(session, get_course_or_404(session, course_id))


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int, body: CourseUpdate, session: SessionDep, _: CurrentUser
) -> CourseOut:
    course = get_course_or_404(session, course_id)
    if body.info is not None:
        course.info = body.info
    if body.exam_info is not None:
        course.exam_info = body.exam_info
    session.add(course)
    session.commit()
    session.refresh(course)
    return _course_out(session, course)
