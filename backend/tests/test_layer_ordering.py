"""The one invariant of the two-layer run that no type can hold.

ADR-0010 keeps the scored and adaptive layers apart with a type: an
`AdaptiveEpisode` cannot be constructed from an `Attempt`, so no adaptive turn
can enter a rate. That closes the denominator, and it does nothing about
*ordering*. A target carrying persistent state — a conversation store, a cache, a
rate limiter that trips — contaminated by an adaptive turn before a scored
attempt corrupts the measurement by a route the separation cannot see, because by
then both records are already correctly separated.

So the rule is: **adaptive episodes run strictly after the fixed suite, per
target.** This file is its enforcement, and it is written before the layer it
guards (#16) so that the ordering cannot be introduced and broken in the same
commit. It skips until `RunState` gains `episodes`, and activates on the commit
that would otherwise be the first able to break it. An invariant with no failing
test survives exactly as long as the person who wrote it is reading the diff.
"""

from dataclasses import replace
from typing import Any

import pytest

from backend.api.run_config import BenchConfig, plan_for
from backend.bench.adaptive.layer import objectives_for
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.library import AnyFamily, Case, DiscoveredBy, Family, Transform
from backend.bench.selection import (
    EVERY_CONSTRUCTION,
    AttackLayer,
    AttackSelection,
)
from backend.graph.budget import Layer, RunBudget
from backend.graph.runstate import Attempt, RunState
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CONFIRMING,
    a_target,
    served_references,
)
from backend.tests.test_api_settings import a_base64_variant

ADAPTIVE_LAYER_EXISTS = hasattr(
    RunState(budget=RunBudget.declare(cases=(), targets=())), "episodes"
)

pytestmark = pytest.mark.skipif(
    not ADAPTIVE_LAYER_EXISTS,
    reason=(
        "The adaptive layer is #16. These tests activate when `RunState` gains "
        "`episodes`; they are written first because the invariant they hold "
        "(ADR-0010) is the one the type separation cannot enforce."
    ),
)


def started_at(record: object) -> float:
    """When an attempt or an episode began.

    Read reflectively because neither record carries the field yet. A missing
    timestamp fails loudly rather than skipping: an adaptive layer that arrives
    without the field that makes ordering checkable is precisely the outcome
    this file exists to prevent.
    """
    value = getattr(record, "started_at", None)
    assert isinstance(value, (int, float)) and not isinstance(value, bool), (
        f"{type(record).__name__} carries no `started_at`. The layer-ordering "
        "invariant of ADR-0010 cannot be checked without one on both records."
    )
    return float(value)


def episodes_of(result: CalibrationResult) -> list[Any]:
    episodes = getattr(result.run_state, "episodes", None)
    assert episodes is not None
    return list(episodes)


def calibrate_all_three(case: Case) -> CalibrationResult:
    """One run over all three reference agents, through the entry point."""
    with served_references() as references:
        return run_calibration(
            cases=[case],
            targets=[served.target for served in references.served],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )


def test_no_adaptive_episode_precedes_a_scored_attempt(leakage_case: Case) -> None:
    result = calibrate_all_three(leakage_case)
    episodes = episodes_of(result)
    assert episodes, "A run that produced no episodes cannot evidence the ordering."

    last_attempt: dict[str, float] = {}
    for attempt in result.run_state.attempts:
        began = started_at(attempt)
        last_attempt[attempt.target_name] = max(
            last_attempt.get(attempt.target_name, began), began
        )

    for episode in episodes:
        target_name = episode.target_name
        assert target_name in last_attempt, (
            f"{target_name} was attacked adaptively but has no scored attempts. "
            "The adaptive layer runs after the fixed suite, never instead of it."
        )
        assert started_at(episode) > last_attempt[target_name], (
            f"An adaptive episode against {target_name} began before that "
            "target's last scored attempt finished. Every attempt after it is "
            "measured against a target the attacker had already touched, which "
            "is the denominator corrupted by a route no type can see (ADR-0010)."
        )


def test_an_episode_is_not_an_attempt(leakage_case: Case) -> None:
    """The type separation itself, asserted rather than assumed.

    `Attempt` and an adaptive turn carry the same fields — case, family, target,
    transcript — so nothing but the type stops `TargetRun.rates` counting both.
    """
    result = calibrate_all_three(leakage_case)

    for episode in episodes_of(result):
        assert not isinstance(episode, Attempt), (
            "An episode was recorded as an `Attempt`. Every rate in the bench "
            "now has an adaptive turn in its denominator, the arithmetic is "
            "still valid, and no other test will fail (ADR-0010)."
        )


def test_the_layer_an_operator_switched_off_opens_no_episode_at_all(
    leakage_case: Case,
) -> None:
    """The scored half of the run is untouched, and the second layer never opens.

    The ordering invariant above is about a layer that runs; this is the same
    boundary read at the other extreme. An operator who switched the adaptive layer
    off is owed a run that spends nothing on it — the estimate they confirmed says
    nothing on the wire (`test_budget.py`) — and a layer that opened one episode
    anyway would have touched the endpoint after the confirmation said it would not
    (ADR-0007, ADR-0058).

    **No episode, and never an episode count of zero.** `ReportView.rows` draws the
    discovery count beside every family's rate as a pre-worded string and each
    outcome is counted for itself (ADR-0056), so a layer that ran no episode
    contributes no count rather than a count that reads as *the attacker found
    nothing*.
    """
    scored_only = AttackSelection(
        layers=frozenset({AttackLayer.SINGLE_TURN, AttackLayer.FIXED_MULTI_TURN}),
        transforms=frozenset(Transform),
    )
    with served_references() as references:
        result = run_calibration(
            cases=[leakage_case],
            targets=[served.target for served in references.served],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            selection=scored_only,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )

    assert episodes_of(result) == []
    assert result.run_state.spent_in(Layer.ADAPTIVE) == 0
    # And the suite still ran: switching the agent off narrows no denominator, which
    # is why it is the switch with no rate behind it.
    assert result.run_state.attempts
    assert result.run_state.spent_in(Layer.SCORED) > 0


def test_a_construction_selection_narrows_what_the_adaptive_layer_aims_at(
    leakage_case: Case, scope_creep_case: Case
) -> None:
    """The one place a *scored* switch reaches the unscored layer, stated and asserted.

    The two layers share one list of cases: `plan_for` filters it and
    `run_calibration` hands what survives to both, so a construction switched off
    narrows the pool `objectives_for` chooses each family's objective from. That is
    the same mechanism the family switch already uses on purpose
    (`BenchConfig.families`), and it reaches no rate — but it is a scored-side switch
    with an effect on the adaptive layer, so it is asserted rather than left to be
    discovered (ADR-0058 §2).

    **What it does not do is change what an episode is about.** An objective supplies
    the family and the success condition and its payload is never sent — the attacker
    composes every probe (`prompt.episode_brief`, `proposal.py`) — and every variant of
    a family measures the same failure against the same criterion, which is the premise
    pooling already rests on (ADR-0055). So a family that keeps *any* construction
    keeps an objective that asks the same question, and `A_effort` stays a reading
    about the attacker rather than about the selection.

    **A family the selection empties opens no episode**, and it needs no second
    mechanism to do it: an episode needs a deterministic case for its family, and a
    family whose cases are gone has none.
    """
    variant = a_base64_variant(leakage_case)
    family = Family(leakage_case.family)
    config = BenchConfig(cases=[leakage_case, variant, scope_creep_case])
    target = a_target("customer-agent")

    def aims_at(selection: AttackSelection) -> dict[AnyFamily, Case]:
        plan = plan_for(replace(config, selection=selection), note_planted=True)
        return objectives_for(plan.cases, target)

    whole = aims_at(EVERY_CONSTRUCTION)
    assert whole[family].id == leakage_case.id

    # The plain construction off: the family still has an objective, it is the variant,
    # and it asks the same question — same family, same success condition.
    encodings_only = aims_at(
        AttackSelection(
            layers=frozenset(AttackLayer),
            transforms=frozenset(Transform) - {Transform.PLAIN},
        )
    )
    assert encodings_only[family].id == variant.id
    assert encodings_only[family].success_condition == leakage_case.success_condition
    assert encodings_only[family].family == leakage_case.family

    # And with both of that family's constructions off, no objective and so no episode
    # — while the family that kept one still has hers.
    emptied = aims_at(
        AttackSelection(
            layers=frozenset(AttackLayer),
            transforms=frozenset(Transform) - {Transform.PLAIN, Transform.BASE64},
        )
    )
    assert family not in emptied
    assert emptied == {}
