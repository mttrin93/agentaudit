"""The one calibration entry point. No web layer, and the tests drive this.

Everything in the pre-web scope is reached from here: the case library, the
attestation, the approval interrupt and its budget, registration and the nonce
protocol, the precondition check, the attempt, and the verdict. Ten attempts per
case (#4), the judge (#8) and the gate decision (#13) extend this callable rather
than adding a second way in.

The order below is the order ADR-0007 requires and is not an implementation
detail: attestation, then the estimate, then the halt, and only then anything that
reaches an endpoint. The approval interrupt sits ahead of registration as well as
ahead of the first attempt, because the nonce echo probe is itself a call on the
operator's endpoint — a run that had already spent something by the time it asked
would be asking about a decision it had partly taken.

`plant_nonce` stands in for the human who edits their target's system prompt when
the bench issues a nonce. A user does that by hand — hence the default of `None`,
which is the production case — and the reference agents have a test-equipment
route for it, so the nonce protocol is exercised on every gate run.
"""

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.attacker import run_case
from backend.bench.contract import TargetConfig
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, Family
from backend.bench.measurability import (
    NotMeasurable,
    not_measurable_families,
    runnable,
)
from backend.bench.registration import (
    Attestation,
    Registration,
    issue_nonce,
    register,
)
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import Rate, failure_rate
from backend.graph.approval import ApprovalOutcome, Approve, run_under_approval
from backend.graph.budget import RunBudget
from backend.graph.runstate import Attempt, RunState

PlantNonce = Callable[[TargetConfig, str], None]


@dataclass(frozen=True)
class TargetRun:
    """One target's part of a calibration run. No attempts unless registration
    completed."""

    target: TargetConfig
    registration: Registration
    attempts: tuple[Attempt, ...]
    rule: GateRule
    """The rule the attempts were run under, so the rate carries the confidence
    it was measured at."""

    not_measurable: Mapping[Family, NotMeasurable] = field(default_factory=dict)
    """The families this target could not be measured on, and why.

    A separate field from `rates` rather than a third value inside it, so that a
    consumer reading rates cannot read a refusal as a number. Empty for a target
    that met every precondition its library asked for.
    """

    def __post_init__(self) -> None:
        both = set(self.not_measurable) & {attempt.family for attempt in self.attempts}
        if both:
            raise ValueError(
                f"{sorted(both)} were reported not measurable and also attempted "
                "against this target. Not measurable is a distinct outcome from "
                "pass and from fail, and a family cannot hold two of the three"
            )

    @property
    def rates(self) -> dict[Family, Rate]:
        """This target's failure rate for each family it was attempted on.

        Per family and never pooled across them: the six families measure six
        different failures, an average over them is not a quantity, and a family
        with no attempts is absent rather than reported as a rate of zero. No
        attempts is not a failure rate of zero — a target the bench never
        measured has to stay distinguishable from one that resisted everything.
        """
        counted: dict[Family, list[Attempt]] = defaultdict(list)
        for attempt in self.attempts:
            counted[attempt.family].append(attempt)

        return {
            family: failure_rate(
                sum(1 for a in attempts if a.verdict is Verdict.SUCCEEDED),
                len(attempts),
                self.rule,
            )
            for family, attempts in counted.items()
        }


@dataclass(frozen=True)
class CalibrationResult:
    run_state: RunState
    target_runs: tuple[TargetRun, ...]
    budget: RunBudget
    approval: ApprovalOutcome
    """What the operator was shown and what they answered. Carried on the result
    because a run's cost and its consent are part of its record, not preamble to
    it — and because an empty `target_runs` means two different things depending
    on which way this went."""


def run_calibration(
    cases: Sequence[Case],
    targets: Sequence[TargetConfig],
    attestation: Attestation,
    plant_nonce: PlantNonce | None = None,
    approve: Approve | None = None,
    rule: GateRule = DECLARED_RULE,
    adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET,
    budget: RunBudget | None = None,
) -> CalibrationResult:
    """Run the given cases against the given targets and return what was measured.

    Nothing reaches a target until the estimate has been presented and confirmed.
    With no `approve`, the run halts at the interrupt and returns having spent
    nothing — which is the correct behaviour rather than a limitation.

    `budget` is for a ceiling that was declared earlier: at 6b the estimate is
    presented and confirmed in one request and the suite runs in another, and the
    run has to be held to the ceiling the operator actually saw rather than to one
    recomputed later against whatever the library holds by then. It defaults to
    being declared from these inputs, which is the case where the two cannot
    differ.
    """
    declared = budget or RunBudget.declare(
        cases=cases, targets=targets, rule=rule, adaptive=adaptive
    )
    run_state = RunState(budget=declared)
    target_runs: list[TargetRun] = []

    def run_suite() -> None:
        for target in targets:
            target_runs.append(
                _run_target(
                    target=target,
                    cases=cases,
                    attestation=attestation,
                    run_state=run_state,
                    plant_nonce=plant_nonce,
                    rule=rule,
                )
            )

    approval = run_under_approval(declared, run_suite, approve)

    return CalibrationResult(
        run_state=run_state,
        target_runs=tuple(target_runs),
        budget=declared,
        approval=approval,
    )


def _run_target(
    target: TargetConfig,
    cases: Sequence[Case],
    attestation: Attestation,
    run_state: RunState,
    plant_nonce: PlantNonce | None,
    rule: GateRule,
) -> TargetRun:
    """Register one target, then run every case against it if it registered."""
    nonce = issue_nonce()
    if plant_nonce is not None:
        plant_nonce(target, nonce)
    registration = register(target, nonce, attestation, run_state)

    # Preconditions gate measurability, never scoring: a case this target cannot
    # answer is skipped before an attempt is spent on it, and the families left
    # with nothing to run report not measurable rather than a rate (ADR-0004).
    attempts: tuple[Attempt, ...] = ()
    if registration.complete:
        # The nonce that proved control is the canary under the leakage case:
        # one planted value, two roles (ADR-0007).
        attempts = tuple(
            attempt
            for case in runnable(cases, target)
            for attempt in run_case(
                target, case, canary=nonce, run_state=run_state, rule=rule
            )
        )

    return TargetRun(
        target=target,
        registration=registration,
        attempts=attempts,
        rule=rule,
        not_measurable=not_measurable_families(cases, target),
    )
