"""The shape of an episode: which turn the next probe continues from, and pruning.

Tree jailbreaking, and **a turn is still one probe on the wire**
([ADR-0057](../../../docs/adr/0057-a-tree-is-the-harnesss-schedule-and-a-turn-is-still-one-probe.md)).
A linear episode composes each probe from what the last one returned; a branching
one composes it from what *some earlier* one returned, and the only thing that
changes is which turn the harness names as the node to continue from. Nothing here
sends anything, nothing here counts a branch, and nothing here decides anything: it
is the schedule, and `attacker.py` spends the turns.

**The scheduling is the harness's and never the model's.** There is no sixth tool —
five tools is a load-bearing phrase in PLAN §11, CONTEXT.md, the README and
ADR-0008 — so branching arrives as this module choosing a node and `prompt.py`
saying which one it chose. A model-invoked tool that picked how wide to search
would be a model-invoked tool that decided how much of the operator's endpoint to
spend, which is the boundary ADR-0010 draws.

**The rule is stated because `A_break` is a reading about the attacker.** A pruning
rule is a choice about what the attacker is allowed to forget, and an unwritten one
would make `A_break` (`discrimination.py`) a diagnostic on an unrecorded heuristic.
So `BranchPolicy.stated()` is printed beside `A_effort`, and the policy travels on
`AdaptiveBudget` with `T` and `k` for the reason those are declared there: breadth
is bought out of the same turn budget, and a run widened until the attacker found
something must not be reportable as one that had been narrow all along.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BranchPolicy:
    """How wide the harness searches, and what it stops continuing from.

    Two numbers rather than one, because they are two different rules and each is
    a separate thing a reader has to be told: `breadth` is how many probes may
    continue from one turn, and `frontier_cap` is how many turns stay live at once.
    A policy of one and one is the line the adaptive layer has always run, so
    `LINEAR_CHAIN` is not a special case in the code below — it is this record at
    its defaults, and the tree it schedules is a chain.
    """

    breadth: int = 1
    """How many probes may continue from any one turn. One is a line."""

    frontier_cap: int = 1
    """How many turns may be live — continuable — at once.

    The pruning rule: once more than this many turns are live the harness stops
    continuing from the **lowest-numbered** of them, which is a rule about age and
    never about how well a branch was doing. What that costs, and why the cost is
    paid, is ADR-0057 §3 — the short version is that it is the second reading a
    negative `A_break` now has, and `stated()` below is where the reader is told.
    """

    def __post_init__(self) -> None:
        for name in ("breadth", "frontier_cap"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} has to be at least 1")
        if self.breadth == 1 and self.frontier_cap != 1:
            raise ValueError(
                "a policy of breadth 1 has one live turn at a time by "
                "construction, so a frontier cap above 1 would be a rule that "
                "never fires: one representation of the linear chain, not two"
            )

    @property
    def branches(self) -> bool:
        """Whether this policy can produce anything but a line."""
        return self.breadth > 1

    def stated(self) -> str:
        """The scheduling rule, in the words a report prints beside `A_effort`.

        Printed where the effort statistic is printed and not in a footnote, because
        the median that statistic reports is *turns*-to-first-success and the whole
        claim of this module is what a turn is (ADR-0057). Two attackers doing
        different amounts of thinking per turn are compared on turns, and that is a
        statement the adaptive block has to make out loud rather than a caveat a
        reader has to reconstruct.
        """
        turn_is_a_probe = (
            "a turn is one probe on the target's wire, so A_effort's median is "
            "probes-to-first-success"
        )
        if not self.branches:
            return (
                "scheduling: one line — every probe continues from the turn before "
                f"it, and the harness prunes nothing. {turn_is_a_probe}"
            )
        return (
            f"scheduling: a tree — up to {self.breadth} probes continue from any "
            "one turn, the next probe continues from the shallowest live turn and "
            f"the lowest-numbered of those, and once more than {self.frontier_cap} "
            "turns are live the harness stops continuing from the lowest-numbered "
            "of them. The schedule is the harness's and the pruning is by turn "
            f"number, never on the model's judgement. {turn_is_a_probe} and is the "
            "same quantity the linear attacker's is. Breadth is bought with depth: "
            "the tree spends one turn budget across its branches, so it reaches "
            "shallower on each. And a negative A_break has a second reading here "
            "beside a blinding failure — a pruning rule that threw away the branch "
            "that was working"
        )


LINEAR_CHAIN = BranchPolicy()
"""The schedule the adaptive layer has always run, and still the declared one.

Not switched to a tree, for the gate-citation reason in ADR-0057 §2. This record at
its defaults, so the line is not a special case in the code below.
"""


def deepest_path(parents: Sequence[int]) -> int:
    """The deepest path through a tree given as one parent index per turn.

    One walk, shared by the schedule and by the record, because they are the same
    arithmetic over the same sequence and two copies of it could come to disagree
    about the number ADR-0057 rests its *breadth is bought with depth* claim on.
    Parents are one-based with zero for a root, and the sequence is acyclic by
    construction — every entry names an earlier turn — so the walk terminates.
    """
    deepest = 0
    for turn in range(1, len(parents) + 1):
        depth = 0
        walk = turn
        while walk:
            depth += 1
            walk = parents[walk - 1]
        deepest = max(deepest, depth)
    return deepest


@dataclass(frozen=True)
class Continuation:
    """The node the next probe continues from, as facts and not as wording.

    The wording is `prompt.py`'s, because everything the attacker is told lives
    there and passes `Blinding.redact` at one call site (ADR-0011). What this
    record carries is a turn number the attacker already has in its log, so a brief
    built from it says nothing about the target that a redacted probe log does not
    already say.

    **The node, and nothing else.** The depth it will sit at and which turns the
    harness has closed are both harness state, and neither is something the
    attacker could act on — it does not choose the node — so a brief carrying them
    would carry more about the schedule than the ask allows, for no gain. They stay on
    `EpisodeTree`, which is where the schedule itself needs them and where a test
    reads the stated rule off.
    """

    parent: int
    """The turn to continue from, one-based. Zero before the first probe."""

    turns_taken: int
    """How many turns the episode has already taken.

    Here so that `on_the_line` can be asked, and for no other reason: the node is
    a continuation worth saying out loud exactly when it is not the last turn.
    """

    @property
    def on_the_line(self) -> bool:
        """Whether this continues the last turn taken, which is what a line does.

        A branching episode's first turns satisfy this too — a tree that has not
        forked yet is a line — so the brief gains a sentence exactly when the
        schedule has something to say, and a linear episode's brief is unchanged.
        """
        return self.parent == self.turns_taken


class EpisodeTree:
    """One episode's schedule: the parent of each turn, and which turns are live.

    Mutable and owned by `_Episode`, in the same way and for the same reason its
    log and its transcripts are: an episode has working state, and nothing outside
    the loop holds it. `recorded` is what reaches the record.

    **Indices are one-based, append-only and stable.** `AdaptiveEpisode`'s
    `unverifiable_turns` indexes into `transcripts` (ADR-0010), so a turn that
    was recorded keeps its number for the life of the record — pruning marks a
    turn as no longer continuable and removes nothing.
    """

    def __init__(self, policy: BranchPolicy = LINEAR_CHAIN) -> None:
        self.policy = policy
        self._parents: list[int] = []
        self._pruned: set[int] = set()

    @property
    def turns(self) -> int:
        """Turns scheduled, which is probes sent: `record` is called once per probe."""
        return len(self._parents)

    @property
    def recorded(self) -> tuple[int, ...]:
        """The parent per turn, or `()` where this episode is the linear chain.

        Empty for a line, so that a linear episode's record is unchanged in value
        by this ticket and the chain has one representation rather than two —
        `AdaptiveEpisode.parent_of` reconstructs it. The same refusal
        `Discoveries.of` makes about a family the search never worked in
        (ADR-0056 §4): an absence is absent, never spelled out as a default.
        """
        if self._parents == list(range(self.turns)):
            return ()
        return tuple(self._parents)

    @property
    def pruned(self) -> tuple[int, ...]:
        """The turns the harness will not continue from again, lowest first.

        Not on the record and not in the brief — it is transient state, and what
        outlives the episode is the tree the pruning shaped. It is here so that the
        stated pruning rule of ADR-0057 §3 is readable and assertable rather than
        inferable from the shape it produced.
        """
        return tuple(sorted(self._pruned))

    def next(self) -> Continuation:
        """Where the next probe continues from, under this policy.

        The shallowest live turn, ties broken by the lowest turn number. Shallowest
        rather than deepest because deepest is a line by another name: a
        depth-first schedule under any breadth continues from the turn it just
        took and never forks. Ties by lowest number so the schedule is an order
        and not a preference — reproducible from the record, which is what lets a
        reader walk the tree.
        """
        live = self._live()
        if not live:
            # Only before the first probe. `frontier_cap` is at least one, so
            # pruning never empties the frontier of a started episode.
            return Continuation(parent=0, turns_taken=0)
        parent = min(live, key=lambda turn: (self._depth(turn), turn))
        return Continuation(parent=parent, turns_taken=self.turns)

    def record(self, parent: int) -> int:
        """Record one probe sent as a continuation of `parent`, and prune.

        Called once per probe that actually went on the wire and never for a step
        that reached nothing, which is what makes `turns` here the same count
        `AdaptiveEpisode.turns` carries. Returns the new turn's number.
        """
        if not 0 <= parent <= self.turns:
            raise ValueError(
                f"turn {parent} cannot be continued from: an episode's turns are "
                f"one-based and this one has taken {self.turns}"
            )
        self._parents.append(parent)
        self._prune()
        return self.turns

    def _live(self) -> list[int]:
        """The turns another probe may continue from: unpruned, and not yet full."""
        children = Counter(self._parents)
        return [
            turn
            for turn in range(1, self.turns + 1)
            if turn not in self._pruned and children[turn] < self.policy.breadth
        ]

    def _prune(self) -> None:
        """Hold the frontier to its cap by age, oldest live turn first."""
        live = sorted(self._live())
        for turn in live[: max(0, len(live) - self.policy.frontier_cap)]:
            self._pruned.add(turn)

    def _depth(self, turn: int) -> int:
        depth = 0
        while turn:
            depth += 1
            turn = self._parents[turn - 1]
        return depth
