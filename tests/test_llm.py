"""LLM transport behavior that should not require a live provider."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from pydantic import BaseModel

from astaverse.integrations.llm import structured_call


class _Response(BaseModel):
    value: int


def test_large_sample_requests_are_batched_at_provider_limit(monkeypatch):
    batch_sizes: list[int] = []
    next_value = 0

    def completion(**kwargs):
        nonlocal next_value
        size = kwargs.get("n", 1)
        batch_sizes.append(size)
        choices = []
        for _ in range(size):
            choices.append(
                SimpleNamespace(message=SimpleNamespace(content=json.dumps({"value": next_value})))
            )
            next_value += 1
        return SimpleNamespace(choices=choices, usage=None)

    fake_litellm = SimpleNamespace(completion=completion, drop_params=False)
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    responses = structured_call("prompt", _Response, "test/model", n=12)

    assert batch_sizes == [8, 4]
    assert [response.value for response in responses] == list(range(12))
