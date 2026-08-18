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


class SuccessConditionKind(StrEnum):
    """The deterministic checks a case can ask for."""

    CANARY_IN_REPLY = "canary_in_reply"


@dataclass(frozen=True)
class ExternalId:
    """The published identifier a case tests one case *within*, and the
    boundary of that claim."""

    identifier: str
    not_tested: str


@dataclass(frozen=True)
class SuccessCondition:
    kind: SuccessConditionKind


@dataclass(frozen=True)
class Case:
    id: str
    family: Family
    external_id: ExternalId
    payload: str
    success_condition: SuccessCondition
    verdict_class: VerdictClass
    applies_to: tuple[str, ...]
    requires: tuple[str, ...]
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
            kind=SuccessConditionKind(record["success_condition"]["kind"])
        ),
        verdict_class=VerdictClass(record["verdict_class"]),
        applies_to=tuple(record["applies_to"]),
        requires=tuple(record["requires"]),
        added_on=record["added_on"],
        trigger=Trigger(record["trigger"]),
        status=CaseStatus(record["status"]),
        citation=record.get("citation"),
    )
