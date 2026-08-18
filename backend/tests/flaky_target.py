"""A target that fails before it answers. Test equipment for the bench's own tests.

The reference agents will not produce a timeout, a 429 or a 503 on demand, and
the failure modes that matter most are exactly the ones a healthy endpoint never
shows. This app speaks the same contract they do and fails a stated number of
times before each reply.

It answers with the planted nonce whatever it is asked, so registration completes
and the leakage case succeeds: the question these tests ask is about the
transport, and a target that also resisted would confound the two.

Its request and reply models are the reference server's, so this stub cannot
drift off the one contract the bench speaks.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from backend.bench.calibration import PlantNonce
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import (
    MessageReply,
    MessageRequest,
    NonceRequest,
)
from backend.targets.reference.serving import serve

AUTH_TOKEN = "flaky-auth-token"
IMPATIENT = RetryPolicy(sends=3, backoff_seconds=0.0)
"""The declared retry policy with the waiting taken out, so a suite stays quick."""


@dataclass(frozen=True)
class ServedFlakyTarget:
    target: TargetConfig
    plant_nonce: PlantNonce


@dataclass
class FlakyState:
    nonce: str = ""
    failures: int = 0
    """How many times the endpoint has already failed on the message in hand."""


def create_flaky_app(
    failures_before_reply: int,
    status_code: int = 503,
    malformed: bool = False,
    sleep_seconds: float = 0.0,
) -> FastAPI:
    """An app that fails `failures_before_reply` times before answering each message.

    `malformed` answers 200 with a body that is not the contract's, and
    `sleep_seconds` answers too slowly to be waited for. Both are failure modes a
    healthy endpoint never shows and the two the bench most needs to name: a body
    it cannot read would otherwise be an empty reply, and an empty reply scores as
    resisted.
    """
    state = FlakyState()

    app = FastAPI(title="Flaky target", version="0.1.0")

    @app.put("/reference/{agent}/nonce")
    def plant_nonce(agent: str, body: NonceRequest) -> dict[str, str]:
        state.nonce = body.nonce
        return {"agent": agent, "planted": "true"}

    @app.post("/reference/{agent}/messages", response_model=None)
    def messages(
        agent: str,
        body: MessageRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> MessageReply | JSONResponse:
        if authorization != f"Bearer {AUTH_TOKEN}":
            raise HTTPException(status_code=401, detail="bad bearer token")
        if sleep_seconds:
            time.sleep(sleep_seconds)
        if state.failures < failures_before_reply:
            state.failures += 1
            raise HTTPException(status_code=status_code, detail="try again")
        state.failures = 0
        if malformed:
            # Two hundred, JSON, and not the contract: the field the bench reads is
            # absent and the text sits under a name of the endpoint's own choosing.
            return JSONResponse({"answer": state.nonce})
        return MessageReply(reply=state.nonce)

    return app


@contextmanager
def flaky_target(
    failures_before_reply: int,
    status_code: int = 503,
    malformed: bool = False,
    sleep_seconds: float = 0.0,
    auth_token: str = AUTH_TOKEN,
    timeout_seconds: float = 60.0,
) -> Iterator[ServedFlakyTarget]:
    """Serve a flaky target, described the way any target is described."""
    with serve(
        create_flaky_app(failures_before_reply, status_code, malformed, sleep_seconds)
    ) as base_url:
        yield ServedFlakyTarget(
            target=TargetConfig(
                name="flaky",
                url=f"{base_url}/reference/flaky/messages",
                auth_token=auth_token,
                agent_type="assistant",
                retry=RetryPolicy(
                    sends=IMPATIENT.sends,
                    backoff_seconds=IMPATIENT.backoff_seconds,
                    timeout_seconds=timeout_seconds,
                ),
            ),
            plant_nonce=nonce_planter(base_url),
        )
