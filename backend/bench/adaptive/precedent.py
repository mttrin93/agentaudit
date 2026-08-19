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
meaning. So the store a run uses is `JsonFileStore`, whose authority is a file, and
`RecordedPrecedents` below is a test double (ADR-0019).

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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)

from backend.bench.judge import Finding
from backend.bench.library import Family, VerdictClass

PRECEDENT_NAMESPACE = ("agentaudit", "precedent")
"""Where a precedent is filed, and it says single-tenant by having no tenant in it.

Two fixed elements and no third. A namespace of `("agentaudit", "precedent",
tenant)` would look like isolation and enforce none, since one file holds every
entry and nothing checks the segment on the way out. Cross-tenant anonymised
retrieval is a Sprint 4 row in PLAN §11 and a blocker before user two; until it
exists, the honest shape is a namespace a reader can see has no tenant in it.
"""

DEFAULT_STORE_PATH = Path(__file__).resolve().parents[3] / "precedent" / "findings.json"
"""Where the store's file is, at the top of the repository and ignored by git.

One location and no environment override. A configurable path is a path that can
be configured into a tracked directory, and the acceptance criterion here is that
no finding about anybody's agent is ever committed — which is a property of *the*
location or of none (ADR-0008). A test asks git whether this path is ignored.

Its own directory so the ignore rule covers a directory rather than a file name: a
second file written beside this one — a backup, an export, an editor's swap — must
not become the first finding about a real target this repository carries.
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


class NoFilterOperators(NotImplementedError):
    """A comparison filter was asked of a store that compares for equality only.

    Named for the reason `NoVectorIndex` is: a comparison a caller believes ran and
    did not is a silently wrong answer, and this store's one filter is the family.
    """


class NoVectorIndex(NotImplementedError):
    """A natural-language search was asked of a store that has no index.

    Refused rather than answered with an unranked list. `BaseStore.search` takes a
    `query` whose support "depends on your store implementation", and a store that
    returned everything in recency order for a semantic query would be answering a
    question it did not understand.
    """


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


class JsonFileStore(BaseStore):
    """A `BaseStore` whose authority is a JSON file, re-read on every batch.

    The file is the state and this object holds none: every `batch` loads it,
    applies the operations and writes it back, so two store objects against one
    path cannot disagree and a process that dies mid-run loses nothing that was
    written before it. That is a slow design and a correct one at this size — a
    single tenant's findings, read once per family per run.

    A dependency was the alternative. `langgraph.checkpoint.sqlite` is not
    installed, and a schema plus a lifecycle for one tenant's findings is out of
    proportion until cross-tenant isolation arrives and brings a real query
    surface with it (ADR-0019, considered options). The claim rests on the
    interface and the lifetime rather than on the backend's brand.

    Two operations are refused rather than approximated: a semantic `query`, which
    would need an index this store has no dependency for, and a filter operator
    (`{"$gt": ...}`), which would let a caller believe a comparison ran that did
    not. Everything a precedent lookup needs — a namespace prefix and an equality
    filter on the family — is supported.
    """

    __slots__ = ("path",)

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else DEFAULT_STORE_PATH

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        held = self._read()
        results: list[Result] = []
        wrote = False
        for op in ops:
            if isinstance(op, GetOp):
                results.append(_found(held, op.namespace, op.key))
            elif isinstance(op, SearchOp):
                results.append(_searched(held, op))
            elif isinstance(op, PutOp):
                held = _applied(held, op)
                wrote = True
                results.append(None)
            else:
                raise NotImplementedError(
                    f"{type(op).__name__} is not supported. This store holds one "
                    "namespace, so enumerating them answers a question nobody "
                    "asked, and a paginated wildcard matcher over a single "
                    "namespace is machinery with no caller"
                )
        if wrote:
            self._write(held)
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """The same file, applied on the same thread.

        No async file layer, deliberately: an implementation that awaited nothing
        while claiming to be asynchronous would be a lie in a signature. The graph
        is free to await this; what it awaits is one small synchronous read.
        """
        return self.batch(list(ops))

    def _read(self) -> list[Item]:
        if not self.path.exists():
            return []
        records: Any = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            Item(
                value=record["value"],
                key=record["key"],
                namespace=tuple(record["namespace"]),
                created_at=record["created_at"],
                updated_at=record["updated_at"],
            )
            for record in records
        ]

    def _write(self, held: Sequence[Item]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([item.dict() for item in held], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _found(held: Sequence[Item], namespace: tuple[str, ...], key: str) -> Item | None:
    for item in held:
        if item.namespace == namespace and item.key == key:
            return item
    return None


def _applied(held: Sequence[Item], op: PutOp) -> list[Item]:
    """The store's contents with one put or one delete applied."""
    kept = [
        item
        for item in held
        if not (item.namespace == op.namespace and item.key == op.key)
    ]
    if op.value is None:
        return kept
    existing = _found(held, op.namespace, op.key)
    now = datetime.now(UTC)
    return [
        *kept,
        Item(
            value=op.value,
            key=op.key,
            namespace=op.namespace,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        ),
    ]


def _searched(held: Sequence[Item], op: SearchOp) -> list[SearchItem]:
    if op.query is not None:
        raise NoVectorIndex(
            f"{op.query!r} is a natural-language query and this store has no "
            "index. A precedent lookup filters on the family and orders by "
            "recency; it does not rank by meaning"
        )
    matched = [
        item
        for item in held
        if item.namespace[: len(op.namespace_prefix)] == op.namespace_prefix
        and _passes(item.value, op.filter)
    ]
    matched.sort(key=lambda item: (item.updated_at, item.key), reverse=True)
    window = matched[op.offset : op.offset + op.limit]
    return [
        SearchItem(
            namespace=item.namespace,
            key=item.key,
            value=item.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in window
    ]


def _passes(value: dict[str, Any], wanted: dict[str, Any] | None) -> bool:
    if not wanted:
        return True
    for field, expected in wanted.items():
        if isinstance(expected, dict):
            raise NoFilterOperators(
                f"{field}={expected!r} is an operator filter and this store "
                "compares for equality only. A comparison a caller believes ran "
                "and did not is worse than a refusal"
            )
        if value.get(field) != expected:
            return False
    return True


@dataclass(frozen=True)
class DurablePrecedents:
    """The precedent store a run uses: deterministic findings, in a file.

    A thin reading of a `BaseStore` rather than a store of its own, so the two
    prohibitions live in one place. `record` is the only way in and it goes
    through `Precedent.of`, which refuses a judged finding; `for_family` is the
    only way out and it returns the filed prose.
    """

    store: JsonFileStore
    """The file-backed store, annotated as one.

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
        return cls(store=JsonFileStore(path))

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


NO_PRECEDENT = RecordedPrecedents()
"""An empty store, for a run that is not given one.

Empty rather than absent, so `retrieve_precedent` is a tool that answers rather
than a tool that is missing: an attacker that spent a turn discovering nothing has
been filed against this family has learned something true.
"""
