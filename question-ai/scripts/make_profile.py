"""출제 프로필만 만들고 검토하기 (M2).

    python scripts/make_profile.py --course demo            # 있으면 보여 주고 검사만
    python scripts/make_profile.py --course demo --new      # 기출·메모로 다시 만들기
    python scripts/make_profile.py --course demo --dry-run  # Analyst에 보낼 입력(번호 붙인 글·이미지 수)만 보기

결과: outputs/<과목>/profile.json — 직접 고친 뒤 run.py를 실행하면 그대로 쓴다.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # 설치된 qgen이 다른 폴더를 가리켜도 이 저장소 코드를 쓰게
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")  # Windows 콘솔 한글·기호 출력

from qgen import exam_profile, llm  # noqa: E402
from qgen.schemas import ExamProfile  # noqa: E402


def show(p: ExamProfile) -> None:
    print(f"과목: {p.course}  교수: {p.professor or '-'}")
    print("유형 비율: " + ", ".join(f"{k} {v:.0%}" for k, v in p.format_ratio.items()))
    print(f"문항 수: {p.num_questions}  세부 정도: {p.detail_level}  난이도: {p.difficulty}")
    for name, items in (("반복 패턴", p.recurring_patterns), ("발문 말투", p.phrasing_examples),
                        ("강조 주제", p.emphasized_topics), ("근거", p.evidence)):
        print(f"{name}:")
        for it in items or ["(없음)"]:
            print(f"  - {it}")
    if p.notes:
        print(f"메모: {p.notes}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", required=True)
    ap.add_argument("--new", action="store_true", help="이미 있어도 기출·메모로 다시 만든다")
    ap.add_argument("--dry-run", action="store_true", help="LLM을 부르지 않고 Analyst 입력만 보여 준다")
    a = ap.parse_args()

    course_dir = ROOT / "data" / a.course
    if not course_dir.exists():
        raise SystemExit(f"{course_dir} 폴더가 없습니다.")

    if a.dry_run:
        inp = exam_profile.build_input(course_dir)
        for w in inp.warnings:
            print(f"[경고] {w}")
        print("## 기출\n" + (inp.past_text or "(없음)"))
        print("\n## 첨부 이미지\n" + inp.image_list)
        print("\n## 메모\n" + (inp.notes_text or "(없음)"))
        print(f"\n번호 {len(inp.valid_ids)}개, 이미지 {len(inp.images)}장 "
              f"({sum(len(d) for d, _ in inp.images) // 1024}KB). 기출·메모 없음이면 LLM 없이 기본 프로필.")
        return

    llm.configure(log_path=None)
    profile = exam_profile.load_or_make(course_dir, a.course, new=a.new)
    print()
    show(profile)
    print(f"\n파일: {exam_profile.profile_path(a.course)} (직접 고친 뒤 run.py를 실행하면 그대로 씁니다)")


if __name__ == "__main__":
    main()
