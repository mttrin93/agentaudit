"""Applicability — the cases a target is never sent, and why that is not a pass.

Two seams, deliberately both. The functions are pure and are driven directly, because
what they decide is which cases a run spends attempts on and an end-to-end test could
not localise an error in that. The wiring is then driven through the calibration entry
point, because the claim spec story 16 makes is about a *run*: a payload written for a
document agent must not be "run against a voice agent and counted as a pass", and only
the entry point can show that no attempt was spent.

The distinction under test throughout is between three answers a family can give. A
rate says what was measured. *Not measurable* says the target could not answer — a
fact about the target, whose gap the operator closes by exposing its tool calls. *Not
applicable* says the bench never asked — a fact about the library, whose gap the bench
closes by writing cases for that agent type. Neither of the last two is a rate of
zero, and neither is the other.
"""

from dataclasses import replace

import pytest

from backend.bench.applicability import (
    Inapplicable,
    applicable,
    applies,
    skipped_cases,
)
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.library import Case, Family
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    CONFIRMING,
    a_target,
    served_references,
)

VOICE = "voice"
"""An agent type no case in the library was written for.

The spec's own example: a payload about supplier notes and August invoices finds no
referent in an agent that takes restaurant bookings by phone.
"""


# --- Which cases a target was written for ------------------------------------


def test_a_case_applies_to_the_agent_type_it_names(leakage_case: Case) -> None:
    assert applies(leakage_case, a_target())
    assert not applies(leakage_case, replace(a_target(), agent_type=VOICE))


def test_the_agent_type_is_the_operators_own_word_and_matched_loosely(
    leakage_case: Case,
) -> None:
    # The type is free text an operator wrote at registration, so 'Document' is not
    # a different kind of agent from 'document'. A closed set here would refuse to
    # register a target whose kind the bench had not thought of — and the honest
    # answer to an agent type with no cases is the skip below, not a refusal.
    assert applies(leakage_case, replace(a_target(), agent_type="  Document "))


def test_only_the_cases_written_for_this_target_are_run(library: list[Case]) -> None:
    assert applicable(library, a_target()) == library
    assert applicable(library, replace(a_target(), agent_type=VOICE)) == []


def test_every_skipped_case_is_named_with_the_types_it_does_apply_to(
    library: list[Case],
) -> None:
    # Every one of them, rather than a count: a run reporting "eighteen cases
    # skipped" would leave a reader unable to tell which family lost coverage.
    skipped = skipped_cases(library, replace(a_target(), agent_type=VOICE))

    assert [entry.case_id for entry in skipped] == [case.id for case in library]
    assert {entry.reason for entry in skipped} == {
        Inapplicable.AGENT_TYPE_OUTSIDE_APPLIES_TO
    }
    for entry, case in zip(skipped, library, strict=True):
        assert entry.family is case.family
        assert entry.agent_type == VOICE
        assert entry.applies_to == case.applies_to
        assert VOICE in entry.stated() and "not run" in entry.stated()


def test_a_target_the_library_was_written_for_skips_nothing(
    library: list[Case],
) -> None:
    assert skipped_cases(library, a_target()) == ()


# --- Through the entry point: no attempt spent, and no rate claimed -----------


def test_no_attempt_is_spent_on_a_case_the_target_is_outside(
    library: list[Case],
) -> None:
    # The whole of spec story 16. Against a voice agent the document library runs
    # nothing at all: no attempt, no verdict, and no rate for any family.
    with served_references(model="stub:cooperative") as references:
        served = references.served[0]
        result = run_calibration(
            cases=library,
            targets=[replace(served.target, agent_type=VOICE)],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )

    [target_run] = result.target_runs
    assert target_run.registration.complete, (
        "the target registered and was still not run"
    )
    assert target_run.attempts == ()
    assert target_run.rates == {}
    assert {entry.case_id for entry in target_run.not_applicable} == {
        case.id for case in library
    }


def test_a_skipped_family_is_not_reported_not_measurable(library: list[Case]) -> None:
    # The two answers are separate and this is where they could be confused. Read
    # over the whole library, every family of a voice agent would report *not
    # measurable* for the two that need a tool trace — sending its operator to look
    # for a capability their target is not missing. Read over the cases written for
    # it, there are none, and the only thing said is that the bench never asked.
    with served_references(model="stub:cooperative") as references:
        served = references.served[0]
        result = run_calibration(
            cases=library,
            targets=[
                replace(served.target, agent_type=VOICE, exposes_tool_calls=False)
            ],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )

    [target_run] = result.target_runs
    assert target_run.not_measurable == {}
    assert target_run.not_applicable != ()


def test_a_run_may_not_report_a_case_as_skipped_and_run_it_anyway(
    library: list[Case],
) -> None:
    # The invariant behind the field: a skip that spent an attempt is a verdict
    # counted for a payload the case never claimed would land. Held by the record
    # rather than by the caller's care, so a future entry point that filtered in the
    # wrong order cannot report a pass for a case it also called inapplicable.
    with served_references(model="stub:cooperative") as references:
        served = references.served[0]
        result = run_calibration(
            cases=library,
            targets=[served.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )

    [target_run] = result.target_runs
    assert target_run.attempts, "nothing ran, so the refusal below would be vacuous"
    everything_skipped = skipped_cases(library, replace(a_target(), agent_type=VOICE))

    with pytest.raises(ValueError, match="were also run against it"):
        TargetRun(
            target=target_run.target,
            registration=target_run.registration,
            attempts=target_run.attempts,
            rule=target_run.rule,
            not_applicable=everything_skipped,
        )


def test_a_family_with_one_inapplicable_case_still_reports_a_rate(
    library: list[Case],
) -> None:
    # Why the skip is recorded per case and not per family. A family can have two
    # cases that apply and one that does not, and the rate over the two that ran is
    # a real number — a family-level skip would have to overwrite it.
    injection = [case for case in library if case.family is Family.DATA_LEAKAGE]
    narrowed = replace(injection[0], applies_to=(VOICE,))

    with served_references(model="stub:obedient") as references:
        served = references.served[0]
        result = run_calibration(
            cases=[narrowed, *injection[1:]],
            targets=[served.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )

    [target_run] = result.target_runs
    assert [entry.case_id for entry in target_run.not_applicable] == [narrowed.id]
    rate = target_run.rates[Family.DATA_LEAKAGE]
    assert rate.attempts == len(injection[1:]) * target_run.rule.attempts_per_case
