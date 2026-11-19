"""Adapted prompt runner from feat/question-generator for the site's Claude client."""

import json
from pathlib import Path

from pydantic import BaseModel

from app.core.config import settings
from app.services.llm import LLMNotConfigured, _parse

PROMPT_DIR = Path(__file__).parent / "prompts"


def render_prompt(name: str, **values: object) -> str:
    prompt = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, indent=1)
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


def call[T: BaseModel](role: str, prompt: str, schema: type[T], seed: int = 0) -> T:
    del seed  # Claude structured output does not support a reproducible seed.
    result = _parse(
        "너는 대학 시험 문제 생성 시스템의 "
        f"{role} 에이전트다. 제공된 자료에만 근거해 한국어로 답한다.",
        prompt,
        schema,
        model=settings.qgen_model,
    )
    if result is None:
        raise LLMNotConfigured(f"{role} 에이전트가 유효한 응답을 반환하지 않았습니다")
    return result
