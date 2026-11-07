from tests.conftest import make_pdf


def test_subject_course_flow(client, login):
    assert client.post("/api/v1/subjects", json={"name": "자료구조"}).status_code == 401
    login()
    subject = client.post("/api/v1/subjects", json={"name": "자료구조"}).json()
    assert client.post("/api/v1/subjects", json={"name": "자료구조"}).status_code == 409

    course = client.post(
        "/api/v1/courses", json={"subject_id": subject["id"], "professor_name": "홍길동"}
    ).json()
    assert course["professor_name"] == "홍길동"
    dup = client.post(
        "/api/v1/courses", json={"subject_id": subject["id"], "professor_name": "홍길동"}
    )
    assert dup.status_code == 409

    subjects = client.get("/api/v1/subjects").json()
    assert subjects == [{"id": subject["id"], "name": "자료구조", "code": None, "course_count": 1}]
    assert len(client.get(f"/api/v1/subjects/{subject['id']}/courses").json()) == 1

    r = client.patch(f"/api/v1/courses/{course['id']}", json={"exam_info": "중간 40%"})
    assert r.json()["exam_info"] == "중간 40%"
    assert client.get("/api/v1/courses/999").status_code == 404


def test_upload_pdf(client, login, course_with_problems):
    cid = course_with_problems["course"].id
    files = {
        "file": (
            "week1.pdf",
            make_pdf(["pointer stores address", "array is contiguous"]),
            "application/pdf",
        )
    }
    data = {"kind": "lecture", "title": "1주차"}
    assert (
        client.post(f"/api/v1/courses/{cid}/materials", files=files, data=data).status_code == 401
    )

    login()
    r = client.post(f"/api/v1/courses/{cid}/materials", files=files, data=data)
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["page_count"] == 2 and m["uploader_name"] == "민제"

    page = client.get(f"/api/v1/materials/{m['id']}/pages/2").json()
    assert "contiguous" in page["text"]
    assert client.get(f"/api/v1/materials/{m['id']}/pages/3").status_code == 404
    assert len(client.get(f"/api/v1/courses/{cid}/materials").json()) == 1


def test_upload_rejects_non_pdf(client, login, course_with_problems):
    login()
    cid = course_with_problems["course"].id
    r = client.post(
        f"/api/v1/courses/{cid}/materials",
        files={"file": ("a.txt", b"hello", "text/plain")},
        data={"kind": "lecture", "title": "t"},
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/v1/courses/{cid}/materials",
        files={"file": ("a.pdf", b"not a pdf", "application/pdf")},
        data={"kind": "lecture", "title": "t"},
    )
    assert r.status_code == 400
