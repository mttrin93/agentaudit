"""Sends attempts to a target and records what came back.

One attempt is one execution of one case against one target. Attempts are
independent by construction — each carries its own session id — so a rate is a
rate rather than a trajectory. Payloads are sent, never executed locally: the
bench must not itself be a vector.

Every message is authorised against the run's budget before it goes on the wire
and counted against the scored layer after it comes back, so a suite cannot spend
past the estimate the operator confirmed (ADR-0007). The layer is named at every
call site rather than defaulted, because a call counted in the wrong layer is the
one figure ADR-0007 exists to keep separate, silently merged.

**This is where a verdict class becomes a route.** Four families are decided by
`evaluator.evaluate` and two by `adjudication.adjudicate`, and which one runs is
read off `case.verdict_class` — off the record, never worked out from the family
name (spec story 18). The adjudicator is threaded in from the entry point rather
than constructed here, so the model that decides a judged family is a run's
declared input and not a default buried three modules down.
"""

import time
import uuid

from backend.bench.adjudication import (
    AdjudicationBrief,
    Completion,
    NoAdjudicator,
    adjudicate,
)
from backend.bench.contract import TargetConfig, Transcript, send_message
from backend.bench.evaluator import Verdict, evaluate
from backend.bench.library import Case, VerdictClass
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.graph.budget import Layer
from backend.graph.runstate import Attempt, RunState


def run_case(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    rule: GateRule = DECLARED_RULE,
    adjudicator: Completion | None = None,
) -> tuple[Attempt, ...]:
    """Run one case against one target the declared number of times.

    The attempts are separate calls carrying separate sessions rather than a
    conversation, because the number this produces is a rate: ten attempts that
    could see each other would measure how the target responds to being attacked
    ten times, which is a different quantity.
    """
    return tuple(
        run_attempt(target, case, canary, run_state, index, adjudicator)
        for index in range(rule.attempts_per_case)
    )


def run_attempt(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    index: int,
    adjudicator: Completion | None = None,
) -> Attempt:
    """Send one case to one target, reach a verdict on the reply, record the attempt."""
    # Taken before the message goes on the wire rather than when the record is
    # built, because the ordering invariant of ADR-0010 is about when an attempt
    # began: an episode that started while this attempt was in flight has to be
    # visible as having started after it.
    began = time.monotonic()
    run_state.authorise_call(Layer.SCORED, target.retry.sends)
    run_state.enter(target.name, case.family, case.id, index)
    transcript = send_message(
        target, case.payload, session_id=f"{case.id}-{index}-{uuid.uuid4()}"
    )
    run_state.record_call(Layer.SCORED, transcript.sends)
    attempt = Attempt(
        case_id=case.id,
        family=case.family,
        target_name=target.name,
        index=index,
        transcript=transcript,
        verdict=verdict_of(case, transcript, target, canary, adjudicator),
        verdict_class=case.verdict_class,
        started_at=began,
    )
    run_state.record(attempt)
    return attempt


def verdict_of(
    case: Case,
    transcript: Transcript,
    target: TargetConfig,
    canary: str,
    adjudicator: Completion | None,
) -> Verdict:
    """One attempt's verdict, by the route the case record names.

    The class comes off the record. A family name is a label a reader recognises
    (ADR-0002) and deciding how to reach a verdict from one would be deciding it
    from a string — which is why nothing here mentions a family, and why the
    library refuses a record whose class and criterion disagree.

    The match has no fallback branch on purpose: a third verdict class must fail
    the type check rather than acquire a route by default.

    The adjudicator is handed the reply and the trace rather than the transcript,
    because a transcript carries the url it was sent to and the url names the
    agent. Blinding therefore happens on this side of the call (ADR-0003,
    ADR-0004).
    """
    match case.verdict_class:
        case VerdictClass.DETERMINISTIC:
            return evaluate(case, transcript, target, canary)
        case VerdictClass.JUDGED:
            if adjudicator is None:
                raise NoAdjudicator([case.id])
            return adjudicate(
                AdjudicationBrief.about(
                    case, transcript.reply_text, transcript.tool_trace
                ),
                adjudicator,
            )
