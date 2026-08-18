---
status: accepted
---

# Adaptive-discovered cases face a cross-model admission bar

The promotion loop in [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) has a defect that the admission gate cannot see. The attacker discovers a route **by exploiting the three reference agents**. The admission gate then decides whether to admit that route **by testing whether it separates the three reference agents**. Discovery and admission run on the same set, and a case fitted to a set and validated on that same set passes more often than a case written blind.

The specific failure is sharper than general overfitting. A route the attacker finds against the **trivial** agent, which the hardened agent happens to resist, scores `D ≈ 1` and is admitted automatically. Trivial breaks on nearly everything, so this is close to free. Over successive gate runs the library fills with cases that separate *these three agents* while the bench gets no better against real targets — and `D` drifts **upward**, so the instrument reports improving health while its coverage of the world degrades. Nothing already in the design catches this: [ADR-0003](./0003-gate-decision-rule-and-sample-size.md)'s bar is the defence against *weak* cases, and it is defenceless against *overfitted* ones, because an overfitted case clears it by construction.

The decisive argument is what phase 8b is for. 8b answers the strongest objection anyone can raise against this project — does the bench read the agent's defences, or the model's default refusals? If the library grows by a mechanism that may itself be model-specific, **8b stops being interpretable**: a collapse on a model swap could not be separated into "the bench reads the model" and "the library was built by that model." Provenance tells us it happened. Only a bar stops it corrupting the measurement 8b exists to make.

**Decision.** Three repairs, all three taken.

1. **A cross-model admission bar for adaptive-discovered cases.** A case proposed by the adaptive layer enters the library only if it reaches `D ≥ 0.4` with non-overlapping Wilson 90% intervals against the three reference agents **on the second underlying model as well as the first**. It must separate on a model it was not discovered on.
2. **`discovered_by` as provenance on the case record** — `authored`, `adaptive`, or `user_gap` — and `docs/validation.md` prints **what fraction of the live library is adaptive-discovered** on every gate run. The drift then has a number attached and arrives as a series rather than as a surprise, which is the move [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) already makes for decay.
3. **The retirement-rate signal.** Adaptive-discovered cases retiring faster than authored ones is the fingerprint of overfitting. Ticket #14 already stores `D` per case per run, so this costs a grouping and nothing else.

**The bar applies to adaptive-discovered cases only.** Hand-authored cases keep the single-model admission rule of ADR-0003. This is not leniency: an authored case was never *fitted* to these three agents, so the selection pressure the bar exists to counter is not acting on it. Applying the bar to everything would double the admission cost of the whole library to correct a defect present in one part of it.

## Considered options

- **Discard the discovery agent and write cases by hand only.** This is the defect removed by removing the feature that makes the project's central loop close. Rejected.
- **Provenance alone.** It makes the drift visible and does nothing about it, and "we printed the number that shows our measurement is degrading" is not a control. Necessary, not sufficient.
- **Hold adaptive-discovered cases out of `D` entirely** — admit them but exclude them from the gate's family statistics. Rejected: it produces a two-tier library where half the cases run but do not count, which is a denominator problem invented to solve a selection problem.

## Consequences

- **Cost is per promoted case, not per gate run.** The second-model seam already exists as configuration from ticket #2 and is exercised by ticket #15, so this is a re-run of one case against three agents, not new machinery.
- **A promoted case that clears the first model and fails the second is discarded — and the discard is itself a finding.** It is direct evidence that a route the attacker found was a property of one model rather than of the agents' defences, which is 8b's question answered case by case instead of only in aggregate. Rejected cases are discarded rather than parked, per the spec, but the count of cross-model rejections is recorded in `docs/validation.md`.
- **The admission bar is now two numbers where the plan says one.** §6 and ticket #12 must state both, and the report must print which bar a case entered under, or a reader cannot tell an adaptive-discovered case from an authored one.
- The claim "user input proposes, a quantitative gate disposes" ([ADR-0006](./0006-overrides-never-change-a-measured-rate.md)) extends to the attacker with one added clause: **the attacker proposes, and it does not get to be graded only by the agents it learned on.**
