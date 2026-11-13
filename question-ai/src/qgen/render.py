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


def render_answers(course: str, plan: ExamPlan, questions: dict[str, Question], history: dict[str, list]) -> str:
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
        out.append(f"- **검증 이력**: {' → '.join(history.get(item.item_id, []))}\n")
    return "\n".join(out)
