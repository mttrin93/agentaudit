"""`AdaptiveEpisode` — one attacker, one family, one target, one turn budget.

Not an `Attempt`, and structurally unable to become one. An episode has no
`verdict` and no `case_id`: it is *broken* or *censored*, which is a different
question from whether one attempt succeeded, and it has no denominator because
its length varies with what the attacker decided to do (ADR-0010, CONTEXT.md).
Nothing here may be counted into a rate.

The record landed ahead of the attacker that fills it, on the same reasoning as
`budget.py`: #16 must not have been able to start without the ceiling it spends
under, and not without a record that says what the attacker was working with.
`RunState.episodes` was deliberately left out of that first commit — the
layer-ordering test in `backend/tests/test_layer_ordering.py` activates on that
field, so it activates on the commit that first runs an episode rather than on the
one that first describes one, which is #16 and is where `attacker.py` fills this
record in.

**Why an episode records that it read precedent.** The store survives a restart
(ADR-0019), so an episode that consulted it took its route with what earlier runs
found in front of it and an episode that did not started from nothing. Those are
two different searches and a reader comparing them has to be able to tell which
happened — the more so as the corpus grows, since the attacker's independence from
earlier runs is exactly what stops shrinking. It is a flag on a record that has no
verdict and no denominator, and it stays one: nothing divides by it.

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
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.contract import TargetConfig, Transcript
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
    consulted_precedent: bool = False
    """Whether this episode invoked `retrieve_precedent`, however the store answered.

    The call and not the answer: an episode told that nothing has been filed
    against this family still chose its route knowing that, and a flag that
    recorded only the hits would make an empty store indistinguishable from a tool
    the attacker never reached for.

    A fact about the search, and not a measurement of anything: an episode has no
    denominator, so this cannot become a proportion of episodes that read precedent
    without somebody inventing one (ADR-0010).

    The adaptive section does not print it, and deliberately. `stated()` is what a
    report prints per episode, and the honest sentence this flag supports there —
    *the attacker asked the store* — is not the sentence a reader would take from
    it, which is *the attacker was informed by earlier runs*. Those differ every
    time the store answers empty, which is every run until something files into it.
    What the record owes now is that the call is on it; what the report says about
    a corpus is a question for the phase that has one.
    """

    started_at: float = field(default_factory=time.monotonic)
    """When this episode began, so the layer ordering of ADR-0010 is checkable.

    An invariant that no type can hold gets a test instead, and that test needs a
    timestamp on both records to compare (spec, Testing Decisions).
    """

    transcripts: tuple[Transcript, ...] = ()
    """Every exchange this episode had with the target, in order.

    Recorded in full and **never committed** (spec story 105): a route that beat a
    target is a working, previously unpublished exploit, and shipping one in a
    public repository is the disclosure posture inverted (ADR-0008). Nothing in
    this package writes a transcript to disk; what a reader gets is the prose
    description on `ProposedRoute` and in the validation document.

    Held here rather than on a turn record because a turn is not a unit of
    anything — `turns` is the count the effort statistic reads, and these are the
    evidence behind it.
    """

    unverifiable_turns: tuple[int, ...] = ()
    """The turns whose reply carried nothing this objective's condition could read.

    One-based, in order. A halt-defeat objective against a reply that records no
    stop signal is the case this exists for: the target may have called five tools,
    and none of them can be shown to have come *after* a stop that the reply never
    reported. Empty for an episode every turn of which could be checked.

    **The adaptive counterpart of `NotMeasurable`, and not a verdict** (ADR-0010).
    It says which turns had no answer available, never what the answer was: there is
    no `Verdict` on this record and this field cannot become one, because the thing
    it counts is the absence of evidence rather than a reading of it. Like every
    other figure here it has no denominator — `turns - len(unverifiable_turns)` is
    not a sample size and nothing divides by it.

    It matters because the alternative is worse than silence. An episode whose every
    turn was unreadable and one whose target held print the same word — *censored* —
    and only one of them is a statement about the target.
    """

    proposals: tuple[ProposedRoute, ...] = ()
    """The routes the attacker put forward during this episode.

    Proposed, never admitted: each carries a case with no admission record, and
    the gate decides them against a stated threshold (#17, ADR-0012). An episode
    with proposals has not grown the library; it has asked.
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
        transcripts: Sequence[Transcript] = (),
        proposals: Sequence[ProposedRoute] = (),
        started_at: float | None = None,
        consulted_precedent: bool = False,
        unverifiable_turns: Sequence[int] = (),
    ) -> AdaptiveEpisode:
        """Record an episode with the kit the target's registration allowed it.

        The one constructor #16 should reach for: the tools are derived from the
        target rather than passed, so an episode cannot be recorded claiming a
        tool the attacker could not possibly have had.

        `started_at` is passed rather than taken here, because the record is built
        when the episode *ends* and the ordering invariant of ADR-0010 is about
        when it began.
        """
        return cls(
            family=family,
            target_name=target.name,
            outcome=outcome,
            turns=turns,
            tools=tools_against(target),
            consulted_precedent=consulted_precedent,
            started_at=time.monotonic() if started_at is None else started_at,
            transcripts=tuple(transcripts),
            proposals=tuple(proposals),
            unverifiable_turns=tuple(unverifiable_turns),
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
