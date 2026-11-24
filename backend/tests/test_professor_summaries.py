from datetime import date

import pytest

from app.core.config import settings
from app.features.professor_summaries import router as module
from app.models import CatalogOffering, CourseReview, Enrollment, Professor, User
from app.services import llm

URL = "/api/v1/catalog/professor-summary?emp_no=E1"


@pytest.fixture
def reviews(session, course_with_problems, monkeypatch):
    monkeypatch.setattr("app.features.enrollments.service._today", lambda: date(2026, 11, 24))
    module._cache.clear()
    module._attempts.clear()
    module._active.clear()
    course = course_with_problems["course"]
    professor = session.get(Professor, course.professor_id)
    professor.emp_no = "E1"
    session.add(professor)
    session.add(
        CatalogOffering(
            year="2026",
            sem_cd="CM160.20",
            sbj_no="CS1",
            sbj_nm="기초프로그래밍",
            emp_no="E1",
            emp_nm=professor.name,
        )
    )
    items = []
    for i in range(3):
        user = User(email=f"private{i}@example.com", name=f"작성자{i}", password_hash="unused")
        session.add(user)
        session.flush()
        enrollment = Enrollment(
            user_id=user.id,
            course_id=course.id,
            year="2026",
            sem_cd="CM160.20",
            sbj_no="CS1",
            sbj_nm="기초프로그래밍",
        )
        session.add(enrollment)
        session.flush()
        review = CourseReview(
            user_id=user.id,
            enrollment_id=enrollment.id,
            course_id=course.id,
            year="2026",
            sem_cd="CM160.20",
            content="실습 과제가 개념 이해에 도움이 됩니다. 연락처 010-1234-5678 private@example.com",
            difficulty=3,
            workload=4,
            recommendation=5,
        )
        session.add(review)
        items.append(review)
    session.commit()
    return items


def draft(ids):
    return llm.ProfessorSummaryDraft(
        overview=llm.ProfessorSummaryClaim(
            text="기초프로그래밍 후기에서는 실습이 도움이 된다는 의견이 있습니다.", review_ids=ids
        ),
        highlights=[],
        differences=[],
    )


def test_generate_cache_privacy_and_deletion(client, login, session, reviews, monkeypatch):
    login()
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    calls = []

    def generate(payload):
        calls.append(payload)
        assert "private@example.com" not in payload
        assert "010-1234-5678" not in payload
        assert "user_id" not in payload
        assert "작성자" not in payload
        return draft([r.id for r in reviews])

    monkeypatch.setattr(llm, "summarize_professor", generate)
    assert client.get(URL).json()["status"] == "not_generated"
    assert not calls
    result = client.post(URL)
    assert result.status_code == 200
    out = result.json()
    assert out["status"] == "ready"
    assert out["stats"]["recommendation"] == 5
    assert len(out["sources"]) == 3
    assert "content" not in out["sources"][0]
    assert client.post(URL).json()["status"] == "ready"
    assert len(calls) == 1
    reviews[0].is_deleted = True
    session.add(reviews[0])
    session.commit()
    out = client.get(URL).json()
    assert out["status"] == "insufficient"
    assert out["summary"] is None
    assert out["stats"]["review_count"] == 2


def test_no_key_and_auth(client, login, reviews):
    assert client.get(URL).status_code == 401
    assert client.post(URL).status_code == 401
    login()
    assert client.get(URL).json()["status"] == "unavailable"
    assert client.post(URL).status_code == 503
    assert client.get(URL.replace("E1", "missing")).status_code == 404


@pytest.mark.parametrize("invalid", ["unknown", "single", "none"])
def test_invalid_evidence_not_published(client, login, reviews, monkeypatch, invalid):
    login()
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    output = (
        None if invalid == "none" else draft([99999] if invalid == "unknown" else [reviews[0].id])
    )
    monkeypatch.setattr(llm, "summarize_professor", lambda _: output)
    assert client.post(URL).status_code == 502
    assert client.get(URL).json()["summary"] is None
    assert client.post(URL).status_code == 429


def test_changes_during_generation_are_discarded(client, login, session, reviews, monkeypatch):
    login()
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")

    def generate(_):
        result = draft([r.id for r in reviews])
        reviews[0].is_deleted = True
        session.add(reviews[0])
        session.commit()
        return result

    monkeypatch.setattr(llm, "summarize_professor", generate)
    assert client.post(URL).status_code == 409
    assert not module._cache


def test_old_reviews_excluded(client, login, session, reviews):
    login()
    reviews[0].year = "2023"
    session.add(reviews[0])
    session.commit()
    assert client.get(URL).json()["stats"]["review_count"] == 2
    assert client.post(URL).json()["status"] == "insufficient"
