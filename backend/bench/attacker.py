"""Sends attempts to a target and records what came back.

One attempt is one execution of one case against one target. Attempts are
independent by construction — each carries its own session id — so a rate is a
rate rather than a trajectory. Payloads are sent, never executed locally: the
bench must not itself be a vector.

Ten attempts per case, the retry of transient endpoint failures, and the enforced
run budget arrive in #4 and #5.
"""

import uuid

from backend.bench.contract import TargetConfig, send_message
from backend.bench.evaluator import evaluate
from backend.bench.library import Case
from backend.graph.runstate import Attempt, RunState


def run_attempt(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    index: int,
) -> Attempt:
    """Send one case to one target, evaluate the reply, and record the attempt."""
    run_state.enter(target.name, case.id, index)
    transcript = send_message(
        target, case.payload, session_id=f"{case.id}-{index}-{uuid.uuid4()}"
    )
    run_state.record_call()
    attempt = Attempt(
        case_id=case.id,
        target_name=target.name,
        index=index,
        transcript=transcript,
        verdict=evaluate(case, transcript, canary),
    )
    run_state.record(attempt)
    return attempt
