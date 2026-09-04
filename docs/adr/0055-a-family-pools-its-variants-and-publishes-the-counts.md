---
status: accepted
---

# A family pools its variants, publishes the counts that make it up, and is comparable only at equal library version and equal selection

Four tickets of #71 added a dimension to the library and each deliberately left the run arithmetic alone, naming #76 as its owner. This is that ticket. What it decides is what one **rate per family** means once a family can hold more than one **variant**, what the artefact has to carry so the figure can be taken apart again, and what a reader comparing two reports is owed. The gate's thresholds, the band's cut points and `attempts_per_case` are untouched, and the reasons are stated in §5.

## 1. Pooling over the variants of one family is legitimate; pooling across families is not, and nothing here does it

A family's rate is **successes over attempts**. Every variant of a family attacks the same failure against the same criterion — `data-leakage-001` and `data-leakage-001-base64` are two ways of asking one question, and the success condition that decides them is the same condition on the same record's terms. So an attempt that succeeded through a base64 wrapper and one that succeeded through a four-rung ladder are both attempts that succeeded, and adding them adds no second quantity.

The **mean of the per-variant rates** is the alternative, and it is the wrong answer that looks right. It is a second quantity averaged in: it weights a variant by nothing but its existence, so a variant run at three attempts would count as much as one run at thirty, and at equal denominators it coincides with the pooled figure often enough to look correct in a test that only ever uses equal ones. `VariantBreakdown.pooled` is therefore the one place the arithmetic happens — `TargetRun._rates` **derives** each family's rate from that family's breakdown rather than counting it in a second walk over the same attempts, so *the rate is these counts pooled* is true by construction and not by assertion — and `backend/tests/test_pooled_rate.py` drives the mean red on unequal denominators. The `accounts_for` invariants of §3 still guard the two types that carry both, because a caller can construct either without going through a run.

**What is not touched is the prohibition one level up.** ADR-0005 refuses a composite across families and `payload.py` carries the structural half of that claim — *drop a family from the result and every other byte of the document is unchanged*. Nothing here reaches across two families: `TargetRun.variant_counts` is keyed on `Family` exactly as `rates` is, a breakdown sits *below* a rate, and there is no container in the codebase holding two families' variants together. Nor is anything pooled across **targets**: the three reference agents are three subjects, so `FamilyVariants` holds three breakdowns and has no method that reaches across them.

## 2. What pooling costs is published rather than hidden

A family holding one plain case and five encodings reports a rate that is mostly about encodings. That is a real cost and it is not avoidable by choosing a different statistic — it is a property of what the library holds.

So the decision is to **publish it**. The signed artefact carries `successes` and `attempts` **per variant** inside the family entry, so a recipient recomputes the plain rate, the encoded rate or any subset they like. This is the idiom the payload already keeps — *every measured figure is written with the counts it came from* — applied one level deeper, and it is what makes the pooled figure a summary of published evidence rather than an average nobody can audit.

Three things the breakdown deliberately does **not** carry:

- **No rate and no interval per variant.** A Wilson interval invites a band, and a band is a summary of a family against the two reference anchors that the gate decided nothing about a slice on (ADR-0014, ADR-0018). The counts are the evidence; the arithmetic over them is the recipient's.
- **No transform that was never sent.** A transform absent from a family is absent from its breakdown, not present at zero — the same refusal a family with no attempts makes by having no rate at all. `VariantCounts` raises on zero attempts.
- **No adaptive figure, and no field one could arrive in.** The keys are `Transform` members; an `AdaptiveEpisode` has no transform and is not an `Attempt` ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)). #77 adds the adaptive **discovery count** to the family *view*, as its own field of its own type, and the two are never summands of one number. That prohibition is carried by the types here and not by a caption.

## 3. The transform travels on the attempt, and the counts add up or the document is refused

**`Attempt.transform` is required and not defaulted.** It is read off the case record at the moment the attempt is made, for the reason `family` and `verdict_class` are: an attempt joined back to the library afterwards is an attempt that can be joined to the wrong record. Here the cost of getting it wrong is peculiarly invisible — the pooled rate would be unchanged and only the breakdown wrong — so a default of `PLAIN` would silently attribute a variant's successes to the payload it is a variant of. This is ADR-0051's argument for `Case.transform` being required-not-defaulted, one hop downstream.

**The counts adding up is an invariant of the types and a check in the verifier, in both places on purpose.** `FamilyEntry` and `FamilyRates` refuse a breakdown that does not account for the rate beside it, so the bench cannot *produce* an artefact whose figures do not add up. `verification._variants` re-derives the pooled denominator from the counts a document carries, so a recipient can detect one that was **edited after signing** — the rate would still follow from `successes`/`attempts`, and no other check on the page would notice. ADR-0027 has the verifier *read the denominator and assert the rest of the bar*; the denominator it reads is now the sum of the published per-variant counts rather than the attempts per case times the cases a library held.

A verifier reads a document it did not make, so the failure mode is a **disagreement and never a crash**: an entry with no breakdown at all is reported in words, on the terms `_entry` already states for counts that are not a rate.

## 4. Two runs at different selections are not comparable, and the artefact says so where a reader compares them

This is the sentence the ticket asked for out loud. A run that sent fewer constructions measured a different denominator over a different mix, and after #79 an operator can produce exactly that pair with two clicks. Neither figure is the other's baseline: a family whose rate moved from 0.20 to 0.45 between two runs may have gained an encoding rather than lost a defence.

The artefact already carries `LibraryVersion`, and after #79 it carries the selection — so the honest form of the sentence is **comparable only at equal library version and equal selection**, and it is printed rather than left to be inferred from a hash. `payload.VARIANTS_STATED` is that wording, in one place for the reason `rule.NOT_A_GATE_RESULT` is in one place: a second copy would only have to disagree once for a document to claim comparability its own verification denies. It travels in the measured section of the payload and in the rendered document, under the per-family figures, which is where a reader holding two reports actually is.

The rendered document also prints the mix beneath every family's rate — including a family holding **one** construction, where the line reads *plain, and nothing else*. The signed document is the surface that travels, so it may not be the one that says less than the payload it is a view of, and *this run sent only the plain payload* is exactly the fact the comparability sentence above makes load-bearing.

## 5. What did not move, and why each one is deliberate

**`attempts_per_case` stays at 10.** `rule.py` fixes it *so that the retirement rule can operate, not merely so the gate can pass*, and retirement is per **case**. A variant is a case with its own admission and its own decay series (ADR-0051), so each one still needs its ten. Nothing here multiplies by anything.

**`n` per family is read off the library and never off a literal.** #66 had already removed `attempts_per_family()` and every expression that multiplied by three; what this ticket adds is the definition that fills the gap — a family's `n` is its **live** case count times `attempts_per_case`, where the live count includes every admitted variant and excludes the retired (`CaseStatus.RETIRED`). It is still *printed* off the attempts that ran, so the figure a document shows is the figure its rates were divided by.

**`NOT_A_GATE_RESULT` and `DECLARED_BAND_CUTS` are untouched.** The first defends against `n` going *down*, and the direction here is upward, which is what makes the growth safe — the argument is #66's and is not re-derived. The second is the reference agents' *constructed* failure rates and is not a function of `n` at all.

**The gate prints the mix only where there is a mix.** A line reading *plain 3/30* beside a rate already printed as `(3/30)` is the same counts twice, and the interesting fact about a one-variant family is the `n` above it. So `gate.stated_variants` prints one line per agent when any agent's breakdown holds more than one entry, and nothing otherwise. The target *report* prints it either way, because that document travels to somebody who has no other way to learn what was sent.

## 6. What is measured today, and what is only held by a test

Said plainly, because the distinction matters for what this ADR licenses. **No variant is admitted into the library.** Admission needs a person at a tty (ADR-0052 §5) and no agent has faked one, so every one of the eighteen records is `PLAIN` and every breakdown a real run produces today holds exactly **one** entry, whose counts are the family's own. The pooled rate is the plain rate, and `n = 30` per family per agent is still what a gate run reads.

The multi-variant arithmetic — the pooling, the per-variant counts in the artefact, the verifier's refusal, the mix in both documents — is **held by tests over constructed libraries** and by the type invariants, and by nothing that has run against a model. That is the point of building it before the variants arrive rather than after: the first admitted variant must not be the thing that discovers whether the denominator was right.

## Considered and rejected

**A rate per variant, with no family figure.** Six families times seven constructions is forty-two figures, each on ten attempts, and a reader wanting to know whether the target leaks data would have to combine them — which is the composite ADR-0005 refuses, rebuilt by the recipient with no rule for how. The family stays the unit a rate is reported on, and the variant is how it is taken apart.

**The mean of the per-variant rates.** §1. It weights a variant by its existence rather than by its evidence, and it looks right at equal denominators.

**A breakdown keyed by case id rather than by transform.** More precise, and the wrong grain: what a reader needs is *how much of this figure is encodings*, and three plain cases of one family are one plain reading and not three. The case ids are pointers into the evidence and appear where a control was defeated; the breakdown is about constructions.

**Carrying the breakdown on `Rate`.** It would flow everywhere for free, including to the elective tier and to rates for which no variant reading exists, and it would have to be optional to do so — which is a field that is sometimes there, checked nowhere. The breakdown sits on the two types that carry a **family's pooled** rate, and it is required on both.
