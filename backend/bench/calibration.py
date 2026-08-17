"""The one calibration entry point. No web layer, and the tests drive this.

Everything in the pre-web scope is reached from here: the case library,
registration and the nonce protocol, the attempt, and the verdict. The approval
interrupt (#5), ten attempts per case (#4), the judge (#8) and the gate decision
(#13) extend this callable rather than adding a second way in.

`plant_nonce` stands in for the human who edits their target's system prompt when
the bench issues a nonce. A user does that by hand — hence the default of `None`,
which is the production case — and the reference agents have a test-equipment
route for it, so the nonce protocol is exercised on every gate run.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from backend.bench.attacker import run_case
from backend.bench.contract import TargetConfig
from backend.bench.library import Case
from backend.bench.registration import Registration, issue_nonce, register
from backend.bench.evaluator import Verdict
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import Rate, failure_rate
from backend.graph.runstate import Attempt, RunState

PlantNonce = Callable[[TargetConfig, str], None]


@dataclass(frozen=True)
class TargetRun:
    """One target's part of a calibration run. No attempts unless registration completed."""

    target: TargetConfig
    registration: Registration
    attempts: tuple[Attempt, ...]
    rule: GateRule
    """The rule the attempts were run under, so the rate carries the confidence it was measured at."""

    @property
    def rate(self) -> Rate | None:
        """The share of this target's attempts that succeeded, with its interval.

        `None` where nothing was attempted, because no attempts is not a failure
        rate of zero: a target the bench never measured has to stay
        distinguishable from one that resisted everything.
        """
        if not self.attempts:
            return None
        succeeded = sum(
            1 for attempt in self.attempts if attempt.verdict is Verdict.SUCCEEDED
        )
        return failure_rate(succeeded, len(self.attempts), self.rule)


@dataclass(frozen=True)
class CalibrationResult:
    run_state: RunState
    target_runs: tuple[TargetRun, ...]


def run_calibration(
    cases: Sequence[Case],
    targets: Sequence[TargetConfig],
    plant_nonce: PlantNonce | None = None,
    rule: GateRule = DECLARED_RULE,
) -> CalibrationResult:
    """Run the given cases against the given targets and return what was measured."""
    run_state = RunState()
    target_runs: list[TargetRun] = []

    for target in targets:
        nonce = issue_nonce()
        if plant_nonce is not None:
            plant_nonce(target, nonce)
        registration = register(target, nonce, run_state)

        attempts: tuple[Attempt, ...] = ()
        if registration.complete:
            # The nonce that proved control is the canary under the leakage case:
            # one planted value, two roles (ADR-0007).
            attempts = tuple(
                attempt
                for case in cases
                for attempt in run_case(
                    target, case, canary=nonce, run_state=run_state, rule=rule
                )
            )

        target_runs.append(
            TargetRun(
                target=target,
                registration=registration,
                attempts=attempts,
                rule=rule,
            )
        )

    return CalibrationResult(run_state=run_state, target_runs=tuple(target_runs))
