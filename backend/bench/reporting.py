"""One target library as a report states it: counts, dates, and what licenses them.

The fifth and last module of the target library, and the only one a reader ever
meets. `held.py` is the store, `holding.py` is the door a person opens, `resending.py`
is the send, `closing.py` is the window it advances — and this is the block. The
decision is
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§4 and its cost paragraph;
[ADR-0119](../../docs/adr/0119-a-held-routes-figures-travel-in-the-signed-artefact-and-its-prose-does-not.md)
is what this record may carry into a signed document and what it may not; the build
spec is [docs/specs/the-target-library.md](../../docs/specs/the-target-library.md).

**Not `rendering/`.** That package turns a serialised payload into Markdown and reads
nothing else. This one turns a run's readings and the library they were read off into
the record a payload can carry, which is a step earlier and needs the store. The two
never meet: `rendering/_measured.py` prints what `payload.document` serialises, and
what it serialises from here is this record.

**Rendering is where the fence is most easily lost, because a reader sees one page.**
The four modules below carry ADR-0117 §4 structurally — a `HeldReading` is not an
`Attempt`, a `HeldRoute` is not a `Case` — and a block drawn beside six family rates
can undo all of it by looking like a seventh row. So three properties are carried by
the types here and asserted by the suite rather than left to a call site:

1. **No quotient exists.** Every figure on `HeldBlock` is a count, there is no method
   that divides one by another, and there is no field a rate could arrive in. Why the
   quotient may not exist is ADR-0117's longest section — *Why the fence is the whole
   decision* — and it is not restated here; what it buys locally is that *3 of 5* is
   two integers on every surface that prints this record, because there is no third
   value for one of them to be.
2. **Nothing here is keyed on `Family`.** A line carries `route`, and the family is
   reached through it, exactly as `resending.HeldReading` makes a caller do. The
   family is printed as a **name** beside a route, on the terms the adaptive section
   already prints `families_broken`: a name is not a figure, and there is no mapping
   here a per-family counter could walk.
3. **The block says what licenses it**, in `WHAT_LICENSES_THIS_BLOCK`, and that
   sentence is on the wire rather than written by each surface. ADR-0117's cost
   paragraph requires it in as many words — a reader of one number in one block is
   trusting an operator's approval where elsewhere they trust a declared threshold —
   and two surfaces wording it themselves would be two claims the day one is edited.

**A storage fault costs a block and never an answer**, which is `holding.py`'s
convention two modules on. Everything here runs after the six family rates have been
measured and paid for, so no refusal raises: a library that could not be listed leaves
as prose on `unlisted` and the block says it could not be listed, which is the one
reading a count of zero must never be allowed to stand for.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.closing import Closing
from backend.bench.held import HELD_ROUTES, HeldRoute, HeldRoutes, HeldState
from backend.bench.library import AnyFamily
from backend.bench.resending import HeldOutcome, HeldReading, HeldRoutesSent
from backend.bench.route_key import RouteKey

WHAT_LICENSES_THIS_BLOCK = (
    "Held on an operator's approval, not the admission bar (ADR-0117)."
)
"""What a reader of this block is trusting, which is not what they trust elsewhere.

ADR-0117's cost paragraph, in the document's own words and on the wire. Stated here
once, carried into the payload, and printed by both the Markdown and the console for
`labels.bears_stated`'s reason: a surface that assembled the sentence would be a
second copy of a claim the signed document already makes, and two copies of one claim
are two claims the day one of them is edited.

**One line, on the operator's judgement that four sentences were not being read.**
It ran four and spelled out what the bar asks and why these routes failed it. What
survives is the only part a reader must not miss — that an approval and not the bar
is what put a route here — and the citation, because the argument itself is
ADR-0117's to make and is still made there in full. A caveat nobody finishes is a
caveat nobody has read, so the cost of the cut is paid against the long form and not
against the disclosure.
"""

NO_RATE_OVER_THESE = (
    "These are counts and there is no rate over them. A held route is selected "
    "because it already broke this target, so a quotient of any two figures here "
    "would be a rate over a sample chosen on its own outcome: it would fall with "
    "every new finding, two targets would stop being comparable, and the band's cut "
    "points were computed against no such population. Nothing in this block is "
    "summed into a family rate, an interval, the break score or the band, no "
    "decision about this bench's own fitness is taken on any of it, and none of "
    "those figures is derived from anything here (ADR-0117 §4)."
)
"""The fence, said on the page a reader sees rather than only in the type system.

The type carries it — there is no quotient to print — and this sentence is why the
type is shaped that way, for the reader who is looking at one page and cannot see the
types. Separate from `WHAT_LICENSES_THIS_BLOCK` because they answer two different
questions: that one says what the evidence is, and this one says what may be done
with it.
"""


class HeldBlockReading(StrEnum):
    """Which of the four answers this block is. Four, and no two are one.

    Three of them are the three `TargetRun.held_routes` keeps apart one field out,
    carried through to the surface so that a consumer tells them apart by a name off a
    closed set rather than by a count — a screen that read *held: 0* as *nothing found
    yet* would print a library that could not be opened as good news.

    The fourth is that library. *We never looked* and *we could not look* are two
    facts, and an enum that had both under one name would be this module drawing a
    distinction in `unlisted` and then dropping it on the way to the screen.
    """

    NOT_ASKED = "not_asked"
    """No target library was read on this run: an older record, or a caller that
    never reached the send. Nobody looked, and nothing failed."""

    UNREADABLE = "unreadable"
    """A library this run went to read and could not open. `unlisted` says why.

    Its own member and not `NOT_ASKED`, because the two differ in whether anything is
    wrong: one is a run made without a target library and the other is a store that
    would not answer, and a surface deciding whether to tell somebody has to be able
    to tell them apart without matching prose.
    """

    HOLDS_NOTHING = "holds_nothing"
    """The library was read and holds no route. *Nothing has been found against this
    agent yet*, which is a fact and reads as one (spec user story 7)."""

    HELD = "held"
    """The library was read and holds routes, open or closed or both."""


@dataclass(frozen=True)
class HeldRouteLine:
    """One held route as the block prints it. Not a `HeldRoute`, and never one.

    What a `HeldRoute` has and this does not is the whole of the fence at this last
    step: no `payload`, because a route that beat this target is a working unpublished
    exploit and this is the document that leaves the building
    ([ADR-0008](../../docs/adr/0008-repo-disclosure-posture.md)); no
    `success_condition`, for the same reason one turn further in; no `target`, because
    the block is scoped to one and a line repeating it would be a second copy of the
    scope; and no `clean_runs`, because a window position is a fact about the bench's
    bookkeeping and not about the operator's agent.

    No `description` either, and that is a **deliberate absence and not an oversight**:
    [ADR-0119](../../docs/adr/0119-a-held-routes-figures-travel-in-the-signed-artefact-and-its-prose-does-not.md)
    admits this record's figures and dates into the signed artefact and keeps the
    attacker's account of the break out of it. The consequence here is the one the ADR
    records as a cost: the build spec's user story 4 — *the report says what the route
    did and not only that a route exists* — is not met on any surface, and the ticket
    that meets it is the one that decides what a signed document does with an
    instrument's prose about a held route.
    """

    route: RouteKey
    """The family and the digest of the probe — the key the whole store is on.

    The route and not a family field, on `HeldReading`'s terms: a figure keyed on
    `Family` is what a family rate is made of, so a caller that wants the family goes
    through the key to get one and there is no mapping here to walk.
    """

    state: HeldState
    """Whether this target still fails the route, **after** this run's readings.

    Read off the record as the library holds it once `closing.count_clean_runs` has
    written, and never off the reading: a route this run's second clean reading closed
    was `OPEN` when it was sent, and a block that printed the send's state would report
    the operator's fix one run late (ADR-0117 §5).
    """

    found_in: str
    """The `run_id` of the run that found the route. The first half of the sentence
    the operator paid for: *found on 3 March, closed on 19 March*."""

    outcome: HeldOutcome | None = None
    """What this run learned about this route, or `None` because it was not sent.

    `None` on every closed route, which is precisely what closing buys: a closed route
    stops being sent, so a run has nothing to report about it and a reading invented
    for it would be a probe nobody paid for. It is also `None` on a route held after
    this run's send — a rediscovery decided between the send and the count — and in
    both cases the line still prints, because the route is held and the block's total
    is every route ever held.
    """

    closed_in: str | None = None
    """The `run_id` of the run whose reading closed this route, or `None` while open.

    The second half of the sentence, off `HeldRoute.closed_in`. Kept on a reopened
    route as the record keeps it: a regression is precisely the pair of a closing and
    a return, and dropping the closing would leave a reader unable to see the pair.
    """

    reopened_in: str | None = None
    """The `run_id` of the run that found this route again after it had closed.

    What makes this line a **regression** rather than a new finding (ADR-0117 §5,
    spec user story 13).
    """

    @property
    def family(self) -> AnyFamily:
        """The family the route was found in, through the key and never beside it."""
        return self.route.family

    @property
    def regressed(self) -> bool:
        """Whether this route has ever closed and come back, off `reopened_in`.

        Read off the field and never off the state, exactly as `HeldRoute.regressed`
        reads it, so that a route which regressed and was then fixed again still
        reads as one.
        """
        return self.reopened_in is not None

    def stated(self) -> str:
        """This route's whole line, for a surface that prints one.

        Assembled here and carried on the wire, so the Markdown and the console print
        one wording. Every clause is a fact off a field above and none of them is a
        figure: a family name, a probe digest, two or three run ids, and which of the
        four readings this run took.
        """
        said = f"{self.route.stated()}, found in {self.found_in}"
        if self.regressed:
            said += (
                f", closed in {self.closed_in} and found again in {self.reopened_in} — "
                "a regression, and not a new finding"
            )
        elif self.state is HeldState.CLOSED:
            said += f", closed in {self.closed_in}"
        if self.outcome is None:
            return (
                f"{said}. Not sent on this run"
                + (
                    ": a closed route stops being sent"
                    if self.state is HeldState.CLOSED
                    else ", so this run read nothing about it"
                )
                + "."
            )
        return f"{said}. This run read it as {_said(self.outcome)}."


@dataclass(frozen=True)
class HeldBlock:
    """One target library, as one run's report states it. Counts, and no rate.

    The record `payload.document` serialises and both surfaces print. It holds every
    route ever held against this target — open and closed — because *3 of 5 still
    open* is a fact only if the 5 is all of them, and it holds the sentences that say
    what the figures are worth and what may not be done with them.

    There is no field here a rate could arrive in and no method that returns one. A
    reader who wants a percentage computes it themselves, which is the same answer
    `TargetResult` gives about a single number standing for a target (ADR-0005).
    """

    target_name: str
    """The agent this library is held against, which is the scope of all of it."""

    lines: tuple[HeldRouteLine, ...] = ()
    """Every route ever held against this target, open and closed, in a fixed order.

    Sorted by `filed_under` at construction so two reports of one target list the same
    routes in the same order — a block whose rows moved between two runs would make a
    reader diffing them read a reordering as a change.
    """

    not_counted: tuple[str, ...] = ()
    """Why a reading this run took reached no record, one sentence each.

    `closing.Closing.not_counted`, carried through rather than dropped. A window that
    failed to advance is exactly the thing a reader of *3 of 5 still open* has to be
    told about: without it, a storage fault reads as a route that is simply still
    open, and the next run's *closed* arrives a run late with no explanation.
    """

    unlisted: str | None = None
    """Why the library could not be listed at all, or `None` on every ordinary run.

    The reading a count of zero must never stand for. `holds_nothing` asks this field
    first, so a store that would not open reports as unread rather than as an agent
    nothing has been found against — which is the difference between *we looked and
    there is nothing* and *we could not look*.
    """

    def __post_init__(self) -> None:
        if self.unlisted is not None and self.lines:
            raise ValueError(
                f"the target library of {self.target_name!r} reported {len(self.lines)}"
                " held route(s) and also reported that it could not be listed. One of"
                " the two is untrue, and a block that carried both would print a "
                "partial listing as a complete one"
            )

    @property
    def reading(self) -> HeldBlockReading:
        """Which of the four answers this block is, as a name off a closed set.

        `NOT_ASKED` is not produced here: a `HeldBlock` exists because something went
        and read a library, so the reading for *nobody looked* belongs to the absence
        of one of these records and is `payload._held`'s to print.
        """
        if self.unlisted is not None:
            return HeldBlockReading.UNREADABLE
        return (
            HeldBlockReading.HOLDS_NOTHING if not self.lines else HeldBlockReading.HELD
        )

    @property
    def holds_nothing(self) -> bool:
        """Whether this target's library was read and holds no route at all."""
        return self.reading is HeldBlockReading.HOLDS_NOTHING

    @property
    def held(self) -> int:
        """Every route ever held against this target, open and closed.

        The denominator of the block and of nothing else. It is a count of records in
        one target's library — not of attempts, not of cases and not of anything a
        family rate is over — and no figure outside this block is derived from it.
        """
        return len(self.lines)

    @property
    def open_routes(self) -> int:
        """Routes this target has not yet closed, whatever this run read about them.

        The library's own state, and deliberately not *how many broke the target this
        run*: an open route whose run could not reach the target is still open and was
        not measured, and one figure standing for both would print an outage as a
        defect or a defect as an outage. `still_breaking` is the other question.
        """
        return sum(1 for line in self.lines if line.state is HeldState.OPEN)

    @property
    def closed(self) -> int:
        """Routes this target has stopped failing, on two consecutive clean runs."""
        return sum(1 for line in self.lines if line.state is HeldState.CLOSED)

    @property
    def still_breaking(self) -> int:
        """Routes this run sent and read as breaking the target again.

        A count of *this run's readings* where `open_routes` is a count of the
        library's state, and the two are different questions with different answers on
        any run that could not reach the target. Both are printed, because printing
        either alone invites the reader to take it for the other.
        """
        return sum(1 for line in self.lines if line.outcome is HeldOutcome.STILL_OPEN)

    @property
    def not_read(self) -> int:
        """Open routes this run could measure nothing about: unreachable, or unreadable.

        `UNMEASURED` and `UNMEASURABLE` together, counted because they are the reason
        `open_routes` and `still_breaking` can differ and a reader comparing the two
        deserves the number that explains the gap. Two outcomes in one count and not
        two counts, because what a reader of this block does with either is the same
        thing — discount the run — and `not_counted` carries the detail.
        """
        return sum(
            1
            for line in self.lines
            if line.outcome in (HeldOutcome.UNMEASURED, HeldOutcome.UNMEASURABLE)
        )

    @property
    def regressed(self) -> int:
        """Routes that have closed once and come back (ADR-0117 §5).

        Counted over the lines rather than over this run's readings, so a route that
        regressed on an earlier run and is still open reads as a regression now: what
        a reader deciding whether to trust a fix wants to know is that this defect has
        returned before, not only that it returned today.
        """
        return sum(1 for line in self.lines if line.regressed)

    def stated(self) -> str:
        """The block in one sentence, for a surface with room for one.

        Counts joined by prose, and the prose never divides them.
        """
        if self.unlisted is not None:
            return self.unlisted
        if not self.lines:
            return (
                f"No route is held against {self.target_name} — "
                "an empty library, not an unread one."
            )
        said = (
            f"{self.held} route(s) are held against {self.target_name}: "
            f"{self.open_routes} still open and {self.closed} closed. "
            f"{self.still_breaking} of them broke the target again on this run"
        )
        if self.not_read:
            said += f", and {self.not_read} could not be read on this run"
        if self.regressed:
            said += f". {self.regressed} of them have closed once and come back"
        return f"{said}."


def held_block(
    sent: HeldRoutesSent,
    closing: Closing,
    *,
    routes: HeldRoutes = HELD_ROUTES,
) -> HeldBlock:
    """This run's readings and the library they were read off, as one block.

    Called once, at the end of `calibration._run_target`, and strictly **after**
    `closing.count_clean_runs`: the state a line prints is the state the record is in
    once this run's readings have been counted into it, so a route this run closed
    reads as closed here and not one run later.

    The library is **re-read** rather than assembled out of `sent`, for two reasons
    and the second is the load-bearing one. A closed route is not sent, so the
    readings alone can never produce the *found on 3 March, closed on 19 March*
    sentence the operator paid for; and the count of held routes is a fact about the
    library rather than about what this run chose to send, which is the whole of why
    `HeldRoutesSent.held` is a field and not `len(readings)`.

    `routes` has a default for `holding.hold_refused`'s reason and with its
    consequence: the default is the module-level object bound at import, so every
    caller reads the one git-ignored location and a test that wants its own passes one.

    Refuses nothing and raises nothing. Everything above this call has been paid for,
    so a library that will not open leaves as prose on `unlisted` — `holding.py`'s
    convention, three modules on.
    """
    if sent.target_name != closing.target_name:
        # Two different agents' records in one block, which would put one operator's
        # findings under another's name. This one **does** raise, and it is not the
        # storage-fault case: nothing external failed, the call site passed a pair
        # that cannot both be about one target, and the honest prose for it would be
        # a sentence saying the block is about a target it is not about.
        raise ValueError(
            f"a held-route block was asked for over readings of {sent.target_name!r} "
            f"and a closing against {closing.target_name!r}. A block is scoped to one "
            "target, and one built from two would report one operator's library under "
            "another operator's name"
        )
    try:
        library: Sequence[HeldRoute] = routes.for_target(sent.target_name)
    except Exception as fault:  # noqa: BLE001 - never fails a measured run
        return HeldBlock(
            target_name=sent.target_name,
            not_counted=closing.not_counted,
            unlisted=(
                f"The target library of {sent.target_name} could not be listed, so "
                f"this run reports no held routes and not none: {fault}. A count of "
                "zero here would read as an agent nothing has been found against, "
                "which is a different fact from a library that would not open."
            ),
        )
    read = {reading.route: reading for reading in sent.readings}
    return HeldBlock(
        target_name=sent.target_name,
        lines=tuple(
            _line(record, read.get(record.route))
            for record in sorted(library, key=lambda one: one.route.filed_under)
        ),
        not_counted=closing.not_counted,
    )


def _line(record: HeldRoute, reading: HeldReading | None) -> HeldRouteLine:
    """One record and this run's reading of it, as the block's one row.

    The state comes off the **record** and the outcome off the **reading**, which is
    the split `TargetRun.closing` sits beside `TargetRun.held_routes` for: the record
    is what the library became and the reading is what this run saw. A row that took
    both off one of them would either print a closing a run late or invent a reading
    for a route that was never sent.
    """
    return HeldRouteLine(
        route=record.route,
        state=record.state,
        found_in=record.found_in,
        outcome=None if reading is None else reading.outcome,
        closed_in=record.closed_in,
        reopened_in=record.reopened_in,
    )


def _said(outcome: HeldOutcome) -> str:
    """One of the four readings in the words a report prints it in.

    Here rather than on `HeldOutcome` itself, because these are the sentences of a
    *report about a target* and the enum is read by the send and the window as well —
    ADR-0018's distinction at the smallest scale there is.
    """
    match outcome:
        case HeldOutcome.STILL_OPEN:
            return "still breaking this target"
        case HeldOutcome.CLEAN:
            return (
                "held — the target did not break on it, which is one reading and not "
                "a fix: two consecutive clean runs close a route"
            )
        case HeldOutcome.UNMEASURED:
            return (
                "unmeasured — nothing was asked of the target, so this is not a clean "
                "run and counts toward nothing"
            )
        case HeldOutcome.UNMEASURABLE:
            return (
                "unmeasurable — the target answered and no reply carried what the "
                "criterion has to read, so this is not a clean run either"
            )
