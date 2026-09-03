"""What a run started over HTTP says it consumed.

The figures #9 and #10 built reached a trace from a script and nowhere else. A
usage sink is fixed when a client is built — `completion_for(..., usage=...)` — and
the API built its instruments once, at boot, before any run existed; so a run
started from the console held a ledger that reported nothing, and its trace
correctly emitted no token figure rather than a zero. Every consequence was
behaving as designed, and the design stopped one layer short of the console (#28).

These tests are about the layer that was missing, and the concurrency one is the
reason the fix is a per-run *build* rather than a per-run *assignment*. The API runs
each run on its own thread. A sink the clients share — a module global, a slot on a
client, a `ContextVar` that a `ThreadPoolExecutor` does not carry — files one run's
tokens under another run's id, and a figure filed against the wrong run is worse
than an absent one (ADR-0026). So the two runs here report *different* figures per
call, and each run's trace is asserted to carry only its own: a stand-in that
reported the same number for every run would pass against a shared ledger.

Nothing here reaches a real provider. What a router would say it charged is not
under test — that would be OpenRouter's accounting rather than this bench's
plumbing, and it would put an attack payload on somebody's wire to prove it
(`test_observability.py` states the same for the same reason).
"""

import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan

from backend.api import runs
from backend.api.app import GATE_RUNS_ROUTE, create_app
from backend.api.gate_runs import BenchGateRuns, GateRunBench, shipped_agents
from backend.api.report import ReportConfig
from backend.api.runs import (
    BenchConfig,
    BenchRuns,
    Instruments,
    PerRunInstruments,
    RunStatus,
)
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adaptive.tools import ToolInvocation
from backend.bench.adjudication import Completion
from backend.bench.completion import ADJUDICATOR_MODEL_ENV, ATTACKER_MODEL_ENV
from backend.bench.evaluator import Verdict
from backend.bench.library import Case
from backend.bench.narration import Narrator
from backend.bench.payload import DeclaredModels
from backend.bench.rule import DECLARED_RULE
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.bench.usage import DISCARDED, ModelUsage, UsageLedger, UsageSink
from backend.graph.budget import Layer
from backend.observability import Field, Span
from backend.tests.conftest import ADJUDICATING, authored_library, stop_every_run
from backend.tests.test_api_gate_runs import (
    SETTLED as GATE_SETTLED,
)
from backend.tests.test_api_gate_runs import (
    a_confirmation,
    a_gate_request,
)
from backend.tests.test_api_runs import (
    AN_ADJUDICATING_MODEL,
    AN_ATTACKING_MODEL,
    DEPLOYMENT_VARIABLES,
    a_request,
    registered,
    watched_reference,
)
from backend.tests.test_observability import recording

ONE_ATTEMPT = replace(DECLARED_RULE, attempts_per_case=1)
"""One attempt per case, so a run's scored model calls are countable by hand.

Exactness is the point of it. A judged case at one attempt is one adjudication, so
the token figure a run's trace carries is the figure one call reported and not a
sum a reader has to trust — which is what lets the concurrency test below assert
that a run carried *only* its own.
"""

A_SMALL_LAYER = AdaptiveBudget(turns_per_episode=2, episodes_per_family=1)
"""The adaptive layer, narrowed so these tests are minutes shorter and no weaker.

Narrowed rather than switched off: the layer's own instrument is half of what is
under test here, and its tokens must land in the adaptive bucket and no other
(ADR-0010)."""

A_STEP = 1_000
ANOTHER_STEP = 7
"""What one stood-in call reports, for the first run and for the second.

Two figures rather than one, and deliberately not near neighbours. A shared ledger
gives each run the sum of the two, and a sum is only distinguishable from a
run's own figure when the figures differ — a stand-in reporting the same count for
every run would trace identically whether the ledger was shared or not, which is
the test passing for the wrong reason.

`1_000` and `7` also make the adaptive layer's totals readable without counting its
calls: a multiple of one is not a multiple of the other, so a layer's sum says
which run's instruments produced it (`only_its_own`).
"""


def cost_of(step: int) -> Decimal:
    """What one call at that step reports as its provider cost.

    Through `Decimal` and never `float`: a cost this bench records has to be the
    figure the provider named (`usage._reported_decimal`).
    """
    return Decimal(step) / Decimal(1_000_000)


def a_reported_call(step: int) -> ModelUsage:
    """One model call as `usage.usage_from` would have read it off a response."""
    return ModelUsage(
        requested_model="stub:reporting",
        latency_seconds=0.01,
        input_tokens=step,
        output_tokens=step,
        reasoning_tokens=step,
        provider_cost=cost_of(step),
    )


def adjudicating(sink: UsageSink, step: int) -> Completion:
    """An adjudicator that reports what it consumed, beside the verdict it returns.

    Beside and never inside: `Completion` stays `(system_prompt, message) -> str`,
    because an instrument that could see a token count is one whose verdict is no
    longer derivable from the record a reader holds (ADR-0004).
    """

    def complete(system_prompt: str, message: str) -> str:
        sink.record(a_reported_call(step))
        return f"verdict: {Verdict.RESISTED}"

    return complete


def attacking(sink: UsageSink, step: int) -> Any:
    """The adaptive attacker, reporting into the adaptive layer and no other."""

    def attack(system_prompt: str, brief: str) -> ToolInvocation | None:
        sink.record(a_reported_call(step))
        return SCRIPTED_ATTACKER(system_prompt, brief)

    return attack


class Instrumenting:
    """A bench's per-run instrument builder, standing in for the deployed one.

    It is the seam `app.declared_instruments` fills on a real deployment, and it
    stands in for the same reason every other instrument in this suite is stood in
    for: what is under test is the plumbing around a model call and not a model.

    **Each build reports a different figure**, taken from `steps` in the order the
    builds arrive. Which run gets which is not asserted and cannot be — two runs
    starting at once reach this on two threads — so the assertions are that each
    run carries one of the figures, that the two runs carry different ones, and
    that every other figure on a run's span is a multiple of the one it carries.

    It keeps the ledgers it was handed, because *one ledger per run* is the half of
    the fix that no figure on a span can show: two builds that were handed the same
    object would trace correctly right up to the moment the two runs overlapped.
    """

    def __init__(self, steps: Sequence[int] = (A_STEP,)) -> None:
        self._steps = tuple(steps)
        self._lock = threading.Lock()
        self.ledgers: list[UsageLedger] = []

    def __call__(self, models: DeclaredModels, usage: UsageLedger) -> Instruments:
        with self._lock:
            step = self._steps[len(self.ledgers) % len(self._steps)]
            self.ledgers.append(usage)
        return Instruments(
            adjudicator=adjudicating(usage.for_layer(Layer.SCORED), step),
            attacker=attacking(usage.for_layer(Layer.ADAPTIVE), step),
            # No narrator: what these tests follow is a token count from an
            # instrument to a span, and the narrative pass has its own file
            # (`test_narration.py`).
            narrator=None,
        )


@contextmanager
def api(
    cases: list[Case], instruments: PerRunInstruments | None
) -> Iterator[tuple[TestClient, BenchRuns]]:
    """The API over a bench whose runs build their own instruments.

    `instruments=None` is the bench that has none — the boot-built pair and nothing
    bound to a run — which is what the console shipped before #28 and is what one
    test here asserts is now the only way to get an unfigured trace.
    """
    app = create_app(
        BenchConfig(
            cases=cases,
            rule=ONE_ATTEMPT,
            adaptive=A_SMALL_LAYER,
            # The boot-time pair, unbound, exactly as a deployment builds it: it is
            # what `plan_for` reads to decide the judged families run at all, and
            # the per-run build is refused if it disagrees with it.
            adjudicator=ADJUDICATING,
            per_run_instruments=instruments,
            approval_wait_seconds=60.0,
            report=ReportConfig(),
        )
    )
    with TestClient(app) as client:
        try:
            yield client, cast(BenchRuns, app.state.bench)
        finally:
            stop_every_run(client)


def approve(client: TestClient, run_id: str) -> None:
    client.post(
        f"/runs/{run_id}/approval", json={"confirmed": True, "identity": "operator"}
    )


def settled(bench: BenchRuns, run_id: str, seconds: float = 120.0) -> RunStatus:
    """Wait for one run to reach a state it does not leave."""
    record = bench.record(run_id)
    assert record is not None
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not record.status.in_flight:
            return record.status
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} is still {record.status}")


def run_span(spans: Sequence[ReadableSpan], run_id: str) -> ReadableSpan:
    """The root span of that run, out of everything the sink was given."""
    found = [
        span
        for span in spans
        if span.name == Span.RUN and (span.attributes or {}).get(Field.RUN_ID) == run_id
    ]
    assert len(found) == 1, f"{len(found)} run spans carry the id {run_id}"
    return found[0]


TOKENS_AND_COST = (
    (Field.INPUT_TOKENS_SCORED, Field.INPUT_TOKENS_ADAPTIVE),
    (Field.OUTPUT_TOKENS_SCORED, Field.OUTPUT_TOKENS_ADAPTIVE),
    (Field.REASONING_TOKENS_SCORED, Field.REASONING_TOKENS_ADAPTIVE),
)
"""The three token readings, each per layer. Cost is asserted apart: it is a
string on a span rather than an integer, because a decimal the provider named is
not a float (ADR-0026)."""


def only_its_own(span: ReadableSpan, steps: Sequence[int]) -> int:
    """The step this run's instruments reported, and nothing another run's did.

    Every figure on the span has to be a whole number of *one* of the steps, and
    the same one throughout. A run whose trace carried another run's calls carries
    a sum, and a sum of two of these figures is a multiple of neither — which is
    the whole of what makes a shared ledger visible from the outside.
    """
    attributes = span.attributes or {}
    scored = attributes[Field.INPUT_TOKENS_SCORED]
    assert scored in steps, (
        f"the scored layer reported {scored}, which is no run's own figure: this "
        f"trace is carrying calls from more than one run's instruments {steps}"
    )
    step = int(cast(int, scored))
    for figure in (field for pair in TOKENS_AND_COST for field in pair):
        reading = attributes[figure]
        assert isinstance(reading, int) and reading % step == 0, (
            f"{figure} reads {reading}, which is not a whole number of this run's "
            f"own {step}-token calls"
        )
    assert attributes[Field.PROVIDER_COST_SCORED] == str(cost_of(step))
    return step


# --- a run started over HTTP -----------------------------------------------------


def test_a_run_started_over_http_carries_the_tokens_and_cost_it_consumed(
    disclosure_denial_case: Case, leakage_case: Case
) -> None:
    """The figures reach the trace of a run nobody started from a terminal.

    Two cases, because both layers have to consume something: the judged one calls
    the adjudicator and the deterministic one gives the adaptive layer a family to
    open an episode against.

    This is the test that fails if a run's instruments are unbound. Before #28 the
    API's clients were built at boot with no sink, the run's ledger reported
    nothing, and the trace emitted no figure rather than a zero — every one of
    these keys was absent.
    """
    instruments = Instrumenting()
    with (
        # The bench first and the sink second, in that order: `create_app` points
        # this process at whatever sink the environment declares, so an exporter
        # installed before it would be the one replaced (`app.install`).
        api([disclosure_denial_case, leakage_case], instruments) as (client, bench),
        recording() as exporter,
        watched_reference() as watched,
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        run_id = str(started["run_id"])
        approve(client, run_id)
        assert settled(bench, run_id) is RunStatus.COMPLETED
        spans = list(exporter.get_finished_spans())

    attributes = run_span(spans, run_id).attributes or {}
    for scored, adaptive in TOKENS_AND_COST:
        assert attributes[scored] == A_STEP, (
            f"{scored} is absent or wrong: one judged attempt is one adjudication, "
            "and this run's adjudicator reported what that call consumed"
        )
        # The adaptive layer's own figure, under its own key. How many turns it
        # took is the layer's business and not this test's, so what is asserted is
        # that it consumed something and that it landed in its own bucket.
        assert isinstance(attributes[adaptive], int)
        assert cast(int, attributes[adaptive]) >= A_STEP
    assert attributes[Field.PROVIDER_COST_SCORED] == str(cost_of(A_STEP))
    assert attributes[Field.PROVIDER_COST_ADAPTIVE]
    # Every call reported, so nothing is missing from either total. Asserted
    # because a partial total is a fact a reader needs and a zero here is the
    # statement that the figures above cover the whole layer (`usage.LayerTotals`).
    assert attributes[Field.CALLS_WITHOUT_TOKENS_SCORED] == 0
    assert attributes[Field.CALLS_WITHOUT_COST_SCORED] == 0

    # And one ledger, built for this run and handed to it.
    assert len(instruments.ledgers) == 1
    [ledger] = instruments.ledgers
    assert ledger.totals_in(Layer.SCORED).input_tokens == A_STEP


def test_a_bench_whose_runs_build_no_instruments_still_reports_no_figure(
    disclosure_denial_case: Case, leakage_case: Case
) -> None:
    """A bench with nothing bound emits no token figure, and never a zero.

    The other side of the one above, and the reason `per_run_instruments` is an
    absence a caller can state rather than a default nobody chose: a stub
    adjudicator has no provider to report a token count, so a bench built with one
    keeps no usage and says so by carrying no figure. A `0` would be a number this
    bench invented and then joined to a run id (ADR-0026, `bench/usage.py`).
    """
    with (
        api([disclosure_denial_case, leakage_case], None) as (client, bench),
        recording() as exporter,
        watched_reference() as watched,
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        run_id = str(started["run_id"])
        approve(client, run_id)
        assert settled(bench, run_id) is RunStatus.COMPLETED
        spans = list(exporter.get_finished_spans())

    attributes = run_span(spans, run_id).attributes or {}
    for scored, adaptive in TOKENS_AND_COST:
        assert scored not in attributes and adaptive not in attributes
    assert Field.PROVIDER_COST_SCORED not in attributes
    # The calls the run spent are still there. What is absent is what nothing
    # reported, and not the run's shape.
    assert cast(int, attributes[Field.CALLS_SCORED]) > 0


def test_two_concurrent_runs_each_carry_only_their_own_figures(
    disclosure_denial_case: Case, leakage_case: Case
) -> None:
    """Two runs at once, two ledgers, and neither trace holds the other's tokens.

    The test the design turns on. Each run happens on its own thread, so any sink
    the clients shared — a process global, a mutable slot on a client, a
    `ContextVar` a `ThreadPoolExecutor` drops (#10) — would put both runs' calls in
    both runs' totals. Both runs are started before either is approved, so both are
    past `run_calibration`'s one-ledger guard before either records a call: a
    shared ledger would not be refused here, it would be *summed*, which is the
    failure worth a test rather than the one an exception already covers.

    The two runs report different figures per call for that reason, and the
    assertion is that each trace is a whole number of its own and that the two are
    not the same figure. A shared ledger gives both spans `1007`, which is neither.
    """
    instruments = Instrumenting(steps=(A_STEP, ANOTHER_STEP))
    cases = [disclosure_denial_case, leakage_case]
    with (
        api(cases, instruments) as (client, bench),
        recording() as exporter,
        ExitStack() as stack,
    ):
        # Two targets rather than one, because a nonce is planted per agent and a
        # second run planting its own in the same agent would unregister the first.
        targets = [
            stack.enter_context(watched_reference(name=name))
            for name in ("trivial", "weak")
        ]
        run_ids = []
        for watched in targets:
            nonce = registered(client, watched)
            started = client.post("/runs", json=a_request(watched.target, nonce)).json()
            run_ids.append(str(started["run_id"]))

        # Both waiting at their own halt, and only then answered. Nothing has been
        # sent to either target yet, so both are inside `run_calibration` and past
        # the guard that refuses a ledger already holding calls.
        for run_id in run_ids:
            assert bench.record(run_id) is not None
        for run_id in run_ids:
            approve(client, run_id)
        for run_id in run_ids:
            assert settled(bench, run_id) is RunStatus.COMPLETED
        spans = list(exporter.get_finished_spans())

    assert len(instruments.ledgers) == 2
    first, second = instruments.ledgers
    assert first is not second, "two runs were handed one ledger"

    steps = [
        only_its_own(run_span(spans, run_id), (A_STEP, ANOTHER_STEP))
        for run_id in run_ids
    ]
    assert sorted(steps) == sorted((A_STEP, ANOTHER_STEP)), (
        "the two runs carried the same figure, so this test could not have told a "
        "shared ledger from two"
    )


# --- a gate run started from the console -----------------------------------------


@contextmanager
def a_gate_bench(
    library: Path, instruments: Instrumenting
) -> Iterator[tuple[TestClient, BenchGateRuns]]:
    """A bench that can run a gate, and whose gate run builds its instruments."""
    app = create_app(
        BenchConfig(
            cases=[],
            rule=ONE_ATTEMPT,
            adaptive=A_SMALL_LAYER,
            adjudicator=ADJUDICATING,
            per_run_instruments=instruments,
            approval_wait_seconds=60.0,
            report=ReportConfig(),
        ),
        GateRunBench(library=library, equipment=shipped_agents("stub:obedient")),
    )
    with TestClient(app) as client:
        try:
            yield client, cast(BenchGateRuns, app.state.gate_runs)
        finally:
            stop_every_run(client)


def test_a_gate_run_started_from_the_console_carries_its_own_figures(
    tmp_path: Path,
) -> None:
    """The expensive run is the one the figures matter most for.

    A gate run is around 830 calls against three agents, it is the run an operator
    is most likely to start from the console rather than a terminal, and until #28
    it was the one that carried no token figure at all — the same boot-built
    instruments, through the other entry point.

    Asserted as a multiple of the reported call rather than as an exact total: how
    many judged attempts six families over three agents come to is the library's
    arithmetic and not this test's subject.
    """
    instruments = Instrumenting()
    library = authored_library(tmp_path / "cases")
    with (
        a_gate_bench(library, instruments) as (client, gates),
        recording() as exporter,
    ):
        body = client.post(GATE_RUNS_ROUTE, json=a_gate_request())
        assert body.status_code == 202, body.text
        gate_run_id = str(body.json()["gate_run_id"])
        client.post(f"{GATE_RUNS_ROUTE}/{gate_run_id}/approval", json=a_confirmation())
        [record] = gates.records()
        deadline = time.monotonic() + 300.0
        while record.status not in GATE_SETTLED and time.monotonic() < deadline:
            time.sleep(0.05)
        assert record.status in GATE_SETTLED, f"gate run is still {record.status}"
        spans = list(exporter.get_finished_spans())

    [root] = [
        span
        for span in spans
        if span.name == Span.RUN
        and (span.attributes or {}).get(Field.GATE_RUN_ID) == gate_run_id
    ]
    attributes = root.attributes or {}
    for scored, adaptive in TOKENS_AND_COST:
        for figure in (scored, adaptive):
            reading = attributes[figure]
            assert isinstance(reading, int) and reading > 0
            assert reading % A_STEP == 0, (
                f"{figure} reads {reading}, which is not a whole number of this "
                "gate run's own calls"
            )
    assert attributes[Field.PROVIDER_COST_SCORED]
    assert len(instruments.ledgers) == 1


# --- the boot-time pair, and what it is still for --------------------------------


def unadjudicating(models: DeclaredModels, usage: UsageLedger) -> Instruments:
    """A builder that hands back no adjudicator, whatever the bench declared."""
    return Instruments(adjudicator=None, attacker=SCRIPTED_ATTACKER, narrator=None)


def test_a_per_run_build_that_disagrees_with_the_boot_pair_is_refused() -> None:
    """The two statements about whether the judged families run have to agree.

    `plan_for` reads `config.adjudicator` to decide which cases a run may attempt
    — before the run, before the estimate the operator confirms — so a per-run
    build that disagrees with the boot pair is a run attempting judged cases with
    nothing to score them, or an operator shown an estimate for a narrower run than
    the one that ran. Refused in both directions, because the pair is a fact about
    the deployment and neither side of it is the authority over the other.
    """
    judged = BenchConfig(
        cases=[], adjudicator=ADJUDICATING, per_run_instruments=unadjudicating
    )
    with pytest.raises(ValueError, match="does not agree"):
        judged.instruments_for(UsageLedger())

    unjudged = BenchConfig(
        cases=[],
        adjudicator=None,
        per_run_instruments=lambda models, usage: Instruments(
            adjudicator=ADJUDICATING, attacker=SCRIPTED_ATTACKER, narrator=None
        ),
    )
    with pytest.raises(ValueError, match="does not agree"):
        unjudged.instruments_for(UsageLedger())


def test_a_run_whose_instruments_cannot_be_built_sends_nothing_and_says_so(
    disclosure_denial_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal lands before the estimate, which is where a refusal belongs.

    A model named and unbuildable is refused at boot (`app.declared_instrument`,
    `NAMED_BUT_UNUSABLE`), and this is the same ordering one floor down: the build
    is attempted at the top of the run, ahead of `run_calibration`, so a bench that
    cannot instrument a run says so before an operator confirms a spend and before
    a byte reaches the target. A run that discovered it after the confirmation
    would have spent somebody's endpoint to learn it (ADR-0007).

    The wait `start` gives the interrupt is shortened rather than waited out: what
    is under test is that the run never reaches one, and thirty seconds of a test
    proving that is thirty seconds nobody needs.
    """
    monkeypatch.setattr(runs, "PRESENT_WAIT_SECONDS", 2.0)
    with (
        api([disclosure_denial_case], unadjudicating) as (client, bench),
        # An in-memory sink, installed for the reason the tests above install one:
        # `create_app` points this process at whatever sink the environment
        # declares, and a test has no business emitting to it.
        recording(),
        watched_reference() as watched,
    ):
        nonce = registered(client, watched)
        response = client.post("/runs", json=a_request(watched.target, nonce))
        # No estimate was ever presented, so there is nothing for the operator to
        # confirm and the route says so rather than serving figures for a run that
        # is already over.
        assert response.status_code == 500, response.text
        assert "Nothing was sent" in response.text

        [record] = bench.records()
        assert settled(bench, record.run_id) is RunStatus.FAILED
        assert "instruments could not be built" in record.statement
        assert "nothing was spent" in record.statement
        assert watched.ledger.hits == 0


# --- the deployed factory's own builder -------------------------------------------


def _bound_adjudicator(
    spec: str,
    temperature: float | None = None,
    reasoning_effort: Any = None,
    usage: UsageSink = DISCARDED,
) -> Completion:
    """`completion_for`, stood in for, asserting the string that declared it."""
    assert spec == AN_ADJUDICATING_MODEL, spec
    return adjudicating(usage, A_STEP)


def _bound_attacker(
    spec: str,
    temperature: float | None = None,
    reasoning_effort: Any = None,
    usage: UsageSink = DISCARDED,
) -> Any:
    """`attacker_completion_for`, stood in for, on the same terms."""
    assert spec == AN_ATTACKING_MODEL, spec
    return attacking(usage, ANOTHER_STEP)


def _bound_narrator(spec: str, usage: UsageSink = DISCARDED) -> Narrator:
    """`narrator_for`, stood in for, and it has to be stood in for separately.

    The factory reaches the two narrative instruments through `narrator_for` rather
    than through `completion_for` twice (ADR-0030), so a test that patched only the
    latter would leave this one building a real client — and a real client needs a
    credential, which is the difference between passing on the machine that has one
    and failing in CI. Two closures, because the pair is two instruments.
    """
    assert spec == AN_ADJUDICATING_MODEL, spec
    return Narrator(
        assess=adjudicating(usage, A_STEP), remediate=adjudicating(usage, A_STEP)
    )


def test_the_deployed_factory_builds_each_run_its_own_bound_instruments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declared strings build the clients, and the sinks are the run's own.

    Over the builder the factory installs rather than over a stand-in for it, which
    is the half the tests above cannot reach: they prove a bound pair reaches a
    trace, and this proves the pair a *deployment* builds is bound at all — and
    bound per layer, the adjudicator's tokens into the scored bucket and the
    attacker's into the adaptive one (ADR-0010).

    Two builds and two ledgers, because *per run* is the property: a builder that
    returned one memoised pair would report the first run's calls into the first
    run's ledger for ever.
    """
    for variable in DEPLOYMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setenv(ADJUDICATOR_MODEL_ENV, AN_ADJUDICATING_MODEL)
    monkeypatch.setenv(ATTACKER_MODEL_ENV, AN_ATTACKING_MODEL)
    monkeypatch.setattr("backend.api.app.completion_for", _bound_adjudicator)
    monkeypatch.setattr("backend.api.app.attacker_completion_for", _bound_attacker)
    monkeypatch.setattr("backend.api.app.narrator_for", _bound_narrator)

    config = cast(BenchRuns, create_app().state.bench).config
    first, second = UsageLedger(), UsageLedger()
    one = config.instruments_for(first)
    other = config.instruments_for(second)

    assert one.adjudicator is not None and other.adjudicator is not None
    one.adjudicator("brief", "transcript")
    one.attacker("brief", "what came back")
    assert first.totals_in(Layer.SCORED).input_tokens == A_STEP
    assert first.totals_in(Layer.ADAPTIVE).input_tokens == ANOTHER_STEP
    # The second run's ledger holds nothing yet, because the first run's calls went
    # to the first run's ledger and to no other.
    assert second.totals_in(Layer.SCORED).input_tokens is None
    assert second.totals_in(Layer.ADAPTIVE).input_tokens is None

    other.adjudicator("brief", "transcript")
    assert second.totals_in(Layer.SCORED).input_tokens == A_STEP
    assert first.totals_in(Layer.SCORED).calls == 1


def test_the_deployed_factory_binds_the_narrative_instruments_to_the_scored_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run started from the console explains what it finds, and pays for it here.

    #37's fault was that no production code called the judge at all. This is the
    half of the fix a run cannot show by itself: the pair a *deployment* builds,
    bound to the run's own ledger and into the scored layer — the narrative is a
    scored-layer instrument, and its tokens counted into the adaptive bucket would
    be a scored figure inside an adaptive one (ADR-0010, ADR-0030).

    Both halves come off `models.adjudicating`, which is ADR-0030's decision: a
    fourth declared model would be a declared input the signed payload has no
    field for.
    """
    for variable in DEPLOYMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setenv(ADJUDICATOR_MODEL_ENV, AN_ADJUDICATING_MODEL)
    monkeypatch.setattr("backend.api.app.completion_for", _bound_adjudicator)
    monkeypatch.setattr("backend.api.app.narrator_for", _bound_narrator)

    config = cast(BenchRuns, create_app().state.bench).config
    ledger = UsageLedger()
    built = config.instruments_for(ledger)

    assert built.narrator is not None
    built.narrator.assess("the judge's prompt", "a blinded brief")
    built.narrator.remediate("the remediation prompt", "a finding")

    assert ledger.totals_in(Layer.SCORED).calls == 2
    assert ledger.totals_in(Layer.ADAPTIVE).calls == 0
    assert not ledger.untagged()


def test_a_deployment_declaring_no_models_builds_the_same_two_absences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No adjudicator and the deterministic stand-in, per run as at boot.

    The pair has to agree with the boot pair or `instruments_for` refuses it, and
    the reason it agrees is that both come off the same declared strings. Asserted
    because the stand-in is the one instrument that reports nothing — it is test
    equipment and not a model — so a bench that declared no attacker traces no
    adaptive figure, which is an absence with a sentence rather than a gap.
    """
    for variable in DEPLOYMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))

    config = cast(BenchRuns, create_app().state.bench).config
    built = config.instruments_for(UsageLedger())

    assert built.adjudicator is None
    assert built.attacker is SCRIPTED_ATTACKER
    # And no narrator, which is the stated absence `TargetRun.narrations` carries
    # as `None`: a bench with no declared model measures and explains nothing,
    # rather than explaining nothing that a reader could mistake for a target
    # with nothing to explain (ADR-0030).
    assert built.narrator is None
