"""스터디 목록에서 나와 약점이 겹치는 스터디를 위로 올리고 겹치는 개념을 보여 준다."""

from app.models import Attempt, StudyApplication, StudyGroup, User

GROUP = dict(
    description="함께 복습하는 스터디입니다.",
    capacity=4,
    mode="offline",
    schedule="수요일",
    location="도서관",
)


def wrong_twice(session, user_id, problems):
    for p in problems:
        session.add(Attempt(user_id=user_id, problem_id=p.id, chosen_index=0, correct=False))


def test_recommends_groups_with_shared_weakness(
    client, login, enroll, course_with_problems, session
):
    c = course_with_problems["course"]
    p_a, p_b, p_ab = course_with_problems["problems"]
    login()
    enroll(c.subject_id)
    me = client.get("/api/v1/auth/me").json()["id"]
    wrong_twice(session, me, [p_a, p_ab])  # 내 약점: A (B는 1문제뿐이라 아직 약점 아님)

    a_weak, b_weak, member = (
        User(email=f"{n}@dgu.ac.kr", name=n, password_hash="x") for n in "xyz"
    )
    nobody = User(email="n@dgu.ac.kr", name="n", password_hash="x")
    session.add_all([a_weak, b_weak, member, nobody])
    session.flush()
    wrong_twice(session, b_weak.id, [p_b, p_ab])  # B 약점
    wrong_twice(session, member.id, [p_a, p_ab])  # A 약점, 참여자로만 들어간 스터디

    def group(title, owner):
        g = StudyGroup(subject_id=c.subject_id, owner_id=owner.id, title=title, **GROUP)
        session.add(g)
        session.flush()
        return g

    group("B 스터디", b_weak)
    via_member = group("참여자 A 스터디", nobody)
    session.add(StudyApplication(group_id=via_member.id, user_id=member.id, status="approved"))
    group("약점 없는 스터디", nobody)
    session.commit()

    url = f"/api/v1/subjects/{c.subject_id}/study-groups"
    data = client.get(url).json()
    assert data["my_weak"] == ["A"]
    first, *rest = data["items"]
    assert first["title"] == "참여자 A 스터디" and first["shared_weak"] == ["A"]
    assert all(g["shared_weak"] == [] for g in rest)  # B만 약한 스터디는 나와 겹치지 않는다
    # 다른 사람의 점수나 누가 약한지는 응답에 없다
    assert "mastery" not in str(data) and "x@dgu" not in str(data)

    # 최신순으로 바꾸면 추천 순서를 쓰지 않는다
    recent = client.get(url, params={"sort": "recent"}).json()["items"]
    assert recent[0]["title"] == "약점 없는 스터디"


def test_pending_applicant_weakness_not_counted(
    client, login, enroll, course_with_problems, session
):
    c = course_with_problems["course"]
    p_a, _, p_ab = course_with_problems["problems"]
    login()
    enroll(c.subject_id)
    me = client.get("/api/v1/auth/me").json()["id"]
    wrong_twice(session, me, [p_a, p_ab])
    owner, waiting = (User(email=f"{n}@dgu.ac.kr", name=n, password_hash="x") for n in "op")
    session.add_all([owner, waiting])
    session.flush()
    wrong_twice(session, waiting.id, [p_a, p_ab])
    g = StudyGroup(subject_id=c.subject_id, owner_id=owner.id, title="대기 중", **GROUP)
    session.add(g)
    session.flush()
    session.add(StudyApplication(group_id=g.id, user_id=waiting.id, status="pending"))
    session.commit()
    [item] = client.get(f"/api/v1/subjects/{c.subject_id}/study-groups").json()["items"]
    assert item["shared_weak"] == []
