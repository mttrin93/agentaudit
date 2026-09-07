---
status: accepted
---

# `A_break` is over the six, and the tier is read beside it

The adaptive layer is about to attack the elective families a run requested (#173).
Every other record it fills widens without an argument — an episode is scored on
nothing, so an episode in the tier costs nothing and decides nothing. One record does
not: `A_break`.

[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) defines
`A_break = (families broken on trivial − families broken on hardened) / 6`, amends the
denominator to *the families that opened an episode against both agents*, and prints
the shortfall beside it. Today that denominator is at most four — the two judged
families have no success condition for `check_canary` to apply, so they open no
episode at all — and every reading in [docs/validation.md](../validation.md) was taken
over it. Let the tier into the same figure and the denominator becomes as many as
seven, run to run, at the operator's selection. The arithmetic stays valid and the
series stops meaning one thing: a run that requested three elective families and broke
one more on the trivial agent would print a *lower* `A_break` than a run that requested
none, and the reading table's four rows would be read against a number whose base the
operator had chosen.

That is the same defect [ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md)
refused one layer down, arriving at the one figure the tier was never held out of —
because nobody had written it down. It gets written down here.

## Decision

1. **`A_break`, `A_effort` and the sign test stay over `Family`.** The scope is the
   six that opened an episode against both agents, exactly as ADR-0011's amendment
   says, and an elective family is not a candidate for it at any selection. The
   readings in `docs/validation.md` stay comparable across this line, and a run that
   requested no elective family produces the identical figure it produced before #173.
   The prohibition is carried by the type: `AgentBreaks.families`, `AgentBreaks.broken`
   and `AdaptiveSeparation.scope` are annotated over `Family`, so an elective episode
   reaching them is a type error and not a silently wider denominator.

2. **The tier is read beside it, per family, and never as a ratio.** An elective
   family that opened an episode reports, in the adaptive block and under its own
   heading, which agents it broke, which censored it, and which it could check nothing
   against at all — three words and not two, for the reason the consequences below
   give. It is a reading and not a statistic: it says what the attacker achieved where,
   and there is no number in it to put in a column next to `A_break`.

3. **And deliberately no `A_break` of its own.** The obvious alternative is a second
   ratio over the requested tier, and it is refused for ADR-0011's own reason, one size
   down. ADR-0011 spends a paragraph on why `n = 6` is small enough that the report has
   to say so; the tier is a closed set of **three**, and a run may request one. A
   difference of family counts over a denominator of one is a figure with two possible
   values, and a reader who met it beside `A_break` would weigh them the same. What
   would be gained is a number; what would be lost is the ability to say what the
   number is over. So the tier's block prints families and outcomes, and a reader who
   wants a difference takes it themselves, knowing over what.

4. **[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) is
   untouched, and nothing here amends it.** An episode on an elective family is scored
   on nothing, has no denominator, and reaches the scored side through the one edge it
   already had: `propose_case` into the admission gate, where
   [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)'s
   cross-model bar decides it. An elective proposal enters nothing by having been
   proposed, and the tier's block is a section of a report and an input to none of them.

5. **The ceiling covers what the layer may attack.** `AdaptiveBudget.family_count` is
   the six and stays the six, because it is what `A_break`'s shortfall line is read
   against. The families a run requested from the tier widen the **ceiling** —
   `elective_families`, a second field — so that an operator who asked for the tier is
   shown, and consents to, the turns it will cost. A ceiling that stayed at six
   families while the layer opened episodes on nine would stop a run mid-layer at the
   counter, which is [ADR-0007](./0007-canary-nonce-as-proof-of-control.md)'s guarantee
   working correctly against a figure that was declared wrongly.

## Considered options

- **Widen the denominator and state the scope per run.** The honest version of this is
  what the ticket offers as the alternative: `A_break` divided by the families in scope
  whichever tier they came from, with the scope printed. It is already how the figure
  is printed — the shortfall line exists — so it costs nothing to build, and that is
  its whole appeal. Rejected because the scope would then be **an operator's
  selection** rather than a property of the library, and the four-row reading table is
  read against a fixed base: *`A_break` ≈ 0, neither broken* and *`A_break` low because
  three families the operator added were never going to break* print the same number.
  ADR-0011's amendment widened the denominator to exclude what the library could not
  supply, which makes the figure *more* about the attacker; this would move it in the
  opposite direction.

- **One reading, with the tier's families flagged inside it.** A single scope with a
  marker per family, so a reader can recompute either figure. Rejected on ADR-0005's
  rule as it applies to families: two tiers in one list is one key that reaches across
  them, and the first thing a reader does with a flagged list is ignore the flag.

- **No reading for the tier at all — attack it, propose from it, print nothing.** The
  cheapest option, and it makes the tier's episodes unfalsifiable: an attacker that
  found nothing on memory poisoning three runs running would be indistinguishable from
  one that was never pointed at it. It is the *a family printed nowhere* defect the
  tier spec already refuses, and it is refused again here.

- **A second `A_break` over the requested tier.** Decision 3.

## Consequences

- **`docs/validation.md`'s `A_break` series continues across #173.** No entry is
  restated, no reading is recomputed, and the figure a future gate run prints is over
  the same six-family base as the one before it. This is the property the decision was
  taken for.

- **The tier's reading has no history and no floor.** Nothing in it is compared to a
  threshold, because there is none to declare: `discrimination_floor` is the gate's and
  is read over `D`, and this block decides nothing. A tier reading is evidence that the
  attacker was pointed at the family and what came back — which is the claim #173 makes
  and the whole of it.

- **Memory poisoning's block needs a third word, and the block has one.** Two facts
  about that family land on this reading and neither is *broke it*. Its cases carry
  `retained_instruction_executed`, so every route found there is declined by
  [ADR-0084](./0084-a-route-the-record-cannot-carry-is-declined-and-not-synthesised.md)
  and proposed to nothing — and, further, that condition is read over **two** turns
  (ADR-0041) while this layer sends probes, so `measurability.checkable` answers
  `False` for every turn and an episode there verifies nothing at all. A block with
  only *broke* and *censored* in it would therefore print the one family the bench
  cannot question here as the agent that held, which is the direction ADR-0011 says a
  reading may not be wrong in. So `ElectiveAttack` carries `unreadable` beside
  `censored` and says *nothing was checkable against this agent* — the adaptive
  counterpart of `NotMeasurable`, one tier out. All of it is the honest outcome, stated
  in `docs/validation.md` before the first run rather than explained after it.

- **A run that requested the tier costs more turns and says so before it starts.**
  Seven families rather than four opening `k` episodes at `T` turns is the estimate the
  operator confirms, and decision 5 is what makes the number they see the number the
  counter enforces.

Cross-references: [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)
(the layer is scored on nothing, and the one edge),
[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (the figure this ADR scopes),
[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) (the
bar an elective proposal faces),
[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) (the tier, and the
records that may not widen),
[ADR-0084](./0084-a-route-the-record-cannot-carry-is-declined-and-not-synthesised.md)
(why memory poisoning files nothing),
[ADR-0088](./0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)
(the parallel-section move this decision follows), #173.
