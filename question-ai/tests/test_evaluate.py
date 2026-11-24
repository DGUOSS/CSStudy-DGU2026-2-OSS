import json

import pytest

from qgen import evaluate as ev
from qgen.schemas import Chunk, ExamPlan, ExamProfile, PlannedItem, Question, SourceRef

SRC = SourceRef(file="lec.pdf", page=3)
CHUNKS = [Chunk(chunk_id="lec-p3", course_id="c", text="IEEE 754 Single Precision: 부호 1, 지수 8, 가수 23", source=SRC)]


def _run(root, name, n_items, accepted, calls=10):
    d = root / name
    d.mkdir(parents=True)
    items = [PlannedItem(item_id=f"q{i}", qtype="계산형" if i % 2 else "서술형", topic=f"t{i}", bloom_level="적용",
                         difficulty="보통", points=25, rationale="r") for i in range(1, n_items + 1)]
    (d / "plan.json").write_text(ExamPlan(items=items).model_dump_json(), encoding="utf-8")
    exam = {i.item_id: Question(item_id=i.item_id, qtype=i.qtype, stem=f"{i.topic} 문제 (Single Precision)",
                                answer="a", model_answer="m", rubric=["핵심 — 5점"], sources=[SRC]).model_dump()
            for i in items[:accepted]}
    (d / "exam.json").write_text(json.dumps(exam, ensure_ascii=False), encoding="utf-8")
    (d / "summary.json").write_text(json.dumps({"accepted": accepted, "planned": n_items, "api_calls": calls,
                                                "tokens": 1000, "sec": 60.0}), encoding="utf-8")
    return d


def _export(tmp_path, per_part=3):
    runs = [ev.RunRef("검증없음", 1, _run(tmp_path / "out", "run-20991231-aaa", 4, 4, calls=4)),
            ev.RunRef("검증있음", 1, _run(tmp_path / "out", "run-20991231-bbb", 4, 3, calls=30))]
    out = ev.export("t", runs, CHUNKS, tmp_path / "for judge", tmp_path / "keys", seed=1, per_part=per_part)
    return out, json.loads((tmp_path / "keys" / "judge_key.json").read_text(encoding="utf-8"))


def test_export_blind_files_and_key_outside(tmp_path):
    out, key = _export(tmp_path)
    assert out == tmp_path / "for judge" / "t"
    assert sorted(p.name for p in out.iterdir()) == ["README.md", "items_part01.md", "items_part02.md",
                                                       "items_part03.md", "judge_prompt.md"]
    assert len(key["items"]) == 7 and not (out / "judge_key.json").exists()
    text = "".join(p.read_text(encoding="utf-8") for p in out.iterdir())
    # 조건·실행 이름이 채점 자료에 없음, 교안 글과 출제 정답은 있음
    for leak in ["검증없음", "검증있음", "run-20991231", "summary", "검증 이력"]:
        assert leak not in text
    assert "IEEE 754 Single Precision" in text and "### 출제 정답" in text
    # 섞였는지: 대응표 순서가 실행 순서 그대로가 아님
    order = [(k["run"], k["item"]) for k in key["items"].values()]
    assert order != sorted(order)


def test_check_blind_blocks_model_names():
    with pytest.raises(ValueError):
        ev.check_blind("이 문항은 Gemini가 만들었다")
    with pytest.raises(ValueError):
        ev.check_blind("solver: gpt-5.4-mini")
    ev.check_blind("IEEE 754 Single Precision, clock generator, 부호 1비트")  # 교안에 나오는 말은 통과


def test_export_refuses_when_question_mentions_model(tmp_path):
    d = _run(tmp_path / "out", "r1", 1, 1)
    exam = json.loads((d / "exam.json").read_text(encoding="utf-8"))
    exam["q1"]["stem"] = "Claude가 낸 문제"
    (d / "exam.json").write_text(json.dumps(exam, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        ev.export("t", [ev.RunRef("a", 1, d)], CHUNKS, tmp_path / "for judge", tmp_path / "keys")


def test_score_by_condition(tmp_path):
    out, key = _export(tmp_path, per_part=10)
    scores = []
    for jid, k in key["items"].items():
        bad = k["condition"] == "검증없음" and k["item"] == "q1"
        scores.append({"id": jid, "judge_answer": "x", "answer_correct": "틀림" if bad else "맞음",
                       "ambiguous": bad, "grounded": not bad,
                       "qgeval": {d: (1 if bad else 3) for d in ev.QGEVAL}, "comment": ""})
    (out / "scores_part01.json").write_text("```json\n" + json.dumps({"scores": scores}, ensure_ascii=False) + "\n```",
                                            encoding="utf-8")
    prof = ExamProfile(course="c", format_ratio={"계산형": 0.5, "서술형": 0.5}, num_questions=4, detail_level="중간",
                       difficulty="보통", recurring_patterns=[], phrasing_examples=[], emphasized_topics=[])
    table, raw = ev.score(tmp_path / "keys" / "judge_key.json", out, prof)
    rows = {r["조건"]: r for r in raw["rows"]}
    assert rows["검증없음"]["정답 오류율"] == 0.25 and rows["검증없음"]["근거율"] == 0.75
    assert rows["검증있음"]["정답 오류율"] == 0.0 and rows["검증있음"]["품질 평균(1~3)"] == 3.0
    assert rows["검증없음"]["유형 분포 거리"] == 0.0 and rows["검증있음"]["통과/계획"] == "3/4"
    assert rows["검증있음"]["호출(세트 평균)"] == 30.0 and raw["missing"] == []
    assert "| 조건 |" in table


def test_tvd():
    assert ev.tvd({"계산형": 3, "서술형": 1}, {"계산형": 0.75, "서술형": 0.25}) == 0.0
    assert ev.tvd({"계산형": 4}, {"계산형": 0.5, "서술형": 0.5}) == 0.5
