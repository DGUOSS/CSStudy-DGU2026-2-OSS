from collections import defaultdict
from dataclasses import dataclass

from sqlmodel import Session, select

from app.features.mastery.bkt import params_for, trace
from app.models import Attempt, ProblemConcept


@dataclass
class ConceptState:
    mastery: float
    attempts: int
    correct: int


def concept_states(
    session: Session, user_id: int, concept_ids: list[int]
) -> dict[int, ConceptState]:
    """개념별로 이 사용자의 숙련도를 계산한다. 파라미터 학습에는 모든 사용자의 기록을 쓴다."""
    if not concept_ids:
        return {}
    rows = session.exec(
        select(ProblemConcept.concept_id, Attempt.user_id, Attempt.correct)
        .join(Attempt, Attempt.problem_id == ProblemConcept.problem_id)
        .where(ProblemConcept.concept_id.in_(concept_ids))
        .order_by(Attempt.id)
    ).all()
    seqs: dict[int, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for concept_id, uid, correct in rows:
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
