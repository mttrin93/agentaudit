"""`python -m backend.mcp`: what it decides, and what it refuses to decide at boot.

The two defaults are this module's own — `server.py` reads no environment variable
and picks no target — so they are asserted here and nowhere else.
"""

from __future__ import annotations

import pathlib

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from backend.declaration import DeclarationRefusal, declaration_at
from backend.mcp.__main__ import (
    DEFAULT_API,
    DEFAULT_DECLARATION,
    configured,
    serving,
)
from backend.tests.test_mcp_tools import NOWHERE, UNREACHED, declared

EXAMPLE = pathlib.Path(__file__).resolve().parents[2] / "agentaudit.toml.example"
"""The declaration an operator copies, read from where the README tells them it is."""

DECLARED = declared(UNREACHED, nonce="planted")
"""A complete declaration naming a target nothing in this file sends anything to."""


@pytest.fixture
def anyio_backend() -> str:
    """The one backend these tests run under, as `test_mcp_tools.py` declares it."""
    return "asyncio"


def test_an_unset_environment_names_the_local_bench_and_the_committed_file() -> None:
    """Both defaults, read from an environment that says nothing.

    An operator who started the API the README's way and committed the file at the
    root it documents runs the server with no configuration at all.
    """
    assert configured({}) == (DEFAULT_API, pathlib.Path(DEFAULT_DECLARATION))


def test_either_variable_names_the_thing_it_is_named_for() -> None:
    """`AGENTAUDIT_API` moves the bench, `AGENTAUDIT_DECLARATION` moves the file."""
    assert configured(
        {
            "AGENTAUDIT_API": "https://bench.example.test",
            "AGENTAUDIT_DECLARATION": "targets/checkout.toml",
        }
    ) == ("https://bench.example.test", pathlib.Path("targets/checkout.toml"))


@pytest.mark.anyio
async def test_a_bench_that_is_not_there_is_the_first_tool_call_and_not_the_boot(
    tmp_path: pathlib.Path,
) -> None:
    """The load-bearing property of this module, asserted in the order it matters.

    First that the server exists and lists its four tools against a port nothing
    listens on — an entrypoint that had checked the connection would have raised
    before a client could read anything — and only then that the call a caller makes
    is where the missing bench is named. A module that exited at boot would leave a
    coding agent with a closed pipe and no sentence to relay.
    """
    declaration = tmp_path / "agentaudit.toml"
    declaration.write_text(DECLARED, encoding="utf-8")

    with serving(
        {"AGENTAUDIT_API": NOWHERE, "AGENTAUDIT_DECLARATION": str(declaration)}
    ) as server:
        assert len(await server.list_tools()) == 4
        with pytest.raises(ToolError) as unreachable:
            await server.call_tool("start_run", {})

    assert NOWHERE in str(unreachable.value)


@pytest.mark.anyio
async def test_no_declaration_where_one_was_expected_is_not_a_boot_failure(
    tmp_path: pathlib.Path,
) -> None:
    """The other absence an operator arrives with, and it stops nothing either.

    The path is not opened at boot — the server is built over a file that is not
    there — and the first call is where the operator is told, by name and with the
    file in the sentence.
    """
    absent = tmp_path / "absent.toml"

    with serving({"AGENTAUDIT_DECLARATION": str(absent)}) as server:
        assert len(await server.list_tools()) == 4
        with pytest.raises(ToolError) as refused:
            await server.call_tool("start_run", {})

    assert DeclarationRefusal.NO_FILE in str(refused.value)
    assert str(absent) in str(refused.value)


def test_the_committed_example_is_a_declaration_this_reader_accepts() -> None:
    """`agentaudit.toml.example` is read by the reader it is an example of.

    An example declaration that had drifted past `declaration.py` would be worse than
    none: the operator copying it has no bench of their own to check it against, and
    the first thing they would learn is a refusal about a file they were handed.
    """
    assert declaration_at(EXAMPLE).identity == "your-name@example.com"


def test_the_example_states_nothing_it_means_to_leave_unstated() -> None:
    """The four Rule of Two keys and `sends`, absent on purpose and asserted absent.

    An example is copied, which is what makes this an assertion and not a comment: a
    file that answered the four would hand every operator who copied it four
    declarations they never made (ADR-0102, and `declaration.py` on each field).
    `sends` is left off for the smaller reason the same file gives — the route applies
    the bench's own ceiling, and a number here would override a default it cannot see.
    """
    example = declaration_at(EXAMPLE)

    assert (
        example.processes_untrusted_input,
        example.reaches_private_data,
        example.changes_state_or_communicates,
        example.under_human_supervision,
        example.sends,
    ) == (None, None, None, None, None)
