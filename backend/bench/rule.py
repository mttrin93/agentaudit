"""The gate rule as declared configuration — every threshold as data, never inline.

ADR-0003 fixes the rule before the code that evaluates it exists, for one reason:
a threshold written inline is a threshold that can be quietly moved at hour 30 to
make a run pass. Holding the numbers in one declared record is what lets the gate
print the rule beside its result, so a reader sees what the bench had to beat.

Nothing here is read from a file or an environment variable. Configuration means
declared, not deployment-tunable: a gate whose bar changes with an environment is
a gate that proves nothing about the library that passed it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GateRule:
    """The stated numbers of ADR-0003. The defaults are the declared rule."""

    interval_confidence: float = 0.90
    """The confidence of the Wilson interval carried by every rate."""

    attempts_per_case: int = 10
    """How many times one case is run against one target.

    Three cases per family at ten attempts is ADR-0003's n = 30 per family per
    agent — the sample size chosen so that the retirement rule can operate, not
    merely so the gate can pass. It sits with the thresholds because moving it
    moves every interval the gate is decided on.
    """

    discrimination_floor: float = 0.4
    """What `D` must reach for a family to pass, and for a case to be admitted.

    One number for both, deliberately: a case may not enter the library on a
    weaker bar than the gate later holds its family to.
    """

    retirement_floor: float = 0.25
    """The `D` below which a case has stopped discriminating.

    Applied over two consecutive gate runs *on one model*, so that one bad night does
    not retire a working case and a change of instrument is not read as the passage of
    time (ADR-0022). The window is `backend/bench/retirement.py`, read over the series
    a gate run stores on each case record; the number is declared here because it
    belongs to the same rule as the floor above it.
    """

    kappa_floor: float = 0.6
    """The Cohen's κ below which a judged family is not fit to report.

    Measured against the gold set by the reliability work (#11, and the figure it
    read is on `completion.DEFAULT_ADJUDICATOR_MODEL`); declared
    here so the bench's accuracy thresholds are stated in one place.
    """

    gold_transcripts_per_family: int = 15
    """How many hand-labelled transcripts one judged family's κ is measured over.

    Fifteen per judged family, thirty in total (spec stories 33 and 34), and stated
    here for the same reason `attempts_per_case` is: it is the denominator the
    reliability figure is read on, so moving it moves what κ means. A figure computed
    over some other number of transcripts is not the declared figure, and
    `goldset.py` refuses to produce one.
    """

    tolerated_inversions: int = 1
    """How far the hardened ≤ weak ≤ trivial ordering may break on one family.

    One, so the rule is strict without being brittle: three agents give two
    adjacent comparisons, and tolerating both would make the check vacuous.
    """

    family_count: int = 6
    """The six families the gate is decided over — the denominator of both counts."""

    families_required: int = 4
    """How many families must pass for the gate to pass. Four of six."""

    monotonic_families_required: int = 5
    """How many families must order the reference agents correctly. Five of six.

    Higher than the pass count because ordering is the claim construction
    licenses, so the bench is held to a stricter bar on it (ADR-0003).
    """

    minimum_fit_families: int = 5
    """How few families the gate may still be decided on. Five (ADR-0015).

    A family the bench cannot vouch for — a judged family below `kappa_floor`, or
    one the target could not answer at all — is **excluded** from the decision
    rather than scored a fail or force-passed, so the denominator can shrink. Five
    is the smallest denominator on which both counts above remain satisfiable at
    all, and below it the gate returns **not decided**, which is a stop and never a
    fail.

    The two counts stay counts and never become fractions of this denominator. A
    fraction would pay a run for degrading its own instrument: the same six
    outcomes with three families passing fail at six fit and would pass at four,
    with nothing changed but the adjudicator getting less reliable. Fixed counts
    satisfy the invariant that exclusion is never a lever — excluding a family can
    only remove a candidate, never move the bar (ADR-0015).
    """

    def attempts_per_family(self) -> int:
        """`n` per family per agent: three cases at this many attempts each.

        ADR-0003's n = 30 at the declared rule, and the number every sentence about
        the denominator quotes — here rather than at each of them, because a run at
        another `attempts_per_case` has to state its own `n` and four inline
        multiplications are four places to get that wrong. The three is the cases per
        family the library holds (#12); a library that held another number would move
        this, which is why the sentences read it from one method.
        """
        return 3 * self.attempts_per_case

    def at_the_declared_denominator(self) -> bool:
        """Whether `attempts_per_case` is the number ADR-0003 declared.

        The one number of this record the console may set (ADR-0025), so it is the one
        a report may honestly state a different value for. Everything else here is
        declared and never tuned, which is why a verifier asserts the rest against
        `DECLARED_RULE` and reads this one (ADR-0027).
        """
        return self.attempts_per_case == DECLARED_RULE.attempts_per_case

    def denominator_stated(self) -> str:
        """What the report says about the denominator these figures were counted on.

        A sentence beside the number rather than the number alone, on the same terms
        as `DeclaredModels.temperature_stated`: the value cannot say by itself whether
        it is the published `n` or an operator's cheaper reading, and a reader who has
        to know ADR-0003's ten by heart to tell is a reader who will not tell.

        Carried into the signed payload and printed in the rendered document, so the
        departure travels with the artefact instead of staying in the console that
        offered it (ADR-0027). It is re-derived from the number in
        `verification._declared_bar`, so a payload cannot state one and mean the other.
        """
        if self.at_the_declared_denominator():
            return (
                f"{_attempts(self.attempts_per_case)} per case — the declared "
                "denominator of ADR-0003, so these figures were counted on the "
                f"published n = {self.attempts_per_family()} per family"
            )
        return (
            f"{_attempts(self.attempts_per_case)} per case where the declared rule "
            f"reads {DECLARED_RULE.attempts_per_case}, so "
            f"n = {self.attempts_per_family()} per family and not the published "
            f"{DECLARED_RULE.attempts_per_family()}. {NOT_A_GATE_RESULT}"
        )

    def stated(self) -> str:
        """The rule as the gate prints it beside its result.

        Printed rather than summarised, because a pass means nothing without the bar
        it cleared, and because a threshold nobody can read is a threshold that can
        be moved (ADR-0003).

        **Nothing here is an adaptive threshold and there is nowhere for one to
        live.** `T` and `k` are declared in `AdaptiveBudget`; this record holds the
        numbers that decide, and the adaptive layer decides nothing (ADR-0010).
        """
        return "\n".join(
            (
                "the decision rule as applied, from ADR-0003 and ADR-0015:",
                f"  n = {self.attempts_per_case} attempts per case, three cases per "
                f"family, so n = {self.attempts_per_family()} per family per agent",
                f"  per-family pass: D ≥ {self.discrimination_floor:.2f} and the "
                f"hardened and trivial Wilson "
                f"{self.interval_confidence:.0%} intervals do not overlap",
                "  monotonicity: hardened ≤ weak ≤ trivial across all three "
                f"reference agents, {self.tolerated_inversions} inversion tolerated",
                f"  a judged family below κ = {self.kappa_floor:.2f} against the "
                "gold set is not fit to report and is excluded from the decision; "
                "so is a family the target could not answer",
                f"  the gate passes only at {self.families_required} of "
                f"{self.family_count} families passing and monotonicity on "
                f"{self.monotonic_families_required} of {self.family_count} — fixed "
                "counts, never fractions of the fit-to-report denominator",
                f"  decided on no fewer than {self.minimum_fit_families} fit "
                "families; below that the gate is not decided, which is a stop and "
                "not a fail",
                "  no adaptive threshold appears above: T and k are declared in "
                "AdaptiveBudget, and nothing that decides nothing belongs in the "
                "rule the gate prints (ADR-0010)",
            )
        )


NOT_A_GATE_RESULT = (
    "**This is not a gate result.** A run at another number is a real run and its "
    "rates carry the rule they were measured at, but nothing may compare it to a "
    "reading taken at the declared rule: the Wilson interval, the band, monotonicity "
    "and the retirement rule are all defined against n = 30 per family (ADR-0003), "
    "the band's cut points were chosen for that n and lose resolving power below it "
    "(ADR-0014), and `scripts/gate.py` takes no setting from any console (ADR-0025)"
)
"""What a report measured at a non-declared denominator says about itself.

One wording, read by the payload, the rendered document and the verifier, because a
second would only have to disagree once for a document to state a run is comparable
where its verification says it is not (ADR-0027).
"""


def _attempts(number: int) -> str:
    """`1 attempt` or `n attempts`, so the sentence above reads as English."""
    return f"{number} attempt" if number == 1 else f"{number} attempts"


DECLARED_RULE = GateRule()
"""The rule the bench is held to. Every scorer function reads this by default.

An alternative `GateRule` exists for one purpose — asking what a run would have
decided under a different bar — and a decision built from one carries that rule
with it, so a report can never present it as the declared one.
"""
