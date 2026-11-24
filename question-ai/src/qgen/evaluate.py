"""M5 평가: 실행 결과 → 가린 채점 자료(for judge/) → 채점 결과 → 조건별 지표.

judge는 API로 부르지 않고 사람이 채점 자료를 Claude 채팅에 붙여 넣어 채점한다 (2026-11-21 결정, 문제사항 E-01).
- 채점 자료에는 출제 정보(모델 이름, 조건, 실행 이름, 검증 이력, 코드 검산)를 넣지 않는다. 문항 순서를 섞고 J001… 번호를 새로 붙인다.
- 채점 번호 → 원래 (조건, 실행, 문항) 대응표(judge_key.json)는 for judge 밖(outputs/)에 둔다.
- 모델 이름이 섞여 들어가면 만들기를 멈춘다 (FORBIDDEN).
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .schemas import Chunk, ExamPlan, ExamProfile, Question

JUDGE_DIR_NAME = "for judge"
ITEMS_PER_PART = 6  # 채팅 한 번에 붙여 넣을 문항 수
QGEVAL = ["유창성", "명확성", "간결성", "관련성", "일관성", "답변 가능성", "답 일관성"]  # 명세 §7, 1~3점
# 채점 자료에 나오면 안 되는 말 (출제에 쓴 모델·회사 이름). 조건 이름·에이전트 이름은 코드가 애초에 쓰지 않는다
# ('single'·'generator'는 교안에도 나오는 말이라 막으면 안 됨: IEEE 754 Single Precision 등)
FORBIDDEN = re.compile(r"gemini|\bgpt|openai|claude|anthropic|\bhaiku\b|\bsonnet\b|\bopus\b|llama|mistral|litellm|"
                       r"multi_cross|multi_same|multi_no_loop", re.I)


@dataclass
class RunRef:
    condition: str  # 실험 조건 이름 (대응표에만 남음)
    set_no: int
    run_dir: Path


def _load_run(run_dir: Path) -> tuple[ExamPlan, dict[str, Question], dict]:
    plan_f = run_dir / "plan_final.json" if (run_dir / "plan_final.json").exists() else run_dir / "plan.json"
    plan = ExamPlan.model_validate_json(plan_f.read_text(encoding="utf-8"))
    exam = {k: Question.model_validate(v) for k, v in
            json.loads((run_dir / "exam.json").read_text(encoding="utf-8")).items()}
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    return plan, exam, summary


def _context(q: Question, chunks: list[Chunk], max_chars: int = 3500) -> str:
    """문항이 근거로 적은 교안 쪽의 글 (judge가 강의자료만 보고 풀고, 근거를 판단하게)."""
    want = {(s.file, s.page) for s in q.sources}
    parts = [f"[{c.source.file} p.{c.source.page}]\n{c.text}" for c in chunks if (c.source.file, c.source.page) in want]
    text = "\n\n".join(parts) or "(근거로 적힌 교안 쪽을 찾지 못함)"
    return text if len(text) <= max_chars else text[:max_chars] + "\n…(이하 생략)"


def _item_block(jid: str, q: Question, chunks: list[Chunk]) -> str:
    lines = [f"## {jid} ({q.qtype})", "", "### 문제", q.stem.strip()]
    if q.choices:
        lines += [""] + [f"{i}) {c}" for i, c in enumerate(q.choices, 1)]
    lines += ["", "### 강의자료 (이 문항이 근거로 적은 쪽)", _context(q, chunks), "",
              "### 출제 정답", q.answer.strip()]
    if q.model_answer:
        lines += ["", "### 모범답안", q.model_answer.strip()]
    if q.rubric:
        lines += ["", "### 채점 기준", *[f"- {r}" for r in q.rubric]]
    return "\n".join(lines)


JUDGE_PROMPT = """# 채점 지시

너는 대학 전공 시험 문항의 **품질을 채점하는 평가자**다. 아래 문항들은 시험 문제 자동 생성 실험에서 나온 것이다.
문항마다 다음 순서로 판단하라. 문항 사이에 정보가 섞이지 않게 하나씩 독립적으로 본다.

1. **풀이**: 출제 정답·모범답안을 보기 전에, 문제와 **함께 준 강의자료만** 보고 직접 푼다. (judge_answer)
2. **정답 판정** (answer_correct): 네 풀이와 출제 정답을 비교한다.
   - "맞음": 출제 정답이 옳다 / "틀림": 출제 정답이 틀렸다 / "판단불가": 강의자료와 문제만으로 정답을 정할 수 없다
   - 계산 문제는 직접 계산해서 확인한다. 서술형은 출제 정답·모범답안 내용이 옳은지 본다.
3. **모호함** (ambiguous): 조건이 부족하거나 답이 여러 개로 갈릴 수 있으면 true.
4. **근거** (grounded): 함께 준 강의자료가 출제 정답을 실제로 뒷받침하면 true. 강의자료에 없는 지식이 정답에 꼭 필요하면 false.
5. **품질 7항목** (qgeval): 각 1~3점 (1 나쁨, 2 보통, 3 좋음).
   - 유창성: 문장이 자연스럽고 문법이 맞는가
   - 명확성: 무엇을 묻는지 분명한가
   - 간결성: 불필요한 말 없이 필요한 정보만 있는가
   - 관련성: 강의자료 내용과 관련 있는가
   - 일관성: 문제 안의 조건·기호·수치가 서로 맞는가
   - 답변 가능성: 강의자료를 공부한 학생이 풀 수 있는가
   - 답 일관성: 출제 정답·모범답안·채점 기준이 문제와 맞는가
6. **comment**: 판정 이유를 한두 문장으로.

## 출력 형식

설명 없이 아래 JSON 하나만 출력한다. 이 파일에 있는 모든 문항을 빠짐없이, 번호 순서대로 넣는다.

```json
{"scores": [
  {"id": "J001", "judge_answer": "…", "answer_correct": "맞음", "ambiguous": false, "grounded": true,
   "qgeval": {"유창성": 3, "명확성": 3, "간결성": 2, "관련성": 3, "일관성": 3, "답변 가능성": 3, "답 일관성": 3},
   "comment": "…"}
]}
```
"""

README = """# 채점 자료 — {name}

문항 {n}개, 파일 {parts}개. 출제 방식에 대한 정보는 들어 있지 않다.

## 채점하는 법
1. 채팅을 새로 연다. (파일마다 새 대화를 권장)
2. `judge_prompt.md` 내용과 `items_partNN.md` 하나를 함께 붙여 넣는다.
3. 채팅에서 받은 JSON을 `scores_partNN.json`으로 이 폴더에 저장한다 (파일 번호를 맞춘다).
4. 모든 파일을 채점했으면 저장소에서 실행:
   `python scripts/evaluate.py score --name "{name}"`

## 파일
{files}
"""


def check_blind(text: str) -> None:
    m = FORBIDDEN.search(text)
    if m:
        raise ValueError(f"채점 자료에 출제 정보로 보이는 말이 있음: '{m.group(0)}' … {text[max(0, m.start() - 40):m.end() + 40]!r}")


def export(name: str, runs: list[RunRef], chunks: list[Chunk], judge_root: Path, key_dir: Path,
           seed: int = 0, per_part: int = ITEMS_PER_PART) -> Path:
    """실행들의 통과 문항을 섞어 가린 채점 자료를 만든다 → for judge/<name>/. 대응표는 key_dir/judge_key.json."""
    entries = []
    for ref in runs:
        plan, exam, _ = _load_run(ref.run_dir)
        for item in plan.items:
            if item.item_id in exam:
                entries.append((ref, item.item_id, exam[item.item_id]))
    if not entries:
        raise ValueError("채점할 문항이 없음 (exam.json이 비어 있음)")
    random.Random(seed).shuffle(entries)
    out = judge_root / name
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("items_part*.md"):
        old.unlink()
    key, files = {}, []
    for p in range(0, len(entries), per_part):
        part = p // per_part + 1
        blocks = []
        for k, (ref, item_id, q) in enumerate(entries[p:p + per_part], start=p + 1):
            jid = f"J{k:03d}"
            key[jid] = {"condition": ref.condition, "set": ref.set_no, "run": ref.run_dir.name, "item": item_id,
                        "qtype": q.qtype}
            blocks.append(_item_block(jid, q, chunks))
        text = f"# 채점 문항 {part}번 파일\n\n" + "\n\n---\n\n".join(blocks) + "\n"
        check_blind(text)
        fname = f"items_part{part:02d}.md"
        (out / fname).write_text(text, encoding="utf-8")
        ids = [f"J{k:03d}" for k in range(p + 1, min(p + per_part, len(entries)) + 1)]
        files.append(f"- `{fname}` → `scores_part{part:02d}.json` ({ids[0]}~{ids[-1]})")
    check_blind(JUDGE_PROMPT)
    (out / "judge_prompt.md").write_text(JUDGE_PROMPT, encoding="utf-8")
    readme = README.format(name=name, n=len(entries), parts=len(files), files="\n".join(files))
    check_blind(readme)
    (out / "README.md").write_text(readme, encoding="utf-8")
    key_dir.mkdir(parents=True, exist_ok=True)
    (key_dir / "judge_key.json").write_text(json.dumps(
        {"name": name, "runs": [{"condition": r.condition, "set": r.set_no, "run": str(r.run_dir)} for r in runs],
         "items": key}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _parse_scores(text: str) -> list[dict]:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    data = json.loads(m.group(1) if m else text)
    return data["scores"] if isinstance(data, dict) else data


def load_scores(judge_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(judge_dir.glob("scores_part*.json")):
        for s in _parse_scores(f.read_text(encoding="utf-8")):
            out[s["id"]] = s
    return out


def tvd(a: dict[str, float], b: dict[str, float]) -> float:
    """유형 분포 거리 (total variation distance, 명세 §7 프로필 부합도)."""
    ta, tb = sum(a.values()) or 1, sum(b.values()) or 1
    keys = set(a) | set(b)
    return round(0.5 * sum(abs(a.get(k, 0) / ta - b.get(k, 0) / tb) for k in keys), 3)


def score(key_file: Path, judge_dir: Path, profile: ExamProfile | None = None) -> tuple[str, dict]:
    """채점 결과 + 대응표 → 조건별 지표 표(Markdown)와 원자료."""
    key = json.loads(key_file.read_text(encoding="utf-8"))
    scores = load_scores(judge_dir)
    missing = [j for j in key["items"] if j not in scores]
    by_cond: dict[str, dict] = {}
    for r in key["runs"]:
        c = by_cond.setdefault(r["condition"], {"runs": [], "items": []})
        run_dir = Path(r["run"])
        plan, exam, summary = _load_run(run_dir)
        tf = run_dir / "trace.json"
        trace = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else []
        tries = Counter(t["item"] for t in trace)
        lf = run_dir / "logs.jsonl"  # 캐시에서 읽은 호출도 한 줄씩 남음 → 조건끼리 비용 비교용 (캐시를 공유하면 api_calls가 0이 될 수 있음)
        all_calls = sum(1 for line in lf.read_text(encoding="utf-8").splitlines() if line.strip()) if lf.exists() else 0
        c["runs"].append({"summary": summary, "qtypes": Counter(q.qtype for q in exam.values()),
                          "tries": [tries.get(i.item_id, 0) for i in plan.items], "all_calls": all_calls})
    for jid, k in key["items"].items():
        if jid in scores:
            by_cond[k["condition"]]["items"].append(scores[jid])
    rows = []
    for cond, c in by_cond.items():
        it, runs = c["items"], c["runs"]
        n = len(it) or 1
        qg = [sum(s["qgeval"].get(d, 0) for d in QGEVAL) / len(QGEVAL) for s in it if s.get("qgeval")]
        sm = [r["summary"] for r in runs]
        dist = [tvd(dict(r["qtypes"]), profile.format_ratio) for r in runs] if profile else []
        rows.append({
            "조건": cond, "세트": len(runs), "문항": len(it),
            "정답 오류율": round(sum(s.get("answer_correct") == "틀림" for s in it) / n, 3),
            "판단불가": round(sum(s.get("answer_correct") == "판단불가" for s in it) / n, 3),
            "모호성 비율": round(sum(bool(s.get("ambiguous")) for s in it) / n, 3),
            "근거율": round(sum(bool(s.get("grounded")) for s in it) / n, 3),
            "품질 평균(1~3)": round(sum(qg) / len(qg), 2) if qg else None,
            "유형 분포 거리": round(sum(dist) / len(dist), 3) if dist else None,
            "통과/계획": f"{sum(x['accepted'] for x in sm)}/{sum(x['planned'] for x in sm)}",
            "문항당 평균 시도": round(sum(sum(r["tries"]) for r in runs) / max(1, sum(len(r["tries"]) for r in runs)), 2),
            "호출(세트 평균)": round(sum(x.get("api_calls", 0) for x in sm) / len(sm), 1),
            "호출 캐시 포함(세트 평균)": round(sum(r["all_calls"] for r in runs) / len(runs), 1),
            "토큰(세트 평균)": round(sum(x.get("tokens", 0) for x in sm) / len(sm)),
            "시간(세트 평균, 초)": round(sum(x.get("sec", 0) for x in sm) / len(sm), 1),
        })
    cols = list(rows[0]) if rows else []
    table = "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
                      + ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows])
    note = f"\n\n채점 안 된 문항 {len(missing)}개: {missing}" if missing else ""
    return table + note, {"rows": rows, "missing": missing}
