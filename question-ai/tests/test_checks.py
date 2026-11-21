from qgen import checks
from qgen.schemas import Chunk, PlannedItem, Question, SourceRef

SRC = SourceRef(file="a.pdf", page=1)
CTX = [Chunk(chunk_id="a-p1", course_id="c", text="t", source=SRC)]
ITEM = PlannedItem(item_id="q1", qtype="객관식", topic="t", bloom_level="이해", difficulty="보통", points=10, rationale="r")


def mc(stem: str, answer: str) -> list[str]:
    q = Question(item_id="q1", qtype="객관식", stem=stem, choices=[f"보기 {i}" for i in range(1, 6)],
                 answer=answer, sources=[SRC])
    return checks.run(q, ITEM, CTX)


def test_single_answer_ok():
    assert mc("다음 중 옳은 것은?", "3") == []


def test_multi_answer_needs_select_all_phrase():
    assert any("모두 고르시오" in i for i in mc("다음 중 옳은 것은?", "1, 3"))
    assert mc("다음 중 옳은 것을 모두 고르시오.", "1, 3") == []
    assert mc("옳은 것을 있는 대로 고르면?", "2,4") == []
    assert mc("Select all that apply.", "1,2") == []


def test_duplicate_and_out_of_range_answer():
    assert any("겹침" in i for i in mc("옳은 것을 모두 고르시오.", "2, 2"))
    assert any("범위" in i for i in mc("옳은 것은?", "6"))
