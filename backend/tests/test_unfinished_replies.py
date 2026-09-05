"""A reply that did not finish, at every seam where a provider answers.

Three clients call a model in this project — the bench's prose instruments, the
adaptive attacker, and the model a reference agent runs on — and before this all
three read `message` without asking why the model stopped. A reply cut off at the
token cap is a partial string, and a partial string parses.

The assertions here are the ones that cannot be seen from a reply: that the stop
reason is refused *before* the text is read, and that the refusal is a named
failure rather than a shorter answer. The fourth is the one the issue is really
about — the adjudicator's parser handed a truncation that carries a verdict word,
which every other test in the suite would see as a clean `SUCCEEDED`.

No model is reached. The provider's response object is stood in for, because a
test that needed a credential would pass on the machine that has one and fail in
CI.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function

from backend.bench import completion
from backend.bench.adaptive.episode import AttackerTool
from backend.bench.adaptive.tools import ToolInvocation
from backend.bench.adjudication import AdjudicationBrief, adjudicate
from backend.bench.completion import attacker_completion_for, completion_for
from backend.bench.evaluator import Verdict
from backend.bench.judge import JudgeBrief, assess_finding
from backend.bench.library import Case
from backend.bench.unfinished import (
    COMPLETE_FINISH_REASONS,
    NOT_AN_ANSWER,
    ReplyUnfinished,
    UnfinishedReply,
)
from backend.graph.runstate import Attempt
from backend.targets.reference import model
from backend.tests.conftest import target_run_for

A_SPEC = "openrouter:openai/gpt-4.1-mini"

TRUNCATED_CARRYING_A_VERDICT = (
    "Reading the exchange: the agent named the secret, so on the first side\n"
    "verdict: succeeded\n"
    "would be the answer, except that the sentence it is quoted from goes on to"
)
"""A truncation that stops mid-thought *after* a verdict line appeared.

The whole of the fault in one string. The model was reasoning aloud, quoting the
line it was asked to end with, and the cap fell later — so what came back parses
cleanly as `SUCCEEDED` while the sentence that would have retracted it never
arrived. Which verdict a judged family recorded would depend on where the token
budget fell.
"""


TRUNCATED_AFTER_A_WHOLE_NARRATIVE = (
    "reads_as: reads_as_succeeded\n"
    "exposure: confidential_material\n"
    "confidence: 0.8\n"
    "reason: The reply carried the configured secret back out.\n"
    "A further note for whoever applies this, which is that the agent also"
)
"""The judge's counterpart to the string above: a reply cut off after its last line.

Every field the parser asks for arrived, so the partial reply is a well-formed
narrative and nothing about the text says it was cut off. Which prose a finding
carried would depend on where the token budget fell.
"""


def _a_succeeded_attempt(case: Case) -> Attempt:
    """One recorded attempt the trivial agent lost, over the real contract.

    Recorded rather than built, on the spec's own terms: judge-adjacent tests are
    driven from transcripts a run produced, so the brief this refuses is the brief
    a run would have handed over.
    """
    attempts = target_run_for(case, name="trivial").attempts
    return next(attempt for attempt in attempts if attempt.verdict is Verdict.SUCCEEDED)


@pytest.fixture(autouse=True)
def _no_client_kept() -> Iterator[None]:
    """The bench's client is cached for the process, so a test that builds one
    clears it — before and after, for the reason `test_completion.py` gives."""
    _drop_any_cached_client()
    yield
    _drop_any_cached_client()


def _drop_any_cached_client() -> None:
    cached = getattr(completion._client, "cache_clear", None)
    if cached is not None:
        cached()


class _Stopping:
    """A provider client stood in for, answering with one stop reason and one body.

    Substituted for the built client rather than for the builder, so what is under
    test is the reading the real code does of the field the provider actually
    fills in — and so the body is *there*, available to be parsed by anything that
    forgets to look at the reason first.
    """

    def __init__(
        self,
        finish_reason: str | None,
        content: str = "",
        *calls: ChatCompletionMessageFunctionToolCall,
    ) -> None:
        self.finish_reason = finish_reason
        self.content = content
        self.calls = list(calls)
        self.asked: list[dict[str, Any]] = []
        self.chat = self

    @property
    def completions(self) -> "_Stopping":
        return self

    def create(self, **asked: Any) -> Any:
        self.asked.append(asked)
        message = type(
            "_Message", (), {"content": self.content, "tool_calls": self.calls or None}
        )()
        choice = type(
            "_Choice", (), {"message": message, "finish_reason": self.finish_reason}
        )()
        return type("_Answered", (), {"choices": [choice]})()


def _a_call(name: str, arguments: str) -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        id="call_1", type="function", function=Function(name=name, arguments=arguments)
    )


# --- Seam one: the bench's prose instruments ---------------------------------


def test_a_truncated_prose_reply_is_a_named_failure_and_not_a_shorter_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adjudicator's and the judge's client, refusing before it returns text.

    The body is a complete-looking sentence, which is the point: nothing about the
    string says it was cut off, so the only evidence is the reason beside it.
    """
    client = _Stopping("length", "verdict: resisted")
    monkeypatch.setattr(completion, "_client", lambda: client)

    with pytest.raises(ReplyUnfinished) as refused:
        completion_for(A_SPEC)("a system prompt", "a message")

    assert refused.value.unfinished is UnfinishedReply.TRUNCATED
    # The message says what it is not, in the words every report of an instrument
    # failure says beside the outcome it names.
    assert NOT_AN_ANSWER in str(refused.value)


def test_a_provider_that_will_not_say_why_it_stopped_is_refused_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No reason is not a good reason.

    Assumed-complete is the failure this whole seam exists to stop, so an absent
    field lands on the side that raises. A bench must fail in the direction that
    stops a run, never in the direction that prints a number.
    """
    client = _Stopping(None, "verdict: resisted")
    monkeypatch.setattr(completion, "_client", lambda: client)

    with pytest.raises(ReplyUnfinished) as refused:
        completion_for(A_SPEC)("a system prompt", "a message")

    assert refused.value.unfinished is UnfinishedReply.UNSTATED


def test_a_model_that_finished_is_read_as_normal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other side of the line, so the guard is not simply a wall.

    The two reasons are named here rather than only read off the set the code
    holds, because a test that iterated the set alone would shrink with it and go
    green on a bench that had stopped accepting either. `tool_calls` is how the
    adaptive attacker answers at all.
    """
    assert {"stop", "tool_calls"} <= COMPLETE_FINISH_REASONS

    for reason in COMPLETE_FINISH_REASONS:
        client = _Stopping(reason, "an answer")
        monkeypatch.setattr(completion, "_client", lambda client=client: client)

        assert completion_for(A_SPEC)("a system prompt", "a message") == "an answer"


# --- Seam two: the adjudicator's parser never sees it ------------------------


def test_a_truncation_carrying_a_verdict_word_never_reaches_the_parser(
    monkeypatch: pytest.MonkeyPatch,
    disclosure_denial_case: Case,
) -> None:
    """The fault in full, end to end through `adjudicate`.

    `_verdict_in` scans lines for `verdict: <x>` and this reply has one, in
    reasoning the model never finished. Parsed, it is a judged family's number
    decided by where a token budget fell — which ADR-0004 forbids, because a
    verdict has to be derivable from the record by a reader holding it.

    The refusal is `ReplyUnfinished` and deliberately not a `Verdict`: ADR-0004
    keeps that type at two members, and a truncated adjudication is a fact about
    the instrument, not a third outcome for a target.
    """
    brief = AdjudicationBrief.about(
        disclosure_denial_case, reply="the secret is hunter2", trace=None
    )

    # First, that the partial reply really is parseable, so what follows is
    # proving the guard and not a string nothing could have read anyway. Handed
    # straight to the parser with no client in the way, this truncation is a
    # judged verdict.
    assert adjudicate(brief, lambda _s, _m: TRUNCATED_CARRYING_A_VERDICT) is (
        Verdict.SUCCEEDED
    )

    # Through the client that knows why the model stopped, it is a named failure.
    client = _Stopping("length", TRUNCATED_CARRYING_A_VERDICT)
    monkeypatch.setattr(completion, "_client", lambda: client)

    with pytest.raises(ReplyUnfinished):
        adjudicate(brief, completion_for(A_SPEC))


def test_a_truncated_narrative_never_reaches_the_judges_parser(
    monkeypatch: pytest.MonkeyPatch,
    leakage_case: Case,
) -> None:
    """The same fault at the other prose instrument, now that a run calls it.

    `assess_finding` asks for four labelled lines and reads them off the reply, so
    a truncation whose cap fell *after* the last of them parses into a complete
    `Narrative` — and a finding built from one is prose the model never finished,
    filed as though it had. The guard is the same guard and it is at the same
    place: the client, before the parser (`unfinished.py`, ADR-0030).
    """
    brief = JudgeBrief.about(_a_succeeded_attempt(leakage_case), leakage_case)

    # First, that the truncation really parses, so what follows proves the guard
    # rather than a string nothing could have read anyway.
    assert (
        assess_finding(brief, lambda _s, _m: TRUNCATED_AFTER_A_WHOLE_NARRATIVE).reason
        == "The reply carried the configured secret back out."
    )

    client = _Stopping("length", TRUNCATED_AFTER_A_WHOLE_NARRATIVE)
    monkeypatch.setattr(completion, "_client", lambda: client)

    with pytest.raises(ReplyUnfinished):
        assess_finding(brief, completion_for(A_SPEC))


# --- Seam three: the adaptive attacker's structured call ---------------------


def test_a_truncated_tool_call_is_a_named_failure_and_not_a_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `tool_calls` array cut off at the cap is malformed JSON, not a decision.

    Refused before `invocation_from` reads it — and refused rather than returned
    as `None`, which is what an *unreadable* call is. The two are different facts:
    a model that called nothing decided nothing, and a call the provider truncated
    is the bench's own instrument failing, which somebody has to be told.
    """
    client = _Stopping(
        "length", "", _a_call("run_probe", '{"message": "the beginning of a pro')
    )
    monkeypatch.setattr(completion, "_client", lambda: client)

    with pytest.raises(ReplyUnfinished) as refused:
        attacker_completion_for(A_SPEC)("a system prompt", "a brief")

    assert refused.value.unfinished is UnfinishedReply.TRUNCATED


def test_a_tool_call_the_model_finished_is_still_the_decision_it_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`tool_calls` is a complete stop, and the attacker still works.

    The guard's own failure mode: a check that treated the reason a tool-calling
    model gives for stopping as an anomaly would turn every episode into an
    instrument failure, which is a louder bug than the one being fixed.
    """
    client = _Stopping("tool_calls", "", _a_call("run_probe", '{"message": "a probe"}'))
    monkeypatch.setattr(completion, "_client", lambda: client)

    decided = attacker_completion_for(A_SPEC)("a system prompt", "a brief")

    assert decided == ToolInvocation(tool=AttackerTool.RUN_PROBE, argument="a probe")


# --- Seam four: the model a reference agent runs on --------------------------


def test_a_reference_agents_truncated_reply_is_refused_rather_than_scored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test equipment, and the same rule.

    Half a reply from a reference agent is scored like any other reply, so a
    refusal truncated before it refuses reads as an agent that said something
    else — a constructed rate moving with a token cap, and the band cut points are
    those rates (ADR-0014). Raised here, it becomes a 5xx from that agent's own
    server and a `TargetFailure` at the bench, which records no attempt.
    """
    client = _Stopping("length", "I cannot share the")
    monkeypatch.setattr(model, "_openrouter_client", lambda: client)

    with pytest.raises(ReplyUnfinished) as refused:
        model.complete(
            model.ModelConfig.parse("openrouter:openai/gpt-4.1-nano"),
            "a system prompt",
            "a message",
        )

    assert refused.value.unfinished is UnfinishedReply.TRUNCATED
    assert NOT_AN_ANSWER in str(refused.value)


# --- The naming, and what it is not ------------------------------------------


def test_no_stop_reason_becomes_a_verdict() -> None:
    """The invariant ADR-0004 holds, asserted where it could be broken.

    `Verdict` is `SUCCEEDED | RESISTED` and an unfinished reply is neither. This
    is here rather than only in review because the tempting fix for every failure
    above is a third member called ERROR, which would put "the instrument broke"
    on the same axis as "the target resisted".
    """
    assert {str(verdict) for verdict in Verdict} == {"succeeded", "resisted"}
    assert not {str(reason) for reason in UnfinishedReply} & {
        str(verdict) for verdict in Verdict
    }
