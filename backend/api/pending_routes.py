"""Deciding a pending route: its own surface, and the one path it takes to the bar.

The service half of the `/pending-routes` family, and
[ADR-0105](../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)
is the record that decides it exists at all. A route the adaptive layer found
against somebody's real agent is filed by the run that found it
(`bench/queued.py`), waits in `pending/routes.sqlite` (ADR-0104), and is decided
here: an attestation, an estimate per route, a halt, then the three reference
agents on two models in **one action**, and a decision per route.

**It is not a gate run's second job**, and the three reasons are ADR-0105's: the
admission memory is keyed on the model pair, so readings gathered a gate run at a
time are `Stale` on arrival; the library lease is exclusive and a gate run holds it
throughout; and a gate run produces a decision about *this bench*, which nothing
else takes (ADR-0018).

**The bar is `admitting.cross_model_bar` and this module does not have one.** It
consults the memory, measures what the memory could not answer, decides one
promotion per proposal and remembers what is worth remembering — the same function
`scripts/swap.py` calls, because a copy would be a second code path to a reference
agent, measured on an arithmetic nothing would notice drifting (ADR-0105 §5). What
is local here is the `Measure` seam's implementation: this deployment's own
equipment, served per model, which is the console's counterpart to
`scripts/admit.measure_on` and shares its arithmetic through `admission.counted`.

**The lease is held for the measurement and given back before the write.** A
measurement takes the library's lease, so a gate run started while it is happening
is refused by name and it is refused while a gate run holds it. It releases the
lease before handing the admitted cases to `entry.enter` — because `enter` takes
that lease itself, deliberately, and a caller that held one would be asking for a
lease it is already holding. That is ADR-0105 §3 observed rather than worked
around: the widening ADR-0033 declined, *take the lease in the caller*, is not
taken here either. A library taken by somebody else in the gap is a `LibraryBusy`
at the write, and the routes it would have written stay **pending** — nothing
measured is lost, because the memory now holds the reading and a second measurement
of them sends nothing (ADR-0032).

**The adaptive layer is switched off for an admission run on this surface.**
`cross_model_bar` discards any proposal made while measuring a proposal — "a
proposal made while measuring a proposal has had no admission run of its own, and
following it would be a loop with no end" — so a layer left on would be turns the
operator pays for and no surface reads. Switching it off is also what makes the
estimate exact rather than a ceiling (ADR-0058: a layer switched off puts nothing
on the wire).
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, replace
from enum import IntEnum
from pathlib import Path

from backend.api.gate_run_equipment import Equipment, a_library
from backend.api.pending_route_state import (
    CannotMeasure,
    MeasurementRecord,
    MeasurementStatus,
    ModelPass,
    NoLongerWaiting,
    NotMeasurable,
    RouteProgress,
    a_holder,
)
from backend.api.run_config import BenchConfig
from backend.api.run_state import NeverPresented, PendingApproval
from backend.api.run_status import PRESENT_WAIT_SECONDS
from backend.bench.adaptive.promotion import Promotion
from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.adjudication import Completion
from backend.bench.admission import admitted_library, counted
from backend.bench.admitting import Measure, cross_model_bar
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.contract import TargetConfig
from backend.bench.decided import RouteKey, criterion_of
from backend.bench.entry import AlreadyInTheLibrary, Entered, Entry, enter
from backend.bench.evaluator import Verdict
from backend.bench.lease import LibraryBusy, held_by, holding_the_library
from backend.bench.library import AdmissionReading, Case, DiscoveredBy, VerdictClass
from backend.bench.pending import (
    PENDING_ROUTES,
    AwaitingDecision,
    Decided,
    PendingRoutes,
    RouteState,
)
from backend.bench.registration import Attestation
from backend.bench.retirement import live_library
from backend.bench.rule import DECLARED_RULE
from backend.bench.selection import EVERY_CONSTRUCTION, AttackLayer
from backend.graph.approval import Approval, Approve
from backend.graph.budget import BudgetExceeded, CallPrice, RunBudget
from backend.graph.runstate import RunState
from backend.observability import TracedRun

NO_ADAPTIVE_LAYER = replace(
    EVERY_CONSTRUCTION,
    layers=frozenset(EVERY_CONSTRUCTION.layers - {AttackLayer.ADAPTIVE}),
)
"""What an admission run on this surface sends: every scored construction, no agent.

The module docstring is where this is argued. The consequence here is that the
estimate is a multiplication rather than a bound, so an operator selecting three
routes is shown a figure that is exact and attributable to the three of them.
"""

AgentsOn = Callable[[str], Equipment | None]
"""How this deployment serves the three reference agents on a named model.

A function of the model rather than the bound `Equipment` a gate run holds, because
the whole of this action is *two* models: a seam fixed to one could not measure the
cross-model bar at all, and one that took the pair would hide that they are served
one at a time. `gate_run_equipment.shipped_agents` is the implementation; `None`
back is a deployment that ships no reference agents, which is a stated refusal and
never an error.
"""


class Unmeasured(IntEnum):
    """Why an admission run did not happen, as the code the `Measure` seam returns.

    `cross_model_bar` returns an `int` where a model's measurement did not happen,
    and decides nothing on it — which is the property this surface needs most: a
    measurement that read one model and not the second leaves every route pending
    and undecided, because a partial reading is never a cross-model admission.

    Named values rather than the exit codes `scripts/console.py` declares: those
    are a process's answer to a shell, and nothing in the backend may reach a
    terminal's entry point (`test_admitting.py`). What a caller does with these is
    settle a record, and `stated` and `status` below are the one place each of
    those is decided.
    """

    DECLINED = 1
    ABORTED = 2
    NO_EQUIPMENT = 3
    NEVER_REGISTERED = 4

    def stated(self) -> str:
        """What this code means, in the words the record keeps.

        No fallback branch: a fifth member has to fail the typecheck rather than
        settle a measurement with nothing said about why.
        """
        match self:
            case Unmeasured.DECLINED:
                return (
                    "the approval interrupt was not answered with a yes, so nothing "
                    "was sent to a reference agent"
                )
            case Unmeasured.ABORTED:
                return (
                    "the admission run hit the ceiling that was confirmed and "
                    "stopped rather than exceeding it"
                )
            case Unmeasured.NO_EQUIPMENT:
                return (
                    "this deployment could not serve the three reference agents on "
                    "that model, so nothing was measured on it"
                )
            case Unmeasured.NEVER_REGISTERED:
                return (
                    "a reference agent did not echo its nonce, so it was never "
                    "attacked. A reading needs all three: an agent that never "
                    "registered is not an agent that resisted"
                )

    @property
    def status(self) -> MeasurementStatus:
        """The state a measurement stopped by this code settles in."""
        if self is Unmeasured.DECLINED:
            return MeasurementStatus.DECLINED
        if self is Unmeasured.ABORTED:
            return MeasurementStatus.ABORTED
        return MeasurementStatus.FAILED


EVERY_ROUTE_IS_STILL_PENDING = (
    "Every route this measurement was started over is still pending and still "
    "undecided: a reading on one model is not a cross-model admission (ADR-0012), "
    "and what was measured is in the admission memory, so measuring them again "
    "starts from the reading this one paid for (ADR-0032)"
)
"""What a measurement that did not finish says about the queue it did not change.

Said out loud on every one of those paths rather than left to be inferred from a
status, because the operator's question about a spend that stopped is what happened
to the routes — and *nothing* is an answer only if somebody writes it down.
"""


@dataclass(frozen=True)
class PendingRouteBench:
    """What deciding a pending route on this bench needs, and how it may be absent.

    Its own record beside `BenchConfig` and beside `GateRunBench`, on the latter's
    reasoning: a deployment that can run a gate has not thereby said it can measure
    on **two** models, and the second one is the whole of ADR-0012's bar. Every
    field defaults to absent, so a deployment acquires none of this by omission.
    """

    library: Path | None = None
    """The case library an admitted route is written into, through `entry.enter`.

    The same directory a gate run holds, handed in from one place at the factory
    rather than declared twice: two declarations that disagreed would be two
    libraries whose lease excluded nothing.
    """

    agents: AgentsOn | None = None
    models: tuple[str, ...] = ()
    """The two underlying models, in the order they are measured. Fewer than two is
    a bench that cannot reach ADR-0012's bar, and it says so (`NO_SECOND_MODEL`)."""

    queue: PendingRoutes = PENDING_ROUTES
    """The queue this surface reads and decides, at the one git-ignored location.

    A field with a default rather than a required argument, on
    `queued.file_proposals`'s reasoning: the restriction that matters is which
    surfaces reach the queue at all, and no signature can carry that. A caller that
    wants a different one says so, which is what every test does.
    """

    def equipment_for(self, model: str) -> Equipment | None:
        """How this deployment serves the three agents on that model, or `None`."""
        return None if self.agents is None else self.agents(model)


@dataclass(frozen=True)
class SelectedRoute:
    """One pending record this measurement puts to the bar, and what it will cost."""

    record: AwaitingDecision
    budget: RunBudget
    """What this one route costs: three reference agents on each of two models.

    Why per route is `MeasurementRecord.per_route`, which is where these end up.
    """

    @property
    def proposal(self) -> ProposedRoute:
        """The route as the bar takes it: the draft, and the attacker's own prose."""
        return ProposedRoute(
            case=self.record.draft, description=self.record.description
        )


class BenchPendingRoutes:
    """Every measurement this process has started, over one queue and one library.

    In memory and single process, which is what `BenchRuns` and `BenchGateRuns`
    are. What is *not* in memory is the exclusion: the lease is a file in the
    library's own directory, so a gate run in another process sees this
    measurement's hold and this measurement sees a gate run's.

    A third registry and not a dictionary inside either of the other two. The
    records are three kinds of fact with three kinds of status reached by three
    route families, and a registry that held any two would be the widening ADR-0105
    §1 asks a reader to stop at.
    """

    def __init__(self, config: BenchConfig, bench: PendingRouteBench) -> None:
        self._config = config
        self._bench = bench
        self._measurements: dict[str, MeasurementRecord] = {}
        self._pending: dict[str, PendingApproval] = {}
        self._lock = threading.Lock()

    @property
    def bench(self) -> PendingRouteBench:
        """What this bench can decide a pending route with, readable and frozen."""
        return self._bench

    def queue(self) -> tuple[AwaitingDecision | Decided, ...]:
        """Every record the queue holds, pending and decided, for one page.

        Both states, on `PendingRoutes.queue`'s reasoning: the page a decision
        writes to is the page it was started from.
        """
        return self._bench.queue.queue()

    def filed(self, route: str) -> AwaitingDecision | Decided | None:
        """One record this queue holds, by the key it is filed under, or `None`.

        Keyed off the queue's own listing rather than by rebuilding a `RouteKey`
        from the string: the key is `family-probe` and a family may hold a hyphen,
        so a parse here would be a second definition of a format `RouteKey` already
        owns.
        """
        return {record.route.filed_under: record for record in self.queue()}.get(route)

    def records(self) -> list[MeasurementRecord]:
        """Every measurement this bench has started, most recent first."""
        with self._lock:
            return list(self._measurements.values())[::-1]

    def record(self, measurement_id: str) -> MeasurementRecord | None:
        """One measurement's record, or `None` for an id this bench never issued."""
        with self._lock:
            return self._measurements.get(measurement_id)

    def holder(self) -> str:
        """What the lease on this bench's library says, or the empty string."""
        library = self._bench.library
        return held_by(library) if library is not None else ""

    def why_not(self) -> NotMeasurable | None:
        """Why a measurement may not start on this bench right now, or `None`.

        Read in the order a reader needs it: the facts about how the bench was
        built come before the one about this moment, because *this deployment ships
        no reference agents* is not answered by waiting. The route-shaped refusals
        are not here — they are about a request rather than about the bench, and a
        screen asks this one before anybody has selected anything.
        """
        bench = self._bench
        if bench.agents is None:
            return NotMeasurable.NO_REFERENCE_AGENTS
        if len(bench.models) < 2:
            return NotMeasurable.NO_SECOND_MODEL
        if any(bench.equipment_for(model) is None for model in bench.models):
            return NotMeasurable.NO_REFERENCE_AGENTS
        if bench.library is None or not a_library(bench.library):
            return NotMeasurable.NO_WRITABLE_LIBRARY
        if self._config.adjudicator is None:
            return NotMeasurable.NO_ADJUDICATOR
        if held_by(bench.library) or any(
            record.status.in_flight for record in self.records()
        ):
            return NotMeasurable.ALREADY_IN_FLIGHT
        return None

    def start(
        self,
        attestation: Attestation,
        price: CallPrice | None,
        routes: Sequence[str],
    ) -> MeasurementRecord:
        """Take the library, declare the estimate per route, and halt in front of it.

        The attestation is a constructed `Attestation` rather than three booleans,
        so a measurement that reaches this line was authorised by a record that
        cannot exist with a statement withheld. There is no argument here that
        could stand in for one, and no configuration that makes it optional
        (ADR-0105 §4).

        Returns once the measurement is holding its interrupt, which is before
        anything has been sent to a reference agent and while every route it names
        is still pending.
        """
        refusal = self.why_not()
        if refusal is not None:
            raise CannotMeasure(refusal, self.holder())
        bench = self._bench
        # Narrowed by `why_not`, which is the one place these absences are decided:
        # a second check here would be a second policy.
        assert bench.library is not None
        chosen = self._chosen(routes)

        measurement_id = str(uuid.uuid4())
        stack = ExitStack()
        try:
            # The lease first, before anything is served: a gate run started from
            # here on is refused by name, which is the second half of ADR-0033's
            # exclusion read from this side.
            stack.enter_context(
                holding_the_library(
                    bench.library, a_holder(attestation, measurement_id)
                )
            )
            targets = self._targets()
            selected = tuple(
                SelectedRoute(
                    record=record, budget=self._estimate([record], targets, price)
                )
                for record in chosen
            )
            budget = self._estimate(chosen, targets, price)
            record = MeasurementRecord(
                measurement_id=measurement_id,
                attestation=attestation,
                library=bench.library,
                models=tuple(bench.models),
                routes=tuple(one.record for one in selected),
                budget=budget,
                presented=budget.as_payload(),
                per_route=tuple((one.record.route, one.budget) for one in selected),
                passes=tuple(
                    ModelPass(
                        model=model,
                        of=_planned_attempts(len(chosen), len(targets)),
                    )
                    for model in bench.models
                ),
                progress=tuple(
                    RouteProgress(
                        route=one.record.route,
                        target=one.record.target,
                        description=one.record.description,
                        where="queued: nothing has been sent for this route",
                    )
                    for one in selected
                ),
            )
            pending = PendingApproval(self._config.approval_wait_seconds)
            with self._lock:
                self._measurements[measurement_id] = record
                self._pending[measurement_id] = pending
            threading.Thread(
                target=_execute,
                args=(record, self._config, self._bench, pending, stack),
                name=f"agentaudit-pending-routes-{measurement_id}",
                daemon=True,
            ).start()
        except LibraryBusy as busy:
            stack.close()
            raise CannotMeasure(NotMeasurable.ALREADY_IN_FLIGHT, str(busy)) from busy
        except BaseException:
            # The lease goes back on any failure before the thread exists: a lease
            # held by nothing is a library nobody may write to and nothing writing.
            stack.close()
            raise

        # The figures the interrupt is holding, not the ones declared above: the two
        # are built from the same budget, and returning the presented copy is what
        # makes that checkable rather than assumed.
        try:
            record.presented = pending.halted(PRESENT_WAIT_SECONDS)
        except NeverPresented:
            # The thread never reached the halt, so nobody will ever answer it and
            # nothing will release the lease. Settled and released here rather than
            # left to the approval wait: a library held for an hour by a measurement
            # that is not going to happen is a bench that refuses gate runs for an
            # hour, which is the failure the lease exists to prevent inverted.
            record.settle(
                MeasurementStatus.FAILED,
                (
                    "this measurement reached no approval interrupt, so it has no "
                    "estimate to confirm and it will not start. "
                    f"{EVERY_ROUTE_IS_STILL_PENDING}"
                ),
            )
            stack.close()
            raise
        return record

    def answer(self, measurement_id: str, approval: Approval) -> MeasurementRecord:
        """Answer one measurement's interrupt. A yes is the only thing that spends."""
        with self._lock:
            record = self._measurements.get(measurement_id)
            pending = self._pending.get(measurement_id)
            if record is None or pending is None:
                raise KeyError(measurement_id)
            if record.status is not MeasurementStatus.AWAITING_APPROVAL:
                raise NoLongerWaiting(record)
            # Moved before the graph is released and both under the lock, on
            # `BenchGateRuns.answer`'s reasoning: whatever the measuring thread
            # writes from here on, it writes last.
            if approval.confirmed:
                record.confirmed_by = approval.identity
                record.settle(
                    MeasurementStatus.MEASURING,
                    (
                        f"Confirmed by {approval.identity}: the selected routes are "
                        "going to the three reference agents on two models, under "
                        "the ceiling that was confirmed and aborting rather than "
                        "exceeding it. This bench's case library is held until the "
                        "measurement is finished"
                    ),
                )
            else:
                record.settle(MeasurementStatus.DECLINED, _declined(approval.reason))
            answered = pending.answer(approval)
        if not answered:
            # The wait ran out in the instant this answer arrived, so the graph has
            # already been told nobody answered.
            raise NoLongerWaiting(record)
        return record

    def _chosen(self, routes: Sequence[str]) -> tuple[AwaitingDecision, ...]:
        """The pending records this request named, or the refusal that stops it.

        Every refusal here happens **before** the library is held and before one
        message is sent: a measurement is three reference agents on two models per
        route, and an operator does not pay to be told that a route was already
        decided or that nothing live could score it.
        """
        if not routes:
            raise CannotMeasure(NotMeasurable.NOTHING_SELECTED)
        held = {record.route.filed_under: record for record in self.queue()}
        scorable = self._criteria()
        chosen: list[AwaitingDecision] = []
        for key in routes:
            record = held.get(key)
            if record is None:
                raise CannotMeasure(NotMeasurable.NOT_IN_THE_QUEUE, key)
            if isinstance(record, Decided):
                raise CannotMeasure(
                    NotMeasurable.ALREADY_DECIDED,
                    f"{record.route.stated()} was decided {record.state} — "
                    f"{record.reason}",
                )
            if record.criterion not in scorable:
                raise CannotMeasure(
                    NotMeasurable.NOTHING_LIVE_SCORES_IT, record.route.stated()
                )
            chosen.append(record)
        return tuple(chosen)

    def _criteria(self) -> frozenset[str]:
        """What this library's live cases can score, as criteria.

        A route's criterion is a digest of what a verdict on it *means* — the
        success condition, the judged condition, the verdict class and the
        preconditions (`decided.criterion_of`) — and a proposed route carries the
        criterion of the live case its episode was working on, copied rather than
        composed (`adaptive/proposal.proposed_from`). So a route whose criterion
        matches no live case is one whose objective was retired or edited
        underneath it: a probe nothing here can score, refused rather than measured
        (spec story 16).
        """
        library = self._bench.library
        if library is None:
            return frozenset()
        try:
            live = live_library(admitted_library(library))
        except (ValueError, OSError) as unreadable:
            # A library `admitted_library` will not load is not a library this
            # surface can decide anything against, and the caller is told so rather
            # than handed a stack trace: the refusal is the same one a bench with no
            # library gets, because the operator's next move is the same either way.
            raise CannotMeasure(
                NotMeasurable.NO_WRITABLE_LIBRARY,
                f"{library} could not be read as a case library: {unreadable}",
            ) from unreadable
        return frozenset(criterion_of(case) for case in live)

    def _targets(self) -> tuple[TargetConfig, ...]:
        """The three reference agents as this deployment describes them.

        Read off the equipment rather than assumed, and this is the one place the
        equipment is touched before the halt: serving sends nothing and spends
        nothing, so what it buys is an estimate declared against the agents that
        will actually be attacked — and a bench whose equipment will not serve
        refuses here, before an operator has been shown a figure to approve.
        """
        equipment = self._bench.equipment_for(self._bench.models[0])
        # Narrowed by `why_not`, which refused a bench that serves none.
        assert equipment is not None
        with equipment() as served:
            return tuple(served.targets)

    def _estimate(
        self,
        routes: Sequence[AwaitingDecision],
        targets: Sequence[TargetConfig],
        price: CallPrice | None,
    ) -> RunBudget:
        """What measuring those routes costs: the three agents, on each model.

        One declaration for the whole measurement and one per route, from this one
        function, so the rows and the total are the same arithmetic rather than two
        that could disagree — `RunBudget.declare` is linear in the cases it is
        given, and the routes are the cases.

        The agents are counted once per model because the pair is measured in one
        action: the figure the operator confirms is the whole of what deciding a
        route spends, and never half of it declared twice (ADR-0105 §2). At the
        declared rule and not at this bench's own, for the reason the admission run
        is run at it (`_measuring`) — an estimate at a denominator the run will not
        use is a figure the operator confirms and the bench does not spend.
        """
        return RunBudget.declare(
            cases=[record.draft for record in routes],
            targets=tuple(targets) * len(self._bench.models),
            rule=DECLARED_RULE,
            adaptive=self._config.adaptive,
            price=price,
            selection=NO_ADAPTIVE_LAYER,
        )


def _planned_attempts(cases: int, targets: int) -> int:
    """How many attempts one model's pass over these cases is planned for.

    The declared rule's attempts and never this bench's own, for the reason the
    admission run below gives: `promote` decides every proposal at the declared rule,
    so a pass counted against a console's tuned `attempts_per_case` (ADR-0025) would
    draw a bar against a denominator the decision was not made on.

    Registration probes are not in it. They are calls and this counts attempts, which
    is the same distinction `budget.py` draws between the two figures it keeps.
    """
    return cases * DECLARED_RULE.attempts_per_case * targets


def _declined(reason: str) -> str:
    stated = reason or "declined at the approval interrupt"
    return (
        f"{stated}. Nothing was sent to a reference agent, nothing was spent, and "
        f"nothing was written to the case library. {EVERY_ROUTE_IS_STILL_PENDING}"
    )


def _execute(
    record: MeasurementRecord,
    config: BenchConfig,
    bench: PendingRouteBench,
    pending: PendingApproval,
    stack: ExitStack,
) -> None:
    """One measurement, on its own thread.

    The `finally` is the whole of the lease's release: whatever this measurement
    does, the library goes back. It is closed a second time inside `_decide`, before
    the write — `ExitStack.close` is idempotent, and the two calls are the module
    docstring's handoff to `enter`'s own lease.
    """
    try:
        _decide(record, config, bench, pending, stack)
    except Exception as failure:
        record.settle(
            MeasurementStatus.FAILED,
            (
                f"the measurement stopped rather than decided anything: {failure}. "
                f"{EVERY_ROUTE_IS_STILL_PENDING}"
            ),
        )
    finally:
        # Beside the lease for the same reason: whatever this measurement did, no
        # pass is left drawn as one still filling. A pass the run finished keeps its
        # counts; anything else is a pass that did not happen (`ModelPass.state`).
        record.unmeasured()
        stack.close()


def _decide(
    record: MeasurementRecord,
    config: BenchConfig,
    bench: PendingRouteBench,
    pending: PendingApproval,
    stack: ExitStack,
) -> None:
    """Halt, measure the selected routes on both models, and answer each of them."""
    # Named against the seam's own type rather than passed straight through, so that
    # a signature drifting away from `Approve` is a typecheck failure here and not a
    # measurement that halts and never resumes.
    approve: Approve = pending.approve
    # The halt, in front of the figures this record is holding and before anything
    # is served: the same `PendingApproval` seam `POST /runs` and
    # `POST /gate-runs/{id}/approval` answer, and there is no second copy of it
    # (ADR-0105 §4). The admission runs below are handed the same seam and are
    # answered from it without halting again, which is what makes *one action* one
    # approval rather than one per model.
    approval = approve(record.presented)
    if not approval.confirmed:
        refused = (
            MeasurementStatus.DECLINED
            if pending.answered
            else MeasurementStatus.UNANSWERED
        )
        record.settle(refused, _declined(approval.reason))
        return

    adjudicator = config.adjudicator
    # Narrowed by `why_not`, which refused a bench with no adjudicating instrument.
    assert adjudicator is not None

    outcome = cross_model_bar(
        proposals=[
            ProposedRoute(case=one.draft, description=one.description)
            for one in record.routes
        ],
        models=record.models,
        # The record's own attestation, never one re-made here: the operator
        # attested in an earlier request and this module constructs none.
        attestation=record.attestation,
        approve=approve,
        adjudicator=adjudicator,
        adjudicator_model=config.report.models.adjudicating,
        price_per_call=record.budget.estimate.price,
        measure=_measuring(record, config, bench),
        # The bar's prose kept on the record rather than printed: this surface has
        # no terminal, and the consultation's report is what an operator checks a
        # decision against.
        say=record.say,
    )
    if isinstance(outcome, int):
        code = Unmeasured(outcome)
        record.settle(code.status, f"{code.stated()}. {EVERY_ROUTE_IS_STILL_PENDING}")
        return

    rejections, promotions, consulted = outcome
    record.say(consulted.reported(promotions))
    record.say(rejections.stated())

    # The lease goes back **before** the write, because `enter` takes it itself
    # (module docstring, ADR-0033). Everything above this line has been measured and
    # paid for, so what follows is a refusal to write and never a refusal to run.
    stack.close()
    admitted = [one.case for one in promotions if one.case is not None]
    entry: Entry | None = None
    busy = ""
    if admitted:
        try:
            entry = enter(
                admitted,
                record.library,
                holder=(
                    f"{record.attestation.identity}, writing an admitted route from "
                    "the console"
                ),
            )
        except LibraryBusy as held:
            busy = str(held)
    if entry is not None:
        record.entry = entry
        record.say(entry.stated())

    answers = _Written(entry)
    decided = 0
    for one, promotion, consult in zip(
        record.routes, promotions, consulted.consulted, strict=True
    ):
        row = record.progress_for(one.route)
        answer = answers.answer_for(promotion, record.library)
        if answer is None:
            # Admitted, and the write did not happen. The route stays pending with
            # its payload, because a row that said *admitted* with no record behind
            # it would be a queue disagreeing with the library it describes.
            if row is not None:
                row.where = (
                    "still pending: this route cleared the bar and the library "
                    f"could not be written to. {busy}"
                )
            continue
        state, reason, entered_as = answer
        try:
            bench.queue.decide(one.route, state=state, reason=reason)
        except (KeyError, ValueError) as refused:
            if row is not None:
                row.where = f"still pending: the queue refused the decision. {refused}"
            continue
        decided += 1
        if row is not None:
            # Whether the counts were bought here or read out of the memory, off the
            # consultation this run made rather than off a second reading of it: a
            # route answered from memory sent nothing, and the row is where the
            # operator can see which of the two they paid for (ADR-0032).
            row.settle(
                state, reason, entered_as, remembered=consult.remembered is not None
            )

    record.settle(
        MeasurementStatus.ANSWERED,
        (
            f"{decided} of {len(record.routes)} route(s) decided, confirmed by "
            f"{record.confirmed_by}, inside the ceiling that was confirmed. A "
            "decided route's payload went with its decision (ADR-0104 §4); a route "
            "this measurement could not answer is still pending with its own"
            + (f". {busy}" if busy else "")
        ),
    )


@dataclass(frozen=True)
class _Written:
    """What one `enter` left behind, as the question each promotion asks of it.

    A small type over the `Entry` rather than two dictionaries built at the call
    site, because the three answers below are one decision — written, already held,
    or not written at all — and a caller that rebuilt them would be free to reach a
    fourth. `None` is an `enter` that did not happen, which is the library having
    been taken by somebody else between the release and the write.
    """

    entry: Entry | None

    @property
    def written(self) -> dict[str, Entered]:
        """The records this write created, by the case id each was proposed under."""
        return (
            {}
            if self.entry is None
            else {one.case.id: one for one in self.entry.entered}
        )

    @property
    def already(self) -> dict[str, AlreadyInTheLibrary]:
        """The routes this library already held, by the id they were proposed under."""
        return (
            {}
            if self.entry is None
            else {one.proposed_as: one for one in self.entry.held}
        )

    def answer_for(
        self, promotion: Promotion, library: Path
    ) -> tuple[RouteState, str, str] | None:
        """What the queue records for this promotion: the state, the reason, the file.

        `None` for a route the bar admitted and the library did not take — the one
        case that leaves a route pending after a measurement that finished, because
        a row saying *admitted* with no record behind it would be a queue
        disagreeing with the library it describes.
        """
        if promotion.case is None:
            return (
                RouteState.REJECTED,
                f"the cross-model bar refused this route: {promotion.outcome.stated()}",
                "",
            )
        case_id = promotion.proposal.case.id
        entered = self.written.get(case_id)
        if entered is not None:
            return (
                RouteState.ADMITTED,
                f"admitted on the cross-model bar and written into {library} as "
                f"{entered.path.name}: {promotion.outcome.stated()}",
                entered.path.name,
            )
        held = self.already.get(case_id)
        if held is not None:
            return (
                RouteState.ADMITTED,
                "admitted on the cross-model bar, and this library already holds "
                f"the route as {held.held_as}, so nothing was written: "
                f"{promotion.outcome.stated()}",
                held.held_as,
            )
        return None


def _measuring(
    record: MeasurementRecord, config: BenchConfig, bench: PendingRouteBench
) -> Measure:
    """This deployment's `Measure`: the three agents on one model, counted.

    The console's counterpart to `scripts/admit.measure_on`, and the arithmetic is
    not copied from it — `admission.counted` is the one place a run becomes the
    number that decides whether a case may reach a user, and both callers go
    through it. What differs is only how the agents are served: a terminal serves
    them itself, and this asks the equipment seam a deployment declares.

    A closure rather than a method, because what it holds is one measurement's
    progress rows: the route-by-route reporting this surface owes an operator
    (spec story 10) is written as the models are walked, and there is no other
    moment that knows which routes are on the wire right now.
    """

    def measure(
        *,
        cases: Sequence[Case],
        model: str,
        adjudicator: Completion,
        adjudicator_model: str,
        attestation: Attestation,
        approve: Approve,
        price_per_call: CallPrice | None,
    ) -> dict[str, AdmissionReading] | int:
        equipment = bench.equipment_for(model)
        if equipment is None:
            return Unmeasured.NO_EQUIPMENT
        on_the_wire = tuple(RouteKey.of(case) for case in cases)
        record.moved(on_the_wire, f"measuring against the three agents on {model}")
        with equipment() as served:
            budget = RunBudget.declare(
                cases=list(cases),
                targets=served.targets,
                rule=DECLARED_RULE,
                adaptive=config.adaptive,
                price=price_per_call,
                selection=NO_ADAPTIVE_LAYER,
            )
            # The pass's bar counts through this state, which is the run's own and
            # not a copy: the attempts land on the admission run's thread, and
            # `ModelPass.attempted` reads the length at the moment a screen asks.
            progress = RunState(budget=budget)
            record.measuring_on(
                model,
                progress,
                _planned_attempts(len(cases), len(served.targets)),
            )
            try:
                result = run_calibration(
                    cases=list(cases),
                    targets=served.targets,
                    attestation=attestation,
                    plant_nonce=served.plant,
                    drop_namespace=served.drop,
                    approve=approve,
                    adjudicator=adjudicator,
                    # The declared rule, and deliberately not this bench's own. A
                    # console may tune `attempts_per_case` (ADR-0025), and `promote`
                    # decides every proposal at the declared rule while the memory
                    # files its conditions under it (ADR-0032) — so an admission run
                    # at another denominator would be counts read against a bar
                    # nobody declared, and remembered as though they were not
                    # (ADR-0003).
                    rule=DECLARED_RULE,
                    adaptive=config.adaptive,
                    # No agent, and the module docstring is why.
                    selection=NO_ADAPTIVE_LAYER,
                    budget=budget,
                    run_state=progress,
                    # A fresh id per admission run and never this measurement's,
                    # which is what `scripts/admit.measure_on` emits too: the two id
                    # fields a trace carries are a run's and a gate run's, and a
                    # measurement is neither (ADR-0018).
                    trace=TracedRun(
                        id=str(uuid.uuid4()),
                        adjudicator_model=adjudicator_model,
                        reference_model=model,
                    ),
                    discovered_by=DiscoveredBy.ADAPTIVE,
                )
            except BudgetExceeded:
                return Unmeasured.ABORTED
        if not result.approval.proceeded:
            return Unmeasured.DECLINED
        if any(run.registration.refused for run in result.target_runs):
            return Unmeasured.NEVER_REGISTERED
        record.measured_on(model)
        record.moved(on_the_wire, f"read on {model}")
        by_name = {run.target.name: run for run in result.target_runs}
        return {
            case.id: counted(
                model,
                hardened=_verdicts(by_name[served.hardened], case),
                weak=_verdicts(by_name[served.weak], case),
                trivial=_verdicts(by_name[served.trivial], case),
                adjudicator=(
                    adjudicator_model
                    if case.verdict_class is VerdictClass.JUDGED
                    else None
                ),
            )
            for case in cases
        }

    return measure


def _verdicts(target_run: TargetRun, case: Case) -> list[Verdict]:
    """This case's verdicts against one agent, in the order the attempts ran."""
    return [
        attempt.verdict for attempt in target_run.attempts if attempt.case_id == case.id
    ]
