---
status: accepted
---

# The elective family tier is declared, gate-measured, and never gate-deciding

[PLAN](../../PLAN.md) §5 P2 decided the shape of this tier on 2026-08-20 and recorded
it there so it would not be re-derived. What it could not do was write the ADR: the
*skipping is never advantageous* invariant has a half that depends on how the
retirement window is scoped, and that scoping was an open question until
[ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md) answered it.
ADR-0022 is accepted, so the block is lifted and this is the ADR.

Three families arrive under #42 — `ASI06` memory poisoning, `LLM01` direct prompt
injection, `LLM02` PII leakage — and **none of them may enter the six**.
[ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) spent its whole
argument proving that `families_required` and `monotonic_families_required` must be
fixed counts over a fixed `family_count`, and that excluding a family may only ever
remove a candidate from a count and never move a bar. A seventh family in the
denominator re-opens all of it. So the tier lands beside the six, and this ADR is
about what "beside" has to mean for that to be true of the code rather than of a
sentence in a planning document.

## Decision

1. **The tier is a second closed set of family names.** `library.ElectiveFamily` is a
   `StrEnum` disjoint from `Family`, holding the three families #42 selected. `Family`
   stays six members and CONTEXT.md's definition of **family** stays exactly as it is.
2. **The distinction is carried by the type, at the decision boundary.** The records
   the gate decision is built from — `FamilyRates`, `FamilyOutcome`, `Excluded`,
   `FamilyEntry`, `GateDecision.outcomes`, `TargetRun.rates` and
   `TargetRun.not_measurable` — are annotated over `Family` alone, and none of them
   may be widened to accept both. An elective reading is carried by `ElectiveRates`
   and `ElectiveOutcome`, which are not those types, so there is no argument anywhere
   through which one could arrive at `decide_gate`. The boundary is the *decision*,
   not the *record*: `Case.family` and `Attempt.family` are data and do widen — see
   "What an elective case is" below, which is what makes the split above load-bearing
   rather than merely tidy.
3. **Gate-measured means the same arithmetic and the same bar, from one
   implementation of it.** `scorer.separation` is the per-family pass condition —
   `D ≥ discrimination_floor` **and** the two intervals apart — and both
   `score_family` and `score_elective` read it. One implementation and not two
   copies, because the tier's claim to being gate-measured is that the rule is the
   *same* rule, and a second `separate and reaches(...)` would only have to drift
   once. An elective family's cases accumulate a decay series and face the
   retirement rule like any others. **Selectable is not ungated.**
4. **The tier reports in its own section.** `GateResult.elective` sits beside the
   `GateDecision` and not inside it, and the gate document prints every declared
   elective family — measured with its figures, requested-and-unread with the reason,
   or **not requested** by name. That is [ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md)
   §6's discipline, that an exclusion prints in the decision, read one level down.
5. **Selection is a declared input.** `ElectiveSelection` is stated before a run and
   no measurement moves it, on the footing of `DeclaredModels` and the denominator the
   console may set ([ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md)).
   `not_requested` is derived from the declared set and never supplied by a caller.
6. **A fifth kind of nothing.** `payload.NotRequested` is a family this run was not
   asked to test — not a `CoverageGap`, not an `UntestedCategory`, not
   `not_measurable`, not `Withheld`. It serialises under its own key and renders under
   its own heading.
7. **A target report carries the tier's declared selection and its absences, and no
   figure at all.** An elective family's `D` is a claim about the bench and a report
   is a claim about a target ([ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)),
   so the figures print in the gate document, never in the measured section — which
   is keyed on `Family` and has no field one could arrive in. Both halves of the
   selection travel, because a run that requested every elective family produces no
   absence and a document that then said nothing about the tier would be
   indistinguishable from one made before the tier existed.
   **"A family whose discriminating power was never measured may not print in a
   signed report" is therefore enforced by there being nowhere for any elective
   figure to print, measured or not** — which is stronger than the rule asks and is
   why no measurement-linked check exists to forget.
8. **Promotion is three consecutive gate runs on the field holding the per-family
   rule, and it confers eligibility rather than entry.** `elective.PROMOTION_RUNS = 3`,
   declared in `elective.py` and deliberately not in `GateRule`. The bar each counted
   run held is `ElectiveOutcome.passes` — both clauses, read off the reading rather
   than re-derived — so promotion cannot be earned on readings the per-family rule
   refuses. Entry into the six is a library-version event that re-declares the gate
   rule **before** the run it applies to, and nothing in the code performs it.
9. **The promotion ledger is per family; the decay series is per case.** A
   `GateReading` is one per case per gate run and lives on `Case.history`, so the
   streak reads `ElectiveReading` — a family's whole `ElectiveOutcome` at one gate run
   — and never a case's counts. A family-level claim read off one case's reading would
   answer a question about a case and print it as an answer about a family, which is
   the conflation CONTEXT.md keeps **attempt**, **case** and **family** apart to
   prevent.
10. **Skipping an elective family is never advantageous**, and both halves are tests.
    A skipped gate run breaks the promotion streak, and a skipped gate run does not
    reset the retirement window.

## Why the type and not a flag

The shape a reviewer reaches for is one `Family` enumeration of nine members with a
`tier` property, or a `FamilyOutcome.elective: bool` checked wherever a count is
taken. Both put the invariant in the hands of every present and future call site,
and this codebase has already refused that trade once, at a sharper point: an
`AdaptiveEpisode` is not an `Attempt`, and
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) argues
that the guarantee is worth a second type because a boolean is only as good as the
last person who remembered to read it.

The consequence here is concrete and checkable rather than stylistic. `gate.family_rates`
loops `for family in Family`; `decide_gate` takes `Sequence[FamilyOutcome]` and a
`Mapping[Family, Reliability | None]`; `MeasuredSection` holds `Mapping[Family, NotMeasurable]`.
With two enumerations, **every one of those is closed against the tier by the type
checker**, and the only way to open it is to write a union into a signature — which is
a visible edit that a test asserts against, not a forgotten `if`. With one
enumeration and a flag, all of them are open by default and the tier's whole claim
rests on six-or-more call sites each doing the right thing.

The cost is real and is accepted: an elective family's cases will need `Case.family`
and `Attempt.family` to hold `Family | ElectiveFamily`, which is a widening on the
**record** — see the next section — and two scoring paths that share their
arithmetic and not their containers.

## What an elective case is, for the tickets that build one

#48, #49 and #50 each add a family with three cases and a reference-agent gradient.
The shape they land in follows from decision 2 and is decided here so that three
tickets do not each decide it differently:

- An elective family's case is an ordinary `Case` record. It has a payload, a success
  condition, an `external_id`, a `not_tested`, an admission reading and a decay
  series, and every one of those means the same thing it means for the six. There is
  no `ElectiveCase`.
- An elective attempt is an **attempt** in CONTEXT.md's sense — one execution of one
  case against one target, ten per case, the unit of the denominator. It is not a new
  unit and must not become one, because the tier's figures are only comparable with
  the six's if they are counted the same way.
- So `Case.family` and `Attempt.family` widen to `Family | ElectiveFamily` when the
  first elective case lands. That widening is on the record, where a family name is
  data, and it is safe precisely because the *deciding* containers do not follow:
  `TargetRun.rates` stays `Mapping[Family, Rate]` and an elective family's counts
  arrive in a second mapping keyed by `ElectiveFamily`. The type checker will demand
  that split at every site that groups attempts by family, which is the point.
- The **family-level** reading each gate run produces is an `ElectiveReading`, and it
  is what the promotion ledger is made of. A run that scores an elective family
  appends a `GateReading` to each of that family's cases, exactly as it does for the
  six, and builds one `ElectiveReading` for the family. The two are not
  interchangeable and neither is derived from the other here.
- The gate run record (`gate_record.py`) gains the elective figures in the same
  ticket that first produces one. It is not added here: a pydantic field on a wire
  contract that no run can fill is a field the console renders as empty and a reader
  reads as a bench that measured nothing.

## Why a skipped run must break the promotion streak

The two halves of the invariant pull in opposite directions, which is the whole
reason it needs stating.

The **retirement** half wants a gap to be invisible. Two low readings retire a case,
and if a gate run in between that the family did not run for reset the pair, an
operator could park a family out of the next few gate runs until its low reading went
stale. So the window must be transparent across the gap.

The **promotion** half wants the opposite. If the streak were counted over readings
alone, then a family that read high, was skipped on the run where it would have read
low, and read high again would show two consecutive good runs where it had one. That
pays an operator for skipping — which is exactly the reading PLAN §5 P2 flagged when
it observed that on a gate run the selection "is also a way to skip a family that was
about to fail".

The resolution is that the two rules are read over two different records, and the
difference is a type. The retirement rule is read over one case's **decay series**,
which holds `GateReading`s; a run the family did not face scores no case and writes
none, so the readings either side of a gap are neighbours and `retirement.window_of`
needs no change. The promotion rule is read over one family's **ledger of gate runs**,
which holds `ElectiveReading | Skipped`; `streak_of` stops at a `Skipped`, because a
run the family did not face is not a run it held the bar on.

`Skipped` is a type rather than a `None` or a missing entry for that reason: the same
fact must be countable in one rule and absent from the other, and a type is what
keeps those two readings of it from being one.

One further stop on the streak, and it is an existing invariant rather than a new
one: a reading that did not measure the field does not count
([ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md)) — a stub's
`D` is a statement about the fixture, and entering the six is a claim about the field.
It is not transparent, for the reason a skip is not: a stop that let the count
continue would pay a run for producing no evidence.

There is deliberately **no** fitness stop, unlike the retirement rule's
([ADR-0016](./0016-retirement-declines-on-a-family-unfit-to-report.md)). What
ADR-0016 declines on is a *judged* family below the κ floor, and every family in the
tier reaches its verdict by canary check — PLAN §5 P2 chose deterministic families
precisely so that `minimum_fit_families` is untouched. So there is no instrument for a
reliability figure to be about and no way for an elective reading to be unfit, and
`ElectiveReading` carries no flag for one. An elective family that is ever *judged* is
a decision needing its own ADR, and that flag is where it would land.

## Why three runs

Two is the number the retirement rule uses, and ADR-0003 argues why: one bad night
must not retire a working case. Entering the six is a **stronger** claim than
retiring one case — it moves the denominator of the gate's own decision rule, which
ADR-0015 fixed deliberately — so the bar has to be strictly harder than the bar for
removing one case, and three is the smallest number that is. It is also the smallest
number over which a streak is a trend rather than a pair.

The figure is declared in `elective.py` and not in `GateRule` for the reason `T` and
`k` are declared in `AdaptiveBudget`: `GateRule` holds the numbers that decide the
run in front of a reader, and `GateRule.stated` says so in those words. A promotion
threshold printed in the gate rule would read as a bar this gate run had to clear.

## Considered options

**One `Family` enumeration of nine, with a tier property.** Rejected: it makes every
count, mapping and loop over families open to the tier by default, and the guarantee
becomes a property of call sites rather than of types. It is the option ADR-0010
already refused one level up.

**A `GateRule.elective_family_count`, with the counts as fractions.** Rejected twice
over. ADR-0015 shows that fractions of a moving denominator pay a run for degrading
its own instrument, and a rule that named the tier at all would make an elective
family's reading part of the bar the gate prints.

**Promotion performed automatically when the streak is met.** Rejected: entry
re-declares the rule the bench is held to, at a new library version, and a rule that
changed because a counter reached three would be a threshold moved by a measurement —
the hour-30 move ADR-0003 exists to prevent, arriving from the other direction.
`Standing.eligible_to_enter` is therefore eligibility, and a human writes the ADR.

**An elective family reported nowhere until it is promoted.** Rejected: it would make
the tier unfalsifiable. A family measured on every gate run and printed nowhere is a
family whose discriminating power nobody can check, and the promotion streak would be
a claim about readings a reader cannot see.

**Elective figures in the target report beside the six.** Rejected on ADR-0018: `D`
is a claim about the bench, a band is a claim about a target, and a reader given both
in one table will read the first as the second. The report says which elective
families were not requested and nothing more.

**A sixth absence for *requested and never measured*.** Rejected as a type and kept
as a derived line. It is not a new kind of nothing: the family *was* asked for, so
`not_requested` is the wrong answer, and it has no reading, so no figure may print —
which is a fact `ElectiveSection.requested_and_unmeasured` states without a fifth
enumeration member for a reader to tell from the other four.

**`ASI05` unexpected code execution as a third member.** Not decided here. PLAN §5 P2
named it alongside `ASI06`, and #42's selection replaced that pair with three other
families. A member of `ElectiveFamily` is a family the bench can be asked for, so it
is added by the ticket that gives it cases and a reference-agent gradient, and no
ticket does that for `ASI05` today.

## Consequences

- The six stay mandatory and keep the gate. No number in `rule.py` moved, and the
  printed rule says nothing about the tier.
- Every target report gains a `not_requested` block naming three families, and the
  golden rendering digest moved once, on purpose, in the diff that added it.
- The tier has no production caller yet, and that is the same order ADR-0003 chose
  when it fixed the gate rule before the code that evaluates it existed. What exists
  is the rule, its types and its tests; what arrives with #48 is the first family
  that can be requested.
- `docs/validation.md` records, in *what has never been validated*, that no elective
  family has ever been measured — the tier's own figures are a mechanism exercised in
  the suite and nothing more.
- The promotion streak is readable only from a ledger a caller assembles. The gate run
  record gains the fields that make one recoverable from disk in the ticket that first
  writes an elective reading into it, and until then a streak can be read but not
  recovered. Stated rather than left to be discovered.
- `scorer.Separation` and `scorer.separation` are new and shared. `score_family`
  behaves identically; what changed is that the per-family pass condition now has one
  implementation instead of one plus a copy.
