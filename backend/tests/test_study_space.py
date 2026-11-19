import pytest

from app.models import StudyApplication, StudyGroup, User, _now
from tests.test_study_groups import BODY


@pytest.mark.parametrize(
    "status,expected",
    [(None, 403), ("pending", 403), ("rejected", 403), ("cancelled", 403), ("approved", 200)],
)
def test_space_membership(client, login, enroll, course_with_problems, session, status, expected):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    group = client.post(f"/api/v1/subjects/{c.subject_id}/study-groups", json=BODY).json()
    url = f"/api/v1/study-groups/{group['id']}/space"
    owner_result = client.get(url)
    assert owner_result.status_code == 200 and owner_result.json()["is_owner"]
    client.cookies.clear()
    assert client.get(url).status_code == 401
    login("space@dgu.ac.kr")
    uid = client.get("/api/v1/auth/me").json()["id"]
    if status:
        session.add(StudyApplication(group_id=group["id"], user_id=uid, status=status))
        session.commit()
    assert client.get(url).status_code == expected
    # Closing recruitment does not close the members' space.
    row = session.get(StudyGroup, group["id"])
    row.closed_at = _now()
    session.add(row)
    session.commit()
    assert client.get(url).status_code == expected
    if status == "approved":
        data = client.get(url).json()
        assert data["subject_id"] == c.subject_id and not data["is_owner"]
        assert (
            client.post(
                f"/api/v1/subjects/{c.subject_id}/study-groups/{group['id']}/cancel"
            ).status_code
            == 200
        )
        assert client.get(url).status_code == 403
    else:
        # Admin status alone must not reveal a private study space.
        user = session.get(User, uid)
        user.role = "admin"
        session.add(user)
        session.commit()
        assert client.get(url).status_code == 403
    assert client.get("/api/v1/study-groups/999999/space").status_code == 404
