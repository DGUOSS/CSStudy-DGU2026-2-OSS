from __future__ import annotations

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


def planner(profile: ExamProfile, topics: list[str], n: int, max_titles: int = 3) -> ExamPlan:
    counts = type_counts(profile.format_ratio, n)
    p = llm.render_prompt("planner", profile=profile.model_dump(), topics="\n".join(f"- {t}" for t in topics),
                          counts=counts, n=str(n), max_titles=str(max_titles))
    return llm.call("planner", p, ExamPlan)


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
