"""라벨 출력 형식. courses·catalog 라우터도 쓰므로 라우터와 따로 둔다(순환 import 방지)."""

from pydantic import BaseModel, Field

from app.features.team_project.service import TeamHistory, TermLabel


class TeamLabelOut(BaseModel):
    year: str
    sem_cd: str
    term: str
    label: str = Field(description="yes | no | likely_no(계획서에 언급 없음) | unknown")
    source: str | None = Field(description="admin | students | syllabus | null")
    evidence: str | None = Field(description="강의계획서 근거 문장")
    note: str | None = Field(description="운영진 메모")
    syllabus: str | None = Field(description="계획서 판정: yes | no | not_mentioned | null")
    differs_from_syllabus: bool
    yes_votes: int
    no_votes: int
    dvcls: list[str]


def label_out(t: TermLabel | None) -> TeamLabelOut | None:
    return TeamLabelOut(**t.__dict__) if t else None


class TeamHistoryOut(BaseModel):
    """같은 교수·같은 과목의 최근 3개 연도 학기별 라벨. 수강신청 전에 보는 용도."""

    summary: str = Field(description="yes | no | likely_no | mixed(학기마다 다름) | unknown")
    from_year: str
    to_year: str
    terms: list[TeamLabelOut]


def history_out(h: TeamHistory) -> TeamHistoryOut:
    return TeamHistoryOut(
        summary=h.summary,
        from_year=h.from_year,
        to_year=h.to_year,
        terms=[TeamLabelOut(**t.__dict__) for t in h.terms],
    )
