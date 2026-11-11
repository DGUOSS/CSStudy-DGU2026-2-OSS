"""Admin review of misconception follow-up questions."""

import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import AdminUser
from app.models import Chapter, Course, Material, MisconceptionProbe, Problem, Professor, Subject

router = APIRouter(prefix="/admin/misconception-probes", tags=["admin"])


class ProbeReviewOut(BaseModel):
    id: int
    course_id: int
    course_name: str
    professor_name: str
    problem_question: str
    problem_choices: list[str]
    problem_answer_index: int
    wrong_choice_index: int
    hypothesis: str
    question: str
    choices: list[str]
    answer_index: int
    explanation: str
    evidence: str | None
    source_material_id: int | None
    source_material_title: str | None
    source_page_text: str | None
    available_materials: list["ReviewMaterialOut"]
    source_page: int | None
    status: Literal["draft", "approved"]
    reviewed_at: datetime | None


class ReviewMaterialOut(BaseModel):
    id: int
    title: str
    page_count: int


class ProbeReviewUpdate(BaseModel):
    hypothesis: str = Field(min_length=1)
    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=2)
    answer_index: int
    explanation: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    source_material_id: int
    source_page: int = Field(ge=1)


def _context(session: SessionDep, probe: MisconceptionProbe):
    problem = session.get(Problem, probe.problem_id)
    chapter = session.get(Chapter, problem.chapter_id) if problem else None
    course = session.get(Course, chapter.course_id) if chapter else None
    if not problem or not course:
        raise HTTPException(status.HTTP_409_CONFLICT, "원본 문제 또는 강좌를 찾을 수 없습니다.")
    return problem, course


def _out(session: SessionDep, probe: MisconceptionProbe) -> ProbeReviewOut:
    problem, course = _context(session, probe)
    subject = session.get(Subject, course.subject_id)
    professor = session.get(Professor, course.professor_id)
    material = session.get(Material, probe.source_material_id) if probe.source_material_id else None
    materials = session.exec(
        select(Material).where(
            Material.course_id == course.id,
            Material.kind == "lecture",
            Material.status == "approved",
            Material.replaced_by.is_(None),  # type: ignore[union-attr]
        )
    ).all()
    return ProbeReviewOut(
        id=probe.id,
        course_id=course.id,
        course_name=subject.name if subject else "알 수 없는 과목",
        professor_name=professor.name if professor else "알 수 없는 교수",
        problem_question=problem.question,
        problem_choices=problem.choices,
        problem_answer_index=problem.answer_index,
        wrong_choice_index=probe.wrong_choice_index,
        hypothesis=probe.hypothesis,
        question=probe.question,
        choices=probe.choices,
        answer_index=probe.answer_index,
        explanation=probe.explanation,
        evidence=probe.evidence,
        source_material_id=probe.source_material_id,
        source_material_title=material.title if material else None,
        source_page_text=(
            material.pages[probe.source_page - 1]
            if material and probe.source_page and 1 <= probe.source_page <= len(material.pages)
            else None
        ),
        available_materials=[
            ReviewMaterialOut(id=m.id, title=m.title, page_count=len(m.pages)) for m in materials
        ],
        source_page=probe.source_page,
        status=probe.status,
        reviewed_at=probe.reviewed_at,
    )


def _probe(session: SessionDep, probe_id: int) -> MisconceptionProbe:
    probe = session.get(MisconceptionProbe, probe_id)
    if probe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "확인 문제를 찾을 수 없습니다.")
    return probe


def _validate(session: SessionDep, probe: MisconceptionProbe) -> None:
    problem, course = _context(session, probe)
    if not 0 <= probe.wrong_choice_index < len(problem.choices):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "원본 오답 번호가 유효하지 않습니다."
        )
    if probe.wrong_choice_index == problem.answer_index:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "원본 정답을 오답으로 지정할 수 없습니다."
        )
    if any(not value.strip() for value in (probe.hypothesis, probe.question, probe.explanation)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "가설, 질문, 해설을 입력하세요.")
    if len(probe.choices) < 2 or any(not choice.strip() for choice in probe.choices):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "보기 두 개 이상을 입력하세요.")
    if len(set(probe.choices)) != len(probe.choices) or not 0 <= probe.answer_index < len(
        probe.choices
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "보기 중복 또는 정답 번호를 확인하세요."
        )
    material = session.get(Material, probe.source_material_id) if probe.source_material_id else None
    if not material or material.course_id != course.id or material.kind != "lecture":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "같은 강좌의 교안을 선택하세요.")
    if material.status != "approved" or material.replaced_by is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "현재 승인된 교안을 선택하세요.")
    if not probe.source_page or not 1 <= probe.source_page <= len(material.pages):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "교안 쪽 번호가 유효하지 않습니다."
        )
    evidence = re.sub(r"\s+", "", probe.evidence or "")
    page = re.sub(r"\s+", "", material.pages[probe.source_page - 1])
    if not evidence or evidence not in page:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "근거 문장이 지정한 교안 쪽에 없습니다."
        )


@router.get("")
def list_probes(session: SessionDep, _: AdminUser) -> list[ProbeReviewOut]:
    probes = session.exec(select(MisconceptionProbe).order_by(MisconceptionProbe.id)).all()
    return [_out(session, probe) for probe in probes]


@router.put("/{probe_id}")
def update_probe(
    probe_id: int, body: ProbeReviewUpdate, session: SessionDep, _: AdminUser
) -> ProbeReviewOut:
    probe = _probe(session, probe_id)
    values = {
        field: value.strip() if isinstance(value, str) else value
        for field, value in body.model_dump().items()
    }
    _validate(session, probe.model_copy(update=values))
    for field, value in values.items():
        setattr(probe, field, value)
    probe.status = "draft"
    probe.reviewed_by = None
    probe.reviewed_at = None
    session.add(probe)
    session.commit()
    return _out(session, probe)


@router.post("/{probe_id}/approve")
def approve_probe(probe_id: int, session: SessionDep, admin: AdminUser) -> ProbeReviewOut:
    probe = _probe(session, probe_id)
    _validate(session, probe)
    probe.status = "approved"
    probe.reviewed_by = admin.id
    probe.reviewed_at = datetime.now(UTC)
    session.add(probe)
    session.commit()
    return _out(session, probe)


@router.post("/{probe_id}/draft")
def return_probe_to_draft(probe_id: int, session: SessionDep, _: AdminUser) -> ProbeReviewOut:
    probe = _probe(session, probe_id)
    probe.status = "draft"
    probe.reviewed_by = None
    probe.reviewed_at = None
    session.add(probe)
    session.commit()
    return _out(session, probe)
