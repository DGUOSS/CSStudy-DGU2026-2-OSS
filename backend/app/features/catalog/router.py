"""개설 목록(엔드림스 종합강의시간표): 관리자 가져오기, 강좌 찾기(엔드림스처럼 검색), 열기 요청.

개설 목록은 강좌를 만들지 않는다. 강좌는 누군가 요청하고 교안이 붙어 승인될 때만 생긴다.
"""

from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.core.db import SessionDep
from app.core.security import AdminUser, CurrentUser
from app.features.course_requests.router import create_keyed_request
from app.features.enrollments.service import (
    catalog_row,
    find_course,
    find_subject,
    norm_code,
    relink_unlinked,
    sem_label,
    term_label,
)
from app.models import CatalogOffering, Course, CourseRequest, Enrollment, Professor

router = APIRouter(tags=["catalog"])


class OfferingIn(BaseModel):
    year: str = Field(pattern=r"^\d{4}$")
    sem_cd: str = Field(min_length=1, max_length=20)
    sbj_no: str = Field(min_length=1, max_length=20)
    sbj_nm: str = Field(min_length=1, max_length=200)
    dvcls: str = Field(default="", max_length=10)
    emp_no: str | None = Field(default=None, max_length=20)
    emp_nm: str | None = Field(default=None, max_length=50)
    colg_nm: str | None = Field(default=None, max_length=100)
    dpt_nm: str | None = Field(default=None, max_length=100)
    cpdiv_nm: str | None = Field(default=None, max_length=50)
    cdt: str | None = Field(default=None, max_length=10)
    timetable: str | None = Field(default=None, max_length=300)
    room: str | None = Field(default=None, max_length=300)
    mid_rate: int | None = None
    fnl_rate: int | None = None
    atnd_rate: int | None = None
    proj_rate: int | None = None
    plan_url: str | None = Field(default=None, max_length=500)


class CatalogImportIn(BaseModel):
    rows: list[OfferingIn] = Field(max_length=30000)


class CatalogImportOut(BaseModel):
    terms: list[str]
    added: int
    updated: int
    professors_linked: int
    records_linked: int


class TermOut(BaseModel):
    year: str
    sem_cd: str
    label: str
    count: int


class CollegeOut(BaseModel):
    name: str
    departments: list[str]


class FiltersOut(BaseModel):
    colleges: list[CollegeOut]
    cpdivs: list[str]


class OfferingGroupOut(BaseModel):
    """같은 과목·교수의 분반을 한 줄로 묶은 결과. 사이트의 강좌 하나에 해당한다."""

    year: str
    sem_cd: str
    sbj_no: str
    sbj_nm: str
    emp_no: str | None
    emp_nm: str | None
    dvcls: list[str]
    colg_nm: str | None
    dpt_nm: str | None
    cpdiv_nm: str | None
    cdt: str | None
    timetable: list[str]
    plan_url: str | None
    eval_rates: dict[str, int | None]
    status: str  # open(열린 강좌) | requested(요청 대기) | none
    course_id: int | None
    request_count: int
    requested_by_me: bool
    mine: bool  # 내 수강 기록에 있는 수업인가(열린 강좌면 들어갈 수 있다)


class SearchOut(BaseModel):
    total: int
    items: list[OfferingGroupOut]


class RequestIn(BaseModel):
    year: str
    sem_cd: str
    sbj_no: str
    dvcls: str = ""


@router.post("/admin/catalog/import")
def import_catalog(body: CatalogImportIn, session: SessionDep, _: AdminUser) -> CatalogImportOut:
    """엔드림스 종합강의시간표 행을 저장한다(같은 학기·학수번호·분반이면 덮어쓴다)."""
    added = updated = 0
    terms = sorted({(r.year, r.sem_cd) for r in body.rows})
    existing = {}
    for y, s in terms:
        for o in session.exec(
            select(CatalogOffering).where(CatalogOffering.year == y, CatalogOffering.sem_cd == s)
        ).all():
            existing[(o.year, o.sem_cd, o.sbj_no, o.dvcls)] = o
    for r in body.rows:
        data = r.model_dump()
        data["sbj_no"] = norm_code(r.sbj_no)
        key = (r.year, r.sem_cd, data["sbj_no"], r.dvcls)
        o = existing.get(key)
        if o is None:
            o = CatalogOffering(**data)
            existing[key] = o
            added += 1
        else:
            for k, v in data.items():
                setattr(o, k, v)
            updated += 1
        session.add(o)
    session.flush()
    linked = _link_professors(session, body.rows)
    records = relink_unlinked(session)
    session.commit()
    return CatalogImportOut(
        terms=[term_label(y, s) for y, s in terms],
        added=added,
        updated=updated,
        professors_linked=linked,
        records_linked=records,
    )


def _link_professors(session, rows: list[OfferingIn]) -> int:
    """이름만 있던 교수(수강 기록으로 만든 강좌)에게 개설 목록의 교원번호를 채운다."""
    n = 0
    for r in rows:
        if not (r.emp_no and r.emp_nm):
            continue
        if session.exec(select(Professor).where(Professor.emp_no == r.emp_no)).first():
            continue
        subject = find_subject(session, r.sbj_no, r.sbj_nm)
        if subject is None:
            continue
        if not subject.code:  # 학수번호 없이 이름으로 만든 옛 과목이면 학수번호를 채운다
            subject.code = norm_code(r.sbj_no)
            session.add(subject)
        for _c, p in session.exec(
            select(Course, Professor)
            .join(Professor, Professor.id == Course.professor_id)
            .where(Course.subject_id == subject.id)
        ).all():
            if p.emp_no is None and p.name == r.emp_nm.strip():
                p.emp_no = r.emp_no
                session.add(p)
                session.flush()
                n += 1
                break
    return n


@router.get("/catalog/terms")
def list_terms(session: SessionDep, _: CurrentUser) -> list[TermOut]:
    rows = session.exec(
        select(CatalogOffering.year, CatalogOffering.sem_cd, func.count()).group_by(
            CatalogOffering.year, CatalogOffering.sem_cd
        )
    ).all()
    rows = sorted(rows, key=lambda r: (r[0], r[1]), reverse=True)
    return [TermOut(year=y, sem_cd=s, label=term_label(y, s), count=n) for y, s, n in rows]


@router.get("/catalog/filters")
def filters(year: str, sem_cd: str, session: SessionDep, _: CurrentUser) -> FiltersOut:
    rows = session.exec(
        select(CatalogOffering.colg_nm, CatalogOffering.dpt_nm, CatalogOffering.cpdiv_nm)
        .where(CatalogOffering.year == year, CatalogOffering.sem_cd == sem_cd)
        .distinct()
    ).all()
    colleges: dict[str, set[str]] = defaultdict(set)
    cpdivs = set()
    for colg, dpt, cp in rows:
        if colg:
            colleges[colg].add(dpt or "")
        if cp:
            cpdivs.add(cp)
    return FiltersOut(
        colleges=[
            CollegeOut(name=c, departments=sorted(d for d in ds if d))
            for c, ds in sorted(colleges.items())
        ],
        cpdivs=sorted(cpdivs),
    )


@router.get("/catalog/search")
def search(
    session: SessionDep,
    user: CurrentUser,
    year: str,
    sem_cd: str,
    colg: str | None = None,
    dpt: str | None = None,
    cpdiv: str | None = None,
    q: Annotated[str | None, Query(max_length=50)] = None,
    prof: Annotated[str | None, Query(max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchOut:
    """엔드림스 종합강의시간표처럼 찾는다. 같은 과목·교수의 분반은 한 줄로 묶는다."""
    stmt = select(CatalogOffering).where(
        CatalogOffering.year == year, CatalogOffering.sem_cd == sem_cd
    )
    if colg:
        stmt = stmt.where(CatalogOffering.colg_nm == colg)
    if dpt:
        stmt = stmt.where(CatalogOffering.dpt_nm == dpt)
    if cpdiv:
        stmt = stmt.where(CatalogOffering.cpdiv_nm == cpdiv)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            CatalogOffering.sbj_nm.ilike(like) | CatalogOffering.sbj_no.ilike(like)  # type: ignore[attr-defined]
        )
    if prof:
        stmt = stmt.where(CatalogOffering.emp_nm.ilike(f"%{prof.strip()}%"))  # type: ignore[union-attr]
    rows = session.exec(stmt.order_by(CatalogOffering.sbj_nm, CatalogOffering.dvcls)).all()
    groups: dict[tuple, list[CatalogOffering]] = {}
    for o in rows:
        groups.setdefault((o.sbj_no, o.emp_no or o.emp_nm), []).append(o)
    keys = list(groups)
    page = keys[offset : offset + limit]
    pending = session.exec(select(CourseRequest).where(CourseRequest.status == "pending")).all()
    my_recs = session.exec(select(Enrollment).where(Enrollment.user_id == user.id)).all()
    items = []
    for k in page:
        g = groups[k]
        o = g[0]
        subject = find_subject(session, o.sbj_no, o.sbj_nm)
        course = find_course(session, subject, o.emp_no, o.emp_nm) if subject else None
        same = [
            r
            for r in pending
            if r.subject_code == o.sbj_no
            and (r.professor_emp_no == o.emp_no if o.emp_no else r.professor_name == o.emp_nm)
        ]
        mine = any(
            (course and e.course_id == course.id)
            or (
                e.sbj_no == o.sbj_no
                and (e.emp_no == o.emp_no if o.emp_no else e.emp_nm == o.emp_nm)
            )
            for e in my_recs
        )
        items.append(
            OfferingGroupOut(
                year=o.year,
                sem_cd=o.sem_cd,
                sbj_no=o.sbj_no,
                sbj_nm=o.sbj_nm,
                emp_no=o.emp_no,
                emp_nm=o.emp_nm,
                dvcls=[x.dvcls for x in g],
                colg_nm=o.colg_nm,
                dpt_nm=o.dpt_nm,
                cpdiv_nm=o.cpdiv_nm,
                cdt=o.cdt,
                timetable=[x.timetable for x in g if x.timetable],
                plan_url=o.plan_url,
                eval_rates={
                    "중간": o.mid_rate,
                    "기말": o.fnl_rate,
                    "출석": o.atnd_rate,
                    "과제": o.proj_rate,
                },
                status="open" if course else ("requested" if same else "none"),
                course_id=course.id if course else None,
                request_count=len(same),
                requested_by_me=any(r.requester_id == user.id for r in same),
                mine=bool(mine),
            )
        )
    return SearchOut(total=len(keys), items=items)


class RequestCreatedOut(BaseModel):
    request_id: int


@router.post("/catalog/request", status_code=status.HTTP_201_CREATED)
def request_from_catalog(
    body: RequestIn, session: SessionDep, user: CurrentUser
) -> RequestCreatedOut:
    """이번 학기 개설 목록의 강좌를 열어 달라고 요청한다."""
    o = catalog_row(session, body.year, body.sem_cd, body.sbj_no, body.dvcls)
    if o is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "개설 목록에 없는 강좌입니다")
    subject = find_subject(session, o.sbj_no, o.sbj_nm)
    if subject and find_course(session, subject, o.emp_no, o.emp_nm):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 열린 강좌입니다")
    r = create_keyed_request(
        session,
        user,
        source="catalog",
        sbj_no=o.sbj_no,
        sbj_nm=o.sbj_nm,
        emp_no=o.emp_no,
        emp_nm=o.emp_nm,
        semester=f"{o.year} {sem_label(o.sem_cd)}",
    )
    session.commit()
    return RequestCreatedOut(request_id=r.id)
