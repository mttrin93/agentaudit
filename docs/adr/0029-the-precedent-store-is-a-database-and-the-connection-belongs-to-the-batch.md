---
status: accepted
amends: 0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md
---

# The precedent store is a database, and the connection belongs to the batch

[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
made the precedent store durable and wrote its backend down as the cheapest thing that
could be:

> **Backed by a file.** If no durable backend is available without a dependency out of
> proportion to a single tenant's findings, a small `BaseStore` implementation over JSON
> is the honest answer — the claim rests on the **interface** and the lifetime, not on
> the backend's brand.

That produced `JsonFileStore`: 150 lines that loaded the whole document on every batch,
applied the operations in Python and wrote the document back. The ADR's considered
options said what it would take to revisit:

> **Add a database-backed Store — `langgraph-checkpoint-sqlite`, Postgres.**
> `langgraph.checkpoint.sqlite` is not currently installed. A dependency, a schema and a
> lifecycle for a single tenant's findings is out of proportion **now**, and it is the
> right answer at P1 when cross-tenant isolation arrives and **brings a real query
> surface with it**.

Both halves of the condition have moved, and neither moved the way it was expected to.

**The query surface arrived from the other direction.** #32's promotion memory is a
lookup *by route* — did this route already win, and against what — rather than a filter
by family. It is not the cross-tenant query the ADR was waiting for; it is a second
reader whose access pattern a rewrite-the-world document is the wrong shape for. The
reason behind the condition was met without the trigger.

**The dependency arrived on its own.**
[ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) added
`langgraph-checkpoint-sqlite` for the approval checkpointer, where the interface was not
ours to choose. That ADR was careful to say it was not amending this one:

> That was a decision about the **precedent store** — a `BaseStore` for findings, where a
> dependency, a schema and a lifecycle were out of proportion to a JSON file. This is a
> decision about the **checkpointer** … ADR-0019 is not amended, and its reasoning about
> the store still holds.

It held for exactly as long as the cost did. That package ships
`langgraph.store.sqlite.SqliteStore` alongside the saver, so the three things ADR-0019
was weighing are now: **no** dependency, because it is already installed and locked;
**not our schema**, because the migrations, the `store` table and the JSON filter
compilation belong to the package; and **the same lifecycle**, because the file is still
one file in one git-ignored directory. What is left of the trade is a net deletion of
code we were maintaining.

So this is not "the deferral expired." It is that the thing deferred stopped costing
anything, and continuing to cite the deferral would be citing a price nobody is being
asked to pay.

## Decision

1. **The store is `PrecedentDatabase`, a `BaseStore` over
   `langgraph.store.sqlite.SqliteStore`**, at `precedent/findings.sqlite`. ADR-0019's
   points 1, 2, 4, 5 and 6 stand unchanged and are what this is measured against; point
   3's *conclusion* is superseded and its *argument* is what licenses the change — the
   claim rests on the interface and the lifetime, and both are byte-for-byte the same.
2. **The connection belongs to the batch.** Not to the object, not to a run, not to the
   process. Every `batch` opens a connection, applies the operations and closes it.
3. **No migration.** An existing `precedent/findings.json` is not imported, and not
   deleted either. `seed_precedent.py` names it once while it is still there.
4. **No tenant column.** ADR-0019 point 5, restated because a SQL schema makes the
   temptation cheap in a way a JSON document did not.
5. **No vector index.** `NoVectorIndex` stays and its reason changes; `NoFilterOperators`
   goes and takes its reason with it.
6. **One database, one concern.** This database holds precedent. The next durable
   thing gets its own file rather than a table in here.
7. **A read does not create the store.** A batch of nothing but reads, against a path
   that is not there, answers empty without opening anything — because opening runs the
   migrations, and *reading precedent is not an event in the store's history*.

## Why the connection is the interesting half, again

ADR-0028 asked *which thread owns the connection* and answered *none of them — the object
does*, because a halt is written by one thread and answered by another. This decision
reaches the opposite answer for a store, and the two are worth reading together, because
the difference is not taste.

An `ApprovalRun` is a **thing with a lifetime**: it is constructed, it halts, it waits up
to an hour, and something else answers it. The connection has to outlive the call that
made it, so somebody has to own it, and the run is the only candidate that is not a
thread.

`DURABLE_PRECEDENT` is the opposite: a **module-level object with no lifetime at all**,
constructed at import and never closed, and the default argument of `run_calibration`,
`run_adaptive_layer` and `run_episode`. ADR-0028 rejected a process-wide singleton saver
because "a module-level connection is a global with a lifetime nobody closes" — and
`DURABLE_PRECEDENT` is precisely that global. Giving it a connection would be building
the option that ADR was right to refuse.

Three things fall out of the batch owning it instead.

- **The path stays the authority and the object holds no state**, which is the property
  ADR-0019's store had and the property that makes a shared module-level object safe:
  two store objects against one path cannot disagree, because neither of them is holding
  anything. It is also what lets `conftest.py` redirect the suite by patching one
  attribute — the alternative is a suite that can only redirect a store it constructs
  itself, which is not the store a default argument already captured.
- **`check_same_thread` stays at its default.** The connection is opened, used and
  closed inside one call, so the strict setting is free, and it would catch a future
  caller who tried to hold one open across threads. ADR-0028 could not have that: the
  Pregel executor writes the checkpoint from its own pool.
- **The cost is a connection and two `SELECT`s per batch** — the version check `_migrated`
  opens with, which takes no lock on a database already migrated — and the traffic is one
  search per family per run and one insert per deterministic finding. If precedent ever
  becomes hot enough for that to matter, the measurement will say so, and the answer then
  is an owned connection with the ownership question answered rather than inherited.

WAL is enabled and outlives the connection, because the journal mode is written into the
file's header. Two bench runs are two OS threads (`backend/api/runs.py`), so two findings
can be filed at once, and a reader should not block behind another's write.

## What the batch owning the connection cost, and it was not the connection

The price of decision 2 turned out to be nothing to do with opening a file, and it was
found by a test failing rather than by reasoning ahead: **`SqliteStore` is written to be
one long-lived object, and two of its behaviours are unsafe when it is not.** It surfaced
as one of two concurrent runs ending `FAILED` in `test_api_usage.py` — two files away
from anything that mentions precedent — and reproduces as six threads filing findings
against one database that does not exist yet.

**Its migration routine is not atomic.** `setup()` reads the applied version, applies
what is missing and inserts the new version numbers, with no transaction around the pair.
Two connections that read the same version both apply migration 0, and the loser of the
insert gets `UNIQUE constraint failed: store_migrations.v` — or `duplicate column name`
on a migration that adds one. Called once per process this is a cold-start curiosity;
called once per batch it is every pair of concurrent runs. `_migrated` applies the schema
instead, inside `BEGIN IMMEDIATE`, taking SQLite's own writer lock and re-reading the
version inside it, so the loser applies nothing. `setup()` still runs on the delegate's
first use and finds nothing to do, which is what makes leaving it alone safe.

**And `PRAGMA journal_mode=WAL` is the one statement the busy timeout does not cover.**
Changing the journal mode needs an exclusive lock, cannot be taken inside a transaction,
and returns `SQLITE_BUSY` *without* consulting the busy handler. So several processes
opening a new database collide on the pragma itself. `_enable_wal` reads the mode before
setting it, and treats a lost race as nothing — matched on `SQLITE_BUSY` and
`SQLITE_LOCKED` rather than on the exception type, so a database that will not open at
all is still an error. The mode is a property of the file, so whoever wins sets it for
everyone after, and refusing to file a finding because another process was enabling an
optimisation would be trading a run for a pragma.

**The wait those two lean on is now a stated number.** `WRITE_WAIT_SECONDS` is passed to
`sqlite3.connect` as its busy timeout, because "a second connection waits rather than
failing" is a claim about a figure, and Python's implicit five seconds was not a figure
anybody here chose.

**Measured, because a race argued for is not a race fixed.** Under six CPU hogs, six
threads against one cold database twenty times over, and eight processes released from a
barrier six times over:

| | six threads, in-process | eight processes, barrier |
| --- | --- | --- |
| As first written, with neither line | 14 of 20 runs failed | 8 batches lost |
| Both lines | **0 of 20** | **0** |

Each also earns its place alone, ablated one at a time: with the delegate applying its
own schema, 5 of 12 runs and 26 batches; with the pragma unguarded, 2 batches. So neither
is covering for the other. The counts are **not comparable between rows** — contention
depends on what else the machine is doing, and the same configuration measured 0, 2 and 5
failures on three different afternoons. What the numbers support is *fails often* against
*did not fail*, and nothing finer.

Two things were built along the way and then deleted, and they are recorded because the
next person to see a `database is locked` here will reach for both. A **process-wide lock
per database path**, restoring the serialisation `SqliteStore`'s own `threading.Lock`
gives when the object is long-lived; and a **`sqlite3.Connection` subclass rewriting the
delegate's deferred `BEGIN` to `BEGIN IMMEDIATE`**, since SQLite fails an upgrade from a
read transaction immediately rather than waiting out the busy timeout. Both are sound
arguments. Neither changed a single measurement once the two above were in place, because
the failures they were aimed at were the pragma's — so both are gone, on the rule that
code which cannot be shown to matter is not kept.

## Why there is no migration, said out loud

The store was machine-local, git-ignored, and filled from two places: `record`, which no
caller reaches yet, and `scripts/seed_precedent.py`, whose entries are four sentences an
operator typed and which are still in the script. So the complete contents of every
`findings.json` in existence are four rows that one command re-creates.

An importer for that would be code with a test, a failure mode and a lifetime, written to
move data that is already in the repository in a more readable form. What it would buy is
the appearance of care. What it would cost is a code path that parses a document written
by a store that no longer exists, kept forever because nothing can prove the last clone
has run it.

The one real hazard is silence: an operator whose seeds stop being read and who concludes
the seeding broke. That is answered where it happens — `seed_precedent.py` prints the old
file's path and says nothing reads it — and not by a migration.

## Why the two refusals part company

`JsonFileStore` refused two things, on one argument: a comparison a caller believes ran
and did not is worse than a refusal.

**`NoFilterOperators` is deleted.** SQLite runs the comparison. A refusal resting on a
limitation the backend no longer has is a guard a reader has to reverse-engineer to
discover means nothing, and the honest replacement for it is a test that the comparison
runs.

**`NoVectorIndex` stays, and its reason is now the delegate's behaviour rather than an
absence.** `SqliteStore` *can* rank by meaning: it takes an `index` config and reaches
`sqlite-vec`. But it takes the vector branch on `op.query and self.index_config`, so with
no embedding model configured it **drops the query** and answers with the same
recency-ordered rows a query-less search would return, `score` null. That is the silently
wrong answer the refusal exists to turn into a stack trace, and it is asserted against the
dependency in `test_precedent.py` — if a future release starts refusing a query it cannot
rank, that test fails and this refusal has become the leftover.

Configuring the index is the alternative and it is refused as a decision. It would put an
embedding model inside the one component ADR-0004 and ADR-0013 keep two instruments away
from, and it would rank precedent by a score nobody could re-derive, which is the
objection `RETRIEVAL_LIMIT` already records against relevance ordering.

## Considered options

- **Keep `JsonFileStore`.** Free, and it is the status quo the ticket is about. Rejected
  on the arithmetic above: the deferral's price is now zero, so keeping it means
  maintaining a hand-written store — a document rewrite, a hand-rolled recency sort, a
  hand-rolled equality filter — beside an installed, locked, tested implementation of the
  same interface. Not a cost question any more; a which-code-do-you-want-to-own question.
- **Write our own SQLite `BaseStore`.** Considered because it would keep the schema ours
  and answer the "no tenant column" point by construction. Rejected: it is the same
  hand-written store with a harder backend, and the schema being ours is not a benefit
  when the requirement is one namespace and one equality filter.
- **Own the connection on the store object** (`PrecedentDatabase.close()`, the ADR-0028
  shape). Rejected on the section above: the object that would own it is a module-level
  global with no close, and the redirection every test depends on would stop working.
- **A connection per run**, passed down from `run_calibration`. This is ADR-0028's answer
  transplanted, and it would make the store an argument threaded through three call sites
  that currently take a default. Rejected as a widening for no gain: a precedent lookup
  has no rendezvous in it, so there is no second thread for the run to be the answer to.
- **`AsyncSqliteStore`**, which the same package ships. It would make `abatch` honest
  rather than a synchronous call in an async signature. Rejected for ADR-0028's reason
  about `AsyncSqliteSaver`: an event loop to hold a precedent lookup is a second
  concurrency model, and the run loop is synchronous. Revisit together, not separately.
- **Import `findings.json` on first open.** Rejected above.
- **Postgres.** A schema and a lifecycle for one tenant's findings, which is the judgement
  ADR-0019 made and ADR-0028 made again. Unchanged: the right answer when cross-tenant
  isolation arrives, and the reason this decision does not pre-empt it is that it adds no
  tenant column to route around.
- **A `tenant` column now, unenforced.** It would make the P1 migration smaller. Rejected
  as ADR-0019 point 5 rejected the namespace segment: a column nothing checks is an
  isolation boundary a reader would believe in. Cross-tenant isolation stays a named
  blocker, visible as an absence.

## Consequences

- `backend/bench/adaptive/precedent.py` loses `JsonFileStore`, `NoFilterOperators` and
  four module-level helpers, and gains a class whose whole body is a location, a pragma
  and one refusal. `uv.lock` does not move: the dependency was already there.
- **`DEFAULT_STORE_PATH` moves to `precedent/findings.sqlite`.** `/precedent/` is a
  directory ignore, so the database and its `-wal`/`-shm` sidecars are covered by the rule
  ADR-0008 already licensed, and git is asked about all three plus the old document.
- **Two functions exist that would not exist with a longer-lived connection**,
  `_enable_wal` and `_migrated`, and the section above is why. They are the honest price of decision 2, and
  they are cheaper than the alternative they replaced — a hand-written store — but they
  are not free, and a future reader weighing an owned connection should weigh them.
- **A read against a database that is not there answers without creating one.**
  Running the migrations is what opening does, so a lookup would otherwise leave an empty
  file where nothing was there before — and *reading precedent is not an event in the
  store's history* is a claim older than this backend, asserted since the store had one
  caller. It was briefly weakened to a claim about **rows** and then restored properly:
  a batch of nothing but reads, against a path that does not exist, returns the empty
  answer without opening anything. That keeps `exists()` meaning what two other tests
  need it to mean — a refused write and a refused query still leave nothing at all — and
  it is why those two tests could go back to asserting exactly what they asserted before
  the backend changed.
- **`created_at` is reset by a re-write.** `SqliteStore` uses `INSERT OR REPLACE` with
  `CURRENT_TIMESTAMP` for both timestamps, where `JsonFileStore` preserved the original
  `created_at`. Nothing reads `created_at`; recency ordering reads `updated_at`, which is
  second-granularity, so two findings filed inside one second come back in an arbitrary
  order relative to each other. Both are properties of the delegate and neither is worth
  a wrapper to hide; recorded because the alternative is rediscovering them.
- **The suite stopped writing findings into the working copy.** `precedent_elsewhere` was
  function-scoped and autouse, so it was not in place while `test_gate.py`'s module-scoped
  gate run was built — 540 attempts, filed at the real location, invisible because the
  location is git-ignored. It is now a session-scoped redirection with the per-test one
  inside it, in the shape `checkpoints_elsewhere` already had, and a module-scoped fixture
  in `test_precedent.py` asserts it from the scope that escaped.
- **#39 gets its own database.** The gate's decisions are scored-side state, and this
  file is adaptive-layer memory that ADR-0004 and ADR-0013 keep two instruments away
  from by an import test. Sharing one file would put a scored reader and precedent behind
  one path, one ignore rule and one set of migrations, and the first question a reviewer
  would have to answer is whether the separation still holds. Its own file makes that
  question not arise. Point 6 above.
- The store's interface is unchanged, so `retrieve_precedent`, `suggest_remediation`,
  `DurablePrecedents` and `RecordedPrecedents` are untouched, and ADR-0019 point 2's
  mechanism still works: `DurablePrecedents.store` is annotated `PrecedentDatabase`, which
  is narrower than `BaseStore`, so mypy refuses an `InMemoryStore` before a test has to.

Cross-references:
[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
(the decision this amends, and the five points of it that stand),
[ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) (the dependency, and
the opposite answer about who owns a connection),
[ADR-0008](./0008-repo-disclosure-posture.md) (why the database is never committed),
[ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) and
[ADR-0013](./0013-adjudication-is-a-third-instrument.md) (the two instruments precedent
cannot reach, and why no embedding model goes in here).
