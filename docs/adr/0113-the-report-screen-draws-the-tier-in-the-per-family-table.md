---
status: accepted
---

# The report screen draws the tier in the per-family table

[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) made the elective
tier a second closed set that decides no gate.
[ADR-0088](./0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)
then admitted the half that *is* about the customer: an elective family's rate against
their target, with its interval and its band, is a fact about that target and belongs on
that target's report.

The screen drew it in a section of its own, under a heading saying the tier decides
nothing, with the payload's sentence about the request and a line per family nobody
asked for. On the common run — every run that requested none of the tier — that was a
heading and four paragraphs of *not requested*, and on a run that did request one it
was a card in a second place a reader had to compare against the table above by eye.

[ADR-0091](./0091-the-console-draws-the-nine-families-as-one-list.md) has already
decided this shape once, for the bench page's switches: **the presentation merges and
the types do not.**

## Decision

**A requested elective family is a row of the per-family table, beside the six.**

1. **Two arrays, two maps, and nothing concatenates them.** `ElectiveReading.measured`
   stays its own list of its own type, `rows` stays keyed on the six, and
   `TheElectiveFamily` takes only the elective record — there is no signature on this
   screen that accepts either, which is what keeps a seventh family out of the six's
   arithmetic (ADR-0015, ADR-0035 §2).

2. **Nothing sums a column and nothing says which list a row came from.** Six rates over
   six denominators were already six figures (ADR-0005); a seventh changes nothing about
   that, because the table has no total and no cell for one.

3. **No refs and no `D` on an elective row.** An elective label makes no coverage claim
   and reaches no report (ADR-0044), so that column is empty rather than filled with
   something composed here. The bench's discriminating power on the tier is a claim
   about the bench and is stated in the gate run's own document (ADR-0018).

4. **The absences leave the screen.** The sentence about the request, the families
   nobody asked for and the ones this target could not answer are still served, still
   typed and still tested, and they travel in `report.json` and in the `report.md` a
   recipient reads — the document that has to account for every family (ADR-0094). A
   screen an operator watches their own run on is not that document.

## What this does not decide

Anything about the signed artefact. `rendering/` keeps the tier in its own section with
its own statement, the payload keeps two lists, and a recipient's copy is unchanged.
This is a decision about one screen.

## The reservation

A reader of this table cannot see which row is elective, and the two differ in things
that are not on it: the tier defaults off, costs the operator's endpoint what any family
costs, and decides no gate. That is the cost ADR-0091 accepted for the switches and it
is the same cost here, paid for a reader who can compare nine rates by running an eye
down one column. What protects the arithmetic is the types, as it was before.
