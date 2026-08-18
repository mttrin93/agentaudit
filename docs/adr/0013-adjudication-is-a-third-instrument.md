---
status: accepted
---

# Adjudication is a third instrument, compelled by ADR-0004 rather than chosen

Two families — wrongful commitment and disclosure denial — reach a verdict that no
success condition can produce. [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md)
says so itself, in its own consequences table: their verdicts are "irreducibly
semantic; LLM verdict with a stated reliability figure." The same ADR also says, as
its central decision, that the judge "**cannot overturn a verdict**" and produces
"narrative fields only". And [CONTEXT.md](../../CONTEXT.md) says a **reading** is
"the narrative counterpart to a verdict, and never a verdict" — a separate type, for
the same reason an episode is not an attempt.

Those three statements are each correct and, taken together, describe a verdict with
nothing authorised to produce it. ADR-0004 asserts that a judged verdict exists,
forbids the only component then in the design from returning one, and the vocabulary
forbids promoting what that component does return. Building #9 walked into the gap:
there is no way to give wrongful commitment a verdict without either breaking one of
the three statements or introducing something that was never named.

**This is the same shape as the hole ADR-0004 was itself written to close.** That
ADR opens on a design that "carried two verdict mechanisms with no precedence rule"
— both mechanisms present, both plausible, and nothing saying which one decided.
The hole was not a wrong answer; it was a *missing* answer that every surrounding
sentence read past, and it survived review because each statement about it was true
in isolation. This one is the mirror image: three true statements and no mechanism
at all. It is recorded here, before #11, #12 and #13 build on it, because the cost
of that shape is not the mistake — it is how long it stays invisible.

**Decision.** A judged verdict is produced by **adjudication**, a third instrument,
distinct from both the deterministic evaluator and the judge.
`adjudication.adjudicate(brief, complete) -> Verdict` returns a verdict and nothing
else. `judge.assess_finding` is untouched and still cannot return one.
**Adjudication** is added to CONTEXT.md as a term of its own, on the same reasoning
that keeps **probe** and **case** apart: two things that would otherwise be called
"judging" in prose, one of which lands in a denominator.

The instrument is compelled, not preferred. Each alternative breaks one of the three
statements above, and the breakage is load-bearing in every case:

- **Let the judge return a verdict for the two judged families.** This reopens
  exactly the ambiguity ADR-0004 exists to close. `assess_finding` would be
  authoritative for two families and narrative for four, with no type distinguishing
  the two modes — a signature widened to mean both things, which is the failure mode
  [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)
  names. It also makes ADR-0004's own constraints unenforceable: the precedent store
  "must never reach `assess_finding`" because precedent would contaminate κ, and a
  judge that also emits verdicts is a component where blinding and precedent limits
  have to hold for one of its outputs and not the other.
- **Write deterministic success conditions for the two families anyway.** False on
  the evidence. Every marker a check could look for — "we will", "guarantee",
  "waive"; "I'm a person", "not a bot" — appears just as readily in a reply
  explaining why the agent will not do the thing. A check there does not measure the
  failure, it manufactures verdicts, and it would do so in the direction that
  flatters the bench.
- **Coerce the judge's `Reading` into a verdict at the call site.** Forbidden by
  CONTEXT.md, and the prohibition is not bookkeeping: `Reading` has an `UNCLEAR`
  member, and a verdict lands in a denominator where "unclear" is not a value.
- **Drop the two families.** Forfeits the only coverage this bench has of Article
  50(1) disclosure and of Article 15 accuracy-with-legal-effect, and PLAN §4 commits
  to six families. Retirement is a legitimate outcome for a family that fails to
  discriminate; it is not a way to avoid naming an instrument.

## What the instrument is, and what its shape is load-bearing for

Adjudication inherits every constraint ADR-0004 puts on the judge, and one it does
not, because the consequence of unblinding is worse here than there.

- **It returns a `Verdict` and nothing narrative** — no reason, no article, no fix,
  no exposure type. A report therefore cannot take its narrative from the instrument
  that decided its number, and the two cannot be conflated in prose even by someone
  who has not read this ADR.
- **It is blinded, and here blinding closes the last circularity in
  [ADR-0003](./0003-gate-decision-rule-and-sample-size.md).** An unblinded judge
  grades a narrative generously; an unblinded adjudicator manufactures `D` directly,
  because its output *is* what `D` is computed from. So it never receives an
  `Attempt` or a `Transcript` — both carry the target's name or its url — but an
  `AdjudicationBrief` whose field list is the whole of what it may see.
- **It reads no precedent and no prior finding.** `adjudicate` takes the brief and a
  model call, and the constraint is the signature rather than a rule: phase 6a
  cannot reach it without widening one.
- **The criterion is data, not prompt.** The question and both sides of the answer
  come off the case record's `judged_condition`, so a reader holding the record and
  the transcript can see what was asked. A model cannot widen the criterion, just as
  it cannot widen a case's coverage claim.
- **There is no `unclear`.** A judged verdict lands in a denominator, so it is binary
  by construction. Uncertainty about a transcript is real, is recorded by the judge's
  `Reading.UNCLEAR`, and is counted nowhere.
- **Verdict class is read from the case record, never inferred from the family
  name.** `Case.verdict_class` decides the route, `Attempt.verdict_class` is copied
  from the record when the attempt is made, and the report's two sections select on
  that field. A family renamed or a case moved between families cannot silently
  change which instrument decided it.

## Consequences

- **κ measures adjudication.** The reliability figure ADR-0004 requires is a figure
  about the instrument that produces the verdict, which is `adjudicate` and not
  `assess_finding`. [ADR-0009](./0009-deepeval-executes-the-goldset.md) named the
  wrong component — it was written when the judge was the only semantic component in
  the design — and is amended rather than left to be discovered by #11, which is
  where it would have broken.
- **Judged rates are reported in their own section and never summed with
  deterministic ones.** `TargetRun.deterministic_rates` and `judged_rates` select on
  `Attempt.verdict_class`; there is deliberately no property returning the two
  together and none that totals either, and a family attempted under both classes
  raises rather than reporting. That is [ADR-0005](./0005-no-composite-risk-score.md)'s
  prohibition on a composite score applied one level down.
- **Two model settings, deliberately.** The adjudicator's model is the one κ
  measures; the judge's is not. They are separate settings so the multi-model check
  at #15 can move one without the other, and the `Completion` alias is declared in
  `adjudication.py` rather than imported from the judge so a shared type cannot
  imply they must move together.
- **A third instrument is a third thing whose own quality is unknown until it is
  measured.** κ < 0.6 means the judged family is not fit to report — that rule is
  ADR-0004's and it now bites on this component. Until #11 exists there is no κ, so
  no rate for either judged family is published; `docs/validation.md` carries the
  section with no table and states why.
- **ADR-0010 is untouched.** `adjudication.py` imports no adaptive route, no
  precedent and no transport, and an import-level test fails if one appears. An
  `AdaptiveEpisode` still cannot become an `Attempt`, and adjudication gives it no
  new way to try.
