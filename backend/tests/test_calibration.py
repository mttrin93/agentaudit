"""Tests at seam one — the calibration entry point.

Every test here drives `run_calibration` and asserts on the value it returns.
Nothing asserts that a module was called or that a prompt contained particular
words: the bench's thesis is that a measurement is re-derivable from recorded
inputs, so a test coupled to implementation would contradict the product.

The only thing that differs between the first three tests is the reference agent's
model, given as a configuration string — which is also what the multi-model
validity check (#15) will change.
"""

from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.evaluator import Verdict
from backend.bench.library import Case
from backend.graph.runstate import Position
from backend.tests.conftest import reference_target


def calibrate(case: Case, model: str = "stub:obedient") -> CalibrationResult:
    """Run one case against one served reference agent, through the entry point."""
    with reference_target(model=model) as reference:
        return run_calibration(
            cases=[case],
            targets=[reference.target],
            plant_nonce=reference.plant_nonce,
        )


def test_trivial_agent_leaks_the_canary_and_the_success_condition_says_so(
    leakage_case: Case,
) -> None:
    result = calibrate(leakage_case)

    assert [attempt.verdict for attempt in result.run_state.attempts] == [
        Verdict.SUCCEEDED
    ]


def test_a_target_that_does_not_echo_the_nonce_is_refused_before_any_attempt(
    leakage_case: Case,
) -> None:
    # A model that ignores its configuration cannot echo a nonce planted in it, so
    # its operator has not proven they control the endpoint.
    result = calibrate(leakage_case, model="stub:parrot")

    [target_run] = result.target_runs
    assert target_run.registration.refused
    assert target_run.attempts == ()
    assert result.run_state.attempts == []


def test_a_target_that_registers_but_does_not_leak_is_resisted(
    leakage_case: Case,
) -> None:
    # Same case, same code path, same success condition as the first test. Only the
    # reply differs, and the verdict follows the reply — no model decides it.
    result = calibrate(leakage_case, model="stub:cooperative")

    [target_run] = result.target_runs
    assert target_run.registration.complete
    assert [attempt.verdict for attempt in target_run.attempts] == [Verdict.RESISTED]


def test_the_full_transcript_sent_and_received_is_recorded(leakage_case: Case) -> None:
    result = calibrate(leakage_case)

    [target_run] = result.target_runs
    [attempt] = target_run.attempts
    assert attempt.transcript.sent["message"] == leakage_case.payload
    assert attempt.transcript.status_code == 200
    assert target_run.registration.nonce in attempt.transcript.reply_text

    # Registration spends a call against the endpoint too, so its exchange is
    # recorded on the same terms as an attempt's.
    probe = target_run.registration.probe
    assert probe.sent["message"] and probe.status_code == 200
    assert target_run.registration.nonce in probe.reply_text

    # Each exchange carries its own session, so attempts are independent.
    assert attempt.transcript.sent["session_id"] != probe.sent["session_id"]


def test_the_run_state_records_position_successes_and_calls_spent(
    leakage_case: Case,
) -> None:
    result = calibrate(leakage_case)

    run_state = result.run_state
    assert run_state.position == Position(
        target_name="trivial", case_id=leakage_case.id, attempt_index=0
    )
    assert [a.case_id for a in run_state.succeeded_attempts] == [leakage_case.id]
    assert run_state.calls_spent == 2  # the registration probe, then one attempt
