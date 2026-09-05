---
status: accepted
amended_by: 0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md, 0070-a-signed-document-may-carry-a-remediation.md
---

# The judge runs over the scored layer's successes, and a finding never touches a rate

> **Amended by [ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md)
> on the refusal, and on nothing else.** One paragraph below is reversed: a broken
> narrative instrument ends the narrative pass and no longer ends the run. The
> *costing* in that paragraph is what licensed the reversal rather than what it
> overturned — a truncation after the last attempt discards a measurement it did not
> affect, and the fourth reading of `narrations` this ADR priced as a ticket is now
> built, so the collapse it refused to accept never happens. Everything else here
> stands: nothing narrative reaches a rate, findings are all of a target's successes
> or the stated absence of all of them, and no partial narrative reaches an artefact.

[ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) settled what the judge
*is*: narrative fields only, blinded, no precedent, and no way to reach a verdict. It
never said when the judge is called, and nothing called it. `assess_finding`,
`Finding.of`, `suggest_remediation` and `disagreements` had callers in `backend/tests/`
and nowhere else, so a run produced **attempts** and never **findings** — and the
difference between those two words is exactly a narrative (CONTEXT.md).

The codebase said so itself, in the two places a reader would look:

> `backend/graph/runstate.py` — `succeeded_attempts`: "Deliberately not called findings:
> a finding is a verdict *plus* its narrative … and the judge that produces the
> narrative arrives in #8."

That `#8` was a number that never landed. What the gap left untrue was not small:
PLAN.md's phase 3 was marked done, spec stories 30 and 32 described behaviour no run
had, spec seam one claimed to cover "the judge's narrative fields", and `#32`'s
precedent write took a `Finding` that nothing in a run constructed. Meanwhile
`adjudicate` *was* wired, which is the sharp version of it: the bench decided
everything it decided and explained none of it.

**Decision.** For every attempt of a scored run whose verdict is `succeeded`, the run
builds a blinded `JudgeBrief`, calls `assess_finding` for the narrative, joins it to the
attempt's own verdict with `Finding.of`, and calls `suggest_remediation` for the fix. The
findings travel on the run's **result**, `calibration.TargetRun.narrations`. Verdict and
reading disagreements are logged there and resolved nowhere.

## Consequences

**One seam, and it takes an `Attempt` and a `Case`.** `backend/bench/narration.py` holds
it. `narrate(attempt, case, narrator, precedent)` names both evidence types and neither
is a union, which matters because wiring the judge in was the first commit at which a
signature could have widened to accept both an `Attempt` and an `AdaptiveEpisode`
— [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) asks
anyone reaching for that to stop, and `JudgeBrief.about` refuses both illegal inputs at
runtime as well. The order inside `narrate` is ADR-0004 in four lines: blind, ask, join
off the attempt, and only then let the precedent store appear — held by
`suggest_remediation`, which is the one instrument permitted one, and never by the judge,
which has already returned.

**Nothing here reaches a rate.** `TargetRun.rates` divides over `attempts`, and the
narrative pass records none: a `Narration` is produced *from* an attempt and never
recorded as one, so the population behind every rate, interval, band and `D` is the
population it was before the judge existed.

**Findings live on the result and deliberately not on `RunState`.** Two reasons, and
either alone would be enough. `judge.py` imports `graph/runstate.py` to annotate
`Finding.of`, so a `Finding` field on `RunState` would invert the dependency the judge's
constraints are held in. And `RunState` holds exactly two lists — `attempts` and
`episodes` — kept apart on ADR-0010's terms, so a third that spanned neither is precisely
where a reader would reach for a `findings` that spanned both.

**A run that explained nothing and a target with nothing to explain are two facts.**
`narrations` is `None` for the first and `()` for the second, on the reasoning
`budget.NOT_PRICED` uses about money and `NotMeasurable` uses about a family: a bench
that did not look must stay distinguishable from a target that held. `TargetRun` refuses
a run that explained *some* of its successes — findings are all of them or the stated
absence of all of them.

**The narrative instruments are a pair, and today they are built from the declared
adjudicator model.** `Narrator` carries two fields annotated with `judge.Completion` and
`remediation.Completion`, which those modules declare apart so a deployment may point
them at separate models. Both are built from `DeclaredModels.adjudicating`, and that is
**not** a widening of that field's meaning: it stays the instrument that decides the
judged families and the one κ is measured on
([ADR-0013](./0013-adjudication-is-a-third-instrument.md)).

The alternative was a fourth declared model — `AGENTAUDIT_JUDGE_MODEL`, a fourth
`DeclaredModels` field, a fourth line in the provenance block — and it loses *now* for
one reason: the signed payload has no narrative or remediation field, so a fourth
declared input would be one no artefact names, and a report that named an instrument
whose output it does not carry would be describing a run the reader cannot check
([ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md)). The
ticket that gives a narrative a place in the document is the ticket that declares the
instrument that wrote it. One consequence follows from sharing the string and is worth
saying out loud: a deployment that declares no bench model gets no narrator either, so it
measures and explains nothing — `narrations` reads `None`, which is the same answer
`scripts/probe_target.py --deterministic-only` gives for the same reason.

What this gives up is real: the two cannot be moved apart from configuration until the
report has a field for either, and the judge's prose still carries no reliability figure
of its own — κ is a figure about `adjudicate`, and the narrative's evaluation is the
DeepEval gold-set run ([ADR-0009](./0009-deepeval-executes-the-goldset.md)).

**The narrative spends, and what bounds it is the halt and the attempt count — not a row
in the consent table.** The estimate counts calls on the *operator's* endpoint at the
operator's own declared price, and `bench/usage.py` forbids the provider's figure for the
bench's own instrument calls from becoming the consent authority; the adjudicator has
always spent on those terms. What holds this honest is mechanism rather than a figure:
both instruments are reached from inside `run_suite`, the body `run_under_approval` will
not enter without a yes, so a run nobody confirmed spends nothing at either of them — and
a confirmed run makes at most one narrative and one fix per succeeded attempt, bounded by
the attempt count the operator was shown
([ADR-0007](./0007-canary-nonce-as-proof-of-control.md)). Their tokens go to the ledger's
**scored** layer: a narrative counted into the adaptive bucket would be a scored figure
inside an adaptive one.

**An instrument that did not answer stops the run.** `ReplyUnfinished`, `JudgeFailed` and
`RemediationFailed` are raised through the narrative pass and never caught. A reply
truncated at the token cap is the case that matters: `assess_finding` reads five labelled
lines off the text, so a cap that fell *after* the last of them parses into a complete
`Narrative` — and a finding built from one would be prose the model never finished, filed
as though it had. `refuse_unfinished` sits at the client, before the parser, which is
where it already sat for the adjudicator (`bench/unfinished.py`). *[Amended by
[ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md):
the three are caught once, at the pass, and become a `NarrativeFailure`. Everything
this paragraph says about what may not be built from a partial reply still holds — no
finding, no invented prose — and what changed is that the run finishes.]*

**What that costs is real and is stated rather than absorbed.** The adjudicator stops a
run because a missing verdict leaves a denominator short, and *a partial suite is void
rather than smaller* (ADR-0007). A narrative leaves no denominator short — every rate,
interval, band and `D` of a run whose judge broke is fully derivable — so a truncation
after the last attempt discards a measurement it did not affect: over HTTP the run settles
`failed`, its attempts survive on `RunState` and its assembled result and signable report
do not. Continuing with the rates and no findings was available and is **not** taken here,
because it would need a fourth reading of `narrations` — *the instruments ran and failed* —
beside the three above, and a `None` that meant either *nobody declared one* or *it broke*
is exactly the collapse this decision spends two paragraphs preventing. That fourth
reading is a ticket, not a line: it needs a name in CONTEXT.md's terms and a surface that
prints it, and #37 asked for the refusal rather than for the recovery. *[That ticket was
#102 and it is built: ADR-0050. The costing in this paragraph is what licensed the
reversal — the reading now exists, so nothing collapses into `None`, and the run keeps
the measurement this refusal used to discard.]*

**The review queue reaches a human on both entry points.** The findings and their
disagreements are on the run's result, which is the record they are logged in, and a list
nobody is handed is a list nobody reads: the two terminal scripts print it
(`console.findings_section`) and `api/runs.py` puts the count on the sentence a poller
reads. A count and never a resolution — neither instrument is corrected and no rate moves.

**A gate run does not narrate, and that is a decision.** A gate run measures the bench
and a finding is about a target
([ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)); nothing
the gate decides can read a narrative; and 540 attempts' worth of prose about the bench's
own reference agents is spend no artefact carries. So `scripts/gate.py` and
`api/gate_runs.py` pass no narrator and every gate run's `narrations` reads `None` — the
stated absence, not an empty result. The three entry points that attack a *target* do
narrate: `api/runs.py`, `scripts/probe_target.py` and `scripts/calibrate.py`. The probe
narrates only when it has an adjudicating model, because `--deterministic-only` promises
the wire and the four re-derivable families first and *a judge and its cost second*.

**Out of scope, and it needs its own ticket.** `bench/payload.py` and
`bench/assembler.py` carry no narrative or remediation field, so a finding now reaches a
caller and still not a document. Surfacing it — and deciding what a signed document may
say about a target's failure under
[ADR-0008](./0008-repo-disclosure-posture.md) — is a separate piece of work with its own
disclosure question, and it is deliberately not bundled here. *[That ticket was #112
and it is built:
[ADR-0070](./0070-a-signed-document-may-carry-a-remediation.md) spends the two
decisions this ADR costed and left — the disclosure answer, and the fourth declared
model named in the paragraph above. `DeclaredModels` now carries `narrative`, and the
condition this ADR set for that field is the one that was met: the document carries the
prose.]*

## Considered and rejected

**Narrate inside `attacker.run_case`, on the adjudication pool.** It would overlap the
prose with the sends the way a judged verdict already is. Rejected on two counts: a
narrative decides nothing, so latency spent on it buys nothing anybody waits for; and
`run_case` would then hold the precedent store, which is the one handle
`suggest_remediation` is the sole holder of (ADR-0004). Narration after a target's
attempts is sequential today, and pooling it stays available without moving the store.

**Narrate from the report assembler.** The assembler runs after the run and holds neither
the case records nor the transcripts in the shape a brief needs — and a run that produced
no finding could still be signed, which puts the judge behind the artefact rather than
inside the run.

**One `Completion` for both narrative instruments.** Rejected because
`judge.Completion` and `remediation.Completion` are declared apart precisely so one can
move without the other; a single argument would be the shared setting that separation
exists to prevent, arrived at from the call site instead of the module.

**A `findings` list on `RunState`.** Rejected for the two reasons above.
