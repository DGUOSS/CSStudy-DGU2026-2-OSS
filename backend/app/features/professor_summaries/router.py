"""교수의 최근 3년 수업 후기 요약. 원문·작성자 정보는 공개 응답에 넣지 않는다."""

import hashlib
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from app.core.config import settings
from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.enrollments.service import current_term, term_label
from app.models import CatalogOffering, Course, CourseReview, Professor, Subject
from app.services import llm

router = APIRouter(tags=["professor_summaries"])
log = logging.getLogger(__name__)
# 프로세스별 최대 128개, 24시간 캐시. DB 변경 없이 사용하며 재시작 시 사라진다.
_cache: OrderedDict[str, tuple[float, llm.ProfessorSummaryDraft, str]] = OrderedDict()
_attempts: OrderedDict[str, float] = OrderedDict()
_active: set[str] = set()
_lock = threading.Lock()


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
    status: Literal["ready", "not_generated", "insufficient", "unavailable"]
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
                "v1",
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


def _cached(key, out, facts):
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 86400:
            _cache.move_to_end(key)
        else:
            _cache.pop(key, None)
            cached = None
    if cached:
        out.status = "ready"
        out.summary = cached[1]
        out.generated_at = cached[2]
        out.model = settings.llm_model
        ids = {
            i
            for claim in [cached[1].overview, *cached[1].highlights, *cached[1].differences]
            for i in claim.review_ids
        }
        out.sources = [
            SummarySource(**{k: f[k] for k in ("review_id", "subject", "term")})
            for f in facts
            if f["review_id"] in ids
        ]
    return out


@router.get("/catalog/professor-summary")
def get_summary(
    session: SessionDep, _: CurrentUser, emp_no: Annotated[str, Query(min_length=1, max_length=20)]
) -> ProfessorSummaryOut:
    key, out, facts, _authors = _snapshot(session, emp_no)
    if out.status == "insufficient":
        return out
    out = _cached(key, out, facts)
    if out.status != "ready" and not settings.anthropic_api_key:
        out.status = "unavailable"
    return out


@router.post("/catalog/professor-summary")
def generate_summary(
    session: SessionDep, _: CurrentUser, emp_no: Annotated[str, Query(min_length=1, max_length=20)]
) -> ProfessorSummaryOut:
    key, out, facts, authors = _snapshot(session, emp_no)
    if out.status == "insufficient":
        return out
    out = _cached(key, out, facts)
    if out.status == "ready":
        return out
    if not settings.anthropic_api_key:
        raise HTTPException(503, "AI 요약이 설정되지 않았습니다")
    with _lock:
        now = time.monotonic()
        if key in _active or len(_active) >= 2 or now - _attempts.get(key, -60) < 60:
            raise HTTPException(
                429, "요약 생성 중이거나 잠시 대기 중입니다. 1분 후 다시 확인해 주세요"
            )
        _active.add(key)
        _attempts[key] = now
        _attempts.move_to_end(key)
        while len(_attempts) > 256:
            _attempts.popitem(last=False)
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
        with _lock:
            _cache[key] = (time.monotonic(), draft, datetime.now(UTC).isoformat())
            while len(_cache) > 128:
                _cache.popitem(last=False)
        return _cached(key, out, facts)
    except llm.LLMNotConfigured:
        raise HTTPException(503, "AI 요약이 설정되지 않았습니다") from None
    except HTTPException:
        raise
    except Exception:
        log.exception("교수 요약 생성 실패")
        raise HTTPException(502, "요약 생성 중 오류가 발생했습니다") from None
    finally:
        with _lock:
            _active.discard(key)
