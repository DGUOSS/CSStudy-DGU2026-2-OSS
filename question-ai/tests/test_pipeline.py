import json
import shutil

from qgen import agents, exam_profile, llm, pipeline
from qgen.schemas import ExamPlan, ExamProfile, PlannedItem, Question, SourceRef

PROFILE = ExamProfile(course="demo", format_ratio={"객관식": 0.5, "서술형": 0.5}, num_questions=2,
                      detail_level="중간", difficulty="보통", recurring_patterns=[], phrasing_examples=[],
                      emphasized_topics=[])


def _setup(tmp_path, monkeypatch, src_page: SourceRef):
    shutil.copytree(llm.ROOT / "data" / "demo", tmp_path / "data" / "demo")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(exam_profile, "load_or_make", lambda *a, **k: PROFILE)
    monkeypatch.setitem(llm.CFG["pipeline"], "num_questions_override", 2)
    plan = ExamPlan(items=[
        PlannedItem(item_id="q1", qtype="객관식", topic="t1", bloom_level="이해", difficulty="보통", points=50, rationale="r"),
        PlannedItem(item_id="q2", qtype="서술형", topic="t2", bloom_level="이해", difficulty="보통", points=50, rationale="r"),
    ])
    monkeypatch.setattr(agents, "planner", lambda *a, **k: plan)
    calls = {"generator": 0, "solver": 0, "reviewer": 0}

    def gen(item, *a, **k):
        calls["generator"] += 1
        choices = [f"보기{i}" for i in range(1, 6)] if item.qtype == "객관식" else None
        return Question(item_id=item.item_id, qtype=item.qtype, stem=f"{item.topic} 문제", choices=choices,
                        answer="1", sources=[src_page])

    def never(name):
        def f(*a, **k):
            calls[name] += 1
            raise AssertionError(f"{name}를 부르면 안 됨")
        return f

    monkeypatch.setattr(agents, "generator", gen)
    monkeypatch.setattr(agents, "solver", never("solver"))
    monkeypatch.setattr(agents, "reviewer", never("reviewer"))
    return calls


def test_no_verify_generates_once_per_item_without_solver_reviewer(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    calls = _setup(tmp_path, monkeypatch, first)
    out = pipeline.run("demo", run_id="t", verify=False)

    assert calls == {"generator": 2, "solver": 0, "reviewer": 0}
    exam = json.loads((out / "exam.json").read_text(encoding="utf-8"))
    assert set(exam) == {"q1", "q2"}
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["verify"] is False
    assert summary["type_counts"] == {"target": {"객관식": 1, "서술형": 1}, "planned": {"객관식": 1, "서술형": 1},
                                      "accepted": {"객관식": 1, "서술형": 1}}
    assert "**1.**" in (out / "exam.md").read_text(encoding="utf-8")
    assert "검증 안 함" in (out / "answers.md").read_text(encoding="utf-8")


def test_no_verify_records_rule_issues_but_keeps_item(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, SourceRef(file="없는파일.pdf", page=99))  # 근거 검사에 걸리게
    out = pipeline.run("demo", run_id="t", verify=False)
    assert calls["generator"] == 2
    trace = json.loads((out / "trace.json").read_text(encoding="utf-8"))
    assert all(t["rule_issues"] for t in trace)
    assert len(json.loads((out / "exam.json").read_text(encoding="utf-8"))) == 2
    assert "규칙위반" in (out / "answers.md").read_text(encoding="utf-8")
