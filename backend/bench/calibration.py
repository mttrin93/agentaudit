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

from backend.bench.attacker import run_attempt
from backend.bench.contract import TargetConfig
from backend.bench.library import Case
from backend.bench.registration import Registration, issue_nonce, register
from backend.graph.runstate import Attempt, RunState

PlantNonce = Callable[[TargetConfig, str], None]


@dataclass(frozen=True)
class TargetRun:
    """One target's part of a calibration run. No attempts unless registration completed."""

    target: TargetConfig
    registration: Registration
    attempts: tuple[Attempt, ...]


@dataclass(frozen=True)
class CalibrationResult:
    run_state: RunState
    target_runs: tuple[TargetRun, ...]


def run_calibration(
    cases: Sequence[Case],
    targets: Sequence[TargetConfig],
    plant_nonce: PlantNonce | None = None,
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
                run_attempt(target, case, canary=nonce, run_state=run_state, index=0)
                for case in cases
            )

        target_runs.append(
            TargetRun(target=target, registration=registration, attempts=attempts)
        )

    return CalibrationResult(run_state=run_state, target_runs=tuple(target_runs))
