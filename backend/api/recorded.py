"""The run around the halt, written down: what a restarted process can still know.

[ADR-0028](../../docs/adr/0028-the-approval-checkpoint-outlives-the-process.md) put
the approval checkpoint on disk and said in as many words which half of restart
survival that was. The halt became durable; the run around it did not, so a human
who came back after a deploy and answered got a `KeyError` at the route against a
bench that said no run of that id had ever been started — a false statement about a
run this bench had started, halted and estimated.

The decision, its alternatives and the argument it had to be built around are
[ADR-0034](../../docs/adr/0034-a-run-record-outlives-its-process-and-carries-no-run.md).
Three of its points decide the shape of everything below and are stated here because
they are what a reader of this file most needs.

**What crosses is the declaration, never the measurement.** A `RunRecord` holds a
`RunState` with live counters, a `CalibrationResult` full of the target's own
replies, a `SignedArtefact`, a `RunPlan` of case records and a `threading.Event`.
None of that is here. `RecordedRun` is the statement *that a run exists, who
authorised it, what it was estimated at and where it got to* — which is ADR-0019's
argument about what may cross a serializer, and `ApprovalState`'s about what may
cross a checkpoint, reaching the third kind of state.

**The target is not here, and that is why a recovered halt cannot be confirmed.** A
`TargetConfig` carries the operator's endpoint URL and its bearer token.
`registration.endpoint_hash` exists because "a live URL that answers jailbreak
payloads is not a thing to write into a document that travels" (ADR-0008), and a
credential is worse. So the hash is stored and the endpoint is not, and the
consequence is stated rather than absorbed: a run whose worker thread is gone cannot
be resumed, because the bench no longer holds what it would need to call. ADR-0034
argues why that is the right direction rather than a limitation.

**The hour is a deadline here rather than an `Event.wait()` there.**
`PendingApproval` is a rendezvous between two threads of one process, and across a
restart there is no second thread to wake. `answerable_until` is the same hour
`APPROVAL_WAIT_SECONDS` promises, written as an instant, so a process that never saw
the wait can still tell a halt somebody may answer from one nobody can.

**The connection belongs to the batch**, not to this object — the opposite of
ADR-0028's answer for the checkpointer, for the reason ADR-0034 gives. How a file is
opened is `backend/bench/store.py`, measured under contention and shared rather than
copied (ADR-0029 decision 2, and ADR-0032's restatement of it).
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from backend.api.run_state import RunRecord
from backend.api.run_status import RunStatus
from backend.bench.library import LibraryVersion
from backend.bench.registration import endpoint_hash
from backend.bench.store import DatabaseStore

RUN_NAMESPACE: Final = ("agentaudit", "runs")
"""Where a started run is filed, and it says single-tenant by having no tenant.

Two fixed elements and no third, on ADR-0019 point 5's reasoning and the
restatements of it in ADR-0029 point 4 and ADR-0032: a namespace with a tenant
segment in it would look like isolation and enforce none, because one file holds
every row and nothing checks the segment on the way out. Cross-tenant isolation is a
named P1 blocker (PLAN §11) and this is a place a reader can see it is absent rather
than assumed.
"""

RUN_RECORD_DIRECTORY: Final = Path(__file__).resolve().parents[2] / "runs"
"""The directory this database lives in, ignored by git as a directory.

A directory rather than a file name, for the reason `/precedent/`, `/decisions/` and
`/checkpoints/` are directories: SQLite writes `-wal` and `-shm` sidecars beside the
database, and a journal holding the identity of whoever authorised a spend against
somebody else's endpoint must not be the one thing the ignore rule missed (ADR-0008).

Its own database and not a table in either of the other two, on ADR-0029 decision 6
— one database, one concern. What is kept here is scored-side operational state
about *this deployment's* runs; precedent is adaptive-layer memory two instruments
are kept away from by an import test, and `decisions/routes.sqlite` is the admission
gate's. Sharing a file would put all three behind one path, one ignore rule and one
set of migrations.
"""

DEFAULT_RUN_RECORD_PATH: Final = RUN_RECORD_DIRECTORY / "started.sqlite"
"""Where the run records are, at the top of the repository and ignored by git.

One location and no environment override, on `DEFAULT_STORE_PATH`'s and
`DEFAULT_DECISION_PATH`'s reasoning: a configurable path is a path that can be
configured into a tracked directory. A test asks git whether this path is ignored,
and asks it of the sidecars too.
"""

RECOVERED_PER_PAGE: Final = 200
"""How many rows one listing batch reads while recovering what is on disk.

A page size and not a limit — `recorded()` pages until a short page comes back, so
the number bounds one query rather than what a restart can see. Two hundred because
the delegate's search is one `SELECT` against a local file and a bench with more
recorded runs than that is a bench where the paging matters more than the round trip.
"""


class MalformedRecordedRun(ValueError):
    """A row in the run-record database could not be read as a run.

    Raised rather than skipped, and the choice is the whole reporting hazard #35
    named, arriving from the other side. A `find` that answered `None` for a row it
    could not parse would tell a human that the run they are holding a URL for was
    never started — and that is exactly the reading ADR-0028 built the durable halt
    to make impossible. A run this bench cannot read about is a loud failure, never
    an absent one.
    """


@dataclass(frozen=True)
class RecordedRun:
    """One run as it is written down: the declaration, and where the run got to.

    Frozen, and every mutation is a `replace` written back under the same key, for
    `BenchConfig`'s reason: a reader that has this row has the row as it was, and a
    row edited in place is a row two readers can disagree about.

    **Every field here is a primitive or a small frozen record of primitives**, and
    the whole of ADR-0034's serializer argument is that the list stops where it
    stops. `test_run_records.py` asserts the field set whole rather than field by
    field, on the pattern `ApprovalState`'s own assertion uses, so a `RunState`
    added here fails rather than passing unnoticed.
    """

    run_id: str
    thread_id: str
    """The halt this run is waiting at, which is the whole reason the row is useful.

    A checkpoint on disk is reachable only by something that can say which thread to
    look in (ADR-0028 point 4), and it is deletable only by the same thing — so this
    field is what makes a recovered halt both answerable and prunable (ADR-0034).
    """

    recorded_at: datetime
    answerable_until: datetime
    """The end of the hour `APPROVAL_WAIT_SECONDS` promises, as an instant.

    `PendingApproval` spends that hour in an `Event.wait()` between two threads of
    one process. A restarted process has no such thread and nothing to wake, so the
    same hour has to be readable from the record — a halt past this instant is
    answerable by nobody, and one before it is answerable by anybody who has the run
    id (ADR-0034).
    """

    status: RunStatus
    statement: str
    confirmed_by: str
    target: str
    """The name the operator gave the target, and never its URL or its token.

    The declared label `GET /runs` already serves — "the target is named and its URL
    is nowhere". What the bench would need in order to *call* the endpoint again is
    deliberately not here, and ADR-0034 is where that costs a recovered halt its
    yes.
    """

    endpoint_hash: str
    """`sha256` of the endpoint this run was authorised against.

    The identifier `AttestationRecord` already keeps for a record that outlives its
    run, and for its reason (ADR-0008): it joins a row to the attestation that
    authorised it without writing down an endpoint that answers jailbreak payloads.
    """

    attested_by: str
    library: LibraryVersion
    scored_ceiling: int
    adaptive_ceiling: int
    currency: str
    proof_waived: bool

    @classmethod
    def of(cls, record: RunRecord, wait_seconds: float) -> RecordedRun:
        """The projection from a run to what is written down about it.

        One function and one place, which is ADR-0034's mechanism rather than its
        tidiness: a field added to `RunRecord` does not become durable by being
        added, and a reader can see the whole of what crosses the serializer at
        once. What is *not* here is the argument — the counters, the plan, the
        result, the artefact and the target — and the ADR says why for each.
        """
        return cls(
            run_id=record.run_id,
            thread_id=record.thread_id,
            recorded_at=record.recorded_at,
            answerable_until=record.recorded_at + timedelta(seconds=wait_seconds),
            status=record.status,
            statement=record.statement,
            confirmed_by=record.confirmed_by,
            target=record.target.name,
            endpoint_hash=endpoint_hash(record.target.url),
            attested_by=record.attestation.identity,
            library=record.run_state.library,
            scored_ceiling=record.presented["scored_ceiling"],
            adaptive_ceiling=record.presented["adaptive_ceiling"],
            currency=record.presented["currency"],
            proof_waived=record.proof_waived,
        )

    def answerable_at(self, now: datetime) -> bool:
        """Whether a human answering at that instant is answering anything.

        **The one place the deadline is compared with a clock**, and it has to be
        one place. Written twice — here and in the reconciliation — it was written
        twice and load-bearing once: the reconciliation ran first, so a run past
        its hour was already `UNANSWERED` by the time this was asked, and breaking
        the comparison here changed nothing that any caller could observe. A
        deadline whose check cannot be broken is a deadline nothing is testing.
        """
        return (
            self.status is RunStatus.AWAITING_APPROVAL and now < self.answerable_until
        )

    def settled(self, status: RunStatus, statement: str) -> RecordedRun:
        """This row moved to its next state. `RunRecord.settle`'s pair, frozen."""
        return replace(self, status=status, statement=statement)

    def stored(self) -> dict[str, Any]:
        """This row as the store keeps it: JSON-safe primitives and nothing else."""
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "recorded_at": self.recorded_at.isoformat(),
            "answerable_until": self.answerable_until.isoformat(),
            "status": str(self.status),
            "statement": self.statement,
            "confirmed_by": self.confirmed_by,
            "target": self.target,
            "endpoint_hash": self.endpoint_hash,
            "attested_by": self.attested_by,
            "library_cases": self.library.cases,
            "library_digest": self.library.digest,
            "scored_ceiling": self.scored_ceiling,
            "adaptive_ceiling": self.adaptive_ceiling,
            "currency": self.currency,
            "proof_waived": self.proof_waived,
        }

    @classmethod
    def read(cls, stored: Any) -> RecordedRun:
        """One row back out, refusing anything it cannot read as a run.

        Defensive because the row outlives the process that wrote it and a package
        upgrade, a hand edit or a database restored from somewhere else can all
        produce one this code did not write. Refused rather than patched up: a row
        half-read would be a run whose deadline or whose status came from a default,
        and both of those decide whether somebody may still answer it.
        """
        if not isinstance(stored, dict):
            raise MalformedRecordedRun(
                f"a run record is a mapping and this row is a {type(stored).__name__}"
            )
        return cls(
            run_id=_text(stored, "run_id"),
            thread_id=_text(stored, "thread_id"),
            recorded_at=_moment(stored, "recorded_at"),
            answerable_until=_moment(stored, "answerable_until"),
            status=_status(stored),
            statement=str(stored.get("statement", "")),
            confirmed_by=str(stored.get("confirmed_by", "")),
            target=str(stored.get("target", "")),
            endpoint_hash=str(stored.get("endpoint_hash", "")),
            attested_by=str(stored.get("attested_by", "")),
            library=LibraryVersion(
                cases=_whole(stored, "library_cases"),
                digest=str(stored.get("library_digest", "")),
            ),
            scored_ceiling=_whole(stored, "scored_ceiling"),
            adaptive_ceiling=_whole(stored, "adaptive_ceiling"),
            currency=str(stored.get("currency", "")),
            proof_waived=stored.get("proof_waived") is True,
        )


@dataclass(frozen=True)
class RecordedRuns:
    """The runs this deployment has started, as they are on disk.

    A thin reading of a `DatabaseStore`, on `DecidedRoutes`' pattern, so that what a
    row *means* lives on `RecordedRun` and this type is only the way in and out.

    Holds no connection, which is the opposite of ADR-0028's answer for the halt
    these rows point at. ADR-0034 argues the difference rather than inheriting
    either answer: every operation here is a complete `get`, `put` or `search`
    inside one call, and the second reader a run record has is separated from its
    writer by a *process boundary* — which a connection per batch crosses and a
    connection per object cannot help with at all, because the object that wrote the
    row is gone.
    """

    store: RunDatabase
    """Annotated with the subclass and not with `BaseStore`, which is ADR-0019 point
    2's mechanism: a field of this type refuses an `InMemoryStore` before a test has
    to, and an ephemeral run registry is the exact defect this module exists for."""

    namespace: tuple[str, ...] = RUN_NAMESPACE

    _writing: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )
    """Held across the read-and-write in `record`, and across nothing else.

    The one piece of state this object has, and it is not the database — the file
    stays the authority (ADR-0029 decision 2) and two `RecordedRuns` over one file
    still cannot disagree about what is in it. What this serialises is a
    read-modify-write between the *two threads of one run*: the worker that finishes
    it and the request that confirmed it both write, and both reach the file through
    the one object `BenchRuns` holds. A lock is therefore exactly the right size for
    the hazard — the hazard is within a process, because two processes never write
    one run id.

    Not taken by `find`, `recorded` or `reconcile`. A lock around a read would make
    every reader wait on a writer, which is what WAL was enabled to avoid
    (`store.py`), and none of those three is deciding anything from what it read.
    """

    @classmethod
    def at(cls, path: Path | None = None) -> RecordedRuns:
        """The run records at that database, or at the declared location."""
        return cls(store=RunDatabase(path))

    def record(self, run: RecordedRun) -> None:
        """Write that run down, replacing whatever this bench last said about it.

        Idempotent by run id, so the same record written at the halt, at the yes and
        at the end is one row moving rather than three rows disagreeing.

        **A run never goes back to being in flight**, and this is not tidiness. One
        run has two writers — the worker thread that finishes it and the request
        that confirmed it — and the request writes `RUNNING` *after* releasing the
        graph, because the release has to happen inside the guard that catches a
        second answer (`BenchRuns.answer`). A suite short enough to finish in
        between would therefore leave the row saying `running` for a run that had
        completed, and a restart would reconcile that to `FAILED` and report a
        finished run as one that stopped part-way.

        **Under `_writing`, because the check and the write are one decision.** A
        `find` followed by a `put` is a read-modify-write, and guarding it with the
        read alone would narrow the window rather than close it: the worker's
        terminal `put` landing between this `get` and this `put` reproduces exactly
        the row the guard exists to prevent. The lock closes it for the writers that
        exist, which are two threads of one process reaching one object — and two
        processes never write one run id.
        """
        with self._writing:
            if run.status.in_flight:
                standing = self.find(run.run_id)
                if standing is not None and not standing.status.in_flight:
                    return
            self.store.put(self.namespace, run.run_id, run.stored())

    def find(self, run_id: str) -> RecordedRun | None:
        """What is written down about one run, or `None` for an id nothing recorded.

        `None` means *nothing was ever written under this id*, and never *the row
        would not parse* — that is `MalformedRecordedRun` and it is raised, because
        a run reported as never started is the reading ADR-0028 exists to prevent.
        """
        found = self.store.get(self.namespace, run_id)
        return None if found is None else RecordedRun.read(found.value)

    def recorded(self) -> list[RecordedRun]:
        """Every run on disk, paged until a short page comes back.

        Paged rather than taken at a limit, so that what a restarted process can see
        is not a number somebody chose: `RECOVERED_PER_PAGE` bounds one query and
        nothing else.

        Read whole before anything is written back, and the reason is what is *not*
        known rather than what is: `recovered` writes to the rows it walks, and how
        a `BaseStore.search` at an offset orders rows a concurrent write has touched
        is the delegate's business and not something `store.py` promises. Collecting
        first costs one list and needs no such promise.
        """
        rows: list[RecordedRun] = []
        offset = 0
        while True:
            page = self.store.search(
                self.namespace, limit=RECOVERED_PER_PAGE, offset=offset
            )
            rows.extend(RecordedRun.read(item.value) for item in page)
            if len(page) < RECOVERED_PER_PAGE:
                return rows
            offset += RECOVERED_PER_PAGE

    def recovered(self, now: datetime | None = None) -> list[RecordedRun]:
        """Every recorded run, as a process that did not start any of them must read
        it.

        The reconciliation, and it is not optional. A row left saying `running` is a
        run `RunStatus.in_flight` calls still going, so `instrument` and `cover`
        would refuse an operator for the lifetime of the deployment on behalf of a
        process that no longer exists — and a poller would be told to keep polling a
        run nothing is driving. Two rows move and the rest are returned as they
        stand:

        - **awaiting an answer past its hour** becomes `UNANSWERED`, which is the
          same outcome the `Event.wait()` reached in the process that is gone —
          nobody said no, nobody said anything.
        - **running** becomes `FAILED`, because the only thing this bench can
          honestly say is that the run stopped and it does not know how far it got:
          the counters were `RunState`'s and they did not cross (ADR-0034).

        Written back, so the reconciliation survives this process too — and returned
        so that the caller can forget the checkpoints the moved rows point at.
        """
        at = datetime.now(tz=UTC) if now is None else now
        return [self.reconcile(row, at) for row in self.recorded()]

    def reconcile(self, row: RecordedRun, now: datetime | None = None) -> RecordedRun:
        """One row, read as a process that did not start it must read it.

        Separate from `recovered` because both callers need it and the second one is
        not a boot: an hour runs out *while* this process is up, so a halt that was
        answerable when the bench was constructed is not answerable when somebody
        answers it forty minutes later. A deadline read once at boot would be a
        deadline that stopped moving.
        """
        moved = _reconciled(row, datetime.now(tz=UTC) if now is None else now)
        if moved is not row:
            self.record(moved)
        return moved


class RunDatabase(DatabaseStore):
    """The run records' own database, at the one git-ignored location.

    Its own file, on ADR-0029 decision 6. How the file is opened is
    `backend/bench/store.py`; who owns the connection is ADR-0034, which reaches
    ADR-0029's answer rather than ADR-0028's and says why the two differ.

    Named rather than replaced by a path argument, because a field annotated with
    this type refuses an `InMemoryStore` before a test has to — ADR-0019 point 2's
    mechanism, and `RecordedRuns.store` is where it bites here.
    """

    __slots__ = ()

    @classmethod
    def default_path(cls) -> Path:
        return DEFAULT_RUN_RECORD_PATH


PAST_ITS_HOUR = (
    "nobody answered this run's approval interrupt inside the hour it was given, so "
    "it never started: nothing was sent to the target and nothing was spent. The "
    "process that was holding the halt is gone and the hour was read off the record "
    "rather than waited out, which is why this says unanswered rather than declined "
    "— nobody said no, nobody said anything"
)

LOST_WITH_ITS_PROCESS = (
    "this run was going when the process running it ended, so it stopped part-way "
    "through. How many calls it had spent is not on this record: the counters "
    "belonged to the run state, which does not outlive its process (ADR-0034). "
    "Nothing here is a reading about the target — a suite that stopped part-way "
    "measured fewer attempts than a rate would be denominated on, so this is not a "
    "partial result, it is not a result"
)


CONFIRMED_AND_NOT_RUN = (
    "this run was confirmed and could not be started. The process that halted it "
    "has ended, and what a run needs in order to call an endpoint is deliberately "
    "not on the record: a run record carries a digest of the endpoint and never the "
    "endpoint or its credential (ADR-0008, ADR-0034). Nothing was sent to the "
    "target and nothing was spent — not by the run that halted, and not by this "
    "confirmation. The record says answered and not run, which is neither declined "
    "nor unanswered. Start a fresh run against the same target: it will present the "
    "same two figures for you to confirm"
)
"""What a human is told when they confirm a halt whose process is gone.

The one outcome in this module that is a refusal rather than a state, and the
wording is load-bearing for the reason ADR-0028's was: the two things a person needs
in the first sentence are that their money was not spent and that this is not the
run being declined on their behalf.
"""

RECOVERED_DECLINE = (
    "The process that halted this run has ended, so the refusal is on the run "
    "record rather than carried back out of the graph. The run had spent nothing "
    "either way, which is why a no is the answer a restart can still honour in full"
)
"""The clause added to a decline that arrives after a restart.

Beside `_declined`'s sentence rather than replacing it: what the operator refused
and what it cost them is the same statement it would have been in the process that
asked, and this says only what is different about how it was recorded.
"""


class HaltRecovered(RuntimeError):
    """An answer arrived for a halt whose process has ended.

    Raised for every answer to a recovered halt, the honoured no included, and the
    reason is what the route can hand back: a `RunResponse` is built from a
    `RunRecord` — its plan, its counters, its presented estimate — and a recovered
    run has none of those (ADR-0034). So there is nothing to respond *with*, and the
    honest answer is a refusal that says what was recorded rather than a response
    assembled out of defaults.

    Carries the row it settled, so a caller can say which state the run is in
    without reading the database a second time.

    **Two sentences, because two different things happen and only one of them is an
    answer being recorded.** A halt still inside its hour takes the answer, and the
    refusal says the answer went onto the record instead of into the graph. A run
    that is already terminal — past its hour, or answered once already — takes
    nothing, and saying *the answer was recorded* of a request that was discarded
    would be the same class of false statement this module exists to remove, one
    branch over.
    """

    def __init__(self, recorded: RecordedRun, *, answered: bool) -> None:
        self.recorded = recorded
        self.answered = answered
        started = (
            f"run {recorded.run_id} was started by an earlier process of this bench "
            f"at {recorded.recorded_at.isoformat(timespec='seconds')}, and this "
            "process did not start it and holds no run state for it"
        )
        super().__init__(
            (
                f"{started}. Your answer was recorded against the run record rather "
                f"than carried into the graph: the run is {recorded.status}. "
                f"{recorded.statement}"
            )
            if answered
            else (
                f"{started}. It is {recorded.status} and no answer may be applied to "
                "it — an interrupt is answered once — so nothing was recorded for "
                f"this request. {recorded.statement}"
            )
        )


def _reconciled(row: RecordedRun, now: datetime) -> RecordedRun:
    """One row as it has to be read once its process is gone. `recovered`'s rule.

    A function rather than a method, because it is a statement about a row *this*
    process did not write and the row itself has no way to know that.
    """
    if row.status is RunStatus.RUNNING:
        return row.settled(RunStatus.FAILED, LOST_WITH_ITS_PROCESS)
    if row.status is RunStatus.AWAITING_APPROVAL and not row.answerable_at(now):
        return row.settled(RunStatus.UNANSWERED, PAST_ITS_HOUR)
    return row


def _text(stored: dict[str, Any], field: str) -> str:
    value = stored.get(field)
    if not isinstance(value, str) or not value:
        raise MalformedRecordedRun(
            f"a run record has to carry a {field}, and this row's is {value!r}"
        )
    return value


def _whole(stored: dict[str, Any], field: str) -> int:
    value = stored.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MalformedRecordedRun(
            f"{field} is a count of calls or cases, and this row's is {value!r}"
        )
    return value


def _moment(stored: dict[str, Any], field: str) -> datetime:
    """One stored instant, refused unless it is one and unless it is anchored.

    A naive datetime is refused rather than assumed to be UTC: `answerable_until`
    decides whether somebody may still answer a halt, and a comparison between an
    aware *now* and a naive deadline raises — so a row that lost its offset would
    turn every recovery into a `TypeError` at the route rather than here.
    """
    value = stored.get(field)
    if not isinstance(value, str):
        raise MalformedRecordedRun(
            f"{field} is an ISO-8601 instant, and this row's is {value!r}"
        )
    try:
        read = datetime.fromisoformat(value)
    except ValueError as unparseable:
        raise MalformedRecordedRun(
            f"{field} is an ISO-8601 instant and {value!r} is not one"
        ) from unparseable
    if read.tzinfo is None:
        raise MalformedRecordedRun(
            f"{field} is {value!r}, which names no time zone. A deadline that has "
            "to be compared with now cannot be read from an unanchored instant"
        )
    return read


def _status(stored: dict[str, Any]) -> RunStatus:
    value = stored.get("status")
    statuses: Sequence[str] = [str(member) for member in RunStatus]
    if not isinstance(value, str) or value not in statuses:
        raise MalformedRecordedRun(
            f"{value!r} is not one of the states a run can be in "
            f"({', '.join(statuses)})"
        )
    return RunStatus(value)


RECORDED_RUNS: Final = RecordedRuns.at()
"""The declared run records, at the declared location.

A module-level object for the reason `DECIDED_ROUTES` is one, and it is safe to be
one for the same reason: it holds a path and no connection, so an object constructed
at import owns nothing that anybody has to remember to close (ADR-0034, and
ADR-0028's rejection of "a global with a lifetime nobody closes" which this is
therefore not).
"""
