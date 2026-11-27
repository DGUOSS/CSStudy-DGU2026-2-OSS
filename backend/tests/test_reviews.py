from sqlmodel import select

from app.models import Course, CourseReview, Enrollment, Professor
from tests.conftest import make_admin


def setup_review(client, login, enroll, course):
    login()
    enroll(course.subject_id)
    terms = client.get(f"/api/v1/courses/{course.id}/reviews/terms").json()
    body = dict(
        enrollment_id=terms[0]["enrollment_id"],
        recommendation=4,
        difficulty=3,
        workload=2,
        content="교안의 예제를 직접 풀어보는 것이 도움이 됩니다.",
    )
    return body


def test_review_lifecycle_and_privacy(client, login, enroll, course_with_problems):
    course = course_with_problems["course"]
    body = setup_review(client, login, enroll, course)
    url = f"/api/v1/courses/{course.id}/reviews"
    r = client.post(url, json=body)
    assert r.status_code == 201, r.text
    review = r.json()
    assert review["is_mine"] and review["year"] == "2026"
    assert review["recommendation"] == 4
    assert not ({"user_id", "enrollment_id", "email", "name"} & review.keys())
    assert client.post(url, json=body).status_code == 409
    edit = dict(
        content="실습 문제를 충분히 연습하면 이해하기 쉬운 수업입니다.", difficulty=4, workload=3
    )
    assert client.patch(f"/api/v1/reviews/{review['id']}", json=edit).status_code == 405
    assert client.get(url + "/terms").json()[0]["review_id"] == review["id"]
    assert client.delete(f"/api/v1/reviews/{review['id']}").status_code == 204
    assert client.get(url).json() == []
    assert client.post(url, json=body).status_code == 409


def test_non_enrolled_user_can_read_but_cannot_write_or_edit(
    client, login, enroll, course_with_problems
):
    course = course_with_problems["course"]
    body = setup_review(client, login, enroll, course)
    url = f"/api/v1/courses/{course.id}/reviews"
    rid = client.post(url, json=body).json()["id"]
    login("other@dgu.ac.kr")
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()[0]["id"] == rid
    assert response.json()[0]["is_mine"] is False
    assert client.post(url, json=body).status_code == 403
    assert client.patch(f"/api/v1/reviews/{rid}", json=body).status_code == 405
    assert client.delete(f"/api/v1/reviews/{rid}").status_code == 404


def test_public_and_admin_access_do_not_grant_writing(client, login, session, course_with_problems):
    course = course_with_problems["course"]
    course.is_public = True
    session.add(course)
    session.commit()
    login()
    url = f"/api/v1/courses/{course.id}/reviews"
    body = dict(
        enrollment_id=999,
        recommendation=4,
        difficulty=3,
        workload=3,
        content="수강 기록 없이 작성하는 후기입니다.",
    )
    assert client.get(url).status_code == 200
    assert client.get(url + "/terms").json() == []
    assert client.post(url, json=body).status_code == 403
    make_admin(session)
    assert client.post(url, json=body).status_code == 403


def test_review_validation_and_terms(client, login, enroll, session, course_with_problems):
    course = course_with_problems["course"]
    body = setup_review(client, login, enroll, course)
    url = f"/api/v1/courses/{course.id}/reviews"
    for change in (
        {"content": " " * 20},
        {"difficulty": 6},
        {"recommendation": 0},
        {"recommendation": 6},
        {"workload": 0},
        {"content": "x" * 3001},
    ):
        assert client.post(url, json=body | change).status_code == 422
    client.post(url, json=body)
    old = session.get(Enrollment, body["enrollment_id"])
    other = Enrollment(
        user_id=old.user_id,
        course_id=course.id,
        year="2025",
        sem_cd=old.sem_cd,
        sbj_no=old.sbj_no,
        sbj_nm=old.sbj_nm,
        dvcls=old.dvcls,
    )
    session.add(other)
    session.commit()
    assert client.post(url, json=body | {"enrollment_id": other.id}).status_code == 409
    assert client.get(url + "?limit=1&offset=1").json() == []
    make_admin(session)
    assert client.delete(f"/api/v1/admin/courses/{course.id}").status_code == 204
    assert session.exec(select(CourseReview)).all() == []


def test_different_professors_allowed_and_each_course_locked_after_delete(
    client, login, enroll, session, course_with_problems
):
    course = course_with_problems["course"]
    body = setup_review(client, login, enroll, course)
    url = f"/api/v1/courses/{course.id}/reviews"
    r = client.post(url, json=body).json()
    original = session.get(Enrollment, body["enrollment_id"])
    prof = Professor(name="Another professor")
    session.add(prof)
    session.flush()
    second = Course(subject_id=course.subject_id, professor_id=prof.id)
    session.add(second)
    session.flush()
    e = Enrollment(
        user_id=original.user_id,
        course_id=second.id,
        year="2025",
        sem_cd=original.sem_cd,
        sbj_no=original.sbj_no,
        sbj_nm=original.sbj_nm,
        dvcls="02",
    )
    session.add(e)
    session.commit()
    other_url = f"/api/v1/courses/{second.id}/reviews"
    assert client.get(other_url + "/terms").json()[0]["review_id"] is None
    second_review = client.post(other_url, json=body | {"enrollment_id": e.id})
    assert second_review.status_code == 201, second_review.text
    second_id = second_review.json()["id"]
    assert client.post(other_url, json=body | {"enrollment_id": e.id}).status_code == 409
    assert client.delete(f"/api/v1/reviews/{r['id']}").status_code == 204
    stored = session.get(CourseReview, r["id"])
    session.refresh(stored)
    assert stored.is_deleted and stored.content == ""
    assert client.post(url, json=body).status_code == 409
    assert client.get(other_url + "/terms").json()[0]["review_id"] == second_id
    assert client.delete(f"/api/v1/reviews/{second_id}").status_code == 204
    assert client.post(other_url, json=body | {"enrollment_id": e.id}).status_code == 409
