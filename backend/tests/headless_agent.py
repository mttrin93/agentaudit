"""A user's agent as a callback, for the headless entrypoint's tests to point at.

Here rather than inside a test function because `scripts/bench.py --callback` takes
a dotted reference and imports it, which is the shape a user's own repository has:
the agent is a module somebody committed, and the workflow names it. A closure
defined inside a test cannot be imported by name and so cannot exercise that path.

It plants its own configuration canary, which is what makes a served target
registrable without a person pasting a nonce anywhere (ADR-0061, ADR-0064), and it
records every message it was sent so a test can assert that nothing was.
"""

from __future__ import annotations

from backend.bench.registration import ECHO_PROBE


class RecordingAgent:
    """A callback that answers, remembers what it was asked, and can be planted."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.canary: str | None = None
        self.namespace: str | None = None
        self.dropped: str | None = None

    def __call__(self, message: str, session_id: str) -> str:
        del session_id
        self.messages.append(message)
        if message == ECHO_PROBE and self.canary is not None:
            return f"AgentAudit registration nonce: {self.canary}"
        return "I can only help with documents in this workspace."

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        self.namespace = namespace
        self.canary = canary

    def teardown(self, namespace: str) -> None:
        self.dropped = namespace
        self.canary = None


AGENT = RecordingAgent()
"""The instance a workflow would name. Reset by the tests that use it."""


def PLAIN(message: str, session_id: str) -> str:
    """A user's agent as a plain function: no hooks, so nothing plants its canary.

    The other half of the shim's surface (ADR-0061): a function cannot carry a
    method, so it declares no plantings, and an unattended run against it waives the
    proof of control exactly as one against a URL does.
    """
    del message, session_id
    return "I only summarise documents in this workspace."
