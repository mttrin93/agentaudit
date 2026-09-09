"""What a committed declaration says, and the four ways it is refused."""

from __future__ import annotations

import pathlib

import pytest

from backend.declaration import (
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
processes_untrusted_input = true
reaches_private_data = true
changes_state_or_communicates = false
under_human_supervision = true
sends = 4
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
        processes_untrusted_input=True,
        reaches_private_data=True,
        changes_state_or_communicates=False,
        under_human_supervision=True,
        sends=4,
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
        # Every key `COMPLETE` writes, and it writes all of them: the set is what the
        # Action's both-given rule is read against, so a key the reader defaulted and
        # a key the operator declared have to be distinguishable here (ADR-0103 §4).
        declared_keys=frozenset(
            line.split(" = ")[0] for line in COMPLETE.splitlines() if " = " in line
        ),
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


def test_the_four_rule_of_two_declarations_are_unstated_when_the_key_is_absent(
    tmp_path: pathlib.Path,
) -> None:
    """A key that is not there is the third answer, and never a denial.

    The one field family on this surface whose default is not the narrowing one, and
    [ADR-0102](../../docs/adr/0102-the-declaration-file-carries-the-four-rule-of-two-declarations.md)
    says why: `False` is the profitable claim on these four, so an absent key
    defaulted to it would be a control declared away by a reader rather than by an
    operator.
    """
    body = COMPLETE.replace("processes_untrusted_input = true", "")
    read = declaration_at(_written(tmp_path, body))
    assert read.processes_untrusted_input is None
    assert read.reaches_private_data is True


def test_a_rule_of_two_declaration_that_is_not_a_boolean_is_not_coerced(
    tmp_path: pathlib.Path,
) -> None:
    """`"unstated"` is truthy, and the field it would land in is a held capability."""
    body = COMPLETE.replace(
        "reaches_private_data = true", 'reaches_private_data = "unstated"'
    )
    with pytest.raises(TypeError) as wrong:
        declaration_at(_written(tmp_path, body))
    assert "reaches_private_data" in str(wrong.value)


def test_a_send_ceiling_that_is_absent_leaves_the_route_its_own_default(
    tmp_path: pathlib.Path,
) -> None:
    """`None` and not a number this reader chose.

    `TargetRequest` builds the default from `RetryPolicy`, which lives behind the
    wall `backend/mcp/` may not import — so a reader that supplied a number here
    would be copying a constant from the far side of the wall and going stale the
    day it changed. Saying nothing is how the route gets to answer.
    """
    read = declaration_at(_written(tmp_path, COMPLETE.replace("sends = 4", "")))
    assert read.sends is None


def test_a_send_ceiling_that_is_true_is_not_read_as_one_send(
    tmp_path: pathlib.Path,
) -> None:
    """`isinstance(True, int)` is true in Python, and one send is not what was meant."""
    with pytest.raises(TypeError) as wrong:
        declaration_at(
            _written(tmp_path, COMPLETE.replace("sends = 4", "sends = true"))
        )
    assert "sends" in str(wrong.value)


def test_a_send_ceiling_below_one_is_a_run_that_would_send_nothing(
    tmp_path: pathlib.Path,
) -> None:
    """Nought is not a quieter run: it is a run with no attempts in its denominator."""
    with pytest.raises(TypeError) as wrong:
        declaration_at(_written(tmp_path, COMPLETE.replace("sends = 4", "sends = 0")))
    assert "at least" in str(wrong.value)
