"""The filing half: a customer run's proposals survive the run that found them.

The store is `test_pending.py`. What is asserted here is the *write* — who makes it,
who must not, and what a run says about having made it. Four seams:

1. **`queued.file_proposals`** — one record per route off a run's episodes, keyed on
   `decided.RouteKey`, the target read off the episode, and a store that refuses
   reported rather than raised.
2. **`POST /runs`** — a customer run, start to finish, and the queue afterwards.
3. **`scripts/bench.py`** — the same run from a `__main__`, and the queue afterwards.
4. **`POST /gate-runs`** — a gate run, start to finish, leaving the queue as it found
   it, and no module on that side able to reach the store at all.

The seam is the customer-run entry points and deliberately not `run_calibration`,
which is shared with gate runs: filing there would fill a queue whose purpose is
routes no surface decides with reference-agent routes `scripts/swap.py` already
decides (`docs/specs/pending-routes.md`).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from backend.api.gate_runs import GateRunStatus
from backend.api.run_status import RunStatus
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.adaptive.precedent import Precedent
from backend.bench.adaptive.proposal import ProposedRoute, proposed_from
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.decided import DecidedRoute, RouteKey
from backend.bench.library import Case, DiscoveredBy, Family
from backend.bench.pending import (
    PENDING_ROUTES,
    AwaitingDecision,
    PendingDatabase,
    PendingRoutes,
    RouteState,
)
from backend.bench.queued import file_proposals
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.graph.budget import BudgetExceeded, Layer
from backend.graph.runstate import RunState
from backend.tests import headless_agent
from backend.tests.conftest import BENCH, REPOSITORY, a_target, reachable_from
from backend.tests.headless_agent import RecordingAgent
from backend.tests.test_api_gate_runs import (
    API_DIR as API,
)
from backend.tests.test_api_gate_runs import (
    GATE_RUN_MODULES,
    a_bench,
    a_confirmation,
    a_library,
    approval_of,
    started,
)
from backend.tests.test_api_gate_runs import settled as gate_settled
from backend.tests.test_api_runs import (
    _record,
    a_request,
    api,
    registered,
    settled,
    watched_reference,
)
from backend.tests.test_headless_run import arguments, attestation_file
from scripts import bench
from scripts.console import EXIT_ABORTED

THE_RUN = "run-2026-08-30-0004"
"""The run whose attacker found the routes below, as an entry point names it.

Not derivable from an episode: `AdaptiveEpisode` records what the attacker did and
not which run it did it in, so the run travels from the entry point beside the day
(`queued.file_proposals`).
"""

RAN_ON = date(2026, 8, 30)
"""The day the run ended. Deliberately not today's date: a filing that read a clock
instead of the date the run passed it would date a replayed run's route to the
morning it was replayed, and a date equal to today's could not tell the two apart."""

A_CUSTOMER = "acme-support-bot"
"""Whose agent the route was found against — the field ADR-0104 §2 grants and the
one thing triage cannot do without."""


def a_route(
    objective: Case,
    payload: str = "the probe that actually beat somebody's agent",
    description: str = "a route worth deciding",
) -> ProposedRoute:
    """One proposal, drafted the way `propose_case` drafts it inside an episode."""
    return proposed_from(
        objective=objective,
        target=a_target("trivial"),
        family=Family(objective.family),
        payload=payload,
        description=description,
        today=RAN_ON,
        broken=True,
        discovered_by=DiscoveredBy.ADAPTIVE,
    )


def an_episode(
    objective: Case,
    *proposals: ProposedRoute,
    target: str = A_CUSTOMER,
) -> AdaptiveEpisode:
    """One recorded episode against one named target, carrying those proposals."""
    return AdaptiveEpisode(
        target_name=target,
        family=Family(objective.family),
        outcome=EpisodeOutcome.BROKEN,
        turns=1,
        proposals=tuple(proposals),
    )


@dataclass(frozen=True)
class RefusesOneRoute(PendingRoutes):
    """A queue whose database refuses one named route and takes every other.

    A subclass rather than a patched attribute, because `PendingRoutes` is frozen
    and deliberately is — and because what has to be exercised is a real store that
    fails on one write, not a stand-in for one: the route after the refusal has to
    reach the database it would have reached.
    """

    refused: RouteKey | None = None

    def file(
        self, proposal: ProposedRoute, *, target: str, found_in: str, today: date
    ) -> AwaitingDecision:
        if RouteKey.of(proposal.case) == self.refused:
            raise OSError("the queue's database is not writable")
        return super().file(proposal, target=target, found_in=found_in, today=today)


@pytest.fixture
def queue(tmp_path: Path) -> PendingRoutes:
    """This test's own queue, at a directory that is not there yet."""
    return PendingRoutes.at(tmp_path / "pending" / "routes.sqlite")


# --- Seam one: what a run's episodes file --------------------------------------


def test_a_runs_proposals_are_filed_with_the_target_the_episode_beat(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # The interesting output of a customer run used to be a printed line. This is
    # the whole of the ticket: the route is on disk afterwards, and the row says
    # whose agent it beat — read off the episode's own record rather than handed in
    # beside it, so a run against two targets cannot file one under the other's name.
    proposal = a_route(leakage_case)

    filed = file_proposals(
        [an_episode(leakage_case, proposal)],
        queue=queue,
        today=RAN_ON,
        found_in=THE_RUN,
    )

    assert [record.route for record in filed.filed] == [RouteKey.of(proposal.case)]
    assert not filed.refusals
    held = queue.filed(RouteKey.of(proposal.case))
    assert isinstance(held, AwaitingDecision)
    assert held.target == A_CUSTOMER
    assert held.draft.payload == proposal.case.payload
    assert held.filed_on == RAN_ON
    assert held.state is RouteState.PENDING


def test_four_proposals_of_one_route_are_one_record_within_a_run_and_across_runs(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # `docs/validation.md` records a run whose four proposals all described one
    # path. The key is `decided.RouteKey` — the same family-plus-probe-digest the
    # memory and the library de-duplicate on — so one route is one pending record,
    # and the report of the filing has to agree with the one row on disk.
    proposal = a_route(leakage_case)
    four = [an_episode(leakage_case, proposal) for _ in range(4)]

    within = file_proposals(four, queue=queue, today=RAN_ON, found_in=THE_RUN)
    across = file_proposals(
        [an_episode(leakage_case, proposal)],
        queue=queue,
        today=RAN_ON,
        found_in=THE_RUN,
    )

    assert len(within.filed) == 1
    assert len(across.filed) == 1
    assert len(queue.queue()) == 1


def test_a_run_that_proposed_nothing_files_nothing_and_says_so(
    queue: PendingRoutes, leakage_case: Case
) -> None:
    # A zero is a reading about the attacker and about the families it worked in,
    # never about the target (ADR-0011). An entry point that printed nothing here
    # would leave an operator unable to tell a queue that grew by nothing from a
    # filing that was never attempted.
    nothing = file_proposals(
        [an_episode(leakage_case)], queue=queue, today=RAN_ON, found_in=THE_RUN
    )

    assert nothing.filed == ()
    assert nothing.refusals == ()
    assert queue.queue() == ()
    assert "proposed no route" in nothing.stated()
    assert "ADR-0011" in nothing.stated()


def test_a_store_that_refuses_is_reported_and_the_rest_of_the_routes_still_file(
    tmp_path: Path, leakage_case: Case
) -> None:
    # Filing cannot fail a run, and it cannot fail the route after the one that
    # refused either: the suite ran and the target was measured, so what a storage
    # fault costs is a row and never a measurement (`runs._filed`'s argument).
    first = a_route(leakage_case)
    second = a_route(leakage_case, payload="a second route, and a second digest")
    refusing = RefusesOneRoute(
        store=PendingDatabase(tmp_path / "pending" / "routes.sqlite"),
        refused=RouteKey.of(first.case),
    )

    both = file_proposals(
        [an_episode(leakage_case, first, second)],
        queue=refusing,
        today=RAN_ON,
        found_in=THE_RUN,
    )

    assert [record.route for record in both.filed] == [RouteKey.of(second.case)]
    assert len(both.refusals) == 1
    assert "not writable" in both.refusals[0]
    assert "measurement stands" in both.stated()
    # And the run is not the thing that failed: the second route is on disk.
    assert len(refusing.queue()) == 1


# --- Seam two: a customer run over the API ------------------------------------


def test_a_customer_run_files_its_proposals_and_says_so_on_its_own_record(
    leakage_case: Case,
) -> None:
    """The ticket, end to end on `POST /runs`: the queue is not empty afterwards.

    Driven all the way through the interrupt, because what is under test is the
    entry point rather than the function it calls: a filing wired into anything
    `run_calibration` reaches would pass a unit test and put reference-agent routes
    in front of an operator.
    """
    narrow = AdaptiveBudget(turns_per_episode=6, episodes_per_family=1, family_count=1)
    with (
        watched_reference() as watched,
        api([leakage_case], adaptive=narrow) as (
            client,
            bench,
        ),
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = _record(bench, started)
        client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": True},
        )
        settled(record)

    assert record.status is RunStatus.COMPLETED
    proposed = {
        RouteKey.of(proposal.case)
        for episode in record.run_state.episodes
        for proposal in episode.proposals
    }
    assert proposed, "the attacker proposed nothing, so nothing here is under test"

    held = PENDING_ROUTES.queue()
    assert {record_.route for record_ in held} == proposed
    # The target the route was found against, on every row: the one field no other
    # store in this repository carries, and the whole of what triage runs on
    # (ADR-0104 §2).
    assert {record_.target for record_ in held} == {watched.target.name}
    assert all(isinstance(record_, AwaitingDecision) for record_ in held)
    # The date the run went on the record, not the day the row was written: nothing
    # between the entry point and the store reads a clock.
    assert {record_.filed_on for record_ in held} == {record.recorded_at.date()}
    # And the run itself, which is the record a reader opens for the rest — its
    # declaration, its target and its date. A route decided months from now is held
    # under this id and under nothing this surface invents (`held.HeldRoute`).
    assert {record_.found_in for record_ in held} == {record.run_id}
    # And the sentence a poller reads says the queue grew, beside what the run said
    # about precedent and about its review queue.
    assert "awaiting a decision" in record.statement


# --- Seam three: the same run from a `__main__` -------------------------------


def test_a_headless_customer_run_files_its_proposals_and_prints_what_it_filed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`scripts/bench.py`, the second customer-run entry point, end to end.

    Both entry points and not one, because a workflow run is the shape in which a
    route is *most* likely to be found and least likely to be looked at: nobody is
    sitting in front of it, so a proposal it does not file is a proposal nobody ever
    reads. Against the trivial reference agent with a nonce planted by hand, which
    is what an operator does before an unattended run (ADR-0061, ADR-0064) — a run
    that waived the proof would have its leakage cases withdrawn for want of a
    plant and so no leakage episode to propose from.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    with watched_reference() as watched:
        nonce = "a-nonce-the-operator-planted"
        watched.plant(watched.target, nonce, "by-hand")
        code = bench.main(
            [
                *arguments(
                    watched.target.url,
                    tmp_path / "artefact",
                    attestation_file(tmp_path, watched.target.url),
                    **{
                        "--max-calls": "100000",
                        "--token": str(watched.target.auth_token),
                        "--nonce": nonce,
                        # The identity the operator declared for their own agent,
                        # which is the name that reaches the row: what triage needs
                        # is whose agent, and the record deliberately holds no url
                        # and no token to reach it by (ADR-0104 §2).
                        "--name": A_CUSTOMER,
                    },
                )
            ]
        )

    assert code == 0
    said = capsys.readouterr().out
    held = PENDING_ROUTES.queue()
    assert held, "the attacker proposed nothing, so nothing here is under test"
    assert {record.target for record in held} == {A_CUSTOMER}
    assert all(isinstance(record, AwaitingDecision) for record in held)
    # The job log says what it filed, in the same run of output that carries the
    # rates and the precedent: an unattended run's output is all anybody reads.
    assert "awaiting a decision" in said
    for record in held:
        assert record.route.stated() in said


def test_a_headless_run_whose_attacker_proposed_nothing_says_so_and_files_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The zero, end to end, against an agent that refuses everything.

    A zero is a reading about the attacker and about the families it worked in,
    never about the target (ADR-0011) — so it is printed rather than left as an
    absence, which is the one thing an operator could not tell apart from a filing
    that was never attempted.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    agent = RecordingAgent()
    monkeypatch.setattr(headless_agent, "AGENT", agent)
    reference = "backend.tests.headless_agent:AGENT"

    code = bench.main(
        [
            *arguments(
                reference,
                tmp_path / "artefact",
                attestation_file(tmp_path, reference),
                **{"--max-calls": "100000"},
            )[:-1],
            f"--callback={reference}",
        ]
    )

    assert code == 0
    assert agent.messages, "the run reached the target"
    assert PENDING_ROUTES.queue() == ()
    assert "proposed no route" in capsys.readouterr().out


# --- Seam four: a gate run, which files nothing -------------------------------


def test_a_gate_run_leaves_the_pending_queue_as_it_found_it(
    tmp_path: Path, leakage_case: Case
) -> None:
    """Start to finish, and the queue afterwards is the queue from before.

    The routes awaiting a decision have to be the ones no surface decides. A gate
    run's proposals are fitted to the three reference agents — the exact population
    ADR-0012 built the cross-model bar around — and `scripts/swap.py` already walks
    the whole path for them: consult the memory, measure on two models, decide,
    remember, write. Filing them here would fill a triage page with routes already
    decided, in front of an operator reading it as findings about a customer.

    Asserted against a route filed *before* the run, so that *unchanged* is a
    comparison rather than an empty store asserted equal to an empty store — and
    asserted alongside the proposals the gate run's own attacker made, so a run
    that proposed nothing cannot make this pass by accident.
    """
    before = PENDING_ROUTES.file(
        a_route(leakage_case), target=A_CUSTOMER, found_in=THE_RUN, today=RAN_ON
    )

    with a_bench(a_library(tmp_path), attempts_per_case=1) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        gate_settled(record)

    assert record.status is GateRunStatus.DECIDED
    proposed = [
        proposal
        for episode in record.run_state.episodes
        for proposal in episode.proposals
    ]
    assert proposed, "the gate run's attacker proposed nothing, so nothing is tested"
    assert PENDING_ROUTES.queue() == (before,)


def test_no_gate_run_surface_can_reach_the_filing_at_all() -> None:
    """The same wall as a reachability question, which is the half that survives.

    The test above is about one gate run. This is about every gate run there will
    ever be: `queued.file_proposals` is unreachable from the gate-run side, from
    `run_calibration` — which both kinds of run take, and which is why the filing
    is at the entry points instead — and from the two command-line surfaces whose
    targets are the three reference agents.

    A reachability question and not an import one, on `test_pending.py`'s
    reasoning: a module that imports a module that imports this one has reached it,
    so a filing added two layers down is caught here rather than by the next
    operator to read a triage page full of routes about the bench itself.
    """
    for source in (
        *(API / name for name in GATE_RUN_MODULES),
        BENCH / "calibration.py",
        REPOSITORY / "scripts" / "gate.py",
        REPOSITORY / "scripts" / "swap.py",
    ):
        reachable = [name for name in reachable_from(source) if "bench.queued" in name]
        assert not reachable, (
            f"{reachable} is reachable from {source.name}. A gate run's routes are "
            "fitted to the three reference agents and `scripts/swap.py` already "
            "decides them, so filing them would fill a triage page with routes no "
            "operator asked about and none of them about a customer (ADR-0012)"
        )


def test_the_filed_route_is_the_only_record_in_the_repository_naming_a_target() -> None:
    """The other half of the identity being filed: nowhere else may hold it.

    ADR-0104 grants this store the target identity as an **exception**, and an
    exception is only bounded if the rule it is an exception to still holds. So the
    four durable records are asked what fields they have, and exactly one of them
    answers with a target: the one that also carries the payload, which is what
    makes it the exception rather than a fifth store with a name on it.

    Asked of the record types rather than of the databases, on `Decided`'s
    reasoning: a record with no field for a thing cannot be made to hold it by a
    caller, and that is the half that survives a refactor (ADR-0104 §4).
    """
    named = {
        store: sorted(
            field.name for field in dataclasses.fields(record) if "target" in field.name
        )
        for store, record in (
            ("precedent/findings.sqlite", Precedent),
            ("decisions/routes.sqlite", DecidedRoute),
            ("the case library", Case),
            ("pending/routes.sqlite", AwaitingDecision),
        )
    }

    assert named == {
        "precedent/findings.sqlite": [],
        "decisions/routes.sqlite": [],
        "the case library": [],
        "pending/routes.sqlite": ["target"],
    }, (
        "the target identity is written down somewhere beside the pending queue. "
        "ADR-0011's rule is that precedent carries no target identity to anything "
        "blinded, and ADR-0104's exception is granted on this store being the only "
        "one that departs from it"
    )
    # And it is beside a payload here, which is the whole of why it is an exception
    # rather than a fifth store that happens to carry a name.
    assert "draft" in {field.name for field in dataclasses.fields(AwaitingDecision)}


# --- What an aborted run keeps ------------------------------------------------


def test_a_run_the_ceiling_aborted_still_files_what_its_attacker_had_found(
    leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that ended on its ceiling ended, and its routes are not lost with it.

    The run most likely to be cut short mid-layer is the run whose attacker was
    still finding things, and `RunState.episodes` holds every episode that finished
    before the ceiling bit. A filing reachable only from the completed path would
    discard exactly those — which is the defect this whole module removes, narrowed
    to the runs an operator paid the most for.

    The abort is raised *after* the real run rather than by starving the layer into
    one, so the routes filed here are routes an attacker actually found: a ceiling
    small enough to bite after an episode that proposed is a figure two budget rules
    away from anything this assertion is about, and the interrupt this run halts at
    lives inside `run_calibration` and has to keep happening.
    """

    def aborts_once_it_has_run(**passed: object) -> CalibrationResult:
        run_calibration(**passed)  # type: ignore[arg-type]
        raise BudgetExceeded(layer=Layer.ADAPTIVE, ceiling=4, spent=5, requested=0)

    monkeypatch.setattr("backend.api.runs.run_calibration", aborts_once_it_has_run)
    narrow = AdaptiveBudget(turns_per_episode=6, episodes_per_family=1, family_count=1)

    with (
        watched_reference() as watched,
        api([leakage_case], adaptive=narrow) as (
            client,
            served,
        ),
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = _record(served, started)
        client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": True},
        )
        settled(record)

    assert record.status is RunStatus.ABORTED
    proposed = {
        RouteKey.of(proposal.case)
        for episode in record.run_state.episodes
        for proposal in episode.proposals
    }
    assert proposed, "the attacker proposed nothing, so nothing here is under test"
    assert {held.route for held in PENDING_ROUTES.queue()} == proposed
    assert "awaiting a decision" in record.statement


def test_a_headless_run_the_ceiling_aborted_files_what_its_attacker_had_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same for the unattended entry point, which has to hold its own state.

    `run_calibration` builds a `RunState` for a caller that hands it none, and a
    caller that let it do so has no way to read the episodes back out of a run that
    raised instead of returning — so this entry point declares the state before the
    run rather than reading it off a result that never arrived. The assertion that
    it does is the `run_state` this stand-in insists on being handed.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))

    def aborts_once_it_has_run(**passed: object) -> CalibrationResult:
        state = passed.get("run_state")
        assert isinstance(state, RunState), (
            "the unattended entry point handed `run_calibration` no run state, so "
            "the episodes of a run it aborts are unreachable and its routes are "
            "lost with it"
        )
        run_calibration(**passed)  # type: ignore[arg-type]
        raise BudgetExceeded(layer=Layer.ADAPTIVE, ceiling=4, spent=5, requested=0)

    monkeypatch.setattr("scripts.bench.run_calibration", aborts_once_it_has_run)
    with watched_reference() as watched:
        nonce = "a-nonce-the-operator-planted"
        watched.plant(watched.target, nonce, "by-hand")
        code = bench.main(
            [
                *arguments(
                    watched.target.url,
                    tmp_path / "artefact",
                    attestation_file(tmp_path, watched.target.url),
                    **{
                        "--max-calls": "100000",
                        "--token": str(watched.target.auth_token),
                        "--nonce": nonce,
                        "--name": A_CUSTOMER,
                    },
                )
            ]
        )

    assert code == EXIT_ABORTED
    held = PENDING_ROUTES.queue()
    assert held, "the attacker proposed nothing, so nothing here is under test"
    assert {record.target for record in held} == {A_CUSTOMER}
    assert "awaiting a decision" in capsys.readouterr().out
