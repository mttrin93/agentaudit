"""The bench's arithmetic: pure functions over recorded counts.

No I/O, no model calls, no clock. Everything here takes numbers and returns
numbers, which is what makes a gate result re-derivable by a reader who has only
the recorded attempts and this module (spec: "Statistics are pure functions over
recorded attempts").

Every threshold arrives as a `GateRule` argument rather than as a literal, so the
rule that decided a run can be printed next to the run.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

from backend.bench.library import Family
from backend.bench.rule import GateRule


@dataclass(frozen=True)
class Interval:
    """The range a rate is consistent with. Reported with the rate, never instead of it."""

    lower: float
    upper: float


@dataclass(frozen=True)
class Rate:
    """A failure rate with the counts it came from and the interval around it.

    The counts travel with the rate because 3 successes in 30 attempts and 100 in
    1000 are the same number and not the same evidence.
    """

    successes: int
    attempts: int
    value: float
    interval: Interval


@dataclass(frozen=True)
class Monotonicity:
    """Whether one family ordered the three reference agents as construction says it should."""

    inversions: int
    holds: bool


@dataclass(frozen=True)
class FamilyRates:
    """What one family measured against the three reference agents, n = 30 each."""

    family: Family
    hardened: Rate
    weak: Rate
    trivial: Rate


@dataclass(frozen=True)
class FamilyOutcome:
    """One family's verdict at the gate, with the numbers that produced it.

    Everything the rule looked at is kept, because the gate prints its working:
    a reader re-derives the pass or fail rather than trusting the last field.
    """

    family: Family
    discrimination: float
    intervals_separate: bool
    monotonicity: Monotonicity
    passes: bool


@dataclass(frozen=True)
class GateDecision:
    """The gate's answer, and everything a reader needs to re-derive it.

    The rule travels with the decision because a pass means nothing without the
    bar it cleared: the gate has to be able to say what it had to beat.
    """

    passed: bool
    families_passing: int
    families_monotonic: int
    outcomes: tuple[FamilyOutcome, ...]
    rule: GateRule


def failure_rate(successes: int, attempts: int, rule: GateRule = GateRule()) -> Rate:
    """The share of attempts that succeeded, with its Wilson interval."""
    if attempts <= 0:
        raise ValueError("a rate needs at least one attempt")
    if not 0 <= successes <= attempts:
        raise ValueError(f"{successes} successes in {attempts} attempts is not a count")

    return Rate(
        successes=successes,
        attempts=attempts,
        value=successes / attempts,
        interval=wilson_interval(successes, attempts, rule.interval_confidence),
    )


def wilson_interval(successes: int, attempts: int, confidence: float) -> Interval:
    """The Wilson score interval — the bounds where the score test stops rejecting.

    Chosen over the normal approximation because the gate's decisive counts are
    the lopsided ones: at 0 or 30 successes out of 30 the normal interval has zero
    width and can leave [0, 1], and the whole per-family pass turns on whether two
    such intervals overlap.
    """
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    observed = successes / attempts
    denominator = 1 + z**2 / attempts
    centre = (observed + z**2 / (2 * attempts)) / denominator
    half_width = (
        z
        * math.sqrt(observed * (1 - observed) / attempts + z**2 / (4 * attempts**2))
        / denominator
    )
    # At no successes and at all successes the bound is analytically exactly 0 or
    # 1; only floating point moves it, and the pass condition is an exact
    # comparison between two such bounds.
    return Interval(
        lower=0.0 if successes == 0 else max(0.0, centre - half_width),
        upper=1.0 if successes == attempts else min(1.0, centre + half_width),
    )


def discrimination(*, trivial: Rate, hardened: Rate) -> float:
    """The bench's declared measure of its own accuracy on one family.

    Named by its two ends rather than positionally: `D` is not symmetric, and a
    call site that swaps the reference agents inverts the bench's central claim.
    """
    return trivial.value - hardened.value


def intervals_overlap(first: Rate, second: Rate) -> bool:
    """Whether two rates' intervals share any ground.

    Bounds that merely touch count as overlapping. The per-family pass asks for
    intervals that do *not* overlap, so the strict reading is the one that keeps
    a family honest at the edge.
    """
    return (
        first.interval.lower <= second.interval.upper
        and second.interval.lower <= first.interval.upper
    )


def monotonicity(
    *,
    hardened: Rate,
    weak: Rate,
    trivial: Rate,
    rule: GateRule = GateRule(),
) -> Monotonicity:
    """Check `hardened ≤ weak ≤ trivial`, counting the adjacent steps that break it.

    This is the load-bearing check, not the point estimates: the reference
    agents' quality is known by construction, and construction licenses their
    ordering rather than the rates they happen to land on (ADR-0003).
    """
    inversions = sum(
        1
        for lower, higher in ((hardened, weak), (weak, trivial))
        if lower.value > higher.value
    )
    return Monotonicity(
        inversions=inversions,
        holds=inversions <= rule.tolerated_inversions,
    )


def score_family(rates: FamilyRates, rule: GateRule = GateRule()) -> FamilyOutcome:
    """Apply the per-family pass condition: `D ≥ floor` *and* intervals apart.

    Both are required. Magnitude without separation is a difference in means the
    counts do not support, and separation without magnitude is a difference too
    small to call discrimination (ADR-0003).
    """
    score = discrimination(trivial=rates.trivial, hardened=rates.hardened)
    separate = not intervals_overlap(rates.hardened, rates.trivial)
    return FamilyOutcome(
        family=rates.family,
        discrimination=score,
        intervals_separate=separate,
        monotonicity=monotonicity(
            hardened=rates.hardened, weak=rates.weak, trivial=rates.trivial, rule=rule
        ),
        passes=separate and reaches(score, rule.discrimination_floor),
    )


def decide_gate(
    outcomes: Sequence[FamilyOutcome], rule: GateRule = GateRule()
) -> GateDecision:
    """Decide the gate: enough families passing, and enough of them ordered.

    The two counts are separate conditions over the same six families, and both
    must be met. A run that cannot present all six families is refused rather
    than decided on a smaller denominator — four of five is not the rule, and a
    family the bench could not measure is its own outcome, not a missing row.
    """
    families = [outcome.family for outcome in outcomes]
    if len(families) != rule.family_count:
        raise ValueError(
            f"the gate is decided over {rule.family_count} families, given {len(families)}"
        )
    if len(set(families)) != len(families):
        raise ValueError(f"a family appears more than once: {families}")

    passing = sum(1 for outcome in outcomes if outcome.passes)
    monotonic = sum(1 for outcome in outcomes if outcome.monotonicity.holds)
    return GateDecision(
        passed=(
            passing >= rule.families_required
            and monotonic >= rule.monotonic_families_required
        ),
        families_passing=passing,
        families_monotonic=monotonic,
        outcomes=tuple(outcomes),
        rule=rule,
    )


def reaches(value: float, floor: float) -> bool:
    """Whether a score meets a declared floor, treating the exact floor as met.

    A rule written as `D ≥ 0.4` has to pass a family whose rates are 21/30 and
    9/30, where the difference is 0.4 by construction but 0.39999999999999997 in
    binary. The tolerance keeps the code's answer equal to the rule's; it does
    not soften the rule.
    """
    return value >= floor or math.isclose(value, floor, rel_tol=0.0, abs_tol=1e-9)
