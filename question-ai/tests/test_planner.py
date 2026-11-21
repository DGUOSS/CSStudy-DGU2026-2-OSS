import pytest

from qgen import agents, llm
from qgen.schemas import ExamPlan, ExamProfile, PlannedItem

PROFILE = ExamProfile(course="c", format_ratio={"계산형": 0.7, "서술형": 0.3}, num_questions=7,
                      detail_level="중간", difficulty="어려움", recurring_patterns=[], phrasing_examples=[],
                      emphasized_topics=[])


def _plan(*qtypes: str, ids: list[str] | None = None) -> ExamPlan:
    ids = ids or [f"q{k}" for k in range(1, len(qtypes) + 1)]
    return ExamPlan(items=[PlannedItem(item_id=i, qtype=t, topic="t", bloom_level="적용", difficulty="보통",
                                       points=25, rationale="r") for i, t in zip(ids, qtypes)])


def test_type_counts_largest_remainder():
    assert agents.type_counts({"계산형": 0.7, "서술형": 0.3}, 4) == {"계산형": 3, "서술형": 1}
    assert agents.type_counts({"객관식": 0.4, "단답형": 0.2, "서술형": 0.4}, 10) == {"객관식": 4, "단답형": 2, "서술형": 4}
    assert sum(agents.type_counts({"a": 1, "b": 1, "c": 1}, 4).values()) == 4


def test_plan_issues():
    counts = {"계산형": 3, "서술형": 1}
    assert agents.plan_issues(_plan("계산형", "계산형", "계산형", "서술형"), counts, 4) == []
    assert len(agents.plan_issues(_plan("계산형", "계산형", "서술형", "서술형"), counts, 4)) == 1  # 유형 수
    assert len(agents.plan_issues(_plan("계산형", "계산형", "계산형"), counts, 4)) == 2              # 문항 수 + 유형 수
    assert "겹친다" in agents.plan_issues(_plan("계산형", "계산형", "계산형", "서술형",
                                              ids=["q1", "q1", "q2", "q3"]), counts, 4)[0]


def _fake_calls(monkeypatch, plans):
    prompts = []
    it = iter(plans)

    def fake(role, prompt, schema, **kw):
        prompts.append(prompt)
        return next(it)

    monkeypatch.setattr(llm, "call", fake)
    return prompts


def test_planner_retries_with_issues_then_passes(monkeypatch):
    prompts = _fake_calls(monkeypatch, [_plan("계산형", "서술형", "서술형", "서술형"),
                                        _plan("계산형", "계산형", "계산형", "서술형")])
    plan = agents.planner(PROFILE, ["A (a.pdf p.1)"], 4)
    assert [i.qtype for i in plan.items].count("계산형") == 3
    assert len(prompts) == 2
    assert "이전 계획의 문제" not in prompts[0]
    assert "이전 계획의 문제" in prompts[1] and "{'계산형': 3, '서술형': 1}" in prompts[1]


def test_planner_gives_up_after_retries(monkeypatch):
    bad = _plan("서술형", "서술형", "서술형", "서술형")
    prompts = _fake_calls(monkeypatch, [bad] * (agents.PLAN_RETRIES + 1))
    with pytest.raises(agents.PlanError):
        agents.planner(PROFILE, ["A (a.pdf p.1)"], 4)
    assert len(prompts) == agents.PLAN_RETRIES + 1


def test_replan_item_same_type_new_id_and_points(monkeypatch):
    failed = PlannedItem(item_id="q4", qtype="서술형", topic="RAM vs Flash", source_titles=["메모리 - RAM"],
                         bloom_level="이해", difficulty="보통", points=15, rationale="r")
    prompts = _fake_calls(monkeypatch, [_plan("서술형")])
    new = agents.replan_item(PROFILE, ["A (a.pdf p.1)"], failed, "교안에 Flash 없음", ["RAM vs Flash", "부울식"])
    assert new.item_id == "q4-r1" and new.points == 15 and new.qtype == "서술형"
    p = prompts[0]
    assert "보충 계획" in p and "교안에 Flash 없음" in p and "'부울식'" in p
    assert '"서술형": 1' in p and "총 1문항" in p


def test_replan_item_retries_when_topic_or_title_overlaps(monkeypatch):
    failed = PlannedItem(item_id="q1", qtype="계산형", topic="카르노 맵", source_titles=["Map Simplification"],
                         bloom_level="적용", difficulty="보통", points=25, rationale="r")
    dup = _plan("계산형").model_copy()
    dup.items[0] = dup.items[0].model_copy(update={"topic": "부동소수점표현", "source_titles": ["부동소수점표현"]})
    ok = _plan("계산형").model_copy()
    ok.items[0] = ok.items[0].model_copy(update={"topic": "상태 배정", "source_titles": ["State Assignment"]})
    prompts = _fake_calls(monkeypatch, [dup, ok])
    new = agents.replan_item(PROFILE, ["A (a.pdf p.1)"], failed, "실패", ["카르노 맵", "부동소수점표현"],
                             used_titles=["부동소수점표현"])
    assert new.topic == "상태 배정" and new.item_id == "q1-r1" and len(prompts) == 2
    assert "직전 보충 계획 '부동소수점표현'" in prompts[1]
    with pytest.raises(agents.PlanError):
        _fake_calls(monkeypatch, [dup] * (agents.PLAN_RETRIES + 1))
        agents.replan_item(PROFILE, ["A (a.pdf p.1)"], failed, "실패", ["부동소수점표현"], used_titles=[])
