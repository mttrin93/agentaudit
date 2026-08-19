"""The artefact: one target run as canonical JSON, carrying counts and no verdict.

`assembler.py` produces the structured result — three sections, the coverage gaps
and no scalar. This module is the point at which that result stops being an object
in a process and becomes **bytes that travel**: sorted keys, fixed separators, and
byte-identical for an identical result, because a signature covers bytes and a
signature over an unstable serialisation certifies nothing (#50 binds the rendering
into it, #51 signs it).

**Counts, never a rate somebody computed once.** Every measured figure is written
with the counts it came from: `successes` and `attempts` beside the rate, the
interval's confidence beside the interval, the band cuts beside the bands, and
`agreements` of `transcripts` beside κ. That is the idiom `[admission]` and
`[[history]]` already follow on a case record, and it is what makes the verifier of
#51 possible at all — a recipient re-derives the arithmetic instead of trusting it.
A payload holding only computed figures would leave *re-derivable* a sentence in the
document rather than a property of it.

**No gate decision about the target, and no field that could hold one** (ADR-0018).
The gate is a claim about the bench: `D` is trivial minus hardened, monotonicity is
an ordering across three agents, and both thresholds are counts over families of
*contrast* — not one of them has a definition when the subject is a single target,
so there is no arithmetic here that could produce a target gate decision and any
field claiming to hold one could only be filled by copying the bench's own result
across. The bench's gate result appears once, as a `GateCitation` inside
`Provenance`, and the words differ deliberately: the bench *passed its gate*, the
target *has rates, intervals and bands*. Neither sentence is available for the other
subject, and `GateDecision` is not importable from here.

**Nothing totals, averages or ranks across families** (ADR-0005, D12). There is no
key at any depth that reaches across two families, and the structural half of that
claim is testable: drop a family from the result and every other byte of the
document is unchanged, because nothing anywhere is computed from more than one.

**Three kinds of nothing, kept apart.** A family measured at 0 of 30 is a
measurement; a family the target could not answer is `not_measurable` with the
reason that closes it; a judged family below the κ floor is **absent from the
measured figures** and named under `withheld` with the reading that barred it
(ADR-0015). A control the operator declared and nothing tested, and one the
checklist asks about and they did not declare, are two further absences and are
reported as themselves. None of the four is a rate of zero, and a reader can tell
which they are looking at without reading a footnote.

**No payload text, anywhere** (ADR-0008). Attempts are not serialised, only the
counts over them; episode transcripts and proposals are not serialised at all, only
the prose description the adaptive section already holds. Case **ids** appear where
a control was defeated, because an id is a pointer into the evidence and not a copy
of it.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.bench.assembler import (
    AdaptiveSection,
    CoverageGap,
    DeclaredSection,
    FamilyEntry,
    MeasuredSection,
    ReportedEpisode,
    ScannedControl,
    TargetResult,
)
from backend.bench.library import ExternalId, LibraryVersion
from backend.bench.registration import AttestationRecord
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import GateOutcome, Interval, Reliability
from backend.graph.budget import Layer

ARTEFACT = "agentaudit.target-report"
"""What this document is, written into it.

A reader who meets the file without the sender says what kind of artefact it is by
reading it, and `verify.py` refuses one of a kind it does not know rather than
checking a signature over something else.
"""

ARTEFACT_VERSION = 1
"""The shape of this document, so a later shape is a different shape and says so."""

CANONICAL_SEPARATORS = (",", ":")
"""No insignificant whitespace. Half of what makes the bytes stable; sorted keys
is the other half."""


class WithheldReason(StrEnum):
    """Why a judged family's rate is absent from the measured figures.

    Two members, because they are two different readings. A κ below the floor says
    the instrument that decided the family was measured and found wanting; no κ at
    all says nobody measured it, which is not the same fact and is not a κ of zero
    (ADR-0004, ADR-0013).
    """

    KAPPA_BELOW_FLOOR = "kappa_below_floor"
    NO_KAPPA_MEASURED = "no_kappa_measured"


@dataclass(frozen=True)
class Withheld:
    """One judged family the report may not publish, and the reading that barred it.

    Carries κ with its counts and the floor it faced, and **no rate** — the rate was
    measured and is recorded on the run (ADR-0006 keeps a measured rate measured),
    and what it does not have is a statable evidentiary strength, which is the whole
    of what a report is for (ADR-0015).
    """

    family: str
    reason: WithheldReason
    floor: float
    kappa: float | None = None
    agreements: int | None = None
    transcripts: int | None = None

    @classmethod
    def of(cls, entry: FamilyEntry, rule: GateRule = DECLARED_RULE) -> "Withheld":
        """The withholding one unfit entry produces, read off the entry itself.

        Derived rather than set, in the discipline `MeasuredSection.unfit_to_report`
        already follows: a renderer that had to be *told* which families to withhold
        is one where forgetting to ask publishes the rate.
        """
        reliability = entry.reliability
        if reliability is None:
            return cls(
                family=entry.family.value,
                reason=WithheldReason.NO_KAPPA_MEASURED,
                floor=rule.kappa_floor,
            )
        return cls(
            family=entry.family.value,
            reason=WithheldReason.KAPPA_BELOW_FLOOR,
            floor=reliability.floor,
            kappa=reliability.kappa,
            agreements=reliability.agreements,
            transcripts=reliability.transcripts,
        )

    def stated(self) -> str:
        """The line the report prints in place of the rate it is not printing."""
        if self.kappa is None:
            return (
                f"{self.family}: withheld — no κ was measured against the gold set, "
                "so the strength of the evidence behind this family's rate cannot "
                "be stated and the rate is not published (ADR-0004, ADR-0013)"
            )
        return (
            f"{self.family}: withheld — κ = {self.kappa:.2f} "
            f"({self.agreements} of {self.transcripts} transcripts agreed) is below "
            f"the declared floor of {self.floor:.2f}. The attempts were made and the "
            "rate is recorded; it is not published (ADR-0015)"
        )


@dataclass(frozen=True)
class GateCitation:
    """The bench's own gate result, cited as provenance and never as a result.

    The instrument's certification, in the part of a document that says *how this
    was made*. It is a fact about the bench — that a stated, falsifiable rule was
    put to three agents of known construction and could have answered "this bench
    measures nothing" — and it is the project's answer to the reader's legitimate
    question about why the figures above should be believed at all (ADR-0018).

    **Typed apart from the target's figures, and that is the whole of the design.**
    This record holds no `Rate`, no `Interval`, no `Band` and no `D`; it is reachable
    only through `Provenance`; and `GateDecision` — the record that carries the
    passing and monotonic counts, the per-family outcomes and the rule — is not
    imported by this module and cannot be put anywhere in this payload. A future
    contributor who wants a gate verdict beside a customer's agent name has to widen
    a type, which is the signal ADR-0010 established for exactly this class of
    mistake.
    """

    outcome: GateOutcome
    decided_on: date
    library: LibraryVersion
    document: str
    """Where the run that decided it is written down, so the citation is checkable."""

    def stated(self) -> str:
        """The citation in the bench's own words, which are not the target's.

        *The bench passed its gate.* There is no sentence available here in which a
        target passes or fails anything, and that absence is deliberate: what
        circulates is a screenshot of one section, so a field whose correctness
        depends on an adjacent caption is a field that will eventually be wrong in
        the flattering direction (ADR-0018).
        """
        return (
            f"the bench {self.outcome.value} its own gate on "
            f"{self.decided_on.isoformat()}, against its three agents of known "
            f"construction, at {self.library.stated()} — recorded in "
            f"{self.document}. A fact about the instrument that produced the "
            "figures above, and not a verdict on this target: this target has "
            "rates, intervals and bands, and passes and fails nothing"
        )


UNCITED_GATE = (
    "no gate run is cited — this report was produced by a bench whose own "
    "discriminating power is unstated here. A stated absence, not a blank: an "
    "uncited instrument is a fact about this report (ADR-0018)"
)
"""What provenance says when it cannot name a gate run.

Said rather than omitted. A missing line reads as a document that had nothing to
declare, and this one has something to declare and no way to declare it.
"""


@dataclass(frozen=True)
class DeclaredModels:
    """The three model identifiers a run was made under. Configuration, not results.

    The same three the gate document records, because they are the three settings
    that decide what a run *is*: the model the bench's own calibration equipment ran
    on, the model that adjudicates the two judged families, and the model the
    adaptive attacker runs on. They are named as models and never as agents — no
    reference agent is named in a target's report, because naming one invites the
    comparison "your agent scored between the weak and the hardened reference",
    which is a composite judgement wearing a comparison's clothes (ADR-0018).
    """

    calibration: str
    """The model the bench's calibration equipment ran on, and so the model its
    gate citation was earned on (ADR-0012: a `D` is a reading about one pair of
    models and never a general claim)."""

    adjudicating: str
    """The instrument that decides the judged families, and the one κ is measured
    on (ADR-0013). Never a calibration model's."""

    attacking: str
    """The adaptive layer's model, and the adaptive layer's only. It decides
    nothing that is scored (ADR-0010)."""


@dataclass(frozen=True)
class Provenance:
    """How this artefact was made — and nothing about what it found.

    Everything a reader needs in order to ask whether the figures were produced by
    an instrument worth believing: who attested to the run, under which three
    models, against which library, at what cost per layer, and whether the bench
    had passed its own gate. Not one field here is a measurement of the target.
    """

    attestation: AttestationRecord
    """The recorded attestation, not a name a caller typed.

    The identity is read off the record that authorised the run, so a report cannot
    name somebody who never attested — and the record carries the endpoint as a
    hash, because a live URL that answers jailbreak payloads is not a thing to write
    into a document that travels (ADR-0008).
    """

    models: DeclaredModels
    library: LibraryVersion
    calls_spent: Mapping[Layer, int]
    """What each layer put on the wire, per layer and never blended.

    Both layers are required — see `__post_init__`. A provenance block that could
    omit the adaptive counter would be one where a run's second half spent the
    operator's budget with nothing on the page to say so (ADR-0007).
    """

    gate: GateCitation | None = None
    """The bench's own gate result, or nothing — and nothing still prints a line."""

    def __post_init__(self) -> None:
        missing = sorted(
            layer.value for layer in Layer if layer not in self.calls_spent
        )
        if missing:
            raise ValueError(
                f"the provenance block reports no calls for {missing}. Spending is "
                "reported per layer and both layers are always reported: a block "
                "that named one would hide which half of the run spent the "
                "operator's budget (ADR-0007)"
            )


@dataclass(frozen=True)
class TargetPayload:
    """One target run, ready to be serialised, signed, served and rendered.

    A result, the provenance of the run that produced it, and the rule the figures
    were measured under. There is no fourth field, and in particular there is no
    field for a summary of any kind: a reader who wants a single number will build
    one out of whatever is on the page, so the page does not offer one (ADR-0005).
    """

    result: TargetResult
    provenance: Provenance
    rule: GateRule = DECLARED_RULE
    """The rule the rates were measured under, carried so the interval a reader
    recomputes is the interval this run measured (ADR-0003)."""


def document(payload: TargetPayload) -> dict[str, Any]:
    """The payload as plain data, in the shape the canonical bytes are taken over.

    Built key by key rather than reflected off the dataclasses, so that what leaves
    the building is a decision somebody made: a field added to a record upstream
    does not silently start travelling, and one that must never travel — an
    attempt's transcript, an episode's probes — has nowhere to arrive.
    """
    return {
        "artefact": ARTEFACT,
        "artefact_version": ARTEFACT_VERSION,
        "target": payload.result.target_name,
        "measured": _measured(payload.result.measured, payload.rule),
        "declared": _declared(payload.result.declared),
        "adaptive": _adaptive(payload.result.adaptive),
        "coverage_gaps": [_gap(gap) for gap in payload.result.coverage_gaps],
        "provenance": _provenance(payload),
    }


def canonical_json(payload: TargetPayload) -> str:
    """The payload as canonical JSON: sorted keys, fixed separators, no whitespace.

    Byte-identical for an identical result, which is the property that makes a
    signature over it mean anything. `ensure_ascii` is off so that the prose reads
    as it was written — κ is κ — and the encoding is fixed at UTF-8 by
    `canonical_bytes`, which is what is actually signed.
    """
    return json.dumps(
        document(payload),
        sort_keys=True,
        separators=CANONICAL_SEPARATORS,
        ensure_ascii=False,
    )


def canonical_bytes(payload: TargetPayload) -> bytes:
    """The bytes a signature covers, and the bytes a verifier reads back."""
    return canonical_json(payload).encode("utf-8")


def write(payload: TargetPayload, path: Path) -> Path:
    """Write the canonical bytes to that path, and nothing else.

    No trailing newline and no re-encoding: the file has to be the bytes that were
    signed, or the signature checks something other than the document a recipient
    holds.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload))
    return path


def _measured(section: MeasuredSection, rule: GateRule) -> dict[str, Any]:
    """What the fixed suite measured: counts per family, and what is not published.

    The unfit judged families are **absent** from `judged` and present in
    `withheld`, so a consumer that reads the figures cannot reach a rate ADR-0015
    says must not be published, however carelessly it reads them. Which families
    those are is derived here from `fit_to_report` and is never an argument: a
    caller that could pass the list is a caller that could pass an empty one.
    """
    barred = withheld_entries(section)
    withheld = tuple(Withheld.of(entry, rule) for entry in barred)
    barred_families = {entry.family for entry in barred}
    return {
        "reproducibility": section.reproducibility.value,
        "reproducibility_stated": section.reproducibility.stated(),
        "cuts": {
            "holds_at_or_below": section.cuts.holds_at_or_below,
            "fails_at_or_above": section.cuts.fails_at_or_above,
            "stated": section.cuts.stated(),
        },
        "deterministic": [_entry(entry, rule) for entry in section.deterministic],
        "judged": [
            _entry(entry, rule)
            for entry in section.judged
            if entry.family not in barred_families
        ],
        "withheld": [
            {
                "family": one.family,
                "reason": one.reason.value,
                "floor": one.floor,
                "kappa": one.kappa,
                "agreements": one.agreements,
                "transcripts": one.transcripts,
                "stated": one.stated(),
            }
            for one in withheld
        ],
        "not_measurable": [
            {
                "family": family.value,
                "reason": reason.value,
                "stated": reason.stated(),
            }
            for family, reason in sorted(
                section.not_measurable.items(), key=lambda pair: pair[0].value
            )
        ],
    }


def withheld_entries(section: MeasuredSection) -> tuple[FamilyEntry, ...]:
    """The judged entries whose rate this payload may not publish."""
    return tuple(entry for entry in section.judged if not entry.fit_to_report)


def _entry(entry: FamilyEntry, rule: GateRule) -> dict[str, Any]:
    """One family's figures, each beside the counts it is derived from.

    `successes` and `attempts` are what a verifier recomputes the rate from; the
    interval's confidence and the band cuts are what it recomputes the interval and
    the band from. Every figure here is therefore checkable, which is the difference
    between a document that says it is re-derivable and one that is.
    """
    return {
        "family": entry.family.value,
        "verdict_class": entry.verdict_class.value,
        "successes": entry.rate.successes,
        "attempts": entry.rate.attempts,
        "rate": entry.rate.value,
        "interval": _interval(entry.rate.interval),
        "interval_confidence": rule.interval_confidence,
        "band": entry.band.value,
        "band_stated": entry.band.stated(),
        "discrimination": entry.discrimination,
        "coverage": [_external(identifier) for identifier in entry.coverage],
        "reliability": _reliability(entry.reliability),
    }


def _interval(interval: Interval) -> dict[str, float]:
    return {"lower": interval.lower, "upper": interval.upper}


def _external(identifier: ExternalId) -> dict[str, str]:
    """The published identifier a family's cases test one case *within*, with the
    boundary of that claim beside it (ADR-0002)."""
    return {
        "identifier": identifier.identifier,
        "tests_one_case_within": identifier.identifier,
        "does_not_test": identifier.not_tested,
    }


def _reliability(reliability: Reliability | None) -> dict[str, Any] | None:
    """κ with its counts and its floor, on a judged entry, and `None` elsewhere.

    `None` on a deterministic entry and it must be: a success condition is
    authoritative and re-derivable, so there is no instrument for a reliability
    figure to be about and one printed there would say the verdict needed vouching
    for (ADR-0004).
    """
    if reliability is None:
        return None
    return {
        "kappa": reliability.kappa,
        "agreements": reliability.agreements,
        "transcripts": reliability.transcripts,
        "floor": reliability.floor,
        "stated": reliability.stated(),
    }


def _declared(section: DeclaredSection) -> dict[str, Any]:
    """The declared-and-defeated join: statuses and names, and no figure at all."""
    return {
        "reproducibility": section.reproducibility.value,
        "reproducibility_stated": section.reproducibility.stated(),
        "controls": [_control(control) for control in section.controls],
        "defeated": [control.control.value for control in section.defeated],
        "absent": [
            {
                "control": control.value,
                "stated": (
                    f"{control}: not declared — the checklist asks about this "
                    "control and this target did not claim it. An absence is not a "
                    "finding and nothing was attempted against it"
                ),
            }
            for control in section.absent
        ],
    }


def _control(control: ScannedControl) -> dict[str, Any]:
    """One declared control and what the attacks made of it. Case ids, no counts."""
    return {
        "control": control.control.value,
        "family": control.family.value,
        "status": control.status.value,
        "broken_by": list(control.broken_by),
        "not_measurable": (
            None if control.not_measurable is None else control.not_measurable.value
        ),
        "stated": control.stated(),
    }


def _adaptive(section: AdaptiveSection) -> dict[str, Any]:
    """One agent's search, in prose, marked not reproducible (ADR-0010, ADR-0017).

    Episodes carry the family, the outcome, the turn count and the prose. Their
    transcripts and their proposals are not here and have nowhere to be: a route
    that beat a target is a working unpublished exploit, and this document is the
    one that leaves the building (ADR-0008).
    """
    return {
        "reproducibility": section.reproducibility.value,
        "reproducibility_stated": section.reproducibility.stated(),
        "stated": section.stated(),
        "episodes": [_episode(episode) for episode in section.episodes],
        "families_broken": sorted(family.value for family in section.families_broken),
    }


def _episode(episode: ReportedEpisode) -> dict[str, Any]:
    return {
        "family": episode.family.value,
        "outcome": episode.outcome.value,
        "turns": episode.episode.turns,
        "description": episode.description,
        "stated": episode.stated(),
    }


def _gap(gap: CoverageGap) -> dict[str, str]:
    return {"category": gap.category, "reason": gap.reason, "stated": gap.stated()}


def _provenance(payload: TargetPayload) -> dict[str, Any]:
    """How this was made: the attestation, the models, the library, the spend, the
    gate citation and the rule.

    The target's name is read off the result rather than carried on the provenance
    record, so the block and the figures above it cannot name two different agents.
    """
    provenance = payload.provenance
    record = provenance.attestation
    return {
        "target": payload.result.target_name,
        "attestation": {
            "identity": record.attestation.identity,
            "endpoint_sha256": record.endpoint_hash,
            "recorded_at": record.recorded_at.isoformat(),
            "statements": [wording for _, wording in record.attestation.STATEMENTS],
        },
        "models": {
            "calibration": provenance.models.calibration,
            "adjudicating": provenance.models.adjudicating,
            "attacking": provenance.models.attacking,
        },
        "library": {
            "cases": provenance.library.cases,
            "digest": provenance.library.digest,
            "stated": provenance.library.stated(),
        },
        "calls_spent": {layer.value: provenance.calls_spent[layer] for layer in Layer},
        "gate": _citation(provenance.gate),
        "rule": {
            "interval_confidence": payload.rule.interval_confidence,
            "attempts_per_case": payload.rule.attempts_per_case,
            "kappa_floor": payload.rule.kappa_floor,
            "stated": payload.rule.stated(),
        },
    }


def _citation(citation: GateCitation | None) -> dict[str, Any]:
    """The gate citation, or the stated absence of one. Never a missing key."""
    if citation is None:
        return {"cited": False, "stated": UNCITED_GATE}
    return {
        "cited": True,
        "outcome": citation.outcome.value,
        "decided_on": citation.decided_on.isoformat(),
        "library": {
            "cases": citation.library.cases,
            "digest": citation.library.digest,
        },
        "document": citation.document,
        "stated": citation.stated(),
    }


def figures(body: Any) -> Iterable[tuple[str, Any]]:
    """Every leaf of a serialised payload, with the dotted path that reached it.

    Here rather than in the tests because two consumers need it — the assertions
    that nothing totals across families and that no payload text travels — and a
    walker each would be two walkers that could disagree about where they had been.
    """
    yield from _walk(body, "")


def _walk(node: Any, path: str) -> Iterable[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, node
