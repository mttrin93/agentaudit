"""The underlying model of a reference agent — configuration, never a constant.

Ticket #15 re-runs the whole library against the same three agents with this one
setting changed, to answer whether the bench reads the agent's defences or the
model's default refusals. That is a re-run only if the seam exists from the first
ticket, so it does.

A configuration string is ``<provider>:<model>``::

    openrouter:openai/gpt-4.1-nano
    stub:obedient

The ``stub`` provider resolves to the deterministic models in `stub_models`.
"""

import functools
import os
from dataclasses import dataclass
from enum import StrEnum

from openai import OpenAI

from backend.targets.reference.stub_models import stub_completion

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Provider(StrEnum):
    OPENROUTER = "openrouter"
    STUB = "stub"


@dataclass(frozen=True)
class ModelConfig:
    provider: Provider
    name: str

    @classmethod
    def parse(cls, spec: str) -> "ModelConfig":
        provider, _, name = spec.partition(":")
        if not provider or not name:
            raise ValueError(
                f"model configuration must read '<provider>:<model>', got {spec!r}"
            )
        return cls(provider=Provider(provider), name=name)

    def __str__(self) -> str:
        return f"{self.provider}:{self.name}"


def measures_the_field(config: ModelConfig) -> bool:
    """Whether a reading taken on this model is a measurement of the field at all.

    False for the stub, and the answer lives here because this is where `Provider` is
    declared. `backend/bench/` reads the retirement rule and must not import this
    package to ask the question — so the gate-run entry point, which already holds a
    `ModelConfig`, records the answer on every reading it stores (ADR-0022).

    The match has no fallback branch on purpose. `Provider` is a closed enum, and a
    third provider added without a line here fails the type check rather than
    defaulting onto the side that lets two free runs retire a working case.
    """
    match config.provider:
        case Provider.OPENROUTER:
            return True
        case Provider.STUB:
            return False


def complete(config: ModelConfig, system_prompt: str, message: str) -> str:
    """One turn from the configured model: a system prompt and a message in,
    text out."""
    match config.provider:
        case Provider.STUB:
            return stub_completion(config.name, system_prompt, message)
        case Provider.OPENROUTER:
            return _openrouter_completion(config.name, system_prompt, message)


def _openrouter_completion(name: str, system_prompt: str, message: str) -> str:
    completion = _openrouter_client().chat.completions.create(
        model=name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )
    return completion.choices[0].message.content or ""


@functools.lru_cache(maxsize=1)
def _openrouter_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL),
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
