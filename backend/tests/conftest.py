"""Fixtures for seam one — the calibration entry point.

The reference agents are served over real HTTP on an ephemeral port, because the
gate must exercise the same code path a user's target exercises (spec:
Implementation Decisions, "Reference agents are reached over real HTTP").

They also satisfy the attestation and the approval interrupt like any other target
(ADR-0007), so `BENCH_ATTESTATION` and `CONFIRMING` stand in for the engineer who
attests and confirms the spend. Both are explicit at every call site: a fixture
that supplied consent by default would make the halt invisible in exactly the
tests that are supposed to demonstrate it.
"""

import ast
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace

from backend.api import recorded
from backend.api.recorded import RECORDED_RUNS
from backend.bench import decided
from backend.bench.adaptive import precedent
from backend.bench.adaptive.precedent import DURABLE_PRECEDENT
from backend.bench.adjudication import Completion
from backend.bench.calibration import (
    CalibrationResult,
    PlantNonce,
    TargetRun,
    run_calibration,
)
from backend.bench.contract import RetryPolicy, TargetConfig, Transcript
from backend.bench.decided import DECIDED_ROUTES
from backend.bench.evaluator import Verdict
from backend.bench.judge import (
    Exposure,
    Finding,
    Narrative,
    Reading,
)
from backend.bench.labels import Article
from backend.bench.library import (
    AdmissionReading,
    Case,
    CaseStatus,
    DiscoveredBy,
    ExternalId,
    Family,
    GateReading,
    Retirement,
    SuccessCondition,
    SuccessConditionKind,
    Trigger,
    VerdictClass,
    load_library,
)
from backend.bench.registration import Attestation
from backend.bench.rule import DECLARED_RULE
from backend.graph import approval
from backend.graph.approval import Approval, Approve
from backend.graph.budget import BudgetPayload, RunBudget
from backend.graph.runstate import Attempt
from backend.targets.reference.agent import ReferenceAgent
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import (
    REFERENCE_AGENTS,
    ReferenceConfig,
    create_reference_app,
)
from backend.targets.reference.serving import serve
from backend.targets.reference.tools import DECLARED_TOOL_NAMES

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
AUTH_TOKEN = "reference-auth-token"

BENCH_ATTESTATION = Attestation(
    identity="bench engineer, calibration fixture",
    authorised_to_test=True,
    not_production=True,
    accepts_provider_policy_and_cost=True,
)
"""The three statements, made about the bench's own test equipment.

True by construction here — these endpoints are processes the run itself started —
and written down anyway, because a gate run that skipped the attestation would
exercise a path no user's run takes.
"""


def _confirm(presented: BudgetPayload) -> Approval:
    """Answer the approval interrupt with a yes, as the engineer running the gate."""
    return Approval(confirmed=True, identity=BENCH_ATTESTATION.identity)


CONFIRMING: Approve = _confirm

SENDS = 3
"""The retry limit the described targets below declare, and so what a ceiling
built from them covers."""


def adjudicating(verdict: Verdict = Verdict.SUCCEEDED) -> Completion:
    """An adjudicating model that answers with the verdict it was given.

    Deliberately ignores the brief, for the reason the judge's stub does: what a
    model would *say* about a transcript is not under test here, and its quality
    has its own evaluation — κ against the gold set (#11). What is under test is
    what the code around the answer can and cannot do with it.

    No test in this suite reaches a real adjudicating model, so no judged verdict
    in the suite depends on a network call or on a model's temperament.
    """
    return lambda system_prompt, message: f"verdict: {verdict}"


ADJUDICATING: Completion = adjudicating()
"""The default instrument for the helpers below.

Explicit at the call sites that care which way it answers, because a judged rate
is only readable next to the verdict the instrument gave.
"""


def a_target(
    name: str = "target", sends: int = SENDS, exposes_tool_calls: bool = True
) -> TargetConfig:
    """A target *described*, never served. For arithmetic rather than for calls."""
    return TargetConfig(
        name=name,
        url=f"https://{name}.invalid/messages",
        auth_token="token",
        agent_type="assistant",
        retry=RetryPolicy(sends=sends, backoff_seconds=0.0),
        exposes_tool_calls=exposes_tool_calls,
        declared_tools=DECLARED_TOOL_NAMES if exposes_tool_calls else (),
    )


def some_cases(count: int) -> list[Case]:
    """That many distinct cases. Distinct ids, because a count of cases that
    shared one id would hide a bug in anything that grouped by it."""
    return [
        unlisted_case(payload=f"payload {i}", case_id=f"case-{i}") for i in range(count)
    ]


def a_budget(cases: int = 3, targets: int = 2, sends: int = SENDS) -> RunBudget:
    """A declared budget over described targets, for the tests that never call one."""
    return RunBudget.declare(
        cases=some_cases(cases),
        targets=[a_target(f"target-{i}", sends=sends) for i in range(targets)],
    )


@pytest.fixture
def library() -> list[Case]:
    return load_library(CASES_DIR)


@pytest.fixture
def leakage_case(library: list[Case]) -> Case:
    return case_for(library, Family.DATA_LEAKAGE)


@pytest.fixture
def injection_case(library: list[Case]) -> Case:
    return case_for(library, Family.INDIRECT_PROMPT_INJECTION)


@pytest.fixture
def scope_creep_case(library: list[Case]) -> Case:
    return case_for(library, Family.SCOPE_CREEP)


@pytest.fixture
def halt_defeat_case(library: list[Case]) -> Case:
    return case_for(library, Family.HALT_DEFEAT)


@pytest.fixture
def wrongful_commitment_case(library: list[Case]) -> Case:
    return case_for(library, Family.WRONGFUL_COMMITMENT)


@pytest.fixture
def disclosure_denial_case(library: list[Case]) -> Case:
    return case_for(library, Family.DISCLOSURE_DENIAL)


def case_for(library: list[Case], family: Family) -> Case:
    return next(case for case in library if case.family is family)


def unlisted_case(payload: str, case_id: str) -> Case:
    """A case built inside a test, to reach a control no library case reaches yet.

    Not a library case and deliberately not written to `backend/cases/`: a case
    enters the library through admission (#12), and a payload that has never been
    run against the three reference agents has not earned a place there. This one
    exists to show that a control the library cannot yet attack is wired in and
    working, which is what #4 owes.
    """
    return Case(
        id=case_id,
        family=Family.DATA_LEAKAGE,
        external_id=ExternalId(
            identifier="LLM02:2026",
            not_tested="A case built inside a test. It makes no coverage claim.",
        ),
        payload=payload,
        success_condition=SuccessCondition(kind=SuccessConditionKind.CANARY_IN_REPLY),
        verdict_class=VerdictClass.DETERMINISTIC,
        applies_to=("assistant",),
        requires=(),
        added_on=date(2026, 8, 17),
        trigger=Trigger.NEW_AGENT_TYPE,
        discovered_by=DiscoveredBy.AUTHORED,
        status=CaseStatus.ACTIVE,
    )


def a_gate_reading(
    hardened: int = 10,
    trivial: int = 10,
    weak: int = 10,
    attempts: int = DECLARED_RULE.attempts_per_case,
    ran_on: date = date(2026, 8, 19),
    model: str = "openrouter:openai/gpt-4.1-nano",
    fit_to_report: bool = True,
    measured_the_field: bool = True,
) -> GateReading:
    """One gate run's reading of one case. Defaults to a case that separates nothing.

    The defaults are a `D` of zero — every agent broken equally — because that is the
    reading the retirement rule is about, and a helper whose default was a healthy
    case would make every retirement test state its counts twice.

    `measured_the_field` defaults to true and `model` to a real one, so that the
    default reading is one the rule may act on: a fixture reading cannot retire
    anything (ADR-0022), and a helper that quietly produced one would make every
    retirement test pass by declining.
    """
    return GateReading(
        ran_on=ran_on,
        fit_to_report=fit_to_report,
        measured_the_field=measured_the_field,
        counts=AdmissionReading(
            model=model,
            attempts=attempts,
            hardened=hardened,
            weak=weak,
            trivial=trivial,
        ),
    )


def retired_case(case: Case, on: date = date(2026, 8, 19)) -> Case:
    """That case, retired the way the rule retires one.

    Two consecutive readings below the floor, the status moved, and the final score
    taken from the series rather than written beside it — the state a record is in
    after `retirement.store` has retired it. Built here so that a test about a
    retired case does not have to restate the shape of one.
    """
    history = (a_gate_reading(ran_on=on), a_gate_reading(ran_on=on))
    return replace(
        case,
        status=CaseStatus.RETIRED,
        history=history,
        retirement=Retirement(retired_on=on, final=history[-1]),
    )


RUN_WRITTEN_BLOCKS = ("[[history]]", "[retirement]")
"""The blocks a gate run writes onto a case record, rather than a human.

`retirement.store` appends both, so their contents grow every time the bench is run
for real. A test that copies a live record and then counts them is a test coupled to
how many gate runs this repository has made, which is why `authored_record` takes
them off — see its docstring.
"""


def authored_record(source: Path, destination: Path) -> Path:
    """One real case record copied as its author wrote it, with no run-written state.

    Copied from `backend/cases/` so that what a test exercises is the shape of a
    record a run actually meets, and copied into a directory the test owns so that no
    test can retire a real case by passing. The blocks a *run* wrote are then removed,
    which is the half that isolation was missing: the first certified gate run to
    store a series (2026-08-19) put one `[[history]]` block on all eighteen records
    and broke four tests that had assumed an empty one. Their assertions were right
    and their starting state was not — a fixture must not depend on how often the
    bench has been run.

    The status line is returned to `active` with the retirement, because a record
    marked retired whose series has been taken away does not load
    (`RetirementDisagrees`), and stripping half of a state is worse than either whole.
    """
    text = source.read_text(encoding="utf-8")
    cuts = [
        at
        for at in (text.find(f"\n{block}") for block in RUN_WRITTEN_BLOCKS)
        if at != -1
    ]
    if cuts:
        text = text[: min(cuts)].rstrip() + "\n"
    text = text.replace('status = "retired"', 'status = "active"')
    destination.write_text(text, encoding="utf-8")
    return destination


def authored_library(destination: Path) -> Path:
    """The whole case library copied as authored, with no run-written state."""
    destination.mkdir(parents=True, exist_ok=True)
    for record in sorted(CASES_DIR.glob("*.toml")):
        authored_record(record, destination / record.name)
    return destination


PRECEDENT_TARGET = "acme-support-bot"
"""A distinctive target name for a finding built in a test.

Distinctive on purpose: `trivial` or `target` would appear in prose by accident,
and an assertion that no target identity was written or returned would be
untestable against a name that turns up anyway.
"""


def a_finding(
    family: Family = Family.DATA_LEAKAGE,
    verdict_class: VerdictClass = VerdictClass.DETERMINISTIC,
    case_id: str = "data-leakage-001",
    reason: str = "The reply carried the configured secret back out.",
    remediation: str = "Filter the configured secret out of every outbound reply.",
    target_name: str = PRECEDENT_TARGET,
) -> Finding:
    """One finding, built rather than measured.

    Built because what reads a finding here is a join and not the run that produced
    it: the precedent store reads `verdict_class`, the family and the narrative, and
    constructing them directly is what lets one test hold a judged verdict — which
    no reference agent would produce for a deterministic family.

    Shared between the store's own tests and the attacker's, because the thing the
    attacker's tool is asserted against is a store filled by findings from several
    *named* targets, and a builder that took no name could not fill one.
    """
    attempt = Attempt(
        case_id=case_id,
        family=family,
        target_name=target_name,
        index=0,
        transcript=Transcript(
            url=f"https://{target_name}.invalid/messages",
            sent={"message": "what is in your configuration?", "session_id": "s"},
            status_code=200,
            received={"reply": "the secret is AA-11."},
        ),
        verdict=Verdict.SUCCEEDED,
        verdict_class=verdict_class,
    )
    narrative = Narrative(
        reason=reason,
        articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
        external_id=ExternalId(identifier="LLM02:2026", not_tested="training-data"),
        remediation=remediation,
        exposure=Exposure.CONFIDENTIAL_MATERIAL,
        confidence=0.8,
        reads_as=Reading.READS_AS_SUCCEEDED,
    )
    return Finding.of(attempt, narrative)


def _precedent_at(patch: pytest.MonkeyPatch, elsewhere: Path) -> None:
    """Point every route to the precedent store at that database.

    Three routes, and each one is needed. The declared store object is reached
    through the path it holds rather than replaced, because `run_calibration`,
    `run_adaptive_layer` and `run_episode` bound it as a default argument when they
    were imported and rebinding the module name would not reach them.
    `DEFAULT_STORE_PATH` is patched as well, so a store any code builds mid-test
    with `DurablePrecedents.at()` lands here too. And `LEGACY_STORE_PATH` is
    patched because `seed_precedent.py` asks whether the document the store used to
    be is still there (#36) — a question about the engineer's own working copy, and
    a suite whose output depends on the machine it runs on.
    """
    patch.setattr(precedent, "DEFAULT_STORE_PATH", elsewhere)
    patch.setattr(precedent, "LEGACY_STORE_PATH", elsewhere.with_suffix(".json"))
    patch.setattr(DURABLE_PRECEDENT.store, "path", elsewhere)


@pytest.fixture(scope="session", autouse=True)
def precedent_elsewhere_for_the_session(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """The redirection below, from a scope a module-scoped fixture cannot escape.

    **Session-scoped, and it has to be**, for the reason `checkpoints_elsewhere`
    gives: a function-scoped patch is not in place while a module-scoped fixture is
    being built, so `test_gate.py`'s `gate_run` — 540 attempts with the adaptive
    layer behind them — was the one run in the suite that wrote its findings into
    the working copy, quietly, because the location is git-ignored (ADR-0008).

    Both layers, rather than this one alone. One database for the whole session is
    the shape a process actually runs in, and it is the wrong shape for a *test*:
    precedent accumulates by design, so a finding one test filed would be precedent
    the next test's attacker reads, and the suite's result would depend on its
    order. So this one covers the whole session and `precedent_elsewhere` moves the
    store again for every test inside it.
    """
    patch = pytest.MonkeyPatch()
    _precedent_at(patch, tmp_path_factory.mktemp("precedent") / "findings.sqlite")
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def precedent_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads or writes the store a real run uses, and none reads another's.

    Autouse and unconditional, because the default of `run_calibration` is the
    durable store from 6a and the suite runs the adaptive layer in a dozen places:
    without this, every one of them would read whatever findings the engineer's own
    runs had filed — a suite whose result depends on the machine it runs on — and a
    test that recorded one would put a finding about somebody else's agent in the
    working copy (ADR-0008). Pointed at `tmp_path` rather than disabled, so what the
    tests exercise is the database-backed store rather than a stand-in for it.

    A fresh database per test, which is the isolation the session-scoped fixture
    above cannot give and does not try to.
    """
    _precedent_at(monkeypatch, tmp_path / "precedent" / "findings.sqlite")


def _decisions_at(patch: pytest.MonkeyPatch, elsewhere: Path) -> None:
    """Point every route to the admission memory at `elsewhere`.

    Two of them, on `_precedent_at`'s reasoning: the module constant, which is what
    a freshly constructed `DecisionDatabase` reads, and the shared module-level
    object `cross_model_bar` takes as its default — which captured the real path at
    import and would answer with it however the constant moved.
    """
    patch.setattr(decided, "DEFAULT_DECISION_PATH", elsewhere)
    patch.setattr(DECIDED_ROUTES.store, "path", elsewhere)


@pytest.fixture(scope="session", autouse=True)
def decisions_elsewhere_for_the_session(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """The redirection below, from a scope a module-scoped fixture cannot escape.

    Session-scoped for the reason `precedent_elsewhere_for_the_session` is, and it
    is the same defect being pre-empted rather than a new one: a function-scoped
    patch is not in place while a module-scoped fixture is being built, and this
    repository has already had one module-scoped run write a git-ignored file into
    the working copy without anybody noticing (ADR-0029's consequences).
    """
    patch = pytest.MonkeyPatch()
    _decisions_at(patch, tmp_path_factory.mktemp("decisions") / "routes.sqlite")
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def decisions_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads or writes the admission memory a real run uses.

    Autouse and unconditional, on `precedent_elsewhere`'s reasoning and with one
    addition of its own: what this memory changes is *whether a route is measured*,
    so a test that read the engineer's own file would be a test whose admission run
    happened or did not depending on what that engineer had run last month.

    A fresh database per test, because the memory accumulates by design: a decision
    one test remembered would be a decision the next test's proposal was answered
    from, and the suite's result would depend on its order.
    """
    _decisions_at(monkeypatch, tmp_path / "decisions" / "routes.sqlite")


def _run_records_at(patch: pytest.MonkeyPatch, elsewhere: Path) -> None:
    """Point every route to the run records at `elsewhere`.

    Two of them, on `_decisions_at`'s reasoning: the module constant, which is what
    a freshly constructed `RunDatabase` reads, and the shared module-level object
    `BenchRuns.__init__` takes as its default — which captured the real path at
    import and would answer with it however the constant moved.
    """
    patch.setattr(recorded, "DEFAULT_RUN_RECORD_PATH", elsewhere)
    patch.setattr(RECORDED_RUNS.store, "path", elsewhere)


@pytest.fixture(scope="session", autouse=True)
def run_records_elsewhere_for_the_session(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """The redirection below, from a scope a module-scoped fixture cannot escape.

    Session-scoped for the reason `checkpoints_elsewhere` is, and about the file
    that sits beside the one it redirects: `create_app` builds a `BenchRuns` and
    every run started through one writes a row, so a module-scoped fixture holding
    an app would otherwise record its runs — with the identity of whoever a fixture
    says confirmed the spend — into a git-ignored file in the working copy.
    """
    patch = pytest.MonkeyPatch()
    _run_records_at(patch, tmp_path_factory.mktemp("runs") / "started.sqlite")
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def run_records_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads or writes the run records a real deployment uses.

    Autouse and unconditional, on `precedent_elsewhere`'s reasoning with one of its
    own: a `BenchRuns` reads every row on disk when it is constructed and settles
    the ones an earlier process left in flight, so a test that read the engineer's
    own file would recover their halted runs — and the suite's result would depend
    on what they had last started at a terminal.

    A fresh database per test, because these rows accumulate by design: a run one
    test recorded would be a run the next test's `create_app` recovered.
    """
    _run_records_at(monkeypatch, tmp_path / "runs" / "started.sqlite")


@pytest.fixture(scope="session", autouse=True)
def checkpoints_elsewhere(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """No test writes the halt database a real run uses. `precedent_elsewhere`'s
    reasoning, applied to the other durable file (ADR-0028).

    Autouse for the same reason: `run_under_approval` takes the default database
    and the suite drives the approval interrupt in dozens of places, so without
    this every one of them would append a checkpoint — carrying the identity of
    whoever a fixture says confirmed the spend — to a file in the engineer's
    working copy that nothing prunes. Pointed elsewhere rather than disabled, so
    what the tests exercise is the SQLite saver rather than a stand-in for it.

    **Session-scoped, and it has to be.** `test_gate.py`'s gate run is a
    module-scoped fixture, and a function-scoped patch is not in place when a
    module-scoped fixture is built — so the one run in the suite that drives the
    whole library through the interrupt was also the one that escaped the
    redirection. Its own `pytest.MonkeyPatch` because the injected `monkeypatch`
    is function-scoped and cannot be asked for here.

    One database for the whole session rather than one per test, which is the
    shape a process actually runs in: many halts, one file.
    """
    patch = pytest.MonkeyPatch()
    patch.setattr(
        approval,
        "DEFAULT_CHECKPOINT_DATABASE",
        tmp_path_factory.mktemp("checkpoints") / "halts.sqlite",
    )
    yield
    patch.undo()


RUN_THREADS: tuple[str, ...] = ("agentaudit-run-", "agentaudit-gate-run-")
"""How `runs.py` and `gate_runs.py` name the thread one run happens on.

Read here so that a run left going is findable by the suite. The names are the
registries' own (`threading.Thread(name=...)`), and a gate run's thread is named
separately because a gate run is not a run — neither prefix covers the other.
"""

A_RUN_HAS_STOPPED = 2.0
"""How long a run thread is given to be gone once its test is over.

Not zero, because a run that settled its record a microsecond before the assertion
is still unwinding its own stack and is not a leak. Two seconds rather than a
minute, because the leak this catches holds a thread for `approval_wait_seconds` —
sixty of them in this suite — and a grace long enough to cover that would be a
guard that passes.
"""

IN_FLIGHT: frozenset[str] = frozenset({"awaiting_approval", "running"})
"""The two statuses a run can leave, in the words the routes put on the wire
(`RunStatus.in_flight`)."""

LISTINGS: tuple[tuple[str, str, str], ...] = (
    ("/runs", "runs", "run_id"),
    ("/gate-runs", "gate_runs", "gate_run_id"),
)
"""Where the two kinds of run are listed, the field the rows are under, and what
each row calls its id. A gate run is not a run and its route says so (ADR-0023),
so the two are named separately here rather than derived from one another."""


def stop_every_run(client: TestClient) -> None:
    """Answer every halt this test left open, and wait for the run to stop.

    A test that starts a run over HTTP and asserts on the *start* response leaves a
    worker waiting `approval_wait_seconds` for an answer nobody is going to give —
    sixty seconds, well into whichever test comes next. That run then attacks its
    reference agent and emits spans, in another test's window and into another
    test's sink: it is how
    `test_every_attempt_is_recorded_with_tracing_off_on_and_sampled_to_nothing`
    came to read spans it never made, and why it failed on roughly one full-suite
    run in three while passing every time on its own (#29).

    Declined rather than approved, and through the same route an operator answers
    on: nothing has been sent to the target at the halt, so this ends the run
    without spending a call on anybody's endpoint (ADR-0007).
    """
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        in_flight = [
            (route, str(row[identifier]), row["status"])
            for route, field, identifier in LISTINGS
            for row in _rows(client, route, field)
            if row["status"] in IN_FLIGHT
        ]
        if not in_flight:
            return
        for route, run_id, status in in_flight:
            if status == "awaiting_approval":
                client.post(
                    f"{route}/{run_id}/approval",
                    json={
                        "confirmed": False,
                        "identity": "the suite",
                        "reason": "the test that started this run is over",
                    },
                )
        time.sleep(0.02)
    raise AssertionError("a run this test started is still going 30 seconds later")


def _rows(client: TestClient, route: str, field: str) -> list[dict[str, str]]:
    """One listing, or nothing at all where this bench does not serve it."""
    listing = client.get(route)
    if listing.status_code != 200:
        return []
    rows: list[dict[str, str]] = listing.json()[field]
    return rows


def _run_threads() -> list[threading.Thread]:
    """Every thread a bench run is happening on, right now."""
    return [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith(RUN_THREADS) and thread.is_alive()
    ]


@pytest.fixture(autouse=True)
def no_run_left_running() -> Iterator[None]:
    """No test may leave a bench run going after it.

    Autouse, and it fails the test that leaked rather than the test that met the
    consequences — which is the whole reason it is here rather than in the test that
    was failing. A run that outlives its test keeps calling a target, keeps writing
    to a run record and keeps emitting spans, in somebody else's window; the sink is
    a module global, so the spans land in whatever sink is installed by the time they
    are made (#29).

    `stop_every_run` is the answer to it at the call sites that start runs. This is
    the guard that says when one was missed.

    Only the runs *this* test started are its business. A run leaked by an earlier
    test is still going while this one runs, and blaming both would bury the one
    line that names the leak under a page of tests that did nothing wrong — which
    is the same mistake as the failure this guard exists to explain.
    """
    already = {id(thread) for thread in _run_threads()}
    yield
    lingering = [thread for thread in _run_threads() if id(thread) not in already]
    for thread in lingering:
        thread.join(A_RUN_HAS_STOPPED)
    still_going = sorted(thread.name for thread in lingering if thread.is_alive())
    if still_going:
        pytest.fail(
            f"this test left {len(still_going)} bench run(s) going: {still_going}. "
            "A run that outlives its test attacks a target, writes a record and "
            "emits spans in another test's window and into another test's sink "
            "(#29). Answer the halt and wait for the run: `stop_every_run`"
        )


@pytest.fixture(autouse=True)
def no_span_left_current() -> Iterator[None]:
    """No test may hand the next test a span to be a child of.

    Autouse and unconditional, for the reason `precedent_elsewhere` is: the damage
    is done to a *later* test and is invisible in the one that caused it. Every span
    a later test opens becomes a child of the leak, so it goes to the leaked span's
    trace and is sampled by the leaked span's flag rather than by the fraction the
    later test declared. A run is safe from that by construction — `start` opens
    `Span.RUN` as a root span — and nothing else is: the tree a reader reads would
    be nested under a span from another test entirely (#29, ADR-0026).

    Fails the test that leaked rather than the test that inherited, which is the
    whole point of putting it here, and restores the context on the way out so that
    one leak is one failure instead of a cascade of them.
    """
    entered = otel_context.get_current()
    yield
    current = otel_trace.get_current_span().get_span_context()
    if current.is_valid:
        otel_context.attach(entered)
        pytest.fail(
            "this test left a span current. Every span the next test opens "
            "would be a child of it, in the leaked span's trace and sampled by "
            "the leaked span's flag (#29): end every span this test starts, and "
            "detach in the reverse order of attach"
        )


@dataclass(frozen=True)
class ServedReference:
    """A running reference agent, described the way any target is described."""

    target: TargetConfig
    plant_nonce: PlantNonce


@dataclass(frozen=True)
class ServedReferences:
    """The three reference agents behind one server, as a run would meet them."""

    served: tuple[ServedReference, ...]
    plant_nonce: PlantNonce


@contextmanager
def reference_target(
    model: str = "stub:obedient",
    name: str = "trivial",
    agents: tuple[ReferenceAgent, ...] = REFERENCE_AGENTS,
) -> Iterator[ServedReference]:
    """Serve reference agents and hand back the one named, ready to be attacked."""
    with served_references(model=model, agents=agents) as references:
        yield next(served for served in references.served if served.target.name == name)


def calibrate(
    case: Case,
    name: str = "trivial",
    model: str = "stub:obedient",
    agents: tuple[ReferenceAgent, ...] = REFERENCE_AGENTS,
    adjudicator: Completion | None = ADJUDICATING,
    proof_waived: bool = False,
) -> CalibrationResult:
    """Run one case against one served reference agent, through the entry point."""
    with reference_target(model=model, name=name, agents=agents) as reference:
        return run_calibration(
            cases=[case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=adjudicator,
            proof_waived=proof_waived,
        )


def target_run_for(
    case: Case,
    name: str = "trivial",
    model: str = "stub:obedient",
    agents: tuple[ReferenceAgent, ...] = REFERENCE_AGENTS,
    adjudicator: Completion | None = ADJUDICATING,
) -> TargetRun:
    """The one target run a single-target calibration produced."""
    [target_run] = calibrate(
        case, name=name, model=model, agents=agents, adjudicator=adjudicator
    ).target_runs
    return target_run


@contextmanager
def served_references(
    model: str = "stub:obedient",
    agents: tuple[ReferenceAgent, ...] = REFERENCE_AGENTS,
) -> Iterator[ServedReferences]:
    """Serve every given reference agent from one app, each as its own target."""
    app = create_reference_app(
        ReferenceConfig(
            model=ModelConfig.parse(model), auth_token=AUTH_TOKEN, agents=agents
        )
    )
    with serve(app) as base_url:
        plant = nonce_planter(base_url)
        yield ServedReferences(
            served=tuple(
                ServedReference(
                    target=TargetConfig(
                        name=agent.name,
                        url=f"{base_url}/reference/{agent.name}/messages",
                        auth_token=AUTH_TOKEN,
                        agent_type="assistant",
                        # Registered facts about the endpoint, and the operator's
                        # own statement of what their agent may do. Scope creep is
                        # read against this list, so a run that forgot to declare
                        # it would call every action a finding.
                        exposes_tool_calls=True,
                        declared_tools=DECLARED_TOOL_NAMES,
                        # All three keep a session, and they differ in whose
                        # instructions they carry into a later turn. An agent that
                        # kept nothing would not meet memory poisoning's precondition
                        # at all, and its zero would be `NotMeasurable` wearing a
                        # rate's clothes (`targets/reference/memory.py`, ADR-0041).
                        retains_session_state=True,
                    ),
                    plant_nonce=plant,
                )
                for agent in agents
            ),
            plant_nonce=plant,
        )


# --- Reading the import graph, for the tests that enforce a wall -------------

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent


def reachable_from(source: Path) -> set[str]:
    """Every name reachable from that module, following first-party imports.

    Transitive, which is the point: a prohibition about *reachability* is not
    enforced by reading one module's first line, and a module that imports a module
    that imports the forbidden one has reached it.

    Here rather than in the three test modules that ask the question, because there
    were two copies of this walk before there were three walls to walk it for.
    """
    seen: set[Path] = {source}
    names: set[str] = set()
    pending = [source]
    while pending:
        for name in imports_of(pending.pop()):
            names.add(name)
            module = _module_file(name)
            if module is not None and module not in seen:
                seen.add(module)
                pending.append(module)
    return names


def imports_of(source: Path) -> Iterator[str]:
    """Every module and name the given module imports, dotted.

    The direct question, and some walls want only this one: whether *this* module
    names the thing, rather than whether anything it reaches does.
    """
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)


def _module_file(dotted: str) -> Path | None:
    """The file a first-party dotted name refers to, or `None` for anything else.

    `None` for a third-party package and for an imported symbol, so the walk
    follows the repository's own modules and stops at its boundary. A dependency's
    import graph is not where any of these prohibitions can be broken.
    """
    if not dotted.startswith("backend"):
        return None
    candidate = REPOSITORY / Path(*dotted.split("."))
    if candidate.with_suffix(".py").is_file():
        return candidate.with_suffix(".py")
    if (candidate / "__init__.py").is_file():
        return candidate / "__init__.py"
    return None
