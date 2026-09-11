---
status: accepted
---

# The run screen shows a live per-family rate

[ADR-0005](./0005-no-composite-risk-score.md) refused a composite risk score and
prescribed what replaces it: **per family**, a failure rate with its Wilson 90%
interval, its verdict class, κ where judged, and a band. A per-family rate is therefore
the shape this bench reports in, and not something it withholds.

What it says nothing about is a rate on the screen a person watches a run on. That
screen carried two counts per family — attempts made, and how many of them the target
let through — and left the reader to divide them.

## Decision

**A family's row on the run screen carries the share of its answered attempts that the
target let through.** It is a reading of the run, and the measurement is still the
report's.

1. **Per family, over that family's own denominator.** Six rates over six denominators
   are six figures. Nothing sums this column and there is nothing under it to sum into:
   the mean of them is the composite ADR-0005 exists to refuse, and the run screen's one
   spanning figure is a count of attempts made (ADR-0110), which this column is
   deliberately not.

2. **Over `attempted` and never over `of`.** A rate taken against the plan would count
   attempts nobody has made yet as attempts the target held — the one direction a live
   figure must not be wrong in, because it flatters the target.

3. **Absent until an attempt comes back.** `—` and never `0%`, on the terms
   `succeeded_attempts` is already `null` for: a family attempted no times has not been
   let through zero times.

4. **It is a point estimate and it is not the measurement.** No interval, no band, no
   verdict class, over a denominator that is still moving — which is precisely what
   ADR-0005 §3 says a rate without its interval loses. The figure a recipient is handed
   arrives on the report, where the denominator has stopped and the interval, the class
   and the band arrive with it. The two live one screen apart on purpose: this one
   answers *how is it going*, and that one is the evidence.

## What this does not decide

That the figure may be given a band, a colour scale, or any mark ranking one family
against another. The band is where a composite gets rebuilt (ADR-0005), its cut points
are the reference agents' constructed rates (ADR-0014), and neither is a thing a live
reading over a moving denominator has any claim to.

## The reservation

A percentage on a screen is the most screenshot-able object this project makes, and
this one has no interval beside it. The guard is that it is per family and that the
denominator it was taken over is printed in the column to its left — a reader who can
see `3 / 50` beside `0%` can see what the figure is worth. If that pairing is ever
broken, this is the decision that put the number there.
