"""The narrative pass: every succeeded attempt explained, and no verdict moved.

Where a run stops producing **attempts** and starts producing **findings**
(CONTEXT.md keeps those apart, and the difference is exactly a narrative). The
decision this module implements — when the judge is called, with what, and what it
may reach — is
[ADR-0030](../../docs/adr/0030-the-judge-runs-over-the-scored-layers-successes.md).

**It is handed an `Attempt` and a `Case`, and there is no other parameter it could
be handed evidence through.** `narrate` names both types and neither is a union:
an `AdaptiveEpisode` is not an `Attempt` (ADR-0010) and a raw `Transcript` is what
`run_probe` hands back, so both are refused by `JudgeBrief.about` at runtime as
well as by the annotation here. Wiring the judge in was the first commit at which
a signature could have widened to accept both, and this one deliberately did not.

**Nothing here reaches a rate.** `TargetRun.rates` divides over `attempts` and this
module writes none: a `Narration` is produced *from* an attempt and never recorded
as one, so the population every rate, interval, band and `D` is read over is the
same population it was before the judge existed. The verdict on a finding is read
off the attempt by `Finding.of`, which is the one-way dependency ADR-0004 requires.

**The two instruments are a pair, and the pair is the caller's declaration.** A
`Narrator` holds both because a finding with a narrative and no fix is a finding
that is true and unactionable, which is the thing `judge.py` and `remediation.py`
each say they exist to prevent. The two fields are annotated with the two aliases
those modules declare *apart*, so a deployment may point them at separate models
without either of them moving the other (`remediation.Completion`).

**An instrument that answers with something that is not a narrative stops the
run.** `JudgeFailed`, `RemediationFailed` and `ReplyUnfinished` are raised
through, not caught: a truncated narrative is a named refusal rather than a
finding, and a finding that said nothing happened because a token cap fell early
is the one thing an artefact may not carry (`unfinished.py`, PLAN §10).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from backend.bench.adaptive.precedent import PrecedentStore
from backend.bench.evaluator import Verdict
from backend.bench.judge import Completion as Assess
from backend.bench.judge import (
    Disagreement,
    Finding,
    JudgeBrief,
    assess_finding,
    disagreements,
)
from backend.bench.library import Case
from backend.bench.remediation import Completion as Remediate
from backend.bench.remediation import Remediation, suggest_remediation
from backend.graph.runstate import Attempt


@dataclass(frozen=True)
class Narrator:
    """The two narrative instruments a run explains its successes with.

    One record rather than two arguments, on `api.run_config.Instruments`' own
    reasoning: a caller able to supply the judge without the remediation tool
    could produce findings that carry a reason and no fix, and both halves are
    unscored, so there is no reason for a run to hold one without the other.

    Two fields rather than one callable used twice, because `judge.Completion` and
    `remediation.Completion` are declared apart on purpose — a shared name would
    imply the two instruments must move together, and a deployment may point them
    at separate models. That neither of them is `adjudication.Completion` is the
    load-bearing part: the adjudicator produces a **verdict** and these produce
    prose, and no annotation here would accept one in place of the other.
    """

    assess: Assess
    """The judge, which writes the narrative and structurally cannot return a
    verdict (`judge.assess_finding`, ADR-0004)."""

    remediate: Remediate
    """The remediation tool, which is the one instrument allowed to hold the
    precedent store (`remediation.suggest_remediation`, ADR-0004)."""


@dataclass(frozen=True)
class Narration:
    """One succeeded attempt explained: the finding, and the fix written for it.

    Two records side by side rather than one, and that is a constraint rather
    than a preference: `Finding` cannot carry a `Remediation`, because judge.py
    may not import remediation.py and `test_precedent.py` walks the judge's
    *transitive* imports to say so (ADR-0004). So the pairing happens here, one
    module out, where holding both is harmless.

    The finding is the record CONTEXT.md defines; `remediation` is the fix the
    tool wrote for it, carrying the precedents that were in front of the model
    (`Remediation.informed_by`).
    """

    finding: Finding
    remediation: Remediation


def narrate(
    attempt: Attempt,
    case: Case,
    narrator: Narrator,
    precedent: PrecedentStore,
) -> Narration:
    """Explain one succeeded attempt: brief the judge, join, then write the fix.

    The order is the whole of ADR-0004 in four lines. The brief is blinded on the
    harness side of the call (`JudgeBrief.about`), the judge answers with a
    `Narrative` that has no field a verdict could be written into, `Finding.of`
    reads the verdict off the attempt, and only then does the store appear — held
    by `suggest_remediation`, which is the one instrument permitted one, and never
    by the judge, which has already returned.

    `attempt` is annotated `Attempt` and not a union of it with anything. A
    signature here that accepted an `AdaptiveEpisode` too would be the widening
    ADR-0010 asks a reader to stop at, and it would un-blind the judge through a
    channel that did not exist when ADR-0004 was written.
    """
    narrative = assess_finding(JudgeBrief.about(attempt, case), narrator.assess)
    finding = Finding.of(attempt, narrative)
    return Narration(
        finding=finding,
        remediation=suggest_remediation(finding, precedent, narrator.remediate),
    )


def narrate_successes(
    attempts: Sequence[Attempt],
    cases: Sequence[Case],
    narrator: Narrator | None,
    precedent: PrecedentStore,
) -> tuple[Narration, ...] | None:
    """Every succeeded attempt of one target explained, in the order it was made.

    **`None` and `()` are two facts and this returns both** (`budget.NOT_PRICED`'s
    own reasoning, one artefact along). `None` is a run made with no narrative
    instrument: it explained nothing, and a reader must not read that as a target
    with nothing to explain. `()` is the instruments having run over a target that
    succeeded at nothing, which is a measurement.

    The successes are selected on `Attempt.verdict` and never on a family, a case
    id or an index: the verdict is the fact that decides whether there is a failure
    to explain, and it is the only fact read here.
    """
    if narrator is None:
        return None
    records = {case.id: case for case in cases}
    return tuple(
        narrate(attempt, _record_for(attempt, records), narrator, precedent)
        for attempt in attempts
        if attempt.verdict is Verdict.SUCCEEDED
    )


def findings_in(narrations: Iterable[Narration]) -> tuple[Finding, ...]:
    """The findings alone, for a consumer that wants the record CONTEXT.md names.

    Here rather than left to a comprehension at every call site, because the
    precedent writer and the report both want exactly this and neither should have
    to know that a fix travels beside it.
    """
    return tuple(narration.finding for narration in narrations)


def disagreements_in(narrations: Iterable[Narration]) -> tuple[Disagreement, ...]:
    """The review queue: the findings whose two instruments read one transcript
    differently.

    `judge.disagreements` over the findings, reached through this module so that a
    caller holding narrations never has to unpack them to ask. Logged and never
    resolved: nothing here corrects a verdict or a reading, and the weaker of the
    bench's two human-in-the-loop instances is a list a human is handed while the
    run finishes (ADR-0004, PLAN §3).
    """
    return disagreements(findings_in(narrations))


def _record_for(attempt: Attempt, records: dict[str, Case]) -> Case:
    """The case record this attempt was made against, or a refusal.

    Refused rather than skipped. `JudgeBrief.about` already declines to brief an
    attempt against the wrong record, because a narrative written against one
    carries that record's coverage claim; an attempt whose record is absent
    entirely is the same fault with nothing to compare against, so it stops here
    rather than losing the finding quietly.
    """
    case = records.get(attempt.case_id)
    if case is None:
        raise ValueError(
            f"attempt {attempt.case_id!r} has no case record among the cases this "
            "target was run against, so there is nothing to brief a judge from. A "
            "finding needs the record's family and external identifier, and "
            "neither is derivable from an attempt alone"
        )
    return case
