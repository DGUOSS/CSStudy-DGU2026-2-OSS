from app.models import Material, Problem
from tests.conftest import make_admin, make_pdf

LECTURE = [
    "A pointer variable stores the address of another variable in memory",
    "Adding one to an int pointer moves it by the size of int which is four bytes",
]


def _pdf(pages, name="week03.pdf"):
    return {"file": (name, make_pdf(pages), "application/pdf")}


def test_request_approve_flow(client, login, session):
    form = {"subject_name": "자료구조", "professor_name": "홍길동", "semester": "2026-2"}
    assert client.post("/api/v1/course-requests", data=form).status_code == 401

    login("u@dgu.ac.kr", "학생")
    r = client.post("/api/v1/course-requests", data=form, files=_pdf(LECTURE))
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending" and req["has_material"] and req["material_page_count"] == 2
    # 같은 강좌 요청이 대기 중이면 또 만들지 않는다
    assert client.post("/api/v1/course-requests", data=form).status_code == 409
    assert len(client.get("/api/v1/course-requests/mine").json()) == 1
    # 일반 사용자는 승인 목록을 볼 수 없다
    assert client.get("/api/v1/admin/course-requests").status_code == 403

    client.post("/api/v1/auth/logout")
    login("admin@dgu.ac.kr", "관리자")
    make_admin(session, "admin@dgu.ac.kr")
    pending = client.get("/api/v1/admin/course-requests", params={"status": "pending"}).json()
    assert [p["id"] for p in pending] == [req["id"]]
    # 승인하면서 과목 표기를 고친다
    r = client.post(
        f"/api/v1/admin/course-requests/{req['id']}/approve",
        json={"subject_name": "자료구조와 알고리즘"},
    )
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "approved" and done["course_id"]
    course = client.get(f"/api/v1/courses/{done['course_id']}").json()
    assert course["subject_name"] == "자료구조와 알고리즘" and course["professor_name"] == "홍길동"
    mats = client.get(f"/api/v1/courses/{done['course_id']}/materials").json()
    assert len(mats) == 1 and mats[0]["kind"] == "lecture" and mats[0]["week"] == 3
    # 처리된 요청은 다시 처리할 수 없다
    assert client.post(f"/api/v1/admin/course-requests/{req['id']}/approve").status_code == 409
    # 이제 있는 강좌라 요청 대신 409
    again = {"subject_name": "자료구조와 알고리즘", "professor_name": "홍길동"}
    assert client.post("/api/v1/course-requests", data=again).status_code == 409


def test_request_without_material_and_reject(client, login, session):
    login()
    form = {"subject_name": "운영체제", "professor_name": "김교수"}
    req = client.post("/api/v1/course-requests", data=form).json()
    assert req["has_material"] is False

    make_admin(session)
    assert (
        client.post(f"/api/v1/admin/course-requests/{req['id']}/reject", json={}).status_code == 422
    )
    r = client.post(
        f"/api/v1/admin/course-requests/{req['id']}/reject", json={"reason": "과목명 확인 필요"}
    )
    assert r.json()["status"] == "rejected" and r.json()["reject_reason"] == "과목명 확인 필요"
    # 반려 뒤에는 다시 요청할 수 있다
    assert client.post("/api/v1/course-requests", data=form).status_code == 201


def test_material_versions(client, login, session, course_with_problems):
    cid = course_with_problems["course"].id
    login()
    up = lambda pages, name, title: client.post(  # noqa: E731
        f"/api/v1/courses/{cid}/materials",
        files=_pdf(pages, name),
        data={"kind": "lecture", "title": title},
    )
    v1 = up(LECTURE, "week03.pdf", "3주차 포인터")
    assert v1.status_code == 201 and v1.json()["action"] == "new"
    v1 = v1.json()

    # 옛 판을 근거로 쓰는 문제
    prob = course_with_problems["problems"][0]
    prob.evidence, prob.source_material_id, prob.source_page = LECTURE[1], v1["id"], 2
    session.add(prob)
    session.commit()

    # 같은 내용을 다시 올리면 등록하지 않는다
    dup = up(LECTURE, "week03_copy.pdf", "3주차 포인터 (복사본)")
    assert dup.status_code == 200 and dup.json()["action"] == "duplicate"
    assert dup.json()["id"] == v1["id"]

    # 수정본: 앞에 쪽이 하나 늘었다(파일명에 주차 정보 없음) -> 새 판, 문제 근거는 새 판의 3쪽으로
    revised = ["Pointer review for the midterm exam", *LECTURE]
    v2 = up(revised, "pointer_final.pdf", "포인터 정리")
    assert v2.status_code == 201, v2.text
    v2 = v2.json()
    assert v2["action"] == "updated" and v2["version"] == 2 and v2["relinked_problems"] == 1
    assert (v2["pages_same"], v2["pages_new"], v2["replaced_ids"]) == (2, 1, [v1["id"]])
    session.expire_all()
    p = session.get(Problem, prob.id)
    assert (p.source_material_id, p.source_page) == (v2["id"], 3)
    assert session.get(Material, v1["id"]).replaced_by == v2["id"]

    # 목록에는 최신판만, all_versions면 옛 판까지
    assert [m["id"] for m in client.get(f"/api/v1/courses/{cid}/materials").json()] == [v2["id"]]
    all_v = client.get(f"/api/v1/courses/{cid}/materials", params={"all_versions": True}).json()
    assert len(all_v) == 2

    # 같은 주차라도 내용이 전혀 다른 자료는 별개 자료다 (예: week11.pdf와 week11_2.pdf)
    other = up(
        ["Structures group several variables together", "Unions let members share one memory"],
        "week03_2.pdf",
        "3주차 2",
    )
    assert other.json()["action"] == "new"
    assert len(client.get(f"/api/v1/courses/{cid}/materials").json()) == 2


WEEK_A = ["Arrays store elements of the same type contiguously", "Index starts from zero in C"]
WEEK_B = ["Functions receive copies of arguments by value", "Return statement ends a function"]


def test_big_file_replaces_week_files(client, login, course_with_problems):
    """주차별 파일 두 개 -> 학기 전체 큰 파일 하나(일부 수정)로 다시 올리면 둘 다 대체된다."""
    cid = course_with_problems["course"].id
    login()
    post = lambda pages, name: client.post(  # noqa: E731
        f"/api/v1/courses/{cid}/materials",
        files=_pdf(pages, name),
        data={"kind": "lecture", "title": name},
    ).json()
    a, b = post(WEEK_A, "a.pdf"), post(WEEK_B, "b.pdf")
    big = post(
        [*WEEK_A, WEEK_B[0], "Return statement ends a function and gives back a value"], "all.pdf"
    )
    assert big["action"] == "updated" and sorted(big["replaced_ids"]) == sorted([a["id"], b["id"]])
    assert big["pages_modified"] == 1
    assert [m["id"] for m in client.get(f"/api/v1/courses/{cid}/materials").json()] == [big["id"]]


def test_partial_update_of_big_file(client, login, session, course_with_problems):
    """큰 교안의 일부만 고친 파일은 큰 교안을 대체하지 않고 새 자료로 붙는다. 근거는 최신 쪽으로 옮긴다."""
    cid = course_with_problems["course"].id
    login()
    post = lambda pages, name: client.post(  # noqa: E731
        f"/api/v1/courses/{cid}/materials",
        files=_pdf(pages, name),
        data={"kind": "lecture", "title": name},
    ).json()
    big = post([*WEEK_A, *WEEK_B], "semester.pdf")
    prob = course_with_problems["problems"][0]
    prob.evidence, prob.source_material_id, prob.source_page = WEEK_B[0], big["id"], 3
    session.add(prob)
    session.commit()
    part = post([WEEK_B[0], "Return statement ends a function and returns its value"], "fix.pdf")
    assert part["action"] == "new" and part["replaced_ids"] == [] and part["relinked_problems"] == 1
    session.expire_all()
    p = session.get(Problem, prob.id)
    assert (p.source_material_id, p.source_page) == (part["id"], 1)
    assert len(client.get(f"/api/v1/courses/{cid}/materials").json()) == 2


def test_parse_week():
    from app.features.materials.versioning import parse_week

    assert parse_week("week11_2.pdf") == 11
    assert parse_week("3주차 포인터") == 3
    assert parse_week("W05 slides") == 5
    assert parse_week("중간고사 정리") is None
