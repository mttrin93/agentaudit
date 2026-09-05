"""Planting is a pre-run step: authorised, recorded, and on no counter at all.

The invariant of
[ADR-0062](../../docs/adr/0062-planting-is-a-pre-run-step-off-every-counter.md),
driven at three seams:

* `planting.plant` and `planting.required_plantings` — what is planted, and what a
  target that answers for none of its own plantings is given.
* `calibration.run_calibration` — a whole shim bench, where the counters live.
* `budget.RunBudget` — the estimate an operator confirms, which itemises the plant.

**An attempt is the unit of the denominator and a send is one message on the wire
(CONTEXT.md), and a plant is neither.** Every assertion below is about that: the
scored counter and the attempt list at the moment the hook runs, the exact spend of
a finished run, and the absence of any route from a hook to `send_message`.
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

from backend.bench import planting
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Family, LibraryVersion, Plant
from backend.bench.measurability import NotMeasurable
from backend.bench.planting import (
    Planting,
    PlantingFailed,
    PlantingFailure,
    plant,
    required_plantings,
)
from backend.bench.rule import DECLARED_RULE
from backend.bench.shim import serve_callback
from backend.graph.budget import (
    PLANTING_CALLS,
    REGISTRATION_PROBES_PER_TARGET,
    FigureKind,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState
from backend.tests.conftest import BENCH_ATTESTATION, CONFIRMING, a_target, imports_of

PLANTING_SOURCE = Path(planting.__file__)


class Agent:
    """A callback that answers, and can be given both plantings.

    A class rather than a function because a plain function cannot carry a method,
    and `declared_plants` reads the hooks off the object (ADR-0061). Everything it
    is handed is kept, so a test can read what the bench planted and when.
    """

    def __init__(self, watching: RunState | None = None) -> None:
        self.watching = watching
        self.seen: list[str] = []
        self.canary: str | None = None
        self.content: list[tuple[str, str]] = []
        self.counters_at_the_plant: list[tuple[int, int, int]] = []
        self.messages_at_the_plant: list[int] = []

    def __call__(self, message: str, session_id: str) -> str:
        self.seen.append(message)
        return self.canary or "nothing to say"

    def _note(self) -> None:
        self.messages_at_the_plant.append(len(self.seen))
        if self.watching is not None:
            self.counters_at_the_plant.append(
                (
                    self.watching.spent_in(Layer.SCORED),
                    self.watching.spent_in(Layer.ADAPTIVE),
                    len(self.watching.attempts),
                )
            )

    def plant_config_canary(self, canary: str) -> None:
        self._note()
        self.canary = canary

    def plant_retrieved_content(self, key: str, body: str) -> None:
        self._note()
        self.content.append((key, body))


class Blind:
    """A callback with no hooks at all. Its plant-dependent families are withdrawn."""

    def __call__(self, message: str, session_id: str) -> str:
        return "nothing to say"


def _calibrate(
    target: TargetConfig,
    cases: list[Case],
    planter: object | None,
    state: RunState | None = None,
) -> CalibrationResult:
    return run_calibration(
        cases=cases,
        targets=[target],
        attestation=BENCH_ATTESTATION,
        planters={} if planter is None else {target.name: planter},
        approve=CONFIRMING,
        budget=None if state is None else state.budget,
        run_state=state,
    )


def _state_for(target: TargetConfig, cases: list[Case]) -> RunState:
    declared = RunBudget.declare(cases=cases, targets=[target])
    return RunState(budget=declared, library=LibraryVersion.of(cases))


# --- The counters -------------------------------------------------------------


def test_a_plant_moves_no_counter_and_the_run_attempts_exactly_its_denominator(
    leakage_case: Case,
) -> None:
    """The headline invariant, read from inside the hook and after the run.

    Both halves are needed. The snapshot the hook takes says nothing was spent to
    reach the plant; the exact arithmetic at the end says nothing was spent *by* it,
    because a planting turn through `send_message` would put one more send in the
    scored counter and leave every other figure here unchanged.
    """
    cases = [leakage_case]
    # Two targets, because one target cannot tell *nothing had happened yet* from
    # *the plant moved nothing*. The second target's plant runs after the first
    # target's whole suite, so the counters it sees are a figure that is not zero and
    # is exactly what the first target spent — which is the reading that says the
    # plant itself added none of it.
    first, second = Agent(), Agent()
    with serve_callback(first, name="first") as one:
        with serve_callback(second, name="second") as two:
            state = RunState(
                budget=RunBudget.declare(cases=cases, targets=[one, two]),
                library=LibraryVersion.of(cases),
            )
            first.watching = second.watching = state
            result = run_calibration(
                cases=cases,
                targets=[one, two],
                attestation=BENCH_ATTESTATION,
                planters={one.name: first, two.name: second},
                approve=CONFIRMING,
                budget=state.budget,
                run_state=state,
            )

    # An attempt is the unit of the denominator and a send is one message on the
    # wire, and the two are different numbers. This library's leakage case is one
    # turn, so they coincide per attempt; they are computed apart anyway, because a
    # multi-turn case makes them diverge and the assertion below is about sends.
    attempts_per_target = DECLARED_RULE.attempts_per_case
    sends_per_target = (
        REGISTRATION_PROBES_PER_TARGET
        + DECLARED_RULE.attempts_per_case * leakage_case.turns
    )

    # At the moment each hook ran: nothing this target had spent, and — for the
    # second — exactly what the first target had. Not one message had gone to either
    # callback, so each plant is ahead of its own registration probe as well as ahead
    # of the first attempt.
    assert first.counters_at_the_plant == [(0, 0, 0)]
    assert second.counters_at_the_plant == [(sends_per_target, 0, attempts_per_target)]
    assert first.messages_at_the_plant == [0] == second.messages_at_the_plant

    # Exact, not a bound. `cases × attempts_per_case` per target, one registration
    # probe and one send per turn attempted, and no send anywhere for either plant.
    assert len(state.attempts) == len(cases) * attempts_per_target * 2
    assert state.spent_in(Layer.SCORED) == sends_per_target * 2
    # The adaptive counter is not asserted at zero here — the second layer runs after
    # the suite and spends against its own ceiling (ADR-0010), which is a figure this
    # test is not about. What it *is* about is that the plant moved neither counter,
    # and the snapshots above are the reading that says so for both.

    for target_run in result.target_runs:
        rate = target_run.rates[Family(leakage_case.family)]
        assert rate.attempts == attempts_per_target


def test_a_plant_is_recorded_with_what_authorised_it_and_with_no_send(
    leakage_case: Case,
) -> None:
    """ADR-0007's record, and the type that cannot be summed into a denominator."""
    cases = [leakage_case]
    agent = Agent()
    with serve_callback(agent, name="recorded") as target:
        result = _calibrate(target, cases, agent)

    [target_run] = result.target_runs
    [performed] = target_run.plantings
    assert performed.plant is Plant.CONFIG_CANARY
    # `None` and not a case id: the value is the run's nonce, which no record names.
    assert performed.case_id is None
    assert performed.authorised_by.attestation == BENCH_ATTESTATION
    assert performed.authorised_by.endpoint_hash

    # The record carries the attestation and nothing a rate could be read off.
    assert {field.name for field in fields(Planting)} == {
        "plant",
        "case_id",
        "authorised_by",
    }


def test_the_planted_value_is_the_run_s_own_nonce(leakage_case: Case) -> None:
    """One planted value, two roles: the hook is given the registration nonce."""
    agent = Agent()
    with serve_callback(agent, name="one-value") as target:
        result = _calibrate(target, [leakage_case], agent)

    [target_run] = result.target_runs
    assert agent.canary == target_run.registration.nonce
    assert target_run.registration.echoed


# --- No route to the wire -----------------------------------------------------


def test_the_planting_module_names_no_counter_and_no_way_onto_the_wire() -> None:
    """The invariant as a wall, because a name is a route.

    Import-level, on the reasoning `gate.py`'s own wall is asserted with: a module
    that cannot name `RunState`, a `Layer` or `send_message` cannot move a counter
    or put a plant on the wire however it is later edited.
    """
    named = sorted(
        name
        for name in imports_of(PLANTING_SOURCE)
        if name.endswith(
            (
                "runstate",
                "RunState",
                "budget",
                "Layer",
                "Attempt",
                "send_message",
                "Transcript",
                "record_call",
                "authorise_call",
            )
        )
    )
    assert not named, (
        f"{named} is imported by planting.py. A plant is neither an attempt nor a "
        "send, and an import is the route by which it would become one"
    )


def test_plant_takes_an_attestation_and_no_run_state() -> None:
    """The signature is the invariant: authorised, and with no counter in scope.

    Not "takes one and does not charge it" — takes none, which is the standing
    rule's own shape (ADR-0010): if a signature is being widened to accept both,
    stop.
    """
    signature = inspect.signature(plant)
    assert "attestation" in signature.parameters
    assert "run_state" not in signature.parameters
    assert RunState not in get_type_hints(plant).values()


def test_no_planted_body_is_ever_sent_to_the_target(injection_case: Case) -> None:
    """The content goes through the hook, and never through a message."""
    agent = Agent()
    with serve_callback(agent, name="retrieving") as target:
        _calibrate(target, [injection_case], agent)

    artefact = injection_case.planted_artefact
    assert artefact is not None
    assert agent.content == [(artefact.key, artefact.body)]
    assert not any(artefact.body in message for message in agent.seen)


# --- What is planted, and for whom --------------------------------------------


def test_the_config_canary_is_planted_once_however_many_cases_ask_for_it(
    library: list[Case],
) -> None:
    """One nonce per run, so one planting — and one retrieved artefact per record."""
    leakage = [case for case in library if case.family is Family.DATA_LEAKAGE]
    assert len(leakage) > 1

    agent = Agent()
    with serve_callback(agent, name="once") as target:
        requested = required_plantings(leakage, target, canary="NONCE-1")

    assert [request.plant for request in requested] == [Plant.CONFIG_CANARY]
    assert requested[0].arguments == {"canary": "NONCE-1"}


def test_a_url_target_is_planted_by_nobody(leakage_case: Case) -> None:
    """A target that does not answer for its own plantings is planted by its operator.

    `TargetConfig.plants` is `None` for every URL, ADR-0024 left the declaration with
    the caller, and a harness that planted into one anyway would be inventing an act
    it cannot perform.
    """
    endpoint = a_target()
    assert endpoint.plants is None

    assert required_plantings([leakage_case], endpoint, canary="NONCE-1") == ()
    assert (
        plant(
            Agent(),
            endpoint,
            [leakage_case],
            canary="NONCE-1",
            attestation=BENCH_ATTESTATION,
        )
        == ()
    )


def test_a_family_withdrawn_for_a_missing_hook_is_not_a_failed_plant(
    leakage_case: Case,
) -> None:
    """The two readings the ticket exists to keep apart.

    A hook that does not exist withdraws the family and the run finishes; a hook
    that exists and did not work stops the run. A reader who cannot tell those apart
    cannot act on either.
    """
    with serve_callback(Blind(), name="blind") as target:
        result = _calibrate(target, [leakage_case], Blind())

    [target_run] = result.target_runs
    assert target_run.plantings == ()
    assert target_run.not_measurable[Family(leakage_case.family)] is (
        NotMeasurable.NO_CONFIG_CANARY_PLANT
    )
    assert not target_run.attempts


def test_a_planting_the_target_cannot_be_given_is_never_requested(
    leakage_case: Case,
) -> None:
    """The withdrawal happens first, and `plant` does not undo it.

    `unmet_preconditions` withdrew the family before an attempt was spent, so the
    case never reaches the harness's plant — and if a caller hands it one anyway,
    nothing is requested for a planting the target said it cannot be given. Turning
    a named withdrawal into a failed run is the one thing this must not do
    (ADR-0061 §6).
    """
    with serve_callback(Blind(), name="blind") as target:
        assert target.plants == frozenset()
        assert required_plantings([leakage_case], target, canary="NONCE-1") == ()


def test_a_planting_hook_that_raises_stops_the_run_before_the_first_attempt(
    leakage_case: Case,
) -> None:
    cases = [leakage_case]

    class Breaks(Agent):
        def plant_config_canary(self, canary: str) -> None:
            raise RuntimeError("the content store was unreachable")

    agent = Breaks()
    with serve_callback(agent, name="breaks") as target:
        state = _state_for(target, cases)
        with pytest.raises(PlantingFailed) as raised:
            _calibrate(target, cases, agent, state)

    assert raised.value.failure is PlantingFailure.HOOK_RAISED
    assert raised.value.plant is Plant.CONFIG_CANARY
    # No family is measured and nothing was spent: not one message reached the
    # callback, so the run stopped ahead of the registration probe.
    assert not state.attempts
    assert state.spent_in(Layer.SCORED) == 0
    assert agent.seen == []


def test_a_target_that_declared_a_planting_and_got_no_planter_is_refused(
    leakage_case: Case,
) -> None:
    """Refused rather than skipped, because skipping reports a clean zero.

    The cases are `runnable` against this target — it said it can be planted — so a
    run that quietly planted nothing would spend every one of their attempts against
    a value that is nowhere and print the rate that reads as a defence.
    """
    with serve_callback(Agent(), name="unhanded") as target:
        with pytest.raises(PlantingFailed) as raised:
            _calibrate(target, [leakage_case], None)

    assert raised.value.failure is PlantingFailure.NO_PLANTER


def test_a_planter_that_is_not_the_object_that_was_served_is_refused(
    leakage_case: Case,
) -> None:
    with serve_callback(Agent(), name="swapped") as target:
        with pytest.raises(PlantingFailed) as raised:
            _calibrate(target, [leakage_case], Blind())

    assert raised.value.failure is PlantingFailure.HOOK_MISSING


def test_every_planting_failure_says_what_it_is_and_what_it_is_not() -> None:
    """A named outcome per mode, each spelled out, and none of them a withdrawal."""
    for failure in PlantingFailure:
        assert failure.stated().strip()
    assert "withdraw" in PlantingFailure.NO_PLANTER.stated()
    assert "has none" in PlantingFailure.HOOK_RAISED.stated()


# --- The estimate -------------------------------------------------------------


def test_the_estimate_itemises_the_plant_at_zero(leakage_case: Case) -> None:
    """A line reading zero, not a line that is absent.

    The operator confirms a ceiling before anything reaches their endpoint, and the
    registration probe is already itemised there. A planting step missing from the
    table would leave a reader to decide for themselves whether it was priced in.
    """
    budget = RunBudget.declare(cases=[leakage_case], targets=[a_target()])

    assert PLANTING_CALLS == 0
    assert budget.planting.calls == 0
    assert budget.planting.kind is FigureKind.EXACT
    assert any(line.strip().startswith("Planting") for line in budget.lines())
    assert budget.as_payload()["planting"]["calls"] == 0

    # And it is added into nothing: the total is the two layers, as it always was.
    assert budget.as_payload()["total"]["calls"] == (
        budget.as_payload()["scored"]["calls"]
        + budget.as_payload()["adaptive"]["calls"]
    )
