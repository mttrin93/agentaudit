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
that is true and unactionable — and since
[ADR-0069](../../docs/adr/0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)
that is load-bearing rather than ergonomic: the judge answers *why it failed* and
writes no fix at all, so the second half of that guarantee is made by
`remediation.py` alone and a caller supplying one instrument without the other
would produce findings nothing could act on. The two fields are annotated with
the two aliases those modules declare *apart*, so a deployment may point them at
separate models without either of them moving the other (`remediation.Completion`).

**An instrument that answers with something that is not a narrative ends the
narrative pass and not the run.** `JudgeFailed`, `RemediationFailed` and
`ReplyUnfinished` are caught here, once, and become `NarrativeFailure` — the
fourth reading of `narrations`
([ADR-0050](../../docs/adr/0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md),
which reverses the refusal ADR-0030 took while it was the only alternative to a
collapsed `None`). What does not change is what a broken instrument may put in an
artefact: no partial narrative, no finding, and nothing that says nothing happened
because a token cap fell early (`unfinished.py`, PLAN §10). Anything else raised
through this pass is a fault in the bench and is not caught
(`NarrativeFailure.of`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.adaptive.precedent import PrecedentStore
from backend.bench.evaluator import Verdict
from backend.bench.judge import Completion as Assess
from backend.bench.judge import (
    Disagreement,
    Finding,
    JudgeBrief,
    JudgeFailed,
    assess_finding,
    disagreements,
)
from backend.bench.library import Case, one_of_the_six
from backend.bench.remediation import Completion as Remediate
from backend.bench.remediation import (
    Remediation,
    RemediationFailed,
    suggest_remediation,
)
from backend.bench.unfinished import ReplyUnfinished
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
    """The judge, which writes *why it failed* and structurally cannot return a
    verdict or a fix (`judge.assess_finding`, ADR-0004, ADR-0069)."""

    remediate: Remediate
    """The remediation tool, which writes *what to change* and is the one
    instrument allowed to hold the precedent store
    (`remediation.suggest_remediation`, ADR-0004, ADR-0069)."""


@dataclass(frozen=True)
class Narration:
    """One succeeded attempt explained: why it failed, and what to change.

    **Two records answering two questions, and neither answers the other's.** The
    finding says why it failed and carries no fix; the remediation says what to
    change and is the only answer to that a reader is handed
    ([ADR-0069](../../docs/adr/0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)).
    Before that decision both instruments wrote a fix and nothing said which one an
    engineer applied — and the judge's was always the unprecedented one, so the
    layout of a page would have defeated ADR-0019's claim about the store.

    Two records side by side rather than one, and that is a constraint rather
    than a preference: `Finding` cannot carry a `Remediation`, because judge.py
    may not import remediation.py and `test_precedent.py` walks the judge's
    *transitive* imports to say so (ADR-0004). So the pairing happens here, one
    module out, where holding both is harmless.

    The finding is the record CONTEXT.md defines; `remediation` is the fix the
    tool wrote for it, carrying the precedents that were in front of the model
    (`Remediation.informed_by`). It is also the unit `filing.file_precedent`
    files, because a precedent is a failure *and* its fix and no single
    instrument's output is both.
    """

    finding: Finding
    remediation: Remediation


class BrokenInstrument(StrEnum):
    """Which named failure ended a narrative pass — one member per raised outcome.

    Named after the outcome rather than after the instrument, and that is the
    honest shape rather than the convenient one: `JudgeFailed` and
    `RemediationFailed` each name their own instrument, and `ReplyUnfinished` is
    raised at the client both of them share (`unfinished.py`), so which of the two
    was mid-call is not derivable from it. A field that guessed would be a reader
    un-guessing it later.

    None of these is a verdict and none of them is a security result, on
    `unfinished.UnfinishedReply`'s own terms: an instrument's health is not an axis
    a target's defences are read on.
    """

    JUDGE_UNREADABLE = "judge_unreadable"
    """`judge.JudgeFailed` — the model answered with something that is not a
    narrative."""

    REMEDIATION_UNREADABLE = "remediation_unreadable"
    """`remediation.RemediationFailed` — the answer could not be read as a fix, so
    the finding it belongs to would be true and unactionable."""

    REPLY_UNFINISHED = "reply_unfinished"
    """`unfinished.ReplyUnfinished` — a reply refused at the client before a parser
    saw it, which is the mode the bench actually meets."""

    def stated(self) -> str:
        """The outcome in the words a run prints."""
        match self:
            case BrokenInstrument.JUDGE_UNREADABLE:
                return "the judge answered with something that is not a narrative"
            case BrokenInstrument.REMEDIATION_UNREADABLE:
                return "the remediation tool's answer could not be read as a fix"
            case BrokenInstrument.REPLY_UNFINISHED:
                return (
                    "a narrative instrument's reply was refused before it was "
                    "parsed, because the provider did not say it finished"
                )


@dataclass(frozen=True)
class NarrativeFailure:
    """The instruments ran and failed: the fourth reading of `narrations`.

    A record and not a sentinel, for the reason it is a fourth *reading* and not a
    fourth meaning of `None`: `None` says nobody declared a narrative instrument
    and `()` says the target succeeded at nothing, and a run whose judge broke is
    neither of those facts
    ([ADR-0050](../../docs/adr/0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md),
    ADR-0030). Every reader that can hold `narrations` can therefore tell the four
    apart without reading a footnote, which is the property `payload.py` holds over
    its own absences.

    **It carries no `Narration`, and the count of the ones that had been written is
    what it carries instead.** A run that explained some of its successes reports a
    subset nobody chose (`TargetRun.__post_init__`), so the findings written before
    the break are discarded — and discarded silently would be a report an operator
    cannot reconcile with the judge's own token bill, so the two counts are stated.
    """

    broken: BrokenInstrument
    """Which named failure ended the pass."""

    detail: str
    """What the failure said, verbatim.

    The exception's own message rather than a re-worded one: it names the model and
    the provider's stop reason, which is the sentence that tells an operator
    whether to raise a token cap or to look at their provider — and a second wording
    of it here would be a second statement that drifts.
    """

    explained: int
    """How many of this target's successes had been explained when it broke.

    Not a count of findings the run holds — it holds none. It is the figure that
    says how far the instruments got, and it is on the record because the tokens
    were spent and the ledger will show them.
    """

    successes: int
    """How many of the six's succeeded attempts there were to explain.

    The denominator of the sentence above, and the figure `TargetRun` checks this
    reading against its own attempts with.
    """

    def __post_init__(self) -> None:
        if self.successes < 1:
            raise ValueError(
                "a narrative failure over no successes is a failure of an "
                "instrument that was never asked: a run with nothing to explain "
                "reads `()`, which is a measurement and not a broken instrument"
            )
        if not 0 <= self.explained < self.successes:
            raise ValueError(
                f"{self.explained} of {self.successes} success(es) were explained "
                "before the break. A pass that explained all of them did not "
                "break, and a count outside its own denominator is not a reading "
                "of how far the instruments got"
            )

    @classmethod
    def of(cls, failure: Exception, explained: int, successes: int) -> NarrativeFailure:
        """This reading, off the failure that ended the pass.

        Refuses anything that is not one of the three, rather than filing it as a
        broken instrument: an exception this module does not know is a fault in the
        bench and not an instrument that answered badly. Why the catch is exactly
        three failures wide is argued in ADR-0050.
        """
        match failure:
            case JudgeFailed():
                broken = BrokenInstrument.JUDGE_UNREADABLE
            case RemediationFailed():
                broken = BrokenInstrument.REMEDIATION_UNREADABLE
            case ReplyUnfinished():
                broken = BrokenInstrument.REPLY_UNFINISHED
            case _:
                raise failure
        return cls(
            broken=broken,
            detail=str(failure),
            explained=explained,
            successes=successes,
        )

    def stated(self) -> str:
        """The whole reading, for the two surfaces that print it.

        The instrument's own words are quoted and terminated rather than spliced:
        neither `JudgeFailed` nor `ReplyUnfinished` ends its message in a full
        stop, and this sentence continues after it on a poller's one-line
        statement.
        """
        return (
            f"{self.broken.stated()}. The instrument said: "
            f"{self.detail.rstrip('. ')}. "
            f"{self.explained} of {self.successes} succeeded attempt(s) had been "
            "explained when it broke, and no finding is carried — findings are all "
            "of them or the stated absence of all of them. Every rate this run "
            "measured stands: nothing here is a verdict and nothing here moved one"
        )


Narrations = tuple[Narration, ...] | NarrativeFailure | None
"""The four readings of one target's explanation, as one name.

Spelled once so that the union cannot be written out at a call site with three of
the four arms in it. The four are: `None`, no narrative instrument was declared;
`()`, the instruments ran and the target succeeded at nothing; a tuple, every
succeeded attempt of the six explained; and a `NarrativeFailure`, the instruments
ran and failed (ADR-0050).
"""


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
    # The judge has returned before the store appears, and it returned no fix:
    # what it wrote is why this failed, and what to change is written below with
    # the precedent for this family in front of it (ADR-0069).
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
) -> Narrations:
    """Every succeeded attempt of one target explained, in the order it was made.

    **`None`, `()` and a `NarrativeFailure` are three facts and this returns all
    three** (`budget.NOT_PRICED`'s own reasoning, one artefact along). `None` is a
    run made with no narrative instrument: it explained nothing, and a reader must
    not read that as a target with nothing to explain. `()` is the instruments
    having run over a target that succeeded at nothing, which is a measurement. A
    `NarrativeFailure` is the instruments having run and broken, which is neither
    of those and is the reading ADR-0050 adds.

    Whether there is a failure to explain is read off `Attempt.verdict` and off
    nothing else — never a case id, never an index, and never a family name. Which
    *tier* the attempt belongs to is a second question and is answered below.

    **The six's successes, and the tier's are stated as unexplained rather than
    explained.** A `Finding` carries the EU AI Act articles its family bears, and an
    elective family's label is a table of its own that nothing shortening a printed
    coverage claim reads
    ([ADR-0039](../../docs/adr/0039-a-familys-label-is-one-record.md)); a target
    report says which elective families a run was not asked for and nothing else
    about the tier
    ([ADR-0018](../../docs/adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md),
    ADR-0035). So an elective success reaches no `Finding`, no remediation and no
    precedent — and `judge.narrated` refuses one at the type's own door, so this
    filter is where the decision is taken rather than the only place it holds. A
    narrated elective family is a decision with an ADR of its own, which is where the
    articles question would be settled.
    """
    if narrator is None:
        return None
    records = {case.id: case for case in cases}
    narratable = [
        attempt
        for attempt in attempts
        if attempt.verdict is Verdict.SUCCEEDED and one_of_the_six(attempt.family)
    ]
    explained: list[Narration] = []
    for attempt in narratable:
        try:
            explained.append(
                narrate(attempt, _record_for(attempt, records), narrator, precedent)
            )
        except (JudgeFailed, RemediationFailed, ReplyUnfinished) as failure:
            # The pass ends here and the run does not. The narrations already
            # written are dropped rather than returned, because `TargetRun` refuses
            # a run that explained *some* of its successes and a subset nobody chose
            # is exactly what this reading exists to avoid reporting.
            return NarrativeFailure.of(
                failure, explained=len(explained), successes=len(narratable)
            )
    return tuple(explained)


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
