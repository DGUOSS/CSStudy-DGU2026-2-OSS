from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.features.mastery.bkt import params_for, trace
from app.models import Attempt, ProblemConcept


@dataclass
class ConceptState:
    mastery: float
    attempts: int
    correct: int


def concept_states(
    session: Session, user_id: int, concept_ids: list[int], before: datetime | None = None
) -> dict[int, ConceptState]:
    """개념별로 이 사용자의 숙련도를 계산한다. 파라미터 학습에는 모든 사용자의 기록을 쓴다.

    같은 문제를 다시 푼 기록은 빼고 처음 푼 결과만 쓴다(정답을 외워 다시 맞혀도 오르지 않게).

    before를 주면 이 사용자의 그 시각 이후 풀이는 빼고 계산한다(예: 시험 보기 전 숙련도).
    """
    if not concept_ids:
        return {}
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
    cut = before.replace(tzinfo=None) if before else None
    seen: set[tuple[int, int, int]] = set()
    for concept_id, uid, problem_id, correct, at in rows:
        if cut and uid == user_id and at is not None and at.replace(tzinfo=None) >= cut:
            continue
        if (concept_id, uid, problem_id) in seen:
            continue
        seen.add((concept_id, uid, problem_id))
        seqs[concept_id][str(uid)].append(correct)

    out = {}
    for cid in concept_ids:
        by_user = seqs.get(cid, {})
        mine = by_user.get(str(user_id), [])
        params = params_for(cid, by_user)
        out[cid] = ConceptState(
            mastery=round(trace(mine, params), 3), attempts=len(mine), correct=sum(mine)
        )
    return out
