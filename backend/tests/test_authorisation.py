"""The guard in front of the run: what is attested, what is asked, what is refused.

These are the spec's authorisation-and-safety stories. The bench takes a URL and a
bearer token and fires jailbreak payloads at whatever answers, so the tests that
hold this shut are not a formality — deployed without them the tool is an open
attack proxy (ADR-0007).

Two of them assert an *absence*: nothing sent, nothing spent. That is the whole
behaviour of a halt, and the only way it can be checked is by looking at what did
not happen.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.bench.calibration import run_calibration
from backend.bench.library import Case
from backend.bench.registration import Attestation, endpoint_hash
from backend.graph.approval import (
    Approval,
    ApprovalRun,
    read_answer,
    run_under_approval,
)
from backend.graph.budget import BudgetPayload, Layer, RunBudget
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    a_budget,
    calibrate,
    reference_target,
    unlisted_case,
)

STATEMENT_FIELDS = (
    "authorised_to_test",
    "not_production",
    "accepts_provider_policy_and_cost",
)
"""The three fields of `Attestation`, named here so each can be withheld in turn."""


def declining(reason: str = "not today") -> Approval:
    return Approval(confirmed=False, identity="operator", reason=reason)


# --- the three statements -------------------------------------------------------


@pytest.mark.parametrize("withheld", STATEMENT_FIELDS)
def test_an_attestation_missing_any_one_statement_cannot_be_constructed(
    withheld: str,
) -> None:
    """Each of the three, refused on its own.

    Parametrised rather than written once, because the interesting failure is a
    consequence a user was never told about, and the second and third are exactly
    the two nobody would infer: that these payloads generate provider policy
    violations against their own account, and that they spend their own inference
    budget.
    """
    statements = dict.fromkeys(STATEMENT_FIELDS, True) | {withheld: False}
    wording = dict(Attestation.STATEMENTS)[withheld]

    with pytest.raises(ValueError) as refusal:
        Attestation(identity="operator", **statements)

    # The refusal names the statement that was not made, because "incomplete" on
    # its own tells an operator nothing about which consequence they declined.
    assert "incomplete" in str(refusal.value)
    assert wording in str(refusal.value)


def test_an_attestation_has_to_record_who_made_it() -> None:
    with pytest.raises(ValueError):
        Attestation(
            identity="   ",
            authorised_to_test=True,
            not_production=True,
            accepts_provider_policy_and_cost=True,
        )


def test_the_wording_shown_to_an_operator_covers_every_statement_recorded() -> None:
    # The prompt and the record are one thing. A statement in the record with no
    # wording beside it is a consequence the bench claims was disclosed and was not.
    assert {field for field, _ in Attestation.STATEMENTS} == set(STATEMENT_FIELDS)


def test_the_attestation_is_recorded_with_timestamp_identity_and_endpoint_hash(
    leakage_case: Case,
) -> None:
    before = datetime.now(tz=UTC)
    result = calibrate(leakage_case)
    [target_run] = result.target_runs

    record = target_run.registration.attestation
    assert record.attestation == BENCH_ATTESTATION
    assert record.attestation.identity == BENCH_ATTESTATION.identity
    assert before <= record.recorded_at <= datetime.now(tz=UTC)
    assert record.recorded_at.tzinfo is not None
    assert record.endpoint_hash == endpoint_hash(target_run.target.url)


def test_the_endpoint_is_recorded_as_a_hash_and_not_as_an_endpoint() -> None:
    url = "https://staging.example.invalid/agent/messages"

    hashed = endpoint_hash(url)

    # The record outlives the run and is destined for a document that travels, so
    # the live URL that answers jailbreak payloads must not be in it (ADR-0008).
    assert url not in hashed
    assert hashed == hashlib.sha256(url.encode("utf-8")).hexdigest()
    assert hashed == endpoint_hash(url)


# --- the halt -------------------------------------------------------------------


def test_a_run_with_nobody_to_ask_halts_and_spends_nothing(
    leakage_case: Case,
) -> None:
    with reference_target(name="trivial") as reference:
        result = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
        )

    assert result.approval.halted
    assert not result.approval.confirmed
    assert not result.approval.proceeded
    # No registration probe either: the echo probe is a call on the operator's
    # endpoint, so it is inside the halt rather than ahead of it.
    assert result.target_runs == ()
    assert result.run_state.calls_spent == 0
    assert result.run_state.attempts == []


def test_a_declined_run_spends_nothing_and_says_it_was_declined(
    leakage_case: Case,
) -> None:
    with reference_target(name="trivial") as reference:
        result = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=lambda presented: declining("the estimate was too high"),
        )

    assert not result.approval.confirmed
    # Declined is not halted: somebody was asked and said no, which is a different
    # fact about the run and the one piece of evidence that the display works.
    assert not result.approval.halted
    assert result.approval.reason == "the estimate was too high"
    assert result.target_runs == ()
    assert result.run_state.calls_spent == 0


def test_a_confirmed_run_records_who_confirmed_it(leakage_case: Case) -> None:
    result = calibrate(leakage_case)

    assert result.approval.proceeded
    assert result.approval.identity == BENCH_ATTESTATION.identity
    assert result.run_state.spent_in(Layer.SCORED) > 0


def test_the_suite_has_not_run_at_the_moment_the_human_is_asked() -> None:
    """The halt, from inside it.

    The approver is called while the graph is paused, so anything the suite would
    do has not been done yet. This is the assertion the entry-point tests can only
    make afterwards, and it is the one that would catch a "halt" implemented as a
    check performed after the spending.
    """
    ran: list[str] = []
    asked: list[bool] = []

    def approve(presented: BudgetPayload) -> Approval:
        asked.append(bool(ran))
        return Approval(confirmed=True, identity="operator")

    outcome = run_under_approval(a_budget(), lambda: ran.append("suite"), approve)

    assert asked == [False]
    assert ran == ["suite"]
    assert outcome.proceeded


def test_the_graph_stays_paused_until_it_is_resumed() -> None:
    ran: list[str] = []

    with ApprovalRun(a_budget(), lambda: ran.append("suite")) as run:
        presented = run.present()

        assert run.paused
        assert ran == []
        assert presented["scored"]["calls"] > 0

        run.resume(Approval(confirmed=True, identity="operator"))

        assert not run.paused
        assert ran == ["suite"]


def test_the_interrupt_presents_two_figures_and_the_ceilings() -> None:
    budget = a_budget()

    with ApprovalRun(budget, lambda: None) as run:
        presented = run.present()

    # The fact and the bound arrive labelled, so a consumer cannot lose which is
    # which on the way to a screen.
    assert presented["scored"]["kind"] == "exact"
    assert presented["adaptive"]["kind"] == "ceiling"
    assert presented["total"]["kind"] == "ceiling"
    assert presented["total"]["calls"] == (
        presented["scored"]["calls"] + presented["adaptive"]["calls"]
    )
    assert presented["scored_ceiling"] == budget.scored_ceiling
    assert presented["adaptive_ceiling"] == budget.adaptive_ceiling
    # And the figure that is actually enforced, larger than the total and also a
    # bound: nothing shown with a `≤` may be exceeded.
    assert presented["hard_ceiling"]["kind"] == "ceiling"
    assert presented["hard_ceiling"]["calls"] >= presented["total"]["calls"]
    assert presented["scored"]["cost"] == "not priced"
    assert any("Adaptive layer" in line for line in presented["presented"])


@pytest.mark.parametrize(
    "answer", [None, "yes", {"confirmed": "yes"}, {}, {"confirmed": 1}]
)
def test_an_answer_that_is_not_an_explicit_confirmation_is_not_one(
    answer: object,
) -> None:
    """Anything but a `True` is a no.

    The resume value crosses a checkpoint today and arrives from an HTTP request at
    6b, so the failure to guard against is a truthy-looking value spending a user's
    budget.
    """
    assert not read_answer(answer)["confirmed"]


# --- the bench is not itself a vector -------------------------------------------


def test_a_payload_is_transported_verbatim_and_never_executed_locally(
    tmp_path: Path,
) -> None:
    """Payloads are sent, never interpreted.

    The payload below would leave a trace on this machine if anything in the bench
    formatted, evaluated or shelled it out, and it reaches the target unchanged if
    nothing does. Both halves matter: a bench that mangled the payload would be
    measuring a case it had rewritten, and one that executed it would be the
    vector it exists to find.
    """
    marker = tmp_path / "executed-locally"
    payload = (
        f"__import__('pathlib').Path('{marker}').write_text('run'); "
        f"$(touch {marker}); {{nonce}} {{}} 100% done"
    )
    case = unlisted_case(payload=payload, case_id="unlisted-not-a-vector-001")

    result = calibrate(case)
    [target_run] = result.target_runs

    assert not marker.exists()
    assert {a.transcript.sent["message"] for a in target_run.attempts} == {payload}


def test_the_declared_budget_travels_with_the_result(leakage_case: Case) -> None:
    # A run's cost and its consent are part of its record. A ceiling that has
    # become separated from the run it governed is one nobody can check.
    result = calibrate(leakage_case)

    assert isinstance(result.budget, RunBudget)
    assert result.approval.budget is result.budget
    assert result.run_state.budget is result.budget


def test_a_run_with_no_terminal_to_ask_is_a_no() -> None:
    """The command line refuses rather than defaults.

    A run nobody is watching has nobody to consent on its behalf, so an absent or
    piped stdin is a no. There is deliberately no `--yes`: a consent mechanism with
    a flag to skip it is the convenience feature ADR-0007 says this must not become.
    """
    from scripts.calibrate import main
    from scripts.console import EXIT_WITHHELD

    # Under pytest stdin is not a terminal, which is the condition being tested.
    assert main(["--identity", "nobody at a terminal", "--model", "stub:obedient"]) == (
        EXIT_WITHHELD
    )
