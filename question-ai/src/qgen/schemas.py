from typing import Literal

from pydantic import BaseModel


class SourceRef(BaseModel):
    file: str
    page: int


class Chunk(BaseModel):
    chunk_id: str
    course_id: str
    text: str
    source: SourceRef
    has_figure: bool = False
    has_formula: bool = False
    image_path: str | None = None  # 그림 위주·글자 부족 쪽 PNG. 과목 폴더(data/<과목>/) 기준 상대 경로 (build_index 때 생성)
    title: str = ""  # 슬라이드 제목 (Planner 주제 목록에 씀)


class PastItem(BaseModel):
    """기출 한 문항. 원문은 refs가 가리키는 줄·이미지에서 코드가 잘라 온다 (모델이 옮겨 적지 않음)."""
    item_id: str                          # "P1", "P2", ... (planner가 past_refs로 가리킴)
    number: str                           # 시험지의 문항 번호 그대로 ("6", "2-(1)")
    qtype: Literal["객관식", "단답형", "서술형", "계산형"]
    topic: str                            # 다루는 개념 (짧게)
    points: str = ""                      # 시험지에 적힌 배점 그대로 ("6%", "10점"), 없으면 ""
    refs: list[str]                       # 원문 위치: 글자 줄은 첫 줄과 마지막 줄 번호(["E1.93", "E1.95"]), 그림 쪽은 ["E1.p3"]


class ExamProfile(BaseModel):
    course: str
    professor: str | None = None
    format_ratio: dict[str, float]
    num_questions: int
    detail_level: Literal["핵심 위주", "중간", "지엽적"]
    difficulty: Literal["쉬움", "보통", "어려움"]
    recurring_patterns: list[str]
    phrasing_examples: list[str]
    emphasized_topics: list[str]
    notes: str = ""
    evidence: list[str] = []
    past_items: list[PastItem] = []       # 기출 문항 목록 (예전 프로필에는 없음 → 빈 목록)


class PlannedItem(BaseModel):
    item_id: str
    qtype: Literal["객관식", "단답형", "서술형", "계산형"]
    topic: str
    # 강의자료 주제 목록의 제목(1~최대 3개)을 번역 없이 그대로 복사한 것. 제목마다 검색해 결과를 번갈아 합친다
    # (교안 언어와 검색어 언어를 맞추기 위해). 예전 plan.json에는 없으므로 기본값은 빈 목록 → 그때는 topic으로 검색
    source_titles: list[str] = []
    # 이 문항이 형식·난이도를 참고할 기출 문항(ExamProfile.past_items의 item_id, 0~2개). 원문을 generator에 준다
    past_refs: list[str] = []
    bloom_level: Literal["기억", "이해", "적용", "분석", "평가", "창안"]
    difficulty: Literal["쉬움", "보통", "어려움"]
    points: int
    rationale: str


class ExamPlan(BaseModel):
    items: list[PlannedItem]


class Verification(BaseModel):
    """코드로 검산할 정답 하나 (verify.py). 해당하는 칸만 채운다."""
    kind: Literal["bool_expr", "ieee754", "int_repr"]
    label: str = ""                       # 어느 소문항인지 ("(1)")
    expected: str                         # 검산할 출제 정답: 불 식, 또는 비트열(16진수는 0x로 시작)
    # bool_expr: 변수 순서 = 민텀 번호의 비트 순서(첫 변수가 최상위 비트)
    variables: list[str] = []
    minterms: list[int] | None = None     # 함수를 민텀으로 줄 때 (Σm)
    dont_cares: list[int] = []
    function: str | None = None           # 함수를 식으로 줄 때 (minterms 대신)
    form: Literal["SOP", "POS", "any"] = "any"
    minimal: bool = False                 # "최소" 조건이 있으면 true
    # ieee754 / int_repr
    value: str = ""                       # 10진수 값 ("-118.625", "-5")
    precision: Literal["single", "double"] = "single"
    repr: Literal["2s", "1s", "sm"] = "2s"  # 2의 보수 / 1의 보수 / 부호-크기
    bits: int | None = None


class Question(BaseModel):
    item_id: str
    qtype: str
    stem: str
    choices: list[str] | None = None
    answer: str
    model_answer: str | None = None
    rubric: list[str] | None = None
    sources: list[SourceRef]
    figure_ref: SourceRef | None = None
    # 불 대수 간소화·수 표현 변환처럼 코드로 확인할 수 있는 정답 (없으면 빈 목록)
    verifications: list[Verification] = []


class SolverOutput(BaseModel):
    item_id: str
    # reasoning을 answer보다 먼저 둔다: 모델이 JSON을 앞에서부터 쓰므로, 먼저 풀고 나서 답을 쓰게 하기 위함
    reasoning: str
    answer: str
    confidence: float
    is_ambiguous: bool


class Review(BaseModel):
    item_id: str
    verdict: Literal["pass", "revise", "reject"]
    answer_match: Literal["일치", "부분일치", "불일치"]
    grounded: bool
    profile_fit: bool
    issues: list[str]
    feedback: str
