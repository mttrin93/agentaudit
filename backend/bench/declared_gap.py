"""What a run's own caller did not provide, and the family it costs.

The fourth kind of nothing a family's line can be, and the one the **bench cannot
detect**: a family whose cases were dropped before the run because of something the
caller declared — no adjudicating instrument, an unplanted artefact, a family or a
construction switched off. Beside `measurability.NotMeasurable` and never merged with
it, on that module's own terms: not measurable is a *case precondition* this bench
checks for itself, and this is the caller's statement about their own setup.

**In `backend/bench/` because the signed artefact carries it.** It was declared in
`backend/api/run_status.py` while the only surface that printed one was an HTTP
response; since
[ADR-0075](../../docs/adr/0075-a-declared-gap-reaches-the-signed-artefact.md)
the measured section of the artefact carries a block of these, and no module of
`backend/bench/` imports `backend/api/` — a rate's own document reaching up into the
routes for the vocabulary its absences are written in would be the one import that
inverts the two layers. `run_status.py` re-exports it, so nothing about the API's
vocabulary moved with it.
"""

from __future__ import annotations

from enum import StrEnum


class DeclaredGap(StrEnum):
    """Something the caller's own setup did not provide, and the family it costs.

    The second surface of the concept `scripts/probe_target.py` keeps as
    `OperatorGap`, and deliberately not `NotMeasurable`: that type is the library's
    answer to a *case precondition* a target cannot meet, decided before an attempt
    is spent. These are the caller's gaps — the bench cannot detect either of them,
    no attempt is skipped for them, and the family is not run at all rather than
    measured at zero. A family missing from a run with no reason beside it is a
    reader guessing which of three answers it was.

    Two enums rather than one shared one, and the duplication is the smaller cost.
    `OperatorGap` says *pass `--adjudicator-model`* and *this was a
    `--deterministic-only` run*: its prose names command-line flags, which is right
    for the surface it was written for and wrong in an HTTP response. It also
    carries two members about reading a rate that was measured, which is a thing
    this surface does not do yet. Sharing them would mean rewriting a script's
    user-facing text to fit a caller who is not at a terminal.
    """

    NO_ADJUDICATOR = "no_adjudicator"
    NOTE_NOT_PLANTED = "note_not_planted"
    NONCE_NOT_PLANTED = "nonce_not_planted"
    FAMILY_SWITCHED_OFF = "family_switched_off"
    TRANSFORMS_SWITCHED_OFF = "transforms_switched_off"
    """Every construction this family holds a case for was switched off for this run.

    Beside `FAMILY_SWITCHED_OFF` and one level below it: that one is *this family was
    not asked*, and this is *this family was asked and nothing was left to ask it
    with*. Two members rather than one, because the two are different things the
    caller did and a reader owed a reason is owed the right one
    ([ADR-0058](../../docs/adr/0058-the-console-selects-layers-and-constructions.md)).

    Not the absence #72 refused a type for. A family whose *library* holds no variant
    of some construction is measured by the variants that exist and needs no reason
    beside it (ADR-0055); this is a construction the **caller** turned off, which is
    what this enumeration is the surface for.
    """

    def stated(self) -> str:
        match self:
            case DeclaredGap.NO_ADJUDICATOR:
                return (
                    "not run: this family reaches its verdict by adjudication and "
                    "this bench has no adjudicating instrument configured. A "
                    "family nothing can score is not attempted, so the estimate "
                    "does not charge for it"
                )
            case DeclaredGap.NOTE_NOT_PLANTED:
                return (
                    "not run: this family needs a third-party note planted in "
                    "content the target retrieves, and the caller declared it is "
                    "not in place. Run without it, the family would report a clean "
                    "zero that reads as a defence and is not one"
                )
            case DeclaredGap.NONCE_NOT_PLANTED:
                return (
                    "not run: this family extracts the registration nonce, and the "
                    "caller started this run without planting it. A canary that is "
                    "nowhere in the target cannot leak, so every attempt would "
                    "report resisted against an attack that was never possible"
                )
            case DeclaredGap.FAMILY_SWITCHED_OFF:
                return (
                    "not run: this family was switched off for this bench, so no "
                    "case in it was attempted and no episode opened against it. "
                    "Nothing here is a reading about the target — a family that was "
                    "not asked is not a family that held"
                )
            case DeclaredGap.TRANSFORMS_SWITCHED_OFF:
                return (
                    "not run: every construction this family holds a case for was "
                    "switched off for this run, so no attempt was made against it "
                    "and it is not measured rather than measured at zero. The family "
                    "was asked and there was nothing left to ask it with — a "
                    "construction that was not sent is not a construction that failed"
                )
