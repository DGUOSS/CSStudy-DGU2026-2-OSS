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
      강좌 ─< 시험지(Paper) ─< 응시(PaperTake) ─< 서술형 답 칸 이미지(PaperEssayImage)
      문제 ─< 오개념(Misconception)   (틀린 보기마다 '왜 골랐을까'. Claude로 문제당 한 번 만든다)
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, LargeBinary, Text, UniqueConstraint, false
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
    # 문제 유형. 지금 문제 은행은 객관식(mcq)뿐이고, 문제 생성(question-ai)이 서술형을 넣을 수 있게 칸을 둔다.
    # 서술형(essay)은 choices=[], answer_index=-1 이고 model_answer·rubric으로 채점한다.
    qtype: str = Field(default="mcq", max_length=10, sa_column_kwargs={"server_default": "mcq"})
    model_answer: str | None = Field(default=None, sa_column=Column(Text))
    rubric: list[str] | None = Field(default=None, sa_column=Column(JSON))  # "항목 — n점"
    points: int = Field(default=1, sa_column_kwargs={"server_default": "1"})


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


class CourseReview(SQLModel, table=True):
    __tablename__ = "course_reviews"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    recommendation: int
    is_deleted: bool = Field(default=False)
    enrollment_id: int = Field(foreign_key="enrollments.id")
    year: str = Field(max_length=4)
    sem_cd: str = Field(max_length=20)
    difficulty: int
    workload: int
    content: str = Field(sa_column=Column(Text, nullable=False))
    # 그 학기 수업에 팀 프로젝트(조별 과제)가 있었는가. None = 답하지 않음(옛 후기 포함)
    team_project: bool | None = None
    created_at: datetime = Field(default_factory=_now)


class TeamProjectReport(SQLModel, table=True):
    """수강생의 팀플 제보: 그 학기 수업에 팀 프로젝트가 있었는가. 학생당 (강좌, 학기)마다 하나, 바꿀 수 있다."""

    __tablename__ = "team_project_reports"
    __table_args__ = (UniqueConstraint("user_id", "course_id", "year", "sem_cd"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    year: str = Field(max_length=4)
    sem_cd: str = Field(max_length=20)
    team_project: bool
    updated_at: datetime = Field(default_factory=_now)


class TeamProjectOverride(SQLModel, table=True):
    """운영진이 직접 정한 팀플 여부. 계획서·제보보다 우선한다."""

    __tablename__ = "team_project_overrides"
    __table_args__ = (UniqueConstraint("course_id", "year", "sem_cd"),)
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    year: str = Field(max_length=4)
    sem_cd: str = Field(max_length=20)
    team_project: bool
    note: str = Field(default="", max_length=300)
    set_by: int | None = Field(default=None, foreign_key="users.id")
    updated_at: datetime = Field(default_factory=_now)


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
    # 강의계획서로 판정한 팀 프로젝트 여부(features/team_project). 시간표를 다시 가져와도 지우지 않는다.
    # yes(있음) | no(없다고 적힘) | not_mentioned(계획서에 언급 없음) | None(계획서 아직 안 봄)
    team_project: str | None = Field(default=None, max_length=20)
    team_evidence: str | None = Field(default=None, max_length=300)  # 판정 근거 문장
    syllabus_checked_at: datetime | None = None


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


class Paper(SQLModel, table=True):
    """인쇄해서 보는 시험지. 문제 순서를 고정해 같은 시험지를 본 사람끼리 등수를 매긴다."""

    __tablename__ = "papers"
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    created_by: int = Field(foreign_key="users.id")
    title: str = Field(max_length=100)
    problem_ids: list[int] = Field(sa_column=Column(JSON, nullable=False))
    time_limit_min: int
    source: str = Field(default="bank", max_length=20)  # bank | generated(문제 생성 연결 후)
    created_at: datetime = Field(default_factory=_now)


class PaperTake(SQLModel, table=True):
    """한 사람의 한 번 응시. [시험 시작] 때 만들고, 답안지 사진을 확인해 제출하면 채점한다."""

    __tablename__ = "paper_takes"
    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="papers.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    started_at: datetime = Field(default_factory=_now)
    submitted_at: datetime | None = None
    elapsed_sec: int | None = None
    late: bool = Field(default=False)  # 제한 시간 + 여유 시간을 넘겨 제출
    answers: list[int | None] | None = Field(default=None, sa_column=Column(JSON))
    mcq_score: int | None = None
    essay_score: int | None = None  # None = 서술형 채점 대기(또는 서술형 없음)
    total_points: int = 0
    status: str = Field(default="started", max_length=20)  # started | submitted | abandoned
    # 일시정지: 멈춘 동안은 시간이 흐르지 않는다. 등수표에는 정지를 썼는지 표시한다
    paused_at: datetime | None = None
    paused_sec: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    pause_count: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
    # 서술형 채점 상태: none(서술형 없음) | pending(채점 중) | done | unavailable(키 없음·실패)
    essay_status: str = Field(
        default="none", max_length=20, sa_column_kwargs={"server_default": "none"}
    )
    summary: str | None = Field(default=None, sa_column=Column(Text))  # 결과 요약(Claude)


class PaperEssayImage(SQLModel, table=True):
    """답안지 사진에서 잘라 낸 서술형 답 칸. 전체 사진은 저장하지 않는다."""

    __tablename__ = "paper_essay_images"
    id: int | None = Field(default=None, primary_key=True)
    take_id: int = Field(foreign_key="paper_takes.id", index=True)
    problem_id: int = Field(foreign_key="problems.id")
    image: bytes = Field(sa_column=Column(LargeBinary, nullable=False))  # JPEG
    score: int | None = None  # Claude 채점 점수(None = 아직)
    transcription: str | None = Field(default=None, sa_column=Column(Text))
    feedback: str | None = Field(default=None, sa_column=Column(Text))
    rubric_detail: list[dict] | None = Field(default=None, sa_column=Column(JSON))
    graded_at: datetime | None = None


class Misconception(SQLModel, table=True):
    """객관식 문제의 틀린 보기 하나에 대한 오개념 추정(Claude). 문제당 한 번 만들어 두고 풀 때는 꺼내 쓴다.

    칸 이름은 오개념 실험실(박상혁, MisconceptionProbe)과 맞췄다: hypothesis, explanation, evidence, source_*, status.
    status: auto(근거 확인되면 'AI 추정'으로 보임) | hidden(관리자가 숨김) | approved(관리자 확인)
    """

    __tablename__ = "misconceptions"
    __table_args__ = (UniqueConstraint("problem_id", "wrong_choice_index"),)
    id: int | None = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    wrong_choice_index: int  # 0부터
    label: str = Field(max_length=100)
    hypothesis: str = Field(sa_column=Column(Text, nullable=False))
    explanation: str = Field(sa_column=Column(Text, nullable=False))
    evidence: str | None = Field(default=None, sa_column=Column(Text))
    evidence_found: bool = False  # 근거 문장이 그 교안 쪽에 실제로 있는가
    source_material_id: int | None = Field(default=None, foreign_key="materials.id")
    source_page: int | None = None
    status: str = Field(default="auto", max_length=20)
    model: str = Field(default="", max_length=50)
    created_at: datetime = Field(default_factory=_now)


class NoticePreference(SQLModel, table=True):
    """공지 구독 설정. 학과 소속/수강 인증과 무관하다."""

    __tablename__ = "notice_preferences"
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    department_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class StudyGroup(SQLModel, table=True):
    """과목별 모집 게시글. 참여 신청/인원 집계는 별도 기능으로 추가한다."""

    __tablename__ = "study_groups"
    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=100)
    description: str = Field(sa_column=Column(Text, nullable=False))
    capacity: int
    mode: str = Field(max_length=20)
    schedule: str = Field(max_length=200)
    location: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=_now)
    closed_at: datetime | None = None


class StudyApplication(SQLModel, table=True):
    __tablename__ = "study_applications"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="study_groups.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    status: str = Field(default="pending", max_length=20)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class StudyMessage(SQLModel, table=True):
    """스터디 공간 채팅 한 줄. 개설자와 승인된 참여자만 읽고 쓴다."""

    __tablename__ = "study_messages"
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="study_groups.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=_now)


class ProfessorSummary(SQLModel, table=True):
    """교원번호별 공유 요약과 생성 임대. 시간은 UTC로 저장한다."""

    __tablename__ = "professor_summaries"
    emp_no: str = Field(primary_key=True, max_length=20)
    fingerprint: str = Field(default="", max_length=64)
    status: str = Field(default="failed", max_length=20)
    model: str = Field(default="", max_length=100)
    summary: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    generated_at: datetime | None = None
    lease_token: str | None = Field(default=None, max_length=36)
    lease_until: datetime | None = None
    retry_after: datetime | None = None
