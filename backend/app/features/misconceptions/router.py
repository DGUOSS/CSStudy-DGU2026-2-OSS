"""관리자: 강좌 문제에 오개념 만들기(백그라운드), 진행 상황, 목록 확인, 숨기기."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import SessionDep
from app.core.security import AdminUser
from app.features.courses.router import get_course_or_404
from app.features.misconceptions.service import attach_misconceptions, missing_problem_ids
from app.models import Chapter, Misconception, Problem
from app.services import llm

router = APIRouter(prefix="/admin", tags=["misconceptions"])

# 강좌별 진행 상황(서버 메모리). 서버를 다시 켜면 사라지지만, 다시 누르면 남은 것만 이어서 만든다.
_jobs: dict[int, dict] = {}


class JobOut(BaseModel):
    running: bool
    total: int
    done: int
    failed: int
    error: str | None
    problems: int  # 강좌의 객관식 문제 수
    covered: int  # 오개념이 붙은 문제 수
    misconceptions: int  # 저장된 오개념 수


class MisconceptionAdminOut(BaseModel):
    id: int
    problem_id: int
    question: str
    choice: str
    label: str
    hypothesis: str
    explanation: str
    evidence: str | None
    evidence_found: bool
    status: str
    created_at: datetime


class StatusIn(BaseModel):
    status: Literal["auto", "hidden", "approved"]


def _counts(session: Session, course_id: int) -> tuple[int, int, int]:
    mcq = session.exec(
        select(Problem.id)
        .join(Chapter, Chapter.id == Problem.chapter_id)
        .where(Chapter.course_id == course_id, Problem.qtype == "mcq")
    ).all()
    rows = session.exec(
        select(Misconception.problem_id).where(Misconception.problem_id.in_(mcq))
    ).all()  # type: ignore[attr-defined]
    return len(mcq), len(set(rows)), len(rows)


def _job_out(session: Session, course_id: int) -> JobOut:
    j = _jobs.get(course_id, {"running": False, "total": 0, "done": 0, "failed": 0, "error": None})
    problems, covered, n = _counts(session, course_id)
    return JobOut(**j, problems=problems, covered=covered, misconceptions=n)


def _run(bind, course_id: int, ids: list[int]) -> None:
    job = _jobs[course_id]
    try:
        with Session(bind) as s:
            attach_misconceptions(s, ids, progress=job)
    except llm.LLMNotConfigured as e:
        job["error"] = str(e)
    finally:
        job["running"] = False


@router.post("/courses/{course_id}/misconceptions/generate")
def generate(
    course_id: int, background: BackgroundTasks, session: SessionDep, _: AdminUser
) -> JobOut:
    """오개념이 없는 객관식 문제에 붙인다. 문제당 수 초, 백그라운드로 돈다."""
    get_course_or_404(session, course_id)
    if _jobs.get(course_id, {}).get("running"):
        return _job_out(session, course_id)
    ids = missing_problem_ids(session, course_id)
    _jobs[course_id] = {
        "running": bool(ids),
        "total": len(ids),
        "done": 0,
        "failed": 0,
        "error": None,
    }
    if ids:
        background.add_task(_run, session.get_bind(), course_id, ids)
    return _job_out(session, course_id)


@router.get("/courses/{course_id}/misconceptions/status")
def job_status(course_id: int, session: SessionDep, _: AdminUser) -> JobOut:
    get_course_or_404(session, course_id)
    return _job_out(session, course_id)


@router.get("/courses/{course_id}/misconceptions")
def list_misconceptions(
    course_id: int, session: SessionDep, _: AdminUser
) -> list[MisconceptionAdminOut]:
    rows = session.exec(
        select(Misconception, Problem)
        .join(Problem, Problem.id == Misconception.problem_id)
        .join(Chapter, Chapter.id == Problem.chapter_id)
        .where(Chapter.course_id == course_id)
        .order_by(Problem.id, Misconception.wrong_choice_index)
    ).all()
    return [
        MisconceptionAdminOut(
            id=m.id,
            problem_id=p.id,
            question=p.question,
            choice=p.choices[m.wrong_choice_index] if m.wrong_choice_index < len(p.choices) else "",
            label=m.label,
            hypothesis=m.hypothesis,
            explanation=m.explanation,
            evidence=m.evidence,
            evidence_found=m.evidence_found,
            status=m.status,
            created_at=m.created_at,
        )
        for m, p in rows
    ]


@router.patch("/misconceptions/{misconception_id}")
def set_status(
    misconception_id: int, body: StatusIn, session: SessionDep, _: AdminUser
) -> MisconceptionAdminOut:
    m = session.get(Misconception, misconception_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "오개념이 없습니다")
    m.status = body.status
    session.add(m)
    session.commit()
    p = session.get(Problem, m.problem_id)
    return MisconceptionAdminOut(
        id=m.id,
        problem_id=p.id,
        question=p.question,
        choice=p.choices[m.wrong_choice_index],
        label=m.label,
        hypothesis=m.hypothesis,
        explanation=m.explanation,
        evidence=m.evidence,
        evidence_found=m.evidence_found,
        status=m.status,
        created_at=m.created_at,
    )
