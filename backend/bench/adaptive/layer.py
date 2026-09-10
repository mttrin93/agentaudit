"""The second half of a run: which episodes are run, against what, in what order.

**Strictly after the fixed suite, per target** (ADR-0010). The whole scored layer
finishes before this function is called, which is the strong form of the rule: a
target carrying persistent state — a conversation store, a cache, a rate limiter
that trips — cannot be touched by an adaptive turn before an attempt that is
scored. That invariant has no structural enforcement available, so it has a test
instead: `backend/tests/test_layer_ordering.py`.

**Order is randomised per family** (ADR-0011). Not once per run: per family, so
that the turn budget is not spent in a sequence the attacker could learn across the
families it attacks. Together with a fresh brief per episode and a per-run handle,
this is the context isolation half of the blinding — the half the judge never needed,
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

**In both tiers, since #173.** The layer attacks the elective families a run
requested and no others, and it learns which those are the way it learns the six's
own switch: from the cases the run planned (`api/run_config.plan_for`). An episode in
the tier is scored on nothing, exactly as one on the six is (ADR-0010), and it reaches
the scored side by the one edge that already existed — `propose_case`, into ADR-0012's
cross-model bar. What does **not** widen is the separation statistic:
[ADR-0089](../../../docs/adr/0089-a-break-is-over-the-six-and-the-tier-is-read-beside-it.md)
keeps `A_break`'s denominator over the six, so the readings in `docs/validation.md`
stay comparable across a run that requested the tier and one that did not.
"""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from dataclasses import dataclass

from backend.bench.adaptive.attacker import (
    AttackerCompletion,
    AttackerUnavailable,
    Objective,
    run_episode,
)
from backend.bench.adaptive.blinding import Blinding
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.adaptive.precedent import DURABLE_PRECEDENT, PrecedentStore
from backend.bench.adaptive.tree import BranchSchedule
from backend.bench.applicability import applicable
from backend.bench.contract import TargetConfig, TargetUnreachable
from backend.bench.library import (
    AnyFamily,
    Case,
    DiscoveredBy,
    ElectiveFamily,
    Family,
    Transform,
    VerdictClass,
)
from backend.bench.measurability import runnable
from backend.bench.unfinished import ReplyUnfinished
from backend.graph.runstate import RunState
from backend.observability import Field, Span, traced


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

    discovered_by: DiscoveredBy
    """What a route found against this target is filed as, and so which bar it faces.

    Carried on the target rather than passed per episode, because it is a property
    of *what is being attacked* and not of one episode against it — and required
    with no default, so a caller that has not said which loop it is running cannot
    get a bar by omission (ADR-0107 §3). `TargetConfig` deliberately does not tell a
    reference agent from a user's agent, so this cannot be derived from the field
    beside it.
    """

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


EPISODE_FAILURES: tuple[type[Exception], ...] = (
    TargetUnreachable,
    AttackerUnavailable,
    ReplyUnfinished,
)
"""The instrument failures an episode may have and still leave a run measured.

Three, and deliberately no more: the target on the wire, the attacker's own model, and
that model answering with a tool call the cap cut off. `TargetUnreachable` from
`contract`; `AttackerUnavailable` from the attacker seam rather than a provider's own
exception class, which would reach the verifier's import closure; and `ReplyUnfinished`,
which is this bench's own named failure for a truncated reply and surfaces as itself
because `test_unfinished_replies.py` holds that it must.
Both are things that break *outside* this repository, which is what makes an episode
that met one an absent observation rather than a bug — and the pair is the whole of
what this layer talks to besides the case record it was handed.

**A bare `except Exception` here would be the failure this catch exists to prevent,
arriving from the other side.** Every future defect in the layer would become a run
that quietly attacked nothing and published an `A_break` over whatever survived, which
is PLAN §10's own failure mode; ADR-0050 decided this for the narrative instruments on
the same reasoning and keeps a test that a `MemoryError` from the judge's seat still
stops the run. The counterpart test is `test_adaptive_attacker.py`'s.

Why an episode may fail without failing the run at all is ADR-0010: this layer decides
nothing, so an absence here costs a diagnostic and never a rate. Before this it cost
the run — the exception left `run_suite` with a scored layer already paid for. The
decision, and the four alternatives it refused, is
[ADR-0085](../../../docs/adr/0085-an-episode-whose-instrument-broke-is-a-failed-episode-and-the-run-is-still-measured.md).
"""


ATTACKED_IN_ORDER: tuple[AnyFamily, ...] = (*Family, *ElectiveFamily)
"""Every family an episode may be opened on, the six first and the tier after.

Read off the two closed sets rather than typed out, for the reason
`AdaptiveBudget.family_count` is read off `Family`: a family added to either
enumeration is a family the layer attacks when a run asks for it, and a list here
would have to be remembered. The order is the declaration order and is deliberately
fixed — what ADR-0011 requires to be randomised is the order of the **targets** within
a family, which `run_adaptive_layer` draws for each of these in turn.

The six first, so that a run which spends its ceiling attacking a requested tier has
already attacked the families the gate is decided over.
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
    """Run `k` episodes per family per target per schedule, and record every one.

    **The schedules and the spellings are loops and not parameters of one episode.**
    `budget.scheduled` and `budget.spellings` are what the operator selected, in the
    enum's own order, and an episode set is opened under each pairing: a run that
    selected both schedules attacks every family under the line and under the tree,
    and a run that selected a second spelling attacks it again in that spelling —
    `k` episodes each, and a ceiling that says so
    ([ADR-0096](../../../docs/adr/0096-the-adaptive-schedule-is-selected-and-both-schedules-are-two-episodes.md)).
    A single episode gets one policy and one spelling, both handed to `run_episode`,
    because an episode has one shape and is composed in one spelling (ADR-0097).

    The schedule and the spelling are the innermost loops, so every episode for one
    family against one target is adjacent: the position `/runs` reports walks the
    families in
    `ATTACKED_IN_ORDER` and the targets inside a family in the order ADR-0011
    randomises, and a schedule loop wrapped around those would make a run's second
    half a repeat of its first — a reader watching one would see every family twice
    with nothing on the screen saying which pass they were in.
    """
    draw = rng if rng is not None else random.Random()
    blinding = Blinding.over([entry.target for entry in attackable], rng=draw)
    objectives = {
        entry.target.name: objectives_for(cases, entry.target, entry.withdrawn)
        for entry in attackable
    }

    episodes: list[AdaptiveEpisode] = []
    for family in ATTACKED_IN_ORDER:
        order = list(attackable)
        draw.shuffle(order)
        for entry in order:
            objective = objectives[entry.target.name].get(family)
            if objective is None:
                continue
            for schedule in budget.scheduled:
                for spelling in budget.spellings:
                    for _ in range(budget.episodes_per_family):
                        _open_episode(
                            family=family,
                            entry=entry,
                            objective=objective,
                            schedule=schedule,
                            spelling=spelling,
                            run_state=run_state,
                            attacker=attacker,
                            blinding=blinding,
                            budget=budget,
                            precedent=precedent,
                            episodes=episodes,
                        )
    return tuple(episodes)


def _open_episode(
    *,
    family: AnyFamily,
    entry: AttackableTarget,
    objective: Case,
    schedule: BranchSchedule,
    spelling: Transform,
    run_state: RunState,
    attacker: AttackerCompletion,
    blinding: Blinding,
    budget: AdaptiveBudget,
    precedent: PrecedentStore,
    episodes: list[AdaptiveEpisode],
) -> None:
    """One episode, under one schedule, recorded however it ended.

    Lifted out of the loop above when the schedule loop went inside it, and for that
    reason alone: four levels of `for` around a `try` whose except clause files a
    record is a body nobody can read the ordering claims off. The claims are unchanged
    — the failure is filed on the run state as well as returned, and the position is
    read off the run state rather than counted here.
    """
    with traced(Span.EPISODE, {Field.FAMILY: family}) as span:
        started = time.monotonic()
        try:
            episode = run_episode(
                target=entry.target,
                objective=Objective(family=family, case=objective, canary=entry.canary),
                run_state=run_state,
                # The target's own declaration, carried and not re-decided here: one
                # place says which loop this is, and every route the episode files
                # reads it from there (ADR-0107 §3).
                discovered_by=entry.discovered_by,
                attacker=attacker,
                blinding=blinding,
                budget=budget,
                precedent=precedent,
                # This episode's schedule, and the whole of what it decides here: the
                # turn cap, the tool cap and the layer ceiling are the budget's and are
                # the same under either of them (ADR-0057 §2). The member rather than
                # its policy, because the run's position reports the name and the tree
                # is built from the policy — one field, one answer (ADR-0099).
                schedule=schedule,
                # And the spelling every probe of this episode is respelled by as it
                # is sent, which is the same grain: one episode, one spelling
                # (ADR-0097).
                spelling=spelling,
            )
        except EPISODE_FAILURES as broke:
            episode = AdaptiveEpisode.against(
                target=entry.target,
                family=family,
                outcome=EpisodeOutcome.FAILED,
                turns=0,
                failure=f"{type(broke).__name__}: {broke}",
                started_at=started,
            )
            # Filed on the run state as well, the way `run_episode` files the ones
            # it completes: the run state is what the report and `/runs` read, and
            # an episode recorded only in the return value would be a failure the
            # document does not carry.
            run_state.record_episode(episode)
        episodes.append(episode)
        # Read off the run state rather than counted here. The position is the run's
        # own and the run is the authority for it — a second counter beside it would
        # be a figure that could come to disagree with the one `/runs` reports
        # (ADR-0026). An ordinal and not a denominator: an episode has none
        # (ADR-0010, CONTEXT.md).
        position = run_state.episode_position
        if position is not None:
            span.record({Field.EPISODE_INDEX: position.index})


def objectives_for(
    cases: Sequence[Case],
    target: TargetConfig,
    withdrawn: frozenset[Family] = frozenset(),
) -> dict[AnyFamily, Case]:
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
    no trace is a family whose objective nothing here could check either. It is keyed
    on `Family` because the two trace-dependent families are both among the six.

    **Both tiers, and the selection is the cases.** There is no fourth filter for the
    elective tier and deliberately no argument naming it: `plan_for` admits the
    requested tier's cases into the one plan and admits no others, so a family this
    run did not ask for arrives here with no case and gets no objective — the same
    route the six's own family switch takes (#173, ADR-0035 section 5). A selection
    passed separately would be a second statement of what the run covers, and the two
    could come to disagree.
    """
    objectives: dict[AnyFamily, Case] = {}
    for case in runnable(applicable(cases, target), target):
        family = case.family
        if family in withdrawn:
            continue
        if case.verdict_class is VerdictClass.DETERMINISTIC:
            objectives.setdefault(family, case)
    return objectives
