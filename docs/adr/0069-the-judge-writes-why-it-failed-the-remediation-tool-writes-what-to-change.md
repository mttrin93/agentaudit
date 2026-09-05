---
status: accepted
---

# The judge writes why it failed; the remediation tool writes what to change

Two fixes were written for every explained failure, by two instruments, and nothing reconciled them. The judge was asked for one — `JUDGE_SYSTEM_PROMPT` ended `remediation: one sentence on the control that would have stopped it`, it landed on `Narrative.remediation`, and a narrative with a blank in it raised. `suggest_remediation` was asked for one too, and it is the one instrument [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) allows to hold the precedent store. `narration.narrate` called both, in that order, and returned them side by side on one `Narration`. Which one an engineer was supposed to apply was written down nowhere.

This is #111, the second decision of #109. Nothing here is printed: the signed document has a price to pay first (#112), and the report screen waits on that answer (#113). What changes is *what is written*, and by whom.

## 1. The two were never two opinions of equal standing

The judge is blinded and holds no store, by construction. The remediation tool sees the finding unblinded and holds the precedent. So the judge's fix was **always the unprecedented one** — the fix that would have been written with no corpus at all, which is the thing [ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md) exists to say is worth less. Two fixes printed side by side, with the blinded one first, would let a reader defeat the store's whole claim about itself by the **layout of a page** rather than by an argument. The moment either is printed, that stops being a curiosity, and #109's third and fourth sub-issues print one.

Keeping both and labelling them was the alternative, and it is rejected in §3.

## 2. The judge keeps the reason and writes no fix

`Narrative` loses `remediation`. `JUDGE_SYSTEM_PROMPT` asks for four labelled lines instead of five and says, in as many words, that it is not to write the control and that a separate tool does. `Narrative.__post_init__` refuses a narrative with no *reason*, and no longer speaks for the fix.

The field is **removed rather than left unasked**, and the prompt line is removed with it, because either half alone is a hole: a field with nothing asking for it gets filled by a model that volunteers one, and a prompt line with no field spends tokens on an answer nothing reads. Both are asserted together in `test_judge.py`.

So the two instruments now answer two different questions, and each answers exactly one:

| Instrument | Answers | Sees |
|---|---|---|
| `assess_finding` | **why it failed** — `Narrative.reason`, and the reading, exposure and confidence around it | one blinded brief, no store, no prior finding |
| `suggest_remediation` | **what to change** — `Remediation.fix`, with `informed_by` beside it | the finding unblinded, and the precedent filed against its family |

That is the title of this ADR, and it is option A of the two #111 named, not option B. **B would have kept a field whose only distinguishing property was that it was written with less information.** The title reads like B and the decision is A: under A the judge still writes *why it failed* and the tool still writes *what to change*, and what goes is the second answer to the second question, not the division of labour.

## 3. What A costs, and why the cost was already paid

`judge.py`'s refusal was that *a narrative with no reason or no remediation is a finding that is true and unactionable*. Half of that guarantee now depends on a **second instrument having run**. Three consequences, and each is stated where it lands:

- **`Narrator` holding both instruments becomes load-bearing** rather than an ergonomic choice. It already held both, for the reason its docstring gives — a caller able to supply the judge without the remediation tool could produce findings with a reason and no fix — and that sentence is now the constraint rather than the argument for a convenience.
- **A broken remediation tool is the failure of the finding.** It already was: [ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md) ends the narrative pass on `RemediationFailed` and reports `BrokenInstrument.REMEDIATION_UNREADABLE`, carrying no partial narrative. This decision does not add a reading, does not remove one, and does not rename one: the three members stay named per raised outcome, and `REMEDIATION_UNREADABLE`'s own docstring — *"the finding it belongs to would be true and unactionable"* — is now literally rather than nearly true. That #102 blocked #109 is exactly this: the fourth reading had to exist before the guarantee could be allowed to depend on the second instrument.
- **`Remediation.__post_init__` refuses a fix-less finding**, in the same words `judge.py` used, so nothing moved: one of two duplicate guarantees went. It is not the only door, because §4 opens a second one — `Precedent.of` takes the fix as a string, and a string parameter is a door a `Remediation` used to be, so it makes the same refusal itself. A blank filed there renders as `fix written then: ` in front of the next run's model, which is the *nothing to report* PLAN §10 forbids; it raises a `ValueError` rather than a `RemediationFailed` because importing that name would close the cycle §4 describes, and because a blank reaching it is a caller in the bench and not a model that answered badly.

## 4. The precedent store recorded the wrong half, and that is fixed here

`Precedent.of` read `finding.narrative.remediation`. So the corpus ADR-0019 claims value for was being filled with the **judge's** fixes — written from a single transcript, by the instrument that may hold no store — while the fix its own reader wrote was computed and thrown away. A store that fed itself the unprecedented half is a store whose retrieved advice cannot be better than advice with no store at all, which is ADR-0019's claim inverted.

`Precedent.of(finding, fix)` therefore takes the fix as a second argument, and `DurablePrecedents.record(finding, fix)` with it. **Not a `Remediation`**: `remediation.py` imports `precedent.py`, so a `Precedent` that imported a `Remediation` would close that cycle. The parameter is a string for the same reason `Precedent` carries prose and not payload text.

**`filing.file_precedent` therefore takes `Narration`s, not `Finding`s.** A precedent is a failure *and* the fix written for it, and since this decision no single instrument's output is one — the pair is, and `Narration` is the only record holding both. `_one_per_case` keeps its identity `(target_name, case_id)`, read off the finding inside the narration, so no caller can widen or narrow the rule by how it batches. `Filing.judged` still carries findings, because a withheld record is one nothing was filed for.

`remediation.brief_for` loses its `what the reviewer suggested` line for the same reason, and the reason it keeps is labelled *why it failed, as the judge read it*. A tool shown one fix and asked for another is being asked to arbitrate between two instruments, which is what this ADR ends. The only fixes in front of that model are precedent.

## 5. What did not change

**ADR-0004's blinding survives untouched, in both directions.** The judge gains nothing: it still takes a brief and a model call, still holds no store handle, and `test_precedent.py` still walks its *transitive* imports and the adjudicator's to say that neither can reach anything named for precedent or remediation. The fix now travels *away* from the judge rather than towards it, so the asymmetry is wider than it was, not narrower. And the remediation tool does not gain the judge's transcript-only role: it never held a brief, it holds a `Finding`, and it is not blinded because it does not need to be.

**Nothing here writes into a rate.** A reason and a fix are prose about a verdict. `TargetRun.rates` divides over `attempts`; filing over narrations instead of findings changes what is written into the store and touches no numerator, denominator, band, interval or `D` (D13, [ADR-0006](./0006-overrides-never-change-a-measured-rate.md), [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)). The existing test that runs a stocked store against an empty one and compares every rate holds it.

**No route for the adaptive layer.** An `AdaptiveEpisode` has no `Finding` and no `Narration`, and nothing here widens a signature to accept both.

**No severity scale and no composite** (D3, D12). Two prose fields on two records, and no number joins them.

**And nothing here is printed.** `test_payload.py`'s import test — *no narrative or remediation reaches the document or its view* — is untouched and unweakened. The two costs it names, a disclosure answer under [ADR-0008](./0008-repo-disclosure-posture.md) and a fourth declared model, are #112's to pay, and this ticket stops at that seam exactly as #110 did.
