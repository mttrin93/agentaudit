---
status: accepted
---

# The approval checkpoint outlives the process, and one run owns one connection

[ADR-0007](./0007-canary-nonce-as-proof-of-control.md) puts a real LangGraph
`interrupt()` in front of the spend, and `APPROVAL_WAIT_SECONDS` in
`backend/api/run_status.py` tells the human how long they have:

> A halted run holds a thread and a checkpoint, so the wait is finite; it is an hour
> because the human it is waiting for has to read two figures and decide whether to
> spend them, and a limit short enough to catch somebody thinking would be a consent
> mechanism that answered on their behalf.

The graph was compiled with `InMemorySaver()`. An hour is exactly the window a
deploy, a crash or a `uvicorn --reload` lands in, so for that hour the sentence was
false: the checkpoint lived in the process that created it, and a run halted at the
interrupt did not survive a restart.

The consequence is worse than a lost run, because the record could not say what
happened. `ApprovalOutcome.halted` exists to separate two outcomes that both spend
nothing — *nobody said no, nobody said anything*. A human who came back to answer a
run that no longer existed produced the second of those, indistinguishable from a
run nobody was ever asked about. The one distinction the halt was built to preserve
was the one a restart erased.

## Decision

1. **The checkpointer is `SqliteSaver` over a file**, from
   `langgraph-checkpoint-sqlite`, and never a memory saver. This is
   [ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
   point 2 applied to the second kind of state: a memory saver is the right thing for
   a unit test and may not be what a run uses.
2. **The connection is owned by the `ApprovalRun` object, not by a thread.** It is
   opened `check_same_thread=False` and closed by `ApprovalRun.close()`.
3. **The database is per process and shared; the connection is per run.** One file
   under `/checkpoints/`, one `sqlite3.Connection` per `ApprovalRun`, WAL enabled.
4. **A run is nameable.** `thread_id` and the database location are constructor
   parameters, because a checkpoint on disk is reachable only by something that can
   say which thread and which file to look in.
5. **The database's directory is git-ignored**, `-wal` and `-shm` included, on
   [ADR-0008](./0008-repo-disclosure-posture.md)'s reasoning and the same reasoning
   `/precedent/` is ignored on.
6. **`ApprovalState` stays three primitives.** A real serializer makes widening it
   more tempting, not less, and the set is asserted whole rather than field by field.

## Why the connection is the interesting half

`backend/api/runs.py` explains why a run gets its own OS thread: a FastAPI
background task starts *after* its response is sent, and this run has to be already
halted when the response is built, "otherwise the figures returned would be a second
computation of the estimate rather than the one the graph is holding, and there would
be nobody to answer." So the request rendezvouses with a worker thread at the
interrupt, and two threads reach one graph — the worker that invoked it, and whatever
thread carries the answer back.

`sqlite3` refuses a connection used off its creating thread unless told otherwise,
and the sync `SqliteSaver` holds exactly one connection. So "which thread owns the
connection" is a question this change had to answer rather than discover, and the
answer is *none of them*: the object owns it.

Driving the two-thread path turned up a second, stronger reason for the same flag,
and it is the reason a single-threaded test would not have found the defect either.
**LangGraph writes the checkpoint from its Pregel executor's thread pool**, not from
the caller. With `check_same_thread` left at its default, the very first `invoke`
raises

```
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in
that same thread.
```

before any second thread of ours exists. `check_same_thread=False` is safe here
because `SqliteSaver` takes a `threading.Lock` across every cursor it opens — its
own docstring says as much — so serialisation is the saver's, and correctness does
not rest on our call pattern.

WAL is enabled for the case of two runs halted at once: one reading its own
checkpoint should not block behind another writing one. It is also what creates the
`-wal` and `-shm` sidecars, which is why the ignore covers a **directory** rather
than a file name.

## Considered options

- **A process-wide singleton saver.** One connection, one lock, every run through it.
  Simpler to reason about and it makes the ownership question vanish. Rejected on two
  counts: a module-level connection is a global with a lifetime nobody closes, and it
  serialises every run's checkpoint writes behind one lock for no gain, since SQLite
  in WAL mode already admits one writer and many readers. It also makes the database
  location impossible to inject, which would leave durability testable only against
  the real path.
- **A connection per thread (`threading.local`).** The obvious reflex given
  `check_same_thread`, and wrong here. The threads are not the units: a *run* is. A
  per-thread connection would give the worker and the answering request two views of
  one halt and put the burden of closing them on whichever thread happened to exit
  last — and it would still need WAL to keep the two from blocking each other.
- **`AsyncSqliteSaver`.** The saver LangGraph recommends for concurrency, and the
  right answer for the async graph this is not. The approval graph is driven
  synchronously from a worker thread precisely because the request has to rendezvous
  with it; introducing an event loop to hold a checkpoint would be a second
  concurrency model beside the one ADR-0007's halt already needs. Revisit if the run
  loop becomes async.
- **Postgres.** A schema and a lifecycle for a single tenant's halted runs, when the
  data is three primitives that live for at most an hour. The right answer when
  cross-tenant isolation arrives, and out of proportion now — the same judgement
  ADR-0019 made about the store, reached again about the checkpoint.
- **Shorten the wait instead.** If a halt cannot survive an hour, promise less. It
  fixes the inconsistency in the wrong direction: `APPROVAL_WAIT_SECONDS` argues the
  hour is the human's, and "a limit short enough to catch somebody thinking would be
  a consent mechanism that answered on their behalf."

**On ADR-0019's rejection of this dependency.** ADR-0019 considered
`langgraph-checkpoint-sqlite` and turned it down. That was a decision about the
**precedent store** — a `BaseStore` for findings, where a dependency, a schema and a
lifecycle were out of proportion to a JSON file. This is a decision about the
**checkpointer**, where the interface is not ours to choose: LangGraph's durability
comes from a `BaseCheckpointSaver`, and the alternatives to a shipped one are a
hand-written saver over the checkpoint protocol or no durability at all. ADR-0019 is
not amended, and its reasoning about the store still holds.

## Consequences

- One dependency, and `uv.lock` moves with it — CI runs `uv sync --all-groups
  --locked`.
- `ApprovalRun` gains `thread_id`, `checkpoints` and `close()`.
  `run_under_approval` closes the connection in a `finally`; the halt it wrote stays
  on disk, which is the whole point.
- A machine that has run the bench has a `/checkpoints/` directory holding approver
  identities. It is git-ignored and it is user data at rest, and nothing yet prunes
  it — a halted run's checkpoint is kept until somebody deletes the file.
- **The graph's half of restart survival is done; the API's half is not.**
  `BenchRuns` holds its `RunRecord`s, its `RunState`s and its `PendingApproval`
  rendezvous in memory, so a process that restarts still forgets that a run exists,
  what target it was pointed at and who to hand the answer to. What changes here is
  that the halt itself is no longer the thing that was lost, and the thread id needed
  to reach it is now nameable. Persisting the run record, and a route that resumes a
  halt found on disk, is the remaining work: it is issue #61, filed rather than left
  as a paragraph here, and it is a decision of its own — a run record is not three
  primitives, so ADR-0019's argument about what may cross a serializer bites harder
  there than it did on `ApprovalState`.
- Two threads reaching one graph is now a tested path
  (`backend/tests/test_approval_checkpoints.py`) rather than an assumption, which is
  the assertion that would catch a future saver that only works from the convenient
  side.

Cross-references:
[ADR-0007](./0007-canary-nonce-as-proof-of-control.md) (the halt this keeps),
[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
(the same argument about the store, and why its rejection of this dependency does not
carry),
[ADR-0008](./0008-repo-disclosure-posture.md) (why the database is never committed).
