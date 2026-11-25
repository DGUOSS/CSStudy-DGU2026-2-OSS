"""교수의 최근 3년 수업 후기 요약. 원문·작성자 정보는 공개 응답에 넣지 않는다."""

import hashlib
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.config import settings
from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.enrollments.service import current_term, term_label
from app.models import CatalogOffering, Course, CourseReview, Professor, ProfessorSummary, Subject
from app.services import llm

router = APIRouter(tags=["professor_summaries"])
log = logging.getLogger(__name__)
PROMPT_VERSION = "v1"


class SummaryStats(BaseModel):
    review_count: int
    author_count: int
    course_count: int
    sampled_count: int
    recommendation: float | None
    difficulty: float | None
    workload: float | None


class SummarySource(BaseModel):
    review_id: int
    subject: str
    term: str


class ProfessorSummaryOut(BaseModel):
    status: Literal["ready", "not_generated", "insufficient", "unavailable", "generating"]
    start_year: str
    end_year: str
    stats: SummaryStats
    summary: llm.ProfessorSummaryDraft | None = None
    sources: list[SummarySource] = []
    generated_at: str | None = None
    model: str | None = None


def _clean(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[이메일 생략]", text)
    text = re.sub(
        r"(?<!\d)(?:01[016789]|02|0[3-6]\d)[ -]?\d{3,4}[ -]?\d{4}(?!\d)", "[연락처 생략]", text
    )
    return re.sub(r"(?<!\d)\d{10}(?!\d)", "[번호 생략]", text)


def _snapshot(session, emp_no):
    end = current_term()[0]
    start = str(int(end) - 2)
    exists = session.exec(
        select(CatalogOffering.id)
        .where(
            CatalogOffering.emp_no == emp_no,
            CatalogOffering.year >= start,
            CatalogOffering.year <= end,
        )
        .limit(1)
    ).first()
    if exists is None:
        raise HTTPException(404, "최근 3년 개설목록에 없는 교수입니다")
    rows = session.exec(
        select(CourseReview, Subject.name)
        .join(Course, Course.id == CourseReview.course_id)
        .join(Professor, Professor.id == Course.professor_id)
        .join(Subject, Subject.id == Course.subject_id)
        .where(
            Professor.emp_no == emp_no,
            CourseReview.is_deleted == False,  # noqa: E712
            CourseReview.year >= start,
            CourseReview.year <= end,
        )
        .order_by(CourseReview.created_at.desc(), CourseReview.id.desc())
    ).all()
    # 같은 이름으로 추정 연결하지 않는다. 교원번호가 확정된 강좌만 사용한다.
    selected = rows[:100]
    facts = [
        {
            "review_id": rev.id,
            "subject": name,
            "term": term_label(rev.year, rev.sem_cd),
            "content": _clean(rev.content)[:1500],
        }
        for rev, name in selected
    ]
    stats = SummaryStats(
        review_count=len(rows),
        author_count=len({rev.user_id for rev, _ in rows}),
        course_count=len({rev.course_id for rev, _ in rows}),
        sampled_count=len(selected),
        **{
            key: round(sum(getattr(rev, key) for rev, _ in rows) / len(rows), 2) if rows else None
            for key in ("recommendation", "difficulty", "workload")
        },
    )
    # 전체 후기의 변경·삭제도 fingerprint에 반영한다. 작성자 ID는 모델로 보내지 않는다.
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                PROMPT_VERSION,
                emp_no,
                start,
                end,
                settings.llm_model,
                [(rev.model_dump(mode="json"), name) for rev, name in rows],
            ],
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    out = ProfessorSummaryOut(status="not_generated", start_year=start, end_year=end, stats=stats)
    if stats.author_count < 3 or len({rev.user_id for rev, _ in selected}) < 3:
        out.status = "insufficient"
    return fingerprint, out, facts, {rev.id: rev.user_id for rev, _ in selected}


def _now():
    return datetime.now(UTC)


def _cached(session, emp_no, key, out, facts):
    row = session.get(ProfessorSummary, emp_no, populate_existing=True)
    if row and row.status == "generating" and row.lease_until and row.lease_until > _now():
        out.status = "generating"
    elif row and row.fingerprint == key and row.status == "ready" and row.summary:
        draft = llm.ProfessorSummaryDraft.model_validate(row.summary)
        out.status = "ready"
        out.summary = draft
        out.generated_at = row.generated_at.replace(tzinfo=UTC).isoformat()
        out.model = row.model
        ids = {
            i
            for claim in [draft.overview, *draft.highlights, *draft.differences]
            for i in claim.review_ids
        }
        out.sources = [
            SummarySource(**{k: f[k] for k in ("review_id", "subject", "term")})
            for f in facts
            if f["review_id"] in ids
        ]
    return out


def _acquire(session, emp_no, key):
    if session.get(ProfessorSummary, emp_no) is None:
        session.add(ProfessorSummary(emp_no=emp_no))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()  # 다른 서버가 먼저 같은 교수 행을 만들었을 수 있다.
    now = _now()
    token = str(uuid4())
    result = session.execute(
        update(ProfessorSummary)
        .where(
            ProfessorSummary.emp_no == emp_no,
            or_(ProfessorSummary.status != "generating", ProfessorSummary.lease_until <= now),
            or_(ProfessorSummary.status != "ready", ProfessorSummary.fingerprint != key),
            or_(
                ProfessorSummary.retry_after.is_(None),
                ProfessorSummary.retry_after <= now,
                ProfessorSummary.fingerprint != key,
            ),
        )
        .values(
            status="generating",
            fingerprint=key,
            model=settings.llm_model,
            summary=None,
            generated_at=None,
            lease_token=token,
            lease_until=now + timedelta(minutes=3),
            retry_after=None,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return token if result.rowcount == 1 else None


def _finish(session, emp_no, token, draft=None):
    # 임대가 만료되어 새 작업이 시작됐다면 이전 작업은 결과를 덮어쓸 수 없다.
    result = session.execute(
        update(ProfessorSummary)
        .where(
            ProfessorSummary.emp_no == emp_no,
            ProfessorSummary.lease_token == token,
            ProfessorSummary.status == "generating",
            ProfessorSummary.lease_until > _now(),
        )
        .values(
            status="ready" if draft else "failed",
            summary=draft.model_dump(mode="json") if draft else None,
            generated_at=_now() if draft else None,
            lease_token=None,
            lease_until=None,
            retry_after=None if draft else _now() + timedelta(seconds=60),
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return result.rowcount == 1


@router.get("/catalog/professor-summary")
def get_summary(
    session: SessionDep, _: CurrentUser, emp_no: Annotated[str, Query(min_length=1, max_length=20)]
) -> ProfessorSummaryOut:
    key, out, facts, _authors = _snapshot(session, emp_no)
    if out.status == "insufficient":
        return out
    out = _cached(session, emp_no, key, out, facts)
    if out.status == "not_generated" and not settings.anthropic_api_key:
        out.status = "unavailable"
    return out


@router.post("/catalog/professor-summary")
def generate_summary(
    session: SessionDep, _: CurrentUser, emp_no: Annotated[str, Query(min_length=1, max_length=20)]
) -> ProfessorSummaryOut:
    key, out, facts, authors = _snapshot(session, emp_no)
    if out.status == "insufficient":
        return out
    out = _cached(session, emp_no, key, out, facts)
    if out.status == "ready":
        return out
    if not settings.anthropic_api_key:
        raise HTTPException(503, "AI 요약이 설정되지 않았습니다")
    token = _acquire(session, emp_no, key)
    if token is None:
        out = _cached(session, emp_no, key, out, facts)
        if out.status == "ready":
            return out
        raise HTTPException(
            429, "요약 생성 중이거나 잠시 대기 중입니다. 잠시 후 다시 확인해 주세요"
        )
    try:
        session.commit()  # 외부 응답을 기다리는 동안 DB 연결을 반환한다.
        draft = llm.summarize_professor(json.dumps({"reviews": facts}, ensure_ascii=False))
        if draft is None:
            raise HTTPException(502, "요약을 만들지 못했습니다. 잠시 후 다시 시도해 주세요")
        # 모든 문장은 실제 입력 후기만 참조해야 한다. 전체·공통 특징은 2명 이상 근거가 필요하다.
        for claim in [draft.overview, *draft.highlights, *draft.differences]:
            if (
                not claim.text.strip()
                or not claim.review_ids
                or any(i not in authors for i in claim.review_ids)
            ):
                raise HTTPException(502, "요약의 근거를 확인하지 못했습니다")
            claim.text = _clean(claim.text)
        for claim in [draft.overview, *draft.highlights]:
            if len({authors[i] for i in claim.review_ids}) < 2:
                raise HTTPException(502, "공통 특징을 뒷받침할 근거가 부족합니다")
        # 생성 중 삭제된 후기를 포함한 결과는 내보내지 않는다.
        session.expire_all()
        current, _, _, _ = _snapshot(session, emp_no)
        if current != key:
            raise HTTPException(409, "후기가 변경되었습니다. 다시 확인해 주세요")
        if not _finish(session, emp_no, token, draft):
            raise HTTPException(409, "생성 시간이 만료되었습니다. 다시 확인해 주세요")
        return _cached(session, emp_no, key, out, facts)
    except llm.LLMNotConfigured:
        raise HTTPException(503, "AI 요약이 설정되지 않았습니다") from None
    except HTTPException:
        raise
    except Exception:
        log.exception("교수 요약 생성 실패")
        raise HTTPException(502, "요약 생성 중 오류가 발생했습니다") from None
    finally:
        session.rollback()
        _finish(session, emp_no, token)
