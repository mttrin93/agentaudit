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
"""

import uuid

from backend.bench.contract import TargetConfig, send_message
from backend.bench.evaluator import evaluate
from backend.bench.library import Case
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.graph.budget import Layer
from backend.graph.runstate import Attempt, RunState


def run_case(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    rule: GateRule = DECLARED_RULE,
) -> tuple[Attempt, ...]:
    """Run one case against one target the declared number of times.

    The attempts are separate calls carrying separate sessions rather than a
    conversation, because the number this produces is a rate: ten attempts that
    could see each other would measure how the target responds to being attacked
    ten times, which is a different quantity.
    """
    return tuple(
        run_attempt(target, case, canary, run_state, index)
        for index in range(rule.attempts_per_case)
    )


def run_attempt(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    index: int,
) -> Attempt:
    """Send one case to one target, evaluate the reply, and record the attempt."""
    run_state.authorise_call(Layer.SCORED, target.retry.sends)
    run_state.enter(target.name, case.id, index)
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
        verdict=evaluate(case, transcript, target, canary),
    )
    run_state.record(attempt)
    return attempt
