---
status: accepted
---

# The signature covers the whole document, and the document carries two claims rather than one

Phase 5 puts a real Ed25519 signature on a report for the first time, and a signature covers **bytes**. The report has an adaptive section. So the question that has been deferred since the first commit arrives with the key: does the signature cover that section?

Two sentences in this repository appear to answer it, and they do not agree. PLAN §3's architecture diagram labels the two layers `SCORED LAYER — this is what gets signed` and `ADAPTIVE LAYER — never signed`, in as many words. [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)'s title says the adaptive layer is never **scored**, and its decision is about rates, intervals, discrimination scores and the gate decision — it says nothing about bytes. The diagram is the stronger claim and it is the one that was never argued.

**Decision.**

1. **The signature covers the whole canonical payload, including the adaptive section.** One artefact, one signature, no unprotected region.
2. **The document carries two claims, and they are always printed together.** *Integrity*, for the whole artefact: this is the document that was produced and it has not been altered. *Re-derivability*, for the scored layer alone: every figure in it follows from the recorded attempts, the case records and the stated rule. The adaptive section is marked **recorded, not reproducible** in the payload and in the rendering.
3. **`verify.py` prints both, never one.** A verifier that printed "signature valid" alone would let a reader infer the stronger claim from the weaker one, which is the whole failure this ADR is about.
4. **The rendered document is bound to the payload by `rendered_sha256` inside the signed payload**, and `key_id` names the signing key. A rendering that does not match its digest fails verification under its own named outcome.
5. **This does not widen ADR-0010 and may not be cited to.** No adaptive figure enters a rate, an interval, a discrimination score, a band or the gate decision. Signing a byte is not scoring a number, and the two are separate operations on separate objects.
6. **PLAN §3's diagram labels are correct about numbers and overstated about bytes.** They are reconciled here rather than by editing the caption, so that the overstatement stays legible in the history instead of being quietly corrected into agreement.

## Why: integrity and reproducibility are different claims, and conflating them fails in both directions

This is not a balance to strike. It is two distinct errors, and each of the two obvious answers commits one of them.

**Sign only the scored half, and a security report ships with an unprotected section.** A recipient cannot detect alteration of the adaptive section at all. That section is the one describing the routes an attacker found against *their* agent, in prose — so it is precisely the section with something worth removing. A vendor handing a report to a customer has a motive to delete an inconvenient route, and the artefact would give the customer no way to notice. Leaving the most sensitive prose in a security deliverable outside the signature, to honour a distinction about *numbers*, is a worse artefact for a strictly worse reason.

**Sign everything and print one claim, and the signature makes a promise the adaptive half cannot keep.** A valid signature over a document containing `A_break = +0.25` invites the reading that the figure is reproducible. It is not: the same declared configuration produced `+0.00` on 2026-08-18 and `+0.25` on 2026-08-19, landing on opposite rows of ADR-0011's reading table ([validation.md](../validation.md)). A recipient who re-ran the bench and got a different number would be right to think the document had lied to them.

The repository already knows the answer and has been printing it for two phases. `scripts/gate.py` ends every run with both statements side by side, and says why:

> the gate decision above is re-derivable from its recorded inputs — the attempts, the case records and the rule printed with it — and the adaptive layer of the same run is recorded rather than re-derivable. **Both statements are printed, because a run that claimed one of them without the other would be claiming the stochastic half was reproducible by omission** (ADR-0010).

This ADR is that discipline applied to the artefact that leaves the building. The gate document says it to a reader who has the repository; the report has to say it to a reader who does not.

## What D11 actually argues, since it looks like an objection

D11 says "an LLM verdict is not reproducible, and a signature over a non-reproducible number certifies only that I held it." Read as a prohibition on signing non-reproducible content, it would forbid this decision.

That is not what it argues. D11 is the justification for making the scored **verdicts** deterministic — it explains why `success_condition` is authoritative and why the judge cannot overturn a verdict. Its subject is what a signature *proves about a number*, and its conclusion is that a signature proves nothing about an irreproducible one. This ADR agrees completely, and that agreement is the reason claim 2 exists: the document states, in the artefact itself, that the signature proves only integrity for the adaptive section. D11 warns against a signature being *mistaken* for a reproducibility claim. Printing both claims is how the mistake is made impossible; leaving the bytes unsigned would not address the mistake at all, it would only reduce what the recipient can check.

## Considered options

- **Sign the scored payload only; the adaptive section travels unsigned.** The strictest reading of the diagram, and it produces the unprotected-section failure above. It also splits the trust properties of one document in a way no reader will hold in their head: "the first half of this file is verified" is not a thing people remember while reading the second half.
- **Two artefacts — a signed evidence file and an unsigned appendix.** Physically separates what the labels separate, which is its appeal. Rejected because it splits one run's record into two files that must be kept together to mean anything, and a recipient who keeps only the signed half loses the entire adaptive record — including the part that says the attacker found a route nobody had written a case for.
- **Sign the rendered Markdown instead of the JSON.** The signature would then cover exactly what the human reads, which is attractive. Rejected twice over: it makes byte-stable rendering a permanent obligation, so any future change to the renderer invalidates every signature ever issued; and it leaves re-derivation to prose parsing, which means `verify.py` could check the transport and never the arithmetic.
- **Sign everything and print one claim.** The omission failure above, and the one `gate.py` already refuses to commit.
- **Sign everything and mark the adaptive section as *unverified*.** Wrong word for the state. The section *is* verified — for integrity. What it is not is reproducible. Using one word for both is how the two claims got conflated in the first place.

## Consequences

- The signed payload gains `rendered_sha256` and `key_id` as fields, and both are inside the signature rather than beside it.
- `scripts/verify.py` performs three checks — signature, binding, arithmetic re-derived and compared — and prints two claims. Each failure has its own named outcome, so a recipient learns *which* property failed rather than that something did.
- **A third evidentiary class would have to extend the claim list, not pick the nearer of two.** If a future section is neither re-derivable from recorded inputs nor merely recorded — a figure from an external service, say — the honest move is a third statement, and the temptation will be to file it under whichever existing claim is less awkward.
- PLAN §3 gains a pointer to this ADR beneath the diagram. The labels stay as written.
- ADR-0010 is untouched. The layer separation is still carried by the type system: `scorer.py` imports nothing from `backend/bench/adaptive/`, an `AdaptiveEpisode` still cannot become an `Attempt`, and the import-level tests that enforce both still fail if either changes.

Cross-references: [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the layer separation this does not widen), [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (the reading table whose rows moved between two certified runs), [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (D11's argument, and why the scored verdicts are reproducible at all), [ADR-0008](./0008-repo-disclosure-posture.md) (why the adaptive section carries prose and never payload text).
