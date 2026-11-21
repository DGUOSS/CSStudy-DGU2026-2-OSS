import json
import shutil

from qgen import agents, exam_profile, experiments, llm, pipeline
from qgen.schemas import ExamPlan, ExamProfile, PlannedItem, Question, SourceRef

PROFILE = ExamProfile(course="demo", format_ratio={"객관식": 0.5, "서술형": 0.5}, num_questions=2,
                      detail_level="중간", difficulty="보통", recurring_patterns=[], phrasing_examples=[],
                      emphasized_topics=[])
PLAN = ExamPlan(items=[
    PlannedItem(item_id="q1", qtype="객관식", topic="t1", bloom_level="이해", difficulty="보통", points=50, rationale="r"),
    PlannedItem(item_id="q2", qtype="서술형", topic="t2", bloom_level="이해", difficulty="보통", points=50, rationale="r")])


def _setup(tmp_path, monkeypatch):
    shutil.copytree(llm.ROOT / "data" / "demo", tmp_path / "data" / "demo")
    monkeypatch.setattr(llm, "ROOT", tmp_path)
    monkeypatch.setattr(exam_profile, "load_or_make", lambda *a, **k: PROFILE)
    plans = []
    monkeypatch.setattr(agents, "planner", lambda *a, **k: plans.append(1) or PLAN)
    calls = []

    def fake_run(course, run_id, use_cache=True, verify=True, seed=0, **k):
        out = tmp_path / "outputs" / course / run_id
        calls.append({"run_id": run_id, "verify": verify, "seed": seed,
                      "solver": llm.CFG["models"]["solver"], "rev": llm.CFG["pipeline"]["max_revisions"],
                      "rep": llm.CFG["pipeline"].get("max_replacements"),
                      "plan": json.loads((out / "plan.json").read_text(encoding="utf-8"))})
        src = SourceRef(file="os_ch5_scheduling.md", page=1)
        exam = {i.item_id: Question(item_id=i.item_id, qtype=i.qtype, stem=f"{i.topic} 문제",
                                    choices=[f"보기{n}" for n in range(1, 6)] if i.qtype == "객관식" else None,
                                    answer="1", sources=[src]).model_dump() for i in PLAN.items}
        (out / "exam.json").write_text(json.dumps(exam, ensure_ascii=False), encoding="utf-8")
        (out / "trace.json").write_text(json.dumps([{"item": "q1"}, {"item": "q2"}, {"item": "q2"}]), encoding="utf-8")
        (out / "summary.json").write_text(json.dumps({"accepted": 2, "planned": 2, "api_calls": 3, "tokens": 10,
                                                      "sec": 1.0}), encoding="utf-8")
        return out

    monkeypatch.setattr(pipeline, "run", fake_run)
    return calls, plans


def test_conditions_share_plan_and_get_right_settings(tmp_path, monkeypatch):
    calls, plans = _setup(tmp_path, monkeypatch)
    before = (dict(llm.CFG["pipeline"]), dict(llm.CFG["models"]))
    exp = experiments.run("demo", "e1", sets=2, judge_root=tmp_path / "for judge")
    assert plans == [1]  # 계획은 한 번만
    assert len(calls) == 8 and all(c["plan"] == json.loads(PLAN.model_dump_json()) for c in calls)
    by = {c["run_id"]: c for c in calls}
    gen = llm.CFG["models"]["generator"]
    assert by["experiments/e1/runs/single-s1"]["verify"] is False
    assert by["experiments/e1/runs/multi_same-s1"]["solver"] == gen
    assert by["experiments/e1/runs/multi_cross-s2"]["solver"] == before[1]["solver"] != gen
    assert by["experiments/e1/runs/multi_no_loop-s1"]["rev"] == 0
    assert all(c["rep"] == 0 for c in calls)  # 보충 끔
    assert {c["seed"] for c in calls} == {1, 2}
    assert (dict(llm.CFG["pipeline"]), dict(llm.CFG["models"])) == before  # 설정 되돌림
    assert (exp / "judge_key.json").exists() and (tmp_path / "for judge" / "e1" / "items_part01.md").exists()
    key = json.loads((exp / "judge_key.json").read_text(encoding="utf-8"))
    assert len(key["items"]) == 16 and {v["condition"] for v in key["items"].values()} == set(experiments.CONDITIONS)


def test_finished_runs_are_skipped(tmp_path, monkeypatch):
    calls, _ = _setup(tmp_path, monkeypatch)
    experiments.run("demo", "e2", sets=1, conditions=["single", "multi_cross"], judge_root=tmp_path / "for judge")
    assert len(calls) == 2
    experiments.run("demo", "e2", sets=2, conditions=["single", "multi_cross"], judge_root=tmp_path / "for judge")
    assert len(calls) == 4 and all(c["seed"] == 2 for c in calls[2:])  # 세트 1은 건너뛰고 세트 2만


def test_seed_base_changes_cache_key(tmp_path, monkeypatch):
    from qgen.schemas import Review

    seen = []
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(llm, "_raw_call", lambda model, messages, t: (seen.append(1) or (json.dumps(
        {"item_id": "x", "issues": [], "answer_match": "일치", "grounded": True, "profile_fit": True,
         "verdict": "pass", "feedback": ""}), 1, 0.0)))
    for base in (0, 0, 1, 1, 2):
        llm.configure(seed_base=base)
        llm.call("reviewer", "같은 프롬프트", Review)
    assert len(seen) == 3  # 0·1·2 세트마다 한 번씩만 실제 호출, 같은 세트는 캐시
    llm.configure()
