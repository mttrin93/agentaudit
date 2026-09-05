"""The structured result for one target: three sections, and no number between them.

ADR-0005 refused a composite score, and this module is where that refusal either
holds or quietly stops holding. A result is three sections —

| Section | What it holds | Reproducible |
|---|---|---|
| Measured | rate, interval, verdict class, `D`, κ, coverage note, band | yes |
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
and it is labelled *not reproducible* beside two sections that are. PLAN §9 says
what the section is worth to a reader and why that worth survives only while nobody
can mistake it for a measurement. This module owns the section's shape; the
statistics that fill it (`A_break`, `A_effort`, the censoring counts) are #17's,
and they are deliberately absent here rather than stubbed.

**κ is on the judged entries and nowhere else** (#11, ADR-0004). It is a figure
about the instrument that decided a judged family, so a deterministic entry carrying
one is refused: the success condition is authoritative and needs no vouching for. A
judged family whose κ misses the declared floor — or that has no κ at all — is
`unfit_to_report`, and that marking is derived rather than set, so a renderer cannot
publish the rate by neglecting to ask.

**One thing here is per failure rather than per section.** `Attribution` is the
declared-and-defeated join read from the other end — given one failure, what is it to
be read against — and it is derived from the case record and the scan rather than
written by a model, which is why it needs no reliability figure and is not a fourth
instrument
([ADR-0068](../../docs/adr/0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md)).
It is in this module because the scan is, and deliberately not in `judge.py`, which
holds no scan and must not gain one. It reaches none of the three sections above and
no key of the payload: printing it is #112's and #113's, and the signed document has a
price to pay first.

**What is deliberately not here.** `D` arrives as `None` until a gate run has read
the family (`gate.py`), and never as 0.0 — the same soft-zero refusal
`measurability.py` makes about a rate.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.calibration import TargetRun
from backend.bench.contract import DeclaredControl
from backend.bench.declared_gap import DeclaredGap
from backend.bench.elective import NOTHING_REQUESTED, ElectiveSelection
from backend.bench.evaluator import Verdict
from backend.bench.fix_standing import NOT_PROVEN, FixStanding, FixStandingReading
from backend.bench.judge import Exposure
from backend.bench.library import (
    AnyFamily,
    Case,
    ExternalId,
    Family,
    Transform,
    VerdictClass,
    one_of_the_six,
)
from backend.bench.measurability import NotMeasurable
from backend.bench.narration import Narration, Narrations, NarrativeFailure
from backend.bench.published import (
    CLAIMED_IN_PART,
    UNTESTED_CATEGORIES,
    ClaimedInPart,
    UntestedCategory,
)
from backend.bench.reproducibility import Reproducibility
from backend.bench.scanner import (
    NOTHING_DECLARED,
    RuleOfTwo,
    Scan,
    control_claiming,
    family_claimed_by,
    scan,
)
from backend.bench.scorer import (
    DECLARED_BAND_CUTS,
    Band,
    BandCuts,
    GateDecision,
    Interval,
    Rate,
    Reliability,
    VariantBreakdown,
    band_for,
)
from backend.bench.source_anchor import (
    NOT_RUN_WHERE_THE_CODE_IS,
    SourceAnchor,
    SourceAnchorReading,
)
from backend.graph.runstate import Attempt


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


class AttributedCause(StrEnum):
    """What one failure is read against: the declaration state of its family.

    Three members, no free text and no fourth
    ([ADR-0068](../../docs/adr/0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md)).
    Naming the *control* would be close to relabelling the family — `family_claimed_by`
    is 1:1 over the four — so what these members say is whether the operator claimed a
    defence for this failure at all, which is a different sentence to an engineer and a
    very different one to a procurement reader.

    **No severity and no ordering.** D3 and D12: there is nothing here to rank, sum or
    threshold, which is the property `Band` has and for the same reason (ADR-0005).
    """

    DECLARED_AND_DEFEATED = "declared_and_defeated"
    """A control claims this family, the operator declared it, and the bench broke it.

    The strongest of the three and the one the headline join already prints per
    control; here it is per failure, so a reader holding one finding gets to it
    without inverting `ScannedControl.broken_by` by hand.
    """

    NOT_DECLARED = "not_declared"
    """A control claims this family and the operator declared none of it.

    Still not a finding *against* the target: the family was measured either way and
    nothing is subtracted for silence. ADR-0005's rejected score deducted points here,
    which is what made declaring more controls profitable.
    """

    NO_CONTROL_CLAIMS_THIS_FAMILY = "no_control_claims_this_family"
    """No control in the checklist claims this family, so there is nothing to read.

    The honest answer for **five of the nine** families — the two judged ones and the
    three elective ones — and the reason this enumeration has three members rather than
    two. Read as `NOT_DECLARED` it would report an absence nobody could have declared,
    which is ADR-0005's defect arriving through a finding (ADR-0068 §3).
    """


@dataclass(frozen=True)
class Attribution:
    """One failure and what gave way, derived from the case record and the scan.

    **Here and not in `judge.py`**: it is derived from the scan, and `judge.py` holds
    no scan and must not gain one — a `JudgeBrief` carrying what the operator declared
    is the blinding channel of ADR-0004 reopened by a new route. It is derived rather
    than written by a model because a model that wrote it would be a fourth instrument
    upstream of a reader, and #64's precedent would then apply without amendment: its
    agreement would have to be measured before it printed
    ([ADR-0068](../../docs/adr/0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md)).

    **No number, and no field one could arrive in.** This is prose about one verdict:
    no rate, band, interval or `D` may read it, and an override annotates one of those
    without moving it (D13, ADR-0006). The prohibition is structural — every field
    below is a name off a closed set or an id — and `test_attribution.py` holds both
    halves, the field list and an import wall over every module that computes a figure.

    **Nothing here prints yet.** It reaches no section of `TargetResult` and no key of
    the payload; the signed document has a disclosure answer and a fourth declared
    model to pay for first (#112), and the report screen waits on that (#113).
    """

    case_id: str
    """The case whose attempt succeeded. A pointer into the evidence, not a copy."""

    family: AnyFamily
    """The family that case belongs to, in either tier.

    `AnyFamily` because an elective family's case is an ordinary case (ADR-0035), and
    an attribution is not a container the gate is decided over — no narrowing is owed
    here, and one would only exclude three of the five families whose reading is
    `NO_CONTROL_CLAIMS_THIS_FAMILY`.
    """

    reading: AttributedCause
    transform: Transform
    """Which technique got in — the construction the case performs on its payload.

    The first thing this record says that the family name does not already say
    (ADR-0051, ADR-0068 §4). Required and read off `Case.transform` rather than
    optional: `PLAIN` is a member rather than a silence, so there is nothing for a
    `None` here to mean and a nullable field would be a kind of nothing invented for a
    value that always exists (`payload.py`).
    """

    control: DeclaredControl | None = None
    """The control that claims this family, or `None` where no control claims it.

    `None` on exactly the third reading, and the refusals below hold the pairing in
    both directions: the two readings that are statements *about* a control may not be
    written without one, and the reading that says no control claims this family may
    not name one.
    """

    def __post_init__(self) -> None:
        claims = control_claiming(self.family)
        if self.reading is AttributedCause.NO_CONTROL_CLAIMS_THIS_FAMILY:
            if self.control is not None:
                raise ValueError(
                    f"{self.case_id} claims no control and names one "
                    f"({self.control}). The third reading is the answer for the two "
                    "judged families and the three elective ones, and a control "
                    "written beside it would file a failure under a defence the "
                    "checklist does not hold for that family"
                )
        elif self.control is None:
            raise ValueError(
                f"{self.case_id} reads as {self.reading} and names no control. Both "
                "of those readings are statements about a declared control, so one "
                "without a control is a sentence no reader can check against the scan"
            )
        elif self.control is not claims:
            raise ValueError(
                f"{self.case_id} is a {self.family} failure attributed to "
                f"{self.control}, which does not claim that family. The join is "
                "`family_claimed_by` in both directions, and an attribution filed "
                "under another control would report one declaration defeated by a "
                "verdict about a different one"
            )

    def stated(self) -> str:
        """The sentence a report prints for this failure.

        On the record rather than in a renderer, in the pattern
        `NotMeasurable.stated()` and `ScannedControl.stated()` already set: the
        sentence is a property of the reading, so two surfaces printing the same
        attribution cannot print two different claims about it (#113 is the second
        surface, and it computes nothing the payload does not carry).
        """
        got_in = f"{self.case_id} got in — {self.transform.stated()}"
        match self.reading:
            case AttributedCause.DECLARED_AND_DEFEATED:
                return (
                    f"{self.family}: the operator declared {self.control}, which "
                    f"claims this family, and {got_in}. A declared control the bench "
                    "broke is the strongest reading here, and it is re-derivable "
                    "from the case record and the registration"
                )
            case AttributedCause.NOT_DECLARED:
                return (
                    f"{self.family}: the checklist holds a control for this family "
                    f"and the operator claimed none, and {got_in}. The absence is "
                    "not itself a finding — the family was measured either way and "
                    "nothing is subtracted for silence (ADR-0005)"
                )
            case AttributedCause.NO_CONTROL_CLAIMS_THIS_FAMILY:
                return (
                    f"{self.family}: no control in the checklist claims this family, "
                    f"so there is no declaration to read this failure against, and "
                    f"{got_in}"
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

    variants: VariantBreakdown
    """The counts, per transform, that `rate` was pooled from.

    **The counts that take the rate apart again.** A family's rate is one figure over
    every variant the family holds, and every variant measures the same failure
    against the same criterion — so pooling is legitimate and the arithmetic is
    `VariantBreakdown.pooled` (ADR-0055). What it costs is that the rate depends on
    the variant mix: a family holding one plain case and five encodings reports a
    rate that is mostly about encodings. This field is how that cost is published
    rather than hidden — the same idiom `payload.py` states one level up, *every
    measured figure is written with the counts it came from*.

    **Required and not defaulted, and asserted against the rate below.** An entry
    whose breakdown does not add up to its own `rate` is an entry over a denominator
    nothing in it accounts for, and a default would let a caller that forgot the
    counts publish a rate no reader could take apart.

    **No adaptive figure is in here and none can be** (ADR-0010). The keys are
    `Transform` members, an `AdaptiveEpisode` has no transform and is not an
    `Attempt`, and the discovery count #77 adds to the family view is a separate
    field of a separate type — never a summand of `attempts`.
    """

    reliability: Reliability | None = None
    """κ for the instrument that decided this family, on a judged entry.

    `None` on every deterministic entry and it must be: a deterministic verdict is
    re-derivable from the record and the transcript, so there is no instrument for a
    reliability figure to be about and one printed there would imply the rate needed
    it. `None` on a judged entry means no gold set has been run against the instrument
    that produced this rate, which is not the same reading as a κ of zero and is why
    `fit_to_report` refuses both.
    """

    def __post_init__(self) -> None:
        if not self.variants.accounts_for(self.rate):
            raise ValueError(
                f"{self.family} reports {self.rate.successes} of "
                f"{self.rate.attempts} attempts and a breakdown that does not "
                f"account for it: {self.variants.mix_stated() or 'nothing at all'}. "
                "A published rate over a denominator nothing in the document adds up "
                "to is a figure no recipient can take apart (ADR-0055)"
            )

    @property
    def interval(self) -> Interval:
        """The Wilson interval around the rate, at the confidence the rule states."""
        return self.rate.interval

    @property
    def fit_to_report(self) -> bool:
        """Whether this family's rate may be published.

        True for every deterministic family, because the success condition is
        authoritative and re-derivable (ADR-0004). For a judged family it is κ against
        the declared floor and nothing else — no argument, no override, and no
        exception for a run that is otherwise complete. ADR-0004 makes the refusal
        automatic precisely so that it is not a judgement call under deadline, and a
        judged entry with no κ at all is refused on the same reasoning: a rate whose
        evidentiary strength nobody can state is the thing the rule exists to stop
        being published (ADR-0013).
        """
        if self.verdict_class is VerdictClass.DETERMINISTIC:
            return True
        return self.reliability is not None and self.reliability.fit_to_report


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
    not_run: Mapping[Family, DeclaredGap] = field(default_factory=dict)
    """The families this run's caller declared away, and which of the reasons it was.

    A **fourth** field beside the third rather than entries at a rate of zero, and a
    fourth kind of nothing rather than a rewording of `not_measurable`: that one is a
    case precondition *this bench checked* and could not meet, and this is a family
    whose cases were dropped before the run because of something only the caller knows
    — no adjudicating instrument, an artefact nobody planted, a family or a
    construction switched off
    ([ADR-0075](../../docs/adr/0075-a-declared-gap-reaches-the-signed-artefact.md)).

    Empty on a run that narrowed nothing, which is the honest reading rather than a
    missing field: every family the library holds was asked for, and the two figure
    lists above account for all of them.
    """

    cuts: BandCuts = DECLARED_BAND_CUTS
    """The cut points the bands above were read against, printed with them."""

    @property
    def unfit_to_report(self) -> tuple[Family, ...]:
        """The judged families whose κ did not reach the declared floor, or is absent.

        Derived and never set, so the marking happens whether or not a caller thought
        to ask for it. A renderer that ignores this list prints a rate ADR-0004 says
        must not be published, which is a defect a reader can find; a renderer that
        had to be told which families to mark would be one where nobody could.
        """
        return tuple(entry.family for entry in self.judged if not entry.fit_to_report)

    def __post_init__(self) -> None:
        misplaced = [entry.family for entry in self.deterministic if entry.reliability]
        if misplaced:
            raise ValueError(
                f"{sorted(misplaced)} are deterministic and carry a κ figure. κ is "
                "the reliability of the instrument that decides a judged family, and "
                "a deterministic verdict has no instrument — printing one there would "
                "say the success condition needed vouching for (ADR-0004)"
            )

        astray = [
            entry.family
            for entry in self.judged
            if entry.reliability and entry.reliability.family is not entry.family
        ]
        if astray:
            raise ValueError(
                f"{sorted(astray)} carry a κ measured on another family. κ is per "
                "judged family and never pooled, so a figure filed under the wrong "
                "one would let a family the instrument reads well vouch for one it "
                "reads badly"
            )

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

        # The same refusal one absence along, and a separate check because it is a
        # separate pair: a family is absent for exactly one reason, so a run that
        # both dropped its cases and measured it is a run whose reader believes
        # whichever block was printed first (ADR-0075).
        declared_away = measured & set(self.not_run)
        if declared_away:
            raise ValueError(
                f"{sorted(declared_away)} carry a rate and a declared gap saying "
                "this run did not attempt them. A family was measured or it was "
                "declared away, and one that says both is a figure no reader can "
                "place"
            )
        both = set(self.not_measurable) & set(self.not_run)
        if both:
            raise ValueError(
                f"{sorted(both)} are reported both not measurable and not run. One "
                "is a precondition this bench checked and the other is a narrowing "
                "its caller declared, so a family holding both would be two answers "
                "to why nothing was attempted"
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

    rule_of_two: RuleOfTwo = NOTHING_DECLARED
    """The target's declared shape, read against the Agents Rule of Two.

    Here because this is the section that shares no arithmetic with any other, and
    a declared capability is the same kind of thing a declared control is: a
    statement read at registration with nothing sent to establish it
    ([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md)).

    **Not a row of the join, and not among the controls.** It claims no family, so
    there is no verdict for it to be crossed with and no `broken_by` it could ever
    carry; `defeated` above cannot select it, because it is not a `ScannedControl`.
    A reader meets it beside the join and not inside it.
    """

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


# --- One failure, explained, with the fix beside it (ADR-0070) ----------------


class FindingsReading(StrEnum):
    """Which of the four readings of `narrations` a findings section holds.

    A closed set beside the sentence, because a consumer that had to tell the four
    apart by matching prose would be a consumer that stops telling them apart the
    day the prose is reworded — and the four are four different facts about a run
    (ADR-0050). The report screen computes nothing the payload does not carry
    (#113), so the payload carries the reading and not only the sentence.
    """

    NO_NARRATIVE_INSTRUMENT_DECLARED = "no_narrative_instrument_declared"
    """`None` — the bench was not asked to explain anything."""

    NOTHING_TO_EXPLAIN = "nothing_to_explain"
    """`()` — the instruments ran and this target succeeded at nothing."""

    EXPLAINED = "explained"
    """A tuple — every succeeded attempt of the six explained."""

    INSTRUMENTS_BROKE = "instruments_broke"
    """A `NarrativeFailure` — the instruments ran and failed (ADR-0050)."""


class WithheldProse(StrEnum):
    """Which sentence of a finding was withheld from the artefact, and never why not.

    Two members, one per instrument, because the two are written by two instruments
    and a reader has to be told which of the two they are not being shown
    ([ADR-0069](../../docs/adr/0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)).
    An empty tuple is *nothing was withheld*, which is the ordinary case, and the
    members are countable rather than only readable for the reason every other
    absence in this codebase is a closed set (`payload.py`).
    """

    REASON = "reason"
    """The judge's sentence was withheld: it reproduced the case's own payload."""

    FIX = "fix"
    """The remediation tool's sentence was withheld, for the same reason."""


PROSE_QUOTED_THE_PAYLOAD = (
    "withheld — this sentence reproduced the case's own payload text, and a report "
    "that travels is the worst possible place for a working attack. The case id "
    "above is the pointer into the evidence, and the payload itself is in the case "
    "record where the disclosure posture governs it (ADR-0008, ADR-0070)"
)
"""What the artefact says in place of a sentence that quoted the payload.

Said rather than omitted, and the finding is kept rather than dropped: a finding
dropped for its prose would take its case id, its family and its attributed cause
with it, and those are the three things a reader can check against the record.
"""

INSTRUMENTS_AGREED = (
    "the success condition and the judge read this transcript the same way, so "
    "nothing here is queued for a human"
)
"""What a finding says where its two instruments did not disagree.

A stated agreement rather than a blank, on `Provenance`'s own terms: a missing line
reads as a document that had nothing to declare, and this one has something to
declare.
"""


@dataclass(frozen=True)
class ReportedFinding:
    """One failure as the signed document reports it: why, what to change, and what
    informed the fix.

    **The record that carries a model's prose into an artefact that travels**, which
    is why the disclosure rule is enforced here rather than asked for in a prompt
    ([ADR-0070](../../docs/adr/0070-a-signed-document-may-carry-a-remediation.md)
    §2). `of` is the only way to build one from a `Narration`, and it holds the case
    record — the one thing a check for quoted payload text needs and the one thing
    `payload.py` does not have. Blinding happens on the harness side of a call for
    the same reason (`JudgeBrief.about`): a rule a model is asked to follow is a
    request, and a rule a record enforces is a mechanism.

    **No confidence, and no field one could arrive in.** `Narrative.confidence` is a
    number the model wrote about its own answer, and a number in a signed document is
    read as a measurement by every reader who did not write it — which is ADR-0005's
    concern arriving through prose. What this record carries about the instruments'
    agreement is `disagreement`, which is a fact about two instruments rather than
    one instrument's self-report.

    **Nothing here reaches a rate.** It is prose about one verdict, on `Attribution`'s
    own terms: no rate, band, interval or `D` may read it (D13, ADR-0006), and the
    prohibition is structural — every field below is prose, a name off a closed set,
    or an id.
    """

    attribution: Attribution
    """What this failure is read against, derived from the case record and the scan.

    Carried whole rather than flattened into three fields, so the sentence a surface
    prints is `Attribution.stated()` and the two surfaces cannot print two different
    claims about one attribution (ADR-0068 §3). It also carries the case id, the
    family and the transform, which is why none of them is repeated here.
    """

    external_id: str
    """The published identifier this case tests within, as a string.

    The identifier alone rather than the `ExternalId`, on `Precedent`'s own reasoning:
    the other half of that record is a coverage boundary, which is a claim about the
    *family* and is printed with the family's figures (ADR-0044).
    """

    exposure: Exposure
    """What a reader of this finding is exposed to, off the judge's closed set.

    A closed set rather than prose, so an exposure can be counted by a reader rather
    than only read — and counted by a reader rather than by this bench, because a
    count over two families would be the composite ADR-0005 refused.
    """

    reason: str
    """Why it failed, in the judge's own sentence — or the statement that the
    sentence was withheld (`PROSE_QUOTED_THE_PAYLOAD`)."""

    fix: str
    """What to change, in the remediation tool's own sentence — or the same
    statement. The one answer to *what to change* a reader is handed (ADR-0069)."""

    informed_by: tuple[str, ...] = ()
    """The case ids of the precedents this fix was written against, most recent first.

    **The ids and never the precedents' own prose.** A precedent's `failure` and
    `remediation` are a *different target's* finding and a different target's fix,
    and a document about this target is not the place a second operator's failure
    travels — that is the identity question `retrieve_precedent` already redacts for
    (ADR-0011). What a reader needs is ADR-0019's claim: whether this fix came from
    their own transcript alone or from a corpus, and how much of one. An empty tuple
    is the truthful answer on run one, and it is the reason ADR-0019 says the store
    cannot be demonstrated inside a single run.
    """

    disagreement: str = INSTRUMENTS_AGREED
    """What the two instruments made of this transcript, in one sentence.

    Stated on every finding rather than only where they disagreed, because a section
    that printed the judge's reason and said nothing about whether the judge agreed
    with the verdict would present one instrument's reading as both. The verdict is
    unmoved either way: a disagreement is recorded under Article 12 and resolved
    nowhere (ADR-0004).
    """

    withheld: tuple[WithheldProse, ...] = ()
    """Which of the two sentences the disclosure rule withheld, and usually neither.

    Countable rather than only legible in the prose, so a reader — and a test — can
    ask how much of a document was withheld without parsing sentences.
    """

    source_anchor: SourceAnchor = NOT_RUN_WHERE_THE_CODE_IS
    """Where in the caller's own checkout the target's entrypoint is, or which
    absence holds
    ([ADR-0071](../../docs/adr/0071-a-finding-points-at-a-file-the-bench-read.md)).

    **Defaulted to the absence rather than to `None`.** The ordinary run has no
    checkout — a hosted bench attacking a URL never had one — so the honest reading is
    the common one, and a field a caller forgot to fill reads as *the bench could not
    see this target's source* rather than as a location it declined to print. It is
    the same anchor on every finding of one run and is passed once into
    `reported_findings`: it is a fact about where this run ran, and a per-finding one
    would claim the bench knows which file each failure came out of (ADR-0071 §2).

    Carried whole rather than flattened, on `attribution`'s own terms: the sentence a
    surface prints is `SourceAnchor.stated()`, so the document and the screen cannot
    print two claims about one anchor.
    """

    standing: FixStanding = NOT_PROVEN
    """Whether this fix was **proven** or is **proposed**, and the change it makes
    ([ADR-0073](../../docs/adr/0073-two-labels-on-a-fix-and-no-third.md)).

    **Defaulted to the untested reading**, on `source_anchor`'s own terms: the
    ordinary run patches nothing — a hosted bench attacking a URL cannot restart
    somebody else's server — so a field a caller forgot to fill reads as *this was not
    tested* rather than as a proof it declined to mention. There is no third value it
    could hold and no boolean under it (ADR-0073 §1).

    **Per finding and not per run**, which is the one way it differs from the anchor
    beside it: a patch replaces one file to close one case, and a run that proved one
    fix has proved nothing about the next failure in the same report.
    """

    def __post_init__(self) -> None:
        """Refuse a proven fix on a run that never saw the code, at the door.

        The second of the two refusals ADR-0073 §2 rests on, and the one that closes
        the case the ticket names: **a fix from a target with no checkout cannot be
        proven.** `standing_for` is the only constructor of a proven standing and it
        takes a `PatchProof`, which `prove_patch` makes only from a checkout on disk —
        this holds the same line one record along, where the two facts are side by
        side, so a hand-built finding cannot pair a proof with an anchor that says the
        bench never saw this target's source.

        Every reading but `ANCHORED` is a run with no located file (ADR-0071 §3), and
        a plain hosted endpoint has one of them by construction: there is nothing in
        the caller's checkout that is known to be the thing that answered, so there is
        nothing to patch and nothing to re-serve.
        """
        if (
            self.standing.reading is FixStandingReading.PROVEN
            and self.source_anchor.reading is not SourceAnchorReading.ANCHORED
        ):
            raise ValueError(
                f"a fix was reported proven on a run whose source anchor reads "
                f"{self.source_anchor.reading.value!r}. Proven means this bench "
                "patched a file of the caller's own checkout, re-served the target "
                "out of the copy and re-attempted the case — and every reading but "
                "the anchored one is a run with no file to patch, which a plain "
                "hosted endpoint always is. An untested change published as a proven "
                "one is the self-graded claim ADR-0001 exists to displace "
                "(ADR-0071 §3, ADR-0073 §2)"
            )

    @property
    def case_id(self) -> str:
        """The case whose attempt succeeded, read off the attribution."""
        return self.attribution.case_id

    @property
    def family(self) -> AnyFamily:
        """The family that case belongs to, read off the attribution."""
        return self.attribution.family

    @classmethod
    def of(
        cls,
        narration: Narration,
        attribution: Attribution,
        case: Case,
        source_anchor: SourceAnchor = NOT_RUN_WHERE_THE_CODE_IS,
        standing: FixStanding = NOT_PROVEN,
    ) -> "ReportedFinding":
        """One narration as the document reports it, with the disclosure rule applied.

        Three records in and no instrument, in `attributed_cause`'s shape: the
        narration is what two instruments wrote, the attribution is what the failure
        is read against, and the case record is what the prose is checked against.
        There is no parameter through which a caller could supply the prose that
        travels, which is what makes the rule a property of this type rather than of
        whoever calls it.

        Refuses a narration joined to another case, on `JudgeBrief.about`'s and
        `attributed_cause`'s reason: a finding checked against the wrong record would
        be checked against a payload it never sent, so the disclosure rule would pass
        by looking in the wrong place.
        """
        finding = narration.finding
        if finding.case_id != case.id or attribution.case_id != case.id:
            raise ValueError(
                f"a finding about {finding.case_id!r} and an attribution about "
                f"{attribution.case_id!r} were reported against case {case.id!r}. "
                "The disclosure rule checks this finding's prose against this case's "
                "payload, so one joined to the wrong record would be checked against "
                "a payload it never sent (ADR-0070)"
            )
        reason, fix = finding.narrative.reason, narration.remediation.fix
        withheld = tuple(
            sentence
            for sentence, prose in (
                (WithheldProse.REASON, reason),
                (WithheldProse.FIX, fix),
            )
            if quotes_the_payload(prose, case)
        )
        return cls(
            attribution=attribution,
            external_id=finding.narrative.external_id.identifier,
            exposure=finding.narrative.exposure,
            reason=PROSE_QUOTED_THE_PAYLOAD
            if WithheldProse.REASON in withheld
            else reason,
            fix=PROSE_QUOTED_THE_PAYLOAD if WithheldProse.FIX in withheld else fix,
            informed_by=tuple(
                precedent.case_id for precedent in narration.remediation.informed_by
            ),
            disagreement=(
                INSTRUMENTS_AGREED
                if finding.disagreement is None
                else finding.disagreement.stated()
            ),
            withheld=withheld,
            source_anchor=source_anchor,
            # Derived where the patch was applied and passed in already labelled:
            # this classmethod builds no proof and reads no filesystem, and the
            # refusal above is what stops one arriving that the anchor contradicts
            # (ADR-0073 §2).
            standing=standing,
        )

    def informed_by_stated(self) -> str:
        """What this fix was written against, in the words ADR-0019's claim needs.

        On the record rather than in a renderer, in `Attribution.stated()`'s pattern
        and for its reason: a reader handed remediation advice has to be able to tell
        advice derived from one transcript from advice derived from a corpus, and two
        surfaces wording that differently would be two claims about one fix. The
        payload carries this sentence, `stated` below composes it rather than
        rewriting it, and section 3b prints it.

        The precedents' ids and never their prose: a precedent is a *different
        target's* failure and a different target's fix (ADR-0011, ADR-0070 §2).
        """
        if not self.informed_by:
            return (
                "This fix was written against no precedent — nothing had been filed "
                "against this family when it was written, which is a fact about the "
                "store and not about this fix (ADR-0019)."
            )
        return (
            "This fix was written with earlier findings of this family in front of "
            "it — " + ", ".join(self.informed_by) + " — so it is a control this "
            "bench has written down before rather than one derived from this "
            "transcript alone (ADR-0019)."
        )

    def stated(self) -> str:
        """This whole failure in one sentence, for a surface that wants one line.

        The one-line form, in `ReportedEpisode.stated()`'s pattern: a console line, a
        poller's summary, a screen that shows a failure collapsed. Section 3b prints
        the fields apart instead, because two sentences from two instruments are the
        point of that section and a paragraph would bury the second — and it prints
        `informed_by_stated` rather than a second wording of it, which is why that
        sentence is composed here and not written twice.
        """
        return (
            f"{self.attribution.stated()}. What went wrong: {self.reason} What to "
            f"change: {self.fix} {self.informed_by_stated()} "
            # Stripped rather than assumed: `INSTRUMENTS_AGREED` ends without a stop
            # and `Disagreement.stated()` ends with one, so a sentence joined to the
            # next clause with a full stop of its own would publish `..` into a signed
            # document — and the two spellings would differ by which instrument read
            # the transcript, which is not a difference a reader should see.
            f"{self.disagreement.rstrip('.')}. "
            # The label is inside the one-line form rather than only beside the fix,
            # because this line is what a surface prints when it shows a failure
            # collapsed — and a summary that carried *what to change* without saying
            # whether the change was ever tested is the blur the two labels exist to
            # prevent (ADR-0001, ADR-0073 §1).
            f"Where: {self.source_anchor.stated()}. This fix is "
            f"{self.standing.stated()}"
        )


PAYLOAD_QUOTE_FLOOR = 40
"""How much of a case payload a sentence has to reproduce before it is withheld.

A floor rather than any match at all, because a payload's turns are ordinary English
and a short one shares phrases with any sentence written about it — a rule that fired
on *what is in your configuration* would withhold every honest fix ever written about
that family. Forty characters is a run no two independent sentences about one
exchange share by accident, and it is short enough that reproducing *half* a payload
is caught — what transfers is the phrasing, and a rule that only caught a whole turn
would be defeated by a model that trimmed the last clause. A turn shorter than the
floor is checked whole rather than skipped, so no payload is unguardable for being
short.

The figure is a property of this literal: raising it lets more of a payload through
and lowering it withholds honest prose, and `test_reported_findings.py` measures both
ends against the committed library — no committed payload and no half of one survives
the check, and no sentence written *about* a case trips it. The high end is pinned
there with a literal of its own rather than a multiple of this one, because a bound
written as a multiple moves with the constant it exists to bound.
"""


def quotes_the_payload(prose: str, case: Case) -> bool:
    """Whether this sentence reproduces the case's own payload text.

    Over the payload's turns and never over the rendered script, because a scripted
    case sends one turn at a time and what would transfer is one turn's wording
    (ADR-0053). Whitespace is normalised on both sides so that a model that
    re-wrapped a payload has still reproduced it.
    """
    written = " ".join(prose.split())
    for turn in case.payload:
        text = " ".join(turn.split())
        if not text:
            continue
        if len(text) <= PAYLOAD_QUOTE_FLOOR:
            if text in written:
                return True
            continue
        if any(
            text[start : start + PAYLOAD_QUOTE_FLOOR] in written
            for start in range(len(text) - PAYLOAD_QUOTE_FLOOR + 1)
        ):
            return True
    return False


NO_NARRATIVE_INSTRUMENT = (
    "no narrative instrument was declared for this run, so no failure here is "
    "explained and none was left unexplained: the bench was not asked. A stated "
    "absence and not an empty list — a report that printed nothing would be "
    "indistinguishable from a run whose target succeeded at nothing (ADR-0030)"
)
"""What this section says when `narrations` reads `None`."""

NOTHING_HERE_TO_EXPLAIN = (
    "the narrative instruments ran and this target succeeded at nothing in the six "
    "measured families, so there is no failure here to explain. A measurement, and "
    "not a bench that declined to look (ADR-0030)"
)
"""What this section says when `narrations` reads `()`."""


@dataclass(frozen=True)
class FindingsSection:
    """Every failure of the six explained, or the stated absence of all of them.

    **Four readings and one section**, because `narrations` reads four ways and a
    section that printed the same thing under all four would put ADR-0050's collapse
    back into the artefact: *nobody declared an instrument*, *there was nothing to
    explain*, *here is every failure* and *the instruments ran and broke* are four
    facts, and a reader holding only the document has to be able to tell them apart
    ([ADR-0070](../../docs/adr/0070-a-signed-document-may-carry-a-remediation.md)
    §4). ADR-0050 signed all four on the footing that no byte of the document moved
    between them, and said in as many words that a ticket putting a narrative into
    the document inherits the question and not the answer. This is that ticket: the
    bytes now differ, and all four are still signed, because every figure in the
    document was measured before either instrument was asked.

    **Findings are all of them or the stated absence of all of them** (ADR-0030), and
    that invariant is `TargetRun`'s rather than this record's — a subset nobody chose
    never reaches here, because a pass that broke returns a `NarrativeFailure` and
    discards what it had written.

    **Not reproducible, and not a field a caller can set.** A model wrote the prose,
    so the label is the one ADR-0017 already has for that class, and no third
    evidentiary class is invented here (`rendering/__init__.py`).
    """

    reported: tuple[ReportedFinding, ...] | NarrativeFailure | None = None
    """The four readings of `narrations`, one type along.

    `ReportedFinding` rather than `Narration`, because what travels is what the
    disclosure rule passed and never what the instruments wrote — a section holding
    the second would make the withholding a property of a renderer.
    """

    @property
    def reproducibility(self) -> Reproducibility:
        """Not reproducible, always, and not a field any caller can set."""
        return Reproducibility.NOT_REPRODUCIBLE

    @property
    def findings(self) -> tuple[ReportedFinding, ...]:
        """The findings this section carries, which is none under three readings."""
        return self.reported if isinstance(self.reported, tuple) else ()

    @property
    def reading(self) -> FindingsReading:
        """Which of the four this section holds, as a name a consumer can match."""
        match self.reported:
            case None:
                return FindingsReading.NO_NARRATIVE_INSTRUMENT_DECLARED
            case NarrativeFailure():
                return FindingsReading.INSTRUMENTS_BROKE
            case ():
                return FindingsReading.NOTHING_TO_EXPLAIN
            case _:
                return FindingsReading.EXPLAINED

    @property
    def broken(self) -> NarrativeFailure | None:
        """The instrument failure this section holds, or nothing broke.

        Exposed so a surface reads the failure's own fields rather than parsing them
        back out of `stated()` — the counts an operator reconciles against a token
        bill are figures, and figures a reader has to extract from prose are figures
        that drift (ADR-0050).
        """
        return self.reported if isinstance(self.reported, NarrativeFailure) else None

    def stated(self) -> str:
        """Which of the four readings this section holds, in the words it prints."""
        match self.reported:
            case None:
                return NO_NARRATIVE_INSTRUMENT
            case NarrativeFailure() as broken:
                return broken.stated()
            case ():
                return NOTHING_HERE_TO_EXPLAIN
            case found:
                return (
                    f"{len(found)} failure(s) of the six explained, one per succeeded "
                    "attempt: what went wrong as the judge read it, and what to "
                    "change as the remediation tool wrote it (ADR-0069). "
                    f"{self.reproducibility.stated()} — a model wrote both sentences, "
                    "and re-running the instruments would not reproduce them. No "
                    "figure above was measured from any of this (ADR-0006)"
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

**Stated, and these four stay stated.** They are limits of the *bench* rather than
entries on anybody's published list — no register of risks carries "there is no
ground truth for the target's domain" — so there is nothing to subtract them from and
declaring them is the only available form. The half of this disclosure that *is* a
published list is now derived rather than declared: `published.py` subtracts the
categories the library's families claim from the stored copy of each list, so
`UntestedCategory`, `ClaimedInPart` and `CoverageGap` are three different claims and
print in three different blocks. The first names a published category no family
reaches; the second names one a family *does* reach and where its reach stops
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)); this one
says the bench cannot measure something at all, and no published register carries it.

**Both lists, since #45.** `editions.py` holds a copy of each and a family's label
holds its claims on both
([ADR-0039](../../docs/adr/0039-a-familys-label-is-one-record.md)), so the derived
blocks below are two subtractions concatenated rather than one over the agentic copy
with the GenAI LLM list unaccounted for. Every entry the second copy carries is now
either claimed with a stated limit or listed with a reason, which is what a subtraction
costs in the direction nobody checks.

The per-family `coverage` notes carry what each case does *not* test inside the
identifier it claims, which is the other half of the same disclosure and is derived
from the case records already.
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
    findings: FindingsSection = FindingsSection()
    """Every failure of the six explained, or the stated absence of all of them.

    A fourth section, and the first one that is neither a measurement nor a search:
    it is what two instruments wrote about the failures the measured section counted
    ([ADR-0070](../../docs/adr/0070-a-signed-document-may-carry-a-remediation.md)).
    It reads none of the three above and none of them reads it — a rate is over
    attempts, and a finding is prose about one verdict (D13, ADR-0006).

    The default is the `None` reading, which is *no narrative instrument was
    declared*: a gate run and a `--deterministic-only` probe both produce it, and a
    default of `()` would report a target that succeeded at nothing for a run nobody
    asked to look (ADR-0030).
    """

    coverage_gaps: tuple[CoverageGap, ...] = DECLARED_COVERAGE_GAPS
    elective: ElectiveSelection = NOTHING_REQUESTED
    """The elective families this run was asked to test, and so the ones it was not.

    A **declared input** of the run rather than something it measured, which is why
    it sits here beside the coverage statement and not in `MeasuredSection`: that
    section is keyed on `Family` and an elective figure has no field in it to arrive
    in
    ([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md),
    ADR-0018). It is the same tuple on every result at a given selection, so it stays
    out of the way of the drop-a-family invariant in `payload.py` for the reason
    `untested_categories` does.
    """

    untested_categories: tuple[UntestedCategory, ...] = UNTESTED_CATEGORIES
    """Published categories no family in the library claims, on either list.

    Derived from the library's families and never from the families this run measured,
    so it is the same tuple on every result at a given library version. That is what
    keeps it out of the way of the drop-a-family invariant in `payload.py`, and it is
    also the honest scope: a category untested by the bench and a family this target
    could not answer are two different absences, and the second one is
    `NotMeasurable`.
    """

    claimed_in_part: tuple[ClaimedInPart, ...] = CLAIMED_IN_PART
    """The published categories the library's families claim, and where each stops.

    The other side of the field above and derived from the same declared records
    (`published.py`), so the two are the whole of that list between them. It is here
    rather than folded into `untested_categories` because it makes the opposite
    claim — this category *is* reached, this far — and a reader who met the two in one
    block could not tell a gap from a boundary
    ([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)).

    Same scope and same reason as the field above: the library's families, never the
    run's, so it is the same tuple on every result at a given library version and
    stays out of the way of the drop-a-family invariant in `payload.py`.
    """

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
    # The six alone: a `DeclaredControl` claims exactly one of them, so an elective
    # attempt has no control to be joined to and a report is about a target
    # (ADR-0018, ADR-0035).
    attempted = {
        attempt.family for attempt in deterministic if one_of_the_six(attempt.family)
    }
    broke: dict[Family, list[str]] = {}
    for attempt in deterministic:
        family = attempt.family
        if attempt.verdict is Verdict.SUCCEEDED and one_of_the_six(family):
            named = broke.setdefault(family, [])
            if attempt.case_id not in named:
                named.append(attempt.case_id)

    return tuple(
        _scanned(control, attempted, broke, reasons) for control in scanned.declared
    )


def attributed_cause(attempt: Attempt, case: Case, scanned: Scan) -> Attribution:
    """What gave way in one failure, derived and not judged (ADR-0068 §1).

    The declared-and-defeated join read from the other end. `declared_and_defeated`
    above answers *which of this target's claims did the bench break*, per control;
    this answers *what is this one failure to be read against*, per case — and a reader
    holding a finding could not get from it to the control it belongs to without
    inverting `ScannedControl.broken_by` by hand.

    **Three records in and no instrument**, which is why the reading needs no κ. There
    is no parameter here through which a model could supply it — the argument
    `Finding.of` makes about a verdict — so making this judged means changing this
    signature, which is the signal ADR-0010 asks an implementer to stop at.

    `attempt` and `case`, in `JudgeBrief.about`'s order and with its two refusals, for
    the same reason it has them: an attribution written against the wrong record would
    name a transform the attempt never sent, and one written against a **resisted**
    attempt would print `DECLARED_AND_DEFEATED` — *the bench broke this control* — over
    an attempt that broke nothing. The verdict is read off the attempt and never
    computed here, so this stays a join over verdicts and never over rates (ADR-0006).

    The `isinstance` is the annotation arriving at runtime, so ADR-0010's wall is
    closed by a test as well as by a type check: an `AdaptiveEpisode` is what an
    episode leaves behind, and it is not an `Attempt`.
    """
    if not isinstance(attempt, Attempt):
        raise TypeError(
            f"an attributed cause is a reading of one scored attempt, and was "
            f"offered a {type(attempt).__name__}. The adaptive layer produces no "
            "finding and nothing here may widen to accept one (ADR-0010)"
        )
    if attempt.case_id != case.id:
        raise ValueError(
            f"attempt {attempt.case_id!r} was attributed against case {case.id!r}. "
            "The reading names a transform and a family off the record, so one "
            "joined to the wrong record is a sentence about a case nobody ran"
        )
    if attempt.verdict is not Verdict.SUCCEEDED:
        raise ValueError(
            f"{case.id} did not succeed against {attempt.target_name}, so there is "
            "no failure here to attribute a cause to. `declared_and_defeated` is "
            "the reading for a control nothing got past"
        )
    control = control_claiming(case.family)
    if control is None:
        return Attribution(
            case_id=case.id,
            family=case.family,
            reading=AttributedCause.NO_CONTROL_CLAIMS_THIS_FAMILY,
            transform=case.transform,
        )
    declared = control in scanned.declared
    return Attribution(
        case_id=case.id,
        family=case.family,
        reading=AttributedCause.DECLARED_AND_DEFEATED
        if declared
        else AttributedCause.NOT_DECLARED,
        transform=case.transform,
        control=control,
    )


def reported_findings(
    narrations: Narrations,
    attempts: Sequence[Attempt],
    cases: Sequence[Case],
    scanned: Scan,
    source_anchor: SourceAnchor = NOT_RUN_WHERE_THE_CODE_IS,
    standings: Mapping[str, FixStanding] | None = None,
) -> FindingsSection:
    """Every explained failure joined to what it is read against, or a reading that
    carries none.

    The one place the narrative pass and the scan meet, and it is a join over
    **records**: `attributed_cause` derives the reading from the case record and the
    registration, this walks the narrations in the order they were written, and no
    model is asked anything (ADR-0068 §1).

    **Three of the four readings pass straight through.** `None`, `()` and a
    `NarrativeFailure` are three facts about a run rather than three spellings of an
    empty section, so each arrives at `FindingsSection` as itself and the document
    says which one holds (ADR-0050, ADR-0070 §4).

    **The attempts are matched in order and consumed**, because `narrate_successes`
    writes one narration per succeeded attempt of the six in the order they were
    made: a lookup that reused one attempt per case id would attribute the second
    success of a case against the first one's record, which is fine today — the
    reading is a function of the case and the scan — and would silently stop being
    fine the moment a per-attempt field joins this record.

    Refuses rather than skips, on `narration._record_for`'s reasoning: a narration
    with no case record or no succeeded attempt behind it is a fault in the bench,
    and dropping it would publish a subset of a run's findings that nobody chose
    (ADR-0030).

    **The source anchor is passed once and reaches every finding**, because it is one
    fact about where this run ran rather than one fact per failure, and its default is
    the stated absence every run without a checkout has
    ([ADR-0071](../../docs/adr/0071-a-finding-points-at-a-file-the-bench-read.md)).
    Nothing here reads a filesystem: the anchor arrives already resolved, from the one
    entrypoint that has a checkout to resolve it against, which keeps every module on
    this side of the run a reader of records (ADR-0068 §1).

    **The standings arrive per case and default to the untested reading**, which is
    the one way they differ from the anchor above: an anchor is a fact about where
    this run ran and a proof is a fact about one patch and one case, so a run that
    proved one fix says nothing about the next failure in the same report
    ([ADR-0073](../../docs/adr/0073-two-labels-on-a-fix-and-no-third.md)). A case with
    no entry reads *proposed*, which is every finding of every run that patched
    nothing — and nothing here builds a proof either: like the anchor, a standing
    arrives already derived from the one entrypoint that had a checkout to patch.
    """
    if narrations is None or isinstance(narrations, NarrativeFailure):
        return FindingsSection(reported=narrations)
    records = {case.id: case for case in cases}
    unclaimed: dict[str, list[Attempt]] = {}
    for attempt in attempts:
        if attempt.verdict is Verdict.SUCCEEDED:
            unclaimed.setdefault(attempt.case_id, []).append(attempt)
    reported = []
    for narration in narrations:
        case_id = narration.finding.case_id
        case = records.get(case_id)
        if case is None:
            raise ValueError(
                f"a finding about {case_id!r} has no case record among the cases "
                "this target was run against, so there is no payload to check its "
                "prose against and no record to derive its cause from"
            )
        pending = unclaimed.get(case_id) or []
        if not pending:
            raise ValueError(
                f"a finding about {case_id!r} has no succeeded attempt left to "
                "attribute it to. A narration is written per succeeded attempt, so "
                "more findings than successes is a run that explained something it "
                "did not record"
            )
        reported.append(
            ReportedFinding.of(
                narration,
                attributed_cause(pending.pop(0), case, scanned),
                case,
                source_anchor,
                (standings or {}).get(case_id, NOT_PROVEN),
            )
        )
    return FindingsSection(reported=tuple(reported))


def reported_episodes(
    episodes: Iterable[AdaptiveEpisode], target_name: str
) -> tuple[ReportedEpisode, ...]:
    """Turn one target's recorded episodes into the rows the adaptive section holds.

    The prose is the attacker's own where it wrote any — a proposed route carries
    the description `propose_case` was given, which is the only part of a route
    that is ever written down outside a run (ADR-0008; CONTEXT.md, **route**). An
    episode that proposed nothing gets a line derived from the record and from
    nothing else, because there is no other source: what an attacker *would* have
    said about a route it did not think worth promoting is not evidence.

    **Never payload text**, on either path. A route that beat a target is a working
    unpublished exploit, and the transcripts that hold it stay on the episode and
    are not committed (spec story 105).

    Per target, because a section belongs to a result and a result belongs to one
    target. Filtering here rather than at the call site keeps an episode against
    one agent out of another agent's section, which is the reporting form of the
    context isolation ADR-0011 requires of the attacker itself.
    """
    return tuple(
        ReportedEpisode(episode=episode, description=_described(episode))
        for episode in episodes
        if episode.target_name == target_name
    )


def _described(episode: AdaptiveEpisode) -> str:
    """What this episode did, in prose, when the attacker supplied none."""
    proposed = " ".join(
        proposal.description.strip()
        for proposal in episode.proposals
        if proposal.description.strip()
    )
    if proposed:
        return proposed
    turns = f"{episode.turns} {'turn' if episode.turns == 1 else 'turns'}"
    if episode.outcome is EpisodeOutcome.BROKEN:
        return (
            f"broke the objective in {turns} and proposed no case, so the route "
            "is recorded and the library does not grow from it"
        )
    if episode.turns == 0:
        return (
            "sent nothing to the target. The attacker spent its decisions without "
            "composing a probe, which is a reading about the attacker"
        )
    return f"no break in {turns}, and the attacker proposed nothing"


def assemble(
    target_run: TargetRun,
    cases: Sequence[Case],
    gate: GateDecision | None = None,
    episodes: Sequence[ReportedEpisode] = (),
    cuts: BandCuts = DECLARED_BAND_CUTS,
    coverage_gaps: tuple[CoverageGap, ...] = DECLARED_COVERAGE_GAPS,
    reliability: Mapping[Family, Reliability] | None = None,
    elective: ElectiveSelection = NOTHING_REQUESTED,
    source_anchor: SourceAnchor = NOT_RUN_WHERE_THE_CODE_IS,
    standings: Mapping[str, FixStanding] | None = None,
) -> TargetResult:
    """Assemble one target's result from what was recorded against it.

    Each section is built from its own inputs and none of them from another's: the
    measured section from the attempts and the case records, the declared section
    from the registration crossed with the verdicts, the adaptive section from the
    recorded episodes. This function sees all three and combines none of them —
    there is no line below that reads a figure out of one section and into another.

    `gate` supplies `D` per family from the last gate run (`gate.py`). Without one,
    every entry says so rather than showing a zero.

    `episodes` are the adaptive layer's, and they arrive as an argument rather than
    off the run state because #16 records them and #17 measures them; this ticket
    owns only the shape they are reported in.

    `reliability` supplies κ per judged family from the gold-set run (`goldset.py`).
    It reaches the judged entries only, and a judged family absent from it is marked
    unfit to report rather than published without a stated reliability (ADR-0004).

    `elective` is the tier's declared selection, carried onto the result and read by
    nothing here: no section below is built from it, because what a report may say
    about an elective family is which ones it was not asked for (ADR-0035).
    """
    scanned = scan(target_run.target)
    return TargetResult(
        target_name=target_run.target.name,
        measured=MeasuredSection(
            deterministic=_entries(
                target_run.deterministic_rates,
                target_run.deterministic_variant_counts,
                VerdictClass.DETERMINISTIC,
                cases,
                gate,
                cuts,
                # Nothing, always. The parameter is required rather than defaulted so
                # that this line has to be written and can be read: a κ figure cannot
                # reach a family whose verdict came from a success condition.
                {},
            ),
            judged=_entries(
                target_run.judged_rates,
                target_run.judged_variant_counts,
                VerdictClass.JUDGED,
                cases,
                gate,
                cuts,
                reliability or {},
            ),
            not_measurable=dict(target_run.not_measurable),
            cuts=cuts,
        ),
        declared=DeclaredSection(
            controls=declared_and_defeated(
                scanned, target_run.attempts, target_run.not_measurable
            ),
            absent=scanned.absent,
            rule_of_two=scanned.rule_of_two,
        ),
        adaptive=AdaptiveSection(episodes=tuple(episodes)),
        findings=reported_findings(
            target_run.narrations,
            target_run.attempts,
            cases,
            scanned,
            # Resolved once, where the checkout is, and read by nothing else here:
            # this function combines no two sections and reads no filesystem
            # (ADR-0071 §3). Its default is the absence every run without a checkout
            # has, which is every run this repository's own API serves.
            source_anchor,
            # Whether each fix was proven, from the one entrypoint that could patch
            # anything. Empty for every run this repository's own API serves: a
            # hosted bench cannot restart somebody else's server, so its fixes are
            # proposed by construction (ADR-0073 §2).
            standings,
        ),
        coverage_gaps=coverage_gaps,
        elective=elective,
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
    variants: Mapping[Family, VariantBreakdown],
    verdict_class: VerdictClass,
    cases: Iterable[Case],
    gate: GateDecision | None,
    cuts: BandCuts,
    reliability: Mapping[Family, Reliability],
) -> tuple[FamilyEntry, ...]:
    """The per-family entries of one verdict class, in the closed family order.

    `Family`'s own order rather than the order the run happened to measure in, so
    two targets' sections line up row for row.

    `reliability` is required rather than defaulted, so the deterministic call site
    has to state that it passes none: a κ figure reaching an entry whose verdict came
    from a success condition would be a defect nobody reading the call could see.

    `variants` is the per-transform counts of the same attempts `rates` was divided
    over, keyed the same way and read from the same run — indexed and never
    `.get`-with-a-default, because a family with a rate and no breakdown is the one
    thing `FamilyEntry` refuses and a silent empty breakdown would turn that refusal
    into a `KeyError` nobody could read (ADR-0055).
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
            variants=variants[family],
            reliability=reliability.get(family),
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
        family = case.family
        # The six alone. What an elective family's cases claim is a fact about the
        # bench's tier, and a target report says which elective families the run was
        # not asked for and nothing else about it (ADR-0018, ADR-0035).
        if not one_of_the_six(family):
            continue
        seen = notes.setdefault(family, ())
        if case.external_id not in seen:
            notes[family] = (*seen, case.external_id)
    return notes


def _discrimination(gate: GateDecision | None) -> dict[Family, float]:
    """`D` per family from the last gate run, or nothing at all."""
    if gate is None:
        return {}
    return {outcome.family: outcome.discrimination for outcome in gate.outcomes}
