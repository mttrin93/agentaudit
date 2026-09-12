"""Four tools over four routes, and starting a run is not paying for one.

The surface itself: `build_server` wires the declaration reader, the compact reading
and the HTTP client into the four tools a coding agent calls. It decides nothing —
every rule below is enforced on the far side of a route, which is the whole of the
claim
[ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)
makes about this package.

**The consent seam is two tools here because ADR-0100 §4 holds it elsewhere.** The
local consequence is the shape below: `start_run` stops at the estimate, `approve_run`
is the call that spends, and neither is where the refusal lives — the approval route
is, over the checkpoint
[ADR-0028](../../docs/adr/0028-the-approval-checkpoint-outlives-the-process.md) put on
disk. So nothing in this module may grow a way to answer the halt on the caller's
behalf, and a tool description is never what stops one.

**The tool descriptions say what this surface will not do.** No registration, no
patch and no revision, which are ADR-0100 §5's three; and no gate run, which is that
ADR's *Considered options* and the spec's own scope. A description is what a model
reads before it asks, so the four are written where the asking happens as well as
where they are answered.

**Nothing is caught bare.** The six named failures of `client.py` and
`declaration.py` become a `ToolError` carrying the refusal's own sentence, and
anything else is a crash the framework reports as one: a surface that turned every
exception into a tool result would hand a model a sentence about a bug as though it
were a fact about a run.
"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from backend.declaration import Declaration, DeclarationRefused, declaration_at
from backend.mcp.client import (
    BenchClient,
    BenchRefused,
    BenchUnreachable,
    NoCredential,
    NoEstimate,
    ReportNotSigned,
)
from backend.mcp.reading import compact_report

INSTRUCTIONS = (
    "An adversarial test bench for AI agents. Runs are declared in a committed "
    "agentaudit.toml and cost real inference budget: start_run returns an estimate "
    "and spends nothing, approve_run spends it. This surface cannot register a "
    "target, start a gate run, or write a patch."
)
"""What a client is told this server is, before it reads a single tool.

The estimate sentence is here as well as on `start_run` because a client that lists
tools has already read this, and the one thing it must not learn late is that a
second call is what spends.
"""

STATED_FAILURES = (
    DeclarationRefused,
    NoCredential,
    BenchUnreachable,
    BenchRefused,
    NoEstimate,
    ReportNotSigned,
)
"""Every failure this surface has a sentence for, named one by one.

A tuple of six types rather than `except Exception`, so that a seventh condition
somebody adds to `client.py` arrives here as a crash and not as a `ToolError` that
says whatever the exception happened to stringify to.

`NoCredential` is first among the client's five because it is the only one raised
before a request goes out: an operator who launched this server without
`AGENTAUDIT_MACHINE_TOKEN` meets it on their first tool call, reads the variable's
name in the sentence, and has not sent anything to a bench to find that out.
"""


@contextmanager
def _stated() -> Iterator[None]:
    """This call's named failure as the sentence the caller is given, or nothing.

    One translation for all four tools, because the sentence is already written at
    every raise site: `client.py` and `declaration.py` each compose the line a person
    reads, and a tool that reworded it would be a second author of a refusal it did
    not make.
    """
    try:
        yield
    except STATED_FAILURES as failure:
        raise ToolError(_sentence(failure)) from failure


def _sentence(failure: Exception) -> str:
    """That failure as one line, with the name a caller branches on inside it.

    A `ToolError` carries a string and nothing else, so a caller of this surface can
    only branch on words: the names this package keeps beside its sentences have to
    be *in* the sentence or they do not reach a model at all. Three of the six put
    theirs there already — `BenchRefused` its status, `ReportNotSigned` its outcome,
    `NoCredential` the variable to set — and this adds the one that does not.
    """
    if isinstance(failure, DeclarationRefused):
        return f"{failure.refusal}: {failure}"
    return str(failure)


def build_server(client: BenchClient, declaration_path: pathlib.Path) -> MCPServer:
    """The four tools, over that bench and that declaration file.

    Both are handed in: the path is the operator's committed file and the client is
    the process's own, so nothing here reads an environment variable or picks a
    default target. `__main__.py` is where those two are decided.
    """

    server: MCPServer = MCPServer(name="agentaudit", instructions=INSTRUCTIONS)

    def _declared() -> Declaration:
        """The committed declaration, re-read on every call.

        Re-read rather than captured at build time, because the file is the
        operator's and a server is long-lived: an edit made between two tool calls is
        an edit the next run is started under, which is the behaviour a caller of a
        *file* expects. It is never written (ADR-0100).
        """
        return declaration_at(declaration_path)

    @server.tool(
        name="start_run",
        title="Start a run and stop at the estimate",
        description=(
            "Start a run against the target declared in agentaudit.toml and stop at "
            "the approval interrupt. Nothing is sent to the target and nothing is "
            "spent: what comes back is the run id, the estimate, and the two layer "
            "ceilings the run would be held to. Relay the figure to the operator and "
            "call approve_run only if they say yes. Takes no arguments — the target, "
            "the attestation and the price are read from the committed file, and "
            "this surface never writes it. It cannot register a new target (use the "
            "console), start a gate run, or write a patch."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    async def start_run() -> dict[str, Any]:
        """`POST /nonces` where the file carries no nonce, then `POST /runs`.

        **No parameters at all, and the bypass test is what holds that.** Not even a
        declaration path: the file is the one `build_server` was handed, and a path
        argument would let the caller pick which target the run is against — a choice
        the committed file has already made, one pull request ago.

        The route's own answer, plus the one key this surface adds:
        `nonce_to_plant` is the value fetched from `POST /nonces` where the file
        carried none, and `None` where the operator committed one and has therefore
        already planted it. One key rather than the value and a flag beside it,
        because they are one fact — *is there anything for you to do before you
        approve* — and two keys would be two places for it to disagree with itself.

        Planting it after the run has started is in time and not late: the run is
        holding its interrupt and the registration probe goes out after the approval,
        which is the same order the console's two screens put the operator through.
        """
        with _stated():
            committed = _declared()
            declaration = (
                committed
                if committed.nonce
                else dataclasses.replace(committed, nonce=client.issue_nonce())
            )
            started = client.start(declaration)
        return dict(started) | {
            "nonce_to_plant": None if committed.nonce else declaration.nonce
        }

    @server.tool(
        name="approve_run",
        title="Answer a run's approval interrupt",
        description=(
            "Answer the approval interrupt a started run is holding. confirmed=true "
            "spends the estimate start_run showed and runs the suite against the "
            "declared target; anything else ends the run having sent nothing. Call "
            "this only on an operator's explicit yes to the figure start_run "
            "returned — it is the one call on this surface that spends their "
            "inference budget. The identity recorded against the answer is the "
            "machine credential this server authenticates with, verified by the "
            "bench and never a name this tool sends: the report says a machine "
            "answered, so relay the figure and the operator's yes rather than "
            "treating the record as their signature."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    async def approve_run(
        run_id: str, confirmed: bool, reason: str = ""
    ) -> dict[str, Any]:
        """`POST /runs/{run_id}/approval`, under the identity the bench verified.

        `confirmed` has no default here for the reason `BenchClient.approve` gives it
        none: the yes is the whole of the seam, and a default is a yes reachable by
        omission. There is no identity argument and there is no identity on the wire
        — a caller that could type any name could record the run against somebody who
        made no statement at all, which is ADR-0007's reasoning and is now ADR-0116
        §1's rule: the name is read from the credential this client presents.

        **What that name is, is a machine, and the artefact says so** (ADR-0124). The
        consent seam is unmoved by it: the operator's yes is still what this call
        requires, and what the record now stops claiming is that they typed it.
        """
        with _stated():
            return dict(client.approve(run_id, confirmed=confirmed, reason=reason))

    @server.tool(
        name="run_status",
        title="Where a run has got to",
        description=(
            "This run's row of the bench's run list: its standing, the record's own "
            "sentence for it, and what each layer has spent so far. Reads and never "
            "waits, so a run that takes minutes is polled by calling this again. "
            "Spends nothing and changes nothing."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    async def run_status(run_id: str) -> dict[str, Any]:
        """`GET /runs`, this run's row (ADR-0100 §1)."""
        with _stated():
            return dict(client.status(run_id))

    @server.tool(
        name="run_report",
        title="A signed run's findings, compacted",
        description=(
            "The signed report of a completed run, as figures, findings and the rule "
            "they were measured at, beside URLs for the payload, the rendering, the "
            "signature and the verification. Every label survives and most of the "
            "prose does not, so quote a rate only with the rule beside it and fetch "
            "the document before repeating a conclusion. Refuses by name where a run "
            "has no signed artefact. Reads only; it writes no patch, and the commit "
            "under test is yours to name, not the bench's."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    async def run_report(run_id: str) -> dict[str, Any]:
        """`GET /report/{run_id}`, compacted by `reading.py` and by nothing here.

        The URLs are computed without a request and the payload is fetched with one,
        which is the order that makes an unsigned run a refusal rather than a reading
        with four links to documents that do not exist.
        """
        with _stated():
            payload = client.report(run_id)
        return compact_report(payload, urls=client.artefact_urls(run_id))

    return server
