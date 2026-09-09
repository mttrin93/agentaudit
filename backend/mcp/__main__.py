"""`python -m backend.mcp`: the four tools over stdio, against a bench somebody else
started.

**It starts no bench, and it will not fail to start because there is none.** The
client is built, the server is built, and the first request goes out on the first
tool call — so an operator who forgot `uvicorn` is told *no bench answered at ...* by
the tool they called, which is a sentence a model can relay. A module that had
checked the connection at boot would exit before the transport existed, and a server
that refused to start leaves its client with nothing to read but a dead pipe.

**Both defaults are decided here.** `build_server` takes a client and a path and
reads no environment variable, because a library that picked a target would make the
target a property of the import rather than of the launch (`server.py`). This is the
launch: `AGENTAUDIT_API` names the running API and `AGENTAUDIT_DECLARATION` names the
committed file, and the two values below are what an operator gets for saying
neither.

The client config block that spawns this, and the walk that produces a file for it to
read, are in the README.
"""

from __future__ import annotations

import os
import pathlib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import httpx
from mcp.server.mcpserver import MCPServer

from backend.mcp.client import BenchClient
from backend.mcp.server import build_server

DEFAULT_API = "http://127.0.0.1:8000"
"""Where `uvicorn backend.api.app:create_app --factory` puts the bench on a laptop.

A loopback address and not a hostname: this surface holds an attestation identity and
an auth token for somebody's target, and a default that could resolve off the machine
is a default that sends them somewhere on a typo.
"""

DEFAULT_DECLARATION = "agentaudit.toml"
"""The file at the operator's repository root, relative and deliberately so.

A client spawns this process with the checkout as its working directory, so the
declaration read is the one committed in the repository the coding agent is working
in — which is the whole of the claim that what the target declared about itself was
reviewed in a pull request.
"""

TIMEOUT_SECONDS = 30.0
"""How long one call to the bench may take before it is a failure rather than a wait.

Above `httpx`'s own five, because `POST /runs` registers a target, plans the run and
declares an estimate before it answers — and no higher, because the suite itself runs
behind the approval, so no request this surface makes is ever waiting for a run.
"""


def configured(environment: Mapping[str, str]) -> tuple[str, pathlib.Path]:
    """Where the bench is and where the declaration is, as that environment says.

    Takes the mapping rather than reading `os.environ` itself, so the two defaults are
    assertable without a test mutating the process it runs in.
    """
    return (
        environment.get("AGENTAUDIT_API", DEFAULT_API),
        pathlib.Path(environment.get("AGENTAUDIT_DECLARATION", DEFAULT_DECLARATION)),
    )


@contextmanager
def serving(environment: Mapping[str, str]) -> Iterator[MCPServer]:
    """The four tools over that environment's bench, built without asking it anything.

    Nothing here connects, resolves a host or opens the declaration: `httpx.Client`
    is a pool and a base URL until a request is made, and `build_server` re-reads the
    path on every call rather than at build time. That is the whole of this module's
    promise — the failure an operator is likeliest to arrive with reaches them as a
    tool result rather than as an exit code.

    A context manager because the client is this process's to close, and separate from
    `main` so that what it built can be listed and called by a test that never speaks
    stdio.
    """
    base_url, declaration = configured(environment)
    with httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS) as http:
        yield build_server(BenchClient(http), declaration)


def main() -> None:
    """The server on this process's stdin and stdout, until the client closes them."""
    with serving(os.environ) as server:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
