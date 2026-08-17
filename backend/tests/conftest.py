"""Fixtures for seam one — the calibration entry point.

The reference agents are served over real HTTP on an ephemeral port, because the
gate must exercise the same code path a user's target exercises (spec:
Implementation Decisions, "Reference agents are reached over real HTTP").
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
from backend.bench.contract import TargetConfig
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
        yield next(
            served for served in references.served if served.target.name == name
        )


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
            plant_nonce=reference.plant_nonce,
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
