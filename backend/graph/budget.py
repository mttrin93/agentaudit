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

**Money is declared, never guessed.** A target is the operator's endpoint on the
operator's provider, so the price of a call belongs to them and not to the bench.
A price the bench invented would be worse than no price at all, for exactly the
reason an averaged adaptive ceiling would be — so `CallPrice` is declared, and a
run with none declared says *not priced* rather than showing zero. What is priced
rounds up: a consent figure that understates is not a consent figure.

**Calls, not attempts.** The budget counts sends on the wire, retries included,
because a retried message reaches the endpoint and costs the operator what it
cost. An attempt is the unit of a denominator and is deliberately not this number
(CONTEXT.md).

**Nothing rendered with `≤` may be exceeded.** The estimate's total is what the
run costs when no message has to be retried, and it says so; the figure a run may
not exceed is the hard ceiling, which is the estimate with every message retried
to its target's own transport limit. Both are shown, both carry `≤`, and the
larger one is the one that is enforced. That relationship is also what lets the
budget be checked *before* each message rather than detected after it: a run that
stays inside its arithmetic can always cover the worst case of its next message,
so a well-behaved run is never aborted early and a misbehaving one never
overspends.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal
from enum import StrEnum
from typing import TypedDict

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.contract import TargetConfig
from backend.bench.library import Case
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.selection import EVERY_CONSTRUCTION, AttackSelection

REGISTRATION_PROBES_PER_TARGET = 1
"""The nonce echo probe, which is a call on the operator's endpoint like any other.

Inside the estimate rather than beside it: a consent figure that quietly omitted
the calls registration makes would understate what the run costs, and it is also
what the scored ceiling has to cover — a suite budgeted at exactly its attempts
would abort on the registration probe of its first target. It is why the scored
figure reads 181 per target where ADR-0007's table reads 180; the difference is
published in the figure's own `basis` rather than absorbed.
"""

NOT_PRICED = "not priced"
"""What the consent surface says when the operator declared no price.

Never `0.00`: a run whose cost is unknown and a run that is free are different
facts, and only one of them is safe to confirm without reading further.
"""


PLANTING_CALLS = 0
"""What every planting a run performs costs on the operator's endpoint.

Zero, and itemised rather than absent —
[ADR-0062](../../docs/adr/0062-planting-is-a-pre-run-step-off-every-counter.md) §6
has the argument. The consequence here is that this is a literal and not arithmetic
over the run: there is nothing a caller can pass that makes it non-zero, so editing
this number is the only way the line moves, which makes it the tripwire for a
planting step that ever became a send (`test_planting_off_the_counters.py`).
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
class CallPrice:
    """What one call to the target costs the operator, as the operator states it."""

    per_call: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.per_call < 0:
            raise ValueError("a call cannot cost less than nothing")
        if not self.currency.strip():
            raise ValueError("a price has to say what currency it is in")

    def cost_of(self, calls: int) -> Decimal:
        """The cost of that many calls, rounded **up** to the currency's minor unit.

        Up rather than to nearest, because this figure is shown to somebody
        deciding whether to spend it. A consent figure that rounded down would be
        the bench understating its own bill.
        """
        return (self.per_call * calls).quantize(Decimal("0.01"), rounding=ROUND_UP)

    def total_of(self, *counts: int) -> Decimal:
        """Each count priced and rounded up, and only then added.

        Summed after rounding rather than before, so the rows of the consent table
        add up to its total. A surface whose columns visibly disagree is one a
        reader stops reading, and rounding each row up first keeps the total on the
        conservative side of the disagreement.
        """
        return sum((self.cost_of(count) for count in counts), Decimal(0))

    def rendered(self, amount: Decimal, kind: FigureKind) -> str:
        """`0.91 USD`, or `≤ 0.48 USD` when the calls it prices are a bound."""
        shown = f"{amount} {self.currency}"
        return shown if kind is FigureKind.EXACT else f"≤ {shown}"


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
    price: CallPrice | None = None
    """The operator's own price per call, or `None` for a run they did not price."""

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

    def cost(self, figure: CallFigure) -> str:
        """What one figure costs, or `not priced`. Never a number the bench invented."""
        if self.price is None:
            return NOT_PRICED
        return self.price.rendered(self.price.cost_of(figure.calls), figure.kind)

    def total_cost(self) -> str:
        """What both layers cost together — the rows added, so the table adds up."""
        if self.price is None:
            return NOT_PRICED
        return self.price.rendered(
            self.price.total_of(self.scored.calls, self.adaptive.calls),
            self.total.kind,
        )


class LayerFigurePayload(TypedDict):
    """One layer's figure, as a machine-readable record for the approval surface."""

    calls: int
    kind: str
    basis: str
    cost: str


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
    planting: LayerFigurePayload
    """The pre-run plantings, at `PLANTING_CALLS`. Present and zero, never absent."""

    hard_ceiling: LayerFigurePayload
    scored_ceiling: int
    adaptive_ceiling: int
    currency: str
    presented: list[str]


class BudgetExceeded(RuntimeError):
    """A run stopped rather than spend past what the operator confirmed.

    Loud on purpose: a run that stopped early measured fewer attempts than the
    rate it would report is denominated on, so a partial run is void rather than
    smaller.
    """

    def __init__(self, layer: Layer, ceiling: int, spent: int, requested: int) -> None:
        self.layer = layer
        self.ceiling = ceiling
        self.spent = spent
        self.requested = requested
        super().__init__(
            (
                f"the {layer} layer has spent {spent} of a declared {ceiling} "
                f"calls, and the next message needs up to {requested} more: "
                "refusing it rather than spend past the estimate the operator "
                "confirmed"
            )
            if requested
            else (
                f"the {layer} layer has spent {spent}, past its declared ceiling "
                f"of {ceiling}: a call was recorded that nothing had authorised "
                "against the budget"
            )
        )


@dataclass(frozen=True)
class _Row:
    """One line of the consent table, plus the arithmetic printed under it."""

    label: str
    figure: CallFigure
    cost: str
    note: str = ""
    basis: str | None = None
    """The line printed beneath the row.

    `""` prints none; `None` means the figure's own stated basis.
    """


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
    """The most sends any one of this run's targets allows a single message.

    Shown so a reader can see where the ceilings came from. The ceilings themselves
    are summed per target rather than multiplied by this, so a fleet whose targets
    declare different retry policies gets the tight bound rather than the most
    patient target's bound applied to all of them.
    """

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
        price: CallPrice | None = None,
        selection: AttackSelection = EVERY_CONSTRUCTION,
    ) -> RunBudget:
        """Work out both numbers from the run's own inputs.

        One constructor for the estimate and the ceiling together, so that the
        limit cannot be declared against a different library than the figures the
        operator was shown.

        **The selection reaches the adaptive figure and nothing else here.** Its
        effect on the scored half arrived before this call — `plan_for` dropped the
        cases whose construction was switched off, so `cases` is already what the run
        will send, and reading the selection again over them would price the same
        narrowing twice. What it decides here is the layer that has no case to drop:
        a layer switched off puts nothing on the wire, so both the figure an operator
        confirms and the ceiling that is enforced fall to nothing
        ([ADR-0058](../../docs/adr/0058-the-console-selects-layers-and-constructions.md)).
        """
        # Turns and not cases, because a case can cost two calls per attempt: a
        # memory-poisoning attempt plants in one turn and is scored in the next, in
        # one session (`Case.turns`, ADR-0041). The denominator does not move — ten
        # attempts per case, as everywhere — and this figure is calls on the
        # operator's endpoint, which is a different number and always has been.
        turns = sum(case.turns for case in cases)
        attempts = turns * rule.attempts_per_case
        per_target = REGISTRATION_PROBES_PER_TARGET + attempts
        scored = CallFigure(
            calls=len(targets) * per_target,
            kind=FigureKind.EXACT,
            basis=(
                f"{_count(len(cases), 'case')} at {_count(turns, 'turn')} "
                f"× {rule.attempts_per_case} attempts "
                f"+ {_count(REGISTRATION_PROBES_PER_TARGET, 'registration probe')}, "
                f"× {_count(len(targets), 'target')}"
            ),
        )
        # Zero and a `CEILING`, not zero and a fact: nothing about a layer that ran
        # is exact, and a bound of nothing is the one bound that cannot be exceeded.
        # The basis says which of the two zeros this is — a layer nobody asked for,
        # rather than a budget somebody set to nothing.
        per_target_turns = adaptive.turn_ceiling if selection.adaptive else 0
        adaptive_figure = CallFigure(
            calls=len(targets) * per_target_turns,
            kind=FigureKind.CEILING,
            basis=(
                f"{adaptive.family_count} families × T={adaptive.turns_per_episode}"
                f" × k={adaptive.episodes_per_family},"
                f" × {_count(len(targets), 'target')}"
                if selection.adaptive
                else (
                    "the adaptive layer was switched off for this run: no episode is "
                    "opened, nothing reaches the endpoint from it, and the run's "
                    "family view carries no discovery count rather than a count of "
                    "zero"
                )
            ),
        )
        sends = [target.retry.sends for target in targets]
        return cls(
            estimate=Estimate(scored=scored, adaptive=adaptive_figure, price=price),
            scored_ceiling=sum(per_target * send for send in sends),
            adaptive_ceiling=sum(per_target_turns * send for send in sends),
            retry_allowance=max(sends, default=1),
        )

    @property
    def planting(self) -> CallFigure:
        """The pre-run planting step, as the figure the estimate itemises.

        A property over the constant rather than a third field on `Estimate`, and the
        difference is the point: `Estimate`'s two figures are arithmetic over this
        run's cases and targets, and this one is not a function of anything. There is
        nothing a caller could pass that would make it non-zero, which is what makes
        the line a statement of the invariant rather than a reading of it.

        Exact and not a ceiling: a bound would say the bench does not know what a
        plant costs, and it does.
        """
        return CallFigure(
            calls=PLANTING_CALLS,
            kind=FigureKind.EXACT,
            basis=(
                "a plant is a call on the operator's own object before the run "
                "registers: off every counter, and never a message on the wire"
            ),
        )

    def ceiling(self, layer: Layer) -> int:
        """The ceiling over one layer. Read per layer, never summed: the two are
        enforced independently, so a layer with room left cannot borrow from the
        other's unspent allowance."""
        return self.scored_ceiling if layer is Layer.SCORED else self.adaptive_ceiling

    @property
    def hard_ceiling(self) -> CallFigure:
        """The most the run may spend across both layers, as a bound.

        Rendered with `≤` like the estimate's total, because it is the same kind of
        number and the larger one: nothing an operator is shown with a `≤` in front
        of it may be exceeded, and this is the figure that is enforced.
        """
        return CallFigure(
            calls=self.scored_ceiling + self.adaptive_ceiling,
            kind=FigureKind.CEILING,
            basis=(
                f"{self.scored_ceiling} scored + {self.adaptive_ceiling} adaptive, "
                "enforced per layer — every message retried to its target's "
                f"transport limit (at most {self.retry_allowance} sends)"
            ),
        )

    @property
    def hard_ceiling_cost(self) -> str:
        """What the limit would cost if the run spent all of it."""
        price = self.estimate.price
        if price is None:
            return NOT_PRICED
        return price.rendered(
            price.total_of(self.scored_ceiling, self.adaptive_ceiling),
            FigureKind.CEILING,
        )

    def lines(self) -> tuple[str, ...]:
        """The consent surface: a fact, a bound, a bounded total, and the limit.

        Each figure's stated basis goes on the line under it rather than beside it,
        because the arithmetic is what makes the number checkable and it should not
        be the part that a narrow terminal cuts off.
        """
        estimate = self.estimate
        rows = (
            _Row("Planting", self.planting, estimate.cost(self.planting)),
            _Row("Scored layer", estimate.scored, estimate.cost(estimate.scored)),
            _Row("Adaptive layer", estimate.adaptive, estimate.cost(estimate.adaptive)),
            None,
            # No basis line under the total: its components are the two rows above
            # it, and repeating both is the one place this table could start hiding
            # the arithmetic inside a wall of it.
            _Row(
                "Total",
                estimate.total,
                estimate.total_cost(),
                note="if no message is retried",
                basis="",
            ),
            _Row(
                "Hard ceiling",
                self.hard_ceiling,
                self.hard_ceiling_cost,
                note="the limit; the run aborts rather than exceed it",
            ),
        )
        shown = [row for row in rows if row is not None]
        width = max(len(row.figure.rendered()) for row in shown)
        money = max(len(row.cost) for row in shown)

        rendered: list[str] = []
        for row in rows:
            if row is None:
                rendered.append(f"  {'':<16}{'─' * (width + 6)}")
                continue
            kind = str(row.figure.kind)
            said = f"{kind} — {row.note}" if row.note else kind
            rendered.append(
                f"  {row.label:<16}{row.figure.rendered():>{width}} calls   "
                f"{row.cost:>{money}}   {said}"
            )
            basis = row.figure.basis if row.basis is None else row.basis
            if basis:
                rendered.append(f"  {'':<18}{basis}")

        if estimate.price is None:
            rendered.append(
                f"  {'':<18}Not priced: declare a price per call to see the cost. "
                "You are confirming a call count only."
            )
        return tuple(rendered)

    def as_payload(self) -> BudgetPayload:
        """The consent surface as primitives, for the interrupt and for 6b."""
        estimate = self.estimate
        return BudgetPayload(
            scored=_layer_payload(estimate.scored, estimate.cost(estimate.scored)),
            adaptive=_layer_payload(
                estimate.adaptive, estimate.cost(estimate.adaptive)
            ),
            total=_layer_payload(estimate.total, estimate.total_cost()),
            planting=_layer_payload(self.planting, estimate.cost(self.planting)),
            hard_ceiling=_layer_payload(self.hard_ceiling, self.hard_ceiling_cost),
            scored_ceiling=self.scored_ceiling,
            adaptive_ceiling=self.adaptive_ceiling,
            currency="" if estimate.price is None else estimate.price.currency,
            presented=list(self.lines()),
        )


def _count(number: int, noun: str) -> str:
    """`1 case`, `18 cases`. The estimate is read by a person deciding whether to
    spend money, so it is written like a sentence rather than like a log line."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _layer_payload(figure: CallFigure, cost: str) -> LayerFigurePayload:
    return LayerFigurePayload(
        calls=figure.calls, kind=str(figure.kind), basis=figure.basis, cost=cost
    )
