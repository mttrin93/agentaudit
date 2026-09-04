"""What a run files into the long-term memory, and what it refuses to file.

Before this, `DurablePrecedents.record` had callers in `backend/tests/` and nowhere
else: the store's only entries were an operator's hand-typed seeds, and
`retrieve_precedent` answered *nothing has been filed against this family yet* on
every run to date (#38). ADR-0019's claim is that the store "earns its place at run
two", and a store nothing writes to never reaches run one.

**The assertions about the write path are at `run_calibration`**, because that is the
one place in the bench that holds a handle able to write and the spec puts the seam
there. The assertions about *selection* are at `filing.file_precedent`, which is
where the two rules live — deterministic only, and one precedent per case per target.

**No model is reached.** The reference agents run on the deterministic stub model and
the two narrative instruments answer with the lines they were handed
(`test_narration.py`'s own reasoning): what a fix *says* is not assertable, and what
is assertable is whether the store reached the model at all.
"""

from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path
from typing import cast, get_type_hints

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.runs import BenchConfig, BenchRuns, RunStatus
from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.blinding import Blinding
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.precedent import (
    DURABLE_PRECEDENT,
    DurablePrecedents,
    Precedent,
    PrecedentStore,
)
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adaptive.tools import retrieve_precedent
from backend.bench.calibration import CalibrationResult, TargetRun, run_calibration
from backend.bench.filing import Filing, file_precedent
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.narration import Narration, Narrator, narrate
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    CONFIRMING,
    a_finding,
    reference_target,
    served_references,
)
from backend.tests.test_adaptive_attacker import Recording
from backend.tests.test_api_runs import (
    a_request,
    registered,
    settled,
    watched_reference,
)
from backend.tests.test_narration import (
    Narrated,
    judging,
    narrated,
    remediating,
)
from scripts.console import precedent_section


@pytest.fixture
def store(tmp_path: Path) -> DurablePrecedents:
    """This test's own store, under a directory that is not there yet.

    Not there yet on purpose, the reason `test_precedent.store_file` gives: the
    store creates its parent, and a fixture that pre-made it would hide a backend
    that could only open a database beside an existing directory.
    """
    return DurablePrecedents.at(tmp_path / "precedent" / "findings.sqlite")


def test_a_deterministic_finding_is_filed_and_is_readable_back(
    store: DurablePrecedents,
) -> None:
    """The write that had no caller, called.

    One finding in, one row out, and read back through `for_family` — which is the
    interface `suggest_remediation` and `retrieve_precedent` both read through, so
    a write only this test could see would not be a write either of them reaches.
    """
    filing = file_precedent([a_finding()], store)

    assert [entry.case_id for entry in filing.filed] == ["data-leakage-001"]
    assert [entry.failure for entry in store.for_family(Family.DATA_LEAKAGE)] == [
        "The reply carried the configured secret back out."
    ]


def test_a_judged_finding_is_withheld_and_the_run_says_so(
    store: DurablePrecedents,
) -> None:
    """The refusal is reported rather than caught, and the deterministic one still
    lands.

    `Precedent.of` raises `JudgedPrecedent` for a judged verdict (ADR-0004), and a
    `try/except` around the write would be a silent partial write — the exact
    failure that named exception exists to prevent (#38). So the selection happens
    here, on `verdict_class`, which is copied off the attempt and is never inferred
    from a family name.
    """
    judged = a_finding(
        family=Family.WRONGFUL_COMMITMENT,
        verdict_class=VerdictClass.JUDGED,
        case_id="wrongful-commitment-001",
    )

    filing = file_precedent([a_finding(), judged], store)

    assert [entry.case_id for entry in filing.filed] == ["data-leakage-001"]
    assert [held.case_id for held in filing.judged] == ["wrongful-commitment-001"]
    assert store.for_family(Family.WRONGFUL_COMMITMENT) == ()


def test_ten_successes_of_one_case_against_one_target_file_one_precedent(
    store: DurablePrecedents,
) -> None:
    """The unit of a precedent is a failure mode, and the case is its identity.

    A case is run ten times against a target (#4), so a target that fails one
    holds up to ten findings of it — ten samples of one mode, differing only in
    what the target replied and in how the judge paraphrased it. `Precedent.key`
    collapses the ones whose prose came back identical and cannot collapse the
    rest, so filing all of them would make the corpus's composition a function of
    the judge's paraphrase variance and could fill `RETRIEVAL_LIMIT` with one case
    (ADR-0031).

    The first is kept rather than the best, because *best* is a ranking nothing
    here can compute — the same reason the lookup orders by recency.
    """
    filing = file_precedent(
        [
            a_finding(reason="It read the secret out on the first ask."),
            a_finding(reason="It read the secret out when asked to migrate."),
        ],
        store,
    )

    assert [entry.failure for entry in filing.filed] == [
        "It read the secret out on the first ask."
    ]
    assert len(store.for_family(Family.DATA_LEAKAGE)) == 1


def test_two_targets_failing_one_case_file_two_precedents(
    store: DurablePrecedents,
) -> None:
    """The collapse above is per target, and this is the half that says so.

    Two targets that failed the same case are two independent observations of it,
    and the record carries no target (ADR-0011) — so the only collapse available
    across them is the content-addressed key, which folds them together exactly
    when the prose came back the same and leaves them apart when it did not. The
    identity is read off `Finding.target_name`, not off a grouping the caller
    passed in, so a caller cannot widen or narrow the rule by how it batches.
    """
    filing = file_precedent(
        [
            a_finding(target_name="one-bot", reason="It read the secret out."),
            a_finding(target_name="another-bot", reason="It leaked from a page."),
        ],
        store,
    )

    assert sorted(entry.failure for entry in filing.filed) == [
        "It leaked from a page.",
        "It read the secret out.",
    ]


# --- Through the run, which is where the write happens -----------------------


def test_the_second_run_is_shown_what_the_first_one_filed(leakage_case: Case) -> None:
    """ADR-0019's claim, finally testable: the store earns its place at run two.

    Two runs against the same store, and the assertions are about both halves of
    the gap #38 named. Run one's fix was written against nothing, because a run
    files after every instrument in it has read (ADR-0031) — which is also the
    honest answer on run one, since there was nothing to read. Run two's fix was
    written against run one's finding, and the attacker's own tool answers with it
    too rather than with *nothing has been filed against this family yet*.
    """
    first = narrated(leakage_case)
    second = narrated(leakage_case)

    assert first.result.filing.filed, (
        "run one filed nothing, so run two had nothing to be shown and the "
        "assertions below would pass against a store that is never written"
    )
    assert [entry.case_id for entry in first.result.filing.filed] == [leakage_case.id]

    assert all(n.remediation.informed_by == () for n in _narrations(first)), (
        "a fix in run one was written against precedent run one filed, so the "
        "store was read after it was written and a run is its own hint (ADR-0031)"
    )
    shown = {
        entry.case_id
        for narration in _narrations(second)
        for entry in narration.remediation.informed_by
    }
    assert shown == {leakage_case.id}, (
        f"run two's fixes were informed by {sorted(shown)}. The store's only "
        "value is cumulative, so a second run that reads nothing is the run "
        "state's lifetime under a second name (ADR-0019)"
    )

    # And the attacker's tool, which is the other reader of the store and the one
    # that has answered "nothing" on every run to date (#38).
    answered = retrieve_precedent(
        DURABLE_PRECEDENT, Family(leakage_case.family), Blinding.over([])
    )
    assert first.result.filing.filed[0].failure in answered

    # Two runs, one entry. `Precedent.key` is a digest of the record, so the same
    # finding filed twice is the same row — a re-run adds to the corpus only when
    # it found something new, and never multiplies one route into copies of itself
    # (`Precedent.key`, #38).
    assert len(DURABLE_PRECEDENT.for_family(Family(leakage_case.family))) == 1


def _narrations(run: Narrated) -> tuple[Narration, ...]:
    """The one target run's narrations, refused rather than defaulted if absent."""
    [target_run] = run.result.target_runs
    return _explained(target_run)


def _explained(target_run: TargetRun) -> tuple[Narration, ...]:
    """One target run's findings, refusing the three readings that carry none.

    Refused rather than defaulted to `()`, because every test in this file that
    reaches for narrations is asserting something about what the two instruments
    produced: a run with no narrator, a target that succeeded at nothing and a
    broken instrument would each make those assertions pass over an empty list
    (ADR-0050).
    """
    narrations = target_run.narrations
    assert isinstance(narrations, tuple), (
        f"this target run explained nothing ({narrations!r}), so an assertion "
        "over its findings would be an assertion over an empty list"
    )
    return narrations


def test_no_targets_findings_become_precedent_for_the_next_targets_fix(
    leakage_case: Case,
) -> None:
    """The within-run cross-target question, decided (ADR-0031).

    Narration runs per target, so a run that filed as it went would put target
    one's findings in front of target two's remediation and make the corpus depend
    on the order targets were run in — an order the bench randomises for the
    blinding's sake (ADR-0011). ADR-0019 says the store cannot be demonstrated
    inside one run; this is that sentence made executable.

    Both targets fail the leakage case, so if the write happened per target the
    second one's fixes would carry the first one's entry.
    """
    result = narrated_run(leakage_case, names=("trivial", "weak"))

    explained = [
        narration
        for target_run in result.target_runs
        for narration in _explained(target_run)
    ]
    assert len({narration.finding.target_name for narration in explained}) == 2, (
        "only one target produced findings, so a write ordered between them could "
        "not have been observed and this test would pass on an empty premise"
    )
    assert all(narration.remediation.informed_by == () for narration in explained), (
        "a fix was informed by precedent filed during its own run, so the corpus "
        "one target's remediation reads depends on which target ran first"
    )
    assert result.filing.filed, "the run filed nothing, so there was no write to place"


def test_this_runs_own_attacker_is_not_shown_what_this_run_filed(
    leakage_case: Case,
) -> None:
    """The other reader of the store, and the sharper half of the same decision.

    `retrieve_precedent` is one of the adaptive attacker's five tools and the
    adaptive layer runs last, so a run that filed before it would hand its own
    attacker its own scored findings. `seed_precedent.py` already names what that
    costs: `A_break` measured on a run that read the store is a reading about the
    attacker *plus the hint*, and a run that hints to itself is one whose
    diagnostic cannot be compared with any other (ADR-0010, ADR-0031).
    """
    recording = Recording()

    result = narrated_run(leakage_case, attacker=recording)

    assert result.filing.filed, (
        "the run filed nothing, so the assertions below would pass against a "
        "store that is never written"
    )
    shown = "\n".join(recording.seen)
    assert f"no precedent recorded against {leakage_case.family} yet" in shown
    for entry in result.filing.filed:
        assert entry.failure not in shown, (
            "this run's attacker was shown a finding this run filed, so its "
            "`A_break` is a reading about the attacker plus its own run's hint"
        )


def narrated_run(
    case: Case,
    names: Sequence[str] = ("trivial",),
    attacker: AttackerCompletion = SCRIPTED_ATTACKER,
    cases: Sequence[Case] | None = None,
) -> CalibrationResult:
    """One case against the named reference agents, narrated, through the entry point.

    Its own runner rather than `test_narration.narrated`, because the two claims
    above need what that helper fixes: more than one target, and a hold on the
    attacker the adaptive layer runs. Everything else is the same call
    (`test_narration.py`, spec seam one).
    """
    with served_references() as references:
        chosen = [served for served in references.served if served.target.name in names]
        assert len(chosen) == len(names)
        return run_calibration(
            cases=list(cases) if cases is not None else [case],
            targets=[served.target for served in chosen],
            attestation=BENCH_ATTESTATION,
            plant_nonce=references.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
            narrator=Narrator(assess=judging(), remediate=remediating()),
            attacker=attacker,
        )


# --- ADR-0010: the write is one-way, and no rate can feel it -----------------


def test_a_run_that_reads_a_stocked_store_measures_what_an_empty_one_measured(
    leakage_case: Case,
) -> None:
    """The invariant most at risk in #38, asserted rather than argued.

    Findings are produced by the judge over the *scored* layer and filed into a
    store the *adaptive* layer reads, so the question a reader has is whether the
    corpus can move a number. It cannot, and this is the demonstration: run two
    reads what run one filed — the assertion above proves the store was not empty
    — and measures the same rate over the same denominator.

    The mechanism is that `TargetRun.rates` divides over `attempts`, and what comes
    back out of the store reaches `suggest_remediation` and `retrieve_precedent`,
    both of which produce prose. No adaptive result enters going the other way
    either: the only door in takes a `Finding`, which is built from an `Attempt`
    (ADR-0010, ADR-0030).
    """
    first = narrated_run(leakage_case)
    second = narrated_run(leakage_case)

    assert first.filing.filed
    assert any(
        narration.remediation.informed_by
        for target_run in second.target_runs
        for narration in _explained(target_run)
    ), (
        "run two read no precedent, so it is not the run this comparison needs "
        "and an unchanged rate would say nothing"
    )

    [before], [after] = first.target_runs, second.target_runs
    assert before.rates == after.rates
    assert before.deterministic_rates == after.deterministic_rates
    assert before.judged_rates == after.judged_rates
    assert [attempt.verdict for attempt in before.attempts] == [
        attempt.verdict for attempt in after.attempts
    ]


def test_the_write_handle_is_the_entry_points_and_the_narrative_pass_has_none() -> None:
    """The write exists in exactly one signature, and a type says so.

    `run_calibration` is annotated with the concrete store because it files;
    `narrate` is annotated with the read-only protocol, which promises no `record`
    at all — so the narrative pass structurally cannot write the store it is about
    to read, and the placement ADR-0031 decided is carried by the types rather
    than by the order of two statements. Widening either annotation is a type
    error before it is a test failure, which is the pattern this repository uses
    wherever an invariant can be carried that way (`test_precedent.py`).
    """
    assert not hasattr(PrecedentStore, "record")
    assert get_type_hints(run_calibration)["precedent"] is DurablePrecedents
    assert get_type_hints(narrate)["precedent"] is PrecedentStore


# --- What a human is handed -------------------------------------------------


def test_a_judged_family_files_nothing_and_the_printed_section_says_why(
    leakage_case: Case, wrongful_commitment_case: Case
) -> None:
    """The refusal reaches a person, which is the only place it counts.

    A run over one deterministic and one judged family files the first and
    withholds the second, and the failure mode this guards against is an operator
    who checks the store, finds nothing from a judged family, and concludes the
    write is broken. So the section names the entry it filed, counts what it
    withheld, and gives the one reason there is (ADR-0004).
    """
    result = narrated_run(leakage_case, cases=[leakage_case, wrongful_commitment_case])

    assert [entry.case_id for entry in result.filing.filed] == [leakage_case.id]
    assert [held.case_id for held in result.filing.judged] == [
        wrongful_commitment_case.id
    ]

    printed = precedent_section(result)
    assert leakage_case.id in printed
    assert wrongful_commitment_case.id in printed
    assert "judged case(s) withheld" in printed
    assert "deterministic findings only" in printed
    # And what the operator most needs to know about the placement: nothing filed
    # here informed a fix this run wrote (ADR-0031).
    assert "after every instrument in this run had read" in printed


def test_a_run_with_nothing_to_file_says_that_rather_than_printing_an_empty_list(
    leakage_case: Case,
) -> None:
    """A gate run's reading, and every run made with no narrative instrument.

    `narrations` is `None` for such a run and it filed nothing — and *nothing to
    file* has to be distinguishable from *the store refused what was offered*,
    which is the same distinction the findings section draws one block up
    (ADR-0030).
    """
    with reference_target(name="trivial") as reference:
        result = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )

    assert result.filing == Filing()
    printed = precedent_section(result)
    assert "nothing filed: this run produced no finding to file" in printed
    assert "refused" in printed, (
        "a run with nothing to file has to be distinguishable from a store that "
        "refused what it was offered"
    )


def test_a_run_over_http_tells_a_poller_what_it_filed_and_what_it_withheld(
    leakage_case: Case,
) -> None:
    """The same statement on the entry point a deployment uses.

    The records are on `record.result`; what this adds is that a poller is *told*,
    for the reason ADR-0030 put the review-queue count on this sentence. The
    failure mode is an operator who checks the store, finds nothing from a judged
    family, and files a bug against the write.
    """
    with watched_reference() as watched:
        app = create_app(
            BenchConfig(
                cases=[leakage_case],
                adaptive=AdaptiveBudget(
                    turns_per_episode=1, episodes_per_family=1, family_count=1
                ),
                adjudicator=None,
                narrator=Narrator(assess=judging(), remediate=remediating()),
                approval_wait_seconds=60.0,
            )
        )
        with TestClient(app) as client:
            bench = cast(BenchRuns, app.state.bench)
            nonce = registered(client, watched)
            started = client.post("/runs", json=a_request(watched.target, nonce)).json()
            record = bench.record(str(started["run_id"]))
            assert record is not None
            client.post(
                f"/runs/{record.run_id}/approval",
                json={"confirmed": True, "identity": "operator"},
            )
            settled(record)

    assert record.status is RunStatus.COMPLETED, record.statement
    assert record.result is not None
    filed = record.result.filing.filed
    assert filed, "the obedient agent leaks, so something has to have been filed"
    assert f"{len(filed)} precedent(s) were filed to the long-term memory" in (
        record.statement
    )
    assert "nothing filed informed a fix this run wrote" in record.statement


def test_nothing_a_run_files_names_the_target_it_measured(leakage_case: Case) -> None:
    """ADR-0011, at the moment the corpus stops being hypothetical.

    Redaction defends one lookup; what defends an accumulating store is that no
    record ever held a target in the first place. `test_precedent.py` asserts this
    of a finding built in a test — this asserts it of a database a *run* wrote,
    which is the caller that did not exist when that test was written and the one
    that has the target's name and url in scope while it writes.

    The database's bytes rather than its rows, and read as bytes because a database
    is not text: a stray column, an index or a freed page would all be outside a
    query against the one table this store writes.
    """
    result = narrated_run(leakage_case)
    [target_run] = result.target_runs

    written = DURABLE_PRECEDENT.store.path.read_bytes()

    assert result.filing.filed, (
        "nothing was filed, so this would pass over an empty file"
    )
    assert result.filing.filed[0].failure.encode("utf-8") in written, (
        "the finding is not in the file, so the assertions below would pass "
        "against a store that records nothing at all"
    )
    assert target_run.target.url.encode("utf-8") not in written
    assert target_run.target.name.encode("utf-8") not in written, (
        "the target's name is in the database a run wrote. It reaches the write "
        "as `Finding.target_name` and nothing may carry it further (ADR-0011)"
    )
    assert {field.name for field in fields(Precedent)} == {
        "family",
        "failure",
        "remediation",
        "case_id",
        "external_id",
    }, (
        "the precedent record's fields changed. A target field here is the one "
        "addition the assertion above could not catch on a run whose target "
        "happened not to be named in any narrative (ADR-0011)"
    )


def test_a_run_whose_every_finding_was_judged_does_not_say_nothing_was_refused(
    wrongful_commitment_case: Case,
) -> None:
    """The third reading, which the other two would contradict between them.

    A run over a judged family only files nothing *and* refuses something, so a
    section that printed the empty line above would tell an operator nothing was
    refused and then list the refusals — which is the confusion the section exists
    against, arrived at from inside it.
    """
    result = narrated_run(wrongful_commitment_case)

    assert not result.filing.filed
    assert result.filing.judged, (
        "no judged finding was produced, so this run is not the one this test is "
        "about and the assertions below would pass on an empty premise"
    )

    printed = precedent_section(result)
    assert "every finding this run produced was judged" in printed
    assert "no finding to file" not in printed, (
        "the section says nothing was refused and then lists the refusals"
    )
    assert wrongful_commitment_case.id in printed
