"""What worked against similar targets, held in a file so it outlives the process.

Two consumers read this store and they read it for different reasons.
`suggest_remediation` reads it because a fix informed only by the transcript in
front of it is the fix it would have written with no store at all, and
`retrieve_precedent` — one of the attacker's five tools — reads it because an
attacker starting from nothing rediscovers the same route every run. Nothing else
reads it, and two things are forbidden from being able to.

**It survives a restart, and that is the whole of the claim.** PLAN §10 answers the
long-term-memory requirement with this store while answering short-term memory with
the run state, so a per-process store would be the same lifetime twice under two
names: `InMemoryStore` would satisfy every word of the table row and none of its
meaning. So the store a run uses is `PrecedentDatabase`, whose authority is a
SQLite file, and `RecordedPrecedents` below is a test double (ADR-0019, ADR-0029).
*How* that file is opened — the pragma, the schema under a write lock, a read that
does not create it, and the two measured functions ADR-0029's decision about the
connection cost — is `backend/bench/store.py`, shared with the second durable store
since ADR-0032 and precedent's business in neither direction.

**The namespace is single-tenant, and there is no tenant segment in it.**
`PRECEDENT_NAMESPACE` is two elements long and neither of them identifies a user,
because this bench has one tenant and pretending otherwise would put an isolation
boundary in the code that nothing enforces. Cross-tenant retrieval is a named P1
blocker before user two (PLAN §11), and this is the place a reader can see that it
is absent rather than assumed.

**Only deterministic findings enter it.** `Precedent.of` refuses a judged finding,
because a judged verdict carries a reliability figure and a wider stated limit
(ADR-0004) and precedent that quietly mixed the two would hand remediation advice
derived from a number the bench qualifies as if it were one the bench stands
behind. The refusal reads `Finding.verdict_class`, which is copied off the attempt,
so it cannot be inferred wrongly from a family name.

**Nothing here reaches the judge or the adjudicator.** ADR-0004 requires precedent
to feed `suggest_remediation` only and never `assess_finding`; ADR-0013 says the
same of `adjudicate` and says it harder, because `adjudicate` is the instrument κ is
measured on. Neither prohibition is new — the enforcement is, and it is
`backend/tests/test_precedent.py`, which walks the *transitive* imports of both
modules rather than their first line.

**No target identity is written here.** A precedent records what failed and the fix
written for it, and never which endpoint failed: the store's contents accumulate
across runs, so with enough of them an attacker could recognise a target by its
failure pattern even after `retrieve_precedent` has redacted the names it can see
(ADR-0011). What is never written cannot be redacted carelessly. The file is also
git-ignored, because a finding is about someone else's agent (ADR-0008).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from backend.bench.judge import Finding
from backend.bench.library import Family, VerdictClass
from backend.bench.store import DatabaseStore

PRECEDENT_NAMESPACE = ("agentaudit", "precedent")
"""Where a precedent is filed, and it says single-tenant by having no tenant in it.

Two fixed elements and no third. A namespace of `("agentaudit", "precedent",
tenant)` would look like isolation and enforce none, since one file holds every
entry and nothing checks the segment on the way out. Cross-tenant anonymised
retrieval is a Sprint 4 row in PLAN §11 and a blocker before user two; until it
exists, the honest shape is a namespace a reader can see has no tenant in it.
"""

PRECEDENT_DIRECTORY = Path(__file__).resolve().parents[3] / "precedent"
"""The directory the store lives in, and `.gitignore` ignores it as a directory.

A directory rather than a file name, so the ignore rule covers everything written
beside the database — SQLite's own `-wal` and `-shm` sidecars, a backup, an export,
an editor's swap file. None of them may become the first finding about a real target
this repository carries (ADR-0008).
"""

DEFAULT_STORE_PATH = PRECEDENT_DIRECTORY / "findings.sqlite"
"""Where the store's database is, at the top of the repository and ignored by git.

One location and no environment override. A configurable path is a path that can
be configured into a tracked directory, and the acceptance criterion here is that
no finding about anybody's agent is ever committed — which is a property of *the*
location or of none (ADR-0008). A test asks git whether this path is ignored, and
asks it of the sidecars too.
"""

LEGACY_STORE_PATH = PRECEDENT_DIRECTORY / "findings.json"
"""The document the store used to be, kept as a name so the drop can be said aloud.

Nothing reads it. A clone that has one holds four hand-typed seeds and no recorded
finding — the store was machine-local and git-ignored, so there was nothing else it
could hold — and re-seeding is one command against the new backend. Named rather
than migrated so that `seed_precedent.py` can tell an operator whose seeds have
stopped being read that they have, which is the one way this decision could
otherwise look like an oversight (ADR-0029).
"""

RETRIEVAL_LIMIT = 20
"""How many precedents one family's lookup returns, most recent first.

A stated ceiling rather than the store interface's default of ten, and small
enough that what comes back fits in the one prompt that reads it. Recency is the
ordering because it is the only one the store can compute without a model: nothing
here scores relevance, and a lookup that claimed to would be claiming a ranking
nobody could re-derive.
"""


class JudgedPrecedent(ValueError):
    """A judged finding was offered to the precedent store.

    Named rather than silently dropped. A store that ignored the write would leave
    the caller believing the finding was recorded, and the thing ADR-0004 forbids
    is precedent that carries a judgement whose reliability is unstated — which is
    exactly what a silent partial write produces.
    """

    def __init__(self, finding: Finding) -> None:
        super().__init__(
            f"{finding.case_id} reached a {finding.verdict_class} verdict, and the "
            "precedent store holds deterministic findings only. A judged verdict "
            "carries a reliability figure and a wider stated limit (ADR-0004), and "
            "remediation informed by one would inherit neither"
        )


@dataclass(frozen=True)
class Precedent:
    """One deterministic finding, kept so the next run's fix is not reinvented.

    Prose and never payload text, for the reason CONTEXT.md gives under **route**:
    a path that beat a target is a working unpublished exploit, and the disclosure
    posture withholds exactly that (ADR-0008). It is deliberately not *called* a
    route either — a route is the sequence of probes one episode took, and what is
    filed here is a scored deterministic finding, which took no probes at all.

    There is no target on this record and that is the decision, not an omission.
    `retrieve_precedent` redacts the identities it can see, and redaction is a
    defence against carelessness in one lookup rather than against a corpus:
    accumulate enough entries and a failure pattern identifies a target on its own
    (ADR-0011). The `case_id` and the external identifier are the *instrument's*
    identity, which is public and versioned by a digest, so they are safe to keep
    and are what makes a lookup more than a bag of sentences.
    """

    family: Family
    failure: str
    """What the target did, in one sentence of prose. `Narrative.reason`."""

    remediation: str
    """The fix that was written for it, prose. Read by `suggest_remediation` and
    never returned to the attacker, which is shown `failure` alone."""

    case_id: str
    external_id: str
    """The published identifier the case tests one case within, as a string.

    The identifier alone rather than the `ExternalId` the case record carries: the
    other half of that type is the coverage boundary, which is a claim about the
    *instrument* and belongs in the report rather than in a lookup about a fix.
    """

    @classmethod
    def of(cls, finding: Finding) -> Precedent:
        """One finding as precedent, or a refusal if its verdict was judged."""
        if finding.verdict_class is not VerdictClass.DETERMINISTIC:
            raise JudgedPrecedent(finding)
        return cls(
            family=finding.family,
            failure=finding.narrative.reason,
            remediation=finding.narrative.remediation,
            case_id=finding.case_id,
            external_id=finding.narrative.external_id.identifier,
        )

    def stored(self) -> dict[str, Any]:
        """The record as the store holds it: JSON, and nothing that names a target."""
        return {
            "family": str(self.family),
            "failure": self.failure,
            "remediation": self.remediation,
            "case_id": self.case_id,
            "external_id": self.external_id,
        }

    @classmethod
    def read(cls, value: dict[str, Any]) -> Precedent:
        """One record back out of the store."""
        return cls(
            family=Family(value["family"]),
            failure=str(value["failure"]),
            remediation=str(value["remediation"]),
            case_id=str(value["case_id"]),
            external_id=str(value["external_id"]),
        )

    @property
    def key(self) -> str:
        """The key this record is filed under: a digest of the record itself.

        Content-addressed rather than counted or timestamped, which buys two
        things. Writing the same finding twice is idempotent, so a re-run does not
        multiply one finding into a corpus of copies; and the key derives from no
        clock and no target, so nothing about *when* or *against whom* leaks into
        a name the store lists.
        """
        canonical = json.dumps(self.stored(), sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()[:16]


class PrecedentStore(Protocol):
    """What a reader of precedent needs, and nothing a writer needs.

    One method, and the writing side deliberately absent from it. `record` lives on
    `DurablePrecedents` as a concrete method because the two consumers — the
    attacker's tool and `suggest_remediation` — only ever read: a protocol that
    also promised a write would make every read-only stand-in refuse half of what
    it claimed to be, which is a type saying less than it appears to.
    """

    def for_family(self, family: Family) -> Sequence[Precedent]:
        """The findings recorded against this family, most recently filed first."""
        ...


class PrecedentDatabase(DatabaseStore):
    """The precedent store's own database, at the one git-ignored location.

    A subclass of `backend/bench/store.py`'s `DatabaseStore` and nothing more: the
    location is the whole of what is precedent-specific about it, and how the file is
    opened — the pragma, the schema under a write lock, a read that does not create
    it — belongs to neither of the two things kept in these files (ADR-0029 decision
    6, ADR-0032).

    Named rather than replaced by a path argument, because a field annotated with
    this type refuses an `InMemoryStore` before a test has to — ADR-0019 point 2's
    mechanism, and `DurablePrecedents.store` is where it bites.

    The store this replaced was 150 lines of document rewriting whose defect was that
    every write was a whole-file rewrite (#36, ADR-0029).
    """

    __slots__ = ()

    @classmethod
    def default_path(cls) -> Path:
        return DEFAULT_STORE_PATH


@dataclass(frozen=True)
class DurablePrecedents:
    """The precedent store a run uses: deterministic findings, in a database.

    A thin reading of a `BaseStore` rather than a store of its own, so the two
    prohibitions live in one place. `record` is the only way in and it goes
    through `Precedent.of`, which refuses a judged finding; `for_family` is the
    only way out and it returns the filed prose.
    """

    store: PrecedentDatabase
    """The database-backed store, annotated as one.

    Narrower than `BaseStore` on purpose. ADR-0019 point 2 says `InMemoryStore` may
    not be the production backend, and a field typed `BaseStore` would accept one
    from any future caller with nothing to stop it — so the prohibition is carried
    by the annotation and mypy refuses the substitution before a test has to.
    """

    namespace: tuple[str, ...] = PRECEDENT_NAMESPACE

    @classmethod
    def at(cls, path: Path | None = None) -> DurablePrecedents:
        """The store at that file, or at the configured one.

        A classmethod rather than a constructor argument on the dataclass,
        because a caller asking for the store should not have to know that the
        thing behind it is a file.
        """
        return cls(store=PrecedentDatabase(path))

    def record(self, finding: Finding) -> Precedent:
        """File one deterministic finding, and refuse a judged one."""
        entry = Precedent.of(finding)
        self.store.put(self.namespace, entry.key, entry.stored())
        return entry

    def for_family(self, family: Family) -> Sequence[Precedent]:
        found = self.store.search(
            self.namespace, filter={"family": str(family)}, limit=RETRIEVAL_LIMIT
        )
        return tuple(Precedent.read(item.value) for item in found)


@dataclass(frozen=True)
class RecordedPrecedents:
    """A store held in memory. Test equipment, and never the store a run uses.

    ADR-0019 point 2 in as many words: an in-memory store is the right thing for a
    unit test and may not be the production backend, because a long-term memory
    that dies with the process makes the claim false. It stays here because a
    fixture that has to write a file to hand the attacker two sentences is a
    fixture that tests the filesystem.
    """

    entries: tuple[Precedent, ...] = ()

    def for_family(self, family: Family) -> Sequence[Precedent]:
        return tuple(entry for entry in self.entries if entry.family is family)


DURABLE_PRECEDENT = DurablePrecedents.at()
"""The store a run reads: the file, at the one location, declared once.

The default of `run_calibration`, of `run_adaptive_layer` and of `run_episode`, so
that a run reads the real store without being handed one — which is the whole of
what phase 6a's second half changes, since `retrieve_precedent` had the store's
interface from #16 and an empty stand-in behind it.

Shared rather than constructed per run, and safe to share because
`PrecedentDatabase` holds no state — not even a connection: the file is the
authority and every batch opens its own, so two callers against this object cannot
disagree any more than two objects against the file could (ADR-0029). A run that
wants a different location says so, which is what every test does and what a second
tenant would need long before it needed a constructor argument (PLAN §11).

**A gate run reads it too, and nothing it decides can move.** The file is
machine-local and git-ignored, so an instrument that read it into a scored figure
would be an instrument whose result depended on the machine — but the only consumer
is one adaptive tool, and ADR-0010 keeps that layer out of every rate, interval,
band and `D` the gate is decided on. What precedent can reach is the adaptive
section, which already declares itself recorded and not reproducible (ADR-0017).
The hazard the ignored file would otherwise carry is closed by the layer separation
rather than by remembering to pass an empty store to the gate.
"""

NO_PRECEDENT = RecordedPrecedents()
"""An empty store, for a caller that must read nothing. Test equipment.

Empty rather than absent, so `retrieve_precedent` is a tool that answers rather
than a tool that is missing: an attacker that spent a turn discovering nothing has
been filed against this family has learned something true. That answer is now also
what the durable store gives on a fresh install, which is the case a run against an
empty file has to survive rather than fail.
"""
