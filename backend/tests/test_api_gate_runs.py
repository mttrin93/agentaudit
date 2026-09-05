"""What `POST /gate-runs` refuses, what it presents, what it writes, and what it
never does twice.

This is the surface PLAN.md §8 said would not exist, so most of these tests assert
that the two things the command line carried came with it (ADR-0021). A gate run is
about 830 calls against three reference agents on the operator's own provider **and**
a write-back to every case record in the library, which is one more consequence than
a target run has, so the absences asserted here are counted at the endpoint and read
off the case records rather than trusted to the run's own statement.

**That no statement can be withheld and no setting stands in for one.** Each of the
three attestation statements is refused on its own, before anything is sent and
before the library is held. Beside that, a scan: this module never constructs an
`Attestation`, so there is no line in it that could make one up, and no parameter or
field anywhere in it is named for a bypass. A flag that let a gate run proceed
unattended is what ADR-0007 forbids, and it is also why one cannot be spawned as a
subprocess — the terminal helper reads absent or piped input as a refusal.

**That the estimate is two figures against two ceilings and never a third.** The two
models share no numeric field, so there is no name under which a sum could be added
without inventing a model to hold it, and the sum itself appears nowhere in the
response.

**That declining spends nothing and writes nothing.** Asserted over the bytes of the
case records, because *nothing was written* is a claim about files and not about a
sentence, and over the wire, because *nothing was sent* is a fact about the endpoint.

**That a gate run is its own record and its own route family.** No function in the
API package names both `RunRecord` and `GateRunRecord`; a run id is a `404` on the
gate-run routes and a gate run id is a `404` under `/runs`. What *is* shared is the
consent mechanism, deliberately: one attestation record, one interrupt seam, one
approval body, because a second copy of a consent flow is a second place for it to be
weakened.

**That two overlapping gate runs cannot corrupt a case record.** One at a time on one
library, held by a lease in the library's own directory so that the command line and
the console exclude each other rather than only themselves, and refused by name
rather than queued.

**That the per-family figures come from the run and not from a document.** Compared
field for field against the `GateResult` the run left in memory, and scanned for the
document-reading this route must never grow: the figures were dropped from the
console once rather than parsed out of prose, and now they arrive from the process
that measured them.

The gate runs here are driven end to end on `stub:obedient` against the real
equipment seam, so they reach no model provider and no network beyond an ephemeral
local port — the same way the command-line gate run is tested (`test_gate.py`).
"""

from __future__ import annotations

import ast
import re
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import (
    BENCH_GATE_ROUTE,
    GATE_RUN_APPROVAL_ROUTE,
    GATE_RUNS_ROUTE,
    create_app,
)
from backend.api.gate_runs import (
    DEPLOYED_LIBRARY,
    BenchGateRuns,
    Equipment,
    GateRunBench,
    GateRunRecord,
    GateRunStatus,
    NotStartable,
    ServedAgents,
    seeded_library,
    shipped_agents,
)
from backend.api.report import ReportConfig
from backend.api.runs import BenchConfig, BenchRuns, RunStatus
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.cited import CITED_GATE_RUN, Replaced, cite, the_citation
from backend.bench.contract import TargetConfig
from backend.bench.gate_record import RecordedGateRun
from backend.bench.lease import LEASE_FILE, LibraryBusy, take_the_library
from backend.bench.library import CaseStatus, Family, load_library
from backend.bench.payload import citation
from backend.bench.registration import Attestation
from backend.bench.rule import DECLARED_RULE
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.graph.approval import Approval
from backend.graph.budget import Layer
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.model import ModelConfig, measures_the_field
from backend.targets.reference.operator import namespace_dropper, nonce_planter
from backend.targets.reference.server import ReferenceConfig, create_reference_app
from backend.targets.reference.serving import serve
from backend.targets.reference.tools import DECLARED_TOOL_NAMES
from backend.targets.reference.trivial import TRIVIAL
from backend.targets.reference.weak import WEAK
from backend.tests.conftest import (
    ADJUDICATING,
    AUTH_TOKEN,
    BENCH_ATTESTATION,
    authored_library,
    stop_every_run,
)
from backend.tests.test_api_runs import Counted, Ledger
from backend.tests.test_cited import a_passing_gate, a_record

API_DIR = Path(__file__).resolve().parents[1] / "api"

GATE_RUN_MODULES = (
    "gate_runs.py",
    "gate_run_equipment.py",
    "gate_run_state.py",
    "gate_run_writeback.py",
)
"""Every module of the gate-run side, which is what the source scans below scan.

Three tests here assert things about the *text* of the gate-run code — that it never
constructs an `Attestation`, that no name in it is a bypass, that it neither reads
`report.gate` nor imports the renderer. Those claims were written when the side was
one file. #14 split it into four, and a scan still pointed at `gate_runs.py` would
have gone on passing while the property it guards moved out from under it — the
quiet way a structural refactor weakens a test without failing it. So the list is
here, once, and a new module on this side has to be added to it.
"""
CASES_DIR = Path(__file__).resolve().parents[1] / "cases"

STATEMENT_FIELDS = (
    "authorised_to_test",
    "not_production",
    "accepts_provider_policy_and_cost",
)

SMALL_ADAPTIVE = AdaptiveBudget(turns_per_episode=2, episodes_per_family=1)
"""The adaptive layer, narrowed so these tests are minutes shorter and no weaker.

Narrowed and not removed: the layer always runs, its ceiling is a figure the operator
consents to, and a gate run that skipped it would be a gate run no operator makes.
Nothing here is decided by it (ADR-0010).
"""

SETTLED = frozenset(
    {
        GateRunStatus.DECIDED,
        GateRunStatus.DECLINED,
        GateRunStatus.UNANSWERED,
        GateRunStatus.NOT_A_GATE_RUN,
        GateRunStatus.ABORTED,
        GateRunStatus.FAILED,
    }
)
"""The states a gate run does not leave. Everything else is one still in flight."""


# --- a bench that can run a gate, and a library it may write to -----------------


def a_library(tmp_path: Path) -> Path:
    """The whole case library, copied as authored, for a run to write back to.

    The whole of it, because the gate is decided over six families and a library
    missing one is not a smaller gate but a run that cannot be gated. As authored,
    because this run appends a reading to every record it reads and a copy arriving
    with a real gate run's series already on it would let one test retire a case.
    """
    return authored_library(tmp_path / "cases")


@contextmanager
def watched_agents(ledger: Ledger) -> Iterator[ServedAgents]:
    """The three reference agents with a ledger in front of them.

    The substitutable half of the equipment seam, and the reason it is a seam: a test
    that has to look at a gate run *while it is happening* needs to stop it somewhere
    in particular, and counting messages at the endpoint is the only clock both ends
    agree on. Everything else here is what `shipped_agents` builds.
    """
    model = ModelConfig.parse("stub:obedient")
    app: FastAPI = create_reference_app(
        ReferenceConfig(model=model, auth_token=AUTH_TOKEN)
    )
    app.add_middleware(Counted, ledger=ledger)
    with serve(app) as base_url:
        yield ServedAgents(
            # Read off the same configuration the agents are served on rather than
            # written as a literal, so this equipment cannot claim to have measured
            # the field while serving a fixture (ADR-0022).
            measured_the_field=measures_the_field(model),
            targets=tuple(
                TargetConfig(
                    name=agent.name,
                    url=f"{base_url}/reference/{agent.name}/messages",
                    auth_token=AUTH_TOKEN,
                    agent_type="assistant",
                    exposes_tool_calls=True,
                    declared_tools=DECLARED_TOOL_NAMES,
                )
                for agent in (TRIVIAL, WEAK, HARDENED)
            ),
            plant=nonce_planter(base_url),
            drop=namespace_dropper(base_url),
            trivial=TRIVIAL.name,
            weak=WEAK.name,
            hardened=HARDENED.name,
        )


@dataclass
class Gating:
    """A bench that can run a gate, its registry, and the library it writes to."""

    client: TestClient
    gates: BenchGateRuns
    runs: BenchRuns
    library: Path


@contextmanager
def a_bench(
    library: Path | None,
    *,
    equipment: Equipment | None = None,
    agents: bool = True,
    adjudicating: bool = True,
    adaptive: AdaptiveBudget = SMALL_ADAPTIVE,
    attempts_per_case: int = DECLARED_RULE.attempts_per_case,
) -> Iterator[Gating]:
    """The API over one bench, and the gate-run bench beside it.

    Two declarations handed to the factory rather than one, which is the shape the
    factory takes: what a run is measured with and what a gate run needs are two
    statements about a deployment, and a bench that declared the first has not
    declared the second.
    """
    config = BenchConfig(
        cases=[],
        rule=replace(DECLARED_RULE, attempts_per_case=attempts_per_case),
        adaptive=adaptive,
        adjudicator=ADJUDICATING if adjudicating else None,
        approval_wait_seconds=60.0,
        report=ReportConfig(),
    )
    app = create_app(
        config,
        GateRunBench(
            library=library,
            equipment=(
                equipment
                if equipment is not None
                else shipped_agents("stub:obedient")
                if agents
                else None
            ),
        ),
    )
    with TestClient(app) as client:
        try:
            yield Gating(
                client=client,
                gates=cast(BenchGateRuns, app.state.gate_runs),
                runs=cast(BenchRuns, app.state.bench),
                library=library if library is not None else Path("/nowhere"),
            )
        finally:
            # See `api` in `test_api_runs.py`: a gate run left at its interrupt
            # outlives the test that started it and runs in another one's window
            # (#29). A gate run holds the library's lease as well, so a leaked one
            # is also a library the next gate run may not write to.
            stop_every_run(client)


def a_gate_request(
    withheld: str | None = None, price_per_call: str | None = "0.0005"
) -> dict[str, Any]:
    """One start request, with any one of the three statements withheld."""
    attestation = dict.fromkeys(STATEMENT_FIELDS, True)
    if withheld is not None:
        attestation[withheld] = False
    return {
        "attestation": {"identity": BENCH_ATTESTATION.identity, **attestation},
        "cost": {"price_per_call": price_per_call, "currency": "USD"},
    }


def a_confirmation(confirmed: bool = True) -> dict[str, Any]:
    return {
        "confirmed": confirmed,
        "identity": BENCH_ATTESTATION.identity,
        "reason": "" if confirmed else "not spending that today",
    }


def settled(record: GateRunRecord, seconds: float = 180.0) -> GateRunRecord:
    """Wait for a gate run to reach a state it does not leave."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if record.status in SETTLED:
            return record
        time.sleep(0.02)
    raise AssertionError(f"gate run {record.gate_run_id} is still {record.status}")


def started(gating: Gating) -> dict[str, Any]:
    """Start a gate run and hand back what the route said, refusing a refusal."""
    response = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())
    assert response.status_code == 202, response.text
    return cast(dict[str, Any], response.json())


def approval_of(gate_run_id: str) -> str:
    return GATE_RUN_APPROVAL_ROUTE.format(gate_run_id=gate_run_id)


def library_bytes(library: Path) -> dict[str, str]:
    """Every case record as it stands, so *nothing was written* is checkable."""
    return {
        record.name: record.read_text(encoding="utf-8")
        for record in sorted(library.glob("*.toml"))
    }


# --- the attestation, which nothing may stand in for ----------------------------


@pytest.mark.parametrize("withheld", STATEMENT_FIELDS)
def test_a_gate_run_cannot_start_with_any_one_statement_withheld(
    withheld: str, tmp_path: Path
) -> None:
    """Each of the three, refused on its own, before anything is held or sent.

    Parametrised because the interesting failures are the second and the third. A
    gate run attacks the bench's own equipment, so it is tempting to think the
    statements are ceremony here — but the payloads reach the operator's model
    provider under the operator's credentials, and the inference is billed to them
    exactly as a target run's is. An API that accepted two of three would be dropping
    the statements ADR-0007 exists to make explicit, on the one surface where nobody
    would notice.
    """
    library = a_library(tmp_path)
    before = library_bytes(library)

    with a_bench(library) as gating:
        response = gating.client.post(
            GATE_RUNS_ROUTE, json=a_gate_request(withheld=withheld)
        )

        assert response.status_code == 422
        assert dict(Attestation.STATEMENTS)[withheld] in response.json()["detail"]
        # No gate run exists, so there is nothing to poll and nothing to confirm.
        assert gating.gates.records() == []

    # And the library was never even held, let alone written to: no lease was taken,
    # and not one case record changed a byte.
    assert not (library / LEASE_FILE).exists()
    assert library_bytes(library) == before


def test_the_list_of_gate_run_modules_is_every_module_of_the_gate_run_side() -> None:
    """The roster the three scans below read, held to the files that are actually
    there.

    Without this the list is the weakest thing in the file: a fifth `gate_run_*`
    module lands, nobody adds it, and all three scans go on passing over four files
    while the property they guard lives in five. That is the same failure the roster
    was written to fix, one level up — a scan that narrows silently — so the roster
    itself is asserted rather than trusted.

    Derived from the directory rather than from a second list, because a second list
    would need a third test.
    """
    on_disk = {
        source.name
        for source in sorted(API_DIR.glob("*.py"))
        if source.name == "gate_runs.py" or source.name.startswith("gate_run_")
    }

    assert set(GATE_RUN_MODULES) == on_disk, (
        "the gate-run side has a module the source scans in this file do not read. "
        "Add it to GATE_RUN_MODULES: a scan pointed at four files while the code "
        "lives in five passes without asserting anything"
    )


def test_no_flag_or_setting_lets_a_gate_run_proceed_without_an_attestation() -> None:
    """The prohibition as a scan, because a flag is what this failure would look like.

    Three assertions over the source, each aimed at a different way the consent could
    be routed around. **This module never constructs an `Attestation`**: it receives
    one, so there is no line in it that could fill in three booleans on somebody's
    behalf. **No name in it is a bypass**: no parameter, field or constant is called
    `yes`, `force`, `assume`, `unattended` or any of their neighbours, so a flag
    would have to be added under a name a reviewer reads. **It reads no environment**:
    that one is asserted for every module of this package in `test_api_runs.py`, and
    it is the reason a variable cannot become the flag either.

    A behavioural counterpart is above, parametrised over the three statements. This
    is the half that catches the *next* change rather than the current behaviour.
    """
    source = "\n".join(
        (API_DIR / module).read_text(encoding="utf-8") for module in GATE_RUN_MODULES
    )
    tree = ast.parse(source)

    built = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Attestation"
    ]
    assert built == [], (
        "the gate-run module builds an Attestation. It must only ever be handed one: "
        "a record constructed here is three statements nobody made"
    )

    bypass = re.compile(
        r"(?:^|_)(yes|force|assume|assumed|bypass|skip|skipped|unattended|"
        r"noninteractive|interactive|auto|automatic|insecure|override|"
        r"without_attestation)(?:$|_)"
    )
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            named.add(node.arg)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            named.add(node.target.id)
        elif isinstance(node, ast.Assign):
            named.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
    offending = sorted(name for name in named if bypass.search(name.lower()))
    assert offending == [], (
        f"{offending} reads like a way to run a gate unattended. ADR-0007 forbids "
        "one, and ADR-0021 reversed PLAN §8 without it"
    )


# --- the estimate, per layer, before anything is sent ---------------------------


def test_the_estimate_is_two_figures_against_two_ceilings_and_no_third(
    tmp_path: Path,
) -> None:
    """What an operator agrees to: the scored layer exactly, the adaptive as a bound.

    The scored figure is a multiplication and this test does it: every live case at
    the declared attempts per case, against each of the three agents, plus one
    registration probe each. The adaptive figure is a ceiling, and the two are
    reported against their own enforced ceilings with **no third figure anywhere** —
    asserted over the field names, so that a sum has nowhere to live, and over the
    text, so that a sum has not been written into a sentence.
    """
    library = a_library(tmp_path)
    cases = [case for case in load_library(library) if case.status is CaseStatus.ACTIVE]

    with a_bench(library) as gating:
        response = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())
        assert response.status_code == 202, response.text
        body = cast(dict[str, Any], response.json())
        estimate = body["estimate"]

        scored = estimate["scored"]
        adaptive = estimate["adaptive"]
        assert scored["attempt_calls"] == 3 * (len(cases) * 10 + 1)
        assert scored["kind"] == "exact"
        assert adaptive["turn_calls"] == 3 * (SMALL_ADAPTIVE.turn_ceiling), (
            "the adaptive figure is the layer's own ceiling, per agent"
        )
        assert adaptive["kind"] == "ceiling"

        # Each beside the ceiling it is enforced against, and neither can borrow the
        # other's: two counters, two limits (ADR-0007, ADR-0010).
        assert scored["attempt_ceiling"] >= scored["attempt_calls"]
        assert adaptive["turn_ceiling"] >= adaptive["turn_calls"]

        # No numeric field is shared by the two layers, so there is no name under
        # which a total could be added without inventing a model to hold it.
        numbers = {
            layer: {
                field
                for field, value in figure.items()
                if isinstance(value, int | float) and not isinstance(value, bool)
            }
            for layer, figure in (("scored", scored), ("adaptive", adaptive))
        }
        assert numbers["scored"].isdisjoint(numbers["adaptive"])

        # And no third figure. Three ways, because a total arrives under a name
        # before it arrives as a number: no field on the estimate is named for one,
        # no field holds the sum, and the sum appears in no sentence on the response.
        blended = scored["attempt_calls"] + adaptive["turn_calls"]
        for field in estimate:
            assert not re.search(
                r"total|sum|combined|both|overall|together|blended", field
            ), f"{field} reads like a figure spanning the two layers"
        for field, value in estimate.items():
            assert value != blended, f"{field} is the two layers added together"
        # As a figure and not as a substring. The response carries a gate run id, and
        # three digits fall inside a random uuid often enough to fail this on a run
        # that changed nothing: `219f579ade63` is not a total, and `\b` is what tells
        # it from one. A sum in a sentence still reads as a number either way.
        assert not re.search(rf"\b{blended}\b", response.text), (
            f"{blended} is the two layers added together, in a sentence"
        )

        # Nothing has been spent: the gate run is holding its interrupt, and the
        # figures above are what it is holding.
        [record] = gating.gates.records()
        assert record.status is GateRunStatus.AWAITING_APPROVAL
        assert record.spent == dict.fromkeys(Layer, 0)


def test_declining_the_estimate_spends_nothing_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """A no at the interrupt: no call, no reading, no retirement, no lease left.

    The strongest of the three absences is the middle one. A gate run's write-back is
    not a side effect of spending — it is a second consequence, on the library every
    user run is measured with — so a declined gate run has to leave the case records
    byte for byte as they were, and this reads them rather than trusting a sentence.
    """
    library = a_library(tmp_path)
    before = library_bytes(library)

    with a_bench(library) as gating:
        body = started(gating)
        answered = gating.client.post(
            approval_of(body["gate_run_id"]), json=a_confirmation(confirmed=False)
        )

        assert answered.status_code == 200
        [record] = gating.gates.records()
        settled(record)
        assert record.status is GateRunStatus.DECLINED
        assert record.spent == dict.fromkeys(Layer, 0)
        assert record.gate is None and record.written is None
        assert "nothing was spent" in record.statement
        assert "not one case record was written to" in record.statement

        # The lease going back is the observable end of a gate run, and it goes back
        # however the run ended: one left behind by a declined run is a library
        # nobody may ever write to again, with no run writing to it.
        _until(
            lambda: not (library / LEASE_FILE).exists(),
            failure=(
                "a declined gate run left the library held. The lease is released "
                "however the run ends, or the next one is refused for ever"
            ),
        )

    assert library_bytes(library) == before


# --- a gate run is not a run ----------------------------------------------------


def test_no_function_in_the_api_takes_both_a_gate_run_and_a_run() -> None:
    """The invariant carried by the type, asserted over every signature there is.

    ADR-0010's discipline on a new axis. A run produces rates about somebody's agent
    and a gate run produces a decision about this bench, and the moment one function
    accepts either, the difference is one `isinstance` away from being a field name.
    So no function in this package names both records, and the two statuses are two
    enums with two different terminal states — a run *completes* and has a report, a
    gate run is *decided* and has an outcome.

    What is deliberately shared is the consent mechanism, and it is named here so
    that the sharing is a decision rather than an oversight: one `Attestation`, one
    `PendingApproval`, one `ApprovalRequest`. A second copy of a consent flow is a
    second place for it to be weakened, which is the failure ADR-0007 is about.
    """
    for source in sorted(API_DIR.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            named = _types_named(node)
            assert not {"RunRecord", "GateRunRecord"} <= named, (
                f"{source.name}:{node.name} takes both a run and a gate run. They "
                "are two records about two subjects (ADR-0018): if you are widening "
                "a signature to accept both, stop"
            )

    gate_run_states = {str(status) for status in GateRunStatus}
    run_states = {str(status) for status in RunStatus}
    assert str(RunStatus.COMPLETED) not in gate_run_states
    assert str(GateRunStatus.DECIDED) not in run_states


def test_a_run_id_is_not_a_gate_run_id_on_either_route_family(
    tmp_path: Path,
) -> None:
    """The two families do not answer for each other's identifiers.

    A gate run id posted to a run's approval route would be an interrupt answered for
    a record that route cannot reach, and the direction that matters is the one where
    a `yes` spends money: both are a named `404` rather than a confirmation that
    lands somewhere unexpected.
    """
    library = a_library(tmp_path)
    with a_bench(library) as gating:
        body = started(gating)
        gate_run_id = str(body["gate_run_id"])

        under_runs = gating.client.post(
            f"/runs/{gate_run_id}/approval", json=a_confirmation()
        )
        assert under_runs.status_code == 404
        assert gate_run_id in under_runs.json()["detail"]

        # And the same from the other end, with an id no gate run ever had.
        under_gate_runs = gating.client.post(
            approval_of("00000000-0000-0000-0000-000000000000"),
            json=a_confirmation(),
        )
        assert under_gate_runs.status_code == 404
        assert "no gate run" in under_gate_runs.json()["detail"]

        [record] = gating.gates.records()
        assert record.status is GateRunStatus.AWAITING_APPROVAL
        assert record.spent == dict.fromkeys(Layer, 0)

    # And the two families do not share an identifier, which is what keeps the two
    # `404`s above from being an accident of which route was declared first: every
    # route under `/runs` takes a `run_id`, every route under `/gate-runs` takes a
    # `gate_run_id`, and no path takes both.
    app = create_app(BenchConfig(cases=[]), GateRunBench())
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path.startswith(GATE_RUNS_ROUTE):
            assert "{run_id}" not in route.path, (
                f"{route.path} names a run id on the gate-run family. One identifier "
                "for both records is the widening ADR-0021 asks a reader to stop at"
            )
        elif route.path.startswith("/runs"):
            assert "{gate_run_id}" not in route.path, (
                f"{route.path} names a gate run id under /runs"
            )


def test_the_gate_run_routes_are_their_own_family_and_bench_stays_read_only() -> None:
    """Where a gate run can be started, exactly, over the whole route table.

    This is the assertion #80 made in the opposite direction, kept as an assertion
    rather than deleted: it used to say no route on this bench starts a gate run, and
    it now says which ones do and that there are no others. The set is pinned, so a
    second start route — under a friendlier word, or under `/bench` where everything
    is meant to be a read — fails here whatever it is called.
    """
    app = create_app(BenchConfig(cases=[]), GateRunBench())
    gate_routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and "gate" in route.path
        for method in route.methods or set()
        if method != "HEAD"
    }

    assert gate_routes == {
        ("/bench/gate", "GET"),
        ("/bench/gate/record", "GET"),
        (GATE_RUNS_ROUTE, "POST"),
        (GATE_RUNS_ROUTE, "GET"),
        ("/gate-runs/{gate_run_id}", "GET"),
        (GATE_RUN_APPROVAL_ROUTE, "POST"),
    }

    # And the two that are not reads are the two the consent flow guards: the one
    # that records the attestation and declares the estimate, and the one that
    # answers the halt. Nothing else on this prefix writes.
    writes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(GATE_RUNS_ROUTE)
        for method in route.methods or set()
        if method not in {"GET", "HEAD"}
    }
    assert writes == {(GATE_RUNS_ROUTE, "POST"), (GATE_RUN_APPROVAL_ROUTE, "POST")}


# --- where a gate run cannot happen, the bench says so --------------------------


def test_a_bench_without_the_reference_agents_offers_no_start_control(
    tmp_path: Path,
) -> None:
    """Test equipment is allowed to be absent, and then this is a stated absence.

    The three reference agents never reach a user and are served by a different
    application, so a build that leaves them out is a legitimate deployment — it just
    cannot run a gate, because there is no contrast to decide one over. The screen
    reads this refusal and offers no control, which is why the reason is a *name* and
    not only a sentence.
    """
    with a_bench(a_library(tmp_path), agents=False) as gating:
        listed = gating.client.get(GATE_RUNS_ROUTE).json()

        assert listed["start"]["available"] is False
        assert listed["start"] == {
            "available": False,
            "refusal": str(NotStartable.NO_REFERENCE_AGENTS),
            "stated": NotStartable.NO_REFERENCE_AGENTS.stated(),
        }
        assert "does not ship the three reference agents" in listed["start"]["stated"]
        assert listed["gate_runs"] == []

        refused = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())
        assert refused.status_code == 409
        assert refused.json()["detail"]["outcome"] == str(
            NotStartable.NO_REFERENCE_AGENTS
        )
        assert gating.gates.records() == []


def test_the_equipment_is_absent_when_the_deployment_does_not_ship_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`shipped_agents` answers with `None` rather than raising on the import.

    The absence has to be an answer at the seam, because everything above it — the
    route's refusal, the screen's missing control — is built on being told. A build
    without `backend/targets/reference` is exercised by making its import fail, which
    is what such a build does.
    """
    monkeypatch.setitem(sys.modules, "backend.targets.reference.server", None)

    assert shipped_agents("stub:obedient") is None
    # The seam's defining module, named so that the answer cannot come from a second
    # `shipped_agents` somewhere else. It moved with #14's split of `gate_runs.py`;
    # the name is still importable from `backend.api.gate_runs`, which is what the
    # routes read it as.
    assert shipped_agents.__module__ == "backend.api.gate_run_equipment"


def test_a_bench_with_no_writable_library_runs_no_gate() -> None:
    """No durable library, no gate run — and the refusal names where one would live.

    A gate run's write-back is evidence: the decay series every retirement is
    re-derived from. Written inside a container image it is gone at the next
    redeploy, and a bench that had retired a case would come back with it live and no
    record that it ever went. So the absence of somewhere durable is a refusal rather
    than a write into a filesystem about to be thrown away.
    """
    with a_bench(None) as gating:
        listed = gating.client.get(GATE_RUNS_ROUTE).json()

        assert listed["start"]["available"] is False
        assert listed["start"]["refusal"] == str(NotStartable.NO_WRITABLE_LIBRARY)
        assert str(DEPLOYED_LIBRARY) in listed["start"]["stated"]
        assert "next redeploy" in listed["start"]["stated"]

        refused = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())
        assert refused.status_code == 409
        assert refused.json()["detail"]["outcome"] == str(
            NotStartable.NO_WRITABLE_LIBRARY
        )


def test_a_bench_with_no_adjudicating_instrument_runs_no_gate(tmp_path: Path) -> None:
    """The gate is decided over six families and two of them are adjudicated.

    Without an adjudicator those two are not fit to report and are excluded, which
    leaves four fit families and an answer the rule cannot be put to (ADR-0015). The
    refusal is before the spend rather than after it, on the same reasoning as every
    other stated absence in this bench: 830 calls to reach an answer that was
    arithmetic before the first one was sent.
    """
    with a_bench(a_library(tmp_path), adjudicating=False) as gating:
        listed = gating.client.get(GATE_RUNS_ROUTE).json()
        assert listed["start"]["available"] is False
        assert listed["start"]["refusal"] == str(NotStartable.NO_ADJUDICATOR)

        refused = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())
        assert refused.status_code == 409
        assert refused.json()["detail"]["outcome"] == str(NotStartable.NO_ADJUDICATOR)


def test_the_deployed_library_is_a_mount_seeded_once_and_never_overwritten(
    tmp_path: Path,
) -> None:
    """Three states, three answers, and the third one is the one that matters.

    No mount is a deployment that declared no storage, and it gets `None`. An empty
    mount is a first boot, and the image's admitted library is copied in. A mount
    with records in it is the library this deployment has been accumulating, and it
    is left exactly as it is — a seed written over a series would erase the decay
    history every retirement is re-derived from, which is the one thing here that
    cannot be recomputed.
    """
    absent = tmp_path / "not-mounted"
    assert seeded_library(absent, CASES_DIR) is None
    assert not absent.exists(), "answering the question must not create the volume"

    empty = tmp_path / "mount"
    empty.mkdir()
    assert seeded_library(empty, CASES_DIR) == empty
    assert {record.name for record in empty.glob("*.toml")} == {
        record.name for record in CASES_DIR.glob("*.toml")
    }

    accumulated = tmp_path / "held"
    accumulated.mkdir()
    (accumulated / "data-leakage-001.toml").write_text(
        "held = true\n", encoding="utf-8"
    )
    assert seeded_library(accumulated, CASES_DIR) == accumulated
    assert (accumulated / "data-leakage-001.toml").read_text(
        encoding="utf-8"
    ) == "held = true\n"
    assert len(list(accumulated.glob("*.toml"))) == 1


# --- one writer at a time -------------------------------------------------------


def test_the_library_lease_admits_one_holder_and_names_it(tmp_path: Path) -> None:
    """The mechanism under the refusal: an exclusive create, and a named holder.

    A file rather than a lock in memory, because the command-line gate run and a
    console gate run are two processes over one directory: a lock either held
    privately would be invisible to the other.
    """
    library = a_library(tmp_path)
    held = take_the_library(library, "the first caller")

    with pytest.raises(LibraryBusy) as refused:
        take_the_library(library, "the second caller")

    assert "the first caller" in str(refused.value)
    assert str(held.path) in str(refused.value)
    assert "nothing has been sent and nothing has been spent" in str(refused.value)

    held.release()
    # And released is released: the next caller is not refused for ever.
    take_the_library(library, "the third caller").release()
    assert not (library / LEASE_FILE).exists()


def test_a_second_gate_run_is_refused_while_the_first_holds_the_library(
    tmp_path: Path,
) -> None:
    """Two overlapping gate runs cannot corrupt a case record, because there is one.

    A gate run reads every case record and writes back to every one of them, so two
    of them overlapping is a read-modify-write race: the second one's write is taken
    against a series missing a reading the first one is about to store, and the
    retirement it decides is re-derived from records that never held that state.

    The refusal is by name and immediate. Queueing would hold an HTTP request open
    across somebody else's 830 calls, and the answer an operator needs is *not now*.
    Asserted at both ends: the start route refuses, and the list route says so before
    a screen draws a control.
    """
    library = a_library(tmp_path)
    # The second message is held, so the assertions below are read off a gate run
    # stopped inside its second attempt rather than one somewhere past a count.
    ledger = Ledger(hold_after=1)

    with (
        watched_agents(ledger) as watched,
        a_bench(
            library, equipment=lambda: _already(watched), attempts_per_case=2
        ) as gating,
    ):
        first = started(gating)
        gating.client.post(approval_of(first["gate_run_id"]), json=a_confirmation())

        # Held at the endpoint, so the first gate run is genuinely in flight and
        # genuinely holding the library while the second one asks. Waited on the
        # hold rather than on a message count reached, so the gate run is stopped
        # rather than merely somewhere past a number.
        ledger.wait_until_held()
        assert (library / LEASE_FILE).exists()
        assert first["gate_run_id"] in (library / LEASE_FILE).read_text(
            encoding="utf-8"
        )

        second = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())
        assert second.status_code == 409
        assert second.json()["detail"]["outcome"] == str(NotStartable.ALREADY_IN_FLIGHT)
        assert (
            "one runs at a time on one library" in second.json()["detail"]["statement"]
        )

        listed = gating.client.get(GATE_RUNS_ROUTE).json()
        assert listed["start"]["available"] is False
        assert listed["start"]["refusal"] == str(NotStartable.ALREADY_IN_FLIGHT)
        assert len(listed["gate_runs"]) == 1

        ledger.release()
        [record] = gating.gates.records()
        settled(record)

    # One gate run, one reading per case record. The count is the assertion: two
    # overlapping runs would have left two, or one written over the other.
    for case in load_library(library):
        assert len(case.history) == 1, (
            f"{case.id} came out of one gate run with {len(case.history)} readings"
        )
    assert not (library / LEASE_FILE).exists()


def test_a_gate_run_is_refused_while_another_process_holds_the_library(
    tmp_path: Path,
) -> None:
    """The command line and the console exclude each other, not only themselves.

    The lease this test writes is the one `scripts/gate.py` takes: same file, same
    directory, same refusal. A console gate run that ignored it would append its
    series to records a terminal gate run was in the middle of writing.
    """
    library = a_library(tmp_path)
    take_the_library(library, "a gate run at a terminal, on another process")

    with a_bench(library) as gating:
        refused = gating.client.post(GATE_RUNS_ROUTE, json=a_gate_request())

        assert refused.status_code == 409
        assert refused.json()["detail"]["outcome"] == str(
            NotStartable.ALREADY_IN_FLIGHT
        )
        assert "a gate run at a terminal" in refused.json()["detail"]["statement"]
        assert gating.gates.records() == []


# --- while it runs, and what it decided -----------------------------------------


def test_progress_is_reported_per_layer_while_the_gate_run_is_in_flight(
    tmp_path: Path,
) -> None:
    """Where it has got to, in the units each layer is counted in, and no third.

    Family, case and attempt in the scored layer; family, episode and turn in the
    adaptive one — six words for six things, and no field anywhere that adds the two
    (CONTEXT.md, ADR-0010). The adaptive layer says it has not been reached rather
    than reporting a zero, because a zero there reads as a layer that ran and found
    nothing.
    """
    library = a_library(tmp_path)
    # The eighth message is held: far enough in that the scored layer has a
    # position to report, and — with the whole library to get through at two
    # attempts a case — nowhere near the adaptive layer, which is the other half
    # of what this reads. Which case the eighth message belongs to is the
    # library's running order rather than this test's business, so the position is
    # asserted by shape and the figures by floor.
    ledger = Ledger(hold_after=7)

    with (
        watched_agents(ledger) as watched,
        a_bench(
            library, equipment=lambda: _already(watched), attempts_per_case=2
        ) as gating,
    ):
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        ledger.wait_until_held()

        reading = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()

        scored = reading["scored"]
        assert scored["reached"] is True
        assert set(scored["position"]) == {"family", "case_id", "attempt"}
        assert scored["position"]["attempt"] >= 1
        assert scored["calls_spent"] >= 1

        adaptive = reading["adaptive"]
        assert adaptive["reached"] is False
        assert adaptive["position"] is None
        assert "has not reached the adaptive layer" in adaptive["statement"]

        # Two layers and nothing spanning them: no key holds the sum of the two
        # spends, and there is no field on the reading outside them that could.
        blended = scored["calls_spent"] + adaptive["calls_spent"]
        assert not any(
            value == blended for key, value in reading.items() if isinstance(value, int)
        )
        assert set(reading) == {
            "gate_run_id",
            "status",
            "statement",
            "rule",
            "scored",
            "adaptive",
            "families",
            "recent",
            "decision",
            "written",
        }
        assert reading["decision"] is None

        ledger.release()
        [record] = gating.gates.records()
        settled(record)


def test_the_six_families_and_the_last_payloads_are_reported_while_it_runs(
    tmp_path: Path,
) -> None:
    """How far each family has got, and the attempts behind the last few calls.

    **Six rows over six denominators, and nothing that adds them.** A family's
    denominator is its own cases at the declared attempts per case against each of
    the three agents, and the row carries the count against it — never a rate, never
    a share of a run-wide total, and never a count of the verdicts so far. Progress
    is how far a family has got, and how well it went is a rate with an interval and
    a band that only the decision may carry (ADR-0005).

    **And the payloads, which are the bench attacking its own equipment.** The three
    reference agents are this project's own constructs, so the message sent and the
    reply it drew are the bench's own transcript and nobody else's traffic. Each
    carries the verdict from the attacker's point of view and how it was reached,
    because *resisted* by a deterministic check and *resisted* in a judge's opinion
    are two different facts (ADR-0004).
    """
    library = a_library(tmp_path)
    active = [
        case for case in load_library(library) if case.status is CaseStatus.ACTIVE
    ]
    ledger = Ledger(hold_after=7)

    with (
        watched_agents(ledger) as watched,
        a_bench(
            library, equipment=lambda: _already(watched), attempts_per_case=2
        ) as gating,
    ):
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        ledger.wait_until_held()

        reading = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()

        families = reading["families"]
        assert [row["family"] for row in families] == [str(one) for one in Family], (
            "six rows, in the enum's own order, whether or not a family has started"
        )
        for row in families:
            cases = [case for case in active if str(case.family) == row["family"]]
            # Its own denominator: this family's cases, at the declared attempts per
            # case, against each of the three agents.
            assert row["of"] == len(cases) * 2 * 3
            assert 0 <= row["attempted"] <= row["of"]
            assert [rate["agent"] for rate in row["agents"]] == [
                "hardened",
                "weak",
                "trivial",
            ]
            assert sum(one["attempted"] for one in row["agents"]) == row["attempted"]
            assert sum(one["of"] for one in row["agents"]) == row["of"]
            # No verdict count on the *row*. The three agents' verdicts are three
            # readings and never one: the trivial agent is built to fail, so a family
            # total over the three would be two thirds broken by construction and
            # would say nothing about any of them.
            assert set(row) == {"family", "attempted", "of", "agents"}
            for one in row["agents"]:
                assert set(one) == {
                    "agent",
                    "attempted",
                    "of",
                    "resisted",
                    "succeeded",
                }
                # Every attempt made has exactly one verdict, so the two split what
                # was attempted and neither is a rate: no denominator is divided here
                # and none of the three is added to another.
                assert one["resisted"] + one["succeeded"] == one["attempted"]

        # Something has been attempted by now, and no field on the reading holds the
        # six rows added together.
        assert sum(row["attempted"] for row in families) >= 1
        crossing = sum(row["attempted"] for row in families)
        assert not any(
            value == crossing
            for key, value in reading.items()
            if isinstance(value, int) and not isinstance(value, bool)
        )

        recent = reading["recent"]
        # The last exchange and only it. A tail of five was five copies of the same
        # attack in a column — the screen shows what is happening now, and what
        # happened before it is in the record the run writes.
        assert len(recent) == 1, "the last call, and never the transcript log"
        for payload in recent:
            assert set(payload) == {
                "family",
                "case_id",
                "agent",
                "attempt",
                "sent",
                "reply",
                "verdict",
                "verdict_class",
                "status_code",
                "sends",
            }
            assert payload["verdict"] in {"succeeded", "resisted"}
            assert payload["verdict_class"] in {"deterministic", "judged"}
            assert payload["sent"], "the message that went on the wire"
            assert payload["agent"] in {"hardened", "weak", "trivial"}
            assert payload["attempt"] >= 1

        ledger.release()
        [record] = gating.gates.records()
        settled(record)


def test_the_declared_rule_is_served_above_the_decision(tmp_path: Path) -> None:
    """The bar first, then what it answered — on the wire, in that order.

    A gate run's outcome read with no rule beside it is a verdict somebody trusted.
    The rule is `DECLARED_RULE` rather than a copy kept for a screen, so a threshold
    moved in `rule.py` moves here and a threshold moved here is impossible, and it is
    the first thing on the response for the same reason it is the first thing on the
    screen (ADR-0003).
    """
    library = a_library(tmp_path)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)

        reading = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()

    assert record.status is GateRunStatus.DECIDED, record.statement
    keys = list(reading)
    assert keys.index("rule") < keys.index("decision")
    assert reading["rule"]["discrimination_floor"] == DECLARED_RULE.discrimination_floor
    assert reading["rule"]["families_required"] == DECLARED_RULE.families_required
    # The whole rule, in the bench's own words, so the outcome is re-derivable.
    for clause in ("per-family pass", "monotonicity", "not fit to report"):
        assert clause in reading["rule"]["stated"]
    assert reading["decision"]["outcome"] in {"passed", "failed", "not_decided"}


def test_the_per_family_figures_come_from_the_run_and_not_from_a_document(
    tmp_path: Path,
) -> None:
    """The three rates and the `D`, compared with the result held in memory.

    The console dropped these figures once rather than parse them out of the gate
    run's own prose, and this is the route that makes them available honestly: they
    are read off the `GateResult` the run that just happened left behind. So the
    assertion is an equality against that result, field for field, and beside it a
    scan of the module for the document-reading it must never grow.
    """
    library = a_library(tmp_path)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)
        reading = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()

    assert record.gate is not None
    outcomes = {str(one.family): one for one in record.gate.decision.outcomes}
    served = {family["family"]: family for family in reading["decision"]["families"]}
    assert set(served) == set(outcomes)

    for family, figure in served.items():
        outcome = outcomes[family]
        assert figure["discrimination"] == outcome.discrimination
        assert figure["passes"] == outcome.passes
        assert figure["inversions"] == outcome.monotonicity.inversions
        assert [rate["agent"] for rate in figure["rates"]] == [
            "hardened",
            "weak",
            "trivial",
        ]
        for rate, measured in zip(
            figure["rates"],
            (outcome.rates.hardened, outcome.rates.weak, outcome.rates.trivial),
            strict=True,
        ):
            assert rate["value"] == measured.value
            assert (rate["successes"], rate["attempts"]) == (
                measured.successes,
                measured.attempts,
            )

    # Every attempt is counted and the library version is the one the run was made
    # against, off the run state rather than derived at reporting time.
    assert reading["decision"]["attempts"] == record.gate.attempts
    assert reading["decision"]["library"] == {
        "cases": record.gate.library.cases,
        "digest": record.gate.library.digest,
    }

    # And there was no document to read. The library this run wrote to holds no
    # Markdown at all, so the figures above cannot have been parsed out of prose:
    # there is no prose. What the run did leave beside its readings is its own record
    # as fields, and the citation the bench now carries names it (ADR-0023) — which
    # is the same claim from the other end, because a citation pointing at a `.json`
    # is a citation nothing has to read a sentence to follow.
    assert list(library.glob("*.md")) == []
    cited = gating.runs.config.report.gate
    assert cited is not None
    assert cited.record.endswith(".json")
    assert (library / cited.record).exists()

    # The module could not read one either. Parsing the bench's own output would mean
    # reaching the renderer or the script that writes it, and it imports neither —
    # which is the import-level form of the reason the spec dropped these figures
    # rather than parse them (spec §75).
    imported = {
        name for module in GATE_RUN_MODULES for name in _imports_of(API_DIR / module)
    }
    assert not [name for name in imported if name.startswith("scripts")]
    assert "backend.bench.rendering" not in imported


def test_the_decision_carries_no_figure_spanning_two_families(
    tmp_path: Path,
) -> None:
    """Six families, six lines, and nothing that adds two of them.

    The console may not construct a score the report withholds, and a gate run's
    response is the surface most likely to grow one: it holds six discrimination
    scores at once, and a mean of them would look like a figure about the bench.
    There is no field for one, and no value on the response is the sum or the mean of
    the six.
    """
    library = a_library(tmp_path)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)
        decision = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()[
            "decision"
        ]

    scores = [family["discrimination"] for family in decision["families"]]
    assert len(scores) >= 5
    combined = {sum(scores), sum(scores) / len(scores)}
    # The three counts are counts *of families* — four of six passing, five of six
    # monotonic, the fit denominator — which the rule declares and the decision is
    # read on. Every other figure on the response is checked against the sum and the
    # mean of the six discrimination scores, which are the two shapes a composite
    # would arrive in.
    counted = {"families_passing", "families_monotonic", "fit_families", "attempts"}
    for field, value in decision.items():
        if field in counted or not isinstance(value, int | float):
            continue
        assert value not in combined, f"{field} combines the six families"
    for count in counted:
        assert decision[count] == int(decision[count])
    # The counts that are over families are counts of families and never of rates:
    # four of six passing is a count, and it is the count the rule declares.
    assert decision["families_passing"] <= decision["fit_families"]
    assert "severity" not in str(decision).lower()


def test_the_gate_run_writes_its_series_back_to_the_library_it_read(
    tmp_path: Path,
) -> None:
    """`D` for every case it read, on that case's own record, in the declared library.

    The write-back is the half of a gate run that outlives it: the series the *next*
    gate run reads and every retirement is re-derived from. It lands in the directory
    the deployment declared — never in the image's own copy, which is the one this
    process booted from and the one a redeploy would replace.
    """
    library = a_library(tmp_path)
    image = library_bytes(CASES_DIR)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)
        reading = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()

    assert record.written is not None
    stored = load_library(library)
    assert record.written.readings == len(stored)
    for case in stored:
        assert len(case.history) == 1, (
            f"{case.id} came out of a gate run with no stored D. A series the route "
            "does not write is a decay chart nobody has"
        )
        # One run below the floor is not two: the rule needs two consecutive runs,
        # so nothing retires here and the assertion is that nothing did.
        assert case.status is CaseStatus.ACTIVE
        # And the reading says which kind of run took it. This bench serves the stub
        # fixture, so its readings are marked as not a measurement of the field and
        # the rule will decline to retire on them however many it stores (ADR-0022).
        # Asserted here because the answer travels from the equipment that served the
        # agents: this module cannot ask `Provider` itself, and a write-back that
        # stored the permissive answer would make a free console run able to retire.
        assert not case.history[0].measured_the_field, (
            f"{case.id} carries a reading claiming to have measured the field, from "
            "a run served by a fixture. Two of those retire the case (#43)"
        )

    assert reading["written"]["library"] == str(library)
    assert reading["written"]["retired"] == []
    assert "never deleted" in reading["written"]["stated"]

    # The image's own library is untouched, byte for byte. A gate run that wrote
    # there would have written into a filesystem the next redeploy replaces.
    assert library_bytes(CASES_DIR) == image


# --- the citation this gate run earned (ADR-0023) -----------------------------


def test_a_console_gate_run_updates_the_gate_this_bench_cites(tmp_path: Path) -> None:
    """The second reversal, end to end: the bench cites the run it just made.

    ADR-0021 recorded this as shut — "the bench does not start citing the gate run it
    just made" — and ADR-0023 opens it. Asserted on all three surfaces the citation
    reaches, because one of them changing and not the others is exactly how a screen
    comes to state a gate result no artefact carries (ADR-0018): the route the console
    reads, the `ReportConfig` every finished run's provenance block is built from, and
    the library the next process will boot with.
    """
    library = a_library(tmp_path)

    with a_bench(library, attempts_per_case=2) as gating:
        assert gating.client.get(BENCH_GATE_ROUTE).json()["citation"]["cited"] is False

        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)
        cited = gating.client.get(BENCH_GATE_ROUTE).json()["citation"]

        assert record.status is GateRunStatus.DECIDED
        assert record.gate is not None
        # The route now cites this gate run, in the outcome the run reached rather
        # than the passing one: a citation is what the bench last put itself through.
        assert cited["cited"] is True
        assert cited["outcome"] == str(record.gate.decision.outcome)
        assert cited["library"] == {
            "cases": record.gate.library.cases,
            "digest": record.gate.library.digest,
        }
        # And the same citation is on the record every report is signed against, so
        # the screen and the artefact cannot state two different gate results.
        carried = gating.runs.config.report.gate
        assert carried is not None
        assert citation(carried) == cited

    # Durable, and in the library rather than in this process: the next boot reads it
    # off the volume the gate run wrote to (`app.deployed_bench`).
    assert (library / CITED_GATE_RUN).exists()
    assert the_citation(library) == carried


def test_the_citation_is_written_while_this_gate_run_still_holds_the_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under the same lease as the write-back, so two gate runs cannot interleave.

    The readings and the citation are one critical section: a citation written after
    the lease went back could be overwritten by a second gate run that had already
    stored its own readings, and the bench would cite a library version that no
    longer describes the cases. Asserted at the moment of the write rather than
    afterwards — the lease file has to be there when `cite` is called, and a call
    outside the lease is a citation nothing excludes.
    """
    library = a_library(tmp_path)
    held: list[bool] = []

    def under_the_lease(record: RecordedGateRun, directory: Path) -> Replaced:
        held.append((directory / LEASE_FILE).exists())
        return cite(record, directory)

    monkeypatch.setattr("backend.api.gate_run_writeback.cite", under_the_lease)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)

    assert held == [True], "the citation was written outside this gate run's lease"
    # And the lease went back afterwards, so the citation is not what holds it. The
    # release is the last thing the run's own thread does, after the status this test
    # waited for, so it is waited for rather than asserted on the instant.
    _until(
        lambda: not (library / LEASE_FILE).exists(),
        failure="the gate run that wrote the citation left the library held",
    )


def test_a_gate_run_that_wrote_nothing_cites_nothing(tmp_path: Path) -> None:
    """A declined gate run leaves the citation exactly as it found it.

    The citation is written from the write-back and the write-back happens only from
    a decision the run reached: a run that was refused at the interrupt sent nothing,
    stored no reading, and has no claim about this library to make. A bench that
    started citing an answer nobody measured would be the worst version of ADR-0023.
    """
    library = a_library(tmp_path)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(
            approval_of(body["gate_run_id"]), json=a_confirmation(confirmed=False)
        )
        [record] = gating.gates.records()
        settled(record)

        assert record.status is GateRunStatus.DECLINED
        assert record.written is None
        assert gating.runs.config.report.gate is None

    assert not (library / CITED_GATE_RUN).exists()
    assert the_citation(library) is None


def test_the_write_back_names_the_record_it_wrote_and_the_citation_it_replaced(
    tmp_path: Path,
) -> None:
    """Both writes are reported, and the replacement is named rather than silent.

    The console's counterpart to the line the terminal prints. A gate run that
    replaced what this bench cites and said nothing about it would be the *silent*
    half of ADR-0023's rejected option, arriving through a response body instead of
    through a file.
    """
    library = a_library(tmp_path)

    with a_bench(library, attempts_per_case=2) as gating:
        body = started(gating)
        gating.client.post(approval_of(body["gate_run_id"]), json=a_confirmation())
        [record] = gating.gates.records()
        settled(record)
        written = gating.client.get(f"{GATE_RUNS_ROUTE}/{body['gate_run_id']}").json()[
            "written"
        ]

    assert written["record"].endswith(".json")
    assert (library / written["record"]).exists()
    assert "cited no gate run before now" in written["cited"]
    assert written["record"] in written["stated"]


def test_a_citation_written_from_a_terminal_reaches_this_process_at_its_next_boot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The difference between the two entry points, which is one restart.

    ADR-0023 decision Five states it and this is the test of it. A gate run at a
    terminal writes the citation into the library — the whole of its durable effect,
    and all it can do, because it is not in this process. A bench already running goes
    on citing what it booted with; the next boot reads the library and cites the new
    one. That is the same shape as ADR-0021's *the library a running process holds is
    the one it booted with*, and a retirement takes effect at the same moment.

    The console's half of the difference — reaching the running process at once — is
    asserted in `test_a_console_gate_run_updates_the_gate_this_bench_cites`.
    """
    # A mounted volume, which is what makes this a deployment rather than a laptop:
    # the factory seeds it from the image once and reads both the cases and the
    # citation off it from then on (ADR-0021 condition 4).
    library = tmp_path / "cases"
    library.mkdir()
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setattr("backend.api.app.DEPLOYED_LIBRARY_MOUNT", library)

    running = create_app()
    assert cast(BenchRuns, running.state.bench).config.report.gate is None
    assert list(library.glob("*.toml")), "the mount was not seeded from the image"

    # What a gate run at a terminal does, and nothing else: it writes the citation
    # into the library it holds. It cannot reach the process above — there is no edge
    # from a different process to this one, which is the point.
    cite(a_record(a_passing_gate()), library)

    assert cast(BenchRuns, running.state.bench).config.report.gate is None, (
        "a gate run in another process changed a running bench's citation"
    )
    assert (
        TestClient(running).get(BENCH_GATE_ROUTE).json()["citation"]["cited"] is False
    )

    # And the next boot reads it off the library, which is where the durable answer is.
    booted = cast(BenchRuns, create_app().state.bench).config.report.gate
    assert booted == the_citation(library)
    assert booted is not None and booted.document is not None


def test_no_function_on_the_gate_run_side_reads_the_citation_the_bench_carries() -> (
    None
):
    """The registry holds a snapshot of a config whose citation now moves.

    `BenchGateRuns` is handed the `BenchConfig` the factory built, and `BenchRuns.cite`
    replaces that record rather than mutating it — so from the first console gate run
    the snapshot's `report.gate` is stale. That is deliberate: a gate run is held to
    the configuration it started under, for the reason `GateRunRecord` carries its own
    budget. It is only safe while this side never *reads* the field, so the absence is
    asserted rather than assumed. A future reader of `report.gate` here would be
    reading a citation this module is one restart behind on.
    """
    source = "\n".join(
        (API_DIR / module).read_text(encoding="utf-8") for module in GATE_RUN_MODULES
    )
    tree = ast.parse(source)

    read = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "gate"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "report"
    ]
    assert read == [], "the gate-run side reads report.gate, which it is behind on"


def test_the_citation_reaches_the_bench_through_one_edge_and_nothing_else(
    tmp_path: Path,
) -> None:
    """A gate run registry wired to no bench still writes the durable citation.

    `Cites` is the one edge from a gate run onto the bench a run is measured with,
    and it is optional on purpose: the citation in the library is the fact, and the
    in-process update is a convenience for the operator who is watching. A registry
    with no bench behind it therefore leaves the library citing this gate run and
    leaves the process citing nothing — which is the same state a command-line gate
    run leaves, and the whole of the difference between the two entry points.
    """
    library = a_library(tmp_path)
    config = BenchConfig(
        cases=[],
        rule=replace(DECLARED_RULE, attempts_per_case=2),
        adaptive=SMALL_ADAPTIVE,
        adjudicator=ADJUDICATING,
        approval_wait_seconds=60.0,
        report=ReportConfig(),
    )
    gates = BenchGateRuns(
        config,
        GateRunBench(library=library, equipment=shipped_agents("stub:obedient")),
    )

    record = gates.start(BENCH_ATTESTATION, None)
    gates.answer(record.gate_run_id, Approval(confirmed=True, identity="a tester"))
    settled(record)

    assert record.status is GateRunStatus.DECIDED
    assert config.report.gate is None, "a frozen record was mutated"
    assert the_citation(library) is not None


def _imports_of(source: Path) -> set[str]:
    """Every module this one imports, by the name it imports it under.

    The same reading `test_api_runs.py` does over this package for the environment,
    because an import is the route by which a module acquires a capability it should
    not have.
    """
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _types_named(node: ast.FunctionDef) -> set[str]:
    """Every type named in one signature, as whole identifiers and never substrings.

    Whole identifiers, because `GateRunRecord` contains `RunRecord`: a scan over the
    unparsed text would report every gate-run function as taking both, and an
    assertion that fires on everything is an assertion nobody can act on.
    """
    named: set[str] = set()
    annotations = [*(argument.annotation for argument in node.args.args), node.returns]
    for annotation in annotations:
        if annotation is None:
            continue
        for inner in ast.walk(annotation):
            if isinstance(inner, ast.Name):
                named.add(inner.id)
            elif isinstance(inner, ast.Attribute):
                named.add(inner.attr)
            elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                named.add(inner.value)
    return named


def _already(served: ServedAgents) -> AbstractContextManager[ServedAgents]:
    """The equipment seam over agents this test is already holding.

    A context manager that yields what it was given and takes nothing down, because
    the test owns the server: the gate run borrows it for the length of the run and
    the test keeps the ledger in front of it.
    """

    @contextmanager
    def borrowed() -> Iterator[ServedAgents]:
        yield served

    return borrowed()


def _until(
    reached: Callable[[], bool],
    seconds: float = 60.0,
    failure: str = "the gate run did not reach the point this test waits for",
) -> None:
    """Wait for something a run is doing on another thread, or fail the test."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if reached():
            return
        time.sleep(0.02)
    raise AssertionError(failure)
