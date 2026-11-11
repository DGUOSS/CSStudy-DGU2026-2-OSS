"""개념별 숙련도 계산 (Bayesian Knowledge Tracing).

- 숙련도 = "이 개념을 알고 있을 확률". 풀이 결과가 하나씩 들어올 때마다 갱신한다.
- 파라미터(처음 알 확률, 배울 확률, 찍어서 맞힐 확률, 실수할 확률)는
  개념마다 풀이 기록이 MIN_ATTEMPTS_FOR_FIT개 이상 쌓이면 pyBKT로 학습하고,
  그 전에는 DEFAULT_PARAMS를 쓴다.
"""

from dataclasses import dataclass

MIN_ATTEMPTS_FOR_FIT = 40
REFIT_EVERY = 40  # 기록이 이만큼 늘 때마다 다시 학습


@dataclass(frozen=True)
class BktParams:
    prior: float = 0.2
    learn: float = 0.15
    guess: float = 0.25  # 4지선다
    slip: float = 0.1


DEFAULT_PARAMS = BktParams()


def update(p: float, correct: bool, params: BktParams) -> float:
    """풀이 결과 하나로 숙련도를 갱신한다."""
    g, s = params.guess, params.slip
    if correct:
        posterior = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    else:
        posterior = p * s / (p * s + (1 - p) * (1 - g))
    return posterior + (1 - posterior) * params.learn


def trace(results: list[bool], params: BktParams = DEFAULT_PARAMS) -> float:
    p = params.prior
    for correct in results:
        p = update(p, correct, params)
    return p


def fit_params(sequences: dict[str, list[bool]]) -> BktParams:
    """한 개념의 사용자별 풀이 순서(user -> 정오 목록)로 pyBKT 파라미터를 학습한다."""
    import pandas as pd  # pyBKT는 불러오는 데 오래 걸려서 필요할 때만 불러온다
    from pyBKT.models import Model

    rows, order = [], 0
    for user, results in sequences.items():
        for correct in results:
            order += 1
            rows.append(
                {"order_id": order, "user_id": user, "skill_name": "c", "correct": int(correct)}
            )
    model = Model(seed=42, num_fits=3)
    model.fit(data=pd.DataFrame(rows))
    v = model.params()["value"]

    def get(name: str) -> float:
        return float(v.loc[("c", name, "default")])

    # 기록이 적으면 극단값이 나올 수 있어 상식적인 범위로 자른다
    return BktParams(
        prior=min(max(get("prior"), 0.01), 0.9),
        learn=min(max(get("learns"), 0.01), 0.5),
        guess=min(max(get("guesses"), 0.05), 0.4),
        slip=min(max(get("slips"), 0.02), 0.3),
    )


_cache: dict[int, tuple[int, BktParams]] = {}


def params_for(concept_id: int, sequences: dict[str, list[bool]]) -> BktParams:
    total = sum(len(s) for s in sequences.values())
    if total < MIN_ATTEMPTS_FOR_FIT:
        return DEFAULT_PARAMS
    cached = _cache.get(concept_id)
    if cached and total - cached[0] < REFIT_EVERY:
        return cached[1]
    params = fit_params(sequences)
    _cache[concept_id] = (total, params)
    return params
