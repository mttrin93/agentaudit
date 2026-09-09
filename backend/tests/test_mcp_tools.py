"""The four tools, exercised against the real app through the real server.

`server.list_tools` and `server.call_tool` are the whole seam. What a client of this
surface can reach is what a model can reach, so every test below goes through the
tool boundary rather than through `BenchClient` — which `test_mcp_client.py` holds on
its own, and which would let a test reach a call no tool exposes. The bench behind it
is the one `create_app` builds, for the reason that file gives: a route that moves
has to break this in CI and not in somebody's chat.

**The consent tests assert an absence at the endpoint.** A run that was not approved
and a run whose counters say it was not approved are different claims, and only the
first is checked by counting what arrived at the target — so the ledger
`test_api_runs.py` puts in front of the reference agent is what says nothing was
spent.
"""

from __future__ import annotations

import json
import pathlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import Tool

from backend.api.report import ReportConfig
from backend.api.run_state import NeverPresented
from backend.api.runs import BenchRuns
from backend.bench.assembler import FindingsReading
from backend.bench.contract import TargetConfig
from backend.bench.library import Case
from backend.bench.signing import generate
from backend.mcp.client import BenchClient
from backend.mcp.server import build_server
from backend.tests.test_api_runs import (
    QUIET_SECONDS,
    Watched,
    api,
    registered,
    settled,
    watched_reference,
)
from backend.tests.test_mcp_client import _bench_client

NOWHERE = "http://127.0.0.1:9"
"""Discard, on a port nothing listens on: a bench nobody started."""

UNREACHED = TargetConfig(
    name="checkout-agent",
    url="https://staging.example.test/agent",
    auth_token="t-123",
    agent_type="assistant",
    exposes_tool_calls=True,
    declared_tools=("search",),
)
"""A declared target no test sends anything to.

Every test that names it either stops before a request could be made or points the
client at a closed port, so the host in it is never resolved.
"""


@pytest.fixture
def anyio_backend() -> str:
    """The one backend these tests run under.

    Declared in this module rather than in a shared conftest, and again in
    `test_mcp_entrypoint.py`, because these two are the only async files in
    `backend/tests/`: a fixture in the conftest would be a requirement of this
    package's whole test suite where it is a requirement of two files in it.
    """
    return "asyncio"


def declared(target: TargetConfig, nonce: str = "", **fields: Any) -> str:
    """One `agentaudit.toml` as an operator would have committed it."""
    return _toml(
        {
            "target": {
                "name": target.name,
                "url": target.url,
                "auth_token": target.auth_token,
                "agent_type": target.agent_type,
                "exposes_tool_calls": True,
                "declared_tools": list(target.declared_tools),
                "nonce": nonce,
                **fields,
            },
            "attestation": {
                "identity": "matteo",
                "authorised_to_test": True,
                "not_production": True,
                "accepts_provider_policy_and_cost": True,
            },
            "cost": {"price_per_call": "0.002", "currency": "USD"},
        }
    )


def _toml(document: dict[str, dict[str, Any]]) -> str:
    """That document as TOML, written out rather than depended on.

    Three tables of scalars and one list of strings is the whole of the format these
    tests write, and `json.dumps` spells every one of those the way TOML does. A
    writer dependency for it would be a dependency the shipped package does not have.
    """
    lines: list[str] = []
    for table, fields in document.items():
        lines.append(f"[{table}]")
        lines.extend(f"{key} = {json.dumps(value)}" for key, value in fields.items())
        lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True)
class Served:
    """One MCP server, the bench behind it, and the file it reads.

    A record rather than the four-tuple these three helpers used to hand back, on
    `Watched`'s reasoning one file over: the four travel together everywhere and most
    tests want two of them, and a tuple makes every test name all four to reach one.

    The declaration path is here because the nonce a run starts on is one this bench
    issued, and it cannot be known until the bench exists: a test writes the real
    declaration over the placeholder and the tools read it on the next call, which is
    the re-read `build_server` documents.
    """

    server: MCPServer
    client: TestClient
    bench: BenchRuns
    declaration: pathlib.Path

    async def called(self, tool: str, **arguments: Any) -> dict[str, Any]:
        """One tool call, as the client of this server reads its answer."""
        result = await self.server.call_tool(tool, dict(arguments))
        # One cast, for a return type that is a tool result *or* a request for more
        # input — a shape no tool on this surface returns, since none of them elicits.
        return cast(dict[str, Any], cast(Any, result).structured_content)

    async def named(self, tool: str) -> Tool:
        """One tool as a client lists it — its schema and its annotations."""
        (one,) = [
            listed for listed in await self.server.list_tools() if listed.name == tool
        ]
        return one


@contextmanager
def served(
    tmp_path: pathlib.Path,
    cases: list[Case],
    document: str,
    report: ReportConfig | None = None,
) -> Iterator[Served]:
    """One MCP server over one bench, reading the declaration written at `tmp_path`."""
    declaration = tmp_path / "agentaudit.toml"
    declaration.write_text(document, encoding="utf-8")
    with api(cases, report=report) as (client, bench):
        server = build_server(_bench_client(client), declaration)
        yield Served(server=server, client=client, bench=bench, declaration=declaration)


@contextmanager
def against_a_target(
    tmp_path: pathlib.Path, cases: list[Case], report: ReportConfig | None = None
) -> Iterator[tuple[Served, Watched]]:
    """A served bench, a served target with a ledger in front of it, and a
    declaration naming the one to the other at a nonce this bench issued and this
    operator planted.

    The three steps every test that starts a run takes, in the order an operator
    takes them: register the nonce, commit the declaration, then call the tool.
    """
    with watched_reference() as watched:
        with served(tmp_path, cases, declared(UNREACHED), report) as running:
            running.declaration.write_text(
                declared(watched.target, registered(running.client, watched)),
                encoding="utf-8",
            )
            yield running, watched


@pytest.mark.anyio
async def test_exactly_four_tools_are_registered(tmp_path: pathlib.Path) -> None:
    """A fifth tool is a fifth route. The count is asserted so that adding one is a
    decision somebody makes on purpose (ADR-0100)."""
    with served(tmp_path, [], declared(UNREACHED)) as running:
        listed = await running.server.list_tools()

    assert sorted(tool.name for tool in listed) == [
        "approve_run",
        "run_report",
        "run_status",
        "start_run",
    ]


@pytest.mark.anyio
async def test_the_two_tools_that_only_read_say_so_and_the_two_that_do_not_do_not(
    tmp_path: pathlib.Path,
) -> None:
    """An honest hint, which is the only kind worth publishing.

    A client decides from these what to confirm with its user, so `read_only_hint` on
    a tool that spends an operator's inference budget would be the surface telling a
    model it was safe to call without asking — the opposite of what the seam above it
    is for.
    """
    with served(tmp_path, [], declared(UNREACHED)) as running:
        hints = {
            tool.name: (
                tool.annotations.read_only_hint,
                tool.annotations.destructive_hint,
            )
            for tool in await running.server.list_tools()
            if tool.annotations is not None
        }

    assert hints == {
        "start_run": (False, False),
        "approve_run": (False, True),
        "run_status": (True, False),
        "run_report": (True, False),
    }


@pytest.mark.anyio
async def test_start_run_halts_and_returns_the_estimate(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """It returns the figures and stops. The run is not confirmed by starting it.

    Both ceilings are asserted by name because they are what the operator is being
    asked about: an estimate quoted without the ceiling it is enforced against is a
    figure with no upper bound beside it (ADR-0007).
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, watched):
        started = await running.called("start_run")
        time.sleep(QUIET_SECONDS)
        arrived = watched.ledger.hits

    assert started["status"] == "awaiting_approval"
    assert started["estimate"]["total"]["calls"] > 0
    assert started["estimate"]["scored_ceiling"] > 0
    assert started["estimate"]["adaptive_ceiling"] > 0
    assert started["nonce_to_plant"] is None
    assert arrived == 0


@pytest.mark.anyio
async def test_a_file_with_no_nonce_is_issued_one_and_told_to_plant_it(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """The register walk's two steps, and the second is still the operator's.

    A declaration that carries no nonce is not a declaration this surface fills in
    (ADR-0100): what it does is fetch the value from `POST /nonces` and hand it back
    to be planted, which is what the console does at the same point. Planting it
    while the run holds its interrupt is in time, because the registration probe goes
    out after the approval.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, watched):
        running.declaration.write_text(declared(watched.target), encoding="utf-8")
        started = await running.called("start_run")
        record = running.bench.record(str(started["run_id"]))
        assert record is not None
        started_on = record.nonce

    assert started["nonce_to_plant"]
    assert started_on == started["nonce_to_plant"]


@pytest.mark.anyio
async def test_no_argument_to_start_run_reaches_a_confirmed_run(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """The consent seam, asserted by trying to cross it (ADR-0007).

    Two assertions and they are one claim. `start_run` publishes no argument a caller
    could confirm with, and an invented one changes nothing about the run it starts:
    the schema is what a model reads, and the run's own standing is what happens when
    a model sends the argument anyway.

    **Not `pytest.raises`.** mcp 2.2.0 validates a call against a pydantic model built
    from the signature, and that model's `extra` is pydantic's default — `ignore`. An
    invented argument is dropped rather than refused, so a test that asserted a raise
    would assert a behaviour this library does not have. Driven red by adding
    `confirmed: bool = False` to `start_run` and approving on it, which fails both
    halves: the run reaches `completed` and the field appears in the schema.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, watched):
        tool = await running.named("start_run")
        started = await running.called("start_run", confirmed=True)
        time.sleep(QUIET_SECONDS)
        arrived = watched.ledger.hits
        record = running.bench.record(str(started["run_id"]))
        assert record is not None
        # Read inside the block: the `api` teardown answers every halt this test
        # left open, so a status read after it is the teardown's and not the tool's.
        standing = str(record.status)

    assert standing == "awaiting_approval"
    assert arrived == 0
    assert tool.input_schema.get("properties", {}) == {}


@pytest.mark.anyio
async def test_approve_run_confirms_and_start_run_did_not(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """Two calls, and only the second one spends.

    The pair is the assertion: *nothing arrived* means nothing on its own, since a
    run refused for a bad declaration would also send nothing. What makes the halt a
    halt is that the same run, answered yes, then reaches the target.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, watched):
        started = await running.called("start_run")
        time.sleep(QUIET_SECONDS)
        before = watched.ledger.hits
        approved = await running.called(
            "approve_run", run_id=started["run_id"], confirmed=True
        )
        record = running.bench.record(str(started["run_id"]))
        assert record is not None
        settled(record)
        after = watched.ledger.hits

    assert before == 0
    assert approved["status"] != "declined"
    assert after > 0


@pytest.mark.anyio
async def test_a_declined_run_is_answered_in_full_and_spends_nothing(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """A no is an answer, and the reason travels with it.

    `confirmed=False` is not the absence of an approval: it ends the run, and the
    sentence the record keeps is the operator's own. A tool that could only say yes
    would leave every declined run waiting out its approval window.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, watched):
        started = await running.called("start_run")
        declined = await running.called(
            "approve_run",
            run_id=started["run_id"],
            confirmed=False,
            reason="too dear",
        )
        time.sleep(QUIET_SECONDS)
        arrived = watched.ledger.hits

    assert declined["status"] == "declined"
    assert "too dear" in declined["statement"]
    assert arrived == 0


@pytest.mark.anyio
async def test_run_status_is_this_run_s_row_and_a_run_on_no_row_is_refused(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """Where the run has got to, per layer, and a plain no for an id nobody holds.

    The two spends are asserted separately because they are two ceilings and never a
    sum (ADR-0010): a row that carried one of them would be a poll that could not see
    which half of the run was spending. The refusal is the half that matters to a
    poller — an id on no row comes back as a no a caller stops asking on, rather than
    as an empty reading it would poll for the lifetime of the process.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, _watched):
        started = await running.called("start_run")
        row = await running.called("run_status", run_id=started["run_id"])
        with pytest.raises(ToolError) as refused:
            await running.called("run_status", run_id="never-started")

    assert row["run_id"] == started["run_id"]
    assert row["status"] == "awaiting_approval"
    assert row["scored"]["calls_spent"] == 0
    assert row["adaptive"]["calls_spent"] == 0
    assert "no run never-started" in str(refused.value)


@pytest.mark.anyio
async def test_run_report_returns_the_compact_reading_with_urls(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """The findings, the labels, and the four artefact URLs — and no artefact content.

    The reading itself is `reading.py`'s and `test_mcp_reading.py` walks it, including
    all four readings of the narrative pass. Those four are held one layer down and
    not here on purpose: three of them are properties of a payload this offline bench
    does not produce, and serving them at this boundary would mean a recorded report
    route — the fixture the spec's other testing decision forbids. What is asserted
    here is the join this tool makes: that reading, whole, beside the four places the
    document is served.
    """
    with against_a_target(
        tmp_path, [leakage_case], ReportConfig(signing_key=generate())
    ) as (running, watched):
        started = await running.called("start_run")
        run_id = str(started["run_id"])
        await running.called("approve_run", run_id=run_id, confirmed=True)
        record = running.bench.record(run_id)
        assert record is not None
        settled(record)
        reading = await running.called("run_report", run_id=run_id)
        base = running.client.base_url

    assert reading["target"] == watched.target.name
    assert reading["findings"]["reading"] in {
        member.value for member in FindingsReading
    }
    assert reading["rule"]["attempts_per_case"] > 0
    assert reading["artefacts"] == {
        "payload": f"{base}/report/{run_id}",
        "rendering": f"{base}/report/{run_id}/rendering",
        "signature": f"{base}/report/{run_id}/signature",
        "verification": f"{base}/report/{run_id}/verification",
    }


@pytest.mark.anyio
async def test_a_run_with_no_signed_report_is_refused_by_the_refusal_s_own_name(
    tmp_path: pathlib.Path, leakage_case: Case
) -> None:
    """A completed run on a bench with no key has no artefact, and says which fact.

    `never_signed` reaches the caller as a word rather than as a status code, because
    a `ToolError` carries a sentence and nothing else: the name has to be *in* the
    sentence or a model cannot tell a run to ask about again from one that will never
    have a report.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, _watched):
        started = await running.called("start_run")
        run_id = str(started["run_id"])
        await running.called("approve_run", run_id=run_id, confirmed=True)
        record = running.bench.record(run_id)
        assert record is not None
        settled(record)
        with pytest.raises(ToolError) as unsigned:
            await running.called("run_report", run_id=run_id)

    assert "never_signed" in str(unsigned.value)


@pytest.mark.anyio
async def test_a_run_that_reached_no_interrupt_is_a_stated_failure(
    tmp_path: pathlib.Path, leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`NeverPresented` arrives as a sentence and not as a run that never answers.

    Provoked at the seam the route translates rather than by contriving a graph that
    stalls, exactly as `test_mcp_client.py` provokes it: what is under test here is
    that the client's name for it reaches the tool boundary with its words intact.
    """
    with against_a_target(tmp_path, [leakage_case]) as (running, _watched):

        def _no_interrupt(*_: object, **__: object) -> None:
            raise NeverPresented(
                "the run reached no approval interrupt, so it has no estimate to "
                "confirm. Nothing was sent"
            )

        monkeypatch.setattr(running.bench, "start", _no_interrupt)
        with pytest.raises(ToolError) as none:
            await running.called("start_run")

    assert "no estimate to confirm" in str(none.value)


@pytest.mark.anyio
async def test_a_declaration_that_withholds_a_statement_is_named_and_says_which(
    tmp_path: pathlib.Path,
) -> None:
    """A refused start is actionable without opening the console.

    The refusal's own name and its own sentence, both: the name is what a caller
    branches on and the sentence is the only place the reader says *which* statement
    was withheld.
    """
    document = declared(UNREACHED).replace(
        "not_production = true", "not_production = false"
    )
    with served(tmp_path, [], document) as running:
        with pytest.raises(ToolError) as refused:
            await running.called("start_run")

    assert "not_attested" in str(refused.value)
    assert "not_production" in str(refused.value)


@pytest.mark.anyio
async def test_an_unreachable_bench_is_a_stated_failure(tmp_path: pathlib.Path) -> None:
    """Not a stack trace, and not an empty result: a caller told nothing would read a
    bench that found nothing.

    The likeliest failure this surface has — a coding agent calling a tool against an
    API nobody started — and the one where an empty answer would be read as a target
    with no findings.
    """
    declaration = tmp_path / "agentaudit.toml"
    declaration.write_text(declared(UNREACHED, nonce="planted"), encoding="utf-8")
    with httpx.Client(base_url=NOWHERE) as http:
        server = build_server(BenchClient(http), declaration)
        with pytest.raises(ToolError) as unreachable:
            await server.call_tool("start_run", {})

    assert NOWHERE in str(unreachable.value)
