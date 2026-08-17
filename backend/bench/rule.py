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
