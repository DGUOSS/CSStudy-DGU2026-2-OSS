"""시험 결과 학습 리포트: 챕터·개념별 숙련도(시험 전/후), 오개념, 다시 볼 교안 쪽, 오답 흐름(Sankey), 응시자 분포.

리포트를 여는 데는 LLM을 쓰지 않는다. 오개념은 미리 붙여 둔 것(misconceptions)을 꺼내고,
요약 한 줄은 채점이 끝날 때 한 번 만들어 PaperTake.summary에 저장해 둔다(grading.finish_take).
"""

from pydantic import BaseModel
from sqlmodel import Session, select

from app.features.mastery.service import concept_states
from app.features.misconceptions.service import visible_for
from app.features.problems.service import concepts_of
from app.models import Chapter, Material, Paper, PaperTake, Problem


class LabelCount(BaseModel):
    label: str
    count: int


class ChapterStat(BaseModel):
    chapter_id: int
    title: str
    before: float
    after: float


class ConceptStat(BaseModel):
    name: str
    chapter: str
    total: int
    correct: int
    before: float
    after: float
    labels: list[LabelCount]
    pages: list[str]


class Dist(BaseModel):
    rank: int
    score: int
    total_points: int
    me: bool


class Flow(BaseModel):
    """틀린 객관식 하나가 이어지는 길: 문제 → 오개념 → 개념 → 다시 볼 교안 쪽(오답 흐름 차트)."""

    no: int
    misconception: str | None  # None = 오개념 추정 없음
    concept: str | None
    page: str | None


class ReportOut(BaseModel):
    chapters: list[ChapterStat]
    concepts: list[ConceptStat]
    repeated: list[LabelCount]  # 2문항 이상에서 나온 오개념
    review_pages: list[str]  # 다시 볼 교안 쪽(틀린 문제가 많이 가리키는 순)
    distribution: list[Dist]
    flows: list[Flow]
    blank_nos: list[int]  # 빈칸으로 둔 객관식 번호(오답 흐름에서는 뺀다)


def page_label(session: Session, material_id: int | None, page: int | None) -> str | None:
    m = session.get(Material, material_id) if material_id else None
    return f"{m.title} {page}쪽" if m and page else None


def first_takes(session: Session, paper: Paper) -> list[PaperTake]:
    """같은 시험지 등수: 사람마다 첫 응시(제출한 것)만, 점수 높은 순 → 걸린 시간 짧은 순."""
    takes = session.exec(
        select(PaperTake)
        .where(PaperTake.paper_id == paper.id, PaperTake.status == "submitted")
        .order_by(PaperTake.started_at)  # type: ignore[arg-type]
    ).all()
    first: dict[int, PaperTake] = {}
    for t in takes:
        first.setdefault(t.user_id, t)
    return sorted(first.values(), key=lambda t: (-score_of(t), t.elapsed_sec or 0))


def score_of(t: PaperTake) -> int:
    return (t.mcq_score or 0) + (t.essay_score or 0)


def build_report(
    session: Session, take: PaperTake, paper: Paper, probs: list[Problem]
) -> ReportOut:
    answers = dict(zip(paper.problem_ids, take.answers or [], strict=False))
    mcq = [p for p in probs if p.qtype == "mcq"]
    cmap = concepts_of(session, [p.id for p in probs])
    cids = sorted({c.id for cs in cmap.values() for c in cs})
    before = concept_states(session, take.user_id, cids, before=take.started_at)
    after = concept_states(session, take.user_id, cids)
    chapters = {
        ch.id: ch
        for ch in session.exec(
            select(Chapter).where(Chapter.id.in_({p.chapter_id for p in probs}))
        ).all()
    }  # type: ignore[attr-defined]
    mis = visible_for(session, [p.id for p in mcq])

    # 개념별: 맞힘, 오개념 라벨, 다시 볼 쪽
    concept_rows: dict[int, dict] = {}
    label_count: dict[str, int] = {}
    page_count: dict[str, int] = {}
    flows: list[Flow] = []
    blank_nos: list[int] = []

    for no, p in enumerate(probs, start=1):
        if p.qtype != "mcq":
            continue
        chosen = answers.get(p.id)
        wrong = chosen != p.answer_index
        m = mis.get((p.id, chosen)) if wrong and chosen is not None else None
        page = page_label(session, p.source_material_id, p.source_page)
        if wrong and page:
            page_count[page] = page_count.get(page, 0) + 1
        if wrong and m:
            label_count[m.label] = label_count.get(m.label, 0) + 1
        for c in cmap.get(p.id, []):
            row = concept_rows.setdefault(
                c.id,
                {
                    "name": c.name,
                    "chapter": chapters[c.chapter_id].title if c.chapter_id in chapters else "",
                    "total": 0,
                    "correct": 0,
                    "labels": {},
                    "pages": set(),
                },
            )
            row["total"] += 1
            if not wrong:
                row["correct"] += 1
                continue
            if m:
                row["labels"][m.label] = row["labels"].get(m.label, 0) + 1
            if page:
                row["pages"].add(page)
        if wrong and chosen is None:
            blank_nos.append(no)
        elif wrong:  # 오답 흐름(빈칸은 고른 보기가 없어 뺀다)
            cs = cmap.get(p.id, [])
            flows.append(
                Flow(
                    no=no,
                    misconception=m.label if m else None,
                    concept=cs[0].name if cs else None,
                    page=page,
                )
            )

    concepts = [
        ConceptStat(
            name=r["name"],
            chapter=r["chapter"],
            total=r["total"],
            correct=r["correct"],
            before=before[cid].mastery,
            after=after[cid].mastery,
            labels=[
                LabelCount(label=k, count=v)
                for k, v in sorted(r["labels"].items(), key=lambda x: -x[1])
            ],
            pages=sorted(r["pages"]),
        )
        for cid, r in concept_rows.items()
    ]
    concepts.sort(key=lambda c: (c.correct - c.total, c.after))

    ch_stats = []
    for ch_id in sorted(chapters, key=lambda i: chapters[i].order):
        ids = [c.id for p in probs if p.chapter_id == ch_id for c in cmap.get(p.id, [])]
        if not ids:
            continue
        ch_stats.append(
            ChapterStat(
                chapter_id=ch_id,
                title=chapters[ch_id].title,
                before=round(sum(before[i].mastery for i in ids) / len(ids), 3),
                after=round(sum(after[i].mastery for i in ids) / len(ids), 3),
            )
        )

    ranking = first_takes(session, paper)
    dist = []
    prev, rank = None, 0
    for i, t in enumerate(ranking):
        key = (score_of(t), t.elapsed_sec)
        if key != prev:
            rank, prev = i + 1, key
        dist.append(
            Dist(rank=rank, score=score_of(t), total_points=t.total_points, me=t.id == take.id)
        )

    return ReportOut(
        chapters=ch_stats,
        concepts=concepts,
        repeated=[
            LabelCount(label=k, count=v)
            for k, v in sorted(label_count.items(), key=lambda x: -x[1])
            if v >= 2
        ],
        review_pages=[k for k, _ in sorted(page_count.items(), key=lambda x: -x[1])],
        distribution=dist,
        flows=flows,
        blank_nos=blank_nos,
    )
