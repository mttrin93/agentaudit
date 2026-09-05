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
from decimal import Decimal

import pytest

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.attacker import run_attempt
from backend.bench.calibration import run_calibration
from backend.bench.contract import RetryPolicy
from backend.bench.library import Case, Family, Transform
from backend.bench.rule import DECLARED_RULE
from backend.bench.selection import AttackLayer, AttackSelection
from backend.graph.budget import (
    NOT_PRICED,
    REGISTRATION_PROBES_PER_TARGET,
    BudgetExceeded,
    CallFigure,
    CallPrice,
    Estimate,
    FigureKind,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CONFIRMING,
    SENDS,
    a_budget,
    a_target,
    reference_target,
    some_cases,
    unlisted_case,
)
from backend.tests.flaky_target import IMPATIENT, flaky_target


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


def test_the_adaptive_layer_switched_off_is_nothing_on_the_wire_and_says_so() -> None:
    """The estimate moves when the selection moves — the operator sees the price.

    A layer switched off puts no call on the operator's endpoint, so the figure they
    are asked to confirm drops to nothing for it and the basis says why rather than
    reading as a bound somebody mistyped. Still a `CEILING`: nothing about a layer
    that ran is exact, and a bound of zero is the one bound that cannot be exceeded
    (ADR-0007, ADR-0058).

    The ceiling drops with it, which is the half that is enforced rather than shown:
    a run that somehow opened an episode against a switched-off layer is refused at
    the counter before the first probe.
    """
    scored_only = AttackSelection(
        layers=frozenset({AttackLayer.SINGLE_TURN, AttackLayer.FIXED_MULTI_TURN}),
        transforms=frozenset(Transform),
    )
    whole = a_budget(cases=3, targets=2)
    narrowed = RunBudget.declare(
        cases=some_cases(3),
        targets=[a_target(f"target-{i}", sends=SENDS) for i in range(2)],
        selection=scored_only,
    )

    assert whole.estimate.adaptive.calls > 0
    assert narrowed.estimate.adaptive.calls == 0
    assert narrowed.estimate.adaptive.kind is FigureKind.CEILING
    assert "switched off" in narrowed.estimate.adaptive.basis
    assert narrowed.adaptive_ceiling == 0
    # And the scored half is untouched: switching the agent off buys a cheaper run
    # and costs no scored attempt, which is why it is the switch with no denominator
    # behind it (ADR-0010).
    assert narrowed.estimate.scored == whole.estimate.scored
    assert narrowed.estimate.total.calls < whole.estimate.total.calls


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


def test_a_fleet_of_differently_patient_targets_gets_the_tight_ceiling() -> None:
    """Summed per target, not the most patient target's limit applied to all.

    `max` across the fleet would be a ceiling nobody's arithmetic asks for: it
    would let a run spend the patient target's allowance against the impatient
    one, which is a consent figure loosened by a convenience.
    """
    cases = some_cases(2)
    patient, impatient = a_target("patient", sends=3), a_target("impatient", sends=1)

    budget = RunBudget.declare(cases=cases, targets=[patient, impatient])

    per_target = REGISTRATION_PROBES_PER_TARGET + 2 * DECLARED_RULE.attempts_per_case
    assert budget.scored_ceiling == per_target * 3 + per_target * 1
    assert budget.scored_ceiling < budget.estimate.scored.calls * 3
    # The largest limit is still reported, so a reader can see where it came from.
    assert budget.retry_allowance == 3


def test_a_priced_run_shows_what_each_figure_costs() -> None:
    budget = RunBudget.declare(
        cases=some_cases(1),
        targets=[a_target("one", sends=1)],
        price=CallPrice(per_call=Decimal("0.002"), currency="EUR"),
    )
    estimate = budget.estimate

    # 11 calls at 0.002 is 0.022, which rounds *up* to the minor unit: a consent
    # figure that rounded down would understate the bench's own bill.
    assert estimate.scored.calls == 11
    assert estimate.cost(estimate.scored) == "0.03 EUR"
    # A bound's cost is a bound, carried from the figure rather than restated.
    assert estimate.cost(estimate.adaptive).startswith("≤ ")
    assert estimate.cost(estimate.total).startswith("≤ ")
    assert budget.as_payload()["currency"] == "EUR"

    # And the rows add up to the total. Each is rounded up and only then added, so
    # a reader checking the column with a pencil agrees with the bench — and the
    # total is never the smaller of the two ways to compute it.
    price = CallPrice(per_call=Decimal("0.002"), currency="EUR")
    assert price.total_of(estimate.scored.calls, estimate.adaptive.calls) == (
        price.cost_of(estimate.scored.calls) + price.cost_of(estimate.adaptive.calls)
    )
    assert price.total_of(estimate.scored.calls, estimate.adaptive.calls) >= (
        price.cost_of(estimate.total.calls)
    )


def test_an_unpriced_run_says_so_rather_than_showing_zero() -> None:
    # A run whose cost is unknown and a run that is free are different facts, and
    # only one of them is safe to confirm without reading further.
    budget = a_budget()

    assert budget.estimate.price is None
    assert budget.estimate.cost(budget.estimate.scored) == NOT_PRICED
    assert budget.as_payload()["scored"]["cost"] == NOT_PRICED
    assert budget.as_payload()["currency"] == ""
    assert any("Not priced" in line for line in budget.lines())


def test_a_price_cannot_be_negative_or_currencyless() -> None:
    with pytest.raises(ValueError):
        CallPrice(per_call=Decimal("-0.01"))
    with pytest.raises(ValueError):
        CallPrice(per_call=Decimal("0.01"), currency="  ")


def test_nothing_shown_with_a_bound_may_be_exceeded() -> None:
    """The estimate's total is conditional; the hard ceiling is the limit.

    A `≤ 277` a run may legitimately overrun threefold would be a bound in
    typography only, so the total says what it assumes and the enforced figure is
    shown beside it, larger, and also as a bound.
    """
    budget = a_budget()
    lines = budget.lines()

    assert budget.hard_ceiling.kind is FigureKind.CEILING
    assert budget.hard_ceiling.calls == (
        budget.scored_ceiling + budget.adaptive_ceiling
    )
    assert budget.hard_ceiling.calls >= budget.estimate.total.calls
    assert any("if no message is retried" in line for line in lines)
    assert any("the run aborts rather than exceed it" in line for line in lines)


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


def test_spend_is_visible_per_layer_while_the_run_is_still_in_progress(
    leakage_case: Case,
) -> None:
    """Read between attempts rather than after the run.

    The figure exists so that a long run is observable while it happens, and so
    that it is visible which half is consuming the budget. The reader at 6b is the
    progress endpoint; the state it will read is this one.
    """
    nonce = "AGENTAUDIT-CANARY-MIDRUN"
    with reference_target(name="trivial") as reference:
        budget = RunBudget.declare(cases=[leakage_case], targets=[reference.target])
        run_state = RunState(budget=budget)
        reference.plant_nonce(reference.target, nonce, "run-budget")

        seen = []
        for index in range(3):
            run_attempt(
                reference.target,
                leakage_case,
                canary=nonce,
                run_state=run_state,
                index=index,
            )
            seen.append(
                (
                    run_state.spent_in(Layer.SCORED),
                    run_state.spent_in(Layer.ADAPTIVE),
                )
            )

    assert seen == [(1, 0), (2, 0), (3, 0)]
    assert run_state.spent_in(Layer.SCORED) < budget.ceiling(Layer.SCORED)


def test_a_call_recorded_without_being_authorised_still_cannot_pass_the_ceiling() -> (
    None
):
    """The counter's own backstop, for a call site that reaches it without asking.

    `authorise_call` guards the two call sites that exist today; #16 adds one, and
    this is what catches it on the day it is written. It raises after recording,
    because by then the call has been made and a counter that lied about it would
    be worse than the breach.
    """
    budget = a_budget()
    run_state = RunState(budget=budget)

    with pytest.raises(BudgetExceeded) as abort:
        run_state.record_call(Layer.ADAPTIVE, sends=budget.adaptive_ceiling + 1)

    assert abort.value.layer is Layer.ADAPTIVE
    assert run_state.spent_in(Layer.ADAPTIVE) == budget.adaptive_ceiling + 1
    assert "nothing had authorised" in str(abort.value)


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
    # And the other layer ran on this endpoint too, retrying every message the same
    # way, without a single one of its sends landing in the figure above. Two
    # counters rather than one is what makes that checkable (ADR-0007, ADR-0010).
    adaptive = result.run_state.spent_in(Layer.ADAPTIVE)
    assert 0 < adaptive <= result.budget.adaptive_ceiling
