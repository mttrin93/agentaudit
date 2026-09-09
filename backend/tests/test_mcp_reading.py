"""A compact reading drops prose and never a label
([ADR-0101](../../docs/adr/0101-a-compact-reading-may-drop-prose-and-never-a-label.md)).

**Every fixture here is a served payload and never hand-written JSON.** The rule
under test is a claim about what survives a compaction of *this* document, so a
finding is built through `ReportedFinding.of` and serialised through
`payload.document` — the same two functions the API's own report route runs. A
hand-written dict would pass this file on the day `_finding` grew a key it does
not carry, which is the day the rule is supposed to fail.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import replace
from enum import StrEnum
from typing import Any

import backend.bench as bench
from backend.bench.assembler import (
    PROSE_QUOTED_THE_PAYLOAD,
    AttributedCause,
    Attribution,
    FindingsReading,
    FindingsSection,
    ReportedFinding,
    WithheldProse,
)
from backend.bench.library import Case, Family
from backend.bench.narration import BrokenInstrument, NarrativeFailure
from backend.bench.payload import document, figures
from backend.bench.scanner import control_claiming
from backend.mcp.reading import PROSE_ONLY, compact_finding, compact_report
from backend.tests.conftest import A_FIX, a_narration
from backend.tests.test_payload import a_payload, a_result

MISSING = object()
"""What a compact leaf is compared against when the payload has no such path.

A sentinel rather than `None`, because `None` is a value the payload really holds —
`source_anchor.location` on every run with no checkout — and a comparison that read
it as *absent* would call a copied null a computed one."""


def _finding(case: Case, fix: str = A_FIX) -> ReportedFinding:
    """One failure as the signed document reports it, through the real constructor.

    `fix` is a parameter because a fix that quotes the case payload is withheld, and
    `withheld` — a closed-set member — is only worth walking when it is not empty.
    """
    narration = a_narration(case_id=case.id, family=Family.DATA_LEAKAGE, fix=fix)
    return ReportedFinding.of(
        narration,
        Attribution(
            case_id=case.id,
            family=Family.DATA_LEAKAGE,
            reading=AttributedCause.NOT_DECLARED,
            transform=case.transform,
            control=control_claiming(case.family),
        ),
        case,
    )


def _served(section: FindingsSection) -> dict[str, Any]:
    """That findings section inside a whole served payload, as bytes-shaped data."""
    return document(a_payload(result=replace(a_result(), findings=section)))


def test_a_compact_finding_drops_prose_and_only_prose(leakage_case: Case) -> None:
    """The rule, as a set difference.

    A label added to `ReportedFinding` later lands in `dropped` and fails here,
    which is why this is a difference and not a list of fields somebody remembered
    to update (ADR-0101 §5).
    """
    served = _served(FindingsSection(reported=(_finding(leakage_case),)))
    one = served["findings"]["findings"][0]

    assert set(one) - set(compact_finding(one)) == PROSE_ONLY


def _closed_set_members() -> set[str]:
    """Every member of every closed set this codebase has, as the strings they are.

    Discovered rather than listed, on ADR-0101's own reasoning: a list of members is
    a list that stops checking the day one is added, which is the failure mode
    `WithheldProse` and `FindingsReading` were made closed sets to prevent.

    **Imported here rather than read off `sys.modules`**, which is the same fact
    about ordering that `conftest.reachable_from` walks imports for: what another
    test happened to import first is not a property of this one, and a walk that
    read the loaded modules would mean one thing under `pytest backend/tests` and
    another under `pytest backend/tests/test_mcp_reading.py`.
    """
    members: set[str] = set()
    for module in pkgutil.walk_packages(bench.__path__, f"{bench.__name__}."):
        for value in vars(importlib.import_module(module.name)).values():
            if isinstance(value, type) and issubclass(value, StrEnum):
                members.update(str(member) for member in value)
    return members


def _leaves(node: Any) -> set[Any]:
    return {value for _, value in figures(node)}


def test_every_closed_set_member_in_the_findings_section_survives(
    leakage_case: Case,
) -> None:
    """The walk ADR-0101 §5 asks for, over a served section and not over a list.

    The finding carries a withheld sentence on purpose: `withheld` is the closed set
    most easily lost, because it is empty on the ordinary run and an empty list
    survives every compaction ever written.
    """
    served = _served(
        FindingsSection(reported=(_finding(leakage_case, fix=leakage_case.payload[0]),))
    )
    compact = compact_report(served, urls={})
    members = _closed_set_members()

    found = _leaves(served["findings"]) & members
    assert WithheldProse.FIX in found, (
        "this fixture's fix did not trip the disclosure rule, so the walk below "
        "never sees a withheld member and proves less than it looks like it does"
    )
    assert found <= _leaves(compact["findings"])


def test_the_nested_readings_survive_as_their_member(leakage_case: Case) -> None:
    """`fix_standing` and `source_anchor` collapse to what a caller branches on.

    The member and not the record: a fix reaches a reviewer with its standing beside
    it (ADR-0073), so a suggestion is never handed over looking like a change this
    bench proved.
    """
    served = _served(FindingsSection(reported=(_finding(leakage_case),)))
    one = served["findings"]["findings"][0]
    compact = compact_finding(one)

    assert compact["fix_standing"] == one["fix_standing"]["reading"]
    assert compact["source_anchor"] == one["source_anchor"]["reading"]


def test_the_two_sentences_are_carried_verbatim(leakage_case: Case) -> None:
    """`reason` and `fix` as the instruments wrote them (ADR-0069, ADR-0101 §3).

    Verbatim including the withheld case: where the disclosure rule replaced a
    sentence, that replacement *is* the field, and it travels as itself rather than
    as a shorter version of itself somebody here composed.
    """
    served = _served(
        FindingsSection(reported=(_finding(leakage_case, fix=leakage_case.payload[0]),))
    )
    one = served["findings"]["findings"][0]
    compact = compact_finding(one)

    assert (compact["reason"], compact["fix"]) == (one["reason"], one["fix"])
    assert compact["fix"] == PROSE_QUOTED_THE_PAYLOAD
    assert leakage_case.payload[0] not in str(compact)


def test_a_broken_narrative_pass_is_not_an_empty_findings_list() -> None:
    """ADR-0050's fourth reading, at the boundary a model reads.

    A caller handed `[]` here would read a target that failed nothing; the truth is
    that the judge was unreadable — which is what happened on run `test-0`, where the
    narrative model answered `reads_as` with two exposure values.
    """
    served = _served(
        FindingsSection(
            reported=NarrativeFailure(
                broken=BrokenInstrument.JUDGE_UNREADABLE,
                detail="the model answered reads_as with two exposure values",
                explained=0,
                successes=3,
            )
        )
    )
    compact = compact_report(served, urls={})["findings"]

    assert compact["reading"] == FindingsReading.INSTRUMENTS_BROKE
    assert compact["instrument_failure"] == served["findings"]["instrument_failure"]
    assert compact["findings"] == []


def _the_payloads_own_path(path: str) -> str:
    """Where a leaf of the compact reading sits in the payload it was copied from.

    Three translations and no fourth, which is itself the assertion: the compaction
    renames one section, collapses two records to a member, and moves nothing else.
    """
    if path.startswith("rule."):
        return path.replace("rule.", "provenance.rule.", 1)
    if path.endswith((".fix_standing", ".source_anchor")):
        return f"{path}.reading"
    return path


def test_nothing_in_the_reading_is_computed(leakage_case: Case) -> None:
    """Every leaf is a payload leaf, at the path it was copied from (ADR-0006).

    Walked by path rather than by value, and that is what gives it teeth: a count of
    findings, a total or a rate averaged over two families is a number that happens
    to equal some other number in the document about half the time, so a test that
    only asked whether the value appeared *somewhere* would miss it. It is also
    where *nothing is reworded* (ADR-0101 §3) is held — a summarised sentence is a
    leaf at a payload path that does not match the payload's own.
    """
    served = _served(FindingsSection(reported=(_finding(leakage_case),)))
    compact = compact_report(served, urls={"payload": "http://bench/report/1"})
    payload_leaves = dict(figures(served))

    copied = {
        path: value
        for path, value in figures(compact)
        if not path.startswith("artefacts")
    }
    assert copied == {
        path: payload_leaves.get(_the_payloads_own_path(path), MISSING)
        for path in copied
    }
    assert compact["artefacts"] == {"payload": "http://bench/report/1"}


def test_the_attempts_per_case_sentence_is_not_dropped_with_the_rest(
    leakage_case: Case,
) -> None:
    """The exception ADR-0101 §2 names, and the reason the drop is by key.

    No label carries this fact, so the sentence is the only thing that does — which
    is why the drop is by key, and why a rule shaped `*_stated` would fail here and
    nowhere else.
    """
    served = _served(FindingsSection(reported=(_finding(leakage_case),)))
    rule = compact_report(served, urls={})["rule"]

    assert (
        rule["attempts_per_case"] == served["provenance"]["rule"]["attempts_per_case"]
    )
    assert (
        rule["attempts_per_case_stated"]
        == served["provenance"]["rule"]["attempts_per_case_stated"]
    )


def test_all_four_readings_of_the_narrative_pass_reach_the_caller(
    leakage_case: Case,
) -> None:
    """Four readings, four compact readings, and no fifth that collapses two.

    `None`, `()`, a tuple and a `NarrativeFailure` are four facts about a run rather
    than four spellings of an empty section (ADR-0050, ADR-0070 §4), and a compaction
    is exactly where three of them turn into the fourth.
    """
    sections = {
        FindingsReading.NO_NARRATIVE_INSTRUMENT_DECLARED: FindingsSection(),
        FindingsReading.NOTHING_TO_EXPLAIN: FindingsSection(reported=()),
        FindingsReading.EXPLAINED: FindingsSection(reported=(_finding(leakage_case),)),
        FindingsReading.INSTRUMENTS_BROKE: FindingsSection(
            reported=NarrativeFailure(
                broken=BrokenInstrument.REMEDIATION_UNREADABLE,
                detail="the answer could not be read as a fix",
                explained=1,
                successes=2,
            )
        ),
    }
    readings = {
        reading: compact_report(_served(section), urls={})["findings"]["reading"]
        for reading, section in sections.items()
    }

    assert readings == {reading: reading.value for reading in sections}


def test_a_sentence_a_member_beside_it_already_carries_is_dropped(
    leakage_case: Case,
) -> None:
    """The one drop ADR-0101 §2 names by field, and the member it leaves behind.

    Held section by section rather than only inside a finding: the reproducibility
    member sits beside its sentence in four sections of this document, and a
    compaction that dropped the sentence in one of them and not the others would be
    two rules wearing one name.
    """
    served = _served(FindingsSection(reported=(_finding(leakage_case),)))
    compact = compact_report(served, urls={})

    for section in (compact["measured"], compact["findings"]):
        assert "reproducibility_stated" not in section
    assert (
        compact["measured"]["reproducibility"] == served["measured"]["reproducibility"]
    )
    assert (
        compact["findings"]["reproducibility"] == served["findings"]["reproducibility"]
    )
