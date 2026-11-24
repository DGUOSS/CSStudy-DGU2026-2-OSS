from qgen.ingest import BM25, EmbeddingIndex, Retriever, load_chunks
from qgen.ingest.chunker import chunk_pages
from qgen.ingest.pdf_parser import Page

TEXTS = [
    "HTTP 쿠키 cookie 세션 상태 유지 Set-Cookie 헤더",
    "TCP 연결 persistent connection keep alive 지속 연결",
    "캐시 cache ETag 조건부 요청 If-Modified-Since",
    "HTTP2 multiplexing stream frame 다중화",
]


def _chunks():
    pages = [Page(file="lec.pdf", page=i + 1, text=t) for i, t in enumerate(TEXTS)]
    return chunk_pages(pages, "c1")


def test_bm25_ranks_keyword_page_first():
    ch = _chunks()
    s = BM25(ch).scores("쿠키 세션")
    assert max(range(len(s)), key=lambda i: s[i]) == 0


def test_embedding_index_used_when_fresh(tmp_path, fake_encoder):
    ch = _chunks()
    EmbeddingIndex.build(ch, fake_encoder, "fake").save(tmp_path)
    r = Retriever(ch, index_dir=tmp_path, encoder=fake_encoder, verbose=False)
    assert r.mode == "embedding"
    assert r.search("ETag cache", k=1)[0].source.page == 3
    assert [c.source.page for c in r.search("multiplexing stream", k=2)][0] == 4


def test_falls_back_to_bm25_when_missing_or_stale(tmp_path, fake_encoder):
    ch = _chunks()
    assert Retriever(ch, index_dir=tmp_path / "none", encoder=fake_encoder, verbose=False).mode == "bm25"
    EmbeddingIndex.build(ch, fake_encoder, "fake").save(tmp_path)
    changed = chunk_pages([Page(file="lec.pdf", page=1, text=TEXTS[0] + " 내용 추가")]
                          + [Page(file="lec.pdf", page=i + 2, text=t) for i, t in enumerate(TEXTS[1:])], "c1")
    r = Retriever(changed, index_dir=tmp_path, encoder=fake_encoder, verbose=False)
    assert r.mode == "bm25"
    assert len(r.search("쿠키", k=2)) == 2


def test_index_roundtrip(tmp_path, fake_encoder):
    ch = _chunks()
    EmbeddingIndex.build(ch, fake_encoder, "fake").save(tmp_path)
    idx = EmbeddingIndex.load(tmp_path)
    assert idx is not None and idx.vectors.shape == (4, 64) and idx.meta["chunk_ids"] == [c.chunk_id for c in ch]


def _titled_chunks():
    titles = ["What is a Cookie?", "Session", "HTTP Methods", "Web Caching"]
    pages = [Page(file="lec.pdf", page=i + 1, text=f"{t}. Some explanation sentence about {t} here.", title=t)
             for i, t in enumerate(titles)]
    return chunk_pages(pages, "c1")


def test_search_queries_uses_titles_in_source_language():
    from qgen.ingest import search_queries

    ch = _titled_chunks()
    # 목록 한 줄을 괄호까지 통째로 복사해도 제목만 쓴다, 중복은 한 번만
    q, w = search_queries("쿠키와 세션", ["What is a Cookie? (lec.pdf p.1)", "Session", "Session"], ch)
    assert (q, w) == (["What is a Cookie?", "Session"], [])
    # 번역해 버린 제목은 빼고 경고, 남은 게 있으면 그것만 쓴다
    q, w = search_queries("쿠키와 세션", ["쿠키란?", "Session"], ch)
    assert q == ["Session"] and len(w) == 1
    # 하나도 안 남으면 topic으로
    q, w = search_queries("쿠키와 세션", ["쿠키란?"], ch)
    assert q == ["쿠키와 세션"] and len(w) == 2
    # 예전 plan.json (source_titles 없음)
    assert search_queries("쿠키와 세션", [], ch) == (["쿠키와 세션"], [])


def test_search_queries_max_titles():
    from qgen.ingest import search_queries

    q, w = search_queries("t", ["What is a Cookie?", "Session", "HTTP Methods", "Web Caching"], _titled_chunks(),
                          max_titles=3)
    assert q == ["What is a Cookie?", "Session", "HTTP Methods"] and "Web Caching" in w[0]


def test_search_many_interleaves(fake_encoder, tmp_path):
    ch = _titled_chunks()
    EmbeddingIndex.build(ch, fake_encoder, "fake").save(tmp_path)
    r = Retriever(ch, index_dir=tmp_path, encoder=fake_encoder, verbose=False)
    pages = lambda hits: [c.source.page for c in hits]  # noqa: E731
    # 제목 2개 → 각 제목의 1등이 1·2번째 자리
    two = pages(r.search_many(["What is a Cookie?", "Session"], k=4))
    assert two[:2] == [1, 2] and len(set(two)) == 4
    # 제목 3개 → 1·2·3번째 자리가 각 제목의 1등
    assert pages(r.search_many(["What is a Cookie?", "Session", "HTTP Methods"], k=4))[:3] == [1, 2, 3]
    # 제목 1개 → 기존 search와 같다
    assert pages(r.search_many(["Session"], k=4)) == pages(r.search("Session", k=4))


def test_load_chunks_demo_course():
    from qgen import llm

    ch = load_chunks(llm.ROOT / "data" / "demo", verbose=False)
    assert len(ch) == 7  # 예전 ingest.py와 같은 청크 수 (speed-1 실행 로그: 청크 7개)
    assert all(c.source.file == "os_ch5_scheduling.md" for c in ch)


def test_title_missing_from_text_is_searchable(fake_encoder):
    """제목이 도형인 쪽: 본문에 제목 글자가 없어도 (이미지로 읽은) 제목으로 찾아야 한다."""
    from qgen.ingest.index import fingerprint, search_text
    from qgen.schemas import Chunk, SourceRef

    def ch(n, title, text):
        return Chunk(chunk_id=f"p{n}", course_id="c", text=text, source=SourceRef(file="a.pdf", page=n), title=title)

    chunks = [ch(1, "Half Adder", "x y c s 0 0 0 0 truth table s = x'y + xy'"),
              ch(2, "Flip-Flops", "Flip-Flops store one bit of state"),
              ch(3, "Decoder", "n inputs to 2^n outputs truth table")]
    assert search_text(chunks[0]).startswith("Half Adder\n")
    assert search_text(chunks[1]) == chunks[1].text  # 본문에 이미 있으면 그대로
    assert BM25(chunks).scores("Half Adder")[0] == max(BM25(chunks).scores("Half Adder"))
    idx = EmbeddingIndex.build(chunks, fake_encoder, "fake")
    assert int(idx.scores("Half Adder", fake_encoder).argmax()) == 0
    # 제목이 바뀌면 지문도 바뀐다 → 예전 인덱스를 잘못 쓰지 않는다
    assert fingerprint(chunks) != fingerprint([chunks[0].model_copy(update={"title": "X"}), *chunks[1:]])


def test_search_many_exclude_skips_used_chunks():
    from qgen.schemas import Chunk, SourceRef

    chunks = [Chunk(chunk_id=f"p{n}", course_id="c", text=t, source=SourceRef(file="a.pdf", page=n))
              for n, t in enumerate(["cache basics cache", "cache details expiry", "cookie session", "cache headers"], 1)]
    from pathlib import Path

    r = Retriever(chunks, index_dir=Path("_no_index_"), verbose=False)  # BM25
    top = [c.chunk_id for c in r.search_many(["cache"], k=2)]
    rest = [c.chunk_id for c in r.search_many(["cache"], k=2, exclude=set(top))]
    assert len(top) == 2 and not set(top) & set(rest) and len(rest) == 2
    assert [c.chunk_id for c in r.search_many(["cache"], k=2, exclude=None)] == top  # 기존 동작 그대로
