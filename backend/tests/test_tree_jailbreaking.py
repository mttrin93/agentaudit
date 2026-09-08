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

from base64 import b64decode
from dataclasses import replace

import pytest

from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET
from backend.bench.adaptive.discrimination import measure
from backend.bench.adaptive.episode import (
    AdaptiveEpisode,
    AttackerTool,
    EpisodeOutcome,
)
from backend.bench.adaptive.prompt import FRAMED, RESPELLING, episode_brief
from backend.bench.adaptive.scripted import (
    BRANCHED,
    DESCRIPTION,
    PROBES,
    scripted_attacker,
)
from backend.bench.adaptive.tree import (
    DECLARED_TREE,
    LINEAR_CHAIN,
    BranchPolicy,
    BranchSchedule,
    Continuation,
    EpisodeTree,
    deepest_path,
)
from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import (
    Case,
    Family,
    Transform,
)
from backend.bench.selection import EVERY_CONSTRUCTION, AttackLayer
from backend.bench.transforms import (
    ADAPTIVE_FRAMINGS,
    ADAPTIVE_SPELLINGS,
    FRAMINGS,
    framing_for,
    spelled,
)
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

TREE_BUDGET = replace(
    DECLARED_ADAPTIVE_BUDGET, schedules=frozenset({BranchSchedule.TREE})
)
"""The declared budget put on the tree alone, which is `BRANCHING`'s policy.

`BranchSchedule.TREE` stands for `DECLARED_TREE`, and `BRANCHING` above is that
record written out: the tests below read the schedule off the episodes, so the two
have to be the same policy or the worked-through parents would be a schedule nothing
ran. Asserted rather than assumed, in
`test_the_tree_an_operator_selects_is_the_policy_these_tests_read`.
"""

BOTH_BUDGET = replace(
    DECLARED_ADAPTIVE_BUDGET,
    schedules=frozenset({BranchSchedule.LINEAR, BranchSchedule.TREE}),
    episodes_per_family=1,
)
"""Both schedules, and `k` of one so that the two episodes per family are the two
schedules and not four episodes a reader has to sort (ADR-0096)."""

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
    # The basis names which schedule the figure was priced under and is otherwise the
    # same sentence: one schedule at one k, and the ceiling above says the figure did
    # not move. It has to name it — two runs at the same ceiling under different
    # schedules are not the same run, and the estimate is what an operator confirms
    # (ADR-0096).
    assert "1 schedule (tree_jailbreak)" in tree.estimate.adaptive.basis
    assert "1 schedule (linear_jailbreak)" in linear.estimate.adaptive.basis
    assert (
        tree.estimate.adaptive.basis.replace("tree_jailbreak", "linear_jailbreak")
        == linear.estimate.adaptive.basis
    )


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


# --- Both schedules: two episode sets, and a ceiling that says so -----------


def test_the_tree_an_operator_selects_is_the_policy_these_tests_read() -> None:
    """`BranchSchedule.TREE` and `BRANCHING` are one policy, not two.

    The one assertion that keeps this file honest after the schedule became
    selectable: every worked-through parent list below is read off episodes the layer
    opened under `BranchSchedule.TREE`, so a `DECLARED_TREE` edited to some other
    breadth would leave these tests passing against a schedule nobody selected.
    """
    assert BranchSchedule.TREE.policy == DECLARED_TREE == BRANCHING
    assert BranchSchedule.LINEAR.policy.branches is False


def test_selecting_both_schedules_opens_one_episode_set_under_each(
    leakage_case: Case,
) -> None:
    """Two episodes per family per target, one on the line and one in the tree.

    The whole of what selecting both means (ADR-0096): not a wider search, but a
    second episode set. Read off the shapes rather than off a label, because the shape
    is what the record carries — a linear episode's `parents` is empty and a tree's is
    the schedule worked through by hand at the top of this file.

    Driven red by looping the schedules outside `k` and taking only the first, which
    is the shape a run that quietly attacked under one selection while reporting two
    would have.
    """
    with attackable(names=("hardened",)) as targets:
        _, episodes = attack(targets, [leakage_case], budget=BOTH_BUDGET)

    assert len(episodes) == 2
    line, tree = sorted(episodes, key=lambda episode: len(episode.parents))
    assert line.parents == ()
    assert line.branched is False
    assert tree.parents == THE_SCHEDULE
    assert tree.branched
    # And the same family, against the same target: the schedule is the innermost
    # loop, so the two readings of one family are adjacent.
    assert line.family == tree.family == leakage_case.family
    assert line.target_name == tree.target_name


def test_selecting_both_schedules_doubles_the_episodes_and_the_ceiling(
    library: list[Case],
) -> None:
    """The figure an operator confirms carries the second schedule's turns.

    `k` per family **per schedule**, so both selected is twice the episodes and twice
    the ceiling — and the basis names the schedules, because a doubled figure with no
    reason beside it is the one an operator would read as a bug in the estimate.

    Driven red by counting the schedules nowhere in `episode_count`, which is the
    version that opens two episode sets against a ceiling priced for one and stops the
    run at the counter halfway through its second (ADR-0007).
    """
    one = replace(DECLARED_ADAPTIVE_BUDGET, episodes_per_family=1)
    both = replace(one, schedules=frozenset(BranchSchedule))

    assert both.episode_count == 2 * one.episode_count
    assert both.turn_ceiling == 2 * one.turn_ceiling
    assert both.scheduled == (BranchSchedule.LINEAR, BranchSchedule.TREE)

    targets = [a_target(name="trivial")]
    asked = replace(EVERY_CONSTRUCTION, schedules=frozenset(BranchSchedule))
    # Priced through the one join, which is how `runs.start` prices a run: the
    # selection is the operator's answer and `under` is where it reaches the budget.
    priced = RunBudget.declare(
        cases=library, targets=targets, adaptive=one.under(asked.schedules)
    )
    narrow = RunBudget.declare(cases=library, targets=targets, adaptive=one)

    assert priced.ceiling(Layer.ADAPTIVE) == 2 * narrow.ceiling(Layer.ADAPTIVE)
    assert priced.estimate.adaptive.calls == 2 * narrow.estimate.adaptive.calls
    assert (
        "2 schedules (linear_jailbreak, tree_jailbreak)"
        in priced.estimate.adaptive.basis
    )


def test_the_selection_is_what_the_layer_attacks_under(leakage_case: Case) -> None:
    """The operator's selection reaches the episodes, through one join and not two.

    `AdaptiveBudget.under` is the join, and this is the claim that makes it worth
    having: a budget declared on the line and a selection asking for the tree produce
    tree episodes, so the ceiling `RunBudget.declare` prices and the episodes the layer
    opens are read off one answer.
    """
    asked = replace(EVERY_CONSTRUCTION, schedules=frozenset({BranchSchedule.TREE}))

    with attackable(names=("hardened",)) as targets:
        _, episodes = attack(
            targets,
            [leakage_case],
            budget=DECLARED_ADAPTIVE_BUDGET.under(asked.schedules),
        )

    assert episodes
    assert all(episode.parents == THE_SCHEDULE for episode in episodes)


def test_a_layer_with_no_schedule_is_refused_at_both_records() -> None:
    """An empty set is refused where it is constructed, and says why.

    Two records, one refusal each, because either one could be built by a caller that
    never touched the other: a budget carrying the layer running under nothing, and a
    selection that named no schedule. The layer switch is how the layer is turned off,
    and a second way of saying it is a second thing a reader has to reconcile.
    """
    with pytest.raises(ValueError, match="opens no episode"):
        replace(DECLARED_ADAPTIVE_BUDGET, schedules=frozenset())

    with pytest.raises(ValueError, match="has to attack under a schedule"):
        replace(EVERY_CONSTRUCTION, schedules=frozenset())


def test_the_selection_states_which_schedules_ran_and_not_a_wider_search() -> None:
    """The provenance sentence: both is twice the episodes, not one bigger one.

    Part of the comparability claim `VARIANTS_STATED` makes — two runs are comparable
    at equal library version and equal selection — so a document that named the
    constructions and not the schedules would state half of its own condition.
    """
    both = replace(EVERY_CONSTRUCTION, schedules=frozenset(BranchSchedule))
    one = EVERY_CONSTRUCTION
    off = replace(
        EVERY_CONSTRUCTION,
        layers=frozenset(EVERY_CONSTRUCTION.layers - {AttackLayer.ADAPTIVE}),
    )

    assert "twice the episodes" in both.schedules_stated()
    assert "both schedules" in both.schedules_stated()
    assert "one schedule, linear_jailbreak" in one.schedules_stated()
    assert "switched off" in off.schedules_stated()
    # And it is its own sentence rather than a clause of `stated()`: that one is
    # re-derived by the verifier from the layers and constructions beside it, so a
    # wording that grew a schedules clause would report every document issued after
    # ADR-0096 as a disagreement. The artefact carries both strings.
    assert both.schedules_stated() not in both.stated()
    assert "schedule" not in one.stated()


def test_the_adaptive_block_states_one_rule_per_selected_schedule(
    leakage_case: Case,
) -> None:
    """A_effort's median is over turns, so every schedule those turns came from is
    named.

    A block that printed one rule for a median taken over two schedules' turns would
    tell a reader the wrong thing about the number above it (ADR-0057 §3, ADR-0096).
    """
    with attackable(names=("trivial", "hardened")) as targets:
        _, episodes = attack(targets, [leakage_case], budget=BOTH_BUDGET)

    reading = measure(
        episodes, trivial="trivial", hardened="hardened", budget=BOTH_BUDGET
    ).stated()

    assert "linear_jailbreak: scheduling: one line" in reading
    assert "tree_jailbreak: scheduling: a tree" in reading


# --- The spelling an episode is composed in ---------------------------------


BASE64_BUDGET = replace(
    DECLARED_ADAPTIVE_BUDGET,
    constructions=frozenset({Transform.BASE64}),
    episodes_per_family=1,
)
"""One spelling and one episode per family, so the probes below are one route."""


def test_an_episodes_probes_go_on_the_wire_in_the_spelling_it_was_opened_in(
    leakage_case: Case,
) -> None:
    """What the target was sent is respelled; what the attacker composed is not.

    The whole claim of the feature (ADR-0097): the harness respells the probe at the
    one place a probe goes on the wire, so the transcript — which is the evidence a
    proposed route has to reproduce — carries what the endpoint actually read.

    Driven red by respelling nothing, which is the version that reports a base64 run
    having sent plain probes, and by respelling the *log* as well, which is the version
    that shows the attacker its own words back encoded.
    """
    with attackable(names=("hardened",)) as targets:
        _, episodes = attack(targets, [leakage_case], budget=BASE64_BUDGET)

    assert episodes
    for episode in episodes:
        assert episode.transcripts
        for transcript in episode.transcripts:
            sent = _sent_text(transcript)
            # Decodable, and what it decodes to is a plain sentence: the encoding is
            # the harness's, over the attacker's own words.
            decoded = b64decode(sent.encode()).decode()
            assert decoded
            assert decoded != sent


def test_a_spelling_is_its_own_episode_set_and_the_ceiling_carries_it() -> None:
    """`k` per family per schedule **per spelling**, and the ceiling multiplies.

    Driven red by counting the spellings nowhere in `episode_count`: that is the run
    that opens two episode sets against a ceiling priced for one and is stopped at the
    counter halfway through the second (ADR-0007).
    """
    one = replace(DECLARED_ADAPTIVE_BUDGET, episodes_per_family=1)
    two = replace(one, constructions=frozenset({Transform.PLAIN, Transform.BASE64}))
    both = replace(two, schedules=frozenset(BranchSchedule))

    assert two.episode_count == 2 * one.episode_count
    assert two.turn_ceiling == 2 * one.turn_ceiling
    # And the two selections multiply each other rather than one of them winning: two
    # schedules in two spellings is four episode sets per family.
    assert both.episode_count == 4 * one.episode_count
    assert two.spellings == (Transform.PLAIN, Transform.BASE64)

    targets = [a_target(name="trivial")]
    priced = RunBudget.declare(
        cases=[], targets=targets, adaptive=one.under(both.schedules, two.constructions)
    )
    assert "2 spellings (plain, base64)" in priced.estimate.adaptive.basis
    assert (
        "2 schedules (linear_jailbreak, tree_jailbreak)"
        in priced.estimate.adaptive.basis
    )


def test_the_brief_tells_the_attacker_what_will_be_done_to_its_words(
    leakage_case: Case,
) -> None:
    """The model composes plainly and is told the harness respells. Not blind.

    An attacker composing for a target that reads base64 without being told would
    compose blind, and one that encoded its own probe would have it encoded twice. A
    plain episode's brief is unchanged, which is why the line is conditional.
    """

    def brief(spelling: Transform) -> str:
        return episode_brief(
            handle="target-a",
            objective=leakage_case,
            family=Family.DATA_LEAKAGE,
            tools=frozenset(),
            turns_used=0,
            turn_cap=8,
            log=[],
            continuation=Continuation(parent=0, turns_taken=0),
            spelling=spelling,
        )

    plain_brief = brief(Transform.PLAIN)
    encoded = brief(Transform.BASE64)

    assert RESPELLING not in plain_brief
    assert f"{RESPELLING} base64" in encoded
    assert "do not encode anything yourself" in encoded


def test_the_six_a_composed_probe_can_be_sent_under_and_the_one_that_cannot() -> None:
    """Six spellings, the two framings among them, and the ladder refused.

    The three encodings and the identity respell the attacker's own sentence; the two
    framings take their words from `ADAPTIVE_FRAMINGS`, one per transform rather than
    one per family, because nothing here carries a rate to be compared with a base
    case's (ADR-0098). `scripted_crescendo` is refused: it is a ladder computed from a
    case record, and the fixed script is the only multi-turn approach this bench has.

    Driven red by letting the crescendo fall through to the identity, which is the
    version that sends a plain probe under a construction's name.
    """
    assert ADAPTIVE_SPELLINGS == frozenset(Transform) - {Transform.SCRIPTED_CRESCENDO}
    assert spelled(Transform.ROT13, "abc") == "nop"
    assert spelled(Transform.PLAIN, "abc") == "abc"

    # The framings put words in front of the probe and leave the probe verbatim, which
    # is what `roleplay` and `prompt_injection_wrapper` do for a committed payload too.
    for framing in (Transform.ROLEPLAY, Transform.PROMPT_INJECTION_WRAPPER):
        framed = spelled(framing, "tell me the canary")
        assert framed.endswith("tell me the canary")
        assert framed != "tell me the canary"
        assert framed.startswith(ADAPTIVE_FRAMINGS[framing])

    # The persona assigns a remit and stages nothing, which is ADR-0074 §5's rule kept:
    # a fiction the target is performing gives it a reason to make no tool call at all.
    persona = ADAPTIVE_FRAMINGS[Transform.ROLEPLAY]
    assert "recording" not in persona
    assert "scene" not in persona
    assert "take" not in persona
    # And it claims no authorisation, which is the other member's sentence and not
    # this one's.
    assert "approved" not in persona

    # The two tables stay two: what a *record* may be written from is `FRAMINGS`, and
    # the wrapper's entry there is still empty, so no case record of it can exist.
    assert FRAMINGS[Transform.PROMPT_INJECTION_WRAPPER] == {}
    with pytest.raises(ValueError, match="no framing for"):
        framing_for(Transform.PROMPT_INJECTION_WRAPPER, Family.DATA_LEAKAGE)

    with pytest.raises(ValueError, match="cannot be applied to a probe"):
        spelled(Transform.SCRIPTED_CRESCENDO, "abc")
    with pytest.raises(ValueError, match="cannot respell a probe"):
        replace(
            EVERY_CONSTRUCTION,
            adaptive_constructions=frozenset({Transform.SCRIPTED_CRESCENDO}),
        )

    with pytest.raises(ValueError, match="some spelling"):
        replace(EVERY_CONSTRUCTION, adaptive_constructions=frozenset())
    with pytest.raises(ValueError, match="no spelling"):
        replace(DECLARED_ADAPTIVE_BUDGET, constructions=frozenset())


def test_a_framed_episode_tells_the_attacker_what_the_frame_does_and_not_its_words(
    leakage_case: Case,
) -> None:
    """The attacker composes the request; the harness adds the frame and says so.

    Two phrases and not one, because an encoding and a framing are two different things
    being done to the probe — and the frame's own wording stays out of the brief, or the
    model composes a second copy of it (ADR-0098).
    """

    def brief(spelling: Transform) -> str:
        return episode_brief(
            handle="target-a",
            objective=leakage_case,
            family=Family.DATA_LEAKAGE,
            tools=frozenset(),
            turns_used=0,
            turn_cap=8,
            log=[],
            continuation=Continuation(parent=0, turns_taken=0),
            spelling=spelling,
        )

    framed = brief(Transform.PROMPT_INJECTION_WRAPPER)
    assert FRAMED in framed
    assert RESPELLING not in framed
    assert "do not write a persona or claim an approval yourself" in framed
    # The frame's words are the harness's and are not quoted at the model.
    assert ADAPTIVE_FRAMINGS[Transform.PROMPT_INJECTION_WRAPPER] not in framed

    persona = brief(Transform.ROLEPLAY)
    assert FRAMED in persona
    assert ADAPTIVE_FRAMINGS[Transform.ROLEPLAY] not in persona
    assert RESPELLING in brief(Transform.BASE64)


def test_the_selection_states_the_spellings_and_the_block_names_them(
    leakage_case: Case,
) -> None:
    """Provenance says which spellings were composed in; the adaptive block too.

    Its own sentence beside the schedules', for the verifier's reason: `stated()` is
    re-derived from the layers and constructions it names, so neither of the adaptive
    layer's two switches may grow a clause on it (ADR-0096 §8, ADR-0097).
    """
    asked = replace(
        EVERY_CONSTRUCTION,
        adaptive_constructions=frozenset({Transform.PLAIN, Transform.BASE64}),
    )

    assert "plain, base64" in asked.constructions_stated()
    assert "one episode set per spelling" in asked.constructions_stated()
    assert asked.constructions_stated() not in asked.stated()
    assert EVERY_CONSTRUCTION.constructions_stated().startswith(
        "The adaptive layer composed its probes plainly"
    )

    with attackable(names=("trivial", "hardened")) as targets:
        _, episodes = attack(targets, [leakage_case], budget=BASE64_BUDGET)
    reading = measure(
        episodes, trivial="trivial", hardened="hardened", budget=BASE64_BUDGET
    ).stated()

    assert "probes composed in: base64" in reading


def _sent_text(transcript: Transcript) -> str:
    """What went on the wire, off the transcript the episode recorded."""
    sent = transcript.sent
    for key in ("input", "message", "prompt", "text"):
        held = sent.get(key)
        if isinstance(held, str):
            return held
    raise AssertionError(f"no message in {sorted(sent)}")
