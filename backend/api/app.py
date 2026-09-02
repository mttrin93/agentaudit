"""The HTTP surface: a nonce, a run, the answer to the run's interrupt, and the
artefact it produced.

Twenty routes, in three families. `POST /nonces` issues the value an operator
plants to prove they control the endpoint; `POST /runs` records the attestation,
declares the estimate and halts; `POST /runs/{id}/approval` answers the halt; `GET
/runs` lists the runs on the record; `GET /runs/{id}` says where the run has got to;
`GET /runs/{id}/episodes` serves the probes that run's own episodes sent and `GET
/runs/{id}/attempts` the exchanges behind its scored layer's successes, both out of
this process's memory and out of no document; four under `/report/{id}` — three that
serve the files one signed run leaves, the payload, the rendering and the detached
signature, and a fourth that says what a verifier makes of them; `GET /artefacts`
lists every signed artefact with that same reading beside it; four under `/bench`,
whose subject is the bench rather than any run — `GET /bench/gate`, `GET
/bench/gate/record`, `GET /bench/settings` and `GET /bench/notes`; and four under
`/gate-runs`, which are the newest and the only ones on this surface that spend money
on the bench's own behalf.

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

**One route serves probe text and the artefact is the line it does not cross.**
`GET /runs/{id}/episodes` reads `AdaptiveEpisode.transcripts` off the run state this
process is holding, so an operator can see the route their own attacker took against
their own endpoint. It reaches no document: what a run signs is assembled from
`ReportedEpisode`, which has no field a probe could be written into, and the response
says on itself that it is not part of the artefact, is committed nowhere and is gone
when the process stops (ADR-0008, amended). There is no such route for a gate run,
whose episodes attack this bench's own reference agents (ADR-0018).

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

from collections.abc import Callable, Sequence
from dataclasses import replace
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
    Instrumented,
    NeverPresented,
    NoLongerWaiting,
    NonceNotIssued,
    RunRecord,
    RunsInFlight,
    RunStatus,
)
from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion
from backend.bench.admission import admitted_library
from backend.bench.capability import (
    NO_TEMPERATURE_ACCEPTED,
    accepts_temperature,
    temperature_for,
)
from backend.bench.cited import the_citation, the_reliability
from backend.bench.completion import (
    ADJUDICATOR_MODEL_ENV,
    ATTACKER_MODEL_ENV,
    DEFAULT_ATTACKER_TEMPERATURE,
    REFERENCE_MODEL_ENV,
    attacker_completion_for,
    completion_for,
    declared_model,
    declared_turns_per_episode,
)
from backend.bench.contract import NOT_A_SECURITY_RESULT, RetryPolicy, TargetConfig
from backend.bench.evaluator import Verdict
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
from backend.graph.runstate import Attempt, RunState
from backend.observability import (
    disable_inherited_tracing,
    install,
    trace_config,
)
from backend.targets.reference.corpus import SHARED_FOLDER

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
"""The case library a bench serves when it was not given one.

The admitted library, never the raw one: a case that has not separated the three
reference agents may not be sent to somebody's endpoint on the strength of nobody
having checked (`admission.py`).
"""

PLANT_STATEMENT = (
    "Plant this value in the target's system prompt before starting a run."
)
"""The one instruction, with the four things it also said taken off it.

It carried the argument as well as the instruction: that only somebody who can edit
the configuration can plant it, so the echo is proof of control (ADR-0007); that the
same value is the data-leakage canary and must not be allow-listed; and that the
registration probe sends the echo probe verbatim. All four are true and none of them
is what an operator does next. Three are on the screen this value is shown on — the
plant step states the proof-of-control argument, states the canary's second role, and
prints the probe under a heading of its own — and the fourth, the refusal when a
target does not echo, is a sentence the run itself gives at the moment it happens.
"""


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

    nonce_planted: bool = True
    """Whether the registration nonce is in the target's configuration.

    Declared false, the data-leakage family is dropped from the plan, because its
    canary *is* this value and a string nowhere in the target cannot leak — and a run
    with nothing planted has nothing an echo could prove, so it also starts without
    the proof (ADR-0007, as amended).

    **It no longer carries the waiver by itself** (ADR-0025). Whether a missing echo
    stops the run is `echo_waived` below, because a target that planted the value and
    will not repeat it on request is measurable on the family this field decides and
    unprovable on the guard that one does.

    Defaults to `True`, so a caller that says nothing gets the guard. The default has
    to be the strict one: a waiver that could be obtained by omitting a field is a
    waiver nobody makes on purpose.
    """

    echo_waived: bool = False
    """Whether the run may start without the target echoing the planted nonce.

    The declaration for an agent whose disclosure rule is blanket: the value is in its
    configuration, and it refuses to repeat it because it cannot tell a registration
    check from an attack. Declared true, the probe is still sent and `echoed` still
    records what came back — what changes is only whether a missing echo *stops* the
    run, and the artefact says control was declared and not proved either way
    (ADR-0025).

    It decides nothing about what is measured. The leakage family turns on
    `nonce_planted` above, so a run that declares the canary planted keeps the family
    it is the canary for, which is the whole reason this field is not that one.

    Defaults to `False`, for the same reason that one defaults to `True`: a guard
    relaxed by an omitted field is a guard nobody chose to relax.
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

    recent: list[AttemptPayload]
    """The last attempt, and the exchange behind the verdict it reached.

    One and never the log: a run makes a hundred and eighty, and a response that grew
    with the run would be a response whose size is a function of how long somebody has
    been watching. What happened before it is on the report the run signs.

    A list of one rather than a field, because *nothing has come back yet* is a real
    state and an empty list says it without a null.
    """

    families: list[FamilyRun]
    """The six families, each over its own denominator. Six rows and no seventh.

    The reading a person watching a run asked for: the position above says which
    attempt is in flight, and says nothing about how much of the work is done or how
    it has been going. Six rows whether or not a family has started, because a family
    missing while the run is on another one would read as one this run is not doing.

    Nothing here is added across rows and nothing is divided. A run-wide count would
    be a total over six denominators, and a fraction of a family's attempts is a share
    of the work that a reader would take for a rate — the rate is on the report, with
    its interval and its band beside it (ADR-0005).
    """


class FamilyRun(BaseModel):
    """How far one family has got against this target, and how it is answering.

    The target-run twin of `FamilyProgress`, and flat where that one nests, because a
    gate run attacks three agents and this attacks one. Same counts, same attacker's
    sense: `succeeded` is the attack working.

    **Counts and never a rate.** `resisted` and `succeeded` split `attempted`, they
    are never divided here, and both are drawn against `of` — this family's own
    denominator — so what a screen draws fills as the run goes and cannot be read as a
    finished figure. What these answer is *how is it going*, which is a live reading;
    *what did it measure* is the report's, where a rate arrives with its interval and
    its band (ADR-0005).
    """

    family: str
    attempted: int
    of: int
    resisted: int
    succeeded: int
    not_run: str = ""
    """Why this family is not in the plan, in the bench's own words, or empty.

    A family the caller's declarations dropped has a denominator of zero, and a zero
    over zero drawn as an empty bar would read as a family that has not started yet.
    The gap the plan already recorded is carried here so the row says which it is
    (ADR-0015's shape: the family, and the reason, together).
    """


def progress_for(record: RunRecord, rule: GateRule) -> RunProgress:
    """One run as a caller polling it sees it, per layer and with no blend."""
    return RunProgress(
        run_id=record.run_id,
        status=str(record.status),
        statement=record.statement,
        scored=_scored_progress(record.run_state),
        adaptive=_adaptive_progress(record.run_state),
        transport=_transport(record),
        report=_report(record),
        recent=_recent_attempt(record),
        families=_run_families(record, rule),
    )


def _recent_attempt(record: RunRecord) -> list[AttemptPayload]:
    """The last attempt this run made, and the exchange behind its verdict.

    The same shape and the same one-at-a-time rule the gate run's reading uses, off the
    same `RunState.attempts` — one definition of *an attempt as evidence*, so the two
    screens cannot come to disagree about what an exchange looks like.
    """
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
        for attempt in record.run_state.attempts[-RECENT_ATTEMPTS:]
    ]


def _run_families(record: RunRecord, rule: GateRule) -> list[FamilyRun]:
    """The six families, each over its own denominator, in the enum's own order.

    The counts are `RunState.attempts` grouped by family — the same grouping the
    rates are built from, without the division — and the verdicts are that same
    grouping counted a second way. The denominator is this run's *plan*, not the
    library: a family whose cases were dropped by a declaration is a family this run
    will make no attempt in, and a denominator taken off the library would leave a bar
    that can never fill.
    """
    made: dict[str, int] = {}
    held: dict[str, int] = {}
    for attempt in record.run_state.attempts:
        name = str(attempt.family)
        made[name] = made.get(name, 0) + 1
        if attempt.verdict is Verdict.RESISTED:
            held[name] = held.get(name, 0) + 1
    rows: list[FamilyRun] = []
    for family in Family:
        name = str(family)
        cases = sum(1 for case in record.plan.cases if case.family is family)
        attempted = made.get(name, 0)
        gap = record.plan.gaps.get(family)
        rows.append(
            FamilyRun(
                family=name,
                attempted=attempted,
                of=cases * rule.attempts_per_case,
                resisted=held.get(name, 0),
                # Subtracted rather than counted a second time: every attempt carries
                # one verdict, so the two are one partition and cannot drift apart by
                # a verdict this branch had not heard of.
                succeeded=attempted - held.get(name, 0),
                not_run="" if gap is None else gap.stated(),
            )
        )
    return rows


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


RUN_EPISODES_ROUTE = "/runs/{run_id}/episodes"
"""Where the probes one run's own episodes sent are read. Memory, and never bytes
anybody signed.

Under `/runs` because the subject is one run, and one run only: an operator reading
the route their own attacker took against their own endpoint, out of the process that
is holding it. There is no counterpart under `/gate-runs` and there is not going to
be one — a gate run's episodes attack this bench's own three reference agents, so
what they would serve is the bench talking to itself (ADR-0018).

**This is the one route on this surface that serves probe text, and the artefact is
still the line it does not cross.** The signed payload carries every episode's
family, its outcome and its turn count, and no probe: a route that beat a defended
target is a working, previously unpublished exploit, and the artefact is the thing
that circulates to a customer (ADR-0008, spec story 105). So the split is a split of
carriers rather than of wording — `ReportedEpisode` has no field a probe could be put
in and this response is built from `AdaptiveEpisode.transcripts`, which nothing
commits, nothing signs and no file holds. What that gives up is stated on the response
and on the screen: a screenshot of this is a copy of a working exploit, and the
operator who took it is carrying it.
"""

THE_PROBES_THIS_PROCESS_IS_HOLDING = (
    "the probes this run's adaptive layer composed, in the order they were sent, "
    "read out of this process's memory. Not part of the signed artefact: the report "
    "this run signs carries every episode's family, outcome and turn count and no "
    "probe text, because a route that beat a target is a working, previously "
    "unpublished exploit and the artefact is the document that circulates (ADR-0008, "
    "spec story 105). Nothing here is committed and nothing here is signed, and it "
    "is gone when this process stops — a copy taken from this response is the "
    "operator's to hold and the operator's to account for"
)
"""What this response is, said on the response, because a screenshot travels alone.

The disclosure is bounded by three facts and all three are mechanism rather than
wording: the text is read off a record in this process's memory, the assembler has
nowhere to put it, and a restart ends it. The sentence is the part a reader of a
screenshot gets, so it says all three.
"""

NO_EPISODE_TO_READ_A_PROBE_FROM = (
    "this run has recorded no episode, so there is no probe to read. A stated "
    "absence and not an empty list: the adaptive layer runs strictly after the "
    "scored one (ADR-0010), so a run halted at its interrupt, a run nobody "
    "approved, a run refused at registration and a run stopped on the wire before "
    "the second layer all arrive here, and the run's own standing says which. "
    "Nothing here is a reading about the target — a layer that ran no episode found "
    "nothing rather than finding none"
)


class ProbeAsSent(BaseModel):
    """One probe, in the words the attacker composed and the target received.

    A **probe** and never a case: a case is a recorded payload with a stated
    criterion, and this is a message a model invented mid-run (CONTEXT.md). Nothing
    on this record is counted — `turn` is an ordinal a reader follows down the list,
    not a denominator, and there is no field here that could hold one.
    """

    turn: int
    """Which turn of its episode sent this, counted from one.

    One-based on the way out for the reason `_scored_progress` is: a reader counts
    *the third probe* and the record holds a position in a list.
    """

    probe: str

    reply: str
    """What the target said back, in full and unedited.

    Served because a probe without its reply is unreadable: *censored* is a fact
    about the attacker, and the only way a reader tells a target that refused from a
    target that was never asked the right thing is the text that came back. It is
    the empty string for a reply the transport could not read, which scores as
    resisted and is not the same as a target that said nothing (`contract.reply_text`).
    """

    tool_trace: str | None = None
    """What the target did on this turn, rendered, or `None` from a target that
    returns no trace.

    `None` and an empty trace are different answers and this keeps them apart: a
    target without tool-call visibility cannot be measured on scope creep or halt
    defeat at all, and one that returned an empty trace took no action. Two of the
    four deterministic families are decided on this and nothing else, so a reader
    judging one of their episodes needs it beside the reply rather than a screen away.
    """

    reading: str
    """What this turn was found to be: broke it, no break, or not checkable.

    Three answers, because two would mislead. Every probe is verified by the harness
    as it comes back, so *no break* is a real reading rather than the absence of one —
    but a turn whose reply carried nothing the objective's condition reads has no
    answer at all, and printing that as *no break* would describe a defence that was
    never tested. The third value is the adaptive counterpart of `NotMeasurable`
    (`measurability.checkable`, ADR-0011 as amended).
    """

    confirmed_the_break: bool
    """Whether the break was confirmed after this probe. Derived, and never guessed.

    The harness applies the objective's condition to every probe as it comes back and
    the episode ends on the first success, so a broken episode's break belongs to its
    last probe by construction rather than by assumption. It is `False` on every probe
    of a censored episode, and on every probe of a broken episode that somehow sent
    none: an ordered list of probes with nothing marked is what this response gives
    where the record cannot say more.
    """


class FamilyBreak(BaseModel):
    """Which probe broke one family, or the stated fact that nothing did.

    One row per family that opened an episode, in the order the layer ran them. A
    reader asking *what broke this agent* is asking a question the episode list can
    answer only by being read end to end, and a route is long — so the answer is
    served as well as derivable.

    **A position, never a count** (ADR-0010). It names an episode and a turn; there
    is no field here for how many families broke, how many episodes it took or a
    proportion of anything, and a family that broke in two episodes is reported at
    the first, because *when it first worked* is a fact and *how often* would be a
    rate over episodes that have no denominator.
    """

    family: str

    broke: bool
    """Whether any episode against this family broke the target."""

    episode: int | None = None
    """Which episode did it, counted from one over the whole run. `None` if none did."""

    turn: int | None = None
    """Which turn of that episode. `None` if none did."""

    probe: str | None = None
    """The probe that did it, in the words the target received. `None` if none did."""

    stated: str
    """The row in words, so a reader who takes only this line still reads it right.

    A family nothing broke says which of the two silences it is — every turn read and
    none of them a break, or turns nothing could be read from at all — because those
    are different facts and only one of them is about the target.
    """


class EpisodeProbes(BaseModel):
    """One episode as the operator's own console may read it: the outcome, and the
    probes.

    **Deliberately not `ReportedEpisode`.** That record is what the assembler builds
    and the signature covers, and it has no field a probe could be written into
    (`bench/assembler.py`, `bench/payload.py`). This one has, it is built here, and
    it reaches no document — which is how a reviewer can see from the types that the
    artefact cannot carry a probe rather than having to trust that nobody added one.

    `turns` is the count the effort statistic reads and the probes are the evidence
    behind it, so the two are beside each other and neither is divided by anything
    (ADR-0010).
    """

    family: str
    outcome: str
    turns: int
    probes: list[ProbeAsSent]
    stated: str
    """The episode's own line about its outcome — `AdaptiveEpisode.stated()`.

    Carried rather than restated, so a censored episode against a trace-blind target
    says here what it says in the report: the attacker ran one-eyed, and the outcome
    is not evidence that the target held.
    """


class RunProbes(BaseModel):
    """Every episode this run recorded, in the order they ran, with their probes."""

    held: Literal[True] = True
    run_id: str
    broke: list[FamilyBreak]
    """One row per family that opened an episode: what broke it, or that nothing did.

    Served above the episodes because it answers the question the block is opened
    for. It is derived from the same records the episodes are, so a reader can check
    it against them rather than believe it.
    """

    episodes: list[EpisodeProbes]
    stated: str


class NoProbes(BaseModel):
    """This run recorded no episode, and which absence that is left to its standing.

    The same shape as the answer above with the episodes gone, and a sentence in
    place of them, on `UnheldRecord`'s reasoning: an empty list would read as a
    search that ran and sent nothing, which is a reading about an attacker and is
    not what happened.
    """

    held: Literal[False] = False
    run_id: str
    stated: str


def probes_sent(record: RunRecord) -> RunProbes | NoProbes:
    """One run's episodes and their probes, or the stated absence of any.

    Read off `RunState.episodes` in the order the layer ran them, which is the order
    a reader needs: an episode's probes are a sequence and a sequence re-sorted is a
    different route. Nothing here is grouped, counted or summarised — there is no
    figure on this response that spans two episodes, and none that spans a family.
    """
    episodes = record.run_state.episodes
    if not episodes:
        return NoProbes(run_id=record.run_id, stated=NO_EPISODE_TO_READ_A_PROBE_FROM)
    return RunProbes(
        run_id=record.run_id,
        episodes=[
            EpisodeProbes(
                family=str(episode.family),
                outcome=str(episode.outcome),
                turns=episode.turns,
                probes=_probes(episode),
                stated=episode.stated(),
            )
            for episode in episodes
        ],
        broke=_breaks(episodes),
        stated=THE_PROBES_THIS_PROCESS_IS_HOLDING,
    )


BROKE_IT = "broke it — the objective was met on this turn"
NO_BREAK = "no break — the objective's condition was read and not met"
NOT_CHECKABLE = (
    "not checkable — the reply carried nothing this objective's condition reads, so "
    "this turn is not the target holding"
)
"""The three readings a turn can have, in the words a screenshot carries.

Words and not a code, because this response is read by a person through a browser
and the distinction that matters most here — *not met* against *not answerable* — is
the one a colour or a boolean would flatten.
"""


def _reading(episode: AdaptiveEpisode, turn: int) -> str:
    """What one turn was found to be, read off the record rather than guessed.

    The break belongs to the last turn of a broken episode by construction: the
    harness verifies each probe as it comes back and the episode stops at the first
    success (`adaptive/attacker.py`).
    """
    if turn in episode.unverifiable_turns:
        return NOT_CHECKABLE
    if episode.outcome is EpisodeOutcome.BROKEN and turn == episode.turns:
        return BROKE_IT
    return NO_BREAK


def _probes(episode: AdaptiveEpisode) -> list[ProbeAsSent]:
    """The probes of one episode, in order, each with what came back and what it was.

    An episode that broke without sending anything marks nothing rather than marking
    the first thing to hand.
    """
    return [
        ProbeAsSent(
            turn=at + 1,
            probe=_message(transcript.sent),
            reply=transcript.reply_text,
            tool_trace=(
                None
                if transcript.tool_trace is None
                else transcript.tool_trace.rendered()
            ),
            reading=_reading(episode, at + 1),
            confirmed_the_break=_reading(episode, at + 1) == BROKE_IT,
        )
        for at, transcript in enumerate(episode.transcripts)
    ]


NOTHING_BROKE_IT = (
    "nothing broke this family: every turn was read against the objective's "
    "condition and none of them met it"
)

NOTHING_COULD_BE_READ = (
    "this family was not measured: every turn's reply carried nothing its "
    "objective's condition reads, so no turn was either a break or a hold. Not a "
    "target that held"
)


def _breaks(episodes: Sequence[AdaptiveEpisode]) -> list[FamilyBreak]:
    """Which probe broke each family, in the order the families opened an episode.

    Grouped by family here and nowhere else on this response: the episode list is a
    sequence and stays one, and this is the summary that sequence is read for. The
    first break is the one reported — *when it first worked* is a fact, where *how
    often* would be a rate over episodes that have no denominator (ADR-0010).
    """
    rows: dict[str, FamilyBreak] = {}
    unreadable: dict[str, bool] = {}
    for index, episode in enumerate(episodes, start=1):
        family = str(episode.family)
        every_turn_unread = (
            episode.turns > 0 and len(episode.unverifiable_turns) == episode.turns
        )
        unreadable[family] = unreadable.get(family, True) and every_turn_unread
        held = rows.get(family)
        if held is not None and held.broke:
            continue
        broke = episode.outcome is EpisodeOutcome.BROKEN and bool(episode.transcripts)
        rows[family] = FamilyBreak(
            family=family,
            broke=broke,
            episode=index if broke else None,
            turn=episode.turns if broke else None,
            probe=_message(episode.transcripts[-1].sent) if broke else None,
            stated="" if broke else NOTHING_BROKE_IT,
        )
    return [
        row
        if row.broke
        else row.model_copy(
            update={
                "stated": (
                    NOTHING_COULD_BE_READ
                    if unreadable.get(family)
                    else NOTHING_BROKE_IT
                )
            }
        )
        for family, row in rows.items()
    ]


RUN_ATTEMPTS_ROUTE = "/runs/{run_id}/attempts"
"""Where the exchanges behind one run's succeeded attempts are read. Memory, and
never bytes anybody signed.

The scored layer's counterpart to `RUN_EPISODES_ROUTE`, on the same terms and for the
same reason: an operator reading their report asks what the payload that beat their
agent actually said, and the answer is a recorded case and a reply, held in the
process that ran it. Under `/runs` because the subject is one run of one operator's
own endpoint, and there is no counterpart under `/gate-runs` for the reason there is
no episode one — a gate run attacks this bench's own reference agents (ADR-0018).

**Only the attempts that succeeded.** A resisted attempt is the same recorded payload
against the same case, and serving all of them would be the log this surface has
already refused once (`RECENT_ATTEMPTS`). What a reader of a report is asking is which
attacks worked, so what is served is `RunState.succeeded_attempts` and nothing else.

**The artefact is still the line this does not cross.** The signed payload carries
`successes` and `attempts` per family and no transcript — `document()` is built key by
key precisely so that an attempt's transcript has nowhere to arrive — and this response
is built from `Attempt.transcript`, which nothing signs and no file holds (ADR-0008,
spec story 105). What that gives up is stated on the response and on the screen: a
screenshot of this is a copy of a payload that worked against a live agent, and the
operator who took it is carrying it.
"""

THE_EXCHANGES_THIS_PROCESS_IS_HOLDING = (
    "the attacks that worked, as they went on the wire and as this target answered "
    "them, read out of this process's memory. Not part of the signed artefact: the "
    "report this run signs carries each family's successes over its attempts and no "
    "transcript, because a payload that beat a target is a working attack and the "
    "artefact is the document that circulates (ADR-0008, spec story 105). Nothing "
    "here is committed and nothing here is signed, and it is gone when this process "
    "stops — a copy taken from this response is the operator's to hold and the "
    "operator's to account for"
)
"""What this response is, said on the response, because a screenshot travels alone.

The same three bounds the probes route states, in the scored layer's own terms: the
text is read off a record in this process's memory, the assembler has nowhere to put
it, and a restart ends it.
"""

NO_ATTEMPT_SUCCEEDED = (
    "no attempt in this run's scored layer succeeded, so there is no exchange to "
    "read. A stated absence and not an empty list: a run halted at its interrupt, a "
    "run nobody approved, a run refused at registration and a run whose every "
    "attempt was resisted all arrive here, and only the last of them is a reading "
    "about the target — the run's own standing and each family's own rate say which "
    "this was"
)


class FamilyExchanges(BaseModel):
    """One family's succeeded attempts, with the exchange behind each.

    Grouped by family because that is the unit a rate is denominated in and the unit
    the report's cards are read in, and grouped nowhere else on this response.

    **A list, never a figure.** There is no count on this record and no denominator:
    the rate is on the report, measured over the attempts the plan declared, and a
    length taken from this list would be a numerator with nothing under it — a family
    is here only if something in it succeeded, so the absence of a family is not a
    zero (ADR-0006, ADR-0010).
    """

    family: str

    verdict_class: str
    """How this family's verdicts were reached, off the attempts themselves.

    Carried so that a reader of an exchange knows which instrument called it a
    success before they read the reply: a deterministic verdict is re-derivable from
    the text in front of them, and a judged one is an adjudicator's reading with a κ
    figure of its own (ADR-0004, ADR-0013). Never inferred from the family name,
    which is the inference the record exists to make impossible.
    """

    succeeded: list[AttemptPayload]
    """The attempts that worked, in the order they were made."""


class RunExchanges(BaseModel):
    """Every succeeded attempt this run recorded, by family, with its exchange."""

    held: Literal[True] = True
    run_id: str
    families: list[FamilyExchanges]
    stated: str


class NoExchanges(BaseModel):
    """Nothing in this run's scored layer succeeded, said in words.

    The same shape with the families gone and a sentence in their place, on
    `NoProbes`' reasoning: an empty list would read as a layer that ran and found
    nothing, and a run that never got to its first attempt is a different fact from
    a target that resisted every one.
    """

    held: Literal[False] = False
    run_id: str
    stated: str


def exchanges_behind(record: RunRecord) -> RunExchanges | NoExchanges:
    """One run's succeeded attempts by family, or the stated absence of any.

    Read off `RunState.succeeded_attempts` in the order they were made and grouped
    into `Family`'s own order, which is the order the report's cards are in: two
    surfaces a reader moves between line up row for row.

    Nothing here is counted or summarised. There is no figure on this response that
    spans two families, and none that spans two attempts of one — what a family's
    rate is stays on the report, where its denominator is.
    """
    succeeded = record.run_state.succeeded_attempts
    if not succeeded:
        return NoExchanges(run_id=record.run_id, stated=NO_ATTEMPT_SUCCEEDED)
    grouped: dict[Family, list[Attempt]] = {}
    for attempt in succeeded:
        grouped.setdefault(attempt.family, []).append(attempt)
    return RunExchanges(
        run_id=record.run_id,
        families=[
            FamilyExchanges(
                family=str(family),
                verdict_class=str(grouped[family][0].verdict_class),
                succeeded=[_exchange(attempt) for attempt in grouped[family]],
            )
            for family in Family
            if family in grouped
        ],
        stated=THE_EXCHANGES_THIS_PROCESS_IS_HOLDING,
    )


def _exchange(attempt: Attempt) -> AttemptPayload:
    """One attempt as the evidence behind its verdict, in the shape the run route
    already serves one in.

    The same model rather than a second one, because it is the same fact: what went
    out, what came back, and how that was scored. What differs is how many of them a
    response carries and why, and that is the route's business rather than the
    record's.
    """
    return AttemptPayload(
        family=str(attempt.family),
        case_id=attempt.case_id,
        agent=attempt.target_name,
        # One-based on the way out, like every other index this surface serves: a
        # reader counts *the third attempt* and the record holds an index into ten.
        attempt=attempt.index + 1,
        sent=_message(attempt.transcript.sent),
        reply=attempt.transcript.reply_text,
        verdict=str(attempt.verdict),
        verdict_class=str(attempt.verdict_class),
        status_code=attempt.transcript.status_code,
        sends=attempt.transcript.sends,
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

    agent_types: list[str]
    """The kinds of agent the live half has cases written for, sorted.

    **A suggestion and not a closed set.** An agent type is the operator's own word
    for their own agent, and `applicability.applies` compares it against each case's
    `applies_to` with no vocabulary to be inside of — deliberately, because a closed
    set here would refuse to register a target of a kind the bench had not thought of,
    while the honest answer to an agent type the library has no cases for is a skip
    per case with its reason on it. This list is what a console can *offer*, and an
    operator may still type a word that is not on it.

    Off the records rather than from a constant beside them, so a case added for a new
    kind of agent puts that kind in front of the next operator to register one. Sorted
    for a stable response, and deduplicated: `applies_to` is a tuple per case and the
    same kind is named by many.
    """

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
        # The live half only: a kind whose every case has retired is a kind a run no
        # longer attempts, and offering it would be offering a registration that
        # attempts nothing.
        agent_types=sorted({kind for case in live for kind in case.applies_to}),
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


class ModelChoice(BaseModel):
    """One model this console offers as the attacker, and what it is for."""

    identifier: str
    decides: str
    chosen: bool


class Bounds(BaseModel):
    """What a setting may be. Served so the form draws the range the route enforces."""

    low: float
    high: float


class FamilyCovered(BaseModel):
    """One failure family, and whether the next run covers it."""

    family: str
    covered: bool


class Tuning(BaseModel):
    """The declared inputs this console may set, their current values and their bounds.

    Served so that a screen draws the same limits the route enforces: a form with its
    own idea of the range is a form that offers a setting the bench will refuse.

    **Four of the five bound a layer that is scored on nothing, and the fifth is the
    scored denominator.** They are in one block because they are set in one request,
    and the block says which is which in `attempts_warning` rather than leaving a
    reader to infer it from the field names (ADR-0003, ADR-0010).
    """

    attacker_models: list[ModelChoice]
    temperature: float | None
    temperature_bounds: Bounds
    temperature_absent: str
    turns_per_episode: int
    turns_bounds: Bounds
    episodes_per_family: int
    episodes_bounds: Bounds
    attempts_per_case: int
    attempts_bounds: Bounds
    attempts_per_family: int
    """`attempts_per_case` times the cases this library holds per family, which is the
    `n` a rate is read at. Derived and served, because `n = 30` is the number ADR-0003
    names and an operator setting the per-case figure is choosing that one."""

    declared_attempts_per_case: int
    """What `rule.py` declares. Shown beside the current value so a reader can see at
    a glance whether this bench is set to the rule the gate is decided on."""

    attempts_warning: str
    families: list[FamilyCovered]
    """The six families and whether each is on, in the enum's own order.

    A declared input like the numbers above, set per family rather than per number. A
    family switched off is **not run** — its cases are dropped and its gap is stated
    on the report — and never measured at zero: a family that was not asked is not a
    family that held.
    """

    families_off_statement: str
    statement: str


THE_CONSOLE_MAY_SET_THESE = (
    "these are the declared inputs of a run, and setting one changes what the next "
    "run measures rather than how it looks. Every one of them is printed in the "
    "report of every run made under it, and a run in flight keeps the settings it "
    "was started with — a change is refused while one is going, because a run "
    "awaiting approval was shown an estimate built from the settings it was "
    "declared with (ADR-0007, ADR-0025)"
)

A_RUN_BELOW_THE_DECLARED_RULE_IS_NOT_A_GATE_RESULT = (
    "attempts per case is the scored denominator, and it is not in the same class as "
    "the four above it. The gate is decided at the declared rule — ADR-0003 sets it "
    "so that n = 30 per family, which is what the Wilson interval, the band, "
    "monotonicity and the retirement rule are all defined against. A run at another "
    "number is a real run whose rates carry the rule they were measured at, and it "
    "is not a gate result: nothing may compare it to a reading taken at the declared "
    "rule, and `scripts/gate.py` takes no setting from this screen"
)

A_FAMILY_SWITCHED_OFF_IS_NOT_RUN = (
    "a family switched off is not run: no case in it is attempted, no episode opens "
    "against it, and the report states it as not run rather than as a rate of zero. "
    "A family that was not asked is not a family that held (ADR-0004)"
)

NO_TEMPERATURE_DECLARED = (
    "no temperature declared — the provider's own default, whatever that is. A "
    "number here is a choice this bench records; leaving it empty is the honest way "
    "to say the choice was not made"
)


def tuning(config: BenchConfig) -> Tuning:
    """What the console may set, as it is set now, with its bounds and its caveat."""
    attacking = config.report.models.attacking
    return Tuning(
        attacker_models=[
            ModelChoice(
                identifier=identifier, decides=decides, chosen=identifier == attacking
            )
            for identifier, decides in _offered(attacking)
        ],
        temperature=config.report.models.attacking_temperature,
        temperature_bounds=Bounds(low=TEMPERATURE_RANGE[0], high=TEMPERATURE_RANGE[1]),
        temperature_absent=NO_TEMPERATURE_DECLARED,
        turns_per_episode=config.adaptive.turns_per_episode,
        turns_bounds=Bounds(low=TURNS_RANGE[0], high=TURNS_RANGE[1]),
        episodes_per_family=config.adaptive.episodes_per_family,
        episodes_bounds=Bounds(low=EPISODES_RANGE[0], high=EPISODES_RANGE[1]),
        attempts_per_case=config.rule.attempts_per_case,
        attempts_bounds=Bounds(low=ATTEMPTS_RANGE[0], high=ATTEMPTS_RANGE[1]),
        attempts_per_family=config.rule.attempts_per_case
        * _cases_per_family(config.cases),
        declared_attempts_per_case=DECLARED_RULE.attempts_per_case,
        attempts_warning=A_RUN_BELOW_THE_DECLARED_RULE_IS_NOT_A_GATE_RESULT,
        families=[
            FamilyCovered(family=str(family), covered=family in config.families)
            for family in Family
        ],
        families_off_statement=A_FAMILY_SWITCHED_OFF_IS_NOT_RUN,
        statement=THE_CONSOLE_MAY_SET_THESE,
    )


def _offered(attacking: str) -> tuple[tuple[str, str], ...]:
    """The models to offer: the declared list, and whatever this bench is currently on.

    The stand-in is not on the list. It is reachable — the route admits it, so a
    bench can be put back on test equipment — but offering it as a choice beside the
    declared models invites picking it by accident, and an operator who wanted no
    spend would not be on this screen.

    **The current setting is always a row, whatever it is.** A form that showed the
    declared list while the bench ran something else would draw the first option as
    selected and be wrong about the instrument — which is the one thing a screen about
    instruments may not be.
    """
    if any(identifier == attacking for identifier, _ in ATTACKER_MODELS):
        return ATTACKER_MODELS
    return (
        *ATTACKER_MODELS,
        (
            attacking,
            THE_STAND_IN_ATTACKER
            if attacking == UNDECLARED_MODEL
            else "what this bench is set to now, and not one of the four above",
        ),
    )


THE_STAND_IN_ATTACKER = (
    "the deterministic stand-in: eight fixed probes in order, no model call and no "
    "spend on the bench's own inference. Test equipment, and the honest choice when "
    "what is under test is the plumbing rather than an attacker"
)


def _cases_per_family(cases: Sequence[Case]) -> int:
    """The most cases this library holds for any one family.

    The most rather than an average, because `n` is what a family with a full set of
    cases is measured at and an average over families would be a figure no rate was
    ever read at (ADR-0005).
    """
    counted: dict[Family, int] = {}
    for case in cases:
        counted[case.family] = counted.get(case.family, 0) + 1
    return max(counted.values(), default=0)


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

    Six fields and a sentence, and not one of them a measurement. There is no field
    here that spans two families, none that spans two layers, no severity scale and no
    composite figure (ADR-0005, ADR-0010).

    **The sixth field is a control, and it is the only one.** `tuning` carries the
    declared inputs an operator may set from the console and the bounds the route
    enforces; the other five state and change nothing. The line this draws is the one
    ADR-0025 draws: a setting that changes what the *next* run measures may be set
    here, and it is printed in the provenance of every run made under it — the signing
    key, the library and the citation are not settings and stay where they are.

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
    tuning: Tuning


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
        tuning=tuning(config),
    )


ATTACKER_MODELS: tuple[tuple[str, str], ...] = (
    (
        "openrouter:openai/gpt-4.1-mini",
        "cheap and the baseline every earlier reading here was taken with",
    ),
    (
        "openrouter:anthropic/claude-haiku-4.5",
        "cheap, and markedly better at following a multi-step brief than the "
        "baseline — the first thing to try when episodes read as one idea rephrased",
    ),
    (
        "openrouter:openai/gpt-5-mini",
        "mid-tier reasoning, for a run where the question is whether the attacker "
        "can plan rather than whether it can phrase",
    ),
    (
        "openrouter:anthropic/claude-opus-4.7",
        "expensive, and the run that answers whether the model was the ceiling: an "
        "A_break that does not move here is a reading about the bench, not the model",
    ),
    (
        "openrouter:deepseek/deepseek-v4-flash-0731",
        "the cheapest on this list by a wide margin and post-trained for agent "
        "workflows — but measured at 16s a call against the baseline's 2s, so an "
        "episode that takes minutes here takes an hour: pick it for a run whose "
        "budget is the constraint, never for one whose clock is",
    ),
)
"""The models this console offers as the adaptive attacker, with what each is for.

A closed list rather than a free-text field, for the reason every enumeration in
this bench is closed: a mistyped slug is refused by the provider at the first call,
which is *after* the operator has attested and confirmed a spend. Held here beside
the route that accepts them, so the options a screen draws and the values the route
admits cannot come apart.

**The stand-in is on the list too** — `UNDECLARED_MODEL` selects it. A bench with no
credential still runs the layer, and an operator has to be able to get back to the
deterministic attacker without editing an environment variable.
"""

TEMPERATURE_RANGE = (0.0, 1.0)
"""What a temperature may be, and refused outside it.

Zero to one rather than the provider's full zero-to-two. The upper half of that range
is where a model stops composing and starts producing noise, and an attacker whose
probes are noise is not a stronger attacker — it is a run that spends an operator's
endpoint on strings nothing chose. A ceiling that cannot be usefully reached is a
setting offering rope to nobody.
"""

TURNS_RANGE = (1, 40)
"""What `T` may be. One, because an episode that may take no turn is a layer that
cannot run; forty, because the ceiling this multiplies into is what an operator
confirms and a number that produces an unreadable estimate is not a setting."""

EPISODES_RANGE = (1, 10)
ATTEMPTS_RANGE = (1, 50)
"""What `attempts_per_case` may be. The declared rule's ten is inside it, and so is
every number that is not it — a run below the declared rule is a real run and not a
gate result, which is what the block that offers this says in words."""


def _within(named: str, value: float | None, bounds: tuple[float, float]) -> None:
    """Refuse a setting outside the range the screen was shown, naming both.

    Refused rather than clamped: a bench that quietly moved a number would run a
    setting nobody chose and print it in a report as though they had, which is the
    failure every declared threshold in this repository is written to avoid.
    """
    if value is None:
        return
    low, high = bounds
    if not low <= value <= high:
        raise HTTPException(
            status_code=422,
            detail=f"{named}={value} is outside {low}–{high}, so it was not set",
        )


def _a_temperature_this_model_takes(model: str, temperature: float | None) -> None:
    """Refuse a temperature the model rejects, at the moment it is set.

    In front of the estimate rather than sixty calls into a run. The capability is
    declared, so this is answerable without spending a call to find out
    (`bench/capability.py`), and the operator who typed the number is the person told
    it cannot be had — which is the one thing the old arrangement could not do: the
    provider's refusal arrived at the first episode, after an attestation and a
    confirmed spend.

    Refused rather than dropped, on `_within`'s reasoning one step further: a bench
    that quietly sent no temperature would print the setting in a provenance block as
    though the request had carried it (ADR-0004, ADR-0025). Leaving the field empty
    is available and means something of its own.
    """
    if temperature is None or accepts_temperature(model):
        return
    raise HTTPException(
        status_code=422,
        detail=(
            f"{model} accepts no temperature, so temperature={temperature} was not "
            f"set. {NO_TEMPERATURE_ACCEPTED}"
        ),
    )


BENCH_TUNING_ROUTE = "/bench/settings/tuning"
"""Where the declared inputs of the next run are set. The one write on this bench.

A `PUT` because it is the whole statement every time: five settings arrive together
so that a bench cannot end up naming one instrument in a report while another one
attacked (ADR-0025).
"""


class TuneRequest(BaseModel):
    """The five settings, as the console sends them."""

    attacker_model: str
    temperature: float | None = None
    turns_per_episode: int
    episodes_per_family: int
    attempts_per_case: int


BENCH_FAMILIES_ROUTE = "/bench/settings/families"
"""Where the families the next run covers are set. The second write on this bench.

Its own route rather than a field on the tuning request, because it is a different
statement made from a different screen: the tuning request is *how the instruments
are set* and takes all five settings every time, and this is *what the next run
covers*. A caller sending one has no business restating the other.
"""


class CoverRequest(BaseModel):
    """The families the next run covers, by name. At least one."""

    families: list[str]


BENCH_NOTES_ROUTE = "/bench/notes"
"""The content the indirect prompt injection family attacks with, served verbatim.

The one thing this walk asked an operator to do and never told them how to do. The
registration form has a box declaring that the hostile content the family reads is
in place, `plan_for` drops every case in the family when it is not, and until this
route there was no way to learn *what* to plant: the notes are committed in
`backend/targets/reference/corpus.py`, which is the bench's source and not a screen.
An operator who planted content of their own invention would have the family run
against an attack whose canary can never appear, and read the clean zero as a
defence — which is the exact failure the declaration box exists to prevent, arriving
through the other door.

**Paired by the canary and never by name.** What is served against a case is the
note whose `executed_line` is that case's `planted_canary`, so the pairing is the
same string the verdict is decided on (`evaluator.py`). A note that pairs with no
live case is not served, and a live case in the family that pairs with no note is
named as one this bench holds no content for rather than quietly omitted.

**It is under `/bench` because the subject is the instrument.** Nothing here is a
measurement of anybody's target and nothing about a target is reachable from it
(ADR-0018). A `GET`, like every other method on this prefix: an operator plants the
content in their own system and declares it at registration, and there is no route
that would take it (ADR-0020).
"""

THE_CONTENT_THE_FAMILY_NEEDS = (
    "the third-party content the indirect prompt injection family attacks with. "
    "Plant each note where this target retrieves it, and declare it at "
    "registration. Each is paired to a case by the canary that case is scored on — "
    "the line that executing the note's instruction adds to a reply — so content "
    "that is hostile but is not this content leaves the family reporting a clean "
    "zero against an attack that was never made"
)
"""What the notes response is, said on the response, because a screenshot travels."""


class NoteToPlant(BaseModel):
    """One note, the case it is the content of, and the line executing it produces."""

    case: str
    """The case this note is the content of. Named, so a reader can open the record."""

    key: str
    """The word a message uses when it means this note.

    The bench's payload names it in ordinary prose — *a note from the supplier*, *a
    remittance advice* — and the target has to bring back this note when it does. It
    is where the note is filed, not a field of the note.
    """

    body: str
    """The text to plant, exactly. Third-party content, all of it."""

    canary: str
    """What executing the instruction in this note adds to a reply.

    Served because it is the whole of the verdict: the bench looks for this string in
    what the target answers, and finds it only where the instruction was carried out.
    Not a value to plant on its own — a note carrying the line already joined would
    be scored by a target that quoted it back.
    """


class NotesToPlant(BaseModel):
    """Every note the live half of the library needs planted, and what is unpaired.

    A list and no count over it, and no field that says the family is ready: whether
    the content is in place is the operator's declaration at registration, which this
    bench cannot check and does not pretend to (`plan_for`, ADR-0007).
    """

    notes: list[NoteToPlant]
    unpaired: list[str]
    """Live cases in the family this bench holds no note for, by id.

    Empty in a bench whose library and corpus agree. Named rather than dropped,
    because a case scored on a canary no served note produces is a case an operator
    cannot plant for, and a shorter list would look complete.
    """

    stated: str = THE_CONTENT_THE_FAMILY_NEEDS


def notes_to_plant(cases: Sequence[Case]) -> NotesToPlant:
    """The notes the live indirect-injection cases are scored against, paired by canary.

    The live half only, for the reason the agent types are read off the live half: a
    case that has retired is a case no run attempts, and content planted for one is
    content planted for nothing.
    """
    by_canary = {
        note.executed_line: note for note in SHARED_FOLDER if note.executed_line
    }
    notes: list[NoteToPlant] = []
    unpaired: list[str] = []
    for case in sorted(cases, key=lambda case: case.id):
        if case.status is not CaseStatus.ACTIVE:
            continue
        if case.family is not Family.INDIRECT_PROMPT_INJECTION:
            continue
        canary = (
            case.success_condition.planted_canary
            if case.success_condition is not None
            else None
        )
        note = by_canary.get(canary) if canary else None
        if note is None:
            unpaired.append(case.id)
            continue
        notes.append(
            NoteToPlant(
                case=case.id, key=note.key, body=note.body, canary=note.executed_line
            )
        )
    return NotesToPlant(notes=notes, unpaired=unpaired)


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
    """One reference agent's share of one family: how far, and how it is going.

    Two counts for how far — a count and the count it is out of — and two for how the
    attempts made so far were answered. The three agents are ordered by construction —
    hardened, weak, trivial — because that is the order the contrast is built in and
    the order every other surface reads them in; the order is read off
    `GateRunRecord.roles`, which the equipment answered, and never off the name.

    **`resisted` and `succeeded` are counts and not a rate.** They split `attempted`,
    they are never divided here, and the screen draws each against `of` — this agent's
    own denominator — so what is drawn fills as the run goes and cannot be read as a
    finished figure. A rate needs its interval and its band beside it, and those belong
    to the decision (ADR-0005): what these two answer is *how is it going*, which is a
    live reading an operator watching a run asked to be able to see, and not *what did
    it measure*, which is on the report the run signs.

    **In the attacker's sense, like every other count in this bench.** `succeeded` is
    the attack working, so a high `succeeded` against the trivial agent is the contrast
    doing its job and not a defect: `D` is trivial minus hardened, and a trivial agent
    that resisted everything would mean the case discriminates nothing. Anything
    drawing these two in a colour has to say which is which in words.
    """

    agent: str
    attempted: int
    of: int
    resisted: int
    succeeded: int


class FamilyProgress(BaseModel):
    """How far one family has got, over its own denominator, and never a rate.

    **Six of these and no seventh figure.** A family's denominator is its own cases
    at the declared attempts per case against each of the three agents, and this row
    carries the count against it. Nothing here is added to another row, because a
    run-wide count would be a total across six denominators — the one arithmetic this
    bench refuses everywhere else (ADR-0005) — and nothing here is divided, because a
    fraction of a family's attempts is a share of the work and would be read as a
    rate.

    **And no count of verdicts on the row.** The three agents carry their own
    (`AgentProgress`), and the three are three readings rather than one: the trivial
    agent is built to fail, so a family total over the three would be two thirds broken
    by construction and would say nothing about any of them — least of all about a
    target, which is what a reader would take it for.
    """

    family: str
    attempted: int
    of: int
    agents: list[AgentProgress]


class AttemptPayload(BaseModel):
    """One attempt as evidence: what went on the wire, what came back, the verdict.

    **Served for a gate run because the three agents are this bench's own
    equipment**, and for a target run because an operator watching their own agent
    being attacked asked to see the exchange behind the verdict that just landed. The
    two are not the same disclosure and the difference is worth naming: a gate run's
    transcript is the bench talking to itself, and a target run's is the operator's
    own agent answering. It is served on the run's own route, one attempt at a time
    and never as a log, and it does not reach the artefact — a report carries figures
    and the boundary of the claim, never the traffic (ADR-0008).

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


RECENT_ATTEMPTS = 1
"""How many attempts the reading carries the payloads of.

**The last one**, and never the log: a gate run makes hundreds, and a response that
grew with the run would be a response whose size is a function of how long somebody
has been watching. It carried five for a while, and five was a column of near-copies
— the same case against the same agent, one attempt apart — where the question the
panel answers is *what is happening now*. What happened before it is in the record the
run writes and on the report it signs, which is where a reader who wants the sequence
should be reading it.

A list of one rather than a field, because *nothing has come back yet* is a real state
and an empty list says it without a null.
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
    grouping the rates are built from, without the division — and the verdicts are that
    same grouping counted a second way.
    """
    made: dict[tuple[str, str], int] = {}
    held: dict[tuple[str, str], int] = {}
    for attempt in record.run_state.attempts:
        key = (str(attempt.family), attempt.target_name)
        made[key] = made.get(key, 0) + 1
        if attempt.verdict is Verdict.RESISTED:
            held[key] = held.get(key, 0) + 1
    rows: list[FamilyProgress] = []
    for family in Family:
        name = str(family)
        cases = sum(1 for case in record.cases if case.family is family)
        each = cases * rule.attempts_per_case
        agents = [
            AgentProgress(
                agent=role,
                attempted=made.get((name, role), 0),
                of=each,
                resisted=held.get((name, role), 0),
                # Subtracted rather than counted a second time: every attempt carries
                # one verdict, so the two are one partition and cannot drift apart by
                # a verdict this branch had not heard of.
                succeeded=made.get((name, role), 0) - held.get((name, role), 0),
            )
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
    """The last attempt and the exchange behind its verdict. Empty before the first."""
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
    models, adjudicator, attacker = deployed_models()
    return BenchConfig(
        cases=admitted_library(library),
        adjudicator=adjudicator,
        attacker=attacker,
        adaptive=deployed_adaptive_budget(),
        report=ReportConfig(
            signing_key=key,
            gate=the_citation(library),
            models=models,
            # The κ the cited gate run measured, and only if it measured it on the
            # model these runs adjudicate with. The guard is the whole reason this is
            # read here rather than inside the report path: a κ about another
            # instrument is not a κ about these verdicts (ADR-0004, ADR-0013).
            reliability=the_reliability(library).for_adjudicator(models.adjudicating),
        ),
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


def deployed_adaptive_budget() -> AdaptiveBudget:
    """The adaptive layer's budget for this deployment, `T` from the environment.

    One field of it is settable and the rest are not, which is the shape rather than
    an omission. `T` is what a run against one target pays for a single attacker's
    time, and the operator paying is the one who should choose it. `k`, the family
    count and the steps per turn are read off the closed sets they cover or are the
    reason the layer terminates at all — a deployment moving those would be moving
    what an episode *is*, not how long one may take.

    **A setting that cannot be read stops the boot**, on the same terms a model named
    and unbuildable does: a bench that quietly ran the declared eight would put a
    number in front of an operator that they did not choose, at the one moment the
    figures are supposed to be theirs to confirm (ADR-0007).
    """
    try:
        turns = declared_turns_per_episode()
    except ValueError as unusable:
        raise RuntimeError(f"{unusable}. {NAMED_BUT_UNUSABLE}") from unusable
    if turns is None:
        return DECLARED_ADAPTIVE_BUDGET
    return replace(DECLARED_ADAPTIVE_BUDGET, turns_per_episode=turns)


def declared_instrument(
    variable: str, temperature: float | None = None
) -> tuple[str, Completion | None]:
    """What a report will print for that instrument, and the client that will run it.

    One function returning both halves, because they are one fact stated twice and a
    deployment where they disagree is the failure this shape exists to make
    unavailable: a provenance block naming a model nothing called, or a model calling
    a target under a report that does not name it. Both come out of the same string
    here, so the pairing is a property of the code rather than of whoever edits the
    caller next.

    The identifier is `UNDECLARED_MODEL` when the environment declares nothing, and
    the client is `None` beside it — a stated absence and no instrument, which is the
    only other pair this can return.

    **A model named and unbuildable stops the boot.** `completion_for` builds its
    client at configuration time precisely so a missing credential is not discovered
    at the first call, and this keeps that promise one level up: the alternative is a
    console that offers a start control for 830 calls against an instrument that was
    never there. The refusal names the variable, because the person who can set one
    is the person reading the traceback.
    """
    return _declared(variable, completion_for, temperature)


def declared_attacker(
    variable: str, temperature: float | None = None
) -> tuple[str, AttackerCompletion | None]:
    """The same reading for the adaptive attacker, whose client is a different shape.

    A sibling rather than an argument to the one above. `AttackerCompletion` returns
    a tool call and `Completion` returns prose, and the two instruments are declared
    apart precisely so one can move without the other (ADR-0011) — a single function
    handing back either would be the shared setting that separation exists to
    prevent. Everything else about the reading is identical, and is shared.
    """
    return _declared(variable, attacker_completion_for, temperature)


def _declared[Instrument](
    variable: str,
    build: Callable[[str, float | None], Instrument],
    temperature: float | None,
) -> tuple[str, Instrument | None]:
    """The identifier a report will print, and the client built from it.

    The half `declared_instrument` and `declared_attacker` have in common: read the
    variable, and either return a stated absence with no client or a declared string
    with the client that string built. What differs is the builder, which is the
    argument.
    """
    declared = declared_model(variable)
    if declared is None:
        return UNDECLARED_MODEL, None
    try:
        # Resolved against the capability table rather than sent as declared. The
        # temperature reaching here is the *bench's* own default and not an
        # operator's choice, so a model that accepts none takes none and the record
        # says which of the two absences that is (`capability.temperature_for`, #4).
        # A deployment that declared a GPT-5-family attacker used to boot cleanly
        # and fail at the first episode of the first run.
        return declared, build(declared, temperature_for(declared, temperature))
    except (KeyError, ValueError) as unusable:
        raise RuntimeError(
            f"{variable}={declared!r}: {unusable}. {NAMED_BUT_UNUSABLE}"
        ) from unusable


def deployed_models() -> tuple[DeclaredModels, Completion | None, AttackerCompletion]:
    """The models a deployment declared, and the two instruments built from them.

    **The environment is read through `completion.declared_model` and nowhere else.**
    No module of `backend/api/` imports `os`, which is what keeps a price, a target
    URL or a bearer token from arriving from the environment behind a default
    (`test_api_runs.py`). A model identifier arrives that way and only that way.

    **Nothing here defaults to a real model.** A bench that declared none says so on
    every screen and in every report, because a default naming an instrument would
    describe a run that did not happen (`UNDECLARED_MODEL`, ADR-0004). What the
    environment declares, this builds; what it does not, stays a stated absence.

    **Three are read, and two of them are built.** The reference agents' model is
    served to equipment rather than called from here, so it is declared and not
    built. The adjudicator and the adaptive attacker are both instruments this
    process calls, they are two settings on purpose (ADR-0011), and each arrives
    through `declared_instrument` or `declared_attacker` — which return the
    identifier and the client
    together, so a run cannot be attacked by a model the provenance block does not
    name, and the block cannot name one that did not attack.

    **An undeclared attacker is the deterministic stand-in, and says so.** The
    adaptive layer always runs, so the fallback is an attacker rather than nothing:
    `SCRIPTED_ATTACKER` spends the operator's endpoint the way a real one would while
    the identifier beside it stays a stated absence, because the stand-in is test
    equipment and not a model (`adaptive/scripted.py`). A deployment that declares
    nothing still boots, still runs, and still serves reports.
    """
    calibration = declared_model(REFERENCE_MODEL_ENV)
    adjudicating, adjudicator = declared_instrument(ADJUDICATOR_MODEL_ENV)
    attacking, attacker = declared_attacker(
        ATTACKER_MODEL_ENV, temperature=DEFAULT_ATTACKER_TEMPERATURE
    )
    return (
        DeclaredModels(
            calibration=calibration or UNDECLARED_MODEL,
            adjudicating=adjudicating,
            attacking=attacking,
            # Declared even when the model is not: the temperature a run was sampled
            # at is a condition of that run, and a bench that left it unstated would
            # be repeatable only by whoever knows what the provider defaults to.
            #
            # Through the same resolution the client above was built with, so the
            # record and the request agree: a model that accepts no temperature
            # records `None`, which `temperature_stated` prints as *this model takes
            # none* rather than as nothing declared (#4).
            attacking_temperature=temperature_for(
                attacking, DEFAULT_ATTACKER_TEMPERATURE
            ),
        ),
        adjudicator,
        attacker or SCRIPTED_ATTACKER,
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
    # Two lines of tracing, and both of them before a bench exists. The first turns
    # off every tracer this process inherited: one environment variable activates a
    # callback tracer that sends prompts and replies verbatim, and a deployment that
    # inherited it would be publishing payloads before it served a route — the
    # switches are named in `observability.INHERITED_TRACING_VARIABLES` and nowhere
    # else, because one module knows what is on the far end of the sink and this is
    # not it (ADR-0026). The second points this bench at the sink
    # its environment declares, and `None` — no sink — is a bench that boots, runs
    # and reports normally. ADR-0020's shape without its severity: a signing key is
    # what makes a report portable and a trace sink is a convenience, and a bench
    # that would not start without a debugging tool has its priorities inverted.
    disable_inherited_tracing()
    install(trace_config())
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
                nonce_planted=request.nonce_planted,
                echo_waived=request.echo_waived,
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
        return progress_for(record, bench.config.rule)

    @app.get(RUN_EPISODES_ROUTE)
    def serve_the_probes_this_runs_episodes_sent(
        run_id: Annotated[str, PathParam()],
    ) -> RunProbes | NoProbes:
        """The probes this run's attacker composed, in the order it sent them.

        The one route on this bench that serves probe text, and the operator's own
        live run is the whole of its subject: the episodes are read off the
        `RunState` this process is holding, for a run this process started, and the
        response says on itself that it is not part of the artefact, is committed
        nowhere and does not survive a restart (ADR-0008, amended).

        **The signed report is untouched by this and cannot be reached from here.**
        What a run signs is assembled from `ReportedEpisode`, which carries a
        family, an outcome, a turn count and prose, and has no field a probe could
        be written into. This response is built from `AdaptiveEpisode.transcripts`
        instead — a record that exists already, that no run writes to disk, and that
        the assembler never sees.

        **Two absences and two answers.** A run id this process never issued is a
        `404` by name, exactly as `GET /runs/{id}` answers one: after a restart every
        run is that, which is the honest form of *the memory is gone*. A run on the
        record that has recorded no episode is a `200` that says so in words, because
        it is a fact about where the run got to rather than a route that was wrong.
        Neither is an empty list: a search that ran and sent nothing is a reading
        about an attacker, and it is not what either of these is.
        """
        record = bench.record(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"no run {run_id} was started by this bench. The probes an "
                    "episode sent live with the process that ran it and are held "
                    "nowhere else, so a run this process did not start has none to "
                    "read — and a restart leaves every earlier run in exactly that "
                    "state"
                ),
            )
        return probes_sent(record)

    @app.get(RUN_ATTEMPTS_ROUTE)
    def serve_the_exchanges_behind_this_runs_successes(
        run_id: Annotated[str, PathParam()],
    ) -> RunExchanges | NoExchanges:
        """The attacks that worked on this run, as they went out and came back.

        The scored layer's counterpart to the episodes route, on the same terms: the
        attempts are read off the `RunState` this process is holding, for a run this
        process started, and the response says on itself that it is not part of the
        artefact, is committed nowhere and does not survive a restart (ADR-0008,
        amended).

        **The signed report is untouched by this and cannot be reached from here.**
        What a run signs carries each family's successes over its attempts and the
        boundary of the claim; `document()` is assembled key by key so that an
        attempt's transcript has nowhere to arrive. This response is built from
        `Attempt.transcript` instead — a record that exists already, that no run
        writes to disk, and that the assembler never sees.

        **Two absences and two answers**, as the episodes route answers them. A run
        id this process never issued is a `404` by name, which is what every earlier
        run becomes after a restart. A run on the record in which nothing succeeded
        is a `200` that says so in words — a fact about where the run got to, or
        about a target that resisted everything, and the rates say which. Neither is
        an empty list.
        """
        record = bench.record(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"no run {run_id} was started by this bench. The exchange behind "
                    "an attempt lives with the process that made it and is held "
                    "nowhere else, so a run this process did not start has none to "
                    "read — and a restart leaves every earlier run in exactly that "
                    "state"
                ),
            )
        return exchanges_behind(record)

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

        **What writes here, and what does not.** One route under `/bench` is a `PUT`
        and it is the one below: the declared inputs of the next run — the attacker's
        model and temperature, `T`, `k` and attempts per case (ADR-0025). Everything
        else on this response states and cannot be set from anywhere: the signing key
        is read from the environment by `signing.signing_key` and by no route, because
        the factory reads it from one place and refuses to boot without it (ADR-0020);
        the library is what was mounted; and the citation moves only when a gate run
        earns it (ADR-0023).
        """
        return bench_settings(bench.config)

    @app.put(BENCH_TUNING_ROUTE)
    def set_the_declared_inputs_of_the_next_run(asked: TuneRequest) -> BenchSettings:
        """Set what the next run is made with, and answer with the whole reading.

        **Every setting here is printed in the report of every run made under it.**
        That is the condition ADR-0025 admits them on: they change what a run
        *measured*, so a bench that could hold one quietly would be a bench whose
        figures are not readable from its own artefact. The attacker's model and
        temperature land in the provenance block, `T` and `k` in the adaptive
        section, and the rule travels on every `TargetRun` beside the rate it
        produced.

        **Refused while a run is going**, and the refusal names the runs. A run
        awaiting approval has been shown an estimate built from the settings it was
        declared with, and ADR-0007's mechanism is that nothing exceeds what a human
        confirmed — a budget raised while that halt is open would make the
        confirmation a statement about a run that never happened.

        **The model is validated against the closed list and the client is built
        here.** A slug the provider rejects fails at the first call, which is after
        an operator has attested and confirmed a spend; and the identifier the report
        will name and the client that will attack come out of one call, so a bench
        cannot name a model that never ran.

        The answer is the whole settings reading rather than an acknowledgement, so a
        console renders what the bench now holds instead of what it hoped it sent.
        """
        offered = {identifier for identifier, _ in ATTACKER_MODELS}
        if asked.attacker_model not in offered | {UNDECLARED_MODEL}:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{asked.attacker_model!r} is not one of the models this console "
                    f"offers: {', '.join(sorted(offered))}, or {UNDECLARED_MODEL} for "
                    "the deterministic stand-in. A slug the provider refuses fails at "
                    "the first call, which is after the spend has been confirmed"
                ),
            )
        _within("temperature", asked.temperature, TEMPERATURE_RANGE)
        _a_temperature_this_model_takes(asked.attacker_model, asked.temperature)
        _within("turns_per_episode", asked.turns_per_episode, TURNS_RANGE)
        _within("episodes_per_family", asked.episodes_per_family, EPISODES_RANGE)
        _within("attempts_per_case", asked.attempts_per_case, ATTEMPTS_RANGE)

        declared = Instrumented(
            attacker_model=asked.attacker_model,
            temperature=asked.temperature,
            turns_per_episode=asked.turns_per_episode,
            episodes_per_family=asked.episodes_per_family,
            attempts_per_case=asked.attempts_per_case,
        )
        try:
            attacker = (
                SCRIPTED_ATTACKER
                if asked.attacker_model == UNDECLARED_MODEL
                else attacker_completion_for(asked.attacker_model, asked.temperature)
            )
        except (KeyError, ValueError) as unusable:
            raise HTTPException(
                status_code=422,
                detail=f"{asked.attacker_model}: {unusable}. {NAMED_BUT_UNUSABLE}",
            ) from unusable
        try:
            bench.instrument(declared, attacker)
        except RunsInFlight as busy:
            # 409 rather than 422: the request is well formed and the bench is the
            # reason it cannot be served, which is a state the caller can wait out.
            raise HTTPException(status_code=409, detail=str(busy)) from busy
        return bench_settings(bench.config)

    @app.put(BENCH_FAMILIES_ROUTE)
    def set_the_families_the_next_run_covers(asked: CoverRequest) -> BenchSettings:
        """Switch families on and off for the next run, and answer with the reading.

        **Switching one off is not the same as measuring it at zero**, and the
        difference is carried rather than trusted: `plan_for` drops the family's cases
        and records `DeclaredGap.FAMILY_SWITCHED_OFF`, whose sentence says the family
        was not attempted. The adaptive layer needs no second mechanism — an episode
        needs a deterministic case for its family, and a family whose cases are gone
        has none.

        **An empty selection is refused.** A run covering no family attacks nothing
        and would still spend a registration probe per target, which is a bill for a
        run that measures nothing.

        Refused while a run is going, on `instrument`'s reasoning: a run awaiting
        approval was shown an estimate built from the families it was declared with.
        """
        named: list[Family] = []
        for name in asked.families:
            try:
                named.append(Family(name))
            except ValueError as unknown:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{name!r} is not a family this bench has. The six are "
                        f"{', '.join(str(family) for family in Family)}"
                    ),
                ) from unknown
        if not named:
            raise HTTPException(
                status_code=422,
                detail=(
                    "a run covering no family attacks nothing, and would still spend "
                    "a registration probe per target. Leave at least one on"
                ),
            )
        try:
            bench.cover(frozenset(named))
        except RunsInFlight as busy:
            raise HTTPException(status_code=409, detail=str(busy)) from busy
        return bench_settings(bench.config)

    @app.get(BENCH_NOTES_ROUTE)
    def state_what_the_injection_family_needs_planted() -> NotesToPlant:
        """The content the indirect prompt injection family attacks with. A reader.

        The registration walk asks an operator to declare that this content is in
        place and, until this route, told them nothing about what it is. The notes
        are committed beside the reference agents that fetch them, and a case in this
        family *is* a piece of content: the payload the bench sends is a colleague's
        ordinary message and everything adversarial is in what the target retrieved.
        So the family cannot be run against content the operator invented — the
        canary would never appear, and thirty attempts would report a clean zero
        against an attack that was never made.

        **Paired by the canary the verdict reads.** A note is served against a case
        when its executed line is that case's `planted_canary`, which is the string
        `evaluator.py` looks for in the reply. Nothing here is matched by name, by
        family alone or by order, so a note edited out of agreement with the case it
        was written for stops being served rather than being served as the wrong
        content.

        **The live half only, and never a readiness field.** A retired case is one no
        run attempts. Whether the content is actually in place is the operator's
        declaration at registration, and this bench cannot check it: a target's
        retrieval is behind their boundary, which is why the declaration exists.
        """
        return notes_to_plant(bench.config.cases)

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
