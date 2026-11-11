from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfError(ValueError):
    pass


# 슬라이드 머리글처럼 모든 쪽에 반복되는 줄은 문제 생성·근거 검색에 방해가 된다.
def _drop_repeated_lines(pages: list[str]) -> list[str]:
    if len(pages) < 4:
        return pages
    counts: dict[str, int] = {}
    for page in pages:
        for line in set(page.splitlines()):
            if line.strip():
                counts[line.strip()] = counts.get(line.strip(), 0) + 1
    repeated = {line for line, n in counts.items() if n >= len(pages) * 0.6}
    return [
        "\n".join(ln for ln in page.splitlines() if ln.strip() not in repeated) for page in pages
    ]


def extract_pages(data: bytes) -> list[str]:
    """PDF 바이트에서 쪽별 텍스트를 뽑는다."""
    try:
        reader = PdfReader(BytesIO(data))
        pages = [(p.extract_text() or "").strip() for p in reader.pages]
    except (PdfReadError, ValueError, KeyError) as e:
        raise PdfError("PDF를 읽을 수 없습니다") from e
    if not pages:
        raise PdfError("빈 PDF입니다")
    return _drop_repeated_lines(pages)
