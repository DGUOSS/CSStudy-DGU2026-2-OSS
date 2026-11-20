"""팀 프로젝트 라벨 조회와 강의계획서 판정 결과 저장."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import AdminUser, CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import norm_code, term_label
from app.features.team_project.schemas import TeamLabelOut, label_out
from app.features.team_project.service import classify_syllabus, term_labels
from app.models import (
    CatalogOffering,
    CourseReview,
    Enrollment,
    TeamProjectOverride,
    TeamProjectReport,
    User,
)

router = APIRouter(tags=["team-project"])


class MyTermOut(BaseModel):
    """내 수강 기록이 있는 학기와 내 응답(제보 버튼, 없으면 후기에서 한 답)."""

    year: str
    sem_cd: str
    term: str
    my_answer: bool | None


class CourseTeamOut(BaseModel):
    latest: TeamLabelOut | None
    terms: list[TeamLabelOut]
    my_terms: list[MyTermOut]


def _course_team(session, course, user: User) -> CourseTeamOut:
    labels = [label_out(t) for t in term_labels(session, course)]
    reports = {
        (r.year, r.sem_cd): r.team_project
        for r in session.exec(
            select(TeamProjectReport).where(
                TeamProjectReport.course_id == course.id, TeamProjectReport.user_id == user.id
            )
        ).all()
    }
    reviewed = {
        (r.year, r.sem_cd): r.team_project
        for r in session.exec(
            select(CourseReview).where(
                CourseReview.course_id == course.id,
                CourseReview.user_id == user.id,
                CourseReview.is_deleted == False,  # noqa: E712
            )
        ).all()
    }
    terms = sorted(
        {
            (e.year, e.sem_cd)
            for e in session.exec(
                select(Enrollment).where(
                    Enrollment.user_id == user.id, Enrollment.course_id == course.id
                )
            ).all()
        },
        reverse=True,
    )
    mine = [
        MyTermOut(
            year=y,
            sem_cd=s,
            term=term_label(y, s),
            my_answer=reports.get((y, s), reviewed.get((y, s))),
        )
        for y, s in terms
    ]
    return CourseTeamOut(latest=labels[0] if labels else None, terms=labels, my_terms=mine)


@router.get("/courses/{course_id}/team-project")
def course_team_project(course_id: int, session: SessionDep, user: CurrentUser) -> CourseTeamOut:
    """학기별 팀 프로젝트 라벨. 수강 기록이 없어도 볼 수 있다(수강 전에 고르는 데 쓰는 정보)."""
    return _course_team(session, get_course_or_404(session, course_id), user)


class TermAnswerIn(BaseModel):
    year: str = Field(pattern=r"^\d{4}$")
    sem_cd: str = Field(min_length=1, max_length=20)
    team_project: bool | None = Field(description="있었다 / 없었다 / null = 응답 지우기")


@router.put("/courses/{course_id}/team-project/report")
def report_team_project(
    course_id: int, body: TermAnswerIn, session: SessionDep, user: CurrentUser
) -> CourseTeamOut:
    """팀플 제보. 그 학기 이 강좌 수강 기록이 있어야 한다. 다시 보내면 바뀐다."""
    course = get_course_or_404(session, course_id)
    took = session.exec(
        select(Enrollment.id).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course_id,
            Enrollment.year == body.year,
            Enrollment.sem_cd == body.sem_cd,
        )
    ).first()
    if took is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "그 학기에 이 강좌를 수강한 기록이 있어야 제보할 수 있습니다"
        )
    r = session.exec(
        select(TeamProjectReport).where(
            TeamProjectReport.user_id == user.id,
            TeamProjectReport.course_id == course_id,
            TeamProjectReport.year == body.year,
            TeamProjectReport.sem_cd == body.sem_cd,
        )
    ).first()
    if body.team_project is None:
        if r:
            session.delete(r)
    else:
        r = r or TeamProjectReport(
            user_id=user.id,
            course_id=course_id,
            year=body.year,
            sem_cd=body.sem_cd,
            team_project=body.team_project,
        )
        r.team_project, r.updated_at = body.team_project, datetime.now(UTC)
        session.add(r)
    session.commit()
    return _course_team(session, course, user)


class OverrideIn(TermAnswerIn):
    note: str = Field(default="", max_length=300)


@router.put("/admin/courses/{course_id}/team-project")
def set_override(
    course_id: int, body: OverrideIn, session: SessionDep, admin: AdminUser
) -> CourseTeamOut:
    """운영진 지정. team_project=null이면 지정을 지워 계획서·제보로 돌아간다."""
    course = get_course_or_404(session, course_id)
    o = session.exec(
        select(TeamProjectOverride).where(
            TeamProjectOverride.course_id == course_id,
            TeamProjectOverride.year == body.year,
            TeamProjectOverride.sem_cd == body.sem_cd,
        )
    ).first()
    if body.team_project is None:
        if o:
            session.delete(o)
    else:
        o = o or TeamProjectOverride(
            course_id=course_id,
            year=body.year,
            sem_cd=body.sem_cd,
            team_project=body.team_project,
        )
        o.team_project, o.note = body.team_project, body.note.strip()
        o.set_by, o.updated_at = admin.id, datetime.now(UTC)
        session.add(o)
    session.commit()
    return _course_team(session, course, admin)


class SyllabusIn(BaseModel):
    year: str = Field(pattern=r"^\d{4}$")
    sem_cd: str = Field(min_length=1, max_length=20)
    sbj_no: str = Field(min_length=1, max_length=20)
    dvcls: str = Field(default="", max_length=10)
    text: str = Field(max_length=100_000)


class SyllabusImportIn(BaseModel):
    rows: list[SyllabusIn] = Field(max_length=5000)


class SyllabusImportOut(BaseModel):
    checked: int
    missing: int  # 개설 목록에 없는 행(시간표를 먼저 가져와야 한다)
    yes: int
    no: int
    not_mentioned: int


@router.post("/admin/catalog/syllabi")
def import_syllabi(body: SyllabusImportIn, session: SessionDep, _: AdminUser) -> SyllabusImportOut:
    """엔드림스 강의계획서 글을 받아 팀 프로젝트 여부만 판정해 저장한다. 계획서 원문은 저장하지 않는다."""
    counts = {"yes": 0, "no": 0, "not_mentioned": 0}
    missing = 0
    now = datetime.now(UTC)
    for r in body.rows:
        o = session.exec(
            select(CatalogOffering).where(
                CatalogOffering.year == r.year,
                CatalogOffering.sem_cd == r.sem_cd,
                CatalogOffering.sbj_no == norm_code(r.sbj_no),
                CatalogOffering.dvcls == r.dvcls,
            )
        ).first()
        if o is None:
            missing += 1
            continue
        o.team_project, o.team_evidence = classify_syllabus(r.text)
        o.syllabus_checked_at = now
        session.add(o)
        counts[o.team_project] += 1
    session.commit()
    return SyllabusImportOut(checked=sum(counts.values()), missing=missing, **counts)
