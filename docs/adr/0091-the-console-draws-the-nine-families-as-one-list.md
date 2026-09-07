---
status: accepted
---

# The console draws the nine families as one list

[ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) fixes the gate's
denominator at six. [ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md)
decided the elective tier beside it, and its decision 1 drew a consequence for the
console:

> a screen offering nine rows in one list would be offering a denominator this bench
> does not have.

The bench page followed that literally: two sections, two headings, two definition
lists, and two paragraphs of prose explaining what the second one was. **This ADR
reverses the presentation half of that consequence and nothing else.** The console now
draws one list of nine rows, undifferentiated — no second heading, no badge, no tier
column, nothing on a row that says which of the two closed sets it came from.

## What the old arrangement actually cost

The two-section split was argued as a protection against a reader inferring a
denominator of nine. What it produced was a screen on which the *tier* was the loudest
thing in the region: a heading, a served caveat, and a hand-written paragraph, against
six families that got one sentence each. An operator arriving to answer **which of
these will the next run cover** met three paragraphs about a tier they had probably not
asked for before they reached the six that decide the gate.

The denominator that inference was protecting is not read off this screen. It is read
off the report, where an elective family prints in a section of its own with its own
statement (ADR-0088 §4), and off the gate document, where the tier is in neither count
(ADR-0035). Nothing on the bench page states a denominator at all — it states a
selection, and a selection of nine things from two sets is still a selection.

## Decision

**One table, nine rows, no mark distinguishing the tier.** Four columns: the switch
with the family's name, what the failure is in a sentence, the OWASP entries the family
claims, and the EU AI Act articles it bears.

1. **The presentation merges and the types do not.** `Family` and `ElectiveFamily` stay
   two closed sets, `Tuning.families` and `Tuning.elective_families` stay two arrays,
   `PUT /bench/settings/families` still takes both as one statement of two lists, and
   `LABELS` and `ELECTIVE_LABELS` stay two tables with two accessors. `FamilyRow.tier`
   exists so the switch knows which array a move writes to, and **is drawn by nothing.**
   Every invariant ADR-0035 carries is carried by a type; none of them was ever carried
   by a heading.

2. **The behaviour behind the identical rows is not identical, and that is accepted
   deliberately.** The three still default off, still cost ten attempts per live case
   on the operator's endpoint, still decide no gate, and still print on the report as
   *not requested* rather than as a rate of zero. A reader of this screen cannot see
   which rows those are. That is the cost, it is real, and it is paid for a region an
   operator can read in one pass.

3. **The two prose blocks are gone from the screen.** The hand-written paragraph under
   the old heading, and the served `Tuning.elective_statement` beneath it. The served
   field stays on the route and stays tested, on `families_off_statement`'s terms —
   the bench's own sentence about what requesting one buys is still built, and this
   screen is not the only thing that could ever print it.

4. **The labels are served, not retyped.** The columns are new to this screen and the
   data is not: `labels.py` declares them, and a second copy in TypeScript is the drift
   that module exists to prevent — ADR-0036's edition tag being exactly what a hand copy
   loses. So `FamilyCovered` carries the label, and `elective_label_for` exists because
   `ELECTIVE_LABELS` now has a reader outside its own table.

5. **No figure in any column.** Not a rate, not an interval, not a band, not a `D`. The
   screen says what the nine *are* and what they are read onto; how a target answered
   one is the report's business (ADR-0018), and how well this bench discriminates on an
   elective family is the gate document's (ADR-0035, ADR-0088).

## What this does not decide

Whether the three should be promoted into the six. That is
[ADR-0087](./0087-entry-into-the-six-is-a-decision-and-not-a-counter.md)'s subject and
was declined on its own grounds; a shared table on one screen is a layout and argues
nothing about a denominator.

## The reservation

If an operator ever ticks an elective family without meaning to and is surprised by the
bill or by a report section they did not expect, this is the decision that let them. The
protection that remains is the tick's own default — off — and the run's declared budget,
which prices the selection before anything is sent. Worth revisiting if that turns out
to be thin.
