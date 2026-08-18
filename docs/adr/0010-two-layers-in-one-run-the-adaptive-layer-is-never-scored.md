---
status: accepted
---

# Two layers in one run: the adaptive layer is never scored

The adaptive attacker moved from Sprint 4 into Sprint 3 because the honest answer to "where is the agent in this project" was one model-invoked tool, against a brief called *Building with AI Agents*. Moving it breaks something, and the break is precise. **The verdict survives adaptivity; the rate does not.** A canary either appeared or it did not, whatever route the attacker took — `success_condition` is indifferent to how the payload was chosen. But run an adaptive attacker twice and you get two different numbers, because each run samples a different path through the space of things it might have tried. That destroys the `n = 30` denominator, the decay chart, the retirement rule, and the reproducibility of the signed number — which is the exact crack [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) exists to close, reopened at the other end of the pipeline. A signature over a rate produced by a stochastic search certifies that we held the number, in the same sense and for the same reason.

Deferring the layer again was rejected: it removes the sprint's named topic from the deliverable, which is the failure [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) already recorded happening once. Letting adaptive results into the rates was rejected on the paragraph above. What remains is to run both and keep them apart.

**Decision.** One run carries **two layers**.

| | Scored layer | Adaptive layer |
|---|---|---|
| What runs | 18 fixed cases, 10 attempts each | one attacker agent, a turn budget per family |
| Who chooses the payload | the case record | the model |
| Denominator | `n = 30` per family per agent | none — the unit is an **episode**, not an attempt |
| Reproducible | yes, from recorded inputs | no; recorded, not re-derivable |
| Feeds | rate, Wilson interval, `D`, band, monotonicity, the gate, the signature | its own report section, and `propose_case` |

The scored layer is unchanged in every particular. **No adaptive result ever enters a rate, a band, a `D`, the gate decision, or the signed number.** Adaptive findings appear in the report as their own section — what a competent attacker achieved beyond the fixed suite — and their one route into anything scored is `propose_case`, which lands in the admission gate and is decided by a stated threshold rather than by the attacker's own assessment.

This is not a new discipline. It is the invariant of [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) — no user input ever changes a measured rate — generalised to its actual scope: **no input that is not a recorded case ever changes a measured rate.** Overrides, the configuration scan and now the adaptive layer are three instances of one rule.

## The invariant is a type, not a discipline

`TargetRun.rates` in `backend/bench/calibration.py:41` groups **everything** in `attempts` by family and divides. `Attempt` already carries `case_id`, `family`, `target_name`, `transcript` and `verdict` — which is exactly the shape an adaptive turn has. Recording adaptive turns as `Attempt`s would therefore move every denominator in the bench **silently**: the arithmetic stays valid, the population changes, and no test fails. A rule written in a plan does not survive that; a type does.

- `AdaptiveEpisode` is a separate record and **cannot be constructed from an `Attempt`**. It carries turns, not attempts, and it has no `verdict` field — an episode is `broken` or `censored`, which is a different question from whether one attempt succeeded.
- Episodes live in their own field on the run state, with **their own call counter**, so the budget the adaptive layer spends is visible separately from the budget the fixed suite spends.
- **The judged families' instrument is inside this invariant, not beside it.** Adjudication ([ADR-0013](./0013-adjudication-is-a-third-instrument.md)) produces a scored verdict, which makes it exactly the kind of component this ADR is about: `adjudication.py` imports no adaptive route, no precedent and no transport, and an import-level test fails if one appears. An `AdaptiveEpisode` has no `verdict` field and cannot acquire one by being handed to a second instrument — the adaptive layer gained a new semantic component to reach for and no new edge to reach it by.
- `run_probe` and `run_attack` share the transport — `contract.send_message`, so the spec's "a single code path from the attacker to any target" survives at the level where it was meant — and share nothing above it: different function, different counter, different store.
- `check_canary` **wraps the evaluator's `evaluate`** and returns its answer. The attacker chooses *when* to look; it never gets to decide *what it sees*. ADR-0004 then holds inside the adaptive layer rather than merely around it.

## Ordering, and why it needs a test rather than a rule

**Adaptive episodes run strictly after the fixed suite, for a given target.** If a target carries any persistent state — a conversation store, a cache, a rate limiter that trips — an adaptive turn arriving before a scored attempt contaminates the scored attempt, and it does so by a route no type can prevent, because the two records are already correctly separated by then.

So this constraint gets an executable check rather than a paragraph: `backend/tests/test_layer_ordering.py::test_no_adaptive_episode_precedes_a_scored_attempt` fails if any episode's start timestamp precedes any attempt's start timestamp for the same target. It is written before the adaptive layer exists and skips until `RunState.episodes` arrives, so it activates on the commit that would otherwise be able to break it. An invariant with no failing test is an invariant that survives exactly as long as the person who wrote it is reading the diff.

## Consequences

- **`n = 30` is scoped.** It is the denominator of the scored layer. An adaptive turn is not an attempt and is never counted as one — see the amendment in [ADR-0003](./0003-gate-decision-rule-and-sample-size.md).
- **Reproducibility is scoped, and the scoping is the honest version.** The *gate decision* is reproducible from its recorded inputs, as before. The *adaptive section* is recorded rather than re-derivable, and the report says so. Claiming a stochastic search is reproducible would be the same overreach the judge's narrative fields were demoted for.
- **The adaptive layer's thresholds live in `AdaptiveBudget`, deliberately not in `GateRule`.** `GateRule` is the rule the gate prints beside its result. Nothing that decides nothing belongs in it, and keeping the turn budget out of it means no adaptive number can ever appear in the printed rule.
- **The adaptive layer decides nothing.** Its own discrimination statistic ([ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md)) is a diagnostic on the attacker. If it collapses, the response is to repair the attacker and report the collapse — never to stop or to pass the gate.
- **Cost.** At a turn budget of `T = 8` and `k = 2` episodes per cell, the adaptive layer adds 6 families × 3 agents × 8 × 2 = **288 target calls** to a gate run, taking it from 540 to roughly 830, and doubling again for the multi-model check. Cheap in money, longer overnight, and it changes what the pre-run estimate must show — see the amendment in [ADR-0007](./0007-canary-nonce-as-proof-of-control.md).
- **The loop closes.** An adaptive success is the best available source for trigger 2 (*a target passed everything — either it is good or my attacks are weak*), because it is the only source that can distinguish the two by demonstration. The agent explores, `propose_case` drafts, the admission gate admits, the library grows, and the signed number stays reproducible because nothing crossed the boundary except a case that beat a stated threshold. That is what makes "an agent that learns" auditable here: **the arbiter is a declared number, not the model's own confidence.**
