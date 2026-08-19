"""What `POST /runs` refuses, what it presents, and what it does not spend.

The bench takes a URL and a bearer token and fires jailbreak payloads at whatever
answers, and this is the surface where it does that for somebody who is not sitting
at a terminal. So most of these tests assert an *absence* — no call reached the
endpoint, no counter moved — because a halt has no other evidence, and because the
two controls that make a run authorised are the two things a web layer is most
likely to quietly drop (ADR-0007).

The target is served over real HTTP with a ledger in front of it. What the bench
did to somebody's endpoint is a fact about the wire, so these tests count requests
at the endpoint rather than trust the run's own counters: a run that spent nothing
and a run whose counters say it spent nothing are different claims, and only one of
them is checked by reading `RunState`.
"""

from __future__ import annotations

import ast
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.api.app import create_app
from backend.api.runs import BenchConfig, BenchRuns, RunRecord, RunStatus
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.episode import EpisodeOutcome
from backend.bench.calibration import run_calibration
from backend.bench.contract import TargetConfig
from backend.bench.library import Case, LibraryVersion
from backend.bench.registration import Attestation
from backend.graph.budget import Layer, RunBudget
from backend.graph.runstate import RunState
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import (
    REFERENCE_AGENTS,
    ReferenceConfig,
    create_reference_app,
)
from backend.targets.reference.serving import serve
from backend.targets.reference.tools import DECLARED_TOOL_NAMES
from backend.tests.conftest import AUTH_TOKEN, BENCH_ATTESTATION, a_target, some_cases

API_DIR = Path(__file__).resolve().parents[1] / "api"

STATEMENT_FIELDS = (
    "authorised_to_test",
    "not_production",
    "accepts_provider_policy_and_cost",
)

QUIET_SECONDS = 1.0
"""How long a halted run is watched for a call it must not make.

An absence is only checkable over an interval. A run that answered its own
interrupt would have its registration probe on the wire inside a millisecond, so a
second is a long time to be sure nothing did.
"""

HELD_SECONDS = 2.0
"""How long the target holds its first message in the background-run test.

Long enough that a request which returned rather than waited is unambiguous, and
finite so that one which waited fails on an assertion instead of hanging.
"""

SETTLED = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.DECLINED,
        RunStatus.UNANSWERED,
        RunStatus.REGISTRATION_REFUSED,
        RunStatus.ABORTED,
        RunStatus.FAILED,
    }
)
"""The states a run does not leave. Everything else is a run still in flight."""


# --- a target with a ledger in front of it ---------------------------------------


@dataclass
class Ledger:
    """What reached the endpoint, and a gate that can hold the next thing that does.

    The gate is open by default. Closed, it holds every message at the endpoint,
    which is how a test can look at a run while the suite is still running rather
    than race it.
    """

    hits: int = 0
    gate: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self) -> None:
        self.gate.set()


class Counted:
    """ASGI middleware that counts and holds messages to a target.

    Only `/messages` — the nonce-planting route of the reference agents is test
    equipment standing in for an operator editing a system prompt by hand, and
    counting it would count something no real run does.
    """

    def __init__(self, app: ASGIApp, ledger: Ledger) -> None:
        self.app = app
        self.ledger = ledger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and str(scope["path"]).endswith("/messages"):
            self.ledger.hits += 1
            await anyio.to_thread.run_sync(self.ledger.gate.wait)
        await self.app(scope, receive, send)


@dataclass(frozen=True)
class Watched:
    """A served reference agent, the ledger in front of it, and how to plant a nonce."""

    target: TargetConfig
    ledger: Ledger
    plant: Any


@contextmanager
def watched_reference(name: str = "trivial") -> Iterator[Watched]:
    """Serve the reference agents with a ledger in front of the one named.

    Built here rather than taken from `conftest.served_references` because these
    tests need to see the wire: the assertion that nothing was sent is an
    assertion about what arrived, and the fixture that serves a target for a
    calibration run has no reason to count.
    """
    ledger = Ledger()
    app: FastAPI = create_reference_app(
        ReferenceConfig(
            model=ModelConfig.parse("stub:obedient"),
            auth_token=AUTH_TOKEN,
            agents=REFERENCE_AGENTS,
        )
    )
    app.add_middleware(Counted, ledger=ledger)
    with serve(app) as base_url:
        yield Watched(
            target=TargetConfig(
                name=name,
                url=f"{base_url}/reference/{name}/messages",
                auth_token=AUTH_TOKEN,
                agent_type="assistant",
                exposes_tool_calls=True,
                declared_tools=DECLARED_TOOL_NAMES,
            ),
            ledger=ledger,
            plant=nonce_planter(base_url),
        )


@contextmanager
def api(
    cases: list[Case],
    adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET,
    approval_wait_seconds: float = 60.0,
) -> Iterator[tuple[TestClient, BenchRuns]]:
    """The API over one bench, and the registry the run records live in."""
    app = create_app(
        BenchConfig(
            cases=cases,
            adaptive=adaptive,
            approval_wait_seconds=approval_wait_seconds,
        )
    )
    with TestClient(app) as client:
        yield client, cast(BenchRuns, app.state.bench)


def a_request(
    target: TargetConfig,
    nonce: str,
    price_per_call: str | None = "0.002",
    withheld: str | None = None,
    note_planted: bool = False,
) -> dict[str, Any]:
    """One start request, with any one of the three statements withheld."""
    attestation = dict.fromkeys(STATEMENT_FIELDS, True)
    if withheld is not None:
        attestation[withheld] = False
    return {
        "target": {
            "name": target.name,
            "url": target.url,
            "auth_token": target.auth_token,
            "agent_type": target.agent_type,
            "exposes_tool_calls": True,
            "declared_tools": list(DECLARED_TOOL_NAMES),
            "sends": target.retry.sends,
        },
        "attestation": {"identity": BENCH_ATTESTATION.identity, **attestation},
        "nonce": nonce,
        "cost": {"price_per_call": price_per_call, "currency": "USD"},
        "note_planted": note_planted,
    }


def registered(client: TestClient, watched: Watched) -> str:
    """A nonce this bench issued, planted in the target the way an operator would."""
    nonce = str(client.post("/nonces").json()["nonce"])
    watched.plant(watched.target, nonce)
    return nonce


def settled(record: RunRecord, seconds: float = 90.0) -> RunRecord:
    """Wait for a run to reach a state it does not leave."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if record.status in SETTLED:
            return record
        time.sleep(0.02)
    raise AssertionError(f"run {record.run_id} is still {record.status}")


# --- the attestation gate --------------------------------------------------------


@pytest.mark.parametrize("withheld", STATEMENT_FIELDS)
def test_a_run_cannot_start_with_any_one_statement_withheld(
    withheld: str, leakage_case: Case
) -> None:
    """Each of the three, refused on its own, before anything is sent.

    Parametrised because the interesting failures are the second and third: a user
    would never infer that these payloads generate provider policy violations
    against their own account, or that they spend their own inference budget, so
    an API that accepted two of three would be dropping exactly the statements
    ADR-0007 exists to make explicit.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        response = client.post(
            "/runs", json=a_request(watched.target, nonce, withheld=withheld)
        )

    assert response.status_code == 422
    assert dict(Attestation.STATEMENTS)[withheld] in response.json()["detail"]
    assert watched.ledger.hits == 0


def test_a_run_cannot_start_on_a_nonce_this_bench_never_issued(
    leakage_case: Case,
) -> None:
    """The half of the guard that can be enforced before a call is spent.

    A caller who did not register cannot have planted anything, so the run they
    are asking for could not prove control of the endpoint however it went. The
    echo itself is checked inside the run, because the probe that checks it is a
    call on the operator's endpoint and the halt is ahead of it.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        response = client.post(
            "/runs", json=a_request(watched.target, "AGENTAUDIT-CANARY-INVENTED")
        )

    assert response.status_code == 422
    assert "never issued that nonce" in response.json()["detail"]
    assert watched.ledger.hits == 0


def test_a_target_that_does_not_echo_the_nonce_is_never_attempted(
    leakage_case: Case,
) -> None:
    """Registration refused, and the difference between that and a rate of zero.

    The nonce is issued and never planted, so the target answers the probe with
    something else. One call reaches the endpoint — the probe itself, which the
    estimate charges for — and no attempt follows it.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = str(client.post("/nonces").json()["nonce"])
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": True, "identity": "operator"},
        )
        record = settled(_record(bench, started))

    assert record.status is RunStatus.REGISTRATION_REFUSED
    assert "no attempt was made" in record.statement
    assert record.run_state.attempts == []
    assert watched.ledger.hits == 1


# --- the two figures -------------------------------------------------------------


def test_the_estimate_is_two_figures_and_nothing_in_it_is_an_average(
    leakage_case: Case,
) -> None:
    """The fixed suite exactly, the adaptive layer as a ceiling, and no blend.

    The two are asserted on their *kind* rather than on their value, because that
    is what a caller reads: a fact and a bound, with the arithmetic printed under
    each. The combined figures are checked to be bounds as well — a fact plus a
    bound is a bound — and every figure is checked against the one number that
    must never appear, which is their average.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()

    estimate = started["estimate"]
    scored, adaptive = estimate["scored"], estimate["adaptive"]

    assert scored["kind"] == "exact"
    assert scored["calls"] == 11
    assert "10 attempts" in scored["basis"]
    assert adaptive["kind"] == "ceiling"
    assert adaptive["calls"] == 96
    assert "T=8" in adaptive["basis"]

    assert estimate["total"]["kind"] == "ceiling"
    assert estimate["hard_ceiling"]["kind"] == "ceiling"
    average = (scored["calls"] + adaptive["calls"]) / 2
    assert average not in {figure["calls"] for figure in _figures(estimate)}


def test_a_run_nobody_priced_says_not_priced_rather_than_zero(
    leakage_case: Case,
) -> None:
    """An unknown cost and a free run are different facts."""
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post(
            "/runs", json=a_request(watched.target, nonce, price_per_call=None)
        ).json()

    assert [figure["cost"] for figure in _figures(started["estimate"])] == [
        "not priced"
    ] * 4


def test_a_price_the_caller_did_not_declare_is_refused(
    leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No figure is filled in from the environment, and a missing one is a refusal.

    The confirmation is the liability record, so the number in it has to be the
    caller's own. A bench that read a price from its own configuration would be
    presenting a figure nobody agreed to — and one that is wrong by construction,
    because the endpoint is the operator's on the operator's provider.
    """
    monkeypatch.setenv("AGENTAUDIT_PRICE_PER_CALL", "0.02")
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        request = a_request(watched.target, nonce)
        del request["cost"]["price_per_call"]
        response = client.post("/runs", json=request)

    assert response.status_code == 422
    assert "price_per_call" in response.text
    assert watched.ledger.hits == 0


def test_no_module_of_the_api_reads_the_environment() -> None:
    """The prohibition as an import test rather than as a rule to remember.

    In the pattern the repository already uses for a constraint that would fail
    silently: a figure defaulted from the environment would present exactly like a
    declared one, and the first time anybody found out would be a bill.
    """
    for source in sorted(API_DIR.glob("*.py")):
        assert "os" not in _imports_of(source), f"{source.name} imports os"
        assert "dotenv" not in _imports_of(source), f"{source.name} imports dotenv"


# --- the halt --------------------------------------------------------------------


def test_nothing_reaches_the_target_before_the_interrupt_is_answered(
    leakage_case: Case,
) -> None:
    """The halt is ahead of registration, so nothing arrives while it is unanswered.

    The run id comes back here — before the suite has started at all, which is the
    strongest form of "before the suite completes": a run that takes many minutes
    does not depend on this request staying open.

    The absence is asserted over an interval rather than at an instant, because a
    run that had answered its own interrupt would reach the endpoint within
    milliseconds of being started and a test that looked once would look before it
    did. `QUIET_SECONDS` is that interval.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        response = client.post("/runs", json=a_request(watched.target, nonce))
        started = response.json()
        record = _record(bench, started)
        time.sleep(QUIET_SECONDS)

        assert response.status_code == 202
        assert record.status is RunStatus.AWAITING_APPROVAL
        assert started["run_id"]
        assert started["status"] == "awaiting_approval"
        assert "nothing has been sent" in started["statement"]
        assert watched.ledger.hits == 0
        assert record.spent == dict.fromkeys(Layer, 0)
        assert started["spent"] == {"scored": 0, "adaptive": 0}


def test_a_declined_interrupt_sends_nothing_and_spends_nothing_and_says_so(
    leakage_case: Case,
) -> None:
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        answered = client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": False, "identity": "operator", "reason": "too dear"},
        ).json()
        record = settled(_record(bench, started))

    assert answered["status"] == "declined"
    assert record.status is RunStatus.DECLINED
    assert "too dear" in record.statement
    assert "Nothing was sent" in record.statement
    assert watched.ledger.hits == 0
    assert record.spent == dict.fromkeys(Layer, 0)
    assert record.result is not None
    assert record.result.target_runs == ()


def test_an_unanswered_interrupt_sends_nothing_and_spends_nothing_and_says_so(
    leakage_case: Case,
) -> None:
    """Nobody said no; nobody said anything. Two states rather than one.

    A caller that read this as *declined* would lose the difference between a run
    a human refused and a run a human never saw, which is the distinction
    `ApprovalOutcome` keeps for the same reason.
    """
    with (
        watched_reference() as watched,
        api([leakage_case], approval_wait_seconds=0.2) as (client, bench),
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = settled(_record(bench, started))

    assert record.status is RunStatus.UNANSWERED
    assert "never answered" in record.statement
    assert "Nothing was sent" in record.statement
    assert watched.ledger.hits == 0
    assert record.spent == dict.fromkeys(Layer, 0)


def test_an_interrupt_is_answered_once(leakage_case: Case) -> None:
    """A second answer is refused rather than applied.

    The first answer is the one a human gave in front of the figures. A second
    arriving after the suite has started would be consent recorded for a spend
    that is already happening.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        answer = {"confirmed": False, "identity": "operator"}
        first = client.post(f"/runs/{started['run_id']}/approval", json=answer)
        second = client.post(f"/runs/{started['run_id']}/approval", json=answer)

    assert first.status_code == 200
    assert second.status_code == 409
    assert "answered" in second.json()["detail"]


# --- the suite, in the background ------------------------------------------------


def test_the_run_id_comes_back_while_the_suite_is_still_running(
    leakage_case: Case,
) -> None:
    """The confirming request returns before the suite finishes.

    The endpoint holds every message while the ledger's gate is closed, and a
    timer opens it a couple of seconds later — so a request that answered the
    interrupt and returned reports a run that has spent nothing yet, and a request
    that waited for the suite reports a finished one. The difference is what this
    asserts, and the timer is what stops the second case hanging instead of
    failing.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = _record(bench, started)
        watched.ledger.gate.clear()
        threading.Timer(HELD_SECONDS, watched.ledger.gate.set).start()

        answered = client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": True, "identity": "operator"},
        ).json()

        assert answered["run_id"] == started["run_id"]
        assert answered["status"] == "running"
        assert answered["spent"] == {"scored": 0, "adaptive": 0}

        finished = settled(record)

    assert finished.status is RunStatus.COMPLETED
    assert finished.confirmed_by == "operator"


def test_the_suite_runs_under_the_ceiling_that_was_confirmed(
    leakage_case: Case,
) -> None:
    """The run is counted against the budget that was presented, not a later one.

    Same object, so the two cannot drift: an estimate separated from the run it
    was presented for is an estimate nobody can check.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = _record(bench, started)
        client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": True, "identity": "operator"},
        )
        settled(record)

    assert record.status is RunStatus.COMPLETED
    assert record.run_state.budget is record.budget
    assert record.presented == record.budget.as_payload()
    assert len(record.run_state.attempts) == 10
    assert watched.ledger.hits == record.run_state.calls_spent
    for layer in Layer:
        assert record.spent[layer] <= record.budget.ceiling(layer)


def test_an_abort_mid_episode_records_that_episode_as_censored(
    leakage_case: Case,
) -> None:
    """A ceiling reached inside an episode, and the one word it must not produce.

    The record on the run is the ceiling the operator confirmed, so a layer that
    would spend past it is stopped rather than allowed to finish — the shape of a
    run whose library grew between the confirmation and the start. The episode the
    abort cut short is **censored**: the attacker stopped, and a target that was
    never given the chance to hold must not read as one that did (ADR-0007,
    ADR-0011).
    """
    with (
        watched_reference(name="hardened") as watched,
        api([leakage_case]) as (
            client,
            bench,
        ),
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = _record(bench, started)
        _tighten(
            record,
            AdaptiveBudget(turns_per_episode=1, episodes_per_family=1, family_count=1),
        )
        client.post(
            f"/runs/{started['run_id']}/approval",
            json={"confirmed": True, "identity": "operator"},
        )
        settled(record)

    assert record.status is RunStatus.ABORTED
    assert "censored, never as resisted" in record.statement
    assert record.run_state.episodes
    # In flight rather than never started: the ceiling was reached between one
    # probe and the next, which is the abort this criterion is about.
    assert record.run_state.episodes[-1].turns >= 1
    assert all(
        episode.outcome is EpisodeOutcome.CENSORED
        for episode in record.run_state.episodes
    )
    assert record.spent[Layer.ADAPTIVE] <= record.budget.adaptive_ceiling


# --- the seam the run state travels through --------------------------------------


def test_a_run_state_handed_in_is_the_one_the_run_fills() -> None:
    """A run watched while it happens is watched through this record.

    Without it the only run state a caller ever sees is the one handed back when
    the run is over, and a progress route reading that would report nothing until
    there was nothing left to report.
    """
    cases = some_cases(1)
    budget = RunBudget.declare(cases=cases, targets=[a_target()])
    state = RunState(budget=budget, library=LibraryVersion.of(cases))

    result = run_calibration(
        cases=cases,
        targets=[a_target()],
        attestation=BENCH_ATTESTATION,
        budget=budget,
        run_state=state,
    )

    assert result.run_state is state


def test_a_run_state_counting_against_another_ceiling_is_refused() -> None:
    """A counter and a limit that disagree are a run with no limit."""
    cases = some_cases(1)
    budget = RunBudget.declare(cases=cases, targets=[a_target()])
    elsewhere = RunBudget.declare(cases=some_cases(4), targets=[a_target()])

    with pytest.raises(ValueError, match="different ceiling"):
        run_calibration(
            cases=cases,
            targets=[a_target()],
            attestation=BENCH_ATTESTATION,
            budget=budget,
            run_state=RunState(budget=elsewhere, library=LibraryVersion.of(cases)),
        )


# --- helpers ---------------------------------------------------------------------


def _record(bench: BenchRuns, started: dict[str, Any]) -> RunRecord:
    record = bench.record(str(started["run_id"]))
    assert record is not None
    return record


def _figures(estimate: dict[str, Any]) -> list[dict[str, Any]]:
    return [estimate[name] for name in ("scored", "adaptive", "total", "hard_ceiling")]


def _tighten(record: RunRecord, adaptive: AdaptiveBudget) -> None:
    """Hold this run to a smaller adaptive ceiling than its layer will spend.

    Both the record's budget and the state's, because they are the same limit read
    from two places and `run_calibration` refuses a run whose counter and ceiling
    disagree.
    """
    budget = RunBudget.declare(
        cases=record.plan.cases, targets=[record.target], adaptive=adaptive
    )
    record.budget = budget
    record.run_state.budget = budget


def _imports_of(source: Path) -> set[str]:
    """Every module the given module imports, dotted."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    return names
