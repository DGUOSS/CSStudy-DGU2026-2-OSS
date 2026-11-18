from datetime import UTC, datetime
from importlib import import_module
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException

from app.features.department_notices import service as s
from app.features.department_notices.catalog import DEPARTMENTS, SOURCES

r = import_module("app.features.department_notices.router")
BASE = "/api/v1/department-notices"


def test_preferences_auth_validation_and_user_isolation(client, login):
    assert client.get(BASE + "/preferences").status_code == 401
    assert client.get(BASE + "/feed").status_code == 401
    login()
    assert client.get(BASE + "/preferences").json() == {"department_ids": []}
    assert client.put(
        BASE + "/preferences", json={"department_ids": ["cs", "cs", "mgt"]}
    ).json() == {"department_ids": ["cs", "mgt"]}
    assert client.get(BASE + "/preferences").json()["department_ids"] == ["cs", "mgt"]
    disabled = next(d.id for d in DEPARTMENTS.values() if not d.source_ids)
    for ids in [["https://attacker.test"], [disabled], list(SOURCES)[1:10]]:
        assert client.put(BASE + "/preferences", json={"department_ids": ids}).status_code == 422
    client.cookies.clear()
    login("other@dgu.ac.kr")
    assert client.get(BASE + "/preferences").json()["department_ids"] == []
    assert client.get(BASE + "/feed?source=cs").status_code == 403
    assert client.get(BASE + "/sources/cs/items/1").status_code == 403


def test_feed_partial_failure_and_source_identity(client, login, monkeypatch):
    login()
    client.put(BASE + "/preferences", json={"department_ids": ["cs", "mgt"]})
    calls = []

    def load(sid, q, page):
        calls.append((sid, q, page))
        if sid == "mgt":
            raise HTTPException(503, "offline")
        item = s.Item(
            id=1,
            source_id=sid,
            source_name=sid,
            title="test",
            date="2026-11-18" if sid == "cs" else "2026-11-17",
            pinned=False,
            url=SOURCES[sid].url,
        )
        return s.BoardPage(
            items=[item, item],
            total=1,
            page=page,
            has_next=False,
            source_id=sid,
            source_name=sid,
            source_url=SOURCES[sid].url,
            fetched_at=datetime.now(UTC),
        )

    monkeypatch.setattr(r, "load_page", load)
    data = client.get(BASE + "/feed", params={"q": " test "}).json()
    assert [i["source_id"] for i in data["items"]] == ["cs", "school"]
    assert data["failed_sources"][0]["id"] == "mgt"
    assert all(q == "test" for _, q, _ in calls)
    assert client.get(BASE + "/feed?page=2").status_code == 422
    data = client.get(BASE + "/feed?source=cs&page=2").json()
    assert data["boards"][0]["page"] == 2
    assert len(data["items"]) == 1


def test_standard_cards_deduplicate_and_search_excludes_pins():
    pin = '<li class="nlist"><div class="num_wrap"><span class="mark"></span></div><div class="tit"><a onclick="goDetail(1)">Pinned</a></div><li class="date">2026-11-18</li></li>'
    row = '<li><div class="tit"><a onclick="goDetail(2)">Regular</a></div><span class="date">2026-11-17</span></li>'
    html = (
        '<p class="count">2</p><ul class="bd_list">'
        + pin
        + row * 2
        + '</ul><div class="paging"><a href="?pageIndex=2">2</a></div>'
    )
    page = s.parse_page(html, SOURCES["cs"], "", 1)
    assert len(page.items) == 2 and page.has_next
    assert page.items[1].date == "2026-11-17"
    assert [x.id for x in s.parse_page(html, SOURCES["cs"], "query", 1).items] == [2]
    assert not s.parse_page('<p class="count">0</p>', SOURCES["cs"], "none", 1).items


def test_gnu_pretty_pagination_and_encoded_search():
    html = '<div id="bo_list_total">Total 30</div><table id="bo_list"><tbody><tr><td class="td_subject"><a href="/movie23_1_3_1/123">Title</a></td><td class="td_date">26-11-18</td></tr></tbody></table><a href="/movie23_1_3_1/p2">2</a>'
    page = s.parse_page(html, SOURCES["movie"], "", 1)
    assert page.has_next and page.items[0].id == 123
    assert page.items[0].date == "2026-11-18"
    url = s.list_url(SOURCES["dguadpr"], "a&b=1", 2)
    params = parse_qs(urlsplit(url).query)
    assert params["stx"] == ["a&b=1"] and params["page"] == ["2"]
    assert params["bo_table"] == ["table31"]


def test_detail_plain_text_and_unknown_id(monkeypatch):
    detail = s.parse_detail(
        '<div class="detail_wrap"><div class="bottom"><div class="contents"><script>evil()</script><p>Hello</p><p>World</p></div></div></div>',
        "https://cs.dongguk.edu",
    )
    assert detail.text == "Hello\nWorld"
    with pytest.raises(ValueError):
        s.parse_detail("<html>Login required</html>", "https://movie.dongguk.edu")
    with pytest.raises(ValueError):
        s.parse_page("<html>Maintenance</html>", SOURCES["cs"], "", 1)
    monkeypatch.setattr(
        s,
        "load_page",
        lambda *args: s.BoardPage(
            items=[],
            total=0,
            page=1,
            has_next=False,
            source_id="cs",
            source_name="CS",
            source_url=SOURCES["cs"].url,
            fetched_at=datetime.now(UTC),
        ),
    )
    with pytest.raises(HTTPException) as error:
        s.load_detail("cs", 999, "", 1)
    assert error.value.status_code == 404
