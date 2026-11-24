"""M5 비교 실험: 같은 계획으로 4개 조건 × N세트 생성 → for judge/에 가린 채점 자료.

    python scripts/run_experiments.py --course 26-CSC2011-02 --sets 1            # 먼저 작게
    python scripts/run_experiments.py --course 26-CSC2011-02 --sets 3 --name 실험2
    python scripts/run_experiments.py --course 26-CSC2011-02 --conditions single multi_cross
    python scripts/run_experiments.py --course 26-CSC2011-02 --swap --sets 1 --plan-from 실험_20261121-175530  # 모델 바꿔 넣기

조건: single(검증 없음) / multi_same(solver = generator와 같은 모델) / multi_cross(지금 설정) / multi_no_loop(판정만)
결과: outputs/<과목>/experiments/<이름>/ (plan.json, runs/<조건>-s<세트>/, runs.json, judge_key.json)
      question-ai/for judge/<이름>/ (채점 자료 — 출제 모델·조건 이름 없음)
같은 --name으로 다시 실행하면 끝난 세트는 건너뛴다 (중간에 멈췄을 때 이어서).
채점 후: python scripts/evaluate.py score --course <과목> --name <이름>
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # 설치된 qgen이 다른 폴더를 가리켜도 이 저장소 코드를 쓰게
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from qgen import experiments  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--course", required=True)
    ap.add_argument("--name", help="실험 이름 (for judge/ 폴더 이름도 됨). 생략하면 '실험_<시각>'")
    ap.add_argument("--sets", type=int, default=3, help="조건마다 만들 세트 수 (명세 기본 3)")
    ap.add_argument("--conditions", nargs="+", default=None,
                    choices=experiments.CONDITIONS + experiments.SWAP_CONDITIONS)
    ap.add_argument("--swap", action="store_true",
                    help="모델 바꿔 넣기 실험: 세 모델이 generator·solver·reviewer를 한 번씩 맡는 3가지 조합")
    ap.add_argument("--plan-from", help="다른 실험 이름 — 그 실험의 plan.json을 그대로 사용")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    name = a.name or f"실험_{time.strftime('%Y%m%d-%H%M%S')}"
    conds = a.conditions or (experiments.SWAP_ROTATIONS if a.swap else experiments.CONDITIONS)
    experiments.run(a.course, name, sets=a.sets, conditions=conds, use_cache=not a.no_cache,
                    plan_from=a.plan_from)


if __name__ == "__main__":
    main()
