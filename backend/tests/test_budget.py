"""The consent surface: two figures, two ceilings, and the abort that holds them.

The arithmetic here is tested as arithmetic — pure functions over declared
configuration, on the same terms as the gate statistics — and the abort is tested
at seam one, because a ceiling that is not enforced on the path a real run takes
is a number in a docstring.

What these tests are really guarding is that the two figures stay two figures. A
fact and a bound blended into one point estimate would still add up, no other test
would fail, and the user would have consented to a number the bench had made up.
"""

from dataclasses import replace

import pytest

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.calibration import run_calibration
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.library import Case, Family
from backend.bench.rule import DECLARED_RULE
from backend.graph.budget import (
    REGISTRATION_PROBES_PER_TARGET,
    BudgetExceeded,
    CallFigure,
    Estimate,
    FigureKind,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CONFIRMING,
    reference_target,
    unlisted_case,
)
from backend.tests.flaky_target import IMPATIENT, flaky_target

SENDS = 3
"""The retry limit the targets below declare, and so the multiplier on the ceiling."""


def a_target(name: str = "target", sends: int = SENDS) -> TargetConfig:
    """A target description. Never served — these tests do arithmetic, not calls."""
    return TargetConfig(
        name=name,
        url=f"https://{name}.invalid/messages",
        auth_token="token",
        agent_type="assistant",
        retry=RetryPolicy(sends=sends, backoff_seconds=0.0),
    )


def some_cases(count: int) -> list[Case]:
    return [
        unlisted_case(payload=f"payload {i}", case_id=f"case-{i}") for i in range(count)
    ]


def a_budget(cases: int = 3, targets: int = 2, sends: int = SENDS) -> RunBudget:
    return RunBudget.declare(
        cases=some_cases(cases),
        targets=[a_target(f"target-{i}", sends=sends) for i in range(targets)],
    )


def test_the_scored_figure_is_the_librarys_own_arithmetic() -> None:
    budget = a_budget(cases=3, targets=2)
    per_target = REGISTRATION_PROBES_PER_TARGET + 3 * DECLARED_RULE.attempts_per_case

    assert budget.estimate.scored.calls == 2 * per_target
    assert budget.estimate.scored.kind is FigureKind.EXACT
    # The basis is published with the figure so a reader can check it rather than
    # believe it.
    assert str(DECLARED_RULE.attempts_per_case) in budget.estimate.scored.basis


def test_the_adaptive_figure_is_the_worst_case_and_never_an_average() -> None:
    budget = a_budget(cases=3, targets=2)
    adaptive = DECLARED_ADAPTIVE_BUDGET

    # Every episode running to its cap: six families, k episodes each, T turns
    # each. An average would be a smaller number, and a smaller number here is
    # the failure this test exists to catch — it invites a run to exceed what the
    # operator agreed to.
    assert budget.estimate.adaptive.calls == 2 * (
        adaptive.family_count
        * adaptive.episodes_per_family
        * adaptive.turns_per_episode
    )
    assert budget.estimate.adaptive.kind is FigureKind.CEILING


def test_the_declared_adaptive_budget_is_the_stated_one() -> None:
    adaptive = DECLARED_ADAPTIVE_BUDGET

    assert (adaptive.turns_per_episode, adaptive.episodes_per_family) == (8, 2)
    assert adaptive.family_count == len(Family)
    assert adaptive.episode_count == 12
    assert adaptive.turn_ceiling == 96


def test_an_adaptive_budget_with_no_turns_in_it_is_refused() -> None:
    with pytest.raises(ValueError):
        AdaptiveBudget(turns_per_episode=0)


def test_a_fact_plus_a_bound_is_a_bound() -> None:
    budget = a_budget()
    total = budget.estimate.total

    assert total.calls == budget.estimate.scored.calls + budget.estimate.adaptive.calls
    assert total.kind is FigureKind.CEILING
    assert total.rendered().startswith("≤")


def test_two_facts_add_to_a_fact() -> None:
    # Otherwise the rule would be "everything is a ceiling", which carries no
    # information and would let the scored layer's exactness quietly disappear.
    one = CallFigure(calls=10, kind=FigureKind.EXACT, basis="ten")
    two = CallFigure(calls=5, kind=FigureKind.EXACT, basis="five")

    assert (one + two).kind is FigureKind.EXACT


def test_an_estimate_cannot_present_the_adaptive_layer_as_exact() -> None:
    with pytest.raises(ValueError):
        Estimate(
            scored=CallFigure(calls=180, kind=FigureKind.EXACT, basis="arithmetic"),
            adaptive=CallFigure(calls=40, kind=FigureKind.EXACT, basis="on average"),
        )


def test_an_estimate_cannot_present_the_scored_layer_as_a_bound() -> None:
    with pytest.raises(ValueError):
        Estimate(
            scored=CallFigure(calls=180, kind=FigureKind.CEILING, basis="about"),
            adaptive=CallFigure(calls=96, kind=FigureKind.CEILING, basis="worst case"),
        )


def test_the_ceiling_covers_every_message_retried_to_the_transport_limit() -> None:
    budget = a_budget(cases=3, targets=2, sends=SENDS)

    assert budget.retry_allowance == SENDS
    assert budget.scored_ceiling == budget.estimate.scored.calls * SENDS
    assert budget.adaptive_ceiling == budget.estimate.adaptive.calls * SENDS


def test_a_ceiling_below_the_figure_it_is_meant_to_cover_is_refused() -> None:
    budget = a_budget()

    with pytest.raises(ValueError):
        RunBudget(
            estimate=budget.estimate,
            scored_ceiling=budget.estimate.scored.calls - 1,
            adaptive_ceiling=budget.adaptive_ceiling,
            retry_allowance=1,
        )

    with pytest.raises(ValueError):
        RunBudget(
            estimate=budget.estimate,
            scored_ceiling=budget.scored_ceiling,
            adaptive_ceiling=budget.estimate.adaptive.calls - 1,
            retry_allowance=1,
        )


def test_the_run_state_reports_what_each_layer_has_spent() -> None:
    run_state = RunState(budget=a_budget())

    run_state.record_call(Layer.SCORED, sends=4)
    run_state.record_call(Layer.ADAPTIVE, sends=7)

    assert run_state.spent_in(Layer.SCORED) == 4
    assert run_state.spent_in(Layer.ADAPTIVE) == 7
    assert run_state.calls_spent == 11


def test_a_message_is_refused_before_it_is_sent_when_its_worst_case_will_not_fit() -> (
    None
):
    budget = a_budget()
    run_state = RunState(budget=budget)
    run_state.record_call(Layer.SCORED, sends=budget.scored_ceiling - SENDS + 1)
    spent_before = run_state.spent_in(Layer.SCORED)

    with pytest.raises(BudgetExceeded) as abort:
        run_state.authorise_call(Layer.SCORED, SENDS)

    assert abort.value.layer is Layer.SCORED
    assert abort.value.ceiling == budget.scored_ceiling
    # Refused rather than detected: the call that would have breached the ceiling
    # was never made, so nothing was spent to find out.
    assert run_state.spent_in(Layer.SCORED) == spent_before


def test_the_adaptive_ceiling_is_enforced_against_its_own_counter() -> None:
    budget = a_budget()
    run_state = RunState(budget=budget)

    # A scored layer spent to its limit says nothing about the adaptive one.
    run_state.record_call(Layer.SCORED, sends=budget.scored_ceiling)
    run_state.authorise_call(Layer.ADAPTIVE, sends=1)

    run_state.record_call(Layer.ADAPTIVE, sends=budget.adaptive_ceiling)
    with pytest.raises(BudgetExceeded) as abort:
        run_state.authorise_call(Layer.ADAPTIVE, sends=1)

    assert abort.value.layer is Layer.ADAPTIVE
    assert abort.value.ceiling == budget.adaptive_ceiling


def test_an_unspent_scored_allowance_cannot_be_borrowed_by_the_adaptive_layer() -> None:
    # The second ceiling of ADR-0007 exists so that a per-family turn cap times
    # six families is not a limit consented to once and then forgotten. Two
    # ceilings enforced against their sum would delete it: a suite that came in
    # under its own figure would hand the attacker the difference.
    budget = a_budget()
    run_state = RunState(budget=budget)

    run_state.record_call(Layer.ADAPTIVE, sends=budget.adaptive_ceiling)

    assert run_state.spent_in(Layer.SCORED) == 0
    assert run_state.calls_spent < budget.scored_ceiling + budget.adaptive_ceiling
    with pytest.raises(BudgetExceeded):
        run_state.authorise_call(Layer.ADAPTIVE, sends=1)


def test_a_run_held_to_a_ceiling_declared_over_a_smaller_library_aborts(
    leakage_case: Case,
) -> None:
    """A misconfigured library cannot spend without limit.

    The ceiling passed in is the one an operator confirmed — at 6b it is declared
    in the request that presents the estimate and the suite runs in another — so
    the run is held to what was actually agreed to rather than to a figure
    recomputed later against whatever the library happens to hold now.
    """
    with reference_target(name="trivial") as reference:
        # A target that does not retry, so the ceiling is the arithmetic with no
        # retry allowance folded into it and the abort lands where it is legible.
        target = replace(
            reference.target, retry=RetryPolicy(sends=1, backoff_seconds=0.0)
        )
        agreed = RunBudget.declare(cases=[leakage_case], targets=[target])
        assert agreed.scored_ceiling == (
            REGISTRATION_PROBES_PER_TARGET + DECLARED_RULE.attempts_per_case
        )

        with pytest.raises(BudgetExceeded) as abort:
            run_calibration(
                cases=[leakage_case, unlisted_case("second payload", "case-second")],
                targets=[target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=reference.plant_nonce,
                approve=CONFIRMING,
                budget=agreed,
            )

    assert abort.value.layer is Layer.SCORED
    assert abort.value.ceiling == agreed.scored_ceiling
    # Mid-run, and at the ceiling exactly: the run spent every call it was given
    # and then refused the next one, rather than stopping early or overrunning.
    assert abort.value.spent == agreed.scored_ceiling


def test_a_run_that_retries_every_message_still_fits_inside_its_ceiling(
    leakage_case: Case,
) -> None:
    """The tight bound, exercised at the bound.

    Every message on this endpoint takes the full retry allowance, which is what
    the ceiling was built from — so the run finishes having spent exactly its
    ceiling and is never aborted early. A ceiling with a comfortable-looking
    margin instead of this arithmetic would pass every other test in the file.
    """
    with flaky_target(failures_before_reply=IMPATIENT.sends - 1) as flaky:
        result = run_calibration(
            cases=[leakage_case],
            targets=[flaky.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=flaky.plant_nonce,
            approve=CONFIRMING,
        )

    scored = result.run_state.spent_in(Layer.SCORED)
    assert scored == result.budget.scored_ceiling
    assert scored == result.budget.estimate.scored.calls * IMPATIENT.sends
    # And the layer that never ran spent nothing, rather than sharing a counter.
    assert result.run_state.spent_in(Layer.ADAPTIVE) == 0
