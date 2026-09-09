"""The signed payload, compacted for a caller that can fetch the document.

The rule, its alternatives and why they lost are
[ADR-0101](../../docs/adr/0101-a-compact-reading-may-drop-prose-and-never-a-label.md):
**a compact reading may drop prose, and it may never drop a label.**

Its local consequence is the shape of this module. Every compaction this project
performs happens in these two functions, from the payload and nothing else — no
second source, no recomputation, no default standing in for a field the payload did
not carry. It is the one place a label could be dropped, which is why it is one
place, and why the walk in `test_mcp_reading.py` has one function to walk.

**The drop is by key and never by suffix**, which is how ADR-0101 §2's exception is
held here: nothing in this module matches `*_stated`, so `attempts_per_case_stated`
and `band_stated` travel because no line of code was written to remove them.

**Which sections travel is a choice; what survives inside them is not.** A compact
reading carries the figures, the findings and the rule they were measured at,
because those are what the tool exists to hand a coding agent. The sections it does
not carry are in the document, which travels as a URL (ADR-0101 §4) — and inside
every section that *is* carried, nothing is dropped but the keys named below.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PROSE_ONLY = frozenset({"stated", "attributed_cause_stated", "informed_by_stated"})
"""The keys of a finding a compact reading may drop, and the only ones.

Each is a sentence composed for a reader holding only the document, and each
restates what a label beside it already carries: `stated` the reading, and its two
neighbours the attribution and the precedents named in the same record. A key not on
this list survives, so a member added to any of the five closed sets reaches the
caller with no edit here — and a *drop* is the thing that has to be argued for.
"""

RESTATED_BY_A_LABEL = PROSE_ONLY | {"reproducibility_stated"}
"""Every key the walk drops, section by section rather than finding by finding.

One key more than `PROSE_ONLY`, and it is the one ADR-0101 §2 names: the
reproducibility member sits beside its sentence in four sections of this document,
so the sentence is the half that goes. One key longer and not one *suffix* longer,
for the reason the module docstring gives — `variants_stated` and `band_stated` are
not on it, and neither is `attempts_per_case_stated`.
"""

COLLAPSED_TO_A_READING = ("fix_standing", "source_anchor")
"""The two records that travel as their `reading` member rather than whole.

Both are a member, a sentence and a detail the document already carries in full
(`FixStanding.diff`, `SourceAnchor.location`). What a caller branches on is the
member — proven or proposed (ADR-0073), anchored or one of four absences (ADR-0071)
— so the member is what a compact reading keeps.
"""


def compact_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    """One failure as a tool returns it: every label, both sentences, no prose.

    `reason` and `fix` are carried verbatim (ADR-0069, ADR-0101 §3), and that
    includes the withheld case: where the disclosure rule replaced a sentence,
    `PROSE_QUOTED_THE_PAYLOAD` *is* the `reason` or the `fix`, so it travels as
    itself and `withheld` says which instrument was silenced.
    """
    compact = {
        key: without_prose(value)
        for key, value in finding.items()
        if key not in PROSE_ONLY
    }
    for key in COLLAPSED_TO_A_READING:
        compact[key] = finding[key]["reading"]
    return compact


def compact_report(
    payload: Mapping[str, Any], *, urls: Mapping[str, str]
) -> dict[str, Any]:
    """A signed run's payload as a tool returns it, beside where the artefact is.

    **Every key is read directly and never with a default.** A payload missing one
    of these sections is a bench this surface does not understand, and it says so by
    raising rather than by handing a caller a reading with a section quietly empty —
    the local form of ADR-0050's line one level down, where a broken narrative pass
    reaches the caller as `instruments_broke` and never as an empty findings list.

    **The findings section is compacted by difference and not by a list of keys.**
    Only the findings themselves are rebuilt; everything else in the section is
    whatever the payload put there, so a key added to `payload._findings` is carried
    with no edit here (ADR-0101, *a hand-picked list of fields to keep*).

    Nothing here computes a figure (ADR-0006): every number below is a payload field
    copied, and there is no total, count, average or rate assembled at this seam.
    """
    findings = payload["findings"]
    return {
        "target": payload["target"],
        "measured": without_prose(payload["measured"]),
        "findings": without_prose(findings)
        | {"findings": [compact_finding(one) for one in findings["findings"]]},
        "rule": without_prose(payload["provenance"]["rule"]),
        "artefacts": dict(urls),
    }


def without_prose(node: Any) -> Any:
    """That value with the restated sentences gone, at every depth, and nothing else.

    One walk rather than a rule per section, so a nested closed set — a family's
    articles, a withheld family's reason, a control's status — is kept by the same
    default that keeps a top-level one.
    """
    if isinstance(node, dict):
        return {
            key: without_prose(value)
            for key, value in node.items()
            if key not in RESTATED_BY_A_LABEL
        }
    if isinstance(node, list):
        return [without_prose(value) for value in node]
    return node
