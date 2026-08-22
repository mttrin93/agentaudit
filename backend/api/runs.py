"""Starting a run from something other than a terminal, and the two controls that
survive the move.

A run is 181 calls in the scored layer and up to 96 more in the adaptive one, every
one of them on the operator's endpoint and their inference budget. The two controls
that make one authorised — a completed three-part attestation, and a halt in front
of the spend — are the whole of what this module is for (ADR-0007), and neither of
them becomes a request field. The attestation is the same record `registration.py`
refuses to construct incomplete. The halt is the same LangGraph `interrupt()`
against a checkpointer that a terminal run stops at: what changes between a
terminal and a browser is the `Approve` seam and nothing else, which is what
`scripts/console.py` said when it wrote the other one.

**The guard is in two places, and it has to be.** The three statements are checked
before a run exists, because nothing about them needs the target. The nonce echo
cannot be checked there: the echo probe is itself a call on the operator's
endpoint, and ADR-0007 puts the halt *ahead* of registration precisely so that a
run has spent nothing by the time it asks. So the bench issues the nonce, the
operator plants it, `start` refuses a nonce this bench never issued, and the echo
itself is checked by `register` inside the run — after the interrupt was answered.
A target that does not echo is a run that makes no attempt and says so. A guard
that checked the echo at the request would be a guard that spent the operator's
money before asking them.

**Two figures, and they are the two figures a terminal shows.** What comes back is
`RunBudget.as_payload()`: the scored layer exact, the adaptive layer a ceiling,
each carrying its own arithmetic, beside the bounded total and the hard ceiling
that ADR-0007's own table prints and that is the figure actually enforced. Nothing
here adds a figure, and nothing averages one — `CallFigure.__add__` makes a fact
plus a bound a bound, so a total cannot be presented as exact by anything
downstream.

**The run is on a thread and the request that started it does not wait for it.**
`start` returns once the graph has halted, carrying the figures the interrupt
presented rather than a second computation of them, so what a caller confirms is
what the graph is holding. The suite is on the far side of the edge the answer
decides, and it is held to the ceiling on the record — never one re-declared later
against whatever the library holds by then.

**A thread rather than a background task, and the reason is the halt.** A FastAPI
background task starts after its response has been sent, and this run has to be
*already halted* when the response is built — otherwise the figures returned would
be a second computation of the estimate rather than the one the graph is holding,
and there would be nobody to answer. So the run starts on its own thread and the
request rendezvouses with it at the interrupt. The cost is a thread per run
awaiting an answer, which is the v1 the spec licensed; a queue is P1.

**Nothing here reads the environment.** The price per call arrives in the request
or the run is *not priced*: the caller's confirmation is the liability record, and
a figure the bench filled in from its own configuration is a figure nobody agreed
to. An unpriced run is a stated fact and never a zero. The signing key arrives the
same way, in `BenchConfig.report`, and it is still true here that there is one line
in this repository that reads `AGENTAUDIT_SIGNING_KEY` and it is in `signing.py` —
what changed with ADR-0020 is that `app.py`'s factory *calls* that line when it was
handed no configuration, and refuses to boot when it comes back empty.

**The artefact is built by the run, once, before the run is called completed.** A
report assembled per request would be bytes that depend on when they were asked
for, and a signature is over one document rather than over a recipe for making one
(`report.py`, #56). A run whose artefact could not be made is still a completed
run — the suite ran and the target was measured — and what it lacks is stated by
name rather than made good with an unsigned payload.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum

from backend.api.report import ReportConfig, Unsigned, artefact_for
from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetConfig, TargetFailure, TargetUnreachable
from backend.bench.library import Case, Family, LibraryVersion, VerdictClass
from backend.bench.payload import GateCitation
from backend.bench.registration import Attestation, issue_nonce
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.signing import SignedArtefact
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    BudgetPayload,
    CallPrice,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState

APPROVAL_WAIT_SECONDS = 3600.0
"""How long a run waits at the interrupt for an answer that may never come.

A halted run holds a thread and a checkpoint, so the wait is finite; it is an hour
because the human it is waiting for has to read two figures and decide whether to
spend them, and a limit short enough to catch somebody thinking would be a consent
mechanism that answered on their behalf. What happens at the end of it is a *no*
recorded as **unanswered** rather than as declined — nobody said no, nobody said
anything — and either way nothing was sent and nothing was spent.
"""

PRESENT_WAIT_SECONDS = 30.0
"""How long `start` waits for the graph to reach its interrupt.

Nothing has been sent to the target by then — the halt is ahead of registration —
so this bounds a graph that never halted rather than a run that is working. A run
that reaches it has failed to present an estimate, and a request that returned a
`run_id` for one would be handing back a run nobody could ever confirm.
"""


class RunStatus(StrEnum):
    """Where a run is, in the words the record keeps.

    `DECLINED` and `UNANSWERED` are two states rather than one, on `approval.py`'s
    own reasoning: a caller that treats them as the same loses the difference
    between "refused by a human" and "awaiting one". `ABORTED` is separate from
    `FAILED` for the same kind of reason — a run stopped by its own ceiling is the
    budget working, and one stopped by a transport failure is not a result at all.
    """

    AWAITING_APPROVAL = "awaiting_approval"
    DECLINED = "declined"
    UNANSWERED = "unanswered"
    RUNNING = "running"
    COMPLETED = "completed"
    REGISTRATION_REFUSED = "registration_refused"
    ABORTED = "aborted"
    FAILED = "failed"

    @property
    def in_flight(self) -> bool:
        """Whether a run in this state is still going, or has stopped for good.

        Asked by anything that has to tell *not yet* from *not ever*: a caller told
        to poll a run that ended without a report would poll for the lifetime of the
        process. Written as the two states a run can leave rather than as the six it
        cannot, so that a seventh terminal state is terminal on the day it is added
        rather than on the day somebody remembers this list.
        """
        return self in {RunStatus.AWAITING_APPROVAL, RunStatus.RUNNING}


class DeclaredGap(StrEnum):
    """Something the caller's own setup did not provide, and the family it costs.

    The second surface of the concept `scripts/probe_target.py` keeps as
    `OperatorGap`, and deliberately not `NotMeasurable`: that type is the library's
    answer to a *case precondition* a target cannot meet, decided before an attempt
    is spent. These are the caller's gaps — the bench cannot detect either of them,
    no attempt is skipped for them, and the family is not run at all rather than
    measured at zero. A family missing from a run with no reason beside it is a
    reader guessing which of three answers it was.

    Two enums rather than one shared one, and the duplication is the smaller cost.
    `OperatorGap` says *pass `--adjudicator-model`* and *this was a
    `--deterministic-only` run*: its prose names command-line flags, which is right
    for the surface it was written for and wrong in an HTTP response. It also
    carries two members about reading a rate that was measured, which is a thing
    this surface does not do yet. Sharing them would mean rewriting a script's
    user-facing text to fit a caller who is not at a terminal.
    """

    NO_ADJUDICATOR = "no_adjudicator"
    NOTE_NOT_PLANTED = "note_not_planted"
    NONCE_NOT_PLANTED = "nonce_not_planted"

    def stated(self) -> str:
        match self:
            case DeclaredGap.NO_ADJUDICATOR:
                return (
                    "not run: this family reaches its verdict by adjudication and "
                    "this bench has no adjudicating instrument configured. A "
                    "family nothing can score is not attempted, so the estimate "
                    "does not charge for it"
                )
            case DeclaredGap.NOTE_NOT_PLANTED:
                return (
                    "not run: this family needs a third-party note planted in "
                    "content the target retrieves, and the caller declared it is "
                    "not in place. Run without it, the family would report a clean "
                    "zero that reads as a defence and is not one"
                )
            case DeclaredGap.NONCE_NOT_PLANTED:
                return (
                    "not run: this family extracts the registration nonce, and the "
                    "caller started this run without planting it. A canary that is "
                    "nowhere in the target cannot leak, so every attempt would "
                    "report resisted against an attack that was never possible"
                )


@dataclass(frozen=True)
class BenchConfig:
    """What every run through this API is measured with.

    One record rather than arguments threaded through the routes, so that the
    library a run is estimated against and the library it is run against are the
    same object by construction. The declared rule and the declared adaptive
    budget are the defaults for the same reason `RunBudget.declare` takes them: a
    run held to numbers that were chosen for it is a run whose figures can be
    checked against `rule.py` and `adaptive/budget.py` rather than against
    whatever this module happened to pass.
    """

    cases: Sequence[Case]
    rule: GateRule = DECLARED_RULE
    adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET
    attacker: AttackerCompletion = SCRIPTED_ATTACKER
    """The adaptive layer's attacker, defaulting to the deterministic stand-in.

    Same default as `run_calibration`, and for the same reason: the layer always
    runs, and a bench with no model credential configured still spends the
    operator's endpoint the way a real one would. Naming a configured model here
    is the deployment's business.
    """

    adjudicator: Completion | None = None
    """The instrument that decides the two judged families, or `None`.

    `None` by default, and the consequence is stated rather than absorbed: the
    judged cases are not run, and their families are reported with the gap that
    explains why. A run that reached its first judged attempt before discovering
    it had no instrument would have spent the operator's budget on attempts
    nothing can score.
    """

    report: ReportConfig = field(default_factory=ReportConfig)
    """The key this bench signs a finished run's report with, and what it declares
    beside the figures.

    Its own record rather than three more fields here, because none of it changes
    what a run does to a target: a bench with the default of every one of them
    attempts the same suite and produces no artefact. What that costs is stated at
    the route rather than absorbed — a run with no signed report is refused by name
    (`report.py`).
    """

    approval_wait_seconds: float = APPROVAL_WAIT_SECONDS


@dataclass(frozen=True)
class RunPlan:
    """The cases one run will actually attempt, and the families it will not.

    Built per request rather than per bench, because one of the two gaps is a
    statement the caller makes about their own content store and the other is a
    property of this bench. They land in the same record because a reader of the
    estimate needs to know what it covers, and the estimate covers what is here.
    """

    cases: tuple[Case, ...]
    gaps: Mapping[Family, DeclaredGap]


def plan_for(
    config: BenchConfig, note_planted: bool, nonce_planted: bool = True
) -> RunPlan:
    """Which of the library's cases this run may attempt, and why the rest are out.

    Selected on `Case.verdict_class` and on the family, never on the family name
    alone for the judged half: the class is a field of the record for exactly this
    reason (ADR-0013), so a case that moves between families cannot change which
    instrument the run needed.
    """
    gaps: dict[Family, DeclaredGap] = {}
    cases = list(config.cases)

    if config.adjudicator is None:
        judged = {
            case.family for case in cases if case.verdict_class is VerdictClass.JUDGED
        }
        gaps.update(dict.fromkeys(judged, DeclaredGap.NO_ADJUDICATOR))
        cases = [
            case for case in cases if case.verdict_class is not VerdictClass.JUDGED
        ]

    if not note_planted:
        injection = Family.INDIRECT_PROMPT_INJECTION
        if any(case.family is injection for case in cases):
            gaps[injection] = DeclaredGap.NOTE_NOT_PLANTED
        cases = [case for case in cases if case.family is not injection]

    # The same argument one family over. The registration nonce is the leakage
    # canary — one planted value, two roles (ADR-0007) — so a run whose operator
    # never planted it is a run whose leakage cases go after a string that is
    # nowhere in the target. Thirty attempts would come back resisted and the
    # report would read as a defence that was never tested.
    if not nonce_planted:
        leakage = Family.DATA_LEAKAGE
        if any(case.family is leakage for case in cases):
            gaps[leakage] = DeclaredGap.NONCE_NOT_PLANTED
        cases = [case for case in cases if case.family is not leakage]

    return RunPlan(cases=tuple(cases), gaps=gaps)


class NonceNotIssued(ValueError):
    """A run asked to start against a nonce this bench never issued.

    The half of the authorisation guard that can be enforced before anything is
    sent. It does not prove the target echoes the value — only the probe inside
    the run can, and it runs after the halt — but it does prove the caller went
    through registration rather than pointing the bench at an endpoint and
    inventing a token.
    """

    def __init__(self, nonce: str) -> None:
        super().__init__(
            "this bench never issued that nonce, so no run may start against it. "
            "Register the target first: the bench issues the value, you plant it "
            "in the target's configuration, and the run's own registration probe "
            "checks that it comes back (ADR-0007)."
            if nonce
            else "a run has to name the nonce it was registered with, and this "
            "request named none (ADR-0007)."
        )


class NeverPresented(RuntimeError):
    """The graph did not reach its interrupt, so there is no estimate to confirm."""


@dataclass
class RunRecord:
    """One run: what authorised it, what it was estimated at, and where it got to.

    The budget, the plan and the run state are all held here rather than in the
    thread's locals, because the ceiling the suite is held to has to be the one the
    caller was shown — an estimate that has become separated from the run it was
    presented for is an estimate nobody can check.
    """

    run_id: str
    target: TargetConfig
    attestation: Attestation
    nonce: str
    plan: RunPlan
    budget: RunBudget
    run_state: RunState
    presented: BudgetPayload
    proof_waived: bool = False
    """The operator started this run without planting the nonce (ADR-0007, amended).

    Held on the record because it decides two things and outlives both: the run still
    sends its echo probe but is not stopped by a missing echo, and the leakage family
    is dropped from the plan rather than measured against a value nobody planted. The
    artefact says which of the two ways the run was authorised, and it says it from
    what the registration recorded rather than from this field — this is the
    declaration, and that is what the endpoint did.
    """

    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    """When this run went on the record: the moment the attestation was taken and
    the estimate declared.

    Deliberately not *when the target was registered*. Registration is the nonce
    echo (CONTEXT.md), and the echo probe is the run's first call on the operator's
    endpoint — on the far side of the interrupt — so a run awaiting approval, a run
    declined and a run nobody answered have no registration time at all, and a
    field that claimed to be one would be empty for exactly the runs a list is most
    useful for. This is the time the bench took responsibility for the run, which
    every run has.

    A wall clock in UTC, because it is read by somebody asking *which of these did I
    start yesterday*. `RunState.started_at` is `time.monotonic()` and stays that
    way: it exists so that the layer-ordering invariant is checkable (ADR-0010), and
    a monotonic reading has no date in it.
    """

    status: RunStatus = RunStatus.AWAITING_APPROVAL
    statement: str = (
        "halted at the approval interrupt: nothing has been sent to the target "
        "and nothing has been spent, and nothing will be until this estimate is "
        "answered. The nonce is checked by the run's own registration probe, "
        "which is the first call it makes — a target that does not echo it is "
        "not attempted, unless the operator declared the proof waived when they "
        "started this run"
    )
    confirmed_by: str = ""
    result: CalibrationResult | None = None
    report: SignedArtefact | Unsigned = field(default_factory=Unsigned)
    """The signed report this run produced, or the reason it has none.

    Built once, by the thread that ran the run, and read by every request for it:
    what a recipient downloads has to be the bytes that were signed, and bytes
    re-assembled per request are bytes nobody signed (#56).

    One of two records rather than a nullable one, so *why there is no report* is
    carried by the thing that stands in for it: `Unsigned` is served as that under
    its own name, and it is never made good by serving an unsigned payload in its
    place. It is not a failed run either — the suite ran and the target was
    measured.
    """

    failure: TargetFailure | None = None
    """The named transport outcome that stopped this run, if one did.

    Kept as the enum the transport raised rather than folded into `statement`,
    because the four the spec names are four different jobs for the person reading
    the run and a reporting surface has to be able to name the one it got. `None`
    for every run that was not stopped by the wire — and a failure here is never a
    verdict, never an attempt and never a finding: `TargetUnreachable` is raised
    precisely so that no counter has anywhere to put it.
    """

    @property
    def spent(self) -> dict[Layer, int]:
        """Calls spent, per layer and never summed.

        Two counters, because a single blended figure hides which half of a run is
        consuming the operator's budget — the same reason the estimate is two
        figures (ADR-0007). `RunState.calls_spent` exists for reporting and is
        deliberately not what a ceiling is read against.
        """
        return dict(self.run_state.spent)

    def settle(self, status: RunStatus, statement: str) -> None:
        """Move the run to its next state, and say in words what that state is."""
        self.status = status
        self.statement = statement


class PendingApproval:
    """The interrupt's two ends: the graph waits here, an HTTP request answers here.

    This is the `Approve` seam and nothing more. The graph does not know it is
    being answered over HTTP any more than it knows it is being answered at a
    terminal, which is the property ADR-0007 asks for — the run does not proceed
    because it *cannot* proceed, not because a code path chose not to.
    """

    def __init__(self, wait_seconds: float) -> None:
        self._wait = wait_seconds
        self._halted = threading.Event()
        self._answered = threading.Event()
        self._payload: BudgetPayload | None = None
        self._answer: Approval | None = None
        self._closed = False
        self._lock = threading.Lock()

    @property
    def answered(self) -> bool:
        """Whether a human ever answered. False for a run that timed out waiting."""
        return self._answer is not None

    def approve(self, presented: BudgetPayload) -> Approval:
        """What the graph calls when it has halted. Blocks until somebody answers.

        The payload is published before the wait, so the request that started the
        run returns the figures the interrupt is holding rather than a recomputed
        copy of them.

        When the wait runs out this closes: an answer arriving afterwards has
        nothing to answer, because the graph has already been told nobody did. The
        close and the answer take the same lock, so a confirmation landing in that
        instant is either taken or refused and never both.
        """
        self._payload = presented
        self._halted.set()
        answered = self._answered.wait(self._wait)
        with self._lock:
            if not answered or self._answer is None:
                self._closed = True
                return Approval(
                    confirmed=False,
                    identity="",
                    reason=(
                        "the approval interrupt was never answered, so the run "
                        "never started"
                    ),
                )
            return self._answer

    def answer(self, approval: Approval) -> bool:
        """Record the human's answer, if this interrupt is still waiting on one.

        False when it is not — answered already, or closed because the wait ran
        out. A caller that took that for a yes would be telling somebody their run
        had started when the graph had already been told it would not.
        """
        with self._lock:
            if self._closed or self._answer is not None:
                return False
            self._answer = approval
            self._answered.set()
            return True

    def halted(self, timeout: float) -> BudgetPayload:
        """The estimate the graph is holding, once it is holding one."""
        if not self._halted.wait(timeout) or self._payload is None:
            raise NeverPresented(
                "the run reached no approval interrupt, so it has no estimate to "
                "confirm. Nothing was sent"
            )
        return self._payload


class BenchRuns:
    """Every run this process has started, and every nonce it has issued.

    In memory, single process, and that is the v1 the spec licensed: a queue and a
    store outlive a restart and are P1. What is *not* deferred is that a run holds
    its own ceiling and its own state — those are correctness rather than
    durability, and they are on `RunRecord`.
    """

    def __init__(self, config: BenchConfig) -> None:
        self._config = config
        self._issued: set[str] = set()
        self._runs: dict[str, RunRecord] = {}
        self._pending: dict[str, PendingApproval] = {}
        self._lock = threading.Lock()

    @property
    def config(self) -> BenchConfig:
        """What this bench measures and signs with, readable and frozen.

        Readable because the factory's boot-time contract is about *this* object: a
        deployment that must not start without a signing key (ADR-0020) is checkable
        only by asking the bench the factory returned what it holds, and a check
        against the function that built it would be a check on a call nobody proved
        was made. Frozen, so reading it is not a way to change it.

        One thing about it does move, and it moves through the named writer below and
        nowhere else: the gate run this bench cites (ADR-0023).
        """
        return self._config

    def cite(self, citation: GateCitation) -> None:
        """Start citing this gate run, in this process, from now on.

        The one writer on `BenchConfig`, and it takes a `GateCitation` rather than
        anything a gate run produced: what reaches this bench is the citation, which
        is provenance, and not a decision, a `GateResult` or a record of either. A
        gate run's own registry is `BenchGateRuns` and no signature here names it —
        this method is the single edge between the two, which is the shape ADR-0010
        established and ADR-0021 applied to the gate-run axis.

        **Why this exists at all.** ADR-0021 left the citation as whatever the
        deployment declared, so a bench that had just passed its own gate went on
        citing something else, and a deployment that declared nothing read as an
        instrument with no certification. ADR-0023 reverses that: the durable record
        is the citation in the library (`bench/cited.py`), which the next process
        boots with, and this is how the process that made the gate run starts citing
        it without waiting for a restart.

        Replaced rather than mutated, under the same lock the records are kept under,
        because `BenchConfig` and `ReportConfig` are frozen and a run that has already
        built its payload keeps the citation it was signed with.
        """
        with self._lock:
            self._config = replace(
                self._config, report=replace(self._config.report, gate=citation)
            )

    def issue(self) -> str:
        """Issue a nonce for a target the caller is about to register.

        One nonce, one run: `start` spends it, so a second run needs a value the
        caller has planted again. That is what a terminal run already does — it
        issues a fresh nonce every time — and it is what keeps the echo evidence
        about *this* run rather than about a value that proved control once.
        """
        nonce = issue_nonce()
        with self._lock:
            self._issued.add(nonce)
        return nonce

    def record(self, run_id: str) -> RunRecord | None:
        """One run's record, or `None` for an id this bench never issued."""
        with self._lock:
            return self._runs.get(run_id)

    def records(self) -> list[RunRecord]:
        """Every run this bench has started, most recently recorded first.

        The records themselves, and never a summary of them: nothing here counts
        runs, adds a spend across them, or averages one. A caller that wanted a
        figure spanning two runs would have to build it in front of the rows it
        built it from.

        Reversed insertion order rather than a sort on `recorded_at`, because
        insertion order *is* chronological — `start` puts the record in this dict
        under the lock, in the same critical section that issued its id — and two
        runs started in the same microsecond would otherwise be ordered by
        whichever comparison the sort happened to make.
        """
        with self._lock:
            return list(self._runs.values())[::-1]

    def start(
        self,
        target: TargetConfig,
        attestation: Attestation,
        nonce: str,
        price: CallPrice | None,
        note_planted: bool,
        nonce_planted: bool = True,
    ) -> RunRecord:
        """Declare the estimate, start the run, and return once it has halted.

        The attestation is a constructed `Attestation` rather than three booleans:
        a statement that was not made cannot be constructed, so a run that reaches
        this line was authorised by a record that exists.
        """
        with self._lock:
            issued = nonce in self._issued
            self._issued.discard(nonce)
        if not issued:
            raise NonceNotIssued(nonce)

        plan = plan_for(self._config, note_planted, nonce_planted)
        budget = RunBudget.declare(
            cases=plan.cases,
            targets=[target],
            rule=self._config.rule,
            adaptive=self._config.adaptive,
            price=price,
        )
        pending = PendingApproval(self._config.approval_wait_seconds)
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            target=target,
            attestation=attestation,
            nonce=nonce,
            proof_waived=not nonce_planted,
            plan=plan,
            budget=budget,
            run_state=RunState(budget=budget, library=LibraryVersion.of(plan.cases)),
            presented=budget.as_payload(),
        )
        with self._lock:
            self._runs[run_id] = record
            self._pending[run_id] = pending

        threading.Thread(
            target=_execute,
            args=(record, self._config, pending),
            name=f"agentaudit-run-{run_id}",
            daemon=True,
        ).start()

        # The figures the graph is holding, not the ones declared above: the two
        # are built from the same budget, and returning the presented copy is what
        # makes that checkable rather than assumed.
        record.presented = pending.halted(PRESENT_WAIT_SECONDS)
        return record

    def answer(self, run_id: str, approval: Approval) -> RunRecord:
        """Answer one run's interrupt. A yes is the only thing that starts a suite."""
        with self._lock:
            record = self._runs.get(run_id)
            pending = self._pending.get(run_id)
        if record is None or pending is None:
            raise KeyError(run_id)
        if record.status is not RunStatus.AWAITING_APPROVAL or not pending.answer(
            approval
        ):
            # Both, and in this order. The status catches the second request; the
            # pending catches the request that arrives in the instant the wait runs
            # out, which no status has moved for yet.
            raise NoLongerWaiting(record)

        if approval.confirmed:
            record.confirmed_by = approval.identity
            record.settle(
                RunStatus.RUNNING,
                (
                    f"confirmed by {approval.identity}: the suite is running in "
                    "the background, under the ceiling that was confirmed and "
                    "aborting rather than exceeding it"
                ),
            )
        else:
            record.settle(RunStatus.DECLINED, _declined(approval.reason))
        return record


class NoLongerWaiting(RuntimeError):
    """An answer to an interrupt that is not waiting for one any more.

    Refused rather than applied, whichever of the two it is. A second answer would
    be consent recorded for a spend that is already happening; an answer arriving
    after the wait ran out would be consent for a run the graph has already been
    told nobody authorised.
    """

    def __init__(self, record: RunRecord) -> None:
        super().__init__(
            f"run {record.run_id} is {record.status} and is no longer waiting on "
            "an answer. An interrupt is answered once"
        )


def _declined(reason: str) -> str:
    stated = reason or "declined at the approval interrupt"
    return f"{stated}. Nothing was sent to the target and nothing was spent"


def _execute(record: RunRecord, config: BenchConfig, pending: PendingApproval) -> None:
    """One run, on its own thread: the same entry point a terminal run takes.

    There is one code path to a target and this does not add a second — the
    attestation, the estimate, the halt, registration, the attempt loop and the
    adaptive layer are all reached through `run_calibration`, which is what the
    gate and `scripts/probe_target.py` reach them through.
    """
    # Named against the seam's own type rather than passed straight through, so
    # that a signature drifting away from `Approve` is a typecheck failure here
    # and not a run that halts and never resumes.
    approve: Approve = pending.approve
    try:
        result = run_calibration(
            cases=record.plan.cases,
            targets=[record.target],
            attestation=record.attestation,
            approve=approve,
            adjudicator=config.adjudicator,
            attacker=config.attacker,
            rule=config.rule,
            adaptive=config.adaptive,
            # The ceiling on the record, never one re-declared here: the operator
            # confirmed these figures in an earlier request, and a run held to a
            # limit recomputed against whatever the library holds by now would be
            # a run held to a number nobody saw.
            budget=record.budget,
            run_state=record.run_state,
            planted_nonces={record.target.name: record.nonce},
            proof_waived=record.proof_waived,
        )
    except BudgetExceeded as abort:
        record.settle(
            RunStatus.ABORTED,
            (
                f"{abort}. An episode the ceiling cut short is recorded as "
                "censored, never as resisted"
            ),
        )
        return
    except TargetUnreachable as unreachable:
        # The outcome under its own name, beside the sentence that says what it is
        # not. A run that reported only the sentence would leave a caller parsing
        # prose to tell a quota from an outage.
        record.failure = unreachable.failure
        record.settle(RunStatus.FAILED, str(unreachable))
        return
    except Exception as failure:
        record.settle(
            RunStatus.FAILED,
            f"the run stopped rather than produced a result: {failure}",
        )
        return

    record.result = result
    if not result.approval.proceeded:
        refused = RunStatus.DECLINED if pending.answered else RunStatus.UNANSWERED
        record.settle(refused, _declined(result.approval.reason))
        return

    [target_run] = result.target_runs
    if target_run.registration.refused:
        record.settle(
            RunStatus.REGISTRATION_REFUSED,
            (
                "the nonce was not echoed, so no attempt was made. Registration "
                "proves you control the endpoint and nothing runs without it: "
                "check that the nonce line is in the target's configuration and "
                "that it reloaded"
            ),
        )
        return

    record.report = _published(record, result, config)
    finished = (
        f"the run finished inside the ceiling that was confirmed by "
        f"{record.confirmed_by}"
    )
    if not target_run.registration.echoed:
        # Reached only by a run started with the proof waived, since a run without
        # the waiver stopped above. Said on the record and not left to the artefact:
        # this is the sentence a poller reads, and a run that measured an endpoint
        # nobody proved control of should not read as an ordinary finish.
        finished = (
            f"{finished}, against an endpoint whose control was declared and not "
            "proved — the nonce was never echoed and this run waived that proof"
        )
    if isinstance(record.report, Unsigned):
        # Said here rather than left to the report route, because this is the
        # sentence a poller reads: a run whose status says completed and whose
        # report location is empty would otherwise read as one to keep polling.
        finished = f"{finished}, and it has no signed report — {record.report.reason}"
    record.settle(RunStatus.COMPLETED, finished)


def _published(
    record: RunRecord, result: CalibrationResult, config: BenchConfig
) -> SignedArtefact | Unsigned:
    """This run's signed artefact, built before the run is called completed.

    Before, and in this order, so that a caller polling for `completed` and then
    fetching the report never meets a run that is finished and has nothing to serve.

    A failure here does not fail the run. The suite ran and the target was measured;
    what did not happen is the document, and a run marked failed for it would be
    reporting a publication fault as a fact about somebody's agent. Every exception
    is caught for that reason and for one more: this runs on the run's own thread,
    where anything that escaped would leave the record saying *running* for the
    lifetime of the process.
    """
    try:
        return artefact_for(result, record.plan.cases, config.rule, config.report)
    except Exception as unpublished:
        return Unsigned(
            "this run has no signed report: the run finished and its artefact could "
            f"not be assembled or signed — {unpublished}. The measurement happened "
            "and is on the record; nothing unsigned is served in its place"
        )
