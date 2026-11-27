"""팀 프로젝트 라벨: 강의계획서 판정 + 후기 응답, (강좌, 학기) 단위."""

import pytest
from sqlmodel import select

from app.features.team_project.service import (
    LABEL_LIKELY_NO,
    LABEL_NO,
    LABEL_UNKNOWN,
    LABEL_YES,
    TermLabel,
    classify_syllabus,
    course_history,
    decide,
    differs,
    summarize,
    term_labels,
)
from app.models import (
    CatalogOffering,
    Course,
    CourseReview,
    Enrollment,
    Professor,
    Subject,
    TeamProjectOverride,
    TeamProjectReport,
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
        "개인 프로젝트 30%",  # 프로젝트만으로는 팀플이 아니다
        "기말 프로젝트 보고서 제출",
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
    # 운영진 > 수강생(2명 이상·과반) > 계획서
    assert decide("yes", 0, 5, override=True) == (LABEL_YES, "admin")
    assert decide("yes", 0, 3) == (LABEL_NO, "students")  # 계획서와 실제가 다르면 실제
    assert decide("no", 2, 0) == (LABEL_YES, "students")
    assert decide("yes", 0, 1) == (LABEL_YES, "syllabus")  # 한 명은 부족
    assert decide("yes", 1, 1) == (LABEL_YES, "syllabus")  # 동률이면 계획서
    assert decide("not_mentioned", 2, 1) == (LABEL_YES, "students")
    assert decide("not_mentioned", 0, 0) == (LABEL_LIKELY_NO, "syllabus")
    assert decide(None, 0, 2) == (LABEL_NO, "students")
    assert decide(None, 1, 0) == (LABEL_UNKNOWN, None)
    assert decide(None, 0, 0) == (LABEL_UNKNOWN, None)


def test_differs_from_syllabus():
    assert differs("yes", LABEL_NO, "students")
    assert differs("not_mentioned", LABEL_YES, "admin")
    assert differs("no", LABEL_YES, "students")
    assert not differs("yes", LABEL_YES, "students")
    assert not differs("yes", LABEL_YES, "syllabus")
    assert not differs(None, LABEL_YES, "students")  # 계획서가 없으면 비교하지 않음


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


def test_students_override_syllabus(session, two_profs):
    kim = two_profs["kim"]
    _review(session, kim, "2025", FALL, True, n=2)
    _review(session, kim, "2025", FALL, False)
    _review(session, kim, "2026", FALL, True, n=3)  # 계획서엔 '조별 과제 없음'
    labels = {t.term: t for t in term_labels(session, kim)}
    assert (labels["2025 2학기"].label, labels["2025 2학기"].source) == ("yes", "students")
    assert (labels["2025 2학기"].yes_votes, labels["2025 2학기"].no_votes) == (2, 1)
    t = labels["2026 2학기"]
    assert (t.label, t.source, t.syllabus, t.differs_from_syllabus) == (
        "yes",
        "students",
        "no",
        True,
    )
    assert t.evidence == "조별 과제 없음"  # 계획서 문장은 비교용으로 남긴다


def test_report_and_review_count_once_per_student(session, two_profs):
    kang = two_profs["kang"]
    _review(session, kang, "2026", FALL, True)  # 후기에서 '있었다'
    u = session.exec(select(CourseReview)).one().user_id
    session.add(
        TeamProjectReport(
            user_id=u, course_id=kang.id, year="2026", sem_cd=FALL, team_project=False
        )
    )
    session.commit()  # 같은 학생이 제보 버튼으로 '없었다' → 제보가 그 학생의 한 표
    t = term_labels(session, kang)[0]
    assert (t.yes_votes, t.no_votes) == (0, 1) and t.source == "syllabus"


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
                    "text": "평가: 팀 프로젝트 20%",
                },
                {"year": "2026", "sem_cd": FALL, "sbj_no": "CSC9999", "dvcls": "01", "text": "x"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"checked": 1, "missing": 1, "yes": 1, "no": 0, "not_mentioned": 0}
    o = session.exec(select(CatalogOffering).where(CatalogOffering.dvcls == "03")).one()
    assert o.team_project == "yes" and o.syllabus_checked_at is not None
    assert o.team_evidence == "평가: 팀 프로젝트 20%"

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
    body = client.get(f"/api/v1/courses/{kim.id}/team-project").json()
    t = {t["term"]: t for t in body["terms"]}["2025 2학기"]
    assert (t["label"], t["yes_votes"]) == ("unknown", 1)  # 한 명은 아직 라벨이 안 됨
    assert body["my_terms"] == [
        {"year": "2025", "sem_cd": FALL, "term": "2025 2학기", "my_answer": True}
    ]


def _student_in(client, login, session, course, email, year="2026", sem=FALL):
    client.post("/api/v1/auth/logout")
    login(email, "학생")
    me = client.get("/api/v1/auth/me").json()
    session.add(
        Enrollment(
            user_id=me["id"],
            year=year,
            sem_cd=sem,
            sbj_no="CSC2001",
            sbj_nm="x",
            dvcls="01",
            course_id=course.id,
        )
    )
    session.commit()


def test_report_button_flow(client, login, session, two_profs):
    kang = two_profs["kang"]  # 2026-2 계획서: 팀 프로젝트 30%
    url = f"/api/v1/courses/{kang.id}/team-project/report"
    login("nope@dgu.ac.kr", "미수강")
    assert (
        client.put(url, json={"year": "2026", "sem_cd": FALL, "team_project": False}).status_code
        == 403
    )

    for email in ("s1@dgu.ac.kr", "s2@dgu.ac.kr"):
        _student_in(client, login, session, kang, email)
        r = client.put(url, json={"year": "2026", "sem_cd": FALL, "team_project": False})
        assert r.status_code == 200, r.text
    latest = r.json()["latest"]
    assert (latest["label"], latest["source"], latest["differs_from_syllabus"]) == (
        "no",
        "students",
        True,
    )
    assert r.json()["my_terms"][0]["my_answer"] is False

    r = client.put(url, json={"year": "2026", "sem_cd": FALL, "team_project": True})  # 마음 바꿈
    assert (r.json()["latest"]["yes_votes"], r.json()["latest"]["no_votes"]) == (1, 1)
    assert r.json()["latest"]["source"] == "syllabus"  # 동률 → 계획서
    r = client.put(url, json={"year": "2026", "sem_cd": FALL, "team_project": None})  # 응답 지우기
    assert r.json()["latest"]["no_votes"] == 1 and r.json()["my_terms"][0]["my_answer"] is None
    assert len(session.exec(select(TeamProjectReport)).all()) == 1


def test_admin_override(client, login, session, two_profs):
    kang = two_profs["kang"]
    url = f"/api/v1/admin/courses/{kang.id}/team-project"
    login("s@dgu.ac.kr", "학생")
    assert (
        client.put(url, json={"year": "2026", "sem_cd": FALL, "team_project": False}).status_code
        == 403
    )
    client.post("/api/v1/auth/logout")
    _setup_api(client, login, session, two_profs)
    r = client.put(
        url,
        json={
            "year": "2026",
            "sem_cd": FALL,
            "team_project": False,
            "note": "  수강생 확인: 개인 과제로 바뀜 ",
        },
    )
    latest = r.json()["latest"]
    assert (latest["label"], latest["source"], latest["note"]) == (
        "no",
        "admin",
        "수강생 확인: 개인 과제로 바뀜",
    )
    assert latest["differs_from_syllabus"] is True
    # 계획서가 없는 학기도 지정할 수 있다
    r = client.put(url, json={"year": "2025", "sem_cd": FALL, "team_project": True})
    assert {t["term"]: t["label"] for t in r.json()["terms"]}["2025 2학기"] == "yes"
    r = client.put(url, json={"year": "2026", "sem_cd": FALL, "team_project": None})  # 지정 해제
    assert r.json()["latest"]["source"] == "syllabus"


# ---------- 최근 3년 ----------


def _offer(session, year, sem, dvcls, emp_no, emp_nm, tp, ev=None):
    session.add(
        CatalogOffering(
            year=year,
            sem_cd=sem,
            sbj_no="CSC2001",
            sbj_nm="기초프로그래밍",
            dvcls=dvcls,
            emp_no=emp_no,
            emp_nm=emp_nm,
            team_project=tp,
            team_evidence=ev,
        )
    )


def test_summary_rules():
    def t(label):
        return TermLabel(year="2026", sem_cd=FALL, term="x", label=label, source=None)

    assert summarize([t("yes"), t("yes")]) == "yes"
    assert summarize([t("yes"), t("no")]) == "mixed"
    assert summarize([t("yes"), t("likely_no")]) == "mixed"
    assert summarize([t("no"), t("likely_no")]) == "no"
    assert summarize([t("likely_no"), t("unknown")]) == "likely_no"
    assert summarize([t("unknown")]) == summarize([]) == "unknown"


def test_history_keeps_last_three_years(session, two_profs):
    kang = two_profs["kang"]
    _offer(session, "2025", FALL, "01", "E1", "강동현", "yes", "조별 발표")
    _offer(session, "2024", FALL, "01", "E1", "강동현", "not_mentioned")
    _offer(session, "2023", FALL, "01", "E1", "강동현", "no", "팀플 없음")  # 3년 밖
    session.commit()
    h = course_history(session, kang)
    assert (h.from_year, h.to_year) == ("2024", "2026")
    assert [t.term for t in h.terms] == ["2026 2학기", "2026 1학기", "2025 2학기", "2024 2학기"]
    assert h.summary == "mixed"  # 2026-1 없음, 나머지 있음/언급 없음
    assert course_history(session, kang, anchor="2024").terms[-1].term == "2023 2학기"


def test_catalog_search_shows_history_before_registration(client, login, session, two_profs):
    """다음 학기 개설 목록은 계획서가 아직 없어도, 같은 교수의 지난 3년 기록을 보인다."""
    _offer(session, "2027", SPRING, "01", "E2", "김교수", None)  # 아직 판정 전
    _offer(session, "2025", FALL, "02", "E2", "김교수", "no", "조별 과제 없음")
    _offer(session, "2027", SPRING, "05", "E9", "새교수", None)  # 사이트에 강좌 없는 교수
    _offer(session, "2026", FALL, "05", "E9", "새교수", "yes", "팀 프로젝트 40%")
    session.commit()
    _setup_api(client, login, session, two_profs)
    items = client.get(
        "/api/v1/catalog/search", params={"year": "2027", "sem_cd": SPRING, "q": "CSC2001"}
    ).json()["items"]
    by = {i["emp_nm"]: i for i in items}
    assert by["김교수"]["team_project"]["label"] == "unknown"
    h = by["김교수"]["team_history"]
    assert (h["summary"], h["from_year"], h["to_year"]) == ("no", "2025", "2027")
    assert [t["term"] for t in h["terms"]] == ["2026 2학기", "2025 2학기"]
    assert by["새교수"]["team_history"]["summary"] == "yes"
    assert by["새교수"]["course_id"] is None


def test_course_endpoints_include_history(client, login, session, two_profs):
    _setup_api(client, login, session, two_profs)
    kang = two_profs["kang"]
    c = client.get(f"/api/v1/courses/{kang.id}").json()
    assert c["team_history"]["summary"] == "mixed" and len(c["team_history"]["terms"]) == 2
    t = client.get(f"/api/v1/courses/{kang.id}/team-project").json()
    assert t["history"]["to_year"] == "2026"


def test_site_codes_for_ndrims_bookmarklet(client, session, two_profs):
    session.add(Subject(name="코드 없음"))
    session.commit()
    r = client.get("/api/v1/catalog/site-codes", headers={"Origin": "https://ndrims.dongguk.edu"})
    assert r.status_code == 200 and r.json() == {"codes": ["CSC2001"]}
    assert r.headers["access-control-allow-origin"] == "https://ndrims.dongguk.edu"
    other = client.get("/api/v1/catalog/site-codes", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


# ---------- 강좌 찾기: 묶음 조회 ----------


def _many_courses(session, n: int, code: str = "CSC3000", name: str = "자료구조"):
    """한 과목에 교수 n명. 교수마다 3년 밖 학기까지 개설 목록, 일부는 응답·제보·운영진 지정,
    일부는 교원번호 없이 이름만, 일부는 사이트 강좌 없음."""
    subj = Subject(name=name, code=code)
    session.add(subj)
    session.flush()
    tps = ["yes", "no", "not_mentioned", None]
    for i in range(n):
        emp_no = None if i % 5 == 3 else f"P{code}{i}"
        prof = Professor(name=f"교수{i}", emp_no=emp_no)
        session.add(prof)
        session.flush()
        course = None
        if i % 4 != 2:  # 넷 중 하나는 사이트에 강좌가 없다
            course = Course(subject_id=subj.id, professor_id=prof.id)
            session.add(course)
            session.flush()
        for y in ("2026", "2025", "2024", "2023"):  # 2023은 3년 밖
            session.add(
                CatalogOffering(
                    year=y,
                    sem_cd=FALL,
                    sbj_no=code,
                    sbj_nm=name,
                    dvcls=f"{i:02d}",
                    emp_no=emp_no,
                    emp_nm=prof.name,
                    team_project=tps[(i + int(y)) % 4],
                    team_evidence="팀 프로젝트 30%" if tps[(i + int(y)) % 4] == "yes" else None,
                )
            )
        if course and i % 3 == 0:
            _review(session, course, "2025", FALL, True, n=2)
        if course and i % 3 == 1:
            u = User(email=f"rep{code}{i}@dgu.ac.kr", name="r", password_hash="x")
            session.add(u)
            session.flush()
            session.add(
                TeamProjectReport(
                    user_id=u.id, course_id=course.id, year="2026", sem_cd=FALL, team_project=False
                )
            )
        if course and i % 7 == 0:
            session.add(
                TeamProjectOverride(
                    course_id=course.id, year="2024", sem_cd=FALL, team_project=True, note="확인"
                )
            )
    session.commit()


def test_catalog_batch_matches_per_group(session, two_profs):
    """묶음 계산 결과가 그룹마다 따로 계산한 것과 같다."""
    from app.features.catalog.router import _courses_for
    from app.features.enrollments.service import find_course, find_subject
    from app.features.team_project.service import (
        catalog_labels,
        group_history,
        offering_group_label,
    )

    _many_courses(session, 12)
    session.add(Subject(name="이름만과목"))  # 학수번호 없는 옛 과목 → 이름으로 찾기
    session.add(
        CatalogOffering(
            year="2026",
            sem_cd=FALL,
            sbj_no="ZZZ9999",
            sbj_nm="이름만과목",
            dvcls="01",
            emp_nm="누구",
        )
    )
    session.commit()
    groups: dict[tuple, list[CatalogOffering]] = {}
    for o in session.exec(select(CatalogOffering).where(CatalogOffering.year == "2026")).all():
        groups.setdefault((o.sbj_no, o.emp_no or o.emp_nm), []).append(o)
    gs = list(groups.values())
    firsts = [g[0] for g in gs]
    batch_courses = _courses_for(session, firsts)
    for o, c in zip(firsts, batch_courses, strict=True):
        sub = find_subject(session, o.sbj_no, o.sbj_nm)
        assert c == (find_course(session, sub, o.emp_no, o.emp_nm) if sub else None)
    batch = catalog_labels(
        session, [(g, c.id if c else None) for g, c in zip(gs, batch_courses, strict=True)]
    )
    seen_sources = set()
    for g, c, (lbl, hist) in zip(gs, batch_courses, batch, strict=True):
        cid = c.id if c else None
        assert lbl == offering_group_label(session, g, cid)
        assert hist == group_history(session, g, cid)
        seen_sources |= {t.source for t in hist.terms}
    assert {
        "admin",
        "students",
        "syllabus",
    } <= seen_sources  # 세 경우가 모두 들어간 데이터로 비교했다


def test_catalog_search_query_count_is_constant(client, login, session, two_profs):
    """강좌 찾기 한 번의 조회 수가 결과 그룹 수와 상관없다."""
    from sqlalchemy import event

    _many_courses(session, 2, code="CSC3000", name="자료구조")
    _many_courses(session, 30, code="CSC4000", name="운영체제")
    login("s@dgu.ac.kr", "학생")
    engine = session.get_bind()
    count = {"n": 0}

    def on_exec(*_):
        count["n"] += 1

    def run(q):
        count["n"] = 0
        event.listen(engine, "before_cursor_execute", on_exec)
        try:
            r = client.get(
                "/api/v1/catalog/search", params={"year": "2026", "sem_cd": FALL, "q": q}
            )
        finally:
            event.remove(engine, "before_cursor_execute", on_exec)
        assert r.status_code == 200
        return len(r.json()["items"]), count["n"]

    few_items, few = run("CSC3000")
    many_items, many = run("CSC4000")
    assert (few_items, many_items) == (2, 30)
    assert few == many, (few, many)
    assert many <= 12, many
