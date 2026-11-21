from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from . import llm

if TYPE_CHECKING:
    from .exam_profile import AnalystInput
from .ingest import format_chunks
from .schemas import Chunk, ExamPlan, ExamProfile, PlannedItem, Question, Review, SolverOutput


def analyst(course: str, inp: "AnalystInput") -> ExamProfile:
    """inp: exam_profile.build_input() 결과 (번호 붙인 기출·메모 + 이미지)."""
    p = llm.render_prompt("analyst", course=course, past_exams=inp.past_text or "(없음)",
                          notes=inp.notes_text or "(없음)", images=inp.image_list)
    return llm.call("analyst", p, ExamProfile, images=inp.images or None)


def type_counts(ratio: dict[str, float], n: int) -> dict[str, int]:
    """format_ratio를 정수 문항 수로 (최대 잉여법). Planner가 비율을 정확히 지키도록 코드에서 계산."""
    total = sum(ratio.values()) or 1
    raw = {k: v / total * n for k, v in ratio.items() if v > 0}
    counts = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: -(raw[k] - counts[k]))[: n - sum(counts.values())]:
        counts[k] += 1
    return {k: v for k, v in counts.items() if v > 0}


PLAN_RETRIES = 2  # 계획이 문항 수·유형 수를 어기면 다시 요청하는 횟수


class PlanError(ValueError):
    """다시 요청해도 planner가 문항 수·유형 수를 지키지 못함."""


def plan_issues(plan: ExamPlan, counts: dict[str, int], n: int) -> list[str]:
    """계획이 정해진 문항 수·유형별 문항 수를 지키는지 코드로 검사한다 (M3 완료 기준: 유형 비율 = 프로필)."""
    issues = []
    if len(plan.items) != n:
        issues.append(f"문항이 {len(plan.items)}개다. 정확히 {n}개여야 한다.")
    got = dict(Counter(i.qtype for i in plan.items))
    if got != counts:
        issues.append(f"유형별 문항 수가 {got}이다. 정확히 {counts}여야 한다.")
    ids = [i.item_id for i in plan.items]
    if len(set(ids)) != len(ids):
        issues.append(f"item_id가 겹친다: {ids}. q1, q2, ... 처럼 모두 달라야 한다.")
    return issues


def planner(profile: ExamProfile, topics: list[str], n: int, max_titles: int = 3) -> ExamPlan:
    counts = type_counts(profile.format_ratio, n)
    base = llm.render_prompt("planner", profile=profile.model_dump(), topics="\n".join(f"- {t}" for t in topics),
                             counts=counts, n=str(n), max_titles=str(max_titles))
    p = base
    for attempt in range(PLAN_RETRIES + 1):
        plan = llm.call("planner", p, ExamPlan)
        issues = plan_issues(plan, counts, n)
        if not issues:
            return plan
        print(f"  [planner] {attempt + 1}번째 계획이 조건과 다름: {issues}")
        p = (base + "\n\n## 이전 계획의 문제 (반드시 고칠 것)\n" + "\n".join(f"- {s}" for s in issues)
             + f"\n\n이전 계획:\n{plan.model_dump_json(indent=1)}")
    raise PlanError(f"planner가 {PLAN_RETRIES + 1}번 모두 조건을 지키지 못함: {issues}")


def generator(item: PlannedItem, chunks: list[Chunk], profile: ExamProfile, examples: str,
              prev: Question | None = None, feedback: str | None = None, seed: int = 0) -> Question:
    revise = ""
    if prev is not None:
        revise = f"## 수정 모드\n이전 문항:\n{prev.model_dump_json(indent=1)}\n\n수정 지시:\n{feedback}\n위 지시를 반영해 문항을 고쳐라."
    p = llm.render_prompt("generator", item=item.model_dump(), chunks=format_chunks(chunks),
                          profile=profile.model_dump(include={"difficulty", "detail_level", "phrasing_examples", "recurring_patterns"}),
                          examples=examples or "(없음)", revise=revise)
    q = llm.call("generator", p, Question, seed=seed)
    q.item_id, q.qtype = item.item_id, item.qtype
    return q


def strip_answer(q: Question) -> dict:
    """Solver에게는 정답 관련 필드를 코드에서 제거해 전달."""
    return q.model_dump(include={"item_id", "qtype", "stem", "choices"})


def solver(q: Question, chunks: list[Chunk]) -> SolverOutput:
    p = llm.render_prompt("solver", question=strip_answer(q), chunks=format_chunks(chunks))
    s = llm.call("solver", p, SolverOutput)
    s.item_id = q.item_id
    return s


def reviewer(q: Question, s: SolverOutput, item: PlannedItem, chunks: list[Chunk], profile: ExamProfile) -> Review:
    p = llm.render_prompt("reviewer", question=q.model_dump(), solver=s.model_dump(), item=item.model_dump(),
                          chunks=format_chunks(chunks),
                          profile=profile.model_dump(include={"difficulty", "detail_level", "phrasing_examples"}))
    r = llm.call("reviewer", p, Review)
    r.item_id = q.item_id
    return r
