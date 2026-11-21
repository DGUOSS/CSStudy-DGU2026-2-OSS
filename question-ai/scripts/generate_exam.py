"""검증된 시험 1세트 만들기 (명세 §9 M4): 계획 → 문항마다 생성 → 규칙 검사·코드 검산 → 블라인드 풀이 → 검토 → 수정.

    python scripts/generate_exam.py --course 26-CSC2011-02
    python scripts/generate_exam.py --course 26-CSC2011-02 --run-id 20261121-140000   # 같은 실행 다시 (아래 참고)
    python scripts/generate_exam.py --course demo --no-verify                          # 검증 없이 생성만

결과: outputs/<과목>/<실행>/
  exam.md (문제지), answers.md (정답·채점 기준·근거·검증 이력·코드 검산), report.md (시도별 검증 기록),
  profile.json, plan.json (+ 보충이 있으면 plan_final.json), exam.json, trace.json, logs.jsonl, summary.json

다시 실행: 같은 --run-id를 주면 저장된 plan.json을 그대로 쓰고, 모델 응답은 cache/에서 다시 읽는다.
중간에 멈춘 실행도 같은 --run-id로 다시 돌리면 멈추기 전까지의 호출은 모델을 부르지 않는다 (--no-cache면 전부 새로).
run.py와 같은 일을 한다 (run.py는 예전 사용법 그대로 둠).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # 설치된 qgen이 다른 폴더를 가리켜도 이 저장소 코드를 쓰게
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")  # Windows 콘솔 한글·기호 출력

from qgen import pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--course", required=True)
    ap.add_argument("--run-id", help="생략하면 실행 시각 (예: 20261121-140000)")
    ap.add_argument("--new-profile", action="store_true", help="기출·메모로 출제 프로필을 다시 만든다")
    ap.add_argument("--no-cache", action="store_true", help="모델 응답 캐시를 쓰지 않는다 (시간 측정할 때)")
    ap.add_argument("--no-verify", action="store_true", help="solver·reviewer 검증과 수정 없이 generator 1번으로 생성")
    a = ap.parse_args()
    pipeline.run(a.course, a.run_id, new_profile=a.new_profile, use_cache=not a.no_cache, verify=not a.no_verify)


if __name__ == "__main__":
    main()
