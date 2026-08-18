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
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from backend.bench.calibration import (
    CalibrationResult,
    PlantNonce,
    TargetRun,
    run_calibration,
)
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.library import (
    Case,
    CaseStatus,
    ExternalId,
    Family,
    SuccessCondition,
    SuccessConditionKind,
    Trigger,
    VerdictClass,
    load_library,
)
from backend.bench.registration import Attestation
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


def a_target(name: str = "target", sends: int = SENDS) -> TargetConfig:
    """A target *described*, never served. For arithmetic rather than for calls."""
    return TargetConfig(
        name=name,
        url=f"https://{name}.invalid/messages",
        auth_token="token",
        agent_type="assistant",
        retry=RetryPolicy(sends=sends, backoff_seconds=0.0),
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
    return next(case for case in library if case.family is Family.DATA_LEAKAGE)


def unlisted_case(payload: str, case_id: str) -> Case:
    """A case built inside a test, to reach a control no library case reaches yet.

    Not a library case and deliberately not written to `backend/cases/`: a case
    enters the library through admission (#12), and a payload that has never been
    run against the three reference agents has not earned a place there. This one
    exists to show that a control the library cannot yet attack is wired in and
    working, which is what #4 owes and #6 turns into a family.
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
        status=CaseStatus.ACTIVE,
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
) -> CalibrationResult:
    """Run one case against one served reference agent, through the entry point."""
    with reference_target(model=model, name=name, agents=agents) as reference:
        return run_calibration(
            cases=[case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
        )


def target_run_for(
    case: Case,
    name: str = "trivial",
    model: str = "stub:obedient",
    agents: tuple[ReferenceAgent, ...] = REFERENCE_AGENTS,
) -> TargetRun:
    """The one target run a single-target calibration produced."""
    [target_run] = calibrate(case, name=name, model=model, agents=agents).target_runs
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
                    ),
                    plant_nonce=plant,
                )
                for agent in agents
            ),
            plant_nonce=plant,
        )
