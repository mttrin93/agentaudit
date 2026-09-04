---
status: accepted
---

# A run whose narrative instruments broke is measured, explained nowhere, and signable

[ADR-0030](./0030-the-judge-runs-over-the-scored-layers-successes.md) wired the judge
into a run and, in the same decision, refused to let a broken judge be anything other
than the end of the run. `JudgeFailed`, `RemediationFailed` and `ReplyUnfinished` were
raised through `narration.narrate_successes` and never caught, so a narrative truncated
at a token cap settled the whole run `failed`: its attempts survived on `RunState` and
its assembled result and signable report did not.

That ADR costed the refusal in the open and named the thing it was buying instead:

> A narrative leaves no denominator short — every rate, interval, band and `D` of a
> run whose judge broke is fully derivable — so a truncation after the last attempt
> discards a measurement it did not affect. Continuing with the rates and no findings
> was available and is **not** taken here, because it would need a fourth reading of
> `narrations` […] and a `None` that meant either *nobody declared one* or *it broke*
> is exactly the collapse this decision spends two paragraphs preventing.

So the refusal was never a judgement that the measurement is worthless. It was the safe
default in front of a missing distinction, and it stood while `narrations` had three
readings and a `None` that would have had to carry a fourth meaning. #102 is the ticket
ADR-0030 said this was, and it exists because the distinction can be built rather than
collapsed.

**Decision.** `narrations` gains a fourth reading and it is a **record**, not a fourth
meaning of an existing value: `narration.NarrativeFailure`, naming which instrument
failure ended the pass (`BrokenInstrument`), what it said, how many of the target's
successes had been explained when it broke, and how many there were. `narrate_successes`
catches the three named failures once, at the pass, and returns it. The run finishes,
every rate it measured stands, no finding is carried, and **the report is assembled and
signed on exactly the terms it would have been signed on had the judge answered.**

## Consequences

**Four readings, and the type refuses three of the four collapses on its own.**
`narrations: Narrations` is `tuple[Narration, ...] | NarrativeFailure | None`. `None` is
a run made with no narrative instrument, `()` is the instruments having run over a target
that succeeded at nothing, a tuple is every succeeded attempt of the six explained, and a
`NarrativeFailure` is the instruments having run and failed. No reader can mistake the
fourth for either absence, because it is a different type and not a value inside one —
which is the property `payload.py` holds over the absences a report keeps apart, and the
reason a sentinel was refused below. The union is spelled once, as `narration.Narrations`,
so no call site can write out three of its four arms.

**The pass ends and the run does not, and what a broken instrument may put in an
artefact does not change.** No partial narrative, no finding assembled from half an
answer, and nothing that says nothing happened because a token cap fell early
(`unfinished.py`, PLAN §10). The findings written before the break are **discarded**
rather than returned: `TargetRun.__post_init__` refuses a run that explained *some* of
its successes, because a subset nobody chose is the report ADR-0030 forbids, and findings
stay all of them or the stated absence of all of them. What the reading carries instead
is the two counts — *n* of *m* explained — because those tokens were spent, the ledger
shows them, and an operator reconciling a bill against an empty findings section should
not have to infer how far the instruments got.

**The catch is three named failures wide and no wider.** `NarrativeFailure.of` re-raises
anything else, so a `ValueError` from `narration._record_for`, a transport fault or a bug
in the pass is still a run that stops. A bare `except Exception` here would have turned
every defect in the narrative pass into a run that quietly explained nothing, which is
PLAN §10's own failure mode reached from the opposite direction to the one this ADR
fixes.

**`findings` and `disagreements` project the fourth reading to `None`, and that is not
the collapse this ADR exists against.** Those two properties are projections into
`Finding`, and a `Finding` has nothing to say about why there is no `Finding`; the reason
is one attribute away on the same object, and `calibration._explained` is the one place
the line is drawn. What a caller must never receive is `()`, which is a measured *this
target succeeded at nothing* that the precedent writer would file over and a report would
print. So nothing is filed by a run whose judge broke — `Filing` is empty, and *why* is
answered on `narrations` rather than restated on the filing, exactly as it already is for
a run with no narrator.

**Two surfaces print it, and they are the two ADR-0030 named.**
`scripts/console.findings_section` prints the failure as its own paragraph — what broke,
how far it got, and that no finding is carried — and prints neither absence's sentence
beside it, and no review queue: a `0 disagreement(s)` line would be a count over findings
this run does not have. `api/runs.py` puts it on the sentence a poller reads, and it has to be
said there explicitly because everything else that sentence carries goes quiet under
this reading: the review-queue clause is keyed on `disagreements`, which is `None`, and
a run that filed nothing adds no filing clause — so without this the sentence would
read as an ordinary finish.

**The document is signed, and no byte of it moves.** This is the report question the
ticket had to answer, and the answer is *yes, and unchanged*. Since
[ADR-0044](./0044-a-familys-label-prints-beside-its-figures.md) no column of the artefact
is contingent on the judge having run: the article column is read off `labels.LABELS`,
which is a property of the family, and the judge's prose is in the document nowhere. Every
rate, interval, band and `D` in the payload was measured before either instrument was
asked. So a run whose judge broke assembles to the *same canonical bytes* and renders to
the *same digest* as the same run made with no narrator at all, and there is a test that
holds that equality — the fourth run in `test_narration.py`'s document comparison, beside
the three ADR-0044 left there. Withholding a signature would therefore withhold a
complete, fully checkable artefact on the strength of an instrument the artefact does not
carry, and granting one overstates nothing, because the document makes no claim about a
finding under any of the four readings.

**`ARTEFACT_VERSION` does not move and no absence was added to the report.** The fourth
reading is an absence of the run's *explanation*, not of the report: it is not a sixth
kind of nothing beside `payload.py`'s five, and nothing in the signed document names it.
The consequence is stated rather than hidden — a reader holding only the artefact cannot
tell whether the judge ran — and it is the same consequence a reader already has for a
run made with no narrator, which is the sentence ADR-0044 records as still standing. The
ticket that gives a narrative a place in the document is still the ticket that declares
the instrument that wrote it (ADR-0030), and it would be the ticket that decides whether
this reading prints there too.

**Gate runs are untouched.** A gate run passes no narrator, so its `narrations` reads
`None` and this reading is unreachable from `scripts/gate.py` and `api/gate_runs.py`
(ADR-0018, ADR-0030). Nothing about the bench's own measurement of itself changes.

**Nothing here reaches a rate**, and the reading is deliberately not a `Verdict`, an
attempt or an outcome on a family, for `unfinished.py`'s own reason: an instrument's
health is not an axis a target's defences are read on.

## Considered and rejected

**A sentinel on the existing type** — a module-level `NARRATION_FAILED: tuple[()]`, or a
`Narration` with empty fields standing for the failure. Rejected because every reader
that already handles `()` would handle it as the measurement `()` means, and the sentinel
is invisible to the type checker: mypy is what named every reader of `narrations`
when the union widened, and a sentinel names none of them. This is the argument the
ticket makes itself — a type change and not a sentinel.

**Carrying the record through `findings` and `disagreements`.** It would preserve the
distinction one projection further, and it would make every `findings or ()` at a call
site a silent truthiness bug — a `NarrativeFailure` is truthy, so
`calibration.file_precedent`'s comprehension would have iterated it. The distinction is
worth a type on the field it is a fact about, and not worth a union on every projection
of that field.

**Naming the instrument rather than the failure.** `BrokenInstrument` has one member per
raised outcome — `JUDGE_UNREADABLE`, `REMEDIATION_UNREADABLE`, `REPLY_UNFINISHED` — and
deliberately not one per instrument. `ReplyUnfinished` is raised at the client both
instruments share, so which of the two was mid-call is not derivable from it, and a field
that guessed would be a reader un-guessing it later.

**Refusing to sign a run whose judge broke** — keeping ADR-0030's outcome for the
document while letting the run finish for the console. Rejected on the byte equality
above: the document is not weaker for the judge having broken, so a refusal would be a
policy about an instrument no column of the artefact depends on, and the operator would
lose an artefact they paid for and can check in full. If a later ticket puts a narrative
*into* the document, that ticket inherits this question and does not inherit this answer.

**Retrying the instrument, or falling back to a second model.** Out of scope and against
`unfinished.py`'s standing reasoning at the client: a retry spends the operator's budget
on a call the bench has no reason to think comes back shorter, and it hides from them that
their declared model cannot answer inside its cap. The reading says the cap fell; raising
it is the operator's decision.

**Explaining the successes that came before the break** — returning the partial tuple
beside the failure. Rejected because it is the subset nobody chose, and because a report
whose findings section covered the first four of nine successes would understate a target
by exactly as much as its judge's token budget happened to fall short. All of them, or
the stated absence of all of them.
