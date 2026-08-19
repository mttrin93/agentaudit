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

The fourth property is a refusal. ADR-0015 leaves open whether the rule may operate
on a family the bench could not vouch for, and assigns the question to #14's own
decision. Until that decision exists the outcome is *not decided*: the reading is
stored, the rule is not applied, and the line says which decision is missing.
"""

import shutil
from dataclasses import replace
from datetime import date
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
    RetirementDisagrees,
    RetirementOutcome,
    RunHistory,
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


# --- The refusal ADR-0015 left open -------------------------------------------


def test_the_rule_is_not_applied_to_a_family_the_bench_could_not_vouch_for() -> None:
    # ADR-0015 excludes a family below the κ floor from the gate decision and states
    # that whether retirement may operate on one is *not* settled there. So the
    # readings are stored and the rule is declined — a case retired here would
    # resolve the open question silently, and so would a case whose stored readings
    # were quietly ignored.
    unfit = replace(DECAYED, fit_to_report=False)

    decision = decide_retirement("wrongful-commitment-001", [unfit, unfit])

    assert decision.outcome is RetirementOutcome.NOT_DECIDED
    assert not decision.retires
    assert decision.scores == (0.0, 0.0)
    assert "ADR-0015" in decision.stated()


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
    can retire a real case by passing.
    """
    path = directory / f"{CASE_ID}.toml"
    shutil.copyfile(CASES_DIR / f"{CASE_ID}.toml", path)
    if status != "active":
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'status = "active"', f'status = "{status}"'
            ),
            encoding="utf-8",
        )
    return path
