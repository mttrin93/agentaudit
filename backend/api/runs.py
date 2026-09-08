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

**What is left here is the service, and the four modules beside it are the rest.**
`run_status.py` holds the vocabulary a run is described in, `run_config.py` what a
run is measured with, `run_state.py` one run's record and the halt it waits at,
`recorded.py` what is written down about a run so a restarted process can still
answer or close its halt (ADR-0034).
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
from datetime import UTC, datetime
from typing import NoReturn

from backend.api.recorded import (
    CONFIRMED_AND_NOT_RUN,
    RECORDED_RUNS,
    RECOVERED_DECLINE,
)
from backend.api.recorded import (
    HaltRecovered as HaltRecovered,
)
from backend.api.recorded import (
    RecordedRun as RecordedRun,
)
from backend.api.recorded import (
    RecordedRuns as RecordedRuns,
)
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
from backend.bench.elective import ElectiveSelection
from backend.bench.library import Family, LibraryVersion
from backend.bench.narration import NarrativeFailure
from backend.bench.nonce import issue_nonce
from backend.bench.payload import GateCitation
from backend.bench.registration import Attestation
from backend.bench.selection import AttackSelection
from backend.bench.signing import SignedArtefact
from backend.bench.usage import UsageLedger
from backend.graph.approval import Approval, Approve, forget_halt
from backend.graph.budget import (
    BudgetExceeded,
    CallPrice,
    RunBudget,
)
from backend.graph.runstate import RunState
from backend.observability import TracedRun


class BenchRuns:
    """Every run this process has started, and every nonce it has issued.

    **Two registries and they are deliberately two.** `self._runs` holds the runs
    *this* process started — the live records, with their counters, their plans and
    the rendezvous a request answers a halt through. What earlier processes wrote
    down is read from `RecordedRuns`, and it is a declaration rather than a run: no
    counters, no plan, no target (ADR-0034). They are two types and they stay two,
    because a signature that took either would be the place a restored row acquired
    a plausible-looking plan — so `records()` returns run records only and
    `recovered` returns the other thing.

    **The live records are held and the recorded ones are read.** A dictionary is
    right for the first: those runs exist because this process started them, and
    their state is in memory by construction. It is wrong for the second, on
    ADR-0029 decision 2's principle that the file is the authority and the object
    holds no state — a cached row would be this process's opinion of a row a second
    deployment over the same volume may have answered since, and the one thing that
    must not happen to an interrupt is being answered twice.

    A queue is still P1, and so is a run started here surviving a restart *as a
    run*: what survives is enough to answer or to close the halt it left behind.
    """

    def __init__(
        self, config: BenchConfig, recorded: RecordedRuns = RECORDED_RUNS
    ) -> None:
        self._config = config
        self._issued: set[str] = set()
        self._runs: dict[str, RunRecord] = {}
        self._pending: dict[str, PendingApproval] = {}
        self._lock = threading.Lock()
        self._answering = threading.Lock()
        self._recorded = recorded
        # Every row on disk, reconciled on the way in, and nothing kept: a row still
        # saying *running* is a run `RunStatus.in_flight` calls still going, so
        # leaving one unread would refuse every `instrument` call for the lifetime of
        # this deployment on behalf of a process that no longer exists (ADR-0034).
        # The reconciliation is written back by `recovered`, so what is needed here
        # is the halts it settled and not the rows.
        #
        # Retention, and this is the half nothing could reach before: a halt whose
        # process ended is settled by nobody, so its checkpoint — and the estimate a
        # person was asked to confirm — would be kept until somebody deleted the file
        # by hand (ADR-0028's consequences). The rows are what know which halts are
        # over, and they name the threads.
        #
        # Not caught. A checkpoint store this cannot open is one the next run cannot
        # halt against either, so a bench that carried on would take an operator's
        # attestation and then fail at the interrupt — after the request that asked
        # for the estimate, which is the wrong end (ADR-0007).
        for run in recorded.recovered():
            if not run.status.in_flight:
                forget_halt(run.thread_id)

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

    def _refuse_while_a_run_is_going(self) -> None:
        """Refuse to move a declared input while any run of this bench is in flight.

        One guard for the three named writers below, and the same guard rather than
        three: a run awaiting approval has been shown an estimate built from the
        settings, the families and the selection it was declared with, and ADR-0007's
        whole mechanism is that nothing exceeds what a human confirmed. Three copies
        would only have to differ once for one of the three writes to move under an
        open halt.

        **Called under `self._lock`, by every caller, and it does not take the lock
        itself** — the check and the `replace` that follows it are one critical
        section, or a run could start between them. `RunsInFlight` names the runs so
        an operator can wait for them or decline them rather than guess; `cite` is
        deliberately not a caller, because a gate citation is provenance a run in
        flight has already copied into its own payload.
        """
        in_flight = [
            run_id for run_id, record in self._runs.items() if record.status.in_flight
        ]
        if in_flight:
            raise RunsInFlight(in_flight)

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
            self._refuse_while_a_run_is_going()
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

    def cover(self, families: frozenset[Family], elective: ElectiveSelection) -> None:
        """Set what the next run covers: the six, and the tier. Third writer, same lock.

        Refused while a run is going for the reason `instrument` is: a run awaiting
        approval was shown an estimate built from the families it was declared with,
        and narrowing them under that halt would make the confirmation a statement
        about a different run (ADR-0007).

        **Both in one call, because they are one statement.** What the next run covers
        has one answer, and a writer that could set the six without restating the tier
        would leave the two halves declared by two different requests — the shape
        `select` already refuses one level down
        ([ADR-0088](../../docs/adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)
        §8). Two arguments and never one set of nine names: the two closed sets are
        what keeps an elective family out of the counts the gate is decided over
        (ADR-0035 §1).

        It takes a constructed `ElectiveSelection` rather than a list of names, on
        `select`'s terms: a selection naming a family twice is refused before it
        reaches this bench, and the route turns that into a 422.
        """
        with self._lock:
            self._refuse_while_a_run_is_going()
            self._config = replace(self._config, families=families, elective=elective)

    def select(self, selection: AttackSelection) -> None:
        """Set which layers the next run runs, and which constructions inside them.

        The fourth named writer on `BenchConfig` and the **third** of the console's
        writes — `cite` is the fourth writer's senior and is no route at all
        (ADR-0023). Same lock, refused while a run is going for the
        reason `cover` is: a run awaiting approval was shown an estimate built from
        the selection it was declared with, and narrowing it under that halt would
        make the confirmation a statement about a cheaper run than the one that ran
        (ADR-0007, ADR-0058).

        It takes a constructed `AttackSelection` rather than two sets of names, so a
        selection that scores nothing is refused before it reaches this bench — the
        type is where that refusal lives, and the route turns it into a 422.
        """
        with self._lock:
            self._refuse_while_a_run_is_going()
            self._config = replace(self._config, selection=selection)

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
        """One run's record, or `None` for an id this process did not start.

        Run records only, and a recovered row is deliberately not one of them: it
        has no counters, no plan and no result, so a caller reading progress off it
        would be reading defaults (ADR-0034). `recovered` below is how a route asks
        the other question, and it answers with the other type.
        """
        with self._lock:
            return self._runs.get(run_id)

    def recovered(self, run_id: str) -> RecordedRun | None:
        """What an earlier process of this bench wrote down about one run.

        The read a route makes when `record` says nothing: a `404` that told an
        operator no run of that id was ever started, of a run this bench had
        started and halted, was the false statement issue #61 was filed about.

        Reconciled on the way out, so a halt whose hour ran out while this process
        was up reads as unanswered here too rather than as still waiting.
        """
        return self._recovered_row(run_id)

    def _recovered_row(self, run_id: str) -> RecordedRun | None:
        """One recorded run, reconciled, its dead halt forgotten, and cached.

        The one lookup for both callers — this bench's `recovered` read and the
        answer path — because the four steps are one operation and two copies of
        them would be two places for the reconciliation and the deletion to come
        apart.

        **Read from the file every time**, on ADR-0029 decision 2's principle that
        the file is the authority: a row cached here would be this bench's opinion
        of a row a second deployment over the same volume may have answered since,
        and an interrupt answered twice is the one thing the live path takes a lock
        to prevent. The cost is one `get` on a route nobody calls in a loop.

        **Reconciled here and not only at construction**, because the hour runs out
        *while* this process is up: a halt that was answerable when the bench was
        built is not answerable forty minutes later, and nothing wakes to notice.

        **And the halt is forgotten here**, which is the case boot-time pruning
        cannot reach. A halt whose process ended is settled by nobody, so if it
        expires while this bench is running, the deletion has to happen at the first
        read that observes the expiry — otherwise the approver identity in it
        outlives the run's answerability until the next restart, against ADR-0034
        decision 8.
        """
        found = self._recorded.find(run_id)
        if found is None:
            return None
        row = self._recorded.reconcile(found)
        if not row.status.in_flight:
            forget_halt(row.thread_id)
        return row

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
            # The declared budget under the schedules this bench is set to, through
            # the one join: selecting both is two episode sets per family, so the
            # ceiling doubles and the figure an operator confirms doubles with it. The
            # same `under` call is made where the layer spends it (`run_calibration`),
            # off the same selection, so what is priced and what runs are one answer
            # (ADR-0096).
            adaptive=self._config.adaptive.under(self._config.selection.schedules),
            price=price,
            # The estimate moves when the selection moves: a layer switched off is
            # nothing on the wire, and the operator sees the price of what they just
            # turned off rather than confirming a figure for a run nobody asked for
            # (ADR-0058). The scored half of that narrowing is already in `plan.cases`.
            selection=self._config.selection,
        )
        pending = PendingApproval(self._config.approval_wait_seconds)
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            # Minted here and not inside `ApprovalRun`, which is where it used to
            # come from: a name the worker thread generates and never returns is a
            # durable checkpoint nothing else can look up, so the halt outlived the
            # process and the id needed to reach it did not (ADR-0034). Derived from
            # the run id so that a reader with one has the other.
            thread_id=f"run-{run_id}",
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
        # Written before the thread starts, and it has to be: `start` returns once
        # the graph is holding its interrupt, so a row written any later would leave
        # a window in which a halt exists on disk and the run around it does not.
        # Not caught, either — nothing has been sent to the target yet, so a store
        # that will not open is a deployment fault the operator should hear about
        # before they are asked to confirm a spend rather than after (ADR-0034).
        self._recorded.record(
            RecordedRun.of(record, self._config.approval_wait_seconds)
        )

        threading.Thread(
            target=_execute,
            args=(record, self._config, pending, self._recorded),
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
            # Not this process's run, which used to be the end of the matter and a
            # false statement: the human was told no run of that id had been
            # started, of a run this bench had started, halted and estimated.
            self._answer_a_recovered_halt(run_id, approval)
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
            # The row moves off *awaiting an answer* here, and it has to move here.
            # A process that died mid-suite would otherwise leave a row saying the
            # run is still at its interrupt — and a human inside the hour would be
            # offered a second consent for a spend that had already happened, which
            # is the one thing ADR-0007's halt exists to make impossible.
            # `RecordedRuns.record` is what keeps this from overwriting a terminal
            # row the worker has already written.
            self._recorded.record(
                RecordedRun.of(record, self._config.approval_wait_seconds)
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

    def _answer_a_recovered_halt(self, run_id: str, approval: Approval) -> NoReturn:
        """Answer a halt this process did not start, and refuse the request saying so.

        Always refuses, and `NoReturn` is how the caller above knows: a
        `RunResponse` is built from a run record's plan, counters and presented
        estimate, and a recovered run has none of those. So there is nothing to
        respond *with*, and the choice is between a refusal that states what was
        recorded and a response assembled out of defaults — which would be a
        restored row wearing a run record's clothes, the one thing ADR-0034 exists
        to prevent.

        **What is recorded is three different things and they stay three.** A no is
        `DECLINED`, in full and with the operator's reason: a refusal needs no
        target and no graph, the run had spent nothing, and losing the difference
        between *refused by a human* and *nobody answered* is the distinction
        ADR-0028 was built to keep. A yes is `FAILED` — the run cannot be started,
        because the endpoint and its credential are deliberately not on the record
        — and it carries `confirmed_by`, so it reads as answered and not run rather
        than as either of the two spend-nothing outcomes it is not. A halt past its
        hour was `UNANSWERED` before this request arrived and stays that way.

        **An interrupt is answered once, and that is this lock's whole job.** The
        live path gets it from `PendingApproval.answer`, which takes a lock of its
        own so that a confirmation landing in the instant the wait closes is either
        taken or refused and never both. There is no `PendingApproval` here, so
        without one, two requests reading an answerable row at the same moment would
        both write and both be told their answer was recorded — a decline and a
        confirmation recorded for one halt, which is the distinction ADR-0028 exists
        to keep, lost in a new way. Its own lock rather than `self._lock`, which
        guards this bench's live records and its configuration and should not be
        held across a write to a file.
        """
        with self._answering:
            row = self._recovered_row(run_id)
            if row is None:
                # The only `KeyError` left, and the honest one: nothing was ever
                # written under this id, in this process or in any earlier one.
                raise KeyError(run_id)

            if not row.answerable_at(datetime.now(tz=UTC)):
                # Already terminal — past its hour, or answered once already. The
                # request is refused and *nothing is written*, which is why the
                # refusal below has to say so rather than claim an answer was
                # recorded (`HaltRecovered`).
                raise HaltRecovered(row, answered=False)

            answered = (
                replace(
                    row.settled(RunStatus.FAILED, CONFIRMED_AND_NOT_RUN),
                    confirmed_by=approval.identity,
                )
                if approval.confirmed
                else row.settled(
                    RunStatus.DECLINED,
                    f"{_declined(approval.reason)}. {RECOVERED_DECLINE}",
                )
            )
            self._recorded.record(answered)
            # The halt is over the instant this answer is recorded, whichever way
            # it went, so the checkpoint holding its estimate goes with it.
            forget_halt(answered.thread_id)
            raise HaltRecovered(answered, answered=True)


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


def _execute(
    record: RunRecord,
    config: BenchConfig,
    pending: PendingApproval,
    recorded: RecordedRuns,
) -> None:
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
        #
        # The row and the halt go *before* the event, so that `finished` means the
        # record is complete rather than complete in this process's memory: a
        # declining request wakes on it and reads the record, and a restart that
        # landed between the two would find a row still saying this run was going.
        # `_filed` swallows its own failures, so it cannot be why the event is
        # never set.
        _filed(recorded, record, config)
        record.finished.set()


def _filed(recorded: RecordedRuns, record: RunRecord, config: BenchConfig) -> None:
    """Write down where this run got to, and forget the halt it is no longer at.

    Before `finished.set()`, and the caller says why: that event is what a declining
    request waits on, so it has to mean *the record is complete* rather than
    complete in this process's memory. The two things here are one fact — the run is
    over, so the row is terminal and the checkpoint has nothing left to answer.

    **Every exception is caught, and it is `_published`'s argument rather than a
    reflex.** The suite ran and the target was measured; what would have failed
    here is the bookkeeping, and a run marked failed for it would be reporting a
    storage fault as a fact about somebody's agent. It also runs on the run's own
    thread, where anything that escaped would be raised into a `finally` nobody is
    catching.

    What that costs is stated rather than absorbed: a row that could not be written
    stays as the last thing this bench said about the run, so a process that
    restarts may reconcile a finished run as one that stopped part-way. That is the
    conservative direction — it under-claims about a run that completed and never
    over-claims about one that did not.
    """
    try:
        recorded.record(RecordedRun.of(record, config.approval_wait_seconds))
        forget_halt(record.thread_id)
    except Exception:  # noqa: BLE001 - a storage fault is not a fact about a target
        return


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
            # The pair that explains this run's successes. A run against a
            # target is what a finding is about (ADR-0018), so this is the
            # entry point that narrates and the gate's is not (ADR-0030).
            narrator=instruments.narrator,
            # The ledger those two report into, handed to the run that holds them.
            # `run_calibration` refuses one that already holds calls, which is what
            # keeps this a fresh one per run rather than a shared slot (ADR-0026).
            usage=ledger,
            rule=config.rule,
            adaptive=config.adaptive,
            # Which layers run, and which constructions inside them. The cases were
            # filtered against it before the estimate; what it decides here is whether
            # the second layer opens an episode at all (ADR-0058).
            selection=config.selection,
            # The ceiling on the record, never one re-declared here: the operator
            # confirmed these figures in an earlier request, and a run held to a
            # limit recomputed against whatever the library holds by now would be
            # a run held to a number nobody saw.
            budget=record.budget,
            run_state=record.run_state,
            planted_nonces={record.target.name: record.nonce},
            proof_waived=record.proof_waived,
            trace=_traced(record.run_id, config),
            # The halt this run's record already names, rather than one minted
            # inside the graph: the record and the checkpoint have to agree, or the
            # id a restart looks the halt up by names nothing (ADR-0034).
            thread_id=record.thread_id,
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
    narrations = target_run.narrations
    if isinstance(narrations, NarrativeFailure):
        # The fourth reading, on the sentence a poller reads, for the reason the
        # waived-proof clause above is on it: everything else this sentence carries
        # goes quiet under it — `disagreements` is `None`, so the review queue
        # clause below is skipped, and a run that filed nothing adds no filing
        # clause either — so a run whose instruments broke would otherwise read as
        # an ordinary finish. The report is already published above and deliberately
        # is: no column of it is contingent on the judge having run (ADR-0044), so
        # what a broken instrument costs is the explanation and never the
        # measurement (ADR-0050).
        finished = (
            f"{finished}, and its narrative instruments ran and failed — "
            f"{narrations.stated()}"
        )
    queue = target_run.disagreements
    if queue:
        # The review queue, on the sentence a poller reads. The findings and the
        # disagreements themselves are on `record.result`, which is the record they
        # are logged in; what this adds is that a human is *told* there are some,
        # because the weaker of the bench's two human-in-the-loop instances is a
        # list somebody has to be handed rather than a field somebody has to think
        # to look at (ADR-0004, PLAN §3). A count and never a resolution: neither
        # instrument is corrected and the rates above do not move.
        finished = (
            f"{finished}. {len(queue)} of its findings are on the review queue, "
            "where the success condition and the judge read one transcript "
            "differently: the verdicts stand and the disagreements are for a human"
        )
    if result.filing.filed or result.filing.judged:
        # What this run contributed to the long-term memory, on the same sentence
        # and for the same reason the review queue is: the records are on
        # `record.result`, and what a poller is *told* is that the store grew and
        # that something was kept out of it. A judged family files nothing
        # (ADR-0004) and an operator who finds the store empty of one has to be
        # able to read that as a refusal rather than as a broken write.
        #
        # A count and never a rate. Nothing filed here moved a number: the write
        # is the last thing a run does, after every instrument in it has read
        # (ADR-0031).
        #
        # The count is this run's contribution and deliberately not the store's
        # growth, which is what the closing clause says: `Precedent.key` is a
        # digest of the record, so a finding an earlier run already filed is the
        # same row — and a sentence claiming the store gained this many rows would
        # be a number a poller could not check (`filing.Filing.filed`).
        finished = (
            f"{finished}. {len(result.filing.filed)} precedent(s) were filed to "
            f"the long-term memory and {len(result.filing.judged)} judged "
            "case(s) were withheld from it, because precedent holds "
            "deterministic findings only. Both counts are per case per target, "
            "so a case attempted ten times counts once. Filed after this run "
            "had finished "
            "reading, so nothing filed informed a fix this run wrote — and a "
            "record an earlier run already filed is the same row rather than a "
            "new one, so this is what the run contributed and not what the store "
            "grew by"
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
        return artefact_for(
            result,
            record.plan.cases,
            config.rule,
            config.report,
            config.selection,
            # The plan's own gaps, off the record the estimate was built from: the
            # families this caller declared away reach the signed document rather
            # than only this run's own response (ADR-0075).
            record.plan.gaps,
            # What this run asked the elective tier for, off the configuration it was
            # started under and never re-derived from what it measured: a family
            # requested and unmeasurable has to stay distinguishable from one nobody
            # asked for (ADR-0035 §5, ADR-0088 §4).
            config.elective,
        )
    except Exception as unpublished:
        return Unsigned(
            "this run has no signed report: the run finished and its artefact could "
            f"not be assembled or signed — {unpublished}. The measurement happened "
            "and is on the record; nothing unsigned is served in its place"
        )
