"""M2 출제 프로필: 기출·메모 → Analyst 입력(번호 붙인 글 + 이미지) → ExamProfile → 근거 검사.

- 근거를 코드로 확인할 수 있게 입력 줄마다 번호를 붙인다.
  메모 [M1], 기출 글자 줄 [E1.3](1번 파일 3번째 줄), 기출 이미지 [E2.p1](2번 파일 1쪽).
  Analyst는 evidence에 이 번호를 적고, validate()가 실제로 있는 번호인지 검사한다 (명세 §9 M2 완료 기준).
- 기출·메모가 모두 없으면 LLM을 부르지 않고 기본 프로필을 쓴다 (없는 경향을 지어내지 않게).
- 사진 기출과 글자가 부족하거나 그림이 있는 PDF 쪽은 이미지로 보낸다 (명세 §5 Analyst).
  이미지는 보내기만 하고 저장하지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .ingest.pdf_parser import parse_pdf, parse_text
from .schemas import ExamProfile

QTYPES = ("객관식", "단답형", "서술형", "계산형")
TEXT_EXT = (".md", ".txt")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_IMAGES = 12  # 한 번에 보내는 이미지 수 상한 (비용·시간)
MAX_SIDE = 1600  # 이미지 긴 변 (휴대폰 사진은 수 MB라 줄여서 보냄)

ID_TOKEN = re.compile(r"^(E\d+\.(?:p\d+|\d+)|M\d+)$")
BRACKET = re.compile(r"\[([^\[\]]+)\]")


def evidence_ids(ev: str) -> list[str]:
    """evidence 한 줄에서 근거 번호를 뽑는다. '[E1.2][M1]'도 '[E1.2, E1.4]'처럼 한 괄호에 여러 개도 인정."""
    out = []
    for grp in BRACKET.findall(ev):
        toks = [t for t in re.split(r"[,\s/·]+", grp.strip()) if t]
        if toks and all(ID_TOKEN.match(t) for t in toks):
            out += toks
    return out

DEFAULT_RATIO = {"객관식": 0.4, "단답형": 0.2, "서술형": 0.4}  # 계산형은 과목마다 달라 0
DEFAULT_NUM_QUESTIONS = 10


@dataclass
class AnalystInput:
    past_text: str = ""  # 번호 붙인 기출 글
    notes_text: str = ""  # 번호 붙인 메모
    images: list[tuple[bytes, str]] = field(default_factory=list)  # (JPEG 바이트, MIME)
    image_ids: list[str] = field(default_factory=list)  # images와 같은 순서의 번호
    valid_ids: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.past_text.strip() or self.notes_text.strip() or self.images)

    @property
    def image_list(self) -> str:
        if not self.image_ids:
            return "(없음)"
        return "\n".join(f"- 첨부 이미지 {i + 1}번째 = [{iid}]" for i, iid in enumerate(self.image_ids))


def _jpeg_from_image(path: Path, max_side: int = MAX_SIDE) -> bytes:
    import pymupdf

    with pymupdf.open(path) as doc:
        pg = doc[0]
        scale = min(1.0, max_side / max(pg.rect.width, pg.rect.height))
        return pg.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("jpeg", jpg_quality=80)


def _jpeg_from_pdf_page(path: Path, page_no: int, dpi: int = 100) -> bytes:
    import pymupdf

    with pymupdf.open(path) as doc:
        return doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=80)


def _numbered(prefix: str, lines: list[str], ids: set[str], start: int = 1) -> tuple[list[str], int]:
    out, n = [], start
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        iid = f"{prefix}{n}"
        ids.add(iid)
        out.append(f"[{iid}] {ln}")
        n += 1
    return out, n


def build_input(course_dir: Path, max_images: int = MAX_IMAGES) -> AnalystInput:
    inp = AnalystInput()
    past_dir, notes_f = course_dir / "past_exams", course_dir / "notes.md"
    pending_images: list[tuple[str, Path, int | None]] = []  # (번호, 파일, PDF 쪽 또는 None)

    blocks: list[str] = []
    files = sorted(f for f in past_dir.iterdir() if f.is_file()) if past_dir.exists() else []
    f_no = 0
    for f in files:
        ext = f.suffix.lower()
        if ext not in (".pdf", *TEXT_EXT, *IMAGE_EXT):
            if f.name not in ("Thumbs.db", ".DS_Store"):
                inp.warnings.append(f"기출 폴더의 {f.name}: 지원하지 않는 형식이라 건너뜀")
            continue
        f_no += 1
        head = f"### [E{f_no}] {f.name}"
        if ext in IMAGE_EXT:
            iid = f"E{f_no}.p1"
            inp.valid_ids.add(iid)
            pending_images.append((iid, f, None))
            blocks.append(f"{head}\n(사진 기출 → 첨부 이미지 [{iid}])")
            continue
        report = parse_text(f) if ext in TEXT_EXT else parse_pdf(f)
        lines_out: list[str] = []
        n = 1
        for pg in report.pages:
            if ext == ".pdf" and (pg.low_text or pg.has_figure):
                iid = f"E{f_no}.p{pg.page}"
                inp.valid_ids.add(iid)
                pending_images.append((iid, f, pg.page))
                lines_out.append(f"(p.{pg.page}: 글자가 부족하거나 그림이 있어 첨부 이미지 [{iid}]로도 보냄)")
            numbered, n = _numbered(f"E{f_no}.", pg.text.splitlines(), inp.valid_ids, n)
            lines_out += numbered
        blocks.append(head + "\n" + "\n".join(lines_out))
    inp.past_text = "\n\n".join(blocks)

    if notes_f.exists():
        numbered, _ = _numbered("M", notes_f.read_text(encoding="utf-8").splitlines(), inp.valid_ids)
        inp.notes_text = "\n".join(numbered)

    if len(pending_images) > max_images:
        dropped = [iid for iid, _, _ in pending_images[max_images:]]
        inp.warnings.append(f"기출 이미지가 {len(pending_images)}장이라 앞의 {max_images}장만 보냄: {dropped} 제외")
        for iid in dropped:
            inp.valid_ids.discard(iid)
        pending_images = pending_images[:max_images]
    for iid, f, page in pending_images:
        data = _jpeg_from_image(f) if page is None else _jpeg_from_pdf_page(f, page)
        inp.images.append((data, "image/jpeg"))
        inp.image_ids.append(iid)
    return inp


def default_profile(course: str) -> ExamProfile:
    """기출·메모가 없을 때. 경향을 지어내지 않도록 중립값만 넣고 근거·강조 주제는 비운다."""
    return ExamProfile(
        course=course, format_ratio=dict(DEFAULT_RATIO), num_questions=DEFAULT_NUM_QUESTIONS,
        detail_level="중간", difficulty="보통", recurring_patterns=[], phrasing_examples=[], emphasized_topics=[],
        notes="기출·메모 없음: 분석 없이 기본값으로 만든 프로필. 기출이나 메모를 넣고 다시 만들면 바뀐다.",
        evidence=[],
    )


def validate(profile: ExamProfile, inp: AnalystInput | None = None) -> list[str]:
    """프로필 검사 → 문제 목록 (빈 목록이면 통과)."""
    issues: list[str] = []
    bad = [k for k in profile.format_ratio if k not in QTYPES]
    if bad:
        issues.append(f"format_ratio에 알 수 없는 유형 {bad} (가능: {list(QTYPES)})")
    if any(v < 0 for v in profile.format_ratio.values()):
        issues.append("format_ratio에 음수가 있음")
    total = sum(profile.format_ratio.values())
    if abs(total - 1) > 0.01:
        issues.append(f"format_ratio 합이 {total:.2f} (1이어야 함)")
    if not 1 <= profile.num_questions <= 50:
        issues.append(f"num_questions {profile.num_questions}이 1~50 밖")
    if inp is None:
        return issues
    if not inp.has_data:
        if profile.evidence:
            issues.append("기출·메모가 없는데 evidence가 있음 (지어낸 근거)")
        return issues
    if not profile.evidence:
        issues.append("evidence가 비어 있음 (기출·메모가 있으면 근거를 적어야 함)")
    for ev in profile.evidence:
        ids = evidence_ids(ev)
        if not ids:
            issues.append(f"근거 번호가 없는 evidence: {ev!r}")
        unknown = [i for i in ids if i not in inp.valid_ids]
        if unknown:
            issues.append(f"없는 번호를 가리키는 evidence {unknown}: {ev!r}")
    return issues


def profile_path(course: str) -> Path:
    """과목 공용 profile.json. 사용자가 직접 고쳐도 되고, 있으면 다시 만들지 않는다."""
    from . import llm

    return llm.ROOT / "outputs" / course / "profile.json"


def load_or_make(course_dir: Path, course: str, new: bool = False, verbose: bool = True) -> ExamProfile:
    f = profile_path(course)
    if f.exists() and not new:
        profile = ExamProfile.model_validate_json(f.read_text(encoding="utf-8"))
        # 직접 고쳤거나 예전 방식으로 만든 프로필도 지금 기출·메모 기준으로 근거까지 검사 (LLM 호출 없음)
        issues = validate(profile, build_input(course_dir))
        if verbose:
            print(f"[analyst] 기존 프로필 재사용: {f}")
    else:
        profile, issues, inp = make(course_dir, course)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        if verbose:
            for w in inp.warnings:
                print(f"[analyst] 경고: {w}")
            if inp.has_data:
                print(f"[analyst] 프로필 생성 (기출 이미지 {len(inp.images)}장) → {f}")
            else:
                print(f"[analyst] 기출·메모 없음 → LLM 없이 기본 프로필 → {f}")
    if verbose:
        for i in issues:
            print(f"[analyst] 검사: {i}")
    return profile


def make(course_dir: Path, course: str | None = None) -> tuple[ExamProfile, list[str], AnalystInput]:
    """기출·메모로 프로필을 만든다 → (프로필, 검사 결과, 입력). 기출·메모가 없으면 LLM을 부르지 않는다."""
    from . import agents

    course = course or course_dir.name
    inp = build_input(course_dir)
    profile = agents.analyst(course, inp) if inp.has_data else default_profile(course)
    return profile, validate(profile, inp), inp
