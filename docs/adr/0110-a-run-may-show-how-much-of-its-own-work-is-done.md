---
status: accepted
---

# A run may show how much of its own work is done

The instrument's line, on the front door and in the README, is that AgentAudit
"reports each family over its own denominator: a rate, an interval and a band each,
and **no total across them**"
([ADR-0005](./0005-per-family-rates-no-composite-score.md)). The run screen was built
against it literally: nothing on that screen spanned the six families, and a person
watching an hour-long run could see how far each family had got and never how far the
run had.

## The distinction this turns on

ADR-0005 is about **rates**. Its argument is that a rate has a denominator of its own,
that six denominators are six different things, and that a mean over them is a figure
no family was ever measured at — which is how a composite score gets built and how a
reader ends up comparing two agents on one number.

A progress bar is not that. Attempts **made** over attempts **planned** are two counts
of what this bench has done. Neither is a reading taken against the target: the plan is
known before a single call goes out, and the numerator moves as the bench works,
whatever the target answers. No verdict is in either of them.

That is the same line [ADR-0108](./0108-a-family-row-states-what-the-library-holds-for-it.md)
drew for the case counts on the bench page — a property of the bench is admissible
where a reading against a customer's agent is not — applied to a run instead of a
library.

## Decision

**The run screen shows how much of the scored layer's plan has been attempted, as a
bar and as its two counts.**

1. **The numbers are counts of work, never a rate.** Attempts made over attempts
   planned, summed across the six. The families' rates are still never added, and
   nothing on this screen divides a verdict count by anything: how the target is
   answering is the per-attempt cells in the table, one cell an attempt, under a legend
   that names the four states.

2. **The bar is drawn in the scored layer's colour and in neither verdict colour.** A
   bar filling green into red at the head of the screen would be exactly the reading
   this ADR says it is not, whatever the prose beside it said.

3. **The six alone, and the scored layer alone.** The elective tier is a second closed
   set this app concatenates nowhere (ADR-0035 §2), so a bar over nine would have a
   denominator built out of both. The adaptive layer counts in episodes and turns, and
   no adaptive quantity may reach a scored one (ADR-0010) — its position stays on its
   own line in its own units.

4. **A family the plan dropped contributes nothing to either number.** Its `of` is zero,
   so a run that is not attacking a family is not a run that is behind on it.

5. **The percentage is rounded down.** A run at 99.6% of its plan has not finished, and
   *100%* over a bar still moving is the one reading this line must not give.

## What this does not decide

That a report may carry it. A signed report is a document about a target, and how much
of the bench's plan ran is provenance rather than a figure a recipient reads — the
report already states the denominator each family was measured on.

Nor does it admit a **cost** or a **call count** spanning the layers. One blended call
figure hides which half of the run is spending the operator's budget (ADR-0007), and
that remains two figures on two lines.

## The reservation

This is the first figure on any screen whose denominator spans the six families, and
the argument for it — *these are counts of our own work* — is exactly the argument
somebody will reach for next time. The guard is decision 2 and the noun: the line reads
*20 / 30 attempts*, and the moment a figure over this denominator is a count of
**verdicts** rather than of attempts made, it is a rate over six denominators and
ADR-0005 refuses it. The word *attempts* is doing that work alone — a caption saying
what the fraction was over stood under the bar and came off — so a screen that drops
the noun has dropped the guard with it.
