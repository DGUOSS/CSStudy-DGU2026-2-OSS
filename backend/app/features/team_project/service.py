"""팀 프로젝트(팀플) 여부 라벨.

같은 과목이라도 교수·학기마다 다르므로 라벨은 (강좌 = 과목+교수, 학기) 단위로 정한다.
계획서와 실제 수업이 다를 수 있어서, 계획서는 기본값으로만 쓰고 실제 경험으로 덮어쓴다.
우선순위:
1. 운영진 지정(team_project_overrides)
2. 수강생 응답: 제보 버튼(team_project_reports) + 후기 응답, 한 학생 한 표. 2명 이상이고 과반일 때
3. 강의계획서: 엔드림스 계획서 글을 규칙으로 판정해 개설 목록(catalog_offerings)에 저장한 값
"""

import re
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.features.enrollments.service import term_label
from app.models import (
    CatalogOffering,
    Course,
    CourseReview,
    Professor,
    Subject,
    TeamProjectOverride,
    TeamProjectReport,
)

# ---------- 강의계획서 판정 ----------

# 앞이 한글이면 다른 단어의 일부("강조 과제", "스팀")라서 뺀다
_TEAM = re.compile(
    r"(?<![가-힣])(?:"
    r"팀\s*(?:프로젝트|과제|플|별|작업|발표|보고서|활동|단위)"
    r"|조\s*별|조\s*(?:과제|프로젝트|발표|활동|단위)"
    r"|그룹\s*(?:프로젝트|과제|발표|활동|별)"
    r"|협업\s*(?:프로젝트|과제)"
    r")"
    r"|\b(?:team|group)\s*(?:project|work|assignment|presentation)s?\b|\bteamwork\b",
    re.IGNORECASE,
)
_NEG = re.compile(
    r"없음|없다|없습니다|없으며|없고|없는|없이|하지\s*않|않습니다|않음|미실시|해당\s*없|"
    r"(?<!\d)0\s*%|\bnone\b|\bnot\b|\bno\s+(?:team|group)",
    re.IGNORECASE,
)
_NEG_BEFORE = re.compile(r"\b(?:no|without|not)\s+(?:a\s+)?$", re.IGNORECASE)
_SPLIT = re.compile(r"[\n\r]+|(?<=[.!?。])\s+|\s*[·•▪■□◦]\s*")

YES, NO, NOT_MENTIONED = "yes", "no", "not_mentioned"


def classify_syllabus(text: str) -> tuple[str, str | None]:
    """강의계획서 글 → (yes | no | not_mentioned, 근거 문장)."""
    no_evidence = None
    for raw in _SPLIT.split(text or ""):
        sent = re.sub(r"\s+", " ", raw).strip()
        m = _TEAM.search(sent)
        if not m:
            continue
        before = sent[max(0, m.start() - 12) : m.start()]
        # 한국어 부정은 뒤에("팀 프로젝트: 없음", "조별 과제는 하지 않는다"), 영어는 앞에("no team project")
        if _NEG.search(sent[m.start() :]) or _NEG_BEFORE.search(before):
            no_evidence = no_evidence or sent[:300]
            continue
        return YES, sent[:300]
    if no_evidence:
        return NO, no_evidence
    return NOT_MENTIONED, None


# ---------- 라벨 ----------

# 화면에 보이는 값
LABEL_YES, LABEL_NO, LABEL_LIKELY_NO, LABEL_UNKNOWN = "yes", "no", "likely_no", "unknown"
MIN_VOTES = (
    2  # 수강생 응답으로 라벨을 정하려면 이만큼 모여야 한다(한 명의 실수·장난에 흔들리지 않게)
)


@dataclass
class TermLabel:
    year: str
    sem_cd: str
    term: str
    label: str  # yes | no | likely_no(계획서에 언급 없음) | unknown
    source: str | None  # admin | students | syllabus | None
    evidence: str | None = None  # 계획서 근거 문장
    note: str | None = None  # 운영진 메모
    syllabus: str | None = None  # 계획서 판정(yes | no | not_mentioned | None)
    differs_from_syllabus: bool = False  # 실제(제보·운영진)가 계획서와 다름
    yes_votes: int = 0
    no_votes: int = 0
    dvcls: list[str] = field(default_factory=list)


def decide(
    syllabus: str | None, yes: int, no: int, override: bool | None = None
) -> tuple[str, str | None]:
    """(라벨, 근거 종류). 운영진 > 수강생 응답(2명 이상, 과반) > 강의계획서."""
    if override is not None:
        return (LABEL_YES if override else LABEL_NO), "admin"
    if yes + no >= MIN_VOTES and yes != no:
        return (LABEL_YES if yes > no else LABEL_NO), "students"
    if syllabus == YES:
        return LABEL_YES, "syllabus"
    if syllabus == NO:
        return LABEL_NO, "syllabus"
    if syllabus == NOT_MENTIONED:
        return LABEL_LIKELY_NO, "syllabus"
    return LABEL_UNKNOWN, None


def differs(syllabus: str | None, label: str, source: str | None) -> bool:
    """계획서와 실제가 다른가. 계획서에 언급이 없었는데 실제로 있었던 경우도 포함."""
    if source not in ("admin", "students") or syllabus is None:
        return False
    if syllabus == YES:
        return label == LABEL_NO
    return label == LABEL_YES  # 계획서 없음/언급 없음인데 실제로 있었음


def _merge_syllabus(rows: list[CatalogOffering]) -> tuple[str | None, str | None]:
    """한 강좌의 여러 분반: 하나라도 있으면 있음."""
    for want in (YES, NO, NOT_MENTIONED):
        for r in rows:
            if r.team_project == want:
                return want, r.team_evidence
    return None, None


def offerings_of(session: Session, course: Course) -> list[CatalogOffering]:
    """이 강좌(과목+교수)의 개설 목록 행. 교원번호가 있으면 교원번호로, 없으면 이름으로."""
    subject = session.get(Subject, course.subject_id)
    prof = session.get(Professor, course.professor_id)
    if subject is None or not subject.code or prof is None:
        return []
    q = select(CatalogOffering).where(CatalogOffering.sbj_no == subject.code)
    q = (
        q.where(CatalogOffering.emp_no == prof.emp_no)
        if prof.emp_no
        else q.where(CatalogOffering.emp_nm == prof.name)
    )
    return list(session.exec(q).all())


Term = tuple[str, str]


def votes(session: Session, course_id: int) -> dict[Term, tuple[int, int]]:
    """학기별 (있었다, 없었다) 수. 한 학생은 한 표: 제보 버튼 응답이 있으면 그것, 없으면 후기 응답."""
    by_user: dict[tuple[Term, int], bool] = {}
    for r in session.exec(
        select(CourseReview).where(
            CourseReview.course_id == course_id,
            CourseReview.is_deleted == False,  # noqa: E712
            CourseReview.team_project.is_not(None),  # type: ignore[union-attr]
        )
    ).all():
        by_user[((r.year, r.sem_cd), r.user_id)] = bool(r.team_project)
    for p in session.exec(
        select(TeamProjectReport).where(TeamProjectReport.course_id == course_id)
    ).all():
        by_user[((p.year, p.sem_cd), p.user_id)] = p.team_project
    out: dict[Term, list[int]] = {}
    for (term, _), v in by_user.items():
        out.setdefault(term, [0, 0])[0 if v else 1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def overrides(session: Session, course_id: int) -> dict[Term, TeamProjectOverride]:
    return {
        (o.year, o.sem_cd): o
        for o in session.exec(
            select(TeamProjectOverride).where(TeamProjectOverride.course_id == course_id)
        ).all()
    }


def _label(
    term: Term,
    rows: list[CatalogOffering],
    vote: tuple[int, int],
    override: TeamProjectOverride | None,
) -> TermLabel:
    syl, ev = _merge_syllabus(rows)
    yes, no = vote
    label, source = decide(syl, yes, no, override.team_project if override else None)
    return TermLabel(
        year=term[0],
        sem_cd=term[1],
        term=term_label(*term),
        label=label,
        source=source,
        evidence=ev,
        note=override.note if override else None,
        syllabus=syl,
        differs_from_syllabus=differs(syl, label, source),
        yes_votes=yes,
        no_votes=no,
        dvcls=sorted(r.dvcls for r in rows),
    )


def term_labels(session: Session, course: Course) -> list[TermLabel]:
    """학기별 라벨, 최근 학기부터. 계획서·응답·운영진 지정이 하나도 없는 학기는 넣지 않는다."""
    by_term: dict[Term, list[CatalogOffering]] = {}
    for o in offerings_of(session, course):
        by_term.setdefault((o.year, o.sem_cd), []).append(o)
    v, ov = votes(session, course.id), overrides(session, course.id)
    out = []
    for term in sorted(set(by_term) | set(v) | set(ov), reverse=True):
        t = _label(term, by_term.get(term, []), v.get(term, (0, 0)), ov.get(term))
        if t.syllabus is None and t.source is None and not (t.yes_votes or t.no_votes):
            continue  # 계획서는 아직 판정 전이고 응답도 없음
        out.append(t)
    return out


def latest_label(session: Session, course: Course) -> TermLabel | None:
    """가장 최근 학기 라벨(목록 배지용)."""
    labels = term_labels(session, course)
    return labels[0] if labels else None


def offering_group_label(
    session: Session, group: list[CatalogOffering], course_id: int | None
) -> TermLabel:
    """개설 목록 화면의 한 줄(같은 학기·과목·교수의 분반 묶음)."""
    term = (group[0].year, group[0].sem_cd)
    vote = votes(session, course_id).get(term, (0, 0)) if course_id else (0, 0)
    override = overrides(session, course_id).get(term) if course_id else None
    return _label(term, group, vote, override)
