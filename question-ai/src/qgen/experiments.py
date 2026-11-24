"""M5 비교 실험 (명세 §7): 같은 과목·같은 ExamPlan으로 조건만 바꿔 N세트씩 생성 → 가린 채점 자료.

조건 (명세 §7 표):
- single:        generator 1번, 검증 없음 (베이스라인)
- multi_same:    전체 루프, solver = generator와 같은 모델
- multi_cross:   전체 루프, solver = 다른 회사 모델 (config 그대로, 제안 방법)
- multi_no_loop: solver·reviewer로 판정만, 수정·재생성 없음 (떨어지면 제외)

공정한 비교를 위해 (명세 §10 "실험 조건마다 다른 ExamPlan 쓰기" 금지):
- 계획은 한 번만 만들어 모든 실행 폴더에 같은 plan.json을 넣는다
- 실패 문항 보충(max_replacements)은 끈다 — 보충하면 조건마다 문항 구성이 달라짐
- 세트 k는 모든 호출의 캐시 키에 k를 넣어 세트끼리 다른 응답을 받는다 (조건끼리는 같은 k라도 프롬프트·모델이 달라 구분됨)
- 이미 summary.json이 있는 실행은 건너뛴다 (중간에 멈춰도 다시 돌리면 이어서)
"""
from __future__ import annotations

import itertools
import json
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from . import agents, evaluate, exam_profile, llm, pipeline
from .ingest import MAX_SOURCE_TITLES, load_chunks, topic_list
from .schemas import ExamPlan

CONDITIONS = ["single", "multi_same", "multi_cross", "multi_no_loop"]

# 모델 바꿔 넣기 실험: config의 세 모델(generator·solver·reviewer 자리)을 세 역할에 돌려 넣는 6가지.
# 이름은 짧은 별명 (실행 폴더·대응표에만 쓰임, 채점 자료에는 안 나옴)
SWAP_ALIASES = {"gemini": "generator", "gpt": "solver", "claude": "reviewer"}  # 별명 → config에서 그 모델을 가져올 역할
SWAP_CONDITIONS = [f"gen_{g}-sol_{s}-rev_{r}" for g, s, r in itertools.permutations(SWAP_ALIASES)]
# --swap 기본: 세 모델이 세 역할을 한 번씩 맡는 3가지 (돌려 넣기). 6가지 전부는 --conditions로
SWAP_ROTATIONS = ["gen_gemini-sol_gpt-rev_claude", "gen_gpt-sol_claude-rev_gemini", "gen_claude-sol_gemini-rev_gpt"]


def swap_models(cond: str) -> dict:
    """'gen_gpt-sol_claude-rev_gemini' → {generator: <gpt 모델>, solver: ..., reviewer: ...}."""
    base = {alias: llm.CFG["models"][role] for alias, role in SWAP_ALIASES.items()}
    out = {}
    for part, role in zip(cond.split("-"), ("generator", "solver", "reviewer")):
        alias = part.split("_", 1)[1]
        out[role] = base[alias]
    return out


def condition_overrides(cond: str) -> tuple[bool, dict, dict]:
    """→ (검증 여부, pipeline 설정 덮어쓰기, models 덮어쓰기)."""
    models = llm.CFG["models"]
    common = {"max_replacements": 0}
    if cond in SWAP_CONDITIONS:  # 전체 루프 (multi_cross와 같은 설정), 모델 자리만 바꿈
        return True, common, swap_models(cond)
    if cond == "single":
        return False, common, {}
    if cond == "multi_same":
        return True, common, {"solver": models["generator"]}
    if cond == "multi_cross":
        return True, common, {}
    if cond == "multi_no_loop":
        return True, {**common, "max_revisions": 0, "max_regenerations": 0}, {}
    raise ValueError(f"알 수 없는 조건: {cond} (가능: {CONDITIONS})")


@contextmanager
def overridden(pipeline_cfg: dict, models: dict):
    """llm.CFG를 잠깐 바꿨다가 되돌린다."""
    saved_p = {k: llm.CFG["pipeline"].get(k, _MISSING) for k in pipeline_cfg}
    saved_m = {k: llm.CFG["models"].get(k, _MISSING) for k in models}
    llm.CFG["pipeline"].update(pipeline_cfg)
    llm.CFG["models"].update(models)
    try:
        yield
    finally:
        for d, saved in ((llm.CFG["pipeline"], saved_p), (llm.CFG["models"], saved_m)):
            for k, v in saved.items():
                if v is _MISSING:
                    d.pop(k, None)
                else:
                    d[k] = v


_MISSING = object()


def make_plan(course: str, exp_dir: Path) -> ExamPlan:
    """실험 전체가 쓸 계획 (있으면 재사용)."""
    f = exp_dir / "plan.json"
    if f.exists():
        return ExamPlan.model_validate_json(f.read_text(encoding="utf-8"))
    course_dir = llm.ROOT / "data" / course
    profile = exam_profile.load_or_make(course_dir, course)
    cfg = llm.CFG["pipeline"]
    n = cfg.get("num_questions_override") or profile.num_questions
    llm.configure(log_path=exp_dir / "plan_logs.jsonl")
    plan = agents.planner(profile, topic_list(load_chunks(course_dir, verbose=False)), n,
                          cfg.get("max_source_titles") or MAX_SOURCE_TITLES)
    exp_dir.mkdir(parents=True, exist_ok=True)
    f.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return plan


def run(course: str, name: str, sets: int = 3, conditions: list[str] | None = None,
        judge_root: Path | None = None, use_cache: bool = True, plan_from: str | None = None) -> Path:
    """plan_from: 다른 실험 이름 — 그 실험의 plan.json을 그대로 써서 두 실험 결과를 비교할 수 있게."""
    conditions = conditions or CONDITIONS
    for c in conditions:
        condition_overrides(c)  # 이름 검사
    exp_rel = Path("experiments") / name
    exp_dir = llm.ROOT / "outputs" / course / exp_rel
    exp_dir.mkdir(parents=True, exist_ok=True)
    if plan_from and not (exp_dir / "plan.json").exists():
        src = llm.ROOT / "outputs" / course / "experiments" / plan_from / "plan.json"
        if not src.exists():
            raise FileNotFoundError(f"계획 없음: {src}")
        shutil.copy(src, exp_dir / "plan.json")
    plan = make_plan(course, exp_dir)
    print(f"[exp] {name}: 조건 {conditions} × {sets}세트, 계획 {len(plan.items)}문항 "
          + ", ".join(f"{i.qtype}/{i.topic}" for i in plan.items))
    refs, log = [], []
    t0 = time.time()
    for k in range(1, sets + 1):
        for cond in conditions:
            run_id = (exp_rel / "runs" / f"{cond}-s{k}").as_posix()
            run_dir = llm.ROOT / "outputs" / course / run_id
            refs.append(evaluate.RunRef(cond, k, run_dir))
            if (run_dir / "summary.json").exists():
                print(f"[exp] {cond} 세트 {k}: 이미 있음 → 건너뜀")
                continue
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")  # 모든 조건 같은 계획
            verify, p_over, m_over = condition_overrides(cond)
            print(f"\n[exp] ===== {cond} 세트 {k} =====")
            with overridden(p_over, m_over):
                pipeline.run(course, run_id, use_cache=use_cache, verify=verify, seed=k)
            s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            log.append({"condition": cond, "set": k, "accepted": s["accepted"], "planned": s["planned"],
                        "api_calls": s["api_calls"], "sec": s["sec"]})
    (exp_dir / "runs.json").write_text(json.dumps(
        {"conditions": conditions, "sets": sets, "runs": [{"condition": r.condition, "set": r.set_no,
                                                            "run": str(r.run_dir)} for r in refs],
         "this_session": log, "sec": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1), encoding="utf-8")
    chunks = load_chunks(llm.ROOT / "data" / course, verbose=False)
    out = evaluate.export(name, refs, chunks, judge_root or (llm.ROOT / evaluate.JUDGE_DIR_NAME), exp_dir)
    print(f"\n[exp] 끝 ({round(time.time() - t0)}초). 채점 자료: {out}\n      README.md대로 채점 후: "
          f"python scripts/evaluate.py score --course {course} --name {name}")
    return exp_dir
