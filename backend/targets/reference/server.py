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
  side does, in the human's place. What it plants is scoped to the run that planted
  it, and ``DELETE /reference/namespaces/{namespace}`` drops that run's plants
  wholesale — the same contract a user's shim implements as ``teardown(namespace)``
  ([ADR-0063](../../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)).

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
    namespace: str
    """Which run planted this, so that dropping that run takes it with it.

    Required and never defaulted: a default would be a namespace nothing drops, which
    is the process-lifetime store this field exists to replace
    ([ADR-0063](../../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)
    §5).
    """


NAMESPACES_PATH = "/reference/namespaces/{namespace}"
"""Where a run drops everything it planted, in one call.

Test equipment like the nonce route beside it, and the same shape a user's shim
implements as `teardown(namespace)`: the drop is of the **namespace** and not of the
records inside it, so its failure is total and visible rather than partial and silent
(ADR-0063).
"""


def create_reference_app(config: ReferenceConfig) -> FastAPI:
    agents = {agent.name: agent for agent in config.agents}
    namespaces: dict[str, dict[str, str]] = {}
    """What each run planted, keyed by that run's namespace and then by agent.

    **Run-scoped rather than process-lifetime**, which is the shape the user-facing
    hooks are held to and so the shape the test equipment demonstrates
    ([ADR-0063](../../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)
    §5). A flat `dict[str, str]` keyed by agent was one where a second run's
    registration silently overwrote a first run's planted value and nothing ever
    removed either; here a run's plants leave together, in one call, when its
    namespace is dropped.

    Insertion-ordered, and `_planted` below reads the most recent namespace that still
    holds a value for the agent — so a namespace that was dropped can never answer for
    one that was not, which is the property the drop exists to have.
    """
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

    def _planted(agent: str) -> str:
        """The nonce this agent currently carries, from the last run still holding one.

        **The store is run-scoped; the read deliberately is not, and cannot be.** A
        `POST /messages` body is `{message, session_id}` and nothing else — that is
        the whole of the target contract (`bench/contract.py`) — so a namespace on
        the request would be a second transport for the sake of a fixture. What is
        possible, and is what run-scoping buys here, is that a plant is *kept* under
        the run that made it and leaves with that run: the old one-slot-per-agent
        store lost the first run's value permanently the moment a second run
        registered, and this one does not. So the reading is the most recent
        namespace still holding a value for this agent, and a dropped namespace can
        never answer for a live one.
        """
        for planted in reversed(list(namespaces.values())):
            if agent in planted:
                return planted[agent]
        return ""

    @app.put("/reference/{agent}/nonce")
    def plant_nonce(agent: str, body: NonceRequest) -> dict[str, str]:
        """Test equipment: plant a registration nonce as an operator would by hand."""
        _agent(agent)
        namespaces.setdefault(body.namespace, {})[agent] = body.nonce
        return {"agent": agent, "namespace": body.namespace, "planted": "true"}

    @app.delete(NAMESPACES_PATH)
    def drop_namespace(namespace: str) -> dict[str, str]:
        """Test equipment: drop one run's namespace, wholesale.

        Not an error when there is nothing under it. A teardown runs on every exit
        path a run has, including the ones that planted nothing — the approval
        checkpoint declined, a `PlantingFailed` before the first attempt — and a drop
        that refused an empty namespace would make the harness decide, per exit path,
        whether to call it (ADR-0063 §2).
        """
        dropped = namespaces.pop(namespace, {})
        return {"namespace": namespace, "dropped": str(len(dropped))}

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
            body.message, _planted(agent), config.model, memory
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
