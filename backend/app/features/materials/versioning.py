"""강좌 자료의 판 관리. 파일명·주차·교안 양식에 기대지 않고 쪽(슬라이드) 내용으로 판단한다.

교수마다 교안 구성이 다르다(주차별 파일, 학기 전체 큰 파일 하나, 양식 없는 문서 등).
그래서 새 자료의 쪽마다 같은 강좌·같은 종류의 최신판 자료들의 모든 쪽과 비교해 가장 비슷한 쪽을 찾는다.

- 쪽 분류: 같음(유사도 >= SAME_PAGE), 수정됨(>= MODIFIED_PAGE), 새 내용(그 아래)
- 새 자료의 모든 쪽이 '같음'이면 등록하지 않는다 ("duplicate").
- 기존 자료의 쪽 가운데 COVER 이상이 새 자료에 '같음/수정됨'으로 들어 있으면, 그 기존 자료는 새 자료로 대체된다.
  (주차 파일 여러 개를 큰 파일 하나로 다시 올리면 여러 개가 한꺼번에 대체된다) ("updated")
- 대체되는 자료가 없으면 새 자료로 등록한다 ("new"). 큰 교안의 일부만 고친 파일이 이 경우다.
- 어느 경우든, 근거 문장이 새 자료에 있는 문제는 근거를 새 자료의 그 쪽으로 옮긴다(최신 쪽을 가리키게).
  옛 판은 지우지 않는다. 근거 문장을 못 찾은 문제는 옛 판 링크를 그대로 쓴다.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from sqlmodel import Session, select

from app.models import Chapter, Material, Problem

SAME_PAGE = 0.9
MODIFIED_PAGE = 0.5
COVER = 0.7
MIN_PAGE_CHARS = 20  # 표지·빈 쪽처럼 글자가 거의 없는 쪽은 판단에서 뺀다

Action = Literal["new", "updated", "duplicate"]

_WEEK = re.compile(r"(?:week|wk|w)[\s_\-]*0*(\d{1,2})|0*(\d{1,2})\s*주\s*차?", re.IGNORECASE)


def parse_week(*texts: str) -> int | None:
    """표시용 주차. 판 관리 판단에는 쓰지 않는다."""
    for t in texts:
        m = _WEEK.search(t or "")
        if m:
            return int(m.group(1) or m.group(2))
    return None


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _grams(text: str) -> frozenset[str]:
    s = _norm(text)
    return frozenset(s[i : i + 3] for i in range(len(s) - 2))


def _sim(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Diff:
    same: int = 0
    modified: int = 0
    new: int = 0
    replaced: list[int] = field(default_factory=list)  # 대체되는 기존 자료 id


def diff_pages(new_pages: list[str], olds: list[Material]) -> Diff:
    """새 자료의 쪽을 기존 자료들의 쪽과 맞춰 본다."""
    d = Diff()
    old_grams = [(m, [_grams(p) for p in m.pages]) for m in olds]
    covered: dict[int, set[int]] = {m.id: set() for m in olds}
    for page in new_pages:
        if len(_norm(page)) < MIN_PAGE_CHARS:
            continue
        g = _grams(page)
        best, best_at = 0.0, None
        for m, pages in old_grams:
            for i, og in enumerate(pages):
                s = _sim(g, og)
                if s > best:
                    best, best_at = s, (m.id, i)
        if best >= SAME_PAGE:
            d.same += 1
        elif best >= MODIFIED_PAGE:
            d.modified += 1
        else:
            d.new += 1
        if best >= MODIFIED_PAGE and best_at:
            covered[best_at[0]].add(best_at[1])
    for m in olds:
        real = [i for i, p in enumerate(m.pages) if len(_norm(p)) >= MIN_PAGE_CHARS]
        if real and len(covered[m.id] & set(real)) / len(real) >= COVER:
            d.replaced.append(m.id)
    return d


def relink_problems(session: Session, course_id: int, material: Material) -> int:
    """근거 문장이 이 자료에 있는 문제는 근거를 이 자료의 그 쪽으로 옮긴다."""
    pages = [_norm(p) for p in material.pages]
    moved = 0
    probs = session.exec(
        select(Problem)
        .join(Chapter, Chapter.id == Problem.chapter_id)
        .where(Chapter.course_id == course_id, Problem.evidence.is_not(None))  # type: ignore[union-attr]
    ).all()
    for prob in probs:
        key = _norm(prob.evidence or "")
        page = next((i + 1 for i, p in enumerate(pages) if key and key in p), None)
        if page and (prob.source_material_id, prob.source_page) != (material.id, page):
            prob.source_material_id, prob.source_page = material.id, page
            session.add(prob)
            moved += 1
    return moved


def add_material(
    session: Session,
    *,
    course_id: int,
    uploader_id: int | None,
    kind: str,
    title: str,
    filename: str,
    pages: list[str],
) -> tuple[Material, Action, int, Diff]:
    """판 관리 규칙에 따라 자료를 등록한다. (자료, 동작, 근거를 옮긴 문제 수, 쪽 비교 결과). commit은 하지 않는다."""
    latest = session.exec(
        select(Material).where(
            Material.course_id == course_id,
            Material.kind == kind,
            Material.replaced_by.is_(None),  # type: ignore[union-attr]
        )
    ).all()
    d = diff_pages(pages, latest)
    if latest and d.same > 0 and d.modified == 0 and d.new == 0:
        # 새 내용이 하나도 없다: 가장 많이 겹치는 기존 자료를 돌려준다
        dup = max(latest, key=lambda m: _sim(_grams("".join(pages)), _grams("".join(m.pages))))
        return dup, "duplicate", 0, d
    replaced = [m for m in latest if m.id in d.replaced]
    material = Material(
        course_id=course_id,
        uploader_id=uploader_id,
        kind=kind,
        title=title,
        filename=filename,
        page_count=len(pages),
        pages=pages,
        week=parse_week(title, filename),
        version=max((m.version for m in replaced), default=0) + 1,
    )
    session.add(material)
    session.flush()
    for m in replaced:
        m.replaced_by = material.id
        session.add(m)
    moved = relink_problems(session, course_id, material) if kind == "lecture" else 0
    return material, ("updated" if replaced else "new"), moved, d
