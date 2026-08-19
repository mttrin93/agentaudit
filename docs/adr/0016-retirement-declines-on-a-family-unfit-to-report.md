---
status: accepted
---

# Retirement declines on a family the bench cannot vouch for, and its clock restarts when the family is repaired

[ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) excluded a judged family below `GateRule.kappa_floor` from the gate decision, and closed with one thing left open in as many words: whether the **retirement** rule may operate on that family's cases is *not* settled there, because "retirement is #14's rule and deciding it in passing would be exactly the kind of inference this repo keeps out of prose. It needs its own decision." #14 has landed — `backend/bench/retirement.py`, the `D` series a gate run stores on every case record and the two-consecutive-runs rule read over it — and declined the question rather than answering it by default. This ADR is that deferral being paid.

It is not hypothetical, and that is why it is being paid now rather than at the report phase. Wrongful commitment reads κ 0.59, 0.59, 0.73, 0.59 against a declared floor of 0.60 ([validation](../validation.md), 2026-08-18), so `Reliability.fit_to_report` marks it unfit and ADR-0015 excludes it from the gate. Its three cases are still attempted, still scored, and still store a `D` on every run. Two consecutive low readings on any of them is reachable on the next two gate runs, and on the day it happens something has to decide whether that case leaves the live library.

**Decision. Retirement declines on a family unfit to report.** A case whose two consecutive low readings were taken on an excluded family is **not decided**: the readings are stored, the rule is not applied, and the line says which reliability figure stopped it.

1. **The rule requires both of its readings to be fit.** `decide_retirement` retires only where every reading in the window carries `fit_to_report`. One unfit reading in the window is enough to withhold the retirement.
2. **The readings are still stored.** Spec story 72 says `D` is stored for every case on every gate run, and [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) keeps a measured rate measured — the attempts were made. The reading is written with `fit_to_report = false`, so a reader can see both that it was taken and that nothing was concluded from it.
3. **Not decided is a third outcome, not a polite version of live.** `RetirementOutcome` has three members for the same reason `GateDecision` grew a third: *live* is a claim that the rule was applied and did not fire, and this is a claim that the rule could not be put. Collapsing them would report a case as holding up under a rule that never ran on it.
4. **The declining reason prints, naming the family and the κ that caused it** — the discipline `NotMeasurable.stated()` and ADR-0015 §6 already follow.
5. **A stored unfit reading never becomes usable.** When a family is repaired, the rule is read over readings taken *after* the repair. A reading taken while the adjudicator's reliability was unstated does not become trustworthy because a later adjudicator was measured. **The retirement clock therefore restarts for that family**, and its cost is named below.

## Why: you cannot claim decay on a number you do not trust enough to report

Retirement is not bookkeeping. It is a **claim**: this case has stopped separating a careful agent from a careless one, and the field has moved past it. That claim rests entirely on `D`, and on an unfit family `D` is computed from verdicts whose agreement with the pre-registered gold set cannot be stated. So the claim would rest on a number that the report itself refuses to print. A number the report will not show may not decide the report — ADR-0015 said that about the gate decision, and retirement is the second consumer of the same number.

This is ADR-0015 §3 read one level down. **Exclusion is total**: "a family barred from the report may not supply evidence to either half of the gate decision", and half-excluding one is worse than either whole answer. Retirement is another half. A family unpublishable in the report yet trusted to shrink the library is the same defect in a different consumer, and the only reason it needs its own ADR at all is that ADR-0015 was careful enough not to extend itself by implication.

## The failure has a direction, which is what makes the permissive answer worse than unsupported

κ 0.59 says the adjudicator's agreement with the gold set cannot be stated as reliable. It does **not** say the disagreement is random, and the difference matters because the two possibilities move `D` in opposite directions:

- **Non-differential error** — the adjudicator is wrong about a hardened transcript as often as about a trivial one. This moves both rates toward the same base rate and **attenuates `D` toward zero**. The rule would then read the adjudicator's noise as the case's decay, and it would read it *in the direction that retires*.
- **Differential error** — wrong more often on one reference agent than another. Here `D` can be inflated as readily as attenuated, and a case that genuinely stopped discriminating would be held live by the same unreliability.

κ below the floor is exactly the state in which the bench cannot say which of the two it is in. But the first is the one worth planning against, because it is the one with a systematic direction: **an adjudicator that degrades becomes a machine for retiring cases that work.** Every case in the family drifts toward the floor together, two runs arrive, and the library quietly loses a whole family's coverage — with the retirement recorded as evidence that "the field moved", which would be a false claim about the world derived from a fault in the instrument.

That is the same shape as the arithmetic ADR-0015 spent its length on. There, a fraction of the fit-to-report denominator turned a degraded instrument into a **lowered bar**. Here, applying retirement to an unfit family turns a degraded instrument into a **shrinking library**. Both let an instrument's own decay be spent as if it were a finding, and both are closed the same way — by refusing to let the unfit family supply the evidence.

It is stateable as the mirror of ADR-0015's invariant, and it holds by construction rather than by care:

> **A family's unfitness can only withhold a retirement. It can never cause one, and it never changes a live case's answer.**

`decide_retirement` reaches the fitness question only on the branch where it would otherwise have returned *retired*, so unfitness can turn *retired* into *not decided* and nothing else. A case whose series does not meet the two-run rule reads *live* whether its family is fit or not.

## Considered options

- **Apply the rule anyway.** The permissive answer, and the one with a direction: under non-differential error it retires working cases at exactly the moment the bench has least standing to say so, and records the loss as a finding about the field. It also converts an adjudicator problem — repairable, and with a repair route already open in ADR-0015 — into a library that has to be rebuilt.
- **Do not store the readings at all.** Breaks spec story 72 and ADR-0006, and destroys the only evidence a future reader could use once κ is repaired: whether the family really was drifting, or whether it read low only while the adjudicator was unreliable. Storing with `fit_to_report = false` costs nothing and keeps that question answerable.
- **Treat an unfit reading as "not below the floor", so the case reads live.** Reaches the same non-retirement by lying about which branch it came from. It is the error [ADR-0013](./0013-adjudication-is-a-third-instrument.md) and `NotMeasurable` both exist to prevent — reporting a number for something that was not measured — and it hides from the reader that the rule could not be applied.
- **Suspend the whole retirement rule until every family is fit.** Over-broad. The four deterministic families have no adjudicator in their path and no κ at issue; their cases should retire on the declared rule. One family's unstated reliability is not a reason to stop the bench noticing its own decay everywhere else.
- **Give unfit families a longer window — three consecutive runs instead of two.** Invents a second threshold with no defence beyond wanting an answer, which is the hour-30 threshold move [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) exists to prevent. It also does not fix the problem: attenuation toward zero is systematic, so a longer window delays the wrong retirement rather than preventing it.
- **Read the rule retrospectively over stored unfit readings once the family becomes fit.** Tempting, because the readings are right there and the clock restart is a real cost. Refused: a measurement does not acquire reliability from a later, different instrument. And under ADR-0015's repair route the new criterion is a *new instrument honestly measured* — readings taken under the old one are the record of what the old criterion measured, and reading them under the new one's reliability figure would be the retro-fitting that ADR forbids, arriving by the back door.

## Consequences

- `retirement.py`'s declining branch is ratified rather than provisional. Its module docstring, `RetirementOutcome.NOT_DECIDED.stated()` and `readings_of` stop describing the question as open and cite this ADR as the decision, keeping ADR-0015 as the principle they apply.
- ADR-0015's "left open, deliberately" consequence is **discharged**, on the same terms as `decide_gate`'s deferred docstring note was discharged by ADR-0015 itself.
- **Wrongful commitment's three cases will accumulate not-decided readings on every gate run** until its criterion is rewritten and a fresh gold set labelled against it — ADR-0015's one open repair route. That is the visible cost of this decision and it is the correct one: the alternative is a family retired on verdicts nobody can vouch for.
- **The retirement clock restarts on repair, and this is a real loss.** A family repaired after two low runs starts again from zero fit readings, so the earliest a genuinely decayed case in it can retire is two gate runs after the repair lands. A case that really has stopped discriminating therefore stays in the live library longer than the declared rule would otherwise allow, and keeps costing ten attempts per target while it does. Named rather than absorbed, because the arithmetic — not the sentiment — is what a later reader will need: the cost is bounded by two runs and it is paid in attempts, and it is smaller than the cost of retiring the wrong cases, which is paid in coverage the library cannot get back without rewriting cases.
- **`NotMeasurable` and unfitness still compose, and they compose differently here than at the gate.** A case no attempt was spent on stores *no reading at all* — `readings_of` names it as unread rather than writing a `D` of zero — so it cannot retire for the simpler reason that its series never grows. Unfitness is the other case: the attempts were made, the reading exists, and only the rule is withheld. Both print distinctly, on ADR-0015's terms.
- The invariant above is the thing to test if this rule is ever changed: for any series and any fitness pattern, unfitness must never move an outcome to *retired*.

Cross-references: [ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) (the exclusion this applies, and the deferral this pays), [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the floor, the two-run window and why thresholds do not move), [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (why refusing to publish is automatic rather than a judgement call), [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) (a measured rate stays measured, which is why the reading is stored), [ADR-0013](./0013-adjudication-is-a-third-instrument.md) (what κ is measured on).
