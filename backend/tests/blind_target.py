"""A target that answers in text only. Test equipment for the bench's own tests.

The reference agents all expose their tool calls, by construction — they are
built to be measurable on all six families. The interesting target is the one
that is not, and the spec names it among the failure modes a real reference agent
will not produce on demand: "a configurable stub target used to produce the
failure modes (timeout, 401, malformed body, 429, **no tool calls**)".

It speaks the same contract the reference agents do and simply omits `tool_trace`
from every reply, which is what a target with no tool-call visibility looks like
on the wire. It answers with the planted nonce whatever it is asked, so
registration completes and the leakage case succeeds: the question these tests
ask is about measurability, and a target that also resisted would confound the
two.

Its request model is the reference server's, so this stub cannot drift off the
one contract the bench speaks. Its *reply* model deliberately is not — a target
without visibility has no field to fill, and using the reference reply would make
the omission an option rather than a property.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from backend.bench.calibration import PlantNonce
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import MessageRequest, NonceRequest
from backend.targets.reference.serving import serve

AUTH_TOKEN = "blind-auth-token"
IMPATIENT = RetryPolicy(sends=3, backoff_seconds=0.0)


class TextOnlyReply(BaseModel):
    """The whole of what a target without tool-call visibility can say."""

    reply: str


@dataclass(frozen=True)
class ServedBlindTarget:
    target: TargetConfig
    plant_nonce: PlantNonce


@dataclass
class BlindState:
    nonce: str = ""


def create_blind_app() -> FastAPI:
    """An app that speaks the contract and never says what it did."""
    state = BlindState()

    app = FastAPI(title="Target without tool-call visibility", version="0.1.0")

    @app.put("/reference/{agent}/nonce")
    def plant_nonce(agent: str, body: NonceRequest) -> dict[str, str]:
        state.nonce = body.nonce
        return {"agent": agent, "planted": "true"}

    @app.post("/reference/{agent}/messages")
    def messages(
        agent: str,
        body: MessageRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TextOnlyReply:
        if authorization != f"Bearer {AUTH_TOKEN}":
            raise HTTPException(status_code=401, detail="bad bearer token")
        return TextOnlyReply(reply=state.nonce)

    return app


@contextmanager
def blind_target(
    declared_tools: tuple[str, ...] = (), declared_visible: bool = False
) -> Iterator[ServedBlindTarget]:
    """Serve a trace-blind target, registered as the operator would register it.

    `exposes_tool_calls=False` is the registration field, and it is what the
    bench reads before it spends anything — not a discovery made from a reply
    that came back without a trace (PLAN §3).

    `declared_visible=True` is the other target this stub can be: the same endpoint,
    registered by an operator who declared a visibility it does not have. The
    declaration is theirs and the bench has nothing to check it against until the
    first reply comes back, so this is the equipment for what happens when one is
    contradicted.
    """
    with serve(create_blind_app()) as base_url:
        yield ServedBlindTarget(
            target=TargetConfig(
                name="blind",
                url=f"{base_url}/reference/blind/messages",
                auth_token=AUTH_TOKEN,
                agent_type="assistant",
                retry=IMPATIENT,
                exposes_tool_calls=declared_visible,
                declared_tools=declared_tools,
            ),
            plant_nonce=nonce_planter(base_url),
        )
