from sqlmodel import select

from app.models import Course, Enrollment, StudyGroup

BODY = dict(
    title="동기화 복습 스터디",
    description="뮤텍스와 세마포어 개념을 함께 복습합니다.",
    capacity=4,
    mode="offline",
    schedule="수요일 18시",
    location="중앙도서관",
)


def test_auth_access_and_invalid_course(client, login, enroll, course_with_problems):
    c = course_with_problems["course"]
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    assert client.get(url).status_code == 401
    assert client.post(url, json=BODY).status_code == 401
    login()
    assert client.get(url).status_code == 403
    assert client.post(url, json=BODY).status_code == 403
    assert client.get("/api/v1/subjects/999999/study-groups").status_code == 404
    enroll(c.subject_id)
    assert client.get(url).json() == {"items": [], "total": 0}


def test_create_close_lifecycle_and_idempotency(
    client, login, enroll, course_with_problems, session
):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    response = client.post(url, json={**BODY, "title": "  함께 복습해요  "})
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["title"] == "함께 복습해요" and row["is_mine"]
    assert row["closed_at"] is None
    assert not {"owner_id", "email", "password_hash"} & row.keys()
    assert client.get(url).json()["total"] == 1
    close = url + f"/{row['id']}/close"
    result = client.post(close)
    assert result.status_code == 200
    closed_at = result.json()["closed_at"]
    assert closed_at and client.post(close).json()["closed_at"] == closed_at
    assert client.get(url).json()["total"] == 0
    assert client.get(url + "?state=closed").json()["total"] == 1
    assert client.get(url + "?state=all").json()["total"] == 1
    assert session.get(StudyGroup, row["id"]).closed_at is not None


def test_non_owner_cannot_close_and_course_scope(
    client, login, enroll, course_with_problems, session
):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    gid = client.post(url, json=BODY).json()["id"]
    assert client.post(f"/api/v1/subjects/99999/study-groups/{gid}/close").status_code == 404
    client.cookies.clear()
    login("other@dgu.ac.kr")
    assert client.post(url + f"/{gid}/close").status_code == 403
    enroll(c.subject_id)
    assert client.get(url).json()["items"][0]["is_mine"] is False
    assert client.post(url + f"/{gid}/close").status_code == 403
    assert client.post(url + "/99999/close").status_code == 404


def test_validation(client, login, enroll, course_with_problems):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    for patch in [
        dict(title="   "),
        dict(description="         "),
        dict(capacity=1),
        dict(capacity=21),
        dict(mode="other"),
        dict(location=""),
        dict(schedule=" "),
        dict(owner_id=999),
        dict(closed_at="2026-01-01"),
    ]:
        assert client.post(url, json={**BODY, **patch}).status_code == 422, patch
    for query in ["state=invalid", "offset=-1", "limit=51"]:
        assert client.get(url + "?" + query).status_code == 422
    assert client.get(url).json()["total"] == 0


def test_public_course_and_separate_lists(client, login, session, course_with_problems):
    c = course_with_problems["course"]
    c.is_public = True
    session.add(c)
    other = Course(subject_id=c.subject_id, professor_id=c.professor_id, is_public=True)
    # Use a different subject so the course pair stays unique.
    from app.models import Subject

    subject = Subject(name="다른 과목")
    session.add(subject)
    session.flush()
    other.subject_id = subject.id
    session.add(other)
    session.commit()
    login()
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    assert client.post(url, json=BODY).status_code == 201
    assert client.get(f"/api/v1/subjects/{other.subject_id}/study-groups").json()["items"] == []
    assert client.get(url + "?limit=1&offset=1").json() == {"items": [], "total": 1}


def test_owner_can_close_after_enrollment_removed(
    client, login, enroll, course_with_problems, session
):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    gid = client.post(url, json=BODY).json()["id"]
    for e in session.exec(select(Enrollment)).all():
        session.delete(e)
    session.commit()
    assert client.get(url).status_code == 403
    assert client.post(url + f"/{gid}/close").status_code == 200


def test_different_professors_share_subject_without_course_access(
    client, login, enroll, session, course_with_problems
):
    from app.models import Professor

    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    gid = client.post(url, json=BODY).json()["id"]
    prof = Professor(name="다른 교수")
    session.add(prof)
    session.flush()
    other = Course(subject_id=c.subject_id, professor_id=prof.id)
    session.add(other)
    session.commit()
    # First user can see shared studies but not the other professor's private course.
    assert client.get(f"/api/v1/courses/{other.id}").status_code == 403
    client.cookies.clear()
    login("second-professor@dgu.ac.kr")
    uid = client.get("/api/v1/auth/me").json()["id"]
    session.add(
        Enrollment(
            user_id=uid,
            course_id=other.id,
            year="2026",
            sem_cd="CM160.20",
            sbj_no="TST9999",
            sbj_nm="같은 과목",
            dvcls="02",
        )
    )
    session.commit()
    assert client.get(f"/api/v1/courses/{c.id}").status_code == 403
    data = client.get(url).json()
    assert data["total"] == 1 and data["items"][0]["id"] == gid
    assert data["items"][0]["subject_id"] == c.subject_id
    assert "course_id" not in data["items"][0]
    assert client.post(url, json=BODY).status_code == 201
    assert client.post(url + f"/{gid}/close").status_code == 403
    assert client.get(url).json()["total"] == 2
    mine = client.get("/api/v1/me/courses").json()
    assert mine["courses"][0]["subject_id"] == c.subject_id
