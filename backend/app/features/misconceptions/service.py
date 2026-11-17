"""오개념 붙이기: 객관식 문제의 틀린 보기마다 '왜 골랐을까'를 Claude로 한 번 만들어 저장한다.

- 지금은 관리자가 [오개념 만들기]로 강좌의 기존 문제에 붙인다.
- 문제 생성기를 연결하면 새 문제를 저장한 직후 attach_misconceptions(session, [새 문제 id들])를 부르면 된다.
- 학생이 풀 때는 저장된 것을 꺼내기만 한다(visible_for). API를 부르지 않는다.
"""

import logging
import re

from sqlmodel import Session, select

from app.core.config import settings
from app.models import Chapter, Material, Misconception, Problem
from app.services import llm

log = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def page_text(session: Session, p: Problem) -> str:
    m = session.get(Material, p.source_material_id) if p.source_material_id else None
    if not m or not p.source_page or not 1 <= p.source_page <= len(m.pages):
        return ""
    return m.pages[p.source_page - 1]


def course_labels(session: Session, course_id: int) -> list[str]:
    rows = session.exec(
        select(Misconception.label)
        .join(Problem, Problem.id == Misconception.problem_id)
        .join(Chapter, Chapter.id == Problem.chapter_id)
        .where(Chapter.course_id == course_id)
    ).all()
    return sorted(set(rows))


def missing_problem_ids(session: Session, course_id: int) -> list[int]:
    """오개념이 아직 없는 객관식 문제."""
    done = select(Misconception.problem_id)
    return list(
        session.exec(
            select(Problem.id)
            .join(Chapter, Chapter.id == Problem.chapter_id)
            .where(Chapter.course_id == course_id, Problem.qtype == "mcq", Problem.id.not_in(done))  # type: ignore[union-attr]
            .order_by(Problem.id)
        ).all()
    )


def attach_one(session: Session, p: Problem, labels: list[str]) -> int:
    """문제 하나에 오개념을 붙인다. 붙인 개수를 돌려준다(실패하면 0)."""
    if p.qtype != "mcq":
        return 0
    text = page_text(session, p)
    drafts = llm.draft_misconceptions(
        p.question, p.choices, p.answer_index, p.explanation, text, labels
    )
    if not drafts:
        return 0
    n = 0
    for d in drafts:
        ci = d.choice_no - 1
        if not 0 <= ci < len(p.choices) or ci == p.answer_index:
            continue
        if session.exec(
            select(Misconception).where(
                Misconception.problem_id == p.id, Misconception.wrong_choice_index == ci
            )
        ).first():
            continue
        found = bool(d.evidence) and _norm(d.evidence) in _norm(text)
        session.add(
            Misconception(
                problem_id=p.id,
                wrong_choice_index=ci,
                label=d.label.strip()[:100],
                hypothesis=d.hypothesis,
                explanation=d.explanation,
                evidence=d.evidence or None,
                evidence_found=found,
                source_material_id=p.source_material_id if found else None,
                source_page=p.source_page if found else None,
                model=settings.llm_model,
            )
        )
        if d.label not in labels:
            labels.append(d.label)
        n += 1
    session.commit()
    return n


def attach_misconceptions(
    session: Session, problem_ids: list[int], progress: dict | None = None
) -> int:
    """문제들에 오개념을 붙인다(이미 있는 보기는 건너뜀). progress가 있으면 done/failed를 올린다."""
    total = 0
    labels_by_course: dict[int, list[str]] = {}
    for pid in problem_ids:
        p = session.get(Problem, pid)
        if p is None:
            continue
        course_id = session.get(Chapter, p.chapter_id).course_id
        labels = labels_by_course.setdefault(course_id, course_labels(session, course_id))
        try:
            n = attach_one(session, p, labels)
        except llm.LLMNotConfigured:
            raise
        except Exception:  # 한 문제 실패로 전체를 멈추지 않는다
            log.exception("오개념 생성 실패: problem %s", pid)
            session.rollback()
            n = 0
        total += n
        if progress is not None:
            progress["done"] += 1
            if n == 0:
                progress["failed"] += 1
    return total


def visible_for(session: Session, problem_ids: list[int]) -> dict[tuple[int, int], Misconception]:
    """학생에게 보여 줄 오개념: 근거가 교안에서 확인된 AI 추정, 또는 관리자 확인. 숨긴 것은 뺀다."""
    if not problem_ids:
        return {}
    rows = session.exec(
        select(Misconception).where(Misconception.problem_id.in_(problem_ids))
    ).all()  # type: ignore[attr-defined]
    return {
        (m.problem_id, m.wrong_choice_index): m
        for m in rows
        if m.status == "approved" or (m.status == "auto" and m.evidence_found)
    }
