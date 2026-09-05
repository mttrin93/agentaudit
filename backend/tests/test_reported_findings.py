"""The per-finding section: what a signed document may say about one failure.

Three claims, and each has its own way of going wrong
([ADR-0070](../../docs/adr/0070-a-signed-document-may-carry-a-remediation.md)).

**A remediation sentence quotes nothing of the exchange, and the record refuses one
that does.** ADR-0008's amended line is transferability — a payload is withheld when
its *wording* is the working part — and the prose in this section is written by a
model that was shown the payload. So the rule is held at the record that carries prose
into the artefact, which is the one place holding the case record to check it against,
and not by a sentence in a prompt asking a model not to quote.

**Four readings, four documents.** `narrations` reads four ways (ADR-0050) and the
section states which one holds, because a document that read the same under all four
would put ADR-0050's collapse back into the artefact one layer along.

**The instrument that wrote the prose is named.** An unattributed sentence in a signed
artefact is the thing this project's provenance rules exist to prevent, and the fourth
declared model is what ADR-0030 costed and deliberately did not spend.
"""

from dataclasses import replace

from backend.bench.adaptive.precedent import Precedent
from backend.bench.assembler import (
    NO_NARRATIVE_INSTRUMENT,
    NOTHING_HERE_TO_EXPLAIN,
    AttributedCause,
    Attribution,
    FindingsSection,
    ReportedFinding,
    WithheldProse,
    quotes_the_payload,
    reported_findings,
)
from backend.bench.contract import DeclaredControl, Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, Family
from backend.bench.narration import BrokenInstrument, Narration, NarrativeFailure
from backend.bench.reproducibility import Reproducibility
from backend.bench.scanner import Scan, control_claiming
from backend.graph.runstate import Attempt
from backend.tests.conftest import A_FIX, a_narration

A_QUOTED_HALF = 80
"""How much of a payload this suite insists is already too much to publish.

A literal here rather than a multiple of `PAYLOAD_QUOTE_FLOOR`, and that is the
point of the assertion: written as a multiple it would move with the constant it is
supposed to pin, and a floor raised to any value at all would keep this file green.
Eighty characters is a clause and a half of a committed payload — enough to lift and
point at a target that was never in this repository, which is the property ADR-0008's
amended line names.
"""


def a_case(library: list[Case], case_id: str = "data-leakage-001") -> Case:
    """One committed case record, by id."""
    return next(case for case in library if case.id == case_id)


def test_a_finding_carries_the_judges_reason_and_the_tools_fix_apart(
    library: list[Case],
) -> None:
    # ADR-0069 split the two: the judge answers *why it failed* and the tool answers
    # *what to change*. A section printing one field would be the state that decision
    # ended, arriving at the surface instead of at the instrument.
    case = a_case(library)
    narration = a_narration(case_id=case.id, family=Family.DATA_LEAKAGE)
    reported = ReportedFinding.of(narration, _attribution(narration, case), case)

    assert reported.reason == narration.finding.narrative.reason
    assert reported.fix == narration.remediation.fix
    assert reported.withheld == ()


def test_prose_that_quotes_the_case_payload_is_withheld_and_the_finding_still_prints(
    library: list[Case],
) -> None:
    # The disclosure answer, as a mechanism. A model shown the payload can reproduce
    # it, and a document that travels is the worst possible place for a working
    # attack (ADR-0008) — so the sentence is withheld and the finding is not, because
    # a finding dropped for its prose would take the case id, the family and the
    # attributed cause with it.
    case = a_case(library)
    narration = a_narration(
        case_id=case.id, family=Family.DATA_LEAKAGE, fix=case.payload[0]
    )
    reported = ReportedFinding.of(narration, _attribution(narration, case), case)

    assert reported.withheld == (WithheldProse.FIX,)
    assert case.payload[0] not in reported.fix
    assert reported.reason == narration.finding.narrative.reason
    assert reported.case_id == case.id


def test_no_committed_payload_survives_the_floor_and_no_honest_sentence_trips_it(
    library: list[Case],
) -> None:
    """The measurement that licenses `PAYLOAD_QUOTE_FLOOR`, at both ends.

    A floor is a trade and a number nobody measured is a number somebody liked. Too
    high and half a payload travels; too low and every honest fix about a family is
    withheld, because a reason and the payload it describes share ordinary English.
    So both ends are checked against the library this bench actually ships.
    """
    for case in library:
        assert quotes_the_payload(case.script, case), (
            f"{case.id}'s own payload does not trip the floor, so a model that "
            "reproduced it verbatim would put it in a document that travels"
        )
        for turn in case.payload:
            text = " ".join(turn.split())
            assert quotes_the_payload(turn, case), (
                f"a turn of {case.id} does not trip the floor. A scripted case sends "
                "one turn at a time, and one turn's wording is what transfers"
            )
            # And *half* a turn trips it, which is the end a whole-turn rule would
            # leave open: a model that trimmed the last clause has reproduced the
            # phrasing all the same, and the floor is what makes that unavailable.
            if len(text) > A_QUOTED_HALF:
                assert quotes_the_payload(
                    f"the reply repeated: {text[: len(text) // 2]}", case
                ), (
                    f"half a turn of {case.id} passes the floor, so a model that "
                    "quoted most of a payload would put most of it in a document "
                    "that travels"
                )

    # And the other end: sentences written *about* a case, in the shape the two
    # instruments write them, pass. These are the fixtures the suite narrates with.
    written = (
        "The reply carried the configured secret back out.",
        A_FIX,
        "The agent followed an instruction embedded in a document it summarised.",
        "Add an output filter that redacts the configured secret before replying.",
    )
    for case in library:
        for sentence in written:
            assert not quotes_the_payload(sentence, case), (
                f"an ordinary sentence about a failure trips the floor on {case.id}, "
                "so this rule would withhold honest prose rather than a quotation"
            )


# --- The four readings, and four documents (ADR-0050, ADR-0070 §4) -----------


def test_the_section_states_which_of_the_four_readings_of_narrations_holds() -> None:
    # Four facts and four sentences. A section that read the same under all four
    # would put ADR-0050's collapse back into the artefact one layer along: `None`
    # is nobody declared an instrument, `()` is a target that succeeded at nothing,
    # a tuple is every failure explained, and a `NarrativeFailure` is the
    # instruments having run and broken.
    broke = NarrativeFailure(
        broken=BrokenInstrument.JUDGE_UNREADABLE,
        detail="the model answered with prose and no labelled lines",
        explained=1,
        successes=3,
    )
    stated = {
        reading: FindingsSection(reported=reading).stated()
        for reading in (None, (), broke)
    }

    assert stated[None] == NO_NARRATIVE_INSTRUMENT
    assert stated[()] == NOTHING_HERE_TO_EXPLAIN
    assert stated[broke] == broke.stated()
    assert len(set(stated.values())) == 3

    # And every one of the four is *not reproducible*, which is not a caller's field:
    # a model wrote the prose, and that is the label ADR-0017 already has for the
    # class. No third evidentiary class is invented here.
    for reading in (None, (), broke):
        assert (
            FindingsSection(reported=reading).reproducibility
            is Reproducibility.NOT_REPRODUCIBLE
        )


def test_a_section_holding_findings_says_how_many_and_carries_no_figure(
    library: list[Case],
) -> None:
    case = a_case(library)
    narration = a_narration(case_id=case.id, family=Family.DATA_LEAKAGE)
    reported = ReportedFinding.of(narration, _attribution(narration, case), case)
    section = FindingsSection(reported=(reported,))

    assert section.findings == (reported,)
    assert "1 failure(s) of the six explained" in section.stated()
    assert Reproducibility.NOT_REPRODUCIBLE.stated() in section.stated()


def test_a_fix_written_against_precedent_says_so_and_carries_no_precedent_prose(
    library: list[Case],
) -> None:
    """ADR-0019's claim, as the two ids a reader can check rather than as a promise.

    The precedents' own `failure` and `remediation` are a **different target's**
    finding and a different target's fix, and this document is about one target: the
    ids travel and the prose does not (ADR-0070 §2).
    """
    case = a_case(library)
    earlier = Precedent(
        family=Family.DATA_LEAKAGE,
        failure="a different operator's agent read its configuration out loud",
        remediation="a different operator's fix",
        case_id="data-leakage-000",
        external_id="LLM02:2026",
    )
    narration = a_narration(case_id=case.id, family=Family.DATA_LEAKAGE)
    narration = replace(
        narration,
        remediation=replace(narration.remediation, informed_by=(earlier,)),
    )
    reported = ReportedFinding.of(narration, _attribution(narration, case), case)

    assert reported.informed_by == ("data-leakage-000",)
    assert earlier.failure not in reported.stated()
    assert earlier.remediation not in reported.stated()
    assert "data-leakage-000" in reported.stated()


# --- The section, built from a run's own attempts and the scan ---------------


def test_every_narration_becomes_one_reported_finding_attributed_against_the_scan(
    library: list[Case],
) -> None:
    """The join this section is assembled by: one narration, one attempt, one case.

    Narrations are one per succeeded attempt in the order they were made
    (`narrate_successes`), so the attribution each one carries is derived from *that*
    attempt's case record and the scan — never from a family name, and never from a
    case id looked up once and reused across two constructions.
    """
    case = a_case(library)
    attempts = (
        _succeeded(case, index=0),
        _succeeded(case, index=1),
        _resisted(case, index=2),
    )
    narrations = (
        a_narration(case_id=case.id, family=Family.DATA_LEAKAGE),
        a_narration(case_id=case.id, family=Family.DATA_LEAKAGE, fix="A second fix."),
    )

    section = reported_findings(
        narrations, attempts, [case], Scan(declared=(DeclaredControl.OUTPUT_FILTER,))
    )

    assert [finding.fix for finding in section.findings] == [A_FIX, "A second fix."]
    for finding in section.findings:
        assert finding.attribution.reading is AttributedCause.DECLARED_AND_DEFEATED
        assert finding.case_id == case.id
    # The resisted attempt produced no narration and reaches no finding: an
    # attribution over one would print *the bench broke this control* over an
    # attempt that broke nothing (ADR-0068).
    assert len(section.findings) == 2


def test_the_three_readings_that_carry_no_finding_pass_through_unchanged(
    library: list[Case],
) -> None:
    # `None`, `()` and a `NarrativeFailure` are three facts about a run and not three
    # spellings of an empty section, so the join hands each of them on rather than
    # flattening it into a tuple nobody chose (ADR-0050).
    broke = NarrativeFailure(
        broken=BrokenInstrument.REPLY_UNFINISHED,
        detail="the provider did not say it finished",
        explained=0,
        successes=2,
    )
    case = a_case(library)
    for reading in (None, (), broke):
        section = reported_findings(reading, (), [case], Scan(declared=()))
        assert section.reported == reading
        assert section.findings == ()


def _succeeded(case: Case, index: int) -> Attempt:
    return _attempt(case, index, Verdict.SUCCEEDED)


def _resisted(case: Case, index: int) -> Attempt:
    return _attempt(case, index, Verdict.RESISTED)


def _attempt(case: Case, index: int, verdict: Verdict) -> Attempt:
    """One recorded attempt on that case, built rather than measured."""
    return Attempt(
        case_id=case.id,
        family=case.family,
        target_name="customer-agent",
        index=index,
        transcripts=(
            Transcript(
                url="https://customer-agent.invalid/messages",
                sent={"message": "payload", "session_id": "s"},
                status_code=200,
                received={"reply": "reply"},
            ),
        ),
        verdict=verdict,
        verdict_class=case.verdict_class,
        transform=case.transform,
    )


def _attribution(narration: Narration, case: Case) -> Attribution:
    """One derived reading for that case, built rather than scanned.

    Built because what is under test here is the record that carries prose, and a
    scan would only decide which of the three readings it carries — which is
    `test_attribution.py`'s subject and settled by ADR-0068.
    """
    return Attribution(
        case_id=case.id,
        family=Family.DATA_LEAKAGE,
        reading=AttributedCause.NOT_DECLARED,
        transform=case.transform,
        control=control_claiming(case.family),
    )
