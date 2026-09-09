"""Where a route found against somebody's real agent waits for the decision it needs.

The fourth store on the `DatabaseStore` seam, and the one the disclosure posture has
a stated exception for. A route the adaptive layer found against a customer's agent
cannot be decided by the run that found it — the bar is `D` against the three
reference agents on two models (ADR-0012), and a customer run touched one endpoint,
the customer's. Until this store existed the route reached one printed line and died
with the run: `AdaptiveEpisode.proposals` is a field on a record of a run that ended,
`precedent/findings.sqlite` holds prose and no target identity (ADR-0008, ADR-0011),
and `decisions/routes.sqlite` holds what the gate *measured*, which for an undecided
route is nothing. Both correct stores refuse it for good reasons and there was no
third.

The decision, the four alternatives it beat and the five terms it is granted on are
[ADR-0104](../../docs/adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md).
Two of its points shape everything below and are stated here because they are what a
reader of this file most needs:

**This store holds two things no other store may — the payload and the target
identity.** The payload because the bar is decided by *sending the probe*, so a route
that cannot be re-run cannot be measured later; the identity because the queue's whole
purpose is that a person reads it and decides which routes are worth paying to
measure, and a page that cannot say whose agent a route beat asks the operator to
spend an inference budget blind. Neither refusal is relaxed for any other store, and
`precedent/`'s two stand exactly as written.

**The payload is emptied by the decision, and the type is what empties it.** State is
`pending`, `admitted` or `rejected`, and `Decided` has no `draft` field for a payload
to sit in — so the two fields the exception was granted for exist only for routes
still awaiting a decision. A convention that said *clear the payload when you decide*
would have one forgetful call site between it and a store of live exploits with no
expiry (ADR-0104 §4).

**Nothing here reaches an instrument and nothing here is scored** (ADR-0010). A
pending route is not an **attempt** and is not a **case** — it becomes one only by
clearing the bar, through `entry.enter` and no other writer (ADR-0033) — so nothing
filed here reaches a denominator. It is read by the queue's own page and by the
surface that decides it (ADR-0105), and by nothing blinded, nothing scored and no
export. That is mitigations 3 and 4, and a second reader is a change to this record
rather than a change to this module.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.decided import RouteKey, criterion_of
from backend.bench.entry import case_record
from backend.bench.library import AnyFamily, Case, case_from_record, family_named
from backend.bench.store import DatabaseStore

PENDING_NAMESPACE = ("agentaudit", "pending")
"""Where a pending route is filed, and it says single-tenant by having no tenant.

Two fixed elements and no third, on `PRECEDENT_NAMESPACE`'s and
`DECISION_NAMESPACE`'s reasoning: a namespace of `("agentaudit", "pending", tenant)`
would look like isolation and enforce none, since one file holds every record and
nothing checks the segment on the way out. Cross-tenant isolation is a named P1
blocker (PLAN §11), and this is the place a reader can see it is **absent rather than
assumed** — which matters more here than in either of the other two, because this is
the one store that knows whose agent a route was found against.
"""

PENDING_DIRECTORY = Path(__file__).resolve().parents[2] / "pending"
"""The directory this database lives in, and `.gitignore` ignores it as a directory.

A directory rather than a file name, for the reason `/precedent/`, `/decisions/`,
`/runs/` and `/checkpoints/` are directories: SQLite writes `-wal` and `-shm`
sidecars beside the database, and a journal must not be what the ignore rule missed.
**That reason is stronger here than anywhere it has been applied before**, because
here the sidecar holds both of the two fields ADR-0104 §5 grants the exception for —
a working probe, and the name of the agent it beat.
"""

DEFAULT_PENDING_PATH = PENDING_DIRECTORY / "routes.sqlite"
"""Where the queue's database is, at the top of the repository and ignored by git.

One location and no environment override, on `DEFAULT_DECISION_PATH`'s reasoning: a
configurable path is a path that can be configured into a tracked directory, and the
operator who does it will have done it to solve a different problem (ADR-0104 §5). A
test asks git whether this path is ignored, and asks it of the sidecars too.
"""


class RouteState(StrEnum):
    """What has happened to a filed route: nothing yet, or one of two decisions.

    Three members and not a boolean, because a rejected route is a finding rather
    than a route that failed to be admitted — ADR-0012 calls a cross-model discard
    "a finding in its own right" — and it stays on the page with the gate's own
    reason beside it.
    """

    PENDING = "pending"
    ADMITTED = "admitted"
    REJECTED = "rejected"


DECIDED_STATES = frozenset({RouteState.ADMITTED, RouteState.REJECTED})
"""The two states a `Decided` record may be in, named once for the refusal below."""


class NotFiled(KeyError):
    """A decision was offered for a route this store holds no record of.

    Refused rather than filed as a fresh decided record. The target, the criterion
    and the attacker's prose come off the record the run filed, and a decision that
    minted them would be a queue row about a route this store never held — which is
    a triage page that invents its own history.
    """


class NotAwaitingDecision(ValueError):
    """A route that has already been decided was offered a second decision.

    Refused, and the reason is §4's rather than tidiness: a decided record has no
    payload, so nothing could have measured the route between the first decision and
    this one. Allowing the write would let an admitted route be recorded as rejected
    on the strength of no reading at all, and would overwrite the gate's own reason
    for the answer that *was* measured.
    """


@dataclass(frozen=True)
class FiledRoute:
    """What every record in this queue carries, decided or not.

    The base of the two record types rather than one type with an optional payload,
    which is ADR-0104 §4 carried by the type: `AwaitingDecision` adds the draft and
    `Decided` adds the answer, and no single class exists that could hold both a
    decision and a live exploit.

    The criterion is stored beside the draft rather than only derived from it,
    because it is the one thing about *what a verdict meant* that outlives the
    payload: a decided record has no draft to re-derive it from, and the surface
    that decides a route refuses one whose criterion no longer matches any live case
    rather than paying to measure a probe nothing can score.
    """

    route: RouteKey
    """The family and the digest of the probe — the same key the admission memory and
    the library de-duplicate on (`decided.RouteKey`), so one route is one pending
    record, one remembered measurement and one library record."""

    criterion: str
    """`decided.criterion_of` of the draft: a digest of what a verdict on it means."""

    description: str
    """What the attacker did, in the attacker's own words. Never payload text — the
    payload is on the draft, which is the field a decision removes."""

    target: str
    """The name of the target the route was found against.

    The one field no other store in this repository carries, and ADR-0104 §2 is why
    it may be here: ADR-0011's rule is *precedent carries no target identity to
    anything blinded*, and nothing that reads this store is an instrument. The name
    and not the url or the token — what triage needs is which agent, and a record
    that also held how to reach it would be a credential waiting for an export.
    """

    filed_on: date
    """The day the run that found the route filed it. Not a clock this module reads:
    the caller passes the date, as `entry` and `decided` do, so a route filed by a
    replayed run is not dated to the morning it was replayed."""

    def _shared(self) -> dict[str, Any]:
        """The fields both record types store, in one place so they cannot drift."""
        return {
            "family": str(self.route.family),
            "probe": self.route.probe,
            "criterion": self.criterion,
            "description": self.description,
            "target": self.target,
            "filed_on": self.filed_on.isoformat(),
        }


@dataclass(frozen=True)
class AwaitingDecision(FiledRoute):
    """A route filed and not yet decided: the record that carries the payload.

    The draft is the whole `Case` `propose_case` produced, held as the TOML record
    `entry.case_record` writes and read back through `library.case_from_record`, so
    what this store keeps is exactly what `enter` would write if the bar admitted it
    — one definition of the format rather than a second serialiser for a database.
    A draft `case_record` cannot write is not filed at all: it is a route no library
    could hold, and ADR-0084 already decides that such a route is declined rather
    than synthesised.
    """

    draft: Case
    """The case the route would become, payload included. Gone once decided."""

    @property
    def state(self) -> RouteState:
        """`pending`, and a property rather than a field: the type is the state.

        A record of this class with any other state would be a live exploit filed
        as decided, so there is nothing for a caller to set and nothing to keep in
        step with the class.
        """
        return RouteState.PENDING

    def stored(self) -> dict[str, Any]:
        """The record as the store holds it, payload and target and all."""
        return {
            **self._shared(),
            "state": str(RouteState.PENDING),
            "draft": case_record(self.draft),
        }


@dataclass(frozen=True)
class Decided(FiledRoute):
    """A route the bar has answered: the state, the reason, and no payload.

    What is left after a decision is a queue's outcome column — a route key, a
    state and the gate's own reason — and ADR-0104 §3 mitigation 1 says plainly that
    this is *not* what the exception was granted for. The row stays so that an
    operator can read what happened to a route they paid to decide; the probe does
    not, because there is nothing left to measure with it.
    """

    state: RouteState
    reason: str
    """Why, in the deciding surface's own words. A rejected route's reason is the
    finding ADR-0012 asks for; an admitted one's says what cleared the bar."""

    def __post_init__(self) -> None:
        if self.state not in DECIDED_STATES:
            raise ValueError(
                f"{self.state} is not a decision. A record with no payload and a "
                "state of pending would be a route awaiting a decision that "
                "nothing could ever measure, because the probe it would be "
                "measured with is the field this class does not have (ADR-0104 §4)"
            )
        if not self.reason.strip():
            raise ValueError(
                f"{self.route.stated()} was decided {self.state} with no reason. A "
                "rejected route is a finding in its own right (ADR-0012) and the "
                "reason is the whole of what the row says to an operator who paid "
                "for it"
            )

    def stored(self) -> dict[str, Any]:
        return {**self._shared(), "state": str(self.state), "reason": self.reason}


def read_filed(value: dict[str, Any]) -> AwaitingDecision | Decided:
    """One record back out of the store, as whichever of the two types it is.

    Dispatched on the stored state rather than on the presence of a `draft` key, so
    a record that somehow held both would be read as decided and its payload
    dropped rather than being handed back to a caller that asked for a decided one.

    A module function and not a classmethod, which is where this differs from
    `DecidedRoute.read`: the dispatch *chooses between the two types*, so it cannot
    belong to either without one of them knowing about the other.
    """
    state = RouteState(value["state"])
    shared: dict[str, Any] = {
        "route": RouteKey(family=_family(value), probe=str(value["probe"])),
        "criterion": str(value["criterion"]),
        "description": str(value["description"]),
        "target": str(value["target"]),
        "filed_on": date.fromisoformat(str(value["filed_on"])),
    }
    if state is RouteState.PENDING:
        return AwaitingDecision(
            **shared, draft=case_from_record(tomllib.loads(str(value["draft"])))
        )
    return Decided(**shared, state=state, reason=str(value["reason"]))


class PendingDatabase(DatabaseStore):
    """The queue's own database, at the one git-ignored location.

    Its own file, on ADR-0029 decision 6 and ADR-0104 §5: the fourth database on
    this seam, because the memory holds what the gate measured and this holds what
    nothing has measured yet. How the file is opened is `backend/bench/store.py`.

    Named rather than replaced by a path argument, because a field annotated with
    this type refuses an `InMemoryStore` before a test has to — ADR-0019 point 2's
    mechanism, and `PendingRoutes.store` is where it bites here.
    """

    __slots__ = ()

    @classmethod
    def default_path(cls) -> Path:
        return DEFAULT_PENDING_PATH


@dataclass(frozen=True)
class PendingRoutes:
    """The queue: what a run files into, and what the deciding surface reads.

    A thin reading of a `DatabaseStore`, so that the two rules that make the
    exception bounded live in one place. `file` is the only way in and it keys on
    the route, so a rediscovered path replaces its own record rather than filling
    the queue with copies of it. `decide` is the only way from a payload to a
    decision, and it is what removes the payload.

    Holds no connection, for ADR-0029 decision 2's reason: the file is the
    authority, every batch opens its own, and `PENDING_ROUTES` below is a
    module-level object with no lifetime.
    """

    store: PendingDatabase
    """The database-backed store, annotated as one.

    Narrower than `BaseStore` on purpose, on `DecidedRoutes.store`'s reasoning:
    ADR-0019 point 2 says `InMemoryStore` may not be a durable store's backend, and
    a field typed `BaseStore` would accept one from any future caller with nothing
    to stop it. Here it also carries the durability the whole store exists for — an
    in-memory queue would lose the route with the process, which is the defect this
    module was written to remove.
    """

    namespace: tuple[str, ...] = PENDING_NAMESPACE

    @classmethod
    def at(cls, path: Path | None = None) -> PendingRoutes:
        """The queue at that file, or at the configured one.

        A classmethod rather than a constructor argument, on `DecidedRoutes.at`'s
        reasoning: a caller asking for the queue should not have to know that the
        thing behind it is a file.
        """
        return cls(store=PendingDatabase(path))

    def file(
        self,
        proposal: ProposedRoute,
        *,
        target: str,
        today: date,
    ) -> AwaitingDecision:
        """File one route the attacker found, so it survives the run that found it.

        Idempotent by the key: a route already filed is *replaced* rather than
        appended to, because the two records are two proposals of one path and the
        newer one is the one whose draft and prose a decision would be taken on.

        **No default for `today`**, so this module reads no clock at all — the
        stricter half of what `entry` and `decided` do, and cheap here because the
        only caller is a run that knows the day it ran. A route filed by a run
        replayed next month is not dated to the morning it was replayed.

        Nothing here decides anything. A filed route "faces a stated bar, and is not
        admitted by having been filed" — the same sentence `propose_case` already
        answers to (ADR-0010, ADR-0012).
        """
        record = AwaitingDecision(
            route=RouteKey.of(proposal.case),
            criterion=criterion_of(proposal.case),
            description=proposal.description,
            target=target,
            filed_on=today,
            draft=proposal.case,
        )
        self.store.put(self.namespace, record.route.filed_under, record.stored())
        return record

    def filed(self, route: RouteKey) -> AwaitingDecision | Decided | None:
        """The record this queue holds for that route, or `None` for one it does not."""
        found = self.store.get(self.namespace, route.filed_under)
        return None if found is None else read_filed(dict(found.value))

    def queue(self) -> tuple[AwaitingDecision | Decided, ...]:
        """Every record this queue holds, pending and decided, for one page.

        Both states rather than the pending ones alone, because the page a decision
        writes to is the page it was started from: an admitted route's row says
        what it became and a rejected one's carries the gate's reason, and a queue
        that dropped a route the moment it was decided would answer "what happened
        to the route I paid for?" with silence (user stories 11 and 12).
        """
        return tuple(
            read_filed(dict(item.value)) for item in self.store.search(self.namespace)
        )

    def decide(
        self,
        route: RouteKey,
        *,
        state: RouteState,
        reason: str,
    ) -> Decided:
        """Record the answer, and take the payload off the disk in the same write.

        One write and not two: the decided record *replaces* the pending one under
        the same key, so there is no window in which a decision is recorded and the
        probe is still there — and no second call anybody could forget to make. That
        is ADR-0104 mitigation 5, and §4 is why it is the type rather than a nulled
        column that carries it.

        The route has to be one this queue holds and one nothing has decided
        (`NotFiled`, `NotAwaitingDecision`): everything the decided row says apart
        from the answer is read off the record the run filed.
        """
        found = self.filed(route)
        if found is None:
            raise NotFiled(
                f"{route.stated()} is not in this queue, so there is no filed "
                "route to decide. A decision needs the target, the criterion and "
                "the prose the run that found the route filed with it"
            )
        if isinstance(found, Decided):
            raise NotAwaitingDecision(
                f"{route.stated()} was already decided {found.state} — "
                f"{found.reason}. Its payload went with that decision, so nothing "
                "has measured this route since, and a second answer would rest on "
                "no reading at all"
            )
        record = Decided(
            route=found.route,
            criterion=found.criterion,
            description=found.description,
            target=found.target,
            filed_on=found.filed_on,
            state=state,
            reason=reason,
        )
        self.store.put(self.namespace, record.route.filed_under, record.stored())
        return record


PENDING_ROUTES = PendingRoutes.at()
"""The queue a run files into: the file, at the one location, declared once.

Shared rather than constructed per run, and safe to share because `PendingDatabase`
holds no state — not even a connection: the file is the authority and every batch
opens its own (ADR-0029 decision 2). A caller that wants a different location says
so, which is what every test does.
"""


def _family(value: dict[str, Any]) -> AnyFamily:
    """The family off a stored record, in either tier.

    Read through `family_named` rather than through `Family`, because `RouteKey` is
    widened to `AnyFamily` with the record it is read off (ADR-0035) and a record
    filed in an elective family would otherwise come back out as a `ValueError`.
    """
    return family_named(str(value["family"]))
