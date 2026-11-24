"""답안지 인식: 휴대폰 사진처럼 기울이고 어둡게 하고 잡음을 넣어도 읽는지."""

import random

import cv2
import numpy as np
import pytest

from app.features.papers import omr


def _photo(img: np.ndarray, seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    big_h, big_w = int(h * 1.35), int(w * 1.35)
    ox, oy = (big_w - w) // 2, (big_h - h) // 2

    def jit():
        return rng.uniform(-0.06, 0.06) * w

    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32(
        [
            [ox + jit(), oy + jit()],
            [ox + w + jit(), oy + jit()],
            [ox + w + jit(), oy + h + jit()],
            [ox + jit(), oy + h + jit()],
        ]
    )
    out = cv2.warpPerspective(
        img, cv2.getPerspectiveTransform(src, dst), (big_w, big_h), borderValue=(90, 90, 90)
    )
    rot = cv2.getRotationMatrix2D((big_w / 2, big_h / 2), rng.uniform(-8, 8), 1.0)
    out = cv2.warpAffine(out, rot, (big_w, big_h), borderValue=(90, 90, 90))
    light = np.linspace(0.55, 1.0, big_w)[None, :, None]
    out = np.clip(out * light + rng.normal(0, 8, out.shape), 0, 255).astype(np.uint8)
    out = cv2.resize(cv2.GaussianBlur(out, (5, 5), 0), (big_w // 2, big_h // 2))
    return cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()


def test_read_sheet_from_photos():
    items = [(100 + i, "mcq", 4 if i % 7 == 0 else 5) for i in range(90)] + [
        (300 + k, "essay", 0) for k in range(4)
    ]
    lay = omr.layout(items)
    assert lay.pages == 3  # 객관식 84개/쪽, 서술형 칸은 남는 자리부터
    for seed in range(3):
        rng = random.Random(seed)
        truth, marks = {}, {}
        for s in lay.mcq:
            r, n = rng.random(), len(s.bubbles)
            if r < 0.1:
                truth[s.no] = ("blank", None)
            elif r < 0.15:
                marks[s.no] = rng.sample(range(n), 2)
                truth[s.no] = ("multiple", None)
            else:
                marks[s.no] = [rng.randrange(n)]
                truth[s.no] = ("ok", marks[s.no][0])
        photos = [
            _photo(omr.render_page_image(lay, p, marks, scribble=True), seed * 10 + p)
            for p in range(lay.pages)
        ]
        res = omr.read_sheet(photos[::-1], lay)  # 쪽 순서가 바뀌어도 표시로 구분
        for m in res["mcq"]:
            status, chosen = truth[m["no"]]
            assert m["status"] == status, (seed, m)
            if status == "ok":
                assert m["chosen"] == chosen, (seed, m)
        assert all(e["image"] for e in res["essays"]) and res["missing_pages"] == []


def test_missing_page_and_no_markers():
    lay = omr.layout([(i, "mcq", 5) for i in range(90)])
    only_first = cv2.imencode(".png", omr.render_page_image(lay, 0, {}))[1].tobytes()
    res = omr.read_sheet([only_first], lay)
    second = {s.no for s in lay.mcq if s.page == 1}
    assert res["missing_pages"] == [2]
    assert {m["status"] for m in res["mcq"] if m["no"] in second} == {"missing"}
    blank = cv2.imencode(".png", np.full((800, 600, 3), 255, np.uint8))[1].tobytes()
    with pytest.raises(omr.SheetError):
        omr.read_sheet([blank], lay)


def test_sheet_svg_escapes_title():
    lay = omr.layout([(1, "mcq", 5), (2, "essay", 0)])
    svg = omr.sheet_svgs(lay, "<script>", 7, "2문항")[0]
    assert "<script>" not in svg and "&lt;script&gt;" in svg


def test_paper_id_mark_rejects_other_paper():
    """답안지의 시험지 번호 표시로 다른 시험지의 답안지를 거른다. 예전 답안지(표시 없음)는 통과."""
    lay = omr.layout([(i, "mcq", 4) for i in range(10)])
    marks = {s.no: [1] for s in lay.mcq}
    for pid in (1, 7, 300, 4095):
        photo = _photo(omr.render_page_image(lay, 0, marks, paper_id=pid), pid)
        assert omr.read_sheet([photo], lay, pid)["mcq"][0]["chosen"] == 1
        with pytest.raises(omr.SheetError, match=f"#{pid}"):
            omr.read_sheet([photo], lay, pid + 1)
    old = _photo(omr.render_page_image(lay, 0, marks), 3)  # 번호 표시가 생기기 전 답안지
    assert omr.read_sheet([old], lay, 42)["mcq"][0]["status"] == "ok"


def test_id_bits_and_svg():
    bits = omr._id_bits(5)
    assert len(bits) == 16 and bits[:3] == [1, 0, 1]
    assert omr._id_bits(0) != [0] * 16  # 번호 0도 표시가 칠해진다
    svg = omr.sheet_svgs(omr.layout([(1, "mcq", 4)]), "t", 5, "1문항")[0]
    assert svg.count('fill="#000"/>') >= sum(bits)


def test_empty_file_is_a_clear_error():
    lay = omr.layout([(1, "mcq", 4)])
    with pytest.raises(omr.SheetError, match="비어"):
        omr.read_sheet([b""], lay)
