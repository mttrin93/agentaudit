"""The operator's side of the nonce protocol, for reference agents.

A user plants the bench's nonce in their target's system prompt by hand. The
reference agents have a test-equipment route for it instead, so they participate
in registration like any other target and the nonce protocol is exercised on
every gate run rather than only in production.
"""

import httpx

from backend.bench.calibration import PlantNonce
from backend.bench.contract import TargetConfig

PLANT_TIMEOUT = 10.0


def nonce_planter(base_url: str) -> PlantNonce:
    """Build the planter for reference agents served at `base_url`."""

    def plant(target: TargetConfig, nonce: str) -> None:
        response = httpx.put(
            f"{base_url}/reference/{target.name}/nonce",
            json={"nonce": nonce},
            timeout=PLANT_TIMEOUT,
        )
        response.raise_for_status()

    return plant
