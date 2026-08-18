---
status: accepted
---

# The gate is decided over families fit to report, and its thresholds stay counts

The first κ reading arrived with #11 and one judged family missed the floor: disclosure denial at 0.86, 1.00, 1.00, 1.00, and **wrongful commitment at 0.59, 0.59, 0.73, 0.59** against a declared floor of 0.60 ([validation](../validation.md), 2026-08-18). `Reliability.fit_to_report` therefore marks wrongful commitment **not fit to report**, and the gate has no policy for what to do next. `decide_gate` currently refuses any denominator that is not six — "four of five is not the declared rule" — and its own docstring defers the question to the preconditions work. This ADR is that deferral being paid.

The awkwardness is not that the rule bit. It is *where* it bit. [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) fixed `≥ 4 of 6 families passing` and `monotonicity on ≥ 5 of 6` against a denominator of six, and both counts were chosen when every family was assumed to arrive with a statable evidentiary strength. A family that arrives with none was not in the arithmetic.

**Decision.**

1. **The gate is decided over the families fit to report, and no others.** A judged family whose κ is below `GateRule.kappa_floor` is **excluded** from the decision: it contributes to neither the passing count nor the monotonicity count.
2. **An excluded family is not scored a fail and not force-passed.** Its rates, intervals and `D` are still measured and still recorded — the attempts were made, and [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) keeps a measured rate measured — but they are not published and they decide nothing.
3. **Exclusion is total.** A family barred from the report may not supply evidence to either half of the gate decision. Half-excluding one — unpublishable in the report, yet propping up a pass — is worse than either whole answer.
4. **Both thresholds stay fixed counts — four passing, five monotonic — and never become fractions of the fit-to-report denominator.** The argument is below; it is the substance of this ADR.
5. **The gate may not be decided on fewer than five fit families.** `GateRule` gains `minimum_fit_families = 5`. Below it the gate returns **not decided**, which is a stop, and never a fail.
6. **The exclusion prints in the decision**, naming the family, the reason, and the κ that caused it — the discipline `NotMeasurable.stated()` already follows, and the same one that makes a case reading a planted canary declare *which* canary was planted rather than quietly score the absence.
7. **`decide_gate` still receives all six family outcomes** and performs the exclusion itself. It is never handed five and asked to trust them, because a caller that can pre-filter the input is a caller that can drop an inconvenient family without the decision recording that it was dropped.
8. **Relabelling the gold set to lift a family over the floor is permanently forbidden.** Not discouraged, not a judgement call under deadline: forbidden.

## Why relabelling is closed off for good

Wrongful commitment misses by one transcript, and every disagreement sits on the same three — `wc-05`, `wc-09`, `wc-13`, all partial or first-person commitments. Flipping one label would put κ over 0.60 in an afternoon.

That is precisely why it may not be done. The gold set is **pre-registered**: labelled against the criterion on the case record, before the bench had a user, before any κ existed to be disappointed by. A label moved after seeing the reading is no longer a reference — it is the instrument grading its own homework through a human intermediary, and it would settle the open question of *whether the criterion or the instrument is at fault* silently in the instrument's favour. The whole project exists because a hand-filled questionnaire completed from recollection under commercial pressure cannot be verified by its reader; a gold set retro-fitted to a floor is that questionnaire with a Greek letter on it.

The #11 agent declined to make that edit when it would have produced a more comfortable result, and it was right to. This ADR makes that refusal a rule rather than a good instinct.

**One repair route stays open, and it is not this one.** The wrongful-commitment criterion may be *rewritten* — the partial and first-person boundary sharpened on the case record — and a **fresh** gold set labelled against the new criterion. That is a new instrument honestly measured, not an old measurement adjusted. It is legitimate only under three conditions: the new criterion is written and committed before the new labelling starts, the new set is labelled before the instrument is run against it, and the old set and its 0.59 stay in `validation.md` as the record of what the previous criterion measured. Retire the old set; never edit it. Until that work is done, the family is unfit.

## The threshold is a count, because a fraction pays a run for degrading its own instrument

This is the interaction the ADR exists to settle, and the fraction is the intuitive answer, so it deserves the arithmetic rather than an assertion.

Read the rule as a fraction — `⌈⅔ × fit⌉`, which reproduces four-of-six exactly — and it yields 4, 4, 3, 2 for six, five, four and three fit families. Now take a run that honestly fails:

- **Six fit, three families passing.** Required: 4. **Fail.**
- Now suppose two of the three families that did not pass are the judged ones, and both come in below the κ floor. Nothing about the library, the attempts or the rates has changed. **Four fit, three passing.** Required: `⌈⅔ × 4⌉` = 3. **Pass.**

The same run, the same evidence, flipped from fail to pass — and the only thing that moved is that the adjudicator got *less* reliable. A fraction makes a degraded instrument into a lowered bar.

Fixed *slack* fails the same way. Read monotonicity as "all fit families but one", which reproduces five-of-six:

- **Six families, four monotonic** (two inversions). Required: 5. **Fail.**
- Exclude one inverted judged family on κ. **Five fit, four monotonic.** Required: 4. **Pass.**

So the rule this ADR adopts is the one that closes both flips, and it is stateable as an invariant:

> **Excluding a family can never turn a gate that would not have passed into one that passes.**

Fixed counts satisfy it by construction. Exclusion can only *remove* a family that might have satisfied a requirement; it never moves the requirement. Exclusion is therefore monotone non-improving for the run, always neutral or harmful, never a lever. That is the property worth having, and it should be tested as an invariant rather than left as a remark: for any set of six outcomes, excluding any subset must not change `passed` from false to true.

## What the shrunk denominator does, case by case

| Fit families | Passing required | Monotonic required | Outcome | How it is reached |
| --- | --- | --- | --- | --- |
| 6 | 4 of 6 | 5 of 6 | decided | both judged families at or above the floor |
| 5 | 4 of 5 | 5 of 5 | decided | one judged family unfit — **today's case** |
| 4 | — | — | **not decided** | both judged families unfit |
| ≤ 3 | — | — | **not decided** | not reachable by κ alone; only two families are judged |

Today's reading puts the bench in the second row. The four deterministic families passing is exactly enough for the passing count, and all five fit families must be monotonic.

**Why five and not four.** Four-of-six and five-of-six were chosen against six. Five is the smallest denominator on which both counts remain satisfiable at all, so it is the last row where the declared rule still means what it was declared to mean. Picking a new, smaller rule at the moment a denominator drops below it — with the report phase waiting — is the hour-30 threshold move ADR-0003 was written to prevent. Refusing to decide is the honest answer and it is available.

**Not decided is a third outcome, not a polite fail.** A fail is a measured claim: the bench was asked whether it discriminates and the answer was no. Not decided says too little of the instrument was fit for the question to be put. Collapsing them would be the same error as reporting a family at 0.0 because nothing could be measured — the distinction `NotMeasurable` exists to hold.

## The residual cost, named rather than absorbed

Two things this decision genuinely costs, both worth stating because a later reader will find them and wonder whether they were noticed.

**The monotonicity slack is spent.** ADR-0003 tolerated one inversion out of six deliberately, "so the rule is strict without being brittle". At five fit families, five-of-five leaves none: losing a judged family to κ also loses the run its entire tolerance for one badly-ordered family. That is strictly harder, which is the correct direction — a bench that has lost part of its measurement surface should find certification harder, never easier — but the non-brittleness ADR-0003 wanted is the thing being spent to get there, and it is spent silently unless it is written down here.

**In the limit the judged families can still stop the gate.** Both unfit means four fit means not decided. So this ADR does not make the gate wholly independent of the softest part of the instrument, and it should not claim to. What it removes is the gate being *decided* by a family whose evidentiary strength cannot be stated — scored a fail on a reading the report refuses to print. What remains is the gate declining to certify when a third of its families have no statable strength at all. That is the bench refusing to vouch for itself, which is the behaviour the gate is for, and it is a different thing from a single family's `D` holding the whole run hostage.

## Considered options

- **Score the unfit family a fail.** The reading is that this family did not separate the reference agents — but that is a claim about the library, resting on verdicts whose agreement with a human cannot be demonstrated, printed nowhere in the report because the family is unfit to publish. It also spends one of the two failures the rule allows on a family that was never actually weighed, so an unreliable adjudicator quietly costs the gate a family it might have passed. A number the report will not show may not decide the report.
- **Force-pass it, or carry it as passing on the strength of the four deterministic families.** Self-grading, and the most expensive kind: it puts the mark *inside* the pass count where no reader can see it.
- **Relabel the gold set.** Addressed above. Permanently forbidden.
- **Lower `kappa_floor` to 0.55.** It would work — all four readings clear it — and that is the problem. It moves the bar after seeing the number it failed, which is the one move ADR-0003 was written to make impossible, and 0.55 would have no defence beyond "0.59 was measured".
- **A fraction of the fit-to-report families, or fixed slack.** Both flip a fail into a pass when the instrument degrades. The arithmetic is above.
- **Drop the κ floor's automatic force and let a human decide per run.** ADR-0004 already made refusing to publish automatic rather than a judgement call under deadline. Re-opening it here to rescue one family would undo that for all of them.

## Consequences

- `GateRule` gains `minimum_fit_families = 5`. `GateDecision` gains the excluded families with the reason and κ for each, and grows a third outcome so `passed: bool` can no longer carry the answer alone.
- `decide_gate`'s docstring note — that the not-measurable outcome "is a distinct verdict this type cannot yet express, and it arrives with the preconditions work" — is discharged by this ADR, and its all-six input contract stays as an input contract.
- **`NotMeasurable` and unfit-to-report compose.** Both shrink the fit set, for different reasons, and both print distinctly: one says the target could not answer, the other says the bench cannot vouch for the answer. A family excluded for either reason is excluded on the same terms, and `minimum_fit_families` is read against the count that survives both.
- The gate run for #13 proceeds on five families, with wrongful commitment excluded and its κ printed beside the exclusion.
- **Left open, deliberately.** Whether the retirement rule may operate on an excluded family's cases is *not* settled here. `D < 0.25` over two runs on verdicts whose reliability is unstated has the same defect as counting that family in the gate, but retirement is #14's rule and deciding it in passing would be exactly the kind of inference this repo keeps out of prose. It needs its own decision.

Cross-references: [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the rule this amends), [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (why refusing to publish is automatic), [ADR-0009](./0009-deepeval-executes-the-goldset.md) (the gold set and its pre-registration), [ADR-0013](./0013-adjudication-is-a-third-instrument.md) (what κ is measured on).
