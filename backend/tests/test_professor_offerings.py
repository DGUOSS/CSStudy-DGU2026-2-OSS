from datetime import date

import pytest

from app.models import CatalogOffering


@pytest.fixture(autouse=True)
def catalog(session, monkeypatch):
    monkeypatch.setattr("app.features.enrollments.service._today", lambda: date(2026, 11, 24))
    for year, sem, code, section, emp in [
        ("2023", "CM160.10", "OLD", "01", "E1"),
        ("2024", "CM160.10", "CS1", "01", "E1"),
        ("2026", "CM160.20", "CS1", "01", "E1"),
        ("2026", "CM160.20", "CS1", "02", "E1"),
        ("2025", "CM160.11", "CS2", "01", "E1"),
        ("2026", "CM160.20", "OTHER", "01", "E2"),
        ("2027", "CM160.10", "FUTURE", "01", "E1"),
        ("2026", "CM160.20", "UNKNOWN", "01", None),
    ]:
        session.add(
            CatalogOffering(
                year=year,
                sem_cd=sem,
                sbj_no=code,
                sbj_nm=code,
                dvcls=section,
                emp_no=emp,
                emp_nm="김교수",
                dpt_nm="컴퓨터공학과",
            )
        )
    session.commit()


def test_search_separates_namesakes_and_pages(client, login):
    login()
    result = client.get("/api/v1/catalog/professors", params={"q": " 김교수 ", "limit": 1}).json()
    assert result["total"] == 2
    assert result["start_year"] == "2024"
    assert result["end_year"] == "2026"
    assert result["items"] == [{"emp_no": "E1", "name": "김교수", "subject_count": 2}]
    second = client.get("/api/v1/catalog/professors", params={"q": "김", "offset": 1}).json()
    assert second["items"][0]["emp_no"] == "E2"
    assert client.get("/api/v1/catalog/professors", params={"q": "%"}).json()["total"] == 0
    assert client.get("/api/v1/catalog/professors", params={"q": "   "}).status_code == 422


def test_history_groups_sections_and_includes_seasonal_terms(client, login):
    login()
    result = client.get("/api/v1/catalog/professor-offerings", params={"emp_no": "E1"}).json()
    assert [s["code"] for s in result["subjects"]] == ["CS1", "CS2"]
    first, second = result["subjects"]
    assert first["terms"][0]["sections"] == ["01", "02"]
    assert [t["year"] for t in first["terms"]] == ["2026", "2024"]
    assert second["terms"][0]["label"] == "2025 여름학기"
    other = client.get("/api/v1/catalog/professor-offerings", params={"emp_no": "E2"}).json()
    assert [s["code"] for s in other["subjects"]] == ["OTHER"]
    assert (
        client.get("/api/v1/catalog/professor-offerings", params={"emp_no": "missing"}).status_code
        == 404
    )


def test_january_uses_previous_academic_year(client, login, monkeypatch):
    login()
    monkeypatch.setattr("app.features.enrollments.service._today", lambda: date(2026, 1, 5))
    result = client.get("/api/v1/catalog/professor-offerings", params={"emp_no": "E1"}).json()
    assert (result["start_year"], result["end_year"]) == ("2023", "2025")
    assert {s["code"] for s in result["subjects"]} == {"OLD", "CS1", "CS2"}


def test_authentication_required(client):
    assert client.get("/api/v1/catalog/professors", params={"q": "김"}).status_code == 401
    assert (
        client.get("/api/v1/catalog/professor-offerings", params={"emp_no": "E1"}).status_code
        == 401
    )
