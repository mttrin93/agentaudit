"""`agentaudit.toml`: what the operator declared about their target, committed.

**Read, never written.** No tool edits this file, fills a field it found empty or
declares a control on the operator's behalf. A surface that could write a
declaration is a surface that could declare a control, and every
`attributed_cause` in a report is read against what this file says
([ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)).

**The defaults are the strict ones.** `nonce_planted` defaults true and
`echo_waived` false, for the reason `StartRunRequest` states at the same two
fields: a waiver obtainable by omitting a field is a waiver nobody makes on
purpose. Four refusals rather than prose, on the reasoning every closed set in
this codebase carries — a caller branches on the name and a person reads the
sentence.

**A callback is refused rather than carried.** `TargetRequest` takes a `url`; a
callback is an object imported out of a checkout, which is the Action's shape
([ADR-0066](../../docs/adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md))
and unreachable over HTTP. Passing one through would produce a run against
nothing.
"""

from __future__ import annotations

import pathlib
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

ATTESTED_STATEMENTS = (
    "authorised_to_test",
    "not_production",
    "accepts_provider_policy_and_cost",
)
"""The three statements a run does not start without, in `AttestationRequest`'s order.

Read from one tuple so the refusal can name *which* were withheld: three fields
rather than one `i_agree`, because the record has to show what was attested
(ADR-0007), and a refusal that said only *unattested* would lose the same fact.
"""


class DeclarationRefusal(StrEnum):
    """The four ways a declaration is refused, each by a name a caller can branch on."""

    NO_FILE = "no_file"
    """There is no `agentaudit.toml` where one was expected."""

    NOT_AN_ENDPOINT = "not_an_endpoint"
    """The target names no `url` — a callback declaration belongs to the Action."""

    NO_IDENTITY = "no_identity"
    """The attestation names nobody, so there is nobody the run is recorded against."""

    NOT_ATTESTED = "not_attested"
    """One of the three statements was withheld, and the sentence says which."""


class DeclarationRefused(ValueError):
    """A declaration that will not be read, with the reason named beside the sentence.

    The name is the field a caller branches on and the sentence is the one a person
    reads — the division `Refusal` and `CannotRunAGate` already make on the API's
    side, kept here so a `ToolError` built from one of these carries both.
    """

    def __init__(self, refusal: DeclarationRefusal, statement: str) -> None:
        super().__init__(statement)
        self.refusal = refusal


@dataclass(frozen=True, slots=True)
class Declaration:
    """One target as its operator committed it, in `StartRunRequest`'s own vocabulary.

    Frozen, because it is read out of a file this surface never writes: a mutable
    reading is a reading a tool could amend between the refusals above and the
    request body built from it.

    The field names are `TargetRequest`'s, `AttestationRequest`'s and
    `CostRequest`'s, flattened into one record because a TOML file is three tables
    and a request body is three objects — renaming anything on the way through
    would make the file and the wire two vocabularies with one meaning.
    """

    name: str
    url: str
    auth_token: str
    agent_type: str
    """Defaulted to `assistant` where `TargetRequest` requires it, because the term
    is inert in the library today — it selects no case and enters no figure — so a
    default here fabricates no control. The two fields `TargetRequest` also requires
    and this reader also defaults, `exposes_tool_calls` below and `auth_token` above,
    default in the narrowing direction for the same reason `TargetConfig` narrows
    (ADR-0041): a capability nobody claimed is one the run is not measured on."""

    exposes_tool_calls: bool
    declared_tools: tuple[str, ...]
    retains_session_state: bool
    holds_personal_records: bool
    nonce: str
    note_planted: bool
    nonce_planted: bool
    echo_waived: bool
    identity: str
    authorised_to_test: bool
    not_production: bool
    accepts_provider_policy_and_cost: bool
    price_per_call: str | None
    """`None` is a declaration too: *not priced* and *free* are different facts, and
    only one of them is safe to confirm without reading further (ADR-0007)."""

    currency: str


def _table(document: dict[str, Any], name: str) -> dict[str, Any]:
    """One table of the document, or an empty one — a missing table is a table of
    omitted fields, and every field this reader takes from one either defaults or is
    refused by name below."""
    table = document.get(name)
    return table if isinstance(table, dict) else {}


def _flag(table: dict[str, Any], key: str, default: bool) -> bool:
    """One declared boolean, read and never coerced.

    `bool("no")` is `True`, so a reader that coerced would turn the word that
    withholds a waiver into the waiver itself — and `echo_waived` and
    `nonce_planted` are exactly the two fields where that direction matters. A
    wrong-typed flag raises rather than being refused by name, for the reason
    `declaration_at` gives below: it is a file that cannot be read, not a
    declaration whose contents can be argued with.
    """
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise TypeError(
            f"{key} is declared as {value!r}: a control is declared true or false, "
            "and a value that is neither is not a declaration this surface will "
            "read one way or the other"
        )
    return value


def _words(table: dict[str, Any], key: str) -> tuple[str, ...]:
    """One declared list of strings, read and never spelt out.

    A bare string is iterable, so `declared_tools = "search"` would read as six
    one-letter tools — and scope creep is read against that list, which would make
    every call this target really makes score as a finding.
    """
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(word, str) for word in value):
        raise TypeError(
            f"{key} is declared as {value!r}: it is a list of strings, and a "
            "target that exposes its tool calls has to declare which tools it has"
        )
    return tuple(value)


def declaration_at(path: pathlib.Path) -> Declaration:
    """The committed declaration at `path`, or the named refusal that stops the run.

    The refusals are ordered the way a reader meets the problem: there is no file,
    then the target is not an endpoint, then nobody is attesting, then somebody is
    attesting less than three things. Each stops before the next is asked, so the
    sentence names the first thing to fix rather than all of them at once.

    A file that is not TOML at all, or one whose `[target]` omits `name`, raises
    rather than refuses. The four refusals are for a declaration that parses and
    says something this surface will not run on; a file that cannot be read is not
    a declaration whose contents can be argued with, and a fifth name invented for
    it would make the closed set mean something other than what the operator
    declared.
    """
    if not path.is_file():
        raise DeclarationRefused(
            DeclarationRefusal.NO_FILE,
            f"no declaration at {path}: this surface runs against a target declared "
            "in a committed file, and the first run against a new target is "
            "registered in the console",
        )
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    target = _table(document, "target")
    attestation = _table(document, "attestation")
    cost = _table(document, "cost")
    if not target.get("url"):
        raise DeclarationRefused(
            DeclarationRefusal.NOT_AN_ENDPOINT,
            "this target declares no url. A callback target is imported out of a "
            "checkout and is the Action's shape, not this surface's — run it "
            "through the Action instead",
        )
    if not attestation.get("identity"):
        raise DeclarationRefused(
            DeclarationRefusal.NO_IDENTITY,
            "this declaration names nobody. An attestation is a statement somebody "
            "made, and a run recorded against an empty identity is a run nobody "
            "made (ADR-0007)",
        )
    withheld = [
        statement for statement in ATTESTED_STATEMENTS if not attestation.get(statement)
    ]
    if withheld:
        raise DeclarationRefused(
            DeclarationRefusal.NOT_ATTESTED,
            f"withheld: {', '.join(withheld)} — a run does not start on a "
            "statement the operator did not make (ADR-0007)",
        )
    return Declaration(
        name=str(target["name"]),
        url=str(target["url"]),
        auth_token=str(target.get("auth_token", "")),
        agent_type=str(target.get("agent_type", "assistant")),
        exposes_tool_calls=_flag(target, "exposes_tool_calls", False),
        declared_tools=_words(target, "declared_tools"),
        retains_session_state=_flag(target, "retains_session_state", False),
        holds_personal_records=_flag(target, "holds_personal_records", False),
        nonce=str(target.get("nonce", "")),
        note_planted=_flag(target, "note_planted", False),
        nonce_planted=_flag(target, "nonce_planted", True),
        echo_waived=_flag(target, "echo_waived", False),
        identity=str(attestation["identity"]),
        authorised_to_test=_flag(attestation, "authorised_to_test", False),
        not_production=_flag(attestation, "not_production", False),
        accepts_provider_policy_and_cost=_flag(
            attestation, "accepts_provider_policy_and_cost", False
        ),
        price_per_call=(
            None if cost.get("price_per_call") is None else str(cost["price_per_call"])
        ),
        currency=str(cost.get("currency", "")),
    )
