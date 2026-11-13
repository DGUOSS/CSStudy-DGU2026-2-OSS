"""모든 LLM 호출의 단일 진입점: 캐시 → 호출(속도 제한·재시도) → JSON 파싱/검증 → 로그."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import TypeVar

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
CACHE_DIR = ROOT / "cache"
PROMPT_DIR = ROOT / "prompts"

T = TypeVar("T", bound=BaseModel)

_state = {"last_call": {},"log_path": None, "use_cache": True, "calls": 0, "tokens": 0}


def configure(log_path: Path | None = None, use_cache: bool = True) -> None:
    _state["log_path"] = log_path
    _state["use_cache"] = use_cache


def stats() -> dict:
    return {"api_calls": _state["calls"], "tokens": _state["tokens"]}


def render_prompt(name: str, **vars: object) -> str:
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for k, v in vars.items():
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False, indent=1)
        text = text.replace("{{" + k + "}}", v)
    return text


def _log(record: dict) -> None:
    if _state["log_path"]:
        with open(_state["log_path"], "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _provider(model: str) -> str:
    return model.split("/", 1)[0]


def _call_kwargs(model: str, temperature: float) -> dict:
    """회사별 파라미터 차이 처리.

    - anthropic: 최신 Claude는 temperature 지정 시 400 → 보내지 않음.
      response_format(json_object)은 LiteLLM이 강제 tool 호출로 바꾸는데 최신 Claude는 이것도 400 →
      보내지 않고 프롬프트 지시 + 파싱/재요청으로 JSON을 보장.
    - openai: 추론 모델(gpt-5 계열 등)은 temperature를 받지 않음 → drop_params로 LiteLLM이 제거.
    """
    p = _provider(model)
    if p == "anthropic":
        return {"max_tokens": 16000}
    kw: dict = {"temperature": temperature, "response_format": {"type": "json_object"}}
    if p == "openai":
        kw["drop_params"] = True
    return kw


def _raw_call(model: str, messages: list[dict], temperature: float) -> tuple[str, int]:
    import litellm

    p = _provider(model)
    interval = CFG["pipeline"].get("min_interval_sec", {})
    interval = interval.get(p, 0) if isinstance(interval, dict) else interval
    for attempt in range(6):
        wait = interval - (time.time() - _state["last_call"].get(p, 0.0))
        if wait > 0:
            time.sleep(wait)
        _state["last_call"][p] = time.time()
        try:
            r = litellm.completion(
                model=model,
                messages=messages,
                timeout=180,
                num_retries=0,
                **_call_kwargs(model, temperature),
            )
            _state["calls"] += 1
            usage = getattr(r, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) or 0
            _state["tokens"] += tokens
            return r.choices[0].message.content or "", tokens
        except Exception as e:  # rate limit / 일시 오류 → 지수 백오프
            name = type(e).__name__
            transient = any(s in name for s in ("RateLimit", "ServiceUnavailable", "InternalServer", "Timeout", "APIConnection"))
            if not transient or attempt == 5:
                raise
            backoff = 10 * 2**attempt
            print(f"    [llm] {name} → {backoff}s 대기 후 재시도")
            time.sleep(backoff)
    raise RuntimeError("unreachable")


def _parse_json(text: str) -> object:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    return json.loads(text)


def call(role: str, prompt: str, schema: type[T], seed: int = 0) -> T:
    model = CFG["models"][role]
    temps = CFG["pipeline"]["temperature"]
    temperature = temps.get(role, temps["others"])
    system = (
        "너는 대학 시험 출제 시스템의 한 에이전트다. 반드시 아래 JSON 스키마를 따르는 JSON 객체 하나만 출력한다. "
        "설명 문장이나 코드블록 없이 JSON만. 모든 텍스트는 한국어, 수식은 LaTeX($...$).\n"
        f"스키마({schema.__name__}):\n{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    key = hashlib.sha256(json.dumps([model, messages, temperature, schema.__name__, seed], ensure_ascii=False).encode()).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if _state["use_cache"] and cache_file.exists():
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        _log({"role": role, "model": model, "cached": True, "schema": schema.__name__})
        return schema.model_validate(data)

    last_err = ""
    for attempt in range(3):  # 최초 + 검증 실패 시 2회 재요청
        t0 = time.time()
        content, tokens = _raw_call(model, messages, temperature)
        try:
            data = _parse_json(content)
            obj = schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)[:1500]
            _log({"role": role, "model": model, "error": last_err, "attempt": attempt})
            messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"출력이 스키마 검증에 실패했다. 오류:\n{last_err}\n수정한 JSON만 다시 출력하라."},
            ]
            continue
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file.write_text(obj.model_dump_json(), encoding="utf-8")
        _log({"role": role, "model": model, "cached": False, "schema": schema.__name__,
              "tokens": tokens, "sec": round(time.time() - t0, 2)})
        return obj
    raise RuntimeError(f"{role}: JSON 검증 3회 실패: {last_err}")


if __name__ == "__main__":  # python -m qgen.llm --ping
    class Pong(BaseModel):
        reply: str

    for role, model in CFG["models"].items():
        try:
            r = call(role, '{"reply": "pong"} 형태로 pong이라고 답하라.', Pong)
            print(f"OK  {role:9s} {model}: {r.reply}")
        except Exception as e:
            print(f"ERR {role:9s} {model}: {type(e).__name__}: {str(e)[:200]}")
