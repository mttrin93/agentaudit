"""The HTTP surface: a nonce, a run, the answer to the run's interrupt, and the
artefact it produced.

Ten routes. `POST /nonces` issues the value an operator plants to prove they
control the endpoint; `POST /runs` records the attestation, declares the estimate
and halts; `POST /runs/{id}/approval` answers the halt; `GET /runs` lists the runs on
the record; `GET /runs/{id}` says where the run has got to; four under `/report/{id}`
— three that serve the files one signed run leaves, the payload, the rendering and
the detached signature, and a fourth that says what a verifier makes of them; and
`GET /bench/gate`, which is about the bench rather than about any run.

**Neither route under `/runs` returns a figure spanning the two layers.** Calls
spent are reported per layer by both — `GET /runs/{id}` for one run in flight,
`GET /runs` for every run on the record — and in both the two figures live inside
`scored` and `adaptive` and nowhere else, so no caller can be handed a blended
number and no list can grow a totals row (ADR-0007, ADR-0010).

**`GET /bench/gate` cites and never starts.** It is the only route here whose
subject is the instrument: the outcome of the gate run this bench was configured to
cite, the date it was decided, the library version it was earned at, and the path
of the document that recorded it. A gate run is 830-odd calls from a terminal that
asks three attestation statements one at a time (PLAN.md §8, `scripts/gate.py`), so
there is no route that begins one and no record type for one — this route reads the
citation the deployment declared and nothing else. The document is **named and
never opened**: a route that parsed the bench's own prose output would break on a
rewording, and the citation already carries every field a reader needs.

**The verification route is a reading and never a fourth file.** It runs the
recipient's own three checks — `verification.checked`, the function
`scripts/verify.py` reaches through, over the same bytes — because a browser cannot
pin a key and an engineer has to learn the artefact is checkable before sending it
to a customer (spec §34). What it may not become is a substitute for the check: it
is computed by the party that produced the document, and it says so in the response
(`report.CHECKED_BY_THE_BENCH_THAT_PRODUCED_IT`).

**The report routes copy bytes and never build them.** What `GET /report/{id}`
returns is the exact byte string that was signed, held on the record since the run
that made it (`report.py`): a route that handed a parsed payload back to the
framework would have it re-serialised on the way out, under whatever that
framework's encoder decides about key order, separators and non-ASCII, and every
signature it served would be over a document the recipient never received. So the
payload is a `Response` over bytes rather than a model, and the assertion that says
so is over bytes rather than over a decoded dict — a test that compared
dictionaries would pass on exactly the document that fails for a recipient (#56).

**Three files under three paths, under the names a verifier already knows.**
`report.json`, `report.md` and `report.sig` are what `scripts/verify.py` reads out
of one directory, so a client that saves the three responses under the filenames
they arrive with can verify the artefact with no further processing — which is the
whole of what *portable* means here. The rendering is served beside the payload
rather than inside it because the digest that binds them is taken over the
document's own bytes: an envelope carrying both would have to re-encode one of
them.

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
rather than a number. **No cost figure is ever read from the environment** — the
confirmation is the liability record, so the figures in it have to be the caller's
own (ADR-0007).

**One value does come from the environment, and the factory will not start without
it.** `AGENTAUDIT_SIGNING_KEY`, read through `signing.signing_key` and by nothing
here, because a deployment that booted without a key would run the whole suite
against somebody's endpoint and then refuse every report it produced as
`never_signed`. The signature is what makes a report portable and portable evidence
is the claim (ADR-0001, ADR-0017), so the absence is a loud failure at startup
rather than a quiet one an operator meets after paying for a run (ADR-0020). It is
the *default* path and not the only one: a caller that hands in a `BenchConfig` has
declared what its bench signs with, including that it signs with nothing.

Served with a factory, because the case library and the signing key are read when
the app is built and an import-time read would make importing this module a
filesystem and environment question::

    uv run uvicorn backend.api.app:create_app --factory
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Body, FastAPI, HTTPException, Response, status
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from backend.api.report import (
    CHECKED_BY_THE_BENCH_THAT_PRODUCED_IT,
    ReportConfig,
    Unsigned,
    verification_of,
)
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
from backend.bench.contract import NOT_A_SECURITY_RESULT, RetryPolicy, TargetConfig
from backend.bench.payload import GateCitation, citation
from backend.bench.registration import ECHO_PROBE, Attestation
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD
from backend.bench.signing import (
    SIGNATURE_FILE,
    NoSigningKey,
    SignedArtefact,
    encoded,
    signing_key,
)
from backend.bench.verification import (
    INTEGRITY_CLAIM,
    RE_DERIVABILITY_CLAIM,
    Verification,
)
from backend.graph.approval import Approval
from backend.graph.budget import BudgetPayload, CallPrice, Layer
from backend.graph.runstate import RunState

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


REPORT_ROUTE = "/report/{run_id}"
"""Where the artefact is served. One definition, formatted by both ends.

The routes are declared from it and `ReportLocation` fills it in, so the path a
completed run advertises cannot drift from the path that serves it.
"""

RENDERING_ROUTE = f"{REPORT_ROUTE}/rendering"
SIGNATURE_ROUTE = f"{REPORT_ROUTE}/signature"
VERIFICATION_ROUTE = f"{REPORT_ROUTE}/verification"
"""The three results over the three files, for a caller that cannot run a script.

Not a fourth file and not part of the artefact: what is downloaded is still three
files, and this route computes nothing that is not recomputable from them. It exists
because the interface has to be able to say *this artefact is checkable* before an
engineer sends it to a customer (spec §34), and a browser cannot pin a key.
"""


def report_paths(run_id: str) -> tuple[str, str, str, str]:
    """The paths one run's artefact is served at, in the order they are read.

    Three files and the verification over them. The three come first because they
    are the artefact: the fourth is a reading of it, and a caller that saved all
    four under the names they arrive with would still verify from the three.
    """
    return (
        REPORT_ROUTE.format(run_id=run_id),
        RENDERING_ROUTE.format(run_id=run_id),
        SIGNATURE_ROUTE.format(run_id=run_id),
        VERIFICATION_ROUTE.format(run_id=run_id),
    )


class ReportRefusal(StrEnum):
    """Why a report is not being served, as a name rather than as a status code.

    Four members and four different facts, kept apart for the reason every other
    outcome in this bench is named. Three of them share a status code and none of
    the three is readable from it, and the difference that matters most is between
    the second and the third: one is a run to ask again about and the other is a run
    that will never have a report, and a caller that could not tell them apart
    would poll for the lifetime of the process.
    """

    NO_SUCH_RUN = "no_such_run"
    IN_FLIGHT = "in_flight"
    DID_NOT_COMPLETE = "did_not_complete"
    NEVER_SIGNED = "never_signed"


class Refusal(BaseModel):
    """A refusal that names itself, beside the sentence that explains it.

    The name is the field a caller branches on and the sentence is the one a person
    reads. A bare string would carry the second and not the first, and a status code
    carries neither.
    """

    outcome: ReportRefusal
    statement: str


def _refused(refusal: ReportRefusal, statement: str) -> dict[str, str]:
    """That refusal as the body of a `detail`, which is plain data by the time it
    reaches FastAPI."""
    return Refusal(outcome=refusal, statement=statement).model_dump(mode="json")


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


SCORED_NO_ATTEMPT_YET = (
    "the scored layer has attempted nothing: no case is in flight and no attempt "
    "has been made. Calls spent here may already be one — the registration probe "
    "is charged to this layer and is the first thing a run sends — and the "
    "attempts that succeeded are absent rather than zero, because a zero would "
    "read as a suite that ran and found nothing"
)

ADAPTIVE_NOT_REACHED = (
    "the run has not reached the adaptive layer: it starts only once the whole "
    "scored suite has finished (ADR-0010), so there is no episode and no turn yet. "
    "Its findings so far are absent rather than zero — a zero would read as an "
    "attacker that ran and found nothing"
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
    """Whether this layer has started, stated rather than left to be inferred.

    It is `position is not None` said out loud, and it is said because the caller
    is a poller: a screen that had to infer *not started* from a null would be one
    null away from drawing a layer that ran and found nothing. It does not follow
    the count below — a layer can have reached an attempt that has not come back —
    which is the case the count is absent for.
    """

    statement: str
    position: ScoredPosition | None
    calls_spent: int
    """Calls this layer has put on the wire. Its own figure, beside the other
    layer's and never added to it.

    A number even before the layer has attempted anything, and that is not the
    zero the ticket forbids: nothing spent is a fact about the wire, checkable
    against the endpoint, where nothing *found* by a layer that never ran is not a
    fact about the target. The registration probe is charged here, so this figure
    is often one while there is still no attempt to report.
    """

    succeeded_attempts: int | None
    """The attempts that succeeded so far, or `None` while none has been recorded.

    Not called findings, on `RunState.succeeded_attempts`' own reasoning: a
    **finding** is a verdict *plus* its narrative, and this is a count of verdicts.

    It is `None` rather than `0` until at least one attempt has produced one,
    because the two are different facts: a count over an empty population is not a
    small number, and the run that most needs the difference is the one killed on
    the wire inside its first attempt — a position in flight beside a zero would
    read as a target that resisted, which is the reading `TargetUnreachable` is
    raised to prevent. A layer with attempts on the record reports the count, zero
    included: nothing has succeeded *yet* is a measurement once something was
    measured.
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
    """The episodes that found a route, or `None` while none has been recorded.

    Absent rather than zero on the same reasoning as the scored layer's count, and
    an episode is recorded when it ends: a first episode still under way has
    broken nothing *yet*, and a zero beside it would read as an attacker that ran
    out of ideas — which is the reading **censored** exists to keep apart
    (ADR-0011).
    """


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
    """Where a finished run's report is served, for a caller that was polling.

    Three paths rather than one, because the artefact is three files and a
    recipient needs all three: `verify.py` reads a payload, a rendering and a
    detached signature out of one directory, so a caller told only where the
    payload is has been handed the part that cannot be checked on its own. A
    completed run says where to go next rather than leaving a poller to guess that
    it is finished with it.
    """

    path: str
    """The signed canonical payload — the bytes that were signed."""

    rendering: str
    """The Markdown the payload's `rendered_sha256` is the digest of."""

    signature: str
    """The detached signature over the payload's bytes."""

    verification: str
    """The three results over those three files, for a caller with no shell.

    Beside the three rather than among them: it is not a file of the artefact and
    it is not what a recipient checks with. A caller that fetched only this one
    would have a reading of a document it never downloaded.
    """

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
        scored=_scored_progress(record.run_state),
        adaptive=_adaptive_progress(record.run_state),
        transport=_transport(record),
        report=_report(record),
    )


def _scored_progress(state: RunState) -> ScoredProgress:
    spent = state.spent_in(Layer.SCORED)
    at = state.position
    if at is None:
        return ScoredProgress(
            reached=False,
            statement=SCORED_NO_ATTEMPT_YET,
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
        # Over the attempts on the record, and absent while there are none: the
        # position may name an attempt that never came back.
        succeeded_attempts=(len(state.succeeded_attempts) if state.attempts else None),
    )


def _adaptive_progress(state: RunState) -> AdaptiveProgress:
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
        adaptive_findings=len(state.broken_episodes) if state.episodes else None,
    )


def _transport(record: RunRecord) -> TransportOutcome | None:
    if record.failure is None:
        return None
    return TransportOutcome(
        failure=str(record.failure),
        statement=f"{record.failure.stated()}. {NOT_A_SECURITY_RESULT}",
    )


def _report(record: RunRecord) -> ReportLocation | None:
    """Where this run's report is, or `None` when there is no report to point at.

    Read off the artefact rather than off the status, because the two can disagree:
    a completed run on a bench with no signing key has finished and has nothing to
    serve, and a location advertised for it would send a caller to three paths that
    all refuse. Why there is none is on the run's own statement, so the absence here
    is a stated one rather than a blank (`runs.py`).
    """
    if record.status is not RunStatus.COMPLETED or isinstance(record.report, Unsigned):
        return None
    payload, rendering, signature, verification = report_paths(record.run_id)
    return ReportLocation(
        path=payload,
        rendering=rendering,
        signature=signature,
        verification=verification,
        statement=(
            "the run finished: its report is served at these three paths, as the "
            "signed payload with the rendered view and the detached signature "
            "alongside it. Saved under the names they arrive with — "
            f"{REPORT_PAYLOAD}, {REPORT_MARKDOWN} and {SIGNATURE_FILE} — the three "
            "are what `scripts/verify.py` reads out of one directory"
        ),
    )


def _no_report_for(record: RunRecord) -> tuple[ReportRefusal, str]:
    """Which of the two *no report* facts this run is, and the sentence for it.

    A run still going is a run to ask about again. A run that stopped without
    completing — declined, unanswered, refused at registration, aborted by its own
    ceiling, or stopped on the wire — will never have a report, and telling its
    caller to poll would be telling them to wait for something that is not coming.
    Both carry the run's own statement, which is where the reason already is.
    """
    if record.status.in_flight:
        return (
            ReportRefusal.IN_FLIGHT,
            f"this run is {record.status} and has not finished: a report is served "
            f"for a completed run only. {record.statement}. Nothing partial is "
            "served in its place — half a report reads as a finished one, and the "
            "figures in it would be over attempts the run has not made",
        )
    return (
        ReportRefusal.DID_NOT_COMPLETE,
        f"this run stopped as {record.status} and produced no report, and it will "
        f"not produce one: a report is made by a run that completed. "
        f"{record.statement}. Nothing is served in its place, and nothing here is a "
        "finding about the target",
    )


def _attachment(filename: str) -> dict[str, str]:
    """Serve this body as the file a verifier expects to find on disk.

    The three fixed names are `verify.py`'s own contract with a recipient — it is
    handed a directory and is told nothing else — so a browser saving these three
    responses lands them under the names that make the directory verifiable.
    """
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


RUNS_ROUTE = "/runs"
"""Where the runs on the record are listed. Rows, and never a summary of them.

Under `/runs` rather than under `/bench` because the subject is a run. `/bench` is
the one prefix whose subject is the instrument (ADR-0018, `BENCH_GATE_ROUTE`), and a
list of somebody's runs is about their targets rather than about this bench. It is
the path `POST /runs` starts a run at, read.

**This route computes no quantity that spans two runs and none that spans two
layers.** There is no count of runs on it, no spend added across rows and no average
of anything: it returns the records as rows, and a caller that wanted a figure over
them would have to build it in front of the rows it built it from (spec: *a list
route returns rows; it does not return a summary of them*).
"""

PER_LAYER_AND_NEVER_ADDED = (
    "one row per run, with calls spent in two figures — the scored layer's and the "
    "adaptive layer's — and no third figure anywhere. The two are enforced against "
    "two separate ceilings, so neither layer can borrow the other's budget and a "
    "blended number would hide which half of a run spent it (ADR-0007, ADR-0010). "
    "There is no total here, no average and no count of these runs."
)
"""What the list is, said on the list, because a screenshot of it travels alone."""

SCORED_SPENT = (
    "calls the scored layer put on the wire for this run, held to the scored "
    "layer's own ceiling. This is the half of the run that produces every number "
    "the bench signs — 18 cases at ten attempts each, plus the registration probe"
)

ADAPTIVE_SPENT = (
    "calls the adaptive layer put on the wire for this run, held to the adaptive "
    "layer's own ceiling. Nothing this layer spent is scored: its unit is an "
    "episode, it has no denominator, and none of it reaches a rate (ADR-0010)"
)

NOTHING_ON_THE_WIRE = (
    "nothing: this layer put no call on the operator's endpoint. A fact about the "
    "wire, checkable against the endpoint, and not a measurement of the target — "
    "the run's standing says why, and a layer that attempted nothing found nothing "
    "rather than finding none"
)
"""Why a zero here is a zero and not the zero CONTEXT.md forbids.

*Not measurable* is a family's outcome against a target that could not answer it,
and it is never a rate of zero. This is not that figure: it is a count of calls,
and a run nobody approved really did put nothing on the wire. What must not appear
beside it is a count of what the layer *found*, and there is no such field on this
row — findings are reported per layer by `GET /runs/{id}`, over a run that ran.
"""


class ScoredSpend(BaseModel):
    """What one run's scored layer put on the wire, and what that figure is.

    A model of its own, and deliberately not one `LayerSpend` shared with the
    adaptive layer. The two figures are two facts about two halves of a run, held
    to two ceilings, and the shared type would be the one thing ADR-0010 asks not
    to exist: a signature that accepts either layer is a signature something can be
    accumulated through. Kept apart, the only way to a total is to write the two
    field names down side by side, in front of the two labels saying what is being
    added.
    """

    calls_spent: int
    statement: str


class AdaptiveSpend(BaseModel):
    """What one run's adaptive layer put on the wire, and what that figure is not.

    Two models rather than one, for the reason `ScoredSpend` gives. This layer's
    calls buy episodes and turns; the other layer's buy attempts. A field a reader
    could add to the scored layer's would be an adaptive quantity entering a scored
    one by arithmetic (ADR-0010), which is the one edge this bench does not have.
    """

    calls_spent: int
    statement: str


class RunRow(BaseModel):
    """One run on the record: what it was against, when, where it got to, what it
    spent in each layer.

    Enough to find a run again and no more. There is no rate here, no band, no
    verdict and no finding — those belong to the report the run produced, which is
    a document with a signature over it, and a figure lifted out of one onto a list
    would be a measurement without its denominator beside it.

    The target is named and its URL is nowhere: a live endpoint that answers
    jailbreak payloads is not a thing to put in a list a screenshot is taken of
    (ADR-0008). The name is the operator's own, which is what they will recognise.
    """

    run_id: str
    """The id the bench issued. What a link back to the run is built from."""

    target: str
    """The operator's own name for the endpoint. Never the endpoint."""

    recorded_at: datetime
    """When the run went on the record — the attestation taken, the estimate
    declared — which is before the target was asked to echo anything.

    Not called a registration time, because registration is the nonce echo and it
    happens on the far side of the interrupt: a declined run and an unanswered run
    never reached one, and those are the runs a list has to be able to show
    (`RunRecord.recorded_at`).
    """

    status: str
    """Where the run got to, in the record's own word. The row's standing."""

    statement: str
    """The record's own sentence for that standing, carried unedited."""

    scored: ScoredSpend
    adaptive: AdaptiveSpend
    """The two spends, as two named fields and never a list of layers.

    A list is a thing a caller reduces. Two names are two facts, and the row has
    nowhere to put a third.
    """


class RunList(BaseModel):
    """The runs on the record, most recently recorded first, and nothing over them.

    No count field and no totals block. A count of runs would be the first figure
    on a screen whose whole subject is that figures belong to the thing that
    measured them, and the rows are countable by whoever needs to count them.
    """

    runs: list[RunRow]
    statement: str


def _scored_spend(record: RunRecord) -> ScoredSpend:
    spent = record.run_state.spent_in(Layer.SCORED)
    return ScoredSpend(
        calls_spent=spent,
        statement=SCORED_SPENT if spent else NOTHING_ON_THE_WIRE,
    )


def _adaptive_spend(record: RunRecord) -> AdaptiveSpend:
    spent = record.run_state.spent_in(Layer.ADAPTIVE)
    return AdaptiveSpend(
        calls_spent=spent,
        statement=ADAPTIVE_SPENT if spent else NOTHING_ON_THE_WIRE,
    )


def run_row(record: RunRecord) -> RunRow:
    """One run as a list of runs shows it. Read off the record, computed nowhere.

    The two spends come from the same counters `GET /runs/{id}` reports and are read
    one layer at a time — `spent_in(Layer.SCORED)` and `spent_in(Layer.ADAPTIVE)`,
    never `RunState.calls_spent`, which is the blended reporting figure and is not
    what either ceiling is enforced against.
    """
    return RunRow(
        run_id=record.run_id,
        target=record.target.name,
        recorded_at=record.recorded_at,
        status=str(record.status),
        statement=record.statement,
        scored=_scored_spend(record),
        adaptive=_adaptive_spend(record),
    )


def runs_response(records: Sequence[RunRecord]) -> RunList:
    """The rows for those records, in the order they were handed over."""
    return RunList(
        runs=[run_row(record) for record in records],
        statement=PER_LAYER_AND_NEVER_ADDED,
    )


class CheckResult(BaseModel):
    """One of the three results: what it found, under its own name, and the words.

    `outcome` is the name a caller branches on — four for the signature, four for
    the binding, three for the arithmetic — and `statement` is the verifier's own
    sentence, carried unedited. A boolean would carry neither: *unsigned* and
    *signed by a key you did not pin* are different facts about the sender, and a
    screen that showed one cross for both would send its reader looking for the
    wrong thing.
    """

    outcome: str
    statement: str


class ReportVerification(BaseModel):
    """The three results over one run's artefact, and the two claims scoping them.

    All three, always, in the order `verification.CHECKS` names them. A response
    that carried only the signature would let its reader infer re-derivability from
    integrity, which is the inference ADR-0017 exists to prevent — so the two claims
    travel with the results here exactly as they do in the verifier's own output,
    and `re_derivability` is stated for the scored layer alone.

    There is no field here that summarises the three into one word for a badge.
    `verified` and `contradicted` are the verifier's own two properties and they are
    not the same question: nothing contradicted with one result never established is
    a third answer, and collapsing it would report a claim the run never made.
    """

    artefact: str
    artefact_version: int
    target: str
    signature: CheckResult
    binding: CheckResult
    arithmetic: CheckResult
    verified: bool
    """Whether all three held. Never shown on its own — see `checked_by`."""

    contradicted: bool
    """Whether any result actively failed, as against not having been established."""

    integrity: str
    """The claim for the whole document, printed beside the second and never alone."""

    re_derivability: str
    """The claim for the scored layer only. The adaptive layer is recorded and not
    reproducible, and a valid signature over it is a claim about its bytes
    (ADR-0010, ADR-0017)."""

    checked_by: str
    """Whose check this is: the bench that produced the artefact, not a recipient."""


def verification_response(verification: Verification) -> ReportVerification:
    """The verifier's own record as the wire carries it. Nothing computed here."""
    return ReportVerification(
        artefact=verification.artefact,
        artefact_version=verification.artefact_version,
        target=verification.target,
        signature=CheckResult(
            outcome=str(verification.signature.outcome),
            statement=verification.signature.stated(),
        ),
        binding=CheckResult(
            outcome=str(verification.binding.outcome),
            statement=verification.binding.stated(),
        ),
        arithmetic=CheckResult(
            outcome=str(verification.arithmetic.outcome),
            statement=verification.arithmetic.stated(),
        ),
        verified=verification.verified,
        contradicted=verification.contradicted,
        integrity=INTEGRITY_CLAIM,
        re_derivability=RE_DERIVABILITY_CLAIM,
        checked_by=CHECKED_BY_THE_BENCH_THAT_PRODUCED_IT,
    )


BENCH_GATE_ROUTE = "/bench/gate"
"""Where the bench's own gate citation is read. About the instrument, not a run.

Under `/bench` rather than under `/runs` because the subject is different, and the
subject is the whole of ADR-0018: a run has rates, intervals and bands, and the
bench passes its own gate. Nothing about a target is reachable from here and
nothing here is reachable from a target's report.
"""


class CitedLibrary(BaseModel):
    """The library version a gate run was decided at: a count and a digest.

    Both, because a citation saying only *eighteen cases* cannot tell a reader
    whether the eighteen are the same eighteen (`library.LibraryVersion`), and the
    digest is what makes "has the bench changed since?" a question with an answer.
    """

    cases: int
    digest: str


class CitedGate(BaseModel):
    """A bench citing a gate run: its outcome, its date, its version, its document.

    The outcome is one of three and this model is not only the passing one: a bench
    whose gate failed or was not decided cites it here in the same shape, because the
    citation is what the bench last put itself through rather than a badge it earned.

    `cited` is the field a caller branches on and it is a literal, so this shape and
    the one below are two facts rather than one record with empty fields. There is
    no field here for a per-family figure: the reference agents' rates and the
    per-family `D` live only in the document, and a route that read them out of it
    would be parsing the bench's own prose (spec §75, "Per-family gate figures are
    out").
    """

    cited: Literal[True] = True
    outcome: str
    """`passed`, `failed` or `not_decided` — three answers, because *not decided*
    is not a polite fail (`scorer.GateOutcome`)."""

    decided_on: str
    """The date the run was decided, as the citation holds it: ISO, no locale."""

    library: CitedLibrary
    document: str
    """Where the run is written down, so the citation is checkable. A path the
    caller may link and this route never opens."""

    stated: str
    """The citation in the bench's own words, whose subject is the bench."""


class UncitedGate(BaseModel):
    """A bench citing no gate run, saying so where a citation would have been.

    A stated absence and not a blank, and not a failed gate either: this bench was
    configured without a citation, which is a fact about the bench and is exactly as
    much as this route knows. There is no `outcome` field to be empty, so nothing
    here can be read as *did not pass*.
    """

    cited: Literal[False] = False
    stated: str


def gate_response(cited: GateCitation | None) -> CitedGate | UncitedGate:
    """The citation this bench carries into a report, served as it is carried.

    Built through `payload.citation` — the same serialiser that writes the block
    into the signed provenance — and then validated into one of the two models, so
    the wire shape is the artefact's own and the schema is still declared. A second
    mapping written here would be a second definition of the citation, and the two
    would only have to disagree once for a screen to state a gate result no
    artefact carries (ADR-0018).
    """
    body = citation(cited)
    if cited is None:
        return UncitedGate.model_validate(body)
    return CitedGate.model_validate(body)


class ApprovalRequest(BaseModel):
    """The answer to one run's interrupt. A yes is the only thing that spends."""

    confirmed: bool
    identity: str
    reason: str = ""


NO_KEY_NO_BOOT = (
    "This factory does not start without a key it can sign with. A bench that cannot "
    "sign attempts the whole library against the operator's endpoint and then refuses "
    "every report it "
    f"produced as {ReportRefusal.NEVER_SIGNED} (`report.py`) — an instrument that "
    "measures and cannot testify. The signature is what makes a report portable, and "
    "portable evidence a recipient can check is the claim this project is making "
    "(ADR-0001, ADR-0017), so a missing key fails here rather than after somebody "
    "has paid for a run (ADR-0020). Hand in a `BenchConfig` instead to say "
    "deliberately that this bench does not sign."
)
"""Why an unusable key is fatal at startup, appended to the refusal that names it.

`signing.signing_key` already says which of its three refusals this is — absent,
not base64, not an Ed25519 key — and how to make a good one. What it cannot say is
what *this* caller was about to do with it, which is the half that makes the
absence fatal rather than a degraded mode. So this sentence is about the
consequence and never about the cause, and it is appended to all three.
"""


def deployed_bench() -> BenchConfig:
    """What a bench is when the deployment declared nothing: the admitted library,
    and the signing key from the environment, or no bench at all.

    The key is fetched through `signing.signing_key`, which stays the only line in
    this repository that reads `AGENTAUDIT_SIGNING_KEY`; the refusal it raises is
    re-raised with what booting anyway would have cost, and its type is unchanged so
    that a deployment catching `NoSigningKey` still catches this one.
    """
    try:
        key = signing_key()
    except NoSigningKey as missing:
        raise NoSigningKey(f"{missing}. {NO_KEY_NO_BOOT}") from missing
    return BenchConfig(
        cases=admitted_library(CASES_DIR), report=ReportConfig(signing_key=key)
    )


def create_app(config: BenchConfig | None = None) -> FastAPI:
    """The API over one bench, over one library.

    The bench is a constructor argument rather than a module global so that a run
    is estimated against the same library it is attempted against — and so that a
    test can hold both ends of that. Given none, the bench is the deployed one,
    which reads a signing key and refuses to exist without it.
    """
    bench = BenchRuns(config if config is not None else deployed_bench())
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

    @app.get(RUNS_ROUTE)
    def list_the_runs_on_the_record() -> RunList:
        """Every run this bench has started, with calls spent per layer.

        A read, and the answer to *which of these did I start and what did it cost
        me* for an operator who did not keep the URL. It starts nothing: the only
        route on this bench that can cause a call on a target is the one that
        answers an interrupt with a yes.

        **Two figures per row and no third one anywhere.** The scored layer's spend
        and the adaptive layer's spend, each against its own ceiling, and nothing
        here adds them, averages them, or adds either across the rows — a run list
        is the surface most likely to grow a totals row, and the response has no
        field for one to live in (`RunList`).
        """
        return runs_response(bench.records())

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

    def servable(run_id: str) -> SignedArtefact:
        """This run's signed artefact, or the named reason there is none to serve.

        Four refusals and four different facts, and the caller is told which: a run
        id this bench never issued, a run still in flight, a run that stopped
        without completing, and a run that finished without a signed report. A
        single *no report* would send a poller into a loop over three runs, two of
        which are never going to have one.
        """
        record = bench.record(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_refused(
                    ReportRefusal.NO_SUCH_RUN,
                    f"no run {run_id} was started by this bench",
                ),
            )
        if record.status is not RunStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_refused(*_no_report_for(record)),
            )
        if isinstance(record.report, Unsigned):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_refused(ReportRefusal.NEVER_SIGNED, record.report.reason),
            )
        return record.report

    @app.get(REPORT_ROUTE)
    def serve_the_signed_payload(run_id: Annotated[str, PathParam()]) -> Response:
        """The canonical payload, as the exact bytes that were signed.

        A `Response` over bytes and never a model: the signature is over one byte
        string, and a payload handed back to the framework would be re-encoded on
        the way out — same document, different bytes, and no signature this route
        ever served would verify. Nothing is added here and nothing is summarised;
        what is in the body is what `payload.py` built and `signing.py` covered.
        """
        return Response(
            content=servable(run_id).canonical,
            media_type="application/json",
            headers=_attachment(REPORT_PAYLOAD),
        )

    @app.get(RENDERING_ROUTE)
    def serve_the_rendering(run_id: Annotated[str, PathParam()]) -> Response:
        """The Markdown a human reads, still hashing to the digest in the payload.

        Served beside the payload rather than inside it: `rendered_sha256` is taken
        over these bytes, so a document delivered inside a JSON envelope would have
        to be re-encoded to get there and would arrive no longer matching the field
        that binds it (ADR-0017).
        """
        return Response(
            content=servable(run_id).rendering.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers=_attachment(REPORT_MARKDOWN),
        )

    @app.get(SIGNATURE_ROUTE)
    def serve_the_signature(run_id: Annotated[str, PathParam()]) -> Response:
        """The detached signature, in the hex form the file on disk holds.

        Detached and naming no key: which key signed a report is stated once, in
        the payload where the signature covers it, so a signature file that carried
        its own key id would be re-attributable by editing the file beside it
        (`signing.py`).
        """
        return Response(
            content=encoded(servable(run_id).signature).encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers=_attachment(SIGNATURE_FILE),
        )

    @app.get(VERIFICATION_ROUTE)
    def verify_the_artefact_this_run_produced(
        run_id: Annotated[str, PathParam()],
    ) -> ReportVerification:
        """What a verifier makes of the three files above. Three results, always.

        Run over the bytes this bench serves, through the same function
        `scripts/verify.py` reaches — a second implementation would be a second
        definition of *verifying*, and the two would only have to disagree once for
        a caller to be shown a property nobody checked.

        **This is not the recipient's check and the response says so.** It is
        computed by the party that produced the document, against the public key
        this bench was told to pin, and the answer it is worth acting on is a
        signature that does *not* verify: a report an engineer cannot send is one
        they find out about here rather than after a customer runs the script.
        """
        return verification_response(
            verification_of(servable(run_id), bench.config.report)
        )

    @app.get(BENCH_GATE_ROUTE)
    def cite_the_gate_run_this_bench_last_passed() -> CitedGate | UncitedGate:
        """The gate run this bench cites, or the stated absence of one.

        A read of the citation the deployment declared (`ReportConfig.gate`), which
        is the same value the provenance block of every report this bench signs
        carries. One source of truth: the citation is not assembled here, not read
        off the filesystem, and not parsed out of the document it names.

        **There is no route that starts a gate run and this is not it.** A gate run
        attacks all three reference agents under a terminal consent flow and writes
        back to the case library, and the console cites it rather than offering it
        (PLAN.md §8). What an operator gets here is a fact about the instrument;
        what they do not get anywhere is a button.
        """
        return gate_response(bench.config.report.gate)

    return app
