"""What a run's readings do to the library it read them from: the window, counted.

The fourth and last module of the target library. `held.py` is the store, `holding.py`
is the door a person opens, `resending.py` is the send, and this is what the send
leaves behind. The decision is
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§5 and the build spec is
[docs/specs/the-target-library.md](../../docs/specs/the-target-library.md).

**Two clean runs close a route, and closing is the only thing that stops a send.**
Without it the suite only grows and every run of a target pays forever for everything
its operator has already fixed. Two and not one, on the window
[ADR-0022](../../docs/adr/0022-the-retirement-window-is-two-readings-of-one-model.md)
already declares rather than a second number: one reading of a probabilistic target
is a coin-flip, and a defect closed on a coin-flip is a report saying a fix worked
when nothing was fixed.

**A break resets the count; an unmeasured or unmeasurable run moves nothing.** The
three are genuinely three, and the middle one is where the honest half of ADR-0117 §5
lives. A run that could not reach the target has not seen the target defend itself, so
it may not count toward closing — that is the reading that would print somebody's
outage as their remediation. It equally may not *reset*, and that is ADR-0022's own
shape: the retirement window there is a filtered series and not the last two positions,
so a reading that does not belong to the window is skipped rather than allowed to
stand for a bad one. A clean run, an outage, a clean run is two clean readings with no
evidence of a break between them, and reading the outage as a break would be inventing
one.

**Nothing here reaches a figure, because nothing here is a figure.** What this module
writes is a state and a count on a record that no rate, interval, band, `A_break` or
gate decision may see (ADR-0117 §4). It reads `HeldReading.counts_a_clean_run` rather
than testing the outcome itself, so the one place that decides what a clean run is
stays one place.

**A storage fault costs a record and never an answer**, which is `holding.py`'s
convention one store-write further on: the run has been paid for and its six family
rates are already measured by the time anything here executes, so every refusal leaves
as prose on `Closing` and nothing raises through a run. Left unread by the run loop
today — the report block that prints it is #242 — and returned rather than swallowed
because a window that failed to advance is exactly the thing a reader of *3 of 5 still
open* would need to be told about.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.bench.held import HELD_ROUTES, HeldRoute, HeldRoutes, HeldState
from backend.bench.resending import HeldOutcome, HeldReading, HeldRoutesSent
from backend.bench.route_key import RouteKey


@dataclass(frozen=True)
class Closing:
    """What one run's readings did to one target's library.

    A record rather than nothing, on `holding.Holding`'s reasoning: the writes here
    are the ones that decide whether a route is ever sent again, and a refusal nobody
    is handed is a refusal nobody reads. `closed` is the one fact a report will want
    — a route this run closed is the operator's fix, confirmed — and `not_counted`
    is every reading that could not be counted into the record it came from.

    Counts and keys, and no rate over them. The quotient of anything here by anything
    else is the figure ADR-0117 spends its longest section forbidding.
    """

    target_name: str
    closed: tuple[RouteKey, ...] = ()
    """Every route this run's second consecutive clean reading closed."""

    not_counted: tuple[str, ...] = ()
    """Why a reading reached no record, one sentence each. Empty on the usual run."""

    def stated(self) -> str:
        """What this run did to the target library, in one sentence.

        Through `stated()` for the reason `Holding.stated` is: `Queued`, `Filing`,
        `Entry` and `Holding` are the records a run says itself with, and a fifth
        that had to be printed differently would be the one a caller forgets.
        """
        closed = (
            "closed nothing"
            if not self.closed
            else f"closed {', '.join(route.stated() for route in self.closed)}"
        )
        said = f"This run {closed} against {self.target_name}"
        if not self.not_counted:
            return f"{said}."
        return f"{said}. {' '.join(self.not_counted)}"


def count_clean_runs(
    sent: HeldRoutesSent,
    *,
    run_id: str,
    routes: HeldRoutes = HELD_ROUTES,
) -> Closing:
    """Count this run's readings into the records they were read off.

    `run_id` is this run's own, and it is what a closed record keeps: *found on 3
    March, closed on 19 March* is two runs, and the second of them is this one. Taken
    as an argument rather than read off a clock, on `HeldRoute.found_in`'s terms — a
    run record carries its own date and a date stored here would be a copy of one
    field of it that nothing keeps in step.

    `routes` has a default for `holding.hold_refused`'s reason and with its
    consequence: the default is the module-level object bound at import, so every
    caller writes to the one git-ignored location and a test that wants its own
    passes one.

    Each record is **re-read** rather than counted off the copy the send carried,
    because the reading is a fact about a probe and the record is a fact about a
    window: between the two, a rediscovery through `/pending-routes` may have
    reopened the same route, and counting a clean run into the copy that was sent
    would write the reopening back out of existence.
    """
    closed: list[RouteKey] = []
    refused: list[str] = []
    for reading in sent.readings:
        held = routes.held(reading.target_name, reading.route)
        if held is None:
            refused.append(_no_record(reading))
            continue
        if held.state is HeldState.CLOSED:
            refused.append(_already_closed(reading))
            continue
        counted = _counted(held, reading, run_id)
        if counted == held:
            continue
        try:
            routes.record(counted)
        except Exception as fault:  # noqa: BLE001 - never fails a measured run
            refused.append(_not_written(reading, fault))
            continue
        if counted.state is HeldState.CLOSED:
            # This run closed it, and not some earlier one: the record read above
            # was open — the guard further up returned every closed one — so the
            # only transition that reaches this line is this run's second clean
            # reading. mypy says the same thing, which is why there is no second
            # half to this condition.
            closed.append(counted.route)
    return Closing(
        target_name=sent.target_name,
        closed=tuple(closed),
        not_counted=tuple(refused),
    )


def _counted(held: HeldRoute, reading: HeldReading, run_id: str) -> HeldRoute:
    """This record after this reading. The three-way decision, in one place.

    Ordered with the clean run first because it is the only branch that may move the
    state, and read off `counts_a_clean_run` rather than off the outcome so that
    *what a clean run is* is decided where ADR-0117 §5 put it and not a second time
    here. The break is read off the outcome directly, because `STILL_OPEN` is the
    one member that means it and a second property saying so would be a second place
    to keep in step. Everything that is not a clean run and not a break — an
    unreachable target, a criterion no reply carried — falls through to the record
    unchanged: it is not a clean run, and it is not evidence of a break either.
    """
    if reading.counts_a_clean_run:
        return held.after_a_clean_run(run_id)
    if reading.outcome is HeldOutcome.STILL_OPEN:
        return held.after_a_break()
    return held


def _already_closed(reading: HeldReading) -> str:
    """A reading of a route the library has closed, which is a fault and reads as one.

    `send_held_routes` sends open routes only, so this is reachable only if a record
    closed between the send and the count, or if that filter ever stops holding.
    Counted into the record it would raise rather than return — a break resets the
    count, and a closed route on a reset count is a state `HeldRoute` refuses — and
    a fenced population may not take down a run whose six family rates are already
    measured (ADR-0117 §4). So the reading is reported and the record left exactly
    as it stands.
    """
    return (
        f"{reading.route.stated()} was read against {reading.target_name} and the "
        "record held under it is closed, so nothing was counted into it. A closed "
        "route is not sent (ADR-0117 §5), and a reading of one is a fault in the "
        "send rather than evidence about the target"
    )


def _no_record(reading: HeldReading) -> str:
    """A reading whose record is gone, which is a fault and reads as one.

    Possible only if the file was replaced or the record deleted between the send and
    this count. Refiling it here would mint a held route no operator approved, so the
    reading is reported and dropped: a person is the door (ADR-0117 §2).
    """
    return (
        f"{reading.route.stated()} was read against {reading.target_name} and no "
        "record is held under it any more, so the reading advanced no window. "
        "Nothing is filed in its place: what licenses a held record is an "
        "operator's approval and not a run's reading (ADR-0117 §2)"
    )


def _not_written(reading: HeldReading, fault: Exception) -> str:
    """A record that could not be written, stated rather than raised.

    `holding.py`'s asymmetry one store-write further on: the suite ran, the target
    was measured and the report is still worth signing, so what a storage fault costs
    here is a window's progress and never an answer.
    """
    return (
        f"{reading.route.stated()} was read against {reading.target_name} and its "
        f"record could not be written: {fault}. The reading stands and the window "
        "did not advance — a storage fault costs a record and never an answer"
    )
