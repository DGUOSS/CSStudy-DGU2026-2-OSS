"""종이 시험: 시험지 → 시작 → 답안지 사진 인식 → 제출·채점 → 등수."""

from datetime import timedelta

import cv2
import pytest

from app.features.papers import omr
from app.models import Attempt, Paper, PaperEssayImage, PaperTake, Problem
from tests.conftest import make_admin


@pytest.fixture
def public_course(session, course_with_problems):
    """누구나 들어가는 강좌 + 서술형 1문제."""
    c = course_with_problems
    c["course"].is_public = True
    essay = Problem(
        chapter_id=c["chapter"].id,
        question="포인터를 설명하라",
        choices=[],
        answer_index=-1,
        explanation="모범답안 참고",
        qtype="essay",
        model_answer="주소를 저장하는 변수",
        rubric=["주소 저장 — 3점"],
        points=3,
    )
    session.add_all([c["course"], essay])
    session.commit()
    c["essay"] = essay
    return c


def _photo(lay, marks):
    img = omr.render_page_image(lay, 0, marks, scribble=True)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


def _make_paper(client, course_id, chapter_id, count=4, limit=30, essay=None):
    r = client.post(
        f"/api/v1/courses/{course_id}/papers",
        json={
            "title": "중간 대비",
            "chapter_ids": [chapter_id],
            "mcq_count": count if essay is None else count,
            "essay_count": 1 if essay is None else essay,
            "time_limit_min": limit,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_paper_full_flow(client, login, session, public_course):
    c = public_course
    login("p1@dgu.ac.kr")
    paper = _make_paper(client, c["course"].id, c["chapter"].id)
    assert [p["qtype"] for p in paper["problems"]] == [
        "mcq",
        "mcq",
        "mcq",
        "essay",
    ]  # 서술형은 뒤로
    assert paper["total_points"] == 6 and "answer_index" not in paper["problems"][0]
    sheet = client.get(f"/api/v1/papers/{paper['id']}/sheet").json()
    assert len(sheet["pages"]) == 1 and sheet["pages"][0].startswith("<svg")

    take = client.post(f"/api/v1/papers/{paper['id']}/takes").json()
    # 같은 시험지를 다시 시작하면 열려 있는 응시를 이어 간다
    assert client.post(f"/api/v1/papers/{paper['id']}/takes").json()["id"] == take["id"]

    # 1번 정답(1), 2번 오답(0), 3번 비움
    probs = [session.get(Problem, p["id"]) for p in paper["problems"]]
    lay = omr.layout([(p.id, p.qtype, len(p.choices)) for p in probs])
    scan = client.post(
        f"/api/v1/takes/{take['id']}/scan",
        files=[("files", ("s.jpg", _photo(lay, {1: [1], 2: [0]}), "image/jpeg"))],
    ).json()
    assert [(m["chosen"], m["status"]) for m in scan["mcq"]] == [
        (1, "ok"),
        (0, "ok"),
        (None, "blank"),
    ]
    assert scan["essays"][0]["image"]

    res = client.post(
        f"/api/v1/takes/{take['id']}/submit",
        json={
            "answers": [
                {"problem_id": m["problem_id"], "chosen": m["chosen"]} for m in scan["mcq"]
            ],
            "essays": [
                {"problem_id": e["problem_id"], "image": e["image"]} for e in scan["essays"]
            ],
        },
    ).json()
    assert res["score"] == 1 and res["total_points"] == 6 and res["essay_pending"] is True
    assert [i["correct"] for i in res["items"]] == [True, False, False, None]
    # 객관식 답한 2문항만 풀이 기록(숙련도에 반영), 서술형 칸 이미지는 저장
    assert len(session.exec(Attempt.__table__.select()).all()) == 2
    assert session.exec(PaperEssayImage.__table__.select()).first() is not None
    # 다시 제출 불가, 결과 다시 보기
    assert (
        client.post(f"/api/v1/takes/{take['id']}/submit", json={"answers": []}).status_code == 409
    )
    assert client.get(f"/api/v1/takes/{take['id']}/result").json()["score"] == 1


def test_ranking_same_paper(client, login, session, public_course):
    c = public_course
    login("r1@dgu.ac.kr")
    paper = _make_paper(client, c["course"].id, c["chapter"].id, count=3)
    pid = paper["id"]
    mcq = [p for p in paper["problems"] if p["qtype"] == "mcq"]

    def take_and_submit(right: int, minutes_ago: int):
        t = client.post(f"/api/v1/papers/{pid}/takes").json()
        row = session.get(PaperTake, t["id"])
        row.started_at = row.started_at - timedelta(minutes=minutes_ago)
        session.add(row)
        session.commit()
        ans = [{"problem_id": p["id"], "chosen": 1 if i < right else 0} for i, p in enumerate(mcq)]
        return client.post(f"/api/v1/takes/{t['id']}/submit", json={"answers": ans}).json()

    take_and_submit(right=2, minutes_ago=20)  # r1: 2점, 20분
    take_and_submit(right=3, minutes_ago=5)  # r1 두 번째 응시는 등수에 안 들어감
    client.post("/api/v1/auth/logout")
    login("r2@dgu.ac.kr")
    take_and_submit(right=2, minutes_ago=10)  # r2: 2점, 10분 → 1등
    client.post("/api/v1/auth/logout")
    login("r3@dgu.ac.kr")
    late = take_and_submit(right=3, minutes_ago=50)  # r3: 3점이지만 시간 초과 표시
    assert late["late"] is True and late["elapsed_sec"] == 30 * 60
    rk = client.get(f"/api/v1/papers/{pid}/ranking").json()["entries"]
    assert [(e["rank"], e["label"], e["score"]) for e in rk] == [
        (1, "나", 3),
        (2, "응시자 1", 2),
        (3, "응시자 2", 2),
    ]
    lst = client.get(f"/api/v1/courses/{c['course'].id}/papers").json()
    assert lst[0]["takers"] == 3 and lst[0]["my_best"] == 3


def test_paper_needs_course_access(client, login, session, course_with_problems):
    c = course_with_problems
    login("x@dgu.ac.kr")
    r = client.post(
        f"/api/v1/courses/{c['course'].id}/papers",
        json={"title": "t", "chapter_ids": [c["chapter"].id], "mcq_count": 2, "time_limit_min": 10},
    )
    assert r.status_code == 403


def test_quiz_skips_essay(client, login, session, public_course):
    login("q@dgu.ac.kr")
    got = client.get(f"/api/v1/chapters/{public_course['chapter'].id}/problems?count=10").json()
    assert len(got) == 3 and all(p["choices"] for p in got)


def test_purge_course_removes_papers(client, login, session, public_course):
    c = public_course
    login("admin@dgu.ac.kr")
    make_admin(session, "admin@dgu.ac.kr")
    paper = _make_paper(client, c["course"].id, c["chapter"].id)
    t = client.post(f"/api/v1/papers/{paper['id']}/takes").json()
    client.post(f"/api/v1/takes/{t['id']}/submit", json={"answers": [], "essays": []})
    assert client.delete(f"/api/v1/admin/courses/{c['course'].id}").status_code == 204
    assert session.exec(Paper.__table__.select()).first() is None


def test_types_and_chapters_spread(client, login, session, public_course):
    """유형별 문항 수를 따르고, 여러 챕터에서 돌아가며 골고루 뽑는다."""
    from app.features.papers.source import type_counts
    from app.models import Chapter

    assert type_counts({"mcq": 0.7, "essay": 0.3}, 10) == {"mcq": 7, "essay": 3}
    c = public_course
    ch2 = Chapter(course_id=c["course"].id, order=2, title="배열")
    session.add(ch2)
    session.flush()
    for i in range(5):
        session.add(
            Problem(
                chapter_id=ch2.id,
                question=f"b{i}",
                choices=["1", "2"],
                answer_index=0,
                explanation="e",
            )
        )
    session.commit()
    login("s@dgu.ac.kr")
    r = client.post(
        f"/api/v1/courses/{c['course'].id}/papers",
        json={
            "title": "t",
            "chapter_ids": [c["chapter"].id, ch2.id],
            "mcq_count": 4,
            "essay_count": 1,
            "time_limit_min": 10,
        },
    ).json()
    probs = [session.get(Problem, q["id"]) for q in r["problems"]]
    mcq = [p for p in probs if p.qtype == "mcq"]
    assert len(mcq) == 4 and sum(p.chapter_id == ch2.id for p in mcq) == 2  # 챕터마다 2개씩
    assert [p.qtype for p in probs][-1] == "essay"
    chapters = client.get(f"/api/v1/courses/{c['course'].id}/chapters").json()
    assert (chapters[0]["problem_count"], chapters[0]["essay_count"]) == (3, 1)


def test_pause_restart_abandon(client, login, session, public_course):
    c = public_course
    login("t@dgu.ac.kr")
    paper = _make_paper(client, c["course"].id, c["chapter"].id, count=3, limit=30, essay=0)
    t = client.post(f"/api/v1/papers/{paper['id']}/takes").json()
    # 10분 풀고 20분 멈췄다가 다시 시작 → 푼 시간은 10분
    row = session.get(PaperTake, t["id"])
    row.started_at = row.started_at - timedelta(minutes=30)
    session.add(row)
    session.commit()
    p = client.post(f"/api/v1/takes/{t['id']}/pause").json()
    assert p["paused"] is True and p["pause_count"] == 1
    session.refresh(row)
    row.paused_at = row.paused_at - timedelta(minutes=20)
    session.add(row)
    session.commit()
    r = client.post(f"/api/v1/takes/{t['id']}/resume").json()
    assert (
        r["paused"] is False
        and 9 * 60 <= r["spent_sec"] <= 11 * 60
        and r["remaining_sec"] > 18 * 60
    )
    # 처음부터 다시: 이번 응시를 버리고 시작 전으로. 다시 [시험 시작]하면 새 응시
    client.post(f"/api/v1/takes/{t['id']}/abandon")
    assert client.post(f"/api/v1/takes/{t['id']}/pause").status_code == 409
    mine = client.get(f"/api/v1/papers/{paper['id']}/mine").json()
    assert mine["open_take"] is None and mine["submitted"] == []
    fresh = client.post(f"/api/v1/papers/{paper['id']}/takes").json()
    assert fresh["id"] != t["id"] and fresh["spent_sec"] < 5
    client.post(f"/api/v1/takes/{fresh['id']}/abandon")
    # 정지를 쓴 응시는 등수표에 표시
    t2 = client.post(f"/api/v1/papers/{paper['id']}/takes").json()
    client.post(f"/api/v1/takes/{t2['id']}/pause")
    client.post(f"/api/v1/takes/{t2['id']}/submit", json={"answers": []})
    rk = client.get(f"/api/v1/papers/{paper['id']}/ranking").json()["entries"]
    assert len(rk) == 1 and rk[0]["paused"] is True


def test_paper_list_shows_creator(client, login, enroll, course_with_problems):
    login("maker@dgu.ac.kr", "출제자")
    c = course_with_problems["course"]
    enroll(c.subject_id)
    ch = course_with_problems["chapter"].id
    assert (
        client.post(
            f"/api/v1/courses/{c.id}/papers",
            json={"title": "모의", "chapter_ids": [ch], "mcq_count": 2, "time_limit_min": 10},
        ).status_code
        == 201
    )
    [p] = client.get(f"/api/v1/courses/{c.id}/papers").json()
    assert p["creator_name"] == "출제자" and p["created_by_me"]
