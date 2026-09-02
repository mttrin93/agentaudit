"""The four sections the Act asks for that this bench answers in prose: lifecycle
changes, standards applied, conformity, and post-market monitoring.

Annex IV points 6 through 9. They are one module because they have one property in
common that none of the other sections has: **no run reaches them.** Each is the same
text for every report this bench issues, so none of them takes a payload, and a
reader who finds a figure appearing in one of these should treat it as a bug.

That is also the reason they carry the *re-derivable* label rather than the payload's:
a stated position follows from the same record every time it is stated.

Point 9 says again, in the Act's own frame, what point 1 already said — that this
document is not a claim of conformity — so the sentence is imported from `_layout.py`
rather than written twice.

Every definition moved verbatim out of `rendering.py`; no byte of the document
changed (ADR-0017).
"""

from __future__ import annotations

from backend.bench.rendering._layout import NOT_A_CLAIM_OF_CONFORMITY, Section


def _lifecycle() -> Section:
    """Annex IV(6): what one run can say about change over time, which is nothing.

    Said rather than omitted. A missing section reads as a document that had nothing
    to declare, and this one has something to declare and one run to declare it from.
    """
    return Section(
        point=6,
        title="Changes through the lifecycle",
        body=(
            "**Nothing, and this document cannot say otherwise.** This is one run "
            "against one target at one time. A band that moved, a control that was "
            "added, a model that was swapped underneath the agent — none of them is "
            "visible from a single run, which is why lifecycle consistency is listed "
            "in section 5a as a category this bench does not test. Two reports of "
            "the same target, each verifiable on its own, are what a reader would "
            "compare; scheduled runs that would produce them are not part of this "
            "artefact (section 9).",
        ),
    )


def _standards() -> Section:
    """Annex IV(7): the standards applied, of which there are none that could be.

    The honest answer is a short one, and it protects the identifiers above it: no
    harmonised standard is cited in the Official Journal, so nothing in this document
    carries a presumption of conformity, however recognisable its labels look.
    """
    return Section(
        point=7,
        title="Standards applied",
        body=(
            "**None, and none is available.** No harmonised standard for Article 15 "
            "is cited in the Official Journal, so nothing in this document carries "
            "the Article 40 presumption of conformity.",
            "",
            "The published identifiers in section 4 are **secondary labels and never "
            "identity**: a family *tests one case within* an identifier; it is not "
            "that identifier. An entry in a published list is a risk category, and a "
            "family is an executable test with a stated criterion (ADR-0002). Draft "
            "European standards are not cited here at all — clause numbers move "
            "between drafts, and a stale clause number inside a signed report is "
            "worse than no reference.",
        ),
    )


def _conformity() -> Section:
    """Annex IV(8): the declaration of conformity, and why there is not one.

    The strongest single sentence in the document, in the place a reader looking for
    a badge will actually turn to.
    """
    return Section(
        point=8,
        title="Declaration of conformity",
        body=(
            "**None. There is no declaration of conformity here, and there will not "
            "be one.**",
            "",
            NOT_A_CLAIM_OF_CONFORMITY,
            "",
            "What this document does carry is the evidence a reader can check for "
            "themselves: counts behind every rate, the rule they were measured "
            "under, the instrument's own certification in section 2, and the "
            "boundary of the claim in section 5a.",
        ),
    )


def _post_market() -> Section:
    """Annex IV(9): post-market monitoring, which this artefact does not provide."""
    return Section(
        point=9,
        title="Post-market monitoring",
        body=(
            "**Not part of this artefact.** This report describes one run, made at "
            "the moment recorded in section 2. A scheduled run, a re-measured "
            "target, an alert when a band moves and delivery of a fresh report are "
            "all outside what this document covers, and a reader should treat every "
            "figure here as an observation of that moment rather than as a standing "
            "property of the agent.",
        ),
    )
