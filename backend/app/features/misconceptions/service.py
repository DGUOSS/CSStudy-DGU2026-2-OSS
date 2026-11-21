"""오개념 붙이기: 객관식 문제의 틀린 보기마다 '왜 골랐을까'를 Claude로 한 번 만들어 저장한다.

- 객관식이 DB에 저장되면 어디서 들어왔든(자동 보충, 관리자, 시드) 커밋 직후 뒤에서 자동으로 붙인다
  (_collect_new_mcq / _attach_after_commit). 문제를 저장하는 쪽은 오개념을 몰라도 된다.
- 빠진 것 채우기: 시험지를 만들 때 그 시험지의 객관식(ensure_for), 서버를 켤 때 전체(backfill).
- 학생이 풀 때는 저장된 것을 꺼내기만 한다(visible_for). API를 부르지 않는다.
"""

import logging
import re
import threading

from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession
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
    question, choices, answer_index, explanation = (
        p.question,
        list(p.choices),
        p.answer_index,
        p.explanation,
    )
    # AI 응답을 기다리는 동안(수십 초) DB 연결을 붙잡고 있지 않게 트랜잭션을 끝내 연결을 돌려준다.
    # 끝나고 다시 쓸 때는 새 연결을 받는다(연결이 끊겨도 다시 연결).
    session.commit()
    drafts = llm.draft_misconceptions(question, choices, answer_index, explanation, text, labels)
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


# ---------- 자동으로 붙이기 ----------

_attach_lock = threading.Lock()  # 같은 문제를 두 스레드가 동시에 만들지 않게(한 번에 하나씩)
BACKFILL_LIMIT = 40  # 서버를 켤 때 한 번에 채우는 최대 문제 수


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def missing_mcq_ids(
    session: Session, problem_ids: list[int] | None = None, limit: int | None = None
) -> list[int]:
    """오개념이 하나도 없는 객관식. problem_ids를 주면 그 안에서만."""
    q = select(Problem.id).where(
        Problem.qtype == "mcq", Problem.id.not_in(select(Misconception.problem_id))
    )  # type: ignore[union-attr]
    if problem_ids is not None:
        q = q.where(Problem.id.in_(problem_ids))  # type: ignore[union-attr]
    q = q.order_by(Problem.id)
    if limit:
        q = q.limit(limit)
    return list(session.exec(q).all())


def _run(bind, ids: list[int]) -> None:
    with _attach_lock:
        try:
            with Session(bind) as s:
                todo = missing_mcq_ids(s, ids)
                n = attach_misconceptions(s, todo) if todo else 0
            if todo:
                log.info("문제 %d개에 오개념 %d개를 붙임", len(todo), n)
        except llm.LLMNotConfigured:
            pass
        except Exception:
            log.exception("오개념 자동 생성 실패: %s", ids)


def spawn(bind, ids: list[int]) -> None:
    """테스트에서는 바꿔 끼워 같은 스레드에서 돌린다."""
    threading.Thread(target=_run, args=(bind, ids), daemon=True).start()


def ensure_for(bind, problem_ids: list[int]) -> None:
    """이 문제들 중 오개념이 빠진 객관식을 뒤에서 채운다(예: 시험지를 만들 때)."""
    if enabled() and problem_ids:
        spawn(bind, list(problem_ids))


def backfill(bind) -> None:
    """서버를 켤 때: 오개념이 없는 객관식을 BACKFILL_LIMIT개까지 채운다."""
    with Session(bind) as s:
        ids = missing_mcq_ids(s, limit=BACKFILL_LIMIT)
    if ids:
        _run(bind, ids)


@event.listens_for(OrmSession, "after_flush")
def _collect_new_mcq(session, _ctx) -> None:
    new = [o.id for o in session.new if isinstance(o, Problem) and o.qtype == "mcq" and o.id]
    if new:
        session.info.setdefault("new_mcq_ids", set()).update(new)


@event.listens_for(OrmSession, "after_rollback")
def _forget_mcq(session) -> None:
    session.info.pop("new_mcq_ids", None)


@event.listens_for(OrmSession, "after_commit")
def _attach_after_commit(session) -> None:
    ids = session.info.pop("new_mcq_ids", None)
    if ids and enabled():
        spawn(session.get_bind(), sorted(ids))
