"""DB 테이블 정의. 테이블을 바꾸면 Alembic 마이그레이션을 만든다 (docs/DB.md 참고).

구조: 과목(Subject) ─< 강좌(Course) >─ 교수(Professor)
      강좌 ─< 자료(Material)
      강좌 ─< 챕터(Chapter) ─< 개념(Concept)
      챕터 ─< 문제(Problem) >─< 개념   (ProblemConcept)
      사용자(User) ─< 풀이 기록(Attempt) >─ 문제
      사용자 ─< 강좌 추가 요청(CourseRequest) ─ (승인 후) 강좌
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=50)
    password_hash: str
    role: str = Field(default="user", max_length=20)  # user | admin
    created_at: datetime = Field(default_factory=_now)


class Subject(SQLModel, table=True):
    __tablename__ = "subjects"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=100)
    code: str | None = Field(default=None, max_length=20)  # 학수번호 앞부분 예: CSC2001


class Professor(SQLModel, table=True):
    __tablename__ = "professors"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    department: str | None = Field(default=None, max_length=100)


class Course(SQLModel, table=True):
    """과목 + 교수 한 쌍. 학기가 바뀌어도 같은 강좌로 본다(기출을 모으기 위해)."""

    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("subject_id", "professor_id"),)
    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    professor_id: int = Field(foreign_key="professors.id", index=True)
    info: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    exam_info: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)


class CourseRequest(SQLModel, table=True):
    """없는 과목·강좌 추가 요청. 관리자가 승인하면 과목·교수·강좌가 생기고, 함께 낸 교안이 자료로 붙는다."""

    __tablename__ = "course_requests"
    id: int | None = Field(default=None, primary_key=True)
    requester_id: int = Field(foreign_key="users.id", index=True)
    subject_name: str = Field(max_length=100)
    subject_code: str | None = Field(default=None, max_length=20)
    professor_name: str = Field(max_length=50)
    semester: str | None = Field(default=None, max_length=20)  # 예: 2026-2
    note: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    # 교안을 함께 냈으면 쪽별 텍스트를 승인 전까지 여기에 둔다. '교안 없음'이면 비어 있다.
    material_title: str | None = Field(default=None, max_length=200)
    material_filename: str | None = Field(default=None, max_length=255)
    material_pages: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="pending", max_length=20, index=True)  # pending|approved|rejected
    reject_reason: str | None = Field(default=None, sa_column=Column(Text))
    reviewed_by: int | None = Field(default=None, foreign_key="users.id")
    reviewed_at: datetime | None = None
    course_id: int | None = Field(default=None, foreign_key="courses.id")  # 승인 결과 강좌
    created_at: datetime = Field(default_factory=_now)


class Material(SQLModel, table=True):
    __tablename__ = "materials"
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    uploader_id: int | None = Field(default=None, foreign_key="users.id")
    kind: str = Field(max_length=20)  # lecture(교안) | exam(기출·족보) | note(시험 정보 등)
    title: str = Field(max_length=200)
    filename: str = Field(max_length=255)
    page_count: int = 0
    # 쪽별 텍스트. pages[0]이 1쪽이다.
    pages: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="approved", max_length=20)  # 지금은 자동 승인
    # 판 관리: 같은 주차·같은 문서의 새 판이 올라오면 옛 판의 replaced_by에 새 판 id를 적는다.
    # 옛 판은 지우지 않는다(옛 문제의 근거 쪽 링크가 깨지지 않게). 목록에는 최신판만 보인다.
    week: int | None = None  # 제목·파일명에서 읽은 주차
    version: int = 1
    replaced_by: int | None = Field(default=None, foreign_key="materials.id")
    created_at: datetime = Field(default_factory=_now)


class Chapter(SQLModel, table=True):
    __tablename__ = "chapters"
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    order: int
    title: str = Field(max_length=200)
    material_id: int | None = Field(default=None, foreign_key="materials.id")


class Concept(SQLModel, table=True):
    __tablename__ = "concepts"
    id: int | None = Field(default=None, primary_key=True)
    chapter_id: int = Field(foreign_key="chapters.id", index=True)
    name: str = Field(max_length=100)


class Problem(SQLModel, table=True):
    __tablename__ = "problems"
    id: int | None = Field(default=None, primary_key=True)
    chapter_id: int = Field(foreign_key="chapters.id", index=True)
    question: str = Field(sa_column=Column(Text, nullable=False))
    choices: list[str] = Field(sa_column=Column(JSON, nullable=False))
    answer_index: int
    explanation: str = Field(sa_column=Column(Text, nullable=False))
    # 정답 근거가 되는 교안 문장과 위치
    evidence: str | None = Field(default=None, sa_column=Column(Text))
    source_material_id: int | None = Field(default=None, foreign_key="materials.id")
    source_page: int | None = None
    origin: str = Field(default="sample", max_length=20)  # sample | llm | exam
    created_at: datetime = Field(default_factory=_now)


class ProblemConcept(SQLModel, table=True):
    __tablename__ = "problem_concepts"
    problem_id: int = Field(foreign_key="problems.id", primary_key=True)
    concept_id: int = Field(foreign_key="concepts.id", primary_key=True)


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    chosen_index: int
    correct: bool
    created_at: datetime = Field(default_factory=_now)
