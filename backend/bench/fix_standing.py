"""Whether a fix was **proven** — patched, re-served and re-run — or is **proposed**,
and the change it makes, as a unified diff.

Two labels and there is no third. Which of the two is reachable is a property of the
*target* rather than of the fix: a target the bench can patch and re-serve is one it
ran beside, on the caller's own runner, with the checkout on disk
([ADR-0066](../../docs/adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md));
a plain hosted endpoint is somebody else's server, and the bench cannot restart it.
So an endpoint's fixes can only ever carry the second label, and
[ADR-0073](../../docs/adr/0073-two-labels-on-a-fix-and-no-third.md) is the argument
for why blurring the two would be
[ADR-0001](../../docs/adr/0001-procurement-not-regulator-is-the-buyer.md)'s
hand-filled security questionnaire reproduced inside the tool meant to displace it: an
untested assertion put in front of a procurement reader under the word *proven*.

**Not a boolean.** `proven=False` and *we did not test this* are the same bit and
different sentences, and a bench that carried the bit would leave every surface to
word the sentence — which is how a reader ends up told that a fix failed when the
truth is that the bench never had a checkout to try it in (ADR-0073 §1).

**A third label is unrepresentable rather than undocumented.** `FixStandingReading`
has two members, `stated()` matches both with no fallback branch so a third fails the
typechecker rather than inheriting a sentence, and *proven* is not a value any caller
supplies: it is derived by `standing_for` from a `PatchProof`, which only
`proving.prove_patch` produces and only from a checkout on disk. `ReportedFinding`
refuses it a second time, against the source anchor, so a finding the bench could not
point at a file for cannot carry it either (ADR-0073 §2).

**And nothing here reaches the proof loop.** This module holds a label, a sentence
and a diff over two strings; it imports neither `proving` nor `throwaway`, because
ADR-0072 §4's wall runs the other way — `assembler.py` reads this record, and a
serialiser that could reach a `PostPatchAttempt` is a serialiser that could put one
in a denominator. The direction is **proof to label and never label to proof**:
`proving.standing_for` is the one function that sees both, it lives on the proof's
own side of that wall, and an import-level test holds it (ADR-0073 §2).

**Nothing here is a figure and nothing here is a rate.** A label is a name off a
closed set and a diff is text; no rate, band, interval or `D` may read either (D13,
[ADR-0006](../../docs/adr/0006-a-rate-is-measured-and-never-adjusted.md)). There is
no count of proven fixes, no proportion of them, and no field one could arrive in —
a reader who wants one counts the blocks (ADR-0005, D12).

**And a proven fix is a claim about one case, never about a family.** The sentence
this record prints is composed with `PostPatchAttempt.stated()`, which says so in the
words #109 asked for: `n = 30` per family, and re-running the family is the
operator's cost to choose
([ADR-0072](../../docs/adr/0072-a-post-patch-re-run-is-its-own-record.md) §5).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import StrEnum

MAX_PUBLISHED_DIFF_LINES = 400
"""The most of a change this bench will publish into a document that travels.

A ceiling rather than the whole of whatever the operator handed over, because a
`Patch` is a **whole file** (ADR-0072 §2) and a patch that rewrote a large module
would put the whole of that module into a signed artefact — which is new material
about somebody's code arriving at a size nobody reviewed (ADR-0008, ADR-0073 §3). Four
hundred lines is a change a person reads in a review and is well above the patches
this loop is for; a change over it is published as the stated absence below, the
standing is unchanged, and the operator still has the file they wrote.

The figure is a property of this literal: `test_fix_standing.py` writes a patch over
it and asserts the absence, so editing the number without editing that test leaves
the claim unmade.
"""

DIFF_TOO_LARGE_TO_PUBLISH = (
    "the change is not printed here: it is longer than this document publishes. A "
    "patch is a whole file, and a rewritten module reproduced in a signed artefact is "
    "new material about somebody's code at a size nobody reviewed (ADR-0008, "
    "ADR-0073 §3). The label beside it is unchanged — what was proven was proven"
)
"""What stands where a diff would be when the change is over the ceiling.

Said rather than truncated. Half a diff is a change a reader would take for the whole
of one, and the half that is missing is the half a patch's own author would want read.
"""

NO_PATCH_WAS_APPLIED = (
    "no patch was applied and nothing was re-run. Patching and re-serving needs the "
    "code and the bench in the same place — the caller's own repository, on their own "
    "runner, with the checkout on disk (ADR-0066) — and a plain hosted endpoint is "
    "somebody else's server that this bench cannot restart. So this fix is untested "
    "here, which is a fact about where the bench ran and not about the fix"
)
"""Why a fix carries *proposed* on every run that had nothing to patch.

The ordinary answer, and the only one an endpoint target ever has. Stated rather than
left blank, on `source_anchor`'s own terms: a label with no sentence under it is a
label a reader completes themselves, and the completion they reach for is the one
this ticket exists to prevent (ADR-0071 §3, ADR-0073 §1).
"""


class FixStandingReading(StrEnum):
    """Proven or proposed, and there is no third member.

    **The closed set is the whole mechanism.** A third reading — *partly proven*,
    *proven for this payload*, *likely* — is the middle state that lets an untested
    change be read as a tested one, which is exactly the blur ADR-0001 exists to
    displace. So there are two, `FixStanding.stated()` matches both with no fallback
    arm, and a third member added upstream fails `mypy` at that match rather than
    reaching a reader wearing somebody else's sentence (ADR-0073 §1).
    """

    PROVEN = "proven"
    """The patch was applied to a copy of the checkout and the case was re-run.

    The strongest claim this bench makes about a fix, and it is a claim about **one
    case** against **one patched revision** — never that the family is closed and
    never that the target is fixed (ADR-0072 §5).
    """

    PROPOSED = "proposed"
    """It was not proven. The sentence beside it says which of the reasons holds.

    **Not *it failed*.** A fix nobody could test and a fix that was tested and did not
    close its case are both *not proven*, they are different sentences, and the
    sentence is carried rather than inferred: `evidence` is the re-run's own words
    where there was a re-run and `NO_PATCH_WAS_APPLIED` where there was not
    (ADR-0073 §1).
    """


@dataclass(frozen=True)
class FixStanding:
    """One fix's label, the evidence behind it, and the change it makes.

    `SourceAnchor`'s shape one field along and for its reasons: a reading off a closed
    set a consumer can match, one sentence both surfaces print unchanged so the
    document and the screen cannot make two claims about one fix, and the material
    beside them that only exists under one reading.
    """

    reading: FixStandingReading
    """Which of the two holds, as a name a consumer matches rather than infers."""

    evidence: str
    """Why it holds, in the words the re-run wrote or in the absence's own sentence.

    `PostPatchAttempt.stated()` where a re-run happened — the sentence that names one
    case, disclaims its family, and says thirty attempts are the operator's to buy
    (ADR-0072 §5) — and `NO_PATCH_WAS_APPLIED` where none did. Never worded on a
    surface: two surfaces wording it would be two claims about one fix (ADR-0068 §3).
    """

    patched: str | None = None
    """The file the patch replaced, relative to the checkout root, or nothing.

    Relative and never absolute, on `SourceAnchor.path`'s terms: the absolute one
    names the runner's filesystem rather than the repository, and a signed artefact
    is the wrong place for it (ADR-0008, ADR-0071 §4).
    """

    diff: str = ""
    """The change as a unified diff, or empty where there is none to show.

    Empty under two circumstances and the sentence says which: no patch was applied,
    or the change was over `MAX_PUBLISHED_DIFF_LINES`. Computed once, here, from the
    file the bench read and the contents the operator supplied — **never recomputed by
    a surface**, which is the rule `frontend/src/api/report.ts` is already held to and
    which for a diff is also the disclosure answer: what a reader is shown is what the
    bench decided to publish and nothing a client could assemble (ADR-0073 §3).
    """

    def __post_init__(self) -> None:
        """Refuse a proven fix with no file under it, at the record's own door.

        `SourceAnchor.__post_init__`'s discipline: the invariant belongs to the type
        rather than to whoever calls `standing_for`. *Proven* means a patch was
        written into a copy of a checkout and the case re-run, so a proven standing
        that cannot name the file it replaced is a claim with no act behind it — and
        a diff with no file it is a diff of is the same fault from the other end.
        """
        if self.reading is FixStandingReading.PROVEN and self.patched is None:
            raise ValueError(
                "a fix was labelled proven and named no file it patched. Proven "
                "means a patch was written into a copy of the caller's checkout and "
                "the case re-run against it, so a proven standing with no file under "
                "it is the untested claim the two labels exist to keep apart "
                "(ADR-0001, ADR-0073 §2)"
            )
        if self.diff and self.patched is None:
            raise ValueError(
                "a fix standing carried a diff and named no file it patched. A diff "
                "is the change to one file of the checkout, and one with no file "
                "under it is a change to nothing (ADR-0073 §3)"
            )

    def stated(self) -> str:
        """This standing in one sentence, for both surfaces to print unchanged.

        On the record rather than in a renderer, in `SourceAnchor.stated()`'s pattern
        and for its reason. **The sentence says what the label asserts and what it
        does not**: a reader who took *proven* for *this family is closed* or for
        *your agent is fixed* would have been handed the stronger of two claims by a
        word, and #109's arithmetic reason — `n = 30`, one flipped case is not a
        fixed family — is carried in the evidence sentence this composes with.
        """
        # `match` with no fallback branch, on `PostPatchAttempt.stated()`'s terms: a
        # third label must fail the typechecker rather than inherit a sentence
        # written for one of the two, because the sentence is the whole of what a
        # reader is handed (ADR-0073 §1).
        match self.reading:
            case FixStandingReading.PROVEN:
                return (
                    "proven — this bench applied the change to a throwaway copy of "
                    "the checkout, re-served the target out of it and re-attempted "
                    f"the case. {self.evidence}"
                )
            case FixStandingReading.PROPOSED:
                return (
                    "proposed — this change has not been shown to close the case it "
                    f"was written for. {self.evidence}"
                )


NOT_PROVEN = FixStanding(
    reading=FixStandingReading.PROPOSED, evidence=NO_PATCH_WAS_APPLIED
)
"""The standing of every fix on every run that patched nothing.

The default on `ReportedFinding` and the answer for every hosted run, because the
bench's subject is a URL: the honest reading is the common one, and a field a caller
forgot to fill reads as *this was not tested* rather than as a proof it declined to
mention (ADR-0071 §3's default, applied to the fix).
"""


def _hunks(before: str, after: str, path: str) -> list[str]:
    """The change from one text to another, line by line, in unified form.

    Three lines of context, which is every reviewer UI's default and the least that
    makes a hunk legible. Two strings and a path rather than the `Patch` record they
    came out of, because a `Patch` lives in `throwaway.py` and nothing on the report
    side of ADR-0072 §4's wall may reach that module — `proving.standing_for` is
    where the two meet, on the proof's own side of it.

    Split from `unified` so that *there is no change* and *the change is too long to
    publish* are told apart by the caller: both publish no diff, they are different
    facts about a patch, and `standing_for` says which one held (`payload.py`'s
    three-kinds-of-nothing rule, one record along).
    """
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def unified(before: str, after: str, path: str) -> str:
    """That diff as one string, or nothing where there is none this bench publishes.

    Computed on this side of the wire and once, because the payload is what a
    signature covers and a diff a client assembled would be a claim no signature was
    over (ADR-0017).

    Empty where the patch changes nothing — a replacement identical to the file is a
    patch with no change in it, and `difflib` says so by producing no lines — and
    empty where the change is over `MAX_PUBLISHED_DIFF_LINES`, which
    `proving.standing_for` reports as `DIFF_TOO_LARGE_TO_PUBLISH` rather than as half
    a diff.
    """
    lines = _hunks(before, after, path)
    return "" if len(lines) > MAX_PUBLISHED_DIFF_LINES else "\n".join(lines)


def over_the_ceiling(before: str, after: str, path: str) -> bool:
    """Whether that change is longer than this document publishes.

    Asked rather than inferred from an empty diff, because an empty diff is also what
    a patch that changed nothing produces — and *the change is too long to print* and
    *there is no change* are two facts a reader has to be able to tell apart
    (ADR-0073 §3).
    """
    return len(_hunks(before, after, path)) > MAX_PUBLISHED_DIFF_LINES
