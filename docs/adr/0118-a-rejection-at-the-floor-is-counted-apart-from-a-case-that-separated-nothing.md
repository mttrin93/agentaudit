---
status: accepted
---

# A rejection at the floor is counted apart from a case that separated nothing

`RejectionKind` is the closed set of ways a decided proposal can come out, and
[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)
counts its members apart because a discard is a finding in its own right. Five members carried two readings that mean
opposite things under one name.

A proposal that cleared nothing landed on `SEPARATED_NOWHERE`, which says *a finding
about the case rather than about any model*. That is true where the three reference
agents engaged and did not separate: the case is weak, and the refusal is what the
bar is for. It is false where the trivial agent was never broken at all. Then the
probe reached nothing, the success condition could not fire, and the refusal is a
statement about the run's equipment rather than about the case.

#234 measured the population. Five consecutive rejections in the live queue, three
families, four targets, every one at `trivial 0.00`, and one of them recording a live
target that called a tool after an explicit stop signal — a true positive discarded
as a dud case. The cause is structural rather than incidental: the reference agents
route tools by literal case-folded substring, a route the adaptive layer finds against
a customer's agent is composed in *that* agent's vocabulary
([ADR-0107](./0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)),
and the bar then grades it against equipment that speaks a different dialect. The same
ticket measured the control: `scope-creep-004`, written in the bench's own dialect
against the same equipment, was admitted at `D = 1.00` the same day. The equipment is
fine; the dialect is the variable.

## Decision

1. **A sixth member, `FLOOR_AT_ZERO`**, counted by `CrossModelRejections` on the same
   denominator as the other five. Every decided proposal still lands on exactly one
   member, so the counts still sum to the proposals decided.

2. **It narrows `SEPARATED_NOWHERE` and nothing else.** `kind_of` reads it inside the
   branch it is a subset of: a proposal that cleared a reading anywhere cannot land on
   it, whatever its floor did on the other model. The claim the member makes is *the
   probe reached nothing here*, and one model where it reached something disproves it.

3. **The threshold is no success at all — every agent at zero, on every reading.** Not a configurable
   rate below some floor. Two reasons. The kind has to mean *nothing happened* for an
   operator to act on it by rewriting a probe, and at the declared ten attempts a rate
   "below a floor" is one success away from a case the bar should simply refuse as
   weak — the reading engaged, and `SEPARATED_NOWHERE` is the honest name for it. And
   a threshold is a declared quantity somebody has to be able to check a decision
   against ([ADR-0003](./0003-gate-decision-rule-and-sample-size.md)); a second
   tunable beside `discrimination_floor` would be a number the gate's reader has to
   hold in their head to know which of the two refusals they are looking at. Zero is
   checkable from the counts the record already prints.

   All three agents rather than the trivial one alone, because the claim the member
   carries is *this probe reached nothing here* and one success anywhere disproves it.
   A reading at `trivial 0/10, hardened 3/10` is noise against three agents that share
   a router, and it falls back to `SEPARATED_NOWHERE` — which is not a good name for
   it either, but at least says something engaged. The predicate is
   `ReadingOutcome.engaged`, beside the counts it is read off.

4. **A refusal names which refusal it was, on `AdmissionOutcome.stated()`.** One line
   rather than one per surface: the gate's reading, a promotion's lines and the reason
   a rejected row carries on `/pending-routes` all print an outcome through it, so an
   operator reading any of the three can tell *your probe never reached the equipment*
   from *your case is weak*. The counts alone say how many of each there were and not
   which proposal was which.

5. **The admission memory still holds it** (`decided.MEASURED_THE_ROUTE`,
   [ADR-0032](./0032-the-admission-memory-holds-the-measurement.md)). This was the
   close call. The member's gloss says nothing was learned about the *case*, which
   reads like the two members the memory refuses — `UNREAD` and `NOT_MEASURED`, both
   of which are measurements that did not happen. But this one did happen: the three
   agents were run the full denominator and returned what they returned, and what they
   returned is reproducible, because the equipment is scripted and the probe is fixed.
   Excluding it would make every re-proposal of the same dead route pay for the same
   thirty attempts again, which is the cost `decided.py` exists to stop. Relabelling a
   refusal must not silently change what the bench pays for.

   The constant ADR-0032 names `ABOUT_THE_ROUTE` is renamed `MEASURED_THE_ROUTE` here,
   because the line it draws is whether the measurement happened and two of its four
   members are refusals that conclude nothing about a route. ADR-0032 is not edited:
   its decision — that `UNREAD` and `NOT_MEASURED` are not remembered, and that the
   set is a frozenset so a new member has to be classified rather than default into
   the memory — is unchanged, and this is where the name moved.

   A record filed under the old label is not migrated. `recall` already answers
   `Stale` where "the same counts now decide X where the run that measured them
   recorded Y", so a floor-at-zero route remembered as `SEPARATED_NOWHERE` is measured
   again once and re-filed under the kind the current arithmetic reaches.

## What this does not do

It does not widen the reference agents' phrase router. A scripted router is what makes
the verdict a fact rather than a model's mood, and trading that away is a separate
argument from being able to see the problem.

It does not give the refused route anywhere to go. The bar is not wrong to refuse
these routes — it asks about generality and they do not have it — and this ADR only
stops the bench asserting something false about them. The exit is
[ADR-0117](./0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md),
which this has to land before: the per-family count of floor-at-zero rejections is
what says how large the held-route population is, and that count does not exist until
the sixth member does.

It does not count the member per family. The population is concentrated in the
trace-read families — `scope_creep`, `halt_defeat` and the fetch half of
`indirect_prompt_injection` read a trace the scripted router produced, while the
reply-read families read what a real model said and are vocabulary-insensitive — and
that split is the reason the count is worth having. But an `AdmissionOutcome` carries
a case id and not a family, and the family a proposal belongs to is on the record
beside it (`promotion.proposal.case.family`). Counting per family is ADR-0117's
series, filed there rather than plumbed through admission's arithmetic for a number
nothing yet reads.

## Consequences

The gate's reading and `/pending-routes` gain one line each and the counts block gains
one row. A rejection that used to read as a finding about the case now says which of
the two it was, so an operator can tell a probe worth rewriting from a case worth
dropping. Nothing scored moves: admission is not a scored rate
([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)), and
no proposal's admitted/rejected answer changes — only the name the refusal prints
under.
