import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import seed  # noqa: E402


def test_seed_files_are_valid():
    """보기·정답·개념 연결이 맞는지 검사한다 (교안 PDF가 없는 CI에서는 근거 쪽수 검사는 건너뜀)."""
    files = list(seed.SEED_DIR.glob("*.json"))
    assert files
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert seed.check(data, seed.load_pdfs(f.stem, data)) == []


def test_find_page_ignores_whitespace():
    pages = ["첫 쪽", "배열 이름은\n배열의  시작 주소이다."]
    assert seed.find_page(pages, "배열 이름은 배열의 시작 주소이다.") == 2
    assert seed.find_page(pages, "없는 문장") is None


def test_seed_into_db(session):
    data = json.loads((seed.SEED_DIR / "basic-programming-kang.json").read_text(encoding="utf-8"))
    first = seed.seed_one(session, data, {})
    again = seed.seed_one(session, data, {})
    assert first["problems_added"] == sum(len(c["problems"]) for c in data["chapters"])
    assert again["problems_added"] == 0
