"""교안이 들어오면 챕터와 개념을 자동으로 만든다(Claude, 교안당 한 번).

- 교안(kind=lecture)이 DB에 저장되면 어디서 올렸든(강좌 만들기, 자료 올리기, 강좌 열기 요청) 커밋 직후
  뒤에서 쪽 제목들을 보고 장(챕터)을 나누고, 챕터마다 핵심 개념을 뽑는다.
- 같은 교안의 새 판이 옛 판을 대체하면 새로 만들지 않고 옛 판의 챕터를 새 판으로 옮긴다.
- 이미 챕터가 있는 교안은 건너뛴다. 서버를 켤 때 챕터가 없는 교안을 찾아 채운다(backfill).
- 문제 생성(problems/generation.py)은 '챕터 → 그 교안 → 그 개념'으로 만들기 때문에 이게 먼저 있어야 한다.
"""

import logging
import re
import threading

from pydantic import BaseModel, Field
from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession
from sqlmodel import Session, func, select

from app.core.config import settings
from app.models import Chapter, Concept, Material
from app.services import llm

log = logging.getLogger(__name__)

MAX_CHAPTERS_PER_MATERIAL = 8
MAX_CONCEPTS = 10
_build_lock = threading.Lock()  # 한 번에 교안 하나씩(같은 강좌 순서·중복 방지)


class ConceptDraft(BaseModel):
    name: str = Field(description="핵심 개념 이름. 교안 용어 그대로의 짧은 명사구(20자 이내)")


class ChapterDraft(BaseModel):
    title: str = Field(description="챕터 제목. 교안에 장 번호·제목이 있으면 그대로(예: '3장 탐색')")
    start_page: int
    end_page: int
    concepts: list[ConceptDraft] = Field(description="이 챕터에서 시험에 나올 핵심 개념 4~8개")


class StructureDraft(BaseModel):
    chapters: list[ChapterDraft]


def _page_outline(pages: list[str]) -> str:
    """쪽마다 앞부분 몇 줄만(제목·소제목). 본문 전체를 보내지 않아 비용이 작다."""
    out = []
    for i, text in enumerate(pages, start=1):
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        head = " / ".join(lines[:3])[:160]
        out.append(f"p{i}: {head or '(빈 쪽)'}")
    return "\n".join(out)


def draft_structure(material: Material, existing_concepts: list[str]) -> StructureDraft | None:
    prompt = (
        f"## 교안: {material.title} (총 {len(material.pages)}쪽)\n"
        f"## 쪽별 앞부분\n{_page_outline(material.pages)}\n\n"
        f"## 이 강좌에 이미 있는 개념(같은 개념이면 이름을 그대로 쓰고, 새 개념만 새 이름)\n"
        f"{', '.join(existing_concepts) or '(없음)'}"
    )
    return llm._parse(
        "대학 강의 교안의 목차를 정리하는 도우미. 쪽별 앞부분을 보고 교안을 챕터(장)로 나누고, 챕터마다 "
        "시험에 나올 핵심 개념을 뽑는다. 교안에 '3장', 'Chapter 3' 같은 장 구분이 있으면 그 경계를 따르고, "
        f"없으면 주제가 바뀌는 곳에서 나눈다(교안 하나에 1~{MAX_CHAPTERS_PER_MATERIAL}개). 표지·목차·참고문헌·"
        "연습문제 정답만 있는 쪽은 앞 챕터에 붙인다. 쪽 범위는 겹치지 않게 앞에서부터 이어지게 한다. "
        "개념은 교안에 실제로 나오는 용어로, 너무 넓은 말(예: '기초', '개요')은 피한다. 한국어 교안이면 한국어로.",
        prompt,
        StructureDraft,
    )


def _clean(draft: StructureDraft, n_pages: int) -> list[ChapterDraft]:
    chapters = []
    for ch in draft.chapters[:MAX_CHAPTERS_PER_MATERIAL]:
        title = re.sub(r"\s+", " ", ch.title).strip()[:200]
        names = list(dict.fromkeys(re.sub(r"\s+", " ", c.name).strip()[:100] for c in ch.concepts))
        names = [n for n in names if n][:MAX_CONCEPTS]
        if not title or not names:
            continue
        start = min(max(ch.start_page, 1), n_pages)
        end = min(max(ch.end_page, start), n_pages)
        chapters.append(
            ChapterDraft(
                title=title,
                start_page=start,
                end_page=end,
                concepts=[ConceptDraft(name=n) for n in names],
            )
        )
    chapters.sort(key=lambda c: c.start_page)
    return chapters


def _repoint_from_old_version(session: Session, material: Material) -> int:
    """새 판이 옛 판을 대체했으면 옛 판에 연결된 챕터를 새 판으로 옮긴다. 옮긴 챕터 수."""
    old_ids = session.exec(select(Material.id).where(Material.replaced_by == material.id)).all()
    if not old_ids:
        return 0
    chapters = session.exec(select(Chapter).where(Chapter.material_id.in_(old_ids))).all()  # type: ignore[union-attr]
    for ch in chapters:
        ch.material_id = material.id
        session.add(ch)
    session.commit()
    return len(chapters)


def build_for_material(session: Session, material_id: int) -> int:
    """교안 하나의 챕터·개념을 만든다. 만든 챕터 수(건너뛰면 0)."""
    m = session.get(Material, material_id)
    if m is None or m.kind != "lecture" or m.status != "approved" or m.replaced_by is not None:
        return 0
    if session.exec(select(Chapter.id).where(Chapter.material_id == m.id)).first() is not None:
        return 0
    if _repoint_from_old_version(session, m):
        return 0
    if not any((p or "").strip() for p in m.pages):
        return 0
    existing = sorted(
        set(
            session.exec(
                select(Concept.name)
                .join(Chapter, Chapter.id == Concept.chapter_id)
                .where(Chapter.course_id == m.course_id)
            ).all()
        )
    )
    session.commit()  # AI를 기다리는 동안 DB 연결을 붙잡지 않게(오개념 쪽과 같은 이유)
    draft = draft_structure(m, existing)
    if draft is None:
        return 0
    chapters = _clean(draft, len(m.pages))
    if not chapters:
        return 0
    order = (
        session.exec(select(func.max(Chapter.order)).where(Chapter.course_id == m.course_id)).one()
        or 0
    )
    new_ids = []
    for ch in chapters:
        order += 1
        row = Chapter(course_id=m.course_id, order=order, title=ch.title, material_id=m.id)
        session.add(row)
        session.flush()
        new_ids.append(row.id)
        for c in ch.concepts:
            session.add(Concept(chapter_id=row.id, name=c.name))
    session.commit()
    # 새 단원마다 처음 문제를 채운다(학생이 처음 들어와도 모든 단원을 풀 수 있게)
    from app.features.problems import generation

    generation.spawn_initial_fill(session.get_bind(), new_ids)
    log.info("교안 %s(%s): 챕터 %d개를 만듦", m.id, m.title, len(chapters))
    return len(chapters)


def missing_material_ids(session: Session) -> list[int]:
    """챕터가 하나도 연결되지 않은 최신 승인 교안."""
    linked = select(Chapter.material_id).where(Chapter.material_id.is_not(None))  # type: ignore[union-attr]
    return list(
        session.exec(
            select(Material.id)
            .where(
                Material.kind == "lecture",
                Material.status == "approved",
                Material.replaced_by.is_(None),  # type: ignore[union-attr]
                Material.id.not_in(linked),  # type: ignore[union-attr]
            )
            .order_by(Material.course_id, Material.seq, Material.id)
        ).all()
    )


def run_for(bind, material_ids: list[int]) -> int:
    total = 0
    with _build_lock:
        for mid in material_ids:
            try:
                with Session(bind) as s:
                    total += build_for_material(s, mid)
            except Exception:
                log.exception("챕터·개념 자동 생성 실패: material %s", mid)
    return total


def backfill(bind) -> int:
    with Session(bind) as s:
        ids = missing_material_ids(s)
    return run_for(bind, ids) if ids else 0


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def spawn(bind, material_ids: list[int]) -> None:
    """테스트에서는 바꿔 끼워 같은 스레드에서 돌린다."""
    threading.Thread(target=run_for, args=(bind, material_ids), daemon=True).start()


# ---------- 교안이 저장되면 자동으로 ----------


@event.listens_for(OrmSession, "after_flush")
def _collect_new_lectures(session, _ctx) -> None:
    new = [o.id for o in session.new if isinstance(o, Material) and o.kind == "lecture" and o.id]
    if new:
        session.info.setdefault("new_lecture_ids", set()).update(new)


@event.listens_for(OrmSession, "after_rollback")
def _forget_lectures(session) -> None:
    session.info.pop("new_lecture_ids", None)


@event.listens_for(OrmSession, "after_commit")
def _build_after_commit(session) -> None:
    ids = session.info.pop("new_lecture_ids", None)
    if ids and enabled():
        spawn(session.get_bind(), sorted(ids))
