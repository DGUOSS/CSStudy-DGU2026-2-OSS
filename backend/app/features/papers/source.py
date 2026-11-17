"""시험지에 넣을 문제를 고른다.

지금은 강좌 문제 은행(source="bank")에서 유형별 문항 수(객관식·서술형)를 받아, 고른 챕터를 돌아가며
골고루 뽑는다. 챕터 안에서는 퀴즈와 같은 우선순위(안 나온 개념 → 안 푼 문제 → 숙련도 낮은 개념).

문제 생성(question-ai)을 붙이면: 족보로 만든 출제 프로필의 유형 비율(format_ratio)로 유형별 문항 수를 정하고
(`type_counts`), 모자란 문제는 생성해 Problem으로 넣은 뒤 같은 방식으로 고른다(source="generated").
"""

import math

from sqlmodel import Session, select

from app.features.problems.service import pick_problems
from app.models import Chapter, Problem


def type_counts(ratio: dict[str, float], n: int) -> dict[str, int]:
    """유형 비율을 정수 문항 수로(최대 잉여법). 예: {"mcq": 0.7, "essay": 0.3}, 10 → {"mcq": 7, "essay": 3}"""
    total = sum(ratio.values()) or 1
    raw = {k: v / total * n for k, v in ratio.items() if v > 0}
    counts = {k: math.floor(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: -(raw[k] - counts[k]))[: n - sum(counts.values())]:
        counts[k] += 1
    return counts


def _spread(
    session: Session, user_id: int, by_chapter: list[list[Problem]], count: int
) -> list[Problem]:
    """챕터마다 우선순위로 줄 세운 뒤, 챕터를 돌아가며 하나씩 뽑는다."""
    queues = [pick_problems(session, user_id, ps, len(ps)) for ps in by_chapter]
    out: list[Problem] = []
    while len(out) < count and any(queues):
        for q in queues:
            if q and len(out) < count:
                out.append(q.pop(0))
    return out


def pick_for_paper(
    session: Session,
    user_id: int,
    course_id: int,
    chapter_ids: list[int],
    counts: dict[str, int],
) -> list[Problem]:
    """counts: 유형별 문항 수 {"mcq": n, "essay": m}. 시험지 순서는 객관식(챕터 순) → 서술형(챕터 순)."""
    chapters = session.exec(
        select(Chapter).where(Chapter.course_id == course_id, Chapter.id.in_(chapter_ids))  # type: ignore[attr-defined]
    ).all()
    chapters = sorted(chapters, key=lambda c: c.order)
    order = {c.id: i for i, c in enumerate(chapters)}
    problems = session.exec(
        select(Problem).where(Problem.chapter_id.in_([c.id for c in chapters]))  # type: ignore[attr-defined]
    ).all()
    picked: list[Problem] = []
    for qtype in ("mcq", "essay"):
        want = counts.get(qtype, 0)
        if want <= 0:
            continue
        by_chapter = [
            [p for p in problems if p.chapter_id == c.id and (p.qtype == "mcq") == (qtype == "mcq")]
            for c in chapters
        ]
        chosen = _spread(session, user_id, by_chapter, want)
        picked += sorted(chosen, key=lambda p: (order[p.chapter_id], p.id))
    return picked
