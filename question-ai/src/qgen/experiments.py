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

import json
import time
from contextlib import contextmanager
from pathlib import Path

from . import agents, evaluate, exam_profile, llm, pipeline
from .ingest import MAX_SOURCE_TITLES, load_chunks, topic_list
from .schemas import ExamPlan

CONDITIONS = ["single", "multi_same", "multi_cross", "multi_no_loop"]


def condition_overrides(cond: str) -> tuple[bool, dict, dict]:
    """→ (검증 여부, pipeline 설정 덮어쓰기, models 덮어쓰기)."""
    models = llm.CFG["models"]
    common = {"max_replacements": 0}
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
        judge_root: Path | None = None, use_cache: bool = True) -> Path:
    conditions = conditions or CONDITIONS
    for c in conditions:
        condition_overrides(c)  # 이름 검사
    exp_rel = Path("experiments") / name
    exp_dir = llm.ROOT / "outputs" / course / exp_rel
    exp_dir.mkdir(parents=True, exist_ok=True)
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
