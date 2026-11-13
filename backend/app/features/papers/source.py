"""시험지에 넣을 문제를 고른다.

지금은 강좌 문제 은행(source="bank")에서 고른다. 문제 생성(question-ai)을 붙이면 source="generated"로
문제를 먼저 만들어 Problem(qtype 포함)으로 넣은 뒤 같은 방식으로 고르면 된다.
"""

from sqlmodel import Session, select

from app.features.problems.service import pick_problems
from app.models import Chapter, Problem


def pick_for_paper(
    session: Session, user_id: int, course_id: int, chapter_ids: list[int], count: int
) -> list[Problem]:
    chapters = session.exec(
        select(Chapter.id).where(Chapter.course_id == course_id, Chapter.id.in_(chapter_ids))  # type: ignore[attr-defined]
    ).all()
    problems = session.exec(select(Problem).where(Problem.chapter_id.in_(chapters))).all()  # type: ignore[attr-defined]
    picked = pick_problems(session, user_id, list(problems), count)
    # 시험지는 챕터 순서, 그 안에서는 고른 순서. 서술형은 뒤로
    order = {cid: i for i, cid in enumerate(chapter_ids)}
    return sorted(picked, key=lambda p: (p.qtype != "mcq", order.get(p.chapter_id, 0)))
