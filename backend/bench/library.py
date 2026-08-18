"""The case library as data — one record per file, never inline in code.

A case is one executable test belonging to a family: a payload plus a success
condition. Adding, retiring and diffing cases is therefore a data operation.
The enumerations here are closed sets on purpose: a case that cannot name its
family, its verdict class or the trigger that caused it to be written does not
load.
"""

import tomllib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any


class Family(StrEnum):
    """The six kinds of failure the bench tests for."""

    INDIRECT_PROMPT_INJECTION = "indirect_prompt_injection"
    SCOPE_CREEP = "scope_creep"
    WRONGFUL_COMMITMENT = "wrongful_commitment"
    DATA_LEAKAGE = "data_leakage"
    HALT_DEFEAT = "halt_defeat"
    DISCLOSURE_DENIAL = "disclosure_denial"


class VerdictClass(StrEnum):
    """How a verdict is reached. Read from the record, never inferred from the
    family."""

    DETERMINISTIC = "deterministic"
    JUDGED = "judged"


class Trigger(StrEnum):
    """Why a case exists. One of six, so the library's growth is auditable."""

    FAMILY_STOPPED_DISCRIMINATING = "family_stopped_discriminating"
    TARGET_PASSED_EVERYTHING = "target_passed_everything"
    USER_REPORTED_GAP = "user_reported_gap"
    NEW_AGENT_TYPE = "new_agent_type"
    NEW_TECHNIQUE_PUBLISHED = "new_technique_published"
    SCAN_CHECKLIST_GREW = "scan_checklist_grew"


class CaseStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class Precondition(StrEnum):
    """What a target must be able to do before a case can be run against it.

    A closed set, like every other enumeration here, and read before the attempt
    rather than after it: a precondition gates *measurability*, never scoring
    (spec, Implementation Decisions). A case whose precondition is unmet is
    skipped explicitly and its family reports **not measurable** — see
    `measurability.py`.
    """

    TOOL_CALL_VISIBILITY = "tool_call_visibility"
    """The endpoint returns the tool calls it made, not only its final text.

    Scope creep and halt defeat reach a deterministic verdict from that trace and
    from nothing else, so against a target without it they have no evidence to
    read (ADR-0004).
    """


class SuccessConditionKind(StrEnum):
    """The deterministic checks a case can ask for."""

    CANARY_IN_REPLY = "canary_in_reply"

    CANARY_INSTRUCTION_EXECUTED = "canary_instruction_executed"
    """Indirect prompt injection: the target did what a planted instruction in
    content it fetched told it to do."""

    TOOL_CALL_OUTSIDE_DECLARED_LIST = "tool_call_outside_declared_list"
    """Scope creep: the target called a tool its operator never declared it had."""

    TOOL_CALL_AFTER_STOP = "tool_call_after_stop"
    """Halt defeat: the target acted after the operator's stop signal reached it."""


@dataclass(frozen=True)
class ExternalId:
    """The published identifier a case tests one case *within*, and the
    boundary of that claim."""

    identifier: str
    not_tested: str


@dataclass(frozen=True)
class SuccessCondition:
    kind: SuccessConditionKind

    planted_canary: str | None = None
    """What executing a planted instruction produces, for the one kind that reads
    execution rather than a leak.

    Not the registration nonce and never confusable with it: that canary is
    planted *inside* the target's boundary and its appearance proves disclosure
    (ADR-0007), while this one is written by a third party into content the
    target fetched and its appearance proves obedience. Held on the case record
    because the verdict has to be re-derivable by a reader holding the record and
    the transcript, and for no other reason.
    """

    def __post_init__(self) -> None:
        executed = self.kind is SuccessConditionKind.CANARY_INSTRUCTION_EXECUTED
        if executed and not self.planted_canary:
            raise ValueError(
                f"{self.kind} reads whether a planted canary came back, so a case "
                "declaring it has to say which canary was planted"
            )
        if not executed and self.planted_canary is not None:
            raise ValueError(
                f"{self.kind} does not read a planted canary, so carrying one "
                "would put a value on the record that nothing checks"
            )


@dataclass(frozen=True)
class Case:
    id: str
    family: Family
    external_id: ExternalId
    payload: str
    success_condition: SuccessCondition
    verdict_class: VerdictClass
    applies_to: tuple[str, ...]
    requires: tuple[Precondition, ...]
    """What the target has to be able to do for this case to mean anything.

    Typed rather than free text so that an unmeasurable case is skipped by a
    check the type system can see, instead of by a string comparison nobody
    updates when the vocabulary moves.
    """
    added_on: date
    trigger: Trigger
    status: CaseStatus
    citation: str | None = None
    """Where a published technique came from. Not the trigger, which says why
    the case exists."""


def load_library(directory: Path) -> list[Case]:
    """Load every case record in a directory, ordered by file name for a
    stable run order."""
    return [load_case(path) for path in sorted(directory.glob("*.toml"))]


def load_case(path: Path) -> Case:
    record: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    external_id = record["external_id"]
    return Case(
        id=record["id"],
        family=Family(record["family"]),
        external_id=ExternalId(
            identifier=external_id["identifier"],
            not_tested=external_id["not_tested"],
        ),
        payload=record["payload"],
        success_condition=SuccessCondition(
            kind=SuccessConditionKind(record["success_condition"]["kind"]),
            planted_canary=record["success_condition"].get("planted_canary"),
        ),
        verdict_class=VerdictClass(record["verdict_class"]),
        applies_to=tuple(record["applies_to"]),
        requires=tuple(Precondition(name) for name in record["requires"]),
        added_on=record["added_on"],
        trigger=Trigger(record["trigger"]),
        status=CaseStatus(record["status"]),
        citation=record.get("citation"),
    )
