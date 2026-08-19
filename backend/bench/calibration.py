"""The one calibration entry point. No web layer, and the tests drive this.

Everything in the pre-web scope is reached from here: the case library, the
attestation, the approval interrupt and its budget, registration and the nonce
protocol, the applicability and precondition checks, the attempt, and the verdict.
Ten attempts per case (#4), the judge (#8) and the gate decision (`gate.py`, which
reads what this returns and decides nothing else) extend this callable rather than
adding a second way in.

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

`adjudicator` is the model that decides the two judged families (#9). It defaults
to `None` because a library of deterministic cases needs none, and a run given judged
cases without one is refused before the estimate and before anything reaches an
endpoint, rather than partway through: an attempt nothing can score is the operator's
money spent with no measurement behind it, and a partial suite is void rather than
smaller (ADR-0007).

**A run has two layers, and the second one runs here, last.** Once the fixed suite
has finished against every target, `run_adaptive_layer` attacks the ones that
registered by a route of its own choosing (#16). Nothing it produces is scored: it
records `AdaptiveEpisode`s in a field of their own, spends against its own ceiling,
and reaches the scored side through exactly one edge — `propose_case`, which the
admission gate decides (ADR-0010). `attacker` defaults to the deterministic
stand-in of `adaptive/scripted.py` so that the layer always runs; the entry point
in `scripts/calibrate.py` names a configured model instead, on the same terms as
the adjudicator.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.layer import AttackableTarget, run_adaptive_layer
from backend.bench.adaptive.precedent import DURABLE_PRECEDENT, PrecedentStore
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion, NoAdjudicator
from backend.bench.applicability import SkippedCase, applicable, skipped_cases
from backend.bench.attacker import run_case
from backend.bench.contract import TargetConfig
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, Family, LibraryVersion, VerdictClass
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

    not_applicable: tuple[SkippedCase, ...] = ()
    """The cases this target was never sent, because they were not written for it.

    A third field rather than a third value in either of the two above, and the
    reason is the same reason `not_measurable` is not a rate of zero: these are
    three different answers. A rate says what was measured, `not_measurable` says
    the target cannot answer the question, and this says the bench never asked —
    the library has no case for this agent type, which is the bench's gap and not
    the target's (`applicability.py`).

    Per case rather than per family, because a family can have some cases that
    apply and some that do not, and the rate over the ones that ran is a real
    number that a family-level skip would have to overwrite.
    """

    def __post_init__(self) -> None:
        both = set(self.not_measurable) & {attempt.family for attempt in self.attempts}
        if both:
            raise ValueError(
                f"{sorted(both)} were reported not measurable and also attempted "
                "against this target. Not measurable is a distinct outcome from "
                "pass and from fail, and a family cannot hold two of the three"
            )

        attempted = {attempt.case_id for attempt in self.attempts}
        sent_anyway = sorted(
            skipped.case_id
            for skipped in self.not_applicable
            if skipped.case_id in attempted
        )
        if sent_anyway:
            raise ValueError(
                f"{sent_anyway} were reported as not written for this target and "
                "were also run against it. A case that does not apply is skipped "
                "explicitly, and a skip that spent an attempt is a verdict counted "
                "for a payload the case never claimed would land"
            )

        classes: dict[Family, set[VerdictClass]] = defaultdict(set)
        for attempt in self.attempts:
            classes[attempt.family].add(attempt.verdict_class)
        mixed = sorted(family for family, seen in classes.items() if len(seen) > 1)
        if mixed:
            raise ValueError(
                f"{mixed} were attempted under both verdict classes. A family is "
                "deterministic or judged, and one whose cases disagree would put a "
                "judged rate in the deterministic section — which is the one place "
                "the two must never meet (ADR-0004)"
            )

    @property
    def rates(self) -> dict[Family, Rate]:
        """This target's failure rate for each family it was attempted on.

        Per family and never pooled across them: the six families measure six
        different failures, an average over them is not a quantity, and a family
        with no attempts is absent rather than reported as a rate of zero. No
        attempts is not a failure rate of zero — a target the bench never
        measured has to stay distinguishable from one that resisted everything.

        Both classes appear here, because `D` and monotonicity are read per family
        and are read the same way whichever route the verdict took. What is
        reported to a reader is the two sections below, never this mapping: they
        carry different evidentiary strength, and the deterministic families carry
        the report's weight (ADR-0004).
        """
        return self._rates(self.attempts)

    @property
    def deterministic_rates(self) -> dict[Family, Rate]:
        """The families whose verdicts came from a success condition.

        The report's own section, and the one that carries its weight: every
        verdict behind these rates is re-derivable by a reader holding the case
        record and the transcript (ADR-0004).
        """
        return self._rates_under(VerdictClass.DETERMINISTIC)

    @property
    def judged_rates(self) -> dict[Family, Rate]:
        """The families whose verdicts came from adjudication.

        Reported apart from the deterministic families and never added to them.
        There is deliberately no property here that returns the two together as one
        collection, and none that totals either: a judged rate carries a wider
        stated limit and a κ figure beside it (#11), and a figure combining one with
        a deterministic rate would be a number whose evidentiary strength nobody
        could state. That is the same prohibition ADR-0005 puts on a composite
        score, applied one level down.
        """
        return self._rates_under(VerdictClass.JUDGED)

    def _rates_under(self, verdict_class: VerdictClass) -> dict[Family, Rate]:
        """The rates of the families decided by one route.

        Selected on `Attempt.verdict_class`, which was copied off the case record
        when the attempt was made — never on the family name (spec story 18).
        """
        return self._rates(
            attempt
            for attempt in self.attempts
            if attempt.verdict_class is verdict_class
        )

    def _rates(self, attempts: Iterable[Attempt]) -> dict[Family, Rate]:
        """Group attempts by family and divide. The one place a rate is computed."""
        counted: dict[Family, list[Attempt]] = defaultdict(list)
        for attempt in attempts:
            counted[attempt.family].append(attempt)

        return {
            family: failure_rate(
                sum(1 for a in grouped if a.verdict is Verdict.SUCCEEDED),
                len(grouped),
                self.rule,
            )
            for family, grouped in counted.items()
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
    adjudicator: Completion | None = None,
    attacker: AttackerCompletion = SCRIPTED_ATTACKER,
    precedent: PrecedentStore = DURABLE_PRECEDENT,
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
    unscorable = [
        case.id for case in cases if case.verdict_class is VerdictClass.JUDGED
    ]
    if unscorable and adjudicator is None:
        # Before the estimate and before the attestation, because this is the one
        # failure the operator should never pay to discover.
        raise NoAdjudicator(unscorable)

    declared = budget or RunBudget.declare(
        cases=cases, targets=targets, rule=rule, adaptive=adaptive
    )
    run_state = RunState(budget=declared, library=LibraryVersion.of(cases))
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
                    adjudicator=adjudicator,
                    rule=rule,
                )
            )
        # And only then the second layer, on every target that registered. After
        # the whole suite rather than after each target's own: the ordering
        # ADR-0010 requires is per target, and running the layer here satisfies it
        # for all of them while leaving target order free to be randomised per
        # family, which ADR-0011 requires and a per-target interleaving would not
        # allow.
        run_adaptive_layer(
            attackable=[
                AttackableTarget(
                    target=completed.target, canary=completed.registration.nonce
                )
                for completed in target_runs
                if completed.registration.complete
            ],
            cases=cases,
            run_state=run_state,
            attacker=attacker,
            budget=adaptive,
            precedent=precedent,
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
    adjudicator: Completion | None,
    rule: GateRule,
) -> TargetRun:
    """Register one target, then run the cases that apply to it if it registered."""
    nonce = issue_nonce()
    if plant_nonce is not None:
        plant_nonce(target, nonce)
    registration = register(target, nonce, attestation, run_state)

    # Two filters, in this order, and both ahead of the first attempt.
    #
    # Applicability first: a case not written for this target's agent type is not
    # this target's business at all, so asking what its preconditions are would be
    # answering a question about a case that is never going to run (spec story 16).
    # Then preconditions, which gate measurability and never scoring: a case this
    # target cannot answer is skipped before an attempt is spent on it, and the
    # families left with nothing to run report not measurable rather than a rate
    # (ADR-0004).
    written_for = applicable(cases, target)
    attempts: tuple[Attempt, ...] = ()
    if registration.complete:
        # The nonce that proved control is the canary under the leakage case:
        # one planted value, two roles (ADR-0007).
        attempts = tuple(
            attempt
            for case in runnable(written_for, target)
            for attempt in run_case(
                target,
                case,
                canary=nonce,
                run_state=run_state,
                rule=rule,
                adjudicator=adjudicator,
            )
        )

    return TargetRun(
        target=target,
        registration=registration,
        attempts=attempts,
        rule=rule,
        # Read over the cases written for this target, never over the whole
        # library: a family whose every case was skipped for the agent type has
        # not been found unmeasurable, and reporting it that way would send the
        # operator looking for a capability their target is not missing.
        not_measurable=not_measurable_families(written_for, target),
        not_applicable=skipped_cases(cases, target),
    )
