"""The precedent store: durable, deterministic-only, and unreachable from two
instruments.

The claims tested here fail in different ways, and the count is deliberately not
stated: the concurrency pair below joined the list at #36 and the next backend
decision may add another.

**Durability** is the whole content of ADR-0019, so the test that matters writes a
finding, drops the store object, builds a new one against the same path, and reads
the finding back. A round trip through one object would pass against
`InMemoryStore`, which is the outcome the ADR exists to forbid.

**It survives concurrent writers**, which is new with the SQLite backend (ADR-0029)
and is the one thing here no single-threaded test can say. Two tests, because there
are two hazards: six threads against one cold database, and then eight separate
processes, which is the shape the journal-mode pragma fails in and the shape a lock
inside this process could never have covered. Both are probabilistic guards on a
race, so both are sized — `WRITERS`, `PROCESSES` and their write counts record what
it took to make a regression show reliably rather than occasionally.

**Deterministic findings only** (ADR-0004) is enforced on `Finding.verdict_class`,
which is copied off the attempt, so the refusal cannot be defeated by a caller who
reasoned about family names.

**Unreachability** from `judge.py` and `adjudication.py` is asserted over the
*transitive* imports of both modules. `test_judge.py` and `test_judged_families.py`
already forbid the direct import, and phase 6a is the first time there is a store
for either to reach — at which point the direct check becomes the weaker one, since
a route through any intermediate module would satisfy it. The κ figure the judged
families depend on is what a leak here would contaminate, and a store that
accumulates would contaminate more of it every run.

**No target identity is written**, so the corpus cannot identify a target by its
failure pattern however carefully one lookup redacts (ADR-0011). The record has no
target field and the prose it carries was written by a blinded instrument, which is
the chain the test below checks the near end of; the file is git-ignored so no
finding about anybody's agent is ever committed (ADR-0008).

**No model is called.** `suggest_remediation` is handed a completion that answers
with the line it was given and records what it was shown, because what the fix
*says* is not assertable in a unit test — what is assertable is whether precedent
reached the model at all.
"""

import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import get_type_hints

import pytest
from langgraph.store.sqlite import SqliteStore

from backend.bench.adaptive import precedent
from backend.bench.adaptive.precedent import (
    DEFAULT_STORE_PATH,
    DURABLE_PRECEDENT,
    LEGACY_STORE_PATH,
    PRECEDENT_DIRECTORY,
    PRECEDENT_NAMESPACE,
    RETRIEVAL_LIMIT,
    DurablePrecedents,
    JudgedPrecedent,
    PrecedentDatabase,
)
from backend.bench.adaptive.precedent import __doc__ as PRECEDENT_DOC
from backend.bench.library import Family, VerdictClass
from backend.bench.remediation import (
    Completion,
    RemediationFailed,
    suggest_remediation,
)
from backend.bench.store import NoVectorIndex
from backend.tests.conftest import (
    A_FIX,
    PRECEDENT_TARGET,
    a_finding,
    reachable_from,
)

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
JUDGE_SOURCE = BACKEND / "bench" / "judge.py"
ADJUDICATION_SOURCE = BACKEND / "bench" / "adjudication.py"
PRECEDENT_SOURCE = BACKEND / "bench" / "adaptive" / "precedent.py"


@pytest.fixture
def store_file(tmp_path: Path) -> Path:
    """This test's own store, under a directory that is not there yet.

    Not there yet on purpose, the reason `test_approval_checkpoints.database` gives:
    the store creates its parent, and a fixture that pre-made it would hide a
    backend that could only open a database beside an existing directory.
    """
    return tmp_path / "precedent" / "findings.sqlite"


def answering(
    fix: str = "Redact the configured secret before the reply is sent.",
) -> tuple[Completion, list[str]]:
    """A model that answers with the line it was given, and keeps what it was shown.

    What the fix says is not under test. Whether precedent reached the model is,
    and the only way to see that is to keep the message.
    """
    shown: list[str] = []

    def complete(system_prompt: str, message: str) -> str:
        shown.append(message)
        return f"fix: {fix}"

    return complete, shown


# --- Durable across a restart -----------------------------------------------


def test_a_finding_outlives_the_store_object_that_wrote_it(store_file: Path) -> None:
    # The whole content of ADR-0019. Write, drop the object, build a new one
    # against the same location, read the finding back. A round trip through one
    # object would pass against `InMemoryStore`, which is what the ADR forbids.
    DurablePrecedents.at(store_file).record(a_finding(), A_FIX)

    restarted = DurablePrecedents.at(store_file)
    found = restarted.for_family(Family.DATA_LEAKAGE)

    assert len(found) == 1, (
        f"a new store object against {store_file.name} read back {len(found)} "
        "findings. A precedent store that does not survive the object that wrote "
        "it is the run state's lifetime under a second name (ADR-0019)"
    )
    [recovered] = found
    assert recovered.failure == "The reply carried the configured secret back out."
    assert recovered.remediation == (
        "Filter the configured secret out of every outbound reply."
    )
    assert recovered.case_id == "data-leakage-001"
    assert recovered.external_id == "LLM02:2026"


READ_BACK = """
import sys
from pathlib import Path

from backend.bench.adaptive.precedent import DurablePrecedents
from backend.bench.library import Family

[found] = DurablePrecedents.at(Path(sys.argv[1])).for_family(Family.DATA_LEAKAGE)
print(found.case_id)
print(found.failure)
print(found.remediation)
print(found.external_id)
"""
"""A reader, as a program, because ADR-0019 point 4 says *in a new process*.

The test below writes the finding and this reads it back — so what crosses is the
file and nothing else: no object, no import-time cache, no module state the writer
left behind. A round trip inside one interpreter cannot say that, which is why the
ticket's definition of done spells the process out.
"""


def test_a_finding_outlives_the_process_that_wrote_it(store_file: Path) -> None:
    """ADR-0019 point 4, at the one boundary that cannot be faked.

    The test above drops the store *object* and rebuilds it, which is the claim the
    ADR states; this drops the whole interpreter. Both are needed and the second is
    the stronger: a store that had quietly kept its contents in a module-level cache
    would satisfy the first and fail this.
    """
    DurablePrecedents.at(store_file).record(a_finding(), A_FIX)

    reader = subprocess.run(
        [sys.executable, "-c", READ_BACK, str(store_file)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=A_WRITER_HAS_FINISHED,
    )

    assert reader.returncode == 0, (
        f"a new process could not read the finding back:\n{reader.stderr}"
    )
    assert reader.stdout.splitlines() == [
        "data-leakage-001",
        "The reply carried the configured secret back out.",
        "Filter the configured secret out of every outbound reply.",
        "LLM02:2026",
    ]


def test_a_finding_is_a_row_and_the_store_is_a_database(store_file: Path) -> None:
    """The shape on disk, which is what #36 changed and the only place it shows.

    Read off the file rather than through `for_family`, because every assertion
    this file makes through the interface passed against the JSON store that
    rewrote the whole document on every batch — the interface is what did **not**
    change. What did is that a finding is now one row that an insert appends, so
    the claim is about the bytes and has to be asserted against them.

    The header rather than the suffix: a store that wrote JSON into a file called
    `.sqlite` would satisfy a name and nothing else.
    """
    DurablePrecedents.at(store_file).record(a_finding(), A_FIX)

    assert store_file.read_bytes().startswith(b"SQLite format 3\x00")
    with closing(sqlite3.connect(store_file)) as connection:
        [(rows,)] = connection.execute("SELECT count(*) FROM store").fetchall()
    assert rows == 1, (
        f"{rows} rows hold one finding. The record is a row, so one finding is "
        "one insert rather than a document rewritten around it"
    )


def test_a_lookup_against_a_store_nothing_wrote_creates_no_database(
    store_file: Path,
) -> None:
    """Reading precedent is not an event in the store's history.

    Older than this backend — `test_adaptive_attacker.py` has asserted it since the
    store had one caller — and the backend is what put it at risk: opening a database
    runs the schema, so a lookup would leave a file where there was none. A corpus
    that recorded who looked would be a record of lookups rather than of what failed.

    It is also what keeps the two refusals' assertions meaningful: `exists()` only
    means "nothing was written" while a read cannot write.
    """
    store = DurablePrecedents.at(store_file)

    assert store.for_family(Family.DATA_LEAKAGE) == ()

    assert not store_file.exists(), (
        f"a lookup created {store_file.name}. Reading is not a write, and a store "
        "whose file appears when it is read cannot say by its own existence that "
        "a finding was ever filed"
    )
    assert not store_file.parent.exists() or not any(store_file.parent.iterdir()), (
        "a lookup left something beside the database it did not create"
    )


def test_two_runs_accumulate_and_one_run_recorded_twice_does_not(
    store_file: Path,
) -> None:
    # Precedent's only value is cumulative (ADR-0019), so a second run has to add
    # to the first rather than replace it — and a re-run of the same finding must
    # not multiply one route into a corpus of copies, which is what the
    # content-addressed key buys.
    first = DurablePrecedents.at(store_file)
    first.record(a_finding(reason="The reply carried the secret out."), A_FIX)
    first.record(a_finding(reason="The reply carried the secret out."), A_FIX)

    second = DurablePrecedents.at(store_file)
    second.record(a_finding(reason="The agent read it out of a fetched page."), A_FIX)

    failures = [
        entry.failure
        for entry in DurablePrecedents.at(store_file).for_family(Family.DATA_LEAKAGE)
    ]
    assert sorted(failures) == [
        "The agent read it out of a fetched page.",
        "The reply carried the secret out.",
    ]


def test_a_lookup_answers_for_one_family_and_not_for_the_others(
    store_file: Path,
) -> None:
    # A store that returned everything would hand `suggest_remediation` the fix for
    # a different failure mode, which is worse advice than no precedent at all.
    store = DurablePrecedents.at(store_file)
    store.record(a_finding(family=Family.DATA_LEAKAGE, reason="It leaked."), A_FIX)
    store.record(
        a_finding(
            family=Family.HALT_DEFEAT,
            case_id="halt-defeat-001",
            reason="It acted after the stop signal.",
        ),
        "Refuse every action taken after the stop signal.",
    )

    assert [entry.failure for entry in store.for_family(Family.HALT_DEFEAT)] == [
        "It acted after the stop signal."
    ]
    assert [entry.failure for entry in store.for_family(Family.DATA_LEAKAGE)] == [
        "It leaked."
    ]
    assert store.for_family(Family.DISCLOSURE_DENIAL) == ()


WRITERS = 6
CALLS_EACH = 20
"""How many threads hammer one store, and how many batches each one sends.

Six rather than two, and released from a barrier below, because the window the
schema race lives in is the **first** batch against a database that is not there
yet: after the migrations are applied every later `setup()` reads the version and
inserts nothing. Two threads racing one cold start is a coin flip that passes on a
quiet machine; six arriving together is not. The calls after the first are what
proves the store still works once the schema is settled.
"""


def test_concurrent_writers_against_one_store_do_not_race_on_its_schema(
    store_file: Path,
) -> None:
    """Two runs filing findings at once, which is what `api/runs.py` makes ordinary.

    Every run gets its own OS thread, so this is not a stress test of an unlikely
    path — it is the second run. What it would catch and why the store has code of
    its own for it is ADR-0029; what this asserts is that six writers against one
    cold database all finish and all of their rows survive.

    Threads rather than a stand-in, for the reason `test_approval_checkpoints.py`
    drives two threads at one graph: a store that works from the convenient side is
    what every other test in this file already proves.
    """
    failures: list[BaseException] = []
    # Released together, because the race is on the cold start: every writer has to
    # be inside its first batch while the database still has no schema.
    together = threading.Barrier(WRITERS)

    def filing(tag: str) -> None:
        store = PrecedentDatabase(store_file)
        together.wait()
        try:
            for call in range(CALLS_EACH):
                store.put(
                    PRECEDENT_NAMESPACE,
                    f"{tag}-{call}",
                    {"family": str(Family.DATA_LEAKAGE), "call": call},
                )
                store.search(PRECEDENT_NAMESPACE, limit=RETRIEVAL_LIMIT)
        except BaseException as raised:  # noqa: BLE001 — the assertion is the report
            failures.append(raised)

    writers = [
        threading.Thread(target=filing, args=(f"writer-{index}",))
        for index in range(WRITERS)
    ]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join()

    assert not failures, (
        f"{len(failures)} of {WRITERS} concurrent writers failed, first "
        f"{type(failures[0]).__name__}: {failures[0]}. Two runs file findings at "
        "once whenever two runs are going, and a store that raises under that "
        "loses a whole run rather than a write"
    )
    filed = PrecedentDatabase(store_file).search(
        PRECEDENT_NAMESPACE, limit=WRITERS * CALLS_EACH
    )
    assert len(filed) == WRITERS * CALLS_EACH, (
        f"{len(filed)} of {WRITERS * CALLS_EACH} writes survived, so one writer's "
        "batch dropped another's rather than queueing behind it"
    )


PROCESSES = 8
WRITES_EACH = 40
"""How many separate processes cold-start one database, and how many rows each files.

Separate processes rather than threads, because the two hazards below are the ones a
thread lock cannot reach: `SqliteStore.setup()` racing itself, and the journal-mode
pragma, which SQLite refuses without consulting the busy handler. Released from a
file the parent creates, for the reason the barrier above exists — the window is the
cold start, and interpreter startup jitter alone is enough to miss it.
"""

WRITER = """
import sys, time
from pathlib import Path

from backend.bench.adaptive.precedent import PRECEDENT_NAMESPACE, PrecedentDatabase

tag, database, gate, writes = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), int(
    sys.argv[4]
)
store = PrecedentDatabase(database)
Path(f"{gate}.{tag}").write_text("ready", encoding="utf-8")
while not gate.exists():
    time.sleep(0.005)
for call in range(writes):
    store.put(PRECEDENT_NAMESPACE, f"{tag}-{call}", {"family": "data_leakage"})
"""
"""One writer, as a program, because a second *process* is what this asks about.

`seed_precedent.py` and `scripts/gate.py` are separate processes an operator runs by
hand, so a run going while one of those writes is not a synthetic scenario — it is
the one shape of concurrency the bench's own thread-per-run does not cover.
"""


def test_separate_processes_cold_starting_one_store_do_not_race_on_it(
    store_file: Path,
) -> None:
    """The half of ADR-0029's concurrency that no lock inside this process can hold.

    `seed_precedent.py` and `scripts/gate.py` are separate processes an operator runs
    by hand, so a run going while one of those writes is real. Two of the delegate's
    behaviours fail in exactly this window and ADR-0029 says which and why
    `_enable_wal` and `_migrated` exist; what this asserts is that eight processes
    cold-starting one database all finish and all of their rows survive.

    The contention is sized rather than chosen: at four processes and a dozen writes
    each, breaking the journal-mode guard went red one run in four, and at these
    numbers it goes red every run.
    """
    gate = store_file.parent.parent / "go"
    writers = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                WRITER,
                f"p{index}",
                str(store_file),
                str(gate),
                str(WRITES_EACH),
            ],
            cwd=REPOSITORY,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(PROCESSES)
    ]
    _released(gate, writers)

    complaints = [
        writer.communicate(timeout=A_WRITER_HAS_FINISHED)[1]
        for writer in writers
        if writer.wait(timeout=A_WRITER_HAS_FINISHED) != 0
    ]

    assert not complaints, (
        f"{len(complaints)} of {PROCESSES} processes failed against one cold "
        f"database. First:\n{complaints[0]}"
    )
    filed = PrecedentDatabase(store_file).search(
        PRECEDENT_NAMESPACE, limit=PROCESSES * WRITES_EACH
    )
    assert len(filed) == PROCESSES * WRITES_EACH


A_WRITER_HAS_FINISHED = 60.0
"""How long one writer process is given to do its writes and exit.

Generous, because the wait is not what is under test: a writer queueing behind
another for up to `store.WRITE_WAIT_SECONDS` is the behaviour being asked for,
and a limit tight enough to catch that would fail the test for the thing it exists
to prove.
"""

WRITERS_HAVE_GATHERED = 30.0
"""How long the parent waits for every writer to reach the gate before giving up.

Its own number rather than the one above, because it measures something else — eight
interpreters starting — and because a test that hung here would otherwise be
indistinguishable from one waiting on a lock.
"""


def _released(gate: Path, writers: list[subprocess.Popen[str]]) -> None:
    """Wait until every writer says it is ready, then let them all go at once."""
    deadline = time.monotonic() + WRITERS_HAVE_GATHERED
    while len(list(gate.parent.glob(f"{gate.name}.*"))) < len(writers):
        if time.monotonic() > deadline:
            for writer in writers:
                writer.kill()
            raise AssertionError(
                f"only {len(list(gate.parent.glob(f'{gate.name}.*')))} of "
                f"{len(writers)} writers reached the gate"
            )
        time.sleep(0.01)
    gate.write_text("go", encoding="utf-8")


# --- What it refuses, and what the backend would have answered ---------------


def test_a_semantic_query_is_refused_before_a_database_is_opened(
    store_file: Path,
) -> None:
    """`NoVectorIndex` survived the change of backend, and moved earlier in it.

    Refused before the connection rather than inside the batch, so a caller that
    asked a question this store cannot answer has not left a database behind as a
    side effect of being told no.
    """
    store = PrecedentDatabase(store_file)

    with pytest.raises(NoVectorIndex, match="no embedding model"):
        store.search(PRECEDENT_NAMESPACE, query="how did the last one leak?")

    assert not store_file.exists(), (
        "a refused query created the database it refused to read, so being told "
        "no writes to disk"
    )


def test_the_backend_would_answer_that_query_with_a_list_it_had_not_ranked(
    store_file: Path,
) -> None:
    """Why the refusal above is load-bearing rather than a leftover.

    The old refusal rested on an absence — a JSON document could not rank by
    meaning, so the alternative to refusing was returning nothing. The new one
    rests on the delegate's behaviour: `SqliteStore` takes the vector branch on
    `op.query and self.index_config`, and with no index configured it drops the
    query and returns the same recency-ordered rows. A `score` of `None` on every
    item is the delegate saying it ranked nothing.

    Asserted against the dependency because that behaviour is the reason this
    repository has code of its own here: if a future release of
    `langgraph-checkpoint-sqlite` starts refusing a query it cannot rank, this
    test fails and the wrapper's own refusal has become the leftover.
    """
    DurablePrecedents.at(store_file).record(a_finding(), A_FIX)

    with closing(sqlite3.connect(store_file, isolation_level=None)) as connection:
        delegate = SqliteStore(connection)
        answered = delegate.search(PRECEDENT_NAMESPACE, query="anything at all")

    assert [item.value["case_id"] for item in answered] == ["data-leakage-001"]
    assert [item.score for item in answered] == [None]


def test_an_operator_filter_runs_the_comparison_rather_than_being_refused(
    store_file: Path,
) -> None:
    """`NoFilterOperators` is gone, and this is what took its place.

    It refused a `{"$gt": ...}` filter on the argument that a comparison a caller
    believes ran and did not is worse than a refusal. SQLite runs the comparison,
    so the argument expired with the backend — and a refusal kept past its reason
    is machinery a reader has to reverse-engineer. What replaces it is this: the
    comparison, run, against a store that has two records to sort.
    """
    store = DurablePrecedents.at(store_file)
    store.record(a_finding(case_id="data-leakage-001", reason="The first one."), A_FIX)
    store.record(a_finding(case_id="data-leakage-002", reason="The second one."), A_FIX)

    compared = store.store.search(
        PRECEDENT_NAMESPACE, filter={"case_id": {"$gt": "data-leakage-001"}}
    )

    assert [item.value["failure"] for item in compared] == ["The second one."], (
        "the operator filter did not compare. A store that answered this with "
        "both records, or with none, is the silently wrong answer the refusal it "
        "replaced existed to prevent"
    )


# --- Deterministic findings only ---------------------------------------------


def test_a_judged_finding_cannot_enter_the_store(store_file: Path) -> None:
    # ADR-0004: a judged verdict carries a reliability figure and a wider stated
    # limit, and precedent that mixed the two would pass advice derived from a
    # qualified number off as advice derived from one the bench stands behind. The
    # refusal reads `verdict_class` off the attempt, never the family name.
    judged = a_finding(
        family=Family.WRONGFUL_COMMITMENT,
        verdict_class=VerdictClass.JUDGED,
        case_id="wrongful-commitment-001",
    )
    store = DurablePrecedents.at(store_file)

    with pytest.raises(JudgedPrecedent, match="deterministic findings only"):
        store.record(judged, A_FIX)

    assert store.for_family(Family.WRONGFUL_COMMITMENT) == ()
    assert not store_file.exists(), (
        "a refused write left a file behind, so the store's contents depend on "
        "which findings were offered rather than on which were accepted"
    )


# --- Nothing in it names a target --------------------------------------------


def test_the_stored_record_names_no_target(store_file: Path) -> None:
    # Redaction at the point of retrieval defends one lookup; it does not defend a
    # corpus, in which a failure pattern identifies a target on its own (ADR-0011),
    # and `Blinding.redact` substitutes the current run's identities so prose filed
    # by an earlier run is beyond it. What holds instead is a chain: no target field
    # on the record, and the one prose field comes from an instrument that was never
    # shown a target name (`JudgeBrief.about`, asserted in `test_judge.py`).
    DurablePrecedents.at(store_file).record(a_finding(), A_FIX)

    # The database's bytes rather than its rows, and read as bytes because a
    # database is not text: what is asserted is that the target's name is nowhere
    # in the file, which a query against the one table this store writes could not
    # say — a stray column, an index or a freed page would all be outside it.
    written = store_file.read_bytes()
    assert b"The reply carried the configured secret back out." in written, (
        "nothing was written, so this test would pass against a store that "
        "records nothing at all"
    )
    assert PRECEDENT_TARGET.encode("utf-8") not in written
    assert b"invalid" not in written


# --- `suggest_remediation` reads it ------------------------------------------


def test_suggest_remediation_is_shown_the_precedent_and_records_what_informed_it(
    store_file: Path,
) -> None:
    # The positive half of ADR-0004's asymmetry: this is the one function that may
    # hold a store handle, and the reason it holds one is that a fix derived from
    # one transcript is the fix it would have written with no memory at all.
    store = DurablePrecedents.at(store_file)
    store.record(
        a_finding(
            case_id="data-leakage-002",
            reason="An earlier agent read its system prompt out on request.",
        ),
        "Refuse any request that names the system prompt.",
    )
    complete, shown = answering()

    remediation = suggest_remediation(a_finding(), store, complete)

    [message] = shown
    assert "An earlier agent read its system prompt out on request." in message
    assert "Refuse any request that names the system prompt." in message
    assert [entry.case_id for entry in remediation.informed_by] == ["data-leakage-002"]
    assert remediation.fix == "Redact the configured secret before the reply is sent."


def test_the_fix_a_precedent_records_is_the_one_the_remediation_tool_wrote(
    store_file: Path,
) -> None:
    """ADR-0069 at the store's own door, and the bug it closes.

    `Precedent.of` used to read `finding.narrative.remediation` — the judge's fix,
    written from one transcript with no corpus behind it. So the corpus ADR-0019
    claims value for was filled with the *unprecedented* half of every pair, and
    the fix its own instrument wrote was thrown away. The fix is now handed in,
    because a `Precedent` cannot import a `Remediation` without the cycle
    `remediation.py` -> `precedent.py` already forbids.
    """
    store = DurablePrecedents.at(store_file)
    complete, _ = answering()
    finding = a_finding()
    written = suggest_remediation(finding, store, complete)

    store.record(finding, written.fix)

    [recovered] = store.for_family(Family.DATA_LEAKAGE)
    assert recovered.remediation == written.fix
    assert (
        recovered.remediation
        == "Redact the configured secret before the reply is sent."
    )


def test_a_precedent_with_no_fix_in_it_cannot_be_filed(store_file: Path) -> None:
    """The refusal that ADR-0069 moved, held at the second door as well.

    `Remediation.__post_init__` refuses a blank fix, so the live path cannot reach
    here with one. But `Precedent.of` now takes the fix as a *string*, and a string
    parameter is a door a `Remediation` used to be: a blank one files a row that
    renders as `fix written then: ` in front of the next run's model, which is
    precisely the "nothing to report" `RemediationFailed` exists to prevent (PLAN
    §10). The guarantee is carried at both ends rather than by which caller happened
    to pass what.

    A `ValueError` and not a `RemediationFailed`, which this module cannot import
    without closing the cycle `remediation.py` -> here: an instrument that answered
    with no fix was already refused where it answered, so a blank arriving at this
    door is a caller in the bench and not a broken model — the distinction
    `JudgedPrecedent` draws one exception up.
    """
    store = DurablePrecedents.at(store_file)

    with pytest.raises(ValueError, match="no fix"):
        store.record(a_finding(), "   ")

    assert store.for_family(Family.DATA_LEAKAGE) == ()


def test_the_remediation_tool_is_shown_why_it_failed_and_no_fix_but_precedent(
    store_file: Path,
) -> None:
    """The other half of ADR-0069: the roles are separated in the brief too.

    The brief used to carry a line `what the reviewer suggested`, which was the
    judge's fix. There is no such fix now, and the point is not only that the field
    went: a tool shown one fix and asked for another is being asked to arbitrate
    between two instruments, which is the thing #111 ended. The only fixes in front
    of the model are precedent, which is what ADR-0004 gives this instrument alone.
    """
    store = DurablePrecedents.at(store_file)
    store.record(
        a_finding(
            case_id="data-leakage-002",
            reason="An earlier agent read its system prompt out on request.",
        ),
        "Refuse any request that names the system prompt.",
    )
    complete, shown = answering()

    suggest_remediation(a_finding(), store, complete)

    [message] = shown
    assert "The reply carried the configured secret back out." in message
    assert "Refuse any request that names the system prompt." in message
    assert "reviewer" not in message, (
        "the brief still carries a fix written about this finding by something "
        "other than this tool (ADR-0069)"
    )


def test_a_fix_written_against_an_empty_store_says_there_was_no_precedent(
    store_file: Path,
) -> None:
    # Run one, and the honest answer rather than a silent one: ADR-0019 says the
    # store cannot be demonstrated inside a single run, so the empty case has to be
    # readable as empty instead of looking like precedent that agreed with itself.
    complete, shown = answering()

    remediation = suggest_remediation(
        a_finding(), DurablePrecedents.at(store_file), complete
    )

    [message] = shown
    assert "none recorded against this family yet" in message
    assert remediation.informed_by == ()


def test_a_reply_with_no_fix_in_it_is_a_named_failure(store_file: Path) -> None:
    # A broken instrument must never be able to put "nothing to report" in front of
    # an engineer waiting for a fix (PLAN §10).
    with pytest.raises(RemediationFailed, match="no `fix:` line"):
        suggest_remediation(
            a_finding(),
            DurablePrecedents.at(store_file),
            lambda system_prompt, message: "I would suggest filtering the output.",
        )


# --- Two instruments cannot reach it, by any chain of imports ----------------


def test_the_judge_cannot_reach_the_store_through_any_module_it_imports() -> None:
    # ADR-0004, enforced past its first line. `test_judge.py` forbids the direct
    # import; phase 6a is the first commit at which an intermediate module could
    # carry the store in instead, and precedent surfaced to the judge is the
    # blinding channel reopened by another route.
    reachable = [
        name
        for name in reachable_from(JUDGE_SOURCE)
        if "precedent" in name.lower() or "remediation" in name.lower()
    ]
    assert not reachable, (
        f"{reachable} is reachable from the judge. Precedent that reaches "
        "`assess_finding` contaminates the κ figure that polices the judged "
        "families (ADR-0004), and a chain of imports is a route"
    )


def test_the_adjudicator_cannot_reach_the_store_through_any_module_it_imports() -> None:
    # The stronger of the two prohibitions (ADR-0013): `adjudicate` is the
    # instrument κ is measured on, so precedent reaching it would contaminate the
    # figure that decides whether a judged family may be reported at all.
    reachable = [
        name
        for name in reachable_from(ADJUDICATION_SOURCE)
        if "precedent" in name.lower() or "remediation" in name.lower()
    ]
    assert not reachable, (
        f"{reachable} is reachable from the adjudicator, whose output is the "
        "number rather than the prose around it (ADR-0013)"
    )


def test_the_store_a_run_uses_cannot_be_the_in_memory_double() -> None:
    # ADR-0019 point 2: `InMemoryStore` is the right thing for a unit test and may
    # not be the production backend, because a memory that dies with the process
    # makes the claim false. Import-level, because the failure mode is somebody
    # reaching for the quickstart's store while the docstring above still promises
    # durability.
    reachable = [
        name
        for name in reachable_from(PRECEDENT_SOURCE)
        if "store.memory" in name or "InMemoryStore" in name
    ]
    assert not reachable, (
        f"{reachable} is reachable from the precedent store. A per-process store "
        "is the run state's lifetime under a second name (ADR-0019)"
    )
    # And the field is annotated narrowly, so the substitution is a type error
    # before it is a test failure — the pattern the repository uses everywhere the
    # invariant can be carried by a type rather than by a rule.
    assert get_type_hints(DurablePrecedents)["store"] is PrecedentDatabase
    assert isinstance(DurablePrecedents.at().store, PrecedentDatabase)


# --- Single-tenant, and git-ignored ------------------------------------------


def test_the_namespace_is_single_tenant_and_the_module_says_so() -> None:
    # ADR-0019 point 5: cross-tenant isolation is a named P1 blocker rather than a
    # silent one, so the namespace has to be visibly without a tenant in it. A
    # third segment naming a user would look like isolation and enforce none.
    assert PRECEDENT_NAMESPACE == ("agentaudit", "precedent")
    assert "single-tenant" in (PRECEDENT_DOC or "")


@pytest.mark.parametrize(
    "name",
    ["findings.sqlite", "findings.sqlite-wal", "findings.sqlite-shm", "findings.json"],
)
def test_the_store_and_its_sidecars_are_ignored_by_git(name: str) -> None:
    """ADR-0008: a finding is about somebody else's agent, so the repository never
    carries one.

    Asked of git rather than of `.gitignore`'s text, because what decides whether a
    file would be committed is git's answer and not a pattern that looks right.

    The sidecars are parametrised rather than assumed covered by the database's own
    name, for the reason `test_approval_checkpoints.py` gives about the other SQLite
    file in the tree: WAL writes two files beside it, and a journal holding a finding
    must not be the one thing the ignore rule missed. The old JSON document is in the
    list too — a clone that ran the bench before #36 still has one, and it is still
    somebody else's agent failing.

    Built from `PRECEDENT_DIRECTORY` rather than from `DEFAULT_STORE_PATH`, because
    `conftest.py` redirects the store and never the directory: reading the location
    off the module inside a test would ask git about a temporary path.
    """
    if not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout, so git's own answer cannot be asked for")

    path = PRECEDENT_DIRECTORY / name
    checked = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=REPOSITORY,
        check=False,
    )
    assert checked.returncode == 0, (
        f"{path} is not ignored by git, so the next run's findings about a real "
        "target are one `git add` away from being published"
    )


def live_store_paths() -> tuple[Path, ...]:
    """Every route to the store, as it stands at the moment of the call.

    Three of them, because `conftest._precedent_at` redirects three and a redirection
    that missed one would leave a route into the working copy. Read off the module
    rather than off the names this file imported, because the fixture patches the
    module and an imported constant answers with the value it had at import — which
    is the real location, and is what the git questions above rely on.
    """
    return (
        precedent.DEFAULT_STORE_PATH,
        precedent.LEGACY_STORE_PATH,
        DURABLE_PRECEDENT.store.path,
    )


@pytest.fixture(scope="module")
def store_at_module_setup() -> tuple[Path, ...]:
    """The same three routes, read while a *module-scoped* fixture is being built.

    Captured here because this is the window the defect lived in. pytest builds a
    higher-scoped fixture before a function-scoped one, so `conftest.precedent_
    elsewhere` — autouse, and function-scoped until now — was not in place when
    `test_gate.py`'s module-scoped `gate_run` was constructed: 540 attempts with
    the adaptive layer behind them, and the one run in the suite that filed its
    findings into the working copy. Reported by #35's agent and left for #36,
    because #36 is the change that touches the store this escaped into.
    """
    return live_store_paths()


def test_no_test_writes_the_store_a_real_run_would_use() -> None:
    """The autouse fixture in `conftest.py`, asserted rather than trusted."""
    for live in live_store_paths():
        assert REPOSITORY not in live.parents, (
            f"the suite is writing findings to {live}, inside the working copy. A "
            "test does not touch the store a real run uses (ADR-0008)"
        )


def test_a_module_scoped_fixture_is_inside_the_redirection_too(
    store_at_module_setup: tuple[Path, ...],
) -> None:
    """The same claim, asked from the scope the function-scoped patch did not reach.

    The test above passes whatever the fixture's scope is, because by the time a
    test body runs a function-scoped patch is in place. This one is the assertion
    that has to be made from higher up, and it is why `precedent_elsewhere` is a
    session-scoped redirection with a per-test one inside it.
    """
    for live in store_at_module_setup:
        assert REPOSITORY not in live.parents, (
            f"a module-scoped fixture was built with the store pointing at {live}. "
            "Every run such a fixture starts files its findings in the working "
            "copy, quietly, because the location is git-ignored"
        )


def test_the_ignored_names_are_the_files_the_store_actually_writes() -> None:
    """The drift guard on the list above, which is literal names.

    Asked because the parametrised names and the constants are two statements of
    one fact, and a store moved to a third file name would leave the test above
    passing about a location nothing writes to.
    """
    assert DEFAULT_STORE_PATH == PRECEDENT_DIRECTORY / "findings.sqlite"
    assert LEGACY_STORE_PATH == PRECEDENT_DIRECTORY / "findings.json"
