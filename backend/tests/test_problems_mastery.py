from app.features.mastery import bkt


def test_problem_hides_answer_and_prefers_unseen_concepts(
    client, login, course_with_problems, enroll
):
    login()
    enroll(course_with_problems["course"].subject_id)
    ch = course_with_problems["chapter"].id
    problems = client.get(f"/api/v1/chapters/{ch}/problems?count=2").json()
    assert all("answer_index" not in p for p in problems)
    direct = client.get(f"/api/v1/problems/{problems[0]['id']}")
    assert direct.status_code == 200 and "answer_index" not in direct.json()
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
