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

DEFAULT_PLAN_MODEL = os.environ.get("ASTAVERSE_PLAN_MODEL", "openai/gpt-5-mini")
DEFAULT_DECISION_MODEL = os.environ.get("ASTAVERSE_DECISION_MODEL", "gemini/gemini-2.5-pro")
DEFAULT_BELIEF_MODEL = os.environ.get("ASTAVERSE_BELIEF_MODEL", "openai/gpt-5-mini")


class LLMError(RuntimeError):
    pass


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

    try:
        if n > 1:
            response = litellm.completion(n=n, **kwargs)
        else:
            response = litellm.completion(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface provider errors verbatim
        raise LLMError(f"{tag or 'llm'} call to {model} failed: {exc}") from exc

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
