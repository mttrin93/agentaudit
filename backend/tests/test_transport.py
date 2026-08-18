"""What a flaky endpoint does to a measurement, at seam one.

A retry is not an attempt. If it were, an endpoint having a bad minute would read
as an agent that defended itself, and the rate the bench signs would be part
network weather. These tests hold that line from the entry point, where the rate
is produced.
"""

import httpx
import pytest

from backend.bench.calibration import run_calibration
from backend.bench.evaluator import Verdict
from backend.bench.library import Case
from backend.bench.rule import DECLARED_RULE
from backend.graph.budget import Layer
from backend.tests.conftest import BENCH_ATTESTATION, CONFIRMING
from backend.tests.flaky_target import IMPATIENT, flaky_target


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
    # would look like is a well-defended agent.
    with flaky_target(failures_before_reply=IMPATIENT.sends + 1) as flaky:
        with pytest.raises(httpx.HTTPStatusError):
            run_calibration(
                cases=[leakage_case],
                targets=[flaky.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=flaky.plant_nonce,
                approve=CONFIRMING,
            )


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
