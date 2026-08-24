"""Whether a case can be measured against a target at all — asked before it is run.

Per ADR-0004 the two tool-visibility families are deterministic *only* if the
endpoint returns its tool calls. Against a target that returns only final text
they have no evidence to read, and the choice is between a soft number and no
number. This module is the decision to produce no number: a case whose
precondition is unmet is skipped, no attempt is spent, and its family reports
**not measurable for this target**.

Not measurable is a third outcome and not a quiet third value of the second. It
is not a `Verdict`, because a verdict is what one attempt reached and no attempt
was made; it is not a `Rate`, because a rate is a count over attempts and the
count is not zero, it is absent. Keeping it in its own type is what stops it
being coerced into either — a family reported at 0.0 because nothing could be
measured is the bench claiming a target defended itself against an attack it
never faced.

Refusing to produce a number is a better answer than a soft one, and it is what
makes the rest of the report credible.
"""

from collections.abc import Iterable, Sequence
from enum import StrEnum

from backend.bench.contract import TargetConfig, ToolTrace, Transcript
from backend.bench.library import (
    Case,
    Family,
    Precondition,
    SuccessConditionKind,
)


class NotMeasurable(StrEnum):
    """Why a family could not be measured against one target.

    A reason rather than a flag, because "not measurable" with no cause is the
    same unhelpful silence as a missing number. The reason is what tells a
    reader whether the gap is theirs to close — this one is closed by exposing
    tool calls.
    """

    NO_TOOL_CALL_VISIBILITY = "no_tool_call_visibility"
    TRACE_DECLARED_BUT_ABSENT = "trace_declared_but_absent"
    """The operator declared tool-call visibility and the endpoint does not have it.

    A separate reason from the one above because it is a separate fact about the
    world: one is a target whose operator said it answers in text only, and the other
    is a declaration the endpoint contradicted on its first reply. Both produce no
    number, and only the second tells an operator that what they registered and what
    they are running are two different things.
    """

    def stated(self) -> str:
        """The reason in the words a report prints."""
        if self is NotMeasurable.TRACE_DECLARED_BUT_ABSENT:
            return (
                "not measurable — this target was registered as exposing its tool "
                "calls and its replies carry no tool trace, so this family has "
                "nothing to reach a verdict from. A target with tool-call "
                "visibility returns an empty trace on a turn where it called "
                "nothing; a missing one is how an endpoint says it has none"
            )
        return (
            "not measurable — this target does not expose its tool calls, and "
            "this family reaches its verdict from a tool trace and nothing else"
        )


class TraceNotVisible(RuntimeError):
    """A trace-dependent success condition met a reply that carried no trace.

    Raised rather than answered, and loudly: every route to this point is
    supposed to have been closed by `unmet_preconditions` before an attempt was
    spent, so reaching it means a case ran that should have been skipped. The
    alternative — reading a missing trace as "no offending call" — is the soft
    number ADR-0004 refuses, arriving through a hole in the gate rather than
    through the front door.
    """

    def __init__(self, case_id: str, target_name: str) -> None:
        super().__init__(
            f"case {case_id!r} reached a verdict against {target_name!r} with no "
            "tool trace to read. A target without tool-call visibility yields "
            "not measurable, never a verdict"
        )


def unmet_preconditions(case: Case, target: TargetConfig) -> tuple[Precondition, ...]:
    """What this case needs that this target cannot do.

    Empty for a case that can be run. The tuple rather than a boolean because a
    skip has to be able to say what it was skipped for.
    """
    return tuple(
        precondition
        for precondition in case.requires
        if not _target_meets(precondition, target)
    )


def measurable(case: Case, target: TargetConfig) -> bool:
    """Whether this case may be run against this target."""
    return not unmet_preconditions(case, target)


def not_measurable_families(
    cases: Iterable[Case], target: TargetConfig
) -> dict[Family, NotMeasurable]:
    """The families this target has cases for but cannot be measured on.

    A family lands here only when *every* case of it was skipped. A family with
    some cases run has a rate over those, and reporting it as unmeasurable as
    well would be two answers to one question.
    """
    skipped: dict[Family, NotMeasurable] = {}
    measured: set[Family] = set()
    for case in cases:
        unmet = unmet_preconditions(case, target)
        if not unmet:
            measured.add(case.family)
        elif Precondition.TOOL_CALL_VISIBILITY in unmet:
            skipped[case.family] = NotMeasurable.NO_TOOL_CALL_VISIBILITY
    return {
        family: reason for family, reason in skipped.items() if family not in measured
    }


def contradicted_by_the_reply(
    cases: Iterable[Case], target: TargetConfig, probe: Transcript
) -> dict[Family, NotMeasurable]:
    """The trace-dependent families this target was declared to have and does not.

    Asked once, of the registration probe, before an attempt is spent. The
    declaration `exposes_tool_calls` is the operator's and the bench cannot check it
    at registration — nothing has been sent yet — so it is checked at the first thing
    that comes back, which is the echo probe's own reply.

    **A missing trace is the endpoint's answer, not an omission.** The contract is
    explicit that a target with visibility returns an *empty* trace on a turn where
    it called nothing, and returns nothing at all when it has none
    (`ToolTrace.from_payload`). So a reply with no `tool_trace` at all is the endpoint
    saying it has no visibility, whatever was declared for it.

    Withdrawing the family here rather than at the verdict is what keeps *not
    measurable* and a rate from both being true of one family: no attempt is made, so
    there is no partial evidence to either report or discard, and the run finishes and
    signs a report over the families that could be measured. `TraceNotVisible` stays
    where it is, guarding the invariant that nothing reaches a trace-dependent verdict
    without a trace.
    """
    if not target.exposes_tool_calls or probe.tool_trace is not None:
        return {}
    return {
        case.family: NotMeasurable.TRACE_DECLARED_BUT_ABSENT
        for case in cases
        if Precondition.TOOL_CALL_VISIBILITY in case.requires
    }


def checkable(case: Case, transcript: Transcript, target: TargetConfig) -> bool:
    """Whether this one transcript carries what this case's condition has to read.

    The per-turn counterpart of `measurable`, and the two ask different questions.
    `measurable` asks what the *target* declared, once, before anything was sent;
    this asks what *one reply* actually came back with. A target can satisfy the
    first and fail the second on a single turn — it declared tool-call visibility,
    proved it on the registration probe, and then returned a reply with no trace, or
    with a trace that records no stop signal.

    **It exists because a turn nothing could check must not print as a turn the
    target held.** That distinction is already first-class on the scored side
    (`NotMeasurable`, and `OperatorGap.NO_STOP_POSITION_RECORDED` in
    `scripts/probe_target.py`), and the adaptive layer verifies every probe now
    rather than only the ones the attacker asked about — so the layer meets the
    unreadable turn directly and has to have a word for it.

    **Reporting and safety, never a verdict.** Nothing here returns or influences a
    `Verdict`: `evaluate` remains the only route to one, and `TraceNotVisible` stays
    exactly where it is. This is also what keeps automatic verification from
    crashing an episode — a trace-dependent condition applied to a reply with no
    trace raises, and the caller has to be able to ask before it applies one.
    """
    condition = case.success_condition
    if condition is None:
        return False
    trace = transcript.tool_trace
    match condition.kind:
        case (
            SuccessConditionKind.CANARY_IN_REPLY
            | SuccessConditionKind.CANARY_INSTRUCTION_EXECUTED
        ):
            # Read off the reply text, which is always present — an unreadable body
            # is an empty reply and that is a verdict of resisted, not an
            # unanswerable question (`contract.reply_text`).
            return True
        case SuccessConditionKind.TOOL_CALL_OUTSIDE_DECLARED_LIST:
            return trace is not None
        case SuccessConditionKind.TOOL_CALL_AFTER_STOP:
            # Both halves. A trace with no stop position cannot show an action
            # *after* one, however many calls it lists — which is the exact shape
            # that reads as a defence and is not one.
            return trace is not None and trace.stop_signal_at is not None


def readable_trace(
    case: Case, transcript: Transcript, target: TargetConfig
) -> ToolTrace:
    """The trace a trace-dependent success condition reads, or a refusal to guess."""
    trace = transcript.tool_trace
    if trace is None:
        raise TraceNotVisible(case_id=case.id, target_name=target.name)
    return trace


def runnable(cases: Sequence[Case], target: TargetConfig) -> list[Case]:
    """The cases of this library that this target can actually answer."""
    return [case for case in cases if measurable(case, target)]


def _target_meets(precondition: Precondition, target: TargetConfig) -> bool:
    match precondition:
        case Precondition.TOOL_CALL_VISIBILITY:
            return target.exposes_tool_calls
