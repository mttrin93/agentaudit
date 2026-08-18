"""The HTTP contract every target speaks, and the only path the bench takes to one.

A target is an HTTP endpoint. The bench sends::

    POST <endpoint>
    Authorization: Bearer <token>
    {"message": "<text>", "session_id": "<id>"}

and expects::

    {"reply": "<text>"}

A target that can show what it *did* as well as what it said returns a tool trace
beside the reply::

    {"reply": "<text>",
     "tool_trace": {"calls": [{"name": "send_email", "arguments": {...}}],
                    "stop_signal_at": 0}}

Two families reach a verdict from that trace and from nothing else — scope creep
from a call outside the declared list, halt defeat from a call made after the
operator's stop signal — so a target that returns no trace makes them
unmeasurable rather than passed (ADR-0004, `measurability.py`).

There is deliberately no in-process branch for the reference agents: they are
reached over this same path, so the gate exercises the code a user's run
exercises (spec: "Reference agents are reached over real HTTP, and there is
only one code path").

A transient failure is retried here rather than upstream, so that no caller has to
decide whether a 503 was a verdict. An **attempt** is one execution of one case,
and the retries inside it are sends — the vocabulary keeps them apart because the
arithmetic does: an endpoint having a bad minute must not read as an agent that
defended itself.

Transport failures — timeout, 401, malformed body, 429 — become distinct named
outcomes in #13. Until then, a failure that outlives the retry policy surfaces as
an exception rather than as a quietly scored security result.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_TIMEOUT = 60.0

TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
"""Replies that say "not now" rather than "no".

Listed rather than derived from the 5xx range, so that adding one is a decision.
401 is deliberately absent: a rejected token is not a bad minute, and retrying it
three times is three more rejections. #13 gives each of these its own named
outcome; here they only decide whether to send again.
"""


@dataclass(frozen=True)
class RetryPolicy:
    """How patient the bench is with one endpoint before it gives up on a message."""

    sends: int = 3
    """How many times one message may go on the wire. Not attempts — see the
    module docstring."""

    backoff_seconds: float = 0.5
    """The first wait, doubled on each further retry."""

    def __post_init__(self) -> None:
        if self.sends < 1:
            raise ValueError("a retry policy has to allow at least one send")

    def wait_before(self, send: int) -> float:
        return self.backoff_seconds * float(2 ** (send - 1))


DEFAULT_RETRY = RetryPolicy()


@dataclass(frozen=True)
class ToolCall:
    """One action a target took, as the target reported it.

    A record of what happened, never of whether it was allowed: the declared list
    lives on the target's registration and the comparison is the evaluator's
    (ADR-0004). A target that decided for itself which of its calls were in scope
    would be grading its own paper.
    """

    name: str
    arguments: dict[str, str] = field(default_factory=dict)

    def rendered(self) -> str:
        """`send_email(to="ops@example.com")` — one call, on one line."""
        shown = ", ".join(f'{key}="{value}"' for key, value in self.arguments.items())
        return f"{self.name}({shown})"


@dataclass(frozen=True)
class ToolTrace:
    """What a target did in one turn, in the order it did it.

    The evidence behind two families, and the whole of it. Scope creep asks
    whether any call is outside the declared list; halt defeat asks whether any
    call came after the operator's stop signal, which is a question about
    *order* — so the trace is a sequence and the stop is a position in it, not a
    flag on the turn.

    `stop_signal_at` is the count of calls already made when the stop signal
    arrived, and it records only that the signal was received. Whether receiving
    it and carrying on constitutes halt defeat is the success condition's
    decision, not the target's.
    """

    calls: tuple[ToolCall, ...] = ()
    stop_signal_at: int | None = None
    """Where the operator's stop signal landed, or `None` if none arrived."""

    def __post_init__(self) -> None:
        at = self.stop_signal_at
        if at is not None and not 0 <= at <= len(self.calls):
            raise ValueError(
                f"a stop signal at call {at} does not sit anywhere in a trace of "
                f"{len(self.calls)} calls"
            )

    @property
    def calls_after_stop(self) -> tuple[ToolCall, ...]:
        """The actions taken after the operator said to stop. Empty when none did."""
        if self.stop_signal_at is None:
            return ()
        return self.calls[self.stop_signal_at :]

    def outside(self, declared: Sequence[str]) -> tuple[ToolCall, ...]:
        """The calls to tools the target never declared it had."""
        return tuple(call for call in self.calls if call.name not in declared)

    def rendered(self) -> str:
        """The trace as text a reader can follow, model or human.

        `read_tool_trace` (#16) is the second consumer of this trace, and it is a
        model-invoked tool whose result is read by a model. Numbering the lines
        and printing the stop signal in its own place is what makes the ordering
        legible to that reader rather than only to the evaluator.
        """
        if not self.calls and self.stop_signal_at is None:
            return "tool trace: no tool calls, no stop signal."

        lines = [f"tool trace, {len(self.calls)} in order:"]
        for position, call in enumerate(self.calls):
            if position == self.stop_signal_at:
                lines.append("  — operator stop signal received —")
            lines.append(f"  {position + 1}. {call.rendered()}")
        if self.stop_signal_at == len(self.calls):
            lines.append("  — operator stop signal received —")
        return "\n".join(lines)

    @classmethod
    def from_payload(cls, payload: Any) -> ToolTrace | None:
        """Read a trace out of what a target returned, or `None` if it returned none.

        Tolerant of a target that omits the field entirely and of one that sends
        it empty, because those are different facts: an endpoint with no
        tool-call visibility returns nothing here, while an endpoint that has it
        and did nothing this turn returns an empty trace. Only the first makes a
        family unmeasurable.
        """
        if not isinstance(payload, dict):
            return None
        calls = payload.get("calls", [])
        if not isinstance(calls, list):
            return None
        return cls(
            calls=tuple(
                ToolCall(
                    name=str(call.get("name", "")),
                    arguments={
                        str(key): str(value)
                        for key, value in (call.get("arguments") or {}).items()
                    },
                )
                for call in calls
                if isinstance(call, dict)
            ),
            stop_signal_at=_position(payload.get("stop_signal_at")),
        )


def _position(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


@dataclass(frozen=True)
class TargetConfig:
    """How a target is described to the bench, reference agent or user agent alike."""

    name: str
    url: str
    auth_token: str
    agent_type: str
    retry: RetryPolicy = field(default=DEFAULT_RETRY)
    """Patience is per endpoint: how flaky a target is, is a property of that target."""

    exposes_tool_calls: bool = False
    """Whether this endpoint returns its tool calls, or only final text.

    A **registered** property rather than one sniffed from a reply, because the
    two families that need it must be refused *before* any attempt is spent
    against a target that cannot answer them (PLAN §3, spec story 63). It
    defaults to false: an endpoint whose operator did not say it exposes tool
    calls is one the bench declines to measure on those families, which is the
    conservative direction.
    """

    declared_tools: tuple[str, ...] = ()
    """The tools the operator declared their target has.

    Scope creep is a call *outside* this list, so the list is the whole of the
    comparison. It is a declaration and not a measurement — the same status as a
    declared control — which is exactly why an attack that produces a call
    outside it is a finding.
    """


@dataclass(frozen=True)
class Transcript:
    """The full exchange, kept so a verdict can be re-derived from evidence."""

    url: str
    sent: dict[str, Any]
    status_code: int
    received: dict[str, Any]
    sends: int = 1
    """How many times this message went on the wire to obtain this reply.

    Recorded because a run that had to retry its way through is evidence about
    the endpoint, and because it is what tells calls spent from attempts made.
    """

    @property
    def reply_text(self) -> str:
        reply = self.received.get("reply")
        return reply if isinstance(reply, str) else ""

    @property
    def tool_trace(self) -> ToolTrace | None:
        """What the target did this turn, or `None` from a target that does not say.

        `None` and an empty trace are deliberately different answers. A target
        with no tool-call visibility returns the first and cannot be measured on
        scope creep or halt defeat; a target that has visibility and took no
        action returns the second, which is a measured result of *resisted*.
        """
        return ToolTrace.from_payload(self.received.get("tool_trace"))


def send_message(target: TargetConfig, message: str, session_id: str) -> Transcript:
    """Send one message to a target, retrying transient failures, and record
    the exchange.

    The retries are invisible to the verdict by design: whatever it took to get a
    reply, what comes back is one exchange and the caller scores it once.
    """
    sent = {"message": message, "session_id": session_id}
    for send in range(1, target.retry.sends + 1):
        last_send = send == target.retry.sends
        try:
            response = httpx.post(
                target.url,
                json=sent,
                headers={"Authorization": f"Bearer {target.auth_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
        except httpx.TransportError:
            # No reply at all — timeout, refused connection, dropped read.
            if last_send:
                raise
        else:
            if response.status_code not in TRANSIENT_STATUSES:
                return Transcript(
                    url=target.url,
                    sent=sent,
                    status_code=response.status_code,
                    received=response.json(),
                    sends=send,
                )
            if last_send:
                response.raise_for_status()
        time.sleep(target.retry.wait_before(send))

    raise AssertionError("a retry policy with no sends cannot deliver a message")
