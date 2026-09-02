"""The nested waits between the bench and a model, and which way round they go.

Three waits exist in this project and two of them are nested: the bench waits on a
target endpoint, and a reference agent — the bench's own calibration equipment —
waits inside that on its own model. Left at the SDK's ten-minute default, the inner
one outlasted the outer: a stalled reference agent held the wire while the caller
had already recorded a `TIMEOUT` against it, and a gate run is around 830 calls.

What is asserted here cannot be seen from a reply. That the client was built with a
patience at all, that the inner budget is strictly shorter than the outer so the
relationship cannot silently invert, and that no retry in it turns a reply the bench
refused into an answer.

No model is reached and nothing sleeps. The provider's client is inspected as built,
or stood in for, because a test that needed a credential would pass on the machine
that has one and fail in CI — and a test that waited out a backoff would make the
suite the thing nobody runs.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from backend.bench.contract import DEFAULT_RETRY, DEFAULT_TIMEOUT
from backend.bench.unfinished import ReplyUnfinished, UnfinishedReply
from backend.targets.reference import model
from backend.targets.reference.model import (
    MODEL_MAX_RETRIES,
    MODEL_PATIENCE_SECONDS,
    MODEL_TIMEOUT_SECONDS,
    ModelConfig,
    PatienceInverted,
    refuse_inverted_patience,
)

A_REFERENCE_SPEC = "openrouter:openai/gpt-4.1-nano"


@pytest.fixture(autouse=True)
def _no_client_kept() -> Iterator[None]:
    """The reference client is cached for the process, so a test that builds one
    must not leave it behind for the next."""
    yield
    cached = getattr(model._openrouter_client, "cache_clear", None)
    if cached is not None:
        cached()


def test_a_reference_agents_model_call_waits_the_declared_time_and_no_longer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bug in one assertion: this client was built with neither setting.

    Read off the built client rather than off the constants, because the constants
    being right is not the thing that was wrong — the ten-minute default was in
    force because nothing passed anything.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")

    client = model._openrouter_client()

    assert client.timeout == MODEL_TIMEOUT_SECONDS
    assert client.max_retries == MODEL_MAX_RETRIES


def test_the_inner_wait_finishes_inside_the_outer_one() -> None:
    """The relationship, asserted so it cannot silently invert.

    Every send this client is allowed, end to end, against the wait the bench gives
    one send to a reference agent. Strictly shorter: equal is already wrong, because
    the outer send has to still be listening when the inner one gives up.
    """
    assert DEFAULT_RETRY.timeout_seconds == DEFAULT_TIMEOUT
    assert MODEL_PATIENCE_SECONDS < DEFAULT_RETRY.timeout_seconds

    refuse_inverted_patience()


def test_an_inner_wait_that_outlasts_the_outer_one_is_refused() -> None:
    """The check's own failure mode, driven from the outer side.

    An outer wait equal to the inner budget is refused rather than accepted, and the
    message carries both numbers — a reader of the failure should not have to look up
    which of the two moved.
    """
    with pytest.raises(PatienceInverted) as refused:
        refuse_inverted_patience(outer_seconds=MODEL_PATIENCE_SECONDS)

    assert refused.value.inner_seconds == MODEL_PATIENCE_SECONDS
    assert refused.value.outer_seconds == MODEL_PATIENCE_SECONDS
    assert str(MODEL_PATIENCE_SECONDS) in str(refused.value)
    assert "No attempt is recorded" in str(refused.value)


def test_building_the_reference_client_refuses_an_inverted_patience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refused at configuration time, not at the call that stalls.

    The precedent `capability` set for a parameter a model will not take: an unusable
    client configuration is refused where the client is built, rather than found out
    part-way through a gate run whose spend is already moving.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")
    monkeypatch.setattr(model, "MODEL_PATIENCE_SECONDS", DEFAULT_TIMEOUT * 10)

    with pytest.raises(PatienceInverted):
        model._openrouter_client()


class _Truncating:
    """A client whose every reply stopped at the token cap, counting its calls."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def chat(self) -> Any:
        return self

    @property
    def completions(self) -> Any:
        return self

    def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        return _Reply()


class _Reply:
    def __init__(self) -> None:
        self.choices = [_Choice()]


class _Choice:
    def __init__(self) -> None:
        self.finish_reason = "length"
        self.message = _Message()


class _Message:
    content = "I cannot share the"


def test_a_refused_reply_is_not_retried_into_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The line a retry policy may not cross.

    `max_retries` is the SDK's, and the SDK retries what it can tell was never an
    answer — a connection error, a timeout, a 429, a 5xx. A 200 carrying
    `finish_reason="length"` is a delivered reply, refused by `refuse_unfinished`,
    and it stays refused: a retry loop wrapped around this call would spend the
    operator's budget on a reply nothing suggests comes back shorter, and would put
    an instrument failure back on the axis that measures defences.

    Asserted over the count of calls, because that is the whole of the difference
    between a policy that retries a refusal and one that does not.
    """
    client = _Truncating()
    monkeypatch.setattr(model, "_openrouter_client", lambda: client)

    with pytest.raises(ReplyUnfinished) as refused:
        model.complete(ModelConfig.parse(A_REFERENCE_SPEC), "a prompt", "a message")

    assert refused.value.unfinished is UnfinishedReply.TRUNCATED
    assert client.calls == 1
