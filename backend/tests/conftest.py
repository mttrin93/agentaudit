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

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pytest

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
from backend.bench.evaluator import Verdict
from backend.bench.judge import (
    Article,
    Exposure,
    Finding,
    Narrative,
    Reading,
)
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
) -> GateReading:
    """One gate run's reading of one case. Defaults to a case that separates nothing.

    The defaults are a `D` of zero — every agent broken equally — because that is the
    reading the retirement rule is about, and a helper whose default was a healthy
    case would make every retirement test state its counts twice.
    """
    return GateReading(
        ran_on=ran_on,
        fit_to_report=fit_to_report,
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
        article=Article.ROBUSTNESS_AND_CYBERSECURITY,
        external_id=ExternalId(identifier="LLM02:2026", not_tested="training-data"),
        remediation=remediation,
        exposure=Exposure.CONFIDENTIAL_MATERIAL,
        confidence=0.8,
        reads_as=Reading.READS_AS_SUCCEEDED,
    )
    return Finding.of(attempt, narrative)


@pytest.fixture(autouse=True)
def precedent_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads or writes the store a real run uses.

    Autouse and unconditional, because the default of `run_calibration` is the
    durable store from 6a and the suite runs the adaptive layer in a dozen places:
    without this, every one of them would read whatever findings the engineer's own
    runs had filed — a suite whose result depends on the machine it runs on — and a
    test that recorded one would put a finding about somebody else's agent in the
    working copy (ADR-0008). Pointed at `tmp_path` rather than disabled, so what the
    tests exercise is the file-backed store rather than a stand-in for it.

    Both ends are redirected, and they have to be. The declared store object is
    reached through the file it holds rather than replaced, because
    `run_calibration`, `run_adaptive_layer` and `run_episode` bound it as a default
    argument when they were imported and rebinding the module name would not reach
    them; `DEFAULT_STORE_PATH` is patched as well, so a store any code builds
    mid-test with `DurablePrecedents.at()` lands here too.
    """
    elsewhere = tmp_path / "precedent" / "findings.json"
    monkeypatch.setattr(precedent, "DEFAULT_STORE_PATH", elsewhere)
    monkeypatch.setattr(DURABLE_PRECEDENT.store, "path", elsewhere)


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
                    ),
                    plant_nonce=plant,
                )
                for agent in agents
            ),
            plant_nonce=plant,
        )
