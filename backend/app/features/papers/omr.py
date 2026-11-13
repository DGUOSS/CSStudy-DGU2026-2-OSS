"""종이 답안지(OMR): 배치, 인쇄용 SVG, 사진 인식.

배치(layout)는 이 파일 한 곳에서만 정한다. 인쇄(SVG)와 인식(read_sheet)이 같은 좌표를 쓴다.
- 단위는 mm(A4 210×297). 쪽마다 네 귀퉁이에 ArUco 표시를 찍는다. p쪽(0부터)의 표시 번호는
  4p+0(왼쪽 위), 4p+1(오른쪽 위), 4p+2(오른쪽 아래), 4p+3(왼쪽 아래).
- 객관식은 번호별 동그라미 줄, 서술형은 번호별 답 칸(사각형).
- 인식: 표시 4개로 원근을 바로잡은 뒤 동그라미 안이 얼마나 칠해졌는지 본다. 서술형 칸은 잘라서 돌려준다.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from html import escape

import cv2
import numpy as np

# 숙련도 계산(pyBKT)이 fork를 쓰므로 OpenCV 작업 스레드를 띄우지 않는다(fork + 스레드는 멈출 수 있음)
cv2.setNumThreads(0)

PAGE_W, PAGE_H = 210.0, 297.0
MARK = 14.0  # 표시 한 변(mm)
MARK_CENTERS = [(17.0, 17.0), (193.0, 17.0), (193.0, 280.0), (17.0, 280.0)]
TOP, BOTTOM = 58.0, 268.0  # 문항이 들어가는 세로 범위
ROW_H = 7.5
COLS_X = [24.0, 80.0, 136.0]  # 객관식 세 줄의 왼쪽 끝
BUBBLE_R = 2.7
BUBBLE_GAP = 8.4
ESSAY_H = 52.0  # 서술형 칸 높이(번호 줄 포함)
PX = 8  # 인식할 때 1mm = 8px
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
MAX_PAGES = 12  # 표시 50개 / 4


@dataclass
class McqSlot:
    no: int
    problem_id: int
    page: int
    bubbles: list[tuple[float, float]]  # 동그라미 중심(mm)


@dataclass
class EssaySlot:
    no: int
    problem_id: int
    page: int
    box: tuple[float, float, float, float]  # x, y, w, h (mm)


@dataclass
class Layout:
    pages: int
    mcq: list[McqSlot] = field(default_factory=list)
    essay: list[EssaySlot] = field(default_factory=list)


def layout(items: list[tuple[int, str, int]]) -> Layout:
    """items: 시험지 순서대로 (문제 id, 유형 mcq|essay, 보기 수). 번호는 1부터."""
    lay = Layout(pages=1)
    numbered = [(i + 1, pid, qt, n) for i, (pid, qt, n) in enumerate(items)]
    mcq = [x for x in numbered if x[2] == "mcq"]
    essays = [x for x in numbered if x[2] != "mcq"]
    rows_per_page = int((BOTTOM - TOP) // ROW_H)
    per_page = rows_per_page * len(COLS_X)
    page, y_end = 0, TOP
    for start in range(0, len(mcq), per_page):
        chunk = mcq[start : start + per_page]
        page = start // per_page
        rows = math.ceil(len(chunk) / len(COLS_X))
        for k, (no, pid, _qt, n) in enumerate(chunk):
            col, row = divmod(k, rows)
            cy = TOP + row * ROW_H + ROW_H / 2
            x0 = COLS_X[col] + 12.0
            bubbles = [(x0 + j * BUBBLE_GAP, cy) for j in range(max(2, min(n, 5)))]
            lay.mcq.append(McqSlot(no=no, problem_id=pid, page=page, bubbles=bubbles))
        y_end = TOP + rows * ROW_H + 6.0
    for no, pid, _qt, _n in essays:
        if y_end + ESSAY_H > BOTTOM:
            page, y_end = page + 1, TOP
        lay.essay.append(
            EssaySlot(
                no=no, problem_id=pid, page=page, box=(22.0, y_end + 6.0, 166.0, ESSAY_H - 8.0)
            )
        )
        y_end += ESSAY_H
    lay.pages = page + 1
    if lay.pages > MAX_PAGES:
        raise ValueError("답안지가 너무 깁니다")
    return lay


# ---------- 인쇄용 SVG ----------


def _marker_bits(marker_id: int) -> np.ndarray:
    return cv2.aruco.generateImageMarker(DICT, marker_id, 6)  # 테두리 포함 6×6, 0=검정


def _marker_svg(marker_id: int, cx: float, cy: float) -> str:
    bits = _marker_bits(marker_id)
    cell = MARK / 6
    x0, y0 = cx - MARK / 2, cy - MARK / 2
    rects = [
        f'<rect x="{x0 + c * cell:.3f}" y="{y0 + r * cell:.3f}" width="{cell + 0.02:.3f}" height="{cell + 0.02:.3f}"/>'
        for r in range(6)
        for c in range(6)
        if bits[r, c] == 0
    ]
    return '<g fill="#000">' + "".join(rects) + "</g>"


def sheet_svgs(lay: Layout, title: str, paper_id: int, info: str) -> list[str]:
    """쪽별 답안지 SVG(A4)."""
    out = []
    for p in range(lay.pages):
        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297" '
            'font-family="sans-serif">',
            '<rect width="210" height="297" fill="#fff"/>',
        ]
        for k, (cx, cy) in enumerate(MARK_CENTERS):
            parts.append(_marker_svg(4 * p + k, cx, cy))
        parts.append(
            f'<text x="30" y="22" font-size="6" font-weight="bold">{escape(title)} — 답안지</text>'
        )
        parts.append(
            f'<text x="30" y="29" font-size="3.4" fill="#444">시험지 #{paper_id} · {escape(info)} · '
            f"{p + 1}/{lay.pages}쪽</text>"
        )
        parts.append('<text x="30" y="40" font-size="3.6">이름</text>')
        parts.append(
            '<rect x="40" y="35" width="60" height="8" fill="none" stroke="#000" stroke-width="0.3"/>'
        )
        parts.append(
            '<text x="30" y="49" font-size="3" fill="#444">검은 펜이나 사인펜으로 동그라미를 꽉 채워 칠하세요. '
            "고칠 때는 지우개로 깨끗이 지우세요.</text>"
            '<text x="30" y="53.5" font-size="3" fill="#444">사진은 네 귀퉁이 검은 네모가 모두 나오게 찍어 주세요.</text>'
        )
        for s in (m for m in lay.mcq if m.page == p):
            y = s.bubbles[0][1]
            parts.append(
                f'<text x="{s.bubbles[0][0] - 9:.2f}" y="{y + 1.3:.2f}" font-size="3.6" font-weight="bold">{s.no}</text>'
            )
            for j, (cx, cy) in enumerate(s.bubbles):
                parts.append(
                    f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{BUBBLE_R}" fill="none" stroke="#000" stroke-width="0.3"/>'
                    f'<text x="{cx:.2f}" y="{cy + 1:.2f}" font-size="2.6" fill="#999" text-anchor="middle">{j + 1}</text>'
                )
        for e in (x for x in lay.essay if x.page == p):
            x, y, w, h = e.box
            parts.append(
                f'<text x="{x:.2f}" y="{y - 1.5:.2f}" font-size="3.6" font-weight="bold">{e.no}. (서술형)</text>'
            )
            parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" stroke="#000" stroke-width="0.35"/>'
            )
        parts.append("</svg>")
        out.append("".join(parts))
    return out


# ---------- 사진 인식 ----------


class SheetError(ValueError):
    pass


def _decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise SheetError("사진을 읽을 수 없습니다")
    h, w = img.shape[:2]
    scale = 2400 / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def _find_page(img: np.ndarray) -> tuple[int, np.ndarray] | None:
    """표시 4개가 다 보이는 쪽 번호와, 그 쪽을 바로 편 이미지(1mm=PX px)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(DICT, cv2.aruco.DetectorParameters())
    for g in (gray, cv2.equalizeHist(gray)):
        corners, ids, _ = detector.detectMarkers(g)
        if ids is None:
            continue
        found = {
            int(i): c.reshape(4, 2).mean(axis=0)
            for i, c in zip(ids.flatten(), corners, strict=True)
        }
        for p in sorted({i // 4 for i in found}):
            if all(4 * p + k in found for k in range(4)):
                src = np.float32([found[4 * p + k] for k in range(4)])
                dst = np.float32([(x * PX, y * PX) for x, y in MARK_CENTERS])
                m = cv2.getPerspectiveTransform(src, dst)
                return p, cv2.warpPerspective(
                    img, m, (int(PAGE_W * PX), int(PAGE_H * PX)), borderValue=(255, 255, 255)
                )
    return None


def _fill_ratio(dark: np.ndarray, cx: float, cy: float) -> float:
    r = int(BUBBLE_R * PX * 0.72)
    x, y = int(cx * PX), int(cy * PX)
    patch = dark[y - r : y + r + 1, x - r : x + r + 1]
    mask = np.zeros_like(patch)
    cv2.circle(mask, (r, r), r, 255, -1)
    return float((patch[mask > 0] > 0).mean())


def read_sheet(images: list[bytes], lay: Layout) -> dict:
    """답안지 사진(쪽마다 한 장)을 읽는다. 저장은 하지 않는다."""
    pages: dict[int, np.ndarray] = {}
    for data in images:
        found = _find_page(_decode(data))
        if found:
            pages[found[0]] = found[1]
    if not pages:
        raise SheetError(
            "답안지의 네 귀퉁이 검은 네모를 찾지 못했습니다. 네모가 모두 나오게 밝은 곳에서 다시 찍어 주세요"
        )

    mcq_out = []
    for p, warped in pages.items():
        gray = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        # 조명이 고르지 않아도 되게 주변보다 어두운 곳을 칠한 곳으로 본다
        dark = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 61, 18
        )
        slots = [s for s in lay.mcq if s.page == p]
        ratios = {s.no: [_fill_ratio(dark, cx, cy) for cx, cy in s.bubbles] for s in slots}
        flat = sorted(r for rs in ratios.values() for r in rs)
        base = flat[len(flat) // 2] if flat else 0.0  # 대부분은 빈 동그라미
        cut = max(0.38, base + 0.25)
        for s in slots:
            rs = ratios[s.no]
            filled = [j for j, r in enumerate(rs) if r >= cut]
            order = sorted(range(len(rs)), key=lambda j: -rs[j])
            if len(filled) == 1:
                chosen, status = filled[0], "ok"
            elif not filled:
                chosen, status = None, "blank"
            else:
                chosen, status = order[0], "multiple"  # 가장 진한 것을 제안만 하고 확인받는다
            mcq_out.append(
                {"no": s.no, "problem_id": s.problem_id, "chosen": chosen, "status": status}
            )
    for s in lay.mcq:
        if s.page not in pages:
            mcq_out.append(
                {"no": s.no, "problem_id": s.problem_id, "chosen": None, "status": "missing"}
            )

    essays = []
    for e in lay.essay:
        if e.page not in pages:
            essays.append({"no": e.no, "problem_id": e.problem_id, "image": None})
            continue
        x, y, w, h = (int(v * PX) for v in e.box)
        crop = pages[e.page][y : y + h, x : x + w]
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 70])
        essays.append(
            {
                "no": e.no,
                "problem_id": e.problem_id,
                "image": base64.b64encode(buf.tobytes()).decode() if ok else None,
            }
        )
    mcq_out.sort(key=lambda m: m["no"])
    missing = sorted(set(range(lay.pages)) - set(pages))
    return {"mcq": mcq_out, "essays": essays, "missing_pages": [p + 1 for p in missing]}


# ---------- 시험·개발용: 칠한 답안지 이미지를 그린다 ----------


def render_page_image(
    lay: Layout, page: int, marks: dict[int, list[int]], scribble: bool = False
) -> np.ndarray:
    """marks: 번호 → 칠할 보기(0부터). 인쇄물을 흉내 낸 이미지(1mm=PX px)."""
    img = np.full((int(PAGE_H * PX), int(PAGE_W * PX), 3), 255, np.uint8)
    for k, (cx, cy) in enumerate(MARK_CENTERS):
        side = int(MARK * PX)
        m = cv2.resize(_marker_bits(4 * page + k), (side, side), interpolation=cv2.INTER_NEAREST)
        x0, y0 = int((cx - MARK / 2) * PX), int((cy - MARK / 2) * PX)
        img[y0 : y0 + side, x0 : x0 + side] = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
    for s in (m for m in lay.mcq if m.page == page):
        for j, (cx, cy) in enumerate(s.bubbles):
            c = (int(cx * PX), int(cy * PX))
            cv2.circle(img, c, int(BUBBLE_R * PX), (0, 0, 0), 2)
            cv2.putText(
                img,
                str(j + 1),
                (c[0] - 6, c[1] + 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (150, 150, 150),
                1,
            )
            if j in marks.get(s.no, []):
                cv2.circle(img, c, int(BUBBLE_R * PX) - 2, (30, 30, 30), -1)
    for e in (x for x in lay.essay if x.page == page):
        x, y, w, h = (int(v * PX) for v in e.box)
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), 2)
        if scribble:
            for i in range(4):
                yy = y + 40 + i * 60
                cv2.line(img, (x + 30, yy), (x + w - 60, yy + 10), (40, 40, 40), 3)
    return img
