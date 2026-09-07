"""The elective family tier: measured by the gate, and unable to decide one.

An **elective family** is a kind of failure the bench can be asked to test that is
not one of the six ([CONTEXT.md](../../CONTEXT.md)). It runs against the three
reference agents on every gate run it is requested for, takes a `D`, faces the same
`discrimination_floor` with the same interval separation, and accumulates a decay
series on each of its cases — and it enters neither of the gate's two counts. The
tier is argued in
[ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)
and the promotion streak it once declared is removed by
[ADR-0087](../../docs/adr/0087-entry-into-the-six-is-a-decision-and-not-a-counter.md);
what lives here is the rule as code.

**The prohibition is carried by the type, not by a flag.** `Family` is the type
`FamilyRates`, `FamilyOutcome` and `GateDecision` are defined over, and
`ElectiveFamily` is a separate enumeration, so an elective reading has no shape in
which it could arrive at `decide_gate`: `ElectiveRates` is not a `FamilyRates` and
`ElectiveOutcome` is not a `FamilyOutcome`. That is the same mechanism ADR-0010 uses
to keep an `AdaptiveEpisode` out of a denominator, applied one level down, and it is
why nothing here widens a signature to accept both.

**The arithmetic is the gate's and nothing here divides anything.** `D`, the
interval overlap, the ordering and the floor comparison all come from `scorer.py`,
so an elective family cannot be measured under an arithmetic the gate does not use
and cannot be held to a softer bar because nothing turns on it. Selectable is not
ungated.

**Nothing here says when a family may enter the six.** Entry re-declares the gate
rule — six families, 4 of 6, monotonicity on 5 of 6 — before the run it applies to,
so it is a decision a person takes and writes down, and the readings this module
produces are evidence offered to it rather than a count accumulating toward it
(ADR-0087).
"""

from dataclasses import dataclass

from backend.bench.library import ElectiveFamily
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import (
    Monotonicity,
    Rate,
    monotonicity,
    separation,
)

NOT_GATE_DECIDING = (
    "an elective family is measured by the gate and decides no gate: it enters "
    "neither the count of families passing nor the count that ordered the "
    "reference agents, at any reading, and a reader who found its D beside those "
    "counts would be reading a seventh family in a denominator ADR-0015 fixed at "
    "six (ADR-0035)"
)
"""What an elective figure says about itself, in one wording.

One sentence read by the gate document and by the report, because a second would only
have to disagree once for a document to present a figure that decided nothing as one
that did — the discipline `rule.NOT_A_GATE_RESULT` already follows.
"""


@dataclass(frozen=True)
class ElectiveRates:
    """What one elective family measured against the three reference agents.

    Deliberately not a `FamilyRates`, and the difference is the whole of the tier's
    guarantee rather than a naming preference: `FamilyRates` is what `score_family`
    consumes and what `decide_gate` counts, so a type that could be passed as one
    would be an elective family in the gate's denominator. Each `Rate` carries its
    own `attempts`, and this record states no denominator, for the reason
    `FamilyRates` states none.
    """

    family: ElectiveFamily
    hardened: Rate
    weak: Rate
    trivial: Rate


@dataclass(frozen=True)
class ElectiveOutcome:
    """One elective family's reading at a gate run, with the numbers behind it.

    Every figure the per-family rule turns on, so a reader re-derives the line
    rather than trusting it — and `passes` is exactly that rule read over these
    counts, which is what makes the tier *gate-measured*. What it is not is a
    contribution: there is no field here a gate count could be read out of, and
    `ElectiveOutcome` is not a `FamilyOutcome`, so there is no argument anywhere
    through which one could arrive at `decide_gate`.
    """

    family: ElectiveFamily
    rates: ElectiveRates
    discrimination: float
    intervals_separate: bool
    monotonicity: Monotonicity
    passes: bool
    rule: GateRule = DECLARED_RULE
    """The rule this reading was taken under, carried for the reason a
    `RetirementDecision` carries it: a reading taken under an alternative floor can
    never be presented as the declared one."""

    def stated(self) -> str:
        """This family's line in the gate document's elective section."""
        return (
            f"{self.family}: D = {self.discrimination:.2f}, intervals "
            f"{'do not overlap' if self.intervals_separate else 'overlap'}, "
            f"{self.monotonicity.inversions} inversion"
            f"{'' if self.monotonicity.inversions == 1 else 's'} "
            f"({'ordered' if self.monotonicity.holds else 'NOT ordered'}) — "
            f"{'holds' if self.passes else 'does not hold'} the declared floor of "
            f"{self.rule.discrimination_floor:.2f}, and decides nothing"
        )


def score_elective(
    rates: ElectiveRates, rule: GateRule = DECLARED_RULE
) -> ElectiveOutcome:
    """Read the per-family rule over one elective family's three rates.

    `scorer.separation` is the *one* implementation of that condition and both tiers
    read it, which is what makes "held to the same bar" a property rather than a
    coincidence: two copies of `separate and reaches(...)` would only have to drift
    once for the tier to be measured on a softer rule and printed in the same
    document. What differs is only what the answer is allowed to do, and that is
    carried by the return type.
    """
    apart = separation(hardened=rates.hardened, trivial=rates.trivial, rule=rule)
    return ElectiveOutcome(
        family=rates.family,
        rates=rates,
        discrimination=apart.discrimination,
        intervals_separate=apart.intervals_separate,
        monotonicity=monotonicity(
            hardened=rates.hardened, weak=rates.weak, trivial=rates.trivial, rule=rule
        ),
        passes=apart.passes,
        rule=rule,
    )


@dataclass(frozen=True)
class ElectiveSelection:
    """The elective families a run was asked to test, and the ones it was not.

    A **declared input** of a run, on the same footing as `DeclaredModels` and the
    denominator the console may set (ADR-0025): it is stated before the run and no
    measurement moves it. Selectable at both gate and target runs, and on a target
    run it is a lever on the dominant cost, which is the point of the tier.

    `not_requested` is derived from the declared set rather than supplied, in the
    discipline `MeasuredSection.unfit_to_report` already follows: a report that had
    to be *told* which families to name as unrequested is one where forgetting to
    ask prints nothing at all, and the fifth absence would be the one absence a
    reader could not see.
    """

    requested: tuple[ElectiveFamily, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.requested)) != len(self.requested):
            raise ValueError(
                f"{[str(family) for family in self.requested]} names an elective "
                "family twice. A family requested twice is a family whose attempts "
                "would be counted twice into one denominator"
            )

    @property
    def not_requested(self) -> tuple[ElectiveFamily, ...]:
        """The declared elective families this run was not asked to test.

        In declaration order, so two runs at the same selection print the same list.
        """
        return tuple(
            family for family in ElectiveFamily if family not in self.requested
        )

    def requested_stated(self) -> str:
        """What this run was asked for, in the words a *target* report may use.

        The word *gate* does not appear in it, which is ADR-0018 rather than brevity:
        this sentence travels in an artefact about a target, and the vocabulary of the
        gate belongs to the bench. `stated()` below is the gate document's wording and
        names it freely, because there the subject *is* the bench.

        **Reworded by
        [ADR-0088](../../docs/adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md).**
        It used to say that what an elective family measured is a fact about the bench
        and is stated nowhere in this document. Half of that was always true and is
        still printed here — the tier's `D` is the bench's own discriminating power and
        belongs in the gate run's document — and the other half was two figures sharing
        one prohibition: the rate a requested family measured against *this target* is
        a fact about that target and is above, with its interval and its band.
        """
        if not self.requested:
            return (
                "no elective family was requested by this run, so its figures are "
                "the six mandatory families and only those"
            )
        asked = ", ".join(str(family) for family in self.requested)
        return (
            f"this run was asked to test {asked}, and what each of them measured "
            "against this target is reported above with its interval and its band. "
            "What is not here is how well this bench discriminates on them: that is "
            "a fact about the bench rather than about this target, and it is stated "
            "where the bench states its own figures (ADR-0018, ADR-0035, ADR-0088)"
        )

    def stated(self) -> str:
        """What the run was asked for, printed whether it was asked for anything."""
        asked = (
            ", ".join(str(family) for family in self.requested)
            if self.requested
            else "none"
        )
        return f"elective families requested: {asked} — {NOT_GATE_DECIDING}"


NOTHING_REQUESTED = ElectiveSelection()
"""No elective family was asked for. The default of every run, and a real answer.

Not an absent selection: a run that requested nothing from the tier is a run whose
figures are the six and only the six, and it says so rather than leaving a reader to
infer it from a missing block.
"""


@dataclass(frozen=True)
class ElectiveSection:
    """What a gate run measured in the elective tier, in its own section.

    Its own section and never a row among the six, on the discipline ADR-0010
    established for the adaptive layer: the layer that decides nothing reports
    beside the decision rather than inside it. Held on `GateResult` next to the
    `GateDecision` rather than within it, so there is no field of the decision an
    elective figure could be reached through.

    The section refuses a reading for a family nobody requested. A figure from a
    family the run was not asked for is a figure whose attempts nobody consented to
    spending, and admitting it would make the selection a suggestion.
    """

    selection: ElectiveSelection = NOTHING_REQUESTED
    outcomes: tuple[ElectiveOutcome, ...] = ()

    def __post_init__(self) -> None:
        unasked = sorted(
            str(outcome.family)
            for outcome in self.outcomes
            if outcome.family not in self.selection.requested
        )
        if unasked:
            raise ValueError(
                f"{unasked} carry a reading and were not requested by this run. A "
                "reading for a family nobody asked for is attempts nobody consented "
                "to spending, and a section that admitted one would make the "
                "selection a suggestion"
            )
        measured = [outcome.family for outcome in self.outcomes]
        if len(set(measured)) != len(measured):
            raise ValueError(
                f"{sorted(str(family) for family in measured)} holds two readings "
                "for one family in one gate run, and a family has one D per gate run"
            )

    @property
    def requested_and_unmeasured(self) -> tuple[ElectiveFamily, ...]:
        """Requested families no reading was taken for, in declaration order.

        A derived list rather than a sixth kind of nothing: the family *was* asked
        for, so it is not `not_requested`, and no attempt reached it, so it has no
        `D` on this run (ADR-0035). Named here so that a gate run which asked for a
        family and read nothing says which one, rather than leaving a reader to
        subtract two lists.
        """
        measured = {outcome.family for outcome in self.outcomes}
        return tuple(
            family
            for family in ElectiveFamily
            if family in self.selection.requested and family not in measured
        )

    def stated(self) -> str:
        """The elective section as the gate document prints it."""
        lines = [
            "the elective tier — measured on this gate run, and deciding nothing on it",
            f"  {self.selection.stated()}",
        ]
        lines.extend(f"  {outcome.stated()}" for outcome in self.outcomes)
        lines.extend(
            f"  {family}: requested and no reading was taken, so it has no D on "
            "this run"
            for family in self.requested_and_unmeasured
        )
        lines.extend(
            f"  {family}: not requested by this run"
            for family in self.selection.not_requested
        )
        return "\n".join(lines)


NOTHING_ELECTIVE = ElectiveSection()
"""A gate run that asked the tier for nothing, which is every gate run so far."""
