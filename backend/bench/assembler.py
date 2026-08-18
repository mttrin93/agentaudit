"""The structured result for one target: three sections, and no number between them.

ADR-0005 refused a composite score, and this module is where that refusal either
holds or quietly stops holding. A result is three sections —

| Section | What it holds | Reproducible |
|---|---|---|
| Measured | rate, interval, verdict class, `D`, coverage note, band | yes |
| Declared | each control marked untested, held or defeated | yes |
| Adaptive | what one attacker achieved, in prose | **no** |

— and the only edge between any two of them is the **declared-and-defeated join**,
which crosses a declaration with a *verdict*. That is the ticket's headline finding
and it is also the reason the sections can be joined at all: a verdict is an
identity fact about one attempt, so the join produces a status and not a figure.
No rate, interval, band or `D` ever crosses a section boundary, in either
direction.

**Why that is structure rather than a rule.** Three separate types with no common
base and no shared numeric field. `MeasuredSection` holds `Rate` and `Interval`,
which are records rather than floats and define no arithmetic; `DeclaredSection`
holds names and statuses; `AdaptiveSection` holds episodes and prose. `Band` is a
`StrEnum` with no ordinal (`scorer.py` says why). `TargetResult` has exactly one
property, and it selects rows from one section — there is no method anywhere that
takes two sections, and nothing to total. A figure combining two of them cannot be
written here without first widening a type, which is the signal ADR-0010 asks an
implementer to stop at.

**The adaptive section carries no rate, no interval, no band and no `D`** (ADR-0010),
and it is labelled *not reproducible* beside two sections that are. Its value to a
reader is the one thing the fixed suite cannot give them — evidence that eighteen
cases are not the boundary of what is possible — and that value survives only if
nobody can mistake it for a measurement. This module owns the section's shape; the
statistics that fill it (`A_break`, `A_effort`, the censoring counts) are #17's,
and they are deliberately absent here rather than stubbed.

**What is deliberately not here.** κ per judged family belongs on the judged
entries and arrives with the gold set (#11); `D` arrives as `None` until a gate run
has read the family (#13), and never as 0.0 — the same soft-zero refusal
`measurability.py` makes about a rate.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.calibration import TargetRun
from backend.bench.contract import DeclaredControl
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, ExternalId, Family, VerdictClass
from backend.bench.measurability import NotMeasurable
from backend.bench.scanner import Scan, family_claimed_by, scan
from backend.bench.scorer import (
    DECLARED_BAND_CUTS,
    Band,
    BandCuts,
    GateDecision,
    Interval,
    Rate,
    band_for,
)
from backend.graph.runstate import Attempt


class Reproducibility(StrEnum):
    """Whether a section can be re-derived by its reader, or only read.

    Printed on every section rather than in a footnote about one, because the
    distinction only means something if it is stated on both sides: a reader who
    sees "not reproducible" once and nothing anywhere else cannot tell whether the
    label is a property of that section or a caveat the author felt like adding.

    Scoping reproducibility rather than claiming it whole is ADR-0010's own
    consequence — the gate decision is re-derivable from recorded inputs, the
    adaptive search is recorded and not re-derivable, and printing the difference is
    the same discipline as printing κ beside a judged family.
    """

    RE_DERIVABLE = "re_derivable"
    NOT_REPRODUCIBLE = "not_reproducible"

    def stated(self) -> str:
        """The label in the words the section header prints."""
        match self:
            case Reproducibility.RE_DERIVABLE:
                return (
                    "re-derivable — every figure here follows from the recorded "
                    "attempts, the case records and the stated rule, so a reader "
                    "holding those can recompute it without this bench"
                )
            case Reproducibility.NOT_REPRODUCIBLE:
                return (
                    "not reproducible — re-run this layer and the attacker takes a "
                    "different path. A route it found is evidence that the route "
                    "exists; a route it did not find is evidence of nothing"
                )


class ControlStatus(StrEnum):
    """What the bench found out about one declared control.

    Three values and no fourth. There is no *present* or *absent* here, because the
    bench cannot see inside a target and never claims to: it knows what the operator
    declared and what the attacks did, and that is the whole of the evidence.
    """

    UNTESTED = "untested"
    """Declared, and the bench ran no deterministic attempt on the family it claims.

    Reached two ways, and they are both real: the family's precondition was unmet
    (a target that does not expose its tool calls cannot be measured on scope creep
    or halt defeat), or the library that ran held no deterministic case for it. Never
    reached by an attempt that failed to break the control — that is `held`.
    """

    HELD = "held"
    """Declared, attempted, and no attempt succeeded.

    The weakest of the three claims and the one most easily over-read: it says these
    attempts did not break this control, not that the control works. The rate and its
    interval are in the measured section for a reader who wants to know how much
    evidence that is.
    """

    DEFEATED = "defeated"
    """Declared, and the bench broke it. The strongest finding the bench produces.

    Rests on a deterministic verdict, so a reader holding the case record and the
    transcript can re-derive it (ADR-0004) — which is what makes it worth putting at
    the head of a report rather than a rhetorical flourish.
    """


@dataclass(frozen=True)
class ScannedControl:
    """One declared control and what the attacks made of it.

    Carries the case ids that broke it and no count of them. A number here would be
    a measurement inside the declared section, and the first thing anyone would do
    with two of them is compare targets on it — which is the composite score
    arriving by the back door. How often the control failed is a rate, and a rate
    lives in the measured section with its interval attached.
    """

    control: DeclaredControl
    family: Family
    """The family this control claims, resolved once by `family_claimed_by`."""

    status: ControlStatus
    broken_by: tuple[str, ...] = ()
    """The ids of the cases whose attempts succeeded against this control.

    Empty unless the status is `defeated`. Ids rather than attempts, because this is
    a pointer into the evidence and not a copy of it.
    """

    not_measurable: NotMeasurable | None = None
    """Why the family could not be measured, when that is why this is untested.

    The load-bearing half of `untested`. A target that declares a stop control and
    does not expose its tool calls must read as *not tested*, never as *held* — the
    alternative is a target improving its standing by withholding the evidence the
    bench needs, which is the same defect as improving it by declaring more
    controls.
    """

    def __post_init__(self) -> None:
        if self.broken_by and self.status is not ControlStatus.DEFEATED:
            raise ValueError(
                f"{self.control} is {self.status} and names cases that broke it. A "
                "control with a case against it is defeated, and one without is not"
            )
        if self.status is ControlStatus.DEFEATED and not self.broken_by:
            raise ValueError(
                f"{self.control} is defeated and names no case. The headline "
                "finding of the report has to point at the verdict behind it"
            )
        if (
            self.not_measurable is not None
            and self.status is not ControlStatus.UNTESTED
        ):
            raise ValueError(
                f"{self.control} is {self.status} and also says why it could not be "
                "measured. A family that was measured has no such reason"
            )

    def stated(self) -> str:
        """The row a report prints for this control."""
        claim = f"{self.control} (declared, claims {self.family})"
        match self.status:
            case ControlStatus.DEFEATED:
                return (
                    f"{claim}: defeated by {', '.join(self.broken_by)} — the target "
                    "declares this control and the bench broke the family it claims"
                )
            case ControlStatus.HELD:
                return (
                    f"{claim}: held — no attempt on that family succeeded. Not "
                    "evidence that the control exists, only that these attempts "
                    "did not get past it"
                )
            case ControlStatus.UNTESTED:
                if self.not_measurable is not None:
                    return f"{claim}: untested — {self.not_measurable.stated()}"
                return (
                    f"{claim}: untested — this run held no deterministic case for "
                    "the family it claims, so the declaration stands unexamined"
                )


@dataclass(frozen=True)
class FamilyEntry:
    """One family's measured result for one target, with its own limits attached.

    Every figure a reader needs to judge the number arrives with it: the counts and
    interval inside the `Rate`, how the verdict was reached, what the bench's own
    discrimination on this family was at the last gate, and which case inside the
    published identifier was not tested. A band on its own would be a grade; a band
    beside these is a summary.
    """

    family: Family
    rate: Rate
    verdict_class: VerdictClass
    band: Band
    discrimination: float | None
    """`D` for this family from the last gate run, or `None` if no gate has read it.

    `None` rather than 0.0, for the reason a family with no attempts has no rate: a
    bench that never measured its own discrimination on a family must stay
    distinguishable from one that measured it at zero, and the second is a reason to
    distrust the family (ADR-0003).
    """

    coverage: tuple[ExternalId, ...]
    """The published identifiers this family's cases test one case *within*, each
    with the boundary of that claim (ADR-0002)."""

    @property
    def interval(self) -> Interval:
        """The Wilson interval around the rate, at the confidence the rule states."""
        return self.rate.interval


@dataclass(frozen=True)
class MeasuredSection:
    """What the fixed suite measured, split by how each verdict was reached.

    Two tuples, disjoint by family, and no property that returns them together or
    totals either — the same deliberate absence `TargetRun` has, and for the same
    reason: a judged rate carries a wider stated limit and a κ figure beside it, so a
    figure combining one with a deterministic rate would have no statable
    evidentiary strength (ADR-0004, ADR-0013).

    Families that could not be measured are a third field rather than entries with a
    rate of zero, exactly as they are on `TargetRun`.
    """

    deterministic: tuple[FamilyEntry, ...] = ()
    judged: tuple[FamilyEntry, ...] = ()
    not_measurable: Mapping[Family, NotMeasurable] = field(default_factory=dict)
    cuts: BandCuts = DECLARED_BAND_CUTS
    """The cut points the bands above were read against, printed with them."""

    def __post_init__(self) -> None:
        for entries, expected in (
            (self.deterministic, VerdictClass.DETERMINISTIC),
            (self.judged, VerdictClass.JUDGED),
        ):
            wrong = [
                entry.family for entry in entries if entry.verdict_class != expected
            ]
            if wrong:
                raise ValueError(
                    f"{sorted(wrong)} are filed under {expected} and say they were "
                    "decided the other way. The class is read off the attempt, so a "
                    "section that disagreed with it would print a judged rate in the "
                    "deterministic column (ADR-0004)"
                )

        both = {entry.family for entry in self.deterministic} & {
            entry.family for entry in self.judged
        }
        if both:
            raise ValueError(
                f"{sorted(both)} appear in both sections. A family is deterministic "
                "or judged, and one in both would be counted twice by any reader "
                "reading down the page"
            )

        measured = {entry.family for entry in (*self.deterministic, *self.judged)}
        overlap = measured & set(self.not_measurable)
        if overlap:
            raise ValueError(
                f"{sorted(overlap)} are reported not measurable and also carry a "
                "rate. Not measurable is a distinct outcome from pass and from "
                "fail, and a family cannot hold two of the three"
            )

    @property
    def reproducibility(self) -> Reproducibility:
        """Re-derivable, always. Not a field: no caller may set it otherwise."""
        return Reproducibility.RE_DERIVABLE


@dataclass(frozen=True)
class DeclaredSection:
    """The declared controls, in the section that shares no arithmetic with any other.

    Statuses and names. No rate, no interval, no band, no `D`, and no count of
    anything — a section holding one number would be a section a reader could add to
    the measured one, and the ADR-0005 defect was precisely that addition.
    """

    controls: tuple[ScannedControl, ...] = ()
    absent: tuple[DeclaredControl, ...] = ()
    """Controls the checklist asks about and this target did not claim. Listed and
    nothing else — an absence is not a finding and costs nothing."""

    @property
    def defeated(self) -> tuple[ScannedControl, ...]:
        """Declared and defeated: the controls the target claims and the bench broke.

        The report's headline. It falls out of the join at no extra cost, and it is
        the direct empirical proof of this project's own thesis — that a declared
        control is a statement and not a measurement.
        """
        return tuple(
            control
            for control in self.controls
            if control.status is ControlStatus.DEFEATED
        )

    @property
    def reproducibility(self) -> Reproducibility:
        """Re-derivable: every status here follows from a deterministic verdict.

        The *declaration* is self-report and stays self-report — that is what
        `untested` says about the ones nothing ran against. What is re-derivable is
        the join: given the attempts, a reader recomputes which claims were broken.
        """
        return Reproducibility.RE_DERIVABLE


@dataclass(frozen=True)
class ReportedEpisode:
    """One episode as the adaptive section reports it: the record, plus prose.

    Named for the episode rather than for the route, because only a **broken**
    episode has a route in CONTEXT.md's sense — the path it took to a canary, the
    sequence of probes that worked. A censored episode reached the turn cap without
    one, and calling its description a route would say the attacker found something
    it did not. The section reports both, so the type is named after the thing they
    have in common.

    Deliberately not named to parallel `FamilyEntry` either. Two row types with
    matching names invite the reading that they are two rows of one table, which is
    the reading ADR-0010 exists to prevent: an entry carries a rate over thirty
    attempts and this carries an agent's search.

    The description is prose and never the probe text. A route that beat a target is
    a working unpublished exploit, and the disclosure posture withholds exactly that
    (ADR-0008; CONTEXT.md on **route**).
    """

    episode: AdaptiveEpisode
    description: str
    """What the attacker did, in prose — the route where one was completed, and what
    it tried where the episode was censored. Never payload text."""

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError(
                "a reported episode with no description is a line a reader can do "
                "nothing with: the prose is the whole of what this section reports"
            )

    @property
    def family(self) -> Family:
        return self.episode.family

    @property
    def outcome(self) -> EpisodeOutcome:
        return self.episode.outcome

    def stated(self) -> str:
        """The line a report prints for this episode, with the attacker's own limits."""
        return f"{self.family}: {self.episode.stated()} — {self.description.strip()}"


@dataclass(frozen=True)
class AdaptiveSection:
    """What a competent attacker achieved beyond the fixed suite. No number here.

    Carries episodes and nothing derived from them arithmetically. `families_broken`
    is a set of names and `censored` is a tuple of episodes, so a reader can count
    them and this section never does — the counts, `A_break` and `A_effort` belong
    to #17 and to their own block, never to a `D` column (ADR-0010, ADR-0011).

    An empty section means no episode was recorded, which is not the same reading as
    a section of censored episodes: the first says the layer did not run, the second
    says the attacker stopped without breaking the target. Neither says the target
    resisted.
    """

    episodes: tuple[ReportedEpisode, ...] = ()

    @property
    def families_broken(self) -> frozenset[Family]:
        """The families some episode broke. Names, not a count and not a rate."""
        return frozenset(
            reported.family
            for reported in self.episodes
            if reported.outcome is EpisodeOutcome.BROKEN
        )

    @property
    def censored(self) -> tuple[ReportedEpisode, ...]:
        """The episodes that stopped on the turn cap or on budget without breaking
        the target. Reported beside the broken ones, because an attacker that ran
        out of turns is not a target that held."""
        return tuple(
            reported
            for reported in self.episodes
            if reported.outcome is EpisodeOutcome.CENSORED
        )

    @property
    def reproducibility(self) -> Reproducibility:
        """Not reproducible, always, and not a field any caller can set."""
        return Reproducibility.NOT_REPRODUCIBLE

    def stated(self) -> str:
        """The section's own header — what it is, and what it is not."""
        return (
            "One agent's search, not a measurement. "
            f"{self.reproducibility.stated()}. It carries no rate, no interval, no "
            "band and no discrimination score, and nothing in it may be read "
            "against the sections above (ADR-0010)"
        )


@dataclass(frozen=True)
class CoverageGap:
    """A published risk category the bench does not test at all.

    Listed in every result and not a defect (CONTEXT.md). A gap with no reason
    beside it reads as an oversight, so each one carries why it is out of reach.
    """

    category: str
    reason: str

    def stated(self) -> str:
        return f"{self.category} — not tested: {self.reason}"


DECLARED_COVERAGE_GAPS: tuple[CoverageGap, ...] = (
    CoverageGap(
        category="data poisoning",
        reason="it needs the training set, which the bench never sees",
    ),
    CoverageGap(
        category="model poisoning",
        reason="it needs the pre-trained components, which the bench never sees",
    ),
    CoverageGap(
        category="output integrity",
        reason=(
            "there is no ground truth for the target's domain. The bench can say "
            "the agent was manipulated; it cannot say the answer was wrong"
        ),
    ),
    CoverageGap(
        category="lifecycle consistency",
        reason="it cannot be shown from one run",
    ),
)
"""The gaps the plan states, printed with every result (PLAN §4, permanent limits).

Declared data, in one place, for the reason every threshold is: a coverage
statement assembled per call site is one that can be quietly shortened for a
report that would read better without it.

**A stated list, not a derived one, and the difference is a limit of this list.**
Deriving the gaps would mean subtracting the identifiers the library's cases claim
from a stored copy of the published category lists, and this repository holds no
such copy — ADR-0002 names the two OWASP 2026 lists as the source of the secondary
labels but does not record their contents. So this list says what the plan can
justify and no more, and a category published after it was written is missing from
it. That is a gap in the gap list, and it is better stated than papered over: the
per-family `coverage` notes carry what each case does *not* test inside the
identifier it claims, which is the other half of the same disclosure and is derived
from the case records rather than declared here.
"""


@dataclass(frozen=True)
class TargetResult:
    """One target's result: three sections, a coverage statement, and no total.

    A record with one property, and that property selects rows from one section.
    There is nothing here that reads two sections, nothing that returns a number,
    and no scalar of any kind — no total, no composite figure, no 0–100 band
    arithmetic (ADR-0005). A reader who wants to compare two families reads two
    entries; a reader who wants one number does not get one.
    """

    target_name: str
    """The target's name and not its `TargetConfig`.

    A result is a record a report renders, and a config carries a bearer token."""

    measured: MeasuredSection
    declared: DeclaredSection
    adaptive: AdaptiveSection
    coverage_gaps: tuple[CoverageGap, ...] = DECLARED_COVERAGE_GAPS

    @property
    def headline(self) -> tuple[ScannedControl, ...]:
        """Declared and defeated — controls this target claims, which the bench broke.

        The headline finding, and empty is a real answer rather than a missing one:
        a target that declared nothing has nothing to be caught over-declaring, and
        a target whose declarations all held is reported as having held them.
        """
        return self.declared.defeated


def declared_and_defeated(
    scanned: Scan,
    attempts: Sequence[Attempt],
    not_measurable: Mapping[Family, NotMeasurable] | None = None,
) -> tuple[ScannedControl, ...]:
    """Cross what a target declared with what the deterministic verdicts say.

    The join, and the whole of the arithmetic it does is set membership: it reads
    each attempt's family, its verdict class and its verdict, and never its rate. A
    version of this that took rates would be adding self-report to measured
    behaviour with one more step, which is the ADR-0005 defect wearing a join's
    clothes.

    **Deterministic attempts only** (spec: the join is computed against the
    attacker's deterministic findings). Every control in the checklist claims a
    deterministic family, so this filter costs nothing in the ordinary case and
    holds the line in the one that matters: a case with a judged verdict class
    filed under a deterministic family's name leaves the control `untested` rather
    than defeating it on an adjudicated verdict.
    """
    reasons = not_measurable or {}
    deterministic = [
        attempt
        for attempt in attempts
        if attempt.verdict_class is VerdictClass.DETERMINISTIC
    ]
    attempted = {attempt.family for attempt in deterministic}
    broke: dict[Family, list[str]] = {}
    for attempt in deterministic:
        if attempt.verdict is Verdict.SUCCEEDED:
            named = broke.setdefault(attempt.family, [])
            if attempt.case_id not in named:
                named.append(attempt.case_id)

    return tuple(
        _scanned(control, attempted, broke, reasons) for control in scanned.declared
    )


def assemble(
    target_run: TargetRun,
    cases: Sequence[Case],
    gate: GateDecision | None = None,
    episodes: Sequence[ReportedEpisode] = (),
    cuts: BandCuts = DECLARED_BAND_CUTS,
    coverage_gaps: tuple[CoverageGap, ...] = DECLARED_COVERAGE_GAPS,
) -> TargetResult:
    """Assemble one target's result from what was recorded against it.

    Each section is built from its own inputs and none of them from another's: the
    measured section from the attempts and the case records, the declared section
    from the registration crossed with the verdicts, the adaptive section from the
    recorded episodes. This function sees all three and combines none of them —
    there is no line below that reads a figure out of one section and into another.

    `gate` supplies `D` per family from the last gate run (#13). Without one, every
    entry says so rather than showing a zero.

    `episodes` are the adaptive layer's, and they arrive as an argument rather than
    off the run state because #16 records them and #17 measures them; this ticket
    owns only the shape they are reported in.
    """
    scanned = scan(target_run.target)
    return TargetResult(
        target_name=target_run.target.name,
        measured=MeasuredSection(
            deterministic=_entries(
                target_run.deterministic_rates,
                VerdictClass.DETERMINISTIC,
                cases,
                gate,
                cuts,
            ),
            judged=_entries(
                target_run.judged_rates, VerdictClass.JUDGED, cases, gate, cuts
            ),
            not_measurable=dict(target_run.not_measurable),
            cuts=cuts,
        ),
        declared=DeclaredSection(
            controls=declared_and_defeated(
                scanned, target_run.attempts, target_run.not_measurable
            ),
            absent=scanned.absent,
        ),
        adaptive=AdaptiveSection(episodes=tuple(episodes)),
        coverage_gaps=coverage_gaps,
    )


def _scanned(
    control: DeclaredControl,
    attempted: set[Family],
    broke: Mapping[Family, list[str]],
    reasons: Mapping[Family, NotMeasurable],
) -> ScannedControl:
    """One declared control's status, from the verdicts on the family it claims."""
    family = family_claimed_by(control)
    if family not in attempted:
        return ScannedControl(
            control=control,
            family=family,
            status=ControlStatus.UNTESTED,
            not_measurable=reasons.get(family),
        )
    if family in broke:
        return ScannedControl(
            control=control,
            family=family,
            status=ControlStatus.DEFEATED,
            broken_by=tuple(broke[family]),
        )
    return ScannedControl(control=control, family=family, status=ControlStatus.HELD)


def _entries(
    rates: Mapping[Family, Rate],
    verdict_class: VerdictClass,
    cases: Iterable[Case],
    gate: GateDecision | None,
    cuts: BandCuts,
) -> tuple[FamilyEntry, ...]:
    """The per-family entries of one verdict class, in the closed family order.

    `Family`'s own order rather than the order the run happened to measure in, so
    two targets' sections line up row for row.
    """
    coverage = _coverage(cases)
    scores = _discrimination(gate)
    return tuple(
        FamilyEntry(
            family=family,
            rate=rates[family],
            verdict_class=verdict_class,
            band=band_for(rates[family], cuts),
            discrimination=scores.get(family),
            coverage=coverage.get(family, ()),
        )
        for family in Family
        if family in rates
    )


def _coverage(cases: Iterable[Case]) -> dict[Family, tuple[ExternalId, ...]]:
    """Each family's published identifiers and stated non-coverage, from the records.

    Read off the case records rather than restated here, so the boundary of the
    claim printed in a report is the boundary the case that ran actually declared
    (ADR-0002). Deduplicated in first-seen order, because three cases of one family
    citing one identifier is one coverage note and not three.
    """
    notes: dict[Family, tuple[ExternalId, ...]] = {}
    for case in cases:
        seen = notes.setdefault(case.family, ())
        if case.external_id not in seen:
            notes[case.family] = (*seen, case.external_id)
    return notes


def _discrimination(gate: GateDecision | None) -> dict[Family, float]:
    """`D` per family from the last gate run, or nothing at all."""
    if gate is None:
        return {}
    return {outcome.family: outcome.discrimination for outcome in gate.outcomes}
