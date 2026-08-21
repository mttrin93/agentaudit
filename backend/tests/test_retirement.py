"""Retirement — the decay series a gate run stores, and the rule read over it.

Seam two, on the same terms as `test_admission.py`: pure functions over recorded
counts, driven directly, because the arithmetic decides whether a case keeps running
and an end-to-end run could not localise an error in it. The one thing that is not
arithmetic — the reading landing on the case's own record — is driven against records
written into `tmp_path`, never against `backend/cases/`, so a test cannot retire a
real case by passing.

Three properties carry the ticket and they are different properties. The **series**:
one reading per case per gate run, and a case nothing ran against gets *no reading*
rather than a `D` of zero. The **rule**: two *consecutive* runs below the declared
floor, so one bad night cannot retire a working case. And the **record**: a retired
case is kept with its date and its final score, leaves the live library, and stays
queryable in it — a retirement is a status, never a deletion.

The fourth property is a refusal, and ADR-0022 makes it two. ADR-0016 declines the
rule on a family the bench could not vouch for — decay cannot be claimed on a number
the report will not print, which is ADR-0015's total exclusion read at the second
consumer of the same `D`. ADR-0022 declines it on a run that did not measure the field
at all, and narrows what *consecutive* means: two readings of **one model**, because
`D` is a reading about the case and the model together and a model swap moves it. The
outcome of both refusals is *not decided*: the reading is stored, the rule is not
applied, and the line says which of the two stopped it.

Both refusals are one-directional and both are tested as invariants below: provenance
and fitness can withhold a retirement and neither can ever cause one. The provenance
invariant is driven over every interleaving of two real models and a stub, because
that is the test ADR-0022 asks for by name — for any series, a stub reading must never
move an outcome to *retired*, and a window must never mix two models.
"""

from dataclasses import replace
from datetime import date
from itertools import product
from pathlib import Path

import pytest

from backend.bench.admission import admitted_library, library_provenance
from backend.bench.calibration import TargetRun
from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import (
    Case,
    CaseStatus,
    Family,
    GateReading,
    LibraryVersion,
    Retirement,
    Trigger,
    load_case,
    load_library,
    trigger_counts,
)
from backend.bench.registration import AttestationRecord, Registration
from backend.bench.retirement import (
    AlreadyRetired,
    Declined,
    RetirementDecision,
    RetirementDisagrees,
    RetirementOutcome,
    RunHistory,
    below_floor,
    decide_retirement,
    discrimination_of,
    live_library,
    readings_of,
    retired_cases,
    store,
)
from backend.bench.rule import DECLARED_RULE
from backend.graph.runstate import Attempt
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CASES_DIR,
    a_gate_reading,
    a_target,
    authored_library,
    authored_record,
    retired_case,
)

MODEL = "openrouter:openai/gpt-4.1-nano"
RAN_ON = date(2026, 8, 19)
LATER = date(2026, 9, 30)

SEPARATING = a_gate_reading(hardened=0, weak=5, trivial=10)
"""A reading that discriminates: D = 1.00, nowhere near the retirement floor."""

DECAYED = a_gate_reading(hardened=10, weak=10, trivial=10)
"""A reading that separates nothing: every agent broken equally, so D = 0.00. The
provider caught up with the payload, and the case still runs."""

SWAPPED = "openrouter:openai/gpt-4.1-mini"
"""A second real model. Not a worse instrument than `MODEL` — a different one, which
is the whole premise of #15 and the reason a window may not span the two."""

STUB = "stub:obedient"
"""The fixture `scripts/gate.py --model stub:obedient` runs on, named as the config
string a run is started with, because that is the thing an operator types."""


def on(reading: GateReading, model: str, *, of_the_field: bool = True) -> GateReading:
    """The same counts, read on another model — and whether that model was the field.

    The two travel together deliberately: provenance is a fact about the model the
    run used, so a helper that let a test say `stub` and *measured the field* would
    let a test assert something no run can produce.
    """
    return replace(
        reading,
        counts=replace(reading.counts, model=model),
        measured_the_field=of_the_field,
    )


STUBBED = on(DECAYED, STUB, of_the_field=False)
"""The reading a free run produces on every case: D = 0.00, and not a measurement.

The stub breaks all three reference agents identically by construction, so this is
the reading — not a low one, *this* one — that two runs of a script costing nothing
would retire the whole library on (#43).
"""


# --- The series: D for every case, on every run -------------------------------


def test_d_is_stored_for_every_case_a_gate_run_read(library: list[Case]) -> None:
    # Spec story 72. One reading per case per run, off the verdicts the three
    # reference agents actually returned, so decay is a series rather than a
    # surprise.
    run = readings_of(
        library,
        hardened=a_run("hardened", library, successes=0),
        weak=a_run("weak", library, successes=5),
        trivial=a_run("trivial", library, successes=10),
        model=MODEL,
        measured_the_field=True,
        ran_on=RAN_ON,
    )

    assert set(run.readings) == {case.id for case in library}
    assert not run.unread
    for reading in run.readings.values():
        assert reading.ran_on == RAN_ON
        assert reading.counts.attempts == DECLARED_RULE.attempts_per_case
        assert discrimination_of(reading) == 1.0


def test_a_case_no_attempt_was_spent_on_has_no_d_and_is_named_instead(
    library: list[Case],
) -> None:
    # A case skipped for its agent type or barred by a precondition was never
    # measured, and a D of zero standing in for that would read as a case that
    # stopped discriminating — which is the reading that would then retire it.
    ran, skipped = library[:2], library[2:]
    run = readings_of(
        library,
        hardened=a_run("hardened", ran, successes=0),
        weak=a_run("weak", ran, successes=5),
        trivial=a_run("trivial", ran, successes=10),
        model=MODEL,
        measured_the_field=True,
        ran_on=RAN_ON,
    )

    assert set(run.readings) == {case.id for case in ran}
    assert set(run.unread) == {case.id for case in skipped}
    assert all(case.id in run.stated() for case in skipped)
    assert "never a D of zero" in run.stated()


def test_a_stored_reading_does_not_move_the_library_version(
    library: list[Case],
) -> None:
    # Two runs of the identical eighteen cases are comparable, and the version is
    # what says so (spec story 27). A digest that moved when a run appended its own
    # reading would report every library as incomparable with itself, on every run,
    # by construction.
    read = [replace(case, history=(case.history + (DECAYED,))) for case in library]

    assert LibraryVersion.of(read) == LibraryVersion.of(library)
    # And an edit to what the case actually asks still moves it.
    edited = [replace(library[0], payload="something else"), *library[1:]]
    assert LibraryVersion.of(edited) != LibraryVersion.of(library)


# --- The rule: two consecutive runs, and one run is not two --------------------


def test_a_case_below_the_floor_on_two_consecutive_runs_is_retired() -> None:
    decision = decide_retirement("data-leakage-001", [SEPARATING, DECAYED, DECAYED])

    assert decision.outcome is RetirementOutcome.RETIRED
    assert decision.retires
    assert decision.scores == (0.0, 0.0)
    assert "never deleted" in decision.stated()


def test_a_single_run_below_the_floor_does_not_retire_a_case() -> None:
    # One bad night must not retire a working case (ADR-0003). This is the whole
    # reason the rule reads two runs rather than the last one.
    decision = decide_retirement("data-leakage-001", [SEPARATING, DECAYED])

    assert decision.outcome is RetirementOutcome.LIVE
    assert not decision.retires
    assert "one run below it is not two" in decision.stated()


def test_a_case_that_recovered_between_two_low_runs_is_not_retired() -> None:
    # Two low readings, and not two *consecutive* ones. Read over the worst two
    # rather than the last two, this case would retire on a series that says it
    # still works.
    decision = decide_retirement("data-leakage-001", [DECAYED, SEPARATING, DECAYED])

    assert decision.outcome is RetirementOutcome.LIVE
    assert decision.scores == (1.0, 0.0)


def test_a_case_exactly_on_the_declared_floor_is_not_below_it() -> None:
    # The rule is `D < 0.25`, and 0.25 is not below itself. Read as a bare
    # comparison this passes by accident; read against a float that has no exact
    # binary form it can fail, which is what `reaches` is for.
    # 29/100 − 4/100 is 0.25 by construction and 0.24999999999999997 in binary, so a
    # bare `<` retires a case sitting exactly on the declared floor.
    on_the_floor = a_gate_reading(hardened=4, weak=15, trivial=29, attempts=100)
    assert discrimination_of(on_the_floor) == pytest.approx(
        DECLARED_RULE.retirement_floor
    )

    decision = decide_retirement("data-leakage-001", [on_the_floor, on_the_floor])

    assert decision.outcome is RetirementOutcome.LIVE


def test_a_case_with_no_reading_yet_is_live_and_says_so() -> None:
    decision = decide_retirement("data-leakage-001", [])

    assert decision.outcome is RetirementOutcome.LIVE
    assert "no reading yet" in decision.stated()


# --- The window: two consecutive readings of one model (ADR-0022) -------------


def test_two_readings_of_two_models_are_not_two_readings_of_one_thing() -> None:
    # `D` is a property of the case *and* the model underneath the three reference
    # agents, and #15 exists because a model swap moves it. A positional window reads
    # a change of instrument as the passage of time: it says "this case stopped
    # discriminating" when what happened is that somebody pointed the bench at
    # something else.
    decision = decide_retirement("data-leakage-001", [DECAYED, on(DECAYED, SWAPPED)])

    assert decision.outcome is RetirementOutcome.LIVE
    assert decision.model == SWAPPED
    # One reading of the model in question, and one is not two.
    assert decision.considered == (on(DECAYED, SWAPPED),)


def test_the_window_is_the_last_two_readings_of_the_most_recent_model() -> None:
    # The clause is not only a restriction: this series retires under ADR-0022 and
    # was live under the positional rule, which read `[B high, A low]`. `B`'s high
    # reading is evidence about `B` and says nothing about whether the case separates
    # on `A`, which has now failed to separate twice.
    series = [DECAYED, on(SEPARATING, SWAPPED), DECAYED]

    decision = decide_retirement("data-leakage-001", series)

    assert decision.outcome is RetirementOutcome.RETIRED
    assert decision.model == MODEL
    assert decision.scores == (0.0, 0.0)
    # And the intervening reading is not silently in the window it was left out of.
    assert 1.0 not in decision.scores


def test_the_most_recent_reading_always_participates() -> None:
    # Anchored to the newest reading's model rather than to whichever model has two
    # low readings somewhere in the series. Retirement is a claim about the case
    # *now*, and a claim that ignores the most recent measurement of it is a claim
    # about the past.
    decision = decide_retirement(
        "data-leakage-001", [DECAYED, DECAYED, on(SEPARATING, SWAPPED)]
    )

    assert decision.outcome is RetirementOutcome.LIVE
    assert decision.model == SWAPPED
    assert decision.considered == (on(SEPARATING, SWAPPED),)


def test_the_clock_restarts_on_a_model_swap() -> None:
    # The cost of the clause, named rather than discovered: a case with two low
    # readings on `A` needs two readings on `B` before `B` can retire it, and one is
    # not two. Bounded by two runs, and paid in attempts against a case that stays
    # live meanwhile.
    once = decide_retirement(
        "data-leakage-001", [DECAYED, DECAYED, on(DECAYED, SWAPPED)]
    )
    twice = decide_retirement(
        "data-leakage-001",
        [DECAYED, DECAYED, on(DECAYED, SWAPPED), on(DECAYED, SWAPPED)],
    )

    assert once.outcome is RetirementOutcome.LIVE
    assert twice.outcome is RetirementOutcome.RETIRED
    assert twice.model == SWAPPED


def test_readings_outside_the_window_are_kept_and_the_window_is_named() -> None:
    # Scoping the *window* is not editing the *series* (ADR-0006): the readings the
    # rule did not read are still on the record, and the line says which model the
    # two it did read were taken on — so it names a window a reader can find in the
    # series, rather than "the last two runs" of a series that spans two models. The
    # readings outside the window were printed by the run that took them.
    series = [DECAYED, on(DECAYED, SWAPPED), DECAYED, DECAYED]

    decision = decide_retirement("data-leakage-001", series)

    assert len(decision.considered) == 2
    assert MODEL in decision.stated()
    assert decision.model == MODEL


# --- The refusal ADR-0022 decides: a fixture is not a measurement -------------


def test_two_runs_of_the_stub_fixture_do_not_retire_a_case() -> None:
    # The defect #43 demonstrated, and the reason the model-scoped window is not
    # enough on its own: two stub runs are two readings of one model and satisfy the
    # window exactly. The stub does not attenuate `D` toward zero — it *is* zero, on
    # every case, every time, for free, so two runs of a script that costs nothing
    # would empty the live library and record each removal as evidence of decay.
    decision = decide_retirement("data-leakage-001", [STUBBED, STUBBED])

    assert decision.outcome is RetirementOutcome.NOT_DECIDED
    assert not decision.retires
    # Stored and read, not ignored: the readings are in the window and the scores are
    # the ones that would have retired it.
    assert decision.scores == (0.0, 0.0)
    assert decision.model == STUB
    # The line says the window was refused for provenance rather than for fitness —
    # two different refusals under one outcome, and a reader gets which one.
    assert "not a measurement of the field" in decision.stated()
    assert "ADR-0022" in decision.stated()


def test_a_run_on_the_field_after_a_stub_run_has_one_reading_of_the_field() -> None:
    # #43's third demonstration: under the positional rule this retired, and the
    # *real* model's name landed on the recorded final score while the stub silently
    # supplied half the evidence the rule used. Both clauses close it — the window
    # holds one reading now, and the stub reading could not have retired anything
    # anyway.
    decision = decide_retirement("data-leakage-001", [STUBBED, DECAYED])

    assert decision.outcome is RetirementOutcome.LIVE
    assert decision.considered == (DECAYED,)
    assert decision.model == MODEL


def test_a_stub_reading_can_never_move_an_outcome_to_retired() -> None:
    # The invariant ADR-0022 extends from ADR-0016: a reading's provenance can only
    # withhold a retirement and never cause one. Driven over every interleaving of
    # two models and every fitness pattern rather than over one example, because the
    # value of an invariant is that no future series gets to be the exception — and
    # because the two refusals compose, so a stub reading on an unfit family must be
    # *not decided* once and not twice.
    models = ((MODEL, True), (SWAPPED, True), (STUB, False))
    withheld = 0
    for shape in product((SEPARATING, DECAYED), repeat=3):
        for provenance in product(models, repeat=3):
            for flags in product((True, False), repeat=3):
                series = [
                    replace(on(reading, model, of_the_field=field), fit_to_report=flag)
                    for reading, (model, field), flag in zip(
                        shape, provenance, flags, strict=True
                    )
                ]
                decision = decide_retirement("data-leakage-001", series)
                window = decision.considered

                # No window ever spans two models, whatever the series.
                assert len({reading.model for reading in window}) <= 1

                if decision.outcome is RetirementOutcome.RETIRED:
                    # Reachable only over two readings, both of the field, both fit,
                    # both below the floor — and never on a model that is a fixture.
                    assert len(window) == 2
                    assert all(reading.measured_the_field for reading in window)
                    assert all(reading.fit_to_report for reading in window)
                    assert all(below_floor(reading) for reading in window)
                    assert decision.model != STUB

                if decision.outcome is RetirementOutcome.NOT_DECIDED:
                    # Declined only where the rule would otherwise have retired.
                    withheld += 1
                    assert len(window) == 2
                    assert all(below_floor(reading) for reading in window)
                    assert not all(
                        reading.measured_the_field and reading.fit_to_report
                        for reading in window
                    )

    # Not vacuous: the withholding really happens, and on the stub in particular.
    assert withheld > 0
    assert (
        decide_retirement("data-leakage-001", [STUBBED, STUBBED]).outcome
        is RetirementOutcome.NOT_DECIDED
    )


def test_a_stub_reading_on_an_unfit_family_is_not_decided_once() -> None:
    # The two refusals compose the same way — both checked only on the branch that
    # would have retired, either one withholding — so there is one outcome and not a
    # fourth member for the pair of them. Provenance is the one named, because it is
    # the stronger statement: an unfit reading is a degraded measurement of the field,
    # and a fixture reading is not a measurement of it at all.
    both = replace(STUBBED, fit_to_report=False)

    decision = decide_retirement("wrongful-commitment-001", [both, both])

    assert decision.outcome is RetirementOutcome.NOT_DECIDED
    assert "not a measurement of the field" in decision.stated()


def test_a_not_decided_decision_cannot_be_built_without_saying_which_ground() -> None:
    # The pairing as a property of the type rather than a sentence in a docstring, on
    # the same terms as `SuccessCondition.__post_init__` and `Case`: both directions
    # are records a reader cannot re-derive. A *not decided* with no ground prints a
    # line that declines and never says why — and the ADR that decided the refusal is
    # named by the ground, so the line would cite nothing. A ground on any other
    # outcome is a refusal recorded against a decision that was not refused, and it
    # prints as an outright contradiction: retired, because the bench could not vouch
    # for the family.
    with pytest.raises(ValueError, match="which of the two grounds"):
        RetirementDecision(
            case_id="data-leakage-001",
            outcome=RetirementOutcome.NOT_DECIDED,
            considered=(STUBBED, STUBBED),
        )

    for outcome in (RetirementOutcome.LIVE, RetirementOutcome.RETIRED):
        with pytest.raises(ValueError, match="was not declined"):
            RetirementDecision(
                case_id="data-leakage-001",
                outcome=outcome,
                considered=(DECAYED, DECAYED),
                declined=Declined.UNFIT_FAMILY,
            )

    # And the rule itself never builds one of either shape: every outcome it can
    # reach is constructed here, so this is the invariant and not an example.
    for series in ([], [DECAYED], [DECAYED, DECAYED], [STUBBED, STUBBED]):
        decision = decide_retirement("data-leakage-001", series)
        assert (decision.declined is not None) is (
            decision.outcome is RetirementOutcome.NOT_DECIDED
        )


def test_a_reading_names_the_model_it_was_taken_on() -> None:
    # One walk, on the reading rather than at every call site: the model is a fact
    # about the reading, and a rule that reached through `counts` for it would make
    # every reader of the series depend on where a reading keeps its counts.
    assert DECAYED.model == MODEL
    assert STUBBED.model == STUB
    assert DECAYED.model == DECAYED.counts.model


def test_a_run_records_on_every_reading_whether_it_measured_the_field(
    library: list[Case],
) -> None:
    # Recorded by the run that took the reading, beside `fit_to_report` and for the
    # same reason: provenance is a fact about the run. Both answers are asserted,
    # because a flag that is always true is not a flag.
    def run_on(field: bool) -> RunHistory:
        return readings_of(
            library,
            hardened=a_run("hardened", library, successes=10),
            weak=a_run("weak", library, successes=10),
            trivial=a_run("trivial", library, successes=10),
            model=MODEL if field else STUB,
            measured_the_field=field,
            ran_on=RAN_ON,
        )

    assert all(reading.measured_the_field for reading in run_on(True).readings.values())
    assert not any(
        reading.measured_the_field for reading in run_on(False).readings.values()
    )


def test_two_stub_runs_write_their_readings_and_retire_nothing(tmp_path: Path) -> None:
    # The rule reaching the store rather than a list in memory, on the series that
    # would have retired the record. The storing path stays exercised by a run that
    # spends nothing — which is the reason the stub fixture exists, and the reason
    # ADR-0022 marks the reading instead of refusing to write it.
    path = _record(tmp_path)
    store(tmp_path, _one_run(STUBBED, ran_on=RAN_ON))
    [decision] = store(tmp_path, _one_run(STUBBED, ran_on=LATER))

    stored = load_case(path)
    assert decision.outcome is RetirementOutcome.NOT_DECIDED
    assert stored.status is CaseStatus.ACTIVE
    assert stored.retirement is None
    # Both readings are on the record, and both say what they are.
    assert len(stored.history) == 2
    assert [reading.measured_the_field for reading in stored.history] == [False, False]


def test_a_reading_that_does_not_say_whether_it_measured_the_field_does_not_load(
    tmp_path: Path,
) -> None:
    # Read rather than defaulted, because the answer a record would acquire by
    # silence is the one that lets the rule retire. A series whose provenance went
    # missing in the file would read as a series of measurements of the field.
    path = _record(tmp_path)
    store(tmp_path, _one_run(DECAYED))
    path.write_text(
        "\n".join(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("measured_the_field")
        ),
        encoding="utf-8",
    )

    with pytest.raises(KeyError, match="measured_the_field"):
        load_case(path)


# --- The refusal ADR-0016 decides ---------------------------------------------


def test_the_rule_is_not_applied_to_a_family_the_bench_could_not_vouch_for() -> None:
    # ADR-0015 excludes a family below the κ floor from the gate decision, and
    # ADR-0016 declines retirement there for the same reason one level down: a
    # retirement is a claim that discrimination decayed, and the claim cannot rest on
    # a number the report refuses to print. So the readings are stored and the rule is
    # declined — retiring here would claim decay on unvouched verdicts, and ignoring
    # the readings would lose the evidence that answers the question once κ is fixed.
    unfit = replace(DECAYED, fit_to_report=False)

    decision = decide_retirement("wrongful-commitment-001", [unfit, unfit])

    assert decision.outcome is RetirementOutcome.NOT_DECIDED
    assert not decision.retires
    assert decision.scores == (0.0, 0.0)
    # Both ADRs are named: the one that decides, and the one whose exclusion it
    # applies. A reader who finds a not-decided line gets the decision, not a defer.
    assert "ADR-0016" in decision.stated()
    assert "ADR-0015" in decision.stated()


def test_unfitness_can_only_withhold_a_retirement_and_never_cause_one() -> None:
    # ADR-0016's invariant, and the mirror of the one ADR-0015 states for the gate.
    # Driven over every two-run window and every fitness pattern rather than over one
    # example, because the whole value of an invariant is that no future window gets
    # to be the exception — including a window whose readings disagree about fitness.
    withheld = 0
    for shape in product((SEPARATING, DECAYED), repeat=2):
        declared = decide_retirement(
            "wrongful-commitment-001",
            [replace(reading, fit_to_report=True) for reading in shape],
        ).outcome
        for flags in product((True, False), repeat=2):
            series = [
                replace(reading, fit_to_report=flag)
                for reading, flag in zip(shape, flags, strict=True)
            ]
            outcome = decide_retirement("wrongful-commitment-001", series).outcome

            if outcome is RetirementOutcome.RETIRED:
                # A retirement is reachable only on a window the bench can vouch for
                # throughout, and only where the declared rule reached it anyway.
                assert all(flags), f"{shape} retired on {flags}"
                assert declared is RetirementOutcome.RETIRED
            if declared is RetirementOutcome.LIVE:
                # Unfitness is not a second way to answer a live case: the rule did
                # not fire, so there is no retirement for the exclusion to hold back.
                assert outcome is RetirementOutcome.LIVE, f"{shape} moved on {flags}"
            if declared is RetirementOutcome.RETIRED and not all(flags):
                assert outcome is RetirementOutcome.NOT_DECIDED
                withheld += 1

    # Not vacuous. The invariant is only worth stating because the withholding really
    # happens: one window retires under the declared rule, and each of the three ways
    # to make it unvouched-for holds that retirement back instead of taking it.
    assert withheld == 3


def test_a_family_the_bench_could_not_vouch_for_still_stores_its_d(
    library: list[Case],
) -> None:
    # Exclusion from the decision is not exclusion from the record: the attempts
    # were made, and a measured rate stays measured (ADR-0006). Both halves are
    # asserted here because storing without deciding is the whole of the position.
    run = readings_of(
        library,
        hardened=a_run("hardened", library, successes=10),
        weak=a_run("weak", library, successes=10),
        trivial=a_run("trivial", library, successes=10),
        model=MODEL,
        measured_the_field=True,
        ran_on=RAN_ON,
        excluded=[Family.WRONGFUL_COMMITMENT],
    )

    by_family = {case.id: case.family for case in library}
    for case_id, reading in run.readings.items():
        expected = by_family[case_id] is not Family.WRONGFUL_COMMITMENT
        assert reading.fit_to_report is expected


# --- The record: kept with its date and its final score -----------------------


def test_a_run_writes_its_reading_onto_every_record_it_read(tmp_path: Path) -> None:
    # Written by the run that measured it rather than transcribed by a person, and
    # appended rather than rewritten: the comments and the payload formatting in a
    # case file are a human's.
    path = _record(tmp_path)
    before = path.read_text(encoding="utf-8")

    [decision] = store(tmp_path, _one_run(DECAYED))

    stored = load_case(path)
    assert [discrimination_of(reading) for reading in stored.history] == [0.0]
    assert stored.history[0].ran_on == RAN_ON
    assert stored.history[0].counts.model == MODEL
    assert stored.status is CaseStatus.ACTIVE
    assert decision.outcome is RetirementOutcome.LIVE
    assert path.read_text(encoding="utf-8").startswith(before)


def test_the_second_consecutive_low_run_retires_the_record(tmp_path: Path) -> None:
    # The rule operating on the store rather than on a list in memory: two runs,
    # each appending its own reading, and the second one marks the record.
    path = _record(tmp_path)
    store(tmp_path, _one_run(DECAYED, ran_on=RAN_ON))
    [decision] = store(tmp_path, _one_run(DECAYED, ran_on=LATER))

    retired = load_case(path)
    assert decision.outcome is RetirementOutcome.RETIRED
    assert retired.status is CaseStatus.RETIRED
    assert retired.retirement is not None
    assert retired.retirement.retired_on == LATER
    # Kept with its final score, and the final score is the last reading of its own
    # series rather than a number written beside it (spec story 74).
    assert retired.retirement.final == retired.history[-1]
    assert discrimination_of(retired.retirement.final) == 0.0
    assert len(retired.history) == 2


def test_a_retired_case_leaves_the_live_library_and_stays_queryable_in_it(
    library: list[Case],
) -> None:
    # Retirement is a status and not a deletion. `live_library` is what a run
    # scores; every other reader still sees the case, which is what makes a retired
    # case evidence that the field moved rather than a case that went away.
    retired = retired_case(library[0])
    written = [retired, *library[1:]]

    assert retired.id not in {case.id for case in live_library(written)}
    assert len(live_library(written)) == len(library) - 1
    assert retired_cases(written) == [retired]
    provenance = library_provenance(written)
    assert provenance.retired[retired.discovered_by] == 1
    assert provenance.live_total == len(library) - 1


def test_a_record_whose_status_and_its_own_series_disagree_does_not_load(
    library: list[Case],
) -> None:
    # Both directions are refusals, and both are lifecycles a reader cannot
    # re-derive: a case retired without the readings that retire it was removed by
    # hand under a rule that exists so removal is not a judgement call, and a case
    # its series retires that is still scored is one the bench has measured as not
    # discriminating and is still spending attempts on.
    by_hand = replace(
        library[0],
        status=CaseStatus.RETIRED,
        history=(SEPARATING, SEPARATING),
        retirement=Retirement(retired_on=RAN_ON, final=SEPARATING),
    )
    with pytest.raises(RetirementDisagrees, match="marked retired"):
        live_library([by_hand])

    overdue = replace(library[0], history=(DECAYED, DECAYED))
    with pytest.raises(RetirementDisagrees, match="marked active"):
        live_library([overdue])


def test_a_retired_case_that_was_read_again_is_refused(tmp_path: Path) -> None:
    # A reading for a retired case means something loaded the library by a route
    # that is not `live_library`. Refused rather than appended, because the appended
    # reading would then be the case's final score.
    _record(tmp_path)
    store(tmp_path, _one_run(DECAYED, ran_on=RAN_ON))
    store(tmp_path, _one_run(DECAYED, ran_on=LATER))

    with pytest.raises(AlreadyRetired, match="excluded from live scoring"):
        store(tmp_path, _one_run(DECAYED, ran_on=date(2026, 10, 1)))


def test_a_retirement_with_no_reading_behind_it_does_not_load(tmp_path: Path) -> None:
    # The retired half of the record has to point at the series that retired it. A
    # `[retirement]` block over no history is an assertion, and the case it retires
    # is a case somebody decided about rather than measured.
    path = _record(tmp_path, status="retired")
    path.write_text(
        path.read_text(encoding="utf-8") + "\n[retirement]\nretired_on = 2026-08-19\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not a measurement"):
        load_case(path)


def test_a_record_cannot_be_retired_without_saying_when_and_on_what(
    library: list[Case],
) -> None:
    # The pairing as a property of the record: a status that could say *retired*
    # with no date and no final score would make "kept with its retirement date and
    # final score" a habit of whoever wrote the record.
    with pytest.raises(ValueError, match="records no retirement"):
        replace(library[0], status=CaseStatus.RETIRED)

    with pytest.raises(ValueError, match="is still active"):
        replace(
            library[0],
            history=(DECAYED,),
            retirement=Retirement(retired_on=RAN_ON, final=DECAYED),
        )

    with pytest.raises(ValueError, match="not the last reading"):
        replace(
            library[0],
            status=CaseStatus.RETIRED,
            history=(DECAYED, SEPARATING),
            retirement=Retirement(retired_on=RAN_ON, final=DECAYED),
        )


# --- The closed set of six triggers -------------------------------------------


def test_the_six_triggers_are_a_closed_set_and_every_case_names_one(
    library: list[Case],
) -> None:
    # Spec story 75. "Why does this case exist" always has an answer, and it comes
    # from a list nobody can extend by writing a sentence into a record.
    assert len(Trigger) == 6
    counts = trigger_counts(library)
    assert set(counts) == set(Trigger)
    assert sum(counts.values()) == len(library)

    for case in library:
        assert case.trigger in Trigger
        assert case.trigger.stated().strip()


def test_a_case_naming_a_trigger_the_set_does_not_hold_does_not_load(
    tmp_path: Path,
) -> None:
    path = _record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'trigger = "new_technique_published"', 'trigger = "seemed_like_a_good_idea"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="seemed_like_a_good_idea"):
        load_case(path)


# --- The library as it stands -------------------------------------------------


def test_the_whole_library_loads_live_and_agrees_with_its_own_series() -> None:
    # The invariant over `backend/cases/` rather than a survey: every case the run
    # scores is admitted, active, and carrying a series its status agrees with.
    live = live_library(admitted_library(CASES_DIR))

    assert len(live) == len(load_library(CASES_DIR))
    assert all(case.status is CaseStatus.ACTIVE for case in live)


# --- Helpers ------------------------------------------------------------------


def a_run(name: str, cases: list[Case], successes: int) -> TargetRun:
    """One reference agent's part of a gate run, over the given cases.

    Constructed rather than measured, on the same terms as `test_scorer.py`: what a
    reference agent does with a payload is a question about that agent, and what is
    under test here is what the series does with the answer.
    """
    target = a_target(name)
    probe = Transcript(
        url=target.url, sent={}, status_code=200, received={"reply": "nonce"}
    )
    return TargetRun(
        target=target,
        registration=Registration(
            target=target,
            nonce="nonce",
            complete=True,
            probe=probe,
            attestation=AttestationRecord.of(BENCH_ATTESTATION, target),
        ),
        attempts=tuple(
            Attempt(
                case_id=case.id,
                family=case.family,
                target_name=name,
                index=index,
                transcript=probe,
                verdict=(Verdict.SUCCEEDED if index < successes else Verdict.RESISTED),
                verdict_class=case.verdict_class,
            )
            for case in cases
            for index in range(DECLARED_RULE.attempts_per_case)
        ),
        rule=DECLARED_RULE,
    )


def _one_run(reading: GateReading, ran_on: date = RAN_ON) -> RunHistory:
    """One gate run's history, holding that reading for the record below."""
    return RunHistory(
        ran_on=ran_on,
        readings={CASE_ID: replace(reading, ran_on=ran_on)},
        unread=(),
    )


CASE_ID = "data-leakage-001"


def _record(directory: Path, status: str = "active") -> Path:
    """A copy of one real case record, in a directory a test may write to.

    Copied from `backend/cases/` so that what is exercised is the shape of a record
    a run actually meets, and copied rather than written in place so that no test
    can retire a real case by passing. Through `authored_record`, so the copy carries
    no series of its own: these tests count readings, and a real record's series grows
    every time the bench is run for real.
    """
    path = authored_record(CASES_DIR / f"{CASE_ID}.toml", directory / f"{CASE_ID}.toml")
    if status != "active":
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'status = "active"', f'status = "{status}"'
            ),
            encoding="utf-8",
        )
    return path


# --- The isolation the record tests rest on -----------------------------------


def test_an_authored_copy_carries_no_series_of_its_own(tmp_path: Path) -> None:
    # The half of the isolation that was missing until it broke. Every test above
    # that counts readings copies a real record first, and a real record's series
    # grows each time the bench is run for real: the certified run of 2026-08-19 put
    # one `[[history]]` block on all eighteen and turned four passing tests red. The
    # assertions were right and the starting state was not. Driven over the whole
    # library rather than one record, so a record that grows a block later cannot
    # quietly reintroduce the coupling.
    library = load_library(authored_library(tmp_path / "cases"))

    assert len(library) == len(load_library(CASES_DIR))
    for case in library:
        assert case.history == (), f"{case.id} arrived carrying a run's readings"
        assert case.retirement is None
        assert case.status is CaseStatus.ACTIVE


def test_an_authored_copy_of_a_retired_record_loads_as_authored(tmp_path: Path) -> None:
    # Both run-written blocks come off together, status included. A record marked
    # retired whose series has been taken away does not load at all
    # (`RetirementDisagrees`), so stripping half of that state would trade a coupling
    # for a fixture that cannot be read.
    path = _record(tmp_path)
    store(tmp_path, _one_run(DECAYED, ran_on=RAN_ON))
    store(tmp_path, _one_run(DECAYED, ran_on=LATER))
    assert load_case(path).status is CaseStatus.RETIRED

    authored = load_case(authored_record(path, tmp_path / "authored.toml"))

    assert (authored.status, authored.history, authored.retirement) == (
        CaseStatus.ACTIVE,
        (),
        None,
    )
