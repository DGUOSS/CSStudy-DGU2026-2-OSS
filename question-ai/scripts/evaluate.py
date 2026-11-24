"""M5 평가: 가린 채점 자료 만들기 → (Claude 채팅으로 채점) → 조건별 결과표.

    # 1) 채점 자료 만들기: 조건 이름:실행 이름 을 여러 개
    python scripts/evaluate.py export --course 26-CSC2011-02 --name 형식확인 \\
        --run 검증없음:20261121-112829 --run 검증:20261121-162212
    #    → question-ai/for judge/<name>/ (README.md, judge_prompt.md, items_partNN.md)
    #    → 대응표는 outputs/<과목>/experiments/<name>/judge_key.json (for judge 밖)

    # 2) README.md대로 Claude 채팅에 붙여 넣고, 받은 JSON을 for judge/<name>/scores_partNN.json으로 저장

    # 3) 결과표
    python scripts/evaluate.py score --course 26-CSC2011-02 --name 형식확인
    #    → outputs/<과목>/experiments/<name>/report.md, scores.json

채점 자료에는 출제에 쓴 모델·조건·실행 이름, 검증 이력을 넣지 않는다 (qgen/evaluate.py 설명 참고).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # 설치된 qgen이 다른 폴더를 가리켜도 이 저장소 코드를 쓰게
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from qgen import evaluate as ev  # noqa: E402
from qgen.ingest import load_chunks  # noqa: E402
from qgen.schemas import ExamProfile  # noqa: E402

JUDGE_ROOT = ROOT / ev.JUDGE_DIR_NAME


def key_dir(course: str, name: str) -> Path:
    return ROOT / "outputs" / course / "experiments" / name


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="가린 채점 자료 만들기")
    e.add_argument("--course", required=True)
    e.add_argument("--name", required=True, help="채점 묶음 이름 (for judge/ 아래 폴더 이름)")
    e.add_argument("--run", action="append", required=True, help="조건이름:실행이름 (같은 조건 여러 번 = 세트 여러 개)")
    e.add_argument("--seed", type=int, default=0, help="문항 섞는 순서")
    s = sub.add_parser("score", help="채점 결과로 조건별 결과표 만들기")
    s.add_argument("--course", required=True)
    s.add_argument("--name", required=True)
    a = ap.parse_args()

    course_out = ROOT / "outputs" / a.course
    if a.cmd == "export":
        refs, seen = [], {}
        for spec in a.run:
            cond, _, run_id = spec.partition(":")
            if not run_id:
                raise SystemExit(f"--run은 '조건이름:실행이름' 형식이어야 함: {spec}")
            seen[cond] = seen.get(cond, 0) + 1
            refs.append(ev.RunRef(cond, seen[cond], course_out / run_id))
        chunks = load_chunks(ROOT / "data" / a.course, verbose=False)
        out = ev.export(a.name, refs, chunks, JUDGE_ROOT, key_dir(a.course, a.name), seed=a.seed)
        print(f"[judge] 채점 자료: {out}  (대응표: {key_dir(a.course, a.name) / 'judge_key.json'})")
        print((out / "README.md").read_text(encoding="utf-8"))
    else:
        kd = key_dir(a.course, a.name)
        pf = course_out / "profile.json"
        profile = ExamProfile.model_validate_json(pf.read_text(encoding="utf-8")) if pf.exists() else None
        table, raw = ev.score(kd / "judge_key.json", JUDGE_ROOT / a.name, profile)
        (kd / "scores.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        (kd / "report.md").write_text(f"# 평가 결과 — {a.name}\n\n{table}\n", encoding="utf-8")
        print(table)
        print(f"\n→ {kd / 'report.md'}")


if __name__ == "__main__":
    main()
