---
status: accepted
---

# Entry into the six is a decision, and not a counter

[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) decided the
elective family tier: a second closed set of names, measured on the gate's own
arithmetic against the same floor, reporting in its own section, deciding no gate.
All of that stands, and this ADR does not touch it.

Its decisions 8, 9 and 10 also gave the tier a **promotion streak** — three
consecutive gate runs on the field holding the per-family rule made an elective
family *eligible to enter the six*, read over a ledger of `ElectiveReading | Skipped`
by `streak_of`, and reported as a `Standing`. **That half is superseded here and the
machinery is removed.** ADR-0035 is not edited: it decided what it decided, on the
evidence it had.

## Decision

**No rule in this project says when an elective family may enter the six. Entry is a
decision a person takes, argues in an ADR, and writes into a library version.**

1. `elective.PROMOTION_RUNS`, `LedgerEntry`, `ElectiveReading`, `Skipped`,
   `streak_of`, `Standing` and `standing_of` are deleted, with their tests.
2. Nothing else in `elective.py` moves. `ElectiveSelection`, `ElectiveOutcome`,
   `score_elective`, `ElectiveSection` and `NOT_GATE_DECIDING` are what the gate
   uses, and the per-family reading printed on every gate run a family was requested
   for is unchanged.
3. `scripts/gate.py`'s `--elective` help no longer promises that a run it is not
   given counts toward no streak, and the printed elective block says what it said
   minus that clause. A family requested and unread still prints, and still says it
   has no `D` on this run.
4. **Nothing about the gate decision changes.** Six families, 4 of 6 passing,
   monotonicity on 5 of 6, and an elective family in neither count.
5. `test_the_promotion_streak_is_not_in_the_tier` is the tripwire: it fails if any of
   the seven names returns to the module, or if the word *streak* returns to what the
   tier prints, and it names this ADR in its message.

## Why the rule was not worth its machinery

**Nothing in `elective.py` ever promoted anything.** ADR-0035 was explicit about
that: `Standing.eligible_to_enter` conferred eligibility, and entry was a
library-version event that re-declares the gate rule *before* the run it applies to.
So the streak was never a mechanism. It was **evidence offered to a human decision**,
and it was the only thing the ledger, the two entry types and `streak_of` existed to
produce.

The decision it informed already carries a far heavier precondition.
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) fixes
the gate at 4 of 6 passing with monotonicity on 5 of 6, and
[ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) spent its whole
argument on why those are counts over a **fixed** six. A seventh scored family means
new counts — argued, declared before the run, and written down — whatever the
promoting family's reading history looks like. A streak is a precondition bolted onto
a decision that cannot be taken without re-opening the gate rule itself.

And the evidence the streak summarised is not lost with it. Every reading an elective
family ever took is on its case records as a decay series and in
[docs/validation.md](../validation.md) as a dated entry. A person arguing for entry
reads those. What is gone is a single integer standing in for them.

## What is given up, stated plainly

**The phrase *skipping is never advantageous* loses one of its two halves.** ADR-0035
named that invariant and proved both: a skipped gate run broke the streak, so
skipping bought no progress, and a skipped gate run did not reset the retirement
window, so skipping bought no protection.

The second half is untouched and is still a test — the retirement window is read over
a case's decay series, a run that scored nothing writes no `GateReading`, and two low
readings retire a case whatever happened between them
([ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md),
`retirement.window_of`).

The first half is now vacuous rather than false: with no streak, skipping a family
for ten gate runs and then requesting it once is no worse than requesting it every
time, because **nothing is earned by requesting it**. The readings inform a human
decision instead of accumulating toward an automatic one, so there is no progress for
a skip to withhold. That is why the loss is acceptable and not merely tolerated.

**One reservation, recorded rather than argued.** If entry into the six ever becomes
routine, the thing standing between a family and entry on one good reading will be
reviewer attention rather than a rule. The protection was removed deliberately, and
what replaced it is the ADR a person has to write and someone has to read. A later
reader who finds that insufficient is looking at a decision this ADR made knowingly,
and the answer then is a rule argued against the practice of the time — not this one
restored because it was here first.

## Considered options

**Keep the streak and stop printing it.** Rejected: it would leave the ledger, the
two entry types and `streak_of` in the module with no reader at all, which is the
machinery without even the evidence it was for.

**Keep `ElectiveReading` alone, as the family-level record of a gate run.** Rejected,
and it is the closest call. The type is genuinely well argued — ADR-0035's decision 9
keeps a family-level claim off one case's counts, and that distinction is real. But
nothing assembles a ledger of them: the gate run record already carries
`ElectiveFigures` per family per run (`gate_record.ElectiveTier`), which is the
recoverable, on-disk form of the same fact. A second in-memory record of it with no
consumer is a record that drifts.

**Lower the bar to two runs instead of three.** Rejected: it argues about the size of
a precondition whose whole existence is the question. Three was the smallest number
strictly harder than the retirement rule's two, and that argument was sound — it just
answers "how long a streak" rather than "why a streak".

**Promote the three families now, so the tier has a route in.** Declined on
2026-09-07 on its own grounds and recorded here because it is the question this one
invites. It would give the gate a denominator that changes with a flag, and
`memory_poisoning` reads `D = 0.33` against a 0.40 floor — so it would hand the gate a
failing family on day one.

## Consequences

- The elective tier is now exactly what its name says: families the bench can be
  asked to measure, measured on the gate's arithmetic, deciding nothing. There is no
  second rule in it.
- `PLAN.md` §5 P2's *promotion, not accretion* paragraph and the promotion half of
  its *skipping is never advantageous* paragraph are superseded, and say so.
  [docs/specs/elective-family-tier.md](../specs/elective-family-tier.md) stories 4,
  16, 19, 20, 21 and 26 are superseded by this ADR; the spec is a record of what was
  built and is not rewritten.
- `docs/validation.md`'s standing entry that the streak *can be read and cannot yet be
  recovered* is closed by removal rather than by a run — the honest resolution of a
  mechanism exercised only in the suite.
- The risk ADR-0035 named — that interesting attacks accumulate in a tier nobody has
  to pass while the six drift toward trigger 1 — is unchanged by this ADR. It was
  never the streak that answered it; a person deciding to move a family is. What is
  removed is the appearance of an answer.
