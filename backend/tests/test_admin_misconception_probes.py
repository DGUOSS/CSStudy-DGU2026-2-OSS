from app.models import Material, MisconceptionProbe
from tests.conftest import make_admin


def _make_probe(session, course_with_problems):
    course = course_with_problems["course"]
    problem = course_with_problems["problems"][0]
    material = Material(
        course_id=course.id,
        kind="lecture",
        title="포인터 교안",
        filename="pointer.pdf",
        pages=["A pointer variable stores an address."],
        page_count=1,
    )
    session.add(material)
    session.flush()
    probe = MisconceptionProbe(
        problem_id=problem.id,
        wrong_choice_index=0,
        hypothesis="주소와 값을 혼동한다",
        question="포인터에는 무엇이 저장되나요?",
        choices=["주소", "값"],
        answer_index=0,
        explanation="포인터에는 주소가 저장됩니다.",
        evidence="pointer variable stores an address",
        source_material_id=material.id,
        source_page=1,
    )
    session.add(probe)
    session.commit()
    return probe


def test_admin_review_requires_admin_and_valid_lecture_evidence(
    client, login, session, course_with_problems
):
    probe = _make_probe(session, course_with_problems)
    login()
    url = f"/api/v1/admin/misconception-probes/{probe.id}"
    assert client.get("/api/v1/admin/misconception-probes").status_code == 403
    assert client.post(url + "/approve").status_code == 403
    make_admin(session)

    listed = client.get("/api/v1/admin/misconception-probes")
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "draft"
    assert listed.json()[0]["problem_choices"] == ["1", "2", "3", "4"]

    probe.evidence = "not in the lecture"
    session.add(probe)
    session.commit()
    assert client.post(url + "/approve").status_code == 422
    assert probe.status == "draft"

    body = {
        "hypothesis": "주소와 값을 혼동한다",
        "question": "포인터에는 무엇이 저장되나요?",
        "choices": ["주소", "값"],
        "answer_index": 0,
        "explanation": "포인터에는 주소가 저장됩니다.",
        "evidence": "pointer variable stores an address",
        "source_material_id": probe.source_material_id,
        "source_page": 1,
    }
    bad = {**body, "source_page": 2}
    assert client.put(url, json=bad).status_code == 422
    session.refresh(probe)
    assert probe.source_page == 1
    assert client.put(url, json=body).status_code == 200
    approved = client.post(url + "/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert probe.reviewed_by is not None

    body["question"] = "포인터 변수에는 무엇이 저장되나요?"
    updated = client.put(url, json=body)
    assert updated.status_code == 200
    assert updated.json()["status"] == "draft"
    assert probe.reviewed_by is None

    client.post(url + "/approve")
    withdrawn = client.post(url + "/draft")
    assert withdrawn.json()["status"] == "draft"
    assert withdrawn.json()["reviewed_at"] is None


def test_admin_can_create_reviewable_probe(client, login, session, course_with_problems):
    original = _make_probe(session, course_with_problems)
    login()
    assert client.get("/api/v1/admin/misconception-probes/candidates").status_code == 403
    make_admin(session)
    candidates = client.get("/api/v1/admin/misconception-probes/candidates").json()
    candidate = next(row for row in candidates if row["problem_id"] == original.problem_id)
    assert candidate["existing_wrong_choice_indices"] == [0]
    body = {
        "problem_id": original.problem_id,
        "wrong_choice_index": 2,
        "hypothesis": "포인터의 주소와 값을 혼동할 수 있습니다.",
        "question": "포인터 변수에는 무엇이 저장되나요?",
        "choices": ["주소", "값"],
        "answer_index": 0,
        "explanation": "포인터에는 주소가 저장됩니다.",
        "evidence": original.evidence,
        "source_material_id": original.source_material_id,
        "source_page": 1,
    }
    created = client.post("/api/v1/admin/misconception-probes", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "draft"
    assert client.post("/api/v1/admin/misconception-probes", json=body).status_code == 409
    body["wrong_choice_index"] = candidate["answer_index"]
    assert client.post("/api/v1/admin/misconception-probes", json=body).status_code == 422
