---
status: accepted
---

# The Rule of Two block is shortened and says the same things

[ADR-0038](./0038-the-agents-rule-of-two-is-read-off-a-declaration.md) decided that
the Agents Rule of Two is read off the operator's own declaration and reported as a
declaration, and its decision 5 is about the ordering of the five arms.
[ADR-0092](./0092-the-rule-of-two-is-declared-on-the-register-walk-and-the-reading-is-the-backends.md)
put the four questions on the register walk and kept every word of the reading in
`scanner.py`, so that no screen words it.

Neither decided how long the block is. It grew to four hundred and ninety characters
on the arm a reader meets most — a target that declared nothing — and the register
walk prints the same block while the questions are still being answered. An operator
answering four radio buttons met a paragraph; a report's reader meets it beside a join
whose rows point at verdicts.

## Decision

**Every part of the block is shortened, and no distinction is dropped.** What came out
is restatement. What stays is every fact one of the five arms, the three keys or the
signature's reader turns on.

1. **The four keys stay, and print on every arm.** `declared:`, `declared absent:`,
   `not stated:`, `supervision:` — a block naming only what was held would leave a
   reader unable to tell a property declared absent from one nobody was asked about,
   which is the distinction the record exists to keep (ADR-0038). The capability names
   stay as the wire spells them, so a reader can match a name here to a field of
   `declared.rule_of_two`.

2. **The supervision answer is three words and no longer a clause.** *not stated*
   rather than *nobody said whether a human confirms what it does*: the key in front of
   it already asks the question. It stays a third answer and never a silence to be read
   as *unsupervised*, which is what `Supervision` has three members for.

3. **Each arm keeps the clause it is read on and loses its gloss.** *not declared, so
   the rule was not read, and nothing was attempted against it* keeps both halves a
   reader acts on and drops locating the absence on a side of a boundary. *At most two*
   keeps why one declared-absent property settles the reading. *Partly declared* keeps
   that the shape could be either and that the bench never infers one. *All three,
   unsupervised* is untouched: it is the arm that reads most like a finding, and the
   shortest one already.

4. **`NOT_A_MEASUREMENT` keeps three claims and loses the fourth.** Nothing was sent,
   no verdict lies behind it, it is not a finding. *No attempt was made against it* was
   the second of those said twice — a verdict is what an attempt would have produced —
   and the one arm where an attempt is worth naming in its own right names it.

5. **The digest moves and the artefact version does not.** Every report carries this
   block, so `GOLDEN_ONE_FAMILY` moves in the same commit, with the reason written
   beside it (ADR-0017). The block is prose: no key moves, no figure moves, and nothing
   in it is re-derived by a verifier, so a version-2 verifier reads a document issued
   after this change exactly as it reads one issued before it.

## What this does not decide

That a screen may word the reading. It may not: `scanner.py` is still the one place the
five arms and their sentences exist, and ADR-0092 decision 4 stands. What changed is
what that one place says, for the report and the register walk alike.

## The reservation

A block that has been shortened once is a block somebody will shorten again, and the
next pass is the one that takes a distinction with it — the three keys are the obvious
target, because two of them print *none* on the arm a reader meets most. They are
listed in decision 1 for that reason. The floor is that a reader can tell the three
absences apart and can tell all of them from a finding.
