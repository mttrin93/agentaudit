"""Does `A_break` survive the model swap? The adaptive layer's half of #15.

The attacker is part of the bench now, so the question the multi-model check puts to
the scored layer applies to it as well: an attacker that discriminates on one
underlying model and not on another is reading model temperament exactly as a family
would be. This module puts two runs' `A_break`, `A_effort` and censoring side by
side and says whether the reading held.

**It decides nothing, and there is nothing here it could decide.** No rate, no
interval, no band, no `D`, no gate. `A_break` is measured on episodes and families
and `D` is measured on attempts, and the two comparisons are computed in two modules
for the same reason they print in two blocks (ADR-0010, ADR-0011). The scored
comparison is `backend/bench/crossmodel.py`; this module imports no part of it, no
`GateRule` and no scored arithmetic.

**A difference here is small evidence, and the module says so where it is read.**
`A_break` is a difference of two family counts over the families in scope, so it
moves in steps of `1 / len(scope)` — one family flipping on one episode moves it a
whole row down ADR-0011's table. `docs/validation.md` already records two runs of one
declared configuration disagreeing by exactly that much, so a swap that moves it by
one family has not been shown to have moved it at all. The step is printed beside
the change rather than folded into a verdict, because turning that into a threshold
would be declaring an adaptive bar — and the layer has none, by construction.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.bench.adaptive.discrimination import (
    DECIDES_NOTHING,
    AdaptiveDiscrimination,
    AdaptiveEffort,
    SeparationReading,
)
from backend.bench.library import Family


class NotAnAdaptiveSwap(ValueError):
    """These two readings are not a model swap, so nothing may be attributed to one.

    A second class rather than the scored comparison's `NotASwap`, because this
    package imports nothing from the scored side and an exception is an import
    (ADR-0010). The two say the same thing about two different denominators, which
    is the situation the vocabulary is built for.
    """


@dataclass(frozen=True)
class EffortComparison:
    """One agent's `A_effort` on two models, with the censoring beside each.

    The censored count travels with each median and is never folded into it: a
    censored episode is an observation known only to exceed `T`, and a median that
    absorbed it would understate a defence that held.
    """

    target_name: str
    first_model: str
    second_model: str
    first: AdaptiveEffort | None
    second: AdaptiveEffort | None

    @property
    def change(self) -> float | None:
        """Second median minus first, or `None` where either has no median.

        `None` and never zero. A run whose every episode was censored produced no
        turns-to-first-success at all, and a change of zero would read as an effort
        that held still.
        """
        if self.first is None or self.second is None:
            return None
        if self.first.median is None or self.second.median is None:
            return None
        return self.second.median - self.first.median

    def stated(self) -> str:
        """The agent's two lines, and the change where there is one to state."""
        lines = [f"{self.target_name}:"]
        for model, effort in (
            (self.first_model, self.first),
            (self.second_model, self.second),
        ):
            lines.append(
                f"  {model} — {effort.stated()}"
                if effort is not None
                else f"  {model} — no episode ran against this agent"
            )
        lines.append(
            "  no change to state — a median needs an episode that broke on both models"
            if self.change is None
            else f"  change {self.change:+g} turns to first success"
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class AdaptiveSwap:
    """`A_break` and `A_effort` on two underlying models, compared.

    Both whole readings travel with the comparison, for the reason
    `AdaptiveSeparation` carries both agents' breaks: a figure that decides nothing
    has to be even easier for a reader to re-derive than one that does.
    """

    first_model: str
    second_model: str
    first: AdaptiveDiscrimination
    second: AdaptiveDiscrimination

    def __post_init__(self) -> None:
        if self.first_model == self.second_model:
            raise NotAnAdaptiveSwap(
                f"both readings were taken on {self.first_model!r}. Two readings of "
                "one model are two samples of a stochastic search, and the "
                "difference between them is this layer's run-to-run variation — "
                "which docs/validation.md records at a whole row of ADR-0011's table"
            )

    @property
    def change(self) -> float:
        """`A_break` on the second model minus `A_break` on the first."""
        return self.second.separation.value - self.first.separation.value

    @property
    def step(self) -> float:
        """The smallest change either reading can move by: one family in scope.

        The wider of the two steps, so the caveat printed beside the change is the
        honest one where the two runs had different families in scope.
        """
        return max(
            1 / len(self.first.separation.scope), 1 / len(self.second.separation.scope)
        )

    @property
    def within_one_family(self) -> bool:
        """Whether the change is no larger than one family flipping.

        Printed, never decided on. It is the difference `docs/validation.md` has
        already observed between two runs of one identical configuration, so a change
        this size is not evidence that the model did anything.
        """
        return abs(self.change) <= self.step

    @property
    def survives(self) -> bool:
        """Whether the attacker separated the two ends of the ladder on both models.

        `A_break > 0` twice, which is ADR-0011's first row twice. Deliberately not a
        magnitude test: this layer has no declared threshold and inventing one to
        answer *survives?* would put an adaptive bar in a bench that has none.
        """
        return self.first.separation.value > 0 and self.second.separation.value > 0

    @property
    def readings(self) -> tuple[SeparationReading, SeparationReading]:
        """Which row of ADR-0011's table each model landed on."""
        return (self.first.separation.reading, self.second.separation.reading)

    @property
    def same_reading(self) -> bool:
        return self.first.separation.reading is self.second.separation.reading

    @property
    def effort(self) -> tuple[EffortComparison, ...]:
        """Every agent either model ran an episode against, paired by name."""
        first = _by_agent(self.first.effort)
        second = _by_agent(self.second.effort)
        return tuple(
            EffortComparison(
                target_name=name,
                first_model=self.first_model,
                second_model=self.second_model,
                first=first.get(name),
                second=second.get(name),
            )
            for name in (*first, *(name for name in second if name not in first))
        )

    @property
    def scope_change(self) -> tuple[Family, ...]:
        """The families in scope on exactly one of the two models.

        Printed because `A_break`'s denominator is its scope: a change measured over
        four families on one model and three on the other is partly a change of
        denominator, and a reader has to be told which.
        """
        first = frozenset(self.first.separation.scope)
        second = frozenset(self.second.separation.scope)
        return tuple(family for family in Family if family in first ^ second)

    def stated(self) -> str:
        """The adaptive half of the swap, in its own block and carrying no `D`."""
        lines = [
            "does A_break survive the model swap? — measured on episodes and "
            "families, never on attempts",
            f"  {DECIDES_NOTHING}",
            f"  first model:  {self.first_model}, A_break = "
            f"{self.first.separation.value:+.2f} — {self.readings[0]}",
            f"  second model: {self.second_model}, A_break = "
            f"{self.second.separation.value:+.2f} — {self.readings[1]}",
            f"  change {self.change:+.2f}, and one family in scope is "
            f"{self.step:.2f} of A_break — a change of one family is inside the "
            "run-to-run variation two runs of one identical configuration have "
            "already shown (docs/validation.md), so it is not evidence that the "
            "model did anything",
            f"  the change is {'no larger' if self.within_one_family else 'larger'} "
            "than one family flipping",
            "  the two readings are "
            + ("the same row" if self.same_reading else "two different rows")
            + " of ADR-0011's table",
            f"  A_break stayed positive on both models: "
            f"{'yes' if self.survives else 'no'} — and nothing follows from either "
            "answer except a repair to the attacker or the turn budget",
        ]
        if self.scope_change:
            lines.append(
                "  in scope on one model only: "
                f"{', '.join(self.scope_change)} — part of the change above is a "
                "change of denominator"
            )
        lines.append("  A_effort, per agent, on each model:")
        lines.extend(
            f"    {line}"
            for comparison in self.effort
            for line in comparison.stated().splitlines()
        )
        return "\n".join(lines)


def compare(
    first: AdaptiveDiscrimination,
    second: AdaptiveDiscrimination,
    *,
    first_model: str,
    second_model: str,
) -> AdaptiveSwap:
    """Compare two adaptive readings taken on two underlying models.

    The models are named keyword arguments rather than positional, on the same terms
    as the two ends of `A_break` itself: the change is second minus first, and a call
    site that swapped them would report the direction of a collapse backwards.
    """
    return AdaptiveSwap(
        first_model=first_model,
        second_model=second_model,
        first=first,
        second=second,
    )


def _by_agent(efforts: Sequence[AdaptiveEffort]) -> Mapping[str, AdaptiveEffort]:
    """One reading's `A_effort` per agent, in the order the agents ran."""
    return {effort.target_name: effort for effort in efforts}
