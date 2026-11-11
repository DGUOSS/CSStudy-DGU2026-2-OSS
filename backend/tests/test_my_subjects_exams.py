from sqlmodel import select

from app.features.exams.router import exam_style_examples
from app.models import User
from tests.conftest import make_admin, make_pdf

EXAM_A = ["Midterm 1. What does p plus one point to when p is an int pointer", "answer four bytes"]
EXAM_B = ["Final exam question about swap function and call by reference", "explain why"]
LECTURE = ["A pointer variable stores the address of another variable in memory"]


def _upload(client, cid, kind, pages, name="file.pdf"):
    files = {"file": (name, make_pdf(pages), "application/pdf")}
    return client.post(f"/api/v1/courses/{cid}/materials", files=files, data={"kind": kind})


def test_only_my_subjects_are_accessible(client, login, course_with_problems, enroll):
    course = course_with_problems["course"]
    login()
    # 내 과목에 없으면 강좌·자료·문제에 들어갈 수 없다
    assert client.get(f"/api/v1/subjects/{course.subject_id}/courses").status_code == 403
    assert client.get(f"/api/v1/courses/{course.id}").status_code == 403
    assert client.get(f"/api/v1/courses/{course.id}/chapters").status_code == 403
    assert client.get(f"/api/v1/courses/{course.id}/materials").status_code == 403
    ch = course_with_problems["chapter"]
    assert client.get(f"/api/v1/chapters/{ch.id}/problems").status_code == 403
    # 과목 목록 자체는 볼 수 있다(내 과목을 고르기 위해)
    assert client.get("/api/v1/subjects").status_code == 200

    mine = enroll(course.subject_id, "taken")
    # 강좌·시험 정보는 관리자만 고친다
    assert client.patch(f"/api/v1/courses/{course.id}", json={"info": "x"}).status_code == 403
    assert mine["status"] == "taken" and mine["source"] == "manual"
    assert client.get(f"/api/v1/courses/{course.id}").status_code == 200
    assert len(client.get("/api/v1/me/subjects").json()) == 1

    # 상태 바꾸기, 빼기
    r = client.put(f"/api/v1/me/subjects/{course.subject_id}", json={"status": "current"})
    assert r.json()["status"] == "current"
    assert client.delete(f"/api/v1/me/subjects/{course.subject_id}").status_code == 204
    assert client.get(f"/api/v1/courses/{course.id}").status_code == 403
    assert client.put("/api/v1/me/subjects/9999", json={}).status_code == 404


def test_admin_can_enter_any_course(client, login, session, course_with_problems):
    login()
    make_admin(session)
    assert client.get(f"/api/v1/courses/{course_with_problems['course'].id}").status_code == 200


def test_material_auto_titles(client, login, course_with_problems, enroll):
    course = course_with_problems["course"]
    login()
    enroll(course.subject_id)
    a = _upload(client, course.id, "exam", EXAM_A).json()
    b = _upload(client, course.id, "exam", EXAM_B).json()
    lec = _upload(client, course.id, "lecture", LECTURE).json()
    assert a["title"] == "기초프로그래밍 족보 1"
    assert b["title"] == "기초프로그래밍 족보 2"
    assert lec["title"] == "기초프로그래밍 교안 1"  # 종류별로 따로 센다

    # 새 판은 대체한 옛 판의 이름을 이어받는다
    v2 = _upload(client, course.id, "exam", [EXAM_A[0], EXAM_A[1] + " and more detail here"]).json()
    assert v2["action"] == "updated" and v2["title"] == "기초프로그래밍 족보 1"
    # 그다음 새 자료는 다음 번호
    c = _upload(client, course.id, "exam", ["Quiz about void pointer casting before dereference"])
    assert c.json()["title"] == "기초프로그래밍 족보 3"


def test_exam_votes_and_selection(client, login, session, course_with_problems, enroll):
    course = course_with_problems["course"]
    login()
    enroll(course.subject_id)
    a = _upload(client, course.id, "exam", EXAM_A).json()
    b = _upload(client, course.id, "exam", EXAM_B).json()
    lec = _upload(client, course.id, "lecture", LECTURE).json()

    # 좋아요/싫어요: 한 사람 한 표, 바꾸기와 취소
    r = client.put(f"/api/v1/materials/{b['id']}/vote", json={"value": 1}).json()
    assert (r["likes"], r["dislikes"], r["my_vote"]) == (1, 0, 1)
    r = client.put(f"/api/v1/materials/{b['id']}/vote", json={"value": -1}).json()
    assert (r["likes"], r["dislikes"]) == (0, 1)
    r = client.put(f"/api/v1/materials/{b['id']}/vote", json={"value": 0}).json()
    assert (r["likes"], r["dislikes"], r["my_vote"]) == (0, 0, 0)
    # 교안에는 누를 수 없다
    assert client.put(f"/api/v1/materials/{lec['id']}/vote", json={"value": 1}).status_code == 400

    # 다른 사용자도 누르면 합산되고, 목록은 좋아요-싫어요가 큰 순
    client.put(f"/api/v1/materials/{b['id']}/vote", json={"value": 1})
    client.post("/api/v1/auth/logout")
    login("b@dgu.ac.kr", "친구")
    enroll(course.subject_id)
    client.put(f"/api/v1/materials/{b['id']}/vote", json={"value": 1})
    client.put(f"/api/v1/materials/{a['id']}/vote", json={"value": -1})
    exams = client.get(f"/api/v1/courses/{course.id}/exams").json()
    assert [e["id"] for e in exams] == [b["id"], a["id"]]
    assert (exams[0]["likes"], exams[0]["my_vote"]) == (2, 1)

    # 족보 선택: 통째로 바꾸기, 이 강좌 족보만
    sel = client.put(
        f"/api/v1/courses/{course.id}/exam-selection", json={"material_ids": [a["id"]]}
    )
    assert [e["id"] for e in sel.json() if e["selected"]] == [a["id"]]
    bad = client.put(
        f"/api/v1/courses/{course.id}/exam-selection", json={"material_ids": [lec["id"]]}
    )
    assert bad.status_code == 400
    client.put(
        f"/api/v1/courses/{course.id}/exam-selection", json={"material_ids": [a["id"], b["id"]]}
    )
    user = session.exec(select(User).where(User.email == "b@dgu.ac.kr")).one()
    examples = exam_style_examples(session, user.id, course.id)
    assert len(examples) == 2 and "Midterm" in examples[0]


def test_exam_access_requires_my_subject(client, login, course_with_problems):
    login()
    cid = course_with_problems["course"].id
    assert client.get(f"/api/v1/courses/{cid}/exams").status_code == 403
    r = client.put(f"/api/v1/courses/{cid}/exam-selection", json={"material_ids": []})
    assert r.status_code == 403
