"""What a flaky endpoint does to a measurement, at seam one.

A retry is not an attempt. If it were, an endpoint having a bad minute would read
as an agent that defended itself, and the rate the bench signs would be part
network weather. These tests hold that line from the entry point, where the rate
is produced.
"""

import pytest

from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetFailure, TargetUnreachable
from backend.bench.evaluator import Verdict
from backend.bench.library import Case
from backend.bench.rule import DECLARED_RULE
from backend.graph.budget import Layer
from backend.tests.conftest import BENCH_ATTESTATION, CONFIRMING
from backend.tests.flaky_target import IMPATIENT, ServedFlakyTarget, flaky_target


def test_transient_failures_are_retried_and_do_not_count_as_attempts(
    leakage_case: Case,
) -> None:
    failures = IMPATIENT.sends - 1
    with flaky_target(failures_before_reply=failures) as flaky:
        result = run_calibration(
            cases=[leakage_case],
            targets=[flaky.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=flaky.plant_nonce,
            approve=CONFIRMING,
        )

    [target_run] = result.target_runs
    assert target_run.registration.complete
    rate = target_run.rates[leakage_case.family]

    # The denominator is the declared sample size, not the number of round trips
    # it took to get there.
    assert rate.attempts == DECLARED_RULE.attempts_per_case
    assert rate.value == 1.0
    assert {a.verdict for a in target_run.attempts} == {Verdict.SUCCEEDED}

    # Every reply cost the same number of sends, and each is recorded, because a
    # run that had to retry its way through is evidence about the endpoint.
    assert {a.transcript.sends for a in target_run.attempts} == {failures + 1}


def test_an_endpoint_that_never_recovers_stops_the_run_rather_than_scoring_it(
    leakage_case: Case,
) -> None:
    # Refusing to return is the point. A transport failure that became a verdict
    # would be infrastructure scored as a security result, and the first thing it
    # would look like is a well-defended agent. It stops under its own name (#13).
    with flaky_target(failures_before_reply=IMPATIENT.sends + 1) as flaky:
        with pytest.raises(TargetUnreachable) as raised:
            run_calibration(
                cases=[leakage_case],
                targets=[flaky.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=flaky.plant_nonce,
                approve=CONFIRMING,
            )

    assert raised.value.failure is TargetFailure.UNAVAILABLE


def test_a_healthy_endpoint_is_sent_each_message_exactly_once(
    leakage_case: Case,
) -> None:
    with flaky_target(failures_before_reply=0) as flaky:
        result = run_calibration(
            cases=[leakage_case],
            targets=[flaky.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=flaky.plant_nonce,
            approve=CONFIRMING,
        )

    [target_run] = result.target_runs
    assert {a.transcript.sends for a in target_run.attempts} == {1}
    assert target_run.registration.probe.sends == 1

    # Calls spent counts what went out on the wire, since every send is on the
    # operator's endpoint and their inference budget. Per layer, because a run has
    # two of them and the attacker's turns are counted against a ceiling of their
    # own (ADR-0007, ADR-0010).
    assert (
        result.run_state.spent_in(Layer.SCORED) == DECLARED_RULE.attempts_per_case + 1
    )


# --- The four named outcomes, and none of them a security result -------------


def run_against(flaky: ServedFlakyTarget, case: Case) -> CalibrationResult:
    """One case against the flaky endpoint, through the entry point."""
    return run_calibration(
        cases=[case],
        targets=[flaky.target],
        attestation=BENCH_ATTESTATION,
        plant_nonce=flaky.plant_nonce,
        approve=CONFIRMING,
    )


def test_a_timeout_is_its_own_named_outcome(leakage_case: Case) -> None:
    # An endpoint that answers too slowly to be waited for. Named as a timeout
    # rather than as an agent that said nothing, which is the same silence.
    with flaky_target(
        failures_before_reply=0, sleep_seconds=1.0, timeout_seconds=0.05
    ) as flaky:
        with pytest.raises(TargetUnreachable) as raised:
            run_against(flaky, leakage_case)

    assert raised.value.failure is TargetFailure.TIMEOUT
    assert raised.value.sends == IMPATIENT.sends


def test_an_auth_failure_is_its_own_named_outcome_and_is_not_retried(
    leakage_case: Case,
) -> None:
    # A rejected token is configuration, not a bad minute: it stops on the first
    # send, and it is emphatically not a target that refused an attack.
    with flaky_target(failures_before_reply=0, auth_token="not-the-token") as flaky:
        with pytest.raises(TargetUnreachable) as raised:
            run_against(flaky, leakage_case)

    assert raised.value.failure is TargetFailure.AUTH_REJECTED
    assert raised.value.status_code == 401
    assert raised.value.sends == 1


def test_a_malformed_reply_is_named_rather_than_read_as_an_empty_one(
    leakage_case: Case,
) -> None:
    # The sharpest of the four. `Transcript.reply_text` answers "" for a body it
    # cannot read, an empty reply carries no canary, and no canary scores as
    # `resisted` — so without this outcome a broken endpoint reads as the best
    # defended target the bench has ever measured.
    with flaky_target(failures_before_reply=0, malformed=True) as flaky:
        with pytest.raises(TargetUnreachable) as raised:
            run_against(flaky, leakage_case)

    assert raised.value.failure is TargetFailure.MALFORMED_REPLY
    assert raised.value.status_code == 200


def test_a_rate_limited_endpoint_is_named_apart_from_an_unavailable_one(
    leakage_case: Case,
) -> None:
    # Both are retried and both outlive the policy here; a quota and an outage
    # send the person reading the run to two different places.
    with flaky_target(
        failures_before_reply=IMPATIENT.sends + 1, status_code=429
    ) as flaky:
        with pytest.raises(TargetUnreachable) as raised:
            run_against(flaky, leakage_case)

    assert raised.value.failure is TargetFailure.RATE_LIMITED
    assert raised.value.status_code == 429


def test_no_named_transport_outcome_is_scored_as_a_verdict() -> None:
    # The invariant behind all four: a failure and a verdict share no value, so
    # nothing downstream can read one as the other, and no `Attempt` can hold one.
    assert not {str(failure) for failure in TargetFailure} & {
        str(verdict) for verdict in Verdict
    }
    for failure in TargetFailure:
        assert failure.stated()
