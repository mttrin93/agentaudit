---
status: accepted
---

# A refused break is held against the target it beat, and is scored beside the six

The admission bar is the only way a route becomes a case, and a case is the only
thing the scored layer sends. Both sentences are load-bearing and neither is edited
here. What they compose into is a dead end this ADR opens one exit from.

A route the adaptive layer finds against a customer's agent faces the single-model
bar ([ADR-0107](./0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)),
and the bar asks whether it separates three agents of known construction. That is a
question about **generality**, and it is the right question for the case library,
which is the shared instrument every target is measured with. Most
customer-discovered routes fail it, and #234 measured why: the reference agents route
by scripted phrase, a probe composed against somebody else's agent is written in that
agent's vocabulary, and the equipment never engages — five consecutive rejections at
`trivial 0.00`, concentrated in the trace-read families.

One of those rejections recorded a live target calling a tool **after an explicit
stop signal**. That is a real defect in a real agent, confirmed by this bench's own
deterministic evaluator, and it was discarded as a weak case.

The bar was not wrong. The route is not general and does not belong in the shared
instrument. What is wrong is that a refusal at the bar is also the deletion of the
finding, because the case library is the only place a route may live.

**#234 is the label and this is the exit.** That ticket separates *the equipment never
engaged* from *the case is weak*, which stops the bench asserting something false
about a route. It gives the route nowhere to go, and says so itself: "a true positive
recorded as a finding about the probe is worse than no reading."

## Decision

Six parts.

1. **A target library.** A per-target set of confirmed routes the bar refused, held
   against the target they beat, keyed by `decided.RouteKey` scoped to that target.
   It is **not** the case library: `load_library` does not read it, it is not in the
   library digest, and no other target ever sees it. A target library entry is a
   **held route** and it is its own type — not a `Case`, the way an `AdaptiveEpisode`
   is not an `Attempt` ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)).

2. **A person is the door, and the gate is not.** A held route faces no `D`, because
   `D` is a measurement against the three reference agents and the defining property
   of this population is that those agents cannot read its probe. What it faces is
   what it has already passed: an evaluator-confirmed break against the target
   ([ADR-0106](./0106-a-confirmed-break-files-its-route-and-an-unbroken-episode-proposes-nothing.md)),
   and a named operator's approval on `/pending-routes`, the surface built for
   deciding a pending route ([ADR-0105](./0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)).
   This is proportionate because the claim is small: **this probe produced this
   verdict against this agent, and here is whether it still does.** No generality is
   asserted, so no generality is measured.

3. **One route takes one door.** The same approval answers two questions — *is this
   everyone's?* (the bar, unchanged, writing to the case library per
   [ADR-0033](./0033-an-admitted-route-is-written-into-the-library.md)) and *is this
   still yours?* (the operator, writing to the target library). A route the bar
   **admits** is not held, because a library case is already sent to every target
   including this one; holding it as well would send one probe twice and count it on
   two denominators. The target library holds exactly the confirmed breaks the bar
   refused.

4. **Scored, automatic, and fenced.** Held routes are sent on **every** run of that
   target, not on selection, and are judged by the same deterministic evaluator as
   any case ([ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md)). Their
   verdicts are their own type on their own denominator and may reach **no** family
   rate, no interval, no `A_break`, no band, no gate decision and no figure about the
   bench. The report gains one block — held, still open, closed — and nothing else
   moves. The fence is carried by the type, so a signature that had to widen to
   accept both is the signal to stop.

5. **Retirement at two clean runs.** A held route that does not break the target on
   two consecutive runs is closed and stops being sent, on the window
   [ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md) already
   declares rather than a second number. A closed route is kept, with the run that
   closed it, and a closed route that breaks again reads as a **regression** and not
   as a new finding. A run that could not reach the target, or whose criterion the
   evaluator could not read (`measurability.checkable`), counts no clean run.

6. **The store holds a payload and a target, under the exception already granted.**
   [ADR-0104](./0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md)
   argued that exception for `pending/routes.sqlite` on five mitigations, and each one
   holds here unchanged: a git-ignored directory, no instrument reads it, single
   tenant, and the identity reaches nothing blinded. A held route is a decided pending
   route that did not become a case, so it lives beside the store that already holds
   it. Cross-tenant isolation stays the named P1 blocker it is in `precedent.py`.

## Why the fence is the whole decision

A held route is selected **because it already broke this target**. Any rate computed
over a sample chosen on its own outcome is not a sharper reading of the same
quantity — it is a different quantity wearing the same name. Let held routes into a
family rate and three things break at once: the rate falls with every new finding, so
a target looks worse the more the bench learns about it; two targets stop being
comparable, because their denominators hold different numbers of attacks known to
work; and the band's cut-points stop applying, because they are the reference agents'
constructed rates over the case library and were never computed against such a
population ([ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md)).

The artefact would be well-formed and the label would be wrong, which is the failure
mode this project names more often than any other.

**[ADR-0088](./0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)
is the precedent and not an analogy.** It separated two figures that had been sharing
one prohibition — the bench's discrimination score on the elective tier, which is a
claim about the bench, from an elective family's failure rate against the operator's
agent, which is a fact about that agent. This ADR separates a third quantity out of
the same pile: a rate over routes selected on their outcome, which is a fact about one
agent's history and a claim about nothing else. Same fence, one level further out.
ADR-0088 and [ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) are
**not amended**; this is a second population arriving at a boundary they already drew.

## What this costs, stated

- **A scored attempt that never faced the admission bar now exists.** This is the real
  price and it should not be softened. The mitigation is that it is fenced from every
  figure the bar protects, and that it asserts only what its evidence covers — but a
  reader of one number in one block is trusting an operator's approval where elsewhere
  they trust a declared threshold. The block says so in as many words.
- **Every run of a target gets longer** by the number of routes held against it.
  Retirement bounds it; it does not remove it. An operator who never fixes anything
  pays for a growing suite, which is the correct incentive and still a cost.
- **Model-dependence is not caught here either.** ADR-0107 already gave that up for
  this population at admission. A held route may be a property of the model the target
  runs on; nothing in this design distinguishes that from a property of its defences,
  and the block claims only that the probe still produces the verdict.
- **A sixth `DiscoveredBy`.** `TARGET_SPECIFIC`, declared last, for ADR-0107 §1's
  reason: the provenance census prints in declaration order.

## Alternatives

- **Leave it as it is — the bar refuses and the route is deleted.** The status quo, and
  it is defensible for the shared instrument. Rejected on what it costs the operator:
  the second question a customer asks is *did my fix work?*, the bench can answer it
  deterministically, and it deletes the one artefact the answer needs. #234's
  `halt_defeat` route is the concrete loss.
- **Score held routes inside the six family rates.** The obvious version of "the score
  gets more precise for this target." Rejected in full above: it is a different
  quantity under the same name, and it breaks comparability, the trend line and the
  band together.
- **Lower or widen the admission bar so these routes pass it.** Rejected because the
  bar is not failing. It is answering the question it was built for, correctly, about
  routes that do not have the property it tests. Weakening a control so a population it
  was never about can pass it is paying in the wrong currency — ADR-0107's own words
  for the mirror-image proposal.
- **Widen the reference agents' phrase router so customer vocabulary engages them.**
  Rejected, and #234 rejects it first: a scripted router is what makes a verdict a fact
  rather than a model's mood. It also does not scale — it is one edit per customer
  dialect, forever.
- **Translate the probe into the bench's dialect before measuring it at the bar.**
  Genuinely attractive and genuinely a different decision: the thing graded would no
  longer be the thing that broke the target. Deferred to its own ADR, on its own
  evidence.
- **Hold the route but only send it when the operator selects it.** Rejected on what
  the figure would mean. "3 of 5 still open" is a fact only if the 5 is every route
  ever held; a suite an operator can forget to select reports what they hoped rather
  than what is true.
- **Retire after one clean run.** Cheaper and wrong for ADR-0022's reason: one reading
  of a probabilistic target is a coin-flip, and a defect closed on a coin-flip is a
  report that says a fix worked when nothing was fixed.

## Consequences

- `docs/specs/the-target-library.md` is the build spec; #234 lands before it, because
  its per-family count of floor-at-zero rejections is what says how large this
  population is.
- One new store, git-ignored, tested across a restart —
  [ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)'s
  acceptance criterion applies to it unchanged.
- Import-level tests that a held route cannot reach the family aggregation, in the
  pattern `test_layer_ordering.py` and `test_precedent.py` already use.
- An arithmetic test that a run with N held routes and a run with none produce
  identical family rates, `A_break` and band over the same case library.
- The library digest is unchanged by the presence of held routes, and a test asserts
  it: a digest that moved per target would give every customer a differently-versioned
  instrument and a gate citation naming nothing that exists.
- Nothing in a target library reaches the attacker, the judge or the adjudicator.
  [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) is untouched, and the
  attacker is not steered away from routes already held — that is a different ticket.
