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
    image_path: str | None = None  # 그림 위주·글자 부족 쪽을 PNG로 남긴 경우 (build_index 때 생성)
    title: str = ""  # 슬라이드 제목 (Planner 주제 목록에 씀)


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


class PlannedItem(BaseModel):
    item_id: str
    qtype: Literal["객관식", "단답형", "서술형", "계산형"]
    topic: str
    # 강의자료 주제 목록의 제목(1~최대 3개)을 번역 없이 그대로 복사한 것. 제목마다 검색해 결과를 번갈아 합친다
    # (교안 언어와 검색어 언어를 맞추기 위해). 예전 plan.json에는 없으므로 기본값은 빈 목록 → 그때는 topic으로 검색
    source_titles: list[str] = []
    bloom_level: Literal["기억", "이해", "적용", "분석", "평가", "창안"]
    difficulty: Literal["쉬움", "보통", "어려움"]
    points: int
    rationale: str


class ExamPlan(BaseModel):
    items: list[PlannedItem]


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
