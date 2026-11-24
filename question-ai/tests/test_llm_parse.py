import pytest

from qgen import llm
from qgen.llm import _parse_json
from qgen.schemas import Review


def test_parse_json_plain_fenced_and_with_prose():
    assert _parse_json('{"a": 1}') == {"a": 1}
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('풀이를 정리하면 다음과 같다.\n{"a": {"b": "}"}}\n이상.') == {"a": {"b": "}"}}


def test_parse_json_no_object_raises():
    with pytest.raises(ValueError):
        _parse_json("답: 3")


def test_content_filter_fails_at_once_without_retry(tmp_path, monkeypatch):
    """안전 검사가 끊은 응답은 다시 보내도 끊기므로 재요청하지 않는다 (문제사항 V-13)."""
    seen = []

    def blocked(model, messages, t):
        seen.append(1)
        llm._state["finish_reason"] = "content_filter"
        return '{"item_id": "x", "reasoning": "1단계', 2000, 0.0  # 쓰다가 끊긴 글

    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(llm, "_raw_call", blocked)
    llm.configure(log_path=tmp_path / "logs.jsonl")
    with pytest.raises(llm.LLMError, match="content_filter"):
        llm.call("solver", "문제", Review)
    assert len(seen) == 1
    assert "content_filter" in (tmp_path / "logs.jsonl").read_text(encoding="utf-8")
    llm._state["finish_reason"] = None
    llm.configure()
