---
status: accepted
---

# A signed document may carry a remediation, at the price of a disclosure answer and a fourth declared model

The bench has written a reason and a fix for every explained failure since [ADR-0030](./0030-the-judge-runs-over-the-scored-layers-successes.md), and neither has ever reached a reader. They end their lives on `calibration.TargetRun.narrations`: computed, paid for, covered by no signature because they are in no document. The most embarrassing half of #109 is that the bench already writes the fix and then discards it.

What stood in the way was not an oversight. It was a test — `test_payload.py`'s *no narrative or remediation reaches the document or its view* — which forbade the judge's prose in the signed artefact **by import** over every serialiser, and which named, in its own failure message, the two things that had to be paid to change that:

> a narrative here would need a disclosure answer under ADR-0008 and a fourth declared model to name the instrument that wrote it

Those are the two decisions ADR-0030 costed and deliberately left. This ADR spends exactly those two and no third.

## 1. The signed payload, and not a side-channel

**Decision.** The findings go in `payload.document`, inside the signature, and are rendered in the document a human reads.

The cheap alternative was live and is named here so that nobody proposes it as a first step: a findings endpoint outside the payload, served beside the report. It pays neither cost — no disclosure question, because nothing signed carries the prose; no declared model, because no artefact names the instrument. And it makes the fix **the one part of the report a recipient cannot check**, on a page whose entire premise is that a recipient can check it ([ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md), [ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md)). A vendor handing a customer a report would be handing them a checkable set of rates and an uncheckable set of remediations — which is the shape of every self-graded claim this project exists to displace.

ADR-0017 already reasoned about exactly this material one section over. The adaptive section is *the region with something worth deleting*, and its answer was to sign everything and print two claims rather than to leave a region unprotected. A findings section is the same shape: it is the part of the report a vendor most wants to trim, and it is the part a customer most needs to know arrived whole.

**A rendering change is a payload change first.** `rendering/__init__.py` states that `render` reads `payload.document` and never the result, so nothing can appear in the document that a recipient cannot find in the payload they verified. There was never a version of this that was only a renderer.

## 2. The disclosure answer: a remediation sentence quotes nothing of the exchange, and the record enforces it

[ADR-0008](./0008-repo-disclosure-posture.md), as amended, draws its line at **transferability**: a payload ships committed when the prose description conveys the attack as fully as the text does, and is withheld when *its wording is the working part* — a phrasing that transfers to a target outside this repository. The judge and the remediation tool are both shown the payload and the reply. So the question this ADR has to answer is not whether prose may travel, it is **how much of the exchange a sentence about it may quote**.

**Decision, in three parts.**

**a. What travels.** Per failure: the case id, the family, the published identifier, the exposure, the attributed cause with its control and its transform ([ADR-0068](./0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md)), the judge's one sentence on what went wrong, the remediation tool's one sentence on what to change ([ADR-0069](./0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)), the case ids of the precedents that informed the fix, and whether the two instruments read the transcript the same way.

**b. What is withheld, and each item has its own reason.**

- **The payload text, the reply and the tool trace.** Absent from the artefact by construction and with nowhere to arrive — the property `payload.py` already had, unchanged.
- **Any reproduction of the payload inside the prose.** This is the new one. A model shown a payload can quote it, and a quotation is the wording travelling under an explanation's cover. Answered with a mechanism rather than a request: `assembler.ReportedFinding.of` checks each of the two sentences against the case record it describes, and replaces one that reproduces the payload with a statement that it was withheld. That is the same discipline as `JudgeBrief.about` — blinding happens on the harness side of the call, never in a prompt asking a model not to look — and the record is the only place in the pipeline that holds both the prose and the case it is about. `payload.py` cannot admit prose the rule refused, because there is no route into the document that does not pass through that record.
- **The precedents' own prose.** `Remediation.informed_by` carries whole `Precedent` records, and a precedent's `failure` and `remediation` are **a different target's** finding and a different target's fix. A document about one target is not where a second operator's failure travels; `retrieve_precedent` already redacts identities for that reason, and a corpus of failure patterns identifies a target on its own ([ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md)). What ADR-0019's claim actually needs is whether this fix came from a corpus or from one transcript alone, and the **case ids** answer that. So the ids travel and the prose does not.
- **`Narrative.confidence`.** Withheld for a different reason and stated here so it is not read as an oversight: it is a number a model wrote about its own answer, and a number in a signed document is read as a measurement by everybody who did not write it. That is [ADR-0005](./0005-no-composite-risk-score.md)'s concern arriving through prose, and the honest substitute is already carried — the two instruments' *disagreement*, which is a fact about two instruments rather than one instrument's self-report.

**c. A withheld sentence does not withhold the finding.** The block keeps its case id, its family and its attributed cause, and says which of the two sentences was replaced. A finding dropped for its prose would take the three checkable facts with it, and `withheld` is a closed set so a reader can ask how much of a document was withheld without reading all of it — the idiom every other absence in this codebase follows.

**The floor is a measurement and lives with the value.** `PAYLOAD_QUOTE_FLOOR = 40` characters. A rule that fired on any shared phrase would withhold every honest sentence, because a reason and the payload it describes are both ordinary English; a rule that only caught a whole turn would be defeated by a model that trimmed the last clause. Both ends are measured against the committed library in `test_reported_findings.py`: no committed payload and no half of one survives the check, and no sentence written *about* a case trips it. The high end is pinned by a literal of its own, because a bound written as a multiple of the floor moves with the constant it exists to bound.

**What this does not do.** It does not touch transcripts, which are still never committed. It does not touch the adaptive layer, whose routes are still prose and never probe text. And it is not a claim that the prose is safe because a check passed: it is a claim that the one mechanical failure mode — the model reproducing what it was shown — is closed by a record rather than by a reviewer's care.

## 3. The section is 3b, beside the join it explains

**Decision.** Annex IV point 3 — *monitoring, functioning and control* — now holds two sections. **3a** is the declared-and-defeated join it always was: what the operator claimed, crossed with the verdicts, per **control**. **3b** is the same material read from the other end, per **failure**: what one break is read against, what went wrong, and what to change.

Point 5 was the live alternative and loses. It already holds two sections and both are statements about the **boundary** of the claim — what the bench does not test at all, and what one attacker found outside the recorded cases. A failure inside the recorded cases is not a statement about that boundary, and filing it there would put the explanation of a break three sections away from the claim it explains. Placing it at 3b also makes the section's evidentiary class legible by position: 3a is re-derivable, 3b is not, and they sit under one Annex IV point with two labels — which is the shape `Section.part` exists for and the honest alternative to one section carrying two labels.

**The label is `not reproducible`, and no third evidentiary class was invented.** A model wrote the prose, which is the class ADR-0017 already has a word for. ADR-0017's own consequence says a genuinely third class would have to *extend* the claim list rather than pick the nearer of two; this is not one, and the temptation to invent one for *prose that was checked* is named here so that it is refused rather than unnoticed.

**The section's own wording avoids the three words a gate answer uses.** There is no sentence anywhere in a target report in which the target passes or fails anything ([ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)), and a section about the target's breaks is where that discipline is easiest to lose. So the printed heading is *what went wrong*, not *why it failed*, even though the latter is ADR-0069's own vocabulary for the field. The vocabulary is unchanged; the wording of one heading in one document is not.

## 4. Four readings, four documents — and all four still signed

`narrations` reads four ways ([ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md)): nobody declared an instrument, the target succeeded at nothing, every failure explained, and the instruments ran and broke. The section states which one holds, as a **name off a closed set** and as a sentence — a consumer that told the four apart by matching prose would stop telling them apart the day the prose was reworded, and the report screen computes nothing the payload does not carry (#113).

**This changes an answer ADR-0050 gave, on the condition ADR-0050 itself named.** That decision signed a run whose judge broke on the footing that *no byte of the document moved* between it and a run with no judge, and closed with: "If a later ticket puts a narrative *into* the document, that ticket inherits this question and does not inherit this answer." This is that ticket. The bytes now differ, and they **must**: a document that read the same under all four would make *the instruments broke* indistinguishable from *nobody declared one*, which is precisely the collapse ADR-0050 spent two paragraphs preventing, arriving one layer along.

The signing answer is unchanged and re-argued rather than inherited. Every figure in each of the four documents was measured before either instrument was asked; a run whose judge broke loses no rate, no interval, no band, no `D` and no article. Withholding a signature would withhold a complete, fully checkable artefact over an instrument no figure in it depends on, and granting one overstates nothing, because the document now *says* what happened to the instrument instead of being silent about it. The broken reading also carries its own counts — how many successes had been explained, of how many — so an operator reconciling a token bill reads figures rather than parsing a sentence.

## 5. The fourth declared model

**Decision.** `DeclaredModels` gains `narrative`, required and with no default, naming the model the judge and the remediation tool ran on. It prints in the provenance block beside the other three.

ADR-0030 rejected a fourth declared model on exactly one ground, and named the condition that would reverse it:

> the signed payload has no narrative or remediation field, so a fourth declared input would be one no artefact names … The ticket that gives a narrative a place in the document is the ticket that declares the instrument that wrote it.

The condition is met. An unattributed sentence in a signed artefact is the one thing this project's provenance rules exist to prevent.

**One field for two instruments, and that is what the run has.** `completion.narrator_for` builds both clients from one configuration string, so a record naming two would name a setting nobody chose — the same refusal `DeclaredModels.__post_init__` already makes about a temperature the attacking model could not have been sent. The two `Completion` aliases stay declared apart, so the day a deployment points them at different models this field splits and nothing else moves. **That splitting is a decision left, not taken here**, and saying so is the point: it is not a third decision smuggled in beside the two this ADR is licensed to spend.

**Required rather than defaulted**, on `Provenance.selection`'s reasoning: a builder added later has to state its answer rather than inherit one. A default would read *the adjudicating model*, which is true of every entry point today and would be silently false the first time one of them moved — and the failure mode is a document attributing a sentence to an instrument that did not write it.

**It is not κ's subject and must not be read as one.** κ is measured on `adjudicating`, the instrument that decides the two judged families ([ADR-0013](./0013-adjudication-is-a-third-instrument.md)). This names the instrument that wrote prose, no figure is read off it, and it carries no reliability figure of its own — the narrative's evaluation is the gold-set run ([ADR-0009](./0009-deepeval-executes-the-goldset.md)), exactly as ADR-0030 said. A bench that declares no model gets no narrator, so its `narrative` field and its findings section state the same absence from the same string.

## 6. The import wall is inverted, not deleted

`THE_JUDGE_SIDE` stays, and the test it drives becomes an assertion about **which serialiser may name a finding** rather than that none may.

- **`payload.py` may**, and must: it is where a result becomes keys, so it is where the record turns into a document. The test fails if it names none.
- **The five rendering modules may not**, for a reason that is about the renderer and not about the judge: `render` reads `payload.document` and never the result, which is what makes the Markdown a *view* of the artefact rather than a second account of the run. A renderer holding a `ReportedFinding` could print a sentence a recipient cannot find in the payload they verified, and it would sit on the far side of the record that enforces the disclosure rule.
- **`payload.py` may name the record and not the instruments' own output.** A second wall says it reaches `assembler.ReportedFinding` and never a `Narration`, a `Narrative` or a `Remediation` — because the first has been checked against the case payload it describes and the other three have not. That is the one way §2's answer could be true of a type and false of a document.

The rendering module that builds the section is named `_explained.py` rather than `_findings.py`. The wall is a deliberately blunt substring check — the record travels under five names in four modules — and a renderer named for the record would have to be exempted from it. An exemption is how a blunt wall stops being one.

## 7. What does not move, and what does

- **`ARTEFACT_VERSION` does not move.** `findings` is an additive top-level key and `narrative` an additive provenance key; nothing is removed, renamed or re-typed, and a verifier reading the previous shape reads every field it read before, checks the same signature, re-derives the same arithmetic. That is the footing #43 set for the `elective` block, #47 for `claimed_in_part`, #45 for `edition`, #52 for `label`, #102 for the fourth reading and #86 for `teardown` — and ADR-0044 rejected moving it to 2 on the cost that every previously issued artefact would read as an older shape to a verifier that refuses one it does not know. Whether an additive key is ever a new document *shape* is still not decided here, and still belongs to whoever changes the shape rather than adds to it.
- **The golden rendering digest moves, and this is the largest move on its list.** A new section, a contents row, a reworded sentence naming which points hold two sections, and section 3 becoming 3a. `GOLDEN_ONE_FAMILY` is updated in the same diff as the change that moved it, with the reason, which is the discipline that constant exists for.
- **Nothing writes into a rate.** A finding is prose about one verdict: no rate, band, interval or `D` reads a word of it (D13, [ADR-0006](./0006-overrides-never-change-a-measured-rate.md)), and the prohibition is structural — `ReportedFinding` has no numeric field, and `test_attribution.py`'s import wall over every module that computes a figure is untouched.
- **No route for the adaptive layer.** An `AdaptiveEpisode` has no `Finding`, `attributed_cause` refuses one at runtime as well as by annotation, and nothing here widened a signature to accept both ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)).
- **No severity and no composite.** D3 and D12. There is no ordering of one block against another and no figure built out of the blocks at all.

## Considered and rejected

**An unsigned findings endpoint beside the report.** §1. Cheap, pays neither cost, and makes the fix the one uncheckable part of a checkable document.

**Delete the import test.** It was a decision with two named prices, not a stale assertion; deleting it would have spent the prices without arguing them and left the renderers unwalled at the same time.

**Refuse to publish prose that quotes the payload, and fail the run.** The symmetry with `Remediation.__post_init__` is tempting — it refuses a blank fix at its own door. Rejected on ADR-0050's reasoning one artefact along: an operator whose run is complete and paid for should not lose the whole artefact because one model quoted one payload, and a withheld sentence beside a kept case id is a fact a reader can act on, where a missing report is not.

**Ask the model not to quote, in the prompt.** The prompts do say what shape the answer takes, and a prompt is a request. Blinding lives at `JudgeBrief.about` rather than in the judge's system prompt for exactly this reason, and the disclosure rule is held to the same standard.

**Carry the precedents' prose so a reader can see what informed the fix.** Rejected in §2b: it puts a different operator's failure in this operator's document to make a point the case ids already make.

**Put the section under Annex IV point 5.** §3. Point 5's two sections are about the boundary of the claim; a failure inside the recorded cases is not.

**Split `narrative` into `judging` and `remediating` now.** §5. Two fields would describe a configuration this bench does not offer, and the field that names a setting nobody chose is the defect `temperature_stated` exists to avoid.

Cross-references: [ADR-0008](./0008-repo-disclosure-posture.md) (the posture this answers a new question under), [ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md) (one signature, two claims, and the material now added to both), [ADR-0030](./0030-the-judge-runs-over-the-scored-layers-successes.md) (the two decisions this spends), [ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md) (the four readings, and the question this inherits without its answer), [ADR-0068](./0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md) and [ADR-0069](./0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md) (the two records this section prints), [ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md) (what `informed_by` is for).
