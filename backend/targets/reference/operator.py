"""The operator's side of the reference agents: how they are described, and the nonce.

A user plants the bench's nonce in their target's system prompt by hand and registers
what their target can do. The reference agents have a test-equipment route for the
first and this module for the second, so they participate in registration like any
other target and the nonce protocol is exercised on every gate run rather than only in
production.

**The description lives here once, and every entry point reads it.** Six callers used
to write the same `TargetConfig` out — the two scripts that gate, the two that attack
and calibrate, the console's gate-run equipment and the suite's own fixture — and each
of them had to be found again whenever the reference agents gained a capability. A
declaration copied six times is a declaration that can be five-sixths true, and the
run that discovers it is the one whose figures were read against the wrong shape.
"""

from collections.abc import Sequence

import httpx

from backend.bench.calibration import PlantNonce
from backend.bench.contract import TargetConfig
from backend.targets.reference.agent import ReferenceAgent
from backend.targets.reference.server import REFERENCE_AGENTS
from backend.targets.reference.tools import DECLARED_TOOL_NAMES

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


def described_agents(
    base_url: str,
    auth_token: str,
    agents: Sequence[ReferenceAgent] = REFERENCE_AGENTS,
) -> list[TargetConfig]:
    """The given reference agents, described the way any target is described.

    Everything here is a **declared** property of an endpoint — the operator's own
    statement of what their agent exposes and may do — and for these three the
    operator is this project. Each is what makes some family measurable at all rather
    than refused before the first attempt: the tool trace for scope creep and halt
    defeat (ADR-0004), the declared tool list scope creep is read against, session
    retention for memory poisoning
    ([ADR-0041](../../../docs/adr/0041-the-persistence-canary-is-read-over-two-turns.md)),
    and the client records PII leakage asks a target to disclose
    ([ADR-0043](../../../docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)).

    `agents` is for a caller asking a narrower question — a hardened variant with one
    control removed, served under the same name, which is how a refusal is attributed
    to the control that produced it.
    """
    return [
        TargetConfig(
            name=agent.name,
            url=f"{base_url}/reference/{agent.name}/messages",
            auth_token=auth_token,
            agent_type="assistant",
            exposes_tool_calls=True,
            declared_tools=DECLARED_TOOL_NAMES,
            retains_session_state=True,
            holds_personal_records=True,
        )
        for agent in agents
    ]
