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

**That a refusal costs nothing and loses nothing.** A declined measurement, one
whose declared model could not be served, and one whose agents on that model never
registered all leave every route pending — asserted on the store rather than on the
response. The last of those is the path a `Measure` answers with a *code*,
which is the same path a run aborted on its ceiling takes.

**That the three families stay apart.** No route under `/pending-routes` takes a run
id or a gate run id, no route under `/runs` or `/gate-runs` takes a pending route
key, and no function in the API package names a `MeasurementRecord` beside a
`RunRecord` or a `GateRunRecord`.

And then the three writes a decision makes, each with its own invariant.

**That the memory keeps what the measurement paid for.** Asserted from the writing
end, which nothing else here reaches: every other memory assertion in this module
seeds the store and watches the consultation read it, so none of them would notice a
surface that consulted correctly and remembered nothing. A route is measured for
real, filed again the way a later run's attacker would file it, and the second
measurement serves no equipment at all (ADR-0032).

**That `enter` is the library's one writer.** A route the library already holds is
reported as held and no second record appears, and this side names no serialiser and
writes no file of its own (ADR-0033).

**That the identity stops at the decision, from both ends.** No argument to
`remember` or to `enter` carries the target's name; and neither `DecidedRoute` nor
`Case` has a field, anywhere in its graph, that could hold one. The second is the
assertion that survives a refactor, and its control is the exception itself —
`AwaitingDecision` carries `target` deliberately, so the walk demonstrably finds an
identity where one is declared (ADR-0008, ADR-0011, ADR-0104 §2).

**That a record is dated by the measurement.** A route admitted out of the memory
carries the day the three reference agents ran, not the day the row was decided, and
no function on this path takes a `today` to date it with (ADR-0032).

**That the loop closes.** `library_provenance` counts the new record as an adaptive
live case, and `run_calibration` runs it — the assertion #40 made for the swap, made
here for a route found against somebody's real agent.
"""

from __future__ import annotations

import ast
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, cast, get_args, get_type_hints

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import pending_routes
from backend.api.app import (
    GATE_RUN_ROUTE,
    GATE_RUNS_ROUTE,
    PENDING_MEASUREMENT_APPROVAL_ROUTE,
    PENDING_MEASUREMENT_ROUTE,
    PENDING_MEASUREMENTS_ROUTE,
    PENDING_ROUTE_ROUTE,
    PENDING_ROUTES_ROUTE,
    create_app,
    deployed_pending_routes,
)
from backend.api.gate_run_equipment import Equipment, ServedAgents, shipped_agents
from backend.api.gate_runs import GateRunBench
from backend.api.pending_route_state import (
    MeasurementRecord,
    MeasurementStatus,
    NotMeasurable,
)
from backend.api.pending_routes import BenchPendingRoutes, PendingRouteBench
from backend.api.report import UNDECLARED_MODEL, UNDECLARED_MODELS, ReportConfig
from backend.api.runs import BenchConfig
from backend.bench import admitting, entry
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute, proposed_from
from backend.bench.admission import (
    RejectionKind,
    admitted_library,
    library_provenance,
)
from backend.bench.contract import TargetConfig
from backend.bench.decided import (
    DECIDED_ROUTES,
    MEASURED_THE_ROUTE,
    DecidedRoute,
    DecidedRoutes,
    Remembered,
    RouteKey,
)
from backend.bench.entry import enter
from backend.bench.lease import LEASE_FILE, take_the_library
from backend.bench.library import (
    AdmissionReading,
    Case,
    DiscoveredBy,
    Family,
    Precondition,
    load_case,
    load_library,
)
from backend.bench.pending import (
    PENDING_ROUTES,
    AwaitingDecision,
    Decided,
    RouteState,
)
from backend.bench.retirement import live_library
from backend.bench.rule import DECLARED_RULE
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    a_target,
    authored_library,
    calibrate,
    imports_of,
    stop_every_run,
    unlisted_case,
)
from backend.tests.test_api_gate_runs import (
    API_DIR,
    a_gate_request,
)

FIRST = "stub:obedient"
MODELS = (FIRST,)
"""The underlying model the reference agents are served on here.

A stub rather than a model: nothing in this module reaches a provider. One rather
than a pair, because that is what this surface declares — every route it decides was
found against a customer's target and faces the single-model bar (ADR-0107 §4), and
the pair is `scripts/swap.py`'s, which measures one by definition.
"""

A_CUSTOMER = "acme-support-bot"
"""Whose agent the route was found against — the field ADR-0104 §2 grants."""

FILED_ON = date(2026, 8, 30)

THE_RUN_THAT_FOUND_IT = "run-2026-08-30-0004"
"""The run the routes here were found in, as the run service names its own.

What a route held against a target is found in (`held.HeldRoute.found_in`), so it
travels from the run that filed the route to the decision that holds it and is
never minted by this surface.
"""

A_PROBE = "the probe that actually beat somebody's agent"
"""The payload the pending store is the one place in this repository allowed to hold.

A constant so a decision can be asked whether it took it off the disk, which is the
mitigation ADR-0104 §4 makes mechanical and the one this module checks on the store
rather than on a response.
"""

SEPARATING = {"attempts": 10, "hardened": 0, "weak": 5, "trivial": 10}
"""Counts that clear the bar: D = 1.00, intervals nowhere near each other."""

FLAT = {"attempts": 10, "hardened": 9, "weak": 9, "trivial": 10}
"""Counts that do not: the two ends are one attempt apart, intervals overlapping."""

FLOOR = {"attempts": 10, "hardened": 0, "weak": 0, "trivial": 0}
"""Counts where nothing engaged: the trivial agent was never broken (ADR-0118)."""

STATEMENT_FIELDS = (
    "authorised_to_test",
    "not_production",
    "accepts_provider_policy_and_cost",
)

PENDING_MODULES = ("pending_routes.py", "pending_route_state.py")
"""Every module of this side, which is what the source scans below scan."""

WRITES = frozenset(
    {
        "write_text",
        "write_bytes",
        "mkdir",
        "makedirs",
        "open",
        "dump",
        "dumps",
        "copy",
        "copyfile",
        "rename",
        "touch",
    }
)
"""Every way of putting bytes somewhere that this side is asserted not to reach.

Named rather than spelled at the call site, and wider than the three ways an
admitted case could plausibly be written: the claim is that `enter` is the library's
one writer (ADR-0033), and a claim that only listed the obvious writes would be one
a second writer passes by reaching for a different function. `replace` is not here
and cannot be: `dataclasses.replace` is how this side makes a changed record, and a
name that meant two things would be a wall that fired on the wrong one.
"""


def on_this_path() -> list[Path]:
    """Every module a route travels through between the bar and the two writes.

    One spelling of *the modules of this side*, so a scan and the module list cannot
    drift apart: the two services, and the bar they both reach the reference agents
    through.
    """
    return [API_DIR / name for name in PENDING_MODULES] + [
        Path(str(admitting.__file__))
    ]


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

    `broken` is a model whose equipment will not serve at all. Used for the models
    a test declares beyond the one this surface deploys with; the shape spec story
    18 asks for on the deployed surface — served for the estimate and gone by the
    measurement — is `serves_once` below.
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
    deployment that can run a gate has not said it ships the equipment a route is
    decided against.
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
            # and holds this library's lease while it does, so every later test's
            # gate run is refused by a library nothing is writing to. `stop_every_run`
            # answers all three kinds of halt — `conftest.LISTINGS` is where the third
            # was added — and `no_run_left_running` is the guard that says when one
            # was missed.
            stop_every_run(client)


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
    payload: str = A_PROBE,
    description: str = "a route worth deciding",
) -> ProposedRoute:
    """One proposal, drafted the way `propose_case` drafts it inside an episode.

    `ADAPTIVE_ON_TARGET` and never `ADAPTIVE`, because that is what a customer run
    declares and this queue holds nothing else (`bench/queued.py`): the route was
    found against a user's agent, so it faces the single-model bar (ADR-0107 §1).
    """
    return proposed_from(
        objective=objective,
        target=a_target("trivial"),
        family=Family(objective.family),
        payload=payload,
        description=description,
        today=FILED_ON,
        broken=True,
        discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET,
    )


def filed(proposal: ProposedRoute, target: str = A_CUSTOMER) -> AwaitingDecision:
    """That route, in the queue, as the run that found it left it."""
    return PENDING_ROUTES.file(
        proposal, target=target, found_in=THE_RUN_THAT_FOUND_IT, today=FILED_ON
    )


def decided_row(route: RouteKey) -> dict[str, Any]:
    """The decided record as the database actually holds it, keys and all.

    Read off the store rather than through `read_filed`, because the question is
    whether the *row* still carries the probe: `Decided` has no `draft` field to
    read one into, so a reader that went through the type would report a payload
    gone whether or not the write took it off the disk (ADR-0104 §4).
    """
    stored = PENDING_ROUTES.store.get(PENDING_ROUTES.namespace, route.filed_under)
    assert stored is not None, f"{route.stated()} is not in the queue"
    return dict(stored.value)


def no_payload_left(route: RouteKey, state: RouteState) -> None:
    """Assert that a decided route's probe went with its decision, on the store."""
    row = decided_row(route)
    assert row["state"] == state
    assert "draft" not in row
    assert A_PROBE not in json.dumps(row), (
        f"{route.stated()} was decided {state} and its probe is still on the disk. "
        "A decided record has no payload, and the write that records the decision "
        "is the write that removes it (ADR-0104 §4, mitigation 5)"
    )


def remembered(
    proposal: ProposedRoute, *counts: dict[str, int], on: date | None = None
) -> Promotion:
    """What the admission memory holds after a run measured this route.

    Written through `DecidedRoutes.remember` rather than into the database by hand,
    so what the consultation reads back is what a measuring run would have left.

    `on` is the day that earlier run read the counts. Given rather than defaulted
    where a test is about the date, because what a record carries is the day the
    three reference agents ran and never the day a row was decided (ADR-0032).
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
    DECIDED_ROUTES.remember(promotion, models=MODELS, today=on)
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


def test_a_route_this_queue_never_held_is_a_404(
    cases_dir: Path, leakage_case: Case
) -> None:
    """A key this queue holds no record for, with a record beside it in the queue.

    Beside it deliberately: a queue with nothing in it would answer `404` however
    the lookup were written, and what has to be true is that the answer is about
    *this key* rather than about whatever the queue happens to hold.
    """
    filed(a_route(leakage_case))

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
        # Three reference agents, once, at the declared attempts per case, plus one
        # registration probe each. Three endpoints per route after ADR-0107 §4 —
        # where it was six — and the figure is a multiplication rather than a bound.
        per_route = 3 * (1 + DECLARED_RULE.attempts_per_case)
        assert [row["calls"] for row in estimate["per_route"]] == [per_route] * 2
        # And the total is the one admission run the two routes ride in: a
        # registration probe is one per agent however many routes it carries, so the
        # rows add up to more than the total and never to less.
        assert estimate["calls"] == 3 * (1 + 2 * DECLARED_RULE.attempts_per_case)
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


def test_a_library_that_cannot_be_read_is_a_refusal_and_not_a_failure(
    cases_dir: Path, leakage_case: Case
) -> None:
    """What can score a route is read off the library, so a library that will not
    load is a stated refusal rather than a stack trace.

    The operator's next move is the same one a bench with no library at all gets —
    look at the volume — so it is the same refusal, with the loader's own words
    beside it. What it must not be is a `500`: nothing was sent, nothing is held,
    and a caller cannot tell those apart from an error.
    """
    record = filed(a_route(leakage_case))
    (cases_dir / "not-a-case.toml").write_text("id = [broken", encoding="utf-8")

    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["refusal"] == NotMeasurable.NO_WRITABLE_LIBRARY
        assert not (cases_dir / LEASE_FILE).exists()
        assert deciding.served.count == 0


def a_deployment_declaring(calibration: str) -> BenchConfig:
    """A bench configuration whose report names that reference model, and no other.

    The one input `deployed_pending_routes` reads off the configuration. Built here
    rather than reused from `a_bench` because that helper hands the pending-route
    bench in ready-made, and what is under test below is the reading that builds it.
    """
    return BenchConfig(
        cases=[],
        rule=DECLARED_RULE,
        adaptive=AdaptiveBudget(turns_per_episode=2, episodes_per_family=1),
        adjudicator=ADJUDICATING,
        approval_wait_seconds=60.0,
        report=ReportConfig(models=replace(UNDECLARED_MODELS, calibration=calibration)),
    )


def test_the_surface_reads_one_declared_reference_model_and_not_a_pair(
    tmp_path: Path,
) -> None:
    """ADR-0107 §4: one declared reference model, and the pair is the swap's.

    Every route this surface decides was found against a customer's target, so after
    ADR-0107 §2 it faces the single-model bar and a second pass is a call the
    decision cannot spend. `AGENTAUDIT_SECOND_REFERENCE_MODEL` stays declared and
    stays required by `scripts/swap.py`, which measures a *pair* by definition — it
    is this surface that stops reading it, which is why nothing here sets it.
    """
    declared = deployed_pending_routes(
        a_deployment_declaring(FIRST), GateRunBench(library=tmp_path)
    )
    assert declared.models == (FIRST,)

    # And nothing is invented where nothing was declared: a bench that named no
    # reference model is a different absence and still a refusal (`why_not`).
    nothing = deployed_pending_routes(
        a_deployment_declaring(UNDECLARED_MODEL), GateRunBench(library=tmp_path)
    )
    assert nothing.models == ()


def test_a_bench_declaring_one_reference_model_may_measure(
    cases_dir: Path, leakage_case: Case
) -> None:
    """The inversion of ADR-0012's refusal, and the whole of ADR-0107 §4.

    One declared model was a bench that could not reach the bar while every route
    here faced the cross-model one. It reaches it now: the routes this surface
    decides are `ADAPTIVE_ON_TARGET` and the bar they face is measured on the model
    the reference agents are served on.
    """
    filed(a_route(leakage_case))

    with a_bench(cases_dir, models=(FIRST,)) as deciding:
        listing = deciding.client.get(PENDING_ROUTES_ROUTE)

    assert listing.json()["measure"]["available"] is True
    assert listing.json()["measure"]["models"] == [FIRST]


def test_the_estimate_counts_one_pass_and_not_two() -> None:
    """The figure the operator confirms is what the run spends (ADR-0107 §4).

    On the function rather than through the API, because the arithmetic is what is
    under test: two passes declared against a one-model bar would be a confirmation
    for calls nothing makes, and `targets` here is the agent count and never the
    model count.
    """
    assert pending_routes._planned_attempts(cases=1, targets=3) == (
        DECLARED_RULE.attempts_per_case * 3
    )
    # Linear in both, so a second route doubles it and a fourth agent does not
    # arrive from somewhere else.
    assert pending_routes._planned_attempts(cases=2, targets=3) == (
        2 * DECLARED_RULE.attempts_per_case * 3
    )


def test_a_bench_declaring_no_reference_model_may_not_measure_at_all(
    cases_dir: Path, leakage_case: Case
) -> None:
    """No model at all, which is the absence that survives ADR-0107 §4.

    Not none of the pair but none at all, because that is the only model-shaped
    absence left: the agents are shipped, the library is writable, and there is
    nothing to serve them on.
    """
    record = filed(a_route(leakage_case))

    with a_bench(cases_dir, models=()) as deciding:
        listing = deciding.client.get(PENDING_ROUTES_ROUTE)
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )

    assert listing.json()["measure"]["refusal"] == NotMeasurable.NO_REFERENCE_MODEL
    assert response.status_code == 409
    assert response.json()["detail"]["refusal"] == NotMeasurable.NO_REFERENCE_MODEL


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
    remembered(proposal, SEPARATING)

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

        # One serving, and it is the estimate's reading of the three agents before
        # the halt. Nothing was served to measure with.
        assert deciding.served.count == 1
        assert reading["status"] == MeasurementStatus.ANSWERED
        [row] = reading["routes"]
        assert row["state"] == RouteState.ADMITTED
        # And the row says which of the two it was. A saving nobody can see on the
        # page they paid from is a saving the operator has to take on trust.
        assert "admission memory" in row["where"]


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
    remembered(proposal, SEPARATING)
    before = {case.id for case in load_library(cases_dir)}

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    [row] = reading["routes"]
    assert row["state"] == RouteState.ADMITTED
    assert row["entered_as"].endswith(".toml")
    assert (cases_dir / row["entered_as"]).exists()
    assert {case.id for case in load_library(cases_dir)} - before == {proposal.case.id}

    # And the payload is gone, asserted on the row the database holds.
    no_payload_left(record.route, RouteState.ADMITTED)


def test_a_rejected_route_keeps_its_row_and_carries_the_gates_reason(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec story 12: a route that separates nothing is a finding, in words.

    In the gate's own words, and that is the assertion rather than a non-empty
    string: a row that said only *rejected* would drop the finding and keep the
    bookkeeping. The counts here separate no agent from another, so the row has to
    say which refusal it was, on which model, and against which declared bar.

    **The cross-model discard is no longer the refusal this surface reaches.** It
    was, and ADR-0012 calls it direct evidence that what the attacker found was a
    property of one model; after ADR-0107 §4 the routes here are read on one model
    and that bucket can only read zero. The reason is still the gate's own reading,
    which is what this asserts.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, FLAT)

    with a_bench(cases_dir) as deciding:
        answered(deciding, [record.route.filed_under])
        listing = deciding.client.get(PENDING_ROUTES_ROUTE).json()

    [row] = listing["routes"]
    assert row["state"] == RouteState.REJECTED
    reason = row["reason"]
    for said in (*MODELS, "does not clear", "D >= 0.4"):
        assert said in reason, (
            f"the row does not say {said!r}. A rejected route's reason is the gate's "
            "own reading — which model was read, what it said, and the declared bar "
            "the counts were held against — because a discard is a finding in its "
            "own right (ADR-0012 §3) and a row saying only *rejected* keeps the "
            "bookkeeping and drops the finding"
        )
    decided = PENDING_ROUTES.filed(record.route)
    assert isinstance(decided, Decided)
    assert decided.reason == reason
    # Whatever the route was decided as: a rejected record keeps no probe either.
    no_payload_left(record.route, RouteState.REJECTED)


def test_a_route_the_agents_never_engaged_says_so_rather_than_blaming_the_case(
    cases_dir: Path, leakage_case: Case
) -> None:
    """#234, and the surface the defect was found on.

    The population this surface decides is the one ADR-0107 sends here: routes found
    against a customer's own agent, composed in that agent's vocabulary. The
    reference agents route by scripted phrase, so most of those probes reach nothing
    here and the reading comes back at `trivial 0.00`. Until ADR-0118 the row told
    the operator their case was weak, which is a claim about a case nothing measured.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, FLOOR)

    with a_bench(cases_dir) as deciding:
        answered(deciding, [record.route.filed_under])
        listing = deciding.client.get(PENDING_ROUTES_ROUTE).json()

    [row] = listing["routes"]
    assert row["state"] == RouteState.REJECTED
    reason = row["reason"]
    assert str(RejectionKind.FLOOR_AT_ZERO) in reason, (
        "the row does not say the reference agents never engaged. An operator "
        "reading this row decides whether to rewrite a probe or drop a case, and "
        "those are opposite actions"
    )
    assert str(RejectionKind.SEPARATED_NOWHERE) not in reason, (
        "the row still reads as a finding about the case. Nothing was measured "
        "about the case: the probe never reached the equipment"
    )
    # The reading itself is still there — the kind is a label on it, not a
    # replacement for the counts a reader checks the decision against.
    assert "trivial 0.00" in reason


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
    remembered(proposal, SEPARATING)

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


# --- a pass that did not happen decides nothing --------------------------------

# The cross-model half of spec story 18 — one model read, the other unreachable —
# is not a state this surface can reach any more: it declares one model
# (ADR-0107 §4), so there is no second pass to lose. What the story is *about*
# survives the narrowing and is asserted twice below: an admission run that did not
# happen decides nothing, leaves every route pending with its payload, and gives the
# library back. The partial reading itself is `cross_model_bar`'s to refuse and
# `scripts/swap.py`'s to reach, on the pair it measures by definition.


def serves_once(served: Served) -> Any:
    """Equipment that serves for the estimate and is gone by the measurement.

    The shape spec story 18 asks for, on a surface with one model: the agents are
    read once to declare what the operator confirms, and the provider behind them
    has gone by the time the confirmed pass starts. A seam that refused from the
    first call would be refused before the halt and would never reach an admission
    run at all.
    """

    def agents(model: str) -> Equipment | None:
        @contextmanager
        def serving() -> Iterator[ServedAgents]:
            first = not served.models
            served.models.append(model)
            if not first:
                raise OSError(f"nothing is listening for {model} any more")
            shipped = shipped_agents(model)
            assert shipped is not None
            with shipped() as ready:
                yield ready

        return cast(Equipment, serving)

    return agents


def test_a_measurement_whose_equipment_stopped_serving_decides_nothing(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Spec story 18, with the equipment gone between the estimate and the pass.

    The estimate is declared against agents that were there, the operator confirms
    it, and the admission run cannot be served. Nothing is decided, and every route
    is still pending with its payload: an admission run that did not happen is not
    an admission.
    """
    record = filed(a_route(leakage_case))
    served = Served()

    with a_bench(cases_dir, served=served, agents=serves_once(served)) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    assert served.models == [FIRST, FIRST], (
        "the estimate's reading, and the measurement's serving refused"
    )
    assert reading["status"] in {MeasurementStatus.FAILED, MeasurementStatus.ABORTED}
    still = PENDING_ROUTES.filed(record.route)
    assert isinstance(still, AwaitingDecision)
    assert still == record
    assert not (cases_dir / LEASE_FILE).exists()


def unplanted(model: str, served: Served) -> Equipment:
    """The three agents on one model, with nobody planting the nonce.

    A reference agent that was never planted into cannot echo its nonce, so it never
    registers and is never attacked. That is the second way an admission run does not
    happen — the first being equipment that will not serve — and it is the one that
    comes back through the `Measure` seam as a code rather than as an exception,
    which is the path that must decide nothing.
    """
    shipped = shipped_agents(model)
    assert shipped is not None

    @contextmanager
    def serving() -> Iterator[ServedAgents]:
        served.models.append(model)
        with shipped() as agents:
            yield replace(agents, plant=lambda target, nonce, namespace: None)

    return serving


def test_a_model_whose_agents_never_registered_decides_nothing(
    cases_dir: Path, leakage_case: Case
) -> None:
    """The other half of spec story 18, and the path that returns a code.

    Nobody plants the nonce, so all three agents refuse registration and the seam
    answers with a code rather than with readings. `cross_model_bar` decides nothing
    on a code — the line that refuses a partial reading, reached here on the one
    model this surface declares — and this asserts the consequence where it matters:
    every route still pending, with its payload, and the library untouched.
    """
    record = filed(a_route(leakage_case))
    served = Served()

    def agents(model: str) -> Equipment | None:
        return unplanted(model, served)

    before = library_bytes(cases_dir)
    with a_bench(cases_dir, served=served, agents=agents) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    assert reading["status"] == MeasurementStatus.FAILED
    assert "never registered" in reading["statement"]
    assert "still pending" in reading["statement"]
    still = PENDING_ROUTES.filed(record.route)
    assert isinstance(still, AwaitingDecision)
    assert still == record
    assert library_bytes(cases_dir) == before


def test_a_measurement_that_reaches_no_interrupt_gives_the_library_back(
    cases_dir: Path, leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A halt nobody will reach releases the lease rather than holding it out.

    The measuring thread is replaced by one that does nothing, so the interrupt is
    never presented and nobody will ever answer it. What must not happen is the
    library staying held: a lease kept by a measurement that is not going to happen
    is a bench that refuses gate runs for as long as the wait lasts, which is the
    failure the lease exists to prevent, inverted.
    """
    record = filed(a_route(leakage_case))
    monkeypatch.setattr(pending_routes, "PRESENT_WAIT_SECONDS", 0.2)
    monkeypatch.setattr(pending_routes, "_execute", lambda *arguments: None)

    with a_bench(cases_dir) as deciding:
        response = deciding.client.post(
            PENDING_MEASUREMENTS_ROUTE, json=a_request([record.route.filed_under])
        )

        assert response.status_code == 500
        assert not (cases_dir / LEASE_FILE).exists()
        [row] = deciding.pending.records()
        assert row.status is MeasurementStatus.FAILED
        assert PENDING_ROUTES.filed(record.route) == record


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
        # And the other direction, on both families: a pending route key handed to
        # either of them is a `404` rather than a record somebody reached by
        # accident, which is the half a path scan cannot see.
        gated = deciding.client.get(
            GATE_RUN_ROUTE.format(gate_run_id=record.route.filed_under)
        )
        run = deciding.client.get(f"/runs/{record.route.filed_under}")
    assert gated.status_code == 404
    assert run.status_code == 404


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


# --- the three writes a decision makes, and the identity that reaches none -----


def test_a_measured_route_is_remembered_so_it_is_never_bought_twice(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0032 from the writing end, which is the end nothing else here asserts.

    Every other assertion about the memory on this surface seeds it and watches the
    consultation read it. This one measures a route for real — the three reference
    agents, whatever they happen to return — and then asks whether
    the surface *wrote* what it paid for. The proof is the second measurement: the
    attacker rediscovers the route in a later run and files it again, and this time
    no equipment is served to measure with. A refused route is never re-bought, and
    that is the whole of what ADR-0032 buys (`worth_remembering`, ADR-0031 point 3).
    """
    first = a_route(leakage_case)
    record = filed(first)
    key = record.route.filed_under

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [key])
        # The estimate's one serving, and one per model to measure with.
        bought = deciding.served.count
        assert deciding.served.models[1:] == list(MODELS)

        # Read back through `recall`, which is the memory's one way out and the way
        # a later run meets this record. A raw read of the stored document would
        # pass for a record no consultation could ever use.
        answer = DECIDED_ROUTES.recall(first, models=MODELS)
        assert isinstance(answer, Remembered), (
            "the measurement decided the route and left the memory nothing a later "
            f"run can use ({answer}), so the next run that meets this route pays "
            "for it again (ADR-0032)"
        )
        assert [one.model for one in answer.decided.readings] == list(MODELS)
        # Whichever way the three agents answered, the memory kept the finding: a
        # cross-model discard is remembered exactly as an admission is, so a refused
        # route is never re-bought either (`worth_remembering`, ADR-0012).
        [row] = reading["routes"]
        assert answer.decided.decided_as in MEASURED_THE_ROUTE
        assert (answer.decided.decided_as is RejectionKind.ADMITTED) == (
            row["state"] == RouteState.ADMITTED
        ), (
            f"the queue says {row['state']} and the memory holds "
            f"{answer.decided.decided_as}. One decision is written in two places "
            "and they are the same decision"
        )

        # The same route, found again by a later run and filed again. It is one
        # record in the queue and one record in the memory, and the memory answers.
        again = filed(a_route(leakage_case))
        assert again.route == record.route
        answered(deciding, [key])

    assert deciding.served.count == bought + 1, (
        f"{deciding.served.models[bought:]} were served for a route the memory "
        "already holds. A route decided once is answered from the memory and the "
        "three reference agents are never called for it again (ADR-0032)"
    )


def test_a_route_this_library_already_holds_is_reported_as_held_and_not_written_again(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0033 read from this surface: `enter` de-duplicates and this reports it.

    The library already holds this route under an earlier case id, so the write is
    a no-op and the row says so — naming the record that stands rather than a file
    the decision did not create. A row that claimed a fresh record here would be a
    queue disagreeing with the library it describes.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    promotion = remembered(proposal, SEPARATING)
    assert promotion.case is not None
    standing = replace(promotion.case, id="adaptive-already-in-the-library")
    written = enter([standing], cases_dir, holder="an earlier admission")
    assert [one.case.id for one in written.entered] == [standing.id]
    before = sorted(path.name for path in cases_dir.glob("*.toml"))

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    [row] = reading["routes"]
    assert row["state"] == RouteState.ADMITTED
    assert row["entered_as"] == standing.id
    assert "already holds" in row["reason"]
    assert sorted(path.name for path in cases_dir.glob("*.toml")) == before, (
        "the decision wrote a second record for a route this library already holds. "
        "One route is one record, and `enter` is the one place that is decided "
        "(ADR-0033)"
    )


NAMES_A_TARGET = frozenset(
    {
        "target",
        "targets",
        "target_name",
        "endpoint",
        "url",
        "base_url",
        "auth_token",
        "host",
    }
)
"""Field names that would name whose agent a route was found against.

A name list beside the type check below, because `target: str` on a record is the
leak the type check cannot see: `TargetConfig` is not the only way to write down an
identity, and the cheapest way is a string field called what it holds.
"""


@dataclass(frozen=True)
class Reachable:
    """One field somewhere in a record's graph: who declares it, and as what."""

    owner: str
    name: str
    annotation: Any

    def stated(self) -> str:
        return f"{self.owner}.{self.name}: {self.annotation}"

    def is_a(self, wanted: type) -> bool:
        """Whether this field could hold one of those, optional or not."""
        return wanted in (get_args(self.annotation) or (self.annotation,))


def a_field_graph(record: type) -> list[Reachable]:
    """Every field reachable from that dataclass, with its annotation resolved.

    Resolved rather than read off `Field.type`, because every module here declares
    `from __future__ import annotations` and an unresolved annotation is a string a
    type assertion would silently pass.
    """
    seen: set[type] = set()
    found: list[Reachable] = []

    def walk(annotation: Any) -> None:
        for inner in get_args(annotation) or (annotation,):
            if get_args(inner):
                walk(inner)
            elif isinstance(inner, type) and is_dataclass(inner) and inner not in seen:
                seen.add(inner)
                hints = get_type_hints(inner)
                for one in fields(inner):
                    found.append(Reachable(inner.__name__, one.name, hints[one.name]))
                    walk(hints[one.name])

    walk(record)
    return found


def test_no_field_the_memory_or_the_library_holds_could_carry_a_target() -> None:
    """The identity boundary asserted from the end that survives a refactor.

    A test over what one decision *wrote* passes for a decision that wrote nothing
    interesting; this one asks whether the two records have anywhere to put an
    identity at all. Every field reachable from `DecidedRoute` — what the admission
    memory holds — and from `Case` — what a `.toml` record is written from — is
    walked, and none of them is a `TargetConfig` or is named like one.

    The queue's own record is the control, and it is the point of the exception:
    `AwaitingDecision` carries `target` deliberately (ADR-0104 §2), so this walk
    demonstrably finds an identity where one is declared. Without that half a walk
    that had quietly stopped finding fields would pass.
    """
    exception = a_field_graph(AwaitingDecision)
    named = [one.name for one in exception if one.name in NAMES_A_TARGET]
    assert named == ["target"], (
        "the walk did not find the one field the disclosure posture has an "
        "exception for, so it is not looking at anything (ADR-0104 §2)"
    )

    for record in (DecidedRoute, Case):
        graph = a_field_graph(record)
        assert graph, f"{record.__name__} has no fields to walk"
        assert not [one.stated() for one in graph if one.name in NAMES_A_TARGET], (
            f"a field reachable from {record.__name__} is named for a target. The "
            "identity stops at the decision: the pending store is the one place it "
            "lives, and the one place a decision deletes (ADR-0008, ADR-0011)"
        )
        assert not [one.stated() for one in graph if one.is_a(TargetConfig)], (
            f"a field reachable from {record.__name__} is typed as a target"
        )


def test_neither_the_memory_nor_the_library_is_told_which_agent_was_beaten(
    cases_dir: Path, leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same boundary from the calling end: no argument carries the name.

    Two routes in one measurement, so that both writes happen and both are watched.
    One the memory has never seen, so it is measured and `remember` is called with
    what the reference agents returned; one the memory holds as admitted, so `enter`
    is called with the case it becomes. Neither call is handed the target, and the
    pending record that *does* hold it is sitting in the queue the whole time.
    """
    measured = a_route(leakage_case, payload="a probe nothing has measured yet")
    admitted = a_route(leakage_case, payload="a probe the memory already holds")
    filed(measured)
    filed(admitted)
    remembered(admitted, SEPARATING)

    told: list[str] = []
    real_remember = DecidedRoutes.remember
    real_enter = entry.enter

    def watched_remember(self: DecidedRoutes, promotion: Promotion, **rest: Any) -> Any:
        told.append(repr((promotion, rest)))
        return real_remember(self, promotion, **rest)

    def watched_enter(cases: Any, library: Path, *, holder: str) -> Any:
        told.append(repr((list(cases), library, holder)))
        return real_enter(cases, library, holder=holder)

    monkeypatch.setattr(DecidedRoutes, "remember", watched_remember)
    monkeypatch.setattr(pending_routes, "enter", watched_enter)

    with a_bench(cases_dir) as deciding:
        answered(
            deciding,
            [
                RouteKey.of(measured.case).filed_under,
                RouteKey.of(admitted.case).filed_under,
            ],
        )

    assert len(told) == 2, (
        f"{len(told)} of the two writes happened, so this test is watching a "
        "decision that did not make both of them"
    )
    for call in told:
        assert A_CUSTOMER not in call, (
            "a decision handed the target's name to the admission memory or to the "
            "library. The identity stops at the decision (ADR-0008, ADR-0011)"
        )
    # And the record that does hold it is still there to have leaked it.
    assert any(record.target == A_CUSTOMER for record in PENDING_ROUTES.queue())


MEASURED_ON = date(2026, 1, 5)
"""The day the three reference agents ran, months before this row was decided."""


def test_an_admission_answered_from_memory_is_dated_the_day_the_agents_ran(
    cases_dir: Path, leakage_case: Case
) -> None:
    """ADR-0032: the record carries the measurement's date and not the decision's.

    The whole saving the memory buys is that a route decided once is not measured
    again — so a route admitted on this surface can be admitted on counts read a
    year ago, and a record dated to the morning the operator clicked would say the
    reference agents ran today when they did not. `recall` hands `promote` the
    remembered date for exactly that reason, and this is that decision observed
    where it lands: in the `.toml` a decision writes.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, SEPARATING, on=MEASURED_ON)

    with a_bench(cases_dir) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    written = load_case(cases_dir / reading["routes"][0]["entered_as"])
    assert written.admission is not None
    assert written.admission.admitted_on == MEASURED_ON, (
        "the record is dated to the day the row was decided. A route answered from "
        "the admission memory was measured earlier, and the record says when "
        "(ADR-0032)"
    )
    assert MEASURED_ON != date.today(), "this test needs a day that is not today"


def test_nothing_on_this_path_can_supply_a_date() -> None:
    """The structural half: no `today` argument exists to date a reading with.

    `entry` withholds it and `decided.recall` withholds it; this is the same
    refusal asserted over the two modules of this surface and over the bar they
    reach it through. A function here able to take one could date a year-old
    measurement to this morning, and the end-to-end assertion above would still
    pass on the day the counts happened to be read.
    """
    for source in on_this_path():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                arguments = node.args
                # Every kind of parameter, positional-only and the two catch-alls
                # included: a wall that looked at two of the four is a wall a
                # `today` walks past.
                named = {
                    one.arg
                    for one in (
                        *arguments.posonlyargs,
                        *arguments.args,
                        *arguments.kwonlyargs,
                        *(one for one in (arguments.vararg, arguments.kwarg) if one),
                    )
                }
                assert "today" not in named, f"{source.name}:{node.name} takes a date"
            if isinstance(node, ast.Attribute):
                # `today` and not `now`: `MeasurementRecord.recorded_at` stamps the
                # moment this bench started a measurement, which is a fact about the
                # request and never a date on a case record.
                assert node.attr != "today", f"{source.name} reads a clock"


def test_an_admitted_route_is_a_live_adaptive_case_the_next_run_runs(
    cases_dir: Path, leakage_case: Case
) -> None:
    """The loop closing, for a route found against somebody's real agent.

    The assertion #40 made for the swap, made here for the path this spec exists
    for. `library_provenance` counts the new record as an adaptive live case —
    which is the reading `docs/validation.md` prints as an honest zero today — and
    then the case is put to a reference agent through the entry point every run
    goes through, so what is asserted is a run *running* it and not only a file
    on disk.

    Counted under `ADAPTIVE_ON_TARGET`, which is the member the census grew for this
    population (ADR-0107 §1): a route found against a user's agent reports apart
    from one found against the three reference agents, because the two entered under
    different bars and a reader of the census has to be able to tell them apart.
    """
    proposal = a_route(leakage_case)
    record = filed(proposal)
    remembered(proposal, SEPARATING)
    counted = library_provenance(admitted_library(cases_dir))
    before = counted.live[DiscoveredBy.ADAPTIVE_ON_TARGET]

    with a_bench(cases_dir) as deciding:
        answered(deciding, [record.route.filed_under])

    grown = admitted_library(cases_dir)
    provenance = library_provenance(grown)
    assert provenance.live[DiscoveredBy.ADAPTIVE_ON_TARGET] == before + 1
    assert provenance.live[DiscoveredBy.ADAPTIVE] == counted.live[DiscoveredBy.ADAPTIVE]
    live = live_library(grown)
    [admitted] = [case for case in live if case.id == proposal.case.id]

    ran = calibrate(admitted)

    [target_run] = ran.target_runs
    assert [attempt.case_id for attempt in target_run.attempts] == [admitted.id] * (
        DECLARED_RULE.attempts_per_case
    ), (
        "the next run loaded the record and did not run it. A case in the library "
        "that no run attempts is a file, not a case"
    )


def test_the_deciding_surface_writes_no_case_record_of_its_own() -> None:
    """ADR-0033: an admitted route reaches the library through `enter` and nothing else.

    De-duplication against the library on disk, the lease, the round-trip check and
    the refusal of a record that does not clear its own bar all live in `enter`. A
    second writer would not be a second copy of that — it would be a path with none
    of it, and the row it wrote would be the one a `library_provenance` reading
    could not account for. So this side hands `enter` cases and takes an `Entry`
    back: it names no serialiser, no record suffix, and writes no file at all.
    """
    for name in PENDING_MODULES:
        source = API_DIR / name
        imported = set(imports_of(source))
        assert not [
            one
            for one in imported
            if one.endswith(("case_record", "CASE_SUFFIX"))
            or one.split(".")[0] in ("shutil", "os", "tomli_w")
        ], f"{name} names a way of writing a record rather than calling `enter`"
        assert not [
            node
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
            and ast.unparse(node.func).split(".")[-1] in WRITES
        ], f"{name} writes to the filesystem. The library's one writer is `enter`"

    assert "backend.bench.entry.enter" in set(imports_of(API_DIR / "pending_routes.py"))


def test_the_reading_carries_one_pass_per_model_with_its_attempt_counts(
    cases_dir: Path, leakage_case: Case
) -> None:
    """A bar per model — one of them here — fed by attempts and not by a stage name.

    The action is minutes long, so *how far into the pass* is the question an
    operator watching it actually has. A pass carries the attempts it has made and
    the attempts it was planned for, because a stage word cannot answer that and a
    percentage would be a figure this surface does not carry (`pending.ts`). One
    pass, because one model is declared (ADR-0107 §4).
    """
    record = filed(a_route(leakage_case))
    served = Served()

    with a_bench(cases_dir, served=served, agents=agents_on(served)) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    passes = reading["passes"]
    assert [one["model"] for one in passes] == [FIRST], (
        "one pass per declared model, in the order they are measured"
    )
    for one in passes:
        assert one["of"] > 0, "a pass planned no attempt at all measures nothing"
        assert one["attempted"] == one["of"], (
            "a measurement that finished made every attempt its rule asked for"
        )
        assert one["state"] == "measured"


def test_a_pass_that_did_not_happen_is_not_drawn_as_one_still_filling(
    cases_dir: Path, leakage_case: Case
) -> None:
    """Nobody plants the nonce, so the one pass never attacks anything.

    The distinction the four states exist for: a pass that ran keeps its counts, and
    a pass that did not is `unmeasured` rather than left `measuring` on a screen
    nothing is going to advance. A bar that stayed measuring would report a refusal
    as a wait. The pass that ran is asserted by the test above; this is the other
    side of that pair, and after ADR-0107 §4 the pair is two measurements rather
    than one measurement's two passes.
    """
    record = filed(a_route(leakage_case))
    served = Served()

    def agents(model: str) -> Equipment | None:
        return unplanted(model, served)

    with a_bench(cases_dir, served=served, agents=agents) as deciding:
        reading = answered(deciding, [record.route.filed_under])

    passes = {one["model"]: one for one in reading["passes"]}
    assert passes[FIRST]["state"] == "unmeasured"
    assert passes[FIRST]["attempted"] == 0, "nothing was sent on this model"
