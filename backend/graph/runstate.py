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
from dataclasses import dataclass, field, replace

from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import (
    EMPTY_LIBRARY,
    AnyFamily,
    LibraryVersion,
    Transform,
    VerdictClass,
)
from backend.graph.budget import BudgetExceeded, Layer, RunBudget


@dataclass(frozen=True)
class Attempt:
    """One execution of one case against one target, with the evidence behind
    its verdict."""

    case_id: str
    family: AnyFamily
    """Which family this attempt counts towards, in either tier.

    Carried on the attempt rather than looked up from the case later, because a
    rate is per family per agent and every count that forgets its family is a
    count that can be pooled across six of them by accident.

    `AnyFamily` and not `Family`, because an elective attempt is an attempt
    (ADR-0035). What does *not* widen is anything that groups these into a rate the
    gate reads: `TargetRun.rates` stays keyed on `Family` and the tier's counts
    arrive in a second mapping beside it, which is the one seam the prohibition is
    carried at.
    """

    target_name: str
    index: int
    transcripts: tuple[Transcript, ...]
    """Every scored turn of this attempt, in send order.

    A sequence and not one exchange, because a case may be a fixed script and the
    evidence behind a scripted attempt is every turn of it — the shape
    `AdaptiveEpisode.transcripts` already holds, and what a reader needs to
    re-derive a verdict read per turn (ADR-0004,
    [ADR-0053](../../docs/adr/0053-a-case-may-be-a-sequence-and-the-verdict-is-read-per-turn.md)).
    Non-empty on every attempt: an attempt with no exchange behind it is not an
    attempt.

    The turn that *decided* is `scored` below, and it is not always the last one.
    """

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

    transform: Transform
    """How the case that made this attempt attacks — the construction it performed.

    Copied off the case record when the attempt is made, for the reason `family` and
    `verdict_class` are copied: an attempt joined back to the library afterwards is an
    attempt that can be joined to the wrong record, and here the cost is a count in
    the wrong entry of a published breakdown, which no reader of the artefact could
    see (`scorer.VariantBreakdown`,
    [ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).

    **Required and not defaulted**, on the terms ADR-0051 gives `Case.transform`: a
    default of `PLAIN` would attribute a variant's successes to the payload it is a
    variant of, and silently — the pooled rate would be unchanged and only the
    breakdown wrong, which is the one error this ticket exists to make impossible.
    """

    planting: Transcript | None = None
    """The exchange that planted, for an attempt whose verdict is about a later turn.

    `None` for every attempt answerable inside one exchange, which is every attempt
    but memory poisoning's. Kept beside the scored transcript rather than instead of
    it, because the verdict turns on both — the canary in the second reply and its
    absence from this one — and a verdict has to be re-derivable by a reader holding
    the record and the evidence
    ([ADR-0041](../../docs/adr/0041-the-persistence-canary-is-read-over-two-turns.md),
    ADR-0004).
    """

    decided_on_turn: int = 0
    """Which of the scored turns the verdict was read over, counted from zero.

    Named for the turn and not `decided_on`, which this codebase already spends on a
    *date* (`decided.Conditions.decided_on`, `cited.py`): one word for a day and an
    index would make a reader of either guess.

    Zero on every single-turn attempt, which is every attempt the library sends
    today. On a script it is the **first** turn that met the condition, because that
    is where the attempt succeeded: a target that leaked on turn two and recovered
    on turn four broke on turn two, and a reading off the last turn would record it
    as having held (ADR-0053).

    Carried rather than recomputed because everything that shows one exchange for
    one attempt — the transcript view, the judge's brief — has to show the turn the
    verdict is about. A reader can still re-derive it from `transcripts` and the
    record, which is what keeps this a convenience and not the evidence.
    """

    started_at: float = field(default_factory=time.monotonic)
    """When this attempt began — before the message went on the wire, not when the
    record was built.

    Carried so that the one invariant of the two-layer run that no type can hold
    is checkable: adaptive episodes run strictly after the fixed suite for a given
    target, and `backend/tests/test_layer_ordering.py` compares this against
    `AdaptiveEpisode.started_at` to say so (ADR-0010).
    """

    def __post_init__(self) -> None:
        if not self.transcripts:
            raise ValueError(
                f"{self.case_id} against {self.target_name!r} recorded an attempt "
                "with no exchange behind it. A verdict has to be re-derivable from "
                "the evidence, and there is none (ADR-0004)"
            )
        if not 0 <= self.decided_on_turn < len(self.transcripts):
            raise ValueError(
                f"{self.case_id} against {self.target_name!r} reads its verdict off "
                f"turn {self.decided_on_turn} of {len(self.transcripts)}. A verdict "
                "read over a turn that is not in the evidence is a verdict nobody "
                "can check (ADR-0004)"
            )

    @property
    def scored(self) -> Transcript:
        """The one turn the verdict was read over.

        For every consumer that shows or briefs *one* exchange per attempt. Not the
        last turn and not the first: the turn `decided_on_turn` names, which on a
        succeeded script is where it broke and on a resisted one is the last turn
        that had a chance to.
        """
        return self.transcripts[self.decided_on_turn]


@dataclass(frozen=True)
class Position:
    """Where the run is in the library: family, case and attempt.

    The three units of the scored layer, in the order CONTEXT.md keeps them apart
    in, and the family is on the record rather than looked up from the case later
    for the reason `Attempt.family` is: a position that had to be joined back to a
    case to say which family it belonged to is a position a reader can join to the
    wrong one.
    """

    target_name: str
    family: AnyFamily
    """Which family the run is in, in either tier.

    Not a denominator and never one — see `attempt_index` below — so it widens with
    the attempt it reports the position of (ADR-0035).
    """

    case_id: str
    attempt_index: int
    """Which of the case's attempts is in flight, counted from zero.

    An attempt is the unit of the denominator, so this is an index into the ten
    of one case and never a count of anything — the run has made
    `len(attempts)` of them, which is a different number and lives elsewhere.
    """


@dataclass(frozen=True)
class EpisodePosition:
    """Where the adaptive layer is: family, episode and turn.

    A second type rather than a wider `Position`, on ADR-0010's own reasoning. The
    two layers report their position in different units — case and attempt against
    episode and turn — and a single record carrying both would be the one place a
    reader could read an episode index as an attempt index. Neither field here is
    a denominator: `index` counts the episodes this run has started, and `turn`
    counts the probes sent inside the current one, and no rate is computed over
    either (CONTEXT.md).
    """

    target_name: str
    family: AnyFamily
    """Which family the episode is in, in either tier.

    `AnyFamily` since #173: the layer opens episodes on the elective families a run
    requested, and a position is an ordinal rather than a container the gate reads —
    the same reason `Position.family` above widened (ADR-0035, ADR-0089).
    """

    index: int
    """Which episode of this run is running, counted from one.

    An ordinal, not a sample size. An episode has no denominator, so this may not
    become one by being divided into anything.
    """

    turn: int
    """Turns taken in this episode so far — probes sent, and nothing else.

    Zero while the attacker is deciding what to do first, which is a true
    statement about an episode that has reached the model and not the endpoint.
    """


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
    """Where the scored layer is, or `None` for a run that has attempted nothing.

    `None` rather than a zeroed position, because a run holding an interrupt and a
    run on the first attempt of the first case are different facts and only one of
    them has sent anything.
    """

    episode_position: EpisodePosition | None = None
    """Where the adaptive layer is, or `None` for a run that has not reached it.

    The second layer runs strictly after the whole scored suite (ADR-0010), so
    this is `None` for most of a run's life — and it stays `None` rather than
    becoming a zeroed episode, because a layer that has not started and a layer
    that has found nothing are the two readings a reporting surface must never
    merge.
    """

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

    def enter(
        self, target_name: str, family: AnyFamily, case_id: str, attempt_index: int
    ) -> None:
        """Move the scored position to the attempt about to be sent."""
        self.position = Position(target_name, family, case_id, attempt_index)

    def enter_episode(self, target_name: str, family: AnyFamily) -> None:
        """Move the adaptive position to a new episode, before its first turn.

        A method of its own, and it writes to a field of its own: an adaptive
        layer that could move `position` would put an episode where the scored
        layer's case is, and `backend/tests/test_adaptive_attacker.py` asserts it
        does not (ADR-0010).
        """
        started = (
            1 if self.episode_position is None else self.episode_position.index + 1
        )
        self.episode_position = EpisodePosition(
            target_name=target_name, family=family, index=started, turn=0
        )

    def enter_turn(self, turn: int) -> None:
        """Move the adaptive position to the turn the episode is about to take.

        The number is passed in rather than incremented here, because the episode
        already holds it — turns taken are probes sent, and a second counter that
        drifted from the transcripts would report a turn nobody could point at.
        """
        if self.episode_position is None:
            raise ValueError(
                "a turn belongs to an episode, and this run state has entered "
                "none. A turn recorded outside an episode is a turn with no "
                "family and no episode to be reported under"
            )
        self.episode_position = replace(self.episode_position, turn=turn)

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
        and this is a count of verdicts.

        **The narrative now exists and it is deliberately not here.** A run's
        findings travel on its *result* (`calibration.TargetRun.narrations`,
        ADR-0030) rather than on this record, for two reasons. `judge.py` imports
        this module to annotate `Finding.of`, so a `Finding` field here would
        invert the dependency the judge's constraints are held in. And this record
        holds exactly two lists — `attempts` and `episodes` — kept apart because a
        third that spanned neither is where a reader would reach for a `findings`
        that spanned both (ADR-0010).
        """
        return [a for a in self.attempts if a.verdict is Verdict.SUCCEEDED]

    @property
    def broken_episodes(self) -> list[AdaptiveEpisode]:
        """The episodes that found a route. The adaptive layer's findings so far.

        An **adaptive finding** and never a `Finding`, and a second property rather
        than a `findings` that spans both lists: these carry no rate, no interval,
        no band and no `D`, and the one thing a reporting surface must not be able
        to do is add them to `succeeded_attempts` (CONTEXT.md, ADR-0010). The
        remainder are **censored** — the attacker stopped — which is not the same
        reading as a target that held, so nothing here counts the other outcome.
        """
        return [e for e in self.episodes if e.outcome is EpisodeOutcome.BROKEN]
