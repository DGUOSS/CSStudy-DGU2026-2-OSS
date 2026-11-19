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
    answer: str
    reasoning: str
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
