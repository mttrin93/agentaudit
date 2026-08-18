"""The bench's short-term memory: where a run is, what it has found, what it has spent.

A run state is carried as a plain object here, in the module PLAN.md §7 assigns it.
The approval interrupt the run halts on is the graph in `approval.py`; #13 adds the
library version.

Spending is counted **per layer** (#5). Two counters rather than one, because a
single blended figure hides which half of a run is consuming the operator's
inference budget, and because the two ceilings of ADR-0007 are enforced
independently — a layer with room left may not borrow from the other's unspent
allowance.
"""

from dataclasses import dataclass, field

from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import Family
from backend.graph.budget import BudgetExceeded, Layer, RunBudget


@dataclass(frozen=True)
class Attempt:
    """One execution of one case against one target, with the evidence behind
    its verdict."""

    case_id: str
    family: Family
    """Which family this attempt counts towards.

    Carried on the attempt rather than looked up from the case later, because a
    rate is per family per agent and every count that forgets its family is a
    count that can be pooled across six of them by accident.
    """

    target_name: str
    index: int
    transcript: Transcript
    verdict: Verdict


@dataclass(frozen=True)
class Position:
    """Where the run is in the library."""

    target_name: str
    case_id: str
    attempt_index: int


@dataclass
class RunState:
    """Where the run is, what it has found, and what each layer has spent.

    The budget is a field rather than a caller's concern because every call the
    bench makes passes through `record_call`, which makes this the one place
    enforcement cannot be forgotten. It has no default for the same reason: a run
    state constructed without a ceiling is a run with no ceiling.
    """

    budget: RunBudget
    position: Position | None = None
    attempts: list[Attempt] = field(default_factory=list)
    spent: dict[Layer, int] = field(default_factory=lambda: dict.fromkeys(Layer, 0))

    def enter(self, target_name: str, case_id: str, attempt_index: int) -> None:
        self.position = Position(target_name, case_id, attempt_index)

    @property
    def calls_spent(self) -> int:
        """Every call the run has made. A reporting figure only.

        Enforcement never reads this: two ceilings enforced against their sum
        would let the adaptive layer spend an underspent suite's leftovers, which
        is the second ceiling of ADR-0007 quietly deleted.
        """
        return sum(self.spent.values())

    def spent_in(self, layer: Layer) -> int:
        return self.spent[layer]

    def authorise_call(self, layer: Layer, sends: int) -> None:
        """Refuse the next message when the layer's budget cannot cover its worst case.

        Checked before the message goes on the wire rather than after, so a breach
        is a refusal instead of a discovery — a call already sent cannot be
        unsent, and the operator consented to a ceiling rather than to a ceiling
        plus whatever the last message happened to cost. `sends` is the target's
        retry limit, and the ceiling is built from the same limit, so a run that
        stays inside its own arithmetic is never aborted early.
        """
        ceiling = self.budget.ceiling(layer)
        if self.spent[layer] + sends > ceiling:
            raise BudgetExceeded(
                layer=layer,
                ceiling=ceiling,
                spent=self.spent[layer],
                requested=sends,
            )

    def record_call(self, layer: Layer, sends: int = 1) -> None:
        """Count what an exchange put on the wire, retries included.

        Every send reaches the operator's endpoint on the operator's inference
        budget, so a retried message costs what it cost. Attempts are counted
        separately, and deliberately are not this number: the enforced budget and
        the denominator of a rate measure different things.

        `layer` has no default. An adaptive call landing in the scored counter
        because a caller left the argument off would blend the two figures that
        ADR-0007 exists to keep apart, and it would do so silently.
        """
        self.spent[layer] += sends
        ceiling = self.budget.ceiling(layer)
        if self.spent[layer] > ceiling:
            raise BudgetExceeded(
                layer=layer, ceiling=ceiling, spent=self.spent[layer], requested=0
            )

    def record(self, attempt: Attempt) -> None:
        self.attempts.append(attempt)

    @property
    def succeeded_attempts(self) -> list[Attempt]:
        """The attempts whose verdict was `succeeded`.

        Deliberately not called findings: a finding is a verdict *plus* its
        narrative — reason, article, external identifier, remediation, exposure —
        and the judge that produces the narrative arrives in #8.
        """
        return [a for a in self.attempts if a.verdict is Verdict.SUCCEEDED]
