from sqlmodel import select

from app.models import StudyApplication
from tests.test_study_groups import BODY


def switch(client, cookies):
    client.cookies.clear()
    client.cookies.update(cookies)


def test_application_capacity_privacy_and_cancel(
    client, login, enroll, course_with_problems, session
):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    owner = dict(client.cookies)
    base = f"/api/v1/subjects/{c.subject_id}/study-groups"
    gid = client.post(base, json={**BODY, "capacity": 2}).json()["id"]
    url = f"{base}/{gid}"
    assert client.post(url + "/apply").status_code == 409
    client.cookies.clear()
    login("one@dgu.ac.kr")
    enroll(c.subject_id)
    one = dict(client.cookies)
    assert client.post(url + "/apply").status_code == 200
    assert client.post(url + "/apply").status_code == 409
    assert client.get(url + "/applications").status_code == 403
    assert client.get(base).json()["items"][0]["pending_count"] is None
    client.cookies.clear()
    login("two@dgu.ac.kr")
    enroll(c.subject_id)
    two = dict(client.cookies)
    assert client.post(url + "/apply").status_code == 200
    switch(client, owner)
    apps = client.get(url + "/applications").json()
    aid, bid = [a["id"] for a in apps]
    assert not {"email", "user_id"} & apps[0].keys()
    assert (
        client.post(
            url + f"/applications/{aid}/decision", json={"decision": "approved"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            url + f"/applications/{bid}/decision", json={"decision": "approved"}
        ).status_code
        == 409
    )
    assert client.get(base).json()["items"][0]["participant_count"] == 2
    switch(client, one)
    assert (
        client.post(
            url + f"/applications/{bid}/decision", json={"decision": "rejected"}
        ).status_code
        == 403
    )
    assert client.post(url + "/cancel").status_code == 200
    switch(client, owner)
    assert (
        client.post(
            url + f"/applications/{bid}/decision", json={"decision": "approved"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            url + f"/applications/{bid}/decision", json={"decision": "approved"}
        ).status_code
        == 409
    )
    assert len(session.exec(select(StudyApplication)).all()) == 2
    switch(client, two)
    assert client.get(base).json()["items"][0]["my_application"] == "approved"


def test_unlimited_reapply_close_and_scope(client, login, enroll, course_with_problems):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    owner = dict(client.cookies)
    base = f"/api/v1/subjects/{c.subject_id}/study-groups"
    group = client.post(base, json={**BODY, "capacity": 0})
    assert group.status_code == 201 and group.json()["capacity"] == 0
    url = base + "/" + str(group.json()["id"])
    client.cookies.clear()
    login("applicant@dgu.ac.kr")
    applicant = dict(client.cookies)
    assert client.post(url + "/apply").status_code == 403
    enroll(c.subject_id)
    assert client.post(url + "/apply").status_code == 200
    assert client.post(url + "/cancel").status_code == 200
    assert client.post(url + "/apply").status_code == 200
    switch(client, owner)
    apps = client.get(url + "/applications").json()
    assert len(apps) == 1
    aid = apps[0]["id"]
    assert (
        client.post(
            url + f"/applications/{aid}/decision", json={"decision": "rejected"}
        ).status_code
        == 200
    )
    switch(client, applicant)
    assert client.post(url + "/apply").status_code == 200
    switch(client, owner)
    assert client.post(url + "/close").status_code == 200
    assert client.get(url + "/applications").json()[0]["status"] == "rejected"
    switch(client, applicant)
    assert client.post(url + "/apply").status_code == 409
    assert (
        client.get(
            "/api/v1/subjects/999/study-groups/" + str(group.json()["id"]) + "/applications"
        ).status_code
        == 404
    )


def test_close_keeps_approved_members(client, login, enroll, course_with_problems):
    c = course_with_problems["course"]
    login()
    enroll(c.subject_id)
    owner = dict(client.cookies)
    base = f"/api/v1/subjects/{c.subject_id}/study-groups"
    gid = client.post(base, json={**BODY, "capacity": 0}).json()["id"]
    url = f"{base}/{gid}"
    client.cookies.clear()
    login("member@dgu.ac.kr")
    enroll(c.subject_id)
    member = dict(client.cookies)
    client.post(url + "/apply")
    switch(client, owner)
    aid = client.get(url + "/applications").json()[0]["id"]
    client.post(url + f"/applications/{aid}/decision", json={"decision": "approved"})
    client.post(url + "/close")
    assert client.get(base + "?state=closed").json()["items"][0]["participant_count"] == 2
    switch(client, member)
    assert client.post(url + "/cancel").status_code == 200
    assert client.get(base + "?state=closed").json()["items"][0]["participant_count"] == 1
