"""Every route held against a target, sent again, on a denominator of its own.

The third of the three modules the target library is built from: `held.py` is the
store, `holding.py` is the door a person opens, and this is the send. The decision
is
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§4 and the build spec is
[docs/specs/the-target-library.md](../../docs/specs/the-target-library.md).

**Automatic, and never a selection.** Every open route held against a target is sent
on every run of that target. ADR-0117 rejects the tick-box version on what the figure
would mean: *3 of 5 still open* is a fact only if the 5 is every route ever held, and
a suite an operator can forget to select reports what they hoped rather than what is
true.

**The same deterministic evaluator, and a different denominator.** The verdict comes
from `evaluator.read_condition` — the identical match on the identical
`SuccessCondition` that decides a scored attempt — so *still open* is a verdict and
never a judgement (ADR-0004). What does not come from the scored side is the record:
a `HeldReading` is not an `Attempt`, it is never put on `RunState`, and it reaches no
family rate, no interval, no `A_break`, no band and no gate decision. The fence is the
type, so no per-family counter needs a new exclusion and no aggregation over `Attempt`
can pick one of these up by accident.

**One send per route per run, and not the declared ten.** A held route's claim is
*this probe produced this verdict against this agent, and here is whether it still
does* (ADR-0117 §2), and what answers it is a count rather than a rate. Ten sends
would buy a proportion nobody may divide by — the shape ADR-0117 spends its longest
section forbidding — at ten times the operator's cost.

**Nothing a held route does may cost the run its scored measurement.** A target that
stopped answering half way through a target library is a run whose six family rates
are already measured and are still worth signing, so a `TargetUnreachable` is caught
here and recorded as *unmeasured* for that route rather than raised through a run
(ADR-0117 §5). It is the same asymmetry `holding.py` has on the filing side: nothing
about a held route raises through a paid-for measurement.

**What is not counted is the honest half of the reading.** An unreachable target
reports `UNMEASURED` and a criterion the evaluator cannot read reports `UNMEASURABLE`,
on the `measurability.condition_checkable` path the adaptive layer already uses.
Neither is a clean run and neither is a fix — an absent endpoint that read as *closed*
would be the bench reporting somebody's outage as their remediation. Counting the
clean runs those two outcomes deny is the retirement ticket's; what this module owes
it is a reading it can count from, which is `HeldReading.counts_a_clean_run`.

**The budget, and what it does not yet cover.** Every send here is authorised against
`Layer.SCORED` before it goes on the wire and counted against it after, on the same
terms as any scored attempt (ADR-0007): a call on the operator's endpoint that no
counter saw is the one thing that decision forbids outright. What is *not* yet true is
that the estimate an operator confirms prices these sends — `RunBudget.declare` is
arithmetic over the case library and the targets and knows nothing about a target
library, so a run's held routes are spent out of the headroom between the exact suite
cost and the retry-allowance ceiling. ADR-0117 states the cost (*every run of a target
gets longer by the number of routes held against it*) and does not price it. This is
written out rather than absorbed: it is a real gap, it wants its own ticket, and until
then a target holding more routes than that headroom covers will see its run refused
at the counter — which is a refusal and not an overspend, and is the direction
ADR-0007 asks a breach to fail in.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.contract import (
    TargetConfig,
    TargetUnreachable,
    Transcript,
    send_message,
)
from backend.bench.decided import RouteKey
from backend.bench.evaluator import Verdict, read_condition, stop_signal_arrived
from backend.bench.held import HELD_ROUTES, HeldRoute, HeldRoutes, HeldState
from backend.bench.library import SuccessConditionKind
from backend.bench.measurability import condition_checkable
from backend.graph.budget import Layer
from backend.graph.runstate import RunState


class HeldOutcome(StrEnum):
    """What one run learned about one held route. Four readings, and no two are one.

    Its own enumeration and deliberately not `Verdict`, which is ADR-0117 §4's fence
    at the smallest scale there is: a value a rate could be counted over is a value a
    rate will eventually be counted over, and these four are not two outcomes with
    two error states — they are four answers to *is this still broken*, two of which
    say the question was not put.
    """

    STILL_OPEN = "still_open"
    """The route broke the target again. The verdict `read_condition` reached."""

    CLEAN = "clean"
    """Every turn the evaluator could read, and the target held on all of them.

    The one outcome retirement may count (ADR-0117 §5), and it is named for what it
    is rather than *closed*: closing takes two of these, and a word that said so on
    one reading would be the coin-flip ADR-0022 refuses.
    """

    UNMEASURED = "unmeasured"
    """The target could not be reached, so nothing was asked of it.

    Not a clean run and not a fix. `measurability.NotMeasurable`'s distinction one
    population out: a rate of zero and an absent endpoint are the same number and
    different facts, and the one that reads as good news is the one a bench must
    never print.
    """

    UNMEASURABLE = "unmeasurable"
    """The target answered and no reply carried what the criterion has to read.

    The `condition_checkable` path, which is the adaptive layer's own word for a turn
    nothing could be read over. A probe whose trace stopped coming back is a broken
    criterion rather than a defence the target showed, and counting it toward
    retirement would close a defect on the evidence going missing.
    """


@dataclass(frozen=True)
class HeldReading:
    """One held route's result on one run. Not an `Attempt`, and never one.

    What an `Attempt` has and this does not is the whole of the fence: no `case_id`,
    because there is no case; no `family` field, because a figure keyed on `Family`
    is what a family rate is made of and this record makes a caller go through
    `route.family` to get one; no `verdict`, because `HeldOutcome` is four-valued
    where a verdict is two; no `transform`, because nothing here is a construction of
    anything; and no `started_at`, because ADR-0010's ordering invariant is about two
    layers of a scored run and this record is in neither.

    Nothing puts one of these on `RunState`. `RunState.record` takes an `Attempt`,
    `record_episode` takes an `AdaptiveEpisode`, and a third store there would be a
    third thing for an aggregation to find.
    """

    route: RouteKey
    """The route that was sent, as the store keys it: family plus probe digest."""

    target_name: str
    """The agent it was sent to, which is the scope of the whole record."""

    outcome: HeldOutcome

    description: str
    """What the attacker said the route did, carried off the held record.

    Here rather than looked up again by the block that prints it, so that a reading
    is readable on its own: the report says what the route did and not only that a
    route exists (spec, user story 4).
    """

    found_in: str
    """The `run_id` of the run that found the route, off the held record."""

    was: HeldState
    """The state the route was in when this run sent it.

    On the reading rather than derived afterwards, because a **regression** is a
    difference between this state and this outcome — a closed route that broke again
    — and a reader who has only the outcome cannot tell one from a new finding.
    Reading it is the retirement ticket's; carrying it is this one's, because this is
    the only moment the two facts are in one place.
    """

    decided_on_turn: int | None = None
    """Which turn of the payload the criterion was met on, counted from zero.

    `None` for every outcome but `STILL_OPEN`: a route the target held was read over
    every turn it had, and a turn number on an outcome that no turn decided would be
    a figure with nothing behind it.
    """

    @property
    def counts_a_clean_run(self) -> bool:
        """Whether retirement may count this reading toward closing the route.

        One outcome of the four, and the property exists so that the answer is in one
        place: ADR-0117 §5 makes *unmeasured* and *unmeasurable* count nothing, and a
        second call site writing `is not STILL_OPEN` would close a defect on an
        outage. The retirement ticket reads this; nothing else does yet.
        """
        return self.outcome is HeldOutcome.CLEAN


@dataclass(frozen=True)
class HeldRoutesSent:
    """One target's target library, as this run read it. Its own denominator.

    Three readings a caller must be able to tell apart, and they are the same three
    `TargetRun.narrations` keeps apart one field over. `None` on the target run is a
    run that never reached this module at all. An empty `readings` here is a target
    that **holds nothing** — *nothing has been found yet against this agent*, which
    is a fact and reads as one, rather than a block that failed to render (ADR-0117
    §4, spec user story 7). A populated tuple is every open route that was sent.

    No rate on this object and no method that would produce one. `still_open` and
    `sent` are counts, and ADR-0117's longest section is about why the quotient of
    the two must never be computed: the sample is chosen on its own outcome, so the
    figure falls with every new finding, two targets stop being comparable, and the
    band's cut-points were never constructed against such a population.
    """

    target_name: str
    readings: tuple[HeldReading, ...] = ()

    @property
    def holds_nothing(self) -> bool:
        """Whether this target's library is empty, said rather than inferred."""
        return not self.readings

    @property
    def sent(self) -> int:
        return len(self.readings)

    @property
    def still_open(self) -> int:
        return sum(
            1 for reading in self.readings if reading.outcome is HeldOutcome.STILL_OPEN
        )


def send_held_routes(
    target: TargetConfig,
    run_state: RunState,
    canary: str,
    held: HeldRoutes = HELD_ROUTES,
    *,
    reachable: bool = True,
) -> HeldRoutesSent:
    """Send every open route held against this target, and read each one.

    `canary` is **this run's** nonce, and it has to be: one success condition reads
    the value the run issued and planted rather than a value on a record, so a held
    record that carried a canary would be carrying a value that changed the moment
    the run that wrote it ended (ADR-0007, `SuccessConditionKind.CANARY_IN_REPLY`).
    A run that issued none reads those routes as `UNMEASURABLE` — see `_verdict` —
    because a leakage criterion read against an empty string answers *resisted* for
    every target there has ever been, and two of those in a row would close a real
    defect on a value that was never planted.

    `reachable` is what the run already learned from its registration probe, passed
    down rather than re-derived: a target whose registration did not complete is one
    this run has established it cannot measure, and putting a held route's payload on
    the wire to find that out a second time would spend the operator's money to
    confirm a fact the run already holds. Every route reads `UNMEASURED`, which is
    what an absent endpoint is.

    Closed routes are not sent, on ADR-0117 §5 — a route past the window that is
    still sent costs the operator a probe on every run for a defect the bench has
    already answered. Nothing closes one yet: the retirement ticket is what moves a
    record into that state, and until it lands this filter is the guard rather than
    the behaviour.
    """
    return HeldRoutesSent(
        target_name=target.name,
        readings=tuple(
            _read(route, target, run_state, canary, reachable=reachable)
            for route in held.for_target(target.name)
            if route.state is HeldState.OPEN
        ),
    )


def _read(
    route: HeldRoute,
    target: TargetConfig,
    run_state: RunState,
    canary: str,
    *,
    reachable: bool,
) -> HeldReading:
    """One held route sent and read, or the honest reason it was not."""
    if not reachable:
        return _reading(route, target, HeldOutcome.UNMEASURED)
    try:
        transcripts = _sent(route, target, run_state)
    except TargetUnreachable:
        # Caught and never re-raised: the run's six family rates are measured by the
        # time this module runs, and a transport failure on a fenced probe may not
        # take a signed report down with it. Nothing off the exception reaches the
        # record — its message names the endpoint url, which is the one identifier
        # a record never carries (ADR-0011).
        return _reading(route, target, HeldOutcome.UNMEASURED)
    return _verdict(route, target, transcripts, canary)


def _sent(
    route: HeldRoute, target: TargetConfig, run_state: RunState
) -> tuple[Transcript, ...]:
    """The payload on the wire, one turn at a time, in one session.

    One session for the whole payload, on `attacker._send`'s reasoning and for the
    same reason: the turns of a route are dependent on each other — that is what a
    multi-turn route is — and a session id is what carries the dependence. Fresh per
    run, so the reading is about the target and not about what an earlier run left
    in its conversation store.

    Every turn is authorised before the first goes out rather than one at a time, so
    a route that spent half its payload and then hit the ceiling cannot happen: that
    would be money on the operator's endpoint for a reading nobody can take.
    """
    run_state.authorise_call(Layer.SCORED, target.retry.sends * len(route.payload))
    session = f"held-{route.route.probe}-{uuid.uuid4()}"
    transcripts = tuple(
        send_message(target, turn, session_id=session) for turn in route.payload
    )
    run_state.record_call(Layer.SCORED, sum(turn.sends for turn in transcripts))
    return transcripts


def _verdict(
    route: HeldRoute,
    target: TargetConfig,
    transcripts: Sequence[Transcript],
    canary: str,
) -> HeldReading:
    """The criterion applied to what came back, turn by turn, first match deciding.

    ADR-0053's per-turn reading, with one difference the population makes necessary:
    **every** turn is guarded by `condition_checkable`, where `evaluate_script` reads
    the last turn unguarded so that a broken criterion raises where a scored attempt
    can see it. Here there is no attempt to fail and no rate to protect — there is a
    retirement window, and a turn nothing could be read over must not be allowed to
    close a defect. So an unreadable last turn is `UNMEASURABLE` rather than a
    `TraceNotVisible`, and a route no turn of which could be read is the same
    (ADR-0117 §5).

    `read_condition` and not a second copy of the match: the verdict a held route
    gets is the verdict a case would get from the same criterion over the same reply,
    which is what makes *still open* a verdict rather than a judgement (ADR-0004).
    """
    if route.success_condition.kind is SuccessConditionKind.CANARY_IN_REPLY and (
        not canary
    ):
        # The one criterion whose value the run issues rather than the record
        # carrying it. With nothing planted there is nothing to look for, and the
        # match below would answer *resisted* — which is the reading that closes a
        # defect on the evidence never having been put in place (ADR-0007).
        return _reading(route, target, HeldOutcome.UNMEASURABLE)
    halted = False
    readable = False
    for turn, transcript in enumerate(transcripts):
        if condition_checkable(
            route.success_condition, transcript, already_halted=halted
        ):
            readable = True
            if (
                read_condition(
                    route.success_condition,
                    transcript,
                    target,
                    canary,
                    named=route.route.stated(),
                    already_halted=halted,
                )
                is Verdict.SUCCEEDED
            ):
                return _reading(
                    route, target, HeldOutcome.STILL_OPEN, decided_on_turn=turn
                )
        halted = halted or stop_signal_arrived(transcript)
    return _reading(
        route,
        target,
        HeldOutcome.CLEAN if readable else HeldOutcome.UNMEASURABLE,
    )


def _reading(
    route: HeldRoute,
    target: TargetConfig,
    outcome: HeldOutcome,
    decided_on_turn: int | None = None,
) -> HeldReading:
    """One reading built off the held record, so the four paths cannot drift."""
    return HeldReading(
        route=route.route,
        target_name=target.name,
        outcome=outcome,
        description=route.description,
        found_in=route.found_in,
        was=route.state,
        decided_on_turn=decided_on_turn,
    )
