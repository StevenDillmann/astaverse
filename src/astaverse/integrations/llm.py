"""Thin LiteLLM wrapper for structured calls.

OpenAI and Gemini only — this workspace has no Anthropic or OpenRouter key.

Every call is logged to the run directory when one is supplied, so a run's
LLM cost and the exact prompts are auditable after the fact.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "openai/gpt-5.6-luna"

# Plan generation and decision extraction can be pointed at different models
# (bias control 4: one model doing both misses forks it never entertains).
# They currently default to the same one — override either to re-separate them.
DEFAULT_PLAN_MODEL = os.environ.get("ASTAVERSE_PLAN_MODEL", DEFAULT_MODEL)
DEFAULT_DECISION_MODEL = os.environ.get("ASTAVERSE_DECISION_MODEL", DEFAULT_MODEL)
DEFAULT_BELIEF_MODEL = os.environ.get("ASTAVERSE_BELIEF_MODEL", DEFAULT_MODEL)
DEFAULT_CONCLUSION_MODEL = os.environ.get("ASTAVERSE_CONCLUSION_MODEL", DEFAULT_MODEL)


class LLMError(RuntimeError):
    pass


#: Sampling params safe to drop and retry without. Dropping one changes how
#: varied the samples are, never what was asked.
DROPPABLE = ("temperature", "top_p", "presence_penalty", "frequency_penalty")
MAX_CHOICES_PER_CALL = 8


def _unsupported_param(message: str) -> str | None:
    """Find which parameter a provider rejected, if that is what went wrong."""
    lowered = message.lower()
    if "unsupported" not in lowered and "does not support" not in lowered:
        return None
    for param in DROPPABLE:
        if param in lowered:
            return param
    return None


def _log(log_dir: Path | None, record: dict) -> None:
    if log_dir is None:
        return
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    with (Path(log_dir) / "llm_calls.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def structured_call(
    prompt: str,
    schema: type[T],
    model: str,
    *,
    system: str | None = None,
    temperature: float = 0.0,
    n: int = 1,
    log_dir: Path | None = None,
    tag: str = "",
) -> list[T]:
    """Call `model` and parse `n` responses into `schema`.

    Returns a list of length `n`. Requests them in one call where the provider
    supports it; falls back to sequential calls otherwise.
    """
    import litellm

    # Providers differ on which sampling params they accept — gpt-5 models pin
    # temperature to 1, for instance. Drop what a model rejects rather than
    # failing the stage; diversity across plans comes from drawing `n`
    # independent samples, not from the temperature value alone.
    litellm.drop_params = True

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "response_format": schema,
    }
    # Some reasoning models reject an explicit temperature; only send it when
    # it is doing work.
    if temperature:
        kwargs["temperature"] = temperature

    def _complete(**extra):
        return litellm.completion(**{**kwargs, **extra})

    def _request(batch_size: int):
        try:
            return _complete(n=batch_size) if batch_size > 1 else _complete()
        except Exception as exc:
            # `drop_params` only drops what LiteLLM *knows* a model rejects,
            # and a model newer than its map is passed through verbatim.
            offender = _unsupported_param(str(exc))
            if offender is None or offender not in kwargs:
                raise LLMError(f"{tag or 'llm'} call to {model} failed: {exc}") from exc
            kwargs.pop(offender)
            try:
                return _complete(n=batch_size) if batch_size > 1 else _complete()
            except Exception as retry_exc:
                raise LLMError(
                    f"{tag or 'llm'} call to {model} failed even without '{offender}': {retry_exc}"
                ) from retry_exc

    responses = []
    contents: list[str] = []
    while len(contents) < n:
        batch_size = min(MAX_CHOICES_PER_CALL, n - len(contents))
        response = _request(batch_size)
        responses.append(response)
        choices = [choice.message.content for choice in response.choices]
        if not choices:
            raise LLMError(f"{tag or 'llm'} call to {model} returned no choices")
        contents.extend(choices)

    usage_records = [
        response.usage.model_dump() if getattr(response, "usage", None) else None
        for response in responses
    ]

    _log(
        log_dir,
        {
            "tag": tag,
            "model": model,
            "temperature": temperature,
            "n": n,
            "prompt": prompt,
            "system": system,
            "responses": contents,
            "usage": usage_records[0] if len(usage_records) == 1 else usage_records,
        },
    )

    parsed: list[T] = []
    for content in contents[:n]:
        try:
            parsed.append(schema.model_validate_json(content))
        except Exception as exc:
            raise LLMError(
                f"{tag or 'llm'}: {model} returned unparseable output for "
                f"{schema.__name__}: {exc}\n---\n{content[:2000]}"
            ) from exc
    return parsed
