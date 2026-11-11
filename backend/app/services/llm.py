"""LLM 호출은 전부 이 파일을 거친다. 어떤 API를 쓸지 정해지면 이 파일만 바꾼다.

지금은 연결된 LLM이 없다. 문제는 data/seed의 샘플 문제를 쓴다.
문제 생성 결과는 아래 GeneratedProblem 형식을 따른다(Problem 테이블과 같은 칸).
"""

from pydantic import BaseModel


class GeneratedProblem(BaseModel):
    question: str
    choices: list[str]  # 4개
    answer_index: int  # 0부터
    explanation: str
    evidence: str  # 정답 근거가 되는 교안 문장(원문 그대로)
    source_page: int | None = None
    concepts: list[str]  # 이 문제가 확인하는 개념 이름


class LLMNotConfigured(RuntimeError):
    pass


def generate_problems(
    chapter_text: str, concepts: list[str], style_examples: list[str], count: int = 5
) -> list[GeneratedProblem]:
    """교안 텍스트와 그 교수님 기출 예시(style_examples)로 문제를 만든다.

    style_examples: 사용자가 문제 풀이 전에 고른 족보 본문.
    app.features.exams.router.exam_style_examples(session, user_id, course_id)로 얻는다.
    """
    raise LLMNotConfigured("LLM API가 아직 정해지지 않았습니다")
