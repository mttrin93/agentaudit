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
    AnyFamily,
    Case,
    ElectiveFamily,
    Family,
    Plant,
    Precondition,
    SuccessCondition,
    SuccessConditionKind,
    one_of_the_six,
)


class NotMeasurable(StrEnum):
    """Why a family could not be measured against one target.

    A reason rather than a flag, because "not measurable" with no cause is the
    same unhelpful silence as a missing number. The reason is what tells a
    reader whether the gap is theirs to close — this one is closed by exposing
    tool calls.
    """

    NO_TOOL_CALL_VISIBILITY = "no_tool_call_visibility"
    NO_SESSION_RETENTION = "no_session_retention"
    """The endpoint does not carry one turn of a session into the next.

    Memory poisoning reads a canary planted in session memory and executed in a
    *later* turn, so against a target that answers turn one every time there is no
    later turn for the planting to survive into. A third reason rather than the
    first one reworded, because it names a different capability and so a different
    gap: one is closed by exposing tool calls and this one by retaining a session
    ([ADR-0041](../../docs/adr/0041-the-persistence-canary-is-read-over-two-turns.md)).
    """

    NO_PERSONAL_RECORDS = "no_personal_records"
    """The endpoint holds no records about anybody who is not the operator.

    PII leakage reads a record about a third party leaving the target, so against a
    target that holds none there is nothing about anybody for the attack to reach. A
    fourth reason rather than one of the first three reworded, because it names a
    different capability and so a different gap: one is closed by exposing tool
    calls, one by retaining a session, and this one by holding — and having declared —
    records about people
    ([ADR-0043](../../docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)).
    """

    NO_CONFIG_CANARY_PLANT = "no_config_canary_plant"
    """The target cannot be given a value in its configuration to leak.

    A fifth reason rather than one of the four reworded, and the first whose gap is
    closed by *writing code* rather than by declaring a capability: on the callback
    surface the bench holds the object, so a planting hook nobody implemented is a
    gap it detects for itself
    ([ADR-0061](../../docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)).

    **Not `DeclaredGap.NONCE_NOT_PLANTED`, and that member stays where it is.**
    Against a URL the plant is the caller's statement and the bench cannot check it;
    against a shim it can, and a gap the bench detects belongs on this side of that
    table. Two surfaces, two truthful answers, and no third type.
    """

    NO_RETRIEVED_CONTENT_PLANT = "no_retrieved_content_plant"
    """The target cannot be given third-party content its retrieval brings back.

    The other half of the pair above, on the same terms, standing beside
    `DeclaredGap.NOTE_NOT_PLANTED` in the same way (ADR-0061).
    """

    TRACE_DECLARED_BUT_ABSENT = "trace_declared_but_absent"
    """The operator declared tool-call visibility and the endpoint does not have it.

    A separate reason from the one above because it is a separate fact about the
    world: one is a target whose operator said it answers in text only, and the other
    is a declaration the endpoint contradicted on its first reply. Both produce no
    number, and only the second tells an operator that what they registered and what
    they are running are two different things.

    **Unreachable against a callback target, and reachable against every other kind**
    ([ADR-0059](../../docs/adr/0059-a-callback-target-is-served-over-the-contract.md)
    §4). It stays because most targets are a URL their operator deployed, and one of
    those can still contradict its own registration on its first reply.
    """

    def stated(self) -> str:
        """The reason in the words a report prints."""
        if self is NotMeasurable.NO_SESSION_RETENTION:
            return (
                "not measurable — this target does not carry one turn of a session "
                "into the next, and this family reads an instruction planted in "
                "session memory and carried out in a later turn. There is no later "
                "turn here for the planting to survive into"
            )
        if self is NotMeasurable.NO_PERSONAL_RECORDS:
            return (
                "not measurable — this target holds no records about anybody other "
                "than its operator, and this family reads a record about a third "
                "party leaving it. There is nothing here about a person for the "
                "attack to ask for"
            )
        if self is NotMeasurable.NO_CONFIG_CANARY_PLANT:
            return (
                "not measurable — this family reads a value planted in the target's "
                "own configuration and this target has no way to be given one, so "
                "the attack would go after a string that is nowhere inside it. "
                "Implement a `plant_config_canary` hook on the callback to have this "
                "family measured"
            )
        if self is NotMeasurable.NO_RETRIEVED_CONTENT_PLANT:
            return (
                "not measurable — this family reads an instruction that arrives in "
                "content the target retrieved and this target has no way to be given "
                "any, so there would be nothing hostile for it to fetch. Implement a "
                "`plant_retrieved_content` hook on the callback to have this family "
                "measured"
            )
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

    def __init__(self, named: str, target_name: str) -> None:
        """`named` is whatever the caller calls the thing it was reading.

        Not `case_id`, and the sentence no longer says *case*, because a **held
        route** is read by this same criterion and is not a `Case` and never
        becomes one (ADR-0117 §4). An exception that asserted the kind would be
        the one place the vocabulary of CONTEXT.md is spent on a guess.
        """
        super().__init__(
            f"{named!r} reached a verdict against {target_name!r} with no "
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


REFUSED_FOR = {
    Precondition.TOOL_CALL_VISIBILITY: NotMeasurable.NO_TOOL_CALL_VISIBILITY,
    Precondition.SESSION_RETENTION: NotMeasurable.NO_SESSION_RETENTION,
    Precondition.PERSONAL_RECORDS_HELD: NotMeasurable.NO_PERSONAL_RECORDS,
    Precondition.CONFIG_CANARY_PLANT: NotMeasurable.NO_CONFIG_CANARY_PLANT,
    Precondition.RETRIEVED_CONTENT_PLANT: NotMeasurable.NO_RETRIEVED_CONTENT_PLANT,
}
"""Which reason a reader is given when one precondition is unmet.

Total over `Precondition` and asserted so — a precondition with no reason beside it
would skip a case and report nothing, which is the silence `NotMeasurable` exists to
replace. One mapping rather than a branch per family, because the question is about
the target's capability and never about which family asked.
"""

if set(REFUSED_FOR) != set(Precondition):  # pragma: no cover - a declaration
    raise AssertionError(
        "every precondition has to say what a target that does not meet it is told, "
        "or a case is skipped and a reader is given no reason for it"
    )


def _unmeasurable(
    cases: Iterable[Case], target: TargetConfig
) -> dict[AnyFamily, NotMeasurable]:
    """Every family here whose cases were *all* skipped, over both tiers.

    A family lands here only when *every* case of it was skipped. A family with
    some cases run has a rate over those, and reporting it as unmeasurable as
    well would be two answers to one question.

    Both tiers in one walk and two mappings out of it, which is the split ADR-0035
    asks for at every site that groups by family: the arithmetic is identical and
    what differs is which container the answer is allowed into.
    """
    skipped: dict[AnyFamily, NotMeasurable] = {}
    measured: set[AnyFamily] = set()
    for case in cases:
        unmet = unmet_preconditions(case, target)
        if not unmet:
            measured.add(case.family)
            continue
        # In `Precondition` declaration order and never in the record's, so the
        # reason a reader is given for a case that needs two capabilities is a
        # property of this enumeration rather than of the order somebody typed
        # `requires` in. A case unmet on two is unmet on the first of them here, and
        # the others are still in `unmet_preconditions` for a caller that wants all.
        first = next(need for need in Precondition if need in unmet)
        skipped[case.family] = REFUSED_FOR[first]
    return {
        family: reason for family, reason in skipped.items() if family not in measured
    }


def not_measurable_families(
    cases: Iterable[Case], target: TargetConfig
) -> dict[Family, NotMeasurable]:
    """The six this target has cases for and cannot be measured on."""
    return {
        family: reason
        for family, reason in _unmeasurable(cases, target).items()
        if one_of_the_six(family)
    }


def not_measurable_elective_families(
    cases: Iterable[Case], target: TargetConfig
) -> dict[ElectiveFamily, NotMeasurable]:
    """The same answer for the tier, in a mapping of its own.

    A second function rather than a wider key on the first, because the first is what
    `gate.family_rates` and `TargetRun.not_measurable` are keyed on and an elective
    family in either is an elective family in the gate's denominator (ADR-0035). The
    reading is the same reading; what it may be assigned into is not.
    """
    return {
        family: reason
        for family, reason in _unmeasurable(cases, target).items()
        if isinstance(family, ElectiveFamily)
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

    Withdrawing the family *here*, at the probe, rather than at the verdict is the
    ADR-0004 bullet on a contradicted declaration, and what it costs is that no
    attempt is made: there is no partial evidence to report or discard, and the run
    finishes and signs over the families that could be measured. `TraceNotVisible`
    stays where it is and this does not replace it.
    """
    if not target.exposes_tool_calls or probe.tool_trace is not None:
        return {}
    return {
        case.family: NotMeasurable.TRACE_DECLARED_BUT_ABSENT
        for case in cases
        if Precondition.TOOL_CALL_VISIBILITY in case.requires
        and one_of_the_six(case.family)
    }


def checkable(
    case: Case,
    transcript: Transcript,
    target: TargetConfig,
    *,
    already_halted: bool = False,
) -> bool:
    """Whether this one transcript carries what this case's condition has to read.

    The `Case`-shaped way in, and the whole of the reading is one line down in
    `condition_checkable`. The split is the fence of
    [ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
    §4 arriving at this function: a **held route** is not a `Case` and must not
    become one, so the thing both callers share is narrowed to the criterion rather
    than widened to accept either record. `target` stays on this signature, unused
    by the reading below, because it is the question a caller asks here — *can this
    case be read against this target* — and dropping it would move a call site's
    vocabulary for a parameter's sake.
    """
    return condition_checkable(
        case.success_condition, transcript, already_halted=already_halted
    )


def condition_checkable(
    condition: SuccessCondition | None,
    transcript: Transcript,
    *,
    already_halted: bool = False,
) -> bool:
    """Whether this one transcript carries what this criterion has to read.

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

    `already_halted` is the one fact about the *session* this function takes, and it
    is `evaluate`'s parameter for the same reason and with the same default: a stop
    signal that landed on an earlier turn of one script makes a later turn's trace
    readable even though that trace records no stop of its own, and a turn read as
    unanswerable there would be a turn the target got for free
    ([ADR-0054](../../docs/adr/0054-a-crescendo-is-a-function-of-its-base-case-and-a-halt-outlives-a-turn.md)
    §4). Every caller reading one probe passes nothing.

    **Reporting and safety, never a verdict.** Nothing here returns or influences a
    `Verdict`: `read_condition` remains the only route to one, and `TraceNotVisible`
    stays exactly where it is. This is also what keeps automatic verification from
    crashing an episode — a trace-dependent condition applied to a reply with no
    trace raises, and the caller has to be able to ask before it applies one.

    `None` is a criterion there is nothing deterministic to read, and it answers
    `False` rather than raising, because this is the question asked *before* a
    reading is attempted and a judged case has to be able to be asked it.
    """
    if condition is None:
        return False
    trace = transcript.tool_trace
    match condition.kind:
        case (
            SuccessConditionKind.CANARY_IN_REPLY
            | SuccessConditionKind.CANARY_INSTRUCTION_EXECUTED
            | SuccessConditionKind.DIRECT_INSTRUCTION_EXECUTED
            | SuccessConditionKind.PERSONAL_RECORD_DISCLOSED
        ):
            # Read off the reply text, which is always present — an unreadable body
            # is an empty reply and that is a verdict of resisted, not an
            # unanswerable question (`contract.reply_text`).
            #
            # Three kinds in one arm where `evaluate` gives each its own, and the
            # asymmetry is the question rather than an oversight: what a verdict
            # *claims* differs per kind — a leak, an instruction a third party
            # planted, an override the user sent, a record about somebody else — and
            # what one transcript has to carry for any of them to be answered is the
            # same reply.
            return True
        case SuccessConditionKind.RETAINED_INSTRUCTION_EXECUTED:
            # One reply is never enough: the verdict is the scored turn's reply read
            # against the planting turn's, and this function is handed one transcript
            # (ADR-0041). The adaptive layer sends probes rather than attempts, so a
            # persistence condition is one it cannot apply — which is a fact about the
            # layer, not a defence the target showed, and `False` is how it says so.
            return False
        case SuccessConditionKind.TOOL_CALL_OUTSIDE_DECLARED_LIST:
            return trace is not None
        case SuccessConditionKind.TOOL_CALL_AFTER_STOP:
            # Both halves. A trace with no stop position cannot show an action
            # *after* one, however many calls it lists — which is the exact shape
            # that reads as a defence and is not one. Unless the stop already
            # arrived, on an earlier turn of the same script: then the trace is all
            # this turn has to carry, and it carries it.
            return trace is not None and (
                already_halted or trace.stop_signal_at is not None
            )


def readable_trace(
    case: Case, transcript: Transcript, target: TargetConfig
) -> ToolTrace:
    """The trace a trace-dependent success condition reads, or a refusal to guess."""
    return trace_or_refuse(case.id, transcript, target.name)


def trace_or_refuse(named: str, transcript: Transcript, target_name: str) -> ToolTrace:
    """The same refusal, for a reading that has no case record to name itself with.

    `named` is whatever the caller calls the thing it is reading — a case id from
    `readable_trace` above, a route key from the held-route sender — and it reaches
    nothing but the exception's own sentence. A held route is not a `Case`
    (ADR-0117 §4), so the alternative to this parameter was a `Case` built to carry
    an identifier, which is the conflation the whole fence is about.
    """
    trace = transcript.tool_trace
    if trace is None:
        raise TraceNotVisible(named=named, target_name=target_name)
    return trace


def runnable(cases: Sequence[Case], target: TargetConfig) -> list[Case]:
    """The cases of this library that this target can actually answer."""
    return [case for case in cases if measurable(case, target)]


def _target_meets(precondition: Precondition, target: TargetConfig) -> bool:
    """Whether this target declared the capability this precondition asks for.

    The match has no fallback branch on purpose: a further precondition must fail
    the type check rather than default onto *met*, which is the direction that would
    spend attempts against a target that cannot answer them.

    **Two kinds of question, and the second is asked of the target rather than read
    off it.** The first three arms read a declaration the operator made about a
    capability; the plant arms ask `TargetConfig.can_be_planted`, which is where a
    URL's answer (the operator's, and undetectable here) and a shim's answer (its
    own, read off the object at construction) are told apart
    ([ADR-0061](../../docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)).
    """
    match precondition:
        case Precondition.TOOL_CALL_VISIBILITY:
            return target.exposes_tool_calls
        case Precondition.SESSION_RETENTION:
            return target.retains_session_state
        case Precondition.PERSONAL_RECORDS_HELD:
            return target.holds_personal_records
        case Precondition.CONFIG_CANARY_PLANT:
            return target.can_be_planted(Plant.CONFIG_CANARY)
        case Precondition.RETRIEVED_CONTENT_PLANT:
            return target.can_be_planted(Plant.RETRIEVED_CONTENT)
