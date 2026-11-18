import sys
from pathlib import Path

import numpy as np
import pytest

# 설치된 qgen이 다른 폴더를 가리켜도 이 저장소의 src를 테스트한다
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _fake_encode(texts: list[str]) -> np.ndarray:
    """실제 모델 대신 쓰는 결정적 인코더: 단어를 해시해 64차원 벡터로. 같은 단어가 많을수록 가깝다."""
    import re

    out = np.zeros((len(texts), 64), dtype=np.float32)
    for i, t in enumerate(texts):
        t = t.removeprefix("passage: ").removeprefix("query: ")
        for w in re.findall(r"[가-힣a-zA-Z]+", t.lower()):
            out[i, sum(map(ord, w)) % 64] += 1.0
        n = np.linalg.norm(out[i])
        if n:
            out[i] /= n
    return out


@pytest.fixture
def fake_encoder():
    return _fake_encode
