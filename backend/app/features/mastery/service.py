from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.features.mastery.bkt import params_for, trace
from app.models import Attempt, Chapter, Concept, Course, ProblemConcept


@dataclass
class ConceptState:
    mastery: float
    attempts: int
    correct: int


def concept_states(
    session: Session, user_id: int, concept_ids: list[int], before: datetime | None = None
) -> dict[int, ConceptState]:
    """개념별로 이 사용자의 숙련도를 계산한다. 파라미터 학습에는 모든 사용자의 기록을 쓴다.

    before를 주면 이 사용자의 그 시각 이후 풀이는 빼고 계산한다(예: 시험 보기 전 숙련도).
    """
    return states_by_user(session, [user_id], concept_ids, before)[user_id]


def states_by_user(
    session: Session,
    user_ids: list[int],
    concept_ids: list[int],
    before: datetime | None = None,
) -> dict[int, dict[int, ConceptState]]:
    """여러 사용자의 개념별 숙련도를 한 번의 조회로 계산한다(user_id -> concept_id -> 상태).

    같은 문제를 다시 푼 기록은 빼고 처음 푼 결과만 쓴다(정답을 외워 다시 맞혀도 오르지 않게).

    before는 user_ids가 한 명일 때 그 사용자에게만 적용된다(concept_states 참고).
    """
    out: dict[int, dict[int, ConceptState]] = {u: {} for u in user_ids}
    if not concept_ids or not user_ids:
        return out
    rows = session.exec(
        select(
            ProblemConcept.concept_id,
            Attempt.user_id,
            Attempt.problem_id,
            Attempt.correct,
            Attempt.created_at,
        )
        .join(Attempt, Attempt.problem_id == ProblemConcept.problem_id)
        .where(ProblemConcept.concept_id.in_(concept_ids))
        .order_by(Attempt.id)
    ).all()
    seqs: dict[int, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    cut = before.replace(tzinfo=None) if before and len(user_ids) == 1 else None
    seen: set[tuple[int, int, int]] = set()
    for concept_id, uid, problem_id, correct, at in rows:
        if cut and uid == user_ids[0] and at is not None and at.replace(tzinfo=None) >= cut:
            continue
        if (concept_id, uid, problem_id) in seen:
            continue
        seen.add((concept_id, uid, problem_id))
        seqs[concept_id][str(uid)].append(correct)

    for cid in concept_ids:
        by_user = seqs.get(cid, {})
        params = params_for(cid, by_user)
        for uid in user_ids:
            mine = by_user.get(str(uid), [])
            out[uid][cid] = ConceptState(
                mastery=round(trace(mine, params), 3), attempts=len(mine), correct=sum(mine)
            )
    return out


# 약점: 2문제 이상 풀었고, 하나 이상 틀렸고, 알고 있을 확률이 절반 미만인 개념
WEAK_MIN_ATTEMPTS = 2
WEAK_BELOW = 0.5


def is_weak(state: ConceptState) -> bool:
    return (
        state.attempts >= WEAK_MIN_ATTEMPTS
        and state.correct < state.attempts
        and state.mastery < WEAK_BELOW
    )


def weak_concepts_by_user(
    session: Session, user_ids: list[int], subject_id: int
) -> dict[int, set[str]]:
    """과목 안에서 사용자별 약점 개념 이름. 교수가 달라도 같은 이름의 개념은 같은 개념으로 본다."""
    concepts = session.exec(
        select(Concept.id, Concept.name)
        .join(Chapter, Chapter.id == Concept.chapter_id)
        .join(Course, Course.id == Chapter.course_id)
        .where(Course.subject_id == subject_id)
    ).all()
    names = {cid: name.strip() for cid, name in concepts}
    states = states_by_user(session, list(dict.fromkeys(user_ids)), list(names))
    return {
        uid: {names[cid] for cid, s in by_concept.items() if is_weak(s)}
        for uid, by_concept in states.items()
    }
