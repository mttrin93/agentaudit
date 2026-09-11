"""The one write into a target library: a confirmed break the bar refused, held.

Where a decided pending route stops being a queue row and starts being a **held
route**. The store and the type are `backend/bench/held.py`; this module is the
decision side of it, and it stands to `held.py` as `queued.py` stands to
`pending.py` and `filing.py` stands to `adaptive/precedent.py`. The decision is
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§2 and §3; the build spec is
[docs/specs/the-target-library.md](../../docs/specs/the-target-library.md).

**One route takes one door, and this function is the door.** The same approval on
`/pending-routes` answers two questions that were always distinct — *is this
everyone's?*, which the bar decides and `entry.enter` writes (ADR-0033), and *is
this still yours?*, which the operator decides and this writes. A route the bar
**admits** is not held: a library case is already sent to every target including
this one, and holding it as well would send one probe twice and count it on two
denominators (ADR-0117 §3). The state the queue is told is the state this is told,
so the two writes cannot disagree about which door a route took.

**A person is the door, and the gate is not.** A held route faces no `D`, and what
it faces instead is what it has already passed: an evaluator-confirmed break
against the target (ADR-0106) and a *named* operator's approval (ADR-0117 §2). Both
halves are refused here rather than assumed, because this is the one place in the
bench where something scored enters without a declared threshold behind it — so a
route no confirmed break stands behind, and an approval with nobody's name on it,
are both declined whatever the surface selected.

**Nothing here is scored and nothing here widens.** The input is an
`AwaitingDecision` and the output is a `HeldRoute` or nothing; there is no
parameter a `Case` enters through and no return value a family rate is computed
from. The fence ADR-0117 §4 rests on is the type, so a signature that had to accept
both a `Case` and a `HeldRoute` is the signal to stop rather than a signature to
write.

**Holding cannot fail a decision**, on `queued.file_proposals`'s reasoning one
store further on: the routes were sent to the reference agents and the operator
paid for the answer, so a store that cannot be written to costs a record and never
an answer. Every refusal leaves on `Holding.reason`, which the caller puts in front
of the operator rather than discarding.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.bench.held import HELD_ROUTES, HeldRoute, HeldRoutes
from backend.bench.library import Case, VerdictClass, found_by_the_attacker
from backend.bench.pending import AwaitingDecision, RouteState


@dataclass(frozen=True)
class Holding:
    """What one decision left in a target library, and what it says about it.

    A record rather than a `HeldRoute | None`, on `queued.Queued`'s reasoning: a
    refusal nobody is handed is a refusal nobody reads, and every way this declines
    to hold a route is something the operator who approved it has to be told. The
    reason is filled on the way in as well as on the way out — a route that *was*
    held says who opened the door, because an approval rather than a declared
    threshold is the whole of what licenses the record.
    """

    held: HeldRoute | None
    reason: str

    def stated(self) -> str:
        """What this decision says about the target library, in one sentence."""
        return self.reason


def hold_refused(
    record: AwaitingDecision,
    *,
    decided_as: RouteState,
    approved_by: str,
    routes: HeldRoutes = HELD_ROUTES,
) -> Holding:
    """Hold this route against the target it beat, if the bar refused it.

    `decided_as` is the answer the queue is being given, taken as an argument
    rather than re-derived, so that the case library's write and this one cannot
    disagree about which of the two doors a route took (ADR-0117 §3). `ADMITTED`
    holds nothing and says why; `PENDING` holds nothing because nothing decided
    anything.

    `approved_by` is the operator whose approval this is, and it is required for
    the reason `found_in` is required on the record: it is the fact this write
    cannot be made honestly without (ADR-0117 §2). It is kept in the sentence the
    queue row carries rather than on the held record, because the record is
    `HeldRoute` and widening it is a decision of its own.

    `routes` has a default for `queued.file_proposals`'s reason and with its
    consequence: the default is the module-level object bound at import, so every
    caller writes to the one git-ignored location and a test that wants its own
    passes one.
    """
    if decided_as is not RouteState.REJECTED:
        return Holding(None, _one_door(record, decided_as))
    refusal = _why_it_cannot_be_held(record, approved_by)
    if refusal is not None:
        return Holding(None, refusal)
    already = routes.held(record.target, record.route)
    if already is not None:
        return Holding(already, _already(already))
    try:
        held = routes.hold(_route_from(record))
    except Exception as refused:  # noqa: BLE001 - never fails a decision
        return Holding(
            None,
            (
                f"{record.route.stated()} was not held against {record.target}: "
                f"{refused}. The route was measured and the decision stands — what "
                "a storage fault costs here is a record and never an answer"
            ),
        )
    return Holding(
        held,
        (
            f"{held.route.stated()} is held against {record.target} on the approval "
            f"of {approved_by}, and is re-sent on every run of that target until it "
            "stops breaking it. The bar refused it and a person did not: what "
            "licenses this record is an evaluator-confirmed break and an approval, "
            "not a declared threshold (ADR-0117 §2)"
        ),
    )


def _route_from(record: AwaitingDecision) -> HeldRoute:
    """The held record this pending one becomes, off the draft and nothing else.

    Every field is read from what the run that found the route wrote down. Nothing
    is minted here — a description this composed would be this module's account of
    a break it did not see, and a run id it invented would send a reader to a
    record that does not exist.
    """
    draft = record.draft
    condition = draft.success_condition
    # Narrowed by `_why_it_cannot_be_held`, which declined a route whose verdict
    # would be a judgement rather than a reading.
    assert condition is not None
    return HeldRoute(
        route=record.route,
        target=record.target,
        payload=draft.payload,
        success_condition=condition,
        description=record.description,
        found_in=record.found_in,
    )


def _why_it_cannot_be_held(record: AwaitingDecision, approved_by: str) -> str | None:
    """Why this route may not be held, or `None` for one that may.

    Three refusals and one function, because they are one question — *does the
    evidence a held route rests on actually exist?* — and a caller that asked them
    one at a time would be free to ask two of the three.
    """
    if not approved_by.strip():
        return (
            f"{record.route.stated()} was not held against {record.target}: the "
            "approval that would license it carries nobody's name. A held route is "
            "the one scored thing here that faced no declared threshold, and what "
            "stands in a threshold's place is a person (ADR-0117 §2)"
        )
    if not _a_confirmed_break(record.draft):
        return (
            f"{record.route.stated()} was not held against {record.target}: nothing "
            "recorded a confirmed break behind it. What a held route claims is that "
            "this probe produced this verdict against this agent, and an approval "
            "is proportionate to that claim only because the evaluator has already "
            "confirmed it (ADR-0106, ADR-0117 §2)"
        )
    if record.draft.verdict_class is not VerdictClass.DETERMINISTIC:
        return (
            f"{record.route.stated()} was not held against {record.target}: its "
            "verdict would be a judgement rather than a reading. A held route is "
            "judged by the same deterministic evaluator as any case, because *still "
            "open* is a verdict and a judged one carries a reliability figure and a "
            "wider stated limit (ADR-0004, ADR-0117 §4)"
        )
    if record.draft.success_condition is None:
        return (
            f"{record.route.stated()} was not held against {record.target}: it "
            "carries no success condition, so there is no deterministic check a "
            "later run could read *still open* off (ADR-0117 §4)"
        )
    if not record.found_in.strip():
        return (
            f"{record.route.stated()} was not held against {record.target}: it was "
            "filed before the run that found it was recorded, so the held record "
            "would answer *found in what?* with nothing. The row is still readable "
            "and still decidable; what it cannot be is held (`pending.FiledRoute`)"
        )
    return None


def _a_confirmed_break(draft: Case) -> bool:
    """Whether an evaluator confirmed a break behind this draft. ADR-0106.

    Read off the provenance rather than off a flag this module would have to be
    handed, because the provenance is where the fact survives: the only way a case
    record carries an attacker's provenance is `proposal.proposed_from`, which
    declines a route "from an episode with no confirmed break" before it drafts
    one. An authored case and a retrieved one are perfectly good library records
    that no episode of this bench ever broke a target with.
    """
    return found_by_the_attacker(draft.discovered_by)


def _one_door(record: AwaitingDecision, decided_as: RouteState) -> str:
    """Why a route that was not refused is not held. ADR-0117 §3."""
    if decided_as is RouteState.ADMITTED:
        return (
            f"{record.route.stated()} is not held against {record.target}: the bar "
            "admitted it, so it is in the shared case library and every run of "
            "every target already sends it as a scored attempt in its family. "
            "Holding it as well would send one probe twice and count it on two "
            "denominators (ADR-0117 §3)"
        )
    return (
        f"{record.route.stated()} is not held against {record.target}: this "
        f"measurement left it {decided_as}, and a route the bar has not refused is "
        "not a route the operator was asked about"
    )


def _already(held: HeldRoute) -> str:
    """What a rediscovery says, and why the record it found is left alone.

    `HeldRoutes.hold` leaves an existing record alone rather than replacing it, and
    this is the sentence that fact reaches an operator as: the count on the record
    is a retirement window in progress, and a rediscovery that reset it would stop
    a target that had nearly closed a defect from ever closing it (ADR-0117 §5).
    """
    return (
        f"{held.route.stated()} is already held against {held.target}, found in "
        f"{held.found_in} and {held.state} on {held.clean_runs} clean run(s). The "
        "record is left as it stands: one route is one held record per target "
        "however many times the attacker walks it again, and the count on it is a "
        "retirement window a rediscovery must not reset (ADR-0117 §1, §5)"
    )
