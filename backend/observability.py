"""The one place a trace is emitted, and the whole of what a trace may carry.

A run is 180 scored calls plus retries and judge calls, plus up to 96 adaptive
calls; a gate run is around 830. When a family comes back all-zero the operator has
two explanations — the target defended, or the instrument misfired — and until this
module existed nothing on the record told them which. `docs/validation.md` answers
that question for the bench as a whole, once, at gate time. It cannot answer it for
the run in front of you.

**What this emits is the shape of a run and never its content.** `Field` is an
allowlist and not a redaction pass: a field that is not a member of it has no way to
reach a span, because `traced` takes a `Mapping[Field, Value]` and mypy will not
type a string key into one. A denylist over trace content goes stale the first time
somebody adds a node, and the failure is irreversible — a payload cannot be
unpublished (ADR-0008, ADR-0026).

A trace of shapes is not a weak trace. Timings, per-node counts, retry storms and
error classes are what actually locate a misfire; the payload text is what you
already have in `backend/cases/`.

## Three things this is not

**Not the Article 12 log.** `Article.RECORD_KEEPING` is a compliance obligation and
part of the evidence chain, and `registration.py` puts the liability record and the
Article 12 record in one artefact deliberately. A trace is a debugging aid pointed at
a sink the operator can delete. So tracing may sample and the Article 12 log may not,
and with tracing off every attempt is still recorded.

**Never the authority for a figure.** Calls spent, rates, intervals and bands come
from the run. If a trace disagrees with the run, the run is right and the trace is a
bug. Nothing in this module returns what it emitted, which is why no consumer can
read a figure back out of the sink (ADR-0006, ADR-0010, ADR-0026).

**Never a run's dependency.** A sink that is down, slow or misconfigured must not
fail, stall or alter a run. Every function here swallows its own failures and logs
them locally; the one thing `traced` does not swallow is an exception from the body
it wraps, because that is the run failing and the run's failure is not the tracer's
to eat. A bench that lost 180 paid calls because a container was restarting would be
a bench whose observability cost more than it explained.

## Why OpenTelemetry rather than the tracer the sink ships with

LangSmith's LangGraph integration captures inputs and outputs verbatim — full
prompts, full model replies. Switched on as documented, the first traced run sends
the attack payloads, the target's replies and the target's `auth_token` to a third
party. The convenience of the auto-tracer is exactly the convenience of having no
allowlist, so it is not the mechanism here: these are plain OTel spans carrying
allowlisted attributes, exported to an OTLP endpoint that happens to be LangSmith's
today and is a URL in the environment tomorrow (ADR-0026).

Three smaller properties of the implementation carry weight, and none of them is
incidental:

- **The provider is private to this module.** `set_tracer_provider` is never called,
  so nothing else in the process — no auto-instrumentation, no library that finds
  the global provider — can attach a span of its own to this exporter. The allowlist
  holds for everything that reaches the sink because this module is the only thing
  that can reach it.
- **No exception is ever recorded on a span.** `TargetUnreachable`'s message
  contains the endpoint URL (`contract.py`), so `record_exception` and a status
  description would each publish the one identifier ADR-0011 keeps out of a
  transcript. A failure is an `ERROR_CLASS` attribute and a bare error status.
- **The inherited switches are neutralised rather than merely unused.**
  `LANGSMITH_TRACING=true` in the environment activates langchain's callback tracer
  with no code change and no allowlist. A guard that works only because nobody set
  the variable is not a guard, so `disable_inherited_tracing` runs at the top of
  every run and at the top of the factory.

## What is deliberately absent

**Token counts.** The admitted list of #112 names call counts and token counts per
layer. Calls are here, from `RunState.spent`, which is the figure the bench enforces
its two ceilings against. Tokens are not, and the reason is this module's own second
rule: a token field whose only source was the sink is exactly what "never the
authority for a figure" forbids, so the bench had to learn to count tokens first, in
the run, where a report can print them.

**It now does, and that is not yet a licence to emit them.** `bench/usage.py` keeps
what the provider returned about every model call the bench makes — tokens in and
out, reasoning tokens, the router's own cost, the stop reason and the generation id,
bucketed per layer and absent rather than zero (#9). So the source is no longer the
sink. What is still missing is the permission: ADR-0026 declares these fields absent
*with a reason*, and adding a member to `Field` amends that ADR rather than
implementing it. The amendment is #10's, agreed before the enum grows, and until
then `Field` stays exactly as long as the ADR says it is.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace import Span as OtelSpan
from opentelemetry.trace import StatusCode

from backend.bench.contract import TargetFailure

log = logging.getLogger(__name__)

SERVICE = "agentaudit"
"""What the sink calls this process. One name, so two deployments are one service."""

Value = str | int | float | bool
"""What an attribute may hold.

Four scalar types and no container: a mapping or a sequence is where a payload
arrives disguised as structure, and a span attribute that had to be walked to be
checked is one whose contents no test can state.
"""


class Field(StrEnum):
    """Every attribute a span of this bench may carry. The allowlist itself.

    Enumerated because a denylist over trace content goes stale the first time
    somebody adds a node, and because the failure direction is irreversible: a field
    admitted by accident has already been sent by the time anybody reads the diff.
    `traced` accepts `Mapping[Field, Value]`, so a new attribute is a new member of
    this enum and a member is a line in a diff somebody has to justify.

    **What is excluded is excluded by not being here**, which is the whole of the
    construction. Named only because a reader will assume they are present: payload
    text, target replies, judge and adjudicator narrative, remediation text,
    precedent store contents, the target's own name, its `auth_token`, the signing
    key, the endpoint URL, and the operator's password and session token.
    """

    RUN_ID = "agentaudit.run.id"
    """Which run this span belongs to, as the run record names it.

    So a trace can be joined to the run it explains. It is the run's own id and
    never one invented here: an identifier no record holds is an identifier that
    joins to nothing.
    """

    GATE_RUN_ID = "agentaudit.gate_run.id"
    """The same, for a gate run. A second field rather than a shared one, because a
    gate run and a run against a target are different artefacts with different
    readers (ADR-0018), and a single id field would let a search for one return the
    other."""

    FAMILY = "agentaudit.family"
    CASE_ID = "agentaudit.case.id"
    ATTEMPT_INDEX = "agentaudit.attempt.index"
    """Which of the case's attempts this is, counted from zero.

    An index into the ten of one case and never a count of anything — an attempt is
    the unit of the denominator, and a count of attempts made is a different number
    (CONTEXT.md).
    """

    EPISODE_INDEX = "agentaudit.episode.index"
    """Which episode of the adaptive layer this is, counted from one.

    Not in #112's admitted list, and here deliberately. The list enumerates the
    scored layer's units — family, case, attempt — and the adaptive layer's units are
    episode and turn (`EpisodePosition`). Reusing `ATTEMPT_INDEX` for an episode
    ordinal is precisely the merge ADR-0010 forbids: it would put an episode where a
    denominator goes, in the one place a reader could not tell the two apart. An
    ordinal, and nothing divides it.
    """

    TURN = "agentaudit.turn"
    """Probes sent inside the current episode. Also an ordinal, also no
    denominator."""

    NODE = "agentaudit.node"
    """Which graph node ran. How long it took is the span's own duration."""

    CALLS_SCORED = "agentaudit.calls.scored"
    CALLS_ADAPTIVE = "agentaudit.calls.adaptive"
    """Calls spent, per layer, and there is deliberately no third field holding
    their sum.

    Two fields rather than one with a layer attribute beside it, because a single
    blended figure hides which half of a run is consuming the operator's inference
    budget and because the two ceilings of ADR-0007 are enforced independently. A
    field that added them would be the one figure ADR-0010 exists to keep apart,
    reconstituted in a sink.
    """

    VERDICT = "agentaudit.verdict"
    VERDICT_CLASS = "agentaudit.verdict_class"
    """Whether the verdict was reached by a success condition or by adjudication.

    Copied off the case record, like `Attempt.verdict_class` is, so a reader cannot
    work it out from the family name (spec story 18). Judged rates carry a wider
    stated limit and a κ figure beside them, so a trace that lost the distinction
    would be a trace whose verdicts all looked equally re-derivable.
    """

    RETRIES = "agentaudit.retries"
    """How many times a message had to go out again to get its reply.

    Sends minus one, so a healthy exchange reads zero. Retry storms are half of what
    locates a misfire, and they are invisible in a rate: the retries are deliberately
    invisible to the verdict (`contract.send_message`), which is exactly why they
    have to be visible here.
    """

    ERROR_CLASS = "agentaudit.error_class"
    """A `TargetFailure` member, and no message with it.

    The type is the enum and not a string, so the closed set of named outcomes is
    the closed set of values this field can hold. A `str` here would be the one
    attribute whose *value* a call site could invent — and the nearest thing to hand
    at every one of those call sites is `str(exception)`, which is the message that
    contains the endpoint url. The allowlist constrains the keys; this constrains
    the one value that had a plausible way of going wrong.

    The name of the outcome and nothing else. `TargetUnreachable`'s own message
    carries the endpoint URL, so it is never recorded — the class is the part that
    tells the reader which job they have, and it is the only part that is safe to
    send.
    """

    ADJUDICATOR_MODEL = "agentaudit.model.adjudicator"
    ATTACKER_MODEL = "agentaudit.model.attacker"
    REFERENCE_MODEL = "agentaudit.model.reference"
    """The three instruments' model identifiers, one field each.

    Three fields and not one, because they are three settings that must be able to
    move independently: #15 moves the model under the reference agents without
    moving the one deciding a judged family, and neither may move the attacker
    (`completion.py`, ADR-0011). A single `model` field would make a trace of a
    multi-model check unreadable.

    Declared by the caller rather than sniffed from a `Completion`, which is an
    opaque callable by construction. The reference model is absent for a run against
    anything that is not a reference agent, because the bench does not know what
    somebody else's agent runs on.
    """

    ENDPOINT_HASH = "agentaudit.endpoint.hash"
    """What the attestation already records, and never the URL (ADR-0007,
    ADR-0011).

    The hash distinguishes two targets in one run and joins a span to a registration
    record. The URL names the agent, and a URL in a third party's sink is an
    identification that cannot be withdrawn.
    """


class Span(StrEnum):
    """Every span name this bench emits. A closed set, for the reason `Field` is one.

    A span name is emitted data as much as an attribute is, and a name assembled
    from a value — a case id, a target's name — would be the allowlist bypassed by
    the one part of a span nobody thinks of as a field.
    """

    RUN = "run"
    CONFIRM_COST = "confirm_cost"
    RUN_SUITE = "run_suite"
    REGISTER = "register"
    CASE = "case"
    ATTEMPT = "attempt"
    EPISODE = "episode"
    TURN = "turn"


ENDPOINT_VARIABLE: Final = "AGENTAUDIT_TRACE_ENDPOINT"
"""Where traces go, and the switch that decides whether any are emitted.

Absent means tracing is off, and that is not a refusal to boot. ADR-0020's shape
without its severity: a signing key is what makes a report portable, and a trace
sink is a convenience. A bench that would not start without a debugging tool has its
priorities inverted.
"""

API_KEY_VARIABLE: Final = "AGENTAUDIT_TRACE_API_KEY"
PROJECT_VARIABLE: Final = "AGENTAUDIT_TRACE_PROJECT"
PREFIX_VARIABLE: Final = "AGENTAUDIT_TRACE_ATTRIBUTE_PREFIX"
"""What the sink needs in front of an attribute name, when it is not the default.

The one variable of this module where **blank is not nothing**. Elsewhere an empty
string is how half the tooling says unset, and blank falls back; here blank is the
meaningful value — a collector that keeps what it is sent wants no prefix at all —
so this is read with a sentinel and only a genuinely absent variable takes the
default.
"""

SAMPLE_VARIABLE: Final = "AGENTAUDIT_TRACE_SAMPLE"
"""What fraction of runs are traced, between 0 and 1, defaulting to all of them.

Sampling is over the trace and not the span, so a sampled-out run emits nothing
rather than a run with holes in it — a partial trace is a run whose missing spans
read as steps that did not happen. The Article 12 log does not sample whatever this
is set to.
"""

INHERITED_TRACING_VARIABLES: Final = (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_OTEL_ENABLED",
)
"""The switches that turn on somebody else's tracer, and are turned off here.

`langsmith` is in `uv.lock` today, pulled in transitively by `langchain-core`, and
any one of these activates the callback tracer with no code change and no allowlist —
which is the unredacted emission ADR-0026 exists to prevent. Nothing in this
repository sets them and, before this module, nothing stopped them: the state was not
"no observability", it was observability that a stray environment variable turns on.

Set to `false` rather than deleted, because the reader of a shell that exported one
of these has to be able to see that something else decided otherwise.
"""

DISABLED: Final = "false"

OTLP_TRACES_PATH: Final = "/v1/traces"
"""What an OTLP/HTTP exporter posts to, appended when the configured endpoint stops
at the base.

LangSmith documents its ingest as `https://api.smith.langchain.com/otel` and notes
that an exporter configured with an explicit endpoint wants the full path. Both forms
are accepted here so that neither reading of the documentation produces a sink that
silently drops everything.
"""

LANGSMITH_METADATA_PREFIX: Final = "langsmith.metadata."
"""What a sink has to see in front of an attribute name before it keeps it.

LangSmith's ingest recognises `gen_ai.*` and `langsmith.*` and surfaces a custom
attribute only under `langsmith.metadata.{key}`. An `agentaudit.*` key matches
neither, so it is accepted on the wire and discarded on arrival: the trace arrives
with its names, its nesting and its durations, and not one field of the allowlist.
That is the failure this constant exists to fix, and it is a rename at the boundary
rather than a change to what is emitted — `Field` keeps its own names, because the
allowlist is what a diff has to justify and it must not be spelled in a sink's
dialect.
"""


@dataclass(frozen=True)
class TraceConfig:
    """Where traces go and how many of them.

    A configured endpoint and nothing sink-specific in its type: moving to a sink
    the operator runs is this value changing, which is what keeps ADR-0026's revisit
    condition cheap. `prefix` is a string an operator sets and not a product name in
    a signature, and its *default* is the dialect of the sink this bench declares —
    a fact worth writing down here rather than leaving an operator to discover that
    their fields arrived and were dropped.
    """

    endpoint: str
    api_key: str | None = None
    project: str | None = None
    sample: float = 1.0
    prefix: str = LANGSMITH_METADATA_PREFIX
    """What is put in front of every attribute name on the way to the wire.

    Empty for a collector that keeps what it is sent. `Field` never spells it: the
    prefix is applied once, at `_attributes`, which is the boundary a member of the
    allowlist already crosses to become a string key.
    """

    def __post_init__(self) -> None:
        if not 0.0 <= self.sample <= 1.0:
            raise ValueError(
                f"{SAMPLE_VARIABLE}={self.sample!r} is not a fraction of runs. "
                "Sampling is a number between 0 and 1, and a bench that guessed "
                "what an out-of-range one meant would trace a share of runs nobody "
                "chose"
            )

    @property
    def traces_url(self) -> str:
        """The endpoint an OTLP/HTTP exporter posts spans to."""
        endpoint = self.endpoint.rstrip("/")
        if endpoint.endswith(OTLP_TRACES_PATH):
            return endpoint
        return endpoint + OTLP_TRACES_PATH

    @property
    def headers(self) -> dict[str, str]:
        """What the sink is sent to authenticate and file the trace.

        `x-api-key` and `Langsmith-Project` are LangSmith's names, and this is the
        one module allowed to know them (ADR-0026). Absent rather than empty when
        nothing is configured: a local collector wants no credential, and a header
        with an empty value is a credential that reads as present.
        """
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        if self.project:
            headers["Langsmith-Project"] = self.project
        return headers


@dataclass(frozen=True)
class TracedRun:
    """What a caller declares about the run a trace is of.

    Three of these fields are model identifiers rather than being read from the
    `Completion` callables a run is given, which are opaque by construction: the
    entry point knows what it configured and the bench deliberately does not
    (`completion.py`).
    """

    id: str
    gate: bool = False
    """Whether `id` is a gate run's. It decides which of the two id fields is
    emitted, and there is no run that emits both (ADR-0018)."""

    adjudicator_model: str | None = None
    attacker_model: str | None = None
    reference_model: str | None = None

    def fields(self) -> dict[Field, Value]:
        """This run's identity and declared instruments, as span attributes."""
        declared: dict[Field, Value] = {
            Field.GATE_RUN_ID if self.gate else Field.RUN_ID: self.id
        }
        for field, model in (
            (Field.ADJUDICATOR_MODEL, self.adjudicator_model),
            (Field.ATTACKER_MODEL, self.attacker_model),
            (Field.REFERENCE_MODEL, self.reference_model),
        ):
            if model:
                declared[field] = model
        return declared


def trace_config(environment: Mapping[str, str] | None = None) -> TraceConfig | None:
    """The sink the environment declares, or `None` for tracing off.

    The one function that reads the environment for tracing, and it lives outside
    `backend/api/` because no module of the API is an environment reader of its own
    (ADR-0020, `test_api_runs.py`).

    **Blank is nothing**, on the reasoning `completion.declared_model` uses: an
    environment variable set to the empty string is how half the tooling that sets
    one says unset.

    A sample that is not a fraction is refused rather than rounded, and the refusal
    happens here — at configuration, before a run — because a bench that fell back to
    tracing everything would be publishing a share of runs nobody chose.
    """
    values = os.environ if environment is None else environment
    endpoint = values.get(ENDPOINT_VARIABLE, "").strip()
    if not endpoint:
        return None
    declared = values.get(SAMPLE_VARIABLE, "").strip()
    try:
        sample = float(declared) if declared else 1.0
    except ValueError as unusable:
        raise ValueError(
            f"{SAMPLE_VARIABLE}={declared!r} is not a fraction of runs"
        ) from unusable
    declared_prefix = values.get(PREFIX_VARIABLE)
    return TraceConfig(
        endpoint=endpoint,
        api_key=values.get(API_KEY_VARIABLE, "").strip() or None,
        project=values.get(PROJECT_VARIABLE, "").strip() or None,
        sample=sample,
        prefix=(
            LANGSMITH_METADATA_PREFIX if declared_prefix is None else declared_prefix
        ),
    )


def disable_inherited_tracing(
    environment: MutableMapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Turn off every tracer this process inherited, and say which ones were on.

    Called at the top of `run_calibration` and at the top of `create_app`, so the
    guard is ahead of the first LangGraph invocation on every path that reaches a
    target. Returning the names it turned off rather than nothing, so the caller can
    log what somebody had set — a guard that fires silently is one nobody knows they
    are relying on.
    """
    values = os.environ if environment is None else environment
    turned_off = tuple(
        variable
        for variable in INHERITED_TRACING_VARIABLES
        if values.get(variable, DISABLED).strip().lower() not in {DISABLED, ""}
    )
    for variable in INHERITED_TRACING_VARIABLES:
        values[variable] = DISABLED
    if turned_off:
        log.warning(
            "tracing switches %s were set in this environment and have been turned "
            "off. They activate a tracer that sends prompts and replies verbatim; "
            "this bench emits an allowlist of fields through %s instead",
            ", ".join(turned_off),
            ENDPOINT_VARIABLE,
        )
    return turned_off


_prefix: str = ""
"""The prefix the installed sink reads, and empty when nothing is installed.

Module state beside `_provider` because it is a property of the sink rather than of
a call site: a span is opened with `Field` members wherever it is opened, and what
those become on the wire is decided once, where the exporter was.
"""

_provider: TracerProvider | None = None
"""This module's own provider, never the global one.

`set_tracer_provider` is not called anywhere in this repository. A global provider is
a sink any library in the process can find, and the allowlist would then be a
property of this module's call sites rather than of the exporter.
"""


def install(config: TraceConfig | None) -> None:
    """Point this module at a sink, or leave tracing off.

    `None` is the configured absence and not a failure: the bench boots, runs and
    reports with no sink at all. A sink that cannot be built is also not a failure —
    it is logged and tracing stays off, because a debugging aid may not be the reason
    a run does not start.
    """
    global _provider, _prefix
    if config is None:
        _provider = None
        _prefix = ""
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        _install(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=config.traces_url, headers=config.headers)
            ),
            sample=config.sample,
            prefix=config.prefix,
        )
    except Exception:  # noqa: BLE001 — a sink is never a reason a run does not start
        log.warning("tracing is off: the sink could not be built", exc_info=True)
        _provider = None
        _prefix = ""


def _install(processor: SpanProcessor, sample: float = 1.0, prefix: str = "") -> None:
    """Install one span processor behind a sampler. The seam the tests export to.

    A private function with a public sibling because it is the only way a test can
    read what was emitted, and a public reader is a route by which a *figure* could
    be read back out of the sink. Nothing outside this module and its tests calls it
    (ADR-0026, `test_observability.py`).
    """
    global _provider, _prefix
    sampler: Sampler = (
        ALWAYS_ON if sample >= 1.0 else ParentBased(TraceIdRatioBased(sample))
    )
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: SERVICE}), sampler=sampler
    )
    provider.add_span_processor(processor)
    _provider = provider
    _prefix = prefix


def flush(timeout_millis: int = 5_000) -> None:
    """Push what is buffered, best effort, and never wait long.

    Called when a run's root span closes. A batch processor exports on its own
    schedule, and a script that finished its run and exited would otherwise take its
    last spans with it — which is the half of a trace that says how the run ended.
    """
    provider = _provider
    if provider is None:
        return
    try:
        provider.force_flush(timeout_millis)
    except Exception:  # noqa: BLE001 — see the module docstring
        log.warning("tracing: flush failed and was dropped", exc_info=True)


def tracing() -> bool:
    """Whether a sink is installed. For a caller deciding whether to say so."""
    return _provider is not None


class Recorder:
    """A span in progress, or a drop. Two shapes behind one call site.

    Every method swallows its own failures. A caller writing to a span never has to
    know whether tracing is on, and never has to guard a `record` against a sink
    that has gone away mid-run.
    """

    def record(self, fields: Mapping[Field, Value]) -> None:
        """Add attributes to this span."""

    def errored(self, error_class: TargetFailure | None = None) -> None:
        """Mark this span failed, with the class of failure and no message.

        No exception is recorded and no status description is set, whatever the
        exception says. `TargetUnreachable`'s message contains the endpoint URL, and
        a status description is emitted verbatim.
        """

    def end(self) -> None:
        """Close this span and hand its context back."""

    def abandon(self, error_class: TargetFailure | None = None) -> None:
        """Mark this span failed and close it, in the one call that pairs them.

        For a span whose end is not lexical (`start`), on a path that is leaving
        through an exception. The two halves are always taken together and are worth
        exactly one call site each: a span marked failed and never closed is a span
        that is never exported at all, which is worse than one that was never opened.
        """
        self.errored(error_class)
        self.end()


DROPPED: Final = Recorder()
"""What a caller gets when tracing is off. Every method is a no-op, so a call site
has one shape and no branch."""


class _Recording(Recorder):
    """A real span, with the context token that has to be handed back."""

    def __init__(self, span: OtelSpan, token: object | None) -> None:
        self._span = span
        self._token = token

    def record(self, fields: Mapping[Field, Value]) -> None:
        # The allowlist is applied outside the guard, on purpose. A key that is not
        # a `Field` is a programming error and has to raise; everything past this
        # line is the sink, and the sink is never a reason a run fails.
        attributes = _attributes(fields)
        try:
            self._span.set_attributes(attributes)
        except Exception:  # noqa: BLE001 — see the module docstring
            log.warning("tracing: an attribute was dropped", exc_info=True)

    def errored(self, error_class: TargetFailure | None = None) -> None:
        # Through the same boundary every other attribute goes through, rather than
        # straight onto the span: one line applies the allowlist, and a second route
        # past it is how the first one stops being true.
        attributes = (
            {} if error_class is None else _attributes({Field.ERROR_CLASS: error_class})
        )
        try:
            self._span.set_attributes(attributes)
            self._span.set_status(StatusCode.ERROR)
        except Exception:  # noqa: BLE001 — see the module docstring
            log.warning("tracing: a failure was not marked", exc_info=True)

    def end(self) -> None:
        try:
            if self._token is not None:
                otel_context.detach(self._token)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 — see the module docstring
            log.warning("tracing: a span context was not detached", exc_info=True)
        try:
            self._span.end()
        except Exception:  # noqa: BLE001 — see the module docstring
            log.warning("tracing: a span was not closed", exc_info=True)


def _attributes(fields: Mapping[Field, Value] | None) -> dict[str, Value]:
    """The allowlist applied, one last time, at the boundary.

    Redundant against the type — `Mapping[Field, Value]` cannot hold a string key
    under mypy strict — and kept because this is the line that would have to be
    edited for an arbitrary key to reach a span. A field that is not a `Field` is a
    programming error and raises here rather than being dropped quietly: it can only
    fire in a test, and a silently discarded attribute is a trace that lies about
    what it carries.

    The installed sink's prefix goes on here and nowhere else, because this is
    already the one line where a member of the allowlist becomes a string key. A
    prefix applied at a call site would be a call site that knows a sink, and a
    prefix applied inside `Field` would be the allowlist spelled in a sink's dialect
    — unreadable against the run record it is supposed to join to.
    """
    if not fields:
        return {}
    for key in fields:
        if not isinstance(key, Field):
            raise TypeError(
                f"{key!r} is not a member of Field. A span attribute is an "
                "allowlisted field and not a name a call site invents: a trace of "
                "this bench carries the shape of a run and never its content "
                "(ADR-0026)"
            )
    return {_prefix + key.value: value for key, value in fields.items()}


@contextmanager
def traced(
    name: Span, fields: Mapping[Field, Value] | None = None
) -> Iterator[Recorder]:
    """One span around a block, or nothing at all if tracing is off.

    The body's exceptions propagate. The span is marked failed on the way out and
    closed either way, and no exception is recorded on it — the class of a target
    failure is written by the caller through `errored`, because the caller is what
    knows the class and the exception is what carries the URL.
    """
    recorder = start(name, fields)
    try:
        yield recorder
    except BaseException:
        recorder.errored()
        recorder.end()
        raise
    recorder.end()


def start(
    name: Span, fields: Mapping[Field, Value] | None = None, *, current: bool = True
) -> Recorder:
    """Open a span whose end is not lexical, or hand back a drop.

    For the one shape `traced` cannot hold: an attempt begins when its message goes
    on the wire and ends when its verdict arrives, and a judged verdict is decided on
    another thread while the next messages go out (`attacker.py`). The caller ends it.

    `current` is what stops that from corrupting the tree. A span made current has to
    be detached in the reverse order it was attached, and attempts do not end in the
    order they start — so an attempt span is created as a child of whatever is
    current, which is its case, and is never made current itself. Nothing nests under
    an attempt, which is true of the bench as well as of the trace.

    Never raises. A sink that has gone away mid-run leaves the run untouched, which
    is the third of the three things a trace is not.
    """
    provider = _provider
    if provider is None:
        return DROPPED
    # Outside the guard below, for the reason `_Recording.record` applies it outside
    # its own: an attribute that is not on the allowlist is a bug in a call site and
    # must be raised in the face of whoever wrote it, and a sink that is down must
    # not be.
    attributes = _attributes(fields)
    try:
        span = provider.get_tracer(SERVICE).start_span(
            name.value, attributes=attributes
        )
        token = (
            otel_context.attach(otel_trace.set_span_in_context(span))
            if current
            else None
        )
        return _Recording(span, token)
    except Exception:  # noqa: BLE001 — see the module docstring
        log.warning("tracing: a span was not started", exc_info=True)
        return DROPPED


WRITERS: Final = MappingProxyType(
    {
        "Field": Field,
        "Span": Span,
        "TraceConfig": TraceConfig,
        "TracedRun": TracedRun,
        "Recorder": Recorder,
        "DROPPED": DROPPED,
        "trace_config": trace_config,
        "disable_inherited_tracing": disable_inherited_tracing,
        "install": install,
        "flush": flush,
        "tracing": tracing,
        "traced": traced,
        "start": start,
        "ENDPOINT_VARIABLE": ENDPOINT_VARIABLE,
        "API_KEY_VARIABLE": API_KEY_VARIABLE,
        "PROJECT_VARIABLE": PROJECT_VARIABLE,
        "SAMPLE_VARIABLE": SAMPLE_VARIABLE,
        "PREFIX_VARIABLE": PREFIX_VARIABLE,
        "INHERITED_TRACING_VARIABLES": INHERITED_TRACING_VARIABLES,
    }
)
"""Everything a consumer of this module may import. Writers, and no reader.

Declared as a value rather than left as a docstring claim, because the constraint it
carries is the one that keeps a trace from becoming the authority for a figure: there
is nothing on this list that returns what was emitted, so no route, report or gate
decision can read a number back out of the sink (ADR-0006, ADR-0026). A test walks
the modules that import this one and asserts they import nothing else
(`test_observability.py`).
"""
