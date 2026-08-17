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

Transport failures — timeout, 401, malformed body, 429 — become distinct named
outcomes in #13. Until then they surface as exceptions rather than as quietly
scored security results.
"""

from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class TargetConfig:
    """How a target is described to the bench, reference agent or user agent alike."""

    name: str
    url: str
    auth_token: str
    agent_type: str


@dataclass(frozen=True)
class Transcript:
    """The full exchange, kept so a verdict can be re-derived from evidence."""

    url: str
    sent: dict[str, Any]
    status_code: int
    received: dict[str, Any]

    @property
    def reply_text(self) -> str:
        reply = self.received.get("reply")
        return reply if isinstance(reply, str) else ""


def send_message(target: TargetConfig, message: str, session_id: str) -> Transcript:
    """Send one message to a target and record everything about the exchange."""
    sent = {"message": message, "session_id": session_id}
    response = httpx.post(
        target.url,
        json=sent,
        headers={"Authorization": f"Bearer {target.auth_token}"},
        timeout=DEFAULT_TIMEOUT,
    )
    return Transcript(
        url=target.url,
        sent=sent,
        status_code=response.status_code,
        received=response.json(),
    )
