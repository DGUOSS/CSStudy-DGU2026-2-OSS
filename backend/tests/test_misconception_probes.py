"""오답별 확인 문제 시드의 유효성과 재실행 안전성을 확인한다."""

import copy
import json
import sys
from pathlib import Path

from sqlmodel import select

from app.models import MisconceptionProbe, Problem

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seed  # noqa: E402


SEED_PATH = Path(__file__).resolve().parents[2] / "data/seed/basic-programming-kang.json"


def load_seed() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_probe_seed_is_draft_and_idempotent(session):
    data = load_seed()
    assert seed.check(data, {}) == []

    seed.seed_one(session, data, {})
    session.commit()
    seed.seed_one(session, data, {})
    session.commit()

    problem = session.exec(
        select(Problem).where(Problem.question == 'printf("[%03d]", 7); 의 출력 결과는?')
    ).one()
    probes = session.exec(
        select(MisconceptionProbe).where(MisconceptionProbe.problem_id == problem.id)
    ).all()
    assert {p.wrong_choice_index for p in probes} == {0, 1, 3}
    assert all(p.status == "draft" and p.reviewed_by is None for p in probes)
    assert all(0 <= p.answer_index < len(p.choices) for p in probes)
    assert all(p.evidence == problem.evidence for p in probes)


def test_probe_seed_rejects_answer_and_duplicate_wrong_choice():
    data = load_seed()
    problem = data["chapters"][0]["problems"][1]
    invalid = copy.deepcopy(problem["misconception_probes"][0])
    invalid["wrong_choice_index"] = problem["answer"]
    problem["misconception_probes"].append(invalid)
    errors = seed.check(data, {})
    assert any("정답 보기에는" in error for error in errors)

    invalid["wrong_choice_index"] = 0
    errors = seed.check(data, {})
    assert any("중복되거나" in error for error in errors)
