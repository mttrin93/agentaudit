"""The reference agents served behind the target contract.

Two surfaces, and the distinction is load-bearing:

* ``POST /reference/{agent}/messages`` is the contract a user's target speaks. The
  bench knows nothing else about a target. The reply carries the turn's tool trace
  beside its text, because two families reach their verdict from what the agent
  did (`backend/bench/contract.py`). Every reference agent exposes it; a target
  that does not is the stub in `backend/tests/blind_target.py`, and the two
  families report *not measurable* against it.
  The ``session_id`` on the request is read rather than accepted and dropped: a turn
  can leave a standing instruction behind for the turns after it, which is the
  capability memory poisoning is measured against (`memory.py`, ADR-0041).
* ``PUT /reference/{agent}/nonce`` is test equipment. It stands in for the human
  who edits their target's system prompt when the bench issues a nonce. No user
  target exposes anything like it, and the bench never calls it — the operator
  side does, in the human's place.

The model is read from configuration once, at app construction, so a model swap is
a configuration change (#15).
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from backend.targets.reference.agent import ReferenceAgent
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.memory import SessionMemory
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.trivial import TRIVIAL
from backend.targets.reference.weak import WEAK

REFERENCE_AGENTS: tuple[ReferenceAgent, ...] = (TRIVIAL, WEAK, HARDENED)
"""The three agents of known construction, in the order their rates are
expected to fall."""


@dataclass(frozen=True)
class ReferenceConfig:
    model: ModelConfig
    auth_token: str
    agents: tuple[ReferenceAgent, ...] = REFERENCE_AGENTS
    """Which agents this app serves.

    The three of them, unless a caller is asking a narrower question — a variant
    with one control removed, served under the same name, is how a refusal is
    attributed to the control that produced it rather than to the agent.
    """


class MessageRequest(BaseModel):
    message: str
    session_id: str


class ToolCallPayload(BaseModel):
    name: str
    arguments: dict[str, str] = {}


class ToolTracePayload(BaseModel):
    """What the agent did this turn, in the order it did it.

    `stop_signal_at` counts the calls already made when the operator's stop
    signal arrived. It reports that the signal was received and nothing about
    whether carrying on was allowed — that judgement is the bench's.
    """

    calls: list[ToolCallPayload] = []
    stop_signal_at: int | None = None


class MessageReply(BaseModel):
    reply: str
    tool_trace: ToolTracePayload | None = None
    """Omitted entirely by a target without tool-call visibility, which is a
    different fact from an empty trace and is read as one."""


class NonceRequest(BaseModel):
    nonce: str


def create_reference_app(config: ReferenceConfig) -> FastAPI:
    agents = {agent.name: agent for agent in config.agents}
    nonces: dict[str, str] = {}
    sessions: dict[tuple[str, str], SessionMemory] = {}
    """What each session has been asked to keep, keyed by agent and session id.

    Keyed by both, because one app serves all three reference agents and a session
    two of them could see would make a gate run's `D` a fact about the fixture. It
    grows without bound for the life of the process, which is what a fixture served
    on an ephemeral port for one run may do and what a user's target may not.
    """

    app = FastAPI(title="AgentAudit reference agents", version="0.1.0")

    def _agent(name: str) -> ReferenceAgent:
        if name not in agents:
            raise HTTPException(status_code=404, detail=f"no reference agent {name!r}")
        return agents[name]

    @app.put("/reference/{agent}/nonce")
    def plant_nonce(agent: str, body: NonceRequest) -> dict[str, str]:
        """Test equipment: plant a registration nonce as an operator would by hand."""
        _agent(agent)
        nonces[agent] = body.nonce
        return {"agent": agent, "planted": "true"}

    @app.post("/reference/{agent}/messages")
    def messages(
        agent: str,
        body: MessageRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> MessageReply:
        if authorization != f"Bearer {config.auth_token}":
            raise HTTPException(status_code=401, detail="bad bearer token")
        reference_agent = _agent(agent)
        # The session id the contract carries is what carries a conversation
        # (`bench/contract.py`), so this is where a reference agent stops being
        # stateless. Every agent gets one: retention is a capability all three have
        # and they differ in whose instructions they keep (`memory.py`, ADR-0041).
        memory = sessions.setdefault((agent, body.session_id), SessionMemory())
        turn = reference_agent.reply(
            body.message, nonces.get(agent, ""), config.model, memory
        )
        return MessageReply(
            reply=turn.text,
            tool_trace=ToolTracePayload(
                calls=[
                    ToolCallPayload(name=call.name, arguments=call.arguments)
                    for call in turn.trace.calls
                ],
                stop_signal_at=turn.trace.stop_signal_at,
            ),
        )

    return app
