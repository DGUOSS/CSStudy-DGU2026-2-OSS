"""라벨 출력 형식. courses·catalog 라우터도 쓰므로 라우터와 따로 둔다(순환 import 방지)."""

from pydantic import BaseModel, Field

from app.features.team_project.service import TermLabel


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
