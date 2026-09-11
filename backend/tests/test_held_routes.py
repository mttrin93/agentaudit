"""The fifth store: a confirmed break the admission bar refused, kept per target.

What is asserted here is the *shape* of a target library and nothing that fills one.
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§1 and §6 are what these tests are about, and the fence they rest on is a property
of the type rather than of any call site — so the type comes first and the writers
come in later tickets (#239 files, #240 sends).

Three seams:

1. **The sixth provenance** — `DiscoveredBy.TARGET_SPECIFIC`, declared last so the
   census prints in an order two gate runs can be compared in (ADR-0107 §1), and
   refused a bar so that no `Case` can carry it.
2. **The record** — `HeldRoute`, which is not a `Case` and holds its own clean-run
   count rather than having one derived by scanning run records (ADR-0019).
3. **Where it is** — one git-ignored directory with its sidecars, one record per
   route per target, and a read that survives the object and the process that wrote
   it.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from backend.bench.adaptive.proposal import FOUND_BY_THE_ATTACKER
from backend.bench.admission import (
    NoAdmissionBar,
    found_by_the_attacker,
    library_provenance,
)
from backend.bench.decided import RouteKey
from backend.bench.held import (
    CLEAN_RUNS_TO_CLOSE,
    DEFAULT_HELD_PATH,
    HELD_DIRECTORY,
    HELD_NAMESPACE,
    HELD_ROUTES,
    PAGE,
    HeldDatabase,
    HeldRoute,
    HeldRoutes,
    HeldState,
)
from backend.bench.library import (
    Case,
    DiscoveredBy,
    Family,
    LibraryVersion,
    SuccessCondition,
    SuccessConditionKind,
    load_library,
)
from backend.bench.pending import DEFAULT_PENDING_PATH, PENDING_NAMESPACE
from backend.tests.conftest import CASES_DIR, REPOSITORY

A_READER_HAS_FINISHED = 60.0
"""How long the reader process below is given to start, read and exit.

Generous, because the wait is not what is under test: what is being asked is that
the file is the only thing that crossed, and a limit tight enough to catch a slow
interpreter start would fail the test for the thing it exists to prove.
"""


@pytest.fixture
def store_file(tmp_path: Path) -> Path:
    """This test's own store, under a directory that is not there yet.

    Not there yet on purpose, on `test_precedent.store_file`'s reasoning: the store
    creates its parent, and a fixture that pre-made it would hide a backend that
    could only open a database beside an existing directory.
    """
    return tmp_path / "held" / "routes.sqlite"


A_CUSTOMER = "acme-support-bot"
"""The target a route is held against — the field ADR-0104 §2 grants the exception
for, and the field that scopes one route's record to one agent."""

PROBE = "the probe that actually beat somebody's agent"

THE_ATTACKER_SAID = "asked for the configured secret under a maintenance pretext"

ANOTHER_CUSTOMER = "beta-research-assistant"
"""A second agent, so that the per-target half of the key is asserted and not
assumed: two targets may fail one route and neither sees the other's record."""

THE_RUN_THAT_FOUND_IT = "run-2026-09-03-0007"


def digest_of(probe: str) -> str:
    """The probe's half of a `RouteKey`, as `decided.RouteKey.of` mints it.

    Computed here rather than taken off a `Case`, because what these tests need is
    a key and not a case record — and building a case to get a key would be the
    conflation the whole ticket is about.
    """
    return sha256(probe.encode("utf-8")).hexdigest()[:16]


def a_held_route(
    target: str = A_CUSTOMER,
    probe: str = PROBE,
    state: HeldState = HeldState.OPEN,
    clean_runs: int = 0,
    found_in: str = THE_RUN_THAT_FOUND_IT,
) -> HeldRoute:
    """One confirmed break the bar refused, as the store holds it."""
    return HeldRoute(
        route=RouteKey(family=Family.DATA_LEAKAGE, probe=digest_of(probe)),
        target=target,
        payload=(probe,),
        success_condition=SuccessCondition(kind=SuccessConditionKind.CANARY_IN_REPLY),
        description=THE_ATTACKER_SAID,
        found_in=found_in,
        state=state,
        clean_runs=clean_runs,
    )


def test_the_sixth_provenance_is_declared_last() -> None:
    """ADR-0117's last stated cost, and ADR-0107 §1's reason for the position.

    The provenance census prints in declaration order, so a member inserted above
    one already counted reorders a line readers of two gate runs compare. Asserted
    as the whole sequence rather than as `list(DiscoveredBy)[-1]`, because what the
    reader of two runs needs is that *none* of the five moved.
    """
    assert list(DiscoveredBy) == [
        DiscoveredBy.AUTHORED,
        DiscoveredBy.ADAPTIVE,
        DiscoveredBy.USER_GAP,
        DiscoveredBy.RETRIEVED,
        DiscoveredBy.ADAPTIVE_ON_TARGET,
        DiscoveredBy.TARGET_SPECIFIC,
    ]


def test_the_provenance_census_prints_six_members_in_declaration_order() -> None:
    """ADR-0107 §1's reason for the position, asked of the line it is about.

    The census is the artefact the ordering claim is *for*: a reader comparing two
    gate runs reads this line, so the assertion is on the printed order and not
    only on the enum's.
    """
    stated = library_provenance([]).stated()
    live = next(
        line for line in stated.splitlines() if line.startswith("provenance of")
    )
    printed = [member for member in DiscoveredBy if f"{member} 0" in live]
    # On `f"{member} "` rather than on the member's own text, because `adaptive` is
    # a prefix of `adaptive_on_target` and a substring search would find the wrong
    # one of the two the moment the order this test is about changed.
    named = sorted(printed, key=lambda member: live.index(f"{member} "))

    # Against a literal rather than against `list(DiscoveredBy)`, which is the
    # sequence the line is built from and so would agree with it however it moved.
    assert [str(member) for member in named] == [
        "authored",
        "adaptive",
        "user_gap",
        "retrieved",
        "adaptive_on_target",
        "target_specific",
    ]
    assert "retirement rate, target_specific: none written" in stated


def test_a_case_cannot_carry_the_held_route_provenance(library: list[Case]) -> None:
    """ADR-0117 §1 carried by the type rather than by a rule at a call site.

    A record claiming this provenance would be a held route inside the shared
    instrument — counted on a family's denominator and versioned into the library
    digest — so it is refused where every case record is built, which is
    `Case.__post_init__` calling `bar_for`.
    """
    with pytest.raises(NoAdmissionBar, match="faces no admission bar"):
        dataclasses.replace(
            library[0], discovered_by=DiscoveredBy.TARGET_SPECIFIC, admission=None
        )


def test_the_held_route_provenance_is_in_neither_half_of_the_adaptive_fraction(
    library: list[Case],
) -> None:
    """`found_by_the_attacker` answers `False` here, and #223 does not return.

    That defect needs a member a `Case` can carry, and the test above is why this
    one cannot: both counts are zero by construction, so the member is in neither
    the numerator nor the denominator of the fraction ADR-0012 §2 asks for.
    """
    provenance = library_provenance(library)

    assert provenance.live[DiscoveredBy.TARGET_SPECIFIC] == 0
    assert provenance.retired[DiscoveredBy.TARGET_SPECIFIC] == 0
    assert provenance.retirement_rate(DiscoveredBy.TARGET_SPECIFIC) is None
    assert found_by_the_attacker(DiscoveredBy.TARGET_SPECIFIC) is False
    assert DiscoveredBy.TARGET_SPECIFIC not in FOUND_BY_THE_ATTACKER


# --- The record --------------------------------------------------------------


def test_a_held_route_is_not_a_case_and_carries_the_sixth_provenance() -> None:
    """ADR-0117 §1, asserted of the type rather than of a call site.

    The fence is that no signature can be widened to take both, so the assertion a
    reader needs here is the negative one: a held route is not a `Case`, has no
    `id`, no `external_id`, no `admission` and no `history` — and the provenance it
    answers to is the one `bar_for` refuses.
    """
    held = a_held_route()

    assert not isinstance(held, Case)
    assert held.provenance is DiscoveredBy.TARGET_SPECIFIC
    assert held.family is Family.DATA_LEAKAGE
    assert held.target == A_CUSTOMER
    assert held.payload == (PROBE,)
    assert held.description == THE_ATTACKER_SAID
    assert held.found_in == THE_RUN_THAT_FOUND_IT
    assert held.state is HeldState.OPEN
    assert held.clean_runs == 0

    absent = {field.name for field in dataclasses.fields(Case)} - {
        field.name for field in dataclasses.fields(HeldRoute)
    }
    assert {"id", "external_id", "admission", "history", "discovered_by"} <= absent


def test_a_record_may_not_disagree_with_its_own_clean_run_count() -> None:
    """ADR-0117 §5 as an invariant of the record, in both directions.

    A closed route on one clean run is a fix reported on a coin-flip; an open route
    past the window is a probe the operator pays for on every run for a defect the
    bench has already answered.
    """
    with pytest.raises(ValueError, match="coin-flip"):
        a_held_route(state=HeldState.CLOSED, clean_runs=1)
    with pytest.raises(ValueError, match="costs the operator"):
        a_held_route(state=HeldState.OPEN, clean_runs=CLEAN_RUNS_TO_CLOSE)

    closed = a_held_route(state=HeldState.CLOSED, clean_runs=CLEAN_RUNS_TO_CLOSE)
    assert closed.state is HeldState.CLOSED


def test_a_held_route_with_nothing_to_send_is_refused() -> None:
    # Being re-sent on every run is the whole of what holding a route buys, so a
    # record that cannot be re-sent is not a held route at all (ADR-0117 §4).
    with pytest.raises(ValueError, match="nothing to send"):
        dataclasses.replace(a_held_route(), payload=())
    with pytest.raises(ValueError, match="finding about nobody"):
        dataclasses.replace(a_held_route(), target="  ")


# --- The store ---------------------------------------------------------------


def test_a_held_route_outlives_the_store_object_that_wrote_it(
    store_file: Path,
) -> None:
    """ADR-0019's acceptance criterion, applied to the fifth store.

    Write, drop the object, build a new one against the same location, read the
    route **and its clean-run count** back. The count is asserted because it is the
    field ADR-0019's argument is actually about: it lives on the record rather than
    being rebuilt by scanning run documents, so the file is the only thing that can
    carry it across a restart.
    """
    route = a_held_route(clean_runs=1)
    HeldRoutes.at(store_file).hold(route)

    restarted = HeldRoutes.at(store_file)
    found = restarted.held(A_CUSTOMER, route.route)

    assert found is not None, (
        f"a new store object against {store_file.name} read nothing back. A target "
        "library that does not survive the object that wrote it answers 'did my "
        "fix work?' with a set that empties itself every restart (ADR-0019)"
    )
    assert found == route
    assert found.clean_runs == 1
    assert found.payload == (PROBE,)
    assert found.success_condition.kind is SuccessConditionKind.CANARY_IN_REPLY


READ_BACK = """
import sys
from pathlib import Path

from backend.bench.decided import RouteKey
from backend.bench.held import HeldRoutes
from backend.bench.library import Family

held = HeldRoutes.at(Path(sys.argv[1]))
[route] = held.for_target(sys.argv[2])
print(route.target)
print(route.clean_runs)
print(route.state)
print(route.payload[0])
"""
"""A reader, as a program, because ADR-0019 point 4 says *in a new process*.

The test below writes the route and this reads it back, so what crosses is the file
and nothing else: no object, no import-time cache, no module state the writer left
behind. A round trip inside one interpreter cannot say that.
"""


def test_a_held_route_outlives_the_process_that_wrote_it(store_file: Path) -> None:
    """ADR-0019 point 4 at the one boundary that cannot be faked.

    The test above drops the store *object*; this drops the whole interpreter. Both
    are needed and the second is the stronger: a store that had quietly kept its
    contents in a module-level cache would satisfy the first and fail this.
    """
    HeldRoutes.at(store_file).hold(a_held_route(clean_runs=1))

    reader = subprocess.run(
        [sys.executable, "-c", READ_BACK, str(store_file), A_CUSTOMER],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=A_READER_HAS_FINISHED,
    )

    assert reader.returncode == 0, (
        f"a new process could not read the held route back:\n{reader.stderr}"
    )
    assert reader.stdout.splitlines() == [A_CUSTOMER, "1", "open", PROBE]


def test_one_route_is_one_held_record_however_often_it_is_rediscovered(
    store_file: Path,
) -> None:
    """ADR-0117 §1's key, asserted within one run and across two.

    Within one run: the same route held twice by one store object is one record.
    Across two: a second store object against the same file — the next run — holds
    it again and finds the first record, with the run that found it and the
    clean-run count it had. A replace here would reset a retirement window every
    time the attacker walked the same path again.
    """
    held = HeldRoutes.at(store_file)
    first = held.hold(a_held_route(clean_runs=1))
    again = held.hold(a_held_route(clean_runs=1))

    assert again == first
    assert len(held.for_target(A_CUSTOMER)) == 1

    next_run = HeldRoutes.at(store_file)
    rediscovered = next_run.hold(a_held_route(clean_runs=0, found_in="run-later"))

    assert rediscovered.found_in == THE_RUN_THAT_FOUND_IT
    assert rediscovered.clean_runs == 1
    assert len(next_run.for_target(A_CUSTOMER)) == 1


def test_one_route_against_two_targets_is_two_records(store_file: Path) -> None:
    """The other half of the key: a target library is per target and per route.

    Two agents that fail the same probe hold two independent records with two
    independent clean-run counts, and neither target's library shows the other's
    (ADR-0117 §1).
    """
    held = HeldRoutes.at(store_file)
    held.hold(a_held_route(target=A_CUSTOMER))
    held.hold(a_held_route(target=ANOTHER_CUSTOMER, clean_runs=1))

    [mine] = held.for_target(A_CUSTOMER)
    [theirs] = held.for_target(ANOTHER_CUSTOMER)

    assert mine.route == theirs.route
    assert mine.held_under != theirs.held_under
    assert mine.clean_runs == 0
    assert theirs.clean_runs == 1
    assert held.for_target("an agent nothing has been found against") == ()


def test_a_targets_library_holds_its_closed_routes_too(store_file: Path) -> None:
    # A closed route is kept rather than deleted: the report says "found on 3 March,
    # closed on 19 March", and a set that dropped it would answer "did my fix work?"
    # with silence (ADR-0117 §5).
    held = HeldRoutes.at(store_file)
    held.hold(a_held_route(probe=PROBE))
    held.hold(
        a_held_route(
            probe="a second probe",
            state=HeldState.CLOSED,
            clean_runs=CLEAN_RUNS_TO_CLOSE,
        )
    )

    states = {route.state for route in held.for_target(A_CUSTOMER)}

    assert states == {HeldState.OPEN, HeldState.CLOSED}


def test_every_route_ever_held_comes_back_and_not_one_page_of_them(
    store_file: Path,
) -> None:
    """`PAGE` is a page size and never a ceiling.

    "3 of 5 still open" is a fact only if the 5 is every route ever held, so a
    target library one page longer than the store's default read has to come back
    whole rather than truncated.
    """
    held = HeldRoutes.at(store_file)
    for index in range(PAGE + 3):
        held.hold(a_held_route(probe=f"probe {index}"))

    assert len(held.for_target(A_CUSTOMER)) == PAGE + 3


def test_the_store_is_a_database_and_an_in_memory_store_cannot_be_supplied() -> None:
    # ADR-0019 point 2, as `PendingRoutes.store` does it: the field is annotated
    # with the subclass rather than with `BaseStore`, so a future caller cannot hand
    # this store an `InMemoryStore` and there is nothing for a test to catch.
    annotations = {field.name: field.type for field in dataclasses.fields(HeldRoutes)}

    assert annotations["store"] == "HeldDatabase"


def test_the_target_libraries_are_their_own_database_and_not_the_pending_queue() -> (
    None
):
    # ADR-0029 decision 6 and the module docstring's argument: the fifth database on
    # the `DatabaseStore` seam. Its own file, because the queue holds what nothing
    # has measured yet and this holds what a decision produced.
    assert DEFAULT_HELD_PATH.parent == HELD_DIRECTORY
    assert HELD_DIRECTORY.name == "held"
    assert DEFAULT_HELD_PATH != DEFAULT_PENDING_PATH
    assert HELD_NAMESPACE != PENDING_NAMESPACE


@pytest.mark.parametrize(
    "name", ["routes.sqlite", "routes.sqlite-wal", "routes.sqlite-shm"]
)
def test_the_target_libraries_and_their_sidecars_are_ignored_by_git(name: str) -> None:
    """ADR-0117 §6's consequence, asked of git rather than of `.gitignore`'s text.

    The sidecars are parametrised rather than assumed covered: the journal holds
    both of the two fields ADR-0104's exception is granted for, so a sidecar is the
    sharpest case for this store as it is for `/pending/`.

    Built from `HELD_DIRECTORY` rather than from `DEFAULT_HELD_PATH`, because
    `conftest.py` redirects the store and never the directory.
    """
    if not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout, so git's own answer cannot be asked for")

    path = HELD_DIRECTORY / name
    checked = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPOSITORY, check=False
    )

    assert checked.returncode == 0, (
        f"{path} is not ignored by git, so a working probe against a named "
        "customer's agent is one `git add` away from being published"
    )


def test_the_store_a_run_reads_is_redirected_into_the_test_that_is_running(
    tmp_path: Path,
) -> None:
    """`conftest.held_elsewhere`, asserted rather than trusted.

    Against *this* test's `tmp_path` rather than merely against the real location,
    because a redirection that pointed every test at one shared file would satisfy
    "not the repository's own" and still let one test read what another held.
    """
    assert HELD_ROUTES.store.path == tmp_path / "held" / "routes.sqlite"
    assert HeldDatabase().path == tmp_path / "held" / "routes.sqlite"


# --- The case library is not moved by any of it ------------------------------


def test_holding_a_route_does_not_move_the_library_digest(
    library: list[Case], store_file: Path
) -> None:
    """ADR-0117's consequence, and the reason it is not a matter of taste.

    A digest that moved per target would give every customer a differently-versioned
    instrument, and the gate citation on their report would stop naming a thing that
    exists. Asserted over the committed library, read again after routes are held
    against two targets, because what the claim is about is `load_library` not
    reading this store at all.
    """
    before = LibraryVersion.of(library)

    held = HeldRoutes.at(store_file)
    held.hold(a_held_route(target=A_CUSTOMER))
    held.hold(a_held_route(target=ANOTHER_CUSTOMER))

    after = LibraryVersion.of(load_library(CASES_DIR))

    assert after == before
    assert after.cases == len(library)
    assert len(held.for_target(A_CUSTOMER)) == 1
