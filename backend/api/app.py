"""The HTTP surface: a nonce, a run, and the answer to the run's interrupt.

Three routes and nothing else yet. `POST /nonces` issues the value an operator
plants to prove they control the endpoint; `POST /runs` records the attestation,
declares the estimate and halts; `POST /runs/{id}/approval` answers the halt. The
progress route is #55 and the report route is #56 — both read records this module
already keeps, and neither is written here.

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
    AlreadyAnswered,
    BenchConfig,
    BenchRuns,
    NeverPresented,
    NonceNotIssued,
    RunRecord,
)
from backend.bench.admission import admitted_library
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.registration import ECHO_PROBE, Attestation
from backend.graph.approval import Approval
from backend.graph.budget import CallPrice, Layer

CASES_DIR = Path(__file__).resolve().parents[2] / "backend" / "cases"

PLANT_STATEMENT = (
    "Plant this value in the target's configuration before starting a run. Only "
    "somebody who can edit that configuration can plant it, which is what makes "
    "the echo proof that you control the endpoint (ADR-0007). The same value is "
    "the data-leakage canary — one planted value, two roles — so do not add it to "
    "any output allow-list. The run's registration probe sends the echo probe "
    "below verbatim, and a target that does not answer it with the nonce is not "
    "attempted."
)


class LayerFigureResponse(BaseModel):
    """One layer's figure: how many calls, what kind of number it is, and why."""

    calls: int
    kind: str
    """`exact` or `ceiling`, carried rather than inferred. A reader who cannot
    tell a fact from a bound has been shown one number, not two."""

    basis: str
    cost: str


class EstimateResponse(BaseModel):
    """The consent surface, as `RunBudget.as_payload()` produced it.

    Field for field the record the approval interrupt presented. There is no
    combined figure here that the budget did not build and mark as a bound, and
    no average of any kind: `CallFigure.__add__` makes a fact plus a bound a bound,
    so the total is a ceiling by arithmetic rather than by convention.
    """

    scored: LayerFigureResponse
    adaptive: LayerFigureResponse
    total: LayerFigureResponse
    hard_ceiling: LayerFigureResponse
    scored_ceiling: int
    adaptive_ceiling: int
    currency: str
    presented: list[str]


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
    currency: str = "USD"

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
    estimate: EstimateResponse
    spent: dict[str, int]
    cases: int
    families_not_run: dict[str, str]


def response_for(record: RunRecord) -> RunResponse:
    return RunResponse(
        run_id=record.run_id,
        status=str(record.status),
        statement=record.statement,
        estimate=EstimateResponse.model_validate(record.presented),
        spent={str(layer): record.spent[layer] for layer in Layer},
        cases=len(record.plan.cases),
        families_not_run={
            str(family): gap.stated() for family, gap in record.plan.gaps.items()
        },
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
        except AlreadyAnswered as answered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(answered)
            ) from answered
        return response_for(record)

    return app
