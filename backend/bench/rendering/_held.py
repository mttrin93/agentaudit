"""The section built from what earlier runs found and this run re-sent: the block.

Annex IV point 5's third section. Points 5a and 5b are statements about the boundary
of the recorded cases — what the bench does not test, and what one attacker found
outside them — and this is a third evidentiary class beside them: confirmed breaks
against **this** agent that the admission bar refused, re-sent on every run of it and
read by the same deterministic evaluator. The decision is
[ADR-0117](../../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§4; the record it prints is `reporting.HeldBlock`.

**That any of it is in these bytes is
[ADR-0119](../../../docs/adr/0119-a-held-routes-figures-travel-in-the-signed-artefact-and-its-prose-does-not.md)**,
which admits the figures and the dates and keeps the attacker's account of the break
out — so there is no field on this section's rows for a sentence an instrument wrote.

**Its own section is the whole of the fence at this last step.** Every module before
this one carries ADR-0117 §4 by type — a `HeldRoute` is not a `Case`, a `HeldReading`
is not an `Attempt`, a `HeldRouteLine` carries no payload — and a reader sees one page,
so the place the separation is actually lost is here. What that buys locally: the
section is numbered apart from the figures, every number in it is printed as a count
beside the counts it came from, and *3 of 5 still open* is two integers on this page
with nowhere in the document the quotient of them appears.

**The reproducibility label is the nearer of the two and it is not a comfortable fit,
which is said on the page rather than solved by inventing a third.** ADR-0017 declares
two labels and `rendering/__init__.py` records why no third was minted: a genuinely
third evidentiary class would have to extend the claim list, which is an ADR and not a
renderer's decision. *Not reproducible* is wrong here — the evaluator is deterministic
and nothing in this block came from a model. *Re-derivable* is the right half of the
pair and the wrong half of its own sentence, because the records these figures follow
from are the target library, which is not in this document and whose probes never will
be (ADR-0008). So the section carries the re-derivable label and then says, in as many
words, from what — and by whom it cannot be re-derived.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.bench.rendering._layout import Section, _listed
from backend.bench.reproducibility import Reproducibility

WHAT_A_READER_CANNOT_RECOMPUTE = (
    "Re-derivable, and by fewer readers than the sections above it: these figures "
    "follow from this target's held-route records and this run's readings of them, "
    "and neither is in this document. A held route's probe is a working unpublished "
    "exploit against the agent this report is about, so it is not published here and "
    "will not be (ADR-0008). What a recipient can check is that these bytes are the "
    "ones that were produced; what the bench can re-derive is every figure below, "
    "from records it holds. No third reproducibility label was invented for that "
    "distinction — a third evidentiary class would have to extend the claim list, "
    "which is a decision and not a rendering (ADR-0017)."
)
"""Why the label over this section means less here than it does two sections up.

Stated rather than smoothed over, which is ADR-0017's own posture about the label: a
reader who meets *re-derivable* on every section and cannot tell that one of them is
re-derivable only by the sender has been told something slightly untrue.
"""


def _held_routes(block: Mapping[str, Any]) -> Section:
    """The target library as one block: held, still open, closed, and what licenses it.

    Reads the serialised block and computes nothing. Every integer printed below is an
    integer the payload already carries, and the two standing sentences are the
    payload's own — a section that worded them here would be a second copy of a claim
    the signed document already makes.
    """
    return Section(
        point=5,
        part="c",
        title=(
            "Confirmed breaks held against this target, and whether they still break it"
        ),
        reproducibility=Reproducibility.RE_DERIVABLE,
        body=(
            block["licensed_by"],
            "",
            block["no_rate_over_these"],
            "",
            WHAT_A_READER_CANNOT_RECOMPUTE,
            "",
            f"**{block['stated']}**",
            "",
            # The counts, and only where there is a library they are counts of. A
            # block of six zeroes under *this run read no target library* would be
            # the reading a count of zero must never stand for, printed by the
            # document that says so two paragraphs up (ADR-0117 §4).
            *_counts(block),
            *_listed(
                (f"- {route['stated']}" for route in block["routes"]),
                "- No route is listed. Which of the three readings that is, is the "
                "sentence above this list, and the two are not the same fact: a "
                "library nothing has been found against, and a run that never read "
                "one, differ in whether anybody looked.",
            ),
            *_refusals(block["not_counted"]),
        ),
    )


def _counts(block: Mapping[str, Any]) -> tuple[str, ...]:
    """The figures, each named for the question it answers and none divided by another.

    Six lines rather than one summary, because four of them answer questions a reader
    would otherwise answer with the wrong figure. *Still open* is the library's state
    and *broke the target again* is this run's reading, and a run that could not reach
    the agent is exactly where they differ — so the count that explains the gap is
    printed between them rather than left for a reader to notice is missing.

    Nothing at all under the other three readings. A library holding no route, a
    library that would not open and a run that never read one have no routes for these
    six figures to be counts of, and six zeroes printed under the sentence that says so
    is the document reporting *nobody looked* as *nothing was found*.
    """
    if block["reading"] != "held":
        return ()
    return (
        f"- **Held against this target**: {block['held']}. Every confirmed break the "
        "admission bar refused and an operator approved, open and closed together — "
        "which is what the counts below are read against.",
        f"- **Still open**: {block['open']}. Routes this target has not yet closed, "
        "whatever this run read about them.",
        f"- **Closed**: {block['closed']}. Routes this target stopped failing on two "
        "consecutive clean runs, kept with the run that closed them.",
        f"- **Broke the target again on this run**: {block['still_breaking']}. A "
        "reading of this run and not a property of the library.",
        f"- **Could not be read on this run**: {block['not_read']}. The target was "
        "unreachable, or no reply carried what the criterion has to read. Neither is "
        "a clean run and neither counts toward closing anything.",
        f"- **Have closed once and come back**: {block['regressed']}. A regression, "
        "and not a new finding.",
    )


def _refusals(refusals: Sequence[str]) -> tuple[str, ...]:
    """Readings this run took that reached no record, or nothing at all.

    Printed because a window that failed to advance is exactly the thing a reader of
    the counts above has to be told about: without it a storage fault reads as a route
    that is simply still open, and next run's *closed* arrives a run late with no
    explanation. Absent entirely on the ordinary run, because a heading over an empty
    list is a reader wondering what it would have said.
    """
    if not refusals:
        return ()
    return (
        "",
        "**Readings this run could not count into the records they were read off.** "
        "The figures above are the library as it stands; each line here is a reading "
        "that did not move it.",
        "",
        *(f"- {refusal}" for refusal in refusals),
    )
