"""문제 고르기: 퀴즈와 종이 시험지가 같이 쓴다."""

from sqlmodel import Session, select

from app.features.mastery.service import concept_states
from app.models import Attempt, Concept, Problem, ProblemConcept


def concepts_of(session: Session, problem_ids: list[int]) -> dict[int, list[Concept]]:
    rows = session.exec(
        select(ProblemConcept.problem_id, Concept)
        .join(Concept, Concept.id == ProblemConcept.concept_id)
        .where(ProblemConcept.problem_id.in_(problem_ids))  # type: ignore[attr-defined]
    ).all()
    out: dict[int, list[Concept]] = {pid: [] for pid in problem_ids}
    for pid, concept in rows:
        out[pid].append(concept)
    return out


def pick_problems(
    session: Session, user_id: int, problems: list[Problem], count: int
) -> list[Problem]:
    """다음에 풀 문제를 고른다.

    우선순위: ① 아직 한 번도 안 나온 개념이 들어간 문제 ② 아직 안 푼 문제
    ③ 숙련도가 낮은 개념의 문제. 같으면 id 순. 한 번에 고를 때도 안 나온 개념이 골고루 들어가게 한다.
    """
    if not problems:
        return []
    concepts = concepts_of(session, [p.id for p in problems])
    concept_ids = sorted({c.id for cs in concepts.values() for c in cs})
    states = concept_states(session, user_id, concept_ids)
    solved = set(
        session.exec(
            select(Attempt.problem_id).where(
                Attempt.user_id == user_id,
                Attempt.problem_id.in_([p.id for p in problems]),  # type: ignore[attr-defined]
            )
        ).all()
    )

    def priority(p: Problem) -> tuple:
        cs = concepts[p.id]
        has_unseen = any(states[c.id].attempts == 0 for c in cs)
        lowest = min((states[c.id].mastery for c in cs), default=1.0)
        return (not has_unseen, p.id in solved, lowest, p.id)

    picked: list[Problem] = []
    seen_now: set[int] = set()
    pool = sorted(problems, key=priority)
    while pool and len(picked) < count:
        best = next(
            (
                p
                for p in pool
                if any(c.id not in seen_now and states[c.id].attempts == 0 for c in concepts[p.id])
            ),
            pool[0],
        )
        picked.append(best)
        pool.remove(best)
        seen_now.update(c.id for c in concepts[best.id])
    return picked
