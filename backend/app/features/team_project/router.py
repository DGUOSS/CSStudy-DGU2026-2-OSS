"""팀 프로젝트 라벨 조회와 강의계획서 판정 결과 저장."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import AdminUser, CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import norm_code
from app.features.team_project.schemas import TeamLabelOut, label_out
from app.features.team_project.service import classify_syllabus, term_labels
from app.models import CatalogOffering

router = APIRouter(tags=["team-project"])


class CourseTeamOut(BaseModel):
    latest: TeamLabelOut | None
    terms: list[TeamLabelOut]


@router.get("/courses/{course_id}/team-project")
def course_team_project(course_id: int, session: SessionDep, _: CurrentUser) -> CourseTeamOut:
    """학기별 팀 프로젝트 라벨. 수강 기록이 없어도 볼 수 있다(수강 전에 고르는 데 쓰는 정보)."""
    labels = [label_out(t) for t in term_labels(session, get_course_or_404(session, course_id))]
    return CourseTeamOut(latest=labels[0] if labels else None, terms=labels)


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
