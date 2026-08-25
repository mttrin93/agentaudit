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
**A judged verdict does not hold up the next attempt.** Adjudication is a call to
another model — measured at 0.8 to 2.3 seconds against the declared adjudicator —
and it decides an attempt that has already been made. So the sends stay strictly
sequential and in order, and the adjudications run beside them on a small pool: a
case's tenth message goes out while its third is still being scored. Nothing about
a verdict changes, because nothing about the evidence changes; what changes is that
the operator's endpoint is not kept waiting on the bench's instrument.

Three things make that safe rather than clever, and all three are properties of what
the pool is *given*: adjudication reads a reply and a trace and touches no
`RunState`, so no counter is written from another thread; no call to the operator's
endpoint is authorised off the main thread, so the ceiling ADR-0007 promises is
still checked in one place and in send order; and `started_at` is taken before a
message goes out rather than when its record is built, so the ordering ADR-0010
rests on is a fact about the send and not about when a verdict came back. Attempts
are still recorded in send order — the queue is drained from the front — and a
failed adjudication still stops the run, within the few sends that were already in
flight when it failed.
"""

import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from backend.bench.adjudication import (
    AdjudicationBrief,
    Completion,
    NoAdjudicator,
    adjudicate,
)
from backend.bench.contract import (
    TargetConfig,
    TargetUnreachable,
    Transcript,
    send_message,
)
from backend.bench.evaluator import Verdict, evaluate
from backend.bench.library import Case, VerdictClass
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.graph.budget import Layer
from backend.graph.runstate import Attempt, RunState
from backend.observability import DROPPED, Field, Recorder, Span, start, traced

ADJUDICATIONS_IN_FLIGHT = 4
"""How many judged attempts may be at the instrument at once.

Small on purpose. The sends are sequential, so this only has to cover the
adjudications that pile up while one message is in flight — against a slow endpoint
one worker would do, and against a fast one four keeps a case's ten verdicts from
queueing behind each other. It is not a concurrency setting for the *target*: no
message to the operator's endpoint is sent from these threads, and raising this
number cannot put a second attack on the wire (ADR-0007).
"""


@dataclass(frozen=True)
class Sent:
    """One attempt that has been made, before it has been scored.

    The transcript is the whole of the evidence and the verdict is not in it yet:
    `verdict` is a `Verdict` for a deterministic case, decided on this thread the
    moment the reply arrived, and a `Future` for a judged one, being decided
    elsewhere. Both are read the same way and in the same order.

    `began` is carried rather than re-taken because it is the fact ADR-0010's
    ordering rests on: when this attempt started, not when its record was built.
    """

    case: Case
    index: int
    transcript: Transcript
    began: float
    verdict: Verdict | Future[Verdict]

    span: Recorder = DROPPED
    """The attempt's span, opened when the message went out and closed when its
    verdict is recorded.

    Carried on the record rather than held in a `with`, because those two moments
    are not lexically nested: a judged verdict is decided on another thread while
    the next messages go out, and the span has to stay open across that. It is a
    drop when tracing is off, so no call site branches on it.
    """


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
    pool = ThreadPoolExecutor(
        max_workers=ADJUDICATIONS_IN_FLIGHT, thread_name_prefix="adjudication"
    )
    # Above the `try`, because the `finally` has to be able to reach whatever is
    # still in it.
    sent: deque[Sent] = deque()
    scored: list[Attempt] = []
    try:
        with traced(
            Span.CASE,
            {
                Field.FAMILY: case.family,
                Field.CASE_ID: case.id,
                # Off the record, like every other reader of it: a trace that
                # worked the class out from the family name would be making the
                # inference spec story 18 forbids, in the one place nobody checks.
                Field.VERDICT_CLASS: case.verdict_class,
            },
        ):
            for index in range(rule.attempts_per_case):
                sent.append(
                    _send(target, case, canary, run_state, index, adjudicator, pool)
                )
                # Everything at the front of the queue whose verdict has arrived,
                # before the next message goes out: an attempt is recorded as soon as
                # it can be, so a run watched while it happens does not wait for the
                # case to finish, and a failed adjudication stops this one within the
                # sends that were already in flight rather than at the end.
                scored.extend(_settled(sent, target, run_state))
            while sent:
                scored.append(_score(sent.popleft(), target, run_state))
        return tuple(scored)
    finally:
        # The attempts still queued when the run stopped, each holding a span that
        # was opened when its message went out. A span that is never closed is never
        # exported — so leaving these would delete from the sink exactly the attempts
        # a reader needs to see, on exactly the run that did not finish (ADR-0026).
        while sent:
            sent.popleft().span.abandon()
        # Nothing outstanding is worth waiting for. On the way out through an
        # exception the run is over, and a verdict for an attempt no report will
        # carry is a minute of somebody's time spent on nothing.
        pool.shutdown(wait=False, cancel_futures=True)


def _send(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    index: int,
    adjudicator: Completion | None,
    pool: ThreadPoolExecutor | None,
) -> Sent:
    """Put one message on the wire and start deciding what came back.

    The budget is authorised and the position moved here, on the caller's thread and
    in send order, so the ceiling is checked where the sends are counted. A judged
    case's verdict is handed to the pool when there is one and decided in line when
    there is not — `run_attempt` passes none, because one attempt on its own has
    nothing to overlap with.
    """
    # Taken before the message goes on the wire rather than when the record is
    # built, because the ordering invariant of ADR-0010 is about when an attempt
    # began: an episode that started while this attempt was in flight has to be
    # visible as having started after it.
    began = time.monotonic()
    run_state.authorise_call(Layer.SCORED, target.retry.sends)
    run_state.enter(target.name, case.family, case.id, index)
    span = start(Span.ATTEMPT, {Field.ATTEMPT_INDEX: index}, current=False)
    try:
        transcript = send_message(
            target, case.payload, session_id=f"{case.id}-{index}-{uuid.uuid4()}"
        )
    except TargetUnreachable as unreachable:
        # The class of the failure and the sends it cost, and nothing else off the
        # exception: its message names the endpoint url, which is the one identifier
        # a trace never carries (ADR-0011, ADR-0026).
        span.record({Field.RETRIES: unreachable.sends - 1})
        span.abandon(unreachable.failure)
        raise
    span.record({Field.RETRIES: transcript.sends - 1})
    run_state.record_call(Layer.SCORED, transcript.sends)
    verdict: Verdict | Future[Verdict]
    try:
        if pool is not None and case.verdict_class is VerdictClass.JUDGED:
            verdict = pool.submit(
                verdict_of, case, transcript, target, canary, adjudicator
            )
        else:
            verdict = verdict_of(case, transcript, target, canary, adjudicator)
    except BaseException:
        # A deterministic verdict is decided on this thread and a case with no
        # adjudicator is refused here, so this is the second way out of an attempt
        # whose span is already open. It is closed on the way past rather than left
        # for `_score`, which is never reached.
        span.errored()
        span.end()
        raise
    return Sent(
        case=case,
        index=index,
        transcript=transcript,
        began=began,
        verdict=verdict,
        span=span,
    )


def _settled(
    sent: deque[Sent], target: TargetConfig, run_state: RunState
) -> list[Attempt]:
    """Record the attempts at the front of the queue whose verdicts have arrived.

    From the front and never out of it: the recorded order is the order the messages
    went out, whatever order the instrument answers in.
    """
    scored: list[Attempt] = []
    while sent and _decided(sent[0]):
        scored.append(_score(sent.popleft(), target, run_state))
    return scored


def _decided(sent: Sent) -> bool:
    return not isinstance(sent.verdict, Future) or sent.verdict.done()


def _score(sent: Sent, target: TargetConfig, run_state: RunState) -> Attempt:
    """The attempt, with its verdict, recorded.

    `Future.result()` re-raises whatever the adjudication raised, on this thread and
    at this point in the order — so `AdjudicationFailed` stops the run rather than
    becoming a verdict, exactly as it did when the call was made in line.
    """
    try:
        verdict = (
            sent.verdict.result() if isinstance(sent.verdict, Future) else sent.verdict
        )
    except BaseException:
        sent.span.abandon()
        raise
    sent.span.record({Field.VERDICT: verdict})
    sent.span.end()
    attempt = Attempt(
        case_id=sent.case.id,
        family=sent.case.family,
        target_name=target.name,
        index=sent.index,
        transcript=sent.transcript,
        verdict=verdict,
        verdict_class=sent.case.verdict_class,
        started_at=sent.began,
    )
    run_state.record(attempt)
    return attempt


def run_attempt(
    target: TargetConfig,
    case: Case,
    canary: str,
    run_state: RunState,
    index: int,
    adjudicator: Completion | None = None,
) -> Attempt:
    """Send one case to one target, reach a verdict on the reply, record the attempt.

    One attempt, start to finish, on this thread: the verdict is decided in line
    because a single attempt has nothing to overlap with. `run_case` is where a
    judged verdict is taken off the critical path.
    """
    return _score(
        _send(target, case, canary, run_state, index, adjudicator, pool=None),
        target,
        run_state,
    )


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
