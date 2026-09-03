"""A `BaseStore` whose authority is a SQLite file, opened for one batch.

The machinery two durable stores share, and it is here rather than in either of
them because the second one arrived. `PrecedentDatabase` is the adaptive layer's
long-term memory (ADR-0019, ADR-0029); `DecisionDatabase` is what the admission
gate has already decided
([ADR-0032](../../docs/adr/0032-the-admission-memory-holds-the-measurement.md)).
They are two files and one concern each — ADR-0029 decision 6 — and this is the one
implementation of *how a file is opened*, which is not a concern either of them
owns.

**A subclass per concern rather than one shared type**, so that neither store can
be handed the other's file by accident and neither module imports the other. Why
that mattered enough to shape the class this way is ADR-0032.

The rows, the SQL and the migration statements are
`langgraph.store.sqlite.SqliteStore`'s, from the package the approval checkpointer
already depends on (ADR-0028). What is left here is where a database is, what
pragma it is opened under, *when* the schema is applied, and one refusal.

**The file is the state and a store object holds none — not even a connection.**
ADR-0029 decision 2, and the two functions at the foot of this module are what it
cost. Both are measured there; neither is here for tidiness.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from langgraph.store.base import (
    BaseStore,
    GetOp,
    ListNamespacesOp,
    Op,
    Result,
    SearchOp,
)
from langgraph.store.sqlite import SqliteStore

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


class NoVectorIndex(NotImplementedError):
    """A natural-language search was asked of a store with no embedding model.

    Refused rather than answered with an unranked list, and the refusal is
    load-bearing in a way it was not while the backend was a document.
    `SqliteStore` *can* rank by meaning — it takes an `index` config and reaches
    `sqlite-vec` — but only against an embedding model, and with none configured its
    search drops the `query` and returns the same recency-ordered rows a query-less
    search would (`_prepare_batch_search_queries` takes the vector branch on
    `op.query and self.index_config`). So the delegate answers a semantic question
    with a list it did not rank, which is exactly the silently wrong answer this name
    exists to turn into a stack trace.

    Configuring that index is the alternative, and ADR-0029 records why it lost. The
    refusal that used to sit beside this one, `NoFilterOperators`, is gone for the
    mirror-image reason recorded there.
    """


class DatabaseStore(BaseStore):
    """One SQLite file, opened per batch, with the schema applied under a lock.

    A subclass per concern rather than a path argument at every call site: the
    subclass names the file, and a field annotated with it refuses an
    `InMemoryStore` before a test has to (ADR-0019 point 2, and the mechanism
    `DurablePrecedents.store` uses).

    A semantic `query` is refused rather than approximated (`NoVectorIndex`), and
    refused before a connection is opened, so a refused search leaves no database
    behind. An operator filter is not refused: SQLite runs the comparison, which was
    the whole of the old refusal's argument.

    **Reading a store nothing has written answers without creating one** (ADR-0029
    point 7). Opening a database runs the schema, so a lookup would otherwise leave a
    file where there was none — and neither of the two things kept in these files
    records who looked at it.
    """

    __slots__ = ("path",)

    @classmethod
    def default_path(cls) -> Path:
        """Where this store's database is when the caller does not name one.

        A method and not a class attribute, so that it is read at construction
        rather than at class creation: `conftest.py` redirects both of these stores
        by patching the module constant each subclass returns, and a value bound
        into the class body would have stopped answering to that.
        """
        raise NotImplementedError

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else self.default_path()

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        asked = list(ops)
        for op in asked:
            if isinstance(op, SearchOp) and op.query is not None:
                raise NoVectorIndex(
                    f"{op.query!r} is a natural-language query and this store has "
                    "no embedding model. A lookup here filters on a stored field "
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
        would also introduce an event loop to hold one small lookup, which is the
        second concurrency model ADR-0028 declined to add for the checkpoint and
        ADR-0029 declined again here. The graph is free to await this; what it awaits
        is one small synchronous batch against a local file.
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
        writes can arrive at once, and one reader should not block behind another's.

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
    Enabling it is an optimisation; refusing to write because an optimisation was
    already being applied is not a trade either store makes.

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
