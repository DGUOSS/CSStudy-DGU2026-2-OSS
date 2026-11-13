"""채점. 객관식은 바로, 서술형은 이미지 LLM이 정해지면 붙인다."""

from app.models import Problem


def grade_mcq(problem: Problem, chosen: int | None) -> bool:
    return chosen is not None and chosen == problem.answer_index


def grade_essay(image_jpeg: bytes, problem: Problem) -> int | None:
    """서술형 답 칸 이미지를 배점표(problem.rubric)로 채점해 점수를 돌려준다.

    손글씨 읽기 + 배점표 채점을 할 이미지 LLM을 아직 정하지 않아서 지금은 None(채점 대기)을 돌려준다.
    정하면 이 함수만 바꾼다(services/llm.py와 같은 방식). 점수는 0~problem.points.
    """
    return None
