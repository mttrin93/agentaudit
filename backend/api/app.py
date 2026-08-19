"""The HTTP surface: a nonce, a run, and the answer to the run's interrupt.

Four routes. `POST /nonces` issues the value an operator plants to prove they
control the endpoint; `POST /runs` records the attestation, declares the estimate
and halts; `POST /runs/{id}/approval` answers the halt; `GET /runs/{id}` says where
the run has got to. The report route is #56 and reads records this module already
keeps.

**Progress is reported per layer, and there is no figure that spans them.**
Position in the scored layer is family, case and attempt; in the adaptive layer it
is family, episode and turn — different units, different models, and no field
anywhere that adds the two (CONTEXT.md, ADR-0010). Calls spent and findings so far
are per layer for the reason the estimate is two figures: a blended number hides
which half of a run is consuming the operator's budget. A layer the run has not
reached says so, because a zero there would read as a layer that ran and found
nothing — and a run stopped on the wire reports its named transport outcome under
its own name, never as a security result.

**The interrupt is a route rather than a request field, and that is the whole
point.** A `confirmed: true` field on the start request would be a form, answered
by whatever composed the request. A separate answer to a graph that has already
halted is a decision taken in front of the figures — the human-in-the-loop pattern
ADR-0007 asks for, in the form LangGraph gives it.

**What the estimate response carries is `BudgetPayload` and nothing else.** The
scored figure exact, the adaptive figure a ceiling, the bounded total and the hard
ceiling that is actually enforced — the same record the terminal prints from, so a
browser and a terminal show an operator identical figures. Nothing in this module
computes a figure of its own, which is the structural version of "never blended
and never averaged": there is no arithmetic here to blend anything with.

**Cost is declared, and declared explicitly.** `price_per_call` has no default: a
caller who has not priced their endpoint says so by sending `null` and gets a run
whose cost reads *not priced*, and a caller who omits the field gets a refusal
rather than a number. Nothing reads the environment — the confirmation is the
liability record, so the figures in it have to be the caller's own.

Served with a factory, because the case library is read when the app is built and
an import-time read would make importing this module a filesystem question::

    uv run uvicorn backend.api.app:create_app --factory
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, status
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from backend.api.runs import (
    BenchConfig,
    BenchRuns,
    NeverPresented,
    NoLongerWaiting,
    NonceNotIssued,
    RunRecord,
    RunStatus,
)
from backend.bench.admission import admitted_library
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.registration import ECHO_PROBE, Attestation
from backend.graph.approval import Approval
from backend.graph.budget import BudgetPayload, CallPrice, Layer

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
"""The case library a bench serves when it was not given one.

The admitted library, never the raw one: a case that has not separated the three
reference agents may not be sent to somebody's endpoint on the strength of nobody
having checked (`admission.py`).
"""

PLANT_STATEMENT = (
    "Plant this value in the target's configuration before starting a run. Only "
    "somebody who can edit that configuration can plant it, which is what makes "
    "the echo proof that you control the endpoint (ADR-0007). The same value is "
    "the data-leakage canary — one planted value, two roles — so do not add it to "
    "any output allow-list. The run's registration probe sends the echo probe "
    "below verbatim, and a target that does not answer it with the nonce is not "
    "attempted."
)


class TargetRequest(BaseModel):
    """How a caller describes the endpoint they are asking the bench to attack."""

    name: str
    url: str
    auth_token: str
    agent_type: str
    exposes_tool_calls: bool
    """Declared, never sniffed. Two families are read from a tool trace, and a
    target that returns none reports them *not measurable* rather than defended."""

    declared_tools: list[str] = Field(default_factory=list)
    """The tools the operator states their target has. Scope creep is a call
    outside this list, so against an empty one every call would be a finding —
    which is why a target that exposes its calls has to declare them."""

    sends: int = RetryPolicy().sends
    """How many times one message may go on the wire to this endpoint. It is what
    the enforced ceiling is built from, so it is the caller's declaration and not
    a constant hidden inside the bench."""

    def config(self) -> TargetConfig:
        if self.exposes_tool_calls and not self.declared_tools:
            raise ValueError(
                "a target that exposes its tool calls has to declare which tools "
                "it has: scope creep is read against that list, and against an "
                "empty one every call this target makes would score as a finding"
            )
        return TargetConfig(
            name=self.name,
            url=self.url,
            auth_token=self.auth_token,
            agent_type=self.agent_type,
            retry=RetryPolicy(sends=self.sends),
            exposes_tool_calls=self.exposes_tool_calls,
            declared_tools=tuple(self.declared_tools),
        )


class AttestationRequest(BaseModel):
    """The three statements, one field each.

    Three fields rather than one `i_agree`, because the record has to show *what*
    was attested — and because two of the three are consequences a user would
    never infer (ADR-0007).
    """

    identity: str
    authorised_to_test: bool
    not_production: bool
    accepts_provider_policy_and_cost: bool

    def attestation(self) -> Attestation:
        """The record, which cannot be constructed with a statement withheld."""
        return Attestation(
            identity=self.identity,
            authorised_to_test=self.authorised_to_test,
            not_production=self.not_production,
            accepts_provider_policy_and_cost=self.accepts_provider_policy_and_cost,
        )


class CostRequest(BaseModel):
    """What one call to this endpoint costs the caller, as the caller states it.

    Required, with no default anywhere: a target is the operator's endpoint on the
    operator's provider, so the price is theirs to declare. `price_per_call: null`
    is a declaration too — the run reports *not priced* rather than zero, because
    an unknown cost and a free run are different facts and only one of them is
    safe to confirm without reading further.
    """

    price_per_call: str | None
    currency: str = ""
    """What currency the price is in, when there is a price.

    Empty by default and refused when a price is declared without it, by
    `CallPrice`'s own guard: an amount with a currency the bench chose is a figure
    the caller did not state, and it is the one part of a cost display that cannot
    be inferred from anywhere.
    """

    def price(self) -> CallPrice | None:
        if self.price_per_call is None:
            return None
        try:
            return CallPrice(
                per_call=Decimal(self.price_per_call), currency=self.currency
            )
        except InvalidOperation as unusable:
            raise ValueError(
                f"{self.price_per_call!r} is not a price per call: declare a "
                "decimal amount, or null for a run you have not priced"
            ) from unusable


class StartRunRequest(BaseModel):
    """Everything a run needs before it may exist, and nothing it can default."""

    target: TargetRequest
    attestation: AttestationRequest
    nonce: str
    cost: CostRequest
    note_planted: bool = False
    """Whether the third-party note the indirect-injection family needs is in place.

    Declared by the caller because the bench cannot check it and does not serve the
    content: the family reads whether a planted instruction was *carried out*, and
    without the note it would report a clean zero that reads as a defence. Declared
    false, the family is not run and the estimate does not charge for it.
    """


class NonceIssued(BaseModel):
    """The value to plant, the probe that will check it, and what both are for."""

    nonce: str
    echo_probe: str
    statement: str


class RunResponse(BaseModel):
    """A run as it stands right now, with its figures and what it has spent.

    `spent` is per layer and there is no total beside it, for the reason the
    estimate is two figures: a blended number hides which half of a run is
    consuming the operator's budget (ADR-0007).
    """

    run_id: str
    status: str
    statement: str
    estimate: BudgetPayload
    """The consent surface exactly as the approval interrupt presented it.

    `BudgetPayload` itself rather than a model restating its fields, because a
    restatement is a second place for the figures to be described and the first
    thing anybody would edit to add a friendlier summary. There is no combined
    figure here the budget did not build and mark as a bound, and no average of
    any kind: `CallFigure.__add__` makes a fact plus a bound a bound, so the total
    is a ceiling by arithmetic rather than by convention (ADR-0007).
    """

    spent: dict[str, int]
    cases: int
    families_not_run: dict[str, str]


def response_for(record: RunRecord) -> RunResponse:
    """One run as it stands, built in one place so every route says the same thing."""
    return RunResponse(
        run_id=record.run_id,
        status=str(record.status),
        statement=record.statement,
        estimate=record.presented,
        spent={str(layer): record.spent[layer] for layer in Layer},
        cases=len(record.plan.cases),
        families_not_run={
            str(family): gap.stated() for family, gap in record.plan.gaps.items()
        },
    )


SCORED_NOT_STARTED = (
    "the scored layer has not started: nothing has been sent to the target, so "
    "there is no case in flight and no attempt to report. Its findings so far are "
    "absent rather than zero — a zero would read as a suite that ran and found "
    "nothing"
)

ADAPTIVE_NOT_REACHED = (
    "the run has not reached the adaptive layer: it starts only once the whole "
    "scored suite has finished (ADR-0010), so there is no episode and no turn yet. "
    "Its findings so far are absent rather than zero — a zero would read as an "
    "attacker that ran and found nothing"
)

NOT_A_SECURITY_RESULT = (
    "No attempt is recorded and nothing here is a security result: an endpoint "
    "having a bad minute and an agent that defended itself are the same silence on "
    "the wire and opposite facts about the target"
)


class ScoredPosition(BaseModel):
    """Where the scored layer is: family, case and attempt.

    Three fields because they are three things (CONTEXT.md). The attempt is
    counted from one, so `attempt: 1` is the first of the case's ten — an ordinal
    a reader is watching go by, and never a count of what the run has done.
    """

    family: str
    case_id: str
    attempt: int


class AdaptivePosition(BaseModel):
    """Where the adaptive layer is: family, episode and turn.

    A separate model from `ScoredPosition` rather than a shared one with a layer
    label, because the units differ and a reader who could compare the two fields
    would be comparing an attempt with a turn — the arithmetic CONTEXT.md keeps
    apart and ADR-0010 forbids. `episode` counts the episodes this run has started
    and `turn` counts the probes sent inside the current one; neither is a
    denominator, and nothing divides by either.
    """

    family: str
    episode: int
    turn: int


class ScoredProgress(BaseModel):
    """What the scored layer has reached, spent and found so far."""

    reached: bool
    statement: str
    position: ScoredPosition | None
    calls_spent: int
    """Calls this layer has put on the wire. Its own figure, beside the other
    layer's and never added to it."""

    succeeded_attempts: int | None
    """The attempts that succeeded so far, or `None` for a layer that has not run.

    Not called findings, on `RunState.succeeded_attempts`' own reasoning: a
    **finding** is a verdict *plus* its narrative, and this is a count of verdicts.
    It is `None` rather than `0` before the layer starts, because those are two
    different facts and only one of them is about a suite that ran.
    """


class AdaptiveProgress(BaseModel):
    """What the adaptive layer has reached, spent and found so far.

    A model of its own for the reason the positions are two models: this layer's
    findings are **adaptive findings** — routes an episode found — which carry no
    rate, no interval, no band and no `D`, and may never be added to the scored
    layer's count (ADR-0010).
    """

    reached: bool
    statement: str
    position: AdaptivePosition | None
    calls_spent: int
    adaptive_findings: int | None
    """The episodes that found a route, or `None` for a layer this run has not
    reached."""


class TransportOutcome(BaseModel):
    """The named outcome that stopped a run on the wire, and what it is not.

    One of the four the spec names — timeout, auth failure, malformed reply, rate
    limit — plus the three the contract keeps beside them, each under its own name
    rather than collapsed into one *unreachable*: a timeout is capacity, a rejected
    token is configuration, a malformed body is a contract breach and a rate limit
    is a quota, and one word for all four sends every one of them to the same wrong
    place.
    """

    failure: str
    statement: str


class ReportLocation(BaseModel):
    """Where a finished run's report is served, for a caller that was polling."""

    path: str
    statement: str


class RunProgress(BaseModel):
    """One run in flight, reported per layer.

    There is no figure here that spans the two layers, and that is structural
    rather than editorial: calls spent and findings so far live inside `scored` and
    `adaptive` and nowhere else, so a caller reading this cannot be handed a
    blended number that hides which half of the run is spending their budget
    (ADR-0007). Anything that wanted a total would have to add two fields itself,
    in front of the two labels saying what it was adding.
    """

    run_id: str
    status: str
    statement: str
    scored: ScoredProgress
    adaptive: AdaptiveProgress
    transport: TransportOutcome | None
    """The named transport outcome that stopped this run, or `None`.

    Never a verdict and never a finding: a run that failed on the wire reports
    here, and its findings stay where they were when the endpoint stopped
    answering.
    """

    report: ReportLocation | None
    """Where to fetch the report, once there is one. `None` until the run
    completes."""


def progress_for(record: RunRecord) -> RunProgress:
    """One run as a caller polling it sees it, per layer and with no blend."""
    return RunProgress(
        run_id=record.run_id,
        status=str(record.status),
        statement=record.statement,
        scored=_scored_progress(record),
        adaptive=_adaptive_progress(record),
        transport=_transport(record),
        report=_report(record),
    )


def _scored_progress(record: RunRecord) -> ScoredProgress:
    state = record.run_state
    spent = state.spent_in(Layer.SCORED)
    at = state.position
    if at is None:
        return ScoredProgress(
            reached=False,
            statement=SCORED_NOT_STARTED,
            position=None,
            calls_spent=spent,
            succeeded_attempts=None,
        )
    return ScoredProgress(
        reached=True,
        statement=(
            f"family {at.family}, case {at.case_id}, attempt "
            f"{at.attempt_index + 1}: the position the scored layer has reached"
        ),
        position=ScoredPosition(
            family=str(at.family),
            case_id=at.case_id,
            # One-based on the way out, because a caller reads it as "the third
            # attempt" and the record holds it as an index into the case's ten.
            attempt=at.attempt_index + 1,
        ),
        calls_spent=spent,
        succeeded_attempts=len(state.succeeded_attempts),
    )


def _adaptive_progress(record: RunRecord) -> AdaptiveProgress:
    state = record.run_state
    spent = state.spent_in(Layer.ADAPTIVE)
    at = state.episode_position
    if at is None:
        return AdaptiveProgress(
            reached=False,
            statement=ADAPTIVE_NOT_REACHED,
            position=None,
            calls_spent=spent,
            adaptive_findings=None,
        )
    return AdaptiveProgress(
        reached=True,
        statement=(
            f"family {at.family}, episode {at.index}, turn {at.turn}: the position "
            "the adaptive layer has reached. Nothing in this layer is scored"
        ),
        position=AdaptivePosition(
            family=str(at.family), episode=at.index, turn=at.turn
        ),
        calls_spent=spent,
        adaptive_findings=len(state.broken_episodes),
    )


def _transport(record: RunRecord) -> TransportOutcome | None:
    if record.failure is None:
        return None
    return TransportOutcome(
        failure=str(record.failure),
        statement=f"{record.failure.stated()}. {NOT_A_SECURITY_RESULT}",
    )


def _report(record: RunRecord) -> ReportLocation | None:
    if record.status is not RunStatus.COMPLETED:
        return None
    return ReportLocation(
        path=f"/report/{record.run_id}",
        statement=(
            "the run finished: its report is served here, as the signed payload "
            "with the rendered view alongside it"
        ),
    )


class ApprovalRequest(BaseModel):
    """The answer to one run's interrupt. A yes is the only thing that spends."""

    confirmed: bool
    identity: str
    reason: str = ""


def create_app(config: BenchConfig | None = None) -> FastAPI:
    """The API over one bench, over one library.

    The bench is a constructor argument rather than a module global so that a run
    is estimated against the same library it is attempted against — and so that a
    test can hold both ends of that.
    """
    bench = BenchRuns(config or BenchConfig(cases=admitted_library(CASES_DIR)))
    app = FastAPI(title="AgentAudit", version="0.1.0")
    app.state.bench = bench

    @app.post("/nonces", status_code=status.HTTP_201_CREATED)
    def issue_nonce_for_a_target() -> NonceIssued:
        """Issue the value the operator plants, and say what it is for."""
        return NonceIssued(
            nonce=bench.issue(), echo_probe=ECHO_PROBE, statement=PLANT_STATEMENT
        )

    @app.post("/runs", status_code=status.HTTP_202_ACCEPTED)
    def start_a_run(request: Annotated[StartRunRequest, Body()]) -> RunResponse:
        """Record the attestation, declare the estimate, and halt in front of it.

        Returns once the graph is holding its interrupt, which is before anything
        has been sent to the target: the run id comes back at once because the run
        takes many minutes and no request should be open for them.
        """
        try:
            attestation = request.attestation.attestation()
            target = request.target.config()
            price = request.cost.price()
        except ValueError as refused:
            # The attestation's own refusal, which names the statements that were
            # withheld. Nothing has been created and nothing has been sent.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(refused)
            ) from refused

        try:
            record = bench.start(
                target=target,
                attestation=attestation,
                nonce=request.nonce,
                price=price,
                note_planted=request.note_planted,
            )
        except NonceNotIssued as unregistered:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(unregistered),
            ) from unregistered
        except NeverPresented as unpresented:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(unpresented),
            ) from unpresented
        return response_for(record)

    @app.post("/runs/{run_id}/approval")
    def answer_the_interrupt(
        run_id: Annotated[str, PathParam()],
        request: Annotated[ApprovalRequest, Body()],
    ) -> RunResponse:
        """Answer the halt. On a yes the suite runs; on anything else it does not.

        Returns as soon as the answer is recorded. A confirmed run is *running*
        rather than finished when this responds — the suite is minutes long and
        the caller polls for it.
        """
        try:
            record = bench.answer(
                run_id,
                Approval(
                    confirmed=request.confirmed,
                    identity=request.identity,
                    reason=request.reason,
                ),
            )
        except KeyError as unknown:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run {run_id} was started by this bench",
            ) from unknown
        except NoLongerWaiting as closed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(closed)
            ) from closed
        return response_for(record)

    @app.get("/runs/{run_id}")
    def report_progress(run_id: Annotated[str, PathParam()]) -> RunProgress:
        """Where a run has got to, per layer, while it is still happening.

        Read from the run state the run is filling rather than from a result that
        does not exist until the run is over, which is what `run_calibration`'s
        `run_state` argument is for. An unknown id is a named refusal rather than
        an empty run: a caller polling a run id that this bench never issued has a
        bug to find, and a `200` describing a run with nothing in it would hide it.
        """
        record = bench.record(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no run {run_id} was started by this bench",
            )
        return progress_for(record)

    return app
