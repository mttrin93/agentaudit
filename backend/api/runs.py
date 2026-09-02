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

**What is left here is the service, and the three modules beside it are the rest.**
`run_status.py` holds the vocabulary a run is described in, `run_config.py` what a
run is measured with, `run_state.py` one run's record and the halt it waits at.
This module drives a run through them, and it re-exports their names because
`app.py`'s routes and the suite both import a run's vocabulary from
`backend.api.runs` — the split moved the definitions and deliberately did not move
the import surface (#14).

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
from dataclasses import replace

from backend.api.report import Unsigned, artefact_for
from backend.api.run_config import (
    BenchConfig as BenchConfig,
)
from backend.api.run_config import (
    Instrumented as Instrumented,
)
from backend.api.run_config import (
    Instruments as Instruments,
)
from backend.api.run_config import (
    PerRunInstruments as PerRunInstruments,
)
from backend.api.run_config import (
    RunPlan as RunPlan,
)
from backend.api.run_config import (
    plan_for as plan_for,
)
from backend.api.run_state import (
    NeverPresented as NeverPresented,
)
from backend.api.run_state import (
    NoLongerWaiting as NoLongerWaiting,
)
from backend.api.run_state import (
    NonceNotIssued as NonceNotIssued,
)
from backend.api.run_state import (
    PendingApproval as PendingApproval,
)
from backend.api.run_state import (
    RunRecord as RunRecord,
)
from backend.api.run_state import (
    RunsInFlight as RunsInFlight,
)
from backend.api.run_status import (
    APPROVAL_WAIT_SECONDS as APPROVAL_WAIT_SECONDS,
)
from backend.api.run_status import (
    FINISHED_WAIT_SECONDS as FINISHED_WAIT_SECONDS,
)
from backend.api.run_status import (
    PRESENT_WAIT_SECONDS as PRESENT_WAIT_SECONDS,
)
from backend.api.run_status import (
    DeclaredGap as DeclaredGap,
)
from backend.api.run_status import (
    RunStatus as RunStatus,
)
from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetConfig, TargetUnreachable
from backend.bench.library import Family, LibraryVersion
from backend.bench.payload import GateCitation
from backend.bench.registration import Attestation, issue_nonce
from backend.bench.signing import SignedArtefact
from backend.bench.usage import UsageLedger
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    CallPrice,
    RunBudget,
)
from backend.graph.runstate import RunState
from backend.observability import TracedRun


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

    def instrument(self, declared: Instrumented, attacker: AttackerCompletion) -> None:
        """Set the declared inputs of every run this bench starts from now on.

        The second named writer on `BenchConfig`, and it works the way the first one
        does: `replace` under the lock, because the record is frozen and a run that
        has already built its payload keeps the instruments it was made with.

        **A run in flight is not re-instrumented, and the caller is refused rather
        than served.** A run awaiting approval has been shown an estimate built from
        the budget it was declared with, and ADR-0007's whole mechanism is that
        nothing exceeds what a human confirmed — so a turn budget raised while that
        halt is open would make the confirmation a statement about a run that is not
        the one that ran. `RunsInFlight` names the runs so the operator can wait for
        them or decline them rather than guess.

        The attacker is passed in already built rather than constructed here: the
        identifier that goes into `report.models.attacking` and the client that will
        attack have to come from one call, or a bench can end up naming a model that
        never ran (`app.declared_instrument` makes the same pairing at boot).
        """
        with self._lock:
            in_flight = [
                run_id
                for run_id, record in self._runs.items()
                if record.status.in_flight
            ]
            if in_flight:
                raise RunsInFlight(in_flight)
            self._config = replace(
                self._config,
                attacker=attacker,
                rule=replace(
                    self._config.rule, attempts_per_case=declared.attempts_per_case
                ),
                adaptive=replace(
                    self._config.adaptive,
                    turns_per_episode=declared.turns_per_episode,
                    episodes_per_family=declared.episodes_per_family,
                ),
                report=replace(
                    self._config.report,
                    models=replace(
                        self._config.report.models,
                        attacking=declared.attacker_model,
                        attacking_temperature=declared.temperature,
                        attacking_reasoning_effort=declared.reasoning_effort,
                    ),
                ),
            )

    def cover(self, families: frozenset[Family]) -> None:
        """Set the families the next run covers. The third named writer, same lock.

        Refused while a run is going for the reason `instrument` is: a run awaiting
        approval was shown an estimate built from the families it was declared with,
        and narrowing them under that halt would make the confirmation a statement
        about a different run (ADR-0007).
        """
        with self._lock:
            in_flight = [
                run_id
                for run_id, record in self._runs.items()
                if record.status.in_flight
            ]
            if in_flight:
                raise RunsInFlight(in_flight)
            self._config = replace(self._config, families=families)

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
        echo_waived: bool = False,
    ) -> RunRecord:
        """Declare the estimate, start the run, and return once it has halted.

        The attestation is a constructed `Attestation` rather than three booleans:
        a statement that was not made cannot be constructed, so a run that reaches
        this line was authorised by a record that exists.

        **`nonce_planted` and `echo_waived` are two declarations and this is the one
        place they meet** (ADR-0025). The first decides whether the leakage family is
        measurable, because the canary's presence is what makes it so; the second
        decides whether a missing echo stops the run. A target that planted the value
        and will not repeat it on request is the case the second exists for, and it
        keeps its leakage family because the canary is in it.
        """
        with self._lock:
            issued = nonce in self._issued
            self._issued.discard(nonce)
        # A waived run carries no nonce and is not checked for one. The value is the
        # proof of control and the leakage canary, and a run that waives the first
        # and drops the second has no use for it: requiring one anyway would be a
        # button press standing in for a guard that is already gone (ADR-0007, as
        # amended). A waived run that *does* carry one is still checked, because a
        # caller who went through registration is telling the truth about it.
        if not issued and (nonce_planted or nonce):
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
            # Either declaration reaches the record as the one thing the record is
            # about: that this run started without the proof. `nonce_planted` says
            # the canary is absent, so nothing could echo; `echo_waived` says it is
            # present and will not be repeated on request. Two reasons, one
            # consequence, and the record carries the consequence (ADR-0025).
            proof_waived=echo_waived or not nonce_planted,
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
            # Deliberately not settled here. The worker is unwinding the graph with
            # this refusal in its hands and is the only thread that may say what the
            # run did — it attaches the result and then settles. A request that
            # settled the record itself would be a second writer of one terminal
            # state, and the loser's write is the one a poller reads: `declined` on
            # a record whose result is not attached yet.
            if not record.finished.wait(FINISHED_WAIT_SECONDS):
                # The worker is wedged, which is not something a declining operator
                # can be left holding. What this states is what the request knows —
                # the answer was recorded and nothing was sent — and the worker's
                # own write, if it ever lands, says the same thing.
                record.settle(RunStatus.DECLINED, _declined(approval.reason))
        return record


def _declined(reason: str) -> str:
    stated = reason or "declined at the approval interrupt"
    return f"{stated}. Nothing was sent to the target and nothing was spent"


def _traced(run_id: str, config: BenchConfig) -> TracedRun:
    """What the sink is told this run is: its id, and the models it was made under.

    The three identifiers come off the declared models the report already prints,
    so the trace and the report name the same instruments or neither does. The run
    id is the one the record holds — a trace whose id joined to nothing would be a
    trace nobody could bring back to a run (ADR-0026).
    """
    models = config.report.models
    return TracedRun(
        id=run_id,
        adjudicator_model=models.adjudicating,
        attacker_model=models.attacking,
        reference_model=models.calibration,
    )


def _execute(record: RunRecord, config: BenchConfig, pending: PendingApproval) -> None:
    """One run, on its own thread: the same entry point a terminal run takes.

    There is one code path to a target and this does not add a second — the
    attestation, the estimate, the halt, registration, the attempt loop and the
    adaptive layer are all reached through `run_calibration`, which is what the
    gate and `scripts/probe_target.py` reach them through.
    """
    try:
        _run(record, config, pending)
    finally:
        # In a `finally` and not at the end, because every way out of `_run` is a
        # run the worker has finished with: an abort, a transport failure and a
        # refusal are all states somebody is waiting to read.
        record.finished.set()


def _run(record: RunRecord, config: BenchConfig, pending: PendingApproval) -> None:
    """The body of one run. Everything `_execute` has to set an event around."""
    # Named against the seam's own type rather than passed straight through, so
    # that a signature drifting away from `Approve` is a typecheck failure here
    # and not a run that halts and never resumes.
    approve: Approve = pending.approve
    # One ledger for this run, and the instruments built against it — here, on this
    # run's own thread, because the sink a client records through is fixed when the
    # client is built and that used to happen at boot, before any run existed (#28).
    # Built before `run_calibration` and so before the estimate this run halts on: a
    # bench that could not build an instrument says so ahead of the confirmation,
    # never after it (`app.NAMED_BUT_UNUSABLE`, ADR-0007).
    ledger = UsageLedger()
    try:
        instruments = config.instruments_for(ledger)
    except (KeyError, ValueError) as unusable:
        record.settle(
            RunStatus.FAILED,
            (
                f"this run's instruments could not be built: {unusable}. Nothing "
                "was sent to the target and nothing was spent"
            ),
        )
        return
    try:
        result = run_calibration(
            cases=record.plan.cases,
            targets=[record.target],
            attestation=record.attestation,
            approve=approve,
            adjudicator=instruments.adjudicator,
            attacker=instruments.attacker,
            # The ledger those two report into, handed to the run that holds them.
            # `run_calibration` refuses one that already holds calls, which is what
            # keeps this a fresh one per run rather than a shared slot (ADR-0026).
            usage=ledger,
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
            trace=_traced(record.run_id, config),
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
