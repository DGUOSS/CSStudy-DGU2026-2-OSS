import re
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Annotated
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

SOURCE = "https://www.dongguk.edu/article/HAKSANOTICE"
router = APIRouter(prefix="/notices", tags=["notices"])


class Notice(BaseModel):
    id: int
    title: str
    category: str
    date: str
    pinned: bool
    url: str


class NoticeList(BaseModel):
    total: int = 0
    page: int = 1
    query: str = ""
    items: list[Notice]
    fetched_at: datetime
    stale: bool = False


class NoticeDetail(BaseModel):
    id: int
    text: str
    url: str
    fetched_at: datetime
    stale: bool = False


def parse_list(html: str, searching: bool = False) -> list[Notice]:
    soup = BeautifulSoup(html, "html.parser")
    notices = {}
    for a in soup.select(".board_list li a[onclick]"):
        if searching and a.select_one(".fix"):
            continue
        match = re.fullmatch(r"goDetail\((\d+)\);?", a.get("onclick", "").strip())
        title, date, category = (
            a.select_one(".tit"),
            a.select_one(".info span"),
            a.select_one(".top em"),
        )
        if not match or not title or not date:
            continue
        for extra in title.select(".mobile, .blind"):
            extra.decompose()
        nid = int(match[1])
        if nid not in notices:
            notices[nid] = Notice(
                id=nid,
                title=title.get_text(" ", strip=True),
                category=category.get_text(strip=True) if category else "학사",
                date=date.get_text(strip=True),
                pinned=bool(a.select_one(".fix")),
                url=f"{SOURCE}/detail/{nid}",
            )
    count = soup.select_one(".count span")
    if not notices and not (
        soup.select_one(".board_list") and count and count.get_text(strip=True) == "0"
    ):
        raise ValueError("Notice list structure changed")
    return list(notices.values())


def parse_detail(html: str, nid: int) -> NoticeDetail:
    body = BeautifulSoup(html, "html.parser").select_one(".board_view .view_cont")
    if body is None:
        raise ValueError("Notice detail structure changed")
    for el in body.select("script, style, iframe, noscript"):
        el.decompose()
    for el in body.select("p, div, tr, li, br"):
        el.insert_after("\n")
    text = "\n".join(line.strip() for line in body.get_text().splitlines() if line.strip())
    return NoticeDetail(
        id=nid, text=text, url=f"{SOURCE}/detail/{nid}", fetched_at=datetime.now(UTC)
    )


def fetch_html(url: str) -> str:
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        response = client.get(url, headers={"User-Agent": "DGUStudy-Notices/1.0"})
        response.raise_for_status()
        return response.text


class NoticeCache:
    """Bounded process cache: fresh 10 min, stale at most 24 h, retry after 1 min."""

    def __init__(self):
        self.lock = Lock()
        self.entries = {}
        self.retry_after = {}

    def get(self, key, loader):
        with self.lock:
            now = monotonic()
            entry = self.entries.get(key)
            if entry and now - entry[0] < 600:
                return entry[1].model_copy()
            if now >= self.retry_after.get(key, 0):
                try:
                    value = loader()
                except (httpx.HTTPError, ValueError):
                    if len(self.retry_after) >= 128:
                        self.retry_after.pop(next(iter(self.retry_after)))
                    self.retry_after[key] = now + 60
                else:
                    if len(self.entries) >= 128:
                        self.entries.pop(next(iter(self.entries)))
                    self.entries[key] = (now, value)
                    self.retry_after.pop(key, None)
                    return value.model_copy()
            if entry and now - entry[0] < 86400:
                return entry[1].model_copy(update={"stale": True})
            raise HTTPException(503, "학사공지를 가져오지 못했습니다. 학교 원문을 확인해 주세요.")


cache = NoticeCache()


SearchQuery = Annotated[str, Query(max_length=100)]
PageNumber = Annotated[int, Query(ge=1, le=10000)]


def load_list(q: str, page: int) -> NoticeList:
    params = {"pageIndex": page}
    if q:
        params.update(searchCondition="TA.SUBJECT||TA.CONTENT", searchKeyword=q)
    html = fetch_html(f"{SOURCE}/list?{urlencode(params)}")
    count = BeautifulSoup(html, "html.parser").select_one(".count span")
    if count is None:
        raise ValueError("Notice count structure changed")
    total = int(count.get_text(strip=True).replace(",", ""))
    return NoticeList(
        items=parse_list(html, searching=bool(q)),
        total=total,
        page=page,
        query=q,
        fetched_at=datetime.now(UTC),
    )


@router.get("", response_model=NoticeList)
def list_notices(q: SearchQuery = "", page: PageNumber = 1):
    q = q.strip()
    return cache.get(f"list:{q}:{page}", lambda: load_list(q, page))


@router.get("/{notice_id}", response_model=NoticeDetail)
def get_notice(
    notice_id: int = Path(gt=0, le=999999999), q: SearchQuery = "", page: PageNumber = 1
):
    if not any(item.id == notice_id for item in list_notices(q, page).items):
        raise HTTPException(404, "현재 공지 목록에서 찾을 수 없습니다. 학교 원문을 확인해 주세요.")
    return cache.get(
        str(notice_id), lambda: parse_detail(fetch_html(f"{SOURCE}/detail/{notice_id}"), notice_id)
    )
