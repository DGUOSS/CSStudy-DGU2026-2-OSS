"""규칙 기반 검사 (LLM 미사용, 비용 0)."""
from __future__ import annotations

import re

from .schemas import Chunk, PlannedItem, Question


def _latex_issues(text: str) -> list[str]:
    issues = []
    if text.replace("$$", "").count("$") % 2:
        issues.append("LaTeX `$` 짝이 맞지 않음")
    if text.count("{") != text.count("}"):
        issues.append("중괄호 `{}` 짝이 맞지 않음")
    return issues


MULTI_SELECT = re.compile(r"모두\s*(고르|골라|찾|선택)|있는\s*대로|전부\s*고르|all\s+that\s+apply|select\s+all", re.I)

COPY_NGRAM = 3
COPY_THRESHOLD = 0.25  # config.yaml pipeline.copy_threshold로 바꿀 수 있음


def _grams(text: str, n: int = COPY_NGRAM) -> set[str]:
    t = re.sub(r"[^0-9a-z가-힣]", "", text.lower())  # 띄어쓰기·기호·수식 기호 무시
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def overlap(a: str, b: str, n: int = COPY_NGRAM) -> float:
    """글자 n개 조각 겹침 비율 (짧은 글 기준). 문장을 베꼈는지 보는 용도 — 같은 주제인지는 보지 않는다."""
    ga, gb = _grams(a, n), _grams(b, n)
    return len(ga & gb) / max(1, min(len(ga), len(gb)))


def copy_issues(q: Question, past: list[tuple[str, str]], threshold: float = COPY_THRESHOLD) -> list[str]:
    """기출 문항(이름, 원문)과 문제 본문·선지의 글자 겹침이 threshold 이상이면 '베끼기'.

    명세 §6은 '임베딩 유사도 > 0.9'였으나 실제 측정(2026-11-21, 컴퓨터구성 8문항 × 기출 7문항)에서
    e5 유사도는 주제만 같아도 0.91~0.93, 기출끼리도 0.91이라 구분이 안 됨. 3글자 조각 겹침은
    문장을 베낀 문항 0.32, 나머지 0.10~0.19, 기출끼리 0.14 → 0.25.
    표현만 바꾼 같은 질문은 이 방법으로도 못 잡는다 → reviewer가 기출 예시를 보고 판단.
    """
    text = " ".join([q.stem, *(q.choices or [])])
    out = []
    for name, src in past:
        r = overlap(text, src)
        if r >= threshold:
            out.append(f"기출 {name} 문장과 겹침 {r:.2f} (기준 {threshold}) — 기출 문장·구성을 쓰지 말고 다른 상황·조건으로 다시 쓸 것")
    return out


def run(q: Question, item: PlannedItem, chunks: list[Chunk]) -> list[str]:
    issues: list[str] = []
    if q.qtype == "객관식":
        ch = q.choices or []
        if not 4 <= len(ch) <= 5:
            issues.append(f"객관식 선지 개수가 {len(ch)}개 (4~5개 필요)")
        if len(set(c.strip() for c in ch)) != len(ch):
            issues.append("중복된 선지가 있음")
        nums = re.findall(r"\d+", q.answer)
        if not nums or not all(1 <= int(n) <= len(ch) for n in nums):
            issues.append(f"정답 번호 '{q.answer}'가 선지 범위(1~{len(ch)})를 벗어남")
        # 명세 §6 "모두 고르시오 등 형식 일치": 정답이 여러 개면 문제에 그렇게 적혀 있어야 한다
        if len(set(nums)) != len(nums):
            issues.append(f"정답 번호가 겹침: '{q.answer}'")
        if len(set(nums)) > 1 and not MULTI_SELECT.search(q.stem):
            issues.append(f"정답이 여러 개({q.answer})인데 문제에 '모두 고르시오' 같은 표시가 없음")
        lens = [len(c) for c in ch]
        if ch and nums and nums[0].isdigit() and 1 <= int(nums[0]) <= len(ch):
            ans_len = lens[int(nums[0]) - 1]
            others = [l for i, l in enumerate(lens) if i != int(nums[0]) - 1]
            if others and ans_len > 2 * max(others):
                issues.append("정답 선지만 지나치게 길어 정답이 드러남")
    elif q.choices:
        issues.append(f"{q.qtype} 문항에 선지가 있음")
    if q.qtype in ("서술형", "계산형") and not q.model_answer:
        issues.append("서술형/계산형인데 model_answer가 없음")
    if q.qtype == "서술형" and not q.rubric:
        issues.append("서술형인데 rubric(채점 기준)이 없음")
    for field in [q.stem, q.answer, q.model_answer or "", *(q.choices or [])]:
        issues += _latex_issues(field)
    if not q.sources:
        issues.append("sources(강의자료 근거)가 비어 있음")
    valid = {(c.source.file, c.source.page) for c in chunks}
    for s in q.sources:
        if (s.file, s.page) not in valid:
            issues.append(f"존재하지 않는 근거 위치: {s.file} p.{s.page} (제공된 자료 위치만 사용)")
    return sorted(set(issues))
