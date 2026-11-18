from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.models import NoticePreference

from .catalog import DEPARTMENTS, SOURCES, DepartmentOut
from .service import POOL, BoardPage, DetailOut, Item, list_url, load_detail, load_page

router = APIRouter(prefix="/department-notices", tags=["department-notices"])
MAX_FAVORITES = 8


class CatalogOut(BaseModel):
    departments: list[DepartmentOut]
    max_favorites: int


class PreferencesOut(BaseModel):
    department_ids: list[str]


class PreferencesIn(BaseModel):
    department_ids: list[str] = Field(max_length=MAX_FAVORITES)


class FailedSource(BaseModel):
    id: str
    name: str
    url: str


class FeedOut(BaseModel):
    items: list[Item]
    boards: list[BoardPage]
    failed_sources: list[FailedSource]
    combined: bool


@router.get("/catalog")
def catalog() -> CatalogOut:
    return CatalogOut(departments=list(DEPARTMENTS.values()), max_favorites=MAX_FAVORITES)


@router.get("/preferences")
def preferences(session: SessionDep, user: CurrentUser) -> PreferencesOut:
    row = session.get(NoticePreference, user.id)
    ids = row.department_ids if row else []
    return PreferencesOut(
        department_ids=[d for d in ids if d in DEPARTMENTS and DEPARTMENTS[d].source_ids]
    )


@router.put("/preferences")
def save_preferences(body: PreferencesIn, session: SessionDep, user: CurrentUser) -> PreferencesOut:
    ids = list(dict.fromkeys(body.department_ids))
    if any(d not in DEPARTMENTS or not DEPARTMENTS[d].source_ids for d in ids):
        raise HTTPException(422, "선택할 수 없는 학과가 포함되어 있습니다.")
    row = session.get(NoticePreference, user.id) or NoticePreference(user_id=user.id)
    row.department_ids = ids
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "설정이 동시에 변경되었습니다. 다시 저장해 주세요.") from None
    return PreferencesOut(department_ids=ids)


def allowed_sources(session, user) -> list[str]:
    ids = preferences(session, user).department_ids
    return list(dict.fromkeys(["school"] + [s for d in ids for s in DEPARTMENTS[d].source_ids]))


Q = Annotated[str, Query(max_length=100)]
Page = Annotated[int, Query(ge=1, le=10000)]
Source = Annotated[str, Query(max_length=80)]


@router.get("/feed")
def feed(
    session: SessionDep, user: CurrentUser, source: Source = "all", q: Q = "", page: Page = 1
) -> FeedOut:
    allowed = allowed_sources(session, user)
    if source != "all" and source not in allowed:
        raise HTTPException(403, "관심 학과로 추가한 뒤 확인해 주세요.")
    combined = source == "all"
    if combined and page != 1:
        raise HTTPException(
            422, "전체 탭은 최신 목록입니다. 이전 공지는 학과 탭에서 확인해 주세요."
        )
    ids = allowed if combined else [source]
    q = q.strip()
    futures = [(sid, POOL.submit(load_page, sid, q, page)) for sid in ids]
    boards, failures = [], []
    for sid, future in futures:
        try:
            boards.append(future.result())
        except HTTPException:
            failures.append(
                FailedSource(id=sid, name=SOURCES[sid].name, url=list_url(SOURCES[sid], q, page))
            )
    unique = {(item.source_id, item.id): item for board in boards for item in board.items}
    items = sorted(unique.values(), key=lambda x: (x.date, x.id, x.source_id), reverse=True)
    return FeedOut(items=items, boards=boards, failed_sources=failures, combined=combined)


@router.get("/sources/{source_id}/items/{notice_id}")
def detail(
    source_id: str,
    session: SessionDep,
    user: CurrentUser,
    notice_id: int = Path(gt=0, le=999999999),
    q: Q = "",
    page: Page = 1,
) -> DetailOut:
    if source_id not in allowed_sources(session, user):
        raise HTTPException(403, "관심 학과로 추가한 뒤 확인해 주세요.")
    return load_detail(source_id, notice_id, q.strip(), page)
