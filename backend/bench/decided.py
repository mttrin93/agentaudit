"""What the admission gate already measured, so a route is not re-measured for it.

`promote` decides one proposed route against a declared threshold and writes
nothing (`adaptive/promotion.py`). So a route the attacker rediscovers next run is
re-proposed and **re-measured against three reference agents on every model the run
declared** — at the operator's cost, for the same answer — and the `RejectionKind`
counts behind a refusal are computed and thrown away, when ADR-0012 calls exactly
those counts a finding in its own right. This module is the memory that stops both.
How many models that is belongs to the caller and not to the route: two under
`scripts/swap.py`, one on `/pending-routes` since
[ADR-0107](../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md),
and `admitting.py` is where the arithmetic of what the memory saves is argued.

The decision, its alternatives and the hazard it had to be built around are
[ADR-0032](../../docs/adr/0032-the-admission-memory-holds-the-measurement.md). Two
of its points decide the shape of everything below and are stated here because they
are what a reader of this file most needs:

**What is remembered is the measurement, never the decision.** Only the counts the
three reference agents returned; `promote` decides them again, under the current
declared rule and the current arithmetic, on every run that reads them. Why that
removes the stale-threshold failure mode rather than guarding it is the ADR's, and
it is the argument `AdmissionReading` already makes about a stored `D`.

**A record is served only when it is this run's measurement.** `recall` answers
`Stale` where the models, the criterion or the denominator has moved, or where the
`RejectionKind` stored beside the counts is not the one the current arithmetic
reaches. The four rules and what each is for are ADR-0032's; `Conditions` and
`recall` below carry the local consequence of each.

**Nothing here enters a scored number** (ADR-0010). The file is machine-local and
git-ignored, so a rate, an interval, a band, a `D` or a κ that read it would be a
figure that depended on the machine. What it reaches is the admission gate — the one
edge the adaptive layer touches the scored side by, where a declared threshold
decides — and the adaptive section of a run's own report, which already declares
itself recorded and not reproducible (ADR-0017). It does not write to the case
library: remembering an admission is not admitting, and #40 is the ticket that takes
an admitted route onward.

**A digest, never payload text, and no target identity** (ADR-0008, ADR-0011). The
key is the family and a digest of the probe; the value carries the attacker's own
prose, which is the only part of a route ever written down outside a run (CONTEXT.md,
**route**).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.admission import RejectionKind, kind_of
from backend.bench.library import AdmissionReading, AnyFamily, Case, Family
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.store import DatabaseStore

DECISION_NAMESPACE = ("agentaudit", "admission")
"""Where a decided route is filed, and it says single-tenant by having no tenant.

Two fixed elements and no third, on ADR-0019 point 5's reasoning and ADR-0029 point
4's restatement of it: a namespace of `("agentaudit", "admission", tenant)` would
look like isolation and enforce none, since one file holds every entry and nothing
checks the segment on the way out. Cross-tenant isolation is a named P1 blocker
(PLAN §11), and this is the place a reader can see it is absent rather than assumed.
"""

DECISION_DIRECTORY = Path(__file__).resolve().parents[2] / "decisions"
"""The directory this database lives in, and `.gitignore` ignores it as a directory.

A directory rather than a file name, for the reason `/precedent/` and `/checkpoints/`
are directories: SQLite writes `-wal` and `-shm` sidecars beside the database, and a
journal holding the prose of a working unpublished route must not be the one thing
the ignore rule missed (ADR-0008).

Its own directory and its own database, not a table in `precedent/findings.sqlite`
— ADR-0029 decision 6, whose reasoning ADR-0032 takes up. The local consequence is
here: this path, this ignore rule and this database are reached by nothing that
reads precedent.
"""

DEFAULT_DECISION_PATH = DECISION_DIRECTORY / "routes.sqlite"
"""Where the memory's database is, at the top of the repository and ignored by git.

One location and no environment override, on `DEFAULT_STORE_PATH`'s reasoning: a
configurable path is a path that can be configured into a tracked directory. A test
asks git whether this path is ignored, and asks it of the sidecars too.
"""

ABOUT_THE_ROUTE = frozenset(
    {
        RejectionKind.ADMITTED,
        RejectionKind.CROSS_MODEL,
        RejectionKind.SEPARATED_NOWHERE,
        RejectionKind.FLOOR_AT_ZERO,
    }
)
"""The four answers that are findings about the route, and so the four worth keeping.

`RejectionKind`'s own docstrings draw this line and this constant reads it off them:
the other two members are facts about a *run* rather than about a route. `UNREAD` is
"a run that did not happen the way the bar needs it to, and it is not evidence about
the route"; `NOT_MEASURED` is "no reading exists, so nothing about this proposal has
been measured and nothing may be concluded from it". Remembering either would be
remembering that a measurement did not happen, and then answering a later run with it.

`FLOOR_AT_ZERO` is on this side of the line and the argument is
[ADR-0118](../../docs/adr/0118-a-rejection-at-the-floor-is-counted-apart-from-a-case-that-separated-nothing.md)
§5, because it is the one member whose gloss makes it look like the other two: it says
nothing was learned about the case. What it does not say is that nothing was measured.
The agents were run the full denominator against a fixed probe and a scripted router,
so the answer is reproducible, and dropping it here would make every re-proposal of the
same dead route pay for the same reading again — which is the cost this module exists
to stop. A record filed before the member existed comes back `Stale` on `recall`'s
fourth rule and is measured once more, so nothing has to be migrated.

Ordered from the outside in like `kind_of`, and a frozenset rather than a predicate
so that a seventh `RejectionKind` has to be classified here rather than defaulting into
the memory.
"""


class NotAboutTheRoute(ValueError):
    """A decided proposal that says nothing about its route was offered to the memory.

    Raised rather than dropped. A store that ignored the write would leave the caller
    believing the decision was remembered, and the next run would pay to measure a
    route it thinks it has already recorded — which is the ticket's own defect with an
    extra layer of silence over it. Callers select with `worth_remembering` rather
    than catching this, on ADR-0031 point 3's reasoning about selection.
    """

    def __init__(self, promotion: Promotion, kind: RejectionKind) -> None:
        super().__init__(
            f"{promotion.proposal.case.id} came out {kind}, which is a fact about "
            f"the run rather than about the route — {kind.stated()}. The memory holds "
            "what the reference agents returned, and a run that did not measure them "
            "the way the bar needs has nothing to hand a later run"
        )


@dataclass(frozen=True)
class RouteKey:
    """What one proposed route is filed under: its family, and a digest of its probe.

    **A key and not a route, and the name says so** — CONTEXT.md's **route** is "the
    sequence of probes that worked", and this is neither a sequence nor a route. What
    it identifies is the one probe a `ProposedRoute` carries: `propose_case` drafts a
    case from the probe that actually ran, so the route an episode took reaches
    admission as a single payload, and it is that payload's identity within its
    family that two proposals of one path have in common.

    **Deliberately not the case.** `proposal.py` mints
    `id=f"adaptive-{family}-{uuid.uuid4().hex[:8]}"`, so a case id is a fresh value
    every time the attacker rediscovers the same path — a key nothing could ever hit
    twice, which is the fact that decides this shape.

    The digest is over the probe and is never the probe, for the reason CONTEXT.md
    gives under **route**: a path that beat a target is a working unpublished exploit
    (ADR-0008). It buys the same two things `Precedent.key` is content-addressed for
    — a re-proposal under a fresh case id lands on the same key, and the name the
    store lists derives from no clock and no target.

    The family is in the key and not only beside it. The same words sent under two
    families are two cases with two criteria, and one entry standing for both would
    answer a question about one of them with the other's counts.
    """

    family: AnyFamily
    """Which family the proposed route belongs to, in either tier.

    Widened with the record it is read off, and it is not a container the gate
    counts: the admission memory holds what a measurement was, and admission is
    decided per case (ADR-0032, ADR-0035). No elective family reaches it today —
    the adaptive layer's episodes are over the six — and the type does not have to
    know that to stay out of a denominator.
    """

    probe: str
    """A `sha256` of the probe that actually ran, truncated. Never the probe."""

    @classmethod
    def of(cls, case: Case) -> RouteKey:
        """The key one proposed case is filed under, read off the case record.

        Off `case.script` — the probe the episode actually sent, which
        `proposed_from` copies from the episode's own record rather than from the
        tool's argument — so nothing can be keyed by a payload the target never saw.

        Every turn of it, which for a proposed route is the one turn a probe is: a
        proposal is a single message the attacker composed, so the digest of the
        joined script is the digest of the probe and keys already filed still resolve
        (ADR-0053).
        """
        return cls(family=case.family, probe=_digest(case.script))

    @property
    def filed_under(self) -> str:
        """The key the store files this route under."""
        return f"{self.family}-{self.probe}"

    def stated(self) -> str:
        """The route as a report names it: the family, and the digest of the probe."""
        return f"{self.family}, probe sha256:{self.probe}"


@dataclass(frozen=True)
class Conditions:
    """What a measurement was taken under, so a later run can tell whether it is its.

    Not a fingerprint of everything that could conceivably differ, and not a version
    number somebody has to remember to raise. Three facts, and each is here because
    a run that differs in it would be reporting somebody else's measurement as its
    own:

    - **`models`** — the underlying models the three reference agents ran on. A
      cross-model bar met on `stub:obedient` and `stub:cooperative` is not met on two
      provider models: a gate run on a stub measures the field not at all (ADR-0022),
      and this is the field flag's argument applied to a remembered reading. It also
      covers the plainer case of a swap that moved its second model.
    - **`criterion`** — a digest of what a verdict *meant*: the success condition, the
      judged condition, the verdict class and the preconditions. The same probe under
      a different criterion is a different measurement, and `proposed_from` copies all
      four off whichever objective the episode was working on.
    - **`attempts`** — the denominator each count was read on. Recomputing a rate at
      one `n` under a rule that declares another is exactly what
      `GateRule.NOT_A_GATE_RESULT` exists to say aloud, and a memory that did it
      quietly would be worse than one that did not exist.

    **The thresholds are deliberately absent.** `discrimination_floor` and
    `interval_confidence` are applied *to* counts rather than baked into them, so a
    run under a moved threshold re-derives its own answer from the same counts and
    needs no invalidation — and the tripwire on `DecidedRoute.decided_as` is what
    catches the case where that re-derivation lands somewhere else.
    """

    models: tuple[str, ...]
    criterion: str
    attempts: int

    @classmethod
    def of(cls, case: Case, models: Sequence[str], rule: GateRule) -> Conditions:
        """The conditions a run measuring this case now would be measuring under."""
        return cls(
            models=tuple(models),
            criterion=criterion_of(case),
            attempts=rule.attempts_per_case,
        )

    def stored(self) -> dict[str, Any]:
        return {
            "models": list(self.models),
            "criterion": self.criterion,
            "attempts": self.attempts,
        }

    @classmethod
    def read(cls, value: dict[str, Any]) -> Conditions:
        return cls(
            models=tuple(str(model) for model in value["models"]),
            criterion=str(value["criterion"]),
            attempts=int(value["attempts"]),
        )

    def stated(self) -> str:
        return (
            f"measured on {', '.join(self.models)} at "
            f"{self.attempts} attempts per case per agent"
        )


@dataclass(frozen=True)
class DecidedRoute:
    """One route the admission gate has measured, as the memory holds it.

    Counts, prose, and the answer the measuring run reached — and nothing derived
    from the counts by arithmetic, because everything derived is re-derived on the
    way out. `decided_as` is the exception and it is not an answer: it is the
    tripwire `recall` compares its own re-derivation against.
    """

    route: RouteKey
    conditions: Conditions
    readings: tuple[AdmissionReading, ...]
    """What the case scored against the three reference agents, one reading per
    underlying model. The measurement, and the whole of what a later run reuses."""

    decided_as: RejectionKind
    """What the run that measured it concluded — the count ADR-0012 asks for.

    Stored so that a disagreement is detectable, and never read as the answer. A
    record whose counts no longer re-derive to this is a record the rule or the
    arithmetic moved under, and `recall` calls that `Stale` rather than choosing
    between the two.
    """

    description: str
    """What the attacker did, in the attacker's own words. Never payload text."""

    case_id: str
    """The id the route was first proposed under. Evidence, never the key.

    Kept so that a run answered from memory can say which earlier proposal the
    counts came from, and so that two proposals of one route are visibly one entry
    rather than one entry that lost the other's name.
    """

    decided_on: date

    def stored(self) -> dict[str, Any]:
        """The record as the store holds it: JSON, and nothing that names a target.

        No `payload`, no url, no endpoint hash and no target name. A route's probe
        is here as a digest inside the key and nowhere else, and the target a route
        was found against is not on the record at all — `Precedent` makes the same
        choice for the same reason, and what is never written cannot be redacted
        carelessly (ADR-0011).
        """
        return {
            "family": str(self.route.family),
            "probe": self.route.probe,
            "conditions": self.conditions.stored(),
            "readings": [entry.stored() for entry in self.readings],
            "decided_as": str(self.decided_as),
            "description": self.description,
            "case_id": self.case_id,
            "decided_on": self.decided_on.isoformat(),
        }

    @classmethod
    def read(cls, value: dict[str, Any]) -> DecidedRoute:
        """One record back out of the store."""
        return cls(
            route=RouteKey(family=Family(value["family"]), probe=str(value["probe"])),
            conditions=Conditions.read(value["conditions"]),
            readings=tuple(AdmissionReading.read(entry) for entry in value["readings"]),
            decided_as=RejectionKind(value["decided_as"]),
            description=str(value["description"]),
            case_id=str(value["case_id"]),
            decided_on=date.fromisoformat(str(value["decided_on"])),
        )

    def stated(self) -> str:
        """The lines a report prints for one remembered decision.

        The counts are not repeated here: they print through the re-derived
        `AdmissionOutcome`, which is the only place in the bench a reader is shown a
        `D` beside the counts it was computed from.
        """
        return "\n".join(
            (
                f"{self.route.stated()} — {self.decided_as}, "
                f"first decided {self.decided_on.isoformat()} as {self.case_id}",
                f"  {self.conditions.stated()}",
                f"  {self.description}",
            )
        )


@dataclass(frozen=True)
class Remembered:
    """One route this run did not have to measure, and the gate's answer about it.

    The `Promotion` is re-decided rather than replayed: `promote` runs over the
    remembered counts, with this run's proposal and this run's rule, so what a report
    prints is the current threshold's answer and carries the current run's case id.
    Every printer a measured promotion reaches — `Promotion.stated`,
    `rejections`, `CrossModelRejections.stated` — takes this one unchanged.
    """

    decided: DecidedRoute
    promotion: Promotion

    def stated(self) -> str:
        """The promotion's own lines, and the sentence that says nothing was spent.

        What the run did not spend is named by the bar the promotion printed
        immediately above it was decided under — `decide` puts `bar_for`'s answer on
        the outcome, so this line reads the mapping rather than restating it and
        cannot drift from the decision it annotates. A fixed pair of models here
        would be a second statement of a mapping that has had two answers since
        [ADR-0107](../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)
        (#228).

        The bar named is this run's, which is the one the sentence is about: the line
        annotates a promotion re-decided here and not the stored measurement, and
        `Conditions` deliberately holds no provenance.
        """
        return "\n".join(
            (
                self.promotion.stated(),
                f"  reported from memory — {self.decided.route.stated()} was "
                f"decided on {self.decided.decided_on.isoformat()} as "
                f"{self.decided.case_id}, and nothing was measured here to ask "
                f"whether it {self.promotion.outcome.bar.asks}",
                f"  {self.decided.conditions.stated()}",
            )
        )


@dataclass(frozen=True)
class Stale:
    """A record for this route that is not this run's measurement, so it is not used.

    A third answer beside a hit and a miss, and named rather than folded into the
    miss for the reason **not measurable** is a third outcome beside a rate and a
    refusal: a run that found a record and would not use it has learned something a
    reader should be told, and a memory that silently re-measured would hide the one
    event that says the invalidation rules are working.
    """

    decided: DecidedRoute
    why: str

    def stated(self) -> str:
        return "\n".join(
            (
                f"re-measuring {self.decided.route.stated()} — a record exists and "
                "is not this run's measurement",
                f"  {self.why}",
                f"  the record: {self.decided.conditions.stated()}, "
                f"{self.decided.decided_as}",
            )
        )


class DecisionDatabase(DatabaseStore):
    """The memory's own database, at the one git-ignored location.

    Its own file, on ADR-0029 decision 6. How the file is opened is
    `backend/bench/store.py`, and who owns the connection is ADR-0029 decision 2 with
    ADR-0032 for why this store reaches the same answer rather than ADR-0028's.

    Named rather than replaced by a path argument, because a field annotated with
    this type refuses an `InMemoryStore` before a test has to — ADR-0019 point 2's
    mechanism, and `DecidedRoutes.store` is where it bites here.
    """

    __slots__ = ()

    @classmethod
    def default_path(cls) -> Path:
        return DEFAULT_DECISION_PATH


@dataclass(frozen=True)
class DecidedRoutes:
    """The memory a run consults before it measures a proposed route.

    A thin reading of a `DatabaseStore`, so that the invalidation rules live in one
    place: `remember` is the only way in and it refuses a decision that is not about
    a route, `recall` is the only way out and it refuses a record that is not this
    run's measurement.

    Holds no connection, for ADR-0029 decision 2's reason: the file is the authority,
    every batch opens its own, and `DECIDED_ROUTES` below is a module-level object
    with no lifetime — exactly the global ADR-0028 refused to give a connection to.
    """

    store: DecisionDatabase
    """The database-backed store, annotated as one.

    Narrower than `BaseStore` on purpose, on `DurablePrecedents.store`'s reasoning:
    ADR-0019 point 2 says `InMemoryStore` may not be a durable store's backend, and a
    field typed `BaseStore` would accept one from any future caller with nothing to
    stop it.
    """

    namespace: tuple[str, ...] = DECISION_NAMESPACE

    @classmethod
    def at(cls, path: Path | None = None) -> DecidedRoutes:
        """The memory at that file, or at the configured one.

        A classmethod rather than a constructor argument, because a caller asking for
        the memory should not have to know that the thing behind it is a file.
        """
        return cls(store=DecisionDatabase(path))

    def remember(
        self,
        promotion: Promotion,
        *,
        models: Sequence[str],
        rule: GateRule = DECLARED_RULE,
        today: date | None = None,
    ) -> DecidedRoute:
        """File what the reference agents returned about one decided route.

        The counts, the conditions they were read under, the attacker's prose and the
        answer the run reached — and the answer is a tripwire rather than a cache, as
        the module docstring says.

        Idempotent by the key: a route already remembered is *replaced* rather than
        appended to. Replaced because the readings are one run's measurement on one
        pair of models, and a record that accumulated them across runs would hold a
        reading set matching no run's declared configuration.
        """
        kind = kind_of(promotion.outcome)
        if kind not in ABOUT_THE_ROUTE:
            raise NotAboutTheRoute(promotion, kind)
        case = promotion.proposal.case
        entry = DecidedRoute(
            route=RouteKey.of(case),
            conditions=Conditions.of(case, models, rule),
            readings=promotion.outcome.counts,
            decided_as=kind,
            description=promotion.proposal.description,
            case_id=case.id,
            decided_on=today or date.today(),
        )
        self.store.put(self.namespace, entry.route.filed_under, entry.stored())
        return entry

    def recall(
        self,
        proposal: ProposedRoute,
        *,
        models: Sequence[str],
        rule: GateRule = DECLARED_RULE,
    ) -> Remembered | Stale | None:
        """What the gate already measured about this route, if it is this run's.

        `None` where the route has never been decided. `Stale` where a record exists
        and one of the three conditions has moved, or where the current arithmetic no
        longer reaches the answer the measuring run reached — in which case the
        record is not repaired and not reconciled, because either would be this
        module choosing between two thresholds. `Remembered` otherwise, carrying a
        `Promotion` `promote` decided from the remembered counts.

        **The date `promote` is given is the date the counts were read**, not the
        date they were read back. `AdmissionRecord.admitted_on` is the day the three
        reference agents were run, so an admission answered from memory carries the
        measurement's date — and a route admitted from a reading taken a year ago
        says so on the record #40 would file rather than looking like this morning's
        work. There is no `today` argument here for that reason: a caller able to
        supply one could date a year-old measurement to today.
        """
        found = self.store.get(self.namespace, RouteKey.of(proposal.case).filed_under)
        if found is None:
            return None
        decided = DecidedRoute.read(dict(found.value))
        asked = Conditions.of(proposal.case, models, rule)
        if decided.conditions != asked:
            return Stale(decided, why=_conditions_moved(decided.conditions, asked))
        promotion = promote(proposal, decided.readings, rule, decided.decided_on)
        reached = kind_of(promotion.outcome)
        if reached is not decided.decided_as:
            return Stale(
                decided,
                why=(
                    f"the same counts now decide {reached} where the run that "
                    f"measured them recorded {decided.decided_as}. A declared "
                    "threshold or the admission arithmetic moved under this record, "
                    "and a route is measured again rather than reported under a "
                    "decision nothing here can vouch for"
                ),
            )
        return Remembered(decided=decided, promotion=promotion)


def worth_remembering(promotion: Promotion) -> bool:
    """Whether that decision says something about the route rather than about a run.

    A predicate for a caller to select with, so that the flow through
    `DecidedRoutes.remember` is a selection rather than a caught exception
    (ADR-0031 point 3). The store still refuses, so the selection cannot be skipped.
    """
    return kind_of(promotion.outcome) in ABOUT_THE_ROUTE


@dataclass(frozen=True)
class Consulted:
    """What the memory said about one proposal, whichever of the three it said."""

    proposal: ProposedRoute
    answer: Remembered | Stale | None

    @property
    def route(self) -> RouteKey:
        return RouteKey.of(self.proposal.case)

    @property
    def remembered(self) -> Remembered | None:
        """The answer where the memory had this run's measurement, else `None`."""
        return self.answer if isinstance(self.answer, Remembered) else None

    @property
    def stale(self) -> Stale | None:
        """The answer where a record exists and this run would not use it.

        Narrowed here rather than at the reader, so that a caller printing the two
        kinds of answer never has to assert which of the three it is holding —
        `Remembered | Stale | None` is one union and this is the pair of accessors
        that opens it.
        """
        return self.answer if isinstance(self.answer, Stale) else None


@dataclass(frozen=True)
class Consultation:
    """What one run's proposals cost after the memory answered what it could.

    The unit stays the **proposal** and never the route, because the proposal is what
    admission decides and the counts ADR-0012 asks for are counted on it
    (`CrossModelRejections`, and the reading `docs/validation.md` records for #15).
    So every proposal is here, whether it was measured or answered — and `to_measure`
    is a route at a time, because measuring one route twice in one run buys the same
    counts twice.
    """

    consulted: tuple[Consulted, ...]

    @property
    def remembered(self) -> tuple[Consulted, ...]:
        """The proposals the memory answered, in the order they were proposed."""
        return tuple(one for one in self.consulted if one.remembered is not None)

    @property
    def stale(self) -> tuple[Consulted, ...]:
        """The proposals that had a record this run would not use."""
        return tuple(one for one in self.consulted if one.stale is not None)

    @property
    def to_measure(self) -> tuple[ProposedRoute, ...]:
        """One proposal per route the memory could not answer, in proposal order.

        Deduplicated by route: `docs/validation.md` records one run proposing four
        cases "all describing the same route in prose", and measuring one route twice
        against the three reference agents buys the second answer nothing. The other
        proposals of that route are answered from the entry the measurement writes,
        which is the same path a second *run* takes.
        """
        seen: set[str] = set()
        first: list[ProposedRoute] = []
        for one in self.consulted:
            if one.remembered is not None or one.route.filed_under in seen:
                continue
            seen.add(one.route.filed_under)
            first.append(one.proposal)
        return tuple(first)

    def reported(self, promotions: Sequence[Promotion]) -> str:
        """Every promotion's own lines, with the remembered ones saying they are.

        Where a run reports its promotions, and the answer to "report the remembered
        decisions where promotions are already reported". `Promotion.stated` prints
        *promoted* or *discarded* and says nothing about whether the counts behind it
        were bought here — so a reader of that list could not tell a decision this
        run paid for from one it read, which is the one thing this memory could cost
        the report.

        Paired positionally with `consulted`, because `cross_model_bar` builds the
        two from one list of proposals in one pass. A length mismatch is somebody
        having filtered one of them, which would silently label the wrong promotions,
        so `zip` is strict and the error says so.
        """
        if len(promotions) != len(self.consulted):
            raise ValueError(
                f"{len(promotions)} promotion(s) against {len(self.consulted)} "
                "consulted proposal(s). These two are one list of proposals read "
                "twice, and a pairing that has lost an element would report a "
                "measured decision as a remembered one"
            )
        return "\n".join(
            one.remembered.stated()
            if one.remembered is not None
            else promotion.stated()
            for one, promotion in zip(self.consulted, promotions, strict=True)
        )

    def stated(self) -> str:
        """What the memory saved this run, and what it declined to answer.

        Printed beside the promotions rather than instead of them, because the
        counts a report carries now include counts no run in front of the reader
        measured — so how many of them came from memory has to be on the page.
        """
        lines = [
            "the admission memory — what the gate already measured, re-decided here "
            "and never replayed (ADR-0032)",
            f"  {len(self.consulted)} proposal(s) put to the bar, "
            f"{len(self.remembered)} answered from memory, "
            f"{len(self.to_measure)} route(s) to measure",
            # Counted apart from the routes never seen before, on `RejectionKind`'s
            # own reasoning about why the four refusals are counted separately: a
            # route re-measured because a record stopped applying is the event that
            # says the invalidation rules are working, and one number over both
            # would report it as a route nobody had ever proposed.
            f"  {len(self.stale)} of those route(s) had a record this run will not use",
        ]
        lines.extend(
            f"  {line}"
            for one in self.consulted
            if one.remembered is not None
            for line in one.remembered.stated().splitlines()
        )
        lines.extend(
            f"  {line}"
            for one in self.consulted
            if one.stale is not None
            for line in one.stale.stated().splitlines()
        )
        return "\n".join(lines)


def consult(
    memory: DecidedRoutes,
    proposals: Iterable[ProposedRoute],
    *,
    models: Sequence[str],
    rule: GateRule = DECLARED_RULE,
) -> Consultation:
    """Ask the memory about every proposal, before anything is measured.

    The consultation happens ahead of the admission run rather than after it, which
    is the whole of what this ticket saves: a route already decided under this run's
    conditions is reported from memory and the three agents are never called for it.
    """
    return Consultation(
        consulted=tuple(
            Consulted(
                proposal=proposal,
                answer=memory.recall(proposal, models=models, rule=rule),
            )
            for proposal in proposals
        )
    )


DECIDED_ROUTES = DecidedRoutes.at()
"""The memory a run reads: the file, at the one location, declared once.

The default of `cross_model_bar`, so that the entry point reads the real memory
without being handed one. Shared rather than constructed per run, and safe to share
because `DecisionDatabase` holds no state — not even a connection: the file is the
authority and every batch opens its own (ADR-0029 decision 2, and ADR-0032 for why
this store reaches the same answer). A caller that wants a different location says
so, which is what every test does.
"""


def _digest(text: str) -> str:
    """A truncated `sha256`, on `Precedent.key`'s terms and at its length."""
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def criterion_of(case: Case) -> str:
    """A digest of what a verdict on this case *means*, and of what it needs to run.

    Four fields and not the whole record. `id` cannot be in it — it is a fresh uuid
    per proposal, which is the fact that made the route the key — and `added_on`,
    `trigger`, `status`, `external_id` and `discovered_by` do not change what the
    three reference agents would return. `payload` is not in it either, because it is
    already the key. What is left is the success condition, the judged condition, the
    verdict class and the preconditions: change any of them and the counts on the
    record were read under a different question.

    Written out rather than digested off `dataclasses.asdict`, because a digest that
    covered every field would be invalidated by the case id it must not read.

    Public because it has a second caller across a module boundary:
    `pending.PendingRoutes.file` stores this digest beside the case draft, since it
    is the one thing about what a verdict meant that outlives the payload a
    decision removes (ADR-0104 §4).
    """
    condition = case.success_condition
    judged = case.judged_condition
    return _digest(
        json.dumps(
            {
                "success_condition": (
                    None
                    if condition is None
                    else {
                        "kind": str(condition.kind),
                        "planted_canary": condition.planted_canary,
                    }
                ),
                "judged_condition": (
                    None
                    if judged is None
                    else {
                        "question": judged.question,
                        "succeeded_when": judged.succeeded_when,
                        "resisted_when": judged.resisted_when,
                    }
                ),
                "verdict_class": str(case.verdict_class),
                "requires": sorted(str(need) for need in case.requires),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _conditions_moved(recorded: Conditions, asked: Conditions) -> str:
    """Which of the three conditions moved, in the words a report prints.

    Each named separately rather than reported as "the conditions differ", because
    the three say different things to an operator: a model changed is a different
    instrument, a criterion changed is a different question, and a denominator
    changed is a figure ADR-0003 will not compare (`GateRule.NOT_A_GATE_RESULT`).
    """
    if recorded.models != asked.models:
        return (
            f"the counts were read on {', '.join(recorded.models)} and this run "
            f"measures on {', '.join(asked.models)}. A reading is a reading *on a "
            "model*, and one taken on a stub measures the field not at all "
            "(ADR-0022)"
        )
    if recorded.criterion != asked.criterion:
        return (
            "the same probe is proposed under a different criterion — the success "
            "condition, the judged condition, the verdict class or the "
            "preconditions moved — so the remembered counts were read under a "
            "different question"
        )
    return (
        f"the counts were read at {recorded.attempts} attempts per case and the "
        f"rule this run applies declares {asked.attempts}. A rate at one "
        "denominator is not a rate at another (ADR-0003)"
    )
