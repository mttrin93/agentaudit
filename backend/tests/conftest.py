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

from backend.bench.adjudication import Completion
from backend.bench.calibration import (
    CalibrationResult,
    PlantNonce,
    TargetRun,
    run_calibration,
)
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.evaluator import Verdict
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
