from app.models import Chapter, Problem
from tests.conftest import make_admin, make_pdf

A = ["A pointer variable stores the address of another variable", "Arrays decay to pointers"]
B = ["Structures group several variables together", "Unions let members share memory"]


def _files(*docs):
    return [("files", (name, make_pdf(pages), "application/pdf")) for name, pages in docs]


def test_admin_only(client, login):
    login()
    form = {"subject_name": "자료구조", "professor_name": "홍길동"}
    assert client.post("/api/v1/admin/courses", data=form).status_code == 403
    assert client.delete("/api/v1/admin/subjects/1").status_code == 403


def test_admin_create_course_with_files(client, login, session):
    login()
    make_admin(session)
    form = {"subject_name": "자료구조", "professor_name": "홍길동", "subject_code": "CSC2004"}
    r = client.post("/api/v1/admin/courses", data=form, files=_files(("w1.pdf", A), ("w2.pdf", B)))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] and body["course"]["professor_name"] == "홍길동"
    assert [u["action"] for u in body["uploads"]] == ["new", "new"]
    cid = body["course"]["id"]

    # 같은 강좌에 다시: 강좌는 그대로(200), 같은 교안은 중복, 수정본은 새 판
    r = client.post(
        "/api/v1/admin/courses",
        data=form,
        files=_files(("w1_copy.pdf", A), ("w2_fix.pdf", [B[0], B[1] + " in one place"])),
    )
    assert r.status_code == 200
    assert [u["action"] for u in r.json()["uploads"]] == ["duplicate", "updated"]
    assert len(client.get(f"/api/v1/courses/{cid}/materials").json()) == 2

    # 파일 없이 강좌만
    r = client.post(
        "/api/v1/admin/courses", data={"subject_name": "운영체제", "professor_name": "김교수"}
    )
    assert r.status_code == 201 and r.json()["uploads"] == []


def test_admin_edit_and_delete(client, login, session, course_with_problems):
    login()
    make_admin(session)
    course = course_with_problems["course"]
    sid = course.subject_id

    # 과목 이름·학수번호 고치기
    r = client.patch(
        f"/api/v1/admin/subjects/{sid}", json={"name": "기초프로그래밍1", "code": "CSC2001"}
    )
    assert r.json()["name"] == "기초프로그래밍1" and r.json()["code"] == "CSC2001"
    # 교수명 고치기
    r = client.patch(f"/api/v1/admin/courses/{course.id}", json={"professor_name": "강교수"})
    assert r.json()["professor_name"] == "강교수"
    # 챕터·문제·풀이 기록·족보 평가가 있는 강좌도 통째로 지운다
    client.put(f"/api/v1/me/subjects/{sid}", json={})
    prob = course_with_problems["problems"][0]
    client.post(f"/api/v1/problems/{prob.id}/attempts", json={"chosen_index": 0})
    ex = client.post(
        f"/api/v1/courses/{course.id}/materials",
        files={"file": ("e.pdf", make_pdf(A), "application/pdf")},
        data={"kind": "exam"},
    ).json()
    client.put(f"/api/v1/materials/{ex['id']}/vote", json={"value": 1})
    client.put(f"/api/v1/courses/{course.id}/exam-selection", json={"material_ids": [ex["id"]]})
    assert client.delete(f"/api/v1/admin/courses/{course.id}").status_code == 204
    assert client.get(f"/api/v1/courses/{course.id}").status_code == 404
    # 과목도 '내 과목' 등록과 함께 지워진다
    assert client.delete(f"/api/v1/admin/subjects/{sid}").status_code == 204
    assert client.get("/api/v1/me/subjects").json() == []

    # 빈 강좌는 자료와 함께 지워지고, 그다음 과목도 지울 수 있다
    r = client.post(
        "/api/v1/admin/courses",
        data={"subject_name": "임시", "professor_name": "누구"},
        files=_files(("x.pdf", A)),
    ).json()
    assert client.delete(f"/api/v1/admin/courses/{r['course']['id']}").status_code == 204
    assert client.delete(f"/api/v1/admin/subjects/{r['course']['subject_id']}").status_code == 204


def test_delete_latest_restores_previous(client, login, session, course_with_problems):
    login()
    make_admin(session)
    cid = course_with_problems["course"].id
    up = lambda name, pages: client.post(  # noqa: E731
        f"/api/v1/courses/{cid}/materials",
        files={"file": (name, make_pdf(pages), "application/pdf")},
        data={"kind": "lecture", "title": name},
    ).json()
    v1 = up("v1.pdf", A)
    v2 = up("v2.pdf", ["Intro page for the midterm review session", *A])
    assert v2["action"] == "updated"
    prob = course_with_problems["problems"][0]
    prob.evidence, prob.source_material_id, prob.source_page = A[0], v2["id"], 2
    session.add(prob)
    session.commit()

    # 제목 고치기
    r = client.patch(f"/api/v1/admin/materials/{v2['id']}", json={"title": "포인터 2판"})
    assert r.json()["title"] == "포인터 2판"
    # 챕터가 가리키는 자료도 지울 수 있다(챕터는 이전 판으로)
    ch = course_with_problems["chapter"]
    ch.material_id = v2["id"]
    session.add(ch)
    session.commit()
    # 최신판을 지우면 1판이 다시 최신판, 문제 근거는 1판으로
    assert client.delete(f"/api/v1/admin/materials/{v2['id']}").status_code == 204
    assert [m["id"] for m in client.get(f"/api/v1/courses/{cid}/materials").json()] == [v1["id"]]
    session.expire_all()
    p = session.get(Problem, prob.id)
    assert (p.source_material_id, p.source_page) == (v1["id"], 1)
    assert session.get(Chapter, ch.id).material_id == v1["id"]
