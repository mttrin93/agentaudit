"""The bench's own model call. The instrument, never the target.

Two model calls exist in this project and they are not the same thing.
`backend/targets/reference/model.py` is the model a *reference agent* runs on: test
equipment, swapped by #15 to ask whether the bench reads an agent's defences or a
model's default refusals. This one is the model the *bench* asks — the adjudicator
that decides a judged family (`adjudication.py`), and the judge that writes a
narrative (`judge.py`).

They are separate modules with separate configuration on purpose. A single shared
client would make "the target's model" and "the instrument's model" one setting,
and the multi-model validity check would then move the instrument every time it
moved the target — which would make its own result unreadable.

The adaptive layer's attacker is the third, and it is built here too — by
`attacker_completion_for`, which is a separate function because it returns
something else. An adjudicator answers in prose; an attacker answers with a
`tool_calls` entry the provider filled in, which is a decision named from a closed
enum rather than a shape read back out of an answer.

Nothing here decides anything or is decided by anything: it returns what the model
said. Every instrument takes its completion as an argument rather than building
one, so the constraints ADR-0004 holds in their signatures stay held (no precedent,
no target identity, no endpoint of their own), and every test in the suite drives
them with a stub instead of a network call.
"""

import functools
import os
import time
from enum import StrEnum

from openai import OpenAI, OpenAIError, omit

from backend.bench.adaptive.attacker import (
    AttackerCompletion,
    AttackerUnavailable,
)
from backend.bench.adaptive.tools import (
    ATTACKER_TOOL_SCHEMAS,
    ToolInvocation,
    invocation_from,
)
from backend.bench.adjudication import Completion
from backend.bench.capability import (
    ReasoningEffort,
    ReasoningEffortNotAccepted,
    TemperatureNotAccepted,
    accepts_reasoning_effort,
    accepts_temperature,
)
from backend.bench.narration import Narrator
from backend.bench.unfinished import refuse_unfinished
from backend.bench.usage import ASK_FOR_COST, DISCARDED, UsageSink, usage_from

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODEL_TIMEOUT_SECONDS = 60.0
"""How long one call to an instrument may wait for its answer.

Declared because the SDK's own default is ten minutes, and a run holds nothing back
while it waits: one adjudication that never returns is a suite stopped at the attempt
it was scoring, with the operator watching a position that will not move. Sixty
seconds is the same patience `contract.DEFAULT_TIMEOUT` gives an endpoint, and the
same reasoning — long enough that a slow answer still arrives, short enough that a
stalled one is a failure somebody is told about.

Measured against the declared adjudicator, a verdict comes back in 0.8 to 2.3
seconds; the narrative judge writes prose and takes longer. This is a ceiling for the
call that hangs, not a target for the call that works, so it is set for the second of
those and not the first. The SDK retries twice inside it, so a stalled call costs
three of these before it is named.

Sixty is the whole of the arithmetic here because nothing waits on the bench. The
other two waits in this project are nested — the bench waits on a target endpoint
and that endpoint waits on its own model — and there the inner one has to finish
inside the outer, which `contract.DEFAULT_TIMEOUT` documents and
`targets/reference/model.refuse_inverted_patience` enforces. This call sits outside
that chain."""

DEFAULT_ADJUDICATOR_MODEL = "openrouter:openai/gpt-4.1-mini"
"""The model that decides the two judged families, and what κ measured it at.

**Measured, no longer provisional** (#11, `uv run python -m
scripts.measure_reliability`). Against the thirty-transcript gold set this model
reads disclosure denial at κ = 0.86 to 1.00 across readings and wrongful commitment
at κ = 0.59 to 0.73 — so it is fit to decide the first family and, on three of four
readings, **not fit to report the second** (ADR-0004's κ < 0.6 rule). The figure, the
four readings and the three transcripts every disagreement lands on are in
`docs/validation.md`; the number is a property of this string, so changing it
invalidates them.

It is a *declared* input either way, printed beside the run that used it, because a
rate is not readable without knowing which instrument produced it (ADR-0004).

Deliberately not the reference agents' model. It is a stronger model than the one
under the agents because it is doing a harder job than they are, and keeping the
two settings apart is what lets #15 move one without moving the other.
"""


DEFAULT_ATTACKER_TEMPERATURE = 0.0
"""What the attacker is sampled at when a deployment declares nothing.

Zero, and declared rather than left to the provider. The attacker's job is to compose
the next probe from what came back, which is reasoning about an observation and not
invention: the variety that matters between episodes comes from the target's replies
and from `k`, not from sampling noise. Declared because a report has a field for it —
a run whose temperature reads *not declared* is a run nobody can repeat the conditions
of, and the provider's own default is a fact about the provider that can change under
a bench without anybody editing anything.
"""

DEFAULT_ATTACKER_MODEL = "openrouter:openai/gpt-4.1-mini"
"""The model the adaptive attacker runs on, and a third declared setting.

Not the adjudicator's, although the string is the same today, and not the
reference agents'. Three instruments, three settings, for the reason #15 needs:
moving the model under the agents must not move the model deciding a judged
family, and neither of those may move the attacker — an adaptive layer whose
attacker changed with the target's model would make `A_break` unreadable
(ADR-0011).

The attacker is a declared input of a run on the same terms as the adjudicator: an
episode is not readable without knowing which instrument produced it, which is why
the alternative — a run silently taking the deterministic stand-in of
`backend/bench/adaptive/scripted.py` — is a thing the entry point never does.
"""


class Provider(StrEnum):
    OPENROUTER = "openrouter"


REFERENCE_MODEL_ENV = "AGENTAUDIT_REFERENCE_MODEL"
"""Where a deployment declares the model its three reference agents run on."""

SECOND_REFERENCE_MODEL_ENV = "AGENTAUDIT_SECOND_REFERENCE_MODEL"
"""Where a deployment declares the *second* model its reference agents are run on.

A second variable rather than a list in the first, because the two are declared for
different reasons and only one of them is what this bench's own gate citation was
earned on: `REFERENCE_MODEL_ENV` is the model every run and every gate run measures
against, and this one is reached by the two things that measure a *pair* — the model
swap `scripts/swap.py` runs, and the cross-model admission bar
([ADR-0012](../../docs/adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md),
[ADR-0105](../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)).

**Here rather than in `scripts/swap.py`, which declared it first.** That was correct
while a swap was the only thing in the bench with a second reference model; the
`/pending-routes` surface is the second, it has no terminal, and no module of
`backend/api/` may read an environment of its own — so one name in one place is what
keeps the two surfaces reading the same declaration. Each caller keeps its own
default: the swap falls back to `swap.DEFAULT_SECOND_MODEL`, and a deployment that
declares nothing here decides no pending route and says so on the screen that would
offer the control, because a bar met on one model is not the bar.
"""

ADJUDICATOR_MODEL_ENV = "AGENTAUDIT_ADJUDICATOR_MODEL"
"""Where a deployment declares the instrument that decides the judged families."""

ATTACKER_MODEL_ENV = "AGENTAUDIT_ATTACKER_MODEL"
"""Where a deployment declares the model the adaptive layer's attacker runs on.

A third variable rather than a reading of either of the other two, for the reason
`DEFAULT_ATTACKER_MODEL` is a third constant: an attacker that moved with the model
under the agents, or with the one deciding a judged family, would make `A_break`
a reading about two things at once (ADR-0011). Unset is the deterministic stand-in
of `backend/bench/adaptive/scripted.py`, declared as such and never named as a model.
"""


def declared_model(variable: str) -> str | None:
    """What the environment declares under that name, or `None` for nothing.

    Here rather than in the caller because this module is where the environment is
    read: `backend/api/` imports no `os` and is asserted not to, so that a price, a
    target URL or a bearer token cannot arrive that way behind a default
    (`test_api_runs.py`). A model identifier can, and only through this function —
    it is declared configuration that every signed report already prints, and the
    scripts read these same variables.

    **Blank is nothing.** An environment variable set to the empty string is how half
    the tooling that sets one says *unset*, and a bench that treated it as a model
    identifier would fail building a client for `''`.

    **There is no default.** A model named here that the deployment did not declare
    would describe a run that did not happen, which is what `UNDECLARED_MODEL` exists
    to say instead (ADR-0004).
    """
    return os.environ.get(variable, "").strip() or None


TURNS_PER_EPISODE_ENV = "AGENTAUDIT_TURNS_PER_EPISODE"
"""Where a deployment declares `T`, the cap on one adaptive episode.

A setting rather than a constant because the declared eight was sized for a **gate
run** — six families against three reference agents, where every extra turn is
multiplied by eighteen — and a run against one target pays for one target. The
operator whose endpoint it is decides how long an attacker may work on it, and they
decide it in front of the estimate, which is built from this number rather than
from the default it replaced.

Unset is `AdaptiveBudget`'s own declared value, which is what the gate is held to
and what `ADR-0010` costs out. Nothing here reaches the scored layer: `T` bounds a
layer that is scored on nothing, and no rate, band or `D` moves with it.
"""


def declared_turns_per_episode() -> int | None:
    """`T` as the environment declares it, or `None` for nothing.

    Read here for the reason every other variable is: `backend/api/` imports no `os`.

    **A value that is not a turn count is refused rather than rounded.** An
    unparseable or non-positive setting is the operator asking for something this
    cannot give, and a bench that fell back to the default would run a budget nobody
    chose and print it in an estimate as though they had.
    """
    declared = os.environ.get(TURNS_PER_EPISODE_ENV, "").strip()
    if not declared:
        return None
    try:
        turns = int(declared)
    except ValueError as unusable:
        raise ValueError(
            f"{TURNS_PER_EPISODE_ENV}={declared!r} is not a number of turns"
        ) from unusable
    if turns < 1:
        raise ValueError(
            f"{TURNS_PER_EPISODE_ENV}={declared!r}: an episode that may take no turn "
            "is an adaptive layer that cannot run"
        )
    return turns


ATTACKER_REASONING_EFFORT_ENV = "AGENTAUDIT_ATTACKER_REASONING_EFFORT"
"""Where a deployment declares how hard a reasoning attacker may think.

A fourth variable and **no default beside it**, unlike `DEFAULT_ATTACKER_TEMPERATURE`.
A temperature is sent on every request whether or not anybody chose one, so the bench
declaring its own zero is the honest reading of a field that will be printed either
way; a `reasoning_effort` is sent only when it is declared, so *not declared* is not a
gap in a report — it is the run's actual condition. A number this bench invented would
be a thinking budget a report named and nobody chose.

Unset is nothing sent, on every model. A model with no such setting is a separate fact
and `capability` holds it: an effort declared here against a chat model is refused at
configuration time rather than dropped into a request the provider will reject.
"""


def declared_reasoning_effort() -> ReasoningEffort | None:
    """The attacker's reasoning effort as the environment declares it, or `None`.

    Read here for the reason every other variable is: `backend/api/` imports no `os`.

    **A level this bench does not offer is refused rather than passed through.** The
    set is closed (`capability.ReasoningEffort`) and a deployment that typed
    `minimal` is asking for a level the o-series refuses, which is a request this
    cannot honour — and a bench that forwarded it would discover that at the first
    episode of a run somebody had already confirmed a spend for.
    """
    declared = os.environ.get(ATTACKER_REASONING_EFFORT_ENV, "").strip()
    if not declared:
        return None
    try:
        return ReasoningEffort(declared)
    except ValueError as unusable:
        raise ValueError(
            f"{ATTACKER_REASONING_EFFORT_ENV}={declared!r} is not a reasoning effort "
            f"this bench offers. The three are "
            f"{', '.join(str(effort) for effort in ReasoningEffort)}"
        ) from unusable


def completion_for(
    spec: str,
    temperature: float | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    usage: UsageSink = DISCARDED,
) -> Completion:
    """The bench's model call, from a `<provider>:<model>` configuration string.

    A string rather than a client, so the model an instrument used is a value a run
    can record and print. Parsed against a closed set of providers, like every other
    enumeration in the bench: an unrecognised provider fails here rather than at the
    first call.

    **`usage` is where the provider's own figures go, and it is beside the return
    and not in it.** `Completion` stays `(system_prompt, message) -> str`: a judge or
    an adjudicator that could see a token count or a cost is an instrument whose
    verdict is no longer derivable from the record a reader holds (ADR-0004), so the
    record travels to a sink the caller bound to a layer
    (`UsageLedger.for_layer`) and never through the signature that decides. The
    default is `DISCARDED` and it is named rather than `None`, so a caller that keeps
    no usage says so instead of leaving a reader to wonder whether a sink was
    forgotten.
    """
    provider, _, name = spec.partition(":")
    if not provider or not name:
        raise ValueError(
            f"a bench model configuration reads '<provider>:<model>', got {spec!r}"
        )
    match Provider(provider):
        case Provider.OPENROUTER:
            return _openrouter_completion(name, temperature, reasoning_effort, usage)


def _openrouter_completion(
    name: str,
    temperature: float | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    usage: UsageSink = DISCARDED,
) -> Completion:
    # The client is built here rather than on the first call, so a missing
    # credential is a refusal at configuration time. A run that reached its first
    # judged attempt before discovering it had no instrument would already have
    # spent the operator's budget on attempts nothing can score.
    _refuse_a_temperature_this_model_will_not_take(name, temperature)
    _refuse_a_reasoning_effort_this_model_has_no_setting_for(name, reasoning_effort)
    client = _client()

    def complete(system_prompt: str, message: str) -> str:
        started = time.monotonic()
        answered = client.chat.completions.create(
            model=name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            # `omit` rather than a number when nothing was declared: a temperature
            # this bench invented would be a setting a report named and nobody
            # chose, and the provider's own default is a fact about the provider
            # rather than a value to copy into the field that records a choice.
            temperature=omit if temperature is None else temperature,
            # Omitted on every model that was declared none, and never sent as a
            # level this bench chose: an effort in the request is an effort somebody
            # declared, which is what makes the field a report prints readable.
            reasoning_effort=(
                omit if reasoning_effort is None else reasoning_effort.value
            ),
            # The router reports what the call cost only when the request asks,
            # and this is the ask (`usage.ASK_FOR_COST`).
            extra_body=ASK_FOR_COST,
        )
        # Recorded before the reply is ruled on, and that order is deliberate: a
        # truncated call cost the operator its tokens all the same, and the one
        # call whose finish reason a reader most wants is the one that did not
        # finish. Usage is not an `Attempt` and records none — `refuse_unfinished`
        # still raises on the next line and no numerator moves (`unfinished`).
        usage.record(usage_from(answered, name, time.monotonic() - started))
        # Before `message` is read at all. A reply cut off at the token cap is a
        # partial string, and `_verdict_in` cannot tell one from a short answer:
        # a truncation that happened to carry a verdict word would decide a judged
        # family on where the budget fell (`unfinished`, ADR-0004).
        refuse_unfinished(name, answered.choices[0].finish_reason)
        return answered.choices[0].message.content or ""

    return complete


def narrator_for(spec: str, usage: UsageSink = DISCARDED) -> Narrator:
    """The pair that explains a run's findings, from one configuration string.

    A third builder rather than a third call to `completion_for` at every entry
    point, and the reason is a promise ADR-0030 makes: the judge and the
    remediation tool share a declared string only until the report has a field for
    a narrative, so the day a fourth string is declared this is the one place that
    moves. Three entry points built the pair themselves before this existed and
    the paraphrase of the reasoning was in all three.

    Two clients rather than one used twice, because `judge.Completion` and
    `remediation.Completion` are declared apart precisely so a deployment can point
    them at separate models — a single client here would be the shared setting that
    separation exists to prevent, arrived at from the builder instead of the call
    site.

    `usage` is one sink for both, and the caller binds it to the scored layer: the
    narrative is a scored-layer instrument, and its tokens counted into the adaptive
    bucket would be a scored figure inside an adaptive one (ADR-0010).
    """
    return Narrator(
        assess=completion_for(spec, usage=usage),
        remediate=completion_for(spec, usage=usage),
    )


def attacker_completion_for(
    spec: str,
    temperature: float | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    usage: UsageSink = DISCARDED,
) -> AttackerCompletion:
    """The adaptive attacker's model call, from the same configuration string.

    A second builder rather than a flag on `completion_for`, because the two return
    different things: the adjudicator answers in prose and the attacker answers with
    a tool call. `AttackerCompletion` is declared apart from
    `adjudication.Completion` precisely so one instrument can move without the
    other (ADR-0011), and widening a shared builder to return either would put the
    two back on one setting through the back door.

    `usage` is the same sink on the same terms, and the caller binds it to
    `Layer.ADAPTIVE` — an attacker's tokens counted into the scored layer's total
    would be an adaptive figure inside a scored one, which is the arithmetic
    ADR-0010 exists to prevent.
    """
    provider, _, name = spec.partition(":")
    if not provider or not name:
        raise ValueError(
            f"a bench model configuration reads '<provider>:<model>', got {spec!r}"
        )
    match Provider(provider):
        case Provider.OPENROUTER:
            return _openrouter_attacker(name, temperature, reasoning_effort, usage)


def _openrouter_attacker(
    name: str,
    temperature: float | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    usage: UsageSink = DISCARDED,
) -> AttackerCompletion:
    # Built at configuration time for the reason `_openrouter_completion` is: a
    # missing credential is a refusal now rather than at the first episode.
    _refuse_a_temperature_this_model_will_not_take(name, temperature)
    _refuse_a_reasoning_effort_this_model_has_no_setting_for(name, reasoning_effort)
    client = _client()

    def attack(system_prompt: str, brief: str) -> ToolInvocation | None:
        # The provider's own failure, translated once and here. What the adaptive
        # layer tolerates is `AttackerUnavailable` (ADR-0085), and translating at this
        # seam is what keeps the OpenAI SDK out of the import closure of everything
        # that reaches the layer — the verifier included, which is asserted to read no
        # credential and reach no network (`test_verify.py`).
        #
        # A truncated tool call is *not* translated: `ReplyUnfinished` is already a
        # named failure of this bench's own and surfaces as itself, which
        # `test_unfinished_replies.py` holds. The layer tolerates that name too.
        try:
            return _answered_with_a_tool_call(system_prompt, brief)
        except OpenAIError as unavailable:
            raise AttackerUnavailable(
                f"the attacker's model {name} did not answer: {unavailable}"
            ) from unavailable

    def _answered_with_a_tool_call(
        system_prompt: str, brief: str
    ) -> ToolInvocation | None:
        started = time.monotonic()
        answered = client.chat.completions.create(
            model=name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": brief},
            ],
            # The five tools as the provider's own schema. OpenRouter passes
            # `tool_calls` through from the underlying provider, so which tool was
            # named and what its argument was are fields the model filled in — not
            # a shape this bench asks for in prose and then cuts back out of an
            # answer.
            tools=list(ATTACKER_TOOL_SCHEMAS),
            temperature=omit if temperature is None else temperature,
            reasoning_effort=(
                omit if reasoning_effort is None else reasoning_effort.value
            ),
            # The router reports what the call cost only when the request asks,
            # and this is the ask (`usage.ASK_FOR_COST`).
            extra_body=ASK_FOR_COST,
        )
        # Recorded before the reply is ruled on, for the reason
        # `_openrouter_completion` gives: an episode that ended in a truncated tool
        # call still spent what it spent.
        usage.record(usage_from(answered, name, time.monotonic() - started))
        # Same check, and it matters more here: a `tool_calls` array cut off at the
        # cap is malformed JSON arriving where the structured path expects a
        # decision. `tool_calls` is itself a *complete* stop reason — it is how
        # this instrument answers — so what is refused is the truncated call, not
        # the called tool.
        refuse_unfinished(name, answered.choices[0].finish_reason)
        calls = answered.choices[0].message.tool_calls
        # No call, or more than one, is the model failing to make *the* decision
        # this step asks for. `None` both times: the attacker is told exactly one
        # tool per turn, the loop can only run the first, and acting on the first
        # of several would act on a decision the model made in parallel with — and
        # therefore without — the result of the one it made beside it.
        if calls is None or len(calls) != 1:
            return None
        called = calls[0]
        if called.type != "function":
            return None
        return invocation_from(called.function.name, called.function.arguments)

    return attack


def _refuse_a_temperature_this_model_will_not_take(
    name: str, temperature: float | None
) -> None:
    """Refuse here, on the declared table, rather than at the first call.

    The parameter is not dropped and the call is not attempted. Dropping it would
    make a report name a sampling temperature the request never carried, which is
    the one thing a declared input may not do (ADR-0004, ADR-0025); attempting it
    would put the discovery after the operator has attested and confirmed a spend,
    which is the fault `capability` exists to move earlier.

    A caller holding a *default* rather than a choice resolves it through
    `capability.temperature_for` first and records which declaration it made. What
    reaches here with a number is a number somebody chose.
    """
    if temperature is not None and not accepts_temperature(name):
        raise TemperatureNotAccepted(name, temperature)


def _refuse_a_reasoning_effort_this_model_has_no_setting_for(
    name: str, reasoning_effort: ReasoningEffort | None
) -> None:
    """The same refusal for the same reason, about the other parameter.

    Not dropped and the call not attempted: a report naming a reasoning effort the
    request never carried is the one thing a declared input may not do (ADR-0004,
    ADR-0025), and a chat model refuses this parameter as loudly as a reasoning model
    refuses a temperature — at the first call of a run whose spend is already
    confirmed, which is the moment `capability` exists to get ahead of.

    A caller holding a deployment's *declared* effort rather than an operator's choice
    resolves it through `capability.reasoning_effort_for` first and records which
    declaration it made.
    """
    if reasoning_effort is not None and not accepts_reasoning_effort(name):
        raise ReasoningEffortNotAccepted(name, reasoning_effort)


@functools.lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL),
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=MODEL_TIMEOUT_SECONDS,
    )
