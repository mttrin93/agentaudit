"""The second half of a run: which episodes are run, against what, in what order.

**Strictly after the fixed suite, per target** (ADR-0010). The whole scored layer
finishes before this function is called, which is the strong form of the rule: a
target carrying persistent state — a conversation store, a cache, a rate limiter
that trips — cannot be touched by an adaptive turn before an attempt that is
scored. That invariant has no structural enforcement available, so it has a test
instead: `backend/tests/test_layer_ordering.py`.

**Order is randomised per family** (ADR-0011). Not once per run: per family, so
that the turn budget is not spent in a sequence the attacker could learn across the
six of them. Together with a fresh brief per episode and a per-run handle, this is
the context isolation half of the blinding — the half the judge never needed,
because the judge grades one transcript at a time and the attacker meets three
targets in a row.

**An episode needs a deterministic break to aim at.** `check_canary` wraps the
evaluator, and the two judged families have no success condition for it to apply
(ADR-0004). ADR-0010 closes the alternative in as many words: an `AdaptiveEpisode`
has no `verdict` field and cannot acquire one by being handed to the adjudicator —
the adaptive layer gained a new semantic component to reach for and no new edge to
reach it by. So episodes run over the families this run holds a deterministic,
applicable and runnable case for, and a family with none is absent from the
adaptive section rather than reported as a family nothing broke.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from backend.bench.adaptive.attacker import (
    AttackerCompletion,
    Objective,
    run_episode,
)
from backend.bench.adaptive.blinding import Blinding
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.episode import AdaptiveEpisode
from backend.bench.adaptive.precedent import DURABLE_PRECEDENT, PrecedentStore
from backend.bench.applicability import applicable
from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.measurability import runnable
from backend.graph.runstate import RunState


@dataclass(frozen=True)
class AttackableTarget:
    """A registered target and the canary planted in it.

    The canary travels with the target rather than being looked up later, because
    `check_canary` has to apply the same value the scored layer applied — one
    planted value, two roles (ADR-0007) — and a layer that re-derived it would be
    a second source for the one number the verdict turns on.
    """

    target: TargetConfig
    canary: str

    withdrawn: frozenset[Family] = frozenset()
    """Families the scored layer withdrew after the target's own first reply.

    A target registered as exposing its tool calls whose replies carry none has had
    the two trace-dependent families withdrawn before an attempt was spent on either
    (`measurability.contradicted_by_the_reply`). The same withdrawal has to reach
    here, because this layer applies the *declared* preconditions and would otherwise
    hand the attacker an objective whose success condition nothing can check — an
    episode censored by construction, and a crash at the first check.

    Carried on this record rather than re-derived, so the two layers cannot come to
    disagree about which families this target can be measured on.
    """


def run_adaptive_layer(
    attackable: Sequence[AttackableTarget],
    cases: Sequence[Case],
    run_state: RunState,
    attacker: AttackerCompletion,
    budget: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET,
    precedent: PrecedentStore = DURABLE_PRECEDENT,
    rng: random.Random | None = None,
) -> tuple[AdaptiveEpisode, ...]:
    """Run `k` episodes per family per target, and record every one of them."""
    draw = rng if rng is not None else random.Random()
    blinding = Blinding.over([entry.target for entry in attackable], rng=draw)
    objectives = {
        entry.target.name: objectives_for(cases, entry.target, entry.withdrawn)
        for entry in attackable
    }

    episodes: list[AdaptiveEpisode] = []
    for family in Family:
        order = list(attackable)
        draw.shuffle(order)
        for entry in order:
            objective = objectives[entry.target.name].get(family)
            if objective is None:
                continue
            for _ in range(budget.episodes_per_family):
                episodes.append(
                    run_episode(
                        target=entry.target,
                        objective=Objective(
                            family=family, case=objective, canary=entry.canary
                        ),
                        run_state=run_state,
                        attacker=attacker,
                        blinding=blinding,
                        budget=budget,
                        precedent=precedent,
                    )
                )
    return tuple(episodes)


def objectives_for(
    cases: Sequence[Case],
    target: TargetConfig,
    withdrawn: frozenset[Family] = frozenset(),
) -> dict[Family, Case]:
    """One deterministic objective per family, for the families this target can
    answer.

    The same two filters the scored layer applies, in the same order and for the
    same reasons: a case not written for this agent type is not this target's
    business, and a case whose precondition the target does not meet is one whose
    success condition could never be checked. An objective nothing could verify
    would produce episodes that are censored by construction — the attacker
    reading as weak because the bench gave it a question this target cannot be
    asked.

    `withdrawn` is the third filter, and it is the endpoint's own answer rather than a
    declaration: a family the scored layer withdrew because the target's replies carry
    no trace is a family whose objective nothing here could check either.
    """
    objectives: dict[Family, Case] = {}
    for case in runnable(applicable(cases, target), target):
        if case.family in withdrawn:
            continue
        if case.verdict_class is VerdictClass.DETERMINISTIC:
            objectives.setdefault(case.family, case)
    return objectives
