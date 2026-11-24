from app.features.mastery import bkt


def test_problem_hides_answer_and_prefers_unseen_concepts(
    client, login, course_with_problems, enroll
):
    login()
    enroll(course_with_problems["course"].subject_id)
    ch = course_with_problems["chapter"].id
    problems = client.get(f"/api/v1/chapters/{ch}/problems?count=2").json()
    assert all("answer_index" not in p for p in problems)
    # 두 문제만으로 개념 A, B가 모두 나와야 한다
    names = {c["name"] for p in problems for c in p["concepts"]}
    assert names == {"A", "B"}


def test_attempt_updates_mastery(client, login, course_with_problems, enroll):
    login()
    enroll(course_with_problems["course"].subject_id)
    p_a, _, p_ab = course_with_problems["problems"]

    r = client.post(f"/api/v1/problems/{p_a.id}/attempts", json={"chosen_index": 1}).json()
    assert r["correct"] is True and r["answer_index"] == 1
    [change] = r["mastery"]
    assert change["name"] == "A" and change["after"] > change["before"]

    r = client.post(f"/api/v1/problems/{p_ab.id}/attempts", json={"chosen_index": 0}).json()
    assert r["correct"] is False
    assert {c["name"] for c in r["mastery"]} == {"A", "B"}
    assert all(c["after"] < c["before"] for c in r["mastery"])

    cid = course_with_problems["course"].id
    [chapter] = client.get(f"/api/v1/courses/{cid}/mastery").json()
    by_name = {c["name"]: c for c in chapter["concepts"]}
    assert by_name["A"]["attempts"] == 2 and by_name["A"]["correct"] == 1
    assert by_name["B"]["attempts"] == 1


def test_attempt_validation(client, login, course_with_problems, enroll):
    login()
    enroll(course_with_problems["course"].subject_id)
    pid = course_with_problems["problems"][0].id
    assert (
        client.post(f"/api/v1/problems/{pid}/attempts", json={"chosen_index": 9}).status_code == 422
    )
    assert client.post("/api/v1/problems/999/attempts", json={"chosen_index": 0}).status_code == 404


def test_chapters_list(client, login, course_with_problems, enroll):
    login()
    enroll(course_with_problems["course"].subject_id)
    cid = course_with_problems["course"].id
    [ch] = client.get(f"/api/v1/courses/{cid}/chapters").json()
    assert ch["concepts"] == ["A", "B"] and ch["problem_count"] == 3


def test_bkt_trace_direction():
    assert bkt.trace([True, True, True]) > bkt.trace([True]) > bkt.DEFAULT_PARAMS.prior
    assert bkt.trace([False, False]) < bkt.trace([True, True])


def test_bkt_uses_default_until_enough_data():
    assert bkt.params_for(1, {"u": [True] * 5}) == bkt.DEFAULT_PARAMS


def test_pybkt_fit_returns_sane_params():
    # 앞부분은 틀리다가 뒤에서 맞히는 학생들: 배울 확률이 0보다 커야 한다
    seqs = {str(u): [False] * (u % 3 + 1) + [True] * 5 for u in range(12)}
    params = bkt.fit_params(seqs)
    assert 0.01 <= params.learn <= 0.5
    assert 0.05 <= params.guess <= 0.4


def test_bkt_default_rises_gradually():
    """정답 몇 개로 바로 '다 안다'가 되지 않는다(예전엔 3개 연속 정답이면 96%)."""
    rises = [bkt.trace([True] * n) for n in range(1, 7)]
    assert rises[0] < 0.3 and rises[2] < 0.75 and rises[5] > 0.95
    assert bkt.trace([True, True, False, True, True]) < 0.7  # 중간 오답이 반영된다


def test_resolving_same_problem_does_not_raise_mastery(client, login, course_with_problems, enroll):
    login()
    enroll(course_with_problems["course"].subject_id)
    p_a = course_with_problems["problems"][0]
    cid = course_with_problems["course"].id
    first = client.post(f"/api/v1/problems/{p_a.id}/attempts", json={"chosen_index": 1}).json()
    again = client.post(f"/api/v1/problems/{p_a.id}/attempts", json={"chosen_index": 1}).json()
    assert again["mastery"][0]["after"] == first["mastery"][0]["after"]
    [chapter] = client.get(f"/api/v1/courses/{cid}/mastery").json()
    a = next(c for c in chapter["concepts"] if c["name"] == "A")
    assert a["attempts"] == 1


def test_wrong_answer_shows_visible_misconception(
    client, login, course_with_problems, enroll, session
):
    """문제 풀이에서 틀리면 고른 보기에 붙여 둔 오개념을 보여 준다(숨긴 것·근거 없는 AI 추정은 빼고)."""
    from app.models import Misconception

    login()
    enroll(course_with_problems["course"].subject_id)
    p_a, p_b, _ = course_with_problems["problems"]  # 정답은 1번 보기(index 1)
    session.add_all(
        [
            Misconception(
                problem_id=p_a.id,
                wrong_choice_index=0,
                label="주소와 값 혼동",
                hypothesis="h",
                explanation="e",
                status="approved",
            ),
            Misconception(
                problem_id=p_b.id,
                wrong_choice_index=0,
                label="숨김",
                hypothesis="h",
                explanation="e",
                status="hidden",
            ),
        ]
    )
    session.commit()
    r = client.post(f"/api/v1/problems/{p_a.id}/attempts", json={"chosen_index": 0}).json()
    assert (
        r["misconception"]["label"] == "주소와 값 혼동"
        and r["misconception"]["status"] == "approved"
    )
    r = client.post(f"/api/v1/problems/{p_b.id}/attempts", json={"chosen_index": 0}).json()
    assert r["misconception"] is None  # 관리자가 숨김
    r = client.post(f"/api/v1/problems/{p_a.id}/attempts", json={"chosen_index": 1}).json()
    assert r["correct"] and r["misconception"] is None
