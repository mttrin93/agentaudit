"""The HTTP contract every target speaks, and the only path the bench takes to one.

A target is an HTTP endpoint. The bench sends::

    POST <endpoint>
    Authorization: Bearer <token>
    {"message": "<text>", "session_id": "<id>"}

and expects::

    {"reply": "<text>"}

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

import time
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
    """How many times one message may go on the wire. Not attempts — see the module docstring."""

    backoff_seconds: float = 0.5
    """The first wait, doubled on each further retry."""

    def __post_init__(self) -> None:
        if self.sends < 1:
            raise ValueError("a retry policy has to allow at least one send")

    def wait_before(self, send: int) -> float:
        return self.backoff_seconds * float(2 ** (send - 1))


DEFAULT_RETRY = RetryPolicy()


@dataclass(frozen=True)
class TargetConfig:
    """How a target is described to the bench, reference agent or user agent alike."""

    name: str
    url: str
    auth_token: str
    agent_type: str
    retry: RetryPolicy = field(default=DEFAULT_RETRY)
    """Patience is per endpoint: how flaky a target is, is a property of that target."""


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


def send_message(target: TargetConfig, message: str, session_id: str) -> Transcript:
    """Send one message to a target, retrying transient failures, and record the exchange.

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
