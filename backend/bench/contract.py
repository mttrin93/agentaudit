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

Transport failures — timeout, 401, malformed body, 429 — are **named outcomes**
(`TargetFailure`), raised as `TargetUnreachable` rather than scored. A failure
that outlives the retry policy stops the run under its own name, and no attempt is
recorded for it: an endpoint having a bad minute must not read as an agent that
defended itself, and a body the bench cannot read is not an empty reply.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from backend.bench.library import Plant

DEFAULT_TIMEOUT = 60.0
"""How long one send waits for a target's reply. The outer wait of the chain.

There are three waits between the bench and a model, and they are not
independent. This one is the bench waiting on a target endpoint. Inside it, that
endpoint waits on its own model — for a reference agent that is
`backend/targets/reference/model.MODEL_PATIENCE_SECONDS`, held strictly under this
number by `refuse_inverted_patience` so that a stalled reference agent is not
still holding the wire after the bench has already named a `TIMEOUT` against it.
The third, `completion.MODEL_TIMEOUT_SECONDS`, is the bench waiting on its own
instrument and sits outside the chain: nothing waits on the bench.

Sixty seconds, and the same reasoning at every one of the three — long enough that
a slow answer still arrives, short enough that a stalled one is a failure somebody
is told about.
"""

RATE_LIMITED_STATUS = 429
"""A quota, told apart from an outage: both are retried, and they end differently."""

AUTH_STATUSES = frozenset({401, 403})
"""A rejected credential. Never retried, and never a verdict."""

TRANSIENT_STATUSES = frozenset({RATE_LIMITED_STATUS, 500, 502, 503, 504})
"""Replies that say "not now" rather than "no".

Listed rather than derived from the 5xx range, so that adding one is a decision.
401 is deliberately absent: a rejected token is not a bad minute, and retrying it
three times is three more rejections. Each of these has its own named outcome
below; here they only decide whether to send again.
"""


class TargetFailure(StrEnum):
    """Why the bench got no usable reply — one named outcome per failure mode.

    **None of these is a verdict, and none of them is a security result.** An
    endpoint having a bad minute must not read as an agent that defended itself:
    the two are the same silence on the wire and opposite facts about the target,
    so the difference is carried by a type rather than by a rate that happens to
    look defensive. A `Verdict` says what one attempt reached; a failure here says
    no attempt was reached at all, and no `Attempt` is recorded for one.

    Named per mode rather than collapsed into one *unreachable*, because the four
    the spec names are four different jobs for the person reading the run: a
    timeout is capacity, a rejected token is configuration, a malformed body is a
    contract breach, and a rate limit is a quota. A single word for all four would
    send every one of them to the same wrong place.
    """

    TIMEOUT = "timeout"
    AUTH_REJECTED = "auth_rejected"
    MALFORMED_REPLY = "malformed_reply"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    """A 5xx that outlived the retry policy. The transient statuses of
    `TRANSIENT_STATUSES` other than 429, which has its own name because a quota is
    not an outage."""

    UNREACHABLE = "unreachable"
    """No connection at all — refused, reset, or a name that does not resolve.
    Distinct from a timeout, which is an endpoint that answered too slowly rather
    than one that was never there."""

    REFUSED = "refused"
    """A status the contract does not define, kept rather than guessed at. A 404 is
    a wrong URL and a 400 is a rejected body, and neither is an agent resisting."""

    def stated(self) -> str:
        """The outcome in the words a run prints, with what it is not."""
        match self:
            case TargetFailure.TIMEOUT:
                return "timeout — the endpoint did not answer inside its declared wait"
            case TargetFailure.AUTH_REJECTED:
                return (
                    "auth failure — the endpoint rejected the bearer token. Not "
                    "retried: a rejected token is not a bad minute"
                )
            case TargetFailure.MALFORMED_REPLY:
                return (
                    "malformed reply — the body was not the contract's "
                    '{"reply": "<text>"}. A reply the bench cannot read is not an '
                    "empty reply, and an empty reply would have scored as resisted"
                )
            case TargetFailure.RATE_LIMITED:
                return "rate limit — the endpoint answered 429 on every send"
            case TargetFailure.UNAVAILABLE:
                return (
                    "unavailable — the endpoint answered 5xx on every send, so the "
                    "retry policy is exhausted rather than the target measured"
                )
            case TargetFailure.UNREACHABLE:
                return "unreachable — no connection to the endpoint was made at all"
            case TargetFailure.REFUSED:
                return (
                    "refused — the endpoint answered with a status this contract "
                    "does not define, so what came back is not a reply"
                )


NOT_A_SECURITY_RESULT = "No attempt is recorded and nothing here is a security result"
"""What every report of a transport failure says beside the outcome it names.

One sentence in one place, because it is said twice — once by the exception a run
stops on and once by the surface that reports the run — and two copies of a
statement this load-bearing are two statements that drift.
"""


class TargetUnreachable(RuntimeError):
    """One named transport outcome, raised instead of being scored.

    Raised rather than returned, and this is the whole of the design: a caller
    cannot forget to look at it, and there is no field on an `Attempt` for a
    transport failure to sit in and be counted from. Infrastructure failure that
    reached a rate would be indistinguishable from a defended agent, and it would
    be the *good* number — which is the direction a bench must never fail in.
    """

    def __init__(
        self,
        failure: TargetFailure,
        url: str,
        sends: int,
        status_code: int | None = None,
    ) -> None:
        self.failure = failure
        self.url = url
        self.sends = sends
        self.status_code = status_code
        status = "" if status_code is None else f" (HTTP {status_code})"
        super().__init__(
            f"{url} after {sends} "
            f"{'send' if sends == 1 else 'sends'}{status}: {failure.stated()}. "
            f"{NOT_A_SECURITY_RESULT}"
        )


@dataclass(frozen=True)
class RetryPolicy:
    """How patient the bench is with one endpoint before it gives up on a message."""

    sends: int = 3
    """How many times one message may go on the wire. Not attempts — see the
    module docstring."""

    backoff_seconds: float = 0.5
    """The first wait, doubled on each further retry."""

    timeout_seconds: float = DEFAULT_TIMEOUT
    """How long one send may wait for a reply before it is a timeout.

    Held on the policy rather than as a module constant so that the named outcome
    below is reachable from a test: a failure mode the suite cannot produce on
    demand is a failure mode nobody knows the bench handles, and a healthy
    endpoint never shows one.
    """

    def __post_init__(self) -> None:
        if self.sends < 1:
            raise ValueError("a retry policy has to allow at least one send")
        if self.timeout_seconds <= 0:
            raise ValueError("a send that may not wait at all cannot get a reply")

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


class DeclaredControl(StrEnum):
    """A defence the operator states their target has. A statement, never a
    measurement.

    The checklist is the four controls the hardened reference agent is built from
    (PLAN §3, `backend/targets/reference/controls.py`), and each member claims
    exactly one deterministic family — which is what makes the declared-and-defeated
    join a join over verdicts rather than over prose. `scanner.py` holds the
    checklist and the mapping; the enumeration sits here because it is a registered
    property of a target, beside `declared_tools` and `exposes_tool_calls`, and a
    target cannot describe itself in terms of a module that reads it.

    Closed like every other enumeration in the bench: a control the checklist has
    no member for is a control the bench has no attack for, and admitting it as
    free text would let a target declare defences against families that do not
    exist. Growing the checklist is trigger 6 (`SCAN_CHECKLIST_GREW`) and it means
    writing the attack first.

    Nothing here is worth anything until an attack has run against it. A target
    that declares all four and holds none of them is the exact case this bench was
    built to find, and it is the reason no declared control ever contributes to a
    rate, a band or a score (ADR-0005, ADR-0006).
    """

    INPUT_CHECK = "input_check"
    """A check ahead of the model that refuses a message carrying an override
    pattern. Claims indirect prompt injection."""

    SCOPE_LIMIT = "scope_limit"
    """An allow-list of the tools the agent may call. Claims scope creep."""

    OUTPUT_FILTER = "output_filter"
    """A filter that withholds a reply carrying protected material. Claims data
    leakage."""

    STOP_CONTROL = "stop_control"
    """A halt that ends the turn when the operator's stop signal arrives. Claims
    halt defeat."""


class AgentCapability(StrEnum):
    """One of the three properties the Agents Rule of Two is read over.

    A **declared capability** ([CONTEXT.md](../../CONTEXT.md)) and not a
    `DeclaredControl`: a control is a defence the operator claims, this is something
    the agent can *do*. Why the rule is read off a declaration rather than measured is
    [ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md).

    It sits here rather than in `scanner.py` for the reason `DeclaredControl` does: it
    is a registered property of a target, beside `declared_controls` and
    `declared_tools`, and a target cannot describe itself in terms of a module that
    reads it. `scanner.py` holds the reading.

    **There is deliberately no `family_claimed_by` for this enumeration**, and that
    absence is ADR-0038's decision 3 at the one call site where it could be undone.
    Each of the three has a family that is its near-neighbour — untrusted input beside
    indirect prompt injection, private data beside data leakage, outward action beside
    scope creep — so a mapping is the obvious next thing to write and it is the thing
    that would let a declaration be read off verdicts. The two enumerations share no
    member and no function.
    """

    PROCESSES_UNTRUSTED_INPUT = "processes_untrusted_input"
    """Handles content the operator does not control — retrieved pages, documents,
    messages from third parties."""

    REACHES_PRIVATE_DATA = "reaches_private_data"
    """Can read private data or reach sensitive systems inside the boundary."""

    CHANGES_STATE_OR_COMMUNICATES = "changes_state_or_communicates"
    """Can change state or communicate outward — write, pay, send, publish."""


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

    retains_session_state: bool = False
    """Whether this endpoint carries one turn of a session into the next.

    A **registered** property on the same terms as `exposes_tool_calls` above, and
    for the same reason: memory poisoning has to be refused *before* any attempt is
    spent against a target that cannot answer it. It defaults to false, which is the
    conservative direction — an endpoint whose operator did not say it remembers
    anything is one the bench declines to measure on persistence rather than one it
    reports a clean zero for
    ([ADR-0041](../../docs/adr/0041-the-persistence-canary-is-read-over-two-turns.md)).

    It is a declaration and never a measurement, so it moves no rate: what it decides
    is whether the family is *attempted*, which is what ADR-0024 already establishes
    a declaration of this kind may decide and no more.
    """

    holds_personal_records: bool = False
    """Whether this endpoint holds records about people who are not the operator.

    A **registered** property on the same terms as the two above, and for the same
    reason: PII leakage has to be refused *before* any attempt is spent against a
    target that has nothing about anybody to disclose. It defaults to false, which is
    the conservative direction — an endpoint whose operator did not say it holds
    third-party records is one the bench declines to measure on disclosure of them
    rather than one it reports a clean zero for
    ([ADR-0043](../../docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)).

    Not the same statement as `reaches_private_data` below, which is one of the three
    properties the Agents Rule of Two is read over: that one is about what this agent
    *can reach* and is read by `scanner.py` alone, and ADR-0038 §3 is explicit that
    nothing joins it to a family. This one is about what is there to be disclosed, it
    decides measurability and no figure, and neither is derived from the other.
    """

    declared_tools: tuple[str, ...] = ()
    """The tools the operator declared their target has.

    Scope creep is a call *outside* this list, so the list is the whole of the
    comparison. It is a declaration and not a measurement — the same status as a
    declared control — which is exactly why an attack that produces a call
    outside it is a finding.
    """

    declared_controls: tuple[DeclaredControl, ...] = ()
    """The defences the operator states this target has. Read by `scanner.py`.

    Empty by default, and the default is the honest one: a target whose operator
    declared nothing has nothing to be caught over-declaring, and every control it
    turns out to have simply goes unclaimed. Declaring more can only add rows to
    the declared-controls section — never move a rate, a band or a `D`, which is
    what makes declaring truthfully the operator's own interest rather than a
    scoring strategy (ADR-0005).
    """

    processes_untrusted_input: bool | None = None
    """Whether this agent handles content the operator does not control.

    The first of the Agents Rule of Two's three properties, and the first of the four
    declarations `scanner.py` reads that rule over. Three states and not two: `None`
    is *unstated*, `False` is a declared absence, and the two are different answers
    all the way through the reading. Why unstated is the default, and why the reading
    they produce moves no figure, is
    [ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md),
    decisions 1 and 4.

    None of the four is derived from another field, `declared_tools` included: a
    capability guessed from a tool name would be a measurement wearing a
    declaration's name, in the direction the module docstring of `scanner.py` names.
    """

    reaches_private_data: bool | None = None
    """Whether this agent can reach private data or sensitive systems. The second."""

    changes_state_or_communicates: bool | None = None
    """Whether this agent can change state or communicate outward. The third."""

    under_human_supervision: bool | None = None
    """Whether a human confirms what this agent does inside one session.

    The fourth declaration, and not an afterthought beside the three above: it is the
    **unsupervised** third property that the rule warns about, so a scan that read the
    three without this one would report a shape the rule does not object to.
    """

    plants: frozenset[Plant] | None = None
    """Which plantings this target can be given, or `None` for a target that is asked.

    Three states, and the third is the whole of why this is not a `bool` per planting.
    A member present is *this planting can be performed on this target*; a member
    absent from a set is *it cannot*, which withdraws the families that need it as
    `NotMeasurable`; and `None` is **this target does not answer for its own
    plantings** — the caller's declaration does, through `plan_for` and
    `DeclaredGap.NOTE_NOT_PLANTED` / `NONCE_NOT_PLANTED`, exactly where those two have
    always been.

    That split is two surfaces giving two truthful answers rather than one answer with
    an exception. Against a URL somebody deployed the bench cannot see inside the
    content store, so a planting is the operator's statement and a gap nothing here
    detects; against a target this bench served itself from a user's own Python
    object it holds that object, so a planting hook nobody implemented is read off it
    before anything is sent
    ([ADR-0061](../../docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)).
    The module ADR-0061 names is the one place this field is ever filled in, and it
    fills it in from the object it serves rather than from a parameter — which is why
    the field is data like every other here, and nothing in this module knows how it
    came to be set.

    Like every declaration on this record it decides whether a family is *attempted*
    and never what an attempt measures — ADR-0006, and ADR-0024's own wording: this is
    a precondition of measurement, not an input to one.
    """

    def can_be_planted(self, plant: Plant) -> bool:
        """Whether this planting can be put in place before an attempt is spent.

        The one question `measurability._target_meets` asks of a target about a
        planting, so that neither surface's answer is spelled out at the call site.
        A target that does not answer for itself answers yes here and is withdrawn —
        or not — by the caller's own declaration instead; reading `None` as *no* would
        withdraw both plant-dependent families from every endpoint target in the
        world, which is not a fact about any of them.
        """
        return self.plants is None or plant in self.plants


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


@functools.lru_cache(maxsize=1)
def _client() -> httpx.Client:
    """The one client every send goes through, so the connection is not rebuilt.

    `httpx.post` builds a client, opens a connection and throws both away, once per
    call. A scored run is 181 calls at one endpoint: measured against a local
    reference agent that is 10.7 ms a call against 1.5 ms through a kept-alive
    client, and the gap is the whole of the handshake — which is TCP alone there and
    TCP plus TLS against anything remote.

    **A reused connection is not a reused session.** Attempts are independent
    because each carries its own `session_id` and the contract says that is what
    carries a conversation; the socket underneath them is transport. A target that
    kept state per connection would be answering a protocol this one does not
    describe.

    The timeout stays on the request rather than moving to the client, because it is
    the *target's* declared patience (`RetryPolicy.timeout_seconds`) and one client
    serves every target in a run. The pool is closed by the process exiting, on the
    reasoning `completion.py` builds its own client on: a bench that is running has
    one of these, and a bench that is not is gone.
    """
    return httpx.Client()


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
            response = _client().post(
                target.url,
                json=sent,
                headers={"Authorization": f"Bearer {target.auth_token}"},
                timeout=target.retry.timeout_seconds,
            )
        except httpx.TimeoutException:
            # An endpoint that answered too slowly, retried like any bad minute
            # and named as itself when the policy runs out.
            if last_send:
                raise TargetUnreachable(
                    TargetFailure.TIMEOUT, target.url, send
                ) from None
        except httpx.TransportError:
            # No connection at all — refused, reset, or a name that did not
            # resolve. A different fact about the endpoint from a timeout.
            #
            # A pooled connection the endpoint closed while it was idle arrives here
            # too, as `RemoteProtocolError`, and is retried like any other bad
            # minute. That race is the price of keeping connections, and the retry
            # policy is what already pays it.
            if last_send:
                raise TargetUnreachable(
                    TargetFailure.UNREACHABLE, target.url, send
                ) from None
        else:
            if response.status_code not in TRANSIENT_STATUSES:
                return _received(target, sent, response, send)
            if last_send:
                raise TargetUnreachable(
                    _transient_failure(response.status_code),
                    target.url,
                    send,
                    response.status_code,
                )
        time.sleep(target.retry.wait_before(send))

    raise AssertionError("a retry policy with no sends cannot deliver a message")


def _received(
    target: TargetConfig, sent: dict[str, Any], response: httpx.Response, send: int
) -> Transcript:
    """The reply as a transcript, or a named outcome if it is not one.

    The body is checked here rather than read leniently downstream, because
    `Transcript.reply_text` answers `""` for a body it cannot read and an empty
    reply scores as **resisted**. A target returning prose in a field the contract
    does not name would therefore be recorded as an agent that held — the exact
    coercion of infrastructure into a security result the named outcomes exist to
    stop.
    """
    if response.status_code in AUTH_STATUSES:
        raise TargetUnreachable(
            TargetFailure.AUTH_REJECTED, target.url, send, response.status_code
        )
    if not response.is_success:
        raise TargetUnreachable(
            TargetFailure.REFUSED, target.url, send, response.status_code
        )
    try:
        received = response.json()
    except ValueError:
        raise TargetUnreachable(
            TargetFailure.MALFORMED_REPLY, target.url, send, response.status_code
        ) from None
    if not isinstance(received, dict) or not isinstance(received.get("reply"), str):
        raise TargetUnreachable(
            TargetFailure.MALFORMED_REPLY, target.url, send, response.status_code
        )
    return Transcript(
        url=target.url,
        sent=sent,
        status_code=response.status_code,
        received=received,
        sends=send,
    )


def _transient_failure(status_code: int) -> TargetFailure:
    """Which named outcome a transient status ends as once the retries are spent."""
    if status_code == RATE_LIMITED_STATUS:
        return TargetFailure.RATE_LIMITED
    return TargetFailure.UNAVAILABLE
