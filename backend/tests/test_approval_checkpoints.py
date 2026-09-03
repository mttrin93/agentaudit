"""The halt on disk: a run paused at the interrupt outlives the object that paused it.

`APPROVAL_WAIT_SECONDS` promises the human an hour to answer, and an hour is exactly
the window a deploy, a crash or a `--reload` lands in. A checkpointer that lives in
the process makes that promise false and makes the failure unreportable: the run the
human answers is gone, and the outcome is indistinguishable from the one the code
names *unanswered* — nobody said no, nobody said anything.

So these tests are about the checkpoint rather than about the decision. What the
interrupt presents and what it decides is `test_authorisation.py`'s subject and
nothing here changes it.

Two of them drive paths a single-threaded unit test cannot reach: the object that
halted the run is destroyed before anything answers, and the answer arrives on a
thread that did not invoke the graph. Both are the shape the API runs in, and a
saver that passes the convenient path and raises under the API is the whole reason
this file exists.
"""

from __future__ import annotations

import ast
import sqlite3
import subprocess
import threading
from contextlib import closing
from pathlib import Path
from typing import get_type_hints

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from backend.graph import approval
from backend.graph.approval import (
    CHECKPOINT_DIRECTORY,
    Approval,
    ApprovalRun,
    ApprovalState,
    approval_checkpoints,
)
from backend.graph.approval import __doc__ as APPROVAL_DOC
from backend.tests.conftest import a_budget

REPOSITORY = Path(__file__).resolve().parents[2]
APPROVAL_SOURCE = REPOSITORY / "backend" / "graph" / "approval.py"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """A halt database of this test's own, under a directory that is not there yet.

    Not there yet on purpose: `approval_checkpoints` creates the parent, and a
    fixture that pre-made it would hide a saver that could only open a database
    beside an existing one.
    """
    return tmp_path / "checkpoints" / "halts.sqlite"


THREAD_WAIT_SECONDS = 10.0
"""Long enough that a loaded machine is not a failure, short enough that a worker
which never reaches the halt is reported rather than waited on."""


def a_yes() -> Approval:
    return Approval(confirmed=True, identity="operator")


# --- the halt survives the object that halted it --------------------------------


def test_a_halted_run_is_resumed_after_the_object_that_halted_it_is_gone(
    database: Path,
) -> None:
    """ADR-0019's restart test, applied to the checkpoint instead of the store.

    Write, drop the object, construct a new one against the same location, and
    finish the run. The interesting assertion is the second `paused`: it is read
    off the database by a graph that has never invoked anything, so a saver that
    kept the halt in the process would report a run that had not started rather
    than one waiting on a human.
    """
    ran: list[str] = []
    budget = a_budget()

    halted = ApprovalRun(budget, lambda: ran.append("suite"), checkpoints=database)
    thread = halted.thread_id
    halted.present()
    assert halted.paused
    halted.close()
    del halted

    resumed = ApprovalRun(
        budget,
        lambda: ran.append("suite"),
        checkpoints=database,
        thread_id=thread,
    )
    assert resumed.paused, (
        "a new object against the same database does not see the halt, so the "
        "checkpoint died with the process that wrote it"
    )

    final = resumed.resume(a_yes())
    resumed.close()

    assert final["confirmed"]
    assert final["identity"] == "operator"
    assert ran == ["suite"]


def test_leaving_the_with_block_releases_the_connection_and_not_the_halt(
    database: Path,
) -> None:
    """Both halves, because releasing the halt too would be the easy mistake.

    `ApprovalRun` owns an OS resource now, so it is a context manager — and the
    thing a reader has to be able to trust about that is that the `with` gives back
    a file handle and not the run. Asserted through the public surface: the closed
    object refuses to answer, and a new one on the same thread id still sees the
    halt waiting.
    """
    with ApprovalRun(a_budget(), lambda: None, checkpoints=database) as run:
        run.present()
        assert run.paused
    thread = run.thread_id

    with pytest.raises(sqlite3.ProgrammingError):
        assert run.paused

    with ApprovalRun(
        a_budget(), lambda: None, checkpoints=database, thread_id=thread
    ) as reopened:
        assert reopened.paused, "the `with` took the halt with it, not just the handle"


# --- the halt and the answer are on different threads ---------------------------


def test_the_answer_reaches_a_graph_another_thread_halted(database: Path) -> None:
    """The shape `api/runs.py` actually runs in, which no convenient test reaches.

    A FastAPI background task starts after its response is sent, so a run has to be
    *already halted* when the response is built and the request rendezvouses with
    it — which is why a run gets its own OS thread (`api/runs.py`, its docstring on
    the thread). Two threads therefore reach one graph: the worker that invoked it
    to the halt, and whatever thread carries the answer back.

    `sqlite3` refuses a connection used off its creating thread unless told
    otherwise, and the sync `SqliteSaver` holds one connection. So a saver that is
    only ever driven from one thread is a saver whose ownership decision has not
    been tested, and the failure it hides is a `ProgrammingError` raised under the
    API and never in the suite. This drives the two-thread path instead.
    """
    ran: list[str] = []
    halted: list[ApprovalRun] = []
    raised: list[BaseException] = []

    def halt_on_a_thread_of_its_own() -> None:
        try:
            run = ApprovalRun(
                a_budget(),
                lambda: ran.append(threading.current_thread().name),
                checkpoints=database,
            )
            halted.append(run)
            run.present()
        except BaseException as error:  # noqa: BLE001 - reported, not handled
            raised.append(error)

    worker = threading.Thread(target=halt_on_a_thread_of_its_own, name="the-worker")
    worker.start()
    worker.join(THREAD_WAIT_SECONDS)

    assert not worker.is_alive(), "the worker never reached the halt"
    assert not raised, f"the worker could not halt its own run: {raised}"
    run = halted[0]

    # From here on it is this thread, which did not open the connection and did not
    # invoke the graph. Both a read and a write of the checkpoint cross the boundary.
    assert run.paused
    final = run.resume(a_yes())
    run.close()

    assert final["confirmed"]
    assert threading.current_thread().name != "the-worker"
    assert ran == [threading.current_thread().name], (
        "the suite ran somewhere other than the thread that answered, so this test "
        "is not exercising the boundary it exists for"
    )


# --- a checkpoint holds a person's name -----------------------------------------


@pytest.mark.parametrize(
    "name", ["approvals.sqlite", "approvals.sqlite-wal", "approvals.sqlite-shm"]
)
def test_the_checkpoint_database_and_its_sidecars_are_ignored_by_git(
    name: str,
) -> None:
    """ADR-0008, on the reasoning `/precedent/` is ignored on.

    `ApprovalState` is `confirmed | identity | reason`, and `identity` is who
    authorised the spend — so the database is user data at rest. The sidecars are
    parametrised rather than assumed covered by the database's own pattern: WAL
    writes two files beside it, and a journal left behind must not become the first
    approver identity this repository carries.

    Asked of git rather than of `.gitignore`'s text, because what decides whether a
    file would be committed is git's answer and not a pattern that looks right
    (`test_precedent.py`, which asks the same question the same way).

    Built from `CHECKPOINT_DIRECTORY` rather than from the default database,
    because this is the one question in the file that is about the real location:
    `conftest.py`'s fixture redirects the database and never the directory
    constant, so deriving the path from the default would ask git about a
    temporary directory the moment somebody read it off the module.
    """
    if not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout, so git's own answer cannot be asked for")

    path = CHECKPOINT_DIRECTORY / name
    checked = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=REPOSITORY,
        check=False,
    )
    assert checked.returncode == 0, (
        f"{path} is not ignored by git, so the name of whoever authorised the next "
        "run's spend is one `git add` away from being published"
    )


# --- the saver is durable, and the module says how it is owned -------------------


def test_the_checkpointer_is_a_durable_saver_and_the_type_says_so(
    database: Path,
) -> None:
    """The prohibition ADR-0019 point 2 states, applied to the checkpoint.

    A memory saver is the right thing for a unit test and may not be what a run
    uses, because a halt that dies with the process makes `api/runs.py`'s hour
    false. Carried by the annotation, so the substitution is a type error before it
    is a test failure — and by the import list, because the failure mode is
    somebody reaching for the quickstart's saver.

    Direct imports rather than transitive reachability, deliberately: `langgraph.
    graph` reaches `InMemorySaver` itself, so a transitive assertion here could
    only ever be false and would say nothing about this module.
    """
    saver = approval_checkpoints(database)
    with closing(saver.conn):
        assert get_type_hints(approval_checkpoints)["return"] is SqliteSaver
        assert isinstance(saver, SqliteSaver)

    imported = _imported_names(APPROVAL_SOURCE)
    memory = [
        name for name in imported if "checkpoint.memory" in name or "InMemory" in name
    ]
    assert not memory, (
        f"{memory} is imported by the approval graph. A per-process checkpointer is "
        "a halt that does not survive the hour the human was promised"
    )


def test_the_module_says_which_thread_owns_the_connection() -> None:
    """The ownership decision is written down where the reader of it will be.

    Two threads reach one graph and `sqlite3` connections are not shareable across
    threads by default, so *who owns the connection* is the question this module
    had to answer. An answer that lives only in a commit message is one the next
    reader has to rediscover from a `ProgrammingError`.
    """
    # Whitespace collapsed, because a docstring is wrapped to a line length and a
    # phrase that straddles a wrap is still the phrase.
    doc = " ".join(
        ((APPROVAL_DOC or "") + (approval_checkpoints.__doc__ or "")).split()
    )

    # Words rather than a sentence, on `test_precedent.py`'s pattern for the same
    # kind of assertion: an honest statement of this decision cannot avoid naming
    # the flag it rests on, who owns the connection, or what it is not owned by —
    # and pinning a spelling would redden CI on a reword that decided nothing.
    for word in ("check_same_thread", "owned by", "not by a thread"):
        assert word in doc, (
            f"the docstrings do not say {word!r}, so who owns the connection is a "
            "decision the next reader rediscovers from a ProgrammingError"
        )


def test_the_checkpointed_state_still_carries_three_primitives() -> None:
    """A real serializer makes widening this more tempting, not less.

    `ApprovalState`'s own docstring is the argument: a checkpoint is not the place
    to discover which of a run's records happen to survive a serializer. Asserted
    as the whole set rather than field by field, so an addition fails rather than
    passing unnoticed.
    """
    assert get_type_hints(ApprovalState) == {
        "confirmed": bool,
        "identity": str,
        "reason": str,
    }


def _imported_names(source: Path) -> set[str]:
    """Every module and name that module imports, dotted."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_no_test_writes_the_checkpoint_database_a_real_run_would_use() -> None:
    """The autouse fixture in `conftest.py`, asserted rather than trusted.

    The suite drives the approval interrupt in dozens of places, and every one of
    them takes the default database. Left pointing at the repository, the suite
    would append the identity of whoever a fixture says confirmed the spend to a
    file in the working copy that nothing prunes — and it would do it quietly,
    because the location is git-ignored.

    Read off the module rather than off the name this file imported, because the
    fixture patches the module and an imported constant would answer with the value
    it had at import.
    """
    live = approval.DEFAULT_CHECKPOINT_DATABASE

    assert REPOSITORY not in live.parents, (
        f"the suite is writing halts to {live}, inside the working copy. A test "
        "does not touch the database a real run uses (ADR-0028)"
    )
