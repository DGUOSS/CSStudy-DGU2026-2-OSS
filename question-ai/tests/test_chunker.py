from qgen.ingest import topic_list
from qgen.ingest.chunker import chunk_pages, title_of
from qgen.ingest.pdf_parser import Page


def _page(n: int, text: str, **kw) -> Page:
    return Page(file="lec.pdf", page=n, text=text, low_text=len(text) < 20, **kw)


def test_short_page_is_one_chunk():
    chunks = chunk_pages([_page(1, "HTTP 개요\nHTTP는 요청-응답 프로토콜이다.", has_figure=True)], "c1")
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_id == "lec-p1" and c.source.page == 1 and c.has_figure and c.course_id == "c1"


def test_low_text_page_skipped():
    assert chunk_pages([_page(1, "그림"), _page(2, "")], "c1") == []


def test_long_page_split_with_title_and_limit():
    body = "\n\n".join(f"문단 {i}: " + "가" * 300 for i in range(10))
    chunks = chunk_pages([_page(3, "쿠키와 세션\n\n" + body)], "c1", max_chars=1000)
    assert len(chunks) > 1
    assert [c.chunk_id for c in chunks] == [f"lec-p3-{k}" for k in range(1, len(chunks) + 1)]
    assert all(len(c.text) <= 1000 for c in chunks)
    assert chunks[0].text.startswith("쿠키와 세션")
    assert all(c.text.startswith("[쿠키와 세션]") for c in chunks[1:])
    # 나뉘어도 내용은 빠지지 않는다
    joined = "".join(c.text for c in chunks)
    assert all(f"문단 {i}:" in joined for i in range(10))


def test_single_huge_line_is_cut():
    chunks = chunk_pages([_page(1, "제목\n" + "나" * 5000)], "c1", max_chars=1200)
    assert len(chunks) >= 5 and all(len(c.text) <= 1200 for c in chunks)


def test_title_skips_page_number_and_date():
    assert title_of("3\nHTTP/1.1 Pipelining\n본문") == "HTTP/1.1 Pipelining"
    assert title_of("2026-03-19\nYeonho Yoo") == "Yeonho Yoo"


def test_page_title_is_used_over_first_line():
    chunks = chunk_pages([_page(1, "12\n본문 첫 줄입니다. 충분히 깁니다.", title="Cookies")], "c1")
    assert chunks[0].title == "Cookies"
    assert topic_list(chunks) == ["Cookies (lec.pdf p.1)"]


def test_title_and_topic_list_dedup():
    assert title_of("\n\n## CPU 스케줄링 개요\n내용") == "CPU 스케줄링 개요"
    body = "\n\n".join("가" * 500 for _ in range(4))
    chunks = chunk_pages([_page(1, "제목A\n\n" + body), _page(2, "제목B\n이 쪽은 나뉘지 않는 짧은 쪽입니다.")], "c1", max_chars=800)
    assert len(chunks) > 2
    assert topic_list(chunks) == ["제목A (lec.pdf p.1)", "제목B (lec.pdf p.2)"]
