"""종이 시험: 시험지 만들기 → 인쇄 → [시험 시작] → 답안지 사진 인식 → 확인 후 제출·채점 → 같은 시험지 등수."""

import base64
import binascii
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import require_course_access
from app.features.misconceptions.service import visible_for
from app.features.papers import omr
from app.features.papers.grading import finish_take, grade_mcq
from app.features.papers.report import ReportOut, build_report, first_takes
from app.features.papers.source import pick_for_paper
from app.features.problems.router import SourceOut
from app.models import Attempt, Material, Paper, PaperEssayImage, PaperTake, Problem, User

router = APIRouter(tags=["papers"])

GRACE_MIN = 10  # 시간이 끝난 뒤 답안지를 찍어 올릴 여유
MAX_PHOTO_MB = 12


class PaperIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    chapter_ids: list[int] = Field(min_length=1)
    # 유형별 문항 수. 문제 생성을 붙이면 족보 출제 프로필의 비율로 채운다(source.type_counts)
    mcq_count: int = Field(default=0, ge=0, le=100)
    essay_count: int = Field(default=0, ge=0, le=30)
    time_limit_min: int = Field(ge=5, le=300)


class PaperSummary(BaseModel):
    id: int
    title: str
    n_questions: int
    n_essay: int
    time_limit_min: int
    created_at: datetime
    created_by_me: bool
    takers: int
    my_best: int | None
    total_points: int
    my_open_take_id: int | None


class PaperProblemOut(BaseModel):
    no: int
    id: int
    qtype: str
    question: str
    choices: list[str]
    points: int


class PaperOut(BaseModel):
    id: int
    course_id: int
    title: str
    time_limit_min: int
    total_points: int
    problems: list[PaperProblemOut]


class SheetOut(BaseModel):
    pages: list[str]  # 쪽별 SVG


class TakeOut(BaseModel):
    id: int
    paper_id: int
    started_at: datetime
    status: str
    paused: bool
    pause_count: int
    time_limit_sec: int
    spent_sec: float  # 정지한 시간을 뺀, 지금까지 푼 시간(서버 기준)
    remaining_sec: float  # 음수면 시간이 지난 것


class ScanMcq(BaseModel):
    no: int
    problem_id: int
    chosen: int | None
    status: str  # ok | blank | multiple | missing


class ScanEssay(BaseModel):
    no: int
    problem_id: int
    image: str | None  # JPEG base64


class ScanOut(BaseModel):
    mcq: list[ScanMcq]
    essays: list[ScanEssay]
    missing_pages: list[int]


class AnswerIn(BaseModel):
    problem_id: int
    chosen: int | None = None


class EssayIn(BaseModel):
    problem_id: int
    image: str | None = None


class SubmitIn(BaseModel):
    answers: list[AnswerIn]
    essays: list[EssayIn] = []


class MisconceptionOut(BaseModel):
    label: str
    hypothesis: str
    explanation: str
    evidence: str | None
    source: SourceOut | None
    status: str  # auto = AI 추정, approved = 관리자 확인


class RubricOut(BaseModel):
    item: str
    max_points: int
    points: int
    reason: str


class ResultItem(BaseModel):
    no: int
    problem_id: int
    qtype: str
    question: str
    choices: list[str]
    points: int
    chosen: int | None
    answer_index: int
    correct: bool | None  # 서술형 채점 대기면 None
    score: int | None
    explanation: str
    evidence: str | None
    source: SourceOut | None
    model_answer: str | None
    misconception: MisconceptionOut | None = None  # 고른 오답의 오개념(미리 붙여 둔 것)
    transcription: str | None = None  # 서술형: 읽은 답
    feedback: str | None = None
    rubric: list[RubricOut] | None = None


class ResultOut(BaseModel):
    take_id: int
    paper_id: int
    score: int
    total_points: int
    essay_pending: bool
    elapsed_sec: int
    late: bool
    essay_status: str  # none | pending(채점 중) | done | unavailable
    summary: str | None
    rank: int | None
    takers: int
    items: list[ResultItem]
    report: ReportOut


class MyTake(BaseModel):
    take_id: int
    score: int
    total_points: int
    elapsed_sec: int
    late: bool
    essay_pending: bool
    submitted_at: datetime


class MineOut(BaseModel):
    open_take: TakeOut | None  # 시작했지만 아직 제출하지 않은 응시(새로고침해도 이어 가기)
    submitted: list[MyTake]


class RankEntry(BaseModel):
    rank: int
    label: str
    me: bool
    score: int
    total_points: int
    elapsed_sec: int
    late: bool
    paused: bool  # 일시정지를 썼는지


class RankingOut(BaseModel):
    entries: list[RankEntry]
    essay_pending: bool  # 서술형 채점 대기가 있으면 객관식 점수 기준


# ---------- 도움 함수 ----------


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _paper_or_404(session: Session, user: User, paper_id: int) -> Paper:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "시험지가 없습니다")
    require_course_access(session, user, get_course_or_404(session, paper.course_id))
    return paper


def _take_or_404(session: Session, user: User, take_id: int) -> tuple[PaperTake, Paper]:
    take = session.get(PaperTake, take_id)
    if take is None or take.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "응시 기록이 없습니다")
    return take, _paper_or_404(session, user, take.paper_id)


def _problems(session: Session, paper: Paper) -> list[Problem]:
    """시험지 순서대로. 그사이 지워진 문제는 뺀다."""
    rows = session.exec(select(Problem).where(Problem.id.in_(paper.problem_ids))).all()  # type: ignore[attr-defined]
    by_id = {p.id: p for p in rows}
    return [by_id[i] for i in paper.problem_ids if i in by_id]


def _layout(problems: list[Problem]) -> omr.Layout:
    return omr.layout([(p.id, p.qtype, len(p.choices)) for p in problems])


def _spent(take: PaperTake, now: datetime) -> float:
    """정지한 시간을 뺀, 실제로 푼 시간(초)."""
    end = _utc(take.paused_at) if take.paused_at else now
    return max(0.0, (end - _utc(take.started_at)).total_seconds() - take.paused_sec)


def _take_out(take: PaperTake, paper: Paper) -> TakeOut:
    spent = _spent(take, datetime.now(UTC))
    limit = paper.time_limit_min * 60
    return TakeOut(
        id=take.id,
        paper_id=paper.id,
        started_at=take.started_at,
        status=take.status,
        paused=take.paused_at is not None,
        pause_count=take.pause_count,
        time_limit_sec=limit,
        spent_sec=round(spent, 1),
        remaining_sec=round(limit - spent, 1),
    )


def _open_take(take_id: int, session: Session, user: User) -> tuple[PaperTake, Paper]:
    take, paper = _take_or_404(session, user, take_id)
    if take.status != "started":
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 끝난 응시입니다")
    return take, paper


def _score(take: PaperTake) -> int:
    return (take.mcq_score or 0) + (take.essay_score or 0)


# ---------- 시험지 ----------


@router.post("/courses/{course_id}/papers", status_code=status.HTTP_201_CREATED)
def create_paper(course_id: int, body: PaperIn, session: SessionDep, user: CurrentUser) -> PaperOut:
    require_course_access(session, user, get_course_or_404(session, course_id))
    if body.mcq_count + body.essay_count == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "문항 수를 정해 주세요")
    counts = {"mcq": body.mcq_count, "essay": body.essay_count}
    picked = pick_for_paper(session, user.id, course_id, body.chapter_ids, counts)
    if not picked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "고른 챕터에 문제가 없습니다")
    paper = Paper(
        course_id=course_id,
        created_by=user.id,
        title=body.title.strip(),
        problem_ids=[p.id for p in picked],
        time_limit_min=body.time_limit_min,
    )
    _layout(picked)  # 답안지가 만들어지는지 미리 확인
    session.add(paper)
    session.commit()
    session.refresh(paper)
    return get_paper(paper.id, session, user)


@router.get("/courses/{course_id}/papers")
def list_papers(course_id: int, session: SessionDep, user: CurrentUser) -> list[PaperSummary]:
    require_course_access(session, user, get_course_or_404(session, course_id))
    papers = session.exec(
        select(Paper).where(Paper.course_id == course_id).order_by(Paper.id.desc())  # type: ignore[union-attr]
    ).all()
    out = []
    for paper in papers:
        probs = _problems(session, paper)
        takes = session.exec(select(PaperTake).where(PaperTake.paper_id == paper.id)).all()
        done = [t for t in takes if t.status == "submitted"]
        mine = [t for t in done if t.user_id == user.id]
        open_take = next((t for t in takes if t.user_id == user.id and t.status == "started"), None)
        out.append(
            PaperSummary(
                id=paper.id,
                title=paper.title,
                n_questions=len(probs),
                n_essay=sum(p.qtype != "mcq" for p in probs),
                time_limit_min=paper.time_limit_min,
                created_at=paper.created_at,
                created_by_me=paper.created_by == user.id,
                takers=len({t.user_id for t in done}),
                my_best=max((_score(t) for t in mine), default=None),
                total_points=sum(p.points for p in probs),
                my_open_take_id=open_take.id if open_take else None,
            )
        )
    return out


@router.get("/papers/{paper_id}")
def get_paper(paper_id: int, session: SessionDep, user: CurrentUser) -> PaperOut:
    """시험지 문제(정답 없음). 인쇄 화면에서 쓴다."""
    paper = _paper_or_404(session, user, paper_id)
    probs = _problems(session, paper)
    return PaperOut(
        id=paper.id,
        course_id=paper.course_id,
        title=paper.title,
        time_limit_min=paper.time_limit_min,
        total_points=sum(p.points for p in probs),
        problems=[
            PaperProblemOut(
                no=i + 1,
                id=p.id,
                qtype=p.qtype,
                question=p.question,
                choices=p.choices,
                points=p.points,
            )
            for i, p in enumerate(probs)
        ],
    )


@router.get("/papers/{paper_id}/sheet")
def get_sheet(paper_id: int, session: SessionDep, user: CurrentUser) -> SheetOut:
    """인쇄용 답안지(쪽별 SVG)."""
    paper = _paper_or_404(session, user, paper_id)
    probs = _problems(session, paper)
    info = f"{len(probs)}문항 · {paper.time_limit_min}분"
    return SheetOut(pages=omr.sheet_svgs(_layout(probs), paper.title, paper.id, info))


# ---------- 응시 ----------


@router.post("/papers/{paper_id}/takes", status_code=status.HTTP_201_CREATED)
def start_take(paper_id: int, session: SessionDep, user: CurrentUser) -> TakeOut:
    """[시험 시작]. 시작 시각은 서버가 기록한다. 끝나지 않은 응시가 있으면 그것을 이어 간다."""
    paper = _paper_or_404(session, user, paper_id)
    open_take = session.exec(
        select(PaperTake).where(
            PaperTake.paper_id == paper.id,
            PaperTake.user_id == user.id,
            PaperTake.status == "started",
        )
    ).first()
    take = open_take or PaperTake(paper_id=paper.id, user_id=user.id)
    if open_take is None:
        session.add(take)
        session.commit()
        session.refresh(take)
    return _take_out(take, paper)


@router.post("/takes/{take_id}/pause")
def pause_take(take_id: int, session: SessionDep, user: CurrentUser) -> TakeOut:
    """일시정지. 멈춘 동안은 시간이 흐르지 않는다."""
    take, paper = _open_take(take_id, session, user)
    if take.paused_at is None:
        take.paused_at = datetime.now(UTC)
        take.pause_count += 1
        session.add(take)
        session.commit()
        session.refresh(take)
    return _take_out(take, paper)


@router.post("/takes/{take_id}/resume")
def resume_take(take_id: int, session: SessionDep, user: CurrentUser) -> TakeOut:
    take, paper = _open_take(take_id, session, user)
    if take.paused_at is not None:
        take.paused_sec += int((datetime.now(UTC) - _utc(take.paused_at)).total_seconds())
        take.paused_at = None
        session.add(take)
        session.commit()
        session.refresh(take)
    return _take_out(take, paper)


@router.post("/takes/{take_id}/abandon")
def abandon_take(take_id: int, session: SessionDep, user: CurrentUser) -> TakeOut:
    """처음부터 다시(그만두기): 이 응시는 버리고 시작 전 상태로. 기록·등수에 들어가지 않는다."""
    take, paper = _open_take(take_id, session, user)
    take.status = "abandoned"
    take.paused_at = None
    session.add(take)
    session.commit()
    session.refresh(take)
    return _take_out(take, paper)


@router.get("/papers/{paper_id}/mine")
def my_takes(paper_id: int, session: SessionDep, user: CurrentUser) -> MineOut:
    paper = _paper_or_404(session, user, paper_id)
    takes = session.exec(
        select(PaperTake)
        .where(PaperTake.paper_id == paper.id, PaperTake.user_id == user.id)
        .order_by(PaperTake.started_at.desc())  # type: ignore[union-attr]
    ).all()
    open_take = next((t for t in takes if t.status == "started"), None)
    has_essay = any(p.qtype != "mcq" for p in _problems(session, paper))
    return MineOut(
        open_take=_take_out(open_take, paper) if open_take else None,
        submitted=[
            MyTake(
                take_id=t.id,
                score=_score(t),
                total_points=t.total_points,
                elapsed_sec=t.elapsed_sec or 0,
                late=t.late,
                essay_pending=has_essay and t.essay_score is None,
                submitted_at=t.submitted_at,
            )
            for t in takes
            if t.status == "submitted"
        ],
    )


@router.get("/takes/{take_id}")
def get_take(take_id: int, session: SessionDep, user: CurrentUser) -> TakeOut:
    take, paper = _take_or_404(session, user, take_id)
    return _take_out(take, paper)


@router.post("/takes/{take_id}/scan")
async def scan_sheet(
    take_id: int,
    session: SessionDep,
    user: CurrentUser,
    files: Annotated[list[UploadFile], File()],
) -> ScanOut:
    """답안지 사진(쪽마다 한 장)을 읽어 결과만 돌려준다. 사진은 저장하지 않는다."""
    take, paper = _take_or_404(session, user, take_id)
    if take.status != "started":
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 제출한 응시입니다")
    lay = _layout(_problems(session, paper))
    if len(files) > lay.pages + 3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"답안지는 {lay.pages}쪽입니다")
    images = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_PHOTO_MB * 1024 * 1024:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE, f"사진은 {MAX_PHOTO_MB}MB 이하만 됩니다"
            )
        images.append(data)
    try:
        return ScanOut.model_validate(omr.read_sheet(images, lay))
    except omr.SheetError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None


def _source(session: Session, p: Problem) -> SourceOut | None:
    m = session.get(Material, p.source_material_id) if p.source_material_id else None
    return SourceOut(material_id=m.id, title=m.title, page=p.source_page) if m else None


def _result(session: Session, take: PaperTake, paper: Paper) -> ResultOut:
    probs = _problems(session, paper)
    answers = dict(zip(paper.problem_ids, take.answers or [], strict=False))
    mis = visible_for(session, [p.id for p in probs if p.qtype == "mcq"])
    imgs = {
        i.problem_id: i
        for i in session.exec(
            select(PaperEssayImage).where(PaperEssayImage.take_id == take.id)
        ).all()
    }
    items = []
    for i, p in enumerate(probs):
        chosen = answers.get(p.id)
        extra: dict = {}
        if p.qtype == "mcq":
            ok = grade_mcq(p, chosen)
            correct, score = ok, (p.points if ok else 0)
            m = mis.get((p.id, chosen)) if not ok and chosen is not None else None
            if m:
                extra["misconception"] = MisconceptionOut(
                    label=m.label,
                    hypothesis=m.hypothesis,
                    explanation=m.explanation,
                    evidence=m.evidence,
                    source=_source_of(session, m.source_material_id, m.source_page),
                    status=m.status,
                )
        else:
            img = imgs.get(p.id)
            if img is None:
                score = 0 if take.status == "submitted" else None
            else:
                score = img.score
                extra.update(
                    transcription=img.transcription,
                    feedback=img.feedback,
                    rubric=[RubricOut(**r) for r in img.rubric_detail]
                    if img.rubric_detail
                    else None,
                )
            correct = None if score is None else score >= p.points
        items.append(
            ResultItem(
                no=i + 1,
                problem_id=p.id,
                qtype=p.qtype,
                question=p.question,
                choices=p.choices,
                points=p.points,
                chosen=chosen,
                answer_index=p.answer_index,
                correct=correct,
                score=score,
                explanation=p.explanation,
                evidence=p.evidence,
                source=_source(session, p),
                model_answer=p.model_answer,
                **extra,
            )
        )
    ranking = first_takes(session, paper)
    rank = next((i + 1 for i, t in enumerate(ranking) if t.id == take.id), None)
    return ResultOut(
        take_id=take.id,
        paper_id=paper.id,
        score=_score(take),
        total_points=take.total_points,
        essay_pending=take.essay_status in ("pending", "unavailable"),
        elapsed_sec=take.elapsed_sec or 0,
        late=take.late,
        essay_status=take.essay_status,
        summary=take.summary,
        rank=rank,
        takers=len(ranking),
        items=items,
        report=build_report(session, take, paper, probs),
    )


def _source_of(session: Session, material_id: int | None, page: int | None) -> SourceOut | None:
    m = session.get(Material, material_id) if material_id else None
    return SourceOut(material_id=m.id, title=m.title, page=page) if m else None


@router.post("/takes/{take_id}/submit")
def submit_take(
    take_id: int,
    body: SubmitIn,
    background: BackgroundTasks,
    session: SessionDep,
    user: CurrentUser,
) -> ResultOut:
    """확인한 답을 제출해 채점한다. 객관식은 바로 채점하고 풀이 기록(Attempt)으로 남겨 숙련도에 반영한다.
    서술형 채점과 결과 요약은 제출 뒤 백그라운드에서 Claude로 한다(grading.finish_take)."""
    take, paper = _take_or_404(session, user, take_id)
    if take.status != "started":
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 제출한 응시입니다")
    probs = _problems(session, paper)
    chosen = {a.problem_id: a.chosen for a in body.answers}
    images = {e.problem_id: e.image for e in body.essays}
    now = datetime.now(UTC)
    spent = _spent(take, now)
    if take.paused_at is not None:  # 멈춘 채로 제출하면 정지를 끝낸 것으로 본다
        take.paused_sec += int((now - _utc(take.paused_at)).total_seconds())
        take.paused_at = None
    answers: list[int | None] = []
    mcq_score = 0
    for p in probs:
        if p.qtype == "mcq":
            c = chosen.get(p.id)
            c = c if c is not None and 0 <= c < len(p.choices) else None
            answers.append(c)
            if c is not None:
                ok = grade_mcq(p, c)
                mcq_score += p.points if ok else 0
                session.add(Attempt(user_id=user.id, problem_id=p.id, chosen_index=c, correct=ok))
            continue
        answers.append(None)
        raw = images.get(p.id)
        jpeg = None
        if raw:
            try:
                jpeg = base64.b64decode(raw, validate=True)
            except (binascii.Error, ValueError):
                jpeg = None
        if jpeg and len(jpeg) <= 2 * 1024 * 1024:  # 답 칸이 없으면 0점(채점할 때)
            session.add(PaperEssayImage(take_id=take.id, problem_id=p.id, image=jpeg))
    essays = [p for p in probs if p.qtype != "mcq"]
    take.answers = answers
    take.mcq_score = mcq_score
    take.essay_score = None if essays else 0
    take.essay_status = "pending" if essays else "none"
    take.total_points = sum(p.points for p in probs)
    take.elapsed_sec = int(min(spent, paper.time_limit_min * 60))
    take.late = spent > (paper.time_limit_min + GRACE_MIN) * 60
    take.submitted_at = now
    take.status = "submitted"
    session.add(take)
    session.commit()
    session.refresh(take)
    background.add_task(finish_take, session.get_bind(), take.id)
    return _result(session, take, paper)


@router.get("/takes/{take_id}/result")
def get_result(take_id: int, session: SessionDep, user: CurrentUser) -> ResultOut:
    take, paper = _take_or_404(session, user, take_id)
    if take.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "아직 제출하지 않았습니다")
    return _result(session, take, paper)


@router.get("/papers/{paper_id}/ranking")
def ranking(paper_id: int, session: SessionDep, user: CurrentUser) -> RankingOut:
    """같은 시험지를 본 사람끼리. 사람마다 첫 응시만, 점수 높은 순 → 걸린 시간 짧은 순. 다른 사람은 익명."""
    paper = _paper_or_404(session, user, paper_id)
    takes = session.exec(
        select(PaperTake)
        .where(PaperTake.paper_id == paper.id, PaperTake.status == "submitted")
        .order_by(PaperTake.started_at)  # type: ignore[arg-type]
    ).all()
    first: dict[int, PaperTake] = {}
    for t in takes:
        first.setdefault(t.user_id, t)
    rows = sorted(first.values(), key=lambda t: (-_score(t), t.elapsed_sec or 0))
    entries, other, prev, rank = [], 0, None, 0
    for i, t in enumerate(rows):
        key = (_score(t), t.elapsed_sec)
        if key != prev:
            rank, prev = i + 1, key
        me = t.user_id == user.id
        if not me:
            other += 1
        entries.append(
            RankEntry(
                rank=rank,
                label="나" if me else f"응시자 {other}",
                me=me,
                score=_score(t),
                total_points=t.total_points,
                elapsed_sec=t.elapsed_sec or 0,
                late=t.late,
                paused=t.pause_count > 0,
            )
        )
    has_essay = any(p.qtype != "mcq" for p in _problems(session, paper))
    return RankingOut(
        entries=entries, essay_pending=has_essay and any(t.essay_score is None for t in rows)
    )
