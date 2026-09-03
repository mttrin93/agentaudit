"""What the provider said about a call, and where it is allowed to go.

Before this, three clients read one field off a chat-completion response and let
the rest fall on the floor: the model that actually served the request, the tokens
in and out, the reasoning tokens, the provider's own cost, the stop reason and the
generation id. A run could not say what it had consumed in any unit.

Four things are asserted here that cannot be seen from a reply.

* **Every one of the nine facts arrives**, off a response built from the SDK's own
  types with OpenRouter's `cost` on the usage block, which is the shape the wire
  actually carries.
* **Every absence is a sentence and never a zero.** A model that reports no
  reasoning tokens and a model that reasoned for none are different facts, and a
  `0` here would be a figure the bench invented and then signed
  (`usage.NO_REASONING_TOKENS_REPORTED`, `budget.NOT_PRICED`'s own reasoning).
* **Nothing an instrument decides from can see it.** `Completion` is still
  `(system_prompt, message) -> str`: a judge that could read a cost is a judge
  whose verdict is not derivable from the record a reader holds (ADR-0004).
* **The two layers are counted apart and nothing adds them.** ADR-0010's
  invariant, in the shape `RunState.spent` already holds it in.

No model is reached. The provider's response objects are stood in for, because a
test that needed a credential would pass on the machine that has one and fail in
CI — and a test that spent real credit to read a token count would be the bench
billing its own author for its own arithmetic.
"""

import ast
import inspect
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionTokensDetails

from backend.bench import completion
from backend.bench.completion import (
    attacker_completion_for,
    completion_for,
    narrator_for,
)
from backend.bench.unfinished import ReplyUnfinished
from backend.bench.usage import (
    DISCARDED,
    LAYER_IS_NOT_A_TARGETS_FACT,
    NO_COST_REPORTED,
    NO_REASONING_TOKENS_REPORTED,
    NO_REQUEST_ID_REPORTED,
    NO_RETURNED_MODEL_REPORTED,
    NO_TOKEN_COUNTS_REPORTED,
    ModelUsage,
    UsageFact,
    UsageLedger,
    usage_from,
)
from backend.graph.budget import Layer
from backend.targets.reference import model
from backend.targets.reference.model import ModelConfig

A_SPEC = "openrouter:openai/gpt-4.1-mini"
A_MODEL = "openai/gpt-4.1-mini"


@pytest.fixture(autouse=True)
def _no_client_kept() -> Iterator[None]:
    """The bench's client is cached for the process, so a test that builds one
    clears it — before and after, for the reason `test_completion.py` gives."""
    _drop_any_cached_client()
    yield
    _drop_any_cached_client()


def _drop_any_cached_client() -> None:
    for cached in (completion._client, model._openrouter_client):
        clear = getattr(cached, "cache_clear", None)
        if clear is not None:
            clear()


def _answered(
    *,
    served_by: str = A_MODEL,
    request_id: str = "gen-1a2b3c",
    finish_reason: Any = "stop",
    usage: CompletionUsage | None = None,
    content: str = "verdict: resisted",
) -> ChatCompletion:
    """One provider response in the SDK's own types.

    Built from the real classes rather than from duck types, because what is under
    test is the reading of the object the provider returns: the `usage` block hangs
    off the response and not off the choice, the reasoning tokens hang off the
    completion-token details and not off `usage`, and a stand-in that flattened any
    of that would assert the reading of a response nothing sends.
    """
    return ChatCompletion(
        id=request_id,
        created=1,
        model=served_by,
        object="chat.completion",
        choices=[
            Choice(
                finish_reason=finish_reason,
                index=0,
                message=ChatCompletionMessage(role="assistant", content=content),
            )
        ],
        usage=usage,
    )


def _reported(
    *,
    prompt_tokens: int = 214,
    completion_tokens: int = 37,
    reasoning_tokens: int | None = 24,
    cost: float | None = 0.00041,
) -> CompletionUsage:
    """A usage block as OpenRouter fills one in.

    `cost` is an extra field on the SDK's own model, which is exactly how it
    arrives: the SDK does not declare it, the router adds it when the request asks
    for it, and the pydantic model carries it through.
    """
    details = (
        None
        if reasoning_tokens is None
        else CompletionTokensDetails(reasoning_tokens=reasoning_tokens)
    )
    block = CompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        completion_tokens_details=details,
    )
    if cost is not None:
        block.cost = cost  # type: ignore[attr-defined]
    return block


class _Answering:
    """A provider client stood in for, answering with one prepared response."""

    def __init__(self, answered: ChatCompletion) -> None:
        self.answered = answered
        self.asked: list[dict[str, Any]] = []
        self.chat = self

    @property
    def completions(self) -> "_Answering":
        return self

    def create(self, **asked: Any) -> ChatCompletion:
        self.asked.append(asked)
        return self.answered


# --- What the response carries -----------------------------------------------


def test_every_fact_the_provider_returned_is_read_off_the_response() -> None:
    """The nine facts, from one response. This is the whole of the issue."""
    read = usage_from(
        _answered(served_by="openai/gpt-4.1-mini-2025-04-14", usage=_reported()),
        requested_model=A_MODEL,
        latency_seconds=1.25,
    )

    assert read.requested_model == A_MODEL
    assert read.returned_model == "openai/gpt-4.1-mini-2025-04-14"
    assert read.input_tokens == 214
    assert read.output_tokens == 37
    assert read.reasoning_tokens == 24
    assert read.provider_cost == Decimal("0.00041")
    assert read.latency_seconds == 1.25
    assert read.finish_reason == "stop"
    assert read.request_id == "gen-1a2b3c"


def test_a_router_that_served_something_else_is_visible_as_two_facts() -> None:
    """Returned model is not requested model, which is why both are recorded.

    A router may serve a different variant than the one asked for, and a record
    that kept only one of the two could not say so.
    """
    read = usage_from(
        _answered(served_by="openai/gpt-4.1-mini-2025-04-14", usage=_reported()),
        requested_model=A_MODEL,
        latency_seconds=0.1,
    )

    assert read.served_a_different_model()
    assert not usage_from(
        _answered(served_by=A_MODEL, usage=_reported()),
        requested_model=A_MODEL,
        latency_seconds=0.1,
    ).served_a_different_model()


def test_the_cost_is_the_decimal_the_provider_named_and_not_a_binary_expansion() -> (
    None
):
    """A money figure read through `str` rather than through `float`.

    `Decimal(0.00041)` is the binary expansion of a number the provider stated in
    decimal. A cost this bench records has to be the cost the provider named.
    """
    read = usage_from(
        _answered(usage=_reported(cost=0.00041)),
        requested_model=A_MODEL,
        latency_seconds=0.1,
    )

    assert str(read.provider_cost) == "0.00041"


# --- What the response does not carry ----------------------------------------


def test_a_provider_that_reported_nothing_gets_absent_fields_and_never_zero() -> None:
    """No `usage` block at all: four absences, and none of them a figure.

    A `0` here would be the bench asserting that a call consumed nothing, which is
    a different fact from a call whose consumption is unknown — `NOT_PRICED`'s own
    reasoning, one layer down.
    """
    read = usage_from(
        _answered(usage=None), requested_model=A_MODEL, latency_seconds=0.1
    )

    assert read.input_tokens is None
    assert read.output_tokens is None
    assert read.reasoning_tokens is None
    assert read.provider_cost is None


def test_a_model_that_does_not_reason_reports_no_reasoning_tokens() -> None:
    """Absent, not zero — the pair `capability` keeps apart on the input side.

    A chat model has no such number; a reasoning model that returned `0` had one
    and it was zero. A blank cannot say which of the two a reader is looking at.
    """
    absent = usage_from(
        _answered(usage=_reported(reasoning_tokens=None)),
        requested_model=A_MODEL,
        latency_seconds=0.1,
    )
    thought_for_none = usage_from(
        _answered(usage=_reported(reasoning_tokens=0)),
        requested_model=A_MODEL,
        latency_seconds=0.1,
    )

    assert absent.reasoning_tokens is None
    assert absent.stated()[UsageFact.REASONING_TOKENS] == NO_REASONING_TOKENS_REPORTED
    assert thought_for_none.reasoning_tokens == 0
    assert thought_for_none.stated()[UsageFact.REASONING_TOKENS] == "0"


def test_a_provider_that_ignored_the_cost_flag_reports_no_cost() -> None:
    """No cost is unknown cost, and it is not free and not the declared price."""
    read = usage_from(
        _answered(usage=_reported(cost=None)),
        requested_model=A_MODEL,
        latency_seconds=0.1,
    )

    assert read.provider_cost is None
    assert read.stated()[UsageFact.PROVIDER_COST] == NO_COST_REPORTED


def test_every_absence_is_a_stated_sentence_and_no_fact_is_ever_blank() -> None:
    """One entry per fact, always, and a sentence wherever there is no figure.

    The precedent `capability.NO_TEMPERATURE_ACCEPTED` set: a reader cannot recover
    which absence they are looking at from an empty cell, so there are no empty
    cells to look at.
    """
    read = ModelUsage(requested_model=A_MODEL, latency_seconds=0.5)
    stated = read.stated()

    assert set(stated) == set(UsageFact)
    assert all(said.strip() for said in stated.values())
    assert stated[UsageFact.RETURNED_MODEL] == NO_RETURNED_MODEL_REPORTED
    assert stated[UsageFact.INPUT_TOKENS] == NO_TOKEN_COUNTS_REPORTED
    assert stated[UsageFact.OUTPUT_TOKENS] == NO_TOKEN_COUNTS_REPORTED
    assert stated[UsageFact.REASONING_TOKENS] == NO_REASONING_TOKENS_REPORTED
    assert stated[UsageFact.PROVIDER_COST] == NO_COST_REPORTED
    assert stated[UsageFact.REQUEST_ID] == NO_REQUEST_ID_REPORTED


# --- The layers, kept apart ---------------------------------------------------


def test_usage_is_counted_per_layer_and_nothing_sums_the_two() -> None:
    """ADR-0010, in the shape `RunState.spent` already holds it in.

    The two totals are readable one layer at a time and there is no method that
    adds them: a caller that wants a blended figure has to write the sum itself,
    in the open, where a reviewer sees it.
    """
    ledger = UsageLedger()
    ledger.for_layer(Layer.SCORED).record(
        ModelUsage(requested_model=A_MODEL, latency_seconds=0.1, output_tokens=10)
    )
    ledger.for_layer(Layer.ADAPTIVE).record(
        ModelUsage(requested_model=A_MODEL, latency_seconds=0.1, output_tokens=400)
    )

    assert ledger.totals_in(Layer.SCORED).output_tokens == 10
    assert ledger.totals_in(Layer.ADAPTIVE).output_tokens == 400
    assert not hasattr(ledger, "totals")
    assert not hasattr(ledger, "record")


def test_a_call_made_behind_the_target_contract_belongs_to_neither_layer() -> None:
    """Which layer asked for a target's turn is not a fact the target holds.

    The bench knows nothing about a target beyond `{reply, tool_trace}`, so
    threading the layer through the contract to tag this would put a
    bench-internal fact on the wire to somebody's endpoint. Untagged is the honest
    tag, and it is summed into neither layer.
    """
    ledger = UsageLedger()
    ledger.behind_the_contract().record(
        ModelUsage(requested_model=A_MODEL, latency_seconds=0.1, output_tokens=9)
    )

    assert [call.output_tokens for call in ledger.untagged()] == [9]
    assert ledger.untagged()[0].layer is None
    assert ledger.untagged()[0].stated_layer() == LAYER_IS_NOT_A_TARGETS_FACT
    for layer in Layer:
        assert ledger.totals_in(layer).calls == 0
        assert ledger.totals_in(layer).output_tokens is None


def test_a_layer_total_says_how_many_of_its_calls_reported_anything() -> None:
    """A sum over calls where some providers reported nothing understates a layer.

    So the count travels with the sum. A reader who cannot see how many calls
    contributed cannot tell an understatement from a fact.
    """
    ledger = UsageLedger()
    scored = ledger.for_layer(Layer.SCORED)
    scored.record(
        ModelUsage(
            requested_model=A_MODEL,
            latency_seconds=0.1,
            input_tokens=100,
            provider_cost=Decimal("0.001"),
        )
    )
    scored.record(ModelUsage(requested_model=A_MODEL, latency_seconds=0.1))

    totals = ledger.totals_in(Layer.SCORED)

    assert totals.calls == 2
    assert totals.input_tokens == 100
    assert totals.calls_reporting_tokens == 1
    assert not totals.every_call_reported_tokens()
    assert totals.provider_cost == Decimal("0.001")
    assert not totals.every_call_reported_cost()


# --- The seam: beside the answer, never inside the decision -------------------


def test_the_instrument_signature_does_not_widen_to_carry_usage() -> None:
    """ADR-0004: a judge that could see a cost is a judge nobody can re-derive.

    The record goes to a sink the caller bound. What the instrument is handed is
    still a system prompt and a message, and it still answers with a string.
    """
    client = _Answering(_answered(usage=_reported()))
    ledger = UsageLedger()

    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(completion, "_client", lambda: client)
        built = completion_for(A_SPEC, usage=ledger.for_layer(Layer.SCORED))
        answer = built("a system prompt", "a message")

    assert list(inspect.signature(built).parameters) == ["system_prompt", "message"]
    assert answer == "verdict: resisted"
    assert ledger.totals_in(Layer.SCORED).calls == 1


def test_no_instrument_that_decides_can_reach_a_usage_figure_at_all() -> None:
    """ADR-0004 closes this by construction, and an import is a construction.

    The two modules that produce a scored output — the adjudicator that decides a
    judged family and the narrative judge that writes about one — must not be able
    to name a token count or a cost. A verdict a reader cannot re-derive from the
    record they hold is the crack this ADR exists to close, and a bill is not part
    of that record. `test_judge.py` makes the same assertion about precedent and
    the adaptive layer, in the same shape.
    """
    deciding = Path(__file__).parent.parent / "bench"
    for instrument in ("adjudication.py", "judge.py"):
        forbidden = [
            name
            for name in _imports_of(deciding / instrument)
            if "usage" in name.lower()
        ]
        assert not forbidden, (
            f"{forbidden} is reachable from {instrument}. An instrument that can "
            "see what a call cost is an instrument whose verdict is no longer "
            "derivable from the record a reader holds (ADR-0004)"
        )


def _imports_of(source: Path) -> Iterator[str]:
    """Every module and name the given module imports, dotted."""
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)


def test_the_benchs_own_instrument_records_what_its_call_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adjudicator's and the judge's client, writing to the sink it was built
    with."""
    client = _Answering(
        _answered(served_by="openai/gpt-4.1-mini-2025-04-14", usage=_reported())
    )
    monkeypatch.setattr(completion, "_client", lambda: client)
    ledger = UsageLedger()

    completion_for(A_SPEC, usage=ledger.for_layer(Layer.SCORED))(
        "a system prompt", "a message"
    )

    (recorded,) = ledger.recorded_in(Layer.SCORED)
    assert recorded.layer is Layer.SCORED
    assert recorded.requested_model == A_MODEL
    assert recorded.returned_model == "openai/gpt-4.1-mini-2025-04-14"
    assert recorded.request_id == "gen-1a2b3c"
    assert recorded.latency_seconds >= 0.0


def test_both_narrative_instruments_report_into_the_layer_the_caller_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`narrator_for` builds two clients, and one sink counts them both.

    The builder three entry points reach for (ADR-0030), asserted here rather than
    at each of them: two clients rather than one used twice, because the two
    instruments are declared apart and may be pointed at separate models — and
    both report into the sink the caller bound, which is the scored layer's,
    because a narrative counted into the adaptive bucket would be a scored figure
    inside an adaptive one (ADR-0010).
    """
    client = _Answering(_answered(usage=_reported()))
    monkeypatch.setattr(completion, "_client", lambda: client)
    ledger = UsageLedger()

    narrator = narrator_for(A_SPEC, ledger.for_layer(Layer.SCORED))
    assert narrator.assess is not narrator.remediate
    narrator.assess("the judge's prompt", "a blinded brief")
    narrator.remediate("the remediation prompt", "a finding")

    assert ledger.totals_in(Layer.SCORED).calls == 2
    assert ledger.totals_in(Layer.ADAPTIVE).calls == 0
    assert not ledger.untagged()


def test_the_attackers_tokens_are_recorded_in_the_adaptive_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An attacker's spend counted into the scored layer would be an adaptive
    figure inside a scored one, which ADR-0010 forbids."""
    client = _Answering(_answered(finish_reason="tool_calls", usage=_reported()))
    monkeypatch.setattr(completion, "_client", lambda: client)
    ledger = UsageLedger()

    attacker_completion_for(A_SPEC, usage=ledger.for_layer(Layer.ADAPTIVE))(
        "a system prompt", "a brief"
    )

    assert ledger.totals_in(Layer.ADAPTIVE).calls == 1
    assert ledger.totals_in(Layer.SCORED).calls == 0
    assert ledger.recorded_in(Layer.ADAPTIVE)[0].finish_reason == "tool_calls"


def test_a_reference_agents_model_records_beside_the_string_it_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other seam. The reply contract is unchanged: a string comes back, and
    nothing about a token count goes onto the wire to the bench (ADR-0026)."""
    client = _Answering(_answered(content="I cannot help with that", usage=_reported()))
    monkeypatch.setattr(model, "_openrouter_client", lambda: client)
    ledger = UsageLedger()

    said = model.complete(
        ModelConfig.parse("openrouter:openai/gpt-4.1-nano"),
        "a system prompt",
        "a message",
        usage=ledger.behind_the_contract(),
    )

    assert said == "I cannot help with that"
    assert [call.input_tokens for call in ledger.untagged()] == [214]


def test_the_stub_provider_reports_no_usage_and_none_is_invented() -> None:
    """A deterministic stand-in has no provider, so it has no figures.

    Inventing some would put a measurement of the field's cost behind a model
    `measures_the_field` already answers `False` for (ADR-0022).
    """
    ledger = UsageLedger()

    model.complete(
        ModelConfig.parse("stub:obedient"),
        "a system prompt",
        "a message",
        usage=ledger.behind_the_contract(),
    )

    assert ledger.untagged() == ()


# --- What the request has to ask for -----------------------------------------


def test_the_request_asks_the_router_for_its_own_cost_figure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter returns a cost only when the request asks for one.

    Asked for on every call rather than configurably: a run that recorded a cost
    for some of its calls and not others would print a total nobody could read.
    """
    client = _Answering(_answered(usage=_reported()))
    monkeypatch.setattr(completion, "_client", lambda: client)

    completion_for(A_SPEC, usage=DISCARDED)("a system prompt", "a message")
    attacker_completion_for(A_SPEC, usage=DISCARDED)("a system prompt", "a brief")

    for asked in client.asked:
        assert asked["extra_body"] == {"usage": {"include": True}}


def test_a_reply_that_did_not_finish_is_recorded_before_it_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated call cost the operator its tokens all the same.

    And the one call whose finish reason a reader most wants to see is the one that
    did not finish. Nothing about this is an `Attempt`: `refuse_unfinished` still
    raises, and no numerator or denominator moves (`unfinished.NOT_AN_ANSWER`).
    """
    client = _Answering(_answered(finish_reason="length", usage=_reported()))
    monkeypatch.setattr(completion, "_client", lambda: client)
    ledger = UsageLedger()

    with pytest.raises(ReplyUnfinished):
        completion_for(A_SPEC, usage=ledger.for_layer(Layer.SCORED))(
            "a system prompt", "a message"
        )

    (recorded,) = ledger.recorded_in(Layer.SCORED)
    assert recorded.finish_reason == "length"
    assert recorded.output_tokens == 37
