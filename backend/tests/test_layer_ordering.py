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

from typing import Any

import pytest

from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.library import Case
from backend.graph.runstate import Attempt, RunState
from backend.tests.conftest import served_references

ADAPTIVE_LAYER_EXISTS = hasattr(RunState(), "episodes")

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
            plant_nonce=references.plant_nonce,
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
