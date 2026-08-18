"""The bench's short-term memory: where a run is, what it has found, what it has spent.

A run state is carried as a plain object here, in the module PLAN.md §7 assigns it.
The approval interrupt the run halts on is the graph in `approval.py`, and the
library version is recorded here, on the run, because a rate is only comparable
with another rate measured against the same cases (spec story 27).

Spending is counted **per layer** (#5). Two counters rather than one, because a
single blended figure hides which half of a run is consuming the operator's
inference budget, and because the two ceilings of ADR-0007 are enforced
independently — a layer with room left may not borrow from the other's unspent
allowance.
"""

import time
from dataclasses import dataclass, field

from backend.bench.adaptive.episode import AdaptiveEpisode
from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import EMPTY_LIBRARY, Family, LibraryVersion, VerdictClass
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
    verdict_class: VerdictClass
    """How this attempt's verdict was reached, copied off the case record.

    Carried here for the same reason `family` is, and against a sharper hazard.
    Judged rates are reported apart from deterministic ones and carry a wider
    stated limit and a κ figure (ADR-0004), so a consumer grouping attempts has to
    be able to tell the two apart — and the one thing it may not do is work it out
    from the family name, which is the inference spec story 18 exists to forbid.
    Reading it off the record at the moment the attempt is made is the only place
    that inference is impossible.
    """

    started_at: float = field(default_factory=time.monotonic)
    """When this attempt began — before the message went on the wire, not when the
    record was built.

    Carried so that the one invariant of the two-layer run that no type can hold
    is checkable: adaptive episodes run strictly after the fixed suite for a given
    target, and `backend/tests/test_layer_ordering.py` compares this against
    `AdaptiveEpisode.started_at` to say so (ADR-0010).
    """


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
    library: LibraryVersion = EMPTY_LIBRARY
    """Which library this run was made against — the count and the digest.

    On the run rather than beside it, so that a result and the version that
    produced it cannot be separated by the time somebody compares two runs. It
    defaults to the empty library rather than to `None`: a run state built with no
    cases has a library of none, which is a fact and not a missing field.
    """

    position: Position | None = None
    attempts: list[Attempt] = field(default_factory=list)
    episodes: list[AdaptiveEpisode] = field(default_factory=list)
    """What the adaptive layer did, in a field of its own.

    Separate from `attempts` and holding a record that cannot be constructed from
    one, so that `TargetRun.rates` — which groups everything in `attempts` by
    family and divides — cannot reach an adaptive turn however it is called. An
    episode sharing that list would move every denominator in the bench silently:
    the arithmetic would stay valid, the population would change, and no test
    would fail (ADR-0010).
    """

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

        The ceiling is checked here as well as in `authorise_call`, and the check
        is not redundant: `authorise_call` guards the two call sites that exist,
        and this one guards a caller that reaches the counter without asking
        first — which is what a new call site looks like on the day it is written
        (#16 adds one). It raises *after* recording, because by then the call has
        been made and a counter that lied about it would be worse than the breach.
        """
        self.spent[layer] += sends
        ceiling = self.budget.ceiling(layer)
        if self.spent[layer] > ceiling:
            raise BudgetExceeded(
                layer=layer, ceiling=ceiling, spent=self.spent[layer], requested=0
            )

    def record(self, attempt: Attempt) -> None:
        self.attempts.append(attempt)

    def record_episode(self, episode: AdaptiveEpisode) -> None:
        """Keep one episode, in the store the adaptive layer has to itself.

        A second method rather than a wider `record`. A signature that accepted
        both records is the widening ADR-0010 asks anyone who reaches for it to
        stop at: the type separation only holds while there is nowhere for the two
        to meet.
        """
        self.episodes.append(episode)

    @property
    def succeeded_attempts(self) -> list[Attempt]:
        """The attempts whose verdict was `succeeded`.

        Deliberately not called findings: a finding is a verdict *plus* its
        narrative — reason, article, external identifier, remediation, exposure —
        and the judge that produces the narrative arrives in #8.
        """
        return [a for a in self.attempts if a.verdict is Verdict.SUCCEEDED]
