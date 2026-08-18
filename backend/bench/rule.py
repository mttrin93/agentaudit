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

    Applied over two consecutive gate runs, so one bad night does not retire a
    working case. The two-run part of the rule arrives with the decay series
    (#12); the number is declared here because it belongs to the same rule.
    """

    kappa_floor: float = 0.6
    """The Cohen's κ below which a judged family is not fit to report.

    Measured against the gold set by the judge reliability work (#8); declared
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


DECLARED_RULE = GateRule()
"""The rule the bench is held to. Every scorer function reads this by default.

An alternative `GateRule` exists for one purpose — asking what a run would have
decided under a different bar — and a decision built from one carries that rule
with it, so a report can never present it as the declared one.
"""
