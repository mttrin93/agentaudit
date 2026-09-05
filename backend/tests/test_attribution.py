"""The attributed cause: derived from the case record and the scan, and not judged.

Four claims, and they fail in different ways.

**It is derived, and it is a reading of one failure**
([ADR-0068](../../docs/adr/0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md)).
What holds the first here is the signature: no parameter a model could arrive
through, and the same answer every time. What holds the second is `JudgeBrief.about`'s
pair of refusals, made again — an attempt joined to the wrong case, and an attempt
that did not succeed, which would print *the bench broke this control* over an attempt
that broke nothing. The `isinstance` beside them is ADR-0010's wall as a runtime fact
rather than a type check nobody can drive red.

**The third reading is not a spelling of the second.** Five of the nine families have
no declared control at all, and reading them as `NOT_DECLARED` would report an absence
nobody could have declared — ADR-0005's rejected score, which deducted points for
controls a target did not claim, arriving a second time through a finding. This is the
red the ticket asked to see first, and the failing test is the one directly below.

**Nothing here writes into a rate.** Import-level over every module that computes a
figure and the two that write one down, in the pattern `test_payload.py` sets — and
over the *transitive* imports of the two instruments, in the pattern `test_precedent.py`
sets, because a scan the judge can see is the blinding ADR-0004 rests on reopened by
another route. The structural half is the field list: there is no field a figure could
arrive in.

**And the sentence says something the family name does not.** `family_claimed_by` is
1:1 over the four controls, so a record that only named the control would be a relabel.
What it names instead is the declaration state and the **transform** (ADR-0051) — the
same case under two scans reads two ways, and the same case in two constructions reads
two ways.
"""

from dataclasses import replace
from pathlib import Path
from typing import get_type_hints

import pytest

from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.assembler import AttributedCause, Attribution, attributed_cause
from backend.bench.contract import DeclaredControl, Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import (
    AnyFamily,
    Case,
    ElectiveFamily,
    Family,
    Transform,
)
from backend.bench.scanner import (
    CONTROL_CHECKLIST,
    Scan,
    control_claiming,
    family_claimed_by,
)
from backend.graph.runstate import Attempt
from backend.tests.conftest import (
    BENCH,
    SERIALISERS,
    imports_of,
    reachable_from,
)


def a_success(case: Case, verdict: Verdict = Verdict.SUCCEEDED) -> Attempt:
    """One recorded attempt on that case. Built rather than measured.

    The failure an attribution is *of*. Three fields are read off it — the case it
    was made against, its verdict, and nothing else — so those are what a test here
    varies, and an attempt carrying a rate would not fit through the signature.
    """
    return Attempt(
        case_id=case.id,
        family=case.family,
        target_name="target",
        index=0,
        transcripts=(
            Transcript(
                url="https://target.invalid/messages",
                sent={"message": "payload", "session_id": "s"},
                status_code=200,
                received={"reply": "reply"},
            ),
        ),
        verdict=verdict,
        verdict_class=case.verdict_class,
        transform=case.transform,
    )


def test_a_family_no_control_claims_attributes_to_no_control(
    wrongful_commitment_case: Case,
) -> None:
    # Five of the nine families have no declared control at all — the two judged
    # ones and the three elective ones — and the honest answer for them is its own
    # member. Read as `NOT_DECLARED` it would report an absence nobody could have
    # declared, which is the ADR-0005 defect (a target penalised for not claiming a
    # control the checklist does not hold) arriving through a finding.
    attributed = attributed_cause(
        a_success(wrongful_commitment_case),
        wrongful_commitment_case,
        Scan(declared=tuple(DeclaredControl)),
    )

    assert attributed.reading is AttributedCause.NO_CONTROL_CLAIMS_THIS_FAMILY
    assert attributed.control is None


def test_a_control_the_operator_declared_attributes_to_declared_and_defeated(
    leakage_case: Case,
) -> None:
    # The sentence this ticket buys. A control the operator claimed and the bench
    # broke is a different reading to an engineer, and a very different one to a
    # procurement reader, than a family nobody ever claimed to defend.
    attributed = attributed_cause(
        a_success(leakage_case),
        leakage_case,
        Scan(declared=(DeclaredControl.OUTPUT_FILTER,)),
    )

    assert attributed.reading is AttributedCause.DECLARED_AND_DEFEATED
    assert attributed.control is DeclaredControl.OUTPUT_FILTER


def test_a_control_that_claims_this_family_and_was_not_declared_says_so(
    leakage_case: Case,
) -> None:
    # The other half, and it names the control the target did not claim: a reader
    # meeting this one learns that the checklist holds a defence for this failure
    # and the operator claimed none. The absence is still not a finding — nothing
    # here is subtracted from anything (ADR-0005) — it is a state a sentence names.
    attributed = attributed_cause(
        a_success(leakage_case),
        leakage_case,
        Scan(declared=(DeclaredControl.INPUT_CHECK,)),
    )

    assert attributed.reading is AttributedCause.NOT_DECLARED
    assert attributed.control is DeclaredControl.OUTPUT_FILTER


def test_no_control_claims_this_family_cannot_be_written_with_a_control() -> None:
    # The third member is not a spelling of the other two, and the type is where
    # that holds: a record naming a control and saying no control claims its family
    # would put a judged failure under a defence the checklist does not hold.
    with pytest.raises(ValueError, match="claims no control and names one"):
        Attribution(
            case_id="wrongful-commitment-001",
            family=Family.WRONGFUL_COMMITMENT,
            reading=AttributedCause.NO_CONTROL_CLAIMS_THIS_FAMILY,
            transform=Transform.PLAIN,
            control=DeclaredControl.INPUT_CHECK,
        )


@pytest.mark.parametrize(
    "reading",
    [AttributedCause.DECLARED_AND_DEFEATED, AttributedCause.NOT_DECLARED],
)
def test_a_declaration_state_without_a_control_is_refused(
    reading: AttributedCause,
) -> None:
    # Both of the other two are statements *about a control*, so a record making one
    # without naming it is a sentence a reader cannot check against the scan.
    with pytest.raises(ValueError, match="names no control"):
        Attribution(
            case_id="data-leakage-001",
            family=Family.DATA_LEAKAGE,
            reading=reading,
            transform=Transform.PLAIN,
        )


def test_a_control_that_does_not_claim_this_family_is_refused() -> None:
    # The one thing `family_claimed_by` cannot stop a caller doing by hand. An
    # attribution filed under the wrong control would let a target's input check be
    # reported defeated by a data-leakage case, which is the declared-and-defeated
    # headline made unreadable in the direction nobody checks.
    with pytest.raises(ValueError, match="does not claim"):
        Attribution(
            case_id="data-leakage-001",
            family=Family.DATA_LEAKAGE,
            reading=AttributedCause.DECLARED_AND_DEFEATED,
            transform=Transform.PLAIN,
            control=DeclaredControl.INPUT_CHECK,
        )


def test_the_sentence_says_two_things_the_family_name_does_not(
    leakage_case: Case,
) -> None:
    # `family_claimed_by` is 1:1 over the four controls, so naming the control is
    # close to relabelling the family and is not what this record buys. What it buys
    # is the **declaration state** — the same family, the same case, two scans, two
    # sentences — and a place for which transform got in (ADR-0051).
    encoded = replace(
        leakage_case,
        id=f"{leakage_case.id}-base64",
        transform=Transform.BASE64,
        derived_from=leakage_case.id,
    )
    declared = attributed_cause(
        a_success(leakage_case),
        leakage_case,
        Scan(declared=(DeclaredControl.OUTPUT_FILTER,)),
    ).stated()
    undeclared = attributed_cause(
        a_success(leakage_case), leakage_case, Scan(declared=())
    ).stated()
    variant = attributed_cause(
        a_success(encoded), encoded, Scan(declared=(DeclaredControl.OUTPUT_FILTER,))
    ).stated()

    assert declared != undeclared
    assert declared != variant
    assert Transform.PLAIN.stated() in declared
    assert Transform.BASE64.stated() in variant


def test_a_family_no_control_claims_says_so_and_names_no_defence(
    disclosure_denial_case: Case,
) -> None:
    # The honest answer for five of the nine families, and it must not read as an
    # accusation: nothing was declared because nothing could have been.
    stated = attributed_cause(
        a_success(disclosure_denial_case),
        disclosure_denial_case,
        Scan(declared=tuple(DeclaredControl)),
    ).stated()

    assert not [one for one in DeclaredControl if one.value in stated]
    assert "no control in the checklist claims" in stated


# --- Nothing attributed writes into a rate, and no instrument writes it -------

THE_SCORED_SIDE = (
    BENCH / "scorer.py",
    BENCH / "gate.py",
    BENCH / "bar.py",
    BENCH / "calibration.py",
    BENCH / "measurability.py",
    *SERIALISERS,
)
"""Every module that computes a figure or reads one, plus the ones that publish it.

The five named here are where the arithmetic is — the rate and its interval, `D`,
the band cuts, the reason a family could not be measured, and the check that turns
a band into a red build step. `SERIALISERS` is `test_payload.py`'s own list of the
modules that turn a result into bytes and into the document a human reads, shared
from `conftest.py` rather than copied, so a split of `rendering/` cannot leave one
of the two walls covering a surface the other one does.

`assembler.py` is deliberately absent: it is where the attribution is derived, so
an import check over it would assert nothing. What holds the line there is the
field list below — the record carries no number for any of these to read.
"""


@pytest.mark.parametrize("source", THE_SCORED_SIDE, ids=lambda one: one.name)
def test_nothing_that_computes_or_prints_a_figure_imports_an_attribution(
    source: Path,
) -> None:
    # An attributed cause is prose about a verdict. No rate, band, interval or `D`
    # may read it, and an override annotates one of those without moving it (D13,
    # ADR-0006). Import-level, because the tempting version is the one that reaches
    # for the declaration state while weighting a band — and it would be one import.
    named = sorted(name for name in imports_of(source) if "attribut" in name.lower())

    assert not named, (
        f"{source.name} imports {named}. Attribution is prose about one verdict and "
        "nothing that computes or publishes a figure may read it (D13, ADR-0006). "
        "Printing it in the signed document is #112's ticket and has a price to pay "
        "first"
    )


@pytest.mark.parametrize("source", (BENCH / "judge.py", BENCH / "adjudication.py"))
def test_neither_instrument_can_see_what_the_operator_declared(source: Path) -> None:
    # A `JudgeBrief` carrying the declaration state would be the blinding channel
    # reopened by a new route (ADR-0004): the judge would be reading a target's own
    # claims about itself while writing prose the κ figure polices.
    named = sorted(
        name
        for name in reachable_from(source)
        if "attribut" in name.lower() or "assembler" in name.lower()
    )

    assert not named, (
        f"{named} is reachable from {source.name}. An attributed cause is derived "
        "from the scan, and a scan the judge can see is the blinding it rests on "
        "(ADR-0004)"
    )


def test_the_record_holds_no_number_and_no_free_text() -> None:
    # The structural half of "nothing here writes into a rate": there is no field a
    # figure could arrive in, so the prohibition above is about routes rather than
    # about arithmetic somebody might write. And no field a model could fill: every
    # value is read off the case record or off the closed checklist, which is what
    # makes this derived rather than a fourth instrument (#64's precedent, ADR-0011).
    hints = get_type_hints(Attribution)

    assert hints == {
        "case_id": str,
        "family": AnyFamily,
        "reading": AttributedCause,
        "transform": Transform,
        "control": DeclaredControl | None,
    }
    assert len(AttributedCause) == 3


def test_the_derivation_takes_records_and_nothing_that_could_write_prose() -> None:
    # `Finding.of`'s argument, restated: there is no parameter here through which a
    # model could supply the reading, so the only way to make this judged is to
    # change the signature — which is the difference between a constraint and a
    # convention. An `AdaptiveEpisode` has no case record and no scan, so it cannot
    # arrive through either one (ADR-0010).
    hints = get_type_hints(attributed_cause)

    assert hints == {
        "attempt": Attempt,
        "case": Case,
        "scanned": Scan,
        "return": Attribution,
    }


def test_the_same_case_and_scan_always_give_the_same_answer(
    injection_case: Case,
) -> None:
    # Derived means re-derivable: a reader holding the case record and the
    # registration recomputes this without running anything, which is the property
    # #64 asked an instrument to earn by measurement and this does not have to
    # (ADR-0004).
    scanned = Scan(declared=(DeclaredControl.INPUT_CHECK,))
    attempt = a_success(injection_case)

    assert attributed_cause(attempt, injection_case, scanned) == attributed_cause(
        attempt, injection_case, scanned
    )


def test_the_lookup_is_the_join_read_backwards_and_not_a_second_table() -> None:
    # `family_claimed_by` has no fallback branch so that a fifth control fails the
    # type check rather than joining against nothing. A hand-written reverse table
    # would have given that fifth control a family in one direction and not the
    # other, silently — so this one is derived from the checklist and the round trip
    # is what says so.
    assert {
        control: control_claiming(family_claimed_by(control))
        for control in CONTROL_CHECKLIST
    } == {control: control for control in CONTROL_CHECKLIST}

    claimed = {family_claimed_by(control) for control in CONTROL_CHECKLIST}
    unclaimed = [
        family for family in (*Family, *ElectiveFamily) if family not in claimed
    ]

    # Five of the nine: the two judged families and the three elective ones.
    assert len(unclaimed) == 5
    assert all(control_claiming(family) is None for family in unclaimed)


# --- One failure, and the record cannot be built without one ------------------


def test_an_attempt_that_did_not_succeed_has_no_cause_to_attribute(
    leakage_case: Case,
) -> None:
    # `DECLARED_AND_DEFEATED` says the bench broke a control the operator declared,
    # and only a succeeded verdict establishes that. Derived from the case record and
    # the scan is what the *reading* is; which failure it is a reading of comes off
    # the attempt, exactly as `ScannedControl.broken_by` does.
    with pytest.raises(ValueError, match="did not succeed"):
        attributed_cause(
            a_success(leakage_case, verdict=Verdict.RESISTED),
            leakage_case,
            Scan(declared=(DeclaredControl.OUTPUT_FILTER,)),
        )


def test_an_attempt_briefed_against_another_case_is_refused(
    leakage_case: Case, injection_case: Case
) -> None:
    # `JudgeBrief.about`'s refusal, one type over and for the same reason: an
    # attribution written against the wrong record would name a transform the
    # attempt never sent and a family it never counted towards.
    with pytest.raises(ValueError, match="was attributed against case"):
        attributed_cause(a_success(leakage_case), injection_case, Scan(declared=()))


def test_nothing_the_adaptive_layer_produces_can_be_attributed(
    leakage_case: Case,
) -> None:
    # The annotation is the constraint and this is the same constraint at runtime,
    # so ADR-0010's wall is closed by a test as well as by a type check. An
    # `AdaptiveEpisode` is what an episode leaves behind, and it is not an `Attempt`.
    episode = AdaptiveEpisode(
        family=Family.DATA_LEAKAGE,
        target_name="target",
        outcome=EpisodeOutcome.BROKEN,
        turns=3,
    )

    with pytest.raises(TypeError, match="AdaptiveEpisode"):
        attributed_cause(episode, leakage_case, Scan(declared=()))  # type: ignore[arg-type]
