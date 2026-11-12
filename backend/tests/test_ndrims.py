"""엔드림스 수강 기록 가져오기, 개설 목록, 강좌 열기 요청 흐름."""

from tests.conftest import make_admin, make_pdf

CUR, PAST = "CM160.20", "CM160.10"
CATALOG = [
    dict(
        year="2026",
        sem_cd=CUR,
        sbj_no="CSC2001",
        sbj_nm="기초프로그래밍",
        dvcls="01",
        emp_no="E1",
        emp_nm="강동현",
        colg_nm="공과대학",
        dpt_nm="컴퓨터·AI학부",
        cpdiv_nm="전공",
    ),
    dict(
        year="2026",
        sem_cd=CUR,
        sbj_no="CSC2001",
        sbj_nm="기초프로그래밍",
        dvcls="02",
        emp_no="E2",
        emp_nm="김교수",
        colg_nm="공과대학",
        dpt_nm="컴퓨터·AI학부",
        cpdiv_nm="전공",
    ),
    dict(
        year="2026",
        sem_cd=CUR,
        sbj_no="BIS2003",
        sbj_nm="인도의철학과문화",
        dvcls="01",
        emp_no="E9",
        emp_nm="이병재",
        colg_nm="불교대학",
        dpt_nm="불교학부",
        cpdiv_nm="전공",
        mid_rate=30,
        fnl_rate=40,
    ),
]
LECTURE = ["Pointers store addresses of other variables in memory", "Arrays and pointer arithmetic"]


def _as(client, login, email, admin=False, session=None):
    client.post("/api/v1/auth/logout")
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    if r.status_code != 200:
        login(email, email.split("@")[0])
    if admin:
        make_admin(session, email)


def test_ndrims_flow(client, login, session, course_with_problems):
    course = course_with_problems[
        "course"
    ]  # 학수번호 없이 이름으로 만든 옛 강좌(기초프로그래밍·강동현)
    _as(client, login, "admin@dgu.ac.kr", admin=True, session=session)
    r = client.post("/api/v1/admin/catalog/import", json={"rows": CATALOG}).json()
    assert (r["added"], r["professors_linked"]) == (
        3,
        1,
    )  # 옛 교수에게 교원번호, 옛 과목에 학수번호

    # 학생: 이번 학기 기초프로그래밍(교수 칸 없음) + 지난 학기 자료구조(성적 기록, 교수명) + 철학
    _as(client, login, "b@dgu.ac.kr")
    recs = [
        dict(
            year="2026",
            sem_cd=CUR,
            sbj_no="CSC2001",
            sbj_nm="기초프로그래밍",
            dvcls="01",
            grade="A+",
        ),
        dict(
            year="2025",
            sem_cd=PAST,
            sbj_no="CSE3001",
            sbj_nm="자료구조",
            dvcls="01",
            emp_nm="이교수",
        ),
        dict(year="2026", sem_cd=CUR, sbj_no="BIS2003", sbj_nm="인도의철학과문화", dvcls="01"),
    ]
    out = client.post("/api/v1/me/ndrims/import", json={"records": recs}).json()
    assert out["current_term"] == "2026 2학기" and out["added"] == 3
    assert [(c["course_id"], c["status"]) for c in out["courses"]] == [(course.id, "current")]
    assert {(w["sbj_no"], w["status"], w["request"]) for w in out["waiting"]} == {
        ("CSE3001", "taken", "none"),
        ("BIS2003", "current", "none"),
    }
    assert client.get(f"/api/v1/courses/{course.id}").status_code == 200
    # 다시 보내도 늘지 않는다
    again = client.post("/api/v1/me/ndrims/import", json={"records": recs}).json()
    assert again["added"] == 0 and again["record_count"] == 3

    # 강좌 찾기: 같은 과목의 두 교수는 따로, 내 강좌는 열림·mine
    s = client.get("/api/v1/catalog/search", params={"year": "2026", "sem_cd": CUR, "q": "CSC2001"})
    items = {i["emp_nm"]: i for i in s.json()["items"]}
    assert items["강동현"]["status"] == "open" and items["강동현"]["mine"]
    assert items["김교수"]["status"] == "none" and not items["김교수"]["mine"]
    f = client.get("/api/v1/catalog/filters", params={"year": "2026", "sem_cd": CUR}).json()
    assert [c["name"] for c in f["colleges"]] == ["공과대학", "불교대학"]

    # 요청: 지난 학기 수업은 내 기록에서, 이번 학기 수업은 개설 목록에서
    wid = next(w["enrollment_id"] for w in out["waiting"] if w["sbj_no"] == "CSE3001")
    me = client.post(f"/api/v1/me/enrollments/{wid}/request").json()
    assert next(w for w in me["waiting"] if w["sbj_no"] == "CSE3001")["request"] == "mine"
    assert client.post(f"/api/v1/me/enrollments/{wid}/request").status_code == 409
    req = client.post(
        "/api/v1/catalog/request",
        json={"year": "2026", "sem_cd": CUR, "sbj_no": "BIS2003", "dvcls": "01"},
    )
    assert req.status_code == 201
    dup = client.post(
        "/api/v1/catalog/request",
        json={"year": "2026", "sem_cd": CUR, "sbj_no": "CSC2001", "dvcls": "01"},
    )
    assert dup.status_code == 409  # 이미 열린 강좌

    # 관리자: 교안 없이는 승인 불가 → 요청자가 교안을 붙이면 승인 → 강좌가 열리고 기록이 이어진다
    mine = client.get("/api/v1/course-requests/mine").json()
    cse = next(m for m in mine if m["subject_code"] == "CSE3001")
    _as(client, login, "admin@dgu.ac.kr")
    assert client.post(f"/api/v1/admin/course-requests/{cse['id']}/approve").status_code == 400
    _as(client, login, "b@dgu.ac.kr")
    files = {"files": ("ds.pdf", make_pdf(LECTURE), "application/pdf")}
    assert client.post(f"/api/v1/course-requests/{cse['id']}/files", files=files).status_code == 200
    _as(client, login, "admin@dgu.ac.kr")
    ok = client.post(f"/api/v1/admin/course-requests/{cse['id']}/approve").json()
    assert ok["status"] == "approved"
    _as(client, login, "b@dgu.ac.kr")
    mine = client.get("/api/v1/me/courses").json()
    ds = next(c for c in mine["courses"] if c["sbj_no"] == "CSE3001")
    assert ds["status"] == "taken" and ds["professor_name"] == "이교수"
    assert client.get(f"/api/v1/courses/{ds['course_id']}").status_code == 200

    # 수강 기록이 없는 다른 학생은 못 들어간다
    _as(client, login, "c@dgu.ac.kr")
    assert client.get(f"/api/v1/courses/{ds['course_id']}").status_code == 403


def test_same_subject_other_professor_is_locked(client, login, session, course_with_problems):
    course = course_with_problems["course"]
    _as(client, login, "admin@dgu.ac.kr", admin=True, session=session)
    client.post("/api/v1/admin/catalog/import", json={"rows": CATALOG})
    # 김교수 강좌를 관리자가 열어 둔다(요청 + 교안)
    _as(client, login, "d@dgu.ac.kr")
    client.post(
        "/api/v1/catalog/request",
        json={"year": "2026", "sem_cd": CUR, "sbj_no": "CSC2001", "dvcls": "02"},
    )
    rid = client.get("/api/v1/course-requests/mine").json()[0]["id"]
    client.post(
        f"/api/v1/course-requests/{rid}/files",
        files={"files": ("k.pdf", make_pdf(LECTURE), "application/pdf")},
    )
    _as(client, login, "admin@dgu.ac.kr")
    kim = client.post(f"/api/v1/admin/course-requests/{rid}/approve").json()["course_id"]
    # 강동현 교수님 수업만 들은 학생은 김교수 강좌에 못 들어간다
    _as(client, login, "b@dgu.ac.kr")
    rec = dict(
        year="2025",
        sem_cd=PAST,
        sbj_no="CSC2001",
        sbj_nm="기초프로그래밍",
        dvcls="01",
        emp_nm="강동현",
    )
    client.post("/api/v1/me/ndrims/import", json={"records": [rec]})
    assert client.get(f"/api/v1/courses/{course.id}").status_code == 200
    assert client.get(f"/api/v1/courses/{kim}").status_code == 403
    lst = client.get(f"/api/v1/subjects/{course.subject_id}/courses").json()
    assert {c["professor_name"]: c["accessible"] for c in lst} == {"강동현": True, "김교수": False}


def test_catalog_import_admin_only(client, login):
    login()
    assert client.post("/api/v1/admin/catalog/import", json={"rows": CATALOG}).status_code == 403
