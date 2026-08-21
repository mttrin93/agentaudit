"""The HTTP surface: a nonce, a run, the answer to the run's interrupt, and the
artefact it produced.

Sixteen routes, in three families. `POST /nonces` issues the value an operator
plants to prove they control the endpoint; `POST /runs` records the attestation,
declares the estimate and halts; `POST /runs/{id}/approval` answers the halt; `GET
/runs` lists the runs on the record; `GET /runs/{id}` says where the run has got to;
four under `/report/{id}` — three that serve the files one signed run leaves, the
payload, the rendering and the detached signature, and a fourth that says what a
verifier makes of them; `GET /artefacts` lists every signed artefact with that same
reading beside it; two under `/bench`, whose subject is the bench rather than any run
— `GET /bench/gate` and `GET /bench/settings`; and four under `/gate-runs`, which are
the newest and the only ones on this surface that spend money on the bench's own
behalf.

**Neither route under `/runs` returns a figure spanning the two layers.** Calls
spent are reported per layer by both — `GET /runs/{id}` for one run in flight,
`GET /runs` for every run on the record — and in both the two figures live inside
`scored` and `adaptive` and nowhere else, so no caller can be handed a blended
number and no list can grow a totals row (ADR-0007, ADR-0010).

**`GET /bench/gate` cites and never starts.** The declared rule the gate is decided
under, and then the outcome of the gate run this bench was configured to cite, the
date it was decided, the library version it was earned at, and the path of the
document that recorded it. The rule is above the outcome on the wire as it is on the
screen, because a pass with no bar beside it is a verdict to be trusted rather than
an answer to be re-derived (ADR-0003). This route reads the rule the bench declares
and the citation the deployment declared, and nothing else; the document it names is
**named and never opened**, because a route that parsed the bench's own prose output
would break on a rewording. Starting a gate run is not here and never was: `/bench`
is read-only in every method, and what begins one is the family below.

**`/gate-runs` starts one, and a gate run is not a run.** Four routes — `POST
/gate-runs` records the three attestation statements and declares the estimate per
layer, `POST /gate-runs/{id}/approval` answers the halt, `GET /gate-runs` lists them
and says whether another may start, `GET /gate-runs/{id}` reports progress per layer
and then the decision under the rule. PLAN.md §8 put this on the command line and
[ADR-0021](../../docs/adr/0021-the-console-may-start-a-gate-run.md) reverses that,
which is a decision of record changed rather than a route added: read the ADR for what
it gives up. What the reversal does not touch is either control — the attestation is
the record `registration.py` refuses to construct incomplete, and the halt is the
same `PendingApproval` seam `POST /runs` answers — and **there is no flag, setting or
environment variable on this surface that lets a gate run proceed without both**.

A gate run is its own record and its own family for the reason a target report has no
gate-decision field: a run produces rates about somebody's agent, a gate run produces
a decision about this bench, and nothing here takes either (ADR-0018, ADR-0010).
`GateRunRecord` and `RunRecord` never appear in one signature; no route under `/runs`
takes a gate run id and no route under `/gate-runs` takes a run id. What *is* shared
is the consent mechanism, deliberately: one `Attestation`, one interrupt seam, one
`ApprovalRequest`, because a second copy of a consent flow is a second place for it
to be weakened. The per-family figures the decision carries — the three reference
agents' rates and each family's `D` — are read off the `GateResult` the run left in
memory and never out of a document.

**`GET /bench/settings` states and never changes.** The second route under
`/bench`, and a reader in the strong sense: the two key fingerprints — the key an
artefact will be signed by and the key a verification is run against, which are two
facts and not one — the live library's version with the retired count kept beside
it, the four model settings as four rows, and each layer's ceiling as its own record
in its own units. There is no field on it that adds the two layers, no fifth field
combining two model settings, and nothing derived from a private key: rotation stays
in the environment and configuration stays on the command line, because the factory
reads its key from one place and refuses to boot without it (ADR-0020).

**`GET /artefacts` is the same reading, once per artefact, and never a mark.** An
engineer choosing which run to send a customer needs to learn the artefact is
checkable before the recipient tells them it is not, so every row carries all three
results by name, both claims stated apart, and the three files under the fixed names
a verifier reads out of a directory. It is a list of rows: no count of artefacts, no
figure over them, and no field on a row that reduces its three results to one word
(ADR-0017).

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

from backend.api.gate_runs import DEPLOYED_LIBRARY as DEPLOYED_LIBRARY_MOUNT
from backend.api.gate_runs import (
    BenchGateRuns,
    CannotRunAGate,
    GateRunBench,
    GateRunRecord,
    seeded_library,
    shipped_agents,
)
from backend.api.gate_runs import NoLongerWaiting as GateRunNoLongerWaiting
from backend.api.report import (
    CHECKED_BY_THE_BENCH_THAT_PRODUCED_IT,
    UNDECLARED_MODEL,
    VERIFY_COMMAND,
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
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adjudication import Completion
from backend.bench.admission import admitted_library
from backend.bench.cited import the_citation
from backend.bench.completion import (
    ADJUDICATOR_MODEL_ENV,
    REFERENCE_MODEL_ENV,
    completion_for,
    declared_model,
)
from backend.bench.contract import NOT_A_SECURITY_RESULT, RetryPolicy, TargetConfig
from backend.bench.gate_record import (
    CitedLibrary,
    DeclaredRule,
    GateDecided,
    RecordedGateRun,
    declared_rule,
    gate_decided,
)
from backend.bench.library import Case, CaseStatus, Family, LibraryVersion
from backend.bench.payload import DeclaredModels, GateCitation, citation
from backend.bench.registration import ECHO_PROBE, Attestation
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD
from backend.bench.retirement import retired_cases
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.signing import (
    SIGNATURE_FILE,
    SIGNING_KEY_VARIABLE,
    NoSigningKey,
    SignedArtefact,
    encoded,
    fingerprint,
    public_key,
    signing_key,
)
from backend.bench.verification import (
    INTEGRITY_CLAIM,
    RE_DERIVABILITY_CLAIM,
    SignatureOutcome,
    Verification,
)
from backend.graph.approval import Approval
from backend.graph.budget import (
    REGISTRATION_PROBES_PER_TARGET,
    BudgetPayload,
    CallPrice,
    Layer,
)
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


def _cannot(refused: CannotRunAGate) -> dict[str, str]:
    """Why a gate run may not start, as a name beside the sentence that explains it.

    The same division `_refused` makes and for the same reason: the name is the field
    a caller branches on and the sentence is the one a person reads. Four names, and
    two of them are permanent facts about the deployment while two are about right
    now — a status code carries neither difference.
    """
    return {"outcome": str(refused.refusal), "statement": str(refused)}


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
    "The run has not reached the adaptive layer: it starts only once the whole "
    "scored suite has finished."
)
"""What a run says of an adaptive layer it has not started.

One clause. The ADR that puts the layer second, and the sentence about findings
absent rather than zero, came off the wording; the absence itself is not carried by
prose and never was — `adaptive_findings` is `null` in exactly this state, which is
what `test_api_runs.py` asserts beside this.
"""


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


ARTEFACTS_ROUTE = "/artefacts"
"""Where every signed artefact this bench has produced is listed, with its reading.

Under its own prefix rather than under `/report`, because the subject is different:
`/report/{run_id}` is one artefact's three files, and this is the answer to *which of
these can I send*. An engineer with several runs behind them has one question here —
is this one still checkable — and they need it answered before a recipient answers it
for them.

**The three results travel with every row, all three of them.** A list carrying one
result per artefact would let its reader infer the strongest claim from the weakest,
which is the inference ADR-0017 exists to prevent, so each row carries the whole
reading the per-run verification route serves: three outcomes by name, the two claims
stated apart, and whose check it is. There is no field on a row that reduces them to
a mark, and no field on the list that reduces the rows to a figure.

**This route computes no quantity and aggregates nothing.** It reads the artefacts
already on the record and runs the recipient's own three checks over their bytes —
`verification.checked`, the same function `scripts/verify.py` reaches through. There
is no count of artefacts on it, nothing added across rows, and no rate, band or
verdict about any target: those belong to the artefact, printed beside the
denominator they were computed over (spec: *a list route returns rows; it does not
return a summary of them*).
"""

THREE_FILES_AND_THREE_RESULTS = (
    "one row per signed artefact, each with all three verification results named "
    "individually and the two claims stated separately — integrity over the whole "
    "document, re-derivability of the scored layer alone (ADR-0010, ADR-0017). The "
    "three files are offered under the fixed names a verifier reads out of one "
    f"directory: {REPORT_PAYLOAD}, {REPORT_MARKDOWN} and {SIGNATURE_FILE}. There is "
    "no mark here that combines the three results, no figure over these artefacts, "
    "and no rate, band or verdict about any target. A completed run that produced no "
    f"signed artefact is not an artefact and is not listed: it is a "
    f"{ReportRefusal.NEVER_SIGNED} on its own report route, and it is on the list of "
    "runs with the record's own sentence for why"
)
"""What the list is, said on the list, because a screenshot of it travels alone."""

PAYLOAD_HOLDS = (
    "the canonical JSON payload — the exact bytes the signature covers, and the "
    "artefact itself"
)

RENDERING_HOLDS = (
    "the document a human reads, bound to those bytes by the digest inside them. A "
    "rendering with no payload beside it verifies nothing"
)

SIGNATURE_HOLDS = (
    "the detached signature over the payload's bytes, naming no key: which key "
    "signed a report is stated inside the payload, where the signature covers it"
)


class ArtefactFile(BaseModel):
    """One of the three files, under the name a verifier already reads it by.

    The filename is not decoration and it is not derived from a run id: `verify.py`
    is handed a directory and told nothing else, so a client that saves these three
    responses under the names they arrive with has a directory that verifies. A file
    served under a name of this route's invention would be portable evidence a
    recipient's tooling cannot find.
    """

    filename: str
    """`report.json`, `report.md` or `report.sig` — the verifier's own contract."""

    path: str
    """Where this bench serves it. The route that already serves it, formatted."""

    holds: str
    """What is in it, so the three are not read as three copies of one thing."""


class ArtefactRow(BaseModel):
    """One signed artefact on the record: what it is of, its files, its reading.

    A row and never a summary of one. There is no field here that marks the three
    results as good or bad, no band, no rate and no verdict — an artefact is a
    document about a target, and a figure lifted out of one onto a list would arrive
    without the denominator that was printed beside it (ADR-0005, ADR-0018).

    The target is named and its URL is nowhere (ADR-0008), and the name is the
    operator's own, which is what they will recognise when they are looking for the
    one to send.
    """

    run_id: str
    """The run that produced it. What a link back to the run is built from."""

    target: str
    """The operator's own name for the endpoint. Never the endpoint."""

    recorded_at: datetime
    """When the run that produced this artefact went on the record."""

    files: list[ArtefactFile]
    """The three files, in the order a verifier reads them.

    Three and never two: a payload with no signature beside it is the part that
    cannot be checked on its own, and a reading of a document a recipient never
    downloaded is not evidence of anything. The verification route is not among
    them — it is a reading of the artefact rather than a file of it, and the reading
    it produces is on this row already.
    """

    verification: ReportVerification
    """The three results over those three files, and the two claims scoping them.

    The same model the per-run verification route serves, built by the same
    function over the same bytes. Not a summary of it and not a subset: a row
    showing one result would be a reader inferring the other two.
    """


class ArtefactList(BaseModel):
    """Every signed artefact on the record, and nothing computed over them.

    No count field and no totals block, for the reason `RunList` has neither. What
    is here beside the rows is the command a recipient runs, which is the same
    command for every artefact because the verifier is handed a directory.
    """

    artefacts: list[ArtefactRow]
    statement: str
    verify_command: str
    """What a recipient runs over the three files, in the form they paste.

    On the list rather than on each row, because it takes a directory and not a run
    id: it is one command whatever artefact was saved into that directory, and a
    per-row copy would be the same line printed once per run.
    """


def _files(run_id: str) -> list[ArtefactFile]:
    """The three files of one artefact, at the paths that already serve them.

    Built from `report_paths`, so the paths on this list cannot drift from the
    routes that answer them, and named from the constants `verify.py` reads — a
    filename written out here would be a second definition of what a recipient's
    tooling looks for.
    """
    payload, rendering, signature, _ = report_paths(run_id)
    return [
        ArtefactFile(filename=REPORT_PAYLOAD, path=payload, holds=PAYLOAD_HOLDS),
        ArtefactFile(filename=REPORT_MARKDOWN, path=rendering, holds=RENDERING_HOLDS),
        ArtefactFile(filename=SIGNATURE_FILE, path=signature, holds=SIGNATURE_HOLDS),
    ]


def artefact_row(
    record: RunRecord, artefact: SignedArtefact, config: ReportConfig
) -> ArtefactRow:
    """One signed artefact as a list of them shows it.

    The artefact is passed in rather than read off the record here, so that this
    function cannot be called for a run that has none: a row for an unsigned run
    would have to invent a reading of a document that does not exist.
    """
    return ArtefactRow(
        run_id=record.run_id,
        target=record.target.name,
        recorded_at=record.recorded_at,
        files=_files(record.run_id),
        verification=verification_response(verification_of(artefact, config)),
    )


def artefacts_response(
    records: Sequence[RunRecord], config: ReportConfig
) -> ArtefactList:
    """The rows for the records that produced an artefact, in the order given.

    A run with no signed artefact is skipped rather than listed with an empty
    reading: *unsigned* is a fact about a run and it is stated on the run, by name,
    where a caller polling for a report already reads it (`ReportRefusal`). A row
    here with nothing in it would be a document a reader could go looking for.
    """
    return ArtefactList(
        artefacts=[
            artefact_row(record, record.report, config)
            for record in records
            if isinstance(record.report, SignedArtefact)
        ],
        statement=THREE_FILES_AND_THREE_RESULTS,
        verify_command=VERIFY_COMMAND,
    )


BENCH_GATE_ROUTE = "/bench/gate"
"""Where the bench's own gate citation is read. About the instrument, not a run.

Under `/bench` rather than under `/runs` because the subject is different, and the
subject is the whole of ADR-0018: a run has rates, intervals and bands, and the
bench passes its own gate. Nothing about a target is reachable from here and
nothing here is reachable from a target's report.
"""


class CitedGate(BaseModel):
    """A bench citing a gate run: its outcome, its date, its version, its two files.

    The outcome is one of three and this model is not only the passing one: a bench
    whose gate failed or was not decided cites it here in the same shape, because the
    citation is what the bench last put itself through rather than a badge it earned.

    `cited` is the field a caller branches on and it is a literal, so this shape and
    the one below are two facts rather than one record with empty fields. There is
    still no field here for a per-family figure — the reference agents' rates and the
    per-family `D` are in the **gate run record**, and a route that recovered them by
    parsing the bench's own prose would break on a rewording (spec §75, "Per-family
    gate figures are out"). What ADR-0023 added is `record`, which is that record's
    name: an address, so those figures are reachable, and still not a figure on this
    response.
    """

    cited: Literal[True] = True
    outcome: str
    """`passed`, `failed` or `not_decided` — three answers, because *not decided*
    is not a polite fail (`scorer.GateOutcome`)."""

    decided_on: str
    """The date the run was decided, as the citation holds it: ISO, no locale."""

    library: CitedLibrary
    document: str | None
    """Where the run is written down in prose, or `null` where it is written nowhere.

    A path the caller may link and this route never opens. `null` is a gate run
    started from the console, which leaves the record below and no dated document
    (ADR-0021, ADR-0023) — a third fact rather than an empty field, so a caller never
    renders a paragraph where it expected a file name."""

    record: str
    """Where the same gate run is written down as fields, for the figures this
    response does not carry.

    The **gate run record**'s own file name (`gate_record.RecordedGateRun.record`),
    so a reader of this response reaches each reference agent's rate and each
    family's `D` without parsing the bench's own prose — the parse #75 refused to
    write and ADR-0023 replaced with a pointer. Named here and opened by nothing:
    this route still serves no per-family figure of its own."""

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


class BenchGate(BaseModel):
    """The bench's own certification: the rule it is held to, then what it answered.

    Two fields and their order is the point. `rule` is declared configuration and is
    a fact about the bench whether or not any gate run was ever made; `citation` is
    what the last one answered, and it is one of two shapes. So the rule is not a
    field *of* the citation — an uncited bench still has a rule, and a bench that
    fails its gate is held to the same one — and it is the first thing on the wire
    for the same reason it is the first thing on the screen.

    **The citation stays byte-identical to the provenance block.** It is nested here
    rather than flattened beside the rule so that `CitedGate` and `UncitedGate` keep
    mirroring `payload.citation` exactly, field for field: one serialiser, two
    carriers, and no field added on the way to a screen that an artefact does not
    carry (ADR-0018).
    """

    rule: DeclaredRule
    citation: CitedGate | UncitedGate


def bench_gate(cited: GateCitation | None, rule: GateRule = DECLARED_RULE) -> BenchGate:
    """The rule this bench is held to, and the gate run it cites under it."""
    return BenchGate(rule=declared_rule(rule), citation=gate_response(cited))


BENCH_GATE_RECORD_ROUTE = "/bench/gate/record"
"""The gate run record the citation names, read out of the library it was written to.

Under `/bench/gate` because it is the same subject one level down: the citation says
*what* the last gate run answered, and this says *what it measured to answer it* —
each reference agent's rate on each family, and each family's `D`. Nothing about
anybody's target is reachable from here (ADR-0018).

**This is the read the citation route deliberately does not do.** `GET /bench/gate`
names the record and opens nothing (ADR-0023), and it still does not: the citation
stays byte-identical to the provenance block of every signed report, with no
per-family figure added on the way to a screen. Reaching those figures is a second
request against a second path, which is what keeps the two facts — *what it
answered* and *what it measured* — separable by a caller who wants only the first.

**It opens the record and never the document.** The record is the machine-readable
rendering of one gate run; the dated Markdown beside it is prose for a person, and a
figure recovered from prose would break on a rewording (#75, #84, ADR-0023). This
route has no reader for a `.md` at all.

**It reads the filesystem on request, and that is the difference from every other
reader under `/bench`.** The record is a file, written by the gate run that earned
the citation, and this bench does not hold it in memory: a console gate run from
before a restart is exactly the case this route exists for. So the read happens per
request, and every way it can fail is one shape — *this bench does not hold that
record* — rather than an error, because a bench that cannot open a file it was
mounted without has not thereby failed a gate.

**Only inside the library.** The file name comes off the citation, which is a
document on disk, so it is taken as a bare name and the resolved path is required to
sit in the library directory. A citation naming `../` is a citation this route
refuses rather than follows.
"""


class HeldRecord(BaseModel):
    """The gate run record this bench holds, whole, as the run wrote it.

    The rule above the decision, because that is the order the record itself is in
    and the order every other carrier of a gate result is in: an outcome read with no
    bar beside it is a verdict somebody trusted (ADR-0003).

    Served as `RecordedGateRun` rather than re-mapped field by field, so the response
    and the file are one schema. A second shape here would be a second definition of
    a gate run, and the two would only have to disagree once for a screen to state a
    gate result no record carries.
    """

    held: Literal[True] = True
    run: RecordedGateRun
    stated: str


class UnheldRecord(BaseModel):
    """No record here, and which of the several nothings it is.

    Four ways to hold no record and one shape for all of them, with the reason in
    words: this bench runs no gate and has no library to hold one; it cites no gate
    run at all; it cites one whose record was written beside its document somewhere
    this bench was not given; or the file is there and could not be read as a record.

    **Not a failed gate, and not an absent one.** There is no `outcome` field here to
    be empty and no figure to be zero. What the last gate run answered is on
    `GET /bench/gate` and is unaffected by anything this route could not open.
    """

    held: Literal[False] = False
    record: str | None
    """The file name the citation gave, where it gave one. An address and not a
    promise: naming it is how a reader learns which file this bench went looking
    for."""

    stated: str


NO_LIBRARY_TO_HOLD_A_RECORD = (
    "this bench holds no case library, so there is no directory a gate run record "
    "could have been written to. It is a deployment that runs no gate rather than a "
    "bench whose gate went badly"
)

CITES_NO_GATE_RUN = (
    "this bench cites no gate run, so there is no record to open. A bench with no "
    "citation has not failed its gate: it has not been put through one that it "
    "carries"
)

WRITTEN_BESIDE_ITS_DOCUMENT = (
    "the citation names a record this bench does not hold. A gate run at a terminal "
    "writes its record into the directory that run was given, beside the dated "
    "document, and a bench mounted with the library alone never sees it. The figures "
    "exist and this deployment is not where they are"
)

NOT_READABLE_AS_A_RECORD = (
    "the file the citation names is there and could not be read as a gate run "
    "record. A partial answer assembled out of whichever fields parsed is how a "
    "bench would come to print figures nothing measured, so nothing here is served "
    "from it"
)

THE_FIGURES_THE_CITATION_POINTS_AT = (
    "every figure here was read off the record the gate run itself wrote, in the "
    "process that made the attempts. Nothing was parsed out of the dated document "
    "beside it, and nothing on this response was recomputed: a second arithmetic "
    "over the same attempts would be a second answer"
)


def held_record(
    cited: GateCitation | None, library: Path | None
) -> HeldRecord | UnheldRecord:
    """The record the citation names, or which of the four nothings this bench has.

    Every failure is the same shape and every one of them names the file it was
    looking for, so a reader learns *which* record this bench does not hold rather
    than only that it holds none.
    """
    if library is None:
        return UnheldRecord(record=None, stated=NO_LIBRARY_TO_HOLD_A_RECORD)
    if cited is None:
        return UnheldRecord(record=None, stated=CITES_NO_GATE_RUN)
    named = Path(cited.record).name
    at = (library / named).resolve()
    if at.parent != library.resolve() or not at.is_file():
        return UnheldRecord(record=cited.record, stated=WRITTEN_BESIDE_ITS_DOCUMENT)
    try:
        run = RecordedGateRun.model_validate_json(at.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UnheldRecord(record=cited.record, stated=NOT_READABLE_AS_A_RECORD)
    return HeldRecord(run=run, stated=THE_FIGURES_THE_CITATION_POINTS_AT)


BENCH_SETTINGS_ROUTE = "/bench/settings"
"""What this instrument is configured to do, read and never written.

Under `/bench` with the gate citation, because the subject is the instrument: not
one field here is a measurement of anybody's target, and nothing about a target is
reachable from here (ADR-0018). A reader, in the strong sense — this route has no
sibling that writes, rotation stays in the environment and configuration stays on
the command line, so an operator who needs a different key or a different model
changes the deployment rather than this screen (ADR-0020).

**Every value on it already exists on the record.** The two key fingerprints are
`signing.fingerprint` over the two public halves `ReportConfig` already holds; the
library version is `LibraryVersion.of` over the cases the bench was built with; the
four model settings are read off `DeclaredModels` and, for the fourth, stated as the
setting this bench does not hold; the ceilings are the declared numbers of
`rule.py` and `adaptive/budget.py`. Nothing here computes a rate, a band or a
verdict, and nothing adds two layers or two families.
"""

THE_INSTRUMENT_AS_CONFIGURED = (
    "what this bench is configured to do, as it is currently loaded. A read: no "
    "route under this prefix writes, and nothing here can be changed from a "
    "browser — the signing key is rotated in the environment and the models and "
    "the library are chosen on the command line, because the factory reads its key "
    "from one place and refuses to boot without it (ADR-0020). Not one field below "
    "is a measurement of a target: this bench has a configuration, and a target has "
    "rates, intervals and bands (ADR-0018)"
)
"""What the settings response is, said on the response, because a screenshot travels."""

TWO_KEYS_TWO_FACTS = (
    "Two identifiers, and they are two facts rather than one restated. One is the "
    "key an artefact this bench produces will be signed by; the other is the key a "
    "verification of one is run against. A bench signing with a key nobody "
    f"published verifies against the published one and reports "
    f"{SignatureOutcome.ANOTHER_KEY} on every report it ever produces — a reachable "
    "state, named, and invisible on a screen that printed one identifier and called "
    "it the key (ADR-0017). Neither of them is the private half: what is served "
    "here is a fingerprint over a public key and nothing else derived from a secret, "
    f"and {SIGNING_KEY_VARIABLE} is read by `signing.signing_key` — the only line in "
    "this repository that reads it — and by no route"
)
"""Why one key identifier would be a screen hiding a state its own tests reach."""

WILL_BE_SIGNED_BY = (
    "the key every artefact this bench produces will be signed by, named by the "
    "fingerprint and by nothing else. The same value is written into the payload as "
    "`key_id`, inside the bytes the signature covers, so a recipient compares what "
    "they were told against what they were handed rather than taking a sender's word "
    "for which key signed"
)

WILL_BE_SIGNED_BY_NOTHING = (
    "this bench holds no signing key, so it will produce no signed artefact. A "
    "stated absence and not a blank: its runs still attempt the library and are "
    "still measured, and the report each one leaves is refused by name as "
    f"{ReportRefusal.NEVER_SIGNED} rather than served unsigned, because the word "
    "*signed* has to mean one thing (ADR-0017). A deployment cannot arrive here by "
    f"omission — the factory refuses to boot without {SIGNING_KEY_VARIABLE} "
    "(ADR-0020) — so a bench in this state is one somebody declared"
)

VERIFIED_AGAINST_A_DECLARED_PIN = (
    "the key this bench runs its own verification readings against: a published "
    "half the deployment declared, which is what a rotated key needs. Compare it "
    "with the fingerprint above — if the two differ, every verification this bench "
    "reports reads "
    f"{SignatureOutcome.ANOTHER_KEY}, and that is worth finding here rather than "
    "after a recipient runs the script"
)

VERIFIED_AGAINST_THE_COMMITTED_KEY = (
    "the key this bench runs its own verification readings against: the committed "
    "public half whose fingerprint this repository's README publishes, which is what "
    "`scripts/verify.py` pins when it is handed no other. This deployment declared "
    "no pin of its own, so this is the key a recipient who does not trust the sender "
    "would use — and it is the default for exactly that reason, because a bench "
    "verifying its own artefacts against its own signing key would report valid on "
    "every report it ever produced"
)


class WillBeSignedBy(BaseModel):
    """The key an artefact this bench produces will be signed by, as a fingerprint.

    The fingerprint and nothing else. Nothing derived from the private half reaches
    this model, and there is no field on it that could carry one: what a settings
    screen is for is telling an operator *which* key, and `signing.fingerprint` is
    the one representation of that — the value in `key_id`, the value the README
    publishes, and the value `verify.py` compares (ADR-0017).
    """

    holds_a_key: Literal[True] = True
    fingerprint: str
    stated: str = WILL_BE_SIGNED_BY


class WillSignNothing(BaseModel):
    """A bench that declared it does not sign, saying so where a key would be.

    `holds_a_key` is the field a caller branches on and it is a literal, so this and
    the shape above are two facts rather than one record with an empty fingerprint.
    There is no `fingerprint` field to be blank, so nothing here can be read as a
    key whose name failed to load.
    """

    holds_a_key: Literal[False] = False
    stated: str = WILL_BE_SIGNED_BY_NOTHING


class VerifiedAgainst(BaseModel):
    """The key a verification of this bench's artefacts is run against.

    Never absent, because there is always an answer: a deployment that declared no
    pin verifies against the committed public half, which is the key a recipient
    would pin. `declared` says which of the two this is, so *the deployment rotated
    its key* and *the deployment said nothing* are distinguishable rather than
    inferred from a fingerprint somebody would have to recognise.
    """

    fingerprint: str
    declared: bool
    """True when the deployment declared its own published half (`pinned`)."""

    stated: str


class SigningKeys(BaseModel):
    """The two key identifiers, kept apart, and neither of them a secret.

    Two fields rather than one, mirroring `SignatureResult.claimed` and `.pinned`
    exactly: those two are separate on the wire because a signature valid under a
    key the recipient did not pin is the failure a single value would hide, and the
    same two keys are what a settings screen is asked about.
    """

    will_be_signed_by: WillBeSignedBy | WillSignNothing
    verified_against: VerifiedAgainst
    statement: str = TWO_KEYS_TWO_FACTS


def signing_keys(config: ReportConfig) -> SigningKeys:
    """The two fingerprints this bench's configuration implies, and nothing else.

    Both read off `ReportConfig`: the first over the public half of the key the
    bench signs with, the second over the pin the deployment declared or over the
    committed key when it declared none — the same fallback `verification_of`
    applies, so the fingerprint shown here is the key the readings this bench serves
    were actually run against.
    """
    key = config.signing_key
    pinned = config.pinned
    return SigningKeys(
        will_be_signed_by=WillSignNothing()
        if key is None
        else WillBeSignedBy(fingerprint=fingerprint(key.public_key())),
        verified_against=VerifiedAgainst(
            fingerprint=fingerprint(pinned if pinned is not None else public_key()),
            declared=pinned is not None,
            stated=VERIFIED_AGAINST_A_DECLARED_PIN
            if pinned is not None
            else VERIFIED_AGAINST_THE_COMMITTED_KEY,
        ),
    )


RETIRED_IS_KEPT = (
    "retired cases are counted and kept. A case that stopped discriminating is "
    "marked retired with the date and the reading it retired on, and it is never "
    "deleted, because a case the field caught up with is evidence that the field "
    "moved (CONTEXT.md, PLAN §6). It leaves live scoring and stays in the library, "
    "which is why this is a count beside the version rather than a difference "
    "between two versions: the library's history is part of what it is, and a screen "
    "showing only the live half would show an instrument with no past"
)
"""Why the retired count sits beside the version rather than inside it."""

THE_VERSION_IS_OVER_THE_LIVE_HALF = (
    "the version is over the cases a run scores — the live half — which is the half "
    "a gate run is decided on, so the version here and the version in the gate "
    "citation are comparable by eye. Both the count and the digest, because a "
    "library described only as *eighteen cases* cannot tell a reader whether the "
    "eighteen are the same eighteen"
)


class LoadedLibrary(BaseModel):
    """The case library this bench is loaded with: its version, and what has retired.

    Two figures and no third. There is no total of the two here and no field that is
    their sum: *live* and *retired* answer different questions — what a run will
    attempt, and what the library has stopped attempting — and a figure adding them
    would be a case count nothing runs.
    """

    live: CitedLibrary
    """The count and the digest over the cases a run scores.

    `CitedLibrary` and not a second shape, because this is the same fact the gate
    citation carries and story 31 is a reader comparing the two. One model, so the
    comparison is between two values of one type rather than two types somebody has
    to be told are the same.
    """

    stated: str
    """The version as a run prints it, from `LibraryVersion.stated`."""

    retired: int
    """How many cases are marked retired and kept. Never a deletion."""

    kept: str = RETIRED_IS_KEPT
    statement: str = THE_VERSION_IS_OVER_THE_LIVE_HALF


def loaded_library(cases: Sequence[Case]) -> LoadedLibrary:
    """The version of the live half, and the count of the retired half beside it.

    Split on the status already on each record rather than by re-deriving the
    retirement rule: `retirement.live_library` re-decides every case and refuses a
    record whose status and stored series disagree, which is the right behaviour for
    a run that is about to spend money and the wrong one for a screen — a settings
    reader that raised would tell an operator nothing at all about the bench they
    are trying to read.
    """
    live = [case for case in cases if case.status is CaseStatus.ACTIVE]
    version = LibraryVersion.of(live)
    return LoadedLibrary(
        live=CitedLibrary(cases=version.cases, digest=version.digest),
        stated=version.stated(),
        retired=len(retired_cases(cases)),
    )


FOUR_SETTINGS_NEVER_ONE = (
    "four separate settings, deliberately, and shown separately for the reason they "
    "are declared separately. The reference agents' model is what is being measured; "
    "the adjudicator's is the instrument measuring it; the adaptive attacker's is a "
    "third thing that decides nothing; the second reference model is what a swap is "
    "measured against. Collapsing any two of them into one would report an "
    "instrument's agreement with itself — a κ measured on the model that produced "
    "the transcripts, or a swap that measured run-to-run variation (ADR-0012, "
    "ADR-0013). There is no combined field here and no default that fills one in"
)
"""Why four rows and never one: each collapse names the figure it would corrupt."""

THE_REFERENCE_AGENTS_MODEL = (
    "the model the three reference agents run on, and so the model this bench's own "
    "discrimination scores were earned on. What is being measured rather than the "
    "instrument measuring it: a `D` is a reading about one pair of models and never "
    "a general claim (ADR-0012)"
)

THE_ADJUDICATORS_MODEL = (
    "the instrument that decides the two judged families, and the one κ is measured "
    "on against the gold set. Never a reference agent's model: an adjudicator "
    "scoring transcripts its own model produced would be reporting its agreement "
    "with itself, which is the reading ADR-0013 keeps a third instrument apart to "
    "prevent"
)

THE_ADAPTIVE_ATTACKERS_MODEL = (
    "the adaptive layer's model, and the adaptive layer's only. It decides nothing "
    "that is scored: no episode it runs lands in a denominator, and `A_break` is "
    "never written `D` (ADR-0010)"
)

THE_SECOND_REFERENCE_MODEL = (
    "the model the library is re-run on when the bench checks whether it reads the "
    "agents' defences or the model's default refusals. Not a setting this bench "
    "holds: it is declared to `scripts/swap.py` on the command line, per run, and it "
    "has to differ from the reference agents' model above or the second run measures "
    "run-to-run variation rather than a model swap (ADR-0012). Stated here rather "
    "than omitted, because a screen showing three of the four would be exactly the "
    "collapse this block exists to make visible"
)

NOT_HELD_BY_THIS_BENCH = (
    "not held by this bench — declared on the command line, per run, to the script "
    "that uses it"
)
"""What the fourth setting's identifier says. A stated absence, not a model."""


class ModelSetting(BaseModel):
    """One of the four model settings: the instrument, its model, what it decides.

    A row with no figure on it. Nothing here is a rate, a κ or a `D` — those belong
    to the runs and to the gate document — and there is no field on which two of
    these rows could be compared, because what a reader has to be able to see is
    that they are four and not one.
    """

    instrument: str
    """What this model is the model *of*, in the bench's own words."""

    identifier: str
    """The model as the deployment declared it, or the stated absence of one."""

    declared: bool
    """Whether a deployment named this one. `False` is a sentence, not a blank."""

    decides: str
    """What it decides, and which other setting it must never be collapsed with."""


def model_settings(models: DeclaredModels) -> list[ModelSetting]:
    """The four settings, in the order they are declared, each on its own row.

    Three read off `DeclaredModels` — the same three identifiers every signed
    provenance block carries, so the models on this screen are the models a report
    names — and the fourth stated as the setting this bench does not hold. Built as
    a list of four rather than one record with four fields so that *four* is a
    length a test can assert, and so that there is nowhere to put a fifth field
    combining any two of them.
    """
    return [
        ModelSetting(
            instrument="the reference agents",
            identifier=models.calibration,
            declared=models.calibration != UNDECLARED_MODEL,
            decides=THE_REFERENCE_AGENTS_MODEL,
        ),
        ModelSetting(
            instrument="the adjudicator",
            identifier=models.adjudicating,
            declared=models.adjudicating != UNDECLARED_MODEL,
            decides=THE_ADJUDICATORS_MODEL,
        ),
        ModelSetting(
            instrument="the adaptive attacker",
            identifier=models.attacking,
            declared=models.attacking != UNDECLARED_MODEL,
            decides=THE_ADAPTIVE_ATTACKERS_MODEL,
        ),
        ModelSetting(
            instrument="the second reference model",
            identifier=NOT_HELD_BY_THIS_BENCH,
            declared=False,
            decides=THE_SECOND_REFERENCE_MODEL,
        ),
    ]


NEITHER_LAYER_BORROWS = (
    "each layer's ceiling is declared for that layer and enforced against that "
    "layer's own counter, so a layer with room left cannot spend the other's "
    "unspent allowance (ADR-0007, ADR-0010). There is no combined budget here and "
    "no field that adds the two: the figures are in different units — attempts over "
    "cases on one side, turns over episodes on the other — and an episode is not an "
    "attempt, which is why the sum a reader might want does not exist to be printed"
)
"""Why two blocks and no total. The units differ, so the sum is not a quantity."""

THE_SCORED_CEILING_IS_DECLARED = (
    "the scored layer runs recorded cases at a declared number of attempts each, and "
    "its ceiling is the whole live library at that number, plus one registration "
    "probe per target, allowing each message the retries that target says it will "
    "tolerate. Exact rather than a bound, because a suite of known size is "
    "arithmetic — the figure for one run is declared at the approval interrupt, "
    "against the library that run is attempted with, and it is presented there as "
    "its own figure beside the adaptive one"
)

THE_ADAPTIVE_CEILING_IS_DECLARED = (
    "the adaptive layer's ceiling is declared here, ahead of any run, because an "
    "attacker choosing its own route spends unpredictably by construction: it is a "
    "worst case and it is stated as one. Every episode running to its turn cap, "
    "across every family, is the most this layer may put on one target's wire — and "
    "the per-episode cap is a different limit, enforced by the attacker as it runs, "
    "so a per-family cap multiplied out is not something a reader has to do in their "
    "head (ADR-0007)"
)


class ScoredCeiling(BaseModel):
    """The scored layer's ceiling, in the units the scored layer is declared in.

    Attempts over cases. There is no turn on this model and no episode: the two
    layers are enforced independently and reported separately, and a shape holding
    both layers' units is a shape somebody eventually adds up (ADR-0010).
    """

    layer: Literal[Layer.SCORED] = Layer.SCORED
    attempts_per_case: int
    """`n` — the declared attempts per case, from `rule.py`. Also a denominator, and
    that is not an accident: the scored layer's cost is its sample size."""

    registration_probes_per_target: int
    """The nonce echo probe, which is a call on the operator's endpoint like any
    other and is inside the ceiling rather than beside it."""

    declared_in: str
    statement: str = THE_SCORED_CEILING_IS_DECLARED


class AdaptiveCeiling(BaseModel):
    """The adaptive layer's ceiling, in the units the adaptive layer is declared in.

    Turns over episodes over families. No field here shares a unit with the model
    above, which is what makes the two ceilings unaddable rather than merely
    un-added: an attempt is the unit of a denominator and a turn is a spending
    limit, and CONTEXT.md keeps them apart for exactly this reason.
    """

    layer: Literal[Layer.ADAPTIVE] = Layer.ADAPTIVE
    turns_per_episode: int
    """`T` — the cap on one episode, which the attacker enforces as it runs."""

    episodes_per_family: int
    """`k` — how many episodes are run per family per target."""

    families: int
    """The families the layer covers, read off the closed enum."""

    turns_per_target: int
    """The layer's own ceiling: every episode running to its cap, per target."""

    declared_in: str
    statement: str = THE_ADAPTIVE_CEILING_IS_DECLARED


class LayerCeilings(BaseModel):
    """The two ceilings, one field each, and no third field anywhere.

    Two differently-typed records rather than two integers, so that the invariant is
    carried by the type: there is no name here under which a sum could be added
    without inventing a model to hold it, and the two models have not one numeric
    field in common to add.
    """

    scored: ScoredCeiling
    adaptive: AdaptiveCeiling
    statement: str = NEITHER_LAYER_BORROWS


def layer_ceilings(
    rule: GateRule = DECLARED_RULE, adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET
) -> LayerCeilings:
    """Each layer's ceiling, read off the record that declares it.

    Two records and two readers: the scored layer's numbers are `rule.py`'s and the
    adaptive layer's are `adaptive/budget.py`'s, which is where they are declared and
    why `AdaptiveBudget` is deliberately not `GateRule`. No number is written here.
    """
    return LayerCeilings(
        scored=ScoredCeiling(
            attempts_per_case=rule.attempts_per_case,
            registration_probes_per_target=REGISTRATION_PROBES_PER_TARGET,
            declared_in="backend/bench/rule.py — the declared gate rule",
        ),
        adaptive=AdaptiveCeiling(
            turns_per_episode=adaptive.turns_per_episode,
            episodes_per_family=adaptive.episodes_per_family,
            families=adaptive.family_count,
            turns_per_target=adaptive.turn_ceiling,
            declared_in="backend/bench/adaptive/budget.py — the declared adaptive "
            "budget",
        ),
    )


class BenchSettings(BaseModel):
    """What this instrument is configured to do. A reader, whole, in one response.

    Five fields and a sentence, and not one of them a measurement. There is no field
    here that spans two families, none that spans two layers, no severity scale, no
    composite figure and no control: what a caller can do with this response is read
    it (ADR-0005, ADR-0010).

    The reference agents are deliberately not on it. They are test equipment served
    by a different application (`backend/targets/reference`) and this bench holds no
    handle on them, so a field here would be this route asserting what some other
    process is running. The console names the three of them from the one constant
    the gate screen already names them by, which is where *what `D` is measured
    against* belongs.
    """

    statement: str = THE_INSTRUMENT_AS_CONFIGURED
    signing: SigningKeys
    library: LoadedLibrary
    models: list[ModelSetting]
    ceilings: LayerCeilings


def bench_settings(config: BenchConfig) -> BenchSettings:
    """The bench's own configuration as it is currently loaded, and nothing derived.

    Every field is read off the record the deployment handed in. There is no clock
    here, no filesystem read of a case, no model call and no write — and the one
    file that is read is the committed public key, through the same
    `signing.public_key` the verification readings already reach.
    """
    return BenchSettings(
        signing=signing_keys(config.report),
        library=loaded_library(config.cases),
        models=model_settings(config.report.models),
        ceilings=layer_ceilings(config.rule, config.adaptive),
    )


GATE_RUNS_ROUTE = "/gate-runs"
"""Where a gate run is started, listed, and read. Its own family, and never `/runs`.

**A gate run is not a run and this is not a route under `/runs`.** A run is one pass
over one target and comes back with rates, intervals and bands about somebody's
agent; a gate run is the whole library against three agents of this project's own
construction and comes back with a decision about this bench (ADR-0018). Nothing on
this prefix takes a run id, nothing under `/runs` takes a gate run id, and no model
on either is the other's.

**It is also not under `/bench`.** `/bench` is the instrument's own prefix and every
method on it is a `GET` — a reader in the strong sense, asserted over the route table
from two directions. A gate run spends about 830 calls and rewrites the case library,
so it belongs where a caller can see that it is not a read.
"""

GATE_RUN_ROUTE = "/gate-runs/{gate_run_id}"
GATE_RUN_APPROVAL_ROUTE = "/gate-runs/{gate_run_id}/approval"
"""The two routes for one gate run: where it is read, and where its halt is answered.

The interrupt is a route rather than a field on the start request for the reason
`POST /runs/{id}/approval` is: a `confirmed: true` in the body that started the run
would be a form answered by whatever composed it, and a separate answer to a graph
that has already halted is a decision taken in front of the figures (ADR-0007).
"""

A_GATE_RUN_IS_NOT_A_RUN = (
    "a gate run, which is not a run. Its subject is this bench: the whole live case "
    "library against three reference agents of known construction, decided by the "
    "declared rule. It produces no rate about anybody's target and no report, and no "
    "route here takes a run id (ADR-0018)"
)
"""Said on the list, because a screenshot of a list travels alone."""


class MayStart(BaseModel):
    """This bench can run a gate, and what one would do before it does it.

    Two facts and no control: the caller learns that the affordance is available and
    what pressing it costs. `available` is a literal so this shape and the one below
    are two facts rather than one record with empty fields.
    """

    available: Literal[True] = True
    library: str
    """The case library a gate run would read and write back to, named as the path
    it is. A gate run is not a read, and the operator sees where it writes."""

    statement: str
    """What starting one does, and what it asks first.

    The three agents are deliberately not named here: they are served by a different
    application this bench holds no handle on, and naming them would mean this module
    importing test equipment a deployment may legitimately not ship. The console
    names them from the one list it already keeps for the gate screen.
    """


class MayNotStart(BaseModel):
    """This bench cannot run a gate, and the named reason it cannot.

    A stated absence rather than a missing field, and never an empty `MayStart`: a
    deployment that ships no reference agents and a library already held by another
    gate run are different facts, and only one of them is answered by waiting.
    """

    available: Literal[False] = False
    refusal: str
    """One of `NotStartable`'s four members — the field a caller branches on."""

    stated: str


THE_GATE_RUN_IS_AVAILABLE = (
    "A gate run evaluates the whole library to three agents of known construction, "
    "then writes each family’s discrimination."
)
"""The sentence a bench that may start one says about itself.

One clause where there were five, and it describes the run rather than the readiness.
The three agents, the library and the lease were named here because they are what
`why_not` checked, and a reader of this sentence is not auditing that check — the
refusal names it when the answer is no. What an operator reading a control wants from
a sentence beside it is what pressing it does, and the consent it asks for first is
the walk that follows, not a promise made here.
"""


def may_start(gates: BenchGateRuns) -> MayStart | MayNotStart:
    """Whether a gate run may start on this bench right now, and why not if not.

    Read off `BenchGateRuns.why_not`, which is the one place the four refusals are
    decided: a second reading here would be a screen that offered a control the bench
    would refuse, or withheld one it would have taken.
    """
    refusal = gates.why_not()
    if refusal is not None:
        held = gates.holder()
        return MayNotStart(
            refusal=str(refusal),
            stated=f"{refusal.stated()}. {held}" if held else refusal.stated(),
        )
    library = gates.bench.library
    return MayStart(library=str(library), statement=THE_GATE_RUN_IS_AVAILABLE)


class GateRunRow(BaseModel):
    """One gate run on the record: when, where it got to, what it spent per layer.

    A row and never a decision. There is no outcome on it and no per-family figure:
    those are read from the gate run's own route, because a decision lifted onto a
    list arrives without the rule it was taken under (ADR-0003).
    """

    gate_run_id: str
    recorded_at: str
    status: str
    statement: str
    spent: dict[str, int]
    """Calls spent per layer, and no third figure. Two keys, and nothing here adds
    them or adds either across the rows (ADR-0007, ADR-0010)."""


class GateRuns(BaseModel):
    """The gate runs this bench has started, and whether it may start another.

    The start availability is on the list rather than on `GET /bench/gate`, because
    `/bench` is a reader about the instrument and *may I start one right now* is a
    fact about this moment — and because the console needs the answer before it draws
    a control, not after somebody presses it.
    """

    start: MayStart | MayNotStart
    gate_runs: list[GateRunRow]
    statement: str = A_GATE_RUN_IS_NOT_A_RUN


def gate_run_row(record: GateRunRecord) -> GateRunRow:
    """One gate run as it stands, built in one place so every route agrees."""
    return GateRunRow(
        gate_run_id=record.gate_run_id,
        recorded_at=record.recorded_at.isoformat(),
        status=str(record.status),
        statement=record.statement,
        spent={str(layer): record.spent[layer] for layer in Layer},
    )


def gate_runs_response(
    gates: BenchGateRuns, records: Sequence[GateRunRecord]
) -> GateRuns:
    """The list, and the one fact a screen needs before it offers a control."""
    return GateRuns(
        start=may_start(gates), gate_runs=[gate_run_row(record) for record in records]
    )


THE_SCORED_ESTIMATE_IS_EXACT = (
    "the scored layer, and it is arithmetic: every live case at the declared attempts "
    "per case, against each of the three reference agents, plus the one registration "
    "probe each. Exact because it is a multiplication, and held to the scored layer's "
    "own ceiling below it"
)

THE_ADAPTIVE_ESTIMATE_IS_A_CEILING = (
    "the adaptive layer, and it is a bound rather than a figure: an attacker that "
    "chooses its own route has no exact cost, so what is shown is the worst case — "
    "every episode running to its turn cap, against each agent. An average here would "
    "invite a gate run to exceed what was agreed to (ADR-0007)"
)

TWO_FIGURES_AND_NO_THIRD = (
    "two figures, and there is no third one on this response. The two layers are "
    "enforced against two separate counters, so neither can borrow what the other did "
    "not spend, and a blended number would hide which half of a gate run is spending "
    "the operator's budget. Nothing shown here with a ≤ in front of it may be "
    "exceeded (ADR-0007, ADR-0010)"
)


class ScoredEstimate(BaseModel):
    """What a gate run's scored layer will cost, in the units it is declared in.

    Attempts over cases over agents. Not one numeric field here appears on the model
    below: the two layers share no number to add, which is the invariant carried by
    the type rather than by a comment asking for care (`ScoredCeiling`'s own reason).
    """

    layer: Literal[Layer.SCORED] = Layer.SCORED
    attempt_calls: int
    """The calls this layer will make. Exact, and the arithmetic is in `basis`."""

    attempt_ceiling: int
    """The scored layer's own enforced ceiling — the figure above with every message
    retried to its transport limit. The larger figure is the enforced one, and a run
    may not exceed anything it was shown with a `≤` in front of it (ADR-0007)."""

    cases: int
    attempts_per_case: int
    kind: str
    basis: str
    cost: str
    statement: str = THE_SCORED_ESTIMATE_IS_EXACT


class AdaptiveEstimate(BaseModel):
    """What a gate run's adaptive layer may cost, in the units *it* is declared in.

    Turns over episodes over families over agents. A separate model with no numeric
    field in common with the one above, for the reason the two ceilings on the
    settings route are two records: an attempt is the unit of a denominator and a turn
    is deliberately not one (CONTEXT.md, ADR-0010).
    """

    layer: Literal[Layer.ADAPTIVE] = Layer.ADAPTIVE
    turn_calls: int
    """The most this layer may spend: every episode to its cap, per agent."""

    turn_ceiling: int
    """The adaptive layer's own enforced ceiling, held on its own counter."""

    turns_per_episode: int
    episodes_per_family: int
    kind: str
    basis: str
    cost: str
    statement: str = THE_ADAPTIVE_ESTIMATE_IS_A_CEILING


class GateRunEstimate(BaseModel):
    """The consent surface for a gate run: two figures, two ceilings, no total.

    Two differently-typed records and no third field. There is no name here under
    which a sum could be added without inventing a model to hold it, and there is no
    arithmetic in the function that builds it: every number is read off the
    `RunBudget` the gate run is held to.
    """

    scored: ScoredEstimate
    adaptive: AdaptiveEstimate
    currency: str
    statement: str = TWO_FIGURES_AND_NO_THIRD


def gate_run_estimate(record: GateRunRecord, config: BenchConfig) -> GateRunEstimate:
    """The estimate this gate run is holding, per layer, off its own budget.

    Read from `RunBudget` and from the two records that declare the units — the gate
    rule and the adaptive budget — and nothing here computes a figure of its own.
    `BudgetPayload`'s bounded total and hard ceiling are deliberately not carried:
    what replaces them is each layer beside *the ceiling it is enforced against*,
    which is what the run screen's interrupt already presents (ADR-0007).
    """
    budget = record.budget
    estimate = budget.estimate
    return GateRunEstimate(
        scored=ScoredEstimate(
            attempt_calls=estimate.scored.calls,
            attempt_ceiling=budget.ceiling(Layer.SCORED),
            cases=len(record.cases),
            attempts_per_case=config.rule.attempts_per_case,
            kind=str(estimate.scored.kind),
            basis=estimate.scored.basis,
            cost=estimate.cost(estimate.scored),
        ),
        adaptive=AdaptiveEstimate(
            turn_calls=estimate.adaptive.calls,
            turn_ceiling=budget.ceiling(Layer.ADAPTIVE),
            turns_per_episode=config.adaptive.turns_per_episode,
            episodes_per_family=config.adaptive.episodes_per_family,
            kind=str(estimate.adaptive.kind),
            basis=estimate.adaptive.basis,
            cost=estimate.cost(estimate.adaptive),
        ),
        currency="" if estimate.price is None else estimate.price.currency,
    )


class GateRunStarted(BaseModel):
    """A gate run recorded and halted in front of its estimate.

    The estimate is returned once, here, by the request that created the gate run —
    the same division `POST /runs` uses, and for the same reason: the route that
    reports progress reports no estimate, because nothing on it spans the layers.
    """

    gate_run_id: str
    status: str
    statement: str
    estimate: GateRunEstimate
    library: str
    """The case library this gate run holds and will write back to."""

    agents: list[str]
    cases: int


def gate_run_started(record: GateRunRecord, config: BenchConfig) -> GateRunStarted:
    """One gate run as it stands right now, with the figures it is holding."""
    return GateRunStarted(
        gate_run_id=record.gate_run_id,
        status=str(record.status),
        statement=record.statement,
        estimate=gate_run_estimate(record, config),
        library=str(record.library),
        agents=list(record.agents),
        cases=len(record.cases),
    )


class WroteBack(BaseModel):
    """What this gate run wrote to the case library, and where it wrote it.

    On the response because it is the half of a gate run that outlives it: the series
    the *next* gate run reads, the retirements this one marked, its own figures as
    fields, and the citation this bench carries from now on. A run that wrote
    nothing is absent rather than a zero here — `written` is null until there is a
    write-back to report.

    **`cited` is on the wire because a citation must not change in silence.** A gate
    run that displaced a passing citation says so, in words, on its own reading — the
    console's counterpart to the line the terminal prints (ADR-0023).
    """

    library: str
    readings: int
    unread: list[str]
    retired: list[str]
    record: str
    """The file name this gate run's own figures were written under, in that
    library. The console's counterpart to the dated record a command-line gate run
    leaves beside its document (ADR-0023)."""

    cited: str
    """What citing this gate run did to the citation this library carried before it,
    in words — because a replacement nobody is told about is the failure mode
    ADR-0023 exists to refuse."""

    stated: str


class AgentProgress(BaseModel):
    """One reference agent's share of one family, over its own denominator.

    A count and the count it is out of, and nothing that says how it went. The three
    are ordered by construction — hardened, weak, trivial — because that is the order
    the contrast is built in and the order every other surface reads them in; the
    order is read off `GateRunRecord.roles`, which the equipment answered, and never
    off the name.
    """

    agent: str
    attempted: int
    of: int


class FamilyProgress(BaseModel):
    """How far one family has got, over its own denominator, and never a rate.

    **Six of these and no seventh figure.** A family's denominator is its own cases
    at the declared attempts per case against each of the three agents, and this row
    carries the count against it. Nothing here is added to another row, because a
    run-wide count would be a total across six denominators — the one arithmetic this
    bench refuses everywhere else (ADR-0005) — and nothing here is divided, because a
    fraction of a family's attempts is a share of the work and would be read as a
    rate.

    **And no count of verdicts.** How well a family is going is a rate with an
    interval and a band beside it, and it belongs to the decision or to nothing.
    A live success count is that rate with the interval taken off.
    """

    family: str
    attempted: int
    of: int
    agents: list[AgentProgress]


class AttemptPayload(BaseModel):
    """One attempt as evidence: what went on the wire, what came back, the verdict.

    **Served because the three agents are this bench's own equipment.** A gate run
    attacks constructs of this project, started and stopped by it, so a transcript
    here is the bench talking to itself — no operator's target, and nobody else's
    traffic. `GET /runs/{id}` serves nothing of the kind for a target run and this is
    not a precedent for it.

    `verdict` is the attacker's point of view, which is the sense the whole bench
    counts in: *succeeded* is the attack working. `verdict_class` is how that was
    reached, copied off the case record rather than inferred from the family, because
    a deterministic *resisted* and a judged one carry different limits (ADR-0004).
    """

    family: str
    case_id: str
    agent: str
    attempt: int
    sent: str
    reply: str
    verdict: str
    verdict_class: str
    status_code: int
    sends: int


RECENT_ATTEMPTS = 5
"""How many attempts the reading carries the payloads of.

The tail and never the log: a gate run makes hundreds, the screen shows the last
few as they go by, and a response that grew with the run is a response whose size is
a function of how long somebody has been watching.
"""


class GateRunReading(BaseModel):
    """Where one gate run has got to, per layer, and what it decided if it has.

    **The rule is above the decision, and that is not a layout preference.** A pass
    or a fail means nothing without the bar it was decided against, so the declared
    rule is served first and an operator can re-derive the answer rather than trust
    it (ADR-0003). It is `DECLARED_RULE` — the record every scorer in this repository
    reads — and not a copy kept for a screen.

    **Progress is per layer and there is no figure that spans them.** The scored
    layer's position is family, case and attempt; the adaptive layer's is family,
    episode and turn — the same two models `GET /runs/{id}` reports a run's progress
    with, because a position is neither a run nor a gate run and the units are the
    units either way (CONTEXT.md, ADR-0010).
    """

    gate_run_id: str
    status: str
    statement: str
    rule: DeclaredRule
    scored: ScoredProgress
    adaptive: AdaptiveProgress
    families: list[FamilyProgress]
    recent: list[AttemptPayload]
    decision: GateDecided | None
    written: WroteBack | None


def gate_run_reading(record: GateRunRecord, rule: GateRule) -> GateRunReading:
    """One gate run: the rule it is held to, where it is, and what it answered."""
    written = record.written
    return GateRunReading(
        gate_run_id=record.gate_run_id,
        status=str(record.status),
        statement=record.statement,
        rule=declared_rule(rule),
        scored=_scored_progress(record.run_state),
        adaptive=_adaptive_progress(record.run_state),
        families=_families(record, rule),
        recent=_recent(record),
        decision=None if record.gate is None else gate_decided(record.gate),
        written=(
            None
            if written is None
            else WroteBack(
                library=str(written.library),
                readings=written.readings,
                unread=list(written.unread),
                retired=list(written.retired),
                record=written.record,
                cited=written.cited,
                stated=written.stated(),
            )
        ),
    )


def _families(record: GateRunRecord, rule: GateRule) -> list[FamilyProgress]:
    """The six families, each over its own denominator, in the enum's own order.

    Six rows whether or not a family has started, because a family missing from the
    list while the run is on another one would read as a family this run is not
    doing. The counts are `RunState.attempts` grouped by family and agent — the same
    grouping the rates are built from, without the division.
    """
    made: dict[tuple[str, str], int] = {}
    for attempt in record.run_state.attempts:
        key = (str(attempt.family), attempt.target_name)
        made[key] = made.get(key, 0) + 1
    rows: list[FamilyProgress] = []
    for family in Family:
        name = str(family)
        cases = sum(1 for case in record.cases if case.family is family)
        each = cases * rule.attempts_per_case
        agents = [
            AgentProgress(agent=role, attempted=made.get((name, role), 0), of=each)
            for role in record.roles
        ]
        rows.append(
            FamilyProgress(
                family=name,
                attempted=sum(one.attempted for one in agents),
                of=each * len(agents),
                agents=agents,
            )
        )
    return rows


def _recent(record: GateRunRecord) -> list[AttemptPayload]:
    """The last few attempts, newest first, with the exchange behind each verdict."""
    tail = record.run_state.attempts[-RECENT_ATTEMPTS:]
    return [
        AttemptPayload(
            family=str(attempt.family),
            case_id=attempt.case_id,
            agent=attempt.target_name,
            # One-based on the way out, for `_scored_progress`' own reason: a reader
            # counts "the third attempt" and the record holds an index into ten.
            attempt=attempt.index + 1,
            sent=_message(attempt.transcript.sent),
            reply=attempt.transcript.reply_text,
            verdict=str(attempt.verdict),
            verdict_class=str(attempt.verdict_class),
            status_code=attempt.transcript.status_code,
            sends=attempt.transcript.sends,
        )
        for attempt in reversed(tail)
    ]


def _message(sent: dict[str, object]) -> str:
    """The message out of a sent payload, or the empty string if it carried none."""
    message = sent.get("message")
    return message if isinstance(message, str) else ""


class StartGateRunRequest(BaseModel):
    """Everything a gate run needs before it may exist, and nothing it can default.

    Two fields, and neither has a default anywhere. The attestation is the same
    three-statement record `POST /runs` takes — one field each, because the record has
    to show *what* was attested — and the cost is declared by the operator because
    the reference agents run on the operator's own provider credential.

    There is no target here, because a gate run's targets are this bench's own three
    reference agents and there is nothing for a caller to choose: `D` is trivial minus
    hardened and monotonicity is read across all three, so a gate over a subset is not
    a smaller gate but a different and undeclared one. There is no nonce either: the
    run plants its own in equipment it started itself, which is the one case where the
    bench can prove control of the endpoint without asking anybody to.
    """

    attestation: AttestationRequest
    cost: CostRequest


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
    the gate run that library last recorded, and the signing key from the
    environment, or no bench at all.

    The key is fetched through `signing.signing_key`, which stays the only line in
    this repository that reads `AGENTAUDIT_SIGNING_KEY`; the refusal it raises is
    re-raised with what booting anyway would have cost, and its type is unchanged so
    that a deployment catching `NoSigningKey` still catches this one.

    **The citation is read off the library, and that is ADR-0023's other half.**
    Until now this function declared none, so a live deployment's front door and gate
    screen read *no gate run cited* even where the bench had passed one — true, and
    misleading, and the same surface as a gate run not updating what the bench cites.
    Now the cases and the citation come out of one directory: the gate run that wrote
    its readings into this library also wrote the citation beside them
    (`bench/cited.py`), so the claim and the cases it is a claim about cannot come
    apart. A library that records no gate run still states the absence, which is a
    fact about the bench and not a blank (`payload.UNCITED_GATE`).

    Read from the mount where one is mounted, exactly as the cases are, so a gate run
    started from the console survives the restart that follows it (ADR-0021,
    condition 4).
    """
    try:
        key = signing_key()
    except NoSigningKey as missing:
        raise NoSigningKey(f"{missing}. {NO_KEY_NO_BOOT}") from missing
    library = deployed_library() or CASES_DIR
    models, adjudicator = deployed_models()
    return BenchConfig(
        cases=admitted_library(library),
        adjudicator=adjudicator,
        report=ReportConfig(signing_key=key, gate=the_citation(library), models=models),
    )


def deployed_library() -> Path | None:
    """The case library a deployed bench reads and a gate run may write to.

    The mounted volume when there is one, seeded once from the image's own admitted
    library, and `None` when the deployment mounted nothing. Both halves of that
    matter: the library is read from the mount so that a case a gate run retired
    comes back retired after a redeploy, and the absence of a mount is what makes a
    gate run unavailable rather than a write into a filesystem that is about to be
    thrown away (`gate_runs.DEPLOYED_LIBRARY`).
    """
    return seeded_library(DEPLOYED_LIBRARY_MOUNT, CASES_DIR)


NAMED_BUT_UNUSABLE = (
    "the deployment declared this model and the bench cannot build it. Refusing to "
    "boot rather than starting without it: an instrument named in a configuration "
    "and absent from the process is the one state where a screen would offer a "
    "control that spends and then fails, and OPENROUTER_API_KEY is the credential "
    "to check first"
)


def deployed_models() -> tuple[DeclaredModels, Completion | None]:
    """The models a deployment declared, and the adjudicator built from one of them.

    **The environment is read through `completion.declared_model` and nowhere else.**
    No module of `backend/api/` imports `os`, which is what keeps a price, a target
    URL or a bearer token from arriving from the environment behind a default
    (`test_api_runs.py`). A model identifier arrives that way and only that way.

    **Nothing here defaults to a real model.** A bench that declared none says so on
    every screen and in every report, because a default naming an instrument would
    describe a run that did not happen (`UNDECLARED_MODEL`, ADR-0004). What the
    environment declares, this builds; what it does not, stays a stated absence.

    **Two are read and the third is not.** The reference agents' model and the
    adjudicating model are both used by a gate run started from the console — one
    serves the three agents, the other decides the two judged families. The attacking
    model is left undeclared because this bench runs the deterministic stand-in for
    it: naming a model it does not call would be the lie the stated absence exists to
    avoid.

    **A model named and unbuildable stops the boot.** `completion_for` builds its
    client at configuration time precisely so a missing credential is not discovered
    at the first call, and this keeps that promise one level up: the alternative is a
    console that offers a start control for 830 calls against an instrument that was
    never there. A deployment that declares nothing still boots and still serves
    reports — it simply runs no gate (ADR-0020's shape, for a different instrument).
    """
    calibration = declared_model(REFERENCE_MODEL_ENV)
    adjudicating = declared_model(ADJUDICATOR_MODEL_ENV)
    adjudicator: Completion | None = None
    if adjudicating is not None:
        try:
            adjudicator = completion_for(adjudicating)
        except (KeyError, ValueError) as unusable:
            raise RuntimeError(
                f"{ADJUDICATOR_MODEL_ENV}={adjudicating!r}: {unusable}. "
                f"{NAMED_BUT_UNUSABLE}"
            ) from unusable
    return (
        DeclaredModels(
            calibration=calibration or UNDECLARED_MODEL,
            adjudicating=adjudicating or UNDECLARED_MODEL,
            attacking=UNDECLARED_MODEL,
        ),
        adjudicator,
    )


def deployed_gate_runs(config: BenchConfig) -> GateRunBench:
    """What a gate run on a deployed bench has to work with, or the absence of it.

    Two readings and neither is a default that fills itself in: the case library is
    the mounted one or nothing, and the equipment is the three reference agents if
    this build ships them or nothing. A deployment missing either states it on the
    console and offers no control, which is the only honest answer — a gate run
    against equipment that is not there, or writing to a library that will not
    survive the next release, would look exactly like the real thing.

    The reference agents' model is read off the record that declares it
    (`DeclaredModels.calibration`) rather than named here, because a `D` is a reading
    about one pair of models and the pair has to be the declared one (ADR-0012). A
    bench that declared none ships no equipment as far as this is concerned: the
    model string is what the agents are served with, and `UNDECLARED_MODEL` is a
    sentence rather than a model. Answering *no reference agents* is what keeps the
    failure at the console, where it is a stated refusal, instead of at the first
    call of a gate run somebody already confirmed.
    """
    declared = config.report.models.calibration
    return GateRunBench(
        library=deployed_library(),
        equipment=(None if declared == UNDECLARED_MODEL else shipped_agents(declared)),
    )


def create_app(
    config: BenchConfig | None = None, gate_runs: GateRunBench | None = None
) -> FastAPI:
    """The API over one bench, over one library.

    The bench is a constructor argument rather than a module global so that a run
    is estimated against the same library it is attempted against — and so that a
    test can hold both ends of that. Given none, the bench is the deployed one,
    which reads a signing key and refuses to exist without it.

    `gate_runs` is a **second** declaration and deliberately not a field of the
    first. What a run is measured with and what a gate run needs are two different
    statements about a deployment: a bench that has said what it signs with has not
    thereby said that it holds a case library it may write to and ships the three
    reference agents a gate is decided over. Given nothing, a bench that declared its
    own configuration runs no gate — the operation that spends 830 calls and rewrites
    the library is not something a deployment acquires by omission — and a bench that
    declared nothing at all gets the deployed reading of both.
    """
    declared = config is not None
    bench = BenchRuns(config if config is not None else deployed_bench())
    if gate_runs is None:
        gate_runs = GateRunBench() if declared else deployed_gate_runs(bench.config)
    # The one edge from a completed gate run back onto the bench a run is measured
    # with: a `GateCitation` in, nothing out (ADR-0023, `gate_runs.Cites`). Wired
    # here rather than held by either registry, so that neither of them names the
    # other's record and the widening ADR-0021 forbids stays unavailable.
    gates = BenchGateRuns(bench.config, gate_runs, cites=bench.cite)
    app = FastAPI(title="AgentAudit", version="0.1.0")
    app.state.bench = bench
    app.state.gate_runs = gates

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

    @app.get(ARTEFACTS_ROUTE)
    def list_the_signed_artefacts_on_the_record() -> ArtefactList:
        """Every signed artefact this bench has produced, each with its own reading.

        The answer to *which of these can I send*, for an engineer with several runs
        behind them. A read: it starts nothing, signs nothing, and writes nothing.

        **All three results on every row, and no mark over them.** Each row carries
        the reading the per-run verification route serves — computed by
        `verification.checked`, the function `scripts/verify.py` reaches through, over
        the bytes this bench holds — so a failing result is named by its own outcome
        and *unsigned* stays a different fact from *signed by a key you did not pin*.
        The two claims travel with it and stay apart: integrity is over the whole
        document, re-derivability is over the scored layer alone (ADR-0010, ADR-0017).

        **It is the bench's own check and every row says so.** `checked_by` is
        carried on each reading rather than once at the top, because what circulates
        is a row: a sender's word for their own document is the thing a signature
        exists to replace, and the command a recipient runs instead is on the list.

        **A run with no artefact is not a row here.** *Never signed* is a fact about a
        run, stated by name on its own report route and on the list of runs, and an
        empty row on this list would be a document somebody could go looking for.
        """
        return artefacts_response(bench.records(), bench.config.report)

    @app.get(BENCH_GATE_ROUTE)
    def cite_the_gate_run_this_bench_last_made() -> BenchGate:
        """The rule this bench is held to, then the gate run it cites under it.

        The citation is a read of `ReportConfig.gate`, which is the same value the
        provenance block of every report this bench signs carries. One source of
        truth: it is not assembled here, not read off the filesystem on request, and
        not parsed out of the document it names.

        **What it cites is now the gate run this bench last made.** ADR-0021 left the
        citation as whatever a deployment declared and recorded the question as shut;
        ADR-0023 opens it. A gate run writes the citation into the library it wrote
        its readings back to, `deployed_bench` reads it from there at boot, and a gate
        run started from the console reaches this response without a restart through
        one edge (`gate_runs.Cites`). So a bench that has passed its own gate says so
        here, and a bench whose last gate run failed says *that* — the citation is
        what the instrument last put itself through and never the best answer it ever
        got.

        **It names the record, and still serves no figure out of it.** The
        per-family rates and each family's `D` are in the gate run record the
        citation points at; this route hands over its name and opens neither it nor
        the document (ADR-0023).

        **The rule comes first, and that is not a layout preference.** A pass or a
        fail means nothing without the bar it was decided against, so the declared
        rule is served above the outcome and an operator can re-derive the answer
        rather than trust it (ADR-0003). It is `DECLARED_RULE` — the record every
        scorer in this repository reads — and not a copy kept for a screen.

        **This route does not start a gate run, and the one that does is not under
        `/bench`.** A gate run attacks all three reference agents, spends about 830
        calls, and appends a discrimination reading to every case record it reads
        while retiring the cases the rule retires. It is started at `POST /gate-runs`
        — its own family, and a path that says plainly it is not a read — behind the
        same three attestation statements and the same halt a terminal gate run asks
        for (ADR-0021, `scripts/gate.py`). Reading what a gate run decided and
        starting one are still two different operations at two different methods on
        two different paths — what ADR-0023 changed is which gate run this read
        answers with, and not whether this route can start one.
        """
        return bench_gate(bench.config.report.gate)

    @app.get(BENCH_GATE_RECORD_ROUTE)
    def open_the_record_the_citation_names() -> HeldRecord | UnheldRecord:
        """The per-family figures of the gate run this bench cites, out of its record.

        The three reference agents' rates on every family, each family's `D`, its
        ordering and its verdict — the figures `GET /bench/gate` names and does not
        carry. One request for what the gate answered, a second for what it measured:
        the citation stays exactly the block a signed report carries, and this is the
        pointer on it being followed.

        **The record and never the document.** The record is one gate run as fields,
        written by the run itself; the dated Markdown beside it is prose for a person.
        Nothing here parses prose, and there is no reader on this route for a `.md`.

        **Every way of holding no record is one answer, and it is not an error.** A
        deployment with no library, a bench citing no gate run, a citation whose
        record was written beside its document somewhere else, and a file that will
        not parse: all four say *this bench does not hold that record*, with the
        reason in words and the file name it looked for. A 404 would say the route was
        wrong; what is true is that the figures are elsewhere.

        **No composite, here as everywhere.** Six families arrive at once and there is
        no field on this response that spans two of them: no mean of six
        discrimination scores, no severity scale, and nothing adaptive (ADR-0005,
        ADR-0010).
        """
        return held_record(bench.config.report.gate, gates.bench.library)

    @app.get(BENCH_SETTINGS_ROUTE)
    def state_what_this_bench_is_configured_to_do() -> BenchSettings:
        """The bench's own configuration as it is currently loaded. A reader.

        Read off the `BenchConfig` this application was built with — the same record
        every run through it is estimated and attempted against — so what an operator
        sees here is what the next run will use rather than what a deployment
        intended. Nothing here is assembled from the filesystem and nothing is parsed
        out of prose.

        **Two key identifiers, because they are two facts.** The fingerprint of the
        key an artefact will be signed by, and the fingerprint of the key a
        verification is run against. A bench signing with a key nobody published
        verifies against the published one and reports every report as
        `signed_by_another_key` — a state this bench's own tests reach, and one a
        screen naming a single key would hide (ADR-0017). Neither is the private
        half: the signing key variable is read by `signing.signing_key` and by no
        route, and what is served is a fingerprint over a public key.

        **The four model settings are four rows and never one.** The reference
        agents' model is what is measured, the adjudicator's is the instrument
        measuring it, the adaptive attacker's decides nothing, and the second
        reference model is what a swap is measured against — declared on the command
        line rather than held here, and stated rather than omitted (ADR-0012,
        ADR-0013).

        **The two layer ceilings are two records with no unit in common.** Attempts
        over cases on one side, turns over episodes on the other. There is no
        combined budget on this response and nothing that could hold one: the two
        are enforced against separate counters, so a layer with room left cannot
        borrow the other's allowance (ADR-0007, ADR-0010).

        **Nothing here writes, and there is no route that would.** Rotation stays in
        the environment and configuration stays on the command line, per the
        decision that the factory reads its key from one place and refuses to boot
        without it (ADR-0020). Every method under `/bench` is a `GET`, asserted over
        the route table in `test_api_settings.py` as well as in `test_api_gate.py`.
        """
        return bench_settings(bench.config)

    @app.post(GATE_RUNS_ROUTE, status_code=status.HTTP_202_ACCEPTED)
    def start_a_gate_run(
        request: Annotated[StartGateRunRequest, Body()],
    ) -> GateRunStarted:
        """Record the attestation, declare the estimate per layer, and halt.

        Returns once the gate run is holding its interrupt, which is before anything
        has been sent to a reference agent and before one case record has been
        written to. The gate run holds this bench's case library from this moment, so
        a second one is refused by name rather than queued.

        **The two controls the command line carried are the two controls here.** The
        three attestation statements are the `Attestation` record that cannot be
        constructed with one withheld, and the halt is the same `PendingApproval`
        seam `POST /runs/{id}/approval` answers. Neither is reimplemented and there is
        no flag, no setting and no environment variable that stands in for either: a
        gate run that proceeded unattended is the thing ADR-0007 forbids, which is
        also why one cannot be spawned as a subprocess — the terminal helper reads
        absent or piped input as a refusal (ADR-0021, PLAN.md §8).

        **There is no target in the request and no nonce.** A gate run's targets are
        this bench's own three reference agents, all three of them, because `D` is
        trivial minus hardened and monotonicity is read across all three. The nonce
        is planted by the run in equipment it started itself, which is the one case
        where the bench can prove control of an endpoint without asking anybody to.
        """
        try:
            attestation = request.attestation.attestation()
            price = request.cost.price()
        except ValueError as refused:
            # The attestation's own refusal, which names the statements that were
            # withheld. No gate run exists, the library was never held, and nothing
            # has been sent.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(refused)
            ) from refused

        try:
            record = gates.start(attestation=attestation, price=price)
        except CannotRunAGate as refused:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=_cannot(refused)
            ) from refused
        except NeverPresented as unpresented:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(unpresented),
            ) from unpresented
        return gate_run_started(record, bench.config)

    @app.post(GATE_RUN_APPROVAL_ROUTE)
    def answer_the_gate_runs_interrupt(
        gate_run_id: Annotated[str, PathParam()],
        request: Annotated[ApprovalRequest, Body()],
    ) -> GateRunStarted:
        """Answer the halt. On a yes the gate run goes; on anything else it does not.

        The same request body the run interrupt takes, deliberately: the answer to an
        interrupt is the consent mechanism itself, and there is exactly one of those
        in this application (ADR-0007). What is not shared is the record it answers —
        this route takes a gate run id, no route under `/runs` takes one, and a run id
        here is a `404` rather than a run somebody accidentally confirmed.

        A declined gate run spends nothing and writes nothing: the library it was
        holding goes back exactly as it was.
        """
        try:
            record = gates.answer(
                gate_run_id,
                Approval(
                    confirmed=request.confirmed,
                    identity=request.identity,
                    reason=request.reason,
                ),
            )
        except KeyError as unknown:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no gate run {gate_run_id} was started by this bench",
            ) from unknown
        except GateRunNoLongerWaiting as closed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(closed)
            ) from closed
        return gate_run_started(record, bench.config)

    @app.get(GATE_RUNS_ROUTE)
    def list_the_gate_runs_on_the_record() -> GateRuns:
        """Every gate run this bench has started, and whether it may start another.

        The availability is here rather than under `/bench` because it is a fact about
        this moment and `/bench` is a reader about the instrument — and because a
        console has to know before it draws a control, not after somebody presses one.
        Where the reference agents are absent, where there is no library to write to,
        where no adjudicating instrument is configured, or where a gate run already
        holds the library, this route says which and the screen states it.

        **Rows, and never a summary of them.** Calls spent are per layer on each row
        and there is no total, no average and no count of these gate runs. No row
        carries a decision: a pass lifted onto a list arrives without the rule it was
        decided under (ADR-0003).
        """
        return gate_runs_response(gates, gates.records())

    @app.get(GATE_RUN_ROUTE)
    def report_the_gate_runs_progress(
        gate_run_id: Annotated[str, PathParam()],
    ) -> GateRunReading:
        """Where one gate run has got to, per layer, and what it decided if it has.

        **The rule comes first and the decision after it.** A pass or a fail means
        nothing without the bar it cleared, so the declared rule is above the outcome
        on the wire as it is on the screen, and it is `DECLARED_RULE` rather than a
        copy kept for a display (ADR-0003).

        **Every per-family figure here was read off the attempts this gate run just
        made.** The three reference agents' rates, each family's `D`, its ordering and
        its verdict come from the `GateResult` the run left in memory. Nothing on this
        route parses the dated Markdown a command-line gate run writes: a screen that
        depended on the shape of the bench's own prose would break on a rewording, and
        this gate run has the figures already.

        **Progress is per layer while it is in flight.** Family, case and attempt in
        the scored layer; family, episode and turn in the adaptive one — six words for
        six things, and no field that adds the two (CONTEXT.md, ADR-0010).
        """
        record = gates.record(gate_run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"no gate run {gate_run_id} was started by this bench",
            )
        return gate_run_reading(record, bench.config.rule)

    return app
