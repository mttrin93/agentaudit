---
status: accepted
---

# The report is about a target; the gate is about the bench, and no field connects them

Every run this repository has made is against its own three reference agents, which are **test equipment and never reach a user** (spec story 8). The gate is decided over them. Phase 5 produces the first artefact about a **target** — someone else's agent, registered, attested and attacked — and it is the first time two things that have never been in the same document need to be in one.

They are not the same kind of claim and they do not share a denominator. The **gate** asks whether a carefully defended agent and a deliberately careless one produce different results: its unit is the contrast between three agents of known construction, over six families, at `n = 30` per family per agent. A **target report** asks what one agent did: its unit is that target's attempts. A gate decision applied to a single agent is not a strict claim or a loose claim — it is not a claim at all, because there is no contrast to measure.

The reason this needs an ADR rather than a careful sentence in the renderer is the direction of the failure. `PASSED` printed beside a customer's agent name is what the buyer wants to see, what the vendor wants to send, and what a compliance officer will file. Nobody in that chain has a motive to object, which is exactly the condition under which a wrong field name survives review — and it would be the badge [D3](../../PLAN.md) forbids, reached by a field name rather than by a decision.

**Decision.**

1. **A target run produces per-family rates, Wilson intervals and bands, and no gate decision.** The payload has no field that could carry one.
2. **The prohibition is carried by the type, not by the renderer.** The target report type has no gate-decision field to populate, so a future contributor cannot add one at the call site — they would have to widen a type, which is the signal [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) established for exactly this class of mistake. `read_gate` is never called on a target run.
3. **The bench's own gate result appears in the provenance block as a citation**: outcome, date, library version with its digest, and the path of the run document. It is typed as **provenance**, alongside the attestation identity and the models used — not as a result, and not in the section carrying the target's numbers.
4. **The rendering uses different words for the two, deliberately.** The bench *passed its gate* on a date, at a library version. The target *has rates, intervals and bands* per family. Neither sentence is available for the other subject.
5. **No band, and no set of bands, is combined into anything.** A band summarises one family for one target ([ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md)); there is no code path that totals, averages or ranks them, per [ADR-0005](./0005-no-composite-risk-score.md) and D12.
6. **The reference agents are never named in a user's report.** They are the instrument's calibration equipment; naming them invites a comparison — "your agent scored between the weak and hardened reference" — which is a composite judgement wearing a comparison's clothes.

## Why the citation stays, when omitting it would be safer

The tidiest way to prevent the conflation is to leave the gate out of the report altogether. That is rejected, and the reason is the project's whole differentiator.

The mission is that a number from an unvalidated bench is exactly as trustworthy as the questionnaire it replaces. A report that shows rates without any evidence that the instrument producing them discriminates is that questionnaire with better typography. The reader's question — *why should I believe this instrument measures anything?* — is legitimate, and the answer exists: a stated, falsifiable rule that could have returned "this bench measures nothing", checked twice, published either way.

So the gate belongs in the report. What this ADR fixes is **where**, and the answer is the same place a reader finds the attestation, the model identifiers and the library digest: the provenance block, which is the part of a document that says *how this was made* rather than *what it found*. A reader who wants to know whether the ruler is trustworthy looks at the ruler's certification; they do not read it as a measurement of the thing they measured.

## The distinction is load-bearing in the arithmetic, not only in the prose

Worth stating plainly, because a reader may take this for a presentational preference.

`D`, the discrimination score, is **trivial minus hardened**. It cannot be computed for a target at all — there is one agent, so there is no difference to take. Monotonicity is `hardened ≤ weak ≤ trivial` across three agents; with one agent there is no ordering to check. The gate's two thresholds are counts over six families of *contrast*: four passing, five monotonic. Not one of the four quantities the gate is decided on has a definition when the subject is a single target.

So the separation is not that a gate decision about a target would be misleading. It is that **there is no arithmetic that would produce one**, and any field claiming to hold it would have to be filled by copying the bench's own result across — which is the precise move point 2 makes impossible.

## Considered options

- **Print the gate decision in the report, clearly labelled as being about the bench.** The intuitive answer, and the one this ADR exists to refuse. Labels are not load-bearing at the distance a document travels: what circulates is a screenshot of one section, a paste into a slide, a sentence in a procurement summary. A field whose correctness depends on an adjacent caption surviving those transformations is a field that will eventually be wrong, and it will be wrong in the flattering direction.
- **Compute a per-target decision under a target-appropriate rule.** Rejected on the arithmetic above: there is no contrast, so there is nothing the declared rule's four quantities could be computed from. Inventing a different rule for targets would mean declaring new thresholds at the moment a reader wants a verdict, which is the threshold-move [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) exists to prevent, arriving from a new direction.
- **Omit the bench's gate result entirely.** Addressed above: it removes the project's answer to its own central question.
- **Put the gate citation in the findings section but visually separated.** A weaker version of option one. Proximity is what gets misread, and visual separation is the first thing lost in any re-rendering.

## Consequences

- Two types, no field between them: the target report and the gate decision are separate records, and a test asserts that no gate decision appears anywhere in a target payload.
- The provenance block carries the gate citation, and a target report whose provenance cannot name a passed gate run says so rather than omitting the line — an uncited instrument is a fact about the report, not a blank.
- **A user's run can therefore never "fail".** It has rates and bands; the vocabulary of pass and fail belongs to the gate, and the report has no sentence in which a target fails anything. Deliberate, and it will feel like a missing feature to anyone who wants a verdict.
- **If a target report is ever to carry a summary judgement, that is a new decision with its own ADR**, and it starts from D12 and ADR-0005 forbidding it. This ADR does not leave that door ajar; it records that it is shut.
- The reference agents stay undocumented in user-facing output, and remain documented as test equipment in the repository (spec story 8).

Cross-references: [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the rule, its denominators and why they do not move), [ADR-0005](./0005-no-composite-risk-score.md) (no composite, which this protects one level up), [ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md) (what a band is and that it never enters the gate), [ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) (what the gate is decided over), [ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md) (no badge, and who the reader is).
