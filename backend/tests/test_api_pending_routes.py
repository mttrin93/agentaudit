"""What `/pending-routes` refuses, what it declares, and what a decision leaves.

The surface
[ADR-0105](../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)
decides exists, so most of what is asserted here is that the two controls every
other spending surface carries came with it, and that the three kinds of record
stayed apart.

**That approval is a refusal and not a flag.** Each of the three attestation
statements is refused on its own, before anything is sent and before the library is
held, and no name anywhere in this module or in the two modules it exercises is a
bypass. A measurement that proceeded unattended is what ADR-0007 forbids.

**That the estimate is per route and declared before anything is sent.** One row
per route, exact, in calls and in the operator's own currency — and the routes are
still pending while it is being read.

**That the memory saves what ADR-0032 says it saves**, asserted as a call count:
a route the memory already measured under these conditions is decided without one
message reaching a reference agent. That is the one assertion that fails if the
consultation is dropped.

**That the lease refuses in both directions.** A measurement is refused while a gate
run holds the library, and a gate run is refused while a measurement holds it —
ADR-0033's property observed from both ends rather than a new one added.

**That a refusal costs nothing and loses nothing.** A declined measurement, an
aborted one, and one that read the first model and not the second all leave every
route pending, asserted on the store rather than on the response.

**That the three families stay apart.** No route under `/pending-routes` takes a run
id or a gate run id, no route under `/runs` or `/gate-runs` takes a pending route
key, and no function in the API package names a `MeasurementRecord` beside a
`RunRecord` or a `GateRunRecord`.
"""

from __future__ import annotations

import ast
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.app import (
    GATE_RUN_ROUTE,
    GATE_RUNS_ROUTE,
    PENDING_MEASUREMENT_APPROVAL_ROUTE,
    PENDING_MEASUREMENT_ROUTE,
    PENDING_MEASUREMENTS_ROUTE,
    PENDING_ROUTE_ROUTE,
    PENDING_ROUTES_ROUTE,
    create_app,
)
from backend.api.gate_run_equipment import Equipment, ServedAgents, shipped_agents
from backend.api.gate_runs import GateRunBench
from backend.api.pending_route_state import (
    MeasurementRecord,
    MeasurementStatus,
    NotMeasurable,
)
from backend.api.pending_routes import BenchPendingRoutes, PendingRouteBench
from backend.api.report import ReportConfig
from backend.api.runs import BenchConfig
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute, proposed_from
from backend.bench.decided import DECIDED_ROUTES, RouteKey
from backend.bench.lease import LEASE_FILE, take_the_library
from backend.bench.library import (
    AdmissionReading,
    Case,
    Family,
    Precondition,
    load_library,
)
from backend.bench.pending import (
    PENDING_ROUTES,
    AwaitingDecision,
    Decided,
    RouteState,
)
from backend.bench.rule import DECLARED_RULE
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    a_target,
    authored_library,
    stop_every_run,
    unlisted_case,
)
from backend.tests.test_api_gate_runs import (
    API_DIR,
    a_gate_request,
)

FIRST = "stub:obedient"
SECOND = "stub:cooperative"
MODELS = (FIRST, SECOND)
"""The two underlying models the reference agents are served on here.

Two stubs rather than two models: nothing in this module reaches a provider, and
the bar it exercises is the *pair* — a measurement that read one model twice would
be a cross-model admission taken on one model (ADR-0012).
"""

A_CUSTOMER = "acme-support-bot"
"""Whose agent the route was found against — the field ADR-0104 §2 grants."""

FILED_ON = date(2026, 8, 30)

SEPARATING = {"attempts": 10, "hardened": 0, "weak": 5, "trivial": 10}
"""Counts that clear the bar: D = 1.00, intervals nowhere near each other."""

FLAT = {"attempts": 10, "hardened": 9, "weak": 9, "trivial": 10}
"""Counts that do not: the two ends are one attempt apart, intervals overlapping."""

STATEMENT_FIELDS = (
    "authorised_to_test",
    "not_production",
    "accepts_provider_policy_and_cost",
)

PENDING_MODULES = ("pending_routes.py", "pending_route_state.py")
"""Every module of this side, which is what the source scans below scan."""

SETTLED = frozenset(
    {
        MeasurementStatus.ANSWERED,
        MeasurementStatus.DECLINED,
        MeasurementStatus.UNANSWERED,
        MeasurementStatus.ABORTED,
        MeasurementStatus.FAILED,
    }
)
"""The states a measurement does not leave. Everything else is still in flight."""


# --- the equipment, served per model, with what it served counted --------------


@dataclass
class Served:
    """How many times each model's equipment was asked for and served.

    The clock both ends of the memory assertion agree on: a route answered from the
    admission memory is a route no equipment was served for, and a count of serves
    is the observable form of a call that did not happen (ADR-0032).
    """

    models: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.models)


def an_equipment(model: str, served: Served) -> Equipment:
    """The three reference agents on one model, with the serving counted."""
    shipped = shipped_agents(model)
    assert shipped is not None

    @contextmanager
    def serving() -> Iterator[ServedAgents]:
        served.models.append(model)
        with shipped() as agents:
            yield agents

    return serving


def agents_on(served: Served, broken: str = "") -> Any:
    """This deployment's equipment seam, with one model optionally unreachable.

    `broken` is the second model failing where the first did not, which is the
    shape spec story 18 asks for: one model read, the other not, and every route
    still pending afterwards.
    """

    def agents(model: str) -> Equipment | None:
        if model == broken:

            @contextmanager
            def refuses() -> Iterator[ServedAgents]:
                served.models.append(model)
                raise OSError(f"nothing is listening for {model}")
                yield  # pragma: no cover - unreachable, and the type needs it

            return cast(Equipment, refuses)
        return an_equipment(model, served)

    return agents


# --- a bench that can decide a pending route -----------------------------------


@dataclass
class Deciding:
    """A bench that can decide a pending route, its registry, and its library."""

    client: TestClient
    pending: BenchPendingRoutes
    library: Path
    served: Served


@contextmanager
def a_bench(
    library: Path,
    *,
    served: Served | None = None,
    agents: Any = None,
    models: tuple[str, ...] = MODELS,
    adjudicating: bool = True,
    gate_agents: bool = True,
) -> Iterator[Deciding]:
    """The API over one bench, with the pending-route bench beside it.

    A third declaration handed to the factory, on the gate-run bench's terms: a
    deployment that can run a gate has not said it can measure on two models.
    """
    counted = served if served is not None else Served()
    config = BenchConfig(
        cases=[],
        rule=DECLARED_RULE,
        adaptive=AdaptiveBudget(turns_per_episode=2, episodes_per_family=1),
        adjudicator=ADJUDICATING if adjudicating else None,
        approval_wait_seconds=60.0,
        report=ReportConfig(),
    )
    gate_runs = GateRunBench(
        library=library,
        equipment=shipped_agents(FIRST) if gate_agents else None,
    )
    app: FastAPI = create_app(
        config,
        gate_runs,
        PendingRouteBench(
            library=library,
            agents=agents if agents is not None else agents_on(counted),
            models=models,
        ),
    )
    with TestClient(app) as client:
        try:
            yield Deciding(
                client=client,
                pending=cast(BenchPendingRoutes, app.state.pending_routes),
                library=library,
                served=counted,
            )
        finally:
            # A measurement left at its interrupt outlives the test that started it
            # and holds this library's lease while it does — the reason
            # `test_api_gate_runs` stops every run it started.
            stop_every_run(client)
            _stop_every_measurement(client)


def _stop_every_measurement(client: TestClient) -> None:
    """Decline anything still waiting, so no lease outlives its test."""
    listing = client.get(PENDING_ROUTES_ROUTE)
    if listing.status_code != 200:
        return
    for row in listing.json()["measurements"]:
        if row["status"] == MeasurementStatus.AWAITING_APPROVAL:
            client.post(approval_of(row["measurement_id"]), json=a_confirmation(False))


def approval_of(measurement_id: str) -> str:
    return PENDING_MEASUREMENT_APPROVAL_ROUTE.format(measurement_id=measurement_id)


def a_confirmation(confirmed: bool = True) -> dict[str, Any]:
    return {
        "confirmed": confirmed,
        "identity": BENCH_ATTESTATION.identity,
        "reason": "" if confirmed else "not spending that today",
    }


def a_request(
    routes: list[str],
    withheld: str | None = None,
    price_per_call: str | None = "0.0005",
) -> dict[str, Any]:
    """One start request, with any one of the three statements withheld."""
    attestation = dict.fromkeys(STATEMENT_FIELDS, True)
    if withheld is not None:
        attestation[withheld] = False
    return {
        "attestation": {"identity": BENCH_ATTESTATION.identity, **attestation},
        "cost": {"price_per_call": price_per_call, "currency": "USD"},
        "routes": routes,
    }


# --- routes, filed the way a customer run files them ---------------------------


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
        today=FILED_ON,
    )


def filed(proposal: ProposedRoute, target: str = A_CUSTOMER) -> AwaitingDecision:
    """That route, in the queue, as the run that found it left it."""
    return PENDING_ROUTES.file(proposal, target=target, today=FILED_ON)


def remembered(proposal: ProposedRoute, *counts: dict[str, int]) -> Promotion:
    """What the admission memory holds after a run measured this route.

    Written through `DecidedRoutes.remember` rather than into the database by hand,
    so what the consultation reads back is what a measuring run would have left.
    """
    promotion = promote(
        proposal,
        [
            AdmissionReading(
                model=model,
                attempts=one["attempts"],
                hardened=one["hardened"],
                weak=one["weak"],
                trivial=one["trivial"],
            )
            for model, one in zip(MODELS, counts, strict=True)
        ],
    )
    DECIDED_ROUTES.remember(promotion, models=MODELS)
    return promotion


def settled(
    pending: BenchPendingRoutes, measurement_id: str, seconds: float = 240.0
) -> MeasurementRecord:
    """Wait for a measurement to reach a state it does not leave."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        record = pending.record(measurement_id)
        if record is not None and record.status in SETTLED:
            return record
        time.sleep(0.02)
    raise AssertionError(f"measurement {measurement_id} is still going")


def started(deciding: Deciding, routes: list[str]) -> dict[str, Any]:
    """Start a measurement and hand back what the route said, refusing a refusal."""
    response = deciding.client.post(PENDING_MEASUREMENTS_ROUTE, json=a_request(routes))
    assert response.status_code == 202, response.text
    return cast(dict[str, Any], response.json())


def answered(deciding: Deciding, routes: list[str]) -> dict[str, Any]:
    """Start one, confirm it, and wait for it to stop."""
    begun = started(deciding, routes)
    confirmation = deciding.client.post(
        approval_of(begun["measurement_id"]), json=a_confirmation()
    )
    assert confirmation.status_code == 200, confirmation.text
    settled(deciding.pending, begun["measurement_id"])
    reading = deciding.client.get(
        PENDING_MEASUREMENT_ROUTE.format(measurement_id=begun["measurement_id"])
    )
    assert reading.status_code == 200, reading.text
    return cast(dict[str, Any], reading.json())


@pytest.fixture
def cases_dir(tmp_path: Path) -> Path:
    """The whole case library, copied as authored, for a decision to write into.

    Named for the directory rather than `library`, which is the name `conftest`
    already binds to the loaded cases: a fixture that shadowed it would take the
    objective every route here is drafted from out from under `leakage_case`.
    """
    return authored_library(tmp_path / "cases")


# --- the queue is a page, and it carries no payload ----------------------------


def test_the_queue_lists_every_filed_route_with_the_target_it_beat(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec stories 2 and 3: the row says whose agent, and what the route did."""
    record = filed(a_route(leakage_case, description="slipped a record out sideways"))

    with a_bench(cases_dir) as deciding:
        listing = deciding.client.get(PENDING_ROUTES_ROUTE)

    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["measure"]["available"] is True
    assert body["measure"]["models"] == list(MODELS)
    [row] = body["routes"]
    assert row["route"] == record.route.filed_under
    assert row["target"] == A_CUSTOMER
    assert row["description"] == "slipped a record out sideways"
    assert row["state"] == RouteState.PENDING
    assert row["reason"] == ""


def test_no_response_on_this_surface_carries_the_payload(
    cases_dir: Path, leakage_case: Case
) -> None:
    """The exception ADR-0104 grants is for measuring a route, never for showing it."""
    probe = "the probe nobody outside the store may read"
    record = filed(a_route(leakage_case, payload=probe))

    with a_bench(cases_dir) as deciding:
        listing = deciding.client.get(PENDING_ROUTES_ROUTE)
        one = deciding.client.get(
            PENDING_ROUTE_ROUTE.format(route=record.route.filed_under)
        )

    assert probe not in listing.text
    assert probe not in one.text
    assert one.json()["route"] == record.route.filed_under


def test_a_route_this_queue_never_held_is_a_404(cases_dir: Path) -> None:
    with a_bench(cases_dir) as deciding:
        response = deciding.client.get(
            PENDING_ROUTE_ROUTE.format(route="data_leakage-0000000000000000")
        )
    assert response.status_code == 404


# --- approval is a refusal, and never a flag -----------------------------------


@pytest.mark.parametrize("withheld", STATEMENT_FIELDS)
def test_a_withheld_statement_starts_nothing_and_holds_no_library(
    cases_dir: Path, leakage_case: Case, withheld: str
) -> None:
    """Each statement refused on its own, before the library is held (ADR-0007)."""
    record = filed(a_route(leakage_case))

    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE,
            json=a_request([record.route.filed_under], withheld=withheld),
        )

        assert response.status_code == 422, response.text
        assert deciding.served.count == 0
        assert not (cases_dir / LEASE_FILE).exists()
        assert deciding.pending.records() == []


def test_nothing_in_this_side_constructs_an_attestation_or_names_a_bypass() -> None:
    """The consent mechanism is the one that exists, and no name here stands in.

    Both halves. Nothing on this side calls `Attestation(...)`, so there is no line
    that could fill in three statements on somebody's behalf; and no name anywhere
    in it reads as a bypass, so there is no flag, setting or field that starts a
    measurement without one (ADR-0105 §4).
    """
    bypasses = ("yes", "skip", "force", "unattended", "auto_approve", "no_confirm")
    for module in PENDING_MODULES:
        tree = ast.parse((API_DIR / module).read_text(encoding="utf-8"))
        constructed = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Attestation"
        ]
        assert not constructed, (
            f"{module} constructs an Attestation. The record is received from the "
            "operator, never made up here"
        )
        named = sorted(
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and any(bypass in node.id.lower() for bypass in bypasses)
        )
        assert not named, f"{module} names {named}, which reads as a bypass"


# --- the estimate is per route, before anything is sent ------------------------


def test_the_estimate_is_one_row_per_route_and_nothing_has_been_sent(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Per route, exact, in calls and in the operator's own currency.

    Two routes from one objective and two payloads, which is two digests and so two
    records: what the estimate is per is the *route*, and a second family would put
    a second criterion in the way of the arithmetic being checkable.
    """
    first = filed(a_route(leakage_case))
    second = filed(a_route(leakage_case, payload="a second route, a second digest"))

    with a_bench(cases_dir) as deciding:
        begun = started(deciding, [first.route.filed_under, second.route.filed_under])

        estimate = begun["estimate"]
        assert [row["route"] for row in estimate["per_route"]] == [
            first.route.filed_under,
            second.route.filed_under,
        ]
        # Three reference agents on each of two models, at the declared attempts per
        # case, plus one registration probe each. Six endpoints per route, and the
        # figure is a multiplication rather than a bound.
        per_route = 6 * (1 + DECLARED_RULE.attempts_per_case)
        assert [row["calls"] for row in estimate["per_route"]] == [per_route] * 2
        # And the total is the one admission run per model the two routes ride in:
        # a registration probe is one per agent per model however many routes it
        # carries, so the rows add up to more than the total and never to less.
        assert estimate["calls"] == 6 * (1 + 2 * DECLARED_RULE.attempts_per_case)
        assert estimate["calls"] < 2 * per_route
        assert estimate["cost"].endswith("USD")
        assert estimate["models"] == list(MODELS)
        # And nothing has been sent: the equipment was served once, to read the
        # three agents the estimate is declared against, and no message has gone.
        assert begun["status"] == MeasurementStatus.AWAITING_APPROVAL
        assert PENDING_ROUTES.filed(first.route) == first
        assert PENDING_ROUTES.filed(second.route) == second


def test_a_declined_measurement_leaves_every_route_pending(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec story 17: a refusal costs nothing and loses nothing."""
    record = filed(a_route(leakage_case))
    before = library_bytes(cases_dir)

    with a_bench(cases_dir) as deciding:
        begun = started(deciding, [record.route.filed_under])
        declined = deciding.client.post(
            approval_of(begun["measurement_id"]), json=a_confirmation(False)
        )
        assert declined.status_code == 200, declined.text
        settled(deciding.pending, begun["measurement_id"])

        assert deciding.served.count == 1, "only the estimate's reading of the agents"
        assert PENDING_ROUTES.filed(record.route) == record
        assert library_bytes(cases_dir) == before
        assert not (cases_dir / LEASE_FILE).exists()


def library_bytes(library: Path) -> dict[str, str]:
    """Every case record as it stands, so *nothing was written* is checkable."""
    return {
        record.name: record.read_text(encoding="utf-8")
        for record in sorted(library.glob("*.toml"))
    }


# --- the refusals about a request, before anything is held ---------------------


def test_a_measurement_over_no_route_is_refused(cases_dir: Path) -> None:
    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(PENDING_MEASUREMENTS_ROUTE, json=a_request([]))

    assert response.status_code == 409
    assert response.json()["detail"]["refusal"] == NotMeasurable.NOTHING_SELECTED


def test_a_route_this_queue_does_not_hold_is_refused_before_the_library_is_held(
    cases_dir: Path,
) -> None:
    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE,
            json=a_request(["data_leakage-0000000000000000"]),
        )
        assert response.status_code == 409
        assert response.json()["detail"]["refusal"] == NotMeasurable.NOT_IN_THE_QUEUE
        assert not (cases_dir / LEASE_FILE).exists()
        assert deciding.served.count == 0


def test_a_route_already_decided_is_refused_rather_than_measured_again(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Its payload went with the decision, so nothing could have measured it since."""
    record = filed(a_route(leakage_case))
    PENDING_ROUTES.decide(
        record.route, state=RouteState.REJECTED, reason="a property of one model"
    )

    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )

    assert response.status_code == 409
    assert response.json()["detail"]["refusal"] == NotMeasurable.ALREADY_DECIDED


def test_a_route_no_live_case_can_score_is_refused_rather_than_measured(
    cases_dir: Path,
) -> None:
    """Spec story 16: nobody pays to decide a probe nothing can score.

    The route's criterion is copied off the live case its episode was working on
    (`adaptive/proposal.proposed_from`), so a library whose live cases no longer
    carry that criterion holds nothing that could score the route. The objective
    here requires a precondition no live case requires, which is what an edit to a
    case looks like from a route filed weeks before it.
    """
    edited = replace(
        unlisted_case("a probe against a case as it used to be", "edited-objective"),
        requires=(Precondition.CONFIG_CANARY_PLANT, Precondition.TOOL_CALL_VISIBILITY),
    )
    record = filed(a_route(edited))

    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )
        assert response.status_code == 409
        assert (
            response.json()["detail"]["refusal"] == NotMeasurable.NOTHING_LIVE_SCORES_IT
        )
        assert deciding.served.count == 0
        assert PENDING_ROUTES.filed(record.route) == record


def test_a_bench_with_one_declared_model_may_not_measure_at_all(
    cases_dir: Path, leakage_case: Case
) -> None:
    """The bar is two models measured together, and one is not the bar (ADR-0012)."""
    record = filed(a_route(leakage_case))

    with a_bench(cases_dir, models=()) as deciding:
        listing = deciding.client.get(PENDING_ROUTES_ROUTE)
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )

    assert listing.json()["measure"]["refusal"] == NotMeasurable.NO_SECOND_MODEL
    assert response.status_code == 409
    assert response.json()["detail"]["refusal"] == NotMeasurable.NO_SECOND_MODEL


# --- the memory, asserted as a call count --------------------------------------


def test_a_remembered_route_is_decided_without_being_measured(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0032, as the one assertion that fails if the consultation is dropped.

    The memory holds this route's measurement under these conditions, so the three
    reference agents are never served: not a shorter measurement, not a cheaper one
    — none at all. The route is still decided, because `promote` decides it again
    against the declared threshold on the counts the memory kept.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, SEPARATING, SEPARATING)

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

        # One serving, and it is the estimate's reading of the three agents before
        # the halt. Nothing was served to measure with.
        assert deciding.served.count == 1
        assert reading["status"] == MeasurementStatus.ANSWERED
        [row] = reading["routes"]
        assert row["state"] == RouteState.ADMITTED


# --- what a decision leaves behind ---------------------------------------------


def test_an_admitted_route_enters_the_library_and_its_row_names_the_record(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec stories 11 and 13, and ADR-0033: `enter` is the only writer.

    The counts come from the admission memory so that the assertion is about the
    decision rather than about whether a stub agent happened to separate — what is
    exercised here is the write, the row and the store, and every one of those is
    the same whichever way the counts arrived.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, SEPARATING, SEPARATING)
    before = {case.id for case in load_library(cases_dir)}

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    [row] = reading["routes"]
    assert row["state"] == RouteState.ADMITTED
    assert row["entered_as"].endswith(".toml")
    assert (cases_dir / row["entered_as"]).exists()
    assert {case.id for case in load_library(cases_dir)} - before == {proposal.case.id}

    # And the payload is gone from the store, asserted on the store itself.
    decided = PENDING_ROUTES.filed(record.route)
    assert isinstance(decided, Decided)
    assert decided.state is RouteState.ADMITTED
    assert not hasattr(decided, "draft")


def test_a_rejected_route_keeps_its_row_and_carries_the_gates_reason(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec story 12: a route that was a property of one model is a finding."""
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, SEPARATING, FLAT)

    with a_bench(cases_dir) as deciding:
        answered(deciding, [record.route.filed_under])
        listing = deciding.client.get(PENDING_ROUTES_ROUTE).json()

    [row] = listing["routes"]
    assert row["state"] == RouteState.REJECTED
    assert row["reason"], "a rejected route's row carries the gate's own reason"
    decided = PENDING_ROUTES.filed(record.route)
    assert isinstance(decided, Decided)
    assert not hasattr(decided, "draft")


def test_nothing_a_decision_writes_carries_the_target(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0008 and ADR-0011: the identity stops at the decision.

    Asserted over what the decision wrote — the case record in the library, and the
    admission memory's own record — because those are the two things that outlive
    the queue the identity lives in.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, SEPARATING, SEPARATING)

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    written = (cases_dir / reading["routes"][0]["entered_as"]).read_text(
        encoding="utf-8"
    )
    assert A_CUSTOMER not in written
    key = RouteKey.of(proposal.case).filed_under
    remembered_route = DECIDED_ROUTES.store.get(DECIDED_ROUTES.namespace, key)
    assert remembered_route is not None
    assert A_CUSTOMER not in repr(remembered_route.value)


# --- the lease, in both directions ---------------------------------------------


def test_a_measurement_is_refused_while_a_gate_run_holds_the_library(
    cases_dir: Path, leakage_case: Case
) -> None:
    record = filed(a_route(leakage_case))
    take_the_library(cases_dir, "a gate run at a terminal")

    with a_bench(cases_dir) as deciding:
        listing = deciding.client.get(PENDING_ROUTES_ROUTE).json()
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )

    assert listing["measure"]["refusal"] == NotMeasurable.ALREADY_IN_FLIGHT
    assert response.status_code == 409
    assert response.json()["detail"]["refusal"] == NotMeasurable.ALREADY_IN_FLIGHT


def test_a_gate_run_is_refused_while_a_measurement_holds_the_library(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0033's exclusion, read from the other end."""
    record = filed(a_route(leakage_case))

    with a_bench(cases_dir) as deciding:
        started(deciding, [record.route.filed_under])
        refused = deciding.client.post(GATE_RUNS_ROUTE, json=a_gate_request())

    assert refused.status_code == 409, refused.text
    assert "already_in_flight" in refused.text


def test_a_second_measurement_is_refused_while_the_first_is_going(
    cases_dir: Path, leakage_case: Case
) -> None:
    record = filed(a_route(leakage_case))
    second = filed(a_route(leakage_case, payload="a second route, a second digest"))

    with a_bench(cases_dir) as deciding:
        started(deciding, [record.route.filed_under])
        refused = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([second.route.filed_under])
        )

    assert refused.status_code == 409
    assert refused.json()["detail"]["refusal"] == NotMeasurable.ALREADY_IN_FLIGHT


# --- a partial reading is never a cross-model admission ------------------------


def test_a_measurement_that_read_one_model_and_not_the_second_decides_nothing(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec story 18, with the second model's equipment unreachable.

    The first model is measured for real — three agents, every attempt the declared
    rule asks for — and the second cannot be served. Nothing is decided, and every
    route is still pending with its payload: a reading on one model is not a
    cross-model admission (ADR-0012).
    """
    record = filed(a_route(leakage_case))
    served = Served()

    with a_bench(cases_dir, served=served, agents=agents_on(served, broken=SECOND)) as (
        deciding
    ):
        reading = answered(deciding, [record.route.filed_under])

    assert served.models == [FIRST, FIRST, SECOND], (
        "the estimate's reading, the first model measured, and the second refused"
    )
    assert reading["status"] in {MeasurementStatus.FAILED, MeasurementStatus.ABORTED}
    still = PENDING_ROUTES.filed(record.route)
    assert isinstance(still, AwaitingDecision)
    assert still == record
    assert not (cases_dir / LEASE_FILE).exists()


# --- the three families stay apart ---------------------------------------------


def test_no_route_here_takes_a_run_id_or_a_gate_run_id(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0105 §1, asserted over the route table and over the wire.

    Both directions: no path under `/pending-routes` names a run id or a gate run
    id, and a pending route key handed to the gate-run family is a `404` rather than
    a record somebody reached by accident.
    """
    record = filed(a_route(leakage_case))
    paths = (
        PENDING_ROUTES_ROUTE,
        PENDING_MEASUREMENTS_ROUTE,
        PENDING_MEASUREMENT_ROUTE,
        PENDING_MEASUREMENT_APPROVAL_ROUTE,
        PENDING_ROUTE_ROUTE,
    )
    assert not [path for path in paths if "run_id" in path]

    with a_bench(cases_dir) as deciding:
        response = deciding.client.get(
            GATE_RUN_ROUTE.format(gate_run_id=record.route.filed_under)
        )
    assert response.status_code == 404


def test_no_function_in_the_api_names_a_measurement_beside_a_run_or_a_gate_run() -> (
    None
):
    """Three records, and no signature that could hold two of them.

    ADR-0010's discipline applied to a third axis: a function that took either a
    `MeasurementRecord` or a `GateRunRecord` would be the widening ADR-0105 §1 asks
    a reader to stop at, and an absent name is only guarded by a test that looks for
    it.
    """
    offenders: list[str] = []
    for module in sorted(API_DIR.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            named = {
                ast.unparse(argument.annotation)
                for argument in node.args.args + node.args.kwonlyargs
                if argument.annotation is not None
            }
            named |= {ast.unparse(node.returns)} if node.returns is not None else set()
            together = {"MeasurementRecord"} <= named and (
                "RunRecord" in named or "GateRunRecord" in named
            )
            if together:
                offenders.append(f"{module.name}:{node.name}")
    assert not offenders, (
        f"{offenders} name a measurement beside a run or a gate run. The three are "
        "different records with different readers (ADR-0018, ADR-0105 §1)"
    )
