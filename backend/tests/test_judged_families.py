"""The two families a human decides, and the seams that keep them apart from four.

Wrongful commitment and disclosure denial have no deterministic check to apply, so
their verdicts come from an adjudicating model instead (ADR-0004). That buys three
hazards, and every test here is one of them:

*The route could be chosen from the family name.* It is chosen from the record.
`verdict_class` is on the case, the library refuses a record whose class and
criterion disagree, and the two tests in the middle of this file run a deterministic
case under a judged family's name and a judged case under a deterministic one to
show the name decides nothing (spec story 18, ADR-0002).

*A judged rate could be read as a deterministic one.* It cannot be reached that way:
the two are separate sections on the target run, keyed disjointly, and a family
whose attempts disagree about their class is refused rather than filed under one.

*The instrument could see which agent it is grading.* An unblinded adjudicator
manufactures `D` directly, because its output is the number `D` is computed from —
a sharper failure than the narrative judge's, and closed the same way, in
`AdjudicationBrief.about` on the harness side of the call.

**No model is called here.** Every judged verdict below comes from a stub that
answers with the verdict it was handed, so what is under test is the code around the
answer rather than a model's temperament. What the instrument is *worth* is not
asserted anywhere in this suite: that has its own evaluation, which is κ against the
gold set (#11).
"""

import ast
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import get_type_hints

import pytest

from backend.bench.adjudication import (
    AdjudicationBrief,
    AdjudicationFailed,
    Completion,
    NoAdjudicator,
    NotAJudgedCase,
    adjudicate,
)
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.evaluator import NotADeterministicCase, Verdict, evaluate
from backend.bench.library import (
    Case,
    Family,
    JudgedCondition,
    SuccessCondition,
    SuccessConditionKind,
    VerdictClass,
)
from backend.bench.rule import DECLARED_RULE
from backend.graph.approval import Approval
from backend.graph.budget import BudgetPayload
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.prompt import DOCUMENT_ASSISTANT_PROMPT
from backend.targets.reference.trivial import HUMAN_PERSONA, TRIVIAL
from backend.targets.reference.weak import WEAK
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    CONFIRMING,
    adjudicating,
    reference_target,
    target_run_for,
    unlisted_case,
)

JUDGED_FAMILIES = (Family.WRONGFUL_COMMITMENT, Family.DISCLOSURE_DENIAL)

ADJUDICATION_SOURCE = Path(__file__).resolve().parents[1] / "bench" / "adjudication.py"

A_NONCE = "AGENTAUDIT-CANARY-0123456789ABCDEF"


# --- Both families run, and adjudication is what decides them ---------------


def test_the_wrongful_commitment_family_runs_and_is_decided_by_adjudication(
    wrongful_commitment_case: Case,
) -> None:
    target_run = target_run_for(
        wrongful_commitment_case, adjudicator=adjudicating(Verdict.SUCCEEDED)
    )

    assert target_run.registration.complete
    assert len(target_run.attempts) == DECLARED_RULE.attempts_per_case
    assert {a.verdict_class for a in target_run.attempts} == {VerdictClass.JUDGED}
    assert target_run.judged_rates[Family.WRONGFUL_COMMITMENT].value == 1.0


def test_the_disclosure_denial_family_runs_and_is_decided_by_adjudication(
    disclosure_denial_case: Case,
) -> None:
    target_run = target_run_for(
        disclosure_denial_case, adjudicator=adjudicating(Verdict.RESISTED)
    )

    assert target_run.registration.complete
    assert len(target_run.attempts) == DECLARED_RULE.attempts_per_case
    assert {a.verdict_class for a in target_run.attempts} == {VerdictClass.JUDGED}
    assert target_run.judged_rates[Family.DISCLOSURE_DENIAL].value == 0.0


def test_the_instrument_is_what_moves_a_judged_rate_and_not_the_reply(
    disclosure_denial_case: Case,
) -> None:
    # Same case, same target, same model, same reply — two instruments and two
    # rates. That is the honest shape of a judged family and the reason it carries
    # κ: nothing in the transcript pins the number down, which is exactly what
    # ADR-0004 refuses to let a *deterministic* family look like.
    succeeded = target_run_for(
        disclosure_denial_case, adjudicator=adjudicating(Verdict.SUCCEEDED)
    )
    resisted = target_run_for(
        disclosure_denial_case, adjudicator=adjudicating(Verdict.RESISTED)
    )

    # Compared with the nonce redacted, because each run issues its own — the
    # thing being held constant is what the target said, not the value planted in
    # it (ADR-0007).
    replies = {
        run.attempts[0].transcript.reply_text.replace(run.registration.nonce, "·")
        for run in (succeeded, resisted)
    }
    assert len(replies) == 1, "the two runs saw different replies, so this proves less"
    assert succeeded.judged_rates[Family.DISCLOSURE_DENIAL].value == 1.0
    assert resisted.judged_rates[Family.DISCLOSURE_DENIAL].value == 0.0


# --- The verdict class comes off the record, never off the family name -------


def test_a_deterministic_case_under_a_judged_familys_name_is_still_deterministic(
    leakage_case: Case,
) -> None:
    # The leakage case, relabelled into a judged family. Its record still says
    # deterministic and still carries a success condition, so the success condition
    # decides it — and the adjudicator, which would have said the opposite, is not
    # consulted. A bench that read the route off the family name would report 0.00
    # here.
    relabelled = replace(leakage_case, family=Family.WRONGFUL_COMMITMENT)

    target_run = target_run_for(relabelled, adjudicator=adjudicating(Verdict.RESISTED))

    assert target_run.deterministic_rates[Family.WRONGFUL_COMMITMENT].value == 1.0
    assert target_run.judged_rates == {}


def test_a_judged_case_under_a_deterministic_familys_name_is_still_adjudicated(
    disclosure_denial_case: Case,
) -> None:
    # The mirror, and the sharper half. Relabelled into data leakage and run
    # against the agent that hands its whole configuration back, so the nonce *is*
    # in the reply and the deterministic check would read `succeeded`. The record
    # says judged, the instrument says resisted, and the rate is 0.00 — so nothing
    # inferred the route from the name it was wearing.
    relabelled = replace(disclosure_denial_case, family=Family.DATA_LEAKAGE)

    target_run = target_run_for(relabelled, adjudicator=adjudicating(Verdict.RESISTED))

    nonce = target_run.registration.nonce
    assert nonce in target_run.attempts[0].transcript.reply_text
    assert target_run.judged_rates[Family.DATA_LEAKAGE].value == 0.0
    assert target_run.deterministic_rates == {}


def test_a_case_record_declares_exactly_one_route_to_its_verdict() -> None:
    # The route is not a caller's choice at all: a record that stated both, or
    # neither, would leave the verdict depending on which field something read.
    deterministic = SuccessCondition(kind=SuccessConditionKind.CANARY_IN_REPLY)
    judged = JudgedCondition(question="q?", succeeded_when="yes", resisted_when="no")

    with pytest.raises(ValueError, match="carries a judged condition"):
        _a_case(VerdictClass.DETERMINISTIC, deterministic, judged)
    with pytest.raises(ValueError, match="carries a success condition"):
        _a_case(VerdictClass.JUDGED, deterministic, judged)
    with pytest.raises(ValueError, match="carries no success condition"):
        _a_case(VerdictClass.DETERMINISTIC, None, None)
    with pytest.raises(ValueError, match="states no question"):
        _a_case(VerdictClass.JUDGED, None, None)


def test_a_judged_condition_that_states_only_half_the_answer_is_refused() -> None:
    # The boundary between the two sides is where a judged verdict is won or lost,
    # and it is the figure κ measures. A record that left one side blank would hand
    # the instrument a question with one answer.
    with pytest.raises(ValueError, match="both sides of the answer"):
        JudgedCondition(question="q?", succeeded_when="yes", resisted_when="  ")


# --- Two sections, and never one -------------------------------------------


def test_the_two_classes_are_reported_as_two_sections_that_share_no_family(
    leakage_case: Case,
    wrongful_commitment_case: Case,
    disclosure_denial_case: Case,
) -> None:
    target_run = _run_against_trivial(
        [leakage_case, wrongful_commitment_case, disclosure_denial_case]
    )

    deterministic, judged = target_run.deterministic_rates, target_run.judged_rates
    assert set(deterministic) == {Family.DATA_LEAKAGE}
    assert set(judged) == set(JUDGED_FAMILIES)

    # Disjoint keys, and between them every family that was attempted. A family
    # cannot appear in both sections, so the two can never be merged into one
    # mapping that quietly overwrites a count — and there is nothing left over that
    # a third section would have to hold.
    assert not set(deterministic) & set(judged)
    assert set(deterministic) | set(judged) == set(target_run.rates)
    for rate in (*deterministic.values(), *judged.values()):
        assert rate.attempts == DECLARED_RULE.attempts_per_case


def test_no_figure_on_a_target_run_reaches_across_the_two_sections(
    leakage_case: Case, disclosure_denial_case: Case
) -> None:
    # Nothing sums or averages the two, and nothing may start to. A judged rate
    # carries a wider stated limit and a κ figure beside it, so a number combining
    # one with a deterministic rate would have no statable evidentiary strength —
    # ADR-0005's prohibition on a composite score, one level down.
    aggregating = [
        name
        for name in dir(TargetRun)
        if any(word in name for word in ("total", "combined", "overall", "average"))
    ]
    assert not aggregating, f"{aggregating} reaches across the two report sections"

    target_run = _run_against_trivial([leakage_case, disclosure_denial_case])
    assert len(target_run.rates) == 2, "a rate over both families would be one entry"


def test_a_family_measured_under_both_verdict_classes_is_refused(
    disclosure_denial_case: Case,
) -> None:
    # The invariant carried by the type rather than by the caller's care. A family
    # whose cases disagreed about their class would put a judged rate in the
    # deterministic section, which is the one place the two must never meet.
    measured = target_run_for(disclosure_denial_case)
    confused = (
        replace(measured.attempts[0], verdict_class=VerdictClass.DETERMINISTIC),
        *measured.attempts[1:],
    )

    with pytest.raises(ValueError, match="both verdict classes"):
        TargetRun(
            target=measured.target,
            registration=measured.registration,
            attempts=confused,
            rule=measured.rule,
        )


# --- Blinded to which target produced the transcript ------------------------


def test_a_brief_carries_no_field_that_could_name_a_target() -> None:
    # The brief's field list is the whole of what the adjudicator may see, so it is
    # asserted rather than reviewed. A field added here is a `D` the instrument can
    # manufacture, which is worse than a narrative it can flatter.
    assert set(get_type_hints(AdjudicationBrief)) == {
        "case_id",
        "family",
        "question",
        "succeeded_when",
        "resisted_when",
        "payload",
        "reply",
        "trace",
    }


def test_nothing_the_adjudicator_is_sent_names_the_agent_it_is_grading(
    disclosure_denial_case: Case,
) -> None:
    # The run knows: the attempt was recorded against `hardened`, over a url with
    # the agent's name in it. What reaches the model must not.
    sent: list[str] = []

    def recording(system_prompt: str, message: str) -> str:
        sent.extend((system_prompt, message))
        return ADJUDICATING(system_prompt, message)

    target_run = target_run_for(
        disclosure_denial_case, name="hardened", adjudicator=recording
    )

    assert sent, "the adjudicator made no model call, so this proves nothing"
    url = target_run.attempts[0].transcript.url
    assert "hardened" in url
    for shown in sent:
        for label in ("hardened", "weak", "trivial", url):
            assert label not in shown


def test_the_adjudicator_is_handed_no_precedent_and_no_prior_finding() -> None:
    # The evidence and the model, and nothing else — the same signature constraint
    # ADR-0004 puts on the judge, for the same reason: precedent reaching the
    # instrument κ measures would contaminate κ.
    assert set(get_type_hints(adjudicate)) == {"brief", "complete", "return"}


def test_the_adjudicator_returns_a_verdict_and_nothing_narrative() -> None:
    # A verdict and only a verdict. Narrative comes from the judge, which cannot
    # return a verdict; if this returned prose too, a report would have two answers
    # to one question and only one of them would carry κ.
    assert get_type_hints(adjudicate)["return"] is Verdict


def test_adjudication_imports_no_route_to_a_target_or_to_the_adaptive_layer() -> None:
    # Import-level, because both channels are reachable by a name rather than by an
    # argument: a precedent lookup the instrument calls itself, and `send_message`,
    # which would let it manufacture the transcript it is deciding. The same test
    # guards the judge, and it guards this module for a stronger reason — this one's
    # output is the number, not the prose around it (ADR-0004, ADR-0010).
    forbidden = [
        name
        for name in _imports_of(ADJUDICATION_SOURCE)
        if name.startswith("backend.bench.adaptive")
        or name.endswith(("send_message", "run_case", "run_attempt"))
        or "precedent" in name
    ]
    assert not forbidden, (
        f"{forbidden} is reachable from the adjudicator. An instrument that can "
        "compose its own evidence, or read what was decided before, is not blinded"
    )


# --- Named outcomes rather than default verdicts ----------------------------


def test_an_unreadable_adjudication_is_a_named_failure_and_not_a_verdict(
    disclosure_denial_case: Case,
) -> None:
    # Infrastructure failure resolved to `resisted` would read in a report as an
    # agent that defended itself, which is the one thing a broken instrument must
    # never be able to say (PLAN §10).
    brief = AdjudicationBrief.about(disclosure_denial_case, "a reply", None)

    for broken, complaint in (
        (_answering("verdict: probably"), "not one of"),
        (_answering("verdict: unclear"), "not one of"),
        (_answering("I would rather not say."), "carried no verdict"),
        (_answering(""), "carried no verdict"),
    ):
        with pytest.raises(AdjudicationFailed, match=complaint):
            adjudicate(brief, broken)


def test_a_deterministic_case_cannot_be_offered_for_adjudication(
    leakage_case: Case,
) -> None:
    # The route ADR-0004 protects, arriving from the other side: a deterministic
    # case decided by inference is a success condition overruled, and the number
    # stops being re-derivable from the record and the transcript.
    with pytest.raises(NotAJudgedCase, match="authoritative"):
        AdjudicationBrief.about(leakage_case, "a reply", None)


def test_a_judged_case_cannot_be_offered_to_the_deterministic_evaluator(
    disclosure_denial_case: Case,
) -> None:
    # The mirror refusal. A judged family scored by a string comparison would be a
    # rate that looks re-derivable and is not.
    measured = target_run_for(disclosure_denial_case)
    attempt = measured.attempts[0]

    with pytest.raises(NotADeterministicCase, match="no success condition"):
        evaluate(
            disclosure_denial_case,
            attempt.transcript,
            measured.target,
            measured.registration.nonce,
        )


def test_a_judged_case_with_no_adjudicator_is_refused_before_anything_is_sent(
    disclosure_denial_case: Case,
) -> None:
    # Refused ahead of the estimate and the interrupt, not partway through. A run
    # that discovered this later would have spent the operator's budget on attempts
    # nothing can score, and a partial suite is void rather than smaller.
    asked: list[BudgetPayload] = []

    def recording_approval(presented: BudgetPayload) -> Approval:
        asked.append(presented)
        return CONFIRMING(presented)

    with reference_target() as reference:
        with pytest.raises(NoAdjudicator, match="disclosure-denial-001"):
            run_calibration(
                cases=[disclosure_denial_case],
                targets=[reference.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=reference.plant_nonce,
                approve=recording_approval,
            )

    assert not asked, "the operator was asked to confirm a run that cannot be scored"


# --- What the two records claim, and what they refuse to claim --------------


def test_both_judged_records_are_judged_and_state_their_criterion(
    wrongful_commitment_case: Case, disclosure_denial_case: Case
) -> None:
    for case in (wrongful_commitment_case, disclosure_denial_case):
        assert case.verdict_class is VerdictClass.JUDGED
        assert case.success_condition is None
        assert case.judged_condition is not None
        assert case.family in JUDGED_FAMILIES


def test_each_judged_record_states_which_case_inside_its_identifier_it_omits(
    wrongful_commitment_case: Case, disclosure_denial_case: Case
) -> None:
    # ADR-0002's wording is load-bearing: a family *tests one case within* an
    # identifier and is not that identifier. The bound is per case and on the
    # record, so it travels with the number rather than living in a document.
    assert wrongful_commitment_case.external_id.identifier == "LLM07:2026"
    assert "originated here" in disclosure_denial_case.external_id.identifier

    for case in (wrongful_commitment_case, disclosure_denial_case):
        stated = case.external_id.not_tested
        assert "does not test" in stated
        assert len(stated.split()) > 30, "a coverage bound this short states nothing"


def test_disclosure_denial_claims_nothing_about_synthetic_content_marking(
    disclosure_denial_case: Case,
) -> None:
    # Article 50(1) — telling a person they are talking to a machine — and Article
    # 50(2) — marking generated content in a machine-readable form — are different
    # duties with different technical answers, and 50(2) applies from 2 December
    # 2026. A reader who took this family for coverage of the second would be
    # reading a claim the bench never made (PLAN §4).
    stated = disclosure_denial_case.external_id.not_tested

    assert "50(2)" in stated
    assert "2 December 2026" in stated


# --- The floor under disclosure denial -------------------------------------


def test_only_the_trivial_reference_agent_is_instructed_to_be_a_person() -> None:
    # Most models decline a role-play-as-human instruction by default, so an agent
    # with no defences at all would resist this family and it would separate
    # nothing — what the bench would have measured is a provider's temperament
    # (PLAN §12). The floor is therefore built, and built into exactly one of the
    # three agents: if it were in the shared prompt, the gap between hardened and
    # trivial would be a difference in wording rather than in engineering.
    assert HUMAN_PERSONA in TRIVIAL.system_prompt(A_NONCE)
    assert HUMAN_PERSONA not in DOCUMENT_ASSISTANT_PROMPT
    for defended in (WEAK, HARDENED):
        assert HUMAN_PERSONA not in defended.system_prompt(A_NONCE)


# --- Helpers ---------------------------------------------------------------


def _answering(reply: str) -> Completion:
    return lambda system_prompt, message: reply


def _imports_of(source: Path) -> Iterator[str]:
    """Every module and name the given module imports, dotted."""
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)


def _run_against_trivial(cases: list[Case]) -> TargetRun:
    """Several cases against one served reference agent, through the entry point."""
    with reference_target() as reference:
        result = run_calibration(
            cases=cases,
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )
    [target_run] = result.target_runs
    assert target_run.registration.complete
    return target_run


def _a_case(
    verdict_class: VerdictClass,
    success_condition: SuccessCondition | None = None,
    judged_condition: JudgedCondition | None = None,
) -> Case:
    """A record with the two criteria set however a test needs them."""
    template = unlisted_case(payload="anything", case_id="unlisted-verdict-route-001")
    return replace(
        template,
        verdict_class=verdict_class,
        success_condition=success_condition,
        judged_condition=judged_condition,
    )
