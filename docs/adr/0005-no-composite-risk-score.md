---
status: accepted
---

# No composite risk score

A single figure was planned — weighted family failures minus points per absent declared control, with the formula printed beside it. Nothing in the assignment required it. Four things were wrong with it, and the second is a category error:

1. The family weights were never written down — a third undefined number after the two [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) pinned. "Formula printed" is not a formula.
2. **It added measured behaviour to untested self-report** — the exact default this project claims to fire. The scan reads what the target *declares*, and the plan's own limits admit a declared control can still be broken. It was also gameable in the worst direction: a target raised its score by **declaring more controls**, with no test that any existed. An incentive to over-declare, built into the headline number of an anti-over-declaration tool.
3. It discarded what [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) and [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) paid for: the Wilson interval collapses to a point, and a κ-0.65 judged family gets summed with a canary-token deterministic one as if they were the same kind of fact.
4. **It is the badge decision D3 forbids.** Handed to a procurement analyst comparing three vendors, a 0–100 number gets ranked; the printed limit that it "compares one agent against itself over time" is read by its author and nobody else. After [ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md) made procurement the audience, the scalar became the artefact most likely to be misused.

**Decision.** No scalar. The result is structured:

- **Per family:** failure rate, Wilson 90% interval, verdict class (deterministic or judged), κ where judged, `D` from the last gate run, and the coverage note from [ADR-0002](./0002-owasp-ids-as-secondary-labels.md).
- **Declared controls, in a separate section:** each marked `untested` / `held` / `defeated`. **No arithmetic between this section and the family results, ever.**
- **Coarse summary is a per-family band** — `holds` / `weak` / `fails`, defined by the interval's position against stated cut points. Legible, not addable, and awkward to rank vendors with. D3 is then honoured structurally rather than by disclaimer.

## The band is where a composite would be rebuilt

The report's per-family band is the one figure a reader could plausibly add up, so its type carries this decision rather than restating it: `Band` is a `StrEnum` and never an `IntEnum`, its members hold no numeric value, and there is no property anywhere that returns two report sections together or totals either. An ordinal band would put a six-family score one line of arithmetic away — this ADR's refusal, rebuilt by whoever reads the report next. The cut points behind the band are declared in [ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md), which also records why there are three bands and not four.

## Consequences

**"Declared and defeated"** — controls the target claims to have, which the bench broke — becomes the report's headline finding. It falls out of a join between the scanner and the attacker at no extra cost, no competitor can produce it, and it is the direct empirical proof of this project's own thesis.

Real signing moves into the Sprint 3 line: an Ed25519 keypair, a detached signature over a canonical JSON payload, a published public key, and a short `verify` script a recipient runs offline. A report that says "signed" and cannot be verified by its recipient ships the mock of the central claim rather than the claim.
