---
status: accepted
---

# An attributed cause is derived from the case record and the scan, so it is not an instrument

The bench can say how often a target failed and which declared control it broke, and it cannot say **why this particular failure happened** to anybody outside the process that produced it. #109 is the group that fixes that; this is its first decision, and it is the one that fixes what an *attributed cause* is before anything prints one. Nothing here is printed — the signed document has a price to pay first (#112) and the report screen waits on that answer (#113).

## 1. It is derived, and that is the whole argument for deriving it

The tempting shape is a model that reads the transcript and says what went wrong. It would be a **fourth instrument**, sitting upstream of something a reader relies on, and #64's precedent then applies without amendment: no unvalidated instrument sits upstream of a reader, so its agreement with a human would have to be measured — a gold set, a κ figure, a declared floor — before it printed a single sentence. That is the bar [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) sets for the judge and [ADR-0013](./0013-adjudication-is-a-third-instrument.md) sets for the adjudicator, and it is not a bar this material can clear cheaply, because there is no ground truth for *what gave way* inside somebody else's agent.

Everything the reading needs is already on two records that a reader holds:

- **the case record** (`Case`) — its `family`, its `id`, and since [ADR-0051](./0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md) its `transform`;
- **the scan** (`Scan`) — what the operator declared at registration, crossed with `family_claimed_by`, which is the closed control → family mapping the declared-and-defeated join already rests on.

So `attributed_cause(attempt, case, scanned)` is a function of three records and of no instrument. There is no parameter through which a model could supply the reading — the argument `Finding.of` makes about a verdict, restated one type over — and the only way to make this judged is to change the signature, which is the signal [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) asks an implementer to stop at. It is **re-derivable** in the same sense a deterministic verdict is: a recipient holding the case record and the registration recomputes it without running anything and without trusting us. That is why it needs no κ, and it is why nothing about it is measured.

**The attempt is the failure, not the derivation.** The cause is derived from the two records above; the attempt is what says there is a failure here to attribute one to, and it arrives in `JudgeBrief.about`'s argument order with its two refusals for the same reasons that record has them. A record joined to the wrong case would name a transform the attempt never sent; a record built over a **resisted** attempt would print *the operator declared this control and the bench broke it* over an attempt that broke nothing, which is a false sentence the purest possible signature would have made unreachable only by convention. Its verdict is **read and never computed**, so this stays a join over verdicts and never over rates — the boundary [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) draws and the one ADR-0005's rejected score crossed.

## 2. The new information is the declaration state, not the name of the control

`family_claimed_by` is **1:1** over the four members of `DeclaredControl` — input check → indirect injection, scope limit → scope creep, output filter → data leakage, stop control → halt defeat — and the match has no fifth arm on purpose. So *which control* is very nearly a relabel of the family, and a record that carried only that would be a new type saying what the family name already said.

What this record buys is the **declaration state**. A control the operator claimed and the bench broke is a different sentence to an engineer, and a very different sentence to a procurement reader, than a family nobody ever claimed to defend. And it buys a **place to put which technique got in**: `Case.transform` (§4).

Two things the record therefore is not, and both were live options:

- **Not a severity, and not a composite.** D3 and D12, and promptfoo's severity scale is the one already rejected on the record. `Attribution` carries no number and there is no field a figure could arrive in.
- **The control is still carried, and the ticket's own words are why that needs saying.** #110 argued that naming the control is not what this buys, and it is on the record precisely so that the reading can be checked: the third member below is *defined* by there being no claiming control, so a record that could not name one would leave the distinction unfalsifiable, and `stated()` would have no defence to name in the two sentences that are about one. It is a field the record can also re-derive from its own family, which is the shape `ScannedControl` already has.
- **Not a second copy of `ScannedControl.broken_by`.** That field points control → the case ids that broke it, per target; it is a fact about the *scan* and a reader holding one failure cannot get from it to the control it belongs to without inverting a table by hand. `control_claiming` is that inversion, **derived from `family_claimed_by`** rather than written out again, so a fifth control claims its family in both directions the moment the mapping gains an arm.

## 3. Three readings, and the third is not a spelling of the second

`AttributedCause` is closed at three members:

| Reading | When | What it says |
|---|---|---|
| `DECLARED_AND_DEFEATED` | a control claims this family and the operator declared it | the strongest reading: a claim the bench broke |
| `NOT_DECLARED` | a control claims this family and the operator declared none | the checklist holds a defence for this and nobody claimed it |
| `NO_CONTROL_CLAIMS_THIS_FAMILY` | no control claims this family at all | there is no declaration to read this failure against |

**The third must not be reachable as the second**, and that is the load-bearing half of the decision. Five of the nine families have no declared control — the two judged ones and the three elective ones — so a bench that read them as `NOT_DECLARED` would report an absence nobody could have declared. That is exactly the defect [ADR-0005](./0005-no-composite-risk-score.md) removed from the rejected score, where a target lost points for controls it did not claim, arriving a second time through a finding. `Attribution.__post_init__` refuses the three ways a caller could conflate them by hand: a third-reading record that names a control, a first- or second-reading record that names none, and a record filed under a control that does not claim its family.

`stated()` is on the record, in the pattern `NotMeasurable.stated()` and `ScannedControl.stated()` already set: the sentence a report prints is a property of the reading and not of the renderer, so the two surfaces #112 and #113 open cannot print two different claims about one attribution.

## 4. The technique dimension is `transform`, and it is required rather than optional

#110 was cut before #72 landed and asked for *a `technique` field, absent until #72 — typed as optional and printed as absent rather than omitted*. #72 landed first, so this ADR spends that provision rather than honouring its letter, and the difference is stated here rather than left to be noticed:

- the field is named **`transform`**, because that is the codebase's word for the dimension (ADR-0051) and `technique` is prose on `RetrievedFrom` meaning something else (ADR-0048 §4, ADR-0051 §2);
- it is **required and read off `Case.transform`**, not `Transform | None`. There is nothing for the optional to mean: every case record carries a transform, `PLAIN` is a member rather than a silence, and a nullable field here would be a third kind of nothing (`payload.py`) invented for a value that always exists.

Today every admitted record is `PLAIN` and no variant has been admitted (ADR-0052 §5), so the transform half of every sentence currently reads *sent as the record commits it*. The field earns its place the day a variant is admitted, and it is here first for the reason ADR-0055 §6 gives: the first admitted variant must not be the thing that discovers there was nowhere to report it.

## 5. Where it lives, what may not see it, and what it may not touch

**In `assembler.py`, not in `judge.py`.** It is derived from the scan, and `judge.py` holds no scan and must not gain one: a `JudgeBrief` carrying what the operator declared is the blinding channel of ADR-0004 reopened by a new route, and the κ figure that polices the judged families is what a leak there would contaminate. Asserted over the *transitive* imports of both instruments, in the pattern `test_precedent.py` sets — the judge and the adjudicator can reach neither `assembler` nor anything named for an attribution.

**Nothing here writes into a rate.** An attributed cause is prose about one verdict: no rate, band, interval or `D` may read it (D13, [ADR-0006](./0006-overrides-never-change-a-measured-rate.md)), and an override annotates one of those without moving it. Two tests hold it — an import-level wall over every module that computes a figure and the two that write one down, and the field list of `Attribution` itself, which admits no numeric type at all.

**No route for the adaptive layer.** An `AdaptiveEpisode` is not an `Attempt`, and the annotation is joined by an `isinstance` so the refusal is a runtime fact a test can drive rather than only a type check — `NotAScoredAttempt`'s argument, made locally rather than by importing it, because `assembler.py` reaching into `judge.py` is the edge §5 opens with. Nothing here widens a signature to accept both (ADR-0010).

**And it is not printed by this decision.** `Attribution` reaches no section of `TargetResult` and no key of the payload. `test_payload.py`'s import test — *no narrative or remediation reaches the document or its view* — is untouched and unweakened: the two costs it names, a disclosure answer under [ADR-0008](./0008-repo-disclosure-posture.md) and a fourth declared model, are #112's to pay, and this ticket stops at that seam.
