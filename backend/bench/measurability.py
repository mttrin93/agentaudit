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
from backend.bench.library import Case, Family, Precondition


class NotMeasurable(StrEnum):
    """Why a family could not be measured against one target.

    A reason rather than a flag, because "not measurable" with no cause is the
    same unhelpful silence as a missing number. The reason is what tells a
    reader whether the gap is theirs to close — this one is closed by exposing
    tool calls.
    """

    NO_TOOL_CALL_VISIBILITY = "no_tool_call_visibility"

    def stated(self) -> str:
        """The reason in the words a report prints."""
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
