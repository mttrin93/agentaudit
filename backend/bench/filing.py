"""The one write into the long-term memory: a run's deterministic findings, filed.

Where a run stops producing **findings** and starts contributing **precedent**
(CONTEXT.md keeps those apart: a finding is this run's record, a precedent is what
the next run retrieves). The decision this module implements — what is filed, what
is withheld, and *when* in a run the write happens — is
[ADR-0031](../../docs/adr/0031-a-run-files-its-deterministic-findings-after-it-has-read-them.md).

**Selection, never a caught exception.** `file_precedent` reads
`Finding.verdict_class` — copied off the attempt, so it cannot be inferred wrongly
from a family name — and the findings it did not file travel back on
`Filing.judged`. Why it selects rather than catching `JudgedPrecedent` is ADR-0031
point 3, and why the store refuses a judged finding at all is that exception's own
docstring.

**Nothing here reaches a rate.** The flow is one-way and it is one direction:
`Attempt` → `Finding` → `Precedent` → the store, and back out only to
`suggest_remediation` and `retrieve_precedent`, both of which produce prose. There
is no parameter here an `AdaptiveEpisode` could enter through and no return value a
rate is computed from — `TargetRun.rates` divides over `attempts`, which this module
neither reads nor writes (ADR-0010, ADR-0030).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from backend.bench.adaptive.precedent import DurablePrecedents, Precedent
from backend.bench.judge import Finding
from backend.bench.library import VerdictClass


@dataclass(frozen=True)
class Filing:
    """What one run contributed to the precedent store, and what it withheld.

    On the run's result rather than logged, for the reason `TargetRun.narrations`
    is: a refusal nobody is handed is a refusal nobody reads, and a judged family
    filing nothing has to be a statement a reader can find rather than an absence
    they have to notice.

    **Two empty tuples are not the three-state contract `narrations` carries.** A
    run made with no narrative instrument produced no findings, so it filed none —
    and *which* of the two it was is already answered one field over, on
    `narrations` itself (ADR-0030). Restating that distinction here would be two
    fields claiming to be the authority for one fact.
    """

    filed: tuple[Precedent, ...] = ()
    """The distinct precedents this run wrote, in the order they were written.

    The records rather than a count, because the one question a reader has about a
    store that now grows per run is *what went into it*, and a number cannot be
    checked against what the store holds.

    Distinct by `Precedent.key`, so this lists rows rather than writes: the key is
    a digest of the record, so two targets that failed one case identically are one
    entry here and one row in the store. It is not a claim that the store gained
    this many rows — a record an earlier run already filed has the same key, and
    finding out would cost a read per finding to answer a question nobody asked.
    """

    judged: tuple[Finding, ...] = ()
    """The findings this run did not file, and the field name is the whole reason.

    One per case per target, the same unit `filed` is (`_one_per_case`).

    Only one rule withholds a finding, so naming the field after it says why
    without a second field to carry a reason that is always the same one. The
    findings themselves and not their identifiers: a reader asking why the store
    has nothing from a judged family should not have to go back to the narrations
    to see what was measured.
    """


def file_precedent(findings: Iterable[Finding], store: DurablePrecedents) -> Filing:
    """File this run's deterministic findings, and report the ones withheld.

    `store` is annotated `DurablePrecedents` and deliberately not `PrecedentStore`:
    the read-only protocol promises no `record`, so the write handle exists in
    exactly the callers that hold the concrete type — which is `run_calibration`
    and nothing inside it (`calibration._run_target` takes the protocol, so the
    narrative pass structurally cannot write what it is about to read). Why the
    protocol was not widened instead is ADR-0031 point 2.
    """
    filed: list[Precedent] = []
    judged: list[Finding] = []
    keys: set[str] = set()
    for finding in _one_per_case(findings):
        if finding.verdict_class is not VerdictClass.DETERMINISTIC:
            judged.append(finding)
            continue
        entry = store.record(finding)
        # Reported once, because `Precedent.key` is a digest of the record and two
        # targets that failed one case identically are one row rather than two
        # (`Precedent.key`). Writing it twice is idempotent; *listing* it twice
        # would make this field disagree with the store it describes.
        if entry.key not in keys:
            keys.add(entry.key)
            filed.append(entry)
    return Filing(filed=tuple(filed), judged=tuple(judged))


def _one_per_case(findings: Iterable[Finding]) -> Iterator[Finding]:
    """The first finding of each case against each target, in the order it was made.

    **The unit of a precedent is a failure mode, and the case is its identity.** A
    case is attempted ten times against a target (#4), so a target that fails one
    carries up to ten findings of it — ten samples of the same mode, differing only
    in what the target replied and in how the judge paraphrased it. `Precedent.key`
    folds the ones that came back word for word identical and structurally cannot
    fold the rest, so this keeps one. Why that is the right unit, and why an attempt
    index is not the field `Finding` is missing, is ADR-0031 point 4.

    Ahead of the deterministic/judged split rather than after it, so that the
    withheld list is the same unit as the filed one: a reader shown ten copies of
    one judged case learns what one copy would have told them.

    The identity is `(target_name, case_id)`, both read off the record. Per target
    because two targets failing one case are two independent observations and the
    stored record carries no target to tell them apart (ADR-0011) — and read off
    the findings rather than taken from how the caller batched them, so no caller
    can widen or narrow this rule by grouping its argument differently.

    The *first* rather than a chosen one, because choosing would need a ranking
    over narratives and nothing in this bench can compute one — the same reason the
    lookup orders by recency (`RETRIEVAL_LIMIT`).
    """
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        identity = (finding.target_name, finding.case_id)
        if identity in seen:
            continue
        seen.add(identity)
        yield finding
