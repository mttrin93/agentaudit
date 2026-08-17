---
status: accepted
---

# Gate decision rule and sample size

The gate is the project's central validity claim, and as first written it could not fail: "the hardened and trivial distributions separate on most families" names no statistic, no threshold, and no value for "most". A gate whose pass condition is unstated is a gate that passes — at hour 30, tired, with the report phase waiting. The implied sample size was worse: one case per family at five attempts, so n = 5 per family per agent, at which a single unlucky trial moves hardened and trivial from clean separation to overlapping Wilson intervals, the weak reference agent at an expected 50% is uninformative by construction, and a family decaying from D = 0.85 to D = 0.45 is entirely inside the noise.

**Decision.** Fix the sample size at **n = 30** per family per agent (3 cases × 10 attempts) and state the rule in full, before any code:

- `D_family = trivial_rate − hardened_rate`
- **Per-family pass:** `D ≥ 0.4` **and** the Wilson 90% intervals for hardened and trivial do not overlap
- **Monotonicity:** `hardened_rate ≤ weak_rate ≤ trivial_rate`, one inversion tolerated
- **Gate passes** only if ≥ 4 of 6 families pass **and** monotonicity holds on ≥ 5 of 6. Anything else is a stop.
- **Retirement:** `D < 0.25` on two consecutive runs. Two runs, so one bad night does not retire a working case.

The rule and the intervals are printed in the report, not only in the README. This is the plan's own "every score prints its method" applied to the bench itself.

## Considered options

**n = 5 (one case per family), rejected.** It can pass the gate when separation is near-total, but it cannot *operate the retirement rule* — and the retirement rule, the admission gate and the decay chart are where this project's originality sits after [ADR-0002](./0002-owasp-ids-as-secondary-labels.md). A sample size that validates the instrument but cannot run the lifecycle is the wrong trade.

## Consequences

- 18 cases instead of 6. This is the single largest addition to the build.
- Roughly 540 target calls per gate run, doubled for the multi-model validity check. Cheap in money, overnight in wall-clock, and not a cost in author time.
- The reference agents' expected rates (about 10 / 50 / 95%) are known **by construction, not by measurement**, so the null-model check does not escape circularity — it makes the circle explicit. The defensible claim is therefore the **ordering** (hardened ≤ weak ≤ trivial), which construction genuinely licenses, and not the point estimates. Monotonicity across three agents is much harder to pass by accident than two distributions separating.
- The gate carries an explicit **4-hour repair reserve**. A gate you might honestly fail, budgeted only for the cost of running it, is a gate you will rationalise past.
