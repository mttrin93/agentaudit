"""The elective family tier: measured by the gate, and unable to decide one.

An **elective family** is a kind of failure the bench can be asked to test that is
not one of the six ([CONTEXT.md](../../CONTEXT.md)). It runs against the three
reference agents on every gate run it is requested for, takes a `D`, faces the same
`discrimination_floor` with the same interval separation, and accumulates a decay
series on each of its cases — and it enters neither of the gate's two counts. The
tier, the promotion rule and the *skipping is never advantageous* invariant are
argued in
[ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md);
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

**The promotion streak is declared here and not in `GateRule`.** It decides nothing
about the gate run in front of a reader, and `rule.py` holds the numbers that decide
— the same reason `T` and `k` are declared in `AdaptiveBudget` and not there
(ADR-0010, and the sentence `GateRule.stated` prints about it).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

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
        """
        if not self.requested:
            return (
                "no elective family was requested by this run, so its figures are "
                "the six mandatory families and only those"
            )
        asked = ", ".join(str(family) for family in self.requested)
        return (
            f"this run was asked to test {asked}. What an elective family measured "
            "is a fact about this bench rather than about this target, so it is "
            "stated where the bench states its own figures and never here "
            "(ADR-0035, ADR-0018)"
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
        `D` on this run and this run counts toward no streak for it (ADR-0035).
        Named here so that a gate run which asked for a family and read nothing says
        which one, rather than leaving a reader to subtract two lists.
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
            "this run and this run counts toward no streak for it"
            for family in self.requested_and_unmeasured
        )
        lines.extend(
            f"  {family}: not requested by this run"
            for family in self.selection.not_requested
        )
        return "\n".join(lines)


NOTHING_ELECTIVE = ElectiveSection()
"""A gate run that asked the tier for nothing, which is every gate run so far."""


PROMOTION_RUNS = 3
"""Consecutive gate runs at or above the floor that make an elective family eligible.

Three, and the argument is
[ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)'s:
entering the six re-declares the rule the bench is held to, which is a stronger claim
than retiring one case, so the bar is strictly harder than the two readings the
retirement rule needs — and three is the smallest number that is.

**Declared here and not in `GateRule`.** It decides nothing about the gate run in
front of a reader, and the rule the gate prints holds the numbers that decide: the
same reason `T` and `k` are declared in `AdaptiveBudget` (ADR-0010), stated in
`GateRule.stated` in those words.
"""


@dataclass(frozen=True)
class ElectiveReading:
    """What one gate run measured for one elective family — the ledger's entry.

    A **family-level** reading, and deliberately not a `GateReading`: that type is
    "one per case per gate run", appended to `Case.history`, and it is what the
    **decay series** and the retirement rule are read over. The promotion streak is a
    claim about the *family* holding the floor across gate runs, so reading it off one
    case's counts would answer a question about a case and print it as an answer about
    a family — the conflation CONTEXT.md keeps **attempt**, **case** and **family**
    apart to prevent.

    It carries the whole `ElectiveOutcome` rather than counts, so `streak_of` reads
    the bar `score_elective` applied instead of re-deriving one: `D ≥ floor` **and**
    intervals apart, both clauses, which is the condition ADR-0003 states and
    ADR-0035 holds the tier to.

    There is no `fit_to_report` flag here, and its absence is a decision rather than
    an omission. ADR-0016 declines the retirement rule on a family the bench cannot
    vouch for, and what it cannot vouch for is a *judged* family below the κ floor.
    Every family in the tier reaches its verdict by canary check, so there is no
    instrument for a reliability figure to be about and no way for one to be unfit —
    the same reason `FamilyEntry.reliability` is `None` on every deterministic entry
    (ADR-0004). An elective family that is ever judged is a decision that needs its
    own ADR, and this field is where that decision would land.
    """

    ran_on: date
    """The date of the gate run this reading was taken on."""

    outcome: ElectiveOutcome
    """The family's reading at that run, already scored against the declared bar."""

    measured_the_field: bool
    """Whether the model underneath the three reference agents was the field at all.

    False on a stub run. Entering the six is a claim about **the field**, and
    ADR-0022 argues why a fixture's `D` is a statement about the fixture — so this is
    what lets `streak_of` decline to count one. Recorded by the run that took the
    reading, never re-derived from a model name, for the reason `GateReading` records
    it rather than parsing `counts.model`.
    """

    def stated(self) -> str:
        """This run's line in one family's standing."""
        field = (
            "" if self.measured_the_field else ", and not a measurement of the field"
        )
        return f"{self.ran_on.isoformat()}: {self.outcome.stated()}{field}"


@dataclass(frozen=True)
class Skipped:
    """A gate run an elective family was not requested for.

    A type and not a `None` in a sequence of readings, because the two halves of
    *skipping is never advantageous* both turn on a skipped run being **countable
    and never confusable with a reading**:

    * It cannot count toward the promotion streak, so skipping buys no progress —
      `streak_of` stops here, because a run the family did not face is not a run it
      held the floor on.
    * It cannot enter a decay series, so skipping buys no protection — a decay series
      holds `GateReading`s written by the run that scored the case, and a run that
      scored nothing writes none, so the retirement window is transparent across a
      gap and two low readings retire a case whatever happened between them
      (`retirement.window_of`, ADR-0022).

    A `Skipped` therefore carries the date and nothing else. There is no `D` to
    carry: nothing was attempted.
    """

    ran_on: date

    def stated(self) -> str:
        return (
            f"{self.ran_on.isoformat()}: not requested — no attempt was made, so "
            "there is no D, and this run counts toward no streak"
        )


LedgerEntry = ElectiveReading | Skipped
"""What one gate run recorded for one elective family: a reading, or a skip.

The ledger is the sequence of these in the order the gate runs happened, and it is
the only thing the promotion rule is read over. A sequence of readings alone could
not answer the streak question at all — a gap in it is invisible, which is precisely
the property the retirement window wants and the promotion streak must not have.
"""


def streak_of(ledger: Sequence[LedgerEntry]) -> int:
    """How many consecutive gate runs, counting back from the last, held the bar.

    Read backwards from the newest entry, because eligibility is a claim about the
    family *now* — the same anchoring `retirement.window_of` uses, and for the same
    reason: a streak chosen from anywhere in the ledger would let a family enter the
    six on three good runs a year ago.

    Two things stop the count, and each of them is a run that did not hold the bar on
    the field:

    * a `Skipped` — the family was not requested, so it held nothing;
    * a reading that did not pass, or did not measure the field. *Passing* is
      `ElectiveOutcome.passes`, which is `scorer.separation` — `D ≥ floor` **and**
      intervals apart — rather than a floor comparison re-derived here, so promotion
      cannot be earned on readings the per-family rule refuses. And a fixture's `D` is
      a statement about the fixture, while entering the six is a claim about the field
      (ADR-0022).

    Neither is transparent. A stop that let the count continue would pay a run for
    producing no evidence, which is the invariant this function exists for.
    """
    counted = 0
    for entry in reversed(ledger):
        if not isinstance(entry, ElectiveReading):
            return counted
        if not (entry.measured_the_field and entry.outcome.passes):
            return counted
        counted += 1
    return counted


@dataclass(frozen=True)
class Standing:
    """Where one elective family stands against the promotion rule.

    Eligibility and never the entry itself. Nothing in this module promotes
    anything: entry into the six is a library-version event that re-declares the
    gate rule **before** the run it applies to, so it is a decision a human takes
    with an ADR beside it and not a state a counter reaches (ADR-0035).
    """

    family: ElectiveFamily
    streak: int
    runs_required: int = PROMOTION_RUNS
    """The streak this standing was read against, carried rather than looked up.

    On the same terms as `RetirementDecision.rule` and for the same reason: a
    standing read against an alternative bar can never be presented as the declared
    one, and `stated()` prints the pair so a reader sees which bar the streak faced.
    `PROMOTION_RUNS` is not in `GateRule`, so it cannot travel in the field below.
    """

    rule: GateRule = DECLARED_RULE
    """The gate rule, for the floor `stated()` names — the bar each counted run held."""

    @property
    def eligible_to_enter(self) -> bool:
        """Whether this family has held the bar for long enough to be considered."""
        return self.streak >= self.runs_required

    def stated(self) -> str:
        """This family's standing, and what it does and does not entitle it to."""
        held = (
            f"{self.streak} of {self.runs_required} consecutive gate runs on the "
            f"field holding D ≥ {self.rule.discrimination_floor:.2f} with the two "
            "intervals apart"
        )
        if self.eligible_to_enter:
            return (
                f"{self.family}: {held} — eligible to be considered for the six. "
                "Entry is a library-version event that re-declares the gate rule "
                "before the run, and nothing here performs it (ADR-0035)"
            )
        return (
            f"{self.family}: {held} — not eligible, and it decides nothing either way"
        )


def standing_of(
    family: ElectiveFamily,
    ledger: Sequence[LedgerEntry],
    rule: GateRule = DECLARED_RULE,
) -> Standing:
    """Read the promotion rule over one elective family's ledger of gate runs.

    Refuses a ledger holding another family's readings: a standing is a claim about
    one family, and a streak assembled from two would be a claim about neither.
    """
    astray = sorted(
        {
            str(entry.outcome.family)
            for entry in ledger
            if isinstance(entry, ElectiveReading) and entry.outcome.family is not family
        }
    )
    if astray:
        raise ValueError(
            f"a standing for {family} was read over a ledger holding readings for "
            f"{astray}. A streak is one family holding the bar across gate runs, and "
            "one assembled from two families is a claim about neither"
        )
    return Standing(family=family, streak=streak_of(ledger), rule=rule)
