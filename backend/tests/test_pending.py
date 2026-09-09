"""The fourth store: a route awaiting the decision the run that found it cannot make.

What is asserted here is mostly what the store *cannot* hold, because that is what
[ADR-0104](../../docs/adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md)
grants the exception on. Three seams:

1. **The record** — `AwaitingDecision` and `Decided`, and the field the second one
   does not have. The payload is emptied by the type rather than by a caller
   remembering to clear a column (ADR-0104 §4).
2. **The store** — `PendingRoutes.file`, `.filed`, `.queue` and `.decide`, keyed on
   `decided.RouteKey` so that a route filed twice is one record.
3. **Where it is** — one location, git-ignored with its sidecars, and a namespace
   with no tenant segment.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from backend.bench import pending
from backend.bench.adaptive.proposal import ProposedRoute, proposed_from
from backend.bench.decided import DECISION_NAMESPACE, RouteKey, criterion_of
from backend.bench.library import Case, Family
from backend.bench.pending import (
    DEFAULT_PENDING_PATH,
    PENDING_DIRECTORY,
    PENDING_NAMESPACE,
    PENDING_ROUTES,
    AwaitingDecision,
    Decided,
    NotAwaitingDecision,
    NotFiled,
    PendingRoutes,
    RouteState,
)
from backend.tests.conftest import REPOSITORY, a_target

FILED_ON = date(2026, 8, 30)
"""The day the run that found the route ended, so nothing here reads a clock.

Deliberately not today: a store that read a clock instead of the date it was given
would date a route filed by a replayed run to the morning it was replayed, and a
date equal to today's is a date that assertion could not tell apart.
"""

PROBE = "the probe that actually beat somebody's agent"

A_CUSTOMER = "acme-support-bot"
"""The target identity the queue is triaged on — ADR-0104 §2, and the one field no
other store in this repository carries."""


def a_route(
    objective: Case,
    payload: str = PROBE,
    description: str = "a route worth deciding",
) -> ProposedRoute:
    """One proposal, drafted the way `propose_case` drafts it inside an episode."""
    return proposed_from(
        objective=objective,
        target=a_target("trivial"),
        family=Family(objective.family),
        payload=payload,
        description=description,
        today=FILED_ON,
    )


@pytest.fixture
def queue(tmp_path: Path) -> PendingRoutes:
    """This test's own queue, under a directory that is not there yet.

    Not there yet on purpose, on `test_decided.memory`'s reasoning: the store
    creates its parent, and a fixture that pre-made it would hide a backend that
    could only open a database beside an existing directory.
    """
    return PendingRoutes.at(tmp_path / "pending" / "routes.sqlite")


# --- Seam one: the record, and the field a decided one does not have ---------


def test_a_filed_route_carries_the_draft_the_prose_the_target_and_the_date(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # The queue's whole purpose is that a person reads it and decides which routes
    # are worth paying to measure (ADR-0104 §2), and the decision is taken by
    # *sending the probe* (§1). So both halves are on the record: what a decision
    # needs, and what triage needs.
    proposal = a_route(leakage_case)

    filed = queue.file(proposal, target=A_CUSTOMER, today=FILED_ON)

    assert filed.route == RouteKey.of(proposal.case)
    assert filed.draft.payload == proposal.case.payload
    assert filed.description == proposal.description
    assert filed.target == A_CUSTOMER
    assert filed.filed_on == FILED_ON
    assert filed.criterion == criterion_of(proposal.case)
    assert filed.state is RouteState.PENDING


def test_a_filed_route_read_back_out_of_the_database_still_carries_its_probe(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # ADR-0104 §1: a route that cannot be re-run cannot be measured later, and the
    # bar is decided by sending the probe. A queue that lost the payload on the way
    # to disk is the present failure with a database in front of it.
    proposal = a_route(leakage_case)
    queue.file(proposal, target=A_CUSTOMER, today=FILED_ON)

    found = queue.filed(RouteKey.of(proposal.case))

    assert isinstance(found, AwaitingDecision)
    assert found.draft.payload == (PROBE,)
    assert found.draft.id == proposal.case.id
    assert found.draft.admission is None
    assert found.target == A_CUSTOMER


def test_a_decided_record_has_no_payload_field_at_all(leakage_case: Case) -> None:
    # ADR-0104 §4, and this is the assertion that survives a refactor: the
    # prohibition is carried by the type, so violating it means widening one, which
    # is a visible act. A convention that says *clear the payload when you decide*
    # has one forgetful call site between it and a store of live exploits.
    on_a_decided_record = {field.name for field in dataclasses.fields(Decided)}
    on_a_pending_one = {field.name for field in dataclasses.fields(AwaitingDecision)}

    assert "draft" in on_a_pending_one
    assert "draft" not in on_a_decided_record
    assert not hasattr(Decided, "draft")
    assert on_a_decided_record < on_a_pending_one | {"reason", "state"}


# --- Seam two: the store, keyed on the route --------------------------------


def test_a_route_filed_twice_is_one_record_and_the_second_replaces_the_first(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # Keyed on `decided.RouteKey` — the same family-plus-probe digest the memory
    # and the library de-duplicate on — so an attacker that rediscovers a path
    # every run does not fill the queue with copies of it (spec, user story 4).
    first = a_route(leakage_case, description="found it once")
    second = a_route(leakage_case, description="found it again")
    assert first.case.id != second.case.id

    queue.file(first, target=A_CUSTOMER, today=FILED_ON)
    queue.file(second, target=A_CUSTOMER, today=FILED_ON)

    assert len(queue.queue()) == 1
    found = queue.filed(RouteKey.of(second.case))
    assert isinstance(found, AwaitingDecision)
    assert found.description == "found it again"


def test_two_probes_against_two_targets_are_two_records(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # Three routes filed against three agents and three filed against one are
    # different situations and call for different decisions (ADR-0104 §2).
    queue.file(a_route(leakage_case, payload="one probe"), target=A_CUSTOMER)
    queue.file(a_route(leakage_case, payload="another probe"), target="other-bot")

    assert {record.target for record in queue.queue()} == {A_CUSTOMER, "other-bot"}
    assert len(queue.queue()) == 2


def test_a_route_nothing_filed_reads_back_as_nothing(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # ADR-0029 point 7: reading a store nothing has written answers without
    # creating one, so a queue nobody has filed into leaves no database behind.
    assert queue.filed(RouteKey.of(a_route(leakage_case).case)) is None
    assert queue.queue() == ()
    assert not queue.store.path.exists()


def test_a_decision_replaces_the_record_and_the_payload_is_gone_from_the_store(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # Asserted on the store and not on the API, which is the spec's own testing
    # decision: mitigation 5 is that the two fields this exception was granted for
    # exist only for routes still awaiting a decision.
    proposal = a_route(leakage_case)
    queue.file(proposal, target=A_CUSTOMER, today=FILED_ON)
    route = RouteKey.of(proposal.case)

    decided = queue.decide(route, state=RouteState.ADMITTED, reason="D = 1.00 on both")

    stored = queue.store.get(PENDING_NAMESPACE, route.filed_under)
    assert stored is not None
    assert "draft" not in dict(stored.value)
    assert PROBE not in json.dumps(dict(stored.value))
    assert decided == queue.filed(route)
    assert isinstance(decided, Decided)
    assert decided.state is RouteState.ADMITTED
    assert decided.reason == "D = 1.00 on both"
    assert decided.route == route
    assert decided.criterion == criterion_of(proposal.case)
    assert decided.target == A_CUSTOMER
    assert len(queue.queue()) == 1


def test_a_rejected_route_keeps_the_gates_own_reason(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # ADR-0012 calls a cross-model discard a finding in its own right, so a
    # rejected route stays on the page with the reason it was rejected for (spec,
    # user story 12).
    proposal = a_route(leakage_case)
    queue.file(proposal, target=A_CUSTOMER, today=FILED_ON)

    decided = queue.decide(
        RouteKey.of(proposal.case),
        state=RouteState.REJECTED,
        reason="separated on one model and nowhere on the second",
    )

    assert decided.state is RouteState.REJECTED
    assert "second" in decided.reason


def test_a_decision_with_no_reason_is_refused(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # A rejected route is a finding in its own right (ADR-0012), and a row that
    # says only "rejected" is the finding thrown away — which is the defect the
    # store exists to remove, one field further in.
    proposal = a_route(leakage_case)
    queue.file(proposal, target=A_CUSTOMER, today=FILED_ON)

    with pytest.raises(ValueError, match="no reason"):
        queue.decide(
            RouteKey.of(proposal.case), state=RouteState.REJECTED, reason="   "
        )


def test_deciding_a_route_nothing_filed_is_refused(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # Refused rather than invented: the target, the prose and the criterion come
    # off the filed record, and a decision that minted them would be a queue row
    # about a route this store never held.
    with pytest.raises(NotFiled):
        queue.decide(
            RouteKey.of(a_route(leakage_case).case),
            state=RouteState.REJECTED,
            reason="nothing to decide",
        )


def test_deciding_a_route_twice_is_refused(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # The second decision would be a decision about a route whose payload this
    # store no longer holds — nothing could have measured it — so it is refused
    # rather than allowed to overwrite the first answer.
    proposal = a_route(leakage_case)
    queue.file(proposal, target=A_CUSTOMER, today=FILED_ON)
    route = RouteKey.of(proposal.case)
    queue.decide(route, state=RouteState.ADMITTED, reason="admitted")

    with pytest.raises(NotAwaitingDecision):
        queue.decide(route, state=RouteState.REJECTED, reason="second thoughts")


def test_a_decided_state_is_not_pending(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # `Decided` is the two decided states and never the third: a record in the
    # pending state with no payload would be a route awaiting a decision that
    # nothing could ever measure.
    with pytest.raises(ValueError, match="pending"):
        Decided(
            route=RouteKey.of(a_route(leakage_case).case),
            criterion="whatever",
            description="a route",
            target=A_CUSTOMER,
            filed_on=FILED_ON,
            state=RouteState.PENDING,
            reason="undecided",
        )


def test_a_filed_route_survives_the_process_that_filed_it(
    tmp_path: Path, leakage_case: Case
) -> None:
    # ADR-0019 point 4 and the whole point of the store: a route found against a
    # real agent survives the run that found it. Two `PendingRoutes` over one file
    # rather than one, because the object holds no state — not even a connection —
    # and the file is the authority (ADR-0029 decision 2).
    path = tmp_path / "pending" / "routes.sqlite"
    proposal = a_route(leakage_case)
    PendingRoutes.at(path).file(proposal, target=A_CUSTOMER, today=FILED_ON)

    found = PendingRoutes.at(path).filed(RouteKey.of(proposal.case))

    assert isinstance(found, AwaitingDecision)
    assert found.draft.payload == (PROBE,)


# --- Seam three: where it is, and what git does with it ----------------------


def test_the_namespace_is_single_tenant_and_has_no_tenant_in_it() -> None:
    # `PRECEDENT_NAMESPACE`'s and `DECISION_NAMESPACE`'s reasoning, restated once
    # more: cross-tenant isolation is a named P1 blocker (PLAN §11), so it has to
    # be a visible absence rather than an assumed presence. A third segment naming
    # a user would look like isolation and enforce none — and it would look most
    # like it here, since this is the one store that knows whose agent it is about.
    assert PENDING_NAMESPACE == ("agentaudit", "pending")
    assert len(PENDING_NAMESPACE) == 2


def test_the_queue_is_its_own_database_and_not_a_table_in_the_admission_memory() -> (
    None
):
    # ADR-0029 decision 6 and ADR-0104 §5: the fourth database on the
    # `DatabaseStore` seam. Its own file, because the memory holds what the gate
    # measured and this holds what nothing has measured yet.
    assert DEFAULT_PENDING_PATH.parent == PENDING_DIRECTORY
    assert PENDING_DIRECTORY.name == "pending"
    assert PENDING_NAMESPACE != DECISION_NAMESPACE


@pytest.mark.parametrize(
    "name", ["routes.sqlite", "routes.sqlite-wal", "routes.sqlite-shm"]
)
def test_the_queue_and_its_sidecars_are_ignored_by_git(name: str) -> None:
    """ADR-0104's consequences, and the reason is stronger here than anywhere.

    Asked of git rather than of `.gitignore`'s text, on `test_decided.py`'s
    reasoning, and the sidecars are parametrised rather than assumed covered: here
    the sidecar holds both of the two fields the exception was granted for — a
    working probe, and the name of the agent it beat.

    Built from `PENDING_DIRECTORY` rather than from `DEFAULT_PENDING_PATH`, because
    `conftest.py` redirects the store and never the directory.
    """
    if not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout, so git's own answer cannot be asked for")

    path = PENDING_DIRECTORY / name
    checked = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPOSITORY, check=False
    )

    assert checked.returncode == 0, (
        f"{path} is not ignored by git, so a working probe against a named "
        "customer's agent is one `git add` away from being published"
    )


def test_the_store_is_a_database_and_an_in_memory_store_cannot_be_supplied() -> None:
    # ADR-0019 point 2, as `DecidedRoutes.store` does it: the field is annotated
    # with the subclass rather than with `BaseStore`, so a future caller cannot
    # hand this store an `InMemoryStore` and there is nothing for a test to catch.
    annotations = {
        field.name: field.type for field in dataclasses.fields(PendingRoutes)
    }

    assert annotations["store"] == "PendingDatabase"


def test_the_queue_a_run_reads_is_redirected_into_the_test_that_is_running(
    tmp_path: Path,
) -> None:
    """`conftest.pending_elsewhere`, asserted rather than trusted.

    Against *this* test's `tmp_path` rather than merely against the real location,
    on `test_decided.py`'s reasoning and with one addition: what a test that
    reached the real file would leave in the working copy is a working probe and a
    target's name, which is the one thing this repository has decided may never be
    committed (ADR-0008, ADR-0104).
    """
    for live in _live_queue_paths():
        assert live != DEFAULT_PENDING_PATH, (
            "a test can reach the queue a real run files into, so a test's route "
            "is filed beside the engineer's own — with a payload and a target name"
        )
        assert live.is_relative_to(tmp_path), (
            f"{live} is not under this test's own directory, so one test's filed "
            "route is what the next test's queue reads back"
        )


@pytest.fixture(scope="module")
def queue_at_module_setup() -> tuple[Path, ...]:
    """The live paths, read while a *module-scoped* fixture is being built.

    The window the equivalent defect lived in for the precedent store, recorded in
    ADR-0029's consequences and pre-empted for the third time here rather than
    rediscovered for the third time.
    """
    return _live_queue_paths()


def test_no_module_scoped_fixture_escapes_the_redirection(
    queue_at_module_setup: tuple[Path, ...],
) -> None:
    """The session-scoped half of the redirection, asserted from the scope that
    escaped the precedent store's."""
    for live in queue_at_module_setup:
        assert live != DEFAULT_PENDING_PATH, (
            "a module-scoped fixture is built outside the per-test redirection, so "
            "any run one of them makes files its routes into the working copy"
        )


def _live_queue_paths() -> tuple[Path, ...]:
    """Every route to the queue, as it stands at the moment of the call.

    Two of them, because `conftest._pending_at` redirects two and a redirection
    that missed one would leave a route into the working copy. Read off the module
    rather than off the name this file imported, because the fixture patches the
    module and an imported constant answers with the value it had at import — which
    is the real location, and is what the git question above relies on.
    """
    return (pending.DEFAULT_PENDING_PATH, PENDING_ROUTES.store.path)
