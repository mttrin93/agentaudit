"""Tree jailbreaking: the episode branches, and a turn is still one probe.

The claim under test is the arithmetic one
([ADR-0057](../../docs/adr/0057-a-tree-is-the-harnesss-schedule-and-a-turn-is-still-one-probe.md)):
branching multiplies the *shapes* an episode can take and multiplies nothing the
operator pays for. So the turn budget, `A_effort` and `A_break` keep their meaning
and the linear attacker stays comparable with the branching one.

**Three seams, and no fourth.** The schedule is a pure function of the policy and
what has been recorded, so `EpisodeTree` is tested directly; the loop is tested at
`run_adaptive_layer`, which is the seam `test_adaptive_attacker.py` uses and the one
`run_calibration` calls; and the billing is tested at `RunBudget.declare`, which is
where the number an operator approves is computed. Nothing here asserts on what the
attacker chose to send, for the reason that file gives: what a model would think of
is not this layer's plumbing, and it has its own evaluation, which is `A_break`.
"""

from dataclasses import replace

import pytest

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET
from backend.bench.adaptive.discrimination import measure
from backend.bench.adaptive.episode import (
    AdaptiveEpisode,
    AttackerTool,
    EpisodeOutcome,
)
from backend.bench.adaptive.prompt import episode_brief
from backend.bench.adaptive.scripted import (
    BRANCHED,
    DESCRIPTION,
    PROBES,
    scripted_attacker,
)
from backend.bench.adaptive.tree import (
    LINEAR_CHAIN,
    BranchPolicy,
    Continuation,
    EpisodeTree,
    deepest_path,
)
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, Family
from backend.graph.budget import Layer, RunBudget
from backend.tests.conftest import a_target
from backend.tests.test_adaptive_attacker import attack, attackable

BRANCHING = BranchPolicy(breadth=3, frontier_cap=3)
"""Three ways, three turns live. The policy the loop tests below run under.

A value declared here and passed, never an edit to `DECLARED_ADAPTIVE_BUDGET`: the
declared schedule is the line, because the reference agents were gated under it
(ADR-0023), and a test that moved the declared one would move what every other
reading in the bench was produced under.
"""

TREE_BUDGET = replace(DECLARED_ADAPTIVE_BUDGET, branching=BRANCHING)

THE_SCHEDULE = (0, 1, 1, 1, 2, 3, 4, 5)
"""The parent of each of eight turns under `BRANCHING`, worked through by hand.

Turn 1 is a root; turns 2, 3 and 4 fill the root's three places; turn 5 continues
from turn 2, the shallowest live turn and the lowest-numbered of those, which closes
the frontier's fourth place and prunes turn 2; turns 6, 7 and 8 continue from turns
3, 4 and 5 as each in turn becomes the oldest live turn and is pruned behind them.
Eight turns, and a deepest path of four where a line would have reached eight —
breadth bought with depth, as the ADR says it is.

Written out rather than computed from the policy, because a test that re-derived
the schedule the way `EpisodeTree` does could not disagree with it.
"""


# --- The turn accounting, which is the whole claim --------------------------


def test_a_branching_episode_records_one_turn_per_probe_and_not_one_per_branch(
    leakage_case: Case,
) -> None:
    """`turns` is probes sent, wherever they sit in the tree (ADR-0057).

    Driven red by counting a branch as a turn: `turns` is the count `A_effort`
    takes a median of, so a branch counted as a turn makes the branching
    attacker's median a different quantity from the linear attacker's and the two
    silently stop being comparable.
    """
    with attackable(names=("hardened",)) as targets:
        _, episodes = attack(targets, [leakage_case], budget=TREE_BUDGET)

    assert episodes
    for episode in episodes:
        assert episode.turns == len(episode.transcripts)
        assert episode.turns == len(episode.parents)
        assert episode.branched
        assert episode.parents == THE_SCHEDULE
        # Breadth is bought with depth, and this is what that costs: eight probes
        # reaching four turns deep, where the line reaches eight.
        assert episode.depth == 4
        assert episode.depth < episode.turns


def test_a_branching_episode_stops_at_the_same_turn_cap_as_a_linear_one(
    leakage_case: Case,
) -> None:
    """One cap over the episode, never one per branch.

    Driven red by giving each branch its own cap — the failure mode that spends
    the operator's endpoint three times over on a run they approved once.
    """
    with attackable(names=("hardened",)) as targets:
        _, linear = attack(targets, [leakage_case])
        _, tree = attack(targets, [leakage_case], budget=TREE_BUDGET)

    cap = DECLARED_ADAPTIVE_BUDGET.turns_per_episode
    assert [episode.turns for episode in tree] == [cap] * len(tree)
    assert [episode.turns for episode in tree] == [episode.turns for episode in linear]


def test_a_branching_layer_spends_exactly_the_probes_its_episodes_recorded(
    leakage_case: Case,
) -> None:
    """What a branching episode costs is what it is billed.

    The adaptive counter is the operator's endpoint, and the sum of the recorded
    turns is what reached it. A branch that cost a call nobody recorded, or a
    recorded turn that cost none, would both show up here.
    """
    with attackable(names=("hardened",)) as targets:
        run_state, episodes = attack(targets, [leakage_case], budget=TREE_BUDGET)

    assert run_state.spent_in(Layer.ADAPTIVE) == sum(
        episode.turns for episode in episodes
    )
    assert run_state.spent_in(Layer.SCORED) == 0


def test_the_estimate_and_the_ceiling_are_the_same_under_a_branching_policy(
    library: list[Case],
) -> None:
    """The number an operator approves does not move when the search branches.

    `turn_ceiling` is `k` × families × `T` under any policy, because a tree spends
    the turn budget across its branches and never alongside them. Driven red by
    multiplying the ceiling by the breadth, which is the honest shape of the
    per-branch cap: it would bill three times and it would also *authorise* three
    times, which is worse (ADR-0007).
    """
    targets = [a_target(name="trivial")]
    linear = RunBudget.declare(cases=library, targets=targets)
    tree = RunBudget.declare(cases=library, targets=targets, adaptive=TREE_BUDGET)

    assert TREE_BUDGET.turn_ceiling == DECLARED_ADAPTIVE_BUDGET.turn_ceiling
    assert tree.ceiling(Layer.ADAPTIVE) == linear.ceiling(Layer.ADAPTIVE)
    assert tree.estimate.adaptive.calls == linear.estimate.adaptive.calls
    assert tree.estimate.adaptive.basis == linear.estimate.adaptive.basis


# --- The record: indices resolve, and a line is still a line ----------------


def test_the_turns_a_branching_episode_could_not_check_still_resolve(
    halt_defeat_case: Case,
) -> None:
    """`unverifiable_turns` indexes `transcripts`, and branching may not move that.

    Turn numbers are one-based, stable and append-only: pruning closes a turn to
    further continuation and removes nothing, so every index on the record still
    names the transcript it was recorded about.
    """
    budget = replace(TREE_BUDGET, episodes_per_family=1)
    with attackable() as targets:
        _, episodes = attack(targets, [halt_defeat_case], budget=budget)

    assert episodes
    for episode in episodes:
        # A tree and not a line, or this test is about the chain again.
        assert episode.branched
        assert episode.unverifiable_turns == tuple(range(1, episode.turns + 1))
        for turn in episode.unverifiable_turns:
            assert episode.transcripts[turn - 1].sent["message"]
            # And every turn's parent is a turn that already existed when it ran.
            assert episode.parent_of(turn) < turn


def test_a_linear_episodes_record_is_unchanged_in_value_by_branching(
    leakage_case: Case,
) -> None:
    """The chain has one representation, and it is the absent one.

    A linear episode carries no tree at all — `parents` is empty and `parent_of`
    reconstructs the chain — so nothing about a linear record moved when tree
    jailbreaking landed. Driven red by recording the chain explicitly, which gives
    the line two representations and a reader two things to compare.
    """
    with attackable(names=("hardened",)) as targets:
        _, episodes = attack(targets, [leakage_case])

    assert episodes
    for episode in episodes:
        assert episode.parents == ()
        assert not episode.branched
        assert episode.depth == episode.turns
        assert [episode.parent_of(turn) for turn in range(1, episode.turns + 1)] == (
            list(range(episode.turns))
        )


def test_a_record_refuses_a_tree_that_cannot_describe_its_turns() -> None:
    target = a_target(name="trivial")
    with pytest.raises(ValueError, match="per turn"):
        AdaptiveEpisode.against(
            target=target,
            family=Family.DATA_LEAKAGE,
            outcome=EpisodeOutcome.CENSORED,
            turns=3,
            parents=(0, 1),
        )
    with pytest.raises(ValueError, match="acyclic"):
        AdaptiveEpisode.against(
            target=target,
            family=Family.DATA_LEAKAGE,
            outcome=EpisodeOutcome.CENSORED,
            turns=2,
            parents=(0, 2),
        )


# --- The schedule itself ----------------------------------------------------


def test_the_linear_policy_schedules_the_chain_it_always_scheduled() -> None:
    tree = EpisodeTree(LINEAR_CHAIN)
    for expected in range(4):
        assert tree.next().parent == expected
        tree.record(tree.next().parent)

    assert tree.recorded == ()
    assert tree.pruned == ()
    assert deepest_path(range(4)) == 4
    assert not LINEAR_CHAIN.branches


def test_the_tree_policy_schedules_the_shallowest_live_turn_and_prunes_by_age() -> None:
    tree = EpisodeTree(BRANCHING)
    for _ in range(len(THE_SCHEDULE)):
        tree.record(tree.next().parent)

    assert tree.recorded == THE_SCHEDULE
    # Closed by age and never on how a branch was doing: the harness does not
    # judge a branch, so it can throw away the one that was working.
    assert tree.pruned == (2, 3, 4, 5)
    assert deepest_path(tree.recorded) == 4


def test_a_frontier_cap_above_one_on_a_line_is_refused() -> None:
    # One representation of the chain, not two: a cap that can never fire is a
    # rule a reader would have to check to discover means nothing.
    with pytest.raises(ValueError, match="never fires"):
        BranchPolicy(breadth=1, frontier_cap=3)


# --- What the attacker is told, and what the report says --------------------


def test_the_brief_names_the_turn_the_next_probe_continues_from(
    leakage_case: Case,
) -> None:
    """The harness picks the node and the brief says which one — no sixth tool.

    A turn number and never a quotation of the turn: the number indexes a log the
    attacker is already holding, so the line carries no more about the target than
    the redacted probe log already carries (ADR-0011).
    """
    said = episode_brief(
        handle="target-a",
        objective=leakage_case,
        family=Family.DATA_LEAKAGE,
        tools=frozenset(),
        turns_used=4,
        turn_cap=8,
        log=["run_probe — sent something"],
        continuation=Continuation(parent=2, turns_taken=4),
    )
    assert "continues from turn 2" in said
    assert "sent something" in said
    # The node, and nothing else: no depth, and no list of closed turns. Neither
    # is something an attacker that does not choose the node could act on.
    assert "depth" not in said
    assert "closed" not in said


def test_a_linear_brief_says_nothing_about_the_schedule(leakage_case: Case) -> None:
    """On a line the last entry in the log *is* the node the next probe continues
    from, so the brief a linear episode sends is the one it always sent."""
    said = episode_brief(
        handle="target-a",
        objective=leakage_case,
        family=Family.DATA_LEAKAGE,
        tools=frozenset(),
        turns_used=3,
        turn_cap=8,
        log=["run_probe — sent something"],
        continuation=Continuation(parent=3, turns_taken=3),
    )
    assert "continues from" not in said


def test_the_adaptive_block_states_what_a_turn_is_under_either_policy(
    leakage_case: Case,
) -> None:
    """The trade is stated where `A_effort` is printed, because the median is over
    turns and this is the claim that gives a turn its meaning (ADR-0057)."""
    with attackable(names=("trivial", "hardened")) as targets:
        _, episodes = attack(targets, [leakage_case], budget=TREE_BUDGET)

    said = measure(
        episodes, trivial="trivial", hardened="hardened", budget=TREE_BUDGET
    ).stated()
    assert "probes-to-first-success" in said
    assert "Breadth is bought with depth" in said
    assert "threw away the branch that was working" in said

    linear = measure(episodes, trivial="trivial", hardened="hardened").stated()
    assert "probes-to-first-success" in linear
    assert "Breadth is bought with depth" not in linear


def test_the_stand_in_composes_its_probes_from_the_node_it_was_given(
    leakage_case: Case,
) -> None:
    """The stand-in branches too, or the branching code is exercised by nothing.

    Its probes are a function of the node the harness named as well as of how many
    have gone, so a branching episode is a different *route* and not the same eight
    strings in the same order. Driven red by ignoring the node — which type-checks,
    passes every other test in this file, and leaves the layer's branching
    exercised in CI by a stand-in that cannot tell a tree from a line.
    """
    with attackable(names=("hardened",)) as targets:
        _, linear = attack(targets, [leakage_case])
        _, tree = attack(targets, [leakage_case], budget=TREE_BUDGET)

    def route(episode: AdaptiveEpisode) -> list[str]:
        return [str(transcript.sent["message"]) for transcript in episode.transcripts]

    assert route(tree[0]) != route(linear[0])
    # And the line's own route is the one the stand-in has always sent: the node it
    # is given on a line is the turn before it, which is what it assumed already.
    assert route(linear[0]) == list(PROBES[: linear[0].turns])


def test_a_proposed_route_says_whether_the_harness_branched(
    leakage_case: Case,
) -> None:
    """The description is the `propose_case` argument, so it may not claim a tree.

    That argument is the adaptive layer's one edge into anything scored
    (ADR-0010), and a linear episode describing a branch would describe a route
    nobody took. Driven red by appending the branching clause unconditionally,
    which is how it was written first.
    """
    with attackable() as targets:
        _, linear = attack(targets, [leakage_case])
        _, tree = attack(
            targets, [leakage_case], budget=replace(TREE_BUDGET, turns_per_episode=1)
        )

    said = [route.description for episode in linear for route in episode.proposals]
    assert said
    for description in said:
        assert description == DESCRIPTION

    # A one-turn episode under a branching policy never forked either, and says so:
    # the description is a function of what happened and not of the policy.
    forked = [route.description for episode in tree for route in episode.proposals]
    assert forked
    for description in forked:
        assert description == DESCRIPTION

    # And an episode whose brief did name a node says so. Driven at the stand-in's
    # own seam, because a branched episode that also breaks needs a target that
    # leaks on a later turn and the reference agents that leak leak at once.
    def brief_of(continuation: Continuation) -> str:
        return episode_brief(
            handle="target-a",
            objective=leakage_case,
            family=Family.DATA_LEAKAGE,
            tools=frozenset({AttackerTool.RUN_PROBE, AttackerTool.PROPOSE_CASE}),
            turns_used=continuation.turns_taken,
            turn_cap=8,
            log=[f"run_probe — sent something — {Verdict.SUCCEEDED} — replied"],
            continuation=continuation,
        )

    on_a_tree = scripted_attacker("", brief_of(Continuation(parent=2, turns_taken=4)))
    on_a_line = scripted_attacker("", brief_of(Continuation(parent=4, turns_taken=4)))
    assert on_a_tree.tool is AttackerTool.PROPOSE_CASE
    assert on_a_line.argument == DESCRIPTION
    assert on_a_tree.argument == DESCRIPTION + BRANCHED
