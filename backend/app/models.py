"""DB 테이블 정의. 테이블을 바꾸면 Alembic 마이그레이션을 만든다 (docs/DB.md 참고).

구조: 과목(Subject) ─< 강좌(Course) >─ 교수(Professor)
      강좌 ─< 자료(Material)
      강좌 ─< 챕터(Chapter) ─< 개념(Concept)
      챕터 ─< 문제(Problem) >─< 개념   (ProblemConcept)
      사용자(User) ─< 풀이 기록(Attempt) >─ 문제
      사용자 ─< 강좌 추가 요청(CourseRequest) ─ (승인 후) 강좌
      사용자 ─< 수강 기록(Enrollment) >─ 강좌   (엔드림스에서 가져온 기록. 기록이 있는 강좌에만 들어간다)
      개설 목록(CatalogOffering)                 (엔드림스 종합강의시간표. 강좌를 만들지 않는 참고용)
      사용자 ─< 족보 평가(MaterialVote) >─ 자료(족보)
      사용자 ─< 족보 선택(ExamSelection) >─ 자료(족보)   (문제 생성 때 참고할 족보)
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, Text, UniqueConstraint, false
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
    # 엔드림스 교원번호(EMP_NO). 동명이인을 가른다. 수강 기록에서만 만든 교수는 비어 있다가
    # 개설 목록을 가져오면 채워진다.
    emp_no: str | None = Field(default=None, max_length=20, unique=True, index=True)
    department: str | None = Field(default=None, max_length=100)


class Course(SQLModel, table=True):
    """과목 + 교수 한 쌍. 학기가 바뀌어도 같은 강좌로 본다(기출을 모으기 위해)."""

    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("subject_id", "professor_id"),)
    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    professor_id: int = Field(foreign_key="professors.id", index=True)
    info: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    # 안 씀: 시험 정보는 자료(kind=note)로 올린다. 화면에서는 뺐고 칸만 남아 있다.
    exam_info: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    created_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)
    # 공용 강좌: 수강 기록이 없어도 누구나 들어간다(팀 시험·공개 자료용). 관리자가 켠다
    is_public: bool = Field(default=False, sa_column_kwargs={"server_default": false()})


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
    # 여러 파일: [{"filename", "page_count", "pages"}]. 승인·반려 뒤에는 pages만 비운다.
    # (위의 material_* 세 칸은 파일 하나만 받던 예전 요청용으로 남겨 둔다)
    material_files: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]")
    )
    # 요청 근거: catalog(이번 학기 개설 목록에서 고름) | record(내 수강 기록) | manual(예전 방식)
    source: str = Field(
        default="manual", max_length=20, sa_column_kwargs={"server_default": "manual"}
    )
    professor_emp_no: str | None = Field(default=None, max_length=20)
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
    week: int | None = None  # 파일명에서 읽은 주차
    version: int = 1
    # 강좌·종류별 번호. 제목은 '과목명 종류 번호'(예: 기초프로그래밍 족보 2)로 자동으로 붙는다.
    # 새 판은 대체한 옛 판의 번호를 이어받는다.
    seq: int | None = None
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


class Enrollment(SQLModel, table=True):
    """엔드림스에서 가져온 수강 기록 한 줄(과목 찾기에 필요한 칸만). 성적·개인 정보는 저장하지 않는다.

    엔드림스에서 수업 하나는 (연도, 학기 코드, 학수번호, 분반)으로 정해진다. course_id는 그 수업이
    사이트의 어느 강좌(과목+교수)인지이고, 아직 열린 강좌가 없으면 비어 있다(강좌가 열리면 채운다).
    """

    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "year", "sem_cd", "sbj_no", "dvcls"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    year: str = Field(max_length=4)
    sem_cd: str = Field(max_length=20)  # 예: CM160.20 (2학기)
    sbj_no: str = Field(max_length=20, index=True)  # 학수번호
    sbj_nm: str = Field(max_length=200)
    dvcls: str = Field(default="", max_length=10)  # 분반
    emp_nm: str | None = Field(default=None, max_length=50)  # 성적 기록에만 있음
    emp_no: str | None = Field(default=None, max_length=20)  # 개설 목록과 맞춰서 채움
    course_id: int | None = Field(default=None, foreign_key="courses.id", index=True)
    source: str = Field(default="ndrims", max_length=20)
    created_at: datetime = Field(default_factory=_now)


class CatalogOffering(SQLModel, table=True):
    """엔드림스 종합강의시간표의 개설 강좌 한 줄. 강좌 찾기·요청·교수 확정에 쓰는 참고용 목록."""

    __tablename__ = "catalog_offerings"
    __table_args__ = (UniqueConstraint("year", "sem_cd", "sbj_no", "dvcls"),)
    id: int | None = Field(default=None, primary_key=True)
    year: str = Field(max_length=4, index=True)
    sem_cd: str = Field(max_length=20, index=True)
    sbj_no: str = Field(max_length=20, index=True)
    sbj_nm: str = Field(max_length=200)
    dvcls: str = Field(default="", max_length=10)
    emp_no: str | None = Field(default=None, max_length=20)
    emp_nm: str | None = Field(default=None, max_length=50)
    colg_nm: str | None = Field(default=None, max_length=100)
    dpt_nm: str | None = Field(default=None, max_length=100)
    cpdiv_nm: str | None = Field(default=None, max_length=50)  # 이수구분
    cdt: str | None = Field(default=None, max_length=10)  # 학점
    timetable: str | None = Field(default=None, max_length=300)
    room: str | None = Field(default=None, max_length=300)
    mid_rate: int | None = None
    fnl_rate: int | None = None
    atnd_rate: int | None = None
    proj_rate: int | None = None
    plan_url: str | None = Field(default=None, max_length=500)
    imported_at: datetime = Field(default_factory=_now)


class MaterialVote(SQLModel, table=True):
    """족보 좋아요(+1)/싫어요(-1). 사용자당 자료 하나에 한 표."""

    __tablename__ = "material_votes"
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    material_id: int = Field(foreign_key="materials.id", primary_key=True, index=True)
    value: int  # 1 | -1
    created_at: datetime = Field(default_factory=_now)


class ExamSelection(SQLModel, table=True):
    """문제 풀이 전에 고른 족보. 문제 생성(services/llm.py)이 이 족보를 출제 스타일 예시로 참고한다."""

    __tablename__ = "exam_selections"
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    material_id: int = Field(foreign_key="materials.id", primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    created_at: datetime = Field(default_factory=_now)
