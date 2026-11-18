from __future__ import annotations

import json
import time
from pathlib import Path

from . import agents, checks, llm
from .ingest import MAX_SOURCE_TITLES, Retriever, load_chunks, load_text_dir, search_queries, topic_list
from .render import render_answers, render_exam
from .schemas import ExamPlan, ExamProfile, Question

ROOT = llm.ROOT


def run(course: str, run_id: str | None = None, new_profile: bool = False, use_cache: bool = True) -> Path:
    cfg = llm.CFG["pipeline"]
    course_dir = ROOT / "data" / course
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    out = ROOT / "outputs" / course / run_id
    out.mkdir(parents=True, exist_ok=True)
    llm.configure(log_path=out / "logs.jsonl", use_cache=use_cache)
    t0 = time.time()

    chunks = load_chunks(course_dir)
    if not chunks:
        raise SystemExit(f"{course_dir/'lectures'}에 강의자료(.pdf/.md/.txt)가 없습니다.")
    retriever = Retriever(chunks)
    past = load_text_dir(course_dir / "past_exams")
    notes_f = course_dir / "notes.md"
    notes = notes_f.read_text(encoding="utf-8") if notes_f.exists() else ""
    print(f"[ingest] 강의자료 청크 {len(chunks)}개, 기출 {len(past)}자")
    phase_sec: dict[str, float] = {"ingest": round(time.time() - t0, 1)}
    t_phase = time.time()

    # 1) Analyst — 과목 공용 profile.json (사용자가 직접 수정 가능, 있으면 재사용)
    prof_f = ROOT / "outputs" / course / "profile.json"
    if prof_f.exists() and not new_profile:
        profile = ExamProfile.model_validate_json(prof_f.read_text(encoding="utf-8"))
        print(f"[analyst] 기존 프로필 재사용: {prof_f}")
    else:
        profile = agents.analyst(course, past, notes)
        prof_f.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        print(f"[analyst] 프로필 생성 → {prof_f}")
    (out / "profile.json").write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    phase_sec["analyst"] = round(time.time() - t_phase, 1)
    t_phase = time.time()

    # 2) Planner
    n = cfg.get("num_questions_override") or profile.num_questions
    plan_f = out / "plan.json"
    if plan_f.exists():
        plan = ExamPlan.model_validate_json(plan_f.read_text(encoding="utf-8"))
    else:
        plan = agents.planner(profile, topic_list(chunks), n, cfg.get("max_source_titles") or MAX_SOURCE_TITLES)
        plan_f.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    print(f"[planner] {len(plan.items)}문항: " + ", ".join(f"{i.qtype}/{i.topic}" for i in plan.items))
    phase_sec["planner"] = round(time.time() - t_phase, 1)
    t_phase = time.time()
    item_sec: dict[str, float] = {}

    # 3) 문항별 생성 → 규칙검사 → 블라인드 풀이 → 검토 → 수정 루프
    accepted: dict[str, Question] = {}
    history: dict[str, list[str]] = {}
    trace = []
    for item in plan.items:
        t_item = time.time()
        print(f"\n[item {item.item_id}] {item.qtype} | {item.topic}")
        hist = history.setdefault(item.item_id, [])
        # 검색어 = 교안 원래 제목들 (교안 언어 그대로, 최대 max_source_titles개). Bloom 수준은 검색과 무관해 넣지 않는다
        queries, warns = search_queries(item.topic, item.source_titles, chunks,
                                        cfg.get("max_source_titles") or MAX_SOURCE_TITLES)
        for w in warns:
            print(f"  [retrieval] {w}")
        print(f"  [retrieval] 검색어: {queries}")
        ctx = retriever.search_many(queries, k=cfg["retrieval_top_k"])
        q = agents.generator(item, ctx, profile, past[:3000])
        regens = 0
        for attempt in range(cfg["max_revisions"] + 1):
            rule_issues = checks.run(q, item, ctx)
            if rule_issues:
                print(f"  attempt {attempt}: 규칙 위반 {rule_issues}")
                hist.append(f"규칙위반({len(rule_issues)})")
                trace.append({"item": item.item_id, "attempt": attempt, "rule_issues": rule_issues, "question": q.model_dump()})
                q = agents.generator(item, ctx, profile, past[:3000], prev=q, feedback="\n".join(rule_issues))
                continue
            s = agents.solver(q, ctx)
            r = agents.reviewer(q, s, item, ctx, profile)
            print(f"  attempt {attempt}: solver={s.answer[:40]!r} (conf {s.confidence:.2f}, 모호 {s.is_ambiguous}) "
                  f"→ {r.verdict} / {r.answer_match}")
            hist.append(f"{r.verdict}({r.answer_match})")
            trace.append({"item": item.item_id, "attempt": attempt, "question": q.model_dump(),
                          "solver": s.model_dump(), "review": r.model_dump()})
            if r.verdict == "pass":
                accepted[item.item_id] = q
                break
            if r.verdict == "reject" and regens < cfg["max_regenerations"]:
                regens += 1
                q = agents.generator(item, ctx, profile, past[:3000], seed=regens)
                continue
            if r.verdict == "reject":
                break
            q = agents.generator(item, ctx, profile, past[:3000], prev=q, feedback=r.feedback + "\n" + "\n".join(r.issues))
        if item.item_id not in accepted:
            hist.append("실패")
            print("  ✗ 검증 실패 — 시험지에서 제외")
        item_sec[item.item_id] = round(time.time() - t_item, 1)
        print(f"  소요 {item_sec[item.item_id]}s")
    phase_sec["items"] = round(time.time() - t_phase, 1)

    # 4) 저장/렌더
    (out / "exam.json").write_text(json.dumps({k: v.model_dump() for k, v in accepted.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "exam.md").write_text(render_exam(profile.course, plan, accepted), encoding="utf-8")
    (out / "answers.md").write_text(render_answers(profile.course, plan, accepted, history), encoding="utf-8")
    summary = {**llm.stats(), "accepted": len(accepted), "planned": len(plan.items), "sec": round(time.time() - t0, 1),
               "phase_sec": phase_sec, "item_sec": item_sec}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] {summary}\n→ {out}")
    return out
