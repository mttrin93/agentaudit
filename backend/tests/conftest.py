"""Fixtures for seam one — the calibration entry point.

The reference agents are served over real HTTP on an ephemeral port, because the
gate must exercise the same code path a user's target exercises (spec:
Implementation Decisions, "Reference agents are reached over real HTTP").
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.bench.calibration import PlantNonce
from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Family, load_library
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import ReferenceConfig, create_reference_app
from backend.targets.reference.serving import serve

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
AUTH_TOKEN = "reference-auth-token"


@pytest.fixture
def library() -> list[Case]:
    return load_library(CASES_DIR)


@pytest.fixture
def leakage_case(library: list[Case]) -> Case:
    return next(case for case in library if case.family is Family.DATA_LEAKAGE)


@dataclass(frozen=True)
class ServedReference:
    """A running reference agent, described the way any target is described."""

    target: TargetConfig
    plant_nonce: PlantNonce


@contextmanager
def reference_target(
    model: str = "stub:obedient", agent: str = "trivial"
) -> Iterator[ServedReference]:
    """Serve one reference agent, with the operator glue that plants its nonce."""
    app = create_reference_app(
        ReferenceConfig(model=ModelConfig.parse(model), auth_token=AUTH_TOKEN)
    )
    with serve(app) as base_url:
        yield ServedReference(
            target=TargetConfig(
                name=agent,
                url=f"{base_url}/reference/{agent}/messages",
                auth_token=AUTH_TOKEN,
                agent_type="assistant",
            ),
            plant_nonce=nonce_planter(base_url),
        )
