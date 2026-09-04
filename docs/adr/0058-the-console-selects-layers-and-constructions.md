---
status: accepted
---

# The console selects layers and constructions, and the artefact carries the selection

The console already sets a run's declared inputs ([ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md)) and already switches families off, so the mechanism for *what the next run does* exists. What #79 adds is a selection over the dimension #72 gave the library: which of the three layers run — single-turn, fixed multi-turn, adaptive — and which `Transform` members inside them. That is a second setting in the class ADR-0025 put `attempts_per_case` in alone, because **it moves the scored denominator**, and unlike that one it is not a scalar: two runs at equal `attempts_per_case` and different selections sent different libraries.

**Decision.** `AttackSelection` — a frozen record of layers and constructions — sits beside `families` on `BenchConfig`. `plan_for` filters the library on it and prices what remains; a family it leaves with nothing is reported as **not run**, carrying a `DeclaredGap` member of its own; the adaptive layer opens no episode when its layer is off, and the estimate an operator confirms falls to nothing for it; and the **signed artefact carries the selection in provenance**, beside the library version. One write is added under `/bench`, on ADR-0025's four conditions, and `scripts/gate.py` takes no selection from it.

## 1. A construction switched off is not a rate of zero, and there are three surfaces to say it on

The distinction this bench keeps everywhere: *not measured* and *measured at zero* are different facts and no reader may confuse them. The vocabulary already existed in three shapes and this record adds nothing parallel to them. `NotMeasurable` is the library's answer to a case precondition a target cannot meet. `Withheld` is a judged rate below the κ floor. `DeclaredGap` is **the caller's own gaps** — what the caller's setup did not provide — which is exactly what a construction the caller switched off is. So:

- **`DeclaredGap.TRANSFORMS_SWITCHED_OFF`**, beside `FAMILY_SWITCHED_OFF` and one level below it: that one says *this family was not asked*, this one says *this family was asked and there was nothing left to ask it with*. It reaches a screen through `families_not_run`, which carries each gap's own sentence.
- **`AttackSelection.stated()` in the artefact's provenance**, which is §4.
- **The counts, from the other end.** `scorer.VariantCounts` already refuses an entry at zero attempts, with the sentence *a transform that was never sent is absent from the breakdown rather than present at zero* ([ADR-0055](./0055-a-family-pools-its-variants-and-publishes-the-counts.md)). #79 does not touch it. What #79 supplies is the reason for the absence, because an absent entry alone cannot say whether the library holds no such variant or this run declined to send one.

**The gap is only for a family the selection *emptied*.** A family that keeps one construction is measured on what remains, with no reason printed beside it — a ragged variant set per family is representable and legitimate (ADR-0055), and narrower is not absent. And a family switched off *and* left empty by the selection reports `FAMILY_SWITCHED_OFF`: the coarser statement is the true one, because a family nobody asked for had no construction offered to it at all.

This is the distinction #72 refused a new absence type for, read from the other side. That refusal was about a variant the **bench** never wrote — an encoding wrapped round `scope-creep-001` destroys the mechanism, so the family is measured by the variants that exist and owes no explanation. This is one the **caller** turned off.

## 2. `AttackLayer` is a third enumeration, and not `budget.Layer`

`Layer` is a pair of budget counters: a call on the wire is billed to the scored side or the adaptive side and there is no third answer (ADR-0007). Both of the layers that carry a construction bill the same counter, so folding the selection into `Layer` would mean an operator could not switch the ladders off without switching the encodings off with them, and splitting `Layer` in two would add a consent counter that nothing enforces. Two vocabularies then — one about spending, one about selection — and `selection.layer_of` is the only join, total and exhaustive, because a transform no layer claimed would be one that ran whatever an operator selected.

**The adaptive layer is a member of `AttackLayer` and carries no `Transform`.** What it would carry are the two loops [ADR-0051](./0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md) §3 deliberately keeps out of the enum, so the operator's question about it is *does the agent run at all* — a boolean, `AttackSelection.adaptive`, with nowhere for an adaptive construction to be named as something a scored record could claim ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)).

**A layer switch is where the two layers could have blurred, and it is where they are furthest apart.** The scored half of a selection reaches the run by dropping cases in `plan_for`, and the adaptive half reaches it by not calling `run_adaptive_layer` at all. Neither path can produce a record of the other's type, and switching the adaptive layer off moves no rate, no band, no `D` and no gate decision — it is the cheap switch precisely because there is no denominator behind it.

**The construction half does reach the adaptive layer, through the cases, and the effect is stated rather than absorbed.** Both layers are handed the plan's cases, so switching a construction off narrows the pool `objectives_for` picks each family's objective from — which is the same mechanism the family switch already uses deliberately, one level down. It changes no episode's subject: an objective supplies the family and the success condition, its payload is never sent (the attacker composes every probe — `prompt.episode_brief`, and `proposal.py`'s *a probe the attacker composed, and not a transform of the objective*), and every variant of a family measures the same failure against the same criterion, which is the premise ADR-0055's pooling already rests on. So `A_effort` stays a reading about the attacker rather than about the selection. What the narrowing can do is leave a family with **no** objective, and that is the correct reading rather than a hole: the family was not run, which is what its `DeclaredGap` says. This is asserted at the composition of the two functions, because nothing in either one's own signature would show it.

**Named `AttackSelection` rather than `Selection`**, because `backend/corpus/selection.py` already holds a `Selection` — the corpus rows a person was shown, which is what CONTEXT.md's **technique** entry means by the word — and `elective.ElectiveSelection` is qualified for the same reason. The concept word in prose and in the artefact stays *selection*, which is what `VARIANTS_STATED` already published.

## 3. Selection is per layer, globally, and not a per-family matrix

A six-by-eight grid of checkboxes is a screen that produces runs nobody can compare. The operator's real question is *do I want the encodings, the ladders, or the agent?*, and the layers answer it. A per-family need is a ticket with a reason and not a default.

## 4. The artefact carries it, which is the question ADR-0025 left open

ADR-0025's families amendment stated its own limit and refused to decide it: *"the signed artefact names the families it measured and does not name the reason the rest are missing… this record does not decide whether it should also travel in the payload — that is a change to the payload and wants an ADR of its own."* This is that ADR, for the selection.

The reason it is decided the other way here is that the two absences are not equally legible. A family that was not run is **visible** as a missing per-family block, and nothing in the report totals or ranks across families, so a reader can see the shape of what was covered. A construction that was not sent is visible only as a missing row in a variant breakdown — and over today's library, which holds eighteen `PLAIN` records and no admitted variant, it is not visible at all: two runs with different transform selections produce identical measured sections, because there is no variant for either to have dropped. Equal outcomes at unequal instructions is a coincidence of the library and not comparability.

So `Provenance.selection` is **required, with no default**. What a default would say is *every construction*, which is the flattering answer: a caller that forgot the field would sign a document claiming a full suite over a run that sent a fraction of one, and nothing else on the page could contradict it. `_provenance` serialises the two sorted member lists, a derived `whole_library` flag, and the sentence — sorted because a set has no order and a serialiser that printed one would make two identical selections two different documents (ADR-0016).

**This is the second half of `VARIANTS_STATED`, and neither half asserts comparability alone.** That constant states the condition — *comparable only at equal library version and equal selection* — and names a selection the artefact did not carry. `AttackSelection.stated()` states this run's half of it. The verifier asserts that the sentence follows from the members beside it, on `provenance.rule.attempts_per_case_stated`'s exact terms ([ADR-0027](./0027-the-verifier-reads-the-denominator-and-asserts-the-rest-of-the-bar.md)): the selection itself is **read and not asserted**, because it is a declared input an operator may set, and what is asserted is that the document cannot carry one selection while telling its reader about another.

The families gap stays where ADR-0025 left it. This record decides the selection only; carrying the family coverage into the payload is still the ticket that ADR-0025 says it is.

## 5. `scripts/gate.py` takes no selection from this type

The gate is a claim about the bench over the whole library ([ADR-0018](./0018-the-gate-is-about-the-bench-and-a-report-is-about-a-target.md)), and a gate run over a chosen subset would be a gate for a bench nobody has. `gate.py` stays on `DECLARED_RULE` and constructs no `AttackSelection` — the precedent `attempts_per_case` set, followed exactly. A run made at a narrowed selection is a real run whose artefact says what it sent, and it is not a gate result.

## 6. A selection that would score nothing is refused, in the type

`AttackSelection.__post_init__` refuses a selection under which no construction runs in a layer that runs. That is condition 4 of ADR-0025 — refused, never widened — applied where this type could have clamped: a bench that read *nothing* as *everything* would run a suite nobody chose. It is in the type rather than only at the route because every caller that can construct one can start a run.

It is not a refusal of an adaptive-only run in disguise, because there is no such run to refuse: an episode needs a deterministic case for its family (`adaptive/layer.objectives_for`), so a selection that dropped every case would open no episode either.

## 7. The branch schedule is **not** selectable here, and that is deliberate

[ADR-0057](./0057-a-tree-is-the-harnesss-schedule-and-a-turn-is-still-one-probe.md) landed `AdaptiveBudget.branching` with no selection path — no flag, no environment variable, no place in provenance — so only a caller constructing an `AdaptiveBudget` can ask for a tree, and every recorded reading was taken on the line. #79 is *the console chooses layers and techniques*, so the question was put here and the answer is no, for two reasons.

**It is not a construction and not a layer.** `Transform` deliberately holds neither adaptive loop, so a branch policy offered beside the seven constructions would put an adaptive-only knob into a record whose other half moves the scored denominator — blurring in one type the thing ADR-0010 keeps apart, on the very surface §2 argues is where the two layers are furthest apart.

**Its home is the other record.** `T` and `k` are adaptive knobs the console already sets, and they travel in `Instrumented` — the six declared inputs that bound a layer scored on nothing. A branch schedule is the third of that kind, so a selection path for it is a **seventh field on `Instrumented`** and a line in the adaptive section of the report, not a member of this record. That work also has to keep the gate citation honest: the declared schedule is the line because the reference agents were gated under it (ADR-0023), so offering a tree means either a gate run under it or a stated sentence that a tree run is not a gate result — which is a decision with its own arithmetic and its own ticket.

## Consequences

- **A third write appears under `/bench`.** `PUT /bench/settings/selection`, admitted on ADR-0025's four conditions and argued in its amendment. `test_api_settings.py` and `test_api_gate.py` name every route on the prefix, so a **fourth** write still fails and has to be argued before it lands.
- **The rendering digest moved**, and so did `test_rendering.GOLDEN_ONE_FAMILY`: the provenance block gained a subsection. That tripwire is updated with the reason and never loosened.
- **The estimate moves when the selection moves.** A layer switched off is a `CallFigure` of zero calls, still a `CEILING` — nothing about a layer that ran is exact, and a bound of nothing is the one bound that cannot be exceeded — with a basis that says which of the two zeros it is. The ceiling falls with it, so a call from a switched-off layer is refused at the counter and not merely absent by convention.
- **The selection is correct over a library that holds one construction, and today's library holds one.** Eighteen records, every one of them `PLAIN`, because admission is per variant and needs a person at a tty ([ADR-0052](./0052-a-transform-is-a-committed-function-and-no-judged-family-gets-a-variant.md) §5). So every reading in this record about a run over two constructions is **held by a test and is not measured today**, and the test that holds it builds its variant in the test file rather than faking an admission.
- Settings held in a process are lost at a restart, which is the shape the run registry already has and the same P1 it carries.
