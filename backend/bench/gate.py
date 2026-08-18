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
from backend.bench.library import Family, LibraryVersion
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
        lines.append(f"  {Reproducibility.RE_DERIVABLE.stated()}")
        lines.append(f"  {REPRODUCIBILITY}")
        return "\n".join(lines)


def stated_outcome(outcome: FamilyOutcome) -> str:
    """One family's three rates, its `D`, its ordering and its verdict.

    Every number the per-family pass turned on, printed beside the verdict rather
    than instead of it, so that a reader re-derives the line rather than trusting it.
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
            f"  D = {outcome.discrimination:.2f}, intervals "
            f"{'do not overlap' if outcome.intervals_separate else 'overlap'}, "
            f"{outcome.monotonicity.inversions} inversion"
            f"{'' if outcome.monotonicity.inversions == 1 else 's'} "
            f"({'ordered' if outcome.monotonicity.holds else 'NOT ordered'}) — "
            f"{'passes' if outcome.passes else 'does not pass'}",
        )
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
                f"{sorted(set(rates) - set(present))}, with no stated reason. A "
                "family that ran against some of the reference agents and not "
                "others has no D and no ordering, and a gate decided without it "
                "would be decided on a denominator nobody declared"
            )
        unmeasured[family] = reason
    return tuple(measured), unmeasured


def read_gate(
    target_runs: Sequence[TargetRun],
    *,
    trivial: str,
    weak: str,
    hardened: str,
    reliability: Mapping[Family, Reliability] | None = None,
    library: LibraryVersion | None = None,
    rule: GateRule = DECLARED_RULE,
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
        decision=decide_gate(outcomes, readings, unmeasured, rule),
        library=library or LibraryVersion.of([]),
        reliability=readings,
        attempts=sum(len(run.attempts) for run in target_runs),
        agents=tuple(run.target.name for run in target_runs),
    )


def _refusal(family: Family, target_runs: Sequence[TargetRun]) -> NotMeasurable | None:
    """Why this family could not be measured, from whichever run said so."""
    for run in target_runs:
        reason = run.not_measurable.get(family)
        if reason is not None:
            return reason
    return None
