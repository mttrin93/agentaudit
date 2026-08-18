"""The gold set, the DeepEval run over it, and the refusal κ triggers.

Three hazards, and every test here is one of them.

*The set could measure something other than what it claims.* Thirty transcripts,
fifteen per judged family, labelled with a `Verdict` and nothing wider — and a set
that is the wrong size, labelled one way, pointed at a deterministic case or silent
about what it excluded does not load at all.

*The blinding could be lost in the harness.* A golden's `input` is a field a human
fills, so it is the obvious place for a target's name to re-enter and manufacture
`D` (ADR-0009's amendment). The goldens are built by the same `AdjudicationBrief`
the run builds, and the tests below read every one of them for a label.

*The refusal could become a judgement call.* κ below the declared floor marks a
judged family unfit to report automatically, in a property no caller can set, and
a judged family with no κ at all is refused on the same terms.

**No model is called here.** Every verdict comes from a stub keyed on the reply in
the brief, so what is under test is the harness and the arithmetic rather than a
model's temperament. What the instrument is *worth* is the reading this evaluation
produces against a real model, and it is recorded in `docs/validation.md` rather
than asserted in a test — and the judge's prose is not asserted on here or anywhere
else in the suite, which is the whole reason this evaluation exists (spec:
"Deliberately not unit-tested: the judge's narrative quality").
"""

import os
from dataclasses import replace
from pathlib import Path

import pytest
from deepeval.test_case import LLMTestCase

from backend.bench.adjudication import Completion
from backend.bench.assembler import MeasuredSection, assemble
from backend.bench.evaluator import Verdict
from backend.bench.goldset import (
    AGREEMENT_METRIC,
    AGREEMENT_THRESHOLD,
    GoldSet,
    GoldSetUnusable,
    GoldTranscript,
    ReliabilityUnreadable,
    VerdictAgreesWithGoldLabel,
    load_gold_sets,
    measure_reliability,
    reliability_from,
    run_gold_set,
)
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import UNFIT_TO_REPORT, Reliability
from backend.tests.conftest import ADJUDICATING, target_run_for

GOLDSET_DIR = Path(__file__).resolve().parents[1] / "goldset"

JUDGED_FAMILIES = (Family.WRONGFUL_COMMITMENT, Family.DISCLOSURE_DENIAL)

TWO_DISAGREEMENTS = ("dd-01", "dd-02")
"""One transcript from each side of the label. Leaves κ above the declared floor."""

FOUR_DISAGREEMENTS = ("dd-01", "dd-03", "dd-02", "dd-04")
"""Two from each side. Leaves κ below the declared floor, on fifteen transcripts."""


@pytest.fixture
def gold_sets(library: list[Case]) -> dict[Family, GoldSet]:
    return {gold.family: gold for gold in load_gold_sets(GOLDSET_DIR, library)}


@pytest.fixture
def denial_set(gold_sets: dict[Family, GoldSet]) -> GoldSet:
    return gold_sets[Family.DISCLOSURE_DENIAL]


# --- The set itself ---------------------------------------------------------


def test_thirty_transcripts_are_labelled_fifteen_per_judged_family(
    gold_sets: dict[Family, GoldSet],
) -> None:
    # Per family and never pooled: each judged family carries its own reliability
    # figure, so a family the instrument reads well cannot vouch for one it reads
    # badly (spec story 34).
    assert set(gold_sets) == set(JUDGED_FAMILIES)

    for family in JUDGED_FAMILIES:
        gold = gold_sets[family]
        assert len(gold.transcripts) == DECLARED_RULE.gold_transcripts_per_family
        assert gold.case.verdict_class is VerdictClass.JUDGED
        assert gold.case.family is family

    labelled = sum(len(gold.transcripts) for gold in gold_sets.values())
    assert labelled == 2 * DECLARED_RULE.gold_transcripts_per_family == 30


def test_every_gold_label_is_a_verdict_and_both_sides_are_represented(
    gold_sets: dict[Family, GoldSet],
) -> None:
    # Binary, because the verdict is (ADR-0013), and two-sided because κ is
    # undefined when a rater used one category. The second half is what makes the
    # figure computable at all rather than a division by zero.
    for gold in gold_sets.values():
        labels = {transcript.label for transcript in gold.transcripts}
        assert labels == set(Verdict)


def test_each_label_is_recorded_with_the_reason_it_was_given(
    gold_sets: dict[Family, GoldSet],
) -> None:
    # A reference label a reader cannot argue with is one they have to take on
    # trust, and the whole claim of the gold set is that it was labelled before
    # anyone had an interest in a particular number (spec story 35).
    for gold in gold_sets.values():
        assert gold.labelled_by.strip()
        assert gold.excluded.strip()
        for transcript in gold.transcripts:
            assert len(transcript.labelled_because.split()) > 5


def test_a_gold_set_labelled_only_one_way_is_refused(denial_set: GoldSet) -> None:
    one_sided = tuple(
        replace(transcript, label=Verdict.SUCCEEDED)
        for transcript in denial_set.transcripts
    )

    with pytest.raises(GoldSetUnusable, match="measures nothing"):
        replace(denial_set, transcripts=one_sided)


def test_a_gold_set_of_the_wrong_size_is_refused(denial_set: GoldSet) -> None:
    # κ over some other number of transcripts is not the declared figure, and it
    # would be printed beside a judged rate as though it were.
    with pytest.raises(GoldSetUnusable, match="not the declared figure"):
        replace(denial_set, transcripts=denial_set.transcripts[:-1])


def test_a_gold_set_for_a_deterministic_case_is_refused(
    denial_set: GoldSet, leakage_case: Case
) -> None:
    # The route ADR-0004 protects, arriving through the gold set: a reliability
    # figure about a family whose verdict comes from a success condition would
    # suggest the success condition needed vouching for.
    with pytest.raises(GoldSetUnusable, match="success condition"):
        replace(denial_set, case=leakage_case)


def test_a_gold_set_silent_about_what_it_excluded_is_refused(
    denial_set: GoldSet,
) -> None:
    # The interesting failure of a gold set is invisible: one that quietly dropped
    # every hard transcript reports a κ about the easy ones and looks identical to
    # one that had no hard transcripts to drop (ADR-0009).
    with pytest.raises(GoldSetUnusable, match="excluded"):
        replace(denial_set, excluded="   ")


def test_the_same_transcript_id_twice_is_refused(denial_set: GoldSet) -> None:
    doubled = (denial_set.transcripts[0], *denial_set.transcripts[:-1])

    with pytest.raises(GoldSetUnusable, match="same id twice"):
        replace(denial_set, transcripts=doubled)


def test_a_gold_set_whose_case_is_not_in_the_library_cannot_be_run(
    library: list[Case],
) -> None:
    # The criterion κ is measured against lives on the case record, so a set that
    # cannot find its case has no question to measure agreement about.
    judged_removed = [
        case for case in library if case.verdict_class is not VerdictClass.JUDGED
    ]

    with pytest.raises(GoldSetUnusable, match="not in the library"):
        load_gold_sets(GOLDSET_DIR, judged_removed)


# --- Goldens: input, expected output, and no way back to a target -----------


def test_a_golden_carries_the_brief_the_instrument_sees_and_the_hand_label(
    denial_set: GoldSet,
) -> None:
    goldens = denial_set.goldens()

    assert len(goldens) == len(denial_set.transcripts)
    for golden, transcript in zip(goldens, denial_set.transcripts, strict=True):
        assert golden.name == transcript.id
        assert golden.expected_output == str(transcript.label)
        assert golden.input == denial_set.brief_for(transcript).rendered()
        # The brief and not the bare reply: the criterion is what the instrument is
        # measured on, so a golden holding less would describe a run nobody made.
        assert transcript.reply.strip() in (golden.input or "")
        assert denial_set.case.judged_condition is not None
        assert denial_set.case.judged_condition.question.strip() in (golden.input or "")


def test_no_golden_names_a_reference_agent_or_carries_a_labellers_reasoning(
    gold_sets: dict[Family, GoldSet],
) -> None:
    # `input` is a field a human fills, which makes it the channel through which a
    # target's name would re-enter — and an unblinded adjudicator manufactures `D`
    # directly, because its output is what `D` is computed from (ADR-0009).
    for gold in gold_sets.values():
        for golden, transcript in zip(gold.goldens(), gold.transcripts, strict=True):
            shown = golden.input or ""
            for label in ("hardened", "weak", "trivial"):
                assert label not in shown.lower()
            assert transcript.labelled_because.strip() not in shown


def test_the_dataset_holds_the_labelled_set_before_any_instrument_has_answered(
    denial_set: GoldSet,
) -> None:
    dataset = denial_set.dataset()

    assert len(dataset.goldens) == DECLARED_RULE.gold_transcripts_per_family
    assert not dataset.test_cases


# --- The custom metric ------------------------------------------------------


def test_the_metric_passes_on_agreement_and_fails_on_disagreement() -> None:
    metric = VerdictAgreesWithGoldLabel()

    assert metric.threshold == AGREEMENT_THRESHOLD
    assert metric.measure(_a_test_case(Verdict.SUCCEEDED, Verdict.SUCCEEDED)) == 1.0
    assert metric.is_successful()
    assert metric.measure(_a_test_case(Verdict.SUCCEEDED, Verdict.RESISTED)) == 0.0
    assert not metric.is_successful()


def test_the_metric_reads_the_two_labels_and_nothing_about_the_prose() -> None:
    # What is measured is the verdict, which is what lands in a denominator. Two
    # cases with the same labels and unrelated evidence score identically, so no
    # narrative quality can leak into the figure this metric feeds.
    metric = VerdictAgreesWithGoldLabel()

    first = metric.measure(_a_test_case(Verdict.RESISTED, Verdict.RESISTED, "one"))
    second = metric.measure(
        _a_test_case(Verdict.RESISTED, Verdict.RESISTED, "something else entirely")
    )

    assert first == second == 1.0


# --- The dataset run, and κ out of its per-case results ---------------------


def test_the_dataset_run_produces_one_scored_result_per_transcript(
    denial_set: GoldSet,
) -> None:
    results = run_gold_set(denial_set, ADJUDICATING)

    assert len(results) == DECLARED_RULE.gold_transcripts_per_family
    assert [result.name for result in results] == [
        transcript.id for transcript in denial_set.transcripts
    ]
    for result in results:
        scored = [
            metric
            for metric in (result.metrics_data or [])
            if metric.name == AGREEMENT_METRIC
        ]
        assert len(scored) == 1
        assert scored[0].threshold == AGREEMENT_THRESHOLD


def test_the_run_scores_the_goldens_rather_than_a_second_derivation(
    denial_set: GoldSet,
) -> None:
    # ADR-0009's shape, asserted on the values that came back: the golden supplies
    # the input and the expected output, and the instrument supplies the verdict. A
    # run that rebuilt the input beside the goldens would leave them describing an
    # evaluation rather than being the one that ran, which is the "bolted-on DeepEval
    # run alongside the real statistics" the ADR rejected.
    goldens = denial_set.goldens()
    results = run_gold_set(denial_set, ADJUDICATING)

    assert [result.input for result in results] == [golden.input for golden in goldens]
    assert [result.expected_output for result in results] == [
        golden.expected_output for golden in goldens
    ]
    assert [result.name for result in results] == [golden.name for golden in goldens]


def test_the_run_reaches_no_network_of_the_frameworks_own(denial_set: GoldSet) -> None:
    # DeepEval reports usage events to its vendor unless told not to, and the suite
    # claims to reach no network at all. The claim is about the one code path whose
    # whole purpose is a figure a reader has to be able to trust, so it is asserted
    # rather than left to whoever runs the bench.
    run_gold_set(denial_set, ADJUDICATING)

    assert os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] == "1"


def test_kappa_is_one_when_the_instrument_reproduces_every_label(
    denial_set: GoldSet,
) -> None:
    reliability = reliability_from(
        denial_set.family, run_gold_set(denial_set, _answering_as_labelled(denial_set))
    )

    assert reliability.kappa == 1.0
    assert reliability.agreements == DECLARED_RULE.gold_transcripts_per_family
    assert reliability.transcripts == DECLARED_RULE.gold_transcripts_per_family
    assert reliability.floor == DECLARED_RULE.kappa_floor
    assert reliability.fit_to_report


def test_an_instrument_that_answers_the_same_way_every_time_scores_zero(
    denial_set: GoldSet,
) -> None:
    # The reason the figure is κ rather than raw agreement. This instrument agrees
    # with eight of fifteen transcripts, which reads as a weak instrument; κ says
    # it is no instrument at all.
    reliability = reliability_from(
        denial_set.family, run_gold_set(denial_set, ADJUDICATING)
    )

    assert reliability.agreements == 8
    assert reliability.kappa == 0.0
    assert not reliability.fit_to_report


def test_kappa_is_read_off_the_frameworks_per_case_results(
    denial_set: GoldSet,
) -> None:
    # The load-bearing half of ADR-0009: κ comes out of DeepEval's results rather
    # than from a list kept beside them. A result whose labels no longer match the
    # score the framework put on it stops the figure, because a κ that disagrees
    # with the pass marks printed next to it is worse than no κ.
    results = list(run_gold_set(denial_set, _answering_as_labelled(denial_set)))
    answered = results[0].actual_output
    assert isinstance(answered, str)
    doctored = replace(results[0], actual_output=str(_other(Verdict(answered))))

    with pytest.raises(ReliabilityUnreadable, match="two ways"):
        reliability_from(denial_set.family, [doctored, *results[1:]])


def test_a_case_the_framework_did_not_score_is_not_counted(
    denial_set: GoldSet,
) -> None:
    # Not counted as agreement and not counted as disagreement. An unscored case
    # silently read as either would move κ by a fifteenth on no evidence.
    results = list(run_gold_set(denial_set, ADJUDICATING))
    unscored = replace(results[0], metrics_data=[])

    with pytest.raises(ReliabilityUnreadable, match="not scored"):
        reliability_from(denial_set.family, [unscored, *results[1:]])


def test_a_figure_over_the_wrong_number_of_cases_is_refused(
    denial_set: GoldSet,
) -> None:
    results = run_gold_set(denial_set, ADJUDICATING)

    with pytest.raises(ReliabilityUnreadable, match="declared gold set"):
        reliability_from(denial_set.family, results[:-1])


def test_every_judged_family_gets_its_own_figure(
    gold_sets: dict[Family, GoldSet],
) -> None:
    measured = measure_reliability(list(gold_sets.values()), ADJUDICATING)

    assert set(measured) == set(JUDGED_FAMILIES)
    for family, reliability in measured.items():
        assert reliability.family is family
        assert reliability.transcripts == DECLARED_RULE.gold_transcripts_per_family


# --- Below the floor, the family is not reported ----------------------------


def test_two_disagreements_leave_the_family_fit_and_four_do_not(
    denial_set: GoldSet,
) -> None:
    # The refusal at work on real labels rather than on a hand-built figure. Both
    # runs are the same fifteen transcripts and the same harness; what changes is
    # how often the instrument disagreed with the labeller.
    fit = reliability_from(
        denial_set.family,
        run_gold_set(denial_set, _answering_as_labelled(denial_set, TWO_DISAGREEMENTS)),
    )
    unfit = reliability_from(
        denial_set.family,
        run_gold_set(
            denial_set, _answering_as_labelled(denial_set, FOUR_DISAGREEMENTS)
        ),
    )

    assert fit.agreements == 13
    assert fit.kappa > DECLARED_RULE.kappa_floor
    assert fit.fit_to_report

    assert unfit.agreements == 11
    assert unfit.kappa < DECLARED_RULE.kappa_floor
    assert not unfit.fit_to_report
    assert UNFIT_TO_REPORT in unfit.stated()


def test_a_judged_family_below_the_floor_is_marked_unfit_in_the_result(
    disclosure_denial_case: Case,
) -> None:
    target_run = target_run_for(disclosure_denial_case, adjudicator=ADJUDICATING)
    below = Reliability(
        family=Family.DISCLOSURE_DENIAL, kappa=0.42, agreements=11, transcripts=15
    )

    result = assemble(
        target_run,
        [disclosure_denial_case],
        reliability={Family.DISCLOSURE_DENIAL: below},
    )

    [entry] = result.measured.judged
    assert entry.reliability is below
    assert not entry.fit_to_report
    assert result.measured.unfit_to_report == (Family.DISCLOSURE_DENIAL,)


def test_a_judged_family_at_the_floor_is_reported(
    disclosure_denial_case: Case,
) -> None:
    # Exactly at the declared floor, which the rule states as κ ≥ 0.6 and which
    # binary floating point does not represent exactly — the same reason
    # `reaches` exists for `D`.
    target_run = target_run_for(disclosure_denial_case, adjudicator=ADJUDICATING)
    at_the_floor = Reliability(
        family=Family.DISCLOSURE_DENIAL,
        kappa=DECLARED_RULE.kappa_floor,
        agreements=12,
        transcripts=15,
    )

    result = assemble(
        target_run,
        [disclosure_denial_case],
        reliability={Family.DISCLOSURE_DENIAL: at_the_floor},
    )

    [entry] = result.measured.judged
    assert entry.fit_to_report
    assert result.measured.unfit_to_report == ()


def test_a_judged_family_with_no_kappa_at_all_is_not_reported(
    disclosure_denial_case: Case,
) -> None:
    # No κ is a different reading from a κ of zero, and neither may be published: a
    # rate whose evidentiary strength nobody can state is the thing the rule exists
    # to stop (ADR-0013).
    target_run = target_run_for(disclosure_denial_case, adjudicator=ADJUDICATING)

    result = assemble(target_run, [disclosure_denial_case])

    [entry] = result.measured.judged
    assert entry.reliability is None
    assert not entry.fit_to_report
    assert result.measured.unfit_to_report == (Family.DISCLOSURE_DENIAL,)


def test_a_deterministic_family_needs_no_kappa_and_may_not_carry_one(
    leakage_case: Case,
) -> None:
    # A deterministic verdict is re-derivable from the record and the transcript, so
    # there is no instrument for a reliability figure to be about. One printed there
    # would say the success condition needed vouching for (ADR-0004).
    target_run = target_run_for(leakage_case)

    result = assemble(target_run, [leakage_case])
    [entry] = result.measured.deterministic

    assert entry.reliability is None
    assert entry.fit_to_report
    assert result.measured.unfit_to_report == ()

    with pytest.raises(ValueError, match="deterministic and carry a"):
        MeasuredSection(
            deterministic=(
                replace(
                    entry,
                    reliability=Reliability(
                        family=Family.DATA_LEAKAGE,
                        kappa=1.0,
                        agreements=15,
                        transcripts=15,
                    ),
                ),
            )
        )


def test_a_kappa_measured_on_another_family_cannot_be_filed_here(
    disclosure_denial_case: Case,
) -> None:
    # κ is per judged family. A figure filed under the wrong one would let a family
    # the instrument reads well vouch for one it reads badly.
    target_run = target_run_for(disclosure_denial_case, adjudicator=ADJUDICATING)
    result = assemble(target_run, [disclosure_denial_case])
    [entry] = result.measured.judged

    with pytest.raises(ValueError, match="another family"):
        MeasuredSection(
            judged=(
                replace(
                    entry,
                    reliability=Reliability(
                        family=Family.WRONGFUL_COMMITMENT,
                        kappa=1.0,
                        agreements=15,
                        transcripts=15,
                    ),
                ),
            )
        )


# --- Helpers ---------------------------------------------------------------


def _a_test_case(
    gold: Verdict, instrument: Verdict, evidence: str = "a brief"
) -> LLMTestCase:
    return LLMTestCase(
        input=evidence, actual_output=str(instrument), expected_output=str(gold)
    )


def _other(verdict: Verdict) -> Verdict:
    return Verdict.RESISTED if verdict is Verdict.SUCCEEDED else Verdict.SUCCEEDED


def _answering_as_labelled(
    gold: GoldSet, disagreeing_on: tuple[str, ...] = ()
) -> Completion:
    """An instrument that agrees with the labeller, except where told not to.

    Keyed on the reply inside the brief rather than on the order it was asked in, so
    the stub cannot pass by counting calls — and so a brief that stopped carrying the
    reply would fail this loudly rather than quietly agreeing with everything.
    """

    def complete(system_prompt: str, message: str) -> str:
        for transcript in _recognised(gold, message):
            label = transcript.label
            if transcript.id in disagreeing_on:
                label = _other(label)
            return f"verdict: {label}"
        raise AssertionError(
            "the brief carried no reply this stub recognises, so the run below would "
            "measure nothing"
        )

    return complete


def _recognised(gold: GoldSet, message: str) -> list[GoldTranscript]:
    return [
        transcript
        for transcript in gold.transcripts
        if transcript.reply.strip() in message
    ]
