"""The gate: the whole library against the three reference agents, decided.

This is the deliverable of the spec — a stated, falsifiable rule that can return
*this bench measures nothing*. The arithmetic is `scorer.py`'s and the thresholds
are `rule.py`'s; what lives here is the step between a run and a decision, which is
reading each family's three rates off the three reference agents and handing all six
families to `decide_gate`.

**The gate is decided on the scored layer alone, and the signature is how.**
`read_gate` is handed `TargetRun`s — registrations, attempts and verdicts — and
nothing else. An `AdaptiveEpisode` lives on the run state, never on a target run, so
there is no argument here through which one could arrive and no field for one to be
read out of. A weak attacker therefore cannot fail a working bench and a lucky one
cannot pass a broken one, which is the property ADR-0010 exists to keep: this module
imports nothing from `backend/bench/adaptive/`, and a test fails if that changes.

**The three agents are named by role, never taken positionally.** `D` is
`trivial − hardened` and is not symmetric, so a call site that swapped the two ends
would invert the bench's central claim and report a broken instrument as a working
one. The names arrive as required keyword arguments from the entry point, because
the reference agents are test equipment and the bench does not import its own test
equipment.

**A family the bench cannot vouch for is excluded, never scored a fail.** A judged
family below the κ floor and a family the target could not answer both leave the fit
set, both print with the reason and the reading that barred them, and neither
supplies evidence to either half of the decision (ADR-0015). Their rates are still
measured and still recorded: the attempts were made, and a measured rate stays
measured (ADR-0006).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.bench.calibration import TargetRun
from backend.bench.elective import (
    NOTHING_ELECTIVE,
    NOTHING_REQUESTED,
    ElectiveRates,
    ElectiveSection,
    ElectiveSelection,
    score_elective,
)
from backend.bench.library import (
    EMPTY_LIBRARY,
    Case,
    Family,
    LibraryVersion,
    one_of_the_six,
)
from backend.bench.measurability import NotMeasurable
from backend.bench.reproducibility import Reproducibility
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import (
    FamilyOutcome,
    FamilyRates,
    GateDecision,
    Rate,
    Reliability,
    decide_gate,
    score_family,
)

REPRODUCIBILITY = (
    "the gate decision above is re-derivable from its recorded inputs — the "
    "attempts, the case records and the rule printed with it — and the adaptive "
    "layer of the same run is recorded rather than re-derivable. Both statements "
    "are printed, because a run that claimed one of them without the other would "
    "be claiming the stochastic half was reproducible by omission (ADR-0010)"
)
"""The scoping ADR-0010 requires, stated on both sides in one place."""


class NotAGateRun(ValueError):
    """These runs cannot be gated, and saying so beats deciding on part of them.

    Raised rather than worked around, because every route to a smaller denominator
    is a route to a gate that passes on less evidence than the rule demands. A
    family missing from one agent and present on another is not an exclusion — it
    is a run that did not happen the way the gate needs it to.
    """


@dataclass(frozen=True)
class GateResult:
    """What a gate run decided, and everything a reader needs to re-derive it.

    The decision, the rule it was taken under, every per-family rate and interval
    behind it, the κ of each judged family, and the library version the whole thing
    was measured against. A reader holding this and `scorer.py` can recompute the
    pass or fail without the bench (spec stories 47, 76 and 80).
    """

    decision: GateDecision
    library: LibraryVersion
    reliability: Mapping[Family, Reliability | None]
    """κ per judged family, `None` for a judged family measured against no gold set.

    Present whatever it says, including where it barred a family: an exclusion whose
    cause is not printed is an exclusion a reader has to take on trust.
    """

    attempts: int
    """Every attempt recorded, whatever its outcome (spec story 79)."""

    agents: tuple[str, ...]
    """The reference agents this gate was decided over, in the order they ran."""

    elective: ElectiveSection = NOTHING_ELECTIVE
    """What this run measured in the elective tier, and what it did not ask for.

    Beside the `GateDecision` and deliberately not inside it
    ([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)),
    on the discipline ADR-0010 established for the adaptive layer: the part of a run
    that decides nothing reports beside the decision rather than within it, so there
    is no field of the decision an elective figure could be reached through. Every
    figure here was measured by the arithmetic the decision above was taken by, and
    not one of them is in either of its counts.
    """

    @property
    def passed(self) -> bool:
        return self.decision.passed

    @property
    def stops_the_build(self) -> bool:
        """Whether this result stops the build. Anything that is not a pass does.

        A fail and a *not decided* stop it for different reasons and both stop it:
        one says the bench does not discriminate, the other says too little of it
        was fit to be asked. Carrying on past either would make the gate a ceremony
        (spec story 45).
        """
        return not self.decision.passed

    def stated(self) -> str:
        """The whole gate run as it is printed and as it is recorded."""
        lines = [
            "gate run — the scored layer, and the scored layer decides it alone",
            f"  {self.library.stated()}",
            f"  reference agents: {', '.join(self.agents)}",
            f"  {self.attempts} attempts recorded, every one of them whatever its "
            "outcome",
        ]
        for outcome in self.decision.outcomes:
            lines.extend(f"  {line}" for line in stated_outcome(outcome).splitlines())
        for family, measured in sorted(self.reliability.items()):
            lines.append(
                f"  {family}: "
                + (
                    measured.stated()
                    if measured is not None
                    else "no κ was measured against the gold set, so the family is "
                    "not fit to report and decides nothing here"
                )
            )
        lines.append("")
        lines.extend(self.decision.stated().splitlines())
        lines.append("")
        # After the decision and never among the figures above it: a reader working
        # toward the answer must not meet a D that is not part of it (ADR-0035, and
        # the placement ADR-0010 gives the adaptive layer's own section).
        lines.extend(f"  {line}" for line in self.elective.stated().splitlines())
        lines.append("")
        lines.append(f"  {Reproducibility.RE_DERIVABLE.stated()}")
        lines.append(f"  {REPRODUCIBILITY}")
        return "\n".join(lines)


def stated_outcome(outcome: FamilyOutcome) -> str:
    """One family's three rates, its `n`, its `D`, its ordering and its verdict.

    Every number the per-family pass turned on, printed beside the verdict rather
    than instead of it, so that a reader re-derives the line rather than trusting it.

    **`n` prints here because this is where the counts are.** `GateRule` used to
    state *three cases per family, so n = 30*, which was the one expression in this
    bench that asserted the library's shape rather than reading it — and the
    admission gate can now grow a family
    ([ADR-0033](../../docs/adr/0033-an-admitted-route-is-written-into-the-library.md)).
    The rule holds thresholds and no library, so the denominator is counted off the
    attempts that ran and printed beside the rates it is the denominator of.
    """
    rates = outcome.rates
    return "\n".join(
        (
            f"{outcome.family}:",
            *(
                f"  {name:<9} {stated_rate(rate)}"
                for name, rate in (
                    ("hardened", rates.hardened),
                    ("weak", rates.weak),
                    ("trivial", rates.trivial),
                )
            ),
            f"  n = {stated_denominator(rates)}, counted off the attempts that ran",
            f"  D = {outcome.discrimination:.2f}, intervals "
            f"{'do not overlap' if outcome.intervals_separate else 'overlap'}, "
            f"{outcome.monotonicity.inversions} inversion"
            f"{'' if outcome.monotonicity.inversions == 1 else 's'} "
            f"({'ordered' if outcome.monotonicity.holds else 'NOT ordered'}) — "
            f"{'passes' if outcome.passes else 'does not pass'}",
        )
    )


def stated_denominator(rates: FamilyRates) -> str:
    """This family's `n` per agent, or the three counts where there is no one `n`.

    One number when the three agents were attempted the same number of times, which
    is every run against three registered reference agents: `n` is
    `attempts_per_case` times the cases the library holds in this family, and it is
    read off the counts rather than computed from the library so that the figure
    printed is the figure the rates were divided by.

    **Three counts when they differ, and the words that say so.** A family whose
    agents were not attempted equally has no single denominator, and one printed for
    it would be a figure no rate was read at — the same refusal `Rate` makes by
    carrying its own `attempts` ("3 successes in 30 attempts and 100 in 1000 are the
    same number and not the same evidence"). The counts are on the rates above this
    line either way; what this adds is that no one of them is the family's `n`.
    """
    counted = (rates.hardened.attempts, rates.weak.attempts, rates.trivial.attempts)
    if len(set(counted)) == 1:
        return f"{counted[0]} attempts per agent"
    hardened, weak, trivial = counted
    return (
        f"hardened {hardened}, weak {weak}, trivial {trivial} — not one "
        "denominator, so this family has no single n"
    )


def stated_rate(rate: Rate) -> str:
    """A failure rate with the counts it came from and its interval."""
    return (
        f"{rate.value:.2f} ({rate.successes}/{rate.attempts}), "
        f"[{rate.interval.lower:.3f}, {rate.interval.upper:.3f}]"
    )


def family_rates(
    target_runs: Sequence[TargetRun],
    *,
    trivial: str,
    weak: str,
    hardened: str,
) -> tuple[tuple[FamilyRates, ...], dict[Family, NotMeasurable]]:
    """Each family's three rates, and the families no rate could be read for.

    Two return values rather than one, because they are two different facts and
    the gate treats them differently: the first is weighed, the second is excluded
    with its reason printed. A family measured against some of the three agents and
    not others is neither — it is a run that cannot be gated, and it says so.
    """
    by_agent = {run.target.name: run.rates for run in target_runs}
    missing = [name for name in (trivial, weak, hardened) if name not in by_agent]
    if missing:
        raise NotAGateRun(
            f"the gate is decided over three reference agents and {missing} did not "
            "run. D is trivial minus hardened and monotonicity is read across all "
            "three, so a missing agent is a missing decision rather than a smaller one"
        )

    measured: list[FamilyRates] = []
    unmeasured: dict[Family, NotMeasurable] = {}
    for family in Family:
        rates = {name: by_agent[name].get(family) for name in (trivial, weak, hardened)}
        present = {name: rate for name, rate in rates.items() if rate is not None}
        if len(present) == 3:
            measured.append(
                FamilyRates(
                    family=family,
                    hardened=present[hardened],
                    weak=present[weak],
                    trivial=present[trivial],
                )
            )
            continue
        reason = _refusal(family, target_runs)
        if present or reason is None:
            raise NotAGateRun(
                f"{family} was measured against {sorted(present)} and not against "
                f"{sorted(set(rates) - set(present))}, and no target reported it "
                "not measurable. A family that ran against some of the reference "
                "agents and not others has no D and no ordering, and so has one "
                "whose every case was skipped as written for another agent type — "
                "a gate decided without either would be decided on a denominator "
                "nobody declared"
            )
        unmeasured[family] = reason
    return tuple(measured), unmeasured


def cited_library(cases: Sequence[Case]) -> LibraryVersion:
    """The library version a gate run cites: the six's, whatever else also ran.

    A gate run asked for an elective family runs the tier's cases in the same suite,
    and the version travels a long way — into the gate document, into the gate run
    record, and onto every report's **gate citation**, which is what tells a reader
    whether the bench's last gate run was made against the library in front of them
    (ADR-0023). A version that moved with the selection would make two gate runs over
    an identical six-family library read as incomparable because one of them was also
    asked for the tier, which is a lever on comparability the operator should not
    hold (ADR-0035).

    So the filter is here rather than at the call site: a caller that hands over
    everything that ran still cites the six, and the tier is named in the elective
    section beside the decision instead.
    """
    return LibraryVersion.of(case for case in cases if one_of_the_six(case.family))


def elective_section(
    target_runs: Sequence[TargetRun],
    *,
    trivial: str,
    weak: str,
    hardened: str,
    selection: ElectiveSelection = NOTHING_REQUESTED,
    rule: GateRule = DECLARED_RULE,
) -> ElectiveSection:
    """What this gate run measured in the elective tier, scored by the gate's rule.

    The counterpart of `family_rates` one tier down, and it reads
    `TargetRun.elective_rates` — the second mapping ADR-0035 asks for beside the one
    `family_rates` reads, so an elective count has no route into either of the gate's
    two
    ([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
    `score_elective` applies `scorer.separation`, which is the same implementation of
    the per-family condition `score_family` reads: *selectable is not ungated*.

    **It raises nothing, and that is the one place it deliberately differs from
    `family_rates`.** A family measured against some of the three agents and not
    others has no `D` and no ordering, and `family_rates` stops the run over it —
    rightly, because the gate is decided over those figures. Here there is no
    decision to protect: a family without three rates simply takes no reading, and
    `ElectiveSection.requested_and_unmeasured` names it. A tier able to stop a gate
    run would be a tier deciding something.
    """
    measured = {run.target.name: run.elective_rates for run in target_runs}
    outcomes = []
    for family in selection.requested:
        rates = {
            name: measured.get(name, {}).get(family)
            for name in (trivial, weak, hardened)
        }
        present = {name: rate for name, rate in rates.items() if rate is not None}
        if len(present) < 3:
            continue
        outcomes.append(
            score_elective(
                ElectiveRates(
                    family=family,
                    hardened=present[hardened],
                    weak=present[weak],
                    trivial=present[trivial],
                ),
                rule,
            )
        )
    return ElectiveSection(selection=selection, outcomes=tuple(outcomes))


def read_gate(
    target_runs: Sequence[TargetRun],
    *,
    trivial: str,
    weak: str,
    hardened: str,
    reliability: Mapping[Family, Reliability] | None = None,
    library: LibraryVersion | None = None,
    rule: GateRule = DECLARED_RULE,
    elective: ElectiveSection = NOTHING_ELECTIVE,
) -> GateResult:
    """Decide the gate from what the scored layer recorded, and say how.

    `reliability` is the gold-set run's κ per judged family (`goldset.py`). A judged
    family absent from it is carried into the decision as *no figure* rather than
    quietly weighed: what it lacks is a statable evidentiary strength, and how it
    came to lack one changes nothing about whether the gate may rest on it
    (ADR-0004, ADR-0015).

    `library` is the version the attempts were made against, off the run state. It
    is not recomputed here from anything: a version derived at reporting time would
    describe the library as it is now rather than the one that ran.

    `elective` is what the run measured in the elective tier, already scored by
    `elective.score_elective`. It is carried onto the result and reaches nothing
    else: it is not an argument of `decide_gate`, there is no `ElectiveFamily` in
    `Family`, and the loop below iterates the six — so the tier has no route to
    either count, and handing this one a family that clears every clause of the
    per-family rule changes no field of the decision (ADR-0035).
    """
    measured, unmeasured = family_rates(
        target_runs, trivial=trivial, weak=weak, hardened=hardened
    )
    judged = {
        family
        for run in target_runs
        for family in run.judged_rates
        if family not in unmeasured
    }
    readings: dict[Family, Reliability | None] = {
        family: (reliability or {}).get(family) for family in sorted(judged)
    }
    outcomes = [score_family(rates, rule) for rates in measured]
    return GateResult(
        decision=decide_gate(
            outcomes, reliability=readings, not_measurable=unmeasured, rule=rule
        ),
        library=library or EMPTY_LIBRARY,
        reliability=readings,
        attempts=sum(len(run.attempts) for run in target_runs),
        agents=tuple(run.target.name for run in target_runs),
        elective=elective,
    )


def _refusal(family: Family, target_runs: Sequence[TargetRun]) -> NotMeasurable | None:
    """Why this family could not be measured, from whichever run said so."""
    for run in target_runs:
        reason = run.not_measurable.get(family)
        if reason is not None:
            return reason
    return None
