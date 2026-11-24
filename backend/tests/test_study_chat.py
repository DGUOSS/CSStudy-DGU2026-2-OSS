"""스터디 공간 채팅."""

import pytest

from app.models import StudyApplication
from tests.test_study_groups import BODY


@pytest.fixture
def group_with_member(client, login, enroll, course_with_problems, session):
    """개설자(민제)가 스터디를 열고 참여자(하늘)가 승인됨. 참여자로 로그인한 상태로 돌려준다."""
    c = course_with_problems["course"]
    login("owner@dgu.ac.kr", "민제")
    enroll(c.subject_id)
    gid = client.post(f"/api/v1/subjects/{c.subject_id}/study-groups", json=BODY).json()["id"]
    client.cookies.clear()
    login("member@dgu.ac.kr", "하늘")
    uid = client.get("/api/v1/auth/me").json()["id"]
    session.add(StudyApplication(group_id=gid, user_id=uid, status="approved"))
    session.commit()
    return gid


def as_user(client, email):
    client.cookies.clear()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200


def test_members_chat(client, group_with_member):
    url = f"/api/v1/study-groups/{group_with_member}/messages"
    assert client.get(url).json() == []
    r = client.post(url, json={"body": "  안녕하세요!  "})
    assert r.status_code == 201
    first = r.json()
    assert first["body"] == "안녕하세요!" and first["is_mine"] and not first["is_owner"]

    as_user(client, "owner@dgu.ac.kr")
    [m] = client.get(url).json()
    assert m["user_name"] == "하늘" and not m["is_mine"]
    second = client.post(url, json={"body": "반가워요"}).json()
    assert second["is_owner"]

    # 새로 온 것만 받기(폴링)
    after = client.get(url, params={"after_id": first["id"]}).json()
    assert [x["body"] for x in after] == ["반가워요"]
    assert client.get(url, params={"after_id": second["id"]}).json() == []
    assert "email" not in str(client.get(url).json())


def test_outsiders_cannot_read_or_write(client, login, session, group_with_member):
    url = f"/api/v1/study-groups/{group_with_member}/messages"
    client.post(url, json={"body": "비밀 이야기"})
    client.cookies.clear()
    assert client.get(url).status_code == 401
    login("outsider@dgu.ac.kr", "외부인")
    assert client.get(url).status_code == 403
    assert client.post(url, json={"body": "끼워 줘"}).status_code == 403
    # 신청만 하고 승인 전인 사람도 못 본다
    uid = client.get("/api/v1/auth/me").json()["id"]
    session.add(StudyApplication(group_id=group_with_member, user_id=uid, status="pending"))
    session.commit()
    assert client.get(url).status_code == 403
    assert client.get("/api/v1/study-groups/99999/messages").status_code == 404


def test_message_validation(client, group_with_member):
    url = f"/api/v1/study-groups/{group_with_member}/messages"
    assert client.post(url, json={"body": "   "}).status_code == 422
    assert client.post(url, json={"body": "가" * 1001}).status_code == 422


def test_initial_load_returns_latest_in_order(client, group_with_member, session):
    from app.models import StudyMessage

    url = f"/api/v1/study-groups/{group_with_member}/messages"
    uid = client.get("/api/v1/auth/me").json()["id"]
    # 도배 제한(10초에 5개)이 있어 메시지는 DB에 바로 넣는다
    session.add_all(
        [StudyMessage(group_id=group_with_member, user_id=uid, body=f"m{i}") for i in range(55)]
    )
    session.commit()
    got = [m["body"] for m in client.get(url).json()]
    assert len(got) == 50 and got[0] == "m5" and got[-1] == "m54"


def test_flood_limit(client, group_with_member):
    url = f"/api/v1/study-groups/{group_with_member}/messages"
    codes = [client.post(url, json={"body": f"도배 {i}"}).status_code for i in range(7)]
    assert codes[:5] == [201] * 5 and codes[5] == 429
