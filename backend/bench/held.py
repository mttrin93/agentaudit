"""A confirmed break the admission bar refused, kept against the target it beat.

The fifth store on the `DatabaseStore` seam, and the second one the disclosure
posture has a stated exception for. A route the adaptive layer finds against a
customer's agent faces the single-model bar
([ADR-0107](../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)),
which asks whether it separates three agents of known construction — a question
about generality. Most customer-discovered routes do not have that property, and a
refusal there used to be the deletion of the finding, because the case library was
the only place a route could live. The decision, its six parts and what it costs are
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md);
the build spec is
[docs/specs/the-target-library.md](../../docs/specs/the-target-library.md).

**One target's slice of this store is that target's *target library*, and it is not
the case library.** `load_library` does not read it, it is not in the library digest,
and no other target ever sees it. A member of it is a **held route** and it is its
own type — not a `Case`, the way an `AdaptiveEpisode` is not an `Attempt`
([ADR-0010](../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)).
The fence is carried by the type, so a signature that had to widen to accept both a
`Case` and a `HeldRoute` is the signal to stop rather than a signature to write.

**Its own directory and its own database, not a second table in
`pending/routes.sqlite`.** The ticket that built this store makes that choice and
this is the argument. ADR-0029 decision 6 is one file per concern, and the two
concerns are genuinely different in the one way that matters here: the pending queue
holds what *nothing has measured yet*, read by a triage page and by a person, and
every row in it is on its way to being emptied by a decision (ADR-0104 §4); this
store holds what a decision *produced*, read on every run of its target, and its rows
accumulate a reading each. Sharing one file would also put a store the scored side
opens on every run behind the same write lock as the surface an operator triages on,
and would leave one ignore rule and one directory standing for two lifetimes. ADR-0117
§6's "beside the store that already holds it" is about the exception being the same
exception, not about the file being the same file — and each of ADR-0104's five
mitigations holds here unchanged.

**This store holds two things no other store may — the payload and the target
identity.** The payload because a held route is re-sent on every run of that target,
so a route that cannot be re-run cannot be re-measured, and re-measuring it is the
whole point (ADR-0117 §4); the identity because a held route is scoped to the agent
it beat and nothing else. Both are ADR-0104 §5's exception, and it is an exception to
what may be *kept* and never to what may be published (ADR-0008). `precedent/`'s two
refusals stand exactly as written.

**The clean-run count lives on the record and is never derived from run documents.**
[ADR-0019](../../docs/adr/0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
rejected rebuilding a store by scanning past runs, because it makes the state depend
on every historical record being present and parseable — and here the state decides
whether a route is still sent at all, so a missing run record would silently reopen a
closed defect or close an open one.

**Three modules write here and each writes one kind of sentence.** `holding.py` files
a decided route (#239), `resending.py` sends every open one on every run of its target
(#240), and `closing.py` counts what those runs read back into the record — two clean
runs close a route and it stops being sent (#241). The transitions themselves are on
the record below, because a state and a count that may not disagree are one fact and
not two fields.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.bench.library import (
    AnyFamily,
    DiscoveredBy,
    SuccessCondition,
    SuccessConditionKind,
    family_named,
)
from backend.bench.route_key import RouteKey
from backend.bench.store import DatabaseStore

HELD_NAMESPACE = ("agentaudit", "held")
"""Where a held route is filed, and it says single-tenant by having no tenant.

Two fixed elements and no third, on `PENDING_NAMESPACE`'s reasoning and for the same
reason it matters more here than in the two stores that came before it: one file
holds every target's routes and nothing checks a segment on the way out, so a
namespace of `("agentaudit", "held", tenant)` would look like isolation and enforce
none. Cross-tenant isolation is a named P1 blocker (PLAN §11) and stays one.

What *is* enforced is the scoping the feature actually claims: one route is one
record **per target**, because the target is in the key (`HeldRoute.held_under`).
That is a fact about which record a write lands on, not a boundary between two
users' data.
"""

HELD_DIRECTORY = Path(__file__).resolve().parents[2] / "held"
"""The directory this database lives in, and `.gitignore` ignores it as a directory.

A directory rather than a file name, for the reason `/pending/` is one and with the
same force: SQLite writes `-wal` and `-shm` sidecars beside the database, and here
the journal holds both of the two fields the exception is granted for — a working
probe, and the name of the agent it beat (ADR-0008, ADR-0104 §5). A test asks git
whether this directory is ignored, and asks it of the sidecars too.
"""

DEFAULT_HELD_PATH = HELD_DIRECTORY / "routes.sqlite"
"""Where the target libraries are, at the top of the repository and ignored by git.

One location and no environment override, on `DEFAULT_PENDING_PATH`'s reasoning: a
configurable path is a path that can be configured into a tracked directory, and the
operator who does it will have done it to solve a different problem.
"""

CLEAN_RUNS_TO_CLOSE = 2
"""How many consecutive clean runs close a held route. ADR-0117 §5.

Two, on the window
[ADR-0022](../../docs/adr/0022-the-retirement-window-is-two-readings-of-one-model.md)
already declares rather than a second number invented here: one reading of a
probabilistic target is a coin-flip, and a defect closed on a coin-flip is a report
that says a fix worked when nothing was fixed.

Named on the record's side because the record is where the contradiction is
refusable — `HeldRoute.__post_init__` refuses a closed route with fewer clean runs
than this and an open one with more. `HeldRoute.after_a_clean_run` reads it rather
than carrying a second copy of the number, and `closing.py` decides which readings
reach it.
"""

PAGE = 100
"""How many records one page of a target's library reads.

A page size and never a ceiling: `for_target` pages until the store runs out,
because the figure a held-route block prints — *3 of 5 still open* — is a fact only
if the 5 is every route ever held against that target (ADR-0117 §4). A limit that
silently truncated would make the block report the first hundred findings as though
they were all of them.
"""


class HeldState(StrEnum):
    """Whether this target still fails a held route, or has stopped.

    Two members and not a boolean, because a closed route is kept rather than
    deleted: the report says *found on 3 March, closed on 19 March*, which is the
    sentence the operator paid for, and a closed route that breaks again reads as a
    regression rather than as a new finding (ADR-0117 §5).
    """

    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class HeldRoute:
    """One confirmed break held against one target. Not a `Case`, and never one.

    ADR-0117 §1 carried by the type. What a `Case` has and this does not is the
    whole of the fence: no `id`, because nothing indexes this into a shared
    instrument; no `external_id`, because a held route makes no coverage claim; no
    `discovered_by`, because the answer is constant and is `provenance` below; no
    `admission`, because a held route faced no `D` and never will (§2); and no
    `history`, because its readings are its own type on its own denominator and not
    a gate reading appended to a library record (§4).

    A **held route** and a **target library** are the spec's two added words, and
    neither is bench vocabulary: nothing here is a **case**, an **attempt** or a
    **family rate**, and no figure over these records is keyed on `Family` in a way
    a family rate could pick up.
    """

    route: RouteKey
    """The family and the digest of the probe — the same key the admission memory,
    the pending queue and the library de-duplicate on, so a route that was filed,
    decided and then held is one key throughout (ADR-0033 §3)."""

    target: str
    """The name of the agent this route beat, and the scope of the whole record.

    The name and not the url or the token, on `pending.FiledRoute.target`'s terms:
    what a held route needs is *whose agent*, and a record that also held how to
    reach it would be a credential waiting for an export.
    """

    payload: tuple[str, ...]
    """What is sent, one element per turn, in send order.

    Kept rather than emptied, which is the one place this record departs from
    `pending.Decided` — and the departure is the feature. A decided pending route
    has nothing left to measure with because nothing will measure it again; a held
    route is re-sent on every run of its target, so the probe is the artefact the
    answer needs (ADR-0117 §4). A sequence and never one string, on `Case.payload`'s
    terms (ADR-0053).
    """

    success_condition: SuccessCondition
    """The deterministic check a verdict on this route is read from.

    Required and not optional, so the type refuses a judged route. ADR-0117 §4 sends
    held routes to the **same deterministic evaluator** as any case, and a judged
    verdict carries a reliability figure and a wider stated limit (ADR-0004) — a
    block that mixed the two would print *still open* on a model's opinion.
    """

    description: str
    """What the attacker did, in the attacker's own words. Never payload text.

    On the record because the report says what the route did and not only that a
    route exists (spec, user story 4). The payload is a separate field and is what
    goes on the wire; this is what goes in front of a reader.
    """

    found_in: str
    """The `run_id` of the run that found the route. Not a clock and not a date.

    The run rather than the day, because a run record is the thing a reader can go
    and read: it carries its own date, its target and its declaration, and a date
    stored here would be a second copy of one field of it that nothing keeps in step.
    """

    state: HeldState = HeldState.OPEN
    clean_runs: int = 0
    """Consecutive runs of this target that did **not** break on this route.

    On the record rather than derived by scanning run documents, which ADR-0019
    rejected for every store here: it would make the state depend on every
    historical record being present and parseable, and this state decides whether
    the route is sent at all.

    Consecutive, so a break resets it to zero. A run that could not reach the target
    or whose criterion the evaluator could not read counts no clean run at all
    (ADR-0117 §5) — which is the sending ticket's arithmetic, not this record's.
    """

    closed_in: str | None = None
    """The `run_id` of the run whose reading closed this route. `None` while open.

    The second half of *found on 3 March, closed on 19 March* (ADR-0117 §5, spec
    user story 12), and a second field rather than an overwrite of `found_in`: the
    two are different runs and a reader wants both. A run id for `found_in`'s
    reason — the run record carries the date, the target and the declaration, and a
    date stored here would be a copy of one of its fields that nothing keeps in step.

    Required of a closed route and refused on an open one that was never closed, so
    the record cannot be in a state whose own report it contradicts.
    """

    reopened_in: str | None = None
    """The `run_id` of the run that found this route again after it had closed.

    What makes a reopened route a **regression** rather than a new finding (ADR-0117
    §5, spec user story 13). Kept even after a second closing, because *this route
    has come back once* is the fact a reader needs and a field that emptied itself
    on the next close would answer *has it ever regressed?* with no.

    Set by `HeldRoutes.hold`, which is the only way a closed route reopens: a closed
    route is not sent, so the run loop can never read one breaking. What can happen
    is that the attacker walks the path again, the evaluator confirms the break
    again, and an operator decides it again — the same door ADR-0117 §2 opened.
    """

    provenance = DiscoveredBy.TARGET_SPECIFIC
    """The sixth provenance, and a constant rather than a field.

    A field would be a value somebody could set to something else; there is exactly
    one kind of record here and its provenance is the member `bar_for` refuses. Read
    by anything that wants to say where a held route came from without asking this
    module what it holds.
    """

    def __post_init__(self) -> None:
        if not self.payload or not any(turn.strip() for turn in self.payload):
            raise ValueError(
                "a held route with nothing to send cannot be re-sent, and being "
                "re-sent on every run is the whole of what holding it buys "
                "(ADR-0117 §4)"
            )
        if not self.target.strip():
            raise ValueError(
                "a held route is scoped to the agent it beat, and a record with no "
                "target is a finding about nobody"
            )
        if not self.description.strip():
            raise ValueError(
                "a held route carries the attacker's own description of the break, "
                "so the report says what the route did and not only that a route "
                "exists (spec, user story 4)"
            )
        if not self.found_in.strip():
            raise ValueError(
                "a held route names the run that found it, which is the record a "
                "reader goes to for the date, the target and the declaration"
            )
        if self.clean_runs < 0:
            raise ValueError(
                f"{self.clean_runs} consecutive clean runs is not a count. A break "
                "resets the count to zero and nothing takes it below"
            )
        self._refuse_a_state_the_count_contradicts()
        self._refuse_a_history_the_state_contradicts()

    def _refuse_a_history_the_state_contradicts(self) -> None:
        """The two run ids against the state, so no record can misreport its own past.

        Three refusals and one question — *does this record's history say what its
        state says?* A closed route with no closing run cannot print the second half
        of the sentence it exists for; an open route carrying one that nothing
        reopened says it closed and says nothing about how it came back; and a
        reopening with no closing behind it is a regression of something that never
        stopped (ADR-0117 §5).
        """
        closed = self.state is HeldState.CLOSED
        if closed and not (self.closed_in or "").strip():
            raise ValueError(
                f"{self.route.stated()} is recorded closed against {self.target} "
                "without saying which run closed it. *Found on 3 March, closed on "
                "19 March* is the sentence the operator paid for, and half of it "
                "is this field (ADR-0117 §5)"
            )
        if self.reopened_in is not None and self.closed_in is None:
            raise ValueError(
                f"{self.route.stated()} is recorded as reopened against "
                f"{self.target} having never closed. A regression is a defect that "
                "came back, and a route that never stopped breaking the target did "
                "not come back"
            )
        if not closed and self.closed_in is not None and self.reopened_in is None:
            raise ValueError(
                f"{self.route.stated()} is recorded open against {self.target} and "
                "closed by a run. A closed route that is open again was reopened by "
                "something, and a record that does not say by what reports a "
                "regression as a route that was never closed (ADR-0117 §5)"
            )

    def _refuse_a_state_the_count_contradicts(self) -> None:
        """ADR-0117 §5 as an invariant of the record rather than of one call site.

        Both directions, because both are a report that says something nothing
        measured: a closed route with one clean run says a fix worked on a
        coin-flip, and an open route with two says the bench is still paying to
        send a probe the window already closed.
        """
        closed = self.state is HeldState.CLOSED
        if closed and self.clean_runs < CLEAN_RUNS_TO_CLOSE:
            raise ValueError(
                f"{self.route.stated()} is recorded closed against {self.target} on "
                f"{self.clean_runs} clean run(s), where closing takes "
                f"{CLEAN_RUNS_TO_CLOSE}. One reading of a probabilistic target is a "
                "coin-flip, and a defect closed on one is a report that says a fix "
                "worked when nothing was fixed (ADR-0022, ADR-0117 §5)"
            )
        if not closed and self.clean_runs >= CLEAN_RUNS_TO_CLOSE:
            raise ValueError(
                f"{self.route.stated()} is recorded open against {self.target} on "
                f"{self.clean_runs} clean runs, where {CLEAN_RUNS_TO_CLOSE} close "
                "it. A route past the window that is still sent costs the operator "
                "a probe on every run for a defect the bench has already answered"
            )

    @property
    def family(self) -> AnyFamily:
        """The family the route was found in, off the key it is filed under."""
        return self.route.family

    @property
    def held_under(self) -> str:
        """The key this record is filed under: the target, then the route.

        One route is one held record **per target**, so the target is in the key and
        two targets that fail the same route hold two independent records with two
        independent clean-run counts (ADR-0117 §1).

        The target is *digested* into the key rather than written into it, for two
        reasons and the second is the load-bearing one. A fixed-length prefix cannot
        run into the route's half of the key, so no pair of target and route can
        collide with another pair by where the separator happened to land; and a key
        the store lists does not name anybody's agent, which keeps the identity to
        the value, where ADR-0104 §2 argued the exception for it.
        """
        return _key(self.target, self.route)

    @property
    def regressed(self) -> bool:
        """Whether this route has ever closed and come back. ADR-0117 §5.

        Read off `reopened_in` and never off the state, so that a route which
        regressed and was then fixed again still reads as one: a reader deciding
        whether to trust a fix wants to know that this defect has returned before.
        """
        return self.reopened_in is not None

    def after_a_clean_run(self, run_id: str) -> HeldRoute:
        """This record after one run of its target that did not break on it.

        **One operation over the state and the count**, because the record refuses
        every intermediate: an open route on `CLEAN_RUNS_TO_CLOSE` clean runs is
        refused and so is a closed one below it, so a caller that set the count and
        then the state would raise between the two lines. There is no order in which
        two writes work, which is the point — the window is one fact.

        Closing is a state and never a deletion. Everything the record carried is
        carried on: the run that found it, the attacker's description, and the
        payload the route would be re-sent with if it ever reopened.
        """
        counted = self.clean_runs + 1
        if counted < CLEAN_RUNS_TO_CLOSE:
            return replace(self, clean_runs=counted)
        return replace(
            self, clean_runs=counted, state=HeldState.CLOSED, closed_in=run_id
        )

    def after_a_break(self) -> HeldRoute:
        """This record after a run on which the route broke the target again.

        The count goes to zero and the state does not move: the window is
        *consecutive* clean runs, so a break is not a smaller number of them. No run
        id is taken, because a break changes nothing a reader dates — the route is
        still open, still found in the run that found it, and this run's reading is
        recorded as a reading (`resending.HeldReading`) rather than on the record.
        """
        return self if self.clean_runs == 0 else replace(self, clean_runs=0)

    def reopened_by(self, run_id: str) -> HeldRoute:
        """This closed record, open again, as the regression it is (ADR-0117 §5).

        The count goes back to zero — the fix this route closed on has been shown
        not to hold, so the window starts again — and `closed_in` is **kept**: it is
        the run that closed it, which happened, and a regression is precisely the
        pair of a closing and a return. `found_in` is untouched for the same reason:
        this is the same finding coming back, which is what distinguishes it from a
        new one.
        """
        return replace(self, state=HeldState.OPEN, clean_runs=0, reopened_in=run_id)

    def stored(self) -> dict[str, Any]:
        """The record as the store holds it, payload and target and all."""
        return {
            "family": str(self.route.family),
            "probe": self.route.probe,
            "target": self.target,
            "payload": list(self.payload),
            "success_condition": str(self.success_condition.kind),
            "planted_canary": self.success_condition.planted_canary,
            "description": self.description,
            "found_in": self.found_in,
            "state": str(self.state),
            "clean_runs": self.clean_runs,
            "closed_in": self.closed_in,
            "reopened_in": self.reopened_in,
        }

    @classmethod
    def read(cls, value: dict[str, Any]) -> HeldRoute:
        """One record back out of the store.

        A classmethod and not a module function, which is where this differs from
        `pending.read_filed`: there is one record type here, so nothing has to
        choose between two and nothing has to know about a sibling.
        """
        return cls(
            route=RouteKey(
                family=family_named(str(value["family"])), probe=str(value["probe"])
            ),
            target=str(value["target"]),
            payload=tuple(str(turn) for turn in value["payload"]),
            success_condition=SuccessCondition(
                kind=SuccessConditionKind(str(value["success_condition"])),
                planted_canary=_planted(value.get("planted_canary")),
            ),
            description=str(value["description"]),
            found_in=str(value["found_in"]),
            state=HeldState(str(value["state"])),
            clean_runs=int(value["clean_runs"]),
            closed_in=_run_or_none(value.get("closed_in")),
            reopened_in=_run_or_none(value.get("reopened_in")),
        )


class HeldDatabase(DatabaseStore):
    """The target libraries' own database, at the one git-ignored location.

    Its own file, on ADR-0029 decision 6 and the module docstring's argument: the
    fifth database on this seam, because the queue holds what nothing has measured
    yet and this holds what a decision produced. How the file is opened is
    `backend/bench/store.py`.

    Named rather than replaced by a path argument, because a field annotated with
    this type refuses an `InMemoryStore` before a test has to — ADR-0019 point 2's
    mechanism, and `HeldRoutes.store` is where it bites here.
    """

    __slots__ = ()

    @classmethod
    def default_path(cls) -> Path:
        return DEFAULT_HELD_PATH


@dataclass(frozen=True)
class HeldRoutes:
    """Every target library there is, keyed by target and then by route.

    Named for what it holds rather than `TargetLibrary`, because one object here
    stands for every target's set at once and because *library* is already the
    shared instrument's word. A caller asks for one target's slice — `for_target` —
    and that slice is the **target library** the spec names.

    Holds no connection, for ADR-0029 decision 2's reason: the file is the
    authority, every batch opens its own, and `HELD_ROUTES` below is a module-level
    object with no lifetime.
    """

    store: HeldDatabase
    """The database-backed store, annotated as one.

    Narrower than `BaseStore` on purpose, on `PendingRoutes.store`'s reasoning:
    ADR-0019 point 2 says `InMemoryStore` may not be a durable store's backend, and
    a field typed `BaseStore` would accept one from any future caller with nothing
    to stop it. Here it carries the durability the feature is *for* — a target
    library that died with the process would answer *did my fix work?* with a set
    that emptied itself every restart.
    """

    namespace: tuple[str, ...] = HELD_NAMESPACE

    @classmethod
    def at(cls, path: Path | None = None) -> HeldRoutes:
        """The store at that file, or at the configured one.

        A classmethod rather than a constructor argument, on `PendingRoutes.at`'s
        reasoning: a caller asking for the store should not have to know that the
        thing behind it is a file.
        """
        return cls(store=HeldDatabase(path))

    def hold(self, route: HeldRoute) -> HeldRoute:
        """Hold this route against its target, or leave the one already held alone.

        **A rediscovery does not overwrite the record**, and this is where this
        store differs from `PendingRoutes.file`, which replaces. There the two
        records are two proposals of one path and the newer one is what a decision
        would be taken on; here the record carries history — the run that found the
        route, and the clean-run count that decides whether it is still sent — so a
        replace would silently reset a retirement window every time the attacker
        walked the same path again. One route is one held record per target,
        however many times it is rediscovered (ADR-0117 §1).

        **A rediscovery of a *closed* route reopens it**, and that is the one case
        where this store does write over a record it found. A closed route is not
        sent, so no run loop can ever read one breaking again — the only way the
        bench learns that a fixed defect came back is that the attacker walks the
        path again, the evaluator confirms the break again and an operator decides
        it again, which is the same door ADR-0117 §2 opened for the first finding.
        Reopened rather than filed afresh, because a new record would lose the run
        that found it and the run that closed it, and a defect that has come back is
        a **regression** and not a new finding (ADR-0117 §5, spec user story 13).
        """
        found = self.held(route.target, route.route)
        if found is not None and found.state is not HeldState.CLOSED:
            return found
        held = route if found is None else found.reopened_by(route.found_in)
        self.store.put(self.namespace, held.held_under, held.stored())
        return held

    def record(self, route: HeldRoute) -> HeldRoute:
        """Write this record over the one held under the same key.

        The write `hold` deliberately is not, and the two are separated for that
        reason: `hold` answers *has this route been found before?* and must not
        touch what it finds, while this is a record that has already been read,
        counted and moved by one of `HeldRoute`'s own transitions. Anything
        contradictory the caller composed was refused by the record before it got
        here, so what this may write is bounded by the type and not by this method.
        """
        self.store.put(self.namespace, route.held_under, route.stored())
        return route

    def held(self, target: str, route: RouteKey) -> HeldRoute | None:
        """The record held against that target for that route, or `None`.

        Both arguments, because neither identifies a record on its own: two targets
        may fail the same route and one target may fail many.
        """
        found = self.store.get(self.namespace, _key(target, route))
        return None if found is None else HeldRoute.read(dict(found.value))

    def for_target(self, target: str) -> Sequence[HeldRoute]:
        """Every route ever held against this target, in no promised order.

        Every one, paged rather than limited, for `PAGE`'s reason: *3 of 5 still
        open* is a fact only if the 5 is every route ever held. Closed routes come
        back too — a closed route is kept with the run that closed it, and dropping
        it here would answer *did my fix work?* with silence (ADR-0117 §5).
        """
        held: list[HeldRoute] = []
        offset = 0
        while True:
            page = self.store.search(
                self.namespace, filter={"target": target}, limit=PAGE, offset=offset
            )
            held.extend(HeldRoute.read(dict(item.value)) for item in page)
            if len(page) < PAGE:
                return tuple(held)
            offset += PAGE


HELD_ROUTES = HeldRoutes.at()
"""The target libraries a run reads: the file, at the one location, declared once.

Shared rather than constructed per run, and safe to share because `HeldDatabase`
holds no state — not even a connection: the file is the authority and every batch
opens its own (ADR-0029 decision 2). A caller that wants a different location says
so, which is what every test does.

**Nothing calls it yet.** Declared with the store because the name a later ticket
reaches for should be the one this module already argues for, not one that appears
beside its first caller.
"""


def _digest(text: str) -> str:
    """A truncated `sha256` of the target, for the first half of a record's key.

    Its length is a property of this key and of nothing else: no other store reads
    it, and the route's half of the key is minted by `decided.RouteKey` and not by
    this. What the truncation has to be is *fixed-length* — that is what stops one
    pair of target and route from colliding with another by where the separator
    landed — and long enough that two of a single tenant's target names do not meet
    in it.
    """
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def _key(target: str, route: RouteKey) -> str:
    """The key a target's record for one route is filed under.

    The same composition `HeldRoute.held_under` states, reachable from a target and
    a route alone — which is what a *lookup* holds, since a caller asking whether a
    route is held does not yet have the record it is asking for.
    """
    return f"{_digest(target)}-{route.filed_under}"


def _run_or_none(value: Any) -> str | None:
    """A run id off a stored record, `None` where the record names no run.

    `_planted`'s reason one field over, and it is the same trap: the record refuses
    a closed route with no closing run, so a `None` read back as the string `"None"`
    would not fail — it would pass, and print a run id that never existed.
    """
    return None if value is None else str(value)


def _planted(value: Any) -> str | None:
    """The planted canary off a stored record, `None` where the kind reads none.

    Its own function rather than an inline conditional because `SuccessCondition`
    refuses a canary on a kind that reads none and refuses its absence on a kind
    that does — so what this returns decides whether a record reads back at all,
    and `None` and `"None"` are a long way apart.
    """
    return None if value is None else str(value)
