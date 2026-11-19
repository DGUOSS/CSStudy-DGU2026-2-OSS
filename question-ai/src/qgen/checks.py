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
