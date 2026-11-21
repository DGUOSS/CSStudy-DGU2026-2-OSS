from __future__ import annotations

from .schemas import ExamPlan, Question


def render_exam(course: str, plan: ExamPlan, questions: dict[str, Question]) -> str:
    pts = {i.item_id: i.points for i in plan.items}
    out = [f"# {course} 모의고사\n"]
    n = 0
    for item in plan.items:
        q = questions.get(item.item_id)
        if not q:
            continue
        n += 1
        out.append(f"**{n}.** ({q.qtype}, {pts[item.item_id]}점) {q.stem}\n")
        for j, c in enumerate(q.choices or [], 1):
            out.append(f"   {j}) {c}")
        out.append("")
    return "\n".join(out)


def render_answers(course: str, plan: ExamPlan, questions: dict[str, Question], history: dict[str, list],
                   code_checks: dict[str, str] | None = None, variants: dict[str, str] | None = None) -> str:
    out = [f"# {course} 모의고사 — 정답 및 채점 기준\n"]
    n = 0
    for item in plan.items:
        q = questions.get(item.item_id)
        if not q:
            out.append(f"- ~~{item.item_id} ({item.topic})~~ — 검증 실패로 제외\n")
            continue
        n += 1
        out.append(f"## {n}. [{q.qtype}] {item.topic}")
        out.append(f"- **정답**: {q.answer}")
        if q.model_answer:
            out.append(f"- **모범답안**: {q.model_answer}")
        if q.rubric:
            out.append("- **채점 기준**:\n" + "\n".join(f"  - {r}" for r in q.rubric))
        out.append("- **근거**: " + ", ".join(f"{s.file} p.{s.page}" for s in q.sources))
        if variants and variants.get(item.item_id):
            out.append(f"- **기출 변형**: {variants[item.item_id]} (시험당 허용 개수 안에서 통과)")
        if code_checks and code_checks.get(item.item_id):
            out.append(f"- **코드 검산**: {code_checks[item.item_id]}")
        out.append(f"- **검증 이력**: {' → '.join(history.get(item.item_id, []))}\n")
    return "\n".join(out)


def _short(text: str, n: int = 220) -> str:
    t = " ".join(str(text).split())
    return t if len(t) <= n else t[:n] + "…"


def render_report(course: str, plan: ExamPlan, questions: dict[str, Question], trace: list[dict],
                  summary: dict) -> str:
    """실행 보고서 (명세 §3 outputs의 report.md): 요약 + 문항별 시도마다 규칙 위반·코드 검산·풀이·검토·수정 이유.
    trace.json을 사람이 읽을 수 있게 펼친 것. '루프에서 실제로 수정된 사례'(M4 완료 기준)를 여기서 본다."""
    tc = summary.get("type_counts", {})
    out = [f"# {course} — 실행 보고서\n",
           "| 항목 | 값 |", "|---|---|",
           f"| 검증 | {'함' if summary.get('verify', True) else '안 함 (--no-verify)'} |",
           f"| 통과 | {summary.get('accepted')} / 계획 {summary.get('planned')}문항 |",
           f"| 유형 (목표 / 계획 / 통과) | {tc.get('target')} / {tc.get('planned')} / {tc.get('accepted')} |",
           f"| 시간 | {summary.get('sec')}초 |",
           f"| 모델 호출 / 토큰 | {summary.get('api_calls')} / {summary.get('tokens'):,} |" if summary.get("tokens") is not None
           else f"| 모델 호출 | {summary.get('api_calls')} |"]
    reps = summary.get("replacements") or []
    if reps:
        out.append("| 보충 | " + ", ".join(f"{r['failed']} → {r['replacement']} ({r['topic']})" for r in reps) + " |")
    pv = summary.get("past_variants") or {}
    out.append(f"| 기출 변형 허용 | {len(pv)} / {summary.get('past_variant_limit', 0)}개"
               + (": " + ", ".join(f"{k} ({v})" for k, v in pv.items()) if pv else "") + " |")
    revised = sum(1 for i in plan.items if sum(1 for t in trace if t["item"] == i.item_id) > 1)
    out.append(f"| 수정·재생성이 있었던 문항 | {revised}개 |\n")

    for item in plan.items:
        steps = [t for t in trace if t["item"] == item.item_id]
        mark = "통과" if item.item_id in questions else "**제외**"
        if item.item_id in (summary.get("past_variants") or {}):
            mark += " (기출 변형)"
        out.append(f"## {item.item_id} [{item.qtype}] {item.topic} — {mark} (시도 {len(steps)}번)")
        for t in steps:
            cc = t.get("code_check") or {}
            cc_s = "".join([f", 검산 맞음 {len(cc['passed'])}" if cc.get("passed") else "",
                            f", 검산 틀림 {len(cc['issues'])}" if cc.get("issues") else "",
                            f", 검산 못 읽음 {len(cc['unreadable'])}" if cc.get("unreadable") else ""])
            if t.get("rule_issues") is not None and "review" not in t:
                head = "규칙 위반" if t["rule_issues"] else "규칙 통과"
                out.append(f"- **시도 {t['attempt']}**: {head}{cc_s}")
                out += [f"  - {_short(i)}" for i in t["rule_issues"]]
                continue
            s, r = t["solver"], t["review"]
            out.append(f"- **시도 {t['attempt']}**: {r['verdict']} / {r['answer_match']}{cc_s} — "
                       f"풀이자 확신도 {s['confidence']:.2f}{', 모호 표시' if s['is_ambiguous'] else ''}")
            if r.get("past_comparison"):
                out.append(f"  - 기출 비교: {_short(r['past_comparison'], 300)}")
            out += [f"  - {_short(i)}" for i in r.get("issues", [])]
            if r["verdict"] != "pass" and r.get("feedback"):
                out.append(f"  - → 수정 지시: {_short(r['feedback'])}")
        out.append("")
    return "\n".join(out)
