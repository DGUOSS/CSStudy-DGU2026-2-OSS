"""팀 프로젝트 라벨: 강의계획서 판정 + 후기 응답, (강좌, 학기) 단위."""

import pytest
from sqlmodel import select

from app.features.team_project.service import (
    LABEL_LIKELY_NO,
    LABEL_NO,
    LABEL_UNKNOWN,
    LABEL_YES,
    classify_syllabus,
    decide,
    term_labels,
)
from app.models import (
    CatalogOffering,
    Course,
    CourseReview,
    Enrollment,
    Professor,
    Subject,
    User,
)
from tests.conftest import make_admin

FALL, SPRING = "CM160.20", "CM160.10"


# ---------- 강의계획서 판정 ----------


@pytest.mark.parametrize(
    "text",
    [
        "평가방법\n중간 30% / 기말 30% / 팀 프로젝트 30% / 출석 10%",
        "학기 말에 조별 발표가 있습니다.",
        "4인 1팀으로 팀프로젝트를 수행한다",
        "그룹 과제: 3~4명이 웹 서비스를 만든다",
        "Final team project (40%) and presentation",
        "팀플 20%",
    ],
)
def test_syllabus_yes(text):
    label, evidence = classify_syllabus(text)
    assert label == "yes" and evidence


@pytest.mark.parametrize(
    "text",
    [
        "팀 프로젝트: 없음",
        "조별 과제는 하지 않는다. 개인 과제 3회.",
        "팀 프로젝트 0%",
        "조별 과제 없이 개인 과제로만 평가한다",
        "No team project; individual homework only.",
    ],
)
def test_syllabus_explicit_no(text):
    label, evidence = classify_syllabus(text)
    assert label == "no" and evidence


@pytest.mark.parametrize(
    "text",
    [
        "중간 40% 기말 40% 과제 20%",
        "중요 개념을 강조 과제로 정리한다",  # '강조 과제'의 '조 과제'는 조별이 아님
        "스팀 엔진 원리",
        "",
    ],
)
def test_syllabus_not_mentioned(text):
    assert classify_syllabus(text) == ("not_mentioned", None)


def test_yes_wins_over_a_negated_mention():
    text = "중간고사 없음.\n팀 프로젝트 1회(30%)"
    assert classify_syllabus(text)[0] == "yes"
    text = "개인 과제는 없고 팀 프로젝트로 대체"  # 부정어가 팀 표현보다 앞이면 영향 없음
    assert classify_syllabus(text)[0] == "yes"


def test_decide_rules():
    assert decide("yes", "e", 0, 3) == (LABEL_YES, "syllabus")  # 계획서가 우선
    assert decide("no", "e", 5, 0) == (LABEL_NO, "syllabus")
    assert decide("not_mentioned", None, 2, 1) == (LABEL_YES, "reviews")
    assert decide("not_mentioned", None, 1, 1) == (LABEL_LIKELY_NO, "syllabus")
    assert decide(None, None, 0, 2) == (LABEL_NO, "reviews")
    assert decide(None, None, 0, 0) == (LABEL_UNKNOWN, None)


# ---------- (강좌, 학기) 단위 ----------


@pytest.fixture
def two_profs(session):
    """같은 과목(CSC2001), 교수 둘. 학기·교수마다 팀플 여부가 다르다."""
    subj = Subject(name="기초프로그래밍", code="CSC2001")
    kang, kim = Professor(name="강동현", emp_no="E1"), Professor(name="김교수", emp_no="E2")
    session.add_all([subj, kang, kim])
    session.flush()
    c_kang = Course(subject_id=subj.id, professor_id=kang.id)
    c_kim = Course(subject_id=subj.id, professor_id=kim.id)
    session.add_all([c_kang, c_kim])
    rows = [
        ("2026", FALL, "01", "E1", "강동현", "yes", "팀 프로젝트 30%"),
        ("2026", FALL, "03", "E1", "강동현", "not_mentioned", None),
        ("2026", SPRING, "01", "E1", "강동현", "no", "팀 프로젝트 없음"),
        ("2026", FALL, "02", "E2", "김교수", "no", "조별 과제 없음"),
    ]
    for y, s, d, eno, enm, tp, ev in rows:
        session.add(
            CatalogOffering(
                year=y,
                sem_cd=s,
                sbj_no="CSC2001",
                sbj_nm="기초프로그래밍",
                dvcls=d,
                emp_no=eno,
                emp_nm=enm,
                team_project=tp,
                team_evidence=ev,
            )
        )
    session.commit()
    return {"kang": c_kang, "kim": c_kim}


def test_labels_differ_by_term_and_professor(session, two_profs):
    kang = term_labels(session, two_profs["kang"])
    assert [(t.term, t.label, t.source) for t in kang] == [
        ("2026 2학기", "yes", "syllabus"),  # 분반 하나라도 있으면 있음
        ("2026 1학기", "no", "syllabus"),
    ]
    assert kang[0].dvcls == ["01", "03"] and kang[0].evidence == "팀 프로젝트 30%"
    kim = term_labels(session, two_profs["kim"])
    assert [(t.term, t.label) for t in kim] == [("2026 2학기", "no")]


def _review(session, course, year, sem, team, n=1):
    for i in range(n):
        u = User(email=f"r{course.id}{year}{sem}{team}{i}@dgu.ac.kr", name="r", password_hash="x")
        session.add(u)
        session.flush()
        e = Enrollment(user_id=u.id, year=year, sem_cd=sem, sbj_no="CSC2001", sbj_nm="x")
        session.add(e)
        session.flush()
        session.add(
            CourseReview(
                user_id=u.id,
                course_id=course.id,
                enrollment_id=e.id,
                year=year,
                sem_cd=sem,
                recommendation=3,
                difficulty=3,
                workload=3,
                content="후기 내용입니다 열 글자",
                team_project=team,
            )
        )
    session.commit()


def test_reviews_fill_terms_without_syllabus(session, two_profs):
    kim = two_profs["kim"]
    _review(session, kim, "2025", FALL, True, n=2)
    _review(session, kim, "2025", FALL, False)
    _review(session, kim, "2026", FALL, True, n=3)  # 계획서(없음)가 있는 학기는 계획서를 따른다
    labels = {t.term: t for t in term_labels(session, kim)}
    assert (labels["2025 2학기"].label, labels["2025 2학기"].source) == ("yes", "reviews")
    assert (labels["2025 2학기"].yes_votes, labels["2025 2학기"].no_votes) == (2, 1)
    assert labels["2026 2학기"].label == "no" and labels["2026 2학기"].yes_votes == 3


# ---------- API ----------


def _setup_api(client, login, session, two_profs):
    login("admin@dgu.ac.kr", "관리자")
    make_admin(session, "admin@dgu.ac.kr")
    return two_profs["kang"]


def test_admin_syllabus_import_and_course_endpoint(client, login, session, two_profs):
    kang = _setup_api(client, login, session, two_profs)
    r = client.post(
        "/api/v1/admin/catalog/syllabi",
        json={
            "rows": [
                {
                    "year": "2026",
                    "sem_cd": FALL,
                    "sbj_no": "csc2001",
                    "dvcls": "03",
                    "text": "평가: 조별 발표 20%",
                },
                {"year": "2026", "sem_cd": FALL, "sbj_no": "CSC9999", "dvcls": "01", "text": "x"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"checked": 1, "missing": 1, "yes": 1, "no": 0, "not_mentioned": 0}
    o = session.exec(select(CatalogOffering).where(CatalogOffering.dvcls == "03")).one()
    assert o.team_project == "yes" and o.syllabus_checked_at is not None

    body = client.get(f"/api/v1/courses/{kang.id}/team-project").json()
    assert body["latest"]["label"] == "yes" and len(body["terms"]) == 2
    course = client.get(f"/api/v1/courses/{kang.id}").json()
    assert course["team_project"]["label"] == "yes"


def test_syllabus_import_is_admin_only(client, login, session, two_profs):
    login("s@dgu.ac.kr", "학생")
    r = client.post("/api/v1/admin/catalog/syllabi", json={"rows": []})
    assert r.status_code == 403


def test_catalog_reimport_keeps_labels(client, login, session, two_profs):
    _setup_api(client, login, session, two_profs)
    row = dict(
        year="2026",
        sem_cd=FALL,
        sbj_no="CSC2001",
        sbj_nm="기초프로그래밍",
        dvcls="01",
        emp_no="E1",
        emp_nm="강동현",
    )
    assert client.post("/api/v1/admin/catalog/import", json={"rows": [row]}).status_code == 200
    session.expire_all()
    o = session.exec(
        select(CatalogOffering).where(CatalogOffering.dvcls == "01", CatalogOffering.sem_cd == FALL)
    ).one()
    assert o.team_project == "yes"


def test_catalog_search_shows_label(client, login, session, two_profs):
    _setup_api(client, login, session, two_profs)
    items = client.get(
        "/api/v1/catalog/search", params={"year": "2026", "sem_cd": FALL, "q": "CSC2001"}
    ).json()["items"]
    by_prof = {i["emp_nm"]: i["team_project"]["label"] for i in items}
    assert by_prof == {"강동현": "yes", "김교수": "no"}


def test_review_records_team_answer(client, login, session, two_profs):
    kim = two_profs["kim"]
    login("s@dgu.ac.kr", "학생")
    me = client.get("/api/v1/auth/me").json()
    e = Enrollment(
        user_id=me["id"],
        year="2025",
        sem_cd=FALL,
        sbj_no="CSC2001",
        sbj_nm="x",
        dvcls="02",
        course_id=kim.id,
    )
    session.add(e)
    session.commit()
    r = client.post(
        f"/api/v1/courses/{kim.id}/reviews",
        json={
            "enrollment_id": e.id,
            "recommendation": 4,
            "difficulty": 3,
            "workload": 3,
            "content": "팀 프로젝트가 꽤 컸어요 열 글자",
            "team_project": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["team_project"] is True
    terms = client.get(f"/api/v1/courses/{kim.id}/team-project").json()["terms"]
    assert {t["term"]: t["label"] for t in terms}["2025 2학기"] == "yes"
