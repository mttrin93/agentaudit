---
status: accepted
---

# An elective family's rate against a target is a fact about that target, and its `D` is not

[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) decided
that a target's report carries rates, intervals and bands about the target, and the
bench's own gate result as **provenance** and never as a result. Every word of it
stands and none of it is edited here.

[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) decided the
elective family tier, and its decision 7 read ADR-0018 one level down:

> A target report carries the tier's declared selection and its absences, and **no
> figure at all**. […] the figures print in the gate document, never in the measured
> section — which is keyed on `Family` and has no field one could arrive in.

**That decision is amended here, in one direction only.** The figure ADR-0018 excluded
is the bench's own discrimination score on the tier — trivial minus hardened, over
three agents of known construction, at the gate's floor. That is a claim about *this
bench* and it stays where the bench's claims are. What ADR-0035 §7 also excluded, and
did not separately argue for, is the **failure rate an elective family measured against
the operator's own agent**. That is the same kind of quantity as `data_leakage`'s rate
on the same run: successes over attempts against one target, at the rule the run
declared. It is a fact about that agent, it is exactly what an operator who asked for
the family paid for, and there is no reading of ADR-0018 under which it is a claim
about the bench.

Two different figures have been sharing one prohibition. This ADR separates them.

## Decision

1. **An elective family a run was asked for, and measured, reports its rate, its
   Wilson interval, its band and its per-construction counts in that target's signed
   report.** Same arithmetic, same rule, same cut points, same functions — because it
   is the same question asked of the same target, and *selectable is not ungated*
   (ADR-0035 §3) has no second reading in which it becomes *selectable is not
   reportable*.

2. **The tier's `D` does not travel, and there is no field it could travel in.**
   `ElectiveEntry` has no `discrimination` attribute, no `reliability` attribute and
   no `label` attribute; the payload writes no such key; the renderer prints no such
   line. `memory_poisoning`'s `D = 0.33` stays in the gate run's own document, which
   is ADR-0018 §3 unamended and ADR-0035 §7's actual claim left standing. The
   prohibition is carried by the type, exactly as ADR-0018 §2 asks: a contributor who
   wanted an elective `D` in a report would have to add a field, which is a visible
   edit a test asserts against.

3. **A parallel section, and `FamilyEntry.family` does not widen.** The tier's
   measured figures arrive in `MeasuredSection.elective: tuple[ElectiveEntry, ...]`,
   keyed on `ElectiveFamily`, beside `deterministic` and `judged` and inside neither.
   `FamilyEntry` stays annotated over `Family`. §"Why parallel and not widened" below
   is the argument, and it is short, because ADR-0035 §2 already names `FamilyEntry`
   in the list of records that *may not be widened*.

4. **The absences follow the figures.** An elective family the run requested and
   could not measure — memory poisoning against a target that carries no session
   state — reaches `MeasuredSection.elective_not_measurable`, keyed on
   `ElectiveFamily`, and prints with its reason. Without it, a requested family would
   be named in the request and absent from the figures with nothing beside it, which
   is the reader guessing that every one of this document's five absences exists to
   prevent (ADR-0004, ADR-0075). *Not requested* is unchanged and is still the fifth
   kind of nothing.

5. **The gate keeps everything it had.** `GateResult.elective` still sits beside
   `GateDecision` and not inside it; `decide_gate` still takes `Sequence[FamilyOutcome]`
   over the six; `family_rates` still loops `for family in Family`;
   `cited_library` still cites the six's version whatever else ran. **An elective
   family decides no gate at any reading**, and this ADR adds no path by which one
   could. ADR-0035 §§1–6 and §§8–10 are untouched.

6. **A run that measured seven families still measured six mandatory families.** The
   report says so in the shape of the document rather than in a caption: the tier's
   figures are under their own heading, with the selection that asked for them printed
   above, and no list, count or property in the artefact holds an elective entry and a
   `FamilyEntry` together. There is no key at any depth that reaches across the two
   tiers, which is ADR-0005's rule about families read one tier out. In particular the
   **declared bar** (ADR-0067) is per family over the six and reads
   `measured.deterministic` and `measured.judged`; it does not read this section, so a
   run that requested the tier cannot turn somebody's pipeline green or red on a family
   their bar does not name.

7. **`ARTEFACT_VERSION` goes 1 → 2.** A later shape is a different shape. This is the
   first change to this document that is not additive in the sense
   [ADR-0044](./0044-a-familys-label-prints-beside-its-figures.md) §8 and
   [ADR-0070](./0070-a-signed-document-may-carry-a-remediation.md) argued about: what
   moves is not a key beside existing keys but **what the measured section is keyed
   on**. A verifier reading version 1 re-derives every figure it knows about and
   silently re-derives *nothing* for the tier — it would report a document as verified
   while an entire block of figures went unchecked, which is the one failure the
   verifier exists to make impossible. So the version moves, `verification.py` refuses
   a version it does not know, and a recipient holding an old verifier is told to get a
   new one rather than handed a clean reading over half a document.

8. **The console may request the tier.** `/bench/settings/families` accepts elective
   names beside the six, and `BenchConfig` carries `ElectiveSelection` as a declared
   input on the footing ADR-0025 sets. The six may not be emptied and the tier may be:
   a run covering none of the six attacks the thing this bench is for and is refused,
   and a run requesting no elective family is every run today.

## Why an elective rate is not the figure ADR-0018 excluded

ADR-0018's argument is arithmetical and it is worth reading it against this case
rather than around it.

`D` **cannot be computed for a target at all**: it is trivial minus hardened, and there
is one agent, so there is no difference to take. Monotonicity is an ordering across
three agents; with one there is nothing to order. The gate's two thresholds are counts
over families of *contrast*. Not one of those quantities has a definition when the
subject is a single target — which is why ADR-0018 says the separation is "not that a
gate decision about a target would be misleading" but that "there is no arithmetic that
would produce one".

Now ask the same question of `memory_poisoning`'s rate against somebody's agent. It is
successes over attempts, at the declared attempts per case, with a Wilson interval at
the declared confidence and a band read against the declared cut points. Every one of
those quantities has a definition, is computed by the same function `data_leakage`'s is,
and is about the one agent in front of the reader. ADR-0018's argument does not reach
it, because ADR-0018's argument is about quantities that do not exist for a single
target, and this one exists.

What ADR-0035 §7 got right, and this ADR keeps, is the direction of the danger. The
figure that would be misread is the `D`: a reader handed a bench's discrimination score
and a target's band in one table will read the first as the second, which is exactly
ADR-0035's own considered option *elective figures in the target report beside the six*.
That option is still rejected. What is admitted here is not "the elective figures" — it
is the target's own rate, without the bench's.

## Why parallel and not widened

The alternative shape is to widen `FamilyEntry.family` to `AnyFamily` and let an
elective family be an ordinary entry in `deterministic`. Rejected, on four counts.

**ADR-0035 §2 names `FamilyEntry` in the list that may not be widened**, and that
decision is not amended here. It is in that list because the split it enforces is
mechanical: `_entries` iterates `for family in Family`, `MeasuredSection.unfit_to_report`
returns `tuple[Family, ...]`, `declared_and_defeated` crosses controls with families,
`payload._label` calls `labels.label_for` over the six's table, `bar._bands` builds a
`Mapping[Family, Band]`. Widening the field opens every one of those by default, and
closing each again is a condition somebody has to remember — the trade ADR-0010 refused
one level up and ADR-0035 refused here.

**A widened field would give an elective family a published label.** `_label` reads
`labels.LABELS` over the six, and CONTEXT.md is explicit that an elective label "makes
no coverage claim […] and it reaches no report, because what prints beside a family name
in a signed report is a claim about one of the six" (ADR-0044). An entry that iterated
into `_entry` would either print one or need a new condition not to. This section prints
no label and no coverage note, and that is a decision rather than an omission: the entry
it claims stays listed as untested, and the tier changes no coverage statement in this
document.

**A widened field makes an elective entry indistinguishable from one of the six in
every consumer that iterates the section** — which is the issue's own sentence and is
the whole cost. The report screen draws a figure grid over the measured entries; a
seventh card in a row of six is a denominator this bench does not have. The parallel
section makes that impossible to do by accident rather than wrong to do deliberately.

**And the two are not the same kind of row anyway.** A `FamilyEntry` carries a `D`, a
`label` and a coverage note; an `ElectiveEntry` carries none of the three, on decision 2
and the paragraph above. A union type whose members disagree about three of their eight
fields is two types wearing one name.

## Considered options

- **Leave ADR-0035 §7 as it is; an elective family is requestable on a gate run
  only.** The status quo, and it makes the tier's target-facing half unreachable:
  ADR-0035 §5 and spec story 12 both say the selection is a lever an operator holds
  *at a target run*, and there has never been a way to pull it. Rejected as the
  decision that leaves a documented capability with no door.
- **Widen `FamilyEntry.family` to `AnyFamily`.** Rejected above.
- **Report the elective rate and also the tier's `D`, clearly labelled.** Rejected on
  ADR-0018's own considered options: "labels are not load-bearing at the distance a
  document travels". A `D` beside a band in one block is the misreading ADR-0035
  rejected by name, and nothing about admitting the rate makes it safer.
- **Report the elective rate with no band.** Considered seriously, because a band is
  read against cut points anchored to the two reference agents (ADR-0014) and one could
  argue that anchoring makes it a claim about the bench. Rejected: the same anchoring
  is true of every band in this document, the cut points travel in the artefact and are
  re-derived by the verifier, and a rate published without the summary a reader is
  given for every other family would be a figure the document declines to interpret for
  exactly the families the operator asked for.
- **A separate signed document for the tier.** Rejected: two artefacts about one run
  is two things to sign, verify, bind and lose, and the operator asked one bench one
  question about one agent.
- **Keep `ARTEFACT_VERSION` at 1.** Rejected in decision 7. Every earlier addition to
  this document was a key a version-1 verifier could ignore without failing to check a
  figure; this one is not.

## Consequences

- `ARTEFACT_VERSION` is 2. Every previously issued artefact reads as an older shape to
  `verification.py` and to `bar.py`, both of which already refuse a version they do not
  know with a sentence saying so. That cost was declined by ADR-0044 for a key and is
  accepted here for a shape, on decision 7's reasoning.
- The golden rendering digest moves, once, in the commit that adds the section.
- `scripts/verify` re-derives an elective entry's rate, interval, band and pooled
  denominator through the same functions it re-derives a `FamilyEntry`'s with. A tier
  the verifier did not read would be figures in a signed document nobody can check,
  which is the state decision 7 exists to prevent.
- `TargetRun.elective_rates` is now pooled from `TargetRun.elective_variant_counts`,
  as the six's rates are pooled from theirs (ADR-0055). The tier's records are all
  `plain` today, so every breakdown has one line — and the line is printed rather than
  assumed, because the document that travels may not be the one that says less than the
  payload it is a view of.
- The bench page's elective block gains tick boxes and loses the sentence saying there
  is nothing there to turn on.
- **The tier's readings are still thin, and the screen says so.** Two of memory
  poisoning's three cases separate nothing on either model measured so far
  (`docs/validation.md`, *2026-09-07, second run*), so an operator ticking that family
  is running one discriminating case and two that are not. That is a fact about the
  bench, it belongs beside the switch rather than in the report, and it is on the
  switch.
- ADR-0035's decision 7 is superseded in part and says so; ADR-0035 is not otherwise
  edited, and nothing in it is rewritten to say something it did not decide. ADR-0018
  is not edited at all.
- `docs/specs/elective-family-tier.md` gains a second *superseded in part* line: story
  23 ("no rate, interval, band or `D` for any elective family in a target report") is
  half superseded — the `D` half stands, the rate half does not — and the *console
  lever* bullet of its Out of Scope is now in scope and built.

Cross-references:
[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) (what a
report is about, unamended),
[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) (the tier; §7
amended here, the rest standing),
[ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md) (a declared input the
console may set),
[ADR-0055](./0055-a-family-pools-its-variants-and-publishes-the-counts.md) (the pooled
rate and the counts beside it),
[ADR-0067](./0067-the-bar-is-per-family-and-a-withdrawn-family-is-not-green.md) (the
bar is per family over the six),
[ADR-0044](./0044-a-familys-label-prints-beside-its-figures.md) (a label prints beside
the six's figures, and only theirs),
[ADR-0005](./0005-no-composite-risk-score.md) (nothing reaches across families, one
tier out).
