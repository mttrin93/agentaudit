"""The run around the halt: what outlives the process, and what deliberately does not.

#35 put the approval checkpoint on disk, and ADR-0028 said in as many words which
half of restart survival that was: the halt is durable, and the run record around it
was not. So a human who came back after a deploy and answered got a `KeyError` at
the route, against a bench that told them no run of that id was ever started — a
false statement about a run this bench had started, halted and estimated.

These tests are about the record rather than about the halt.
`test_approval_checkpoints.py` owns the checkpoint and nothing here changes it.

**Most of the assertions here are absences, and they are the point.** A restored
run has no counters, no plan, no result and no target, because none of those crossed
the serializer (ADR-0034) — so what is checked is that the surfaces which serve
those things still refuse a restored run rather than answering with a reconstruction
of it, and that the answer a human gets names what happened instead of denying it.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_type_hints

import pytest
from fastapi.testclient import TestClient

from backend.api import recorded as recorded_module
from backend.api.app import ReportRefusal, create_app
from backend.api.recorded import (
    DEFAULT_RUN_RECORD_PATH,
    RECORDED_RUNS,
    RUN_RECORD_DIRECTORY,
    HaltRecovered,
    MalformedRecordedRun,
    RecordedRun,
    RecordedRuns,
    RunDatabase,
)
from backend.api.run_config import BenchConfig, plan_for
from backend.api.runs import BenchRuns, RunRecord, RunsInFlight, RunStatus
from backend.bench.elective import NOTHING_REQUESTED
from backend.bench.library import Family, LibraryVersion, Transform
from backend.bench.selection import (
    EVERY_CONSTRUCTION,
    AttackLayer,
    AttackSelection,
)
from backend.graph import approval
from backend.graph.approval import Approval, ApprovalRun, checkpoint_kept
from backend.graph.runstate import RunState
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    REPOSITORY,
    a_budget,
    a_target,
    some_cases,
)

THREAD_WAIT_SECONDS = 10.0
"""How long a worker is given to finish with a record it is the only writer of.

`test_approval_checkpoints.py`'s bound and its reasoning: long enough that a loaded
machine is not a failure, short enough that a worker which never gets there is
reported rather than waited on.
"""

ANSWERABLE_SECONDS = 30.0
"""How long a run started by these tests stays answerable.

Shorter than the hour a real run is promised (`APPROVAL_WAIT_SECONDS`) because
nothing here waits it out, and long enough that a loaded machine is not a failure:
the halt has to still be open when the assertion two lines later reads it.
"""


def a_config(answerable_seconds: float = ANSWERABLE_SECONDS) -> BenchConfig:
    return BenchConfig(cases=some_cases(3), approval_wait_seconds=answerable_seconds)


@contextmanager
def a_bench(
    recorded: RecordedRuns,
    answerable_seconds: float = ANSWERABLE_SECONDS,
) -> Iterator[BenchRuns]:
    """A bench with no HTTP in front of it, and every halt it opened answered.

    Direct rather than through `create_app`, because what is under test is the
    registry: a route would add a second thing that could be the reason an answer
    did or did not reach a halt. The teardown declines rather than confirms — the
    halt is ahead of registration, so nothing has been sent and a decline ends the
    run without a call on anybody's endpoint.
    """
    bench = BenchRuns(a_config(answerable_seconds), recorded=recorded)
    try:
        yield bench
    finally:
        for record in bench.records():
            if record.status.in_flight:
                bench.answer(
                    record.run_id,
                    Approval(
                        confirmed=False,
                        identity="the suite",
                        reason="the test that started this run is over",
                    ),
                )


def a_run(bench: BenchRuns, nonce_planted: bool = False) -> RunRecord:
    """One halted run on that bench. No target is called: the halt is ahead of one."""
    return bench.start(
        target=a_target(),
        attestation=BENCH_ATTESTATION,
        nonce="",
        price=None,
        note_planted=False,
        nonce_planted=nonce_planted,
    )


def halted_at(thread_id: str, record: RunRecord) -> bool:
    """Whether a graph named by that thread id is paused, read off the database.

    Through `ApprovalRun.paused`, which is the public read of a halt, and against
    the database `run_under_approval` actually used — read off the module rather
    than off an import, because `conftest.py` redirects it per session.
    """
    with ApprovalRun(
        record.budget,
        lambda: None,
        thread_id=thread_id,
        checkpoints=approval.DEFAULT_CHECKPOINT_DATABASE,
    ) as reopened:
        return reopened.paused


# --- the record names the halt ---------------------------------------------------


@pytest.fixture
def recorded(tmp_path: Path) -> RecordedRuns:
    """This test's own run-record database, under a directory that is not there yet.

    Not there yet on purpose, on `test_approval_checkpoints.py`'s reasoning about
    the halt database: the store creates its own parent, and a fixture that pre-made
    it would hide a store that could only open a database beside an existing one.
    """
    return RecordedRuns.at(tmp_path / "runs" / "started.sqlite")


def test_the_record_names_the_halt_the_run_is_waiting_at(
    recorded: RecordedRuns,
) -> None:
    """ADR-0028 point 4 reaching the record that needs it.

    A checkpoint on disk is reachable only by something that can say which thread
    to look in, and for a run started through the API that name was minted inside
    `ApprovalRun.__init__` and never left the worker thread. So the durable halt
    was unreachable in exactly the case it was built for.

    Asserted by opening the halt rather than by comparing two strings: an id that
    matched a field and named no checkpoint would be a record that looked right.
    """
    with a_bench(recorded) as bench:
        record = a_run(bench)

        assert record.thread_id, "the record does not name the halt it is waiting at"
        assert halted_at(record.thread_id, record), (
            f"{record.thread_id!r} is on the record and names no halt on disk, so "
            "the id a restart would look the checkpoint up by is not the id the "
            "run halted under"
        )


def test_no_declared_input_moves_while_a_run_is_holding_its_halt(
    recorded: RecordedRuns,
) -> None:
    """Condition 2 of ADR-0025, at the one guard all three console writes share.

    A run awaiting approval has been shown an estimate built from the instruments, the
    families **and** the selection it was declared with, and ADR-0007's whole mechanism
    is that nothing exceeds what a human confirmed — so a change under an open halt
    would make the confirmation a statement about a run that never happened. The three
    writers refuse together because they refuse through one method
    (`_refuse_while_a_run_is_going`), and the refusal names the run so an operator can
    wait for it or decline it rather than guess.

    Asserted at the registry rather than at the routes, on `a_bench`'s reasoning: what
    is under test is the guard, and a route would add a second thing that could be the
    reason a change was refused. The routes' own job is to turn this into a `409`
    rather than a `422`, which is `test_api_settings.py`'s.
    """
    with a_bench(recorded) as bench:
        record = a_run(bench)
        held = bench.config

        narrowed = AttackSelection(
            layers=frozenset({AttackLayer.SINGLE_TURN}),
            transforms=frozenset({Transform.PLAIN}),
        )
        changes: tuple[Callable[[], None], ...] = (
            lambda: bench.cover(frozenset({Family.DATA_LEAKAGE}), NOTHING_REQUESTED),
            lambda: bench.select(narrowed),
        )
        for change in changes:
            with pytest.raises(RunsInFlight) as refused:
                change()
            assert record.run_id in str(refused.value)

        # And nothing moved on the way to either refusal: the run in flight is still
        # held to the configuration it was estimated against.
        assert bench.config is held
        assert bench.config.selection == EVERY_CONSTRUCTION

    # The halt answered, the write goes through. `a_bench` declines every run it
    # opened, so what this asserts is that the guard is about a run *in flight* and
    # not about a bench that has ever started one.
    bench.select(
        AttackSelection(
            layers=frozenset({AttackLayer.SINGLE_TURN}),
            transforms=frozenset({Transform.PLAIN}),
        )
    )
    assert bench.config.selection.scored == frozenset({Transform.PLAIN})


# --- the run around the halt is on disk ------------------------------------------


def test_a_run_is_on_disk_from_the_moment_it_halts(recorded: RecordedRuns) -> None:
    """The written record, at the one moment it has to exist: while the halt is open.

    Not at the end of the run — a run that recorded itself when it finished would
    be durable for exactly the states nobody needs to answer. `start` returns once
    the graph is holding its interrupt, so by the time it has returned the row is
    the thing a restarted process would find.

    Read back through a *second* `RecordedRuns` over the same file rather than off
    the one that wrote it, so the assertion is about the database and not about an
    object's memory (ADR-0019 point 4, ADR-0034).
    """
    with a_bench(recorded) as bench:
        record = a_run(bench)

        found = RecordedRuns.at(recorded.store.path).find(record.run_id)

        assert found is not None, (
            f"run {record.run_id} halted and nothing on disk says so, so a restarted "
            "process has no way to know the run it is holding a checkpoint for"
        )
        assert found.thread_id == record.thread_id, (
            "the row names a different halt from the record, so the checkpoint a "
            "restart would look up is not this run's"
        )
        assert found.status is RunStatus.AWAITING_APPROVAL
        assert found.statement == record.statement


# --- a halt this process did not start ------------------------------------------


def an_earlier_process_halted(
    recorded: RecordedRuns,
    run_id: str = "a-run-from-before",
    recorded_at: datetime | None = None,
    status: RunStatus = RunStatus.AWAITING_APPROVAL,
) -> RecordedRun:
    """One row on disk, as a process that has since ended left it.

    Built through `RecordedRun.of` off a constructed `RunRecord` rather than by
    listing fields, so the row is the same projection `start` writes — which
    `test_a_run_is_on_disk_from_the_moment_it_halts` is what proves. A real halted
    run is deliberately not used: the run this stands for is one whose thread is
    gone, and a live worker is the one thing this test must not have.
    """
    budget = a_budget(cases=3, targets=1)
    plan = plan_for(BenchConfig(cases=some_cases(3)), note_planted=True)
    record = RunRecord(
        run_id=run_id,
        thread_id=f"run-{run_id}",
        target=a_target(),
        attestation=BENCH_ATTESTATION,
        nonce="nonce",
        plan=plan,
        budget=budget,
        run_state=RunState(budget=budget, library=LibraryVersion.of(plan.cases)),
        presented=budget.as_payload(),
        recorded_at=recorded_at or datetime.now(tz=UTC),
        status=status,
    )
    row = RecordedRun.of(record, ANSWERABLE_SECONDS)
    recorded.record(row)
    return row


def a_restarted_bench(recorded: RecordedRuns) -> BenchRuns:
    """A bench that has this database and none of the runs in it in memory.

    Which is what a restarted process is: `create_app` builds one of these, and the
    rows it finds were written by something that is gone. No teardown, because it
    started nothing — every run it knows about is a row.
    """
    return BenchRuns(a_config(), recorded=recorded)


def test_a_recovered_halt_can_still_be_declined(recorded: RecordedRuns) -> None:
    """The half of an answer that survives a restart, and it is the whole of a no.

    A refusal needs no target, no credential and no graph: the run had spent
    nothing, and a figure a user refused is the one piece of evidence that the cost
    display is doing its job (`Approval.reason`). So it is recorded as `DECLINED`
    rather than folded into whatever a lost run is — losing the difference between
    *refused by a human* and *nobody answered* is the exact distinction ADR-0028
    was built to preserve.
    """
    row = an_earlier_process_halted(recorded)
    bench = a_restarted_bench(recorded)

    with pytest.raises(HaltRecovered) as refused:
        bench.answer(
            row.run_id,
            Approval(
                confirmed=False, identity="operator", reason="too expensive today"
            ),
        )

    assert "too expensive today" in str(refused.value)
    found = RecordedRuns.at(recorded.store.path).find(row.run_id)
    assert found is not None
    assert found.status is RunStatus.DECLINED, (
        f"a refusal after a restart was recorded as {found.status}, so a run a human "
        "said no to is indistinguishable from one nobody answered"
    )


def test_a_recovered_halt_cannot_be_confirmed_and_is_not_unanswered(
    recorded: RecordedRuns,
) -> None:
    """A yes is refused, and the record says *answered and not run*.

    Refused because the bench no longer holds what the run would need: a
    `TargetConfig` carries the endpoint and its bearer token, and the record carries
    a digest of the endpoint and never the endpoint (ADR-0008, ADR-0034).

    The status is the assertion that matters. `UNANSWERED` would say nobody
    answered, of a run somebody came back and confirmed; `DECLINED` would say they
    refused it. Both are false, and both are the reporting hazard #35 named — so
    the outcome is `FAILED`, which is the state this vocabulary already keeps for a
    run that stopped without being a reading about the target.
    """
    row = an_earlier_process_halted(recorded)
    bench = a_restarted_bench(recorded)

    with pytest.raises(HaltRecovered) as refused:
        bench.answer(row.run_id, Approval(confirmed=True, identity="operator"))

    said = str(refused.value)
    assert "nothing was spent" in said.lower(), (
        "the refusal does not tell the operator that their confirmation cost them "
        f"nothing, which is the first thing they need to know: {said}"
    )
    found = RecordedRuns.at(recorded.store.path).find(row.run_id)
    assert found is not None
    assert found.status is RunStatus.FAILED
    assert found.status not in {RunStatus.UNANSWERED, RunStatus.DECLINED}
    assert found.confirmed_by == "operator", (
        "the record does not say who answered, so a run somebody confirmed and "
        "could not run reads as one nobody was ever asked about"
    )


def test_a_run_nothing_recorded_is_named_as_one_this_bench_never_started(
    recorded: RecordedRuns,
) -> None:
    """The one case that is still a `KeyError`, and it is the honest one.

    A `KeyError` used to be what a human got for a run this bench *had* started,
    which made the route's own 404 wording a false statement. It is right for an id
    nothing was ever written under, and nothing else may reach it.
    """
    bench = a_restarted_bench(recorded)

    with pytest.raises(KeyError):
        bench.answer("no-such-run", Approval(confirmed=False, identity="operator"))


# --- what the route tells the human who answers ----------------------------------


@contextmanager
def a_restarted_api(recorded: RecordedRuns) -> Iterator[TestClient]:
    """The API over a bench whose runs are all rows. `conftest` put the store here.

    `create_app` is given no store, because the point is the one a deployment gets:
    the autouse redirection in `conftest.py` moves `RECORDED_RUNS` for the test, and
    a bench handed its own store would be testing the injection rather than the
    default.
    """
    with TestClient(create_app(a_config())) as client:
        yield client


def test_the_route_tells_a_human_what_happened_instead_of_denying_the_run(
    recorded: RecordedRuns,
) -> None:
    """The whole of the human-facing defect, at the surface a human meets it.

    Before this, the answer to a halt whose process had restarted was a `404` whose
    body said no run of that id had been started by this bench — a false statement
    about a run it had started, halted and estimated, and the last thing a person
    holding a run URL can do anything with.

    A `409` rather than a `404` because the run is there and the answer is what
    cannot be applied, and rather than a `200` because a `RunResponse` is built from
    a plan and counters a recovered run does not have (ADR-0034).
    """
    row = an_earlier_process_halted(RecordedRuns.at())

    with a_restarted_api(recorded) as client:
        answered = client.post(
            f"/runs/{row.run_id}/approval",
            json={"confirmed": True, "identity": "operator", "reason": ""},
        )

    assert answered.status_code == 409, answered.text
    detail = answered.json()["detail"]
    assert "earlier process" in detail, (
        f"the answer does not say the run outlived its process: {detail}"
    )
    assert "nothing was spent" in detail.lower(), (
        f"the answer does not say the confirmation cost nothing: {detail}"
    )


def test_progress_on_a_recovered_run_names_it_rather_than_denying_it(
    recorded: RecordedRuns,
) -> None:
    """The same false statement, on the route an operator polls.

    Still a `404`, because there is no progress to report: the counters were
    `RunState`'s and they did not cross the serializer. What changes is that the
    body says which run this is and what the record says about it, so a poller can
    stop rather than read *never started* for a run they have the id of.
    """
    row = an_earlier_process_halted(RecordedRuns.at())

    with a_restarted_api(recorded) as client:
        polled = client.get(f"/runs/{row.run_id}")

    assert polled.status_code == 404
    detail = polled.json()["detail"]
    assert "earlier process" in detail and str(row.status) in detail, (
        f"the refusal does not name the run it is refusing to report on: {detail}"
    )


# --- the hour is a deadline in a record, not a wait ------------------------------


def test_a_halt_past_its_hour_is_unanswered_and_stays_unanswered(
    recorded: RecordedRuns,
) -> None:
    """`APPROVAL_WAIT_SECONDS` promised an hour and spent it in an `Event.wait()`.

    Across a restart there is no thread holding that wait and nothing to wake, so
    the hour is on the record as an instant and read rather than waited out. What
    that has to produce is the outcome the wait produced — `UNANSWERED`, nobody
    said no and nobody said anything — and it has to produce it for somebody who
    arrives with a yes, because a confirmation an hour late is consent for a run
    the graph was already told nobody authorised (`PendingApproval.answer`).
    """
    row = an_earlier_process_halted(
        recorded,
        recorded_at=datetime.now(tz=UTC) - timedelta(seconds=ANSWERABLE_SECONDS * 2),
    )
    bench = a_restarted_bench(recorded)

    reconciled = RecordedRuns.at(recorded.store.path).find(row.run_id)
    assert reconciled is not None
    assert reconciled.status is RunStatus.UNANSWERED, (
        f"a halt {ANSWERABLE_SECONDS * 2}s past a {ANSWERABLE_SECONDS}s deadline is "
        f"{reconciled.status}, so the hour is still only the wait a dead process was "
        "holding"
    )

    with pytest.raises(HaltRecovered):
        bench.answer(row.run_id, Approval(confirmed=True, identity="operator"))

    after = RecordedRuns.at(recorded.store.path).find(row.run_id)
    assert after is not None
    assert after.status is RunStatus.UNANSWERED, (
        f"a yes past the deadline moved the record to {after.status}, so a "
        "confirmation nobody may act on was recorded as one somebody did"
    )
    assert not after.confirmed_by


def test_a_row_left_running_is_not_a_run_still_going(recorded: RecordedRuns) -> None:
    """The reconciliation that is not optional, and what it costs to skip it.

    `RunStatus.in_flight` calls `RUNNING` still going. A row left saying so is a
    run nothing is driving, and it would keep saying it for the lifetime of the
    deployment: `instrument` and `cover` refuse an operator while any run is in
    flight, so a single row from a killed process would refuse every settings
    change for ever, on behalf of a process that no longer exists.

    `FAILED` and not `ABORTED`: a run stopped by its own ceiling is the budget
    working, and this run was stopped by its process ending. Nor is it a partial
    reading — the counters belonged to `RunState` and did not cross (ADR-0034).
    """
    row = an_earlier_process_halted(recorded, status=RunStatus.RUNNING)
    bench = a_restarted_bench(recorded)

    found = bench.recovered(row.run_id)
    assert found is not None
    assert found.status is RunStatus.FAILED
    assert not found.status.in_flight

    # The consequence, asserted rather than argued: a settings change is not
    # refused on behalf of a run whose process has ended.
    bench.cover(frozenset(Family), NOTHING_REQUESTED)
    assert bench.config.families == frozenset(Family)


# --- the checkpoint is kept only while its run can be answered -------------------


def a_halt_on_disk(thread_id: str) -> None:
    """One checkpoint under that thread id, in the database a real run would use.

    Through `ApprovalRun` and not by writing a row, because what retention has to
    delete is whatever LangGraph actually wrote — a fixture that hand-made a row
    would prove that this code can delete its own shape.
    """
    with ApprovalRun(
        a_budget(cases=3, targets=1),
        lambda: None,
        thread_id=thread_id,
        checkpoints=approval.DEFAULT_CHECKPOINT_DATABASE,
    ) as run:
        run.present()


def test_a_halt_is_forgotten_when_its_run_can_no_longer_be_answered(
    recorded: RecordedRuns,
) -> None:
    """ADR-0028 left `/checkpoints/` growing without bound and nothing pruning it.

    Nothing *could* prune it: the halt is reachable only by thread id, and no run
    record carried one. It does now, so retention is decided by the record rather
    than by a timer — a checkpoint is kept exactly as long as the run it belongs
    to can still be answered, and deleted when it cannot.

    The identity is why this matters rather than being housekeeping. A checkpoint
    holds `ApprovalState`, and `identity` is who authorised the spend, so a
    directory of halts nobody can answer is a directory of names at rest
    (ADR-0008).
    """
    with a_bench(recorded) as bench:
        record = a_run(bench)
        assert checkpoint_kept(
            record.thread_id, approval.DEFAULT_CHECKPOINT_DATABASE
        ), "the run did not halt, so this test would pass on a bench that never wrote"

        bench.answer(
            record.run_id,
            Approval(confirmed=False, identity="operator", reason="not today"),
        )
        record.finished.wait(THREAD_WAIT_SECONDS)

    assert not checkpoint_kept(
        record.thread_id, approval.DEFAULT_CHECKPOINT_DATABASE
    ), (
        "the halt of a run that has ended is still on disk, so /checkpoints/ keeps "
        "the identity of whoever authorised a spend for as long as the volume lasts"
    )


def test_a_stale_halt_and_the_name_on_it_are_forgotten_when_a_bench_starts(
    recorded: RecordedRuns,
) -> None:
    """The half retention could not reach before: a halt whose process is gone.

    Nobody answers it, so nothing on the run's own path ever settles it, and its
    checkpoint would be kept until somebody deleted the file by hand — which is
    ADR-0028's consequence in as many words. A bench that reconciles a row past its
    hour is the one thing that knows the halt is over, and it knows which thread to
    delete because the row says so.
    """
    row = an_earlier_process_halted(
        recorded,
        recorded_at=datetime.now(tz=UTC) - timedelta(seconds=ANSWERABLE_SECONDS * 2),
    )
    a_halt_on_disk(row.thread_id)
    assert checkpoint_kept(row.thread_id, approval.DEFAULT_CHECKPOINT_DATABASE)

    a_restarted_bench(recorded)

    assert not checkpoint_kept(row.thread_id, approval.DEFAULT_CHECKPOINT_DATABASE), (
        "a halt past its hour is answerable by nobody and its checkpoint is still "
        "there, holding the estimate a person was asked to confirm"
    )


# --- the file is user data, and the suite does not touch the real one -----------


@pytest.mark.parametrize(
    "name", ["started.sqlite", "started.sqlite-wal", "started.sqlite-shm"]
)
def test_the_run_records_and_their_sidecars_are_ignored_by_git(name: str) -> None:
    """ADR-0008, on the reasoning `/checkpoints/` and `/decisions/` are ignored on.

    A row carries who attested, who confirmed the spend, the name the operator gave
    their target and a digest of its endpoint. That is user data at rest whether or
    not it is a URL, and the sidecars are parametrised rather than assumed covered
    by the database's own pattern: WAL writes two files beside it, and a journal
    left behind must not be the first approver identity this repository carries.

    Asked of git rather than of `.gitignore`'s text, because what decides whether a
    file would be committed is git's answer and not a pattern that looks right
    (`test_precedent.py`, `test_decided.py`, both of which ask it this way).

    Built from `RUN_RECORD_DIRECTORY` rather than from the default path, because
    `conftest.py` redirects the database and never the directory constant.
    """
    if not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout, so git's own answer cannot be asked for")

    path = RUN_RECORD_DIRECTORY / name
    checked = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPOSITORY, check=False
    )

    assert checked.returncode == 0, (
        f"{path} is not ignored by git, so who authorised a run against somebody "
        "else's endpoint is one `git add` away from being published"
    )


def test_no_test_writes_the_run_records_a_real_deployment_uses(
    tmp_path: Path,
) -> None:
    """`conftest.run_records_elsewhere`, asserted rather than trusted.

    Two things have to hold and only one is visible from *it is not the real file*.
    No test reaches the engineer's own records — otherwise every `create_app` in the
    suite would recover their halted runs and settle them. And no test reads
    another's, which is what keeps the suite's result independent of its order,
    because a `BenchRuns` reconciles every row it finds.

    Read off the module and off the shared object, because those are the two routes
    `_run_records_at` has to have covered: a freshly built store reads the constant,
    and `BenchRuns`' default argument captured the object at import.
    """
    for live in (recorded_module.DEFAULT_RUN_RECORD_PATH, RECORDED_RUNS.store.path):
        assert live != DEFAULT_RUN_RECORD_PATH, (
            "a test can reach the run records a real deployment uses, so the suite "
            "recovers and settles the engineer's own halted runs"
        )
        assert live.is_relative_to(tmp_path), (
            f"the run records are at {live}, which is not this test's own directory. "
            "A row one test wrote is a run the next test's bench recovers"
        )


READ_BACK = """
import sys
from pathlib import Path

from backend.api.recorded import RUN_NAMESPACE, RecordedRun, RunDatabase

found = RunDatabase(Path(sys.argv[1])).get(RUN_NAMESPACE, sys.argv[2])
run = RecordedRun.read(dict(found.value))
print(run.run_id)
print(run.thread_id)
print(run.status)
print(run.answerable_until.isoformat())
"""
"""A reader, as a program, because ADR-0019 point 4 says *in a new process*.

The test below writes the row and this reads it back, so what crosses is the file
and nothing else: no object, no import-time cache, no module state the writer left
behind. `test_decided.py` and `test_precedent.py` make the same argument for the
other two durable stores, and the argument is what says the object-level tests
above are not the whole claim.
"""

A_READER_HAS_FINISHED = 60.0
"""Seconds the reader gets to open a local database and print four lines.

Generous, because what it protects against is a hang rather than slowness: a reader
that took longer is one waiting for a lock nothing holds, and the test should say so
rather than run until CI gives up. `test_decided.py`'s bound and its reasoning.
"""


def test_a_run_record_outlives_the_whole_interpreter(recorded: RecordedRuns) -> None:
    """ADR-0019 point 4, at the boundary that cannot be faked.

    The tests above drop the `RecordedRuns` object and rebuild it against the same
    file; this drops the interpreter. Both are needed and this is the stronger: a
    registry that had quietly kept its rows in a module-level dictionary would
    satisfy the first and fail this — and that dictionary is exactly what
    `BenchRuns` used to be.

    The deadline is one of the four values asserted, because it is the field a
    restart most depends on and the one most easily lost to a serializer: an instant
    that came back naive would compare against nothing.
    """
    row = an_earlier_process_halted(recorded)

    reader = subprocess.run(
        [sys.executable, "-c", READ_BACK, str(recorded.store.path), row.run_id],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=A_READER_HAS_FINISHED,
    )

    assert reader.returncode == 0, (
        f"a new process could not read the run back:\n{reader.stderr}"
    )
    assert reader.stdout.splitlines() == [
        row.run_id,
        row.thread_id,
        str(RunStatus.AWAITING_APPROVAL),
        row.answerable_until.isoformat(),
    ]


def test_what_crosses_the_serializer_is_still_a_declaration(
    recorded: RecordedRuns,
) -> None:
    """ADR-0034's whole argument, asserted as a set rather than field by field.

    `ApprovalState`'s own assertion, one kind of state out: a real serializer makes
    widening this more tempting, not less, and a checkpoint — or a run record — is
    not the place to discover which of a run's records happen to survive one. So an
    addition fails rather than passing unnoticed, and whoever adds it has to decide
    whether the thing they are adding is a declaration about a run or a measurement
    taken by one.

    The two absences named in the message are the two that would be most useful and
    are most clearly refused: `RunState` because a second copy of a run's counters
    can disagree with the counters, and `TargetConfig` because it carries the
    operator's endpoint and its bearer token (ADR-0008).
    """
    assert get_type_hints(RecordedRun) == {
        "run_id": str,
        "thread_id": str,
        "recorded_at": datetime,
        "answerable_until": datetime,
        "status": RunStatus,
        "statement": str,
        "confirmed_by": str,
        "target": str,
        "endpoint_hash": str,
        "attested_by": str,
        "library": LibraryVersion,
        "scored_ceiling": int,
        "adaptive_ceiling": int,
        "currency": str,
        "proof_waived": bool,
    }, (
        "a field was added to or removed from the durable run record. A run state, "
        "a plan, a calibration result or a target config here would be a run "
        "rebuilt from whatever survived a serializer, which is what ADR-0034 "
        "refuses — and a `TargetConfig` would put an endpoint and its credential in "
        "a file at rest (ADR-0008)"
    )


def test_a_row_that_will_not_read_is_loud_and_never_an_absent_run(
    recorded: RecordedRuns,
) -> None:
    """The reporting hazard #35 named, arriving from the other side.

    A row outlives the process that wrote it, so a package upgrade, a hand edit or a
    database restored from somewhere else can produce one this code did not write.
    Answering `None` for it would tell a human that the run they are holding a URL
    for was never started — which is exactly the reading ADR-0028 put the checkpoint
    on disk to prevent. So it raises, and a bench cannot serve a run it cannot read
    about as one that does not exist.

    Written through the store rather than by editing a file, so the row is one the
    real read path fetches: what is under test is `find`, not `read`.
    """
    row = an_earlier_process_halted(recorded)
    recorded.store.put(
        recorded.namespace, row.run_id, {**row.stored(), "status": "nearly finished"}
    )

    with pytest.raises(MalformedRecordedRun):
        recorded.find(row.run_id)


# --- what the review found, kept from coming back --------------------------------


def test_a_finished_run_is_not_dragged_back_to_running_by_the_request(
    recorded: RecordedRuns,
) -> None:
    """`RecordedRuns.record` refuses the backward write, asserted rather than argued.

    Two threads write one run's row: the worker that finishes it, and the request
    that confirmed it — and the request writes `RUNNING` *after* releasing the
    graph, because the release has to happen inside the guard that catches a second
    answer. A suite short enough to finish in between would leave the row saying
    `running` for a run that had completed, and the reconciliation would then report
    a finished run as one that stopped part-way.

    Driven directly rather than by racing two threads, because the assertion is
    about the rule and not about a timing: a rule that only holds when the interleave
    is unlucky is not a rule anybody can rely on.
    """
    row = an_earlier_process_halted(recorded)
    recorded.record(row.settled(RunStatus.COMPLETED, "the run finished"))

    recorded.record(row.settled(RunStatus.RUNNING, "the suite is running"))

    found = RecordedRuns.at(recorded.store.path).find(row.run_id)
    assert found is not None
    assert found.status is RunStatus.COMPLETED, (
        "a completed run was written back as running, so a restart would reconcile "
        "it to failed and report a finished run as one that stopped part-way"
    )


def test_an_hour_that_runs_out_while_the_bench_is_up_forgets_the_halt(
    recorded: RecordedRuns,
) -> None:
    """The retention case boot-time pruning cannot reach.

    A halt whose process ended is settled by nobody, so an expiry that happens
    *while* this bench is running is observed by nothing unless a read observes it.
    Left there, the approver identity in the checkpoint outlives the run's
    answerability until the next restart — which is decision 8's rule broken by the
    one path that has no restart in it.

    The bench is built while the halt is still answerable, so the construction-time
    prune deliberately does *not* apply: what is under test is the read afterwards.
    """
    row = an_earlier_process_halted(recorded)
    a_halt_on_disk(row.thread_id)
    bench = a_restarted_bench(recorded)
    assert checkpoint_kept(row.thread_id, approval.DEFAULT_CHECKPOINT_DATABASE), (
        "the halt was pruned at construction, so this test is not exercising the "
        "expiry it exists for"
    )

    recorded.record(
        replace(row, answerable_until=datetime.now(tz=UTC) - timedelta(seconds=1))
    )
    found = bench.recovered(row.run_id)

    assert found is not None and found.status is RunStatus.UNANSWERED
    assert not checkpoint_kept(row.thread_id, approval.DEFAULT_CHECKPOINT_DATABASE), (
        "an hour that ran out while this bench was up left the checkpoint on disk, "
        "so the name of whoever would have authorised the spend outlives the run"
    )


def test_a_halt_that_takes_no_answer_is_not_told_that_it_did(
    recorded: RecordedRuns,
) -> None:
    """The false statement one branch over from the one this ticket was filed about.

    An answer to a run that is already terminal is discarded — correctly, because an
    interrupt is answered once. What the refusal must not do is say *your answer was
    recorded*, of a request nothing was recorded for: telling an operator their
    confirmation is on the record when it was thrown away is the same class of thing
    as telling them their run was never started.
    """
    row = an_earlier_process_halted(recorded, status=RunStatus.COMPLETED)
    bench = a_restarted_bench(recorded)

    with pytest.raises(HaltRecovered) as refused:
        bench.answer(row.run_id, Approval(confirmed=True, identity="operator"))

    assert not refused.value.answered
    said = str(refused.value)
    assert "nothing was recorded for this request" in said, (
        f"the refusal claims an answer was recorded and none was: {said}"
    )
    after = RecordedRuns.at(recorded.store.path).find(row.run_id)
    assert after is not None
    assert after.status is RunStatus.COMPLETED and not after.confirmed_by


def test_the_report_route_names_a_recovered_run_rather_than_denying_it(
    recorded: RecordedRuns,
) -> None:
    """The third route that said *no run of that id was started by this bench*.

    A recovered run's artefact was built once by the run that made it and held in
    that process, so a restart takes the bytes with it — and nothing may be
    reassembled in their place, because a signature is over one document rather than
    over a recipe for making one (`report.py`, #56). That is a fifth reason for
    there to be no report and none of the four names above states it truly, which is
    why this one is `lost_with_its_process` and not `no_such_run`.
    """
    row = an_earlier_process_halted(RecordedRuns.at(), status=RunStatus.COMPLETED)

    with a_restarted_api(recorded) as client:
        asked = client.get(f"/report/{row.run_id}")

    assert asked.status_code == 404
    refusal = asked.json()["detail"]
    assert refusal["outcome"] == str(ReportRefusal.LOST_WITH_ITS_PROCESS), refusal
    assert "earlier process" in refusal["statement"], refusal


A_SECOND_ANSWER_HAS_TRIED = 1.0
"""How long the first answer waits for a second one to reach the store.

Deterministic in both directions, which is the point. Without the lock the second
request reaches `find` at once and the wait ends immediately, so two answers are
honoured every time rather than on an unlucky interleave. With the lock the second
request is still blocked acquiring it, so this wait runs out — and a second's delay
in one test is the price of a guard that does not depend on timing to catch its bug.
"""


@dataclass(frozen=True)
class Contended(RecordedRuns):
    """A store that lets the test choose the interleave of two answers.

    The blocking is in `find` rather than in `record`, because what has to be
    interleaved is the *check* and not the write: `_answer_a_recovered_halt` reads
    the row, decides it is answerable, and only then writes, so a second request
    that got past the read before the first wrote is the failure being driven.

    Threads are told apart by name rather than by a counter, so nothing here has a
    race of its own.
    """

    inside: threading.Event = field(default_factory=threading.Event)
    followed: threading.Event = field(default_factory=threading.Event)

    def find(self, run_id: str) -> RecordedRun | None:
        if threading.current_thread().name == FIRST_ANSWER:
            self.inside.set()
            self.followed.wait(A_SECOND_ANSWER_HAS_TRIED)
        else:
            self.followed.set()
        return super().find(run_id)


FIRST_ANSWER = "the-first-answer"


def test_a_recovered_halt_takes_one_answer_and_not_two(tmp_path: Path) -> None:
    """An interrupt is answered once, and there is no `PendingApproval` to say so.

    The live path gets this from `PendingApproval.answer`, which takes a lock so
    that a confirmation landing in the instant the wait closes is either taken or
    refused and never both. A recovered halt has no rendezvous — that is the whole
    of what a restart destroys — so without a lock of its own, two requests reading
    an answerable row at the same moment would both write and both be told their
    answer was recorded: a decline and a confirmation recorded for one halt, which
    is the distinction ADR-0028 exists to keep, lost in a new way.
    """
    store = Contended(store=RunDatabase(tmp_path / "runs" / "started.sqlite"))
    row = an_earlier_process_halted(store)
    bench = a_restarted_bench(store)
    outcomes: list[HaltRecovered] = []

    def answer(identity: str, confirmed: bool) -> None:
        try:
            bench.answer(
                row.run_id,
                Approval(confirmed=confirmed, identity=identity, reason="mine"),
            )
        except HaltRecovered as refused:
            outcomes.append(refused)

    first = threading.Thread(target=answer, args=("first", True), name=FIRST_ANSWER)
    first.start()
    assert store.inside.wait(THREAD_WAIT_SECONDS), "the first answer never got in"
    second = threading.Thread(target=answer, args=("second", False), name="the-second")
    second.start()
    for thread in (first, second):
        thread.join(THREAD_WAIT_SECONDS)
        assert not thread.is_alive()

    assert len(outcomes) == 2, "both requests should have been refused by name"
    taken = [refused for refused in outcomes if refused.answered]
    assert len(taken) == 1, (
        f"{len(taken)} of two answers to one recovered halt were recorded. An "
        "interrupt is answered once, and both requests were told theirs was taken"
    )
    found = RecordedRuns.at(store.store.path).find(row.run_id)
    assert found is not None
    assert found.status is taken[0].recorded.status
