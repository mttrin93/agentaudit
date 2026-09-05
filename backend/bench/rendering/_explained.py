"""Section 3b: each failure the bench explained, and the fix written for it.

The headline join is one section above this one — *the controls this target declared,
and what the attacks made of them* — and it is a fact about the **scan** crossed with
the verdicts, per control. This section is the same material read from the other end,
per failure: what one break is to be read against, why it happened, and what to
change. The two records it prints are argued in ADR-0068 (the attributed cause) and
ADR-0069 (which instrument writes which sentence).

**Why it sits under Annex IV point 3 and not point 5.** Point 3 is *monitoring,
functioning and control*, and the reader arriving at 3a has just been told which
declared control gave way; 3b is each of those breaks, named. Point 5 already holds
two sections about the **boundary** of the claim — what is not tested at all, and what
one attacker found outside the recorded cases — and a failure inside the recorded
cases is not a statement about that boundary. So the placement is the one that puts
the explanation beside the claim it explains
([ADR-0070](../../docs/adr/0070-a-signed-document-may-carry-a-remediation.md) §3).

**It is the first section of this document under a *not reproducible* label that is
not the adaptive one**, and the label is the same one: a model wrote these sentences,
and re-running the instruments would not reproduce them. No third evidentiary class is
invented for it — that is ADR-0017's own consequence and not this module's to spend
(`rendering/__init__.py`).

**It reads the serialised document and never a finding.** Like every other module in
this package: the disclosure rule that decided what may be printed here ran at
`assembler.ReportedFinding.of`, where the case record is, and a renderer that could
reach a `Narration` would be a renderer able to print a sentence that rule never saw.
`test_payload.py` holds that as an import wall over this file.

**And that wall is why this module is `_explained` rather than `_findings`.** The wall
is a substring check over the imports of every serialiser, deliberately blunt because
the record travels under five names in four modules — so a rendering module named for
the record would have to be exempted from it, and an exemption is how a blunt wall
stops being one. The section this builds is *each failure the bench explained*, which
is the name it goes under.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.bench.rendering._layout import Section, _listed
from backend.bench.reproducibility import Reproducibility

WHAT_THIS_SECTION_IS = (
    "One block per failure the bench explained. Two sentences from two instruments: "
    "the judge answers *what went wrong* and the remediation tool answers *what to "
    "change*, and neither answers the other's question (ADR-0069). Neither of them "
    "moved a verdict, a rate, an interval or a band — every figure in this document "
    "was measured before either instrument was asked (ADR-0006, ADR-0030)."
)
"""What this section is, printed above the blocks.

The wording deliberately avoids the three words a gate answer uses, here and in every
sentence this package writes into these blocks: there is no sentence anywhere in this
document in which the target passes or fails anything, and a section about the
target's breaks is where that discipline is easiest to lose (ADR-0018,
`rendering/__init__.py`).
"""

WHICH_INSTRUMENT_IS_STOCHASTIC = (
    "The stochastic instruments the label above names are those two models, and "
    "there is no attacker anywhere in this section: ask them again about the same "
    "recorded transcripts and they write different sentences. That is the whole of "
    "what the label withholds — the verdicts these sentences are about were decided "
    "by success conditions and are re-derivable in section 4 (ADR-0004, ADR-0017)."
)

WHERE_A_BLOCK_POINTS = (
    "Where a block names a file, it is a path relative to the repository the bench "
    "ran in and a line in it, read off that checkout at the time of the run — the "
    "definition site of the object that answered, and not a claim about which line "
    "is at fault. Most runs name none: the bench's subject is an endpoint, and it "
    "sees a source tree only when it runs as a step in the repository that holds one "
    "(ADR-0066, ADR-0071). A block that names no file says so in its own words, and "
    "nothing about a target's code should be read out of it either way."
)
"""What the location line means, said once above the blocks rather than in each.

The sentence that keeps the two claims apart — *this is where the target's entrypoint
is* and *this is where the bug is* — for a reader who has skipped every other line of
this section, which is the reader a reviewer UI's file-and-line is written for.
"""

WHAT_A_LABEL_ON_A_FIX_ASSERTS = (
    "Every fix below carries one of two labels and there is no third. **Proven** "
    "means this bench applied the change to a throwaway copy of the caller's own "
    "checkout, re-served the target out of it and re-attempted the case — and it is "
    "a claim about *that one case against that one patched revision*, never that the "
    "family is closed and never that the target is fixed. A family is measured over "
    "thirty attempts against every live case in it, and re-running one is the "
    "operator's cost to choose (ADR-0003, ADR-0072). **Proposed** means it has not "
    "been shown to close its case: the sentence beside it says whether the change "
    "was tested and did not close it, or was never tested at all. A target this "
    "bench reached only over the network can carry nothing but the second — the "
    "bench cannot restart somebody else's server (ADR-0073)."
)
"""What the two labels assert, said once above the blocks rather than in each.

The sentence that keeps the strong reading out of the word: a reader who took
*proven* for *this family is closed* would have been handed the stronger of two
claims by a label, and #109's arithmetic reason is the one this states in prose.
It sits beside `WHERE_A_BLOCK_POINTS` because both do the same job — a reviewer UI's
conventions borrowed without the claims they usually come attached to.
"""

WHAT_IS_WITHHELD = (
    "The exchange itself is not here and has nowhere here to arrive: no payload "
    "text, no reply, no tool trace. A sentence that reproduced the case's own "
    "payload is replaced by a statement that it was withheld, and the case id "
    "beside it is the pointer into the evidence rather than a copy of it (ADR-0008)."
)

NO_FIGURE_HERE = (
    "Nothing in this section is counted for you. There is no severity here, no "
    "ordering of one block against another, and no figure built out of these blocks "
    "at all: a reader who wants one number will build it out of whatever is on the "
    "page, so the page does not offer one (D3, D12, ADR-0005)."
)


def _explained(findings: Mapping[str, Any]) -> Section:
    """Each explained failure, or which of the four absences this run holds.

    The section prints under all four readings of `narrations` and says which one it
    is: nobody declared an instrument, the target succeeded at nothing, every failure
    explained, or the instruments ran and broke (ADR-0050). A section that read the
    same under all four would make a broken judge indistinguishable from a bench that
    was never asked, on the page rather than in the record.
    """
    return Section(
        point=3,
        part="b",
        title="Each failure the bench explained, and the fix written for it",
        reproducibility=Reproducibility(findings["reproducibility"]),
        body=(
            WHAT_THIS_SECTION_IS,
            "",
            WHICH_INSTRUMENT_IS_STOCHASTIC,
            "",
            WHAT_IS_WITHHELD,
            "",
            WHERE_A_BLOCK_POINTS,
            "",
            WHAT_A_LABEL_ON_A_FIX_ASSERTS,
            "",
            NO_FIGURE_HERE,
            "",
            f"{findings['stated']}.",
            "",
            *_listed(
                (line for finding in findings["findings"] for line in _block(finding)),
                "- No failure is explained here. The line above says which of the "
                "four readings this run holds, and none of them is a blank.",
            ),
        ),
    )


def _block(finding: Mapping[str, Any]) -> tuple[str, ...]:
    """One failure's block: what it is read against, then the two sentences.

    A heading per failure rather than a row per failure, because the two sentences
    are prose and a table of prose is a table nobody reads. `###` and not `##`, which
    is reserved for the document's own sections (`rendering/__init__.py`).
    """
    return (
        f"### {finding['case_id']} — {finding['family']}",
        "",
        f"- {finding['attributed_cause_stated']}.",
        f"- Published identifier: {finding['external_id']}. "
        f"What a reader of this is exposed to: {finding['exposure']}.",
        f"- **What went wrong** — {finding['reason']}",
        f"- **What to change** — {finding['fix']}",
        f"- {finding['informed_by_stated']}",
        f"- {finding['disagreement'].capitalize()}.",
        # Last in the block, and printed under all six readings. It is the line a
        # reviewer UI leads with and the one thing the bench structurally could not
        # know before ADR-0066 put it in the caller's own repository — so most runs
        # print an absence here, and the absence is a sentence rather than a gap: a
        # block that simply had no location line would read as a failure nobody could
        # place rather than as one this bench was not standing beside (ADR-0071 §3).
        f"- **Where** — {finding['source_anchor']['stated']}.",
        # The label on the fix, in the record's own sentence and never worded here:
        # the document and the report screen print one claim about one fix, which is
        # the rule `Attribution.stated()` already holds one record over (ADR-0068 §3,
        # ADR-0073 §1).
        f"- **Is this fix proven?** — {finding['fix_standing']['stated']}.",
        "",
        # And the change itself, where the run recorded one — which is only on a run
        # that had a checkout to patch, so most documents end the block above this
        # line. Fenced rather than listed, because a diff whose leading `-` and `+`
        # were rendered as list markup would be a change a reader could not read
        # (ADR-0073 §3).
        *_change(finding["fix_standing"]),
    )


def _change(standing: Mapping[str, Any]) -> tuple[str, ...]:
    """The diff, fenced, or nothing at all where the run recorded none.

    **Nothing rather than a stated absence, alone in this section**, and the reason is
    that the absence is already stated one line above: `fix_standing['stated']` says
    why there is no proof, and a second line saying there is no diff either would be
    the same fact printed twice. Every other absence in this document is said because
    nothing else says it.
    """
    diff = standing["diff"]
    if not diff:
        return ()
    return ("```diff", *diff.splitlines(), "```", "")
