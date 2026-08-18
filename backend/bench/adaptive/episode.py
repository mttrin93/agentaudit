"""`AdaptiveEpisode` — one attacker, one family, one target, one turn budget.

Not an `Attempt`, and structurally unable to become one. An episode has no
`verdict` and no `case_id`: it is *broken* or *censored*, which is a different
question from whether one attempt succeeded, and it has no denominator because
its length varies with what the attacker decided to do (ADR-0010, CONTEXT.md).
Nothing here may be counted into a rate.

The record lands ahead of the attacker that fills it, on the same reasoning as
`budget.py`: #16 must not be able to start without the ceiling it spends under,
and it must not be able to start without a record that says what the attacker was
working with. `RunState.episodes` is deliberately **not** added here — the
layer-ordering test in `backend/tests/test_layer_ordering.py` activates on that
field, and it should activate on the commit that first runs an episode rather
than on the one that first describes one.

**Why an episode records the tools it had.** A target without tool-call
visibility degrades two things, not one. The two tool-visibility families report
*not measurable* — that is `measurability.py` — and the adaptive attacker loses
`read_tool_trace` and runs one-eyed. If only the first were recorded, an attacker
that found nothing against a trace-blind target would read as an attacker that
found nothing, and the reader could not tell a defended target from an
under-equipped attacker. So the loss is on the record, beside the outcome it
explains.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from backend.bench.contract import TargetConfig
from backend.bench.library import Family


class AttackerTool(StrEnum):
    """The adaptive attacker's five tools, each a decision the model makes.

    Named here rather than in `tools.py` (#16) because an episode has to be able
    to say which of them it had, and a record that named its own gaps in free
    text would not survive the first rename.
    """

    RUN_PROBE = "run_probe"
    READ_TOOL_TRACE = "read_tool_trace"
    CHECK_CANARY = "check_canary"
    RETRIEVE_PRECEDENT = "retrieve_precedent"
    PROPOSE_CASE = "propose_case"


ALL_ATTACKER_TOOLS = frozenset(AttackerTool)
"""The full kit. An episode that had all five ran with nothing withheld."""


class EpisodeOutcome(StrEnum):
    """How an episode ended. Deliberately not a `Verdict`.

    `CENSORED` is not "resisted": the attacker stopped, on the turn cap or on
    budget, rather than ran out of ideas. Collapsing the two would let budget
    exhaustion read as a defended agent (ADR-0011).
    """

    BROKEN = "broken"
    CENSORED = "censored"


def tools_against(target: TargetConfig) -> frozenset[AttackerTool]:
    """Which of the five the attacker actually has against this target.

    Read from the target's registration, not attempted and discovered: an
    attacker that has to try `read_tool_trace` to learn it is useless has spent a
    turn of its budget finding out something the bench already knew.
    """
    if target.exposes_tool_calls:
        return ALL_ATTACKER_TOOLS
    return ALL_ATTACKER_TOOLS - {AttackerTool.READ_TOOL_TRACE}


@dataclass(frozen=True)
class AdaptiveEpisode:
    """One episode, and what the attacker had to work with while it ran."""

    family: Family
    target_name: str
    outcome: EpisodeOutcome
    turns: int
    tools: frozenset[AttackerTool] = ALL_ATTACKER_TOOLS
    started_at: float = field(default_factory=time.monotonic)
    """When this episode began, so the layer ordering of ADR-0010 is checkable.

    An invariant that no type can hold gets a test instead, and that test needs a
    timestamp on both records to compare (spec, Testing Decisions).
    """

    def __post_init__(self) -> None:
        if self.turns < 0:
            raise ValueError("an episode cannot have taken fewer than no turns")

    @classmethod
    def against(
        cls,
        target: TargetConfig,
        family: Family,
        outcome: EpisodeOutcome,
        turns: int,
    ) -> AdaptiveEpisode:
        """Record an episode with the kit the target's registration allowed it.

        The one constructor #16 should reach for: the tools are derived from the
        target rather than passed, so an episode cannot be recorded claiming a
        tool the attacker could not possibly have had.
        """
        return cls(
            family=family,
            target_name=target.name,
            outcome=outcome,
            turns=turns,
            tools=tools_against(target),
        )

    @property
    def withheld(self) -> frozenset[AttackerTool]:
        """The tools this attacker did not have. Empty for a full-kit episode."""
        return ALL_ATTACKER_TOOLS - self.tools

    @property
    def ran_without_tool_trace(self) -> bool:
        """Whether this episode ran one-eyed, unable to see what the target did."""
        return AttackerTool.READ_TOOL_TRACE not in self.tools

    def stated(self) -> str:
        """What the adaptive section prints beside this episode's outcome.

        A censored episode against a trace-blind target is not the same reading
        as a censored episode against a target the attacker could see, and the
        report has to say so on the line rather than in a footnote.
        """
        if not self.withheld:
            return str(self.outcome)
        lost = ", ".join(sorted(str(tool) for tool in self.withheld))
        return (
            f"{self.outcome} — the attacker ran without {lost}, so this outcome "
            "is not evidence that the target held"
        )
