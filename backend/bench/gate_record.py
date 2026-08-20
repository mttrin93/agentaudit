"""One gate run's decision as data — the vocabulary both entry points write it in.

A gate run leaves two things behind and they say the same thing twice. The dated
Markdown a command-line run writes is prose for a person; what lives here is the
same decision as fields for a machine, so that a reader recovers each family's three
reference-agent rates and its `D` without parsing a sentence (spec §75, #84). A gate
run started from the console holds the same figures in memory and serves them on
`GET /gate-runs/{id}`, and this module is why the two describe one gate run in one
vocabulary rather than in two that have to be kept in step.

**Below both entry points, because both are its callers.** `backend/api/app.py`
validates these models onto the wire and `scripts/gate.py` writes them beside the
document. A second definition on either side is the thing this module exists instead
of: two shapes for one decision would only have to disagree once for a screen and a
document to state different gate results (ADR-0018).

**Nothing here computes anything.** Every figure is read off the `GateResult` that
`read_gate` produced — the rates, the intervals, the `D`, the ordering, the κ, the
library version and the count of attempts — and every sentence is the one the gate
prints. A second arithmetic over the same attempts is a second answer, and the
record's whole claim is that it is the same answer as the document's.

**A family barred from the counts says so on its own line.** An excluded family's
rates were measured and stay recorded — the attempts were made (ADR-0006) — and its
`FamilyFigures.excluded` names the reason they decided nothing, so no reader of one
family has to cross-reference a sibling list to learn that its `D` fed neither count
(ADR-0015). A family the target could not answer has no line at all: absent is not
zero, and excluded is not measured-and-failed.

**No composite, on either carrier.** Six families arrive here at once, which makes
this the shape most likely to grow a mean of six discrimination scores. There is no
field for one, no severity scale, and nothing adaptive: `A_break` is computed over
episodes and decides nothing, and the record is the scored layer alone (ADR-0005,
ADR-0010).
"""

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from backend.bench.gate import GateResult, stated_outcome, stated_rate
from backend.bench.library import Family
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import Excluded, FamilyOutcome, Rate


class CitedLibrary(BaseModel):
    """The library version a gate run was decided at: a count and a digest.

    Both, because a citation saying only *eighteen cases* cannot tell a reader
    whether the eighteen are the same eighteen (`library.LibraryVersion`), and the
    digest is what makes "has the bench changed since?" a question with an answer.
    """

    cases: int
    digest: str


class DeclaredRule(BaseModel):
    """The rule the gate is decided under, every threshold of it, as data.

    Served whole rather than summarised, and served *above* the outcome, because a
    pass means nothing without the bar it cleared: an operator reading *passed* with
    no rule beside it is trusting a verdict, and an operator reading the rule first
    can re-derive one. ADR-0003 fixed these numbers before the code that evaluates
    them existed for exactly that reason, and a threshold nobody can read is a
    threshold that can be moved at hour 30.

    **The numbers and the sentences, both.** `stated` is `GateRule.stated()` — the
    same text the gate prints beside its answer and the same text the report's
    provenance carries — and the fields beside it are the declared record's own, so a
    reader gets the rule in the bench's words and a caller gets it in figures without
    parsing them back out of prose.

    **Nothing here is a measurement, and nothing here is per family.** Every field is
    a declared threshold or a declared count; not one of them is a rate, an interval,
    a `D` or a κ that a gate run produced. The reference agents' rates and the
    per-family `D` live only in the gate run's document, and no route reads it (spec
    §75, "Per-family gate figures are out"). Nothing adaptive appears either: `T` and
    `k` are declared in `AdaptiveBudget`, and the adaptive layer decides nothing
    (ADR-0010).
    """

    stated: str
    """The whole rule as the gate prints it, from `rule.py` and never from a
    document. Multi-line, one clause per line, in the order ADR-0003 states them."""

    interval_confidence: float
    attempts_per_case: int
    discrimination_floor: float
    retirement_floor: float
    kappa_floor: float
    gold_transcripts_per_family: int
    tolerated_inversions: int
    family_count: int
    families_required: int
    monotonic_families_required: int
    minimum_fit_families: int


def declared_rule(rule: GateRule = DECLARED_RULE) -> DeclaredRule:
    """The declared rule as it goes on the wire, read off the record that holds it.

    `DECLARED_RULE` by default and never a literal here, so that a threshold moved in
    `rule.py` moves here and a threshold moved here is impossible: this function has
    no numbers in it.
    """
    return DeclaredRule(
        stated=rule.stated(),
        interval_confidence=rule.interval_confidence,
        attempts_per_case=rule.attempts_per_case,
        discrimination_floor=rule.discrimination_floor,
        retirement_floor=rule.retirement_floor,
        kappa_floor=rule.kappa_floor,
        gold_transcripts_per_family=rule.gold_transcripts_per_family,
        tolerated_inversions=rule.tolerated_inversions,
        family_count=rule.family_count,
        families_required=rule.families_required,
        monotonic_families_required=rule.monotonic_families_required,
        minimum_fit_families=rule.minimum_fit_families,
    )


class MeasuredRate(BaseModel):
    """One reference agent's failure rate on one family, with what it came from.

    The counts and the interval travel with the value, because a rate with no
    denominator beside it is a number a reader has to trust: thirty attempts per
    family per agent is the declared sample size, and it is printed rather than
    implied (ADR-0003).
    """

    agent: str
    value: float
    successes: int
    attempts: int
    lower: float
    upper: float
    stated: str


class FamilyFigures(BaseModel):
    """One family at this gate run: three rates, its `D`, its ordering, its verdict.

    Every number the per-family pass turned on, beside the verdict rather than
    instead of it, so a reader re-derives the line rather than trusting it. There is
    no band here and no severity: a band summarises one family for one *target*, and
    the subject of a gate run is the bench (ADR-0014, ADR-0018).
    """

    family: str
    rates: list[MeasuredRate]
    """The three agents in construction order — hardened, weak, trivial — because
    the ordering is what monotonicity is read across."""

    discrimination: float
    """`D` for this family: trivial minus hardened, from this gate run's attempts."""

    intervals_separate: bool
    inversions: int
    monotonic: bool
    passes: bool
    excluded: str | None
    """Why this family decided nothing, or null where it decided something.

    The reason off the decision's own exclusion record (`scorer.ExclusionReason`),
    carried on the family's own line and not only in a sibling list. An excluded
    family's rates and its `D` were measured and stay recorded — the attempts were
    made, and a measured rate stays measured (ADR-0006) — and `passes` beside them is
    the per-family rule read over figures the decision then set aside. Marked here so
    that no figure on this line can be read as a contribution to the outcome:
    exclusion is total, and a family unpublishable in the report may not prop up a
    pass (ADR-0015).

    **No default, deliberately.** Every caller states whether this family decided,
    because a field that defaults to *not excluded* is a field a call site forgets
    and nothing reports.
    """

    stated: str


class ExcludedFamily(BaseModel):
    """One family barred from the counts, with the reason and the reading behind it.

    Excluded is not scored a fail and not force-passed: its rates were measured and
    are still recorded, and they decide nothing in either count (ADR-0015).
    """

    family: str
    reason: str
    kappa: float | None
    stated: str


class JudgedReliability(BaseModel):
    """One judged family's κ against the gold set, or the stated absence of one."""

    family: str
    kappa: float | None
    stated: str


FIGURES_FROM_THE_RUN_ITSELF = (
    "every figure here was read off the attempts this gate run just made, in the "
    "process that made them. Nothing on this response was parsed out of a document: "
    "the dated Markdown a command-line gate run writes is prose, and a screen that "
    "depended on its shape would break on a rewording"
)


class GateDecided(BaseModel):
    """What this gate run decided, and everything a reader needs to re-derive it.

    The counts are over the fit families and the excluded ones are carried beside
    them with their reasons. There is no composite figure here, nothing that adds two
    families and no severity scale: the outcome is one of three answers to a stated
    rule, and the rule is served above this on the same response (ADR-0003, ADR-0005).
    """

    outcome: str
    """`passed`, `failed` or `not_decided` — three answers, because *not decided* is
    not a polite fail (`scorer.GateOutcome`)."""

    families_passing: int
    families_monotonic: int
    fit_families: int
    families: list[FamilyFigures]
    excluded: list[ExcludedFamily]
    reliability: list[JudgedReliability]
    library: CitedLibrary
    attempts: int
    agents: list[str]
    stated: str
    """The whole decision as the gate prints it, from `GateResult.stated()` — the
    same text a command-line run puts in its document."""

    read_from: str = FIGURES_FROM_THE_RUN_ITSELF


def _rate(agent: str, rate: Rate) -> MeasuredRate:
    """One agent's rate on one family, off the record the scorer produced."""
    return MeasuredRate(
        agent=agent,
        value=rate.value,
        successes=rate.successes,
        attempts=rate.attempts,
        lower=rate.interval.lower,
        upper=rate.interval.upper,
        stated=stated_rate(rate),
    )


def family_figures(outcome: FamilyOutcome, barred: Excluded | None) -> FamilyFigures:
    """One family's line, read off the outcome the gate decided it on.

    `barred` is the exclusion the decision recorded for this family, or `None` where
    it decided. Required rather than defaulted: an excluded family carrying no mark
    is the one failure this line can have, and it would be silent.
    """
    rates = outcome.rates
    return FamilyFigures(
        family=str(outcome.family),
        rates=[
            _rate("hardened", rates.hardened),
            _rate("weak", rates.weak),
            _rate("trivial", rates.trivial),
        ],
        discrimination=outcome.discrimination,
        intervals_separate=outcome.intervals_separate,
        inversions=outcome.monotonicity.inversions,
        monotonic=outcome.monotonicity.holds,
        passes=outcome.passes,
        excluded=None if barred is None else str(barred.reason),
        stated=stated_outcome(outcome),
    )


def gate_decided(gate: GateResult) -> GateDecided:
    """The decision as it goes on the wire, read off the result held in memory.

    Every field is the `GateResult` this gate run produced. Nothing is recomputed
    here — a second reading of the rates would be a second arithmetic — and nothing
    is read from the filesystem.

    The exclusions are read once and handed to each family's own line as well as
    carried beside them, so the two say the same thing: a family in `excluded` is a
    family whose figures are marked, and there is no third place either could come
    from (ADR-0015).
    """
    decision = gate.decision
    barred: Mapping[Family, Excluded] = {
        excluded.family: excluded for excluded in decision.excluded
    }
    return GateDecided(
        outcome=str(decision.outcome),
        families_passing=decision.families_passing,
        families_monotonic=decision.families_monotonic,
        fit_families=decision.fit_families,
        families=[
            family_figures(outcome, barred.get(outcome.family))
            for outcome in decision.outcomes
        ],
        excluded=[
            ExcludedFamily(
                family=str(excluded.family),
                reason=str(excluded.reason),
                kappa=excluded.kappa,
                stated=excluded.stated(),
            )
            for excluded in decision.excluded
        ],
        reliability=[
            JudgedReliability(
                family=str(family),
                kappa=None if measured is None else measured.kappa,
                stated=(
                    measured.stated()
                    if measured is not None
                    else "no κ was measured against the gold set, so the family is "
                    "not fit to report and decides nothing here"
                ),
            )
            for family, measured in sorted(gate.reliability.items())
        ],
        library=CitedLibrary(cases=gate.library.cases, digest=gate.library.digest),
        attempts=gate.attempts,
        agents=list(gate.agents),
        stated=gate.stated(),
    )


RECORDED_BESIDE_THE_DOCUMENT = (
    "this record and the dated Markdown beside it are two renderings of one reading. "
    "The document's scored-layer section is this record's `decision.stated`, the same "
    "string written twice, and every figure below it was read off the GateResult that "
    "produced that string. Nothing here was parsed out of the document: a record "
    "recovered from prose would break on a rewording, and there would be a second "
    "arithmetic for the two to disagree about"
)
"""Why the record and the document cannot disagree, stated on the record itself."""


class RecordedGateRun(BaseModel):
    """One gate run as data, beside the dated document that says it in prose.

    The rule is above the decision here as it is on the wire and on the screen: a
    pass or a fail means nothing without the bar it was decided against, and an
    operator reading the rule first re-derives the answer rather than trusting it
    (ADR-0003). The rule carried is the one this run applied, off the decision's own
    record rather than off whatever `rule.py` says today.

    **It names its document and nothing else on the filesystem.** The pairing is what
    makes the two legible as one gate run, and the direction of the reference is the
    point: the record names the prose, and the prose has never heard of the record.

    **The scored layer alone.** There is no adaptive figure here — the layer runs in
    the same gate run and carries no rate, no interval, no band and no `D`, and it is
    recorded in the document's own second section (ADR-0010).
    """

    decided_at: str
    """When this run was decided, as the document is dated: ISO, UTC, no locale."""

    document: str
    """The file name of the dated Markdown this record sits beside."""

    rule: DeclaredRule
    decision: GateDecided
    recorded: str = RECORDED_BESIDE_THE_DOCUMENT


def recorded_gate_run(
    gate: GateResult, *, decided_at: str, document: str
) -> RecordedGateRun:
    """This gate run as a record, off the result the run left in memory.

    One `GateResult` in, and the rendering the document prints comes back out on
    `decision.stated`: a caller writing both writes that string into the prose rather
    than asking the gate a second time, which is what makes the two unable to
    disagree rather than merely observed to agree.
    """
    return RecordedGateRun(
        decided_at=decided_at,
        document=document,
        rule=declared_rule(gate.decision.rule),
        decision=gate_decided(gate),
    )


def write_the_record(record: RecordedGateRun, path: Path) -> Path:
    """Write one gate run's record, in the shape its console counterpart serves.

    JSON, and the same JSON: `GET /gate-runs/{id}` validates these models onto the
    wire and this writes them to a file, so a reader who has parsed one has parsed
    the other. Indented and newline-terminated because it lands in a directory a
    person browses beside the documents it belongs to.
    """
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
