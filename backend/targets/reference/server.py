"""The reference agents served behind the target contract.

Two surfaces, and the distinction is load-bearing:

* ``POST /reference/{agent}/messages`` is the contract a user's target speaks. The
  bench knows nothing else about a target.
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
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.trivial import TRIVIAL
from backend.targets.reference.weak import WEAK

REFERENCE_AGENTS: tuple[ReferenceAgent, ...] = (TRIVIAL, WEAK, HARDENED)
"""The three agents of known construction, in the order their rates are expected to fall."""


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


class MessageReply(BaseModel):
    reply: str


class NonceRequest(BaseModel):
    nonce: str


def create_reference_app(config: ReferenceConfig) -> FastAPI:
    agents = {agent.name: agent for agent in config.agents}
    nonces: dict[str, str] = {}

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
        reply = reference_agent.reply(body.message, nonces.get(agent, ""), config.model)
        return MessageReply(reply=reply)

    return app
