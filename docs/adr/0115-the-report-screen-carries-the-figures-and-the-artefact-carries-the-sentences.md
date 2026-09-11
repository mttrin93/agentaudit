---
status: accepted
---

# The report screen carries the figures, and the artefact carries the sentences

Four ADRs put a sentence on the report screen, each for a good reason and each without
anybody counting what was already there.
[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
asked that a reader be able to tell a fix written against precedent from one written
against nothing, so `informed_by_stated` was drawn under every finding.
[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) and
[ADR-0071](./0071-a-finding-points-at-a-file-the-bench-read.md)
put the source anchor and its sentence there.
[ADR-0070](./0070-a-signed-document-may-carry-a-remediation.md) §2c put the statement
standing where a withheld sentence was, and §4 put the reading's own name above the
section. [ADR-0073](./0073-two-labels-on-a-fix-and-no-third.md) §4
put what a label on a fix asserts. Each is one line. Together they are eight lines of
standing under every finding, three findings to a family, above a block of two
paragraphs — and the thing an engineer opened the page for, *what broke and what to
change*, was below all of it.

## Decision

**The screen draws the figures and the blocks. The sentences travel in the artefact.**

1. **What the screen keeps.** The per-family table — rate, interval, band, refs — and,
   under *Failures and fixes*, one block a finding: the case, the fix's label as a
   word, *what went wrong* and *what to change*. The label stays because *proven* and
   *proposed* are the one pair a reader must not confuse, and the sentence over the
   section says a fix reads proven only where the bench re-attempted the case, so the
   word that points at has to be on the page (ADR-0073 §4).

2. **What moves to the artefact alone.** The reading's own name, what the failure was
   attributed to, the exposure and the identifier, what informed the fix, whether the
   two instruments disagreed, what was withheld, the source anchor and its sentence,
   and what a label asserts. **None of them leaves the payload.** Every one is on
   `FindingReading`, every one is the payload's own sentence, and every one travels in
   the `report.json` and the `report.md` a recipient reads — which is the document this
   project exists to produce, and the one that has to account for everything.

3. **The three paragraphs over the section become one line.** `WHAT_THIS_SECTION_IS`
   keeps all three claims a reader needs standing over any block: a model wrote these
   sentences and would not write them again, no figure above was measured from any of
   them, and *proven* is a claim about one case against one patched revision.
   `A_MODEL_WROTE_THESE_SENTENCES` and `WHAT_A_LABEL_ON_A_FIX_ASSERTS` are still built
   and still tested; what changed is that the screen states them once.

4. **Where each claim is checked did not change, only over what.** The sentences are
   asserted over the reading in `report.test.ts`, against the same served fixture the
   walkthrough uses. What the end-to-end specs assert is what the page draws. A claim
   with no test anywhere would be this decision going wrong, and none is.

## What this costs, stated

A reader holding **only a screenshot** of the report screen can no longer tell a fix
written against precedent from one written against nothing, cannot see where in their
source the failure sits, and cannot tell which of the four readings the section is
under. That is a real loss and it is the price: the sentence ADR-0070 §4 was protecting
against — four readings that render alike — is now protected in the document rather
than on the page, and a screenshot is not the document. The artefact is what a
recipient is handed, it is what is signed, and it says all of it.

## What this does not decide

That any of it may leave the payload. Every sentence above is in the signed document
and this ADR is the reason to keep it there rather than a step towards dropping it: a
screen that stopped drawing a fact is a screen, and a document that stopped carrying
one is a different claim (ADR-0008, ADR-0017).

Nor does it decide anything about the run screen, the gate screen or the console. The
question here is one section of one page and the reason it was crowded.
