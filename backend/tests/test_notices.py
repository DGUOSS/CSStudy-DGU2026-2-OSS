from datetime import UTC, datetime
from importlib import import_module

import httpx
import pytest
from fastapi import HTTPException

n = import_module("app.features.notices.router")
ROW = '<li><a onclick="goDetail(123);"><span class="fix">공지</span><div class="top"><em>학적</em><p class="tit"><span class="mobile">공지</span>제목 &amp; 안내</p><div class="info"><span>2026.11.17.</span></div></div></a></li>'
HTML = '<p class="count"><span>1</span></p><div class="board_list"><ul>' + ROW * 2 + "</ul></div>"


def test_list_deduplicates_and_removes_mobile_label():
    items = n.parse_list(HTML)
    assert len(items) == 1
    assert items[0].title == "제목 & 안내"
    assert items[0].pinned
    assert items[0].url.endswith("/detail/123")


def test_detail_is_plain_text():
    result = n.parse_detail(
        '<div class="board_view"><div class="view_cont"><script>evil()</script><p><span>신청</span><span>기간</span></p><p>&lt;img onerror=evil&gt;</p></div></div>',
        123,
    )
    assert "evil()" not in result.text
    assert "신청기간" in result.text
    assert "<img onerror=evil>" in result.text  # React renders as text, never HTML.


def test_changed_structure_is_failure():
    with pytest.raises(ValueError):
        n.parse_list("<html>점검 중</html>")
    with pytest.raises(ValueError):
        n.parse_detail("<html>점검 중</html>", 123)


def test_cache_fresh_stale_expired_and_retry(monkeypatch):
    cache = n.NoticeCache()
    clock = [0]
    monkeypatch.setattr(n, "monotonic", lambda: clock[0])
    value = n.NoticeList(items=[], fetched_at=datetime.now(UTC))
    assert not cache.get("list", lambda: value).stale
    calls = []

    def fail():
        calls.append(1)
        raise httpx.ConnectError("offline")

    assert not cache.get("list", fail).stale
    assert not calls
    clock[0] = 601
    assert cache.get("list", fail).stale
    assert cache.get("list", fail).stale
    assert len(calls) == 1
    clock[0] = 86401
    with pytest.raises(HTTPException) as error:
        cache.get("list", fail)
    assert error.value.status_code == 503


def test_routes_and_unknown_ids(client, monkeypatch):
    monkeypatch.setattr(n, "cache", n.NoticeCache())
    urls = []

    def fetch(url):
        urls.append(url)
        return (
            HTML
            if "/list?" in url
            else '<div class="board_view"><div class="view_cont">내용</div></div>'
        )

    monkeypatch.setattr(n, "fetch_html", fetch)
    assert client.get("/api/v1/notices").status_code == 200
    assert client.get("/api/v1/notices/123").json()["text"] == "내용"
    assert client.get("/api/v1/notices/456").status_code == 404
    assert client.get("/api/v1/notices/-1").status_code == 422
    assert len(urls) == 2


def test_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(n, "cache", n.NoticeCache())

    def fail(url):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(n, "fetch_html", fail)
    assert client.get("/api/v1/notices").status_code == 503


def test_search_omits_unrelated_pins_and_allows_zero_results():
    regular = ROW.replace('<span class="fix">공지</span>', "")
    assert len(n.parse_list(HTML.replace("</ul>", regular + "</ul>"), searching=True)) == 1
    empty = HTML.replace("<span>1</span>", "<span>0</span>")
    assert n.parse_list(empty, searching=True) == []


def test_search_paging_encoding_and_detail(client, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setattr(n, "cache", n.NoticeCache())
    urls = []
    regular = HTML.replace('<span class="fix">공지</span>', "").replace(
        "<span>1</span>", "<span>21</span>"
    )

    def fetch(url):
        urls.append(url)
        return (
            regular
            if "/list?" in url
            else '<div class="board_view"><div class="view_cont">검색 본문</div></div>'
        )

    monkeypatch.setattr(n, "fetch_html", fetch)
    params = {"q": "  졸업 & 장학  ", "page": 2}
    r = client.get("/api/v1/notices", params=params)
    assert r.status_code == 200
    assert r.json()["total"] == 21
    assert r.json()["query"] == "졸업 & 장학"
    assert r.json()["page"] == 2
    query = parse_qs(urlsplit(urls[0]).query)
    assert query == {
        "searchKeyword": ["졸업 & 장학"],
        "searchCondition": ["TA.SUBJECT||TA.CONTENT"],
        "pageIndex": ["2"],
    }
    assert client.get("/api/v1/notices/123", params=params).status_code == 200
    assert len(urls) == 2
    assert client.get("/api/v1/notices", params={"q": "x" * 101}).status_code == 422
    assert client.get("/api/v1/notices", params={"page": 0}).status_code == 422
