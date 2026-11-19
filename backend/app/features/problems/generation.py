"""미풀이 객관식이 부족하면 question-ai(qgen) 생성기로 문제를 보충한다.

question-ai/ 는 생성기 담당 코드라 여기서 고치지 않는다. 사이트에 필요한 것은 전부 이 파일에서 감싼다.
- 스키마: qgen.schemas.Question 을 상속해 해설·근거·개념 칸을 더한 SiteQuestion
- 프롬프트: qgen.llm.render_prompt 로 원래 프롬프트를 만든 뒤 사이트용 지시를 뒤에 덧붙인다
- 모델 호출: qgen.agents 대신 사이트의 Claude 호출(services/llm._parse)로 같은 순서를 돈다
  (qgen.pipeline 과 같음: 출제 → 규칙검사 → 블라인드 풀이 → 검토 → 수정/재출제)
- 검사: qgen.checks.run 뒤에 사이트 검사(근거 문장 대조, 개념 이름 정확히 일치)를 더한다
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock

from fastapi import BackgroundTasks
from pydantic import BaseModel, Field
from qgen import checks
from qgen.ingest import Retriever, format_chunks
from qgen.ingest.chunker import chunk_pages
from qgen.ingest.pdf_parser import Page
from qgen.schemas import Chunk, ExamProfile, PlannedItem, Question, Review, SolverOutput
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.features.exams.router import exam_style_examples
from app.models import Attempt, Chapter, Concept, Material, Problem, ProblemConcept
from app.services.llm import LLMNotConfigured, _parse

log = logging.getLogger(__name__)

LOW_STOCK = 2  # 강좌 전체에서 이 사용자가 안 푼 객관식이 이 수 이하면 보충
REFILL_SIZE = 5
# question-ai/config.yaml 의 pipeline 값과 같게 둔다(그 파일은 git 설치본에 들어 있지 않다)
MAX_REVISIONS = 2
MAX_REGENERATIONS = 1
RETRIEVAL_TOP_K = 4
MIN_EVIDENCE_CHARS = (
    8  # 공백·문장부호를 뺀 근거 글자 수 하한(한두 단어짜리 '근거'는 아무 데나 맞는다)
)

# ---------- 비용 상한(강좌별) ----------
# 생성이 실패(저장 0개)해도 '부족' 상태가 그대로라, 막지 않으면 문제를 풀 때마다 다시 생성한다.
# 시작 전에 아래를 확인하고 하나라도 걸리면 생성하지 않는다. 기록은 서버 메모리(재시작하면 초기화).
FAIL_COOLDOWN_SEC = 60 * 60  # 저장 0개로 끝났으면 1시간 쉼
MIN_GAP_SEC = 10 * 60  # 성공했어도 다음 시도까지 10분
DAILY_RUNS = 5  # 강좌별 하루(UTC) 최대 시도 횟수 → 하루 최대 5 × REFILL_SIZE 문항


@dataclass
class _Guard:
    day: date
    runs: int = 0
    last_at: float = 0.0
    last_saved: int | None = None  # 마지막 시도에서 저장한 개수(None = 아직 없음)
    running: bool = False


_guards: dict[int, _Guard] = {}
_guard_lock = Lock()
_locks_guard = Lock()
_course_locks: dict[int, Lock] = {}


def _now() -> float:  # 테스트에서 바꿔 끼운다
    return time.time()


def _today() -> date:
    return datetime.fromtimestamp(_now(), UTC).date()


def reset_guards() -> None:
    with _guard_lock:
        _guards.clear()


def _reserve(course_id: int) -> bool:
    """생성을 시작해도 되면 자리를 잡고 True. 실행 중·실패 후 쉬는 중·간격 미달·하루 한도면 False."""
    now, today = _now(), _today()
    with _guard_lock:
        g = _guards.setdefault(course_id, _Guard(day=today))
        if g.day != today:
            g.day, g.runs = today, 0
        if g.running:
            return False
        since = now - g.last_at
        if g.last_saved == 0 and since < FAIL_COOLDOWN_SEC:
            return False
        if g.last_at and since < MIN_GAP_SEC:
            return False
        if g.runs >= DAILY_RUNS:
            log.info("Course %s reached the daily generation limit", course_id)
            return False
        g.running = True
        g.runs += 1
        g.last_at = now
        return True


def _release(course_id: int, saved: int | None) -> None:
    with _guard_lock:
        g = _guards.get(course_id)
        if g:
            g.running = False
            g.last_saved = saved
            g.last_at = _now()


# ---------- qgen 감싸기 ----------


class SiteQuestion(Question):
    """qgen 문항 + 사이트 저장에 필요한 칸."""

    explanation: str = Field(description="정답 해설. 왜 정답이고 다른 보기는 왜 틀렸는지 2~3문장")
    evidence: str = Field(
        description="정답의 근거가 되는 문장. 제공된 강의자료에서 글자 그대로 복사한다"
    )
    concepts: list[str] = Field(
        description="이 문항이 확인하는 개념 이름. 주어진 개념 목록에서 글자 그대로 고른다"
    )


SYSTEM = (
    "너는 대학 시험 출제 시스템의 한 에이전트다. 주어진 스키마의 JSON 하나로만 답한다. "
    "모든 텍스트는 한국어, 수식은 LaTeX($...$)."
)


def render_prompt(name: str, **vars: object) -> str:
    """question-ai 원래 프롬프트. qgen.llm 은 불러올 때 config.yaml·prompts/ 를 패키지 밖 경로에서
    읽으므로, question-ai 쪽에서 패키지 데이터로 넣기 전까지 git 설치본에서는 여기서 실패한다."""
    from qgen.llm import render_prompt as _render

    return _render(name, **vars)


def _generator_extra(concept_names: list[str]) -> str:
    names = "\n".join(f"- {n}" for n in concept_names)
    return (
        "\n\n## 사이트 저장용 추가 칸\n"
        "- explanation: 정답 해설(왜 정답이고 다른 보기는 왜 틀렸는지).\n"
        "- evidence: 정답 근거 문장 하나를 위 강의자료에서 글자 그대로 복사한다. 요약하거나 고쳐 쓰지 않는다. "
        "그 문장이 있는 쪽을 sources에 넣는다.\n"
        "- concepts: 이 문항이 실제로 확인하는 개념을 아래 목록에서 1개 이상 골라 이름을 글자 그대로 적는다. "
        "목록에 없는 이름을 만들거나 관련 없는 개념을 고르지 않는다.\n"
        f"개념 목록:\n{names}"
    )


REVIEWER_EXTRA = (
    "\n\n## 사이트 추가 검토\n"
    "- 문항의 concepts에 적힌 개념을 이 문항이 실제로 묻는지 확인한다. 관련 없는 개념이 있으면 revise로 하고 "
    "feedback에 어떤 개념을 빼거나 바꿀지 적는다.\n"
    "- explanation이 정답과 맞는지, evidence가 정답을 지지하는지 확인한다."
)


class GenerationCallFailed(RuntimeError):
    pass


def _call(role: str, prompt: str, schema: type[BaseModel]):
    result = _parse(SYSTEM, prompt, schema, model=settings.qgen_model)
    if result is None:
        raise GenerationCallFailed(f"{role}: 모델 응답 없음(거절·API 오류·파싱 실패)")
    return result


def generator(
    item: PlannedItem,
    chunks: list[Chunk],
    profile: ExamProfile,
    examples: str,
    concept_names: list[str],
    prev: "SiteQuestion | None" = None,
    feedback: str | None = None,
) -> SiteQuestion:
    revise = ""
    if prev is not None:  # qgen.agents.generator 의 수정 모드 문구 그대로
        revise = f"## 수정 모드\n이전 문항:\n{prev.model_dump_json(indent=1)}\n\n수정 지시:\n{feedback}\n위 지시를 반영해 문항을 고쳐라."
    prompt = render_prompt(
        "generator",
        item=item.model_dump(),
        chunks=format_chunks(chunks),
        profile=profile.model_dump(
            include={"difficulty", "detail_level", "phrasing_examples", "recurring_patterns"}
        ),
        examples=examples or "(없음)",
        revise=revise,
    ) + _generator_extra(concept_names)
    q = _call("generator", prompt, SiteQuestion)
    q.item_id, q.qtype = item.item_id, item.qtype
    return q


def solver(q: SiteQuestion, chunks: list[Chunk]) -> SolverOutput:
    from qgen.agents import strip_answer  # 정답·해설·근거·개념은 빼고 문제와 보기만

    prompt = render_prompt("solver", question=strip_answer(q), chunks=format_chunks(chunks))
    s = _call("solver", prompt, SolverOutput)
    s.item_id = q.item_id
    return s


def reviewer(
    q: SiteQuestion, s: SolverOutput, item: PlannedItem, chunks: list[Chunk], profile: ExamProfile
) -> Review:
    prompt = (
        render_prompt(
            "reviewer",
            question=q.model_dump(),
            solver=s.model_dump(),
            item=item.model_dump(),
            chunks=format_chunks(chunks),
            profile=profile.model_dump(include={"difficulty", "detail_level", "phrasing_examples"}),
        )
        + REVIEWER_EXTRA
    )
    r = _call("reviewer", prompt, Review)
    r.item_id = q.item_id
    return r


# ---------- 사이트 추가 검사 ----------


def normalize(text: str) -> str:
    """공백·문장부호를 지우고 글자·숫자만 남긴다(PR #17과 같음)."""
    return re.sub(r"[\W_]+", "", text or "")


def evidence_chunk(q: SiteQuestion, chunks: list[Chunk]) -> Chunk | None:
    """근거 문장이 들어 있고 sources에도 적힌 청크."""
    ev = normalize(q.evidence)
    if len(ev) < MIN_EVIDENCE_CHARS:
        return None
    cited = {(s.file, s.page) for s in q.sources}
    for c in chunks:
        if (c.source.file, c.source.page) in cited and ev in normalize(c.text):
            return c
    return None


def site_issues(q: SiteQuestion, chunks: list[Chunk], concept_names: list[str]) -> list[str]:
    issues = []
    if not re.fullmatch(r"\d+", q.answer.strip()):
        issues.append(f"정답 '{q.answer}'는 번호 하나여야 함(사이트는 정답 하나만 저장)")
    if not q.explanation.strip():
        issues.append("explanation(해설)이 비어 있음")
    ev = normalize(q.evidence)
    if len(ev) < MIN_EVIDENCE_CHARS:
        issues.append("evidence(근거 문장)가 비었거나 너무 짧음 — 강의자료 문장을 그대로 복사")
    elif not any(ev in normalize(c.text) for c in chunks):
        issues.append("evidence가 제공된 강의자료에 없음 — 요약하지 말고 글자 그대로 복사")
    elif evidence_chunk(q, chunks) is None:
        issues.append("evidence가 있는 쪽이 sources에 없음")
    allowed = set(concept_names)
    if not q.concepts:
        issues.append("concepts가 비어 있음 — 개념 목록에서 1개 이상 고를 것")
    unknown = [n for n in q.concepts if n not in allowed]
    if unknown:
        issues.append(f"개념 목록에 없는 이름 {unknown} — 목록의 이름을 글자 그대로 쓸 것")
    if len(set(q.concepts)) != len(q.concepts):
        issues.append("concepts에 같은 개념이 중복됨")
    return issues


def all_issues(
    q: SiteQuestion, item: PlannedItem, chunks: list[Chunk], concept_names: list[str]
) -> list[str]:
    return sorted(set(checks.run(q, item, chunks) + site_issues(q, chunks, concept_names)))


# ---------- 한 문항: qgen.pipeline 과 같은 순서 ----------


@dataclass
class ItemResult:
    item_id: str
    topic: str
    saved: bool = False
    reason: str = ""  # 탈락 사유
    history: list[str] = field(default_factory=list)
    question: SiteQuestion | None = None
    page: int | None = None


def run_item(
    item: PlannedItem,
    ctx: list[Chunk],
    profile: ExamProfile,
    examples: str,
    concept_names: list[str],
) -> ItemResult:
    res = ItemResult(item.item_id, item.topic)
    q = generator(item, ctx, profile, examples, concept_names)
    regens = 0
    last = ""
    for _ in range(MAX_REVISIONS + 1):
        issues = all_issues(q, item, ctx, concept_names)
        if issues:
            res.history.append(f"규칙위반({len(issues)})")
            last = "규칙검사: " + "; ".join(issues)
            q = generator(
                item, ctx, profile, examples, concept_names, prev=q, feedback="\n".join(issues)
            )
            continue
        s = solver(q, ctx)
        r = reviewer(q, s, item, ctx, profile)
        res.history.append(f"{r.verdict}({r.answer_match})")
        if r.verdict == "pass":
            res.question = q
            return res
        last = f"검토 {r.verdict}: " + "; ".join(
            [*r.issues, r.feedback] if r.feedback else r.issues
        )
        if r.verdict == "reject" and regens < MAX_REGENERATIONS:
            regens += 1
            q = generator(item, ctx, profile, examples, concept_names)
            continue
        if r.verdict == "reject":
            break
        q = generator(
            item,
            ctx,
            profile,
            examples,
            concept_names,
            prev=q,
            feedback=r.feedback + "\n" + "\n".join(r.issues),
        )
    res.reason = last or "수정 한도 초과"
    return res


# ---------- 강좌 단위 ----------


@dataclass
class GenerationReport:
    course_id: int
    chapter_id: int | None = None
    chapter_title: str = ""
    saved: int = 0
    items: list[ItemResult] = field(default_factory=list)
    note: str = ""


def _lock_for(course_id: int) -> Lock:
    with _locks_guard:
        return _course_locks.setdefault(course_id, Lock())


def unanswered_count(session: Session, course_id: int, user_id: int) -> int:
    ids = list(
        session.exec(
            select(Problem.id)
            .join(Chapter, Problem.chapter_id == Chapter.id)
            .where(Chapter.course_id == course_id, Problem.qtype == "mcq")
        ).all()
    )
    if not ids:
        return 0
    answered = set(
        session.exec(
            select(Attempt.problem_id).where(
                Attempt.user_id == user_id,
                Attempt.problem_id.in_(ids),  # type: ignore[attr-defined]
            )
        ).all()
    )
    return sum(problem_id not in answered for problem_id in ids)


def schedule_if_low(
    background_tasks: BackgroundTasks, session: Session, course_id: int, user_id: int
) -> None:
    if not settings.anthropic_api_key:
        return
    if unanswered_count(session, course_id, user_id) > LOW_STOCK:
        return
    if _reserve(course_id):
        background_tasks.add_task(_replenish_background, course_id, user_id)


def _replenish_background(course_id: int, user_id: int) -> None:
    saved: int | None = None
    with _lock_for(course_id):
        try:
            with Session(engine) as session:
                if unanswered_count(session, course_id, user_id) <= LOW_STOCK:
                    report = generate_for_course(session, course_id, user_id)
                    saved = report.saved
                    for it in report.items:
                        if not it.saved:
                            log.info("qgen %s %s 탈락: %s", course_id, it.item_id, it.reason)
        except Exception:
            saved = 0  # 예외도 실패로 보고 쉬게 한다
            log.exception("Automatic problem generation failed for course %s", course_id)
        finally:
            _release(course_id, saved)


def _source_material(session: Session, chapter: Chapter) -> Material | None:
    """챕터에 연결된 승인 교안. 없으면 다른 교안으로 만들지 않는다(챕터 개념과 안 맞는 문제가 생기지 않게)."""
    if chapter.material_id is None:
        return None
    material = session.get(Material, chapter.material_id)
    if (
        material is not None
        and material.course_id == chapter.course_id
        and material.kind == "lecture"
        and material.status == "approved"
    ):
        return material
    return None


def lecture_chunks(material: Material, course_id: int) -> list[Chunk]:
    """DB에 저장된 쪽 글을 qgen 청커로 나눈다."""
    name = material.filename or f"material-{material.id}"
    pages = [Page(file=name, page=i, text=t) for i, t in enumerate(material.pages, start=1)]
    return chunk_pages(pages, str(course_id))


def _target(session: Session, course_id: int, user_id: int):
    """안 푼 객관식이 가장 적은 챕터(교안·개념이 있는 것만)."""
    chapters = session.exec(
        select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.order)
    ).all()
    answered = set(session.exec(select(Attempt.problem_id).where(Attempt.user_id == user_id)).all())
    ranked = []
    for chapter in chapters:
        if session.exec(select(Concept.id).where(Concept.chapter_id == chapter.id)).first() is None:
            continue
        material = _source_material(session, chapter)
        if material is None or not lecture_chunks(material, course_id):
            continue
        ids = session.exec(
            select(Problem.id).where(Problem.chapter_id == chapter.id, Problem.qtype == "mcq")
        ).all()
        ranked.append((sum(pid not in answered for pid in ids), chapter.order, chapter, material))
    if not ranked:
        return None
    _, _, chapter, material = min(ranked, key=lambda row: (row[0], row[1]))
    return chapter, material


def plan_items(concept_names: list[str], chapter_title: str, n: int) -> list[PlannedItem]:
    """Planner(LLM) 대신 챕터 개념을 돌아가며 n문항을 계획한다.

    교안 한 파일이 여러 챕터를 담기도 해서(예: week2.pdf = 2~4장) 쪽 제목으로 고르면 다른 챕터 내용이 나온다.
    개념 이름으로 검색하면 그 챕터 개념을 묻는 쪽이 잡힌다.
    """
    return [
        PlannedItem(
            item_id=f"q{i + 1}",
            qtype="객관식",
            topic=f"{chapter_title} — {concept_names[i % len(concept_names)]}",
            bloom_level="이해",
            difficulty="보통",
            points=1,
            rationale=f"미풀이 문제 자동 보충. 개념: {concept_names[i % len(concept_names)]}",
        )
        for i in range(n)
    ]


def generate_for_course(
    session: Session, course_id: int, user_id: int, chapter_id: int | None = None
) -> GenerationReport:
    """검토를 통과한 객관식을 저장하고 문항별 결과를 돌려준다. chapter_id를 주면 그 챕터로."""
    report = GenerationReport(course_id)
    if chapter_id is not None:
        chapter = session.get(Chapter, chapter_id)
        material = _source_material(session, chapter) if chapter else None
        target = (chapter, material) if chapter and material else None
    else:
        target = _target(session, course_id, user_id)
    if target is None:
        report.note = "교안과 개념이 연결된 챕터가 없음"
        return report
    chapter, material = target
    report.chapter_id, report.chapter_title = chapter.id, chapter.title
    concepts = list(session.exec(select(Concept).where(Concept.chapter_id == chapter.id)).all())
    if not concepts:
        report.note = "챕터에 개념이 없음"
        return report
    by_name = {c.name: c for c in concepts}
    concept_names = list(by_name)
    chunks = lecture_chunks(material, course_id)
    if not chunks:
        report.note = "교안에 글이 있는 쪽이 없음"
        return report
    profile = ExamProfile(
        course=str(course_id),
        format_ratio={"객관식": 1.0},
        num_questions=REFILL_SIZE,
        detail_level="중간",
        difficulty="보통",
        recurring_patterns=[],
        phrasing_examples=[],
        emphasized_topics=[],
        notes=chapter.title,
    )
    examples = "\n\n".join(exam_style_examples(session, user_id, course_id))[:3000]
    # DB에 있는 쪽 글로 검색한다. 독립 실행용 임베딩 인덱스는 읽지 않게 없는 폴더를 준다 → BM25
    retriever = Retriever(chunks, index_dir=Path(__file__).parent / "_no_index", verbose=False)
    existing = {
        p.strip()
        for p in session.exec(
            select(Problem.question).where(Problem.chapter_id == chapter.id)
        ).all()
    }
    for i, item in enumerate(plan_items(concept_names, chapter.title, REFILL_SIZE)):
        concept = concept_names[i % len(concept_names)]
        ctx = retriever.search_many([concept, chapter.title], k=RETRIEVAL_TOP_K)
        try:
            res = run_item(item, ctx, profile, examples, concept_names)
        except (GenerationCallFailed, LLMNotConfigured) as e:
            res = ItemResult(item.item_id, item.topic, reason=str(e))
        report.items.append(res)
        q = res.question
        if q is None:
            continue
        if q.stem.strip() in existing:
            res.reason = "기존 문제와 본문이 같음"
            continue
        src = evidence_chunk(q, ctx)
        if src is None:  # all_issues 를 통과했으면 있어야 한다
            res.reason = "근거 문장 위치를 찾지 못함"
            continue
        problem = Problem(
            chapter_id=chapter.id,
            question=q.stem.strip(),
            choices=q.choices or [],
            answer_index=int(q.answer.strip()) - 1,
            explanation=q.explanation.strip(),
            evidence=q.evidence.strip(),
            source_material_id=material.id,
            source_page=src.source.page,
            origin="llm",
            qtype="mcq",
        )
        session.add(problem)
        session.flush()
        for name in dict.fromkeys(q.concepts):
            session.add(ProblemConcept(problem_id=problem.id, concept_id=by_name[name].id))
        existing.add(problem.question)
        res.saved, res.page = True, src.source.page
        report.saved += 1
    session.commit()
    return report
