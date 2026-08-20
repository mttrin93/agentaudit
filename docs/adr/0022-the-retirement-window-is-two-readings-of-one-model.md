---
status: accepted
---

# The retirement window is two readings of one model, and a run that did not measure the field cannot retire anything

[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) declares the retirement rule as `D < 0.25` on **two consecutive runs**, and #14 implemented it: a `GateReading` per case per gate run, appended to the case's own record, and `decide_retirement` reading the rule over `history[-2:]`. The window is positional. The reading has carried the model it was taken on since #14 — `AdmissionReading.model`, written into every `[[history]]` block — and nothing reads that field when the rule is applied.

So the rule cannot presently tell one instrument from another. #43 demonstrated both halves of what that costs, against the merged code:

```
two stub runs      -> retired | retires: True
  models in window : ['stub:obedient', 'stub:obedient']
real then stub     -> live
stub then real low -> retired | final score model: openrouter:openai/gpt-4.1-nano
```

`scripts/gate.py --model stub:obedient` is how the pipeline is exercised without spending money, and it is a gate run like any other: it appends readings. The stub breaks every reference agent equally, so it reads `D = 0.00` on families a real model separates at 1.00 — the stub swap run of 2026-08-19 read data leakage 1.00 → 0.00 across two stubs on exactly this basis. Two free runs therefore retire working cases, and a stub run followed by a real one retires with the *real* model's name landing on the recorded final score.

This is decided now rather than after the fact because retirement is not reversible by re-measuring. A retired case leaves the live library, and `RetirementDisagrees` refuses to load a record whose status and series disagree, so a case retired on stub evidence stays retired until a human edits a record by hand — the removal-by-judgement the rule exists to prevent. Nothing has been wrongly retired yet: no case record carries a `[[history]]` block, because both committed gate runs predate #14. The first two gate runs on the current code decide whether that stays true.

## Decision

**Two consecutive runs means two consecutive readings of the same instrument, and a run on a stub model is not a reading of the field at all.**

1. **The window is scoped to one model.** The series is filtered to the model of its most recent reading, and the rule is read over the last two of that filtered subsequence. Readings on other models are not in the window and cannot supply half of a retirement.
2. **The most recent reading always participates.** The window is anchored to the newest reading's model rather than to whichever model has two low readings somewhere in the series. Retirement is a claim about the case *now*; a claim that ignores the most recent measurement of the case is a claim about the past, and it would let a case retire on two old readings after a newer model measured it separating.
3. **Readings outside the window are still stored, still printed, and never deleted.** A reading is the record of what one model measured on one day ([ADR-0006](./0006-overrides-never-change-a-measured-rate.md)); the series is the whole of it. Scoping the *window* is not editing the *series*.
4. **A reading taken on a stub model cannot retire a case.** It is stored like any other, marked as not a measurement of the field, and the rule declines: the outcome is `NOT_DECIDED`, the third member [ADR-0016](./0016-retirement-declines-on-a-family-unfit-to-report.md) already introduced, and no fourth is added.
5. **Provenance is recorded on the reading by the run that took it**, on the same terms as `fit_to_report` — a fact about the run, not something `retirement.py` re-derives later by parsing a model string. `backend/bench/` does not import `backend/targets/`, and it must not acquire the dependency to answer this: the gate-run entry point already holds the `ModelConfig`, and `Provider` is a closed enum, so a third provider has to decide which side of this line it falls on rather than defaulting onto one.
6. **The decision line names the model the window was read on**, and says so when a window was refused for provenance — the discipline `NotMeasurable.stated()` and ADR-0016 §4 already follow.

## Why the window is scoped to a model

`D` is trivial minus hardened over a fixed denominator, and it is a property of the case *and the model underneath the three reference agents*, not of the case alone. #15 exists because a model swap moves it — that is the whole premise of the multi-model validity check, and the strongest objection the project answers. A rule that reads two readings positionally treats a change of instrument as the passage of time. It says "this case stopped discriminating" when what happened is "somebody pointed the bench at something else."

This is the general statement, and the stub is only its loudest instance. Two real models are not two consecutive readings of the same thing either. Scoping the window is therefore a correction to what *consecutive* means, not a special case bolted on for a test fixture — which is why it is preferred to a rule that names stubs and nothing else.

## Why scoping to a model is not sufficient on its own, and what closes the rest

A same-model window does not close the defect it was chosen for. The demonstrated `stub:obedient, stub:obedient` case is two readings of one model, and it satisfies clause 1 exactly. Recording that here rather than discovering it in review: the option this ADR adopts had to be extended before it covered its own motivating example.

The extension is not arbitrary, because a stub reading fails a different test from a real one. ADR-0016 refused to let retirement rest on a number the report will not print — a *degraded* measurement of the field. A stub reading is not degraded. The stub is a fixture with hardcoded replies; it breaks every reference agent identically by construction, so its `D` is not a poor estimate of the case's discriminating power but a statement about the fixture. Retiring on it would be a claim about the field derived from something that never touched the field.

The direction is the same one ADR-0016 spent its length on, and it is worse here. A degraded adjudicator attenuates `D` toward zero and becomes a machine for retiring cases that work. The stub does not attenuate toward zero — it *is* zero, on every case, every time, for free. Two runs of a script that costs nothing would empty the live library, and each removal would be recorded as evidence that the field moved.

So the invariant of ADR-0016 extends rather than being restated:

> **A reading's provenance can only withhold a retirement. It can never cause one.**

`decide_retirement` reaches the provenance question only on the branch that would otherwise have returned *retired*, exactly as it reaches the fitness question, so a stub reading can turn *retired* into *not decided* and nothing else. A stub run still stores its readings, still prints its section, and still exercises the storing path end to end without spending money.

## What this rule does that the positional one did not

Clause 1 is not only a restriction. Given a series `A(low), B(high), A(low)`, the positional window reads `[B high, A low]` and says *live*; the model-scoped window reads `[A low, A low]` and says *retired*. **The new rule retires a case the old one would have held live**, and that is intended: `B`'s high reading is evidence about `B` and says nothing about whether the case separates on `A`, which has now failed to separate twice. The "one bad night" protection of ADR-0003 is untouched — two distinct runs on `A` are still required.

It has a cost, and it is the one to watch. Retirement is a single status on a case record, so a case that separates on `B` and not on `A` is retired out of the live library for `B` runs too. That is deliberate: model-dependent discrimination is precisely the finding #15 is looking for, and it has to be visible in the record rather than absorbed by a permissive rule that keeps such a case live and unremarked. The retired record carries the reading that retired it, and that reading names its model, so the case is legible as *retired on `A`* rather than as *retired*.

## Considered options

- **Bar a stub run from writing readings at all.** The cleanest sentence — the series records what the field did, and a stub says nothing about the field. Refused because it removes the premise of `test_gate`, which asserts that an end-to-end run stores one `D` per record and which runs on stubs, and because it would leave the storing path exercised only by runs that spend money. Storing with the provenance marked costs nothing and keeps the path under test.
- **Write stub readings to a separate series the rule never reads.** Same protection, more machinery: a second store, a second reader, and two places a reading can live. It also loses the thing the marked reading gives a later reader — that this run happened, on this date, and concluded nothing.
- **Name stubs in the rule and leave the window positional.** Closes the demonstrated case and leaves the general one open: two real models in a window would still be read as two readings of one thing, and #15 exists because they are not.
- **Retire only if the case is below the floor on the most recent reading of *every* model measured.** Makes retirement depend on how many models the bench happens to have been pointed at, and lets one favourable reading on a model nobody runs any more hold a case live forever. Retirement would become unreachable in practice as models accumulate.
- **Make retirement a per-model status.** The honest generalisation of the cost named above, and rejected as over-built for what exists now: `status` is one line on a case record, `live_library` is one filter, and per-model status multiplies both by a model list that changes. If #15 finds discrimination to be substantially model-dependent, this is the option to revisit, and this paragraph is the note to revisit it from.
- **Widen the window to three runs so a stub cannot fill it.** The hour-30 threshold move ADR-0003 exists to prevent, and it does not even work: three stub runs are as free as two.

## Consequences

- `decide_retirement` takes the model and the provenance off the readings it is given, and `RetirementDecision` carries the model its window was read on. `retirement.py`'s module docstring stops describing the window as the last two readings and describes it as the last two on one model.
- `readings_of` and the gate-run entry point record provenance on each reading, beside `fit_to_report`. The `[[history]]` block gains the field; the model was already written there.
- **Provenance and fitness compose, and they compose the same way**: both are checked only on the branch that would have retired, and either one withholds. A stub reading on an unfit family is *not decided* once, not twice.
- **The clock restarts on a model swap.** A case with one low reading on `A`, then measured on `B`, needs two `B` readings before it can retire. The cost has the same shape as ADR-0016's restart, is bounded by two runs, and is paid in attempts against a case that stays live meanwhile.
- **No migration.** No case record carries a `[[history]]` block yet, so no stored series changes meaning and no retired record has to be re-derived. `RetirementDisagrees` continues to enforce agreement between status and series at load, now under the stricter window.
- The gate-run pipeline stays runnable for free, end to end, including the storing path — which was the reason the stub fixture exists.
- The thing to test if this rule is ever changed: for any series, any interleaving of models and any fitness pattern, a stub reading must never move an outcome to *retired*, and a window must never mix two models.

Cross-references: [ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the floor, the two-run window, and why thresholds do not move), [ADR-0016](./0016-retirement-declines-on-a-family-unfit-to-report.md) (the fitness half of the same question, and the invariant this extends), [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) (why the readings outside the window are kept), [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) (the other place a second model is load-bearing), #14 (the series), #15 (why one model's `D` is not another's), #43 (the defect report and its demonstration).
