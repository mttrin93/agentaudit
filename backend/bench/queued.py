"""The one write into the pending-route queue: a customer run's proposals, filed.

Where a run stops holding **proposals** and starts contributing **pending routes**
(`docs/specs/pending-routes.md` keeps those apart: a proposal is a field on the
record of a run that ended, a pending route is a proposal filed durably, awaiting a
decision it has not had). The store itself is `backend/bench/pending.py` and the
exception it is granted on is
[ADR-0104](../../docs/adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md);
this module is the run side of it, and it stands to `pending.py` as `filing.py`
stands to `adaptive/precedent.py`.

**Not called by `run_calibration`, and that is the whole design of this module.**
`run_calibration` is the one code path to a target, and a gate run takes it too — so
filing there would put routes fitted to the three reference agents, the exact
population
[ADR-0012](../../docs/adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)
built the cross-model bar around, into a queue whose whole purpose is routes no
surface decides. The consequence of that separation, since
[ADR-0107](../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md):
every route this module files was found against a user's own agent, carries
`ADAPTIVE_ON_TARGET`. Which bar that provenance faces stays `bar_for`'s answer and
is nowhere composed in this module: the sentence a filed route is reported with says
it is awaiting *a decision*, because what this module knows is what it wrote down and
not what the bar will make of it. `scripts/swap.py` already walks the whole path for
the routes this does not file. So the callers are the customer-run
entry points — the API's run service and
`scripts/bench.py` — and a function here rather than a field on `CalibrationResult`
is what makes that difference something a reader can see at the call site.

**Filing cannot fail a run.** Every exception a route's write raises is caught, kept
as prose on `Queued.refusals`, and the remaining routes are still attempted. The
suite ran and the target was measured; what would have failed here is bookkeeping,
and a run marked failed for it would be reporting a storage fault as a fact about
somebody's agent — `filing.file_precedent`'s position, and `runs._filed`'s, applied
to the store that holds the more sensitive of the two records.

**Nothing here is scored** —
[ADR-0010](../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md).
The input is `AdaptiveEpisode` and there is no parameter an `Attempt` could enter
through and no return value a rate is computed from. A filed route "faces a stated
bar, and is not admitted by having been filed" — the sentence `propose_case` already
answers to, one store further on.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from backend.bench.adaptive.episode import AdaptiveEpisode
from backend.bench.decided import RouteKey
from backend.bench.pending import PENDING_ROUTES, AwaitingDecision, PendingRoutes

NOTHING_WAS_PROPOSED = (
    "the attacker proposed no route, so this run filed nothing to await the bar. "
    "A zero here is a reading about the attacker and about the families it worked "
    "in, never a reading about the target (ADR-0011)"
)
"""What a run that proposed nothing says, said out loud rather than left absent.

An absence is not a reading. The adaptive layer's own section already prints a line
for an episode that found nothing, because an attacker that composed no probe and a
target that held are two facts a reporting surface must never merge (ADR-0011) — and
a queue that grew by nothing is the same fact one store further on.
"""


@dataclass(frozen=True)
class Queued:
    """What one run contributed to the pending queue, and what the store refused.

    Returned rather than raised, and returned rather than logged, on
    `filing.Filing`'s reasoning: a refusal nobody is handed is a refusal nobody
    reads, and the entry points that call this print or record `stated()` beside
    the rest of what the run has to say for itself.
    """

    filed: tuple[AwaitingDecision, ...] = ()
    """The distinct records this run wrote, in the order the routes were proposed.

    The records rather than a count, on `Filing.filed`'s reasoning: the one question
    a reader has about a store that now grows per run is *what went into it*.

    **Distinct by `RouteKey`, and that is the definition of done rather than
    tidiness.** An attacker that finds one path in four episodes proposes it four
    times, `PendingRoutes.file` replaces its own record on the key, and a queue that
    listed four would disagree with the one row on disk it describes. Each route
    keeps the position it was first proposed at and the record of its *last* write,
    which is the record a decision would be taken on (`PendingRoutes.file`) — the
    order is the run's and the content is the store's.
    """

    refusals: tuple[str, ...] = ()
    """One sentence per route this run could not file, and why.

    Per route rather than per run, because the two things that refuse here refuse
    for different populations: a store that cannot be opened refuses every route,
    and a draft no record can carry refuses one
    ([ADR-0084](../../docs/adr/0084-a-route-the-record-cannot-carry-is-declined-and-not-synthesised.md)).
    A batch that gave up on the first would lose the routes after it, which is the
    defect this whole module exists to remove.
    """

    def stated(self) -> str:
        """What this run says about its queue, in one sentence, always.

        Always, including for the run that filed nothing: the zero is
        `NOTHING_WAS_PROPOSED` rather than silence, for that constant's reason.
        """
        if not self.filed and not self.refusals:
            return NOTHING_WAS_PROPOSED
        said = []
        if self.filed:
            said.append(
                f"{len(self.filed)} route(s) the attacker found are filed and "
                "awaiting a decision: "
                + ", ".join(record.route.stated() for record in self.filed)
                + ". A filed route is not admitted by having been filed (ADR-0012 "
                "as ADR-0107 narrows it)"
            )
        if self.refusals:
            said.append(
                f"{len(self.refusals)} route(s) could not be filed, and the "
                "measurement stands regardless: " + "; ".join(self.refusals)
            )
        return ". ".join(said)


def file_proposals(
    episodes: Iterable[AdaptiveEpisode],
    *,
    today: date,
    queue: PendingRoutes = PENDING_ROUTES,
) -> Queued:
    """File every route this run's episodes proposed, and report what refused.

    The target is read off each episode rather than taken as an argument, so the
    identity on the row is the identity of the agent the route was actually found
    against — a run handed a target name beside its episodes could file a route
    under the wrong agent's name, and the queue's one job is that a person can tell
    which routes are worth paying to decide (ADR-0104 §2).

    **`queue` has a default where `file_precedent`'s store does not**, and the
    departure is deliberate rather than an oversight. ADR-0031 point 2 makes the
    precedent write handle a required argument so that only `run_calibration` holds
    one; here the equivalent restriction is *which entry points call this at all*,
    which no signature can carry — a required argument would be satisfied by
    `PENDING_ROUTES` at any call site that imported it. So the wall is the
    reachability test instead (`test_pending_filed_by_a_run.py`), and the default is
    what keeps every caller filing into the one location with no environment
    override (`pending.DEFAULT_PENDING_PATH`). It is the module-level object bound
    at import, so a caller that wants a different queue passes one — which is what
    every test does, and how the suite's redirection reaches this (`conftest`
    moves the store's path rather than rebinding the name).

    **No default for `today`**, for `PendingRoutes.file`'s reason: nothing between
    the entry point and the row reads a clock, so a route filed by a replayed run is
    dated to the run rather than to the morning it was replayed. The entry point is
    where a clock may be read, and it is the one place that knows which day it means.
    """
    filed: dict[RouteKey, AwaitingDecision] = {}
    refusals: list[str] = []
    for episode in episodes:
        for proposal in episode.proposals:
            try:
                record = queue.file(proposal, target=episode.target_name, today=today)
            except Exception as refused:  # noqa: BLE001 - never fails the run
                refusals.append(
                    f"{RouteKey.of(proposal.case).stated()} was not filed: {refused}"
                )
                continue
            # Keyed rather than appended, so this lists rows and not writes: the
            # store replaces on the key, so four proposals of one path are one
            # record and have to be one entry here (`Queued.filed`).
            filed[record.route] = record
    return Queued(filed=tuple(filed.values()), refusals=tuple(refusals))
