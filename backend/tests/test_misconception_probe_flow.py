from app.models import Material, MisconceptionProbe


def _probe(session, course_with_problems):
    course = course_with_problems["course"]
    problem = course_with_problems["problems"][0]
    material = Material(
        course_id=course.id,
        kind="lecture",
        title="포인터 교안",
        filename="pointer.pdf",
        pages=["A pointer stores an address."],
        page_count=1,
    )
    session.add(material)
    session.flush()
    probe = MisconceptionProbe(
        problem_id=problem.id,
        wrong_choice_index=0,
        hypothesis="주소와 값을 혼동할 수 있습니다.",
        question="포인터에는 무엇이 저장되나요?",
        choices=["주소", "값"],
        answer_index=0,
        explanation="포인터에는 주소가 저장됩니다.",
        evidence="pointer stores an address",
        source_material_id=material.id,
        source_page=1,
    )
    session.add(probe)
    session.commit()
    return problem, probe, material


def test_only_approved_matching_wrong_choice_opens_probe(
    client, login, enroll, session, course_with_problems
):
    problem, probe, material = _probe(session, course_with_problems)
    login()
    enroll(course_with_problems["course"].subject_id)
    url = f"/api/v1/problems/{problem.id}/attempts"

    draft = client.post(url, json={"chosen_index": 0}).json()
    assert draft["misconception_probe"] is None

    probe.status = "approved"
    session.add(probe)
    session.commit()
    matched = client.post(url, json={"chosen_index": 0}).json()
    assert matched["misconception_probe"] == {
        "question": probe.question,
        "choices": probe.choices,
    }
    assert "answer_index" not in matched["misconception_probe"]
    assert client.post(url, json={"chosen_index": 1}).json()["misconception_probe"] is None
    assert client.post(url, json={"chosen_index": 2}).json()["misconception_probe"] is None

    material.pages = ["The source text has changed."]
    session.add(material)
    session.commit()
    assert client.post(url, json={"chosen_index": 0}).json()["misconception_probe"] is None


def test_probe_answer_is_private_and_does_not_change_mastery(
    client, login, enroll, session, course_with_problems
):
    problem, probe, _ = _probe(session, course_with_problems)
    probe.status = "approved"
    session.add(probe)
    session.commit()
    login()
    enroll(course_with_problems["course"].subject_id)
    first = client.post(f"/api/v1/problems/{problem.id}/attempts", json={"chosen_index": 0}).json()
    url = f"/api/v1/attempts/{first['attempt_id']}/misconception-probe"
    before = client.get(f"/api/v1/courses/{course_with_problems['course'].id}/mastery").json()
    assert client.post(url, json={"chosen_index": 9}).status_code == 422
    answer = client.post(url, json={"chosen_index": 0}).json()
    assert answer["correct"] is True
    assert answer["answer_index"] == 0
    assert answer["source"]["page"] == 1
    assert answer["hypothesis"] == probe.hypothesis
    assert (
        client.get(f"/api/v1/courses/{course_with_problems['course'].id}/mastery").json() == before
    )

    from sqlmodel import select

    from app.models import Attempt

    assert len(session.exec(select(Attempt)).all()) == 1
    login(email="other@dgu.ac.kr", name="다른 학생")
    assert client.post(url, json={"chosen_index": 0}).status_code == 404
