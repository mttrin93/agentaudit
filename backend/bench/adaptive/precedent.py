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
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from langgraph.store.base import (
    BaseStore,
    GetOp,
    ListNamespacesOp,
    Op,
    Result,
    SearchOp,
)
from langgraph.store.sqlite import SqliteStore

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

WRITE_WAIT_SECONDS = 15.0
"""Seconds a connection waits for another to finish writing before giving up.

Stated rather than inherited, because two of the arguments below rest on it: a
second writer *waits* on SQLite's busy handler rather than failing, and `_migrated`
lets the loser of a schema race wait and then find nothing to do. Both are claims
about this number, and Python's implicit five seconds is not a number anybody here
chose.

Fifteen because the thing being waited out is one small transaction against a local
file — one insert, or five DDL statements on a cold database — so a wait this long
means something is wrong rather than busy, and a run should hear about it. It is not
a limit on how long a batch takes; it is how long one contends.
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


class NoVectorIndex(NotImplementedError):
    """A natural-language search was asked of a store with no embedding model.

    Refused rather than answered with an unranked list, and the refusal is now
    load-bearing in a way it was not while the backend was a document. `SqliteStore`
    *can* rank by meaning — it takes an `index` config and reaches `sqlite-vec` —
    but only against an embedding model, and with none configured its search drops
    the `query` and returns the same recency-ordered rows a query-less search would
    (`_prepare_batch_search_queries` takes the vector branch on `op.query and
    self.index_config`). So the delegate answers a semantic question with a list it
    did not rank, which is exactly the silently wrong answer this name exists to
    turn into a stack trace.

    Configuring that index is the alternative, and ADR-0029 records why it lost. The
    refusal that used to sit beside this one, `NoFilterOperators`, is gone for the
    mirror-image reason recorded there.
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


class PrecedentDatabase(BaseStore):
    """A `BaseStore` whose authority is a SQLite file, opened for one batch.

    The rows, the SQL and the migration statements are
    `langgraph.store.sqlite.SqliteStore`'s, from the package the approval
    checkpointer already depends on. What is left here is where the database is, what
    pragma it is opened under, *when* the schema is applied, and one refusal — and
    the store this replaced was 150 lines of document rewriting whose defect was that
    every write was a whole-file rewrite (#36, ADR-0029).

    **The file is the state and this object holds none — not even a connection.**
    Every batch opens one, applies the operations and closes it, so two store
    objects against one path cannot disagree and `DURABLE_PRECEDENT` stays a
    module-level object with no open handle in it. That is the *opposite* of the
    answer ADR-0028 reached one file over, where the connection belongs to the
    `ApprovalRun`; ADR-0029 records why the two differ, and the short version is
    that a halt is answered by a thread that did not open it and a precedent lookup
    is not.

    A semantic `query` is refused rather than approximated (`NoVectorIndex`), and
    refused before a connection is opened, so a refused search leaves no database
    behind. An operator filter is not refused any more: SQLite runs the comparison,
    which was the whole of the old refusal's argument.

    **Reading a store nothing has written answers without creating one.** Opening a
    database runs the schema, so a lookup would otherwise leave a file where there
    was none — and *reading precedent is not an event in the store's history*. That
    claim is older than this backend and `test_adaptive_attacker.py` has always
    asserted it: a corpus that recorded who looked would be a record of lookups
    rather than of what failed.
    """

    __slots__ = ("path",)

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else DEFAULT_STORE_PATH

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        asked = list(ops)
        for op in asked:
            if isinstance(op, SearchOp) and op.query is not None:
                raise NoVectorIndex(
                    f"{op.query!r} is a natural-language query and this store has "
                    "no embedding model. A precedent lookup filters on the family "
                    "and orders by recency; it does not rank by meaning, and the "
                    "backend would answer this with a list it had not ranked"
                )
        if _reads_only(asked) and not self.path.exists():
            return [None if isinstance(op, GetOp) else [] for op in asked]
        with self._opened() as store:
            return store.batch(asked)

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """The same database, on the same thread.

        Still no async layer, and the reason has changed shape rather than gone
        away: an implementation that awaited nothing while claiming to be
        asynchronous would be a lie in a signature, and the package this delegates
        to now ships an `AsyncSqliteStore` that would make the signature true. It
        would also introduce an event loop to hold a precedent lookup, which is the
        second concurrency model ADR-0028 declined to add for the checkpoint and
        declines again here. The graph is free to await this; what it awaits is one
        small synchronous batch against a local file.
        """
        return self.batch(list(ops))

    @contextmanager
    def _opened(self) -> Iterator[SqliteStore]:
        """This batch's connection, closed with the batch that opened it.

        `isolation_level=None` because `SqliteStore` issues its own `BEGIN` and
        `COMMIT` around every cursor it opens, and Python's implicit transaction
        handling would be a second transaction manager over the same connection —
        the same choice `SqliteStore.from_conn_string` makes, which is not used here
        only because it cannot be told where to put the file's parent directory.

        `check_same_thread` is left at its default, which is where ADR-0028's
        checkpointer could not leave it: this connection is opened, used and closed
        inside one call, so the stricter setting is free and would catch a future
        caller that tried to hold one open across threads.

        WAL, and it outlives the connection because the journal mode is written into
        the file's header. Two bench runs are two OS threads (`api/runs.py`), so two
        findings can be filed at once, and one reader should not block behind
        another's write.

        **`_enable_wal` and `_migrated` are what make a connection per batch safe**,
        and neither is here for tidiness: `SqliteStore` is written to be one
        long-lived object, and ADR-0029 records which two of its behaviours are unsafe
        when it is not, what each of these answers, and what it measured. With both
        removed, six threads against one cold database failed 14 runs in 20 — a
        figure the ADR qualifies, because contention depends on the machine.

        `SqliteStore.setup()` still runs on the delegate's own first use and finds the
        version already current, which is what makes leaving it alone safe — and is
        why `_migrated` has to *apply* the schema rather than check it.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path, isolation_level=None, timeout=WRITE_WAIT_SECONDS
        )
        try:
            _enable_wal(connection)
            _migrated(connection)
            yield SqliteStore(connection)
        finally:
            connection.close()


def _reads_only(ops: Sequence[Op]) -> bool:
    """Whether that batch would write nothing, so an absent database can stay absent.

    Named against the three read operations rather than against `PutOp`, because the
    shortcut has to answer for every op in the batch and a `BaseStore` op this store
    has never seen must fall through to the delegate rather than be assumed harmless.
    """
    return all(isinstance(op, GetOp | SearchOp | ListNamespacesOp) for op in ops)


SCHEMA: Sequence[str] = SqliteStore.MIGRATIONS
"""The delegate's schema, so that this module decides *when* it is applied.

Read off `SqliteStore.MIGRATIONS` rather than copied out, because *what* the schema
is stays the delegate's business and only the locking is ours. Why the locking has
to be ours — `setup()` reads the applied version and then inserts it with no
transaction around the pair — is ADR-0029's, along with the measurement that
licensed taking it over: with the delegate applying its own schema, six threads
against one cold database failed 5 runs in 12 and eight processes lost 26 batches. The
ADR qualifies those counts; what they support is *fails often*, not a rate.
"""


_CONTENDED = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})
"""The two error codes that mean *another connection has it*, and nothing else does."""


def _enable_wal(connection: sqlite3.Connection) -> None:
    """Put that database in WAL, and never fail a batch over the journal mode.

    Asked before told, because the mode is written into the file's header: it
    outlives the connection, so only the first open of a new database has anything
    to do, and setting a mode a database is already in is a write attempt for no
    reason at all.

    The failure swallowed here is the one pragma the busy timeout does not cover.
    Changing the journal mode needs an exclusive lock, it cannot be taken inside a
    transaction, and SQLite returns `SQLITE_BUSY` for it **without** consulting the
    busy handler — so several processes opening a database that does not exist yet
    will collide, and it is the only thing left that did (measured: eight processes
    released from a barrier onto a cold database, ADR-0029).

    Losing that race costs nothing and failing on it costs a run. The mode is a
    property of the *file*, so whichever connection wins sets it for every connection
    after, and a loser that carried on has a database another process just put in WAL.
    Enabling it is an optimisation; refusing to file a finding because an optimisation
    was already being applied is not a trade this store makes.

    Swallowed on the error *code* and not on the exception type, so that the one
    contention this tolerates cannot stand in for a database that will not open at
    all: anything but a lock is re-raised here rather than carried into `_migrated`,
    which would report it from a stranger place.
    """
    [mode] = connection.execute("PRAGMA journal_mode").fetchone()
    if str(mode).lower() == "wal":
        return
    try:
        connection.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError as contended:
        if contended.sqlite_errorcode not in _CONTENDED:
            raise


def _migrated(connection: sqlite3.Connection) -> None:
    """Bring that connection's database up to `SCHEMA`, once and under a write lock.

    Checked twice, and the first check is why every read is not a writer: the common
    case is a database already at the current version, which costs two `SELECT`s
    against `sqlite_master` and the migration table and takes no lock at all. Only a
    connection that finds the schema behind opens `BEGIN IMMEDIATE` — SQLite's own
    writer lock, which a second connection waits on rather than failing, and which is
    the mechanism WAL exists to make cheap — and re-reads the version inside it, so
    the loser of the race applies nothing instead of applying everything twice.

    `execute` and never `executescript`, deliberately twice over. `executescript`
    commits the transaction out from under itself, which is why wrapping
    `SqliteStore.setup()` in `BEGIN IMMEDIATE` was not available as the fix; and it
    would accept a multi-statement migration silently, where `execute` raises
    `ProgrammingError` if a future release of the package ships one. A dependency
    upgrade that changes the shape of the schema should fail loudly here rather than
    apply half of it.
    """
    if _schema_version(connection) >= len(SCHEMA) - 1:
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS store_migrations (v INTEGER PRIMARY KEY)"
        )
        applied = _schema_version(connection)
        for version, statement in enumerate(SCHEMA):
            if version <= applied:
                continue
            connection.execute(statement)
            connection.execute(
                "INSERT INTO store_migrations (v) VALUES (?)", (version,)
            )
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def _schema_version(connection: sqlite3.Connection) -> int:
    """The highest migration this database has, or -1 if it has no schema at all.

    Two reads and no `CREATE TABLE IF NOT EXISTS`, so that asking the question on a
    database that is already migrated cannot take a write lock: the fast path above
    runs on every batch, and a fast path that wrote would put every reader behind
    every writer and give up what WAL was enabled for.
    """
    named = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'store_migrations'"
    ).fetchone()
    if named is None:
        return -1
    row = connection.execute("SELECT max(v) FROM store_migrations").fetchone()
    return -1 if row is None or row[0] is None else int(row[0])


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
