"""What a trace carries, what it never carries, and what happens when it cannot.

The tests here are in three groups, and the middle one is the reason the module
exists. The first says the allowlist is a declared list and the emitted set is
exactly it. The second says the things a trace must never contain are not in one —
payload text, replies, narrative, the target's name, its token, the endpoint url —
and that a bench which inherited `LANGSMITH_TRACING=true` emits nothing except
through the allowlist anyway. The third says a sink is never a run's dependency: off,
absent, unreachable and sampled to nothing, the run finishes and the Article 12
record is whole.

The exclusion tests are written over **every string a span carries** rather than
over its attributes alone — names, attribute values, event names, status
descriptions. A span name assembled from a case's payload would pass an
attributes-only check, and the failure it would represent is the irreversible one
(ADR-0008, ADR-0026).
"""

import ast
import os
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from backend import observability
from backend.api.app import create_app
from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.precedent import DURABLE_PRECEDENT
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adaptive.tools import ToolInvocation
from backend.bench.adjudication import Completion
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetFailure, TargetUnreachable
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, DiscoveredBy, Family
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.bench.usage import ModelUsage, UsageLedger
from backend.graph.budget import Layer
from backend.observability import (
    API_KEY_VARIABLE,
    ENDPOINT_VARIABLE,
    INHERITED_TRACING_VARIABLES,
    LANGSMITH_METADATA_PREFIX,
    PREFIX_VARIABLE,
    PROJECT_VARIABLE,
    SAMPLE_VARIABLE,
    Field,
    Span,
    TraceConfig,
    TracedRun,
    disable_inherited_tracing,
    trace_config,
)
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CONFIRMING,
    a_finding,
    reference_target,
)
from backend.tests.flaky_target import IMPATIENT, flaky_target

A_RUN = TracedRun(
    id="run-under-test",
    adjudicator_model="openrouter:openai/gpt-4.1-mini",
    attacker_model="openrouter:openai/gpt-4.1-nano",
    reference_model="stub:obedient",
)
A_GATE_RUN = TracedRun(id="gate-run-under-test", gate=True)

A_LONG_TIME = 600_000
"""A batch schedule longer than any test, so only an explicit flush exports."""

AN_ADJUDICATORS_PROSE = "the agent conceded the refund without checking eligibility"
A_PRECEDENT_REASON = "a prior finding's reason, which is narrative and not a shape"
A_PRECEDENT_REMEDIATION = "a prior finding's remediation, which is also not a shape"


def narrating(prose: str, verdict: Verdict = Verdict.SUCCEEDED) -> Completion:
    """An adjudicator that prefaces its verdict with prose, as a real one does.

    The line the bench reads is the labelled one; everything above it is the
    instrument talking, and it is the half that must not leave the process.
    """
    return lambda system_prompt, message: f"{prose}\nverdict: {verdict}"


@contextmanager
def recording(sample: float = 1.0, prefix: str = "") -> Iterator[InMemorySpanExporter]:
    """Install an exporter this test can read, and take it out again afterwards.

    Reaches `observability._install`, which is private and is the only way to read
    what was emitted. That privacy is the point rather than an inconvenience: a
    public reader would be a route by which a figure could be read back out of the
    sink, and `test_nothing_outside_this_module_can_read_what_was_emitted` asserts
    no module of the bench takes it.
    """
    exporter = InMemorySpanExporter()
    processor: SpanProcessor = SimpleSpanProcessor(exporter)
    observability._install(processor, sample=sample, prefix=prefix)
    try:
        yield exporter
    finally:
        observability.install(None)


def traced_calibration(
    case: Case, trace: TracedRun = A_RUN, name: str = "trivial", prefix: str = ""
) -> tuple[CalibrationResult, list[ReadableSpan]]:
    """One case against one served reference agent, with the trace it emitted."""
    with recording(prefix=prefix) as exporter, reference_target(name=name) as reference:
        result = run_calibration(
            cases=[case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            trace=trace,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )
        return result, list(exporter.get_finished_spans())


A_REPORTED_COST = Decimal("0.000123")
REPORTED_INPUT_TOKENS = 1_101
REPORTED_OUTPUT_TOKENS = 37
REPORTED_REASONING_TOKENS = 11
"""What one stood-in provider response says it consumed.

Figures rather than a live call, and the reason is what these tests are about: the
trace carries what the run's ledger holds, so a real router would be proving
OpenRouter's accounting rather than this module's emission — and it would put an
attack payload on somebody's wire to do it (ADR-0026, `bench/usage.py`).
"""


def a_reported_call(reported: bool = True) -> ModelUsage:
    """One model call as `usage.usage_from` would have read it off a response.

    `reported=False` is the provider that returned no usage block at all, which is
    the call a layer's total is missing and the reason a total says how many of
    those there were (`usage.NO_TOKEN_COUNTS_REPORTED`).
    """
    return ModelUsage(
        requested_model="openrouter:openai/gpt-4.1-mini",
        latency_seconds=0.25,
        input_tokens=REPORTED_INPUT_TOKENS if reported else None,
        output_tokens=REPORTED_OUTPUT_TOKENS if reported else None,
        reasoning_tokens=REPORTED_REASONING_TOKENS if reported else None,
        provider_cost=A_REPORTED_COST if reported else None,
    )


class Reporting:
    """An instrument's usage, recorded into one layer of a run's ledger.

    Under a lock and counting its own calls, because a judged case's adjudications
    are decided on a pool while the next messages go out (`attacker.py`) — two
    threads reaching the same stand-in is the ordinary case here and not an edge.

    `every_call=False` reports on one call in three, which is the partial total a
    reader has to be able to see is partial. One in three rather than one in two,
    because a layer where half the calls reported is a layer whose shortfall and
    whose coverage are the same number — and a test that cannot tell those apart
    would pass on a trace emitting either.
    """

    def __init__(
        self, ledger: UsageLedger, layer: Layer, every_call: bool = True
    ) -> None:
        self._sink = ledger.for_layer(layer)
        self._every_call = every_call
        self._lock = threading.Lock()
        self.calls = 0

    def record(self) -> None:
        with self._lock:
            self.calls += 1
            reported = self._every_call or self.calls % 3 == 1
        self._sink.record(a_reported_call(reported))


def adjudicating(usage: Reporting) -> Completion:
    """An adjudicator that reports what it consumed, beside the verdict it returns.

    Beside and never inside: `Completion` stays `(system_prompt, message) -> str`,
    because an instrument that could see a token count is one whose verdict is no
    longer derivable from the record a reader holds (ADR-0004).
    """

    def complete(system_prompt: str, message: str) -> str:
        usage.record()
        return f"verdict: {Verdict.RESISTED}"

    return complete


def attacking(usage: Reporting) -> AttackerCompletion:
    """The adaptive attacker, reporting into the adaptive layer and no other."""

    def attack(system_prompt: str, brief: str) -> ToolInvocation | None:
        usage.record()
        return SCRIPTED_ATTACKER(system_prompt, brief)

    return attack


def a_run_that_reports_usage(
    judged: Case,
    deterministic: Case,
    every_call: bool = True,
    trace: TracedRun = A_RUN,
) -> tuple[CalibrationResult, list[ReadableSpan]]:
    """A run over both layers whose instruments report what the provider said.

    Two cases, because both layers have to consume something: the judged one calls
    the adjudicator, and the adaptive layer runs over the families this run holds a
    deterministic case for.

    The ledger is built here and handed to `run_calibration` for the reason that
    function states — the sink an instrument records through is fixed when the
    client is built, which is before a run exists, so the caller that built the
    instruments is the one that holds the ledger they were bound to.
    """
    ledger = UsageLedger()
    with recording() as exporter, reference_target() as reference:
        result = run_calibration(
            cases=[judged, deterministic],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=adjudicating(Reporting(ledger, Layer.SCORED, every_call)),
            attacker=attacking(Reporting(ledger, Layer.ADAPTIVE, every_call)),
            usage=ledger,
            trace=trace,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )
        return result, list(exporter.get_finished_spans())


TOKEN_AND_COST_FIELDS = (
    Field.INPUT_TOKENS_SCORED,
    Field.INPUT_TOKENS_ADAPTIVE,
    Field.OUTPUT_TOKENS_SCORED,
    Field.OUTPUT_TOKENS_ADAPTIVE,
    Field.REASONING_TOKENS_SCORED,
    Field.REASONING_TOKENS_ADAPTIVE,
    Field.PROVIDER_COST_SCORED,
    Field.PROVIDER_COST_ADAPTIVE,
    Field.CALLS_WITHOUT_TOKENS_SCORED,
    Field.CALLS_WITHOUT_TOKENS_ADAPTIVE,
    Field.CALLS_WITHOUT_COST_SCORED,
    Field.CALLS_WITHOUT_COST_ADAPTIVE,
)
"""Every field a run's usage can put on a span, named once for the absence test."""


def fields_of(spans: Sequence[ReadableSpan]) -> set[str]:
    """Every attribute name the given spans carry."""
    return {key for span in spans for key in (span.attributes or {})}


def strings_in(spans: Sequence[ReadableSpan]) -> list[str]:
    """Every string a trace of these spans would put on the wire.

    Names, attribute names and values, event names, and the status description.
    Deliberately not just the attribute values: the allowlist governs what a span
    *carries*, and a span name built out of a payload would be content published
    through the one field nobody thinks of as one.
    """
    said: list[str] = [span.name for span in spans]
    for span in spans:
        for key, value in (span.attributes or {}).items():
            said.append(str(key))
            said.append(str(value))
        said.extend(event.name for event in span.events)
        if span.status.description:
            said.append(span.status.description)
    return said


# --- the allowlist ----------------------------------------------------------------


def test_the_emitted_fields_are_exactly_the_declared_allowlist(
    leakage_case: Case,
    wrongful_commitment_case: Case,
) -> None:
    """Every member of `Field` is written by something, and nothing else is written.

    Both halves matter and they fail in opposite directions. A field emitted and not
    declared is the allowlist bypassed — the failure this construction exists to
    prevent. A field declared and never emitted is a reader told a trace carries
    something it does not, which is how somebody comes to conclude a run had no
    retries from a field nothing writes.

    The union is taken over four runs because no single run can produce all of
    them: a run carries a run id or a gate run id and never both (ADR-0018), a
    healthy endpoint never shows an error class, and a run whose instruments were
    built with no usage sink reports no tokens — which is a fourth run here rather
    than a relaxation of the assertion, because *declared and never emitted* is
    half of what this test is for.
    """
    _, ordinary = traced_calibration(leakage_case)
    _, gate = traced_calibration(leakage_case, trace=A_GATE_RUN)
    _, reporting = a_run_that_reports_usage(wrongful_commitment_case, leakage_case)

    with (
        recording() as exporter,
        flaky_target(failures_before_reply=IMPATIENT.sends + 1) as flaky,
    ):
        with pytest.raises(TargetUnreachable):
            run_calibration(
                cases=[leakage_case],
                targets=[flaky.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=flaky.plant_nonce,
                approve=CONFIRMING,
                trace=A_RUN,
                discovered_by=DiscoveredBy.ADAPTIVE,
            )
        failed = list(exporter.get_finished_spans())

    assert fields_of(ordinary + gate + reporting + failed) == {
        field.value for field in Field
    }


def test_the_allowlist_reaches_the_sink_under_the_prefix_the_sink_reads(
    leakage_case: Case,
) -> None:
    """A field the sink discards is a field that was never emitted.

    The failure this guards is silent in both directions and cost a real trace: the
    spans arrive, the waterfall is right, the durations are right, and every
    attribute of the allowlist is dropped at ingest because `agentaudit.*` is not a
    namespace LangSmith recognises. Nothing errors, nothing is logged, and a reader
    concludes the bench emits names and timings by design.

    Asserted over the emitted keys rather than over the configuration, because a
    prefix that a config held and an exporter did not apply would pass every test
    that read the config back.
    """
    _, spans = traced_calibration(leakage_case, prefix=LANGSMITH_METADATA_PREFIX)
    emitted = fields_of(spans)

    assert emitted, "a run that emitted no attributes proves nothing here"
    unprefixed = sorted(
        key for key in emitted if not key.startswith(LANGSMITH_METADATA_PREFIX)
    )
    assert not unprefixed, f"{unprefixed} reach the sink under a name it discards"

    # And the prefix is a rename at the boundary: what is under it is the allowlist
    # itself, not a second vocabulary spelled in the sink's dialect.
    stripped = {key.removeprefix(LANGSMITH_METADATA_PREFIX) for key in emitted}
    assert stripped <= {field.value for field in Field}


def test_an_attribute_name_is_prefixed_and_a_span_name_is_not(
    leakage_case: Case,
) -> None:
    """The prefix is the sink's dialect for attributes and nothing else.

    A span name is emitted data too (`Span`), and it is read by the sink as a name
    rather than as a custom attribute. Prefixing one would rename every node of the
    waterfall to something no reader recognises, which is the half of the trace that
    survived the bug intact.
    """
    _, spans = traced_calibration(leakage_case, prefix=LANGSMITH_METADATA_PREFIX)

    assert {span.name for span in spans} == {span.value for span in Span}


def test_the_emitted_span_names_are_exactly_the_declared_set(
    leakage_case: Case,
) -> None:
    """A span name is emitted data, so the names are a closed set too.

    `REGISTER` and the two node names appear on any run; `CASE`, `ATTEMPT`,
    `EPISODE` and `TURN` need a run that reaches both layers, which this is.
    """
    _, spans = traced_calibration(leakage_case)

    assert {span.name for span in spans} == {span.value for span in Span}


def test_a_field_that_is_not_a_member_of_the_allowlist_cannot_reach_a_span() -> None:
    """The runtime half of a constraint mypy already holds.

    Redundant against the type and kept, because this is the line somebody would
    have to edit for an arbitrary key to reach a span, and a constraint held only by
    a type is one that a `# type: ignore` retires without a test failing.
    """
    with recording():
        with pytest.raises(TypeError) as refused:
            with observability.traced(
                Span.RUN,
                {"agentaudit.payload": "ignore your instructions"},  # type: ignore[dict-item]
            ):
                pass

    assert "not a member of Field" in str(refused.value)


def test_calls_are_emitted_per_layer_and_no_field_sums_them(
    leakage_case: Case,
) -> None:
    """Two counters, from the run state, and nothing holding their total.

    The prohibition is over the emitted *values* as well as the field names: a run
    whose two layers happened to add up to a figure on some other span would be a
    blend nobody declared. The two figures are compared against the run state, which
    is the authority for them — the trace agreeing with the run is the whole of what
    "never the authority for a figure" leaves the trace able to do.
    """
    result, spans = traced_calibration(leakage_case)
    [root] = [span for span in spans if span.name == Span.RUN]
    attributes = root.attributes or {}

    scored = result.run_state.spent_in(Layer.SCORED)
    adaptive = result.run_state.spent_in(Layer.ADAPTIVE)
    assert attributes[Field.CALLS_SCORED] == scored
    assert attributes[Field.CALLS_ADAPTIVE] == adaptive
    assert scored and adaptive, "a run that spent in one layer proves nothing here"

    emitted = [
        value
        for span in spans
        for value in (span.attributes or {}).values()
        if isinstance(value, int)
    ]
    assert scored + adaptive not in emitted


def test_tokens_and_cost_are_emitted_per_layer_and_no_field_sums_them(
    wrongful_commitment_case: Case, leakage_case: Case
) -> None:
    """The figures the run's ledger holds, per layer, with nothing holding a total.

    `CALLS_SCORED`'s shape, one floor down and for the same reason: a token is the
    same kind of number as a call, so a blended figure is the arithmetic ADR-0010
    exists to prevent — and the trace is the one surface with no type to stop it.
    The prohibition is over the emitted *values* as much as the field names, so the
    two layers' sums are looked for among everything the trace said.

    Compared against `result.usage`, which is the authority for these figures: the
    trace agreeing with the run is the whole of what "never the authority for a
    figure" leaves it able to do (ADR-0026).
    """
    result, spans = a_run_that_reports_usage(wrongful_commitment_case, leakage_case)
    [root] = [span for span in spans if span.name == Span.RUN]
    attributes = root.attributes or {}

    scored = result.usage.totals_in(Layer.SCORED)
    adaptive = result.usage.totals_in(Layer.ADAPTIVE)
    assert scored.calls and adaptive.calls, (
        "a run one layer of which made no model call proves nothing here"
    )
    assert attributes[Field.INPUT_TOKENS_SCORED] == scored.input_tokens
    assert attributes[Field.OUTPUT_TOKENS_SCORED] == scored.output_tokens
    assert attributes[Field.REASONING_TOKENS_SCORED] == scored.reasoning_tokens
    assert attributes[Field.PROVIDER_COST_SCORED] == str(scored.provider_cost)
    assert attributes[Field.INPUT_TOKENS_ADAPTIVE] == adaptive.input_tokens
    assert attributes[Field.OUTPUT_TOKENS_ADAPTIVE] == adaptive.output_tokens
    assert attributes[Field.REASONING_TOKENS_ADAPTIVE] == adaptive.reasoning_tokens
    assert attributes[Field.PROVIDER_COST_ADAPTIVE] == str(adaptive.provider_cost)

    said = strings_in(spans)
    for one, other in (
        (scored.input_tokens, adaptive.input_tokens),
        (scored.output_tokens, adaptive.output_tokens),
        (scored.reasoning_tokens, adaptive.reasoning_tokens),
    ):
        assert one is not None and other is not None
        assert str(one + other) not in said, "a blended token total reached the trace"
    assert scored.provider_cost is not None and adaptive.provider_cost is not None
    blended = scored.provider_cost + adaptive.provider_cost
    assert str(blended) not in said, "a blended cost reached the trace"


def test_a_layer_that_reported_no_tokens_emits_no_figure_rather_than_a_zero(
    leakage_case: Case,
) -> None:
    """Absent rather than zero, which is what ADR-0026 said before there was a source.

    A run whose instruments were built with no usage sink is the ordinary case for
    the suite and for a deployment that has not wired one: its ledger reports
    nothing, and a `0` on the span would be a figure the bench invented and then
    joined to a run id. Nothing is emitted — not the totals, and not the shortfall
    counts that qualify them, because zero missing out of zero is a statement about
    a total that is not there.
    """
    result, spans = traced_calibration(leakage_case)
    emitted = fields_of(spans)

    for figure in TOKEN_AND_COST_FIELDS:
        assert figure.value not in emitted, (
            f"{figure} was emitted for a run with no ledger"
        )
    for layer in Layer:
        totals = result.usage.totals_in(layer)
        assert totals.input_tokens is None and totals.provider_cost is None


def test_a_partial_total_says_how_many_of_the_layers_calls_it_is_missing(
    wrongful_commitment_case: Case, leakage_case: Case
) -> None:
    """A total summed over half the calls understates the layer, and says so.

    The failure this guards is a reader taking a floor for a fact: every provider
    behind the router fills in a different subset of the usage block, so a layer
    whose total covers some of its calls is the normal case and not an edge
    (`usage.LayerTotals`). The shortfall is an absolute count of the layer's own
    model calls and never a share of `CALLS_SCORED`, which counts messages to a
    target and is a different population.
    """
    result, spans = a_run_that_reports_usage(
        wrongful_commitment_case, leakage_case, every_call=False
    )
    [root] = [span for span in spans if span.name == Span.RUN]
    attributes = root.attributes or {}

    scored = result.usage.totals_in(Layer.SCORED)
    missing = scored.calls - scored.calls_reporting_tokens
    assert missing, "a layer every call of which reported tokens proves nothing here"
    assert not scored.every_call_reported_tokens()
    assert attributes[Field.CALLS_WITHOUT_TOKENS_SCORED] == missing
    assert missing != scored.calls_reporting_tokens, (
        "a layer whose shortfall equals its coverage cannot tell the two apart"
    )
    assert attributes[Field.CALLS_WITHOUT_COST_SCORED] == (
        scored.calls - scored.calls_reporting_cost
    )
    assert (
        attributes[Field.CALLS_WITHOUT_TOKENS_SCORED] != attributes[Field.CALLS_SCORED]
    ), "the shortfall is a count of the bench's own model calls, not of sends"


def test_the_cost_a_trace_carries_is_the_decimal_the_provider_named(
    wrongful_commitment_case: Case, leakage_case: Case
) -> None:
    """A string, because the one conversion this figure may not take is `float`.

    `float("0.0000123")` is a binary expansion of a number the provider stated in
    decimal, and a cost this bench records has to be the cost the provider named
    (`usage._reported_decimal`). A span attribute may hold a float, which is exactly
    why the type this one is emitted as has a test.
    """
    result, spans = a_run_that_reports_usage(wrongful_commitment_case, leakage_case)
    [root] = [span for span in spans if span.name == Span.RUN]
    attributes = root.attributes or {}
    exact = result.usage.totals_in(Layer.SCORED).provider_cost
    assert exact is not None

    emitted = attributes[Field.PROVIDER_COST_SCORED]
    assert isinstance(emitted, str)
    assert emitted == str(exact)
    assert Decimal(emitted) == exact


def test_the_two_layers_positions_are_emitted_under_their_own_fields(
    leakage_case: Case,
) -> None:
    """An attempt index is not an episode ordinal, in the trace as in the run state.

    The one merge ADR-0010 forbids, checked where it would be cheapest to make: an
    episode reported under `ATTEMPT_INDEX` would put an ordinal where a denominator
    goes, in the one surface that has no type to stop it.
    """
    _, spans = traced_calibration(leakage_case)
    attempts = [span for span in spans if span.name == Span.ATTEMPT]
    episodes = [span for span in spans if span.name == Span.EPISODE]

    assert attempts and episodes
    assert all(Field.ATTEMPT_INDEX in (span.attributes or {}) for span in attempts)
    assert all(Field.EPISODE_INDEX in (span.attributes or {}) for span in episodes)
    assert not any(Field.ATTEMPT_INDEX in (span.attributes or {}) for span in episodes)
    assert not any(Field.EPISODE_INDEX in (span.attributes or {}) for span in attempts)


def test_a_gate_run_is_emitted_under_the_gate_field_and_never_the_run_field(
    leakage_case: Case,
) -> None:
    """Two artefacts, two fields, and no span that carries both (ADR-0018)."""
    _, spans = traced_calibration(leakage_case, trace=A_GATE_RUN)
    fields = fields_of(spans)

    assert Field.GATE_RUN_ID in fields
    assert Field.RUN_ID not in fields


# --- what a trace never carries ---------------------------------------------------


def test_no_payload_reply_narrative_target_name_url_or_token_is_emitted(
    leakage_case: Case,
) -> None:
    """The exclusions named in #112, asserted over every string in the trace.

    Each of these is in the run and none of them is in the trace. The endpoint url
    and the bearer token are the two that cannot be withdrawn once they have reached
    a third party, and the target's own name is the identification ADR-0011 keeps out
    of what an instrument sees.
    """
    result, spans = traced_calibration(leakage_case)
    [target_run] = result.target_runs
    target = target_run.target
    reply = target_run.attempts[0].scored.reply_text

    said = " | ".join(strings_in(spans))
    for withheld in (
        leakage_case.script,
        reply,
        target.url,
        target.auth_token,
        target.name,
        target_run.registration.nonce,
    ):
        assert withheld
        assert withheld not in said, f"{withheld!r} reached the trace"


def test_no_adjudicator_narrative_precedent_or_remediation_is_emitted(
    disclosure_denial_case: Case, leakage_case: Case
) -> None:
    """The three exclusions a deterministic run has nothing to test.

    An adjudicated case puts an instrument's prose into the run, and a seeded
    precedent store puts a prior finding's reason and remediation within reach of
    the adaptive layer's `retrieve_precedent`. None of the three is a shape, and
    none of them reaches the sink.

    Both cases run, and the deterministic one is what makes the precedent reachable:
    the store holds deterministic findings only (ADR-0004), and the adaptive layer
    runs over the families this run holds a deterministic case for.
    """
    DURABLE_PRECEDENT.record(
        a_finding(
            family=Family(leakage_case.family),
            case_id=leakage_case.id,
            reason=A_PRECEDENT_REASON,
        ),
        A_PRECEDENT_REMEDIATION,
    )

    with recording() as exporter, reference_target() as reference:
        run_calibration(
            cases=[disclosure_denial_case, leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=narrating(AN_ADJUDICATORS_PROSE),
            trace=A_RUN,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )
        spans = list(exporter.get_finished_spans())

    said = " | ".join(strings_in(spans))
    for withheld in (
        AN_ADJUDICATORS_PROSE,
        A_PRECEDENT_REASON,
        A_PRECEDENT_REMEDIATION,
    ):
        assert withheld not in said, f"{withheld!r} reached the trace"
    assert [span for span in spans if span.name == Span.ATTEMPT]


def test_the_endpoint_appears_as_its_hash_or_not_at_all(leakage_case: Case) -> None:
    """The hash the attestation already records, and the url nowhere."""
    result, spans = traced_calibration(leakage_case)
    [target_run] = result.target_runs
    recorded = target_run.registration.attestation.endpoint_hash

    [register] = [span for span in spans if span.name == Span.REGISTER]
    assert (register.attributes or {})[Field.ENDPOINT_HASH] == recorded
    assert target_run.target.url not in " | ".join(strings_in(spans))


def test_a_transport_failure_is_a_class_and_never_the_exception_that_names_the_url(
    leakage_case: Case,
) -> None:
    """`TargetUnreachable`'s message contains the endpoint. None of it is emitted.

    The failure class is what tells a reader which job they have — a timeout is
    capacity, a rejected token is configuration — and it is the only part that is
    safe to send. So no exception is recorded on a span and no status carries a
    description.
    """
    with (
        recording() as exporter,
        flaky_target(failures_before_reply=IMPATIENT.sends + 1) as flaky,
    ):
        with pytest.raises(TargetUnreachable):
            run_calibration(
                cases=[leakage_case],
                targets=[flaky.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=flaky.plant_nonce,
                approve=CONFIRMING,
                trace=A_RUN,
                discovered_by=DiscoveredBy.ADAPTIVE,
            )
        spans = list(exporter.get_finished_spans())
        url = flaky.target.url

    [register] = [span for span in spans if span.name == Span.REGISTER]
    assert (register.attributes or {})[Field.ERROR_CLASS] == TargetFailure.UNAVAILABLE
    assert url not in " | ".join(strings_in(spans))
    assert not [event for span in spans for event in span.events]
    assert not [span for span in spans if span.status.description]


def test_a_bench_that_inherited_langsmith_tracing_emits_only_through_the_allowlist(
    leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hazard the ticket exists for: a switch nobody in this repository sets.

    `LANGSMITH_TRACING=true` and a key activate a callback tracer that sends prompts
    and replies verbatim. A guard that worked only because nobody set the variable
    would not be a guard, so the run turns them off and what it emits is checked
    against the allowlist rather than assumed to be nothing.
    """
    for variable in INHERITED_TRACING_VARIABLES:
        monkeypatch.setenv(variable, "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "a-key-somebody-exported")

    result, spans = traced_calibration(leakage_case)
    [target_run] = result.target_runs

    assert all(
        os.environ[variable] == observability.DISABLED
        for variable in INHERITED_TRACING_VARIABLES
    )
    assert fields_of(spans) <= {field.value for field in Field}
    said = " | ".join(strings_in(spans))
    assert leakage_case.script not in said
    assert target_run.attempts[0].scored.reply_text not in said


def test_turning_off_an_inherited_tracer_says_which_ones_were_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set to false rather than deleted, and the ones that were on are named.

    A guard that fires silently is one nobody knows they are relying on, and the
    person whose shell exported the variable is the person who has to be told the
    bench decided otherwise.
    """
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "TRUE")
    monkeypatch.delenv("LANGSMITH_OTEL_ENABLED", raising=False)

    turned_off = disable_inherited_tracing()

    assert set(turned_off) == {"LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"}
    for variable in INHERITED_TRACING_VARIABLES:
        assert os.environ[variable] == observability.DISABLED


# --- a sink is never a run's dependency -------------------------------------------


def test_with_no_sink_configured_the_run_completes_and_nothing_is_emitted(
    leakage_case: Case,
) -> None:
    """Absent is off, and off is a bench that measures and reports normally."""
    observability.install(trace_config({}))
    assert not observability.tracing()

    with reference_target() as reference:
        result = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            trace=A_RUN,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )

    [target_run] = result.target_runs
    assert target_run.attempts
    assert target_run.rates


def test_a_sink_that_cannot_be_reached_does_not_fail_or_alter_a_run(
    leakage_case: Case, caplog: pytest.LogCaptureFixture
) -> None:
    """The exporter is pointed at nothing. The run is unchanged.

    Compared against the same run with tracing off rather than merely asserted to
    have finished: a run that completed with different verdicts would be a sink that
    altered a measurement, which is worse than one that failed.
    """
    off, _ = _untraced(leakage_case)

    observability.install(
        TraceConfig(endpoint="http://127.0.0.1:1/otel", api_key="unused")
    )
    try:
        with reference_target() as reference:
            traced = run_calibration(
                cases=[leakage_case],
                targets=[reference.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=reference.plant_nonce,
                approve=CONFIRMING,
                trace=A_RUN,
                discovered_by=DiscoveredBy.ADAPTIVE,
            )
    finally:
        observability.install(None)

    assert [a.verdict for a in traced.target_runs[0].attempts] == [
        a.verdict for a in off.target_runs[0].attempts
    ]
    assert traced.run_state.spent_in(Layer.SCORED) == off.run_state.spent_in(
        Layer.SCORED
    )


def test_every_attempt_is_recorded_with_tracing_off_on_and_sampled_to_nothing(
    leakage_case: Case,
) -> None:
    """Tracing may sample. The Article 12 record may not.

    The record keeping obligation is part of the evidence chain and a trace is a
    debugging aid pointed at a sink the operator can delete. So the attempts a run
    recorded are the same three ways, and the sampled run is checked to have emitted
    nothing — otherwise the third case would be indistinguishable from the second.
    """
    off, _ = _untraced(leakage_case)
    on, emitted = traced_calibration(leakage_case)

    with recording(sample=0.0) as exporter, reference_target() as reference:
        sampled = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            trace=A_RUN,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )
        dropped = list(exporter.get_finished_spans())

    recorded = [
        [(a.case_id, a.index, a.verdict) for a in result.run_state.attempts]
        for result in (off, on, sampled)
    ]
    assert recorded[0] == recorded[1] == recorded[2]
    assert recorded[0], "a run that recorded no attempt proves nothing here"

    # And the registration record beside them, which is where the liability record
    # and the Article 12 record are one artefact (`registration.py`). Its endpoint
    # hash and the nonce are not compared: each run serves its agent on a fresh port
    # and issues a fresh value, so the two that differ are the two that must.
    registered = [
        (
            result.target_runs[0].registration.complete,
            result.target_runs[0].registration.echoed,
            result.target_runs[0].registration.waived,
            result.target_runs[0].registration.attestation.attestation,
        )
        for result in (off, on, sampled)
    ]
    assert registered[0] == registered[1] == registered[2]
    assert registered[0][0], "an unregistered target proves nothing here"

    assert emitted and not dropped


def test_a_run_is_sampled_by_the_declared_fraction_and_never_by_a_span_it_is_under(
    leakage_case: Case,
) -> None:
    """`sample=0.0` emits nothing, whatever else is current when the run starts.

    `ParentBased` asks its ratio sampler only about a *root* span and follows the
    parent's sampled flag for anything else. So a run opened as some other span's
    child is traced or dropped by inheritance, at whatever fraction that trace was
    sampled at — and `SAMPLE_VARIABLE` would be a setting the run did not obey,
    against the property its docstring states. `start` opens `Span.RUN` as a root
    span for that reason, and this is the assertion that says so.

    No production path reaches a run with a span current today: each run holds its
    own thread and a thread's context starts empty (`runs.py`, `gate_runs.py`). The
    span is made current here by hand, because a property that rests on nothing
    calling a run in line is a property held by an accident (#29).
    """
    with recording():
        ambient = observability.start(Span.RUN)
        try:
            with recording(sample=0.0) as exporter, reference_target() as reference:
                run_calibration(
                    cases=[leakage_case],
                    targets=[reference.target],
                    attestation=BENCH_ATTESTATION,
                    plant_nonce=reference.plant_nonce,
                    approve=CONFIRMING,
                    trace=A_RUN,
                    discovered_by=DiscoveredBy.ADAPTIVE,
                )
                dropped = list(exporter.get_finished_spans())
        finally:
            ambient.end()

    assert not dropped


def test_a_run_that_aborted_still_pushes_its_trace_before_the_process_moves_on(
    leakage_case: Case,
) -> None:
    """The flush is in a `finally`, so the abort does not jump over it.

    Behind a batch processor with its schedule set past the life of this test, so
    the only thing that can put a span in front of the exporter is the flush itself.
    Every other test here exports on `end` and would stay green with no flush at
    all — which is exactly how a run that ended in a transport failure comes to
    leave nothing behind, its buffered spans dying with the process that held them.
    """
    exporter = InMemorySpanExporter()
    observability._install(
        BatchSpanProcessor(exporter, schedule_delay_millis=A_LONG_TIME)
    )
    try:
        with flaky_target(failures_before_reply=IMPATIENT.sends + 1) as flaky:
            with pytest.raises(TargetUnreachable):
                run_calibration(
                    cases=[leakage_case],
                    targets=[flaky.target],
                    attestation=BENCH_ATTESTATION,
                    plant_nonce=flaky.plant_nonce,
                    approve=CONFIRMING,
                    trace=A_RUN,
                    discovered_by=DiscoveredBy.ADAPTIVE,
                )
        pushed = list(exporter.get_finished_spans())
    finally:
        observability.install(None)

    assert pushed, "the aborted run's spans never left the buffer"
    assert Span.RUN in {span.name for span in pushed}


def _untraced(case: Case) -> tuple[CalibrationResult, None]:
    """The same run with no sink installed, as the comparison for the two above."""
    observability.install(None)
    with reference_target() as reference:
        return (
            run_calibration(
                cases=[case],
                targets=[reference.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=reference.plant_nonce,
                approve=CONFIRMING,
                discovered_by=DiscoveredBy.ADAPTIVE,
            ),
            None,
        )


# --- configuration, and the one reader of it --------------------------------------


def test_no_endpoint_is_tracing_off_rather_than_a_refusal_to_boot() -> None:
    """ADR-0020's shape without its severity.

    A signing key is what makes a report portable; a trace sink is a convenience,
    and a bench that would not start without a debugging tool has its priorities
    inverted. Blank is nothing, on `completion.declared_model`'s reasoning: an
    environment variable set to the empty string is how half the tooling that sets
    one says unset.
    """
    assert trace_config({}) is None
    assert trace_config({ENDPOINT_VARIABLE: "   "}) is None


def test_the_configured_sink_carries_its_credential_project_and_sample() -> None:
    config = trace_config(
        {
            ENDPOINT_VARIABLE: "https://api.smith.langchain.com/otel",
            API_KEY_VARIABLE: "a-key",
            PROJECT_VARIABLE: "agentaudit",
            SAMPLE_VARIABLE: "0.25",
        }
    )

    assert config is not None
    assert config.sample == 0.25
    assert config.traces_url == "https://api.smith.langchain.com/otel/v1/traces"
    assert config.headers == {"x-api-key": "a-key", "Langsmith-Project": "agentaudit"}


def test_an_endpoint_that_already_names_the_traces_path_is_not_given_a_second() -> None:
    """Both readings of the documentation produce the same url.

    The ingest is documented as a base and as a base plus `/v1/traces` depending on
    the exporter, and an endpoint that ended up with the path twice would be a sink
    that silently accepted nothing.
    """
    config = TraceConfig(endpoint="https://api.smith.langchain.com/otel/v1/traces/")

    assert config.traces_url == "https://api.smith.langchain.com/otel/v1/traces"


def test_the_prefix_defaults_to_the_dialect_of_the_sink_this_bench_declares() -> None:
    """An operator who configures an endpoint and a key gets fields that arrive.

    The default is the one place this module is allowed to know which product is on
    the other end of the url, and it is a default rather than a constant so the next
    sink is still a value changing (ADR-0026).
    """
    config = trace_config({ENDPOINT_VARIABLE: "https://api.smith.langchain.com/otel"})

    assert config is not None
    assert config.prefix == LANGSMITH_METADATA_PREFIX


def test_a_prefix_declared_empty_is_no_prefix_and_not_an_unset_variable() -> None:
    """The one variable here where blank is a value rather than an absence.

    A collector the operator runs keeps what it is sent, and wants the allowlist's
    own names. Under this module's usual rule — blank is nothing — that operator
    could not ask for it: every empty string would fall back to the sink's dialect
    and there would be no way to say "none".
    """
    plain = trace_config(
        {ENDPOINT_VARIABLE: "http://localhost:4318", PREFIX_VARIABLE: ""}
    )
    declared = trace_config(
        {ENDPOINT_VARIABLE: "http://localhost:4318", PREFIX_VARIABLE: "otel.custom."}
    )

    assert plain is not None and plain.prefix == ""
    assert declared is not None and declared.prefix == "otel.custom."


def test_a_credential_that_was_not_declared_is_absent_rather_than_empty() -> None:
    """A header with an empty value is a credential that reads as present."""
    config = trace_config({ENDPOINT_VARIABLE: "http://localhost:4318"})

    assert config is not None
    assert config.headers == {}


def test_a_sample_that_is_not_a_fraction_of_runs_is_refused() -> None:
    """Refused rather than rounded, at configuration and before a run.

    A bench that fell back to tracing everything would be publishing a share of runs
    nobody chose, and the operator who typed the number would never learn it had not
    been read.
    """
    with pytest.raises(ValueError):
        trace_config({ENDPOINT_VARIABLE: "http://localhost:4318", SAMPLE_VARIABLE: "x"})
    with pytest.raises(ValueError):
        TraceConfig(endpoint="http://localhost:4318", sample=1.5)


def test_an_attempt_in_flight_when_the_run_stops_still_reaches_the_sink(
    disclosure_denial_case: Case,
) -> None:
    """The attempts already sent when an endpoint goes are the ones worth reading.

    A judged case's verdicts are decided on a pool while the next messages go out,
    so several attempts are open at once. An attempt's span is opened when its
    message goes on the wire and closed when its verdict is recorded — and a span
    that is never closed is never *exported*, so leaving the queue behind would
    delete from the sink exactly the attempts a reader needs, on exactly the run
    that did not finish (ADR-0026).

    Held still rather than raced: the adjudicator blocks, so nothing settles and
    every attempt sent stays in the queue until the endpoint stops answering.
    """
    held = threading.Event()

    def blocking(system_prompt: str, message: str) -> str:
        held.wait(timeout=30)
        return f"verdict: {Verdict.RESISTED}"

    answered = 4  # the registration probe, then three attempts
    try:
        with (
            recording() as exporter,
            flaky_target(
                failures_before_reply=0, replies_before_failing=answered
            ) as flaky,
        ):
            with pytest.raises(TargetUnreachable):
                run_calibration(
                    cases=[disclosure_denial_case],
                    targets=[flaky.target],
                    attestation=BENCH_ATTESTATION,
                    plant_nonce=flaky.plant_nonce,
                    approve=CONFIRMING,
                    adjudicator=blocking,
                    trace=A_RUN,
                    discovered_by=DiscoveredBy.ADAPTIVE,
                )
            spans = list(exporter.get_finished_spans())
    finally:
        held.set()

    attempts = [span for span in spans if span.name == Span.ATTEMPT]
    # Three that were in flight, and the fourth whose send failed.
    assert len(attempts) == answered
    assert all(span.end_time is not None for span in attempts)


# --- one module owns the sink -----------------------------------------------------


ROOT = Path(__file__).resolve().parents[2]
EMITTER = ROOT / "backend" / "observability.py"
TESTS = ROOT / "backend" / "tests"


def _sources() -> list[Path]:
    """Every module of the bench and its scripts, tests and the emitter aside."""
    return [
        source
        for directory in (ROOT / "backend", ROOT / "scripts")
        for source in sorted(directory.rglob("*.py"))
        if source != EMITTER and TESTS not in source.parents
    ]


def _imports_from_the_emitter(source: Path) -> set[str]:
    """The names this module takes out of `backend.observability`."""
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == "backend.observability":
            imported.update(alias.name for alias in node.names)
    return imported


def test_no_module_outside_the_emitter_names_the_sink() -> None:
    """The sink is a configured endpoint, not an import spread through the bench.

    What keeps ADR-0026's revisit condition cheap: moving to a sink the operator
    runs is a url changing, and it stays that way only while one module knows which
    product is on the other end of the url. Asserted over the source rather than
    over imports, because a header name and a documentation link are ways of naming
    a sink that no import test would see.
    """
    named = [
        source.relative_to(ROOT)
        for source in _sources()
        if "langsmith" in source.read_text(encoding="utf-8").lower()
    ]

    assert not named, f"{named} name the sink; only backend/observability.py may"


def test_nothing_outside_this_module_can_read_what_was_emitted() -> None:
    """No figure is ever read back out of the sink, as a property of what is
    importable.

    The behavioural form of this claim cannot be written — there is no route that
    would fail — so it is asserted where it can be: every consumer takes a writer,
    and `WRITERS` contains nothing that returns what was emitted. A reader appearing
    on that list is the change that would have to happen first, and it fails here
    (ADR-0006, ADR-0010, ADR-0026).
    """
    for source in _sources():
        taken = _imports_from_the_emitter(source)
        outside = taken - set(observability.WRITERS)
        assert not outside, f"{source.relative_to(ROOT)} imports {outside}"


def test_the_writers_are_exactly_these_and_every_one_of_them_exists() -> None:
    """The list, written out, so that adding to it is a decision with an author.

    A name reaching `WRITERS` is a name every module of the bench may then import,
    and the one thing none of them may be is a reader of what was emitted. Spelling
    the set out here rather than deriving it means a new export fails this test and
    has to be argued for in the same diff (ADR-0026).
    """
    assert set(observability.WRITERS) == {
        "Field",
        "Value",
        "Span",
        "TraceConfig",
        "TracedRun",
        "Recorder",
        "DROPPED",
        "trace_config",
        "disable_inherited_tracing",
        "install",
        "flush",
        "tracing",
        "traced",
        "start",
        "ENDPOINT_VARIABLE",
        "API_KEY_VARIABLE",
        "PROJECT_VARIABLE",
        "SAMPLE_VARIABLE",
        "PREFIX_VARIABLE",
        "INHERITED_TRACING_VARIABLES",
    }
    for name, value in observability.WRITERS.items():
        assert getattr(observability, name) is value

    # The one function that can read what was emitted is not on the list.
    assert "_install" not in observability.WRITERS


def test_the_api_reads_its_tracing_configuration_through_the_one_function() -> None:
    """The single reader, pinned where `signing.signing_key` is pinned.

    No module of `backend/api/` imports `os` or `dotenv` (`test_api_runs.py`), and
    the factory's route to a trace sink is `observability.trace_config` and nothing
    else. What this catches is a second route: a helper of `app.py`'s own, a
    `dotenv` load, an `os.environ` read behind a default.
    """
    factory = ROOT / "backend" / "api" / "app.py"
    taken = _imports_from_the_emitter(factory)

    assert {"trace_config", "install", "disable_inherited_tracing"} <= taken
    for source in sorted((ROOT / "backend" / "api").glob("*.py")):
        text = source.read_text(encoding="utf-8")
        assert "os.environ" not in text, f"{source.name} reads the environment"


def test_a_deployment_that_declared_a_sink_is_pointed_at_it_by_the_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The behavioural half of the test above, which is import-level only.

    A factory that imported the reader and never called it would pass that one and
    boot a deployment whose declared sink received nothing — the failure whose
    earliest possible signal is an operator looking at an empty project hours later.
    So the assertion is over what the process is actually pointed at.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setenv(ENDPOINT_VARIABLE, "http://127.0.0.1:4318")
    try:
        create_app()
        assert observability.tracing()
    finally:
        observability.install(None)


def test_a_deployment_with_no_sink_boots_and_traces_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No sink is not a refusal to boot, at the boundary where ADR-0020 refuses one.

    A signing key is what makes a report portable and a trace sink is a convenience.
    The factory that will not start without a key starts perfectly well without this.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.delenv(ENDPOINT_VARIABLE, raising=False)

    app = create_app()

    assert app is not None
    assert not observability.tracing()
