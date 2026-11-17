"""채점. 객관식은 제출할 때 바로, 서술형과 결과 요약은 제출 뒤 백그라운드에서 Claude로(finish_take)."""

import json
import logging
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import Paper, PaperEssayImage, PaperTake, Problem
from app.services import llm

log = logging.getLogger(__name__)


def grade_mcq(problem: Problem, chosen: int | None) -> bool:
    return chosen is not None and chosen == problem.answer_index


def finish_take(bind, take_id: int) -> None:
    """제출 직후 백그라운드: 서술형 답 칸을 읽고 배점표로 채점한 뒤, 결과 요약을 한 번 만들어 둔다.

    키가 없거나 실패하면 서술형은 '채점 대기(unavailable)'로 두고, 요약은 건너뛴다.
    """
    with Session(bind) as s:
        take = s.get(PaperTake, take_id)
        if take is None:
            return
        paper = s.get(Paper, take.paper_id)
        probs = {
            p.id: p for p in s.exec(select(Problem).where(Problem.id.in_(paper.problem_ids))).all()
        }  # type: ignore[attr-defined]
        essays = [probs[i] for i in paper.problem_ids if i in probs and probs[i].qtype != "mcq"]
        if essays:
            _grade_essays(s, take, essays)
        try:
            _summarize(s, take, paper)
        except llm.LLMNotConfigured:
            pass
        except Exception:
            log.exception("결과 요약 실패: take %s", take_id)


def _grade_essays(s: Session, take: PaperTake, essays: list[Problem]) -> None:
    imgs = {
        i.problem_id: i
        for i in s.exec(select(PaperEssayImage).where(PaperEssayImage.take_id == take.id)).all()
    }
    total, ok = 0, True
    for p in essays:
        img = imgs.get(p.id)
        if img is None:  # 답 칸 사진이 없으면 0점
            continue
        try:
            g = llm.grade_essay(
                img.image,
                p.question,
                p.model_answer,
                p.rubric or [f"모범답안과 맞는 정도 — {p.points}점"],
                p.points,
            )
        except llm.LLMNotConfigured:
            ok = False
            break
        except Exception:
            log.exception("서술형 채점 실패: take %s problem %s", take.id, p.id)
            g = None
        if g is None:
            ok = False
            continue
        img.score = g.total
        img.transcription = g.transcription
        img.feedback = g.feedback
        img.rubric_detail = [i.model_dump() for i in g.items]
        img.graded_at = datetime.now(UTC)
        s.add(img)
        total += g.total
    if ok:
        take.essay_score = total
        take.essay_status = "done"
    else:
        take.essay_status = "unavailable"
    s.add(take)
    s.commit()
    s.refresh(take)


def _summarize(s: Session, take: PaperTake, paper: Paper) -> None:
    from app.features.papers.report import build_report, first_takes, score_of

    by_id = {
        p.id: p for p in s.exec(select(Problem).where(Problem.id.in_(paper.problem_ids))).all()
    }  # type: ignore[attr-defined]
    probs = [by_id[i] for i in paper.problem_ids if i in by_id]
    rep = build_report(s, take, paper, probs)
    ranking = first_takes(s, paper)
    rank = next((i + 1 for i, t in enumerate(ranking) if t.id == take.id), None)
    pending = take.essay_status not in ("done", "none")
    facts = {
        "점수": f"{score_of(take)}/{take.total_points}" + (" (서술형 채점 전)" if pending else ""),
        "등수": f"{rank}/{len(ranking)}" if rank else None,
        "약한 개념": [
            f"{c.name} {c.correct}/{c.total}" for c in rep.concepts if c.correct < c.total
        ][:6],
        "의심 오개념": [f"{c.label} ×{c.count}" for c in rep.repeated]
        or [x.label for c in rep.concepts for x in c.labels][:5],
        "다시 볼 교안 쪽": rep.review_pages[:4],
    }
    text = llm.summarize_result(json.dumps(facts, ensure_ascii=False))
    if text:
        take.summary = text
        s.add(take)
        s.commit()
