"""A user's function, served over the target contract, on loopback.

Somebody whose agent is a Python object rather than a deployed endpoint hands over
``f(message, session_id) -> reply`` and gets back a `TargetConfig`. The bench then
reaches it the way it reaches everything else — `send_message` over HTTP — so
nothing downstream of registration can tell a served callback from an endpoint
somebody deployed.

**The decision, the design it rejects, and the security properties of what is
served are
[ADR-0059](../../docs/adr/0059-a-callback-target-is-served-over-the-contract.md).**
The consequence here is the shape of the module: `serve_callback` takes no host and
no token, `_create_callback_app` builds one route, and the exception handler answers
in fixed prose. Each of those is an absence, so each is noted where it would
otherwise be added back.

The server lives for the ``with`` block and no longer.
"""

from __future__ import annotations

import inspect
import logging
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Protocol, get_type_hints

from fastapi import FastAPI, Header, HTTPException

from backend.bench.contract import (
    DEFAULT_RETRY,
    DeclaredControl,
    RetryPolicy,
    TargetConfig,
    ToolTrace,
)
from backend.bench.library import Plant
from backend.targets.reference.server import (
    MessageReply,
    MessageRequest,
    ToolCallPayload,
    ToolTracePayload,
)
from backend.targets.reference.serving import serve

LOGGER = logging.getLogger(__name__)

CALLBACK_RAISED = "the callback raised"
"""The whole of what a reply says when the callback fell over.

Fixed prose rather than the exception's own words, per ADR-0059 §2: the traceback
goes to `LOGGER` instead, where it is the operator's own to read.
"""

CALLBACK_FAILED_STATUS = 500
"""A raise, answered as the internal failure it is.

**In `contract.TRANSIENT_STATUSES`, and that membership is the whole of why this
literal is 500 rather than 400 or 200** — the retry policy sees it, so the sends a
raise costs land on `Transcript.sends` against one attempt and a callback that
raises on every send ends the run as `TargetFailure.UNAVAILABLE`. Editing this
number to one outside that set silently changes which of those two happens
(ADR-0059 §3).
"""

MESSAGES_PATH = "/messages"
"""The one route. A second route on this surface would be a second way in."""


@dataclass(frozen=True)
class Turn:
    """What a callback that can see its own tool calls returns.

    The trace is required, not optional, and that is the whole reason this type
    exists beside a bare `str`. `None` and an empty trace are already different
    answers (`contract.Transcript.tool_trace`): a target with no visibility returns
    the first and cannot be measured on scope creep or halt defeat, and a target
    that has visibility and did nothing this turn returns the second, which is a
    measured *resisted*. A callback with no visibility says so by returning a
    string, and the shim never invents an empty trace on its behalf.

    **Not CONTEXT.md's Turn**, which is one probe inside an adaptive **episode** and
    is the unit `A_effort` and the turn budget are counted in. This is a reply shape
    on the scored side, and it is named for the word the target layer already uses
    informally for the same thing — `server.messages` calls a reference agent's
    answer to one message `turn`. Nothing in the adaptive layer constructs one of
    these and nothing here is counted, so the collision is in the vocabulary and not
    in the arithmetic; the entry in CONTEXT.md draws the line.
    """

    reply: str
    tool_trace: ToolTrace


def hook_name(plant: Plant) -> str:
    """The method a callback implements to perform one planting.

    Derived from the member and never listed, which is the whole of what keeps the
    hook set general: #48 and #50 add a `Plant` member and get their hook name, their
    precondition and their withdrawal sentence from it, and no branch in this module
    or in `measurability.py` moves
    ([ADR-0061](../../docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)
    §4). The two `Protocol`s below spell the names out for a type checker and are
    checked against this function by the suite, so a member whose hook nobody wrote
    is caught here rather than at a run.
    """
    return f"plant_{plant.value}"


class ConfigCanaryPlanting(Protocol):
    """A callback that can be given a value in its own configuration.

    A `Protocol` and never a base class, on ADR-0059 §4's terms restated for the
    hooks: nothing about a user's agent should have to inherit from this bench to be
    measured by it, and a class that already has this method satisfies it as written.
    Beside `TextCallback` and `TracingCallback` rather than folded into them, because
    a callback either answers messages or plants and most do only the first.

    The value is the run's registration nonce and the bench issues it — one planted
    value, two roles (ADR-0007) — so the hook receives it and does not choose it.
    What calls this, when, and into what namespace, is #85 and #86; nothing in this
    module calls it, and there is deliberately no route by which a plant could arrive
    through `send_message` as an attempt.
    """

    def plant_config_canary(self, canary: str) -> None: ...


class RetrievedContentPlanting(Protocol):
    """A callback that can be given content its own retrieval will bring back.

    The `key` and the `body` are `PlantedArtefact`'s own two fields (ADR-0060): the
    word a message uses when it means this content, and the text to file under it
    exactly. So the hook is handed what the case record already holds, and a user
    implements it by putting that text where their agent's retrieval would find it.
    """

    def plant_retrieved_content(self, key: str, body: str) -> None: ...


class TextCallback(Protocol):
    """A user's agent that answers in text and cannot say what it did."""

    def __call__(self, message: str, session_id: str) -> str: ...


class TracingCallback(Protocol):
    """A user's agent that shows its tool calls beside its reply, every turn."""

    def __call__(self, message: str, session_id: str) -> Turn: ...


Callback = TextCallback | TracingCallback
"""A user's agent, as one call, in one of the two shapes a reply may take.

`Protocol`s and not a base class: nothing about a user's agent should have to
inherit from this bench to be measured by it, and a plain function, a bound method
and a callable object all satisfy either as written. The optional planting hooks are
`ConfigCanaryPlanting` and `RetrievedContentPlanting` above, and nothing here
requires them: a callback implementing neither is a target measured on the families
that need no planting and withdrawn from the ones that do (ADR-0061). The
`teardown()` that drops what they planted is #86.

**Two protocols rather than one returning `str | Turn`, because the union is what
`exposes_tool_calls_of` reads and a callback that could return either would be
declaring a visibility it has only sometimes.** A function annotated `-> str | Turn`
satisfies neither protocol, so `mypy` refuses it at the `serve_callback` call site
rather than the bench discovering it a turn later (ADR-0059 §4).
"""


def declared_plants(callback: Callback) -> frozenset[Plant]:
    """Which plantings this callback can perform, read off the object it is.

    **At construction and never at attack time**, which is why `serve_callback` calls
    this once and puts the answer on the `TargetConfig`. A hook discovered missing
    halfway through a family is a family half-measured: the attempts already spent
    went after content that was never planted and came back resisted, and the honest
    answer — not measurable — is one no partial run can give
    ([ADR-0061](../../docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)
    §5).

    `hasattr` and `callable`, not `isinstance` against the protocols: a
    `runtime_checkable` protocol checks the names and not the signatures either, so
    the extra machinery would buy nothing, and a plain function — which has none of
    these attributes — is the common shape and reads as no plantings, which is the
    conservative direction and the one `TargetConfig.plants` treats as *withdraw*.
    """
    return frozenset(
        plant for plant in Plant if callable(getattr(callback, hook_name(plant), None))
    )


def exposes_tool_calls_of(callback: Callback) -> bool:
    """Whether a callback shows what it did, read off the callback itself.

    **Derived, not declared, because here the bench built the endpoint.** One of two
    target properties that can be checked before a single message is sent, and it was
    the only one until `declared_plants` above joined it on the same argument
    (ADR-0061 §5). Every other target's `exposes_tool_calls` is its operator's word
    about a URL the bench cannot see inside, and the bench finds out it was wrong on
    the first reply (`NotMeasurable.TRACE_DECLARED_BUT_ABSENT`). ADR-0059 §4 has the
    argument, and the alternatives it beat.

    The reading is **exact**: the resolved return annotation *is* `Turn`, or there is
    no visibility. Not "mentions" — a union, an unannotated function and a lambda all
    read as no visibility, which is the conservative direction and the default
    `TargetConfig.exposes_tool_calls` already has.
    """
    signature_holder: Any = callback
    if not (inspect.isfunction(callback) or inspect.ismethod(callback)):
        # A callable object, which is the shape a real agent most often has: the
        # annotation lives on its `__call__` rather than on the instance.
        signature_holder = type(callback).__call__
    try:
        annotation = get_type_hints(signature_holder).get("return")
    except Exception:
        # An annotation naming a type that cannot be resolved from the callback's
        # own module. Unreadable is not visibility.
        return False
    return annotation is Turn


class CallbackBreachedItsAnnotation(TypeError):
    """A callback annotated `-> Turn` answered with a bare string.

    Raised inside the app, where it becomes a `CALLBACK_FAILED_STATUS` like any other
    raise, and so a named transport failure rather than a reply. **This is the
    mechanism that makes `exposes_tool_calls_of` a fact rather than a hope**: a shim
    target that declares visibility never emits a traceless reply, so
    `NotMeasurable.TRACE_DECLARED_BUT_ABSENT` is unreachable on this surface rather
    than merely unlikely (ADR-0059 §4).

    **Only this direction raises.** The mirror — a trace from a callback registered
    without visibility — is dropped with a warning by `_reply` instead, because the
    two families that read a trace were already withdrawn before anything was sent
    and passing it through would measure a family the registration withdrew. Refusing
    it would kill a run over evidence nobody was going to read.
    """

    def __init__(self, name: str) -> None:
        super().__init__(
            f"the callback served as {name!r} is annotated as returning a Turn and "
            f"returned a string. On this surface the annotation is what the bench "
            f"registered as `exposes_tool_calls`, so the two cannot disagree"
        )


TRACE_FROM_A_BLIND_TARGET = (
    "callback %r returned a tool trace and was registered without tool-call "
    "visibility, so the trace is dropped. Annotate it `-> Turn` to have the "
    "tool-visibility families measured against it"
)
"""What a dropped trace says in the log. Warned rather than silent: the operator is
the only person who can turn this into a measurement, and they can only do it if
they are told."""


def _create_callback_app(
    callback: Callback, auth_token: str, name: str, exposes_tool_calls: bool
) -> FastAPI:
    """The whole of the endpoint: one route, one bearer check, one reply shape.

    Private, and that is part of the property ADR-0059 §2 claims: `serve_callback`
    has no `auth_token` parameter, and a public app builder taking one would be the
    same choice available one import away.

    The request and reply models are the reference server's, so a shim target cannot
    drift off the one contract the bench speaks — the reasoning
    `backend/tests/flaky_target.py` is built on, applied to a surface a user reaches.
    """
    app = FastAPI(title=f"AgentAudit callback shim: {name}", version="0.1.0")

    @app.post(MESSAGES_PATH, response_model_exclude_none=True)
    def messages(
        body: MessageRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> MessageReply:
        if not secrets.compare_digest(authorization or "", f"Bearer {auth_token}"):
            raise HTTPException(status_code=401, detail="bad bearer token")
        try:
            answered = callback(body.message, body.session_id)
        except Exception:
            # The traceback goes to the log and not to the wire, and the status is
            # one the retry policy already knows what to do with.
            LOGGER.exception("callback %r raised while answering a message", name)
            raise HTTPException(
                status_code=CALLBACK_FAILED_STATUS, detail=CALLBACK_RAISED
            ) from None
        return _reply(answered, name, exposes_tool_calls)

    return app


def _reply(answered: str | Turn, name: str, exposes_tool_calls: bool) -> MessageReply:
    """One callback's return value as the contract's reply body.

    `response_model_exclude_none=True` on the route is what keeps the two absences
    apart on the wire: a bare string produces a body with no `tool_trace` key at
    all, which is how an endpoint says it has no visibility, while a `Turn` carrying
    an empty trace produces `{"calls": []}` — an endpoint that can see what it did
    and did nothing. The shim never invents the second from the first.
    """
    if isinstance(answered, Turn):
        if not exposes_tool_calls:
            LOGGER.warning(TRACE_FROM_A_BLIND_TARGET, name)
            return MessageReply(reply=answered.reply)
        return MessageReply(
            reply=answered.reply,
            tool_trace=ToolTracePayload(
                calls=[
                    ToolCallPayload(name=call.name, arguments=call.arguments)
                    for call in answered.tool_trace.calls
                ],
                stop_signal_at=answered.tool_trace.stop_signal_at,
            ),
        )
    if exposes_tool_calls:
        raise CallbackBreachedItsAnnotation(name)
    return MessageReply(reply=answered)


@contextmanager
def serve_callback(
    callback: Callback,
    *,
    name: str = "callback",
    agent_type: str = "assistant",
    retry: RetryPolicy = DEFAULT_RETRY,
    declared_tools: tuple[str, ...] = (),
    declared_controls: tuple[DeclaredControl, ...] = (),
    retains_session_state: bool = False,
    holds_personal_records: bool = False,
    processes_untrusted_input: bool | None = None,
    reaches_private_data: bool | None = None,
    changes_state_or_communicates: bool | None = None,
    under_human_supervision: bool | None = None,
) -> Iterator[TargetConfig]:
    """Serve a callback behind the contract and yield the target it now is.

    What comes back is a `TargetConfig` and nothing more specific. Everything
    downstream — registration, the applicability and precondition checks, the
    attempt, the verdict, the report — sees a target described the way a user's
    staging URL is described, and there is no field on it that says which of the two
    it was. That is the design: a shim target is measured by the code a URL target
    is measured by, or the gate is not evidence about a user's run.

    Every keyword but `retry` is a declaration the operator makes about their own
    agent, forwarded untouched, because these are the operator's statements wherever
    the agent lives. **The three the shim decides for itself are `url`,
    `auth_token` and `exposes_tool_calls`** — the port it bound, the secret it
    generated, and the one property it can read off the callback
    (`exposes_tool_calls_of`). There is no parameter for any of the three, and their
    absence is the whole of ADR-0059 §2's claim about this surface.

    **`plants` is the fourth the shim decides for itself**, read off the callback by
    `declared_plants` and with no parameter of its own either: a shim that could be
    *told* it plants would be the sentence ADR-0024 settled for, on the one surface
    where the bench can check instead (ADR-0061 §5). An endpoint target leaves the
    field `None` and its plantings stay the caller's declaration, where ADR-0024 put
    them.

    Not in scope here, stated so nobody adds it: nothing calls a planting hook yet
    (#85, #86, #87), there is no `teardown()`, and there is no route by which a plant
    could become an attempt — this module's one route is `MESSAGES_PATH`, and a hook
    is not on it.
    """
    exposes_tool_calls = exposes_tool_calls_of(callback)
    auth_token = secrets.token_urlsafe(32)
    app = _create_callback_app(callback, auth_token, name, exposes_tool_calls)
    with serve(app) as base_url:
        yield TargetConfig(
            name=name,
            url=f"{base_url}{MESSAGES_PATH}",
            auth_token=auth_token,
            agent_type=agent_type,
            retry=retry,
            exposes_tool_calls=exposes_tool_calls,
            plants=declared_plants(callback),
            retains_session_state=retains_session_state,
            holds_personal_records=holds_personal_records,
            declared_tools=declared_tools,
            declared_controls=declared_controls,
            processes_untrusted_input=processes_untrusted_input,
            reaches_private_data=reaches_private_data,
            changes_state_or_communicates=changes_state_or_communicates,
            under_human_supervision=under_human_supervision,
        )
