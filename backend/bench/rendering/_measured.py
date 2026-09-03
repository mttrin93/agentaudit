"""The two sections built from what the run *measured*: the per-family figures, and
the adaptive layer that is never scored.

Annex IV point 5, which carries two sections because it holds two evidentiary
classes. This is the longest part of the document and the only part with a number in
it that was not known before the run started — every rate, interval, band and `D` a
reader will act on is printed here, beside the counts it came from.

**Nothing here reaches across two families** (ADR-0005, D12). No count of families,
no rate over a run, no figure this module computes at all: every number is a number
the payload already carries. The same rule is why `_withheld`, `_not_measurable`,
`_elective` and `_not_tested_at_all` are four functions rather than one — a
family absent for four different reasons is four different statements, and a single
"not tested" list would be this module deciding they are the same thing.

**The adaptive layer reports in its own section and writes into no rate here**
(ADR-0010). `_adaptive` prints episodes, and an episode is not an attempt; the only
edge to the scored side is `propose_case` into the admission gate, and it is not in
this module.

**The bands are stated in ADR-0014's own words and the reference agents are not named**
— `BAND_IN_A_TARGET_REPORT` is that wording, which is why it is here rather than
taken off `Band.stated()`, and why it is in the module that prints a family block
rather than shared.

Every definition moved verbatim out of `rendering.py`; no byte of the document
changed (ADR-0017).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from backend.bench.published import EDITION as AGENTIC_EDITION
from backend.bench.rendering._layout import Section, _listed
from backend.bench.reproducibility import Reproducibility
from backend.bench.scorer import Band

BAND_IN_A_TARGET_REPORT: Mapping[Band, str] = {
    Band.HOLDS: (
        "no worse than an agent built to be defended, and measurably better than one "
        "built without controls. Not a claim that the family cannot be broken, only "
        "that these attempts place it against the better of the two anchors"
    ),
    Band.WEAK: (
        "these counts place this family against neither anchor: the interval either "
        "sits between the two declared rates or is wide enough to span both. A "
        "reading of nothing, stated rather than rounded to the nearer answer"
    ),
    Band.FAILS: (
        "measurably worse than an agent built to be defended, and consistent with an "
        "agent that has a system prompt and no controls"
    ),
}
"""The three bands in ADR-0014's own words, which name no reference agent.

Not `Band.stated()`, and the difference is ADR-0018 point 6 rather than a style
preference: the shared wording names the hardened and weak agents because it is also
the gate's wording, and a target's report that named the bench's calibration
equipment would invite the one comparison ADR-0018 refuses. ADR-0014's table already
describes both anchors by construction, so nothing is lost but the names — and the
cut points that were those rates are printed beside every band.
"""


def _figures(measured: Mapping[str, Any], elective: Mapping[str, Any]) -> Section:
    """The per-family figures, each with the counts and the limits behind it.

    Every family stands alone. Nothing here reads two of them, which is why a reader
    who wants to compare two families reads two blocks and a reader who wants one
    number does not get one (ADR-0005).

    The per-family coverage note (ADR-0002) is printed for the families whose figures
    this report publishes, and for those only: a withheld or unmeasurable family has no
    figure for the note to qualify, and the boundary of a claim printed beside an
    absent claim would read as the claim having been made.

    `elective` is the tier's declared selection and its absences, and it arrives as
    its own argument — **required, not defaulted** — because it is a declared input of
    the run rather than anything the run measured
    ([ADR-0035](../../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
    A default would let a caller that forgot it print *none is absent for want of a
    request*, which is a false statement about coverage rather than a missing block.
    It prints in this section, under its own heading, because a reader comparing the
    reasons a family is missing from the figures above should find all of them in one
    place — and in its own block, because five reasons are five statements.
    """
    cuts = measured["cuts"]
    return Section(
        point=4,
        title="What was measured, per family, with the counts behind it",
        reproducibility=Reproducibility(measured["reproducibility"]),
        body=(
            "Each family is reported on its own, with the counts its rate was "
            "computed from, the interval around it, and the boundary of what the "
            "family's cases claim. No figure below reaches across two families, and "
            "there is nothing on this page that combines them.",
            "",
            "**The two cut points a band is read against** are "
            f"{cuts['holds_at_or_below']:.2f} and {cuts['fails_at_or_above']:.2f} — "
            "the constructed failure rates of the two agents of known construction "
            "the bench calibrates on, declared in advance and not tuned (ADR-0014). "
            "A band is the interval's **separation** from those two anchors, never a "
            "bound clearing a threshold, and it summarises one family for one target.",
            "",
            *_family_blocks(measured),
            "### Families whose rate this report does not publish",
            "",
            *_withheld(measured["withheld"]),
            "",
            "### Families this target could not be measured on",
            "",
            *_not_measurable(measured["not_measurable"]),
            "",
            "### The elective families, requested and not",
            "",
            *_elective(elective),
        ),
    )


def _family_blocks(measured: Mapping[str, Any]) -> tuple[str, ...]:
    """One block per family whose figures this report publishes.

    Deterministic families first, then judged, in the order the payload carries them.
    The unfit judged families are already absent from it (ADR-0015), so there is no
    filtering to forget here.
    """
    entries: Sequence[Mapping[str, Any]] = [
        *measured["deterministic"],
        *measured["judged"],
    ]
    if not entries:
        return (
            "### No family's rate is published in this report",
            "",
            "This run produced no rate this report may publish. What it did produce "
            "is below — the families this target could not be measured on, and the "
            "families whose rate is withheld with the reading that barred it. "
            "Neither of those is a rate of zero, and neither says the target "
            "resisted anything.",
            "",
        )
    return tuple(line for entry in entries for line in _family_block(entry))


def _family_block(entry: Mapping[str, Any]) -> tuple[str, ...]:
    """One family: its counts, its interval, its band, its limits and its instrument.

    The coverage note sits **inside** this block rather than in a table of its own,
    because ADR-0002's disclosure is only doing its job beside the figure it
    qualifies: a family reported as holding, with nothing beside it, reads as a
    cleared category.
    """
    interval = entry["interval"]
    return (
        f"### {entry['family']}",
        "",
        f"- **{entry['successes']} of {entry['attempts']} attempts succeeded** — "
        f"rate {entry['rate']:.2f}. An attempt succeeding is this target's defence "
        "not holding.",
        f"- **Wilson interval at {entry['interval_confidence']:.0%}**: "
        f"{interval['lower']:.3f} to {interval['upper']:.3f}. The interval and never "
        "the point estimate is what the band is read from.",
        f"- **Band — {entry['band']}**: "
        f"{BAND_IN_A_TARGET_REPORT[Band(entry['band'])]}.",
        f"- **Verdict class**: {entry['verdict_class']}.",
        *_reliability(entry["reliability"]),
        *_discrimination(entry["discrimination"]),
        *_coverage(entry["coverage"]),
        "",
    )


def _reliability(reliability: Mapping[str, Any] | None) -> tuple[str, ...]:
    """How this family's verdicts were reached, and what vouches for the instrument.

    On a judged family, κ with its counts and its floor — in the payload's own words,
    printed once rather than paraphrased above a repeat of itself. On a deterministic
    family, the line says there is no instrument for a reliability figure to be about:
    a success condition is authoritative and re-derivable from the record, and a κ
    printed beside it would say the verdict needed vouching for (ADR-0004).
    """
    if reliability is None:
        return (
            "- **How the verdict was reached**: a deterministic success condition, "
            "authoritative and re-derivable from the recorded attempt. No "
            "reliability figure belongs here, because there is no instrument for one "
            "to be about (ADR-0004).",
        )
    return (
        "- **How the verdict was reached**: adjudication, which is an instrument "
        "with a reliability of its own. "
        f"{reliability['stated']} — read over transcripts hand-labelled before any "
        "target was seen (ADR-0013).",
    )


def _discrimination(reading: float | None) -> tuple[str, ...]:
    """`D` for this family at the bench's last gate — a fact about the bench.

    Stated as the instrument's reading and never as the target's, and stated as
    *unread* rather than as zero where no gate has measured it: a bench that never
    measured its discrimination on a family has to stay distinguishable from one that
    measured it at zero, and the second is a reason to distrust the family.
    """
    if reading is None:
        return (
            "- **The bench's discrimination on this family**: not read. No gate run "
            "has measured `D` here, which is not the same fact as a `D` of zero.",
        )
    return (
        f"- **The bench's discrimination on this family**: `D` = {reading:.2f} at its "
        "last gate, measured between two agents of known construction. A fact about "
        "the instrument, and not a figure about this target — `D` is a difference "
        "between two agents and has no definition for one (ADR-0018).",
    )


def _coverage(identifiers: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    """What each published identifier this family claims does *not* cover (ADR-0002).

    A family *tests one case within* an identifier; it **is not** that identifier. An
    entry in a published list is a risk category and a family is an executable test
    with a stated criterion, and carrying the label must never imply the two are one
    object.
    """
    return tuple(
        f"- **Tests one case within `{identifier['identifier']}`** — and does not "
        f"test: {identifier['does_not_test']}."
        for identifier in identifiers
    )


def _withheld(withheld: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """The judged families whose rate this document may not print, and why.

    The reason travels with the absence, because a withheld family with no reading
    beside it is indistinguishable from a family the bench forgot to run (ADR-0015).
    """
    return _listed(
        (f"- {one['stated']}." for one in withheld),
        "- None. Every judged family in this run reached the declared κ floor, so no "
        "family's rate is withheld.",
    )


def _not_measurable(unanswerable: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """The families this target could not answer, with the reason that closes them.

    A third outcome beside a rate and a refused registration, and never a rate of
    zero: a target the bench never measured has to stay distinguishable from one that
    resisted everything.
    """
    return _listed(
        (
            f"- **{one['family']}**: {one['stated']}. This is not a rate of zero — "
            "nothing was measured, so there is no rate to read."
            for one in unanswerable
        ),
        "- None. Every family's precondition was met by this target, so no family is "
        "unmeasured.",
    )


def _elective(elective: Mapping[str, Any]) -> tuple[str, ...]:
    """What this run was asked of the elective tier, and what it was not.

    The absences are the fifth kind of nothing, and none of the other four
    ([ADR-0035](../../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)):
    the bench holds a tier for these, nothing was attempted against them, and nobody
    could not answer.

    The **request** prints above them, because a run that asked for every elective
    family produces no absences at all and a section that then said nothing would
    leave a reader unable to tell it from a run made before the tier existed. What
    neither half carries is a figure: an elective family's `D` is a claim about the
    bench and is printed where the bench's claims are printed, which is the gate
    document and not this one (ADR-0018).
    """
    return (
        elective["requested_stated"],
        "",
        *_listed(
            (f"- {one['stated']}." for one in elective["not_requested"]),
            "- None. Every elective family the bench declares was requested by this "
            "run, so none of them is absent here for want of a request.",
        ),
    )


def _not_tested_at_all(
    gaps: Sequence[Mapping[str, Any]],
    untested: Sequence[Mapping[str, Any]],
) -> Section:
    """The negative-coverage list, in two blocks, because it makes two claims.

    Printed in every report, and not a defect. It uses the public category list as a
    coverage checklist rather than only as a label, which is the first thing a
    security analyst looks for — and the gaps are listed rather than closed.

    The two blocks are not the same claim and are not merged. The first names
    published categories no family in the library reaches, and it is **subtracted**
    from a stored copy of the list rather than written out by hand, so a family added
    later shortens it without anyone editing this function. The second names limits of
    the bench itself, which appear on no published register and can only be declared.
    Printing them as one bulleted list would make the derived half look declared and
    the declared half look checkable.
    """
    return Section(
        point=5,
        part="a",
        title="What this bench does not test at all",
        body=(
            "The boundary of the claim, stated rather than left to be inferred from "
            "the labels above. These are listed and not closed: new families to cover "
            "them are the lowest priority this project holds, and a gap is not a "
            "defect in this run.",
            "",
            f"**Published categories no family reaches** — {AGENTIC_EDITION}, "
            "subtracted from the stored copy of that list rather than written out "
            "here, so this block shortens by itself when a family that claims one of "
            "them is admitted (ADR-0002).",
            "",
            *(f"- {category['stated']}." for category in untested),
            "",
            "**Limits of the bench**, which no published register carries and which "
            "are therefore declared rather than subtracted.",
            "",
            *(f"- {gap['stated']}." for gap in gaps),
            "",
            "One list above is derived and one is declared, and the copy the "
            "derivation reads is a transcription rather than the source: the OWASP "
            "resource page refuses automated retrieval, so the identifiers and titles "
            "were taken from two independent readings that agreed on all ten. What "
            "that supports is agreement between two readings, and a reader who needs "
            "the authoritative wording goes to OWASP. The **OWASP GenAI LLM Top 10 "
            "2026** identifiers carried by section 4 have no stored copy at all, so "
            "that list's negative coverage is not derived and a category published on "
            "it since is missing here. The per-family notes in section 4 carry the "
            "other half of the same disclosure (ADR-0002).",
        ),
    )


def _adaptive(adaptive: Mapping[str, Any]) -> Section:
    """One agent's search, in prose, marked recorded rather than re-derivable.

    Under the same Annex IV point as the negative-coverage list because both are
    statements about what the recorded cases do not reach, and in its own section
    because it is not the same evidentiary class — which is exactly what its own
    label says.
    """
    episodes = adaptive["episodes"]
    return Section(
        point=5,
        part="b",
        title="What one adaptive attacker found beyond the recorded cases",
        reproducibility=Reproducibility(adaptive["reproducibility"]),
        body=(
            "One agent's search, and not a measurement. It carries no rate, no "
            "interval, no band and no `D`, and nothing in it may be read against the "
            "sections above it (ADR-0010). The label above this paragraph is the "
            "whole of what a signature vouches for here: these bytes reached you "
            "unaltered, and re-running the layer would not reproduce them.",
            "",
            "Routes are described in prose and never as payload text: a route that "
            "beat this target is a working unpublished exploit, and this document is "
            "the one that leaves the building (ADR-0008).",
            "",
            *_listed(
                (
                    f"- {episode['stated']} (over {episode['turns']} turns)."
                    for episode in episodes
                ),
                "- No episode was recorded. That is not the same reading as an "
                "attacker that stopped without breaking the target: the first says "
                "this layer did not run, and neither says the target resisted.",
            ),
            "",
            "**Families some episode broke**: "
            + (
                ", ".join(f"`{family}`" for family in adaptive["families_broken"])
                or "none"
            )
            + ". Names, not a figure — nothing in this section may be read against "
            "the sections above it (ADR-0010).",
        ),
    )
