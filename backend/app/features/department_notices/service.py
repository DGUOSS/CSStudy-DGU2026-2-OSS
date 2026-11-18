"""Public board adapters. Only reviewed catalog URLs are fetched; HTML is never rendered."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup
from fastapi import HTTPException
from pydantic import BaseModel

from app.features.notices import router as school

from .catalog import SOURCES, SourceOut


class Item(BaseModel):
    id: int
    source_id: str
    source_name: str
    title: str
    date: str
    pinned: bool
    url: str


class BoardPage(BaseModel):
    items: list[Item]
    total: int
    page: int
    has_next: bool
    source_id: str
    source_name: str
    source_url: str
    fetched_at: datetime
    stale: bool = False


class DetailOut(BaseModel):
    text: str
    url: str
    fetched_at: datetime
    stale: bool = False


# Separate locks prevent a slow department from blocking all other boards.
CACHES = {sid: school.NoticeCache() for sid in SOURCES}
POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="department-notice")
DATE = re.compile(r"(?<!\d)(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\.?(?!\d)")


def list_url(source: SourceOut, q: str, page: int) -> str:
    parts = urlsplit(source.url)
    params = {k: v[0] for k, v in parse_qs(parts.query).items()}
    if source.kind == "gnu":
        params.update(page=page)
        if q:
            params.update(sfl="wr_subject||wr_content", stx=q, sop="and")
    else:
        params.update(pageIndex=page)
        if q:
            params.update(searchCondition="TA.SUBJECT||TA.CONTENT", searchKeyword=q)
    return source.url.split("?")[0] + "?" + urlencode(params)


def detail_url(source: SourceOut, nid: int) -> str:
    if source.kind != "gnu":
        return source.url.rsplit("/list", 1)[0] + f"/detail/{nid}"
    if "bo_table=" in source.url:
        return source.url + f"&wr_id={nid}"
    return source.url + f"/{nid}"


def _date(text: str) -> str:
    m = DATE.search(text)
    if m:
        return f"{m[1]}-{int(m[2]):02}-{int(m[3]):02}"
    # GNU boards sometimes show a 2-digit year; month-day alone is kept unknown.
    m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2})", text.strip())
    return f"20{m[1]}-{m[2]}-{m[3]}" if m else ""


def _total(soup: BeautifulSoup, source: SourceOut) -> int:
    selector = "#bo_list_total" if source.kind == "gnu" else "p.count, .bd_count"
    count = soup.select_one(selector)
    if count is None:
        raise ValueError("Board count structure changed")
    m = re.search(r"[\d,]+", count.get_text(" ", strip=True))
    if not m:
        raise ValueError("Board count missing")
    return int(m[0].replace(",", ""))


def parse_page(html: str, source: SourceOut, q: str, page: int) -> BoardPage:
    soup = BeautifulSoup(html, "html.parser")
    total = _total(soup, source)
    rows = (
        soup.select("#bo_list tbody tr")
        if source.kind == "gnu"
        else soup.select("table.board tbody tr, ul.bd_list > li")
    )
    items = {}
    for row in rows:
        if source.kind == "gnu":
            a = row.select_one(
                '.td_subject a[href*="wr_id="], .td_subject a[href*="movie23_1_3_1/"]'
            )
            if not a:
                continue
            href = a.get("href", "")
            match = re.search(r"(?:wr_id=|movie23_1_3_1/)(\d+)", href)
            pinned = "bo_notice" in row.get("class", [])
        else:
            a = row.select_one(".td_tit a, .tit a")
            if not a:
                continue
            match = re.search(r"goDetail\((\d+)\)", a.get("onclick", "")) or re.search(
                r"/detail/(\d+)", a.get("href", "")
            )
            pinned = bool(row.select_one(".td_num .mark, .num_wrap .mark"))
        if not match:
            continue
        nid = int(match[1])
        if q and pinned:
            continue  # Schools include unrelated sticky announcements during searches.
        for extra in a.select(".mobile, .blind, .m_notice_badge, .sr-only, script, style"):
            extra.decompose()
        date_node = row.select_one(".td_date, .date")
        if date_node:
            date = _date(date_node.get_text(strip=True))
        else:
            # Date cells, not titles that may mention an old deadline/year.
            date = next(
                (
                    _date(td.get_text(strip=True))
                    for td in row.select("td")
                    if _date(td.get_text(strip=True)) and "td_tit" not in td.get("class", [])
                ),
                "",
            )
        if nid not in items:
            items[nid] = Item(
                id=nid,
                source_id=source.id,
                source_name=source.name,
                title=a.get_text(" ", strip=True),
                date=date,
                pinned=pinned,
                url=detail_url(source, nid),
            )
    if total and not items:
        # A legitimate out-of-range page contains an explicit empty row/message.
        if not any(
            word in soup.get_text()
            for word in ("게시물이 없습니다", "게시글이 없습니다", "검색된 자료가 없습니다")
        ):
            raise ValueError("Board rows structure changed")
    # Follow only observed numeric pagination, rather than assume a page size.
    next_page = False
    for a in soup.select("a[href]"):
        href = a["href"]
        values = parse_qs(urlsplit(href).query)
        value = (values.get("pageIndex") or values.get("page") or ["0"])[0]
        pretty_page = re.search(r"/p(\d+)(?:[/?#]|$)", href)
        if pretty_page:
            value = pretty_page[1]
        if value.isdigit() and int(value) > page:
            next_page = True
    return BoardPage(
        items=list(items.values()),
        total=total,
        page=page,
        has_next=next_page,
        source_id=source.id,
        source_name=source.name,
        source_url=list_url(source, q, page),
        fetched_at=datetime.now(UTC),
    )


def load_page(sid: str, q: str, page: int) -> BoardPage:
    source = SOURCES[sid]
    if sid == "school":
        data = school.list_notices(q, page)
        return BoardPage(
            items=[
                Item(
                    id=x.id,
                    source_id=sid,
                    source_name=source.name,
                    title=x.title,
                    date=_date(x.date),
                    pinned=x.pinned,
                    url=x.url,
                )
                for x in data.items
            ],
            total=data.total,
            page=page,
            has_next=page * 10 < data.total,
            source_id=sid,
            source_name=source.name,
            source_url=list_url(source, q, page),
            fetched_at=data.fetched_at,
            stale=data.stale,
        )
    return CACHES[sid].get(
        f"list:{q}:{page}",
        lambda: parse_page(school.fetch_html(list_url(source, q, page)), source, q, page),
    )


def parse_detail(html: str, url: str) -> DetailOut:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(
        ".board_view .view_cont, .view_cont, #bo_v_con, .bd_view_content, .detail_wrap .bottom .contents"
    )
    if body is None:
        raise ValueError("Board detail structure changed")
    for el in body.select("script, style, iframe, noscript"):
        el.decompose()
    for el in body.select("p, div, tr, li, br"):
        el.insert_after("\n")
    text = "\n".join(line.strip() for line in body.get_text().splitlines() if line.strip())
    return DetailOut(text=text, url=url, fetched_at=datetime.now(UTC))


def load_detail(sid: str, nid: int, q: str, page: int) -> DetailOut:
    listing = load_page(sid, q, page)
    if not any(item.id == nid for item in listing.items):
        raise HTTPException(404, "목록에서 공지를 찾지 못했습니다. 원문에서 확인해 주세요.")
    url = detail_url(SOURCES[sid], nid)
    return CACHES[sid].get(f"detail:{nid}", lambda: parse_detail(school.fetch_html(url), url))
