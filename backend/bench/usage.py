"""What the provider said about the call, kept instead of dropped.

Every model call in this project came back carrying more than words. The response
object names the model that actually served the request, the tokens in and out, the
reasoning tokens on a model that reasons, the provider's own cost figure, the stop
reason and the generation id — and until this module the wrapper read one field off
it and let the rest fall on the floor. A run could not say what it had consumed, in
any unit, and the trace ADR-0026 shipped had no figure to carry because the only
place a figure could have come from was the sink itself.

**A record beside the answer, never an argument to the thing that decides.**
`adjudication.Completion` is `(system_prompt, message) -> str` and
`AttackerCompletion` returns a `ToolInvocation | None`, and both stay exactly that.
ADR-0004 fixes what an instrument may be given: a judge that could see a token count
or a cost is a judge whose verdict is no longer derivable from the record a reader
holds, because the reader does not hold the bill. So the usage goes to a `UsageSink`
the wrapper was built with, on the side, and no instrument signature widens.

**Counted per layer, and nothing sums the two.** ADR-0010 keeps the adaptive layer
off every scored figure, and `RunState.spent` already counts calls per layer for
that reason. Tokens are the same kind of number, so `UsageLedger` buckets by
`Layer` and offers `totals_in(layer)` and no `totals()` — there is deliberately no
method here that adds the scored layer's tokens to the adaptive layer's, because a
blended figure is the one shape ADR-0010 forbids and an absent method is the only
kind of absence a caller cannot work around by accident.

**Absent rather than zero, with a sentence for each absence.** A provider that
reported no cost and a call that was free are different facts, which is
`budget.NOT_PRICED`'s own reasoning; a provider that reports no reasoning tokens and
a model that reasoned for none are two more. So every fact is `None` when nothing
was reported, and `ModelUsage.stated()` prints a *sentence* for each absence rather
than a blank — the precedent `capability.NO_TEMPERATURE_ACCEPTED` set, for the same
reason. A `0` here would be a figure the bench invented and then signed.

**The provider's cost is a third kind of money and never the consent figure.**
`graph/budget.py` holds that money is declared, never guessed, and a run with no
declared price reads `not priced`. What arrives here is neither: it is what was
actually spent, after the fact, in the provider's own accounting for the bench's own
instrument calls — not for the operator's endpoint, which is what the estimate is
about. It may not become the authority for the consent estimate, may not overwrite
`not priced`, and may not be shown beside the `≤` figures as though it were one of
them. Nothing in this module imports `CallPrice` or `RunBudget`, and that is the
whole of the enforcement.

**This is not the finish-reason check.** `unfinished.refuse_unfinished` reads the
stop reason to decide whether there is an answer at all, before a parser sees the
text; this module *records* the same field as one of the nine facts. A truncated
reply still cost the operator its tokens, so the record is written before the
refusal is raised — the one call whose finish reason a reader most wants to see is
the one that did not finish.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from backend.graph.budget import Layer

NO_RETURNED_MODEL_REPORTED = (
    "the provider did not name the model that served this call, so what ran is "
    "known only as what was asked for. Not the same statement as the router "
    "serving what it was asked: unnamed is unknown, not confirmed"
)
"""What a record says when the response carried no model name.

Said rather than filled in from the request, because *returned model is not
requested model* is the reason both facts are on the list: a router may serve a
different variant than the one asked for, and copying the request into the answer
would be the bench manufacturing the agreement it was trying to check.
"""

NO_TOKEN_COUNTS_REPORTED = (
    "the provider reported no token counts for this call, so how much was read and "
    "written is unknown. Not the same statement as a call that consumed nothing"
)
"""What a record says when the response carried no `usage` block at all."""

NO_REASONING_TOKENS_REPORTED = (
    "the provider reported no reasoning tokens for this call, which is what a model "
    "that does not reason reports. Not the same statement as a reasoning model that "
    "thought for zero tokens"
)
"""What a record says about a model that reported no reasoning tokens.

Two facts under one blank, which is why the blank is not allowed: a chat model has
no such number, and a reasoning model that returned the figure `0` had one and it
was zero. `capability.NO_REASONING_EFFORT_ACCEPTED` keeps the same pair apart on the
declared-input side (#5), and this is its reported-output counterpart.
"""

NO_COST_REPORTED = (
    "the provider reported no cost for this call, so what it cost is unknown. Not "
    "the same statement as a call that was free, and not the run's declared price"
)
"""What a record says when no cost came back.

`budget.NOT_PRICED`'s sentence, one layer down and about a different figure: the
consent estimate is priced from what the operator declared, and this is what a
provider says it charged the bench. Both refuse to print a zero for an unknown.
"""

NO_REQUEST_ID_REPORTED = (
    "the provider returned no generation id for this call, so there is nothing to "
    "search a provider dashboard by"
)
"""What a record says when the response carried no `id`."""

NO_FINISH_REASON_REPORTED = (
    "the provider did not say why this reply ended, which is what "
    "unfinished.UnfinishedReply.UNSTATED refuses rather than reads as complete"
)
"""What a record says when the response carried no stop reason.

The same absence `unfinished` refuses on, recorded rather than re-decided: this
module reports what came back and never rules on whether the reply is usable.
"""

LAYER_IS_NOT_A_TARGETS_FACT = (
    "no layer — this call was made behind the target contract, where which layer of "
    "the bench caused it is not a fact the caller holds. Counted with the target's "
    "own calls and summed into neither layer"
)
"""What a record says when it carries no layer.

A reference agent's model calls are the one kind this module keeps untagged, and
the reason is the contract: the bench knows nothing about a target beyond
`{reply, tool_trace}` (`bench/contract.py`), so the agent serving a turn cannot
know whether a scored attempt or an adaptive probe asked for it. Threading the
layer through the contract to find out would put a bench-internal fact on the wire
to a target, which is the one thing the contract's narrowness exists to prevent.

Untagged is therefore the honest tag, and `UsageLedger.totals_in` never counts
these — an untagged call may not be added to either layer, on ADR-0010's own terms.
"""


ASK_FOR_COST: dict[str, dict[str, bool]] = {"usage": {"include": True}}
"""The request body that makes the router report what the call cost.

OpenRouter returns its own cost figure only when the request asks for it. The
answer arrives inside the same response — no second upstream call — and adds `cost`
and the token-detail objects to the `usage` block without changing anything else
about the shape.

One constant and two importers (`bench/completion.py`, `targets/reference/model.py`)
rather than a literal at each call site, for the reason `capability` keeps its
sentences in one place: a bench that asked for a cost on some of its calls and not
others would print a total nobody could read.
"""


class UsageFact(StrEnum):
    """The nine facts a model call reports, as a closed set.

    Closed and named so that `stated()` returns one entry per fact and a reader can
    tell a fact that was not reported from a fact nobody asked for. It is also the
    surface a trace consumes: ADR-0026's `Field` is an allowlist, and a figure that
    reaches a span reaches it as one of these.
    """

    REQUESTED_MODEL = "requested_model"
    RETURNED_MODEL = "returned_model"
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    REASONING_TOKENS = "reasoning_tokens"
    PROVIDER_COST = "provider_cost"
    LATENCY_SECONDS = "latency_seconds"
    FINISH_REASON = "finish_reason"
    REQUEST_ID = "request_id"


@dataclass(frozen=True)
class ModelUsage:
    """One model call as the provider described it, and which layer asked for it.

    Frozen, because it is a record of something that already happened. The two
    facts that are never absent are the ones this process holds itself: what was
    asked for, and how long the wait was. Everything else is the provider's to
    report or not.
    """

    requested_model: str
    """The model identifier the request carried — this process's own fact."""

    latency_seconds: float
    """How long the call took, wall clock, measured around the send.

    Measured here rather than read off the response, because no provider reports
    it and the figure a run cares about is the one its own operator waited.
    """

    returned_model: str | None = None
    output_tokens: int | None = None
    input_tokens: int | None = None
    reasoning_tokens: int | None = None
    provider_cost: Decimal | None = None
    finish_reason: str | None = None
    request_id: str | None = None

    layer: Layer | None = None
    """Which half of the run this call belongs to, or `None` for a call made behind
    the target contract (`LAYER_IS_NOT_A_TARGETS_FACT`)."""

    currency: str = "USD"
    """What `provider_cost` is denominated in. OpenRouter accounts in US dollars."""

    def served_a_different_model(self) -> bool:
        """Whether the router served something other than what was asked for.

        `False` when nothing was returned to compare: an unnamed model is not a
        model that matched, and the record says so in `stated()` rather than here.
        """
        return self.returned_model is not None and (
            self.returned_model != self.requested_model
        )

    def stated_layer(self) -> str:
        """Which layer asked for this call, or the sentence for having no layer.

        Separate from `stated()` because a layer is not one of the nine facts the
        *provider* reports — it is the bench's own fact about why the call
        happened, and the one record that has none is the one made behind the
        target contract.
        """
        return LAYER_IS_NOT_A_TARGETS_FACT if self.layer is None else self.layer.value

    def stated(self) -> dict[UsageFact, str]:
        """Every fact as a reader sees it: a figure, or a sentence saying why not.

        One entry per member of `UsageFact`, always, so a consumer that renders
        this cannot produce a blank cell. The sentences are the module's constants
        rather than phrases composed here, for the reason `capability` keeps its
        own: two copies of a load-bearing statement are two statements that drift.
        """
        return {
            UsageFact.REQUESTED_MODEL: self.requested_model,
            UsageFact.RETURNED_MODEL: (
                NO_RETURNED_MODEL_REPORTED
                if self.returned_model is None
                else self.returned_model
            ),
            UsageFact.INPUT_TOKENS: (
                NO_TOKEN_COUNTS_REPORTED
                if self.input_tokens is None
                else str(self.input_tokens)
            ),
            UsageFact.OUTPUT_TOKENS: (
                NO_TOKEN_COUNTS_REPORTED
                if self.output_tokens is None
                else str(self.output_tokens)
            ),
            UsageFact.REASONING_TOKENS: (
                NO_REASONING_TOKENS_REPORTED
                if self.reasoning_tokens is None
                else str(self.reasoning_tokens)
            ),
            UsageFact.PROVIDER_COST: (
                NO_COST_REPORTED
                if self.provider_cost is None
                else f"{self.provider_cost} {self.currency}"
            ),
            UsageFact.LATENCY_SECONDS: f"{self.latency_seconds:.3f}",
            UsageFact.FINISH_REASON: (
                NO_FINISH_REASON_REPORTED
                if self.finish_reason is None
                else self.finish_reason
            ),
            UsageFact.REQUEST_ID: (
                NO_REQUEST_ID_REPORTED if self.request_id is None else self.request_id
            ),
        }


@dataclass(frozen=True)
class LayerTotals:
    """What one layer of a run consumed, and how much of it was reported.

    The counts beside the figures are the point. A total summed over calls where
    some providers reported nothing understates the layer, and a reader who cannot
    see how many calls contributed cannot tell an understatement from a fact — so
    `calls_reporting_tokens` and `calls_reporting_cost` travel with the sums, and a
    layer where nothing was reported gets `None` rather than `0`.
    """

    layer: Layer
    calls: int
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    provider_cost: Decimal | None
    calls_reporting_tokens: int
    calls_reporting_reasoning_tokens: int
    calls_reporting_cost: int

    def every_call_reported_tokens(self) -> bool:
        """Whether the token total covers every call in the layer."""
        return self.calls == self.calls_reporting_tokens

    def every_call_reported_cost(self) -> bool:
        """Whether the cost total covers every call in the layer."""
        return self.calls == self.calls_reporting_cost


class UsageSink(Protocol):
    """Where a wrapper puts what the provider said.

    A protocol rather than a class, so the seam is a one-method obligation and a
    caller that keeps no record says so by name (`DISCARDED`) instead of passing
    `None` and leaving a reader to guess whether a sink was forgotten.
    """

    def record(self, usage: ModelUsage) -> None: ...


class _Discarding:
    """A sink that keeps nothing, and is named so that keeping nothing is a choice.

    A script measuring inter-rater reliability is not a run and has no ledger to
    hand a record to; the honest reading of that is *this caller keeps no usage*,
    stated in its signature's default, rather than an optional sink whose absence
    could equally mean somebody forgot one.
    """

    def record(self, usage: ModelUsage) -> None:
        return None


DISCARDED: UsageSink = _Discarding()
"""The sink for a caller that keeps no usage record. Never a run's sink."""


class UsageLedger:
    """Every model call a run made, bucketed by layer, with no blended total.

    Mutable on purpose — it is a run's accumulating record, the way
    `RunState.spent` is — and it is the one sink a run installs.

    **The ledger is not itself a sink.** A wrapper is handed a sink bound to a
    layer, by `for_layer` or by `behind_the_contract`, and it is the *caller* that
    picks which — because the caller is what knows whether the instrument it is
    building serves the scored half of a run or the adaptive one, and the wrapper
    reading a provider response does not. So there is no `record` here for a
    builder to be handed by mistake and no path by which a call lands in a bucket
    nobody named (ADR-0010).

    **There is no `totals()`.** Adding the adaptive layer's tokens to the scored
    layer's is the shape ADR-0010 forbids, and the enforcement is that the method
    does not exist: a caller that wants a blended figure has to write the sum
    itself, in the open, where a reviewer sees it.
    """

    def __init__(self) -> None:
        self._recorded: dict[Layer | None, list[ModelUsage]] = {
            **{layer: [] for layer in Layer},
            None: [],
        }

    def for_layer(self, layer: Layer) -> UsageSink:
        """The sink an instrument serving that layer is built with."""
        return _Stamping(self, layer)

    def behind_the_contract(self) -> UsageSink:
        """The sink for a model call made behind the target contract.

        Its records carry no layer, for the reason `LAYER_IS_NOT_A_TARGETS_FACT`
        states, and `totals_in` never counts them.
        """
        return _Stamping(self, None)

    def _append(self, usage: ModelUsage) -> None:
        """Where a bound sink puts an already-tagged record."""
        self._recorded[usage.layer].append(usage)

    def recorded_in(self, layer: Layer) -> Sequence[ModelUsage]:
        """Every call that layer made, in the order it made them."""
        return tuple(self._recorded[layer])

    def untagged(self) -> Sequence[ModelUsage]:
        """Every call made behind the target contract, which belongs to no layer."""
        return tuple(self._recorded[None])

    def totals_in(self, layer: Layer) -> LayerTotals:
        """What that layer consumed, over the calls that reported anything.

        One layer at a time, and there is no argument for *both*: see the class
        docstring. An empty layer reads zero calls and `None` figures, because a
        layer that made no call reported no tokens rather than zero tokens.
        """
        calls = self._recorded[layer]
        return LayerTotals(
            layer=layer,
            calls=len(calls),
            input_tokens=_summed(call.input_tokens for call in calls),
            output_tokens=_summed(call.output_tokens for call in calls),
            reasoning_tokens=_summed(call.reasoning_tokens for call in calls),
            provider_cost=_summed_cost(call.provider_cost for call in calls),
            calls_reporting_tokens=sum(
                1
                for call in calls
                if call.input_tokens is not None or call.output_tokens is not None
            ),
            calls_reporting_reasoning_tokens=sum(
                1 for call in calls if call.reasoning_tokens is not None
            ),
            calls_reporting_cost=sum(
                1 for call in calls if call.provider_cost is not None
            ),
        )


class _Stamping:
    """A sink that writes one layer's tag onto every record it forwards.

    The wrapper builds a record of what the provider said and knows nothing about
    which half of a run asked for it; this is where that fact is added, once, by
    the object the caller chose. `replace` rather than mutation because
    `ModelUsage` is frozen — a record of something that already happened.
    """

    def __init__(self, ledger: "UsageLedger", layer: Layer | None) -> None:
        self._ledger = ledger
        self._layer = layer

    def record(self, usage: ModelUsage) -> None:
        self._ledger._append(replace(usage, layer=self._layer))


def _summed(figures: Iterable[int | None]) -> int | None:
    """The sum of the figures that were reported, or `None` if none were.

    `None` rather than `0` for the module's own reason: a set of calls that
    reported no counts did not consume nothing, and a zero here would be the total
    a reader is least able to question.
    """
    reported = [figure for figure in figures if figure is not None]
    return sum(reported) if reported else None


def _summed_cost(figures: Iterable[Decimal | None]) -> Decimal | None:
    """`_summed` for money, which does not go through `int`."""
    reported = [figure for figure in figures if figure is not None]
    return sum(reported, Decimal(0)) if reported else None


def usage_from(
    answered: object,
    requested_model: str,
    latency_seconds: float,
    layer: Layer | None = None,
) -> ModelUsage:
    """One `ModelUsage` read off a chat-completion response.

    **Every field is read defensively and an unreadable one is absent.** The SDK's
    own types do not declare OpenRouter's `cost`, providers behind the router differ
    in which details they fill in, and a reader that assumed a field would trade a
    missing figure for an exception in the middle of a run — which would turn a
    reporting gap into a stopped suite. The type is `object` for the same reason:
    what arrives is whatever the provider serialised, and the isinstance checks
    below are the only thing this module trusts about it.

    **`usage: {include: true}` is what makes the cost field arrive at all.** It is
    asked for in the request (`backend/bench/completion.py`), it comes back in the
    same response, and it costs no second upstream call — it adds `cost` and the
    token-detail objects to the `usage` block and changes nothing else about the
    shape. A provider that ignores the flag reports no cost, which is
    `NO_COST_REPORTED` and not a zero.
    """
    reported = getattr(answered, "usage", None)
    details = getattr(reported, "completion_tokens_details", None)
    return ModelUsage(
        requested_model=requested_model,
        latency_seconds=latency_seconds,
        returned_model=_reported_str(answered, "model"),
        input_tokens=_reported_int(reported, "prompt_tokens"),
        output_tokens=_reported_int(reported, "completion_tokens"),
        reasoning_tokens=_reported_int(details, "reasoning_tokens"),
        provider_cost=_reported_decimal(reported, "cost"),
        finish_reason=_first_finish_reason(answered),
        request_id=_reported_str(answered, "id"),
        layer=layer,
    )


def _first_finish_reason(answered: object) -> str | None:
    """The stop reason of the first choice, or `None` if there is nothing to read.

    Read here as a *fact to record* and nowhere ruled on: whether it means the
    reply is usable is `unfinished.refuse_unfinished`'s decision, made at the call
    site on the same field. Two readers of one field rather than one, because a
    record that dropped the reason on a truncated call would lose the very figure
    that explains why the tokens stopped where they did.
    """
    choices = getattr(answered, "choices", None)
    if not isinstance(choices, list) or not choices:
        return None
    return _reported_str(choices[0], "finish_reason")


def _reported_str(source: object, name: str) -> str | None:
    value = getattr(source, name, None)
    return value if isinstance(value, str) and value else None


def _reported_int(source: object, name: str) -> int | None:
    value = getattr(source, name, None)
    # `bool` is an `int` in Python and is not a token count.
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _reported_decimal(source: object, name: str) -> Decimal | None:
    """A money figure, through `str` rather than through `float`.

    `Decimal(0.0000123)` is the binary expansion of a number the provider stated in
    decimal, and a cost this bench records has to be the cost the provider named.
    """
    value = getattr(source, name, None)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None
