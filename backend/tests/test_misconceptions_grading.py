"""오개념 붙이기와 서술형 Claude 채점·학습 리포트. Claude 호출은 전부 가짜로 바꾼다."""

import pytest

from app.models import Material, Misconception, PaperEssayImage, PaperTake
from app.services import llm
from tests.conftest import make_admin
from tests.test_papers import _make_paper, public_course  # noqa: F401  (fixture 재사용)


@pytest.fixture
def with_source(session, public_course):  # noqa: F811
    """문제마다 근거 교안 1쪽을 단다."""
    c = public_course
    m = Material(
        course_id=c["course"].id,
        kind="lecture",
        title="교안 1",
        filename="a.pdf",
        page_count=1,
        pages=["포인터는 주소를 저장하는 변수이다. 역참조는 * 연산자로 한다."],
    )
    session.add(m)
    session.flush()
    for p in c["problems"]:
        p.source_material_id, p.source_page = m.id, 1
        session.add(p)
    session.commit()
    c["material"] = m
    return c


def _fake_drafts(calls):
    def f(question, choices, answer_index, explanation, page_text, existing_labels):
        calls.append(list(existing_labels))
        return [
            llm.MisconceptionDraft(
                choice_no=i + 1,
                label="주소와 값 혼동" if i == 0 else f"오답{i}",
                hypothesis="~했을 수 있다",
                explanation="설명",
                evidence="포인터는 주소를 저장하는 변수이다." if i == 0 else "교안에 없는 문장",
            )
            for i in range(len(choices))
            if i != answer_index
        ] + [
            llm.MisconceptionDraft(
                choice_no=answer_index + 1, label="정답", hypothesis="", explanation="", evidence=""
            )
        ]

    return f


def test_generate_misconceptions(client, login, session, with_source, monkeypatch):
    c = with_source
    calls = []
    monkeypatch.setattr(llm, "draft_misconceptions", _fake_drafts(calls))
    login("adm@dgu.ac.kr")
    make_admin(session, "adm@dgu.ac.kr")
    url = f"/api/v1/admin/courses/{c['course'].id}/misconceptions"
    r = client.post(url + "/generate").json()
    assert r["total"] == 3  # 객관식 3개만(서술형 제외)
    st = client.get(url + "/status").json()
    assert st["running"] is False and st["done"] == 3 and st["covered"] == 3
    rows = session.exec(Misconception.__table__.select()).all()
    assert len(rows) == 9  # 문제당 틀린 보기 3개, 정답 보기는 버림
    assert all(r.wrong_choice_index != 1 for r in rows)
    found = [r for r in rows if r.evidence_found]
    assert len(found) == 3 and all(r.source_page == 1 for r in found)
    assert "주소와 값 혼동" in calls[-1]  # 앞에서 만든 이름표를 다음 문제에 넘겨 재사용
    # 다시 눌러도 이미 있는 건 건너뜀
    assert client.post(url + "/generate").json()["total"] == 0
    # 숨기기
    mid = client.get(url).json()[0]["id"]
    assert (
        client.patch(f"/api/v1/admin/misconceptions/{mid}", json={"status": "hidden"}).json()[
            "status"
        ]
        == "hidden"
    )
    client.post("/api/v1/auth/logout")
    login("stu@dgu.ac.kr")
    assert client.post(url + "/generate").status_code == 403


def test_generate_without_key(client, login, session, with_source):
    login("adm@dgu.ac.kr")
    make_admin(session, "adm@dgu.ac.kr")
    r = client.post(
        f"/api/v1/admin/courses/{with_source['course'].id}/misconceptions/generate"
    ).json()
    st = client.get(
        f"/api/v1/admin/courses/{with_source['course'].id}/misconceptions/status"
    ).json()
    assert r["total"] == 3 and st["error"] and st["misconceptions"] == 0


def _submit(client, session, paper, wrong_choice=0):
    take = client.post(f"/api/v1/papers/{paper['id']}/takes").json()
    mcq = [p for p in paper["problems"] if p["qtype"] == "mcq"]
    essays = [p for p in paper["problems"] if p["qtype"] != "mcq"]
    import base64

    res = client.post(
        f"/api/v1/takes/{take['id']}/submit",
        json={
            "answers": [
                {"problem_id": p["id"], "chosen": 1 if i == 0 else wrong_choice}
                for i, p in enumerate(mcq)
            ],
            "essays": [
                {"problem_id": p["id"], "image": base64.b64encode(b"\xff\xd8jpeg").decode()}
                for p in essays
            ],
        },
    ).json()
    session.expire_all()  # 백그라운드 채점이 다른 세션으로 바꾼 값을 다시 읽는다
    return take["id"], res


def test_essay_graded_in_background_and_report(client, login, session, with_source, monkeypatch):
    c = with_source
    monkeypatch.setattr(llm, "draft_misconceptions", _fake_drafts([]))
    monkeypatch.setattr(
        llm,
        "grade_essay",
        lambda img, q, model, rubric, points: llm.EssayGrade(
            transcription="주소를 담는 변수",
            items=[llm.RubricScore(item=rubric[0], max_points=3, points=2, reason="대체로 맞음")],
            total=2,
            feedback="역참조도 써 보세요",
        ),
    )
    monkeypatch.setattr(
        llm, "summarize_result", lambda facts: "A 개념이 약합니다. 교안 1 1쪽을 다시 보세요."
    )
    login("adm@dgu.ac.kr")
    make_admin(session, "adm@dgu.ac.kr")
    client.post(f"/api/v1/admin/courses/{c['course'].id}/misconceptions/generate")

    paper = _make_paper(client, c["course"].id, c["chapter"].id)
    take_id, res = _submit(client, session, paper)
    assert res["essay_status"] == "pending"  # 제출 직후엔 채점 중
    t = session.get(PaperTake, take_id)
    assert t.essay_status == "done" and t.essay_score == 2
    img = session.exec(PaperEssayImage.__table__.select()).first()
    assert img.score == 2 and img.transcription == "주소를 담는 변수"

    r = client.get(f"/api/v1/takes/{take_id}/result").json()
    assert r["score"] == 1 + 2 and r["essay_pending"] is False and r["summary"].startswith("A 개념")
    essay = r["items"][-1]
    assert essay["score"] == 2 and essay["rubric"][0]["points"] == 2 and essay["feedback"]
    wrong = [i for i in r["items"] if i["qtype"] == "mcq" and i["correct"] is False]
    # 고른 보기(0번)의 오개념: 근거 확인된 것이라 보인다
    assert wrong and all(i["misconception"]["label"] == "주소와 값 혼동" for i in wrong)
    assert wrong[0]["misconception"]["source"]["page"] == 1
    rep = r["report"]
    assert len(wrong) == 2 and rep["repeated"] == [{"label": "주소와 값 혼동", "count": 2}]
    assert rep["review_pages"] == ["교안 1 1쪽"]
    assert rep["blank_nos"] == []
    assert {n["kind"] for n in rep["sankey_nodes"]} == {
        "problem",
        "misconception",
        "concept",
        "page",
    }
    assert rep["chapters"][0]["title"] == "포인터" and rep["concepts"]
    assert rep["distribution"] == [{"rank": 1, "score": 3, "total_points": 6, "me": True}]
    assert r["rank"] == 1 and r["takers"] == 1


def test_unverified_or_hidden_misconception_not_shown(
    client, login, session, with_source, monkeypatch
):
    c = with_source
    monkeypatch.setattr(llm, "draft_misconceptions", _fake_drafts([]))
    login("adm@dgu.ac.kr")
    make_admin(session, "adm@dgu.ac.kr")
    client.post(f"/api/v1/admin/courses/{c['course'].id}/misconceptions/generate")
    # 보기 0번(근거 확인됨)은 숨기고, 보기 2번(근거 없음)을 고른다
    for m in session.exec(Misconception.__table__.select()).all():
        if m.wrong_choice_index == 0:
            row = session.get(Misconception, m.id)
            row.status = "hidden"
            session.add(row)
    session.commit()
    paper = _make_paper(client, c["course"].id, c["chapter"].id, essay=0)
    _, r0 = _submit(client, session, paper, wrong_choice=0)
    assert all(i.get("misconception") is None for i in r0["items"])
    client.post("/api/v1/auth/logout")
    login("other@dgu.ac.kr")
    _, r2 = _submit(client, session, paper, wrong_choice=2)
    assert all(i.get("misconception") is None for i in r2["items"])  # 근거 없는 추정은 안 보인다


def test_essay_unavailable_without_key(client, login, session, public_course):  # noqa: F811
    c = public_course
    login("s@dgu.ac.kr")
    paper = _make_paper(client, c["course"].id, c["chapter"].id)
    take_id, res = _submit(client, session, paper)
    t = session.get(PaperTake, take_id)
    assert t.essay_status == "unavailable" and t.essay_score is None
    r = client.get(f"/api/v1/takes/{take_id}/result").json()
    assert r["essay_pending"] is True and r["items"][-1]["score"] is None and r["summary"] is None
