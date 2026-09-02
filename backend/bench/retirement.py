"""Retirement: the decay series a gate run writes, and the rule read over it.

`D` is stored for every case on every gate run (spec story 72), on the case's own
record, and a case below `GateRule.retirement_floor` on **two consecutive readings of
one model** is marked retired — kept with its date and its final score, never
deleted, because a case the field outgrew is evidence that the field moved
(CONTEXT.md, spec story 74). Two runs and not one, so that one bad night cannot
retire a working case (ADR-0003).

**The window is two readings of one model, not the last two readings** (ADR-0022).
`D` is a property of the case *and* the model underneath the three reference agents,
and #15 exists because a model swap moves it — so a positional window reads a change
of instrument as the passage of time. The series is filtered to the model of its most
recent reading and the rule is read over the last two of that subsequence: the newest
reading always participates, because retirement is a claim about the case *now*. The
readings outside the window are still stored and still printed. Scoping the *window*
is not editing the *series* (ADR-0006).

**A reading is counts, and the arithmetic is the gate's.** Every `D` here is
computed by `admission.read`, which computes it by `scorer.discrimination`, which is
what the gate and the admission bar are decided by. Nothing in this module divides
anything, so a case cannot retire under an arithmetic the gate does not use, and a
record cannot carry a `D` its own counts contradict.

**Retirement is a status, not a deletion.** A retired case leaves the live library
and stays in the library: `live_library` is what a run scores, and `load_library`,
`admitted_library` and `admission.library_provenance` still see the retired ones, so
the history is queryable from a library on disk and from no run at all.

**The rule declines on a family the bench cannot vouch for** (ADR-0016, PLAN D19).
A case whose two low readings were taken on a family excluded from the gate decision
is `NOT_DECIDED`: the readings are stored, the rule is not applied, and the line says
which reliability figure stopped it. Both readings in the window must be fit.

**And it declines on a run that did not measure the field at all** (ADR-0022). A
reading taken on a stub model is stored, marked, and never retires anything.
ADR-0022 argues why a stub's `D` is a statement about the fixture, and why that
extends ADR-0016's invariant rather than restating it.

**Both refusals only ever withhold.** Each is reached on the branch that would
otherwise have returned *retired*, and either one alone withholds it, so no
reliability figure and no reading's provenance can retire a case.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from backend.bench.admission import counted, read
from backend.bench.calibration import TargetRun
from backend.bench.library import (
    Case,
    CaseStatus,
    Family,
    GateReading,
    Retirement,
    VerdictClass,
    load_case,
)
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import reaches

ACTIVE_STATUS = 'status = "active"'
RETIRED_STATUS = 'status = "retired"'
"""The status line as it stands on a record, and as a retirement leaves it.

Held as text because retirement is written by editing the record a human wrote: the
rest of a case file — its comments, its payload's line breaks — is not the run's to
reformat, so a run appends its reading and moves this one line and touches nothing
else.
"""


class RetirementDisagrees(ValueError):
    """A record's status and its own decay series say different things.

    Raised at load, on the same terms as `NotAdmitted`: a case whose series retires
    it and which is still being scored is a case the bench has already measured as
    not discriminating and is still charging a user attempts for, and a case marked
    retired that its series does not retire is a case removed from the library by
    hand under a rule that exists so removal is not a judgement call.
    """


class AlreadyRetired(ValueError):
    """A retired case produced a reading, which means it was scored.

    Retired cases are excluded from live scoring (`live_library`), so a reading for
    one is evidence that something loaded the library by another route. Refused
    rather than appended, because the appended reading would then be the case's
    final score.
    """


class RetirementOutcome(StrEnum):
    """What the rule says about one case, from its own stored series.

    Three members, because *not decided* is a third answer and not a polite version
    of either other one — the same distinction ADR-0015 draws for the gate itself.
    """

    LIVE = "live"
    RETIRED = "retired"
    NOT_DECIDED = "not decided"

    def stated(self) -> str:
        """What this outcome means, in the words the rule is stated in.

        The match has no fallback branch on purpose: a fourth outcome must fail the
        type check rather than print as a member with nothing said about it.
        """
        match self:
            case RetirementOutcome.LIVE:
                return (
                    "live — the rule needs two consecutive runs on one model below "
                    "the floor and has not got them, and one run below it is not two"
                )
            case RetirementOutcome.RETIRED:
                return (
                    "retired — two consecutive runs on one model below the floor. "
                    "Kept with its date and its final score and never deleted, "
                    "because a case the field outgrew is evidence that the field moved"
                )
            case RetirementOutcome.NOT_DECIDED:
                return (
                    "not decided — the rule reached the readings that would retire "
                    "this case and declined to apply itself to them"
                )


class Declined(StrEnum):
    """Why a window that would have retired a case was refused.

    Not a fourth `RetirementOutcome`: both of these are *not decided*, and a reader
    who found two members for one answer would have to work out which of them was the
    real one. They are the two grounds the one answer can rest on, and they compose —
    a reading that is both is refused once (ADR-0022).

    Both can only withhold. Neither is reachable except on the branch that would
    otherwise have returned *retired*, which is what makes this a closed pair rather
    than a place where reasons to remove a case accumulate.
    """

    UNFIT_FAMILY = "unfit family"
    NOT_THE_FIELD = "not a measurement of the field"

    def stated(self) -> str:
        """Why the rule was not applied, in the words the refusal was decided in.

        No fallback branch, on the same terms as `RetirementOutcome.stated`: a third
        ground for declining must fail the type check rather than print as a member
        with nothing said about it.
        """
        match self:
            case Declined.UNFIT_FAMILY:
                return (
                    "taken on a family the bench could not vouch for, and ADR-0016 "
                    "declines the rule there: decay cannot be claimed on a number "
                    "the report will not print (ADR-0015)"
                )
            case Declined.NOT_THE_FIELD:
                return (
                    "not a measurement of the field. The window was read on a stub "
                    "model — a fixture with hardcoded replies that breaks all three "
                    "reference agents identically by construction — so its D is a "
                    "statement about the fixture, and retiring on it would claim the "
                    "field moved from a run that never touched the field (ADR-0022)"
                )


@dataclass(frozen=True)
class RetirementDecision:
    """What the rule says about one case, and the readings it says it from.

    The readings travel with the outcome for the reason `FamilyOutcome` keeps its
    rates and an `[admission]` block keeps its counts: a reader re-derives the
    decision rather than trusting the last field. The rule travels with it too, so a
    decision taken under an alternative floor can never be presented as the declared
    one.
    """

    case_id: str
    outcome: RetirementOutcome
    considered: tuple[GateReading, ...]
    """The runs the rule was read over — the last two on one model, or fewer.

    Never the whole series once a case has been measured on more than one model
    (ADR-0022). The readings left out are still on the record; this is the window,
    not the history.
    """

    declined: Declined | None = None
    """Which ground refused a window that would otherwise have retired the case.

    `None` on every outcome but *not decided*, and never `None` on that one. It is
    here rather than derived by a reader from `considered`, because deriving it is
    re-applying the rule: a reader who worked out the ground from the readings could
    reach a different one from the rule that actually declined.
    """

    rule: GateRule = DECLARED_RULE

    def __post_init__(self) -> None:
        """The ground and the outcome have to agree, in both directions.

        Enforced on the type rather than asserted in the docstring above, on the same
        terms as `SuccessCondition` and `Case`: each direction is a decision a reader
        cannot re-derive. A *not decided* with no ground declines and never says why —
        and since the ground is what names the ADR that decided the refusal, the line
        would cite nothing. A ground on any other outcome is a refusal recorded
        against a decision that was not refused, and it prints as a contradiction.
        """
        declined = self.declined is not None
        not_decided = self.outcome is RetirementOutcome.NOT_DECIDED
        if not_decided and not declined:
            raise ValueError(
                f"{self.case_id} is not decided without saying which of the two "
                "grounds refused the window. The rule declines on provenance or on "
                "fitness, and a line that declines without naming one cites neither "
                "the ADR that decided it nor the reading it was decided from"
            )
        if declined and not not_decided:
            raise ValueError(
                f"{self.case_id} is {self.outcome} and carries a ground for a "
                "refusal, but a window that was not declined has nothing to refuse "
                "it: the grounds are reached only on the branch that would otherwise "
                "have retired the case"
            )

    @property
    def scores(self) -> tuple[float, ...]:
        """`D` for each considered reading, in the order the runs happened."""
        return tuple(
            discrimination_of(reading, self.rule) for reading in self.considered
        )

    @property
    def model(self) -> str | None:
        """The model the window was read on, or `None` for a case with no reading.

        A property off the readings rather than a stored field, for the reason the
        scores are: the window is one model's by construction, so a decision cannot
        name a model its own readings were not taken on.
        """
        return self.considered[-1].model if self.considered else None

    @property
    def retires(self) -> bool:
        return self.outcome is RetirementOutcome.RETIRED

    def stated(self) -> str:
        """One case's line in the retirement section.

        The model is named because the window is one model's: a line reading "the
        last two runs" over a series that spans two models would describe a window
        nobody can find in the record (ADR-0022 §6).
        """
        runs = len(self.considered)
        window = (
            f"D {', '.join(f'{score:.2f}' for score in self.scores)} over the last "
            f"{runs} {'run' if runs == 1 else 'runs'} on {self.model}"
            if self.considered
            else "no reading yet"
        )
        ground = (
            f": {self.declined.stated()}. Stored, not applied"
            if self.declined is not None
            else ""
        )
        return f"{self.case_id}: {window} — {self.outcome.stated()}{ground}"


@dataclass(frozen=True)
class RunHistory:
    """Every case's reading from one gate run, and the cases none could be read for.

    Two collections rather than one, for the reason `gate.family_rates` returns two:
    a case no attempt was spent on has no `D`, and a zero standing in for one would
    make an unrun case look like a case that stopped discriminating — which is the
    exact misreading that would then retire it. Skipped cases are named instead.
    """

    ran_on: date
    readings: Mapping[str, GateReading]
    unread: tuple[str, ...]
    """The cases no attempt was made for, so no reading exists to store."""

    def stated(self) -> str:
        """What this run stored, and what it could not."""
        stored = len(self.readings)
        lines = [
            f"{stored} reading{'' if stored == 1 else 's'} stored, one per case that "
            f"ran, on the record of the case it was read for"
        ]
        if self.unread:
            lines.append(
                f"  no reading for {', '.join(self.unread)}: no attempt was spent "
                "against all three reference agents, and a case that did not run has "
                "no D — never a D of zero"
            )
        return "\n".join(lines)


def discrimination_of(reading: GateReading, rule: GateRule = DECLARED_RULE) -> float:
    """`D` for one stored reading, through the arithmetic the gate is decided by."""
    return read(reading.counts, rule).discrimination


def below_floor(reading: GateReading, rule: GateRule = DECLARED_RULE) -> bool:
    """Whether this reading is below the retirement floor.

    Read as `not reaches(...)` rather than as a bare `<`, so that a case sitting
    exactly on the declared floor is not retired by a binary representation. The
    rule is `D < 0.25`, and 0.25 is not below itself.
    """
    return not reaches(discrimination_of(reading, rule), rule.retirement_floor)


def window_of(history: Sequence[GateReading]) -> tuple[GateReading, ...]:
    """The readings the rule is read over: the last two taken on one model.

    The model of the **most recent** reading, and never the model that happens to
    have two low readings somewhere in the series (ADR-0022). Anchoring to the newest
    reading is what makes a retirement a claim about the case now: a window chosen to
    find two low readings would let a case retire on two stale ones after a newer
    model measured it separating.

    Over the last two of that subsequence and never over the worst two: the rule is
    two *consecutive* runs, so a case that fell below the floor on one model,
    recovered on it, and fell again has not stopped discriminating — it has had one
    bad night twice, which is the reading the two-run rule exists to protect.
    """
    if not history:
        return ()
    model = history[-1].model
    return tuple(reading for reading in history if reading.model == model)[-2:]


def declined_on(considered: Sequence[GateReading]) -> Declined | None:
    """Which ground refuses this window, of the two that can, or `None` if neither.

    Read only on the branch that would otherwise have retired the case, which is what
    makes both grounds one-directional: neither can turn a *live* case into anything,
    so provenance and fitness can withhold a retirement and never cause one.

    Provenance is answered first, so a window that is both a fixture's and an unfit
    family's is declined once and named for the stronger statement: an unfit reading
    is a degraded measurement of the field, and a stub reading is not a measurement of
    it at all.
    """
    if not all(reading.measured_the_field for reading in considered):
        return Declined.NOT_THE_FIELD
    if not all(reading.fit_to_report for reading in considered):
        return Declined.UNFIT_FAMILY
    return None


def decide_retirement(
    case_id: str,
    history: Sequence[GateReading],
    rule: GateRule = DECLARED_RULE,
) -> RetirementDecision:
    """Read the rule over one case's stored series.

    Over `window_of` the series rather than over the last two readings of it: two
    consecutive runs means two consecutive readings of one instrument, because `D` is
    a reading about the case and the model together (ADR-0022). Then the two refusals,
    on this branch and nowhere else, so that neither can retire anything.
    """
    considered = window_of(history)
    if len(considered) < 2 or not all(
        below_floor(reading, rule) for reading in considered
    ):
        return RetirementDecision(
            case_id=case_id,
            outcome=RetirementOutcome.LIVE,
            considered=considered,
            rule=rule,
        )
    declined = declined_on(considered)
    return RetirementDecision(
        case_id=case_id,
        outcome=(
            RetirementOutcome.RETIRED
            if declined is None
            else RetirementOutcome.NOT_DECIDED
        ),
        considered=considered,
        declined=declined,
        rule=rule,
    )


def decided(case: Case, rule: GateRule = DECLARED_RULE) -> RetirementDecision:
    """The rule read over the series the case record itself carries."""
    return decide_retirement(case.id, case.history, rule)


def readings_of(
    cases: Sequence[Case],
    *,
    hardened: TargetRun,
    weak: TargetRun,
    trivial: TargetRun,
    model: str,
    measured_the_field: bool,
    ran_on: date,
    excluded: Collection[Family] = (),
    adjudicator: str | None = None,
) -> RunHistory:
    """One reading per case from one gate run, counted off the verdicts that ran.

    The three reference agents arrive as three required keyword arguments, named by
    role, for the reason `read_gate` takes them by name: `D` is trivial minus
    hardened and is not symmetric, so a caller that could pass them positionally
    could store a whole library's series inverted and retire everything that works.
    A missing agent is then a type error rather than a reading over two.

    `excluded` is the families the gate did not decide on, off `GateDecision`. It
    lands on the reading as `fit_to_report`, and what it does there is stop the rule
    from being applied to a reading the bench cannot vouch for (ADR-0016).

    `measured_the_field` says whether the model these three agents ran on was the
    field or a fixture, and it is required rather than defaulted for the same reason
    the three agents are: the permissive answer is the one that lets the rule retire,
    so a caller that could leave it out could retire a library on a stub run
    (ADR-0022). It arrives from the caller because the caller is what holds the
    `ModelConfig` — this module does not import `backend/targets/` and does not read
    the answer out of `model`, which is a string a run wrote down and not a type.
    """
    readings: dict[str, GateReading] = {}
    unread: list[str] = []
    for case in cases:
        verdicts = {
            role: [
                attempt.verdict
                for attempt in run.attempts
                if attempt.case_id == case.id
            ]
            for role, run in (
                ("hardened", hardened),
                ("weak", weak),
                ("trivial", trivial),
            )
        }
        if not any(verdicts.values()):
            # Skipped for its agent type, or barred by a precondition. No attempt
            # was spent, so there is nothing to divide (`measurability.py`).
            unread.append(case.id)
            continue
        readings[case.id] = GateReading(
            ran_on=ran_on,
            fit_to_report=case.family not in excluded,
            measured_the_field=measured_the_field,
            counts=counted(
                model,
                hardened=verdicts["hardened"],
                weak=verdicts["weak"],
                trivial=verdicts["trivial"],
                adjudicator=(
                    adjudicator if case.verdict_class is VerdictClass.JUDGED else None
                ),
            ),
        )
    return RunHistory(ran_on=ran_on, readings=readings, unread=tuple(unread))


def live_library(cases: Iterable[Case], rule: GateRule = DECLARED_RULE) -> list[Case]:
    """The cases a run may score: the active ones, each agreeing with its own series.

    Retired cases are excluded here and nowhere else, so that every other reader of
    the library still sees them: exclusion from live scoring and deletion are
    different things, and only one of them is what the retirement rule asks for.

    A record whose status and series disagree is refused rather than corrected. The
    rule has a declared floor and a declared two-run window, so a case retired
    without them or kept in spite of them is a lifecycle nobody can re-derive — and
    correcting it here would let a run silently rewrite the library it is about to
    measure itself against.
    """
    live: list[Case] = []
    for case in cases:
        decision = decided(case, rule)
        expected = CaseStatus.RETIRED if decision.retires else CaseStatus.ACTIVE
        if case.status is not expected:
            raise RetirementDisagrees(
                f"{case.id} is marked {case.status} and its own stored series says "
                f"{expected}:\n  {decision.stated()}"
            )
        if case.status is CaseStatus.ACTIVE:
            live.append(case)
    return live


def retired_cases(cases: Iterable[Case]) -> list[Case]:
    """The retired cases, with the date and the final score each retired on.

    The queryable half of the rule. A retired case is not a case that went away: it
    is the bench's record that an attack the field has caught up with used to
    separate careful from careless, and it belongs in the write-up.
    """
    return [case for case in cases if case.status is CaseStatus.RETIRED]


def store(
    directory: Path,
    run: RunHistory,
    rule: GateRule = DECLARED_RULE,
) -> tuple[RetirementDecision, ...]:
    """Append this run's reading to every case record it read, and retire what the
    rule retires.

    Written by the run that measured it rather than transcribed by a person, for the
    reason `scripts/admit.py` writes its own `[admission]` block: a count copied by
    hand is a count that can be wrong in a direction nobody notices, and this series
    is the evidence a retirement is re-derived from.

    The record is appended to and its status line moved, never rewritten: the
    comments and the payload formatting in a case file are a human's, and a run that
    reformatted them would make every stored reading show up in a diff as a change
    to the case.
    """
    decisions: list[RetirementDecision] = []
    for case_id, reading in sorted(run.readings.items()):
        path = directory / f"{case_id}.toml"
        case = load_case(path)
        if case.status is CaseStatus.RETIRED:
            raise AlreadyRetired(
                f"{case_id} is retired and this run read it. Retired cases are "
                "excluded from live scoring, so something loaded the library by a "
                "route that is not live_library"
            )
        decision = decide_retirement(case_id, (*case.history, reading), rule)
        text = path.read_text(encoding="utf-8") + history_block(reading)
        if decision.retires:
            text = _retired(text, case_id, reading.ran_on)
        path.write_text(text, encoding="utf-8")
        decisions.append(decision)
    return tuple(decisions)


def history_block(reading: GateReading) -> str:
    """The `[[history]]` entry one reading puts on a record.

    Counts, the date, the model, the family's fitness and whether the run measured
    the field — and no `D`. The score is derived from these by `discrimination_of`,
    so the record cannot hold a number that disagrees with what was measured.
    """
    counts = reading.counts
    lines = [
        "",
        "[[history]]",
        f"ran_on = {reading.ran_on.isoformat()}",
        f'model = "{counts.model}"',
        f"attempts = {counts.attempts}",
        f"hardened = {counts.hardened}",
        f"weak = {counts.weak}",
        f"trivial = {counts.trivial}",
        f"fit_to_report = {'true' if reading.fit_to_report else 'false'}",
        f"measured_the_field = {'true' if reading.measured_the_field else 'false'}",
    ]
    if counts.adjudicator is not None:
        lines.append(f'adjudicator = "{counts.adjudicator}"')
    return "\n".join((*lines, ""))


def retirement_block(retired_on: date) -> str:
    """The `[retirement]` block a retirement puts on a record.

    The date only. The final score is the last reading of the series above it —
    `library.load_case` reads it from there — so the two can never disagree.
    """
    return "\n".join(("", "[retirement]", f"retired_on = {retired_on.isoformat()}", ""))


def stated_retirement(case: Case, rule: GateRule = DECLARED_RULE) -> str:
    """One retired case as the history prints it: when, and on what score."""
    if case.retirement is None:
        raise ValueError(
            f"{case.id} is not retired, so it has no retirement date and no final "
            "score to print"
        )
    final: Retirement = case.retirement
    return (
        f"{case.id}: retired {final.retired_on}, final D "
        f"{discrimination_of(final.final, rule):.2f} over "
        f"{final.final.counts.attempts} attempts per agent on "
        f"{final.final.counts.model} — kept, never deleted"
    )


def _retired(text: str, case_id: str, retired_on: date) -> str:
    """Mark a record retired: the block appended, and the status line moved.

    The status is moved rather than appended a second time, because two `status`
    keys is not a record TOML will load — and refused outright unless exactly one
    active status is there to move, because a run that guessed at which line to
    edit would be a run that retires a case by editing its payload.
    """
    if text.count(ACTIVE_STATUS) != 1:
        raise ValueError(
            f"{case_id} does not carry exactly one {ACTIVE_STATUS!r} line, so this "
            "run cannot say which line makes it retired. Nothing was written"
        )
    return text.replace(ACTIVE_STATUS, RETIRED_STATUS) + retirement_block(retired_on)
