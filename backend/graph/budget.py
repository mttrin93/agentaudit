"""What a run will cost, the most it may spend, and the abort when it would spend more.

A run is a denial-of-wallet attack the bench performs on its own user: 180 target
calls in the scored layer and up to 96 more in the adaptive layer, every one of
them on the operator's own endpoint and their own inference spend. So the cost
display here is a **consent mechanism, not a convenience feature** (ADR-0007),
and everything in this module exists to keep it honest.

**Two figures, and they are never one figure.** The scored layer is arithmetic —
cases times attempts, known exactly before anything runs. The adaptive layer is a
worst case, because an attacker that chooses its own route spends unpredictably by
construction. A `CallFigure` therefore carries whether it is a fact or a bound,
and adding a fact to a bound yields a bound: the epistemic status is arithmetic
here rather than prose, so no consumer can present a total as though it were
exact. Showing an *average* adaptive cost is the one thing explicitly forbidden —
it would be worse than showing nothing, because it invites a run to exceed what
the user agreed to.

**Calls, not attempts.** The budget counts sends on the wire, retries included,
because a retried message reaches the endpoint and costs the operator what it
cost. An attempt is the unit of a denominator and is deliberately not this number
(CONTEXT.md).

**The ceiling is not the estimate.** The estimate says what the run costs when
nothing has to be retried; the declared ceiling is what it may not exceed when
everything does. Both are shown, and neither is derived from the other by a
comfortable-looking margin: the ceiling is the estimate times the transport's own
retry limit, which is the tight worst case of the policy the bench already
declares in `contract.py`. That relationship is what lets the budget be checked
*before* each message rather than detected after it — a run that stays inside its
arithmetic can always cover the worst case of its next message, so a well-behaved
run is never aborted early and a misbehaving one never overspends.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.contract import TargetConfig
from backend.bench.library import Case
from backend.bench.rule import DECLARED_RULE, GateRule

REGISTRATION_PROBES_PER_TARGET = 1
"""The nonce echo probe, which is a call on the operator's endpoint like any other.

Inside the estimate rather than beside it: a consent figure that quietly omitted
the calls registration makes would understate what the run costs, and it is also
what the scored ceiling has to cover — a suite budgeted at exactly its attempts
would abort on the registration probe of its first target.
"""


class Layer(StrEnum):
    """The two halves of a run, as budget counters.

    Two counters rather than one, because a single blended figure would hide which
    half of a run is spending (ADR-0007). They are enforced independently for the
    same reason they are reported separately.
    """

    SCORED = "scored"
    ADAPTIVE = "adaptive"


class FigureKind(StrEnum):
    """Whether a call count is a fact or a bound. Carried, never inferred."""

    EXACT = "exact"
    CEILING = "ceiling"


@dataclass(frozen=True)
class CallFigure:
    """A number of target calls, together with what kind of number it is."""

    calls: int
    kind: FigureKind
    basis: str
    """The arithmetic in words, so a reader can check the figure rather than
    believe it."""

    def __post_init__(self) -> None:
        if self.calls < 0:
            raise ValueError("a call figure cannot be negative")

    @property
    def is_exact(self) -> bool:
        return self.kind is FigureKind.EXACT

    def __add__(self, other: CallFigure) -> CallFigure:
        """Add two figures, keeping the weaker of the two kinds.

        A fact plus a bound is a bound. This is the whole reason `FigureKind`
        exists: the total of an exact suite and a capped layer is not exact, and
        the only way to be sure nobody ever prints it as though it were is to make
        the addition itself unable to produce one.
        """
        both_exact = self.is_exact and other.is_exact
        kind = FigureKind.EXACT if both_exact else FigureKind.CEILING
        return CallFigure(
            calls=self.calls + other.calls,
            kind=kind,
            basis=f"{self.basis}; plus {other.basis}",
        )

    def rendered(self) -> str:
        """`180` or `≤ 96` — the kind visible in the number itself."""
        return f"{self.calls}" if self.is_exact else f"≤ {self.calls}"


@dataclass(frozen=True)
class Estimate:
    """What a run will cost, as two figures that are never blended into one."""

    scored: CallFigure
    adaptive: CallFigure

    def __post_init__(self) -> None:
        if not self.scored.is_exact:
            raise ValueError(
                "the scored layer's figure is arithmetic and has to be exact; a "
                "bound there would hide that the fixed suite's cost is known"
            )
        if self.adaptive.is_exact:
            raise ValueError(
                "the adaptive layer's figure has to be a ceiling; an attacker "
                "choosing its own route has no exact cost, and an average one "
                "invites a run to exceed what the operator agreed to (ADR-0007)"
            )

    @property
    def total(self) -> CallFigure:
        """The two figures added, which makes the total a ceiling and never a fact."""
        return self.scored + self.adaptive

    def lines(self) -> tuple[str, ...]:
        """The estimate as ADR-0007 presents it: a fact, a bound, and a bounded
        total."""
        rows = (
            ("Scored layer", self.scored),
            ("Adaptive layer", self.adaptive),
        )
        width = max(len(figure.rendered()) for _, figure in (*rows, ("", self.total)))
        rendered = [
            f"  {label:<16}{figure.rendered():>{width}} calls   "
            f"{figure.kind} — {figure.basis}"
            for label, figure in rows
        ]
        rendered.append(f"  {'':<16}{'─' * (width + 6)}")
        rendered.append(
            f"  {'Total':<16}{self.total.rendered():>{width}} calls   "
            f"{self.total.kind} — a fact plus a bound is a bound"
        )
        return tuple(rendered)


class LayerFigurePayload(TypedDict):
    """One layer's figure, as a machine-readable record for the approval surface."""

    calls: int
    kind: str
    basis: str


class BudgetPayload(TypedDict):
    """The whole consent surface as JSON-safe primitives.

    A `TypedDict` of primitives rather than the records themselves, because this
    is what crosses an interrupt into a checkpoint now and an HTTP response at
    6b, and both want the same thing. `presented` carries the rendered table so
    that a terminal and a browser show a user the identical figures.
    """

    scored: LayerFigurePayload
    adaptive: LayerFigurePayload
    total: LayerFigurePayload
    scored_ceiling: int
    adaptive_ceiling: int
    retry_allowance: int
    presented: list[str]


class BudgetExceeded(RuntimeError):
    """A run aborted rather than spend past what the operator confirmed.

    Raised before the message that would breach the ceiling goes on the wire, so
    the abort is a refusal rather than a discovery. It is loud on purpose: a run
    that stopped early measured fewer attempts than the rate it would report is
    denominated on, so a partial run is void rather than smaller.
    """

    def __init__(self, layer: Layer, ceiling: int, spent: int, requested: int) -> None:
        self.layer = layer
        self.ceiling = ceiling
        self.spent = spent
        self.requested = requested
        super().__init__(
            f"the {layer} layer has spent {spent} of a declared {ceiling} calls, "
            f"and the next message needs up to {requested} more: aborting rather "
            "than spend past the estimate the operator confirmed"
        )


@dataclass(frozen=True)
class RunBudget:
    """The declared maximum a run may spend, per layer, beside the estimate it
    was declared against.

    The estimate travels with the ceiling rather than beside it in a caller's
    variables, on the same reasoning as `TargetRun.rule`: a limit that has become
    separated from the figures it was computed from is a limit nobody can check.
    """

    estimate: Estimate
    scored_ceiling: int
    adaptive_ceiling: int
    retry_allowance: int
    """How many times one message may go on the wire, from the transport's own
    retry policy. The ceilings are the estimate times this."""

    def __post_init__(self) -> None:
        if self.scored_ceiling < self.estimate.scored.calls:
            raise ValueError(
                "a scored ceiling below the exact cost of the suite would abort "
                "every complete run"
            )
        if self.adaptive_ceiling < self.estimate.adaptive.calls:
            raise ValueError(
                "an adaptive ceiling below the layer's own worst case is the "
                "second ceiling of ADR-0007 set below the first"
            )

    @classmethod
    def declare(
        cls,
        cases: Sequence[Case],
        targets: Sequence[TargetConfig],
        rule: GateRule = DECLARED_RULE,
        adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET,
    ) -> RunBudget:
        """Work out both numbers from the run's own inputs.

        One constructor for the estimate and the ceiling together, so that the
        limit cannot be declared against a different library than the figures the
        operator was shown.
        """
        attempts = len(cases) * rule.attempts_per_case
        per_target = REGISTRATION_PROBES_PER_TARGET + attempts
        scored = CallFigure(
            calls=len(targets) * per_target,
            kind=FigureKind.EXACT,
            basis=(
                f"{_count(len(cases), 'case')} × {rule.attempts_per_case} attempts "
                f"+ {_count(REGISTRATION_PROBES_PER_TARGET, 'registration probe')}, "
                f"× {_count(len(targets), 'target')}"
            ),
        )
        adaptive_figure = CallFigure(
            calls=len(targets) * adaptive.turn_ceiling,
            kind=FigureKind.CEILING,
            basis=(
                f"{adaptive.family_count} families × T={adaptive.turns_per_episode}"
                f" × k={adaptive.episodes_per_family},"
                f" × {_count(len(targets), 'target')}"
            ),
        )
        estimate = Estimate(scored=scored, adaptive=adaptive_figure)
        allowance = max((target.retry.sends for target in targets), default=1)
        return cls(
            estimate=estimate,
            scored_ceiling=scored.calls * allowance,
            adaptive_ceiling=adaptive_figure.calls * allowance,
            retry_allowance=allowance,
        )

    def ceiling(self, layer: Layer) -> int:
        """The ceiling over one layer. Read per layer, never summed: the two are
        enforced independently, so a layer with room left cannot borrow from the
        other's unspent allowance."""
        return self.scored_ceiling if layer is Layer.SCORED else self.adaptive_ceiling

    def lines(self) -> tuple[str, ...]:
        """The estimate, then the ceiling that is enforced over it."""
        return (
            *self.estimate.lines(),
            "",
            f"  Hard ceiling    {self.scored_ceiling} scored + "
            f"{self.adaptive_ceiling} adaptive calls, enforced independently.",
            f"  {'':<16}Every message retried to the transport limit "
            f"({self.retry_allowance} sends).",
            f"  {'':<16}The run aborts rather than exceed either.",
        )

    def as_payload(self) -> BudgetPayload:
        """The consent surface as primitives, for the interrupt and for 6b."""
        return BudgetPayload(
            scored=_figure_payload(self.estimate.scored),
            adaptive=_figure_payload(self.estimate.adaptive),
            total=_figure_payload(self.estimate.total),
            scored_ceiling=self.scored_ceiling,
            adaptive_ceiling=self.adaptive_ceiling,
            retry_allowance=self.retry_allowance,
            presented=list(self.lines()),
        )


def _count(number: int, noun: str) -> str:
    """`1 case`, `18 cases`. The estimate is read by a person deciding whether to
    spend money, so it is written like a sentence rather than like a log line."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _figure_payload(figure: CallFigure) -> LayerFigurePayload:
    return LayerFigurePayload(
        calls=figure.calls, kind=str(figure.kind), basis=figure.basis
    )
