from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from . import agents, checks, exam_profile, llm
from . import verify as verify_mod  # run()의 verify 인자와 이름이 겹치지 않게
from .ingest import MAX_SOURCE_TITLES, Retriever, load_chunks, load_text_dir, search_queries, topic_list
from .render import render_answers, render_exam, render_report
from .schemas import ExamPlan, PlannedItem, Question

ROOT = llm.ROOT


def _check_summary(vr: "verify_mod.VerifyResult") -> str:
    parts = []
    if vr.passed:
        parts.append(f"맞음 {len(vr.passed)}개")
    if vr.issues:
        parts.append(f"틀림 {len(vr.issues)}개")
    if vr.unreadable:
        parts.append(f"읽지 못함 {len(vr.unreadable)}개 ({'; '.join(vr.unreadable)})")
    return ", ".join(parts)


def run(course: str, run_id: str | None = None, new_profile: bool = False, use_cache: bool = True, seed: int = 0,
        verify: bool = True) -> Path:
    """verify=False: 문항마다 generator 1번만 부르고 검증(solver·reviewer·수정) 없이 시험지를 만든다.
    M3 완료 기준 확인용이자 M5 실험의 single 조건(베이스라인). 규칙 검사는 비용이 없어 결과만 기록한다."""
    cfg = llm.CFG["pipeline"]
    course_dir = ROOT / "data" / course
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    out = ROOT / "outputs" / course / run_id
    out.mkdir(parents=True, exist_ok=True)
    llm.configure(log_path=out / "logs.jsonl", use_cache=use_cache, seed_base=seed)  # seed: 실험 세트 번호
    t0 = time.time()

    chunks = load_chunks(course_dir)
    if not chunks:
        raise SystemExit(f"{course_dir/'lectures'}에 강의자료(.pdf/.md/.txt)가 없습니다.")
    retriever = Retriever(chunks)
    past = load_text_dir(course_dir / "past_exams")  # 기출 문항 목록이 없는 예전 프로필용 (글자 기출 앞 3000자)
    print(f"[ingest] 강의자료 청크 {len(chunks)}개, 기출 {len(past)}자")
    phase_sec: dict[str, float] = {"ingest": round(time.time() - t0, 1)}
    t_phase = time.time()

    # 1) Analyst — 과목 공용 profile.json (사용자가 직접 수정 가능, 있으면 재사용). 기출·메모가 없으면 기본 프로필
    profile = exam_profile.load_or_make(course_dir, course, new=new_profile)
    past_inp = exam_profile.build_input(course_dir)  # 기출 원문 줄·이미지 (past_items 원문을 잘라 올 때)
    # 베끼기 검사 대상: 기출 문항 전부 (참고로 준 문항만이 아니라)
    past_texts = [(f"{p.number}번", exam_profile.past_item_text(p, past_inp)) for p in profile.past_items]
    copy_threshold = cfg.get("copy_threshold", checks.COPY_THRESHOLD)
    if profile.past_items:
        print(f"[analyst] 기출 문항 {len(profile.past_items)}개: "
              + ", ".join(f"{p.item_id}={p.number}번 {p.qtype}" for p in profile.past_items))
    elif past:
        print("[analyst] 프로필에 기출 문항 목록이 없음 → 기출 앞 3000자를 예시로 씀 (--new-profile로 다시 만들면 문항별로 씀)")
    (out / "profile.json").write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    phase_sec["analyst"] = round(time.time() - t_phase, 1)
    t_phase = time.time()

    # 2) Planner
    n = cfg.get("num_questions_override") or profile.num_questions
    plan_f = out / "plan.json"
    counts = agents.type_counts(profile.format_ratio, n)
    if plan_f.exists():
        plan = ExamPlan.model_validate_json(plan_f.read_text(encoding="utf-8"))
        # 사용자가 고친 계획일 수 있어 다시 만들지 않고 알리기만 한다
        for w in agents.plan_issues(plan, counts, n):
            print(f"[planner] 경고(저장된 plan.json): {w}")
    else:
        plan = agents.planner(profile, topic_list(chunks), n, cfg.get("max_source_titles") or MAX_SOURCE_TITLES)
        plan_f.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    print(f"[planner] {len(plan.items)}문항: " + ", ".join(f"{i.qtype}/{i.topic}" for i in plan.items))
    phase_sec["planner"] = round(time.time() - t_phase, 1)
    t_phase = time.time()
    item_sec: dict[str, float] = {}

    # 3) 문항별 생성 → 규칙검사 → 블라인드 풀이 → 검토 → 수정 루프
    accepted: dict[str, Question] = {}
    code_checks: dict[str, str] = {}  # 문항 → 코드 검산 요약 (answers.md)
    # "지엽적" 검색 규칙 (명세 §5, M3): 더 많이 검색하고, 앞 문항이 이미 근거로 쓴 쪽은 뺀다
    detail = profile.detail_level == "지엽적"
    top_k = cfg["retrieval_top_k"] * (cfg.get("detail_top_k_factor", 2) if detail else 1)
    reuse_limit = cfg.get("detail_reuse_limit", 1)
    used_pages: Counter[tuple[str, int]] = Counter()  # 통과한 문항들의 근거 쪽 (파일, 쪽) → 횟수
    if detail:
        print(f"[retrieval] 지엽적 출제: 검색 {top_k}쪽, 앞 문항이 {reuse_limit}번 이상 쓴 쪽은 제외")
    history: dict[str, list[str]] = {}
    trace = []
    fail_reason: dict[str, str] = {}
    # 기출 변형 허용 (2026-11-21 결정, 문제사항 V-11): 기출과 같은 질문(숫자만 바꾼 것 포함)도 시험 문항 수의
    # past_variant_ratio(25%)까지는 통과시킨다. 실제 시험도 기출 일부를 바꿔 다시 내고, 모양이 정해진 단원(카르노 맵 등)은
    # 같은 질문을 피하기 어려워 3번 모두 떨어졌기 때문. 선착순이며, 다 쓰면 예전처럼 수정 요청
    variant_limit = int(n * cfg.get("past_variant_ratio", 0.25))
    same_ratio = cfg.get("past_same_ratio", 0.5)
    variants: dict[str, str] = {}  # 문항 → 허용 사유

    def process(item: PlannedItem) -> bool:
        """문항 하나: 검색 → 생성 → (검증 루프) → 통과하면 True."""
        t_item = time.time()
        print(f"\n[item {item.item_id}] {item.qtype} | {item.topic}")
        hist = history.setdefault(item.item_id, [])
        # 검색어 = 교안 원래 제목들 (교안 언어 그대로, 최대 max_source_titles개). Bloom 수준은 검색과 무관해 넣지 않는다
        queries, warns = search_queries(item.topic, item.source_titles, chunks,
                                        cfg.get("max_source_titles") or MAX_SOURCE_TITLES)
        for w in warns:
            print(f"  [retrieval] {w}")
        print(f"  [retrieval] 검색어: {queries}")
        exclude = None
        if detail:
            exclude = {c.chunk_id for c in chunks if used_pages[(c.source.file, c.source.page)] >= reuse_limit}
            if exclude:
                print(f"  [retrieval] 앞 문항이 쓴 청크 {len(exclude)}개 제외")
        ctx = retriever.search_many(queries, k=top_k, exclude=exclude)
        # 기출 예시: planner가 고른 기출 문항(없으면 같은 유형) 원문 1~2개. 문항 목록이 없는 예전 프로필은 앞 3000자
        if profile.past_items:
            chosen, warns = exam_profile.select_past_items(item, profile)
            for w in warns:
                print(f"  [past] {w}")
            examples, ex_images = exam_profile.format_past_examples(chosen, past_inp)
            past_names = [f"{p.number}번" for p in chosen]
            print(f"  [past] 기출 예시: {[f'{p.number}번' for p in chosen] or '없음'}"
                  + (f" (이미지 {len(ex_images)}장)" if ex_images else ""))
        else:
            examples, ex_images, past_names = past[:3000], [], []
        q = agents.generator(item, ctx, profile, examples, images=ex_images)
        if not verify:
            vr = verify_mod.run(q)
            code_checks[item.item_id] = _check_summary(vr)
            rule_issues = checks.run(q, item, ctx) + checks.copy_issues(q, past_texts, copy_threshold) + vr.issues
            if rule_issues:
                print(f"  규칙 위반(검증 안 함, 기록만): {rule_issues}")
            hist.append(f"검증 안 함, 규칙위반 {len(rule_issues)}개" if rule_issues else "검증 안 함")
            trace.append({"item": item.item_id, "attempt": 0, "rule_issues": rule_issues, "question": q.model_dump(),
                          "code_check": vr.__dict__})
            accepted[item.item_id] = q
            used_pages.update({(s.file, s.page) for s in q.sources})
            item_sec[item.item_id] = round(time.time() - t_item, 1)
            print(f"  소요 {item_sec[item.item_id]}s")
            return True
        regens = 0
        prev_issues: list[str] = []  # 직전 검토의 지적 (수정한 문항을 다시 검토할 때 전달, 문제사항 V-04)
        for attempt in range(cfg["max_revisions"] + 1):
            # 마지막 시도에서는 고쳐도 다시 검사할 기회가 없으므로 generator를 부르지 않는다 (실패 문항마다 약 12초·9천 토큰 낭비였음)
            last = attempt == cfg["max_revisions"]
            vr = verify_mod.run(q)
            code_checks[item.item_id] = _check_summary(vr)
            copy_rule = checks.copy_issues(q, past_texts, copy_threshold)
            budget_left = len(variants) < variant_limit
            # 기출 문장 겹침은 허용 개수가 남아 있으면 막지 않고 검증을 계속한다 (통과하면 기출 변형으로 셈)
            rule_issues = checks.run(q, item, ctx) + vr.issues + ([] if budget_left else copy_rule)
            if copy_rule and budget_left:
                print(f"  attempt {attempt}: 기출 문장 겹침 — 허용 개수({len(variants)}/{variant_limit}) 안이라 검증 계속")
            if rule_issues:
                print(f"  attempt {attempt}: 규칙 위반 {rule_issues}")
                hist.append(f"규칙위반({len(rule_issues)})")
                trace.append({"item": item.item_id, "attempt": attempt, "rule_issues": rule_issues, "question": q.model_dump(),
                              "code_check": vr.__dict__})
                if last:
                    break
                q = agents.generator(item, ctx, profile, examples, images=ex_images, prev=q, feedback="\n".join(rule_issues))
                continue
            s = agents.solver(q, ctx)
            r = agents.reviewer(q, s, item, ctx, profile, past_examples=examples if profile.past_items else "",
                                verified=vr.passed, prev_issues=prev_issues)
            print(f"  attempt {attempt}: solver={s.answer[:40]!r} (conf {s.confidence:.2f}, 모호 {s.is_ambiguous}) "
                  f"→ {r.verdict} / {r.answer_match}")
            hist.append(f"{r.verdict}({r.answer_match})")
            trace.append({"item": item.item_id, "attempt": attempt, "question": q.model_dump(),
                          "solver": s.model_dump(), "review": r.model_dump(), "code_check": vr.__dict__})
            same = r.past_total > 0 and r.past_same / r.past_total >= same_ratio
            feedback = r.feedback + "\n" + "\n".join(r.issues)
            if r.verdict == "pass" and (same or copy_rule):
                why = ", ".join([f"소문항 {r.past_same}/{r.past_total} 같음" if same else "",
                                 f"문장 겹침 ({copy_rule[0].split(' (')[0]})" if copy_rule else ""]).strip(", ")
                if len(variants) < variant_limit:
                    variants[item.item_id] = f"기출 {', '.join(past_names)} 변형 — {why}" if past_names else f"기출 변형 — {why}"
                    hist.append(f"기출 변형 허용 ({len(variants)}/{variant_limit})")
                    print(f"  → 기출과 같은 질문이지만 허용 개수 안 ({len(variants)}/{variant_limit}) — 통과: {why}")
                    accepted[item.item_id] = q
                    break
                # 허용 개수를 다 썼으면 예전처럼 다른 과제로 고치게 한다
                print(f"  → 기출과 같은 질문, 허용 개수({variant_limit}) 다 씀 — 수정 요청: {why}")
                hist[-1] = f"revise(기출 변형 허용 개수 초과: {why})"
                feedback = (f"기출과 같은 질문이다 ({why}). 이 시험의 기출 변형 허용 개수({variant_limit}개)를 이미 썼으므로 "
                            f"같은 소문항을 기출과 다른 과제로 바꿔라.\n{r.past_comparison}\n" + feedback)
                if last:
                    break
                prev_issues = r.issues
                q = agents.generator(item, ctx, profile, examples, images=ex_images, prev=q, feedback=feedback)
                continue
            if r.verdict == "pass":
                accepted[item.item_id] = q
                break
            if last:
                break
            if r.verdict == "reject" and regens < cfg["max_regenerations"]:
                regens += 1
                prev_issues = []  # 새로 만든 문항은 이전 지적과 무관
                q = agents.generator(item, ctx, profile, examples, images=ex_images, seed=regens)
                continue
            if r.verdict == "reject":
                break
            prev_issues = r.issues
            q = agents.generator(item, ctx, profile, examples, images=ex_images, prev=q, feedback=feedback)
        if item.item_id not in accepted:
            hist.append("실패")
            print("  ✗ 검증 실패 — 시험지에서 제외")
            last_t = next((t for t in reversed(trace) if t["item"] == item.item_id), {})
            fail_reason[item.item_id] = "; ".join(
                (last_t.get("review") or {}).get("issues") or last_t.get("rule_issues") or ["검증 실패"])[:800]
        else:
            used_pages.update({(s.file, s.page) for s in accepted[item.item_id].sources})
        item_sec[item.item_id] = round(time.time() - t_item, 1)
        print(f"  소요 {item_sec[item.item_id]}s")
        return item.item_id in accepted

    # 검증에서 실패한 문항은 같은 유형·다른 주제로 다시 계획해 보충한다 (문제사항 V-07). 보충 문항이 또 실패하면 그대로 둔다
    max_rep = cfg.get("max_replacements", 1) if verify else 0
    queue = list(plan.items)
    final_items: list[PlannedItem] = []
    replacements: list[dict] = []
    while queue:
        item = queue.pop(0)
        final_items.append(item)
        if process(item) or "-r" in item.item_id or max_rep <= 0:
            continue
        avoid = list(dict.fromkeys(i.topic for i in [*plan.items, *final_items]))
        try:
            used_titles = [t for i in [*plan.items, *final_items] if i.item_id != item.item_id for t in i.source_titles]
            new = agents.replan_item(profile, topic_list(chunks), item, fail_reason.get(item.item_id, ""), avoid,
                                     cfg.get("max_source_titles") or MAX_SOURCE_TITLES, used_titles=used_titles)
        except agents.PlanError as e:
            print(f"  [planner] 보충 계획 실패: {e}")
            continue
        replacements.append({"failed": item.item_id, "replacement": new.item_id, "topic": new.topic,
                             "reason": fail_reason.get(item.item_id, "")})
        print(f"  [planner] 보충: {item.item_id} → {new.item_id} {new.qtype} | {new.topic}")
        queue.insert(0, new)
    phase_sec["items"] = round(time.time() - t_phase, 1)

    # 4) 저장/렌더
    (out / "exam.json").write_text(json.dumps({k: v.model_dump() for k, v in accepted.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    final_plan = ExamPlan(items=final_items)
    if replacements:  # plan.json은 다시 실행할 때 쓰므로 그대로 두고, 보충이 들어간 계획은 따로 저장
        (out / "plan_final.json").write_text(final_plan.model_dump_json(indent=2), encoding="utf-8")
    (out / "exam.md").write_text(render_exam(profile.course, final_plan, accepted), encoding="utf-8")
    (out / "answers.md").write_text(render_answers(profile.course, final_plan, accepted, history, code_checks, variants), encoding="utf-8")
    type_counts = {"target": counts, "planned": dict(Counter(i.qtype for i in plan.items)),
                   "accepted": dict(Counter(q.qtype for q in accepted.values()))}
    summary = {**llm.stats(), "accepted": len(accepted), "planned": len(plan.items), "sec": round(time.time() - t0, 1),
               "verify": verify, "type_counts": type_counts, "replacements": replacements,
               "past_variants": variants, "past_variant_limit": variant_limit, "phase_sec": phase_sec, "item_sec": item_sec}
    if (out / "summary.json").exists():  # 같은 --run-id로 다시 돌리면 측정값(시간·호출)이 바뀌므로 직전 기록을 남긴다
        (out / "summary.json").replace(out / "summary.prev.json")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(render_report(profile.course, final_plan, accepted, trace, summary), encoding="utf-8")
    print(f"\n[done] {summary}\n→ {out}")
    return out
