"""수강 기록·개설 목록과 강좌를 잇는 규칙. 구조 설명은 docs/NDRIMS.md.

- 엔드림스에서 수업 하나 = (연도, 학기 코드, 학수번호, 분반).
- 사이트의 과목 = 학수번호, 교수 = 교원번호(없으면 이름), 강좌 = 과목 + 교수.
- 학생은 수강 기록이 있는 강좌에만 들어간다(학기와 상관없이). 관리자는 예외.
"""

import re
from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import CatalogOffering, Course, Enrollment, Professor, Subject, User

SEM_LABEL = {
    "CM160.10": "1학기",
    "CM160.11": "여름학기",
    "CM160.20": "2학기",
    "CM160.21": "겨울학기",
    "CM160.99": "공통학기",
}


def sem_label(sem_cd: str) -> str:
    return SEM_LABEL.get(sem_cd, sem_cd)


def term_label(year: str, sem_cd: str) -> str:
    return f"{year} {sem_label(sem_cd)}"


def _term_key(year: str, sem_cd: str) -> tuple[str, str]:
    return (year, sem_cd)  # 학기 코드는 1학기 < 여름 < 2학기 < 겨울 순으로 커진다


def norm_code(code: str | None) -> str:
    """학수번호 표기를 맞춘다. 'csc 2001-01' → 'CSC2001'."""
    s = re.sub(r"\s+", "", (code or "").upper())
    return re.sub(r"-\d{1,3}$", "", s)


def _today() -> date:
    return date.today()


def current_term(session: Session | None = None) -> tuple[str, str]:
    """이번 학기: 날짜로 정한다(2~7월 1학기, 8~1월 2학기).
    개설 목록에서 고르면 다음 학기 목록이나 공통학기 행을 미리 가져왔을 때 바뀌어 버린다."""
    d = _today()
    if d.month == 1:
        return (str(d.year - 1), "CM160.20")
    return (str(d.year), "CM160.10" if 2 <= d.month <= 7 else "CM160.20")


def find_subject(session: Session, code: str, name: str | None = None) -> Subject | None:
    """학수번호로 과목을 찾는다. 학수번호가 아직 없는 옛 과목은 이름이 같으면 같은 과목으로 본다."""
    code = norm_code(code)
    if code:
        s = session.exec(select(Subject).where(Subject.code == code)).first()
        if s:
            return s
    if name:
        return session.exec(
            select(Subject).where(Subject.name == name.strip(), Subject.code.is_(None))  # type: ignore[union-attr]
        ).first()
    return None


def catalog_row(session: Session, year: str, sem_cd: str, sbj_no: str, dvcls: str):
    return session.exec(
        select(CatalogOffering).where(
            CatalogOffering.year == year,
            CatalogOffering.sem_cd == sem_cd,
            CatalogOffering.sbj_no == norm_code(sbj_no),
            CatalogOffering.dvcls == dvcls,
        )
    ).first()


def find_course(
    session: Session, subject: Subject, emp_no: str | None, emp_nm: str | None
) -> Course | None:
    """과목 안에서 교수(교원번호 우선, 없으면 이름)로 강좌를 찾는다."""
    q = select(Course, Professor).join(Professor, Professor.id == Course.professor_id)
    rows = session.exec(q.where(Course.subject_id == subject.id)).all()
    if emp_no:
        for c, p in rows:
            if p.emp_no == emp_no:
                return c
    if emp_nm:
        for c, p in rows:
            if p.name == emp_nm.strip() and (not emp_no or not p.emp_no):
                return c
    return None


def resolve(session: Session, e: Enrollment) -> int | None:
    """수강 기록 한 줄이 어느 강좌인지 찾는다. 개설 목록에 있으면 교원번호·교수명을 채운다."""
    row = catalog_row(session, e.year, e.sem_cd, e.sbj_no, e.dvcls)
    if row:
        e.emp_no = e.emp_no or row.emp_no
        e.emp_nm = e.emp_nm or row.emp_nm
    subject = find_subject(session, e.sbj_no, e.sbj_nm)
    if subject is None:
        return None
    course = find_course(session, subject, e.emp_no, e.emp_nm)
    return course.id if course else None


def relink_unlinked(session: Session, codes: set[str] | None = None) -> int:
    """강좌가 아직 없던 수강 기록을 다시 맞춰 본다(강좌가 열리거나 개설 목록을 가져온 뒤).
    codes를 주면 그 학수번호의 기록만 본다(전체를 훑지 않도록)."""
    q = select(Enrollment).where(Enrollment.course_id.is_(None))  # type: ignore[union-attr]
    if codes is not None:
        if not codes:
            return 0
        q = q.where(Enrollment.sbj_no.in_(codes))  # type: ignore[attr-defined]
    n = 0
    for e in session.exec(q).all():
        cid = resolve(session, e)
        if cid:
            e.course_id = cid
            n += 1
        session.add(e)
    return n


def ensure_course_by_keys(
    session: Session,
    *,
    sbj_no: str,
    sbj_nm: str,
    emp_no: str | None,
    emp_nm: str,
    created_by: int | None,
) -> tuple[Course, bool]:
    """학수번호·교원번호로 과목·교수·강좌를 찾고 없으면 만든다. commit은 하지 않는다."""
    code = norm_code(sbj_no)
    subject = find_subject(session, code, sbj_nm)
    if subject is None:
        subject = Subject(name=_unique_subject_name(session, sbj_nm.strip(), code), code=code)
        session.add(subject)
        session.flush()
    elif not subject.code:
        subject.code = code
        session.add(subject)
    course = find_course(session, subject, emp_no, emp_nm)
    if course is not None:
        prof = session.get(Professor, course.professor_id)
        taken = emp_no and session.exec(select(Professor).where(Professor.emp_no == emp_no)).first()
        if prof and emp_no and not prof.emp_no and not taken:  # 교원번호는 한 교수에게만
            prof.emp_no = emp_no
            session.add(prof)
        return course, False
    professor = None
    if emp_no:
        professor = session.exec(select(Professor).where(Professor.emp_no == emp_no)).first()
    else:  # 교원번호를 모르면 같은 이름의 '교원번호 없는' 교수를 쓴다(이름만 같은 교수를 늘리지 않게)
        professor = session.exec(
            select(Professor).where(Professor.name == emp_nm.strip(), Professor.emp_no.is_(None))  # type: ignore[union-attr]
        ).first()
    if professor is None:
        professor = Professor(name=emp_nm.strip(), emp_no=emp_no or None)
        session.add(professor)
        session.flush()
    course = Course(subject_id=subject.id, professor_id=professor.id, created_by=created_by)
    session.add(course)
    session.flush()
    return course, True


def relink_course(session: Session, course: Course) -> None:
    """강좌를 만들거나 교수를 바꾼 뒤: 이 강좌에 붙어 있던 기록을 떼고, 맞는 기록을 다시 붙인다."""
    for e in session.exec(select(Enrollment).where(Enrollment.course_id == course.id)).all():
        e.course_id = None
        session.add(e)
    session.flush()
    subject = session.get(Subject, course.subject_id)
    relink_unlinked(session, {subject.code} if subject and subject.code else None)


def _unique_subject_name(session: Session, name: str, code: str) -> str:
    """과목명은 고유해야 한다. 다른 학수번호의 같은 이름 과목이 있으면 학수번호를 붙인다."""
    if session.exec(select(Subject).where(Subject.name == name)).first() is None:
        return name
    return f"{name} ({code})"


def can_enter(session: Session, user: User, course: Course) -> bool:
    if user.role == "admin" or course.is_public:
        return True
    return (
        session.exec(
            select(Enrollment.id).where(
                Enrollment.user_id == user.id, Enrollment.course_id == course.id
            )
        ).first()
        is not None
    )


def require_course_access(session: Session, user: User, course: Course) -> None:
    if not can_enter(session, user, course):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "수강 기록이 있는 강좌만 들어갈 수 있습니다. 엔드림스에서 수강 기록을 가져와 주세요",
        )
