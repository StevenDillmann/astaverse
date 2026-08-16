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


class LLMError(RuntimeError):
    pass


#: Sampling params safe to drop and retry without. Dropping one changes how
#: varied the samples are, never what was asked.
DROPPABLE = ("temperature", "top_p", "presence_penalty", "frequency_penalty")


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

    try:
        response = _complete(n=n) if n > 1 else _complete()
    except Exception as exc:  # noqa: BLE001
        # `drop_params` only drops what LiteLLM *knows* a model rejects, and a
        # model newer than its map is passed through verbatim — the provider
        # then rejects it. Sampling params are advisory here (diversity comes
        # from drawing n samples), so drop the offender and retry rather than
        # failing a stage over it.
        offender = _unsupported_param(str(exc))
        if offender is None or offender not in kwargs:
            raise LLMError(f"{tag or 'llm'} call to {model} failed: {exc}") from exc
        kwargs.pop(offender)
        try:
            response = _complete(n=n) if n > 1 else _complete()
        except Exception as retry_exc:  # noqa: BLE001
            raise LLMError(
                f"{tag or 'llm'} call to {model} failed even without "
                f"'{offender}': {retry_exc}"
            ) from retry_exc

    contents = [choice.message.content for choice in response.choices]
    # Providers that ignore `n` give back one choice; top up sequentially.
    while len(contents) < n:
        extra = litellm.completion(**kwargs)
        contents.append(extra.choices[0].message.content)

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
            "usage": getattr(response, "usage", None).model_dump()
            if getattr(response, "usage", None)
            else None,
        },
    )

    parsed: list[T] = []
    for content in contents[:n]:
        try:
            parsed.append(schema.model_validate_json(content))
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"{tag or 'llm'}: {model} returned unparseable output for "
                f"{schema.__name__}: {exc}\n---\n{content[:2000]}"
            ) from exc
    return parsed
