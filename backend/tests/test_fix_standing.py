"""Two labels on a fix and no third — and the change one of them is a proof of.

[ADR-0073](../../docs/adr/0073-two-labels-on-a-fix-and-no-third.md), driven at three
seams:

* `fix_standing.FixStanding` — the closed pair, the sentence each member prints, and
  the refusals that make *proven with nothing behind it* unrepresentable.
* `proving.standing_for` — the one constructor of a proven standing, and the four
  outcomes it reads. Exactly one of them earns the word.
* `assembler.ReportedFinding` — the refusal the ticket names in as many words: **a fix
  from a target with no checkout cannot be proven**.

**The load-bearing claim is the label and not the diff.** Blurring proven and proposed
would put an untested assertion in front of a procurement reader under the word
*proven*, which is the hand-filled questionnaire
[ADR-0001](../../docs/adr/0001-procurement-not-regulator-is-the-buyer.md)
exists to displace, reproduced inside the tool meant to replace it.
"""

from __future__ import annotations

import pytest

from backend.bench.assembler import (
    AttributedCause,
    Attribution,
    ReportedFinding,
)
from backend.bench.fix_standing import (
    MAX_PUBLISHED_DIFF_LINES,
    NO_PATCH_WAS_APPLIED,
    NOT_PROVEN,
    FixStanding,
    FixStandingReading,
    unified,
)
from backend.bench.library import Case, Family
from backend.bench.payload import document
from backend.bench.proving import (
    PatchProof,
    PostPatchAttempt,
    PostPatchOutcome,
    standing_for,
)
from backend.bench.rendering import render
from backend.bench.scanner import control_claiming
from backend.bench.source_anchor import (
    NOT_RUN_WHERE_THE_CODE_IS,
    SourceAnchor,
    SourceAnchorReading,
)
from backend.bench.throwaway import Patch
from backend.tests.conftest import a_narration
from backend.tests.test_payload import a_payload, explaining

BEFORE = "def answer(message):\n    return message\n"
"""The file as the bench read it off the caller's checkout."""

AFTER = (
    "def answer(message):\n"
    "    if 'ignore previous' in message:\n"
    "        return ''\n"
    "    return message\n"
)
"""What the operator's own patch puts in its place. A whole file (ADR-0072 §2)."""

ANCHORED = SourceAnchor(
    reading=SourceAnchorReading.ANCHORED, path="app/agent.py", line=1
)


def a_proof(
    outcome: PostPatchOutcome = PostPatchOutcome.NO_LONGER_SUCCEEDS,
    contents: str = AFTER,
) -> PatchProof:
    """One proof, as `prove_patch` returns one."""
    return PatchProof(
        patch=Patch(path="app/agent.py", contents=contents),
        re_attempt=PostPatchAttempt(
            case_id="indirect-injection-001",
            family=Family.INDIRECT_PROMPT_INJECTION,
            target_name="patched",
            outcome=outcome,
            patched="app/agent.py",
        ),
        post_patch_calls=1,
    )


def a_finding(
    library: list[Case],
    anchor: SourceAnchor = NOT_RUN_WHERE_THE_CODE_IS,
    standing: FixStanding = NOT_PROVEN,
) -> ReportedFinding:
    case = next(one for one in library if one.id == "data-leakage-001")
    narration = a_narration(case_id=case.id, family=Family.DATA_LEAKAGE)
    return ReportedFinding.of(
        narration,
        Attribution(
            case_id=case.id,
            family=Family.DATA_LEAKAGE,
            reading=AttributedCause.NOT_DECLARED,
            transform=case.transform,
            control=control_claiming(case.family),
        ),
        case,
        anchor,
        standing,
    )


# --- Two labels, and the third is unrepresentable ----------------------------


def test_a_fix_carries_one_of_two_labels_and_there_is_no_third() -> None:
    """The closed pair is the whole mechanism (ADR-0073 §1).

    A third reading — *partly proven*, *proven for this payload*, *likely* — is the
    middle state that lets an untested change be read as a tested one, and the pair is
    what makes it a source edit to a closed enum rather than a value somebody passes.
    """
    assert set(FixStandingReading) == {
        FixStandingReading.PROVEN,
        FixStandingReading.PROPOSED,
    }
    assert [one.value for one in FixStandingReading] == ["proven", "proposed"]


def test_a_fix_never_tested_says_so_rather_than_reading_as_one_that_failed() -> None:
    """`proven=False` and *we did not test this* are the same bit and two sentences.

    The enum is what stops the second being read as the first, and the sentence under
    it is what says which of them holds — a label with nothing under it is a label a
    reader completes themselves (ADR-0073 §1).
    """
    said = NOT_PROVEN.stated()

    assert NOT_PROVEN.reading is FixStandingReading.PROPOSED
    assert said.startswith("proposed —")
    assert "has not been shown to close the case" in said
    assert NO_PATCH_WAS_APPLIED in said
    # And the reason is where the bench ran, not a judgement about the fix.
    assert "somebody else's server that this bench cannot restart" in said
    assert "not about the fix" in said


def test_a_proven_label_with_no_patched_file_under_it_is_refused() -> None:
    """*Proven* means a patch was written and a case re-run, so a proven standing that
    can name no file is a claim with no act behind it (ADR-0073 §2)."""
    with pytest.raises(ValueError, match="named no file it patched"):
        FixStanding(reading=FixStandingReading.PROVEN, evidence="it worked")

    with pytest.raises(ValueError, match="change to nothing"):
        FixStanding(
            reading=FixStandingReading.PROPOSED, evidence="untested", diff="- a\n+ b"
        )


# --- A fix from a target with no checkout cannot be proven -------------------


def test_a_fix_from_a_target_with_no_checkout_cannot_be_proven(
    library: list[Case],
) -> None:
    """The ticket's own red test, at the record that publishes both facts.

    A plain hosted endpoint is somebody else's server: nothing in any checkout is
    known to be the thing that answered, so there is nothing to patch and nothing to
    re-serve, and every anchor reading but `ANCHORED` is a run with no file
    (ADR-0071 §3). A finding that paired *proven* with one of them would be the
    self-graded claim ADR-0001 exists to displace.
    """
    proven = FixStanding(
        reading=FixStandingReading.PROVEN,
        evidence="it no longer succeeds",
        patched="app/agent.py",
    )

    for reading in SourceAnchorReading:
        if reading is SourceAnchorReading.ANCHORED:
            continue
        with pytest.raises(ValueError, match="reported proven"):
            a_finding(library, SourceAnchor(reading=reading), proven)

    # And the one reading that names a file the bench opened inside the checkout is
    # the one that may carry it.
    assert a_finding(library, ANCHORED, proven).standing is proven


def test_every_finding_of_a_run_that_patched_nothing_reads_proposed(
    library: list[Case],
) -> None:
    """The default is the untested reading, on the anchor's own terms: a field a
    caller forgot to fill reads as *this was not tested* rather than as a proof it
    declined to mention."""
    reported = a_finding(library)

    assert reported.standing is NOT_PROVEN
    # And the one-line form carries the label, because a summary that printed *what to
    # change* without saying whether it was ever tested is the blur itself.
    assert "This fix is proposed —" in reported.stated()


# --- Exactly one of the four outcomes earns the word -------------------------


def test_only_a_case_that_no_longer_succeeds_earns_the_word_proven() -> None:
    """One outcome of four, and the other three carry the re-run's own sentence — how
    *tested and found wanting* stays distinguishable from *never tested* under one
    label (ADR-0073 §1)."""
    proven = standing_for(a_proof(), BEFORE)

    assert proven.reading is FixStandingReading.PROVEN
    assert proven.stated().startswith("proven — this bench applied the change")
    # The claim is about one case and says so, in the re-run's own words (ADR-0072 §5).
    assert "deliberately not about its family" in proven.stated()
    assert "thirty attempts" in proven.stated()

    for outcome in PostPatchOutcome:
        if outcome is PostPatchOutcome.NO_LONGER_SUCCEEDS:
            continue
        standing = standing_for(a_proof(outcome), BEFORE)
        assert standing.reading is FixStandingReading.PROPOSED, outcome
        # Each carries its own reason, and none of the three is worded here.
        assert a_proof(outcome).re_attempt.stated() in standing.stated(), outcome

    tested = standing_for(a_proof(PostPatchOutcome.STILL_SUCCEEDS), BEFORE)
    untried = standing_for(a_proof(PostPatchOutcome.NOT_RE_ATTEMPTED), BEFORE)
    assert "was not closed by it" in tested.stated()
    assert "untested rather than tested and found wanting" in untried.stated()
    assert tested.stated() != untried.stated()


# --- The diff, computed here and never by a surface --------------------------


def test_the_change_travels_as_a_unified_diff_of_the_file_the_patch_replaced() -> None:
    """Rendered from the patch the run recorded rather than recomputed client-side,
    which is `api/report.ts`'s standing rule and, for a diff, the disclosure answer
    too: what a reader is shown is what this bench decided to publish (ADR-0073 §3)."""
    standing = standing_for(a_proof(), BEFORE)

    assert standing.patched == "app/agent.py"
    assert standing.diff.startswith("--- a/app/agent.py\n+++ b/app/agent.py")
    assert "+    if 'ignore previous' in message:" in standing.diff
    assert " def answer(message):" in standing.diff
    # And no line of the file that the change did not touch or sit beside.
    assert "return message" in standing.diff


def test_a_change_longer_than_this_document_publishes_is_stated_and_not_truncated() -> (
    None
):
    """Half a diff is a change a reader would take for the whole of one, and the half
    that is missing is the half its author would want read (ADR-0073 §3)."""
    enormous = "\n".join(f"line {index}" for index in range(MAX_PUBLISHED_DIFF_LINES))
    standing = standing_for(a_proof(contents=enormous), BEFORE)

    assert standing.diff == ""
    assert "longer than this document publishes" in standing.stated()
    # The label is unchanged: what was proven was proven.
    assert standing.reading is FixStandingReading.PROVEN


def test_a_patch_that_changes_nothing_publishes_no_diff_and_no_excuse() -> None:
    """Two ways of publishing no diff, and they are different facts about a patch."""
    unchanged = standing_for(a_proof(contents=BEFORE), BEFORE)

    assert unchanged.diff == ""
    assert "longer than this document publishes" not in unchanged.stated()
    assert unified(BEFORE, BEFORE, "app/agent.py") == ""


# --- On both surfaces: the signed document ------------------------------------


def test_the_label_and_the_change_reach_the_signed_document(
    library: list[Case],
) -> None:
    """Both surfaces print one claim about one fix, so the document carries the
    reading as a name, the sentence as the record wrote it, and the change as this
    bench computed it (ADR-0068 §3, ADR-0073 §3)."""
    proven = standing_for(a_proof(), BEFORE)
    body = document(
        a_payload(
            result=explaining(
                library, source_anchor=ANCHORED, standings={"data-leakage-001": proven}
            )
        )
    )["findings"]
    [finding] = body["findings"]

    assert finding["fix_standing"]["reading"] == "proven"
    assert finding["fix_standing"]["stated"] == proven.stated()
    assert finding["fix_standing"]["patched"] == "app/agent.py"
    assert finding["fix_standing"]["diff"] == proven.diff

    # And the reading is the record's own and not a constant: a run that patched
    # nothing carries the other member under the same key.
    untested = document(a_payload(result=explaining(library)))["findings"]
    assert untested["findings"][0]["fix_standing"]["reading"] == "proposed"
    assert untested["findings"][0]["fix_standing"]["patched"] is None
    assert untested["findings"][0]["fix_standing"]["diff"] == ""


def test_the_document_a_reader_holds_says_what_proven_asserts_and_what_it_does_not(
    library: list[Case],
) -> None:
    """The sentence a human reads, above the blocks rather than inside each: a reader
    who took *proven* for *this family is closed* would have been handed the stronger
    of two claims by a label (#109, ADR-0073 §1)."""
    markdown = render(
        a_payload(
            result=explaining(
                library,
                source_anchor=ANCHORED,
                standings={"data-leakage-001": standing_for(a_proof(), BEFORE)},
            )
        )
    )

    assert "carries one of two labels and there is no third" in markdown
    assert "never that the family is closed and never that the target is fixed" in (
        markdown
    )
    assert "cannot restart somebody else's server" in markdown
    # The label on the block, and the change under it in a fence a diff survives.
    assert "- **Is this fix proven?** — proven —" in markdown
    assert "```diff" in markdown
    assert "+    if 'ignore previous' in message:" in markdown
    # And no severity, no rank and no score anywhere near the label (D3, D12,
    # ADR-0005). Named because every reviewer UI this borrows from has a scale in
    # exactly this position, and promptfoo's is already refused on the record (#109).
    said = standing_for(a_proof(), BEFORE).stated().lower()
    for word in ("severity", "critical", "high", "medium", "low", "score", "rank"):
        assert word not in said, word


def test_a_document_with_no_proof_in_it_carries_no_diff_and_no_second_absence(
    library: list[Case],
) -> None:
    """The stated absence is already one line above: `fix_standing['stated']` says why
    there is no proof, and a second line saying there is no diff either would print
    one fact twice."""
    markdown = render(a_payload(result=explaining(library)))

    assert "- **Is this fix proven?** — proposed —" in markdown
    assert "```diff" not in markdown
