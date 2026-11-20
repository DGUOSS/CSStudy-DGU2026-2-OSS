"""교안이 들어오면 챕터·개념 자동 생성, 객관식이 들어오면 오개념 자동 생성. Claude는 가짜."""

from sqlmodel import select

from app.core.config import settings
from app.features.misconceptions import service as mis
from app.features.structure import service as st
from app.models import (
    Chapter,
    Concept,
    Course,
    Material,
    Misconception,
    Problem,
    Professor,
    Subject,
)
from app.services import llm


def _course(session):
    subj, prof = Subject(name="인공지능"), Professor(name="홍길동")
    session.add_all([subj, prof])
    session.flush()
    c = Course(subject_id=subj.id, professor_id=prof.id)
    session.add(c)
    session.commit()
    return c


def _lecture(session, course, pages, title="인공지능 교안 1"):
    m = Material(
        course_id=course.id,
        kind="lecture",
        title=title,
        filename="ai1.pdf",
        page_count=len(pages),
        pages=pages,
    )
    session.add(m)
    session.commit()
    return m


def _fake_structure(calls):
    def f(material, existing):
        calls.append((material.id, list(existing)))
        return st.StructureDraft(
            chapters=[
                st.ChapterDraft(
                    title="2장 탐색",
                    start_page=3,
                    end_page=99,
                    concepts=[
                        st.ConceptDraft(name="너비 우선 탐색"),
                        st.ConceptDraft(name="깊이 우선 탐색"),
                        st.ConceptDraft(name="너비 우선 탐색"),
                    ],
                ),
                st.ChapterDraft(
                    title="1장 에이전트",
                    start_page=1,
                    end_page=2,
                    concepts=[st.ConceptDraft(name="합리적 에이전트")],
                ),
                st.ChapterDraft(title="빈 챕터", start_page=4, end_page=4, concepts=[]),
            ]
        )

    return f


def test_lecture_saved_builds_chapters_and_concepts(session, monkeypatch):
    """교안을 저장하면(어디서든) 커밋 뒤 챕터·개념이 생긴다. 쪽 순서로 정렬, 중복·빈 챕터 정리."""
    calls = []
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    monkeypatch.setattr(st, "draft_structure", _fake_structure(calls))
    monkeypatch.setattr(st, "spawn", lambda bind, ids: st.run_for(bind, ids))
    course = _course(session)
    m = _lecture(session, course, ["표지", "에이전트란", "탐색 문제", "BFS"])
    chapters = session.exec(
        select(Chapter).where(Chapter.course_id == course.id).order_by(Chapter.order)
    ).all()
    assert [c.title for c in chapters] == ["1장 에이전트", "2장 탐색"]
    assert all(c.material_id == m.id for c in chapters)
    names = session.exec(select(Concept.name).where(Concept.chapter_id == chapters[1].id)).all()
    assert names == ["너비 우선 탐색", "깊이 우선 탐색"]
    # 같은 교안은 다시 만들지 않는다
    assert st.build_for_material(session, m.id) == 0 and len(calls) == 1
    # 두 번째 교안은 순서가 이어지고, 기존 개념 이름을 생성기에 넘긴다
    _lecture(session, course, ["3장 학습"], title="인공지능 교안 2")
    assert "합리적 에이전트" in calls[-1][1]
    orders = session.exec(
        select(Chapter.order).where(Chapter.course_id == course.id).order_by(Chapter.order)
    ).all()
    assert orders == [1, 2, 3, 4]


def test_new_version_moves_chapters_instead_of_rebuilding(session, monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    monkeypatch.setattr(st, "draft_structure", _fake_structure(calls))
    course = _course(session)
    old = _lecture(session, course, ["a", "b", "c"])
    st.build_for_material(session, old.id)
    new = _lecture(session, course, ["a", "b", "c 수정"])
    old.replaced_by = new.id
    session.add(old)
    session.commit()
    assert st.build_for_material(session, new.id) == 0 and len(calls) == 1
    assert {c.material_id for c in session.exec(select(Chapter)).all()} == {new.id}


def test_backfill_and_skip_without_key(session, monkeypatch):
    course = _course(session)
    m = _lecture(session, course, ["x"])
    assert st.missing_material_ids(session) == [m.id]
    monkeypatch.setattr(st, "draft_structure", lambda material, existing: None)  # 실패해도 조용히
    assert st.build_for_material(session, m.id) == 0
    assert session.exec(select(Chapter)).all() == []


def test_new_mcq_gets_misconceptions_automatically(session, course_with_problems, monkeypatch):
    """객관식을 저장하면 오개념이 자동으로 붙는다. 서술형은 안 붙고, 키가 없으면 아무것도 안 한다."""
    ch = course_with_problems["chapter"]
    drafted = []

    def fake(question, choices, answer_index, explanation, page_text, existing_labels):
        drafted.append(question)
        return [
            llm.MisconceptionDraft(
                choice_no=i + 1, label=f"착각{i}", hypothesis="h", explanation="e", evidence=""
            )
            for i in range(len(choices))
            if i != answer_index
        ]

    monkeypatch.setattr(llm, "draft_misconceptions", fake)
    monkeypatch.setattr(mis, "spawn", lambda bind, ids: mis._run(bind, ids))
    session.add(
        Problem(
            chapter_id=ch.id,
            question="키 없음",
            choices=["a", "b"],
            answer_index=0,
            explanation="e",
        )
    )
    session.commit()
    assert drafted == []
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    p = Problem(
        chapter_id=ch.id,
        question="새 문제",
        choices=["a", "b", "c"],
        answer_index=0,
        explanation="e",
    )
    essay = Problem(
        chapter_id=ch.id,
        question="서술",
        choices=[],
        answer_index=-1,
        explanation="e",
        qtype="essay",
    )
    session.add_all([p, essay])
    session.commit()
    assert drafted == ["새 문제"]
    rows = session.exec(select(Misconception).where(Misconception.problem_id == p.id)).all()
    assert sorted(r.wrong_choice_index for r in rows) == [1, 2]


def test_misconception_backfill_and_paper_safety_net(
    client, login, session, course_with_problems, monkeypatch
):
    """서버를 켤 때, 시험지를 만들 때 오개념이 빠진 객관식을 채운다."""
    c = course_with_problems
    c["course"].is_public = True
    session.add(c["course"])
    session.commit()
    done = []

    def fake(question, choices, answer_index, explanation, page_text, existing_labels):
        done.append(question)
        return [
            llm.MisconceptionDraft(
                choice_no=answer_index + 2, label="L", hypothesis="h", explanation="e", evidence=""
            )
        ]

    monkeypatch.setattr(llm, "draft_misconceptions", fake)
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    assert len(mis.missing_mcq_ids(session)) == 3
    monkeypatch.setattr(mis, "BACKFILL_LIMIT", 2)
    mis.backfill(session.get_bind())
    assert len(done) == 2 and len(mis.missing_mcq_ids(session)) == 1
    # 시험지를 만들면 그 시험지 객관식 중 빠진 것을 채운다
    monkeypatch.setattr(mis, "spawn", lambda bind, ids: mis._run(bind, ids))
    login("p@dgu.ac.kr")
    r = client.post(
        f"/api/v1/courses/{c['course'].id}/papers",
        json={
            "title": "t",
            "chapter_ids": [c["chapter"].id],
            "mcq_count": 3,
            "essay_count": 0,
            "time_limit_min": 10,
        },
    )
    assert r.status_code == 201, r.text
    session.expire_all()
    assert mis.missing_mcq_ids(session) == []
