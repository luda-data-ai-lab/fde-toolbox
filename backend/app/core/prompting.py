"""Prompt builder and result parser primitives shared by LLM calls and prompt-copy mode.

Nothing here talks to the network: copy mode shows the same prompt to the user and parses
the pasted answer with the same parser the LLM adapter uses.
"""

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class ResultParseError(ValueError):
    def __init__(self, reason: str, errors: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.errors = errors or []


def json_instruction(schema: type[BaseModel]) -> str:
    spec = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    return (
        "Respond with a single JSON object only, with no explanation and no Markdown, "
        f"that validates against this JSON Schema:\n{spec}"
    )


def build_json_prompt(prompt: str, schema: type[BaseModel]) -> str:
    return f"{prompt.rstrip()}\n\n{json_instruction(schema)}"


def build_retry_prompt(prompt: str, previous: str, error: ResultParseError) -> str:
    problems = "\n".join(f"- {e}" for e in error.errors[:20]) or f"- {error.reason}"
    return (
        f"{prompt}\n\nYour previous answer was rejected:\n{problems}\n\n"
        f"Previous answer:\n{previous[:4000]}\n\nAnswer again with corrected JSON only."
    )


def _extract_json(text: str) -> str:
    fenced = _FENCE.search(text)
    candidate = (fenced.group(1) if fenced else text).strip()
    if candidate.startswith(("{", "[")):
        return candidate
    start = min((i for i in (candidate.find("{"), candidate.find("[")) if i >= 0), default=-1)
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    if start < 0 or end < start:
        raise ResultParseError("no_json")
    return candidate[start : end + 1]


def parse_json_result(text: str, schema: type[T]) -> T:
    raw = _extract_json(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResultParseError("invalid_json", [str(exc)]) from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise ResultParseError("schema_mismatch", errors) from exc
