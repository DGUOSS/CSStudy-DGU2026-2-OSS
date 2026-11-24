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
        essay = item.qtype != "객관식"
        return Question(item_id=item.item_id, qtype=item.qtype, stem=f"{item.topic} 문제", choices=choices,
                        answer="1", sources=[src_page], model_answer="m" if essay else None,
                        rubric=["핵심 — 10점"] if essay else None)

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


def test_generator_gets_matching_past_item_not_whole_exam(tmp_path, monkeypatch):
    from qgen.exam_profile import AnalystInput
    from qgen.ingest import load_chunks
    from qgen.schemas import PastItem

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    prof = PROFILE.model_copy(update={"past_items": [
        PastItem(item_id="P1", number="1", qtype="객관식", topic="스케줄링", refs=["E1.1"]),
        PastItem(item_id="P2", number="2", qtype="서술형", topic="호위 효과", refs=["E1.2"]),
    ]})
    monkeypatch.setattr(exam_profile, "load_or_make", lambda *a, **k: prof)
    monkeypatch.setattr(exam_profile, "build_input", lambda *a, **k: AnalystInput(
        lines={"E1.1": "1. 기출 객관식 원문", "E1.2": "2. 기출 서술형 원문"}))
    seen = {}

    def gen(item, ctx, profile, examples, **k):
        seen[item.item_id] = examples
        choices = [f"보기{i}" for i in range(1, 6)] if item.qtype == "객관식" else None
        return Question(item_id=item.item_id, qtype=item.qtype, stem="s", choices=choices, answer="1", sources=[first])

    monkeypatch.setattr(agents, "generator", gen)
    pipeline.run("demo", run_id="t", verify=False)
    # planner가 past_refs를 안 줬으므로 같은 유형 기출 원문만
    assert "기출 객관식 원문" in seen["q1"] and "서술형 원문" not in seen["q1"]
    assert "기출 서술형 원문" in seen["q2"] and "객관식 원문" not in seen["q2"]


def _run_with_detail(tmp_path, monkeypatch, detail_level: str):
    from qgen.ingest import Retriever, load_chunks

    chunks = load_chunks(llm.ROOT / "data" / "demo", verbose=False)
    first = chunks[0].source
    _setup(tmp_path, monkeypatch, first)  # 모든 문항이 첫 쪽을 근거로 씀
    monkeypatch.setattr(exam_profile, "load_or_make",
                        lambda *a, **k: PROFILE.model_copy(update={"detail_level": detail_level}))
    calls = []
    orig = Retriever.search_many

    def spy(self, queries, k=4, exclude=None):
        calls.append((k, set(exclude or ())))
        return orig(self, queries, k=k, exclude=exclude)

    monkeypatch.setattr(Retriever, "search_many", spy)
    pipeline.run("demo", run_id="t", verify=False)
    first_ids = {c.chunk_id for c in chunks if (c.source.file, c.source.page) == (first.file, first.page)}
    return calls, first_ids


def test_detail_level_jiyeopjeok_doubles_k_and_excludes_used_pages(tmp_path, monkeypatch):
    calls, first_ids = _run_with_detail(tmp_path, monkeypatch, "지엽적")
    k = llm.CFG["pipeline"]["retrieval_top_k"] * llm.CFG["pipeline"]["detail_top_k_factor"]
    assert calls[0] == (k, set())          # 첫 문항: 뺄 쪽 없음
    assert calls[1] == (k, first_ids)      # 둘째 문항: 첫 문항이 쓴 쪽 제외


def test_other_detail_levels_unchanged(tmp_path, monkeypatch):
    calls, _ = _run_with_detail(tmp_path, monkeypatch, "중간")
    assert calls == [(llm.CFG["pipeline"]["retrieval_top_k"], set())] * 2


def _verify_run(tmp_path, monkeypatch, verdict: str, bad_source: bool = False):
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    src = SourceRef(file="없는파일.pdf", page=1) if bad_source else first
    calls = _setup(tmp_path, monkeypatch, src)
    monkeypatch.setitem(llm.CFG["pipeline"], "max_replacements", 0)  # 호출 수만 세는 테스트: 보충은 끔
    monkeypatch.setattr(agents, "solver", lambda q, ctx: (calls.__setitem__("solver", calls["solver"] + 1),
                        SolverOutput(item_id=q.item_id, reasoning="r", answer="1", confidence=0.9, is_ambiguous=False))[1])
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: (calls.__setitem__("reviewer", calls["reviewer"] + 1),
                        Review(item_id="", verdict=verdict, answer_match="불일치", grounded=True, profile_fit=True,
                               issues=["x"], feedback="고쳐"))[1])
    out = pipeline.run("demo", run_id="t", verify=True)
    return calls, out


def test_no_wasted_generator_call_after_last_revise(tmp_path, monkeypatch):
    calls, out = _verify_run(tmp_path, monkeypatch, "revise")
    tries = llm.CFG["pipeline"]["max_revisions"] + 1
    # 문항당: 첫 생성 1 + 수정 (tries-1)번. 마지막 검토 뒤에는 부르지 않음
    assert calls == {"generator": 2 * tries, "solver": 2 * tries, "reviewer": 2 * tries}
    assert json.loads((out / "exam.json").read_text(encoding="utf-8")) == {}


def test_no_wasted_generator_call_after_last_rule_issue(tmp_path, monkeypatch):
    calls, _ = _verify_run(tmp_path, monkeypatch, "pass", bad_source=True)
    tries = llm.CFG["pipeline"]["max_revisions"] + 1
    assert calls == {"generator": 2 * tries, "solver": 0, "reviewer": 0}


def _with_verification(monkeypatch, first, expected):
    from qgen.schemas import Verification

    def gen(item, *a, **k):
        essay = item.qtype != "객관식"
        return Question(item_id=item.item_id, qtype=item.qtype, stem="F=Σm(1,3,6,7)을 간소화", answer="A'C+AB",
                        choices=None if essay else [f"보기{i}" for i in range(1, 6)], sources=[first],
                        model_answer="m" if essay else None, rubric=["핵심 — 10점"] if essay else None,
                        verifications=[Verification(kind="bool_expr", variables=["A", "B", "C"], minterms=[1, 3, 6, 7],
                                                    expected=expected, form="SOP", minimal=True)])

    monkeypatch.setattr(agents, "generator", gen)


def test_code_check_failure_becomes_rule_issue(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    _with_verification(monkeypatch, first, "A'C + B")  # 틀린 정답
    out = pipeline.run("demo", run_id="t", verify=False)
    trace = json.loads((out / "trace.json").read_text(encoding="utf-8"))
    assert all(any("코드 검산 실패" in i for i in t["rule_issues"]) for t in trace)
    assert "**코드 검산**: 틀림 1개" in (out / "answers.md").read_text(encoding="utf-8")


def test_reviewer_is_told_verified_answers(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    _with_verification(monkeypatch, first, "A'C + AB")  # 맞는 정답
    seen = []
    monkeypatch.setattr(agents, "solver", lambda q, ctx: SolverOutput(item_id=q.item_id, reasoning="r", answer="x",
                                                                     confidence=0.5, is_ambiguous=False))

    def rev(*a, verified=None, **k):
        seen.append(verified)
        return Review(item_id="", verdict="pass", answer_match="일치", grounded=True, profile_fit=True, issues=[], feedback="")

    monkeypatch.setattr(agents, "reviewer", rev)
    out = pipeline.run("demo", run_id="t", verify=True)
    assert seen and all(v and "Σm(1, 3, 6, 7)" in v[0] for v in seen)
    assert "**코드 검산**: 맞음 1개" in (out / "answers.md").read_text(encoding="utf-8")


def test_failed_item_is_replaced_once_with_same_type(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    calls = _setup(tmp_path, monkeypatch, first)
    monkeypatch.setitem(llm.CFG["pipeline"], "max_replacements", 1)
    monkeypatch.setattr(agents, "solver", lambda q, ctx: SolverOutput(item_id=q.item_id, reasoning="r", answer="1",
                                                                     confidence=0.9, is_ambiguous=False))
    # q2(서술형)는 원래 주제 t2면 계속 reject, 보충 문항은 pass
    def rev(q, s, item, *a, **k):
        bad = item.topic == "t2" or item.item_id == "q2-r1-r1"
        return Review(item_id="", verdict="reject" if bad else "pass", answer_match="일치", grounded=not bad,
                      profile_fit=True, issues=["교안에 없는 내용"] if bad else [], feedback="")
    monkeypatch.setattr(agents, "reviewer", rev)
    seen = []

    def replan(profile, topics, failed, reason, avoid, max_titles=3, used_titles=None):
        seen.append((failed.item_id, reason, avoid))
        return failed.model_copy(update={"item_id": f"{failed.item_id}-r1", "topic": "새 주제"})

    monkeypatch.setattr(agents, "replan_item", replan)
    out = pipeline.run("demo", run_id="t", verify=True)
    assert seen == [("q2", "교안에 없는 내용", ["t1", "t2"])]
    exam = json.loads((out / "exam.json").read_text(encoding="utf-8"))
    assert set(exam) == {"q1", "q2-r1"}
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["replacements"][0]["replacement"] == "q2-r1"
    assert summary["type_counts"]["accepted"] == {"객관식": 1, "서술형": 1}
    final = json.loads((out / "plan_final.json").read_text(encoding="utf-8"))
    assert [i["item_id"] for i in final["items"]] == ["q1", "q2", "q2-r1"]
    ans = (out / "answers.md").read_text(encoding="utf-8")
    assert "~~q2 (t2)~~" in ans and "새 주제" in ans


def test_replacement_that_fails_is_not_replaced_again(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    monkeypatch.setitem(llm.CFG["pipeline"], "max_replacements", 1)
    monkeypatch.setattr(agents, "solver", lambda q, ctx: SolverOutput(item_id=q.item_id, reasoning="r", answer="1",
                                                                     confidence=0.9, is_ambiguous=False))
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: Review(item_id="", verdict="reject", answer_match="불일치",
                        grounded=False, profile_fit=True, issues=["x"], feedback=""))
    n = []
    monkeypatch.setattr(agents, "replan_item", lambda profile, topics, failed, *a, **k: (
        n.append(failed.item_id), failed.model_copy(update={"item_id": f"{failed.item_id}-r1"}))[1])
    out = pipeline.run("demo", run_id="t", verify=True)
    assert n == ["q1", "q2"]  # 원래 문항마다 1번, 보충 문항(q1-r1, q2-r1)은 다시 보충 안 함
    assert json.loads((out / "exam.json").read_text(encoding="utf-8")) == {}


def test_reviewer_gets_previous_issues_on_revision_only(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    monkeypatch.setitem(llm.CFG["pipeline"], "max_replacements", 0)
    monkeypatch.setattr(agents, "solver", lambda q, ctx: SolverOutput(item_id=q.item_id, reasoning="r", answer="1",
                                                                     confidence=0.9, is_ambiguous=False))
    seen = []
    verdicts = iter(["revise", "reject", "pass", "pass"])  # q1: revise → reject(재생성) → pass / q2: pass

    def rev(q, s, item, *a, prev_issues=None, **k):
        seen.append((item.item_id, list(prev_issues or [])))
        v = next(verdicts)
        return Review(item_id="", issues=[f"지적-{len(seen)}"], answer_match="일치", grounded=True, profile_fit=True,
                      verdict=v, feedback="f")

    monkeypatch.setattr(agents, "reviewer", rev)
    pipeline.run("demo", run_id="t", verify=True)
    assert seen == [("q1", []), ("q1", ["지적-1"]), ("q1", []), ("q2", [])]


def test_report_md_shows_revision_history(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    monkeypatch.setattr(agents, "solver", lambda q, ctx: SolverOutput(item_id=q.item_id, reasoning="r", answer="1",
                                                                     confidence=0.7, is_ambiguous=False))
    verdicts = iter(["revise", "pass", "pass"])
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: Review(
        item_id="", past_comparison="", issues=["조건이 모호함"], answer_match="부분일치", grounded=True,
        profile_fit=True, verdict=next(verdicts), feedback="조건을 명확히"))
    out = pipeline.run("demo", run_id="t", verify=True)
    rep = (out / "report.md").read_text(encoding="utf-8")
    assert "## q1 [객관식] t1 — 통과 (시도 2번)" in rep
    assert "- **시도 0**: revise / 부분일치" in rep and "→ 수정 지시: 조건을 명확히" in rep
    assert "| 수정·재생성이 있었던 문항 | 1개 |" in rep


def test_rerun_same_run_id_keeps_previous_summary(tmp_path, monkeypatch):
    from qgen.ingest import load_chunks

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    out = pipeline.run("demo", run_id="same", verify=False)
    first_summary = (out / "summary.json").read_text(encoding="utf-8")
    pipeline.run("demo", run_id="same", verify=False)
    assert (out / "summary.prev.json").read_text(encoding="utf-8") == first_summary


def _variant_setup(tmp_path, monkeypatch, ratio):
    from qgen.ingest import load_chunks
    from qgen.schemas import SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    calls = _setup(tmp_path, monkeypatch, first)
    monkeypatch.setitem(llm.CFG["pipeline"], "past_variant_ratio", ratio)  # 2문항 × ratio
    monkeypatch.setitem(llm.CFG["pipeline"], "max_replacements", 0)
    monkeypatch.setattr(agents, "solver", lambda q, ctx: SolverOutput(item_id=q.item_id, reasoning="r", answer="1",
                                                                     confidence=0.9, is_ambiguous=False))
    feedbacks = []
    orig_gen = agents.generator

    def gen(item, ctx, profile, examples, **k):
        if k.get("feedback"):
            feedbacks.append((item.item_id, k["feedback"]))
        return orig_gen(item, ctx, profile, examples, **k)

    monkeypatch.setattr(agents, "generator", gen)
    return feedbacks


def _review(same, total):
    from qgen.schemas import Review
    return Review(item_id="", past_comparison="(1) 같음 (2) 같음 (3) 다름", past_same=same, past_total=total,
                  issues=["기출 2번과 같은 질문: (1),(2)"] if same else [], answer_match="일치", grounded=True,
                  profile_fit=True, verdict="pass", feedback="")


def test_past_variant_allowed_up_to_limit_then_revise(tmp_path, monkeypatch):
    feedbacks = _variant_setup(tmp_path, monkeypatch, 0.5)  # 2문항 → 1개 허용
    reviews = iter([_review(2, 3), _review(2, 3), _review(0, 3)])  # q1 같음 → 허용 / q2 같음 → 초과, 수정 → 다름 → 통과
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: next(reviews))
    out = pipeline.run("demo", run_id="t", verify=True)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["past_variant_limit"] == 1 and list(summary["past_variants"]) == ["q1"]
    assert "소문항 2/3 같음" in summary["past_variants"]["q1"]
    assert summary["accepted"] == 2
    assert len(feedbacks) == 1 and feedbacks[0][0] == "q2" and "허용 개수(1개)를 이미 썼으므로" in feedbacks[0][1]
    ans = (out / "answers.md").read_text(encoding="utf-8")
    assert "**기출 변형**" in ans and "기출 변형 허용 개수 초과" in ans
    assert "(기출 변형)" in (out / "report.md").read_text(encoding="utf-8")


def test_past_variant_zero_limit_keeps_old_behavior(tmp_path, monkeypatch):
    feedbacks = _variant_setup(tmp_path, monkeypatch, 0.25)  # 2문항 × 0.25 = 0개
    reviews = iter([_review(2, 3), _review(0, 3), _review(0, 3)])
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: next(reviews))
    out = pipeline.run("demo", run_id="t", verify=True)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["past_variant_limit"] == 0 and summary["past_variants"] == {}
    assert [f[0] for f in feedbacks] == ["q1"]  # q1은 같은 질문이라 수정 요청


def test_copied_sentences_count_as_variant_while_budget_left(tmp_path, monkeypatch):
    from qgen import checks

    feedbacks = _variant_setup(tmp_path, monkeypatch, 0.5)  # 1개 허용
    monkeypatch.setattr(checks, "copy_issues", lambda q, past, th=0.25: ["기출 6번 문장과 겹침 0.32 (기준 0.25) — 다시 쓸 것"])
    reviews = iter([_review(0, 1), _review(0, 1), _review(0, 1)])
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: next(reviews))
    out = pipeline.run("demo", run_id="t", verify=True)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert list(summary["past_variants"]) == ["q1"] and "문장 겹침" in summary["past_variants"]["q1"]
    # q2: 허용 개수를 다 써서 글자 겹침이 규칙 위반으로 막힘 → 계속 고치다 실패
    assert summary["accepted"] == 1 and all(f[0] == "q2" for f in feedbacks)


def test_solver_blocked_fails_only_that_item(tmp_path, monkeypatch):
    """검증 모델이 응답을 못 주면(예: 안전 필터 차단) 실행 전체가 멈추지 않고 그 문항만 실패."""
    from qgen.ingest import load_chunks
    from qgen.schemas import Review, SolverOutput

    first = load_chunks(llm.ROOT / "data" / "demo", verbose=False)[0].source
    _setup(tmp_path, monkeypatch, first)
    monkeypatch.setitem(llm.CFG["pipeline"], "max_replacements", 0)

    def solver(q, ctx):
        if q.item_id == "q1":
            raise llm.LLMError("solver: 응답 차단(finish_reason=content_filter)")
        return SolverOutput(item_id=q.item_id, reasoning="r", answer="1", confidence=0.9, is_ambiguous=False)

    monkeypatch.setattr(agents, "solver", solver)
    monkeypatch.setattr(agents, "reviewer", lambda *a, **k: Review(
        item_id="", verdict="pass", answer_match="일치", grounded=True, profile_fit=True, issues=[], feedback=""))
    out = pipeline.run("demo", run_id="t", verify=True)
    assert set(json.loads((out / "exam.json").read_text(encoding="utf-8"))) == {"q2"}
    trace = json.loads((out / "trace.json").read_text(encoding="utf-8"))
    assert any("응답 실패" in i for t in trace if t["item"] == "q1" for i in t.get("rule_issues") or [])
