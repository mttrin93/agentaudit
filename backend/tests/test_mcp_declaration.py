"""What a committed declaration says, and the four ways it is refused."""

from __future__ import annotations

import pathlib

import pytest

from backend.mcp.declaration import (
    Declaration,
    DeclarationRefusal,
    DeclarationRefused,
    declaration_at,
)

COMPLETE = """
[target]
name = "checkout-agent"
url = "https://staging.example.test/agent"
auth_token = "t-123"
agent_type = "assistant"
exposes_tool_calls = true
declared_tools = ["search", "email"]
retains_session_state = true
holds_personal_records = false
nonce = "n-abc"
note_planted = true
nonce_planted = true
echo_waived = false

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true

[cost]
price_per_call = "0.002"
currency = "USD"
"""


def _written(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "agentaudit.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_complete_declaration_reads_every_field(tmp_path: pathlib.Path) -> None:
    read = declaration_at(_written(tmp_path, COMPLETE))
    assert read == Declaration(
        name="checkout-agent",
        url="https://staging.example.test/agent",
        auth_token="t-123",
        agent_type="assistant",
        exposes_tool_calls=True,
        declared_tools=("search", "email"),
        retains_session_state=True,
        holds_personal_records=False,
        nonce="n-abc",
        note_planted=True,
        nonce_planted=True,
        echo_waived=False,
        identity="matteo",
        authorised_to_test=True,
        not_production=True,
        accepts_provider_policy_and_cost=True,
        price_per_call="0.002",
        currency="USD",
    )


def test_the_conservative_defaults_are_the_strict_ones(tmp_path: pathlib.Path) -> None:
    """An omitted field never buys a waiver.

    `nonce_planted` defaults true and `echo_waived` false for the reason
    `StartRunRequest` gives: a waiver obtainable by leaving a field out is a
    waiver nobody makes on purpose.
    """
    minimal = """
[target]
name = "a"
url = "https://staging.example.test/agent"

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true
"""
    read = declaration_at(_written(tmp_path, minimal))
    assert (read.nonce_planted, read.echo_waived, read.note_planted) == (
        True,
        False,
        False,
    )
    assert (read.exposes_tool_calls, read.declared_tools) == (False, ())
    assert (read.price_per_call, read.currency) == (None, "")


def test_a_missing_file_is_refused_by_name(tmp_path: pathlib.Path) -> None:
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(tmp_path / "agentaudit.toml")
    assert refused.value.refusal is DeclarationRefusal.NO_FILE


def test_a_callback_target_is_refused_and_points_at_the_action(
    tmp_path: pathlib.Path,
) -> None:
    """The API takes a URL. A callback is imported from a checkout, which is the
    Action's shape and not this surface's — so it is refused by name rather than
    silently dropped."""
    body = """
[target]
name = "a"
callback = "mypkg.agent:reply"

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true
"""
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(_written(tmp_path, body))
    assert refused.value.refusal is DeclarationRefusal.NOT_AN_ENDPOINT
    assert "action" in str(refused.value).lower()


def test_an_unattested_declaration_is_refused(tmp_path: pathlib.Path) -> None:
    body = COMPLETE.replace("not_production = true", "not_production = false")
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(_written(tmp_path, body))
    assert refused.value.refusal is DeclarationRefusal.NOT_ATTESTED
    assert "not_production" in str(refused.value)


def test_an_empty_identity_is_refused(tmp_path: pathlib.Path) -> None:
    body = COMPLETE.replace('identity = "matteo"', 'identity = ""')
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(_written(tmp_path, body))
    assert refused.value.refusal is DeclarationRefusal.NO_IDENTITY


def test_a_flag_that_is_not_a_boolean_is_not_coerced(tmp_path: pathlib.Path) -> None:
    """`echo_waived = "no"` does not read as a waiver.

    `bool("no")` is `True`, so a coercing reader would relax the guard on the word
    that says not to — the one direction this file's defaults exist to prevent.
    """
    body = COMPLETE.replace("echo_waived = false", 'echo_waived = "no"')
    with pytest.raises(TypeError) as wrong:
        declaration_at(_written(tmp_path, body))
    assert "echo_waived" in str(wrong.value)


def test_a_tool_list_that_is_a_string_is_not_read_as_letters(
    tmp_path: pathlib.Path,
) -> None:
    """`declared_tools = "search"` is not six one-letter tools.

    Scope creep is read against that list, so a reading that spelt it out would
    make every real call this target makes score as a finding.
    """
    body = COMPLETE.replace(
        'declared_tools = ["search", "email"]', 'declared_tools = "search"'
    )
    with pytest.raises(TypeError) as wrong:
        declaration_at(_written(tmp_path, body))
    assert "declared_tools" in str(wrong.value)
