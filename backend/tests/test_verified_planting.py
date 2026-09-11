"""The harness generates the canary and reads the same value back, so *planted*
stops being a declaration.

The invariant of
[ADR-0064](../../docs/adr/0064-the-harness-reads-its-own-canary-back.md), driven at
four seams:

* `planting.checked` and `planting.PlantCheck` — the read-back on its own, and the
  three answers it has.
* `calibration.run_calibration` over a served callback — a whole shim run, which is
  the only surface where the bench planted the value it later looks for.
* `api/report.payload_for` and `payload.document` / `rendering.render` — the
  artefact, because a reader who cannot tell a verified plant from a confident one
  is reading ADR-0024's sentence with a new word on it.
* `run_calibration`'s `planted_nonces` — the value has one provenance, and a shim
  never takes one from the caller.

**The test that matters here is the target that lies.** `Deceitful` implements
`plant_config_canary`, does nothing with the value, and returns cleanly — the exact
shape a broken planting hook has — and the run comes back with thirty resisted and
an artefact that refuses to call the plant verified.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from backend.api.report import ReportConfig, payload_for
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.elective import NOTHING_REQUESTED
from backend.bench.library import Case, DiscoveredBy, Family, Plant
from backend.bench.payload import document
from backend.bench.planting import (
    NOTHING_WAS_PLANTED_BY_THE_BENCH,
    CanaryFromTwoPlaces,
    PlantCheck,
)
from backend.bench.registration import ECHO_PROBE
from backend.bench.rendering import render
from backend.bench.rule import DECLARED_RULE
from backend.bench.selection import EVERY_CONSTRUCTION
from backend.bench.shim import serve_callback
from backend.tests.conftest import BENCH_ATTESTATION, CONFIRMING
from backend.tests.test_payload import a_payload, a_provenance


class Agent:
    """A callback that keeps what it is planted with and answers with it.

    The honest shape: the value the harness planted is in this target's
    configuration, so the registration probe can read it back out.
    """

    def __init__(self) -> None:
        self.canary: str | None = None
        self.content: list[tuple[str, str]] = []

    def __call__(self, message: str, session_id: str) -> str:
        return self.canary or "nothing to say"

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        self.canary = canary

    def teardown(self, namespace: str) -> None:
        return None


class Deceitful(Agent):
    """A callback whose planting hook returns cleanly and plants nothing.

    Not a hostile target and not a missing hook: a hook that was written, ran, and
    did not do what it says. Under ADR-0024 this run reports the family resisted at
    every attempt and nothing on the page contradicts it.
    """

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        return None


class Retriever(Agent):
    """A callback that can also be given content to retrieve."""

    def plant_retrieved_content(self, namespace: str, key: str, body: str) -> None:
        self.content.append((key, body))


def _calibrate(
    target: object,
    cases: list[Case],
    planter: object,
    *,
    proof_waived: bool = False,
    planted_nonces: dict[str, str] | None = None,
) -> CalibrationResult:
    return run_calibration(
        cases=cases,
        targets=[target],  # type: ignore[list-item]
        attestation=BENCH_ATTESTATION,
        planters={target.name: planter},  # type: ignore[attr-defined]
        approve=CONFIRMING,
        proof_waived=proof_waived,
        planted_nonces=planted_nonces,
        discovered_by=DiscoveredBy.ADAPTIVE,
    )


def _planting_block(result: CalibrationResult, cases: list[Case]) -> dict[str, object]:
    payload = payload_for(
        result,
        cases,
        DECLARED_RULE,
        ReportConfig(),
        EVERY_CONSTRUCTION,
        {},
        NOTHING_REQUESTED,
    )
    block: dict[str, object] = document(payload)["provenance"]["planting"]
    return block


# --- What the shim buys -------------------------------------------------------


def test_a_shim_run_reads_its_own_canary_back_and_the_artefact_says_verified(
    leakage_case: Case,
) -> None:
    """The claim #87 exists to make: measured, and not the operator's word."""
    agent = Agent()
    with serve_callback(agent, name="verified") as target:
        result = _calibrate(target, [leakage_case], agent)

    [target_run] = result.target_runs
    [performed] = target_run.plantings
    assert performed.plant is Plant.CONFIG_CANARY
    assert performed.check is PlantCheck.VERIFIED

    block = _planting_block(result, [leakage_case])
    assert block["planted"] is True
    assert block["verified"] is True


def test_a_hook_that_plants_nothing_and_returns_cleanly_is_not_verified(
    leakage_case: Case,
) -> None:
    """The lie, and the whole of what stops being a declaration.

    The run is started with the echo waived, and it has to be: unwaived, this target
    is refused at registration and spends no attempt at all — which is itself the
    read-back doing its job one step earlier. The waiver is what produces the run
    ADR-0024 named, where every leakage attempt comes back resisted against a value
    that is nowhere in the target. What the artefact refuses is the *verified* claim,
    which is the only thing on the page that could have told a reader the difference.
    """
    agent = Deceitful()
    with serve_callback(agent, name="lying") as target:
        result = _calibrate(target, [leakage_case], agent, proof_waived=True)

    [target_run] = result.target_runs
    rate = target_run.rates[Family(leakage_case.family)]
    assert rate.attempts == DECLARED_RULE.attempts_per_case
    assert rate.value == 0.0

    # The probe is unchanged and was still sent, on the waived path as on every
    # other one: what the waiver decides is whether a missing echo stops the run,
    # never whether the bench looks (ADR-0007 as amended).
    assert target_run.registration.probe.sent["message"] == ECHO_PROBE
    assert target_run.registration.waived
    assert not target_run.registration.echoed

    [performed] = target_run.plantings
    assert performed.check is PlantCheck.NOT_RETURNED

    block = _planting_block(result, [leakage_case])
    assert block["planted"] is True
    assert block["verified"] is False
    assert PlantCheck.NOT_RETURNED.stated() in str(block["stated"])


def test_an_endpoint_run_never_says_a_plant_was_verified() -> None:
    """The strongest claim in the provenance block stays the dearest one.

    An endpoint target does not answer for its own plantings, plants nothing through
    this bench, and so has no `Planting` to be checked. The block says who planted
    instead of saying nothing, and the word the shim earns is not in it.
    """
    payload = a_payload(provenance=replace(a_provenance(), plantings=()))
    block = document(payload)["provenance"]["planting"]
    assert block["planted"] is False
    assert block["verified"] is False
    assert block["stated"] == NOTHING_WAS_PLANTED_BY_THE_BENCH
    assert PlantCheck.VERIFIED.stated() not in render(payload)
    assert NOTHING_WAS_PLANTED_BY_THE_BENCH in render(payload)


def test_a_target_that_answers_for_no_planting_claims_nothing_even_with_a_planter(
    leakage_case: Case,
) -> None:
    """The endpoint reading, taken over a whole run rather than over a fixture.

    `plants = None` is every target that is a URL, and it is the reading — not the
    scheme of the address — that decides: the target below is reached over loopback
    like every served one, answers the canary like the honest agent above, and is
    handed the planter object anyway. The bench requests nothing, plants nothing, and
    the block claims nothing, because the claim is *the bench planted this value and
    read it back* and this bench planted nothing (ADR-0064 §5).
    """
    agent = Agent()
    with serve_callback(agent, name="asked") as served:
        # Indistinguishable from a URL target from here on, which is ADR-0059's whole
        # point: there is no field saying which of the two it was, so this is what
        # *any* configuration of an endpoint target looks like to the harness.
        target = replace(served, plants=None)
        result = _calibrate(target, [leakage_case], agent, proof_waived=True)

    [target_run] = result.target_runs
    assert target_run.plantings == ()
    assert agent.canary is None

    block = _planting_block(result, [leakage_case])
    assert block["planted"] is False
    assert block["verified"] is False
    assert block["stated"] == NOTHING_WAS_PLANTED_BY_THE_BENCH


def test_planted_content_is_planted_by_the_bench_and_still_not_read_back(
    injection_case: Case,
) -> None:
    """The third answer, and it is the honest one for content.

    The bench planted the note itself, off the case record, so *that it is there* is
    no longer the operator's statement. What it did not do is read it back: the only
    read-back available for planted content is this family's own scored attempt, and
    a precondition read off a scored attempt is not a precondition (ADR-0004).
    """
    agent = Retriever()
    with serve_callback(agent, name="retrieving") as target:
        result = _calibrate(target, [injection_case], agent)

    [target_run] = result.target_runs
    checks = {performed.plant: performed.check for performed in target_run.plantings}
    assert checks[Plant.RETRIEVED_CONTENT] is PlantCheck.NO_READ_BACK

    block = _planting_block(result, [injection_case])
    assert block["planted"] is True
    # Conjunctive: one planting read back and one not is not a verified run.
    assert block["verified"] is False


def test_the_shim_never_takes_the_canary_from_the_caller(leakage_case: Case) -> None:
    """`issue_nonce` is the only source, and two provenances are two values."""
    agent = Agent()
    with serve_callback(agent, name="supplied") as target:
        with pytest.raises(CanaryFromTwoPlaces, match="issue"):
            _calibrate(
                target,
                [leakage_case],
                agent,
                planted_nonces={target.name: "SUPPLIED-BY-THE-CALLER"},
            )
