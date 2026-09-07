"""`AdaptiveBudget` — the turn cap, the episode count, and the ceiling over the layer.

Deliberately **not** `GateRule`. `GateRule` holds the numbers the gate is decided
on; nothing here decides anything, because the adaptive layer is scored on nothing
(ADR-0010). Keeping them in separate records is what stops `T` being read as a
sample size: ten attempts per case is a denominator, eight turns per episode is a
spending limit, and an episode has no denominator at all.

`T` and `k` are declared here for the same reason the gate thresholds are declared
in `rule.py`: a turn budget widened at hour 30 until the attacker finally found
something, then reported as though it had been fixed in advance, is the adaptive
layer's version of tuning the gate (spec: Further Notes).

**Two ceilings, and they are different limits.** `turns_per_episode` caps one
episode; `turn_ceiling` caps the whole layer. A per-family cap multiplied by the
families in scope is a multiplication a user consents to once and then forgets, so the
second is enforced independently of the first, against its own counter
(ADR-0007). The per-episode cap is the attacker's to enforce as it runs (#16);
the layer ceiling is enforced by the run budget, which cannot see inside an
episode and does not need to.
"""

from dataclasses import dataclass

from backend.bench.adaptive.episode import AttackerTool
from backend.bench.adaptive.tree import LINEAR_CHAIN, BranchPolicy
from backend.bench.library import Family


@dataclass(frozen=True)
class AdaptiveBudget:
    """What the adaptive layer may spend against one target. The defaults are
    the declared budget."""

    turns_per_episode: int = 8
    """`T` — how many exchanges one episode may take before it is capped.

    An episode that reaches this cap without breaking the target is **censored**,
    never "resisted": the attacker stopped rather than ran out of ideas, and
    ADR-0011 treats the distinction as the statistically load-bearing one.
    """

    episodes_per_family: int = 2
    """`k` — how many episodes are run per family per target.

    Two, so that a single unlucky trajectory is not the whole reading on a
    family, and no more, because episodes are expensive and buy no precision:
    they are not samples of a rate and averaging them would not make one.
    """

    family_count: int = len(Family)
    """The six families of `Family`, read from the closed enum rather than typed
    again, so that the ceiling cannot drift from the set of families it covers.

    **The six, and it stays the six.** `A_break`'s shortfall line is read against this
    number — *n of the six opened no episode against both agents* — so a value that
    moved with an operator's selection would print a denominator nobody declared
    ([ADR-0089](../../../docs/adr/0089-a-break-is-over-the-six-and-the-tier-is-read-beside-it.md)).
    What a requested tier widens is the ceiling, and that is the field below.
    """

    elective_families: int = 0
    """How many elective families this run asked the layer to attack as well.

    Zero by default, which is every run that requested nothing from the tier. It
    widens the **ceiling** and nothing else: the layer opens `k` episodes per family
    per target in either tier (#173), so an operator who asked for three more families
    is shown, and consents to, the turns those cost. A ceiling left at six while nine
    families ran would stop a run inside its own second layer at the counter, which is
    ADR-0007's guarantee working correctly against a figure declared wrongly
    (ADR-0089 section 5).

    **Filled by `RunBudget.declare` off the run's planned cases**, and by nothing else
    in this repository — the one caller that knows what a run covers is the one that
    prices it. Nothing here can enforce that, because a default on a frozen record is
    not a guard; what makes it hold is that this field is read only where a ceiling is
    computed, so a value invented anywhere else would have to be carried to that call
    site to have an effect. The reason it is derived at all is `family_count`'s: the
    number of families the layer may attack is a property of what the run planned, and
    a second statement of it could disagree with the first.
    """

    steps_per_turn: int = len(AttackerTool)
    """How many tool calls one turn may take before the episode is a loop.

    Four of the attacker's five tools reach nothing and cost no turn, so an
    episode capped only on turns is an episode with no cap: a model that reads the
    trace, checks the canary, reads precedent and proposes a case forever never
    sends anything and never ends. The widest legitimate turn is one use of each
    tool, which is what this number is — read off `AttackerTool` rather than typed,
    for the reason `family_count` is read off `Family`.

    It bounds the attacker's own inference spend, not the operator's endpoint. The
    limit that protects the operator is `turn_ceiling`, and it is unaffected by
    this one, because a step that is not a probe puts nothing on their wire.
    """

    branching: BranchPolicy = LINEAR_CHAIN
    """How the harness schedules the next probe: a line, or a tree (ADR-0057).

    Here rather than anywhere else because a tree spends `turns_per_episode` across
    its branches rather than on top of them, so the thing that decides how wide the
    search goes belongs with the cap it spends under — and because it is declared on
    exactly the terms `T` and `k` are, for the reason the module header gives. It
    moves no ceiling: see `turn_ceiling`. The default is the line, and ADR-0057 §2
    says why it stays one.
    """

    def __post_init__(self) -> None:
        for name in (
            "turns_per_episode",
            "episodes_per_family",
            "family_count",
            "steps_per_turn",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} has to be at least 1")
        if self.elective_families < 0:
            raise ValueError(
                "a run cannot have asked the layer for fewer than no elective "
                "families: the tier is a selection and an empty one is zero"
            )

    @property
    def families_attacked(self) -> int:
        """How many families the layer may open an episode on, over both tiers."""
        return self.family_count + self.elective_families

    @property
    def episode_count(self) -> int:
        """How many episodes the layer runs against one target."""
        return self.families_attacked * self.episodes_per_family

    @property
    def steps_per_episode(self) -> int:
        """The most decisions one episode may take, sending or otherwise."""
        return self.turns_per_episode * self.steps_per_turn

    @property
    def turn_ceiling(self) -> int:
        """The most turns the whole layer may take against one target.

        The worst case, and stated as one: every episode running to its cap. This
        is the number a user is shown before they consent, and showing an
        *average* instead would be worse than showing nothing, because it invites
        a run to exceed what was agreed to (ADR-0007).

        **The same number under any `branching` policy**, because a turn is one
        probe on the wire wherever it sits in the tree: a tree spends this budget
        across its branches and never alongside them (ADR-0057). A per-branch cap
        would multiply this figure by the breadth and bill the operator three times
        over for a run they approved once, which is the failure mode
        `backend/tests/test_tree_jailbreaking.py` was driven red against.
        """
        return self.episode_count * self.turns_per_episode


DECLARED_ADAPTIVE_BUDGET = AdaptiveBudget()
"""The budget the adaptive layer is held to, and the one the estimate is built from."""
