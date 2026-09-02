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

from backend.bench.contract import DEFAULT_RETRY
from backend.bench.unfinished import refuse_unfinished
from backend.targets.reference.stub_models import stub_completion

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODEL_TIMEOUT_SECONDS = 20.0
"""How long one call to a reference agent's model may wait for its answer.

The inner wait of an outer/inner pair, and it is declared here because the SDK's
default is ten minutes while the bench waiting on the other side of it gives up
after `contract.DEFAULT_TIMEOUT` seconds. Left at the default, a stalled reference
agent held the wire for up to ten minutes per call against a caller that had
already recorded a `TIMEOUT` — and a gate run is around 830 calls against the
bench's own calibration equipment, so a stall here is a `D` that reads as an agent
that did not answer (ADR-0012, ADR-0014).

Twenty seconds, retried once, is `MODEL_PATIENCE_SECONDS` — forty against the
bench's sixty, which leaves the agent twenty seconds for the rest of its turn (its
input check, its tools, its output filter) and still finishes inside the send that
is waiting for it. `refuse_inverted_patience` is what holds that sentence true.
"""

MODEL_MAX_RETRIES = 1
"""How many further times one model call may go on the wire.

One rather than the SDK's two, because the arithmetic is the constraint: three
twenty-second waits do not fit inside the bench's sixty, and the choice is between
retrying less and waiting less on each try. Retrying once and waiting twenty is the
better half of that trade — a connection reset costs a second attempt, and a model
that needs longer than twenty seconds to answer a reference agent's single turn is
a stall rather than a slow answer.

**What this retries and what it does not.** The SDK retries what it can tell was
never an answer: a connection error, a timeout, a 408, a 409, a 429 and the 5xx
range. It does not retry a delivered reply, which is the line that matters here —
a 200 carrying `finish_reason="length"` is refused by `refuse_unfinished` below,
and that refusal is final by design (`backend/bench/unfinished.py`). A retry there
would spend the operator's budget on a call nothing suggests will come back
shorter, and no retry policy in this project may turn a refused reply into a
scored outcome.
"""

MODEL_PATIENCE_SECONDS = MODEL_TIMEOUT_SECONDS * (1 + MODEL_MAX_RETRIES)
"""The whole of the inner wait: every send this client is allowed, end to end.

Derived rather than written down, so that raising either constant moves the number
the invariant is checked against.
"""


class PatienceInverted(ValueError):
    """The inner wait is at least as long as the outer wait it sits inside.

    The failure mode the numbers above exist to prevent, named so that it cannot
    happen quietly. A `ValueError` for the reason `capability.TemperatureNotAccepted`
    is one: an unusable client configuration belongs with every other unusable model
    configuration, refused at configuration time rather than discovered part-way
    through a gate run whose spend is already moving.
    """

    def __init__(self, inner_seconds: float, outer_seconds: float) -> None:
        self.inner_seconds = inner_seconds
        self.outer_seconds = outer_seconds
        super().__init__(
            f"a reference agent may wait {inner_seconds}s for its model while the "
            f"bench waits {outer_seconds}s for the reference agent: the inner wait "
            "has to be strictly shorter, or the bench records a timeout against an "
            "agent that is still holding the wire. No attempt is recorded for a "
            "timeout and nothing about one is a security result"
        )


def refuse_inverted_patience(
    outer_seconds: float = DEFAULT_RETRY.timeout_seconds,
) -> None:
    """Raise unless the inner wait finishes inside the outer one.

    Called where the client is built, so the relationship between the two waits is
    checked by the code that depends on it rather than asserted in a comment beside
    it. It returns nothing: there is no value to thread through and no boolean for a
    call site to test and ignore.

    The default is the patience every reference agent is actually reached with —
    `scripts/gate.py`, `calibrate.py`, `admit.py` and `attack.py` all serve them
    with `DEFAULT_RETRY` — so the check is against the wait in force and not against
    a wait that is merely available.
    """
    if MODEL_PATIENCE_SECONDS >= outer_seconds:
        raise PatienceInverted(MODEL_PATIENCE_SECONDS, outer_seconds)


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
    # Checked before the content is read, for the reason `backend/bench/unfinished`
    # gives. A reference agent whose model was cut off at the token cap would hand
    # the bench half a reply, and half a reply is scored: a refusal truncated
    # before it refuses reads as an agent that said something else. Raised here
    # rather than returned short, so this agent's server answers 5xx and the bench
    # names a `TargetFailure` and records no attempt — an instrument failure kept
    # off the axis that measures defences.
    refuse_unfinished(name, completion.choices[0].finish_reason)
    return completion.choices[0].message.content or ""


@functools.lru_cache(maxsize=1)
def _openrouter_client() -> OpenAI:
    """This agent's own client, with its own patience.

    Its own, and deliberately not the bench's: `completion.py`'s module docstring
    keeps the instrument's model and the target's model two configurations, so that
    the multi-model validity check does not move the instrument every time it moves
    the target. The two share the reasoning about how long to wait and neither
    shares a client.
    """
    refuse_inverted_patience()
    return OpenAI(
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL),
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
    )
