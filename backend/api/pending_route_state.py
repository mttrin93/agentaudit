"""One pending-route measurement's record, and the refusals in front of it.

The lower half of the `/pending-routes` side, and it stands to
`pending_routes.py` as `gate_run_state.py` stands to `gate_runs.py`: this is
what a measurement *is* while it happens, together with the vocabulary that
describes it — why one may not start (`NotMeasurable`, `CannotMeasure`), where one
got to (`MeasurementStatus`), where each route in it got to (`RouteProgress`), and
who the lease says is holding the library (`a_holder`). The service that drives a
record through all of it is in the module beside this one.

**A measurement is not a gate run and is not a run**, and `app.PENDING_ROUTES_ROUTE`
is where the three kinds of fact are told apart. The consequence here is the shape
of everything below: `MeasurementRecord` never appears in a signature with
`RunRecord` or `GateRunRecord`, it carries no run id and no gate run id, and there
is no status in `MeasurementStatus` that either of the other two records could be
in.

**This module never constructs an `Attestation`.** It receives one, so there is no
line in it that could fill in three statements on somebody's behalf, and no name in
it is a bypass — ADR-0105 §4, asserted over the source of both modules on this side
in `test_api_pending_routes.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from backend.bench.decided import RouteKey
from backend.bench.entry import Entry
from backend.bench.pending import AwaitingDecision, RouteState
from backend.bench.registration import Attestation
from backend.graph.budget import BudgetPayload, RunBudget
from backend.graph.runstate import RunState


class NotMeasurable(StrEnum):
    """Why a pending-route measurement may not start, as a name the caller branches
    on.

    Nine members and nine different facts, in two groups a screen has to keep
    apart. The first five are about how the bench was built or what it is doing
    right now — the shape `NotStartable` has, and the reason it is not that enum is
    that the other four are about *the routes this request named*, and a caller of
    `/gate-runs` can never be handed one of them.

    A route-shaped refusal is refused before anything is sent and before the
    library is held: measuring is three reference agents, once, per route, and the
    operator does not pay to find out that a route was already decided.
    """

    NO_REFERENCE_AGENTS = "no_reference_agents"
    NO_REFERENCE_MODEL = "no_reference_model"
    NO_WRITABLE_LIBRARY = "no_writable_library"
    NO_ADJUDICATOR = "no_adjudicator"
    ALREADY_IN_FLIGHT = "already_in_flight"
    NOTHING_SELECTED = "nothing_selected"
    NOT_IN_THE_QUEUE = "not_in_the_queue"
    ALREADY_DECIDED = "already_decided"
    NOTHING_LIVE_SCORES_IT = "nothing_live_scores_it"

    def stated(self) -> str:
        """What this refusal means, and what would change it.

        No fallback branch: a tenth member has to fail the typecheck rather than
        print as a name with nothing said about it.
        """
        match self:
            case NotMeasurable.NO_REFERENCE_AGENTS:
                return (
                    "this deployment does not ship the three reference agents, so "
                    "there is nothing to measure a pending route against. The bar "
                    "is D against a hardened, a weak and a trivial agent of known "
                    "construction (ADR-0012), and a build that leaves them out is a "
                    "legitimate deployment that cannot decide a route"
                )
            case NotMeasurable.NO_REFERENCE_MODEL:
                return (
                    "this bench declares no reference model, so there is nothing to "
                    "serve the three reference agents on. One is enough and one is "
                    "required: a route filed here was found against a customer's "
                    "target and faces the single-model bar of ADR-0003 "
                    "(ADR-0107 §4), and a bench that names no model at all cannot "
                    "measure that bar either"
                )
            case NotMeasurable.NO_WRITABLE_LIBRARY:
                return (
                    "this bench has no case library it may write to, and an "
                    "admitted route is a record written into one (ADR-0033). A "
                    "measurement whose admission landed inside a container image "
                    "would be gone at the next redeploy, having spent the operator's "
                    "budget to produce nothing that survives it"
                )
            case NotMeasurable.NO_ADJUDICATOR:
                return (
                    "this bench has no adjudicating instrument configured, and an "
                    "admission run is a calibration run: it takes the same "
                    "instrument every other run against the reference agents takes"
                )
            case NotMeasurable.ALREADY_IN_FLIGHT:
                return (
                    "this case library is already held — by a gate run, or by "
                    "another measurement — and one writer at a time is the whole of "
                    "the lease (ADR-0033). Nothing has been sent and nothing has "
                    "been spent. The holder is named on the lease"
                )
            case NotMeasurable.NOTHING_SELECTED:
                return (
                    "this request named no route to measure. A measurement is per "
                    "route — the three reference agents, once each — so the routes "
                    "are selected by the operator who reads the queue and never "
                    "defaulted to all of them"
                )
            case NotMeasurable.NOT_IN_THE_QUEUE:
                return (
                    "this request named a route this queue holds no record of. The "
                    "target, the criterion and the attacker's own prose come off "
                    "the record the run that found the route filed, so there is "
                    "nothing here to measure"
                )
            case NotMeasurable.ALREADY_DECIDED:
                return (
                    "this request named a route that has already been decided. Its "
                    "payload went with that decision (ADR-0104 §4), so there is no "
                    "probe left to measure it with and a second answer would rest "
                    "on no reading at all"
                )
            case NotMeasurable.NOTHING_LIVE_SCORES_IT:
                return (
                    "this request named a route whose criterion matches no live "
                    "case in this library. The criterion is what a verdict on the "
                    "route *means* — the success condition, the judged condition, "
                    "the verdict class and the preconditions — and a route drafted "
                    "under one that no live case carries any more is a probe "
                    "nothing here can score. Refused rather than measured, so "
                    "nobody pays for a pass over three agents for it"
                )


class CannotMeasure(RuntimeError):
    """A measurement that was asked for and may not happen, with the reason named.

    Carries the `NotMeasurable` as well as the sentence, because the caller
    branches on one and a person reads the other — and because some of the nine are
    permanent facts about the deployment while others are about this request or
    about right now.
    """

    def __init__(self, refusal: NotMeasurable, detail: str = "") -> None:
        super().__init__(f"{refusal.stated()}{f'. {detail}' if detail else ''}")
        self.refusal = refusal


class MeasurementStatus(StrEnum):
    """Where one measurement is, in the words its own record keeps.

    Not `GateRunStatus` and not `RunStatus`. A run *completes* and has a report, a
    gate run is *decided* and has an outcome about this bench; a measurement
    **answers routes** and leaves the ones it could not answer pending. There is no
    member here either of the other two could be in, which is how a record of one
    kind cannot be reported as another (ADR-0105 §1).
    """

    AWAITING_APPROVAL = "awaiting_approval"
    DECLINED = "declined"
    UNANSWERED = "unanswered"
    MEASURING = "measuring"
    ANSWERED = "answered"
    ABORTED = "aborted"
    FAILED = "failed"

    @property
    def in_flight(self) -> bool:
        """Whether this measurement is still going, or has stopped for good."""
        return self in {
            MeasurementStatus.AWAITING_APPROVAL,
            MeasurementStatus.MEASURING,
        }


@dataclass
class RouteProgress:
    """Where one route in a measurement has got to, and what it ended as.

    Per route rather than per measurement, because the action is minutes long and
    the operator selected the routes one at a time: *measuring on the second model*
    and *answered from the memory without being measured* are two different things
    to be told about a route somebody is paying for (spec story 10).

    The state is a `RouteState` and never a fourth word for one: what a decided
    route is, is what the store says it is, and a progress row that could say
    *admitted* about a record the store holds as pending would be a screen
    disagreeing with the disk.
    """

    route: RouteKey
    target: str
    description: str
    where: str
    """Where this route is right now, in words: queued, measuring on a named model,
    answered from the memory, or decided. Prose because it is read and never
    branched on — the field a caller branches on is `state` below."""

    state: RouteState = RouteState.PENDING
    """What the queue holds this route as. `pending` until a decision is written,
    and a route the measurement could not answer is still `pending` at the end."""

    reason: str = ""
    """The gate's own reason, once there is one. Empty while the route is pending —
    a route awaiting a decision has no finding to report yet."""

    entered_as: str = ""
    """The case record an admitted route became, named as the file it is.

    Empty for everything else. The loop closing is a file an operator can open
    (spec story 11), so the row names it rather than saying that a write happened.
    """

    def settle(
        self,
        state: RouteState,
        reason: str,
        entered_as: str = "",
        remembered: bool = False,
    ) -> None:
        """Record what this route was decided as, why, and how it was measured.

        `remembered` says the counts came from the admission memory rather than from
        three reference agents this measurement paid for (ADR-0032). It is on the
        row rather than only in the total, because it is the difference between a
        route the operator was billed for and one they were not — and a page that
        could not tell them apart would report a saving nobody can see.
        """
        self.state = state
        self.reason = reason
        self.entered_as = entered_as
        self.where = f"decided: {state}" + (
            ", on counts the admission memory already held — nothing was sent to "
            "a reference agent for this route (ADR-0032)"
            if remembered
            else ""
        )


class ModelPassState(StrEnum):
    """Where one model's admission run got to.

    Four members and not a boolean pair, because *has not started* and *did not
    happen* are the two an operator must never see merged: the first is a model
    still to be paid for, the second is a model whose equipment would not serve, and
    a screen that drew both as an empty bar would report a refusal as a wait.
    """

    WAITING = "waiting"
    MEASURING = "measuring"
    MEASURED = "measured"
    UNMEASURED = "unmeasured"
    """The pass that did not happen — equipment that would not serve, an agent that
    never registered, a ceiling reached, or a measurement that stopped before this
    model was reached."""


@dataclass
class ModelPass:
    """One model's pass over the selected routes, and how far into it the run is.

    Per model because the models are walked strictly one at a time and the action is
    minutes long: *how far into the pass* is the fact `RouteProgress.where` already
    reports in prose, and this is the same fact as the two counts a length can be
    drawn from. One pass on this surface after ADR-0107 §4, and still a sequence
    rather than a single record, because `cross_model_bar` walks N models and the
    swap walks two of them.

    **The counts are attempts, and the ceiling is the declared rule's.** An attempt
    is the unit of the denominator (CONTEXT.md), so `of` is what the rule asks for
    over the cases and the three agents of this pass — known exactly before the pass
    starts, which is what lets a bar be drawn at all. Neither figure is a rate and
    there is no percentage on either: the share is a length on the page and never a
    number (`pending.ts`, `GateCards.FamilyBar`).
    """

    model: str
    of: int
    """How many attempts this pass was planned for: cases × the declared rule's
    attempts, against each of the three reference agents."""

    state: ModelPassState = ModelPassState.WAITING
    counted: int = 0
    """The attempts this pass finished with, kept once the pass is over.

    Held rather than read from `progress` at the end, because the `RunState` a pass
    counts through belongs to that pass's own admission run and is dropped with it —
    a bar that read a finished pass through a discarded run state would empty itself
    the moment the pass completed.
    """

    progress: RunState | None = None
    """The live run state of this pass, while it is the pass in flight.

    `None` before the pass starts and after it ends. It is the run's own state
    object rather than a copy of a count, because the count changes on the run's
    thread and there is no moment on this side that knows when: reading `len` off it
    at serialisation is what makes the bar live rather than polled.
    """

    @property
    def attempted(self) -> int:
        """Attempts made so far in this pass — live while it runs, fixed after.

        Clamped to `of` rather than reported past it. The planned figure is the
        declared rule's over this pass's cases and agents, and a registration probe
        or a retry landing in `attempts` would otherwise draw a bar past its own
        end (`budget.py`: the ceiling counts calls, this counts attempts).
        """
        made = self.counted if self.progress is None else len(self.progress.attempts)
        return min(made, self.of)


@dataclass
class MeasurementRecord:
    """One measurement: what authorised it, what it was estimated at, what it
    answered.

    Deliberately not a `GateRunRecord`: there is no `GateResult` on it and no
    library write-back, because what it produces is a decision per route. The budget
    and the presented figures are on the record for `RunRecord`'s reason — the
    ceiling the measurement is held to has to be the one the operator was shown.
    """

    measurement_id: str
    attestation: Attestation
    library: Path
    models: tuple[str, ...]
    """The underlying models the reference agents are run on, in order.

    One on this surface (ADR-0107 §4) and a sequence all the same, because the bar
    is measured in **one action**: a reading assembled across runs is a reading no
    run's configuration matches (ADR-0032, ADR-0105 §2). Carried on the record so
    the estimate, the measurement and the memory the measurement writes all name
    the same models.
    """

    routes: tuple[AwaitingDecision, ...]
    """The pending records this measurement was started over, as they stood when it
    was started. The drafts are here because they are what is measured; they leave
    the store with the decision that removes them (ADR-0104 §4)."""

    budget: RunBudget
    presented: BudgetPayload
    per_route: tuple[tuple[RouteKey, RunBudget], ...] = ()
    """Each route's own share of the estimate, declared before anything is sent.

    Per route because that is the unit the operator selects in and the unit the
    spend is incurred in — the three reference agents, once per route — and a
    single total would ask them to confirm a figure they cannot attribute to
    anything they chose (ADR-0105 §4).
    """

    progress: tuple[RouteProgress, ...] = ()
    passes: tuple[ModelPass, ...] = ()
    """One pass per declared model, in the order they are measured.

    Beside `progress` and not folded into it, because the two answer different
    questions about the same minutes: a row says where *one route* got to, and a
    pass says how far into *one model* the run is. A measurement of three routes on
    one model has three rows and one pass, and neither count is derivable from the
    other.
    """

    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    status: MeasurementStatus = MeasurementStatus.AWAITING_APPROVAL
    statement: str = (
        "halted at the approval interrupt: nothing has been sent to a reference "
        "agent, nothing has been spent, and every route named here is still "
        "pending. None of that changes until this estimate is answered, and "
        "answering anything but yes leaves the queue exactly as it is"
    )
    confirmed_by: str = ""
    lines: tuple[str, ...] = ()
    """The bar's own prose, as it produced it — the consultation's report, the
    rejections, each promotion's lines. Kept rather than printed, because this
    surface has no terminal and the sentences are what an operator checks a
    decision against (`admitting.Say`)."""

    entry: Entry | None = None
    """What the admitted routes did to the case library, or `None` where nothing was
    written. Through `entry.enter` and no other writer (ADR-0033)."""

    def settle(self, status: MeasurementStatus, statement: str) -> None:
        """Move the measurement to its next state, and say in words what that is."""
        self.status = status
        self.statement = statement

    def say(self, line: str) -> None:
        """Keep one line of the bar's prose. The `Say` seam's implementation here."""
        self.lines = (*self.lines, line)

    def progress_for(self, route: RouteKey) -> RouteProgress | None:
        """This measurement's progress row for one route, or `None`.

        Named for what it returns rather than for the field it carries: `where` on a
        row is the prose, and a method of that name returning the whole row would
        read as the prose at every call site.
        """
        for row in self.progress:
            if row.route == route:
                return row
        return None

    def moved(self, routes: tuple[RouteKey, ...], where: str) -> None:
        """Say where these routes are now, for the rows that are still undecided."""
        for row in self.progress:
            if row.route in routes and row.state is RouteState.PENDING:
                row.where = where

    def pass_on(self, model: str) -> ModelPass | None:
        """This measurement's pass for one model, or `None` where it declares none."""
        for one in self.passes:
            if one.model == model:
                return one
        return None

    def measuring_on(self, model: str, progress: RunState, of: int) -> None:
        """Start this model's pass, and hand it the run state its bar counts through.

        `of` is passed rather than kept from the estimate: what a pass is planned
        for is the attempts over *the cases that reached it*, and the routes the
        admission memory already answered never reach a reference agent at all
        (ADR-0032). A bar drawn against the estimate's figure would sit permanently
        short by the routes nobody was billed for.
        """
        one = self.pass_on(model)
        if one is not None:
            one.state = ModelPassState.MEASURING
            one.progress = progress
            one.of = of

    def measured_on(self, model: str) -> None:
        """Finish this model's pass, keeping the count and dropping the run state."""
        one = self.pass_on(model)
        if one is not None:
            one.counted = one.attempted
            one.progress = None
            one.state = ModelPassState.MEASURED

    def unmeasured(self) -> None:
        """Mark every pass that never finished as one that did not happen.

        Called where a measurement stops for good, so that a pass left `measuring`
        by an equipment failure is not drawn as a bar still filling on a screen
        nothing is going to advance. A pass already `measured` keeps its counts:
        the first model's run happened whether or not the second one's did
        (ADR-0012, and `test_a_measurement_that_read_one_model_and_not_the_second`).
        """
        for one in self.passes:
            if one.state is not ModelPassState.MEASURED:
                one.counted = one.attempted
                one.progress = None
                one.state = ModelPassState.UNMEASURED


def a_holder(attestation: Attestation, measurement_id: str) -> str:
    """Who the lease says is holding the library. A person and a measurement, both.

    Names the measurement rather than borrowing the gate run's words, because the
    refusal the *next* caller reads is this sentence: an operator told the library
    is held wants to know which of the two things that hold it is holding it.
    """
    return (
        f"{attestation.identity}, pending-route measurement {measurement_id} "
        "from the console"
    )


class NoLongerWaiting(RuntimeError):
    """An answer to a measurement's interrupt that is not waiting for one any more."""

    def __init__(self, record: MeasurementRecord) -> None:
        super().__init__(
            f"measurement {record.measurement_id} is {record.status} and is no "
            "longer waiting on an answer. An interrupt is answered once"
        )
