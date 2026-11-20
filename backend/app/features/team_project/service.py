"""팀 프로젝트(팀플) 여부 라벨.

같은 과목이라도 교수·학기마다 다르므로 라벨은 (강좌 = 과목+교수, 학기) 단위로 정한다.
근거는 두 가지다.
- 강의계획서: 엔드림스에서 받은 계획서 글을 규칙으로 판정해 개설 목록(catalog_offerings)에 저장한다.
- 후기: 그 학기 수강 기록으로 쓴 후기의 "팀 프로젝트가 있었나요?" 응답.
계획서가 있으면 계획서를 따르고(교수가 공지한 내용), 없거나 언급이 없으면 후기 응답으로 정한다.
"""

import re
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.features.enrollments.service import term_label
from app.models import CatalogOffering, Course, CourseReview, Professor, Subject

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


@dataclass
class TermLabel:
    year: str
    sem_cd: str
    term: str
    label: str  # yes | no | likely_no(계획서에 언급 없음) | unknown
    source: str | None  # syllabus | reviews | None
    evidence: str | None = None
    yes_votes: int = 0
    no_votes: int = 0
    dvcls: list[str] = field(default_factory=list)


def decide(syllabus: str | None, evidence: str | None, yes: int, no: int) -> tuple[str, str | None]:
    """(라벨, 근거 종류). 계획서에 적힌 내용 > 후기 다수결 > 계획서 언급 없음."""
    if syllabus == YES:
        return LABEL_YES, "syllabus"
    if syllabus == NO:
        return LABEL_NO, "syllabus"
    if yes > no:
        return LABEL_YES, "reviews"
    if no > yes:
        return LABEL_NO, "reviews"
    if syllabus == NOT_MENTIONED:
        return LABEL_LIKELY_NO, "syllabus"
    return LABEL_UNKNOWN, None


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


def _votes(session: Session, course_id: int) -> dict[tuple[str, str], tuple[int, int]]:
    out: dict[tuple[str, str], list[int]] = {}
    for r in session.exec(
        select(CourseReview).where(
            CourseReview.course_id == course_id,
            CourseReview.is_deleted == False,  # noqa: E712
            CourseReview.team_project.is_not(None),  # type: ignore[union-attr]
        )
    ).all():
        v = out.setdefault((r.year, r.sem_cd), [0, 0])
        v[0 if r.team_project else 1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def term_labels(
    session: Session, course: Course, offerings: list[CatalogOffering] | None = None
) -> list[TermLabel]:
    """학기별 라벨, 최근 학기부터. 계획서도 후기 응답도 없는 학기는 넣지 않는다."""
    offerings = offerings_of(session, course) if offerings is None else offerings
    by_term: dict[tuple[str, str], list[CatalogOffering]] = {}
    for o in offerings:
        by_term.setdefault((o.year, o.sem_cd), []).append(o)
    votes = _votes(session, course.id)
    out = []
    for key in sorted(set(by_term) | set(votes), reverse=True):
        rows = by_term.get(key, [])
        syl, ev = _merge_syllabus(rows)
        yes, no = votes.get(key, (0, 0))
        label, source = decide(syl, ev, yes, no)
        if syl is None and not (yes or no):
            continue
        out.append(
            TermLabel(
                year=key[0],
                sem_cd=key[1],
                term=term_label(*key),
                label=label,
                source=source,
                evidence=ev if source == "syllabus" else None,
                yes_votes=yes,
                no_votes=no,
                dvcls=sorted(r.dvcls for r in rows),
            )
        )
    return out


def latest_label(session: Session, course: Course) -> TermLabel | None:
    """가장 최근 학기 라벨(목록 배지용)."""
    labels = term_labels(session, course)
    return labels[0] if labels else None


def offering_group_label(
    session: Session, group: list[CatalogOffering], course_id: int | None
) -> TermLabel:
    """개설 목록 화면의 한 줄(같은 학기·과목·교수의 분반 묶음)."""
    o = group[0]
    syl, ev = _merge_syllabus(group)
    yes, no = _votes(session, course_id).get((o.year, o.sem_cd), (0, 0)) if course_id else (0, 0)
    label, source = decide(syl, ev, yes, no)
    return TermLabel(
        year=o.year,
        sem_cd=o.sem_cd,
        term=term_label(o.year, o.sem_cd),
        label=label,
        source=source,
        evidence=ev if source == "syllabus" else None,
        yes_votes=yes,
        no_votes=no,
        dvcls=sorted(r.dvcls for r in group),
    )
