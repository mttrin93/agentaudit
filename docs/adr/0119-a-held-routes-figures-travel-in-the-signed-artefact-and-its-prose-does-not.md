---
status: accepted
---

# A held route's figures travel in the signed artefact, and its prose does not

[ADR-0117](./0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§4 says *"the report gains one block — held, still open, closed — and nothing else
moves"*, and it does not say which document it means. This project has two, and
[ADR-0115](./0115-the-report-screen-carries-the-figures-and-the-artefact-carries-the-sentences.md)
split them on purpose: the report **screen** draws the figures and the signed
**artefact** carries the sentences. The build spec
([docs/specs/the-target-library.md](../specs/the-target-library.md)) put the question
in its own Out of Scope list — *"whether the signed document carries a held-route
section is a question for the ADR and not assumed here"* — and left it open.

The question has to be answered before the block can be drawn anywhere, and the
reason is mechanical rather than editorial: **the report screen reads the signed
payload and nothing else.** `GET /report/{id}` copies the bytes a recipient verifies,
`frontend/src/api/report.ts` parses that document, and `reportView` is a view of it.
There is no second endpoint a figure could reach the screen through, and building one
is how a checkable document grows an uncheckable half — ADR-0070 §1's own argument,
one section along. So *only the screen carries it* was never available: either the
artefact carries the block, or nothing does.

## Decision

**The block's figures and dates go in the signed artefact. The prose does not.**

1. **In**, as Annex IV point 5's third section: how many routes are held against this
   target, how many are still open, how many are closed, how many broke the target
   again on this run, how many could not be read, and how many have closed once and
   come back — each printed as a count beside the counts it came from. Per route: the
   family, the digest of the probe, the state, which of the four readings this run
   took, and the run ids that found it, closed it and found it again. A per-route line
   assembled out of exactly those fields is a figure line and is in.

2. **Out**: the attacker's own description of the break, which `HeldRoute.description`
   carries and `reporting.HeldRouteLine` deliberately does not. The probe and its
   success condition were never in question —
   [ADR-0008](./0008-repo-disclosure-posture.md) keeps a working unpublished exploit
   out of the document that leaves the building — and this is the third thing: a
   sentence a model wrote about a route it found against one customer's agent.

3. **The block states what licenses it, in the document and on the screen.** ADR-0117's
   cost paragraph requires it in as many words, and it is one sentence on the payload
   rather than two surfaces wording it: a reader of a figure in this block is trusting
   a named operator's approval where every figure in the measured sections is trusting
   a threshold declared before the run.

4. **The artefact version does not move.** `held_routes` is a key added beside existing
   keys, which ADR-0044 §8 and ADR-0070 both declined to move the version for — and
   the case for moving it is weaker here than it was for
   [ADR-0088](./0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)
   §7, which moved it because a version-1 verifier would have re-derived *nothing* for
   half a measured section and reported the document verified. There is no arithmetic
   in this block for a verifier to re-derive at all: the records it is derived from are
   the target library, which is not in the document and whose probes never will be.

## Why the prose is the half that stays out

Three reasons, and the third is why this is a decision rather than a preference.

**It is about a different subject from everything else in the document.** Every other
sentence in the artefact is about the target this report names. A held route's
description is the attacker's account of what it did, written by a model, about a
route found against this agent — closer to the adaptive section's episode prose than
to a finding, and the adaptive section carries its own *not reproducible* label for
exactly that reason (ADR-0017, ADR-0010). The held-route block does not have that
label and should not: its figures are deterministic-evaluator verdicts.

**A sentence in a signed document is a claim the signature covers.** ADR-0070 §1 put
the findings block inside the signature rather than beside it, and the price was that
every sentence in it had to be accounted for — attributed, labelled, and answerable.
A held route's description has had none of that work done to it: nothing attributes
it, no label says what it asserts, and no disclosure pass has decided what in it may
travel. Admitting it because there was room would be the self-graded claim this
project exists to displace, arriving one section later.

**The evidence the figures rest on already is thinner than the rest of the document's,
and prose would widen the claim without widening the evidence.** ADR-0117 §2 is
explicit that a held route faces a person rather than a `D`, and its cost paragraph is
explicit about what that costs a reader. A block of counts asserts exactly what its
evidence covers — *this probe produced this verdict against this agent, and here is
whether it still does*. A paragraph describing the defect asserts more.

## What this costs, stated

**The build spec's user story 4 is not met, on any surface, and this decision is why.**
The story reads: *"As an operator, I want the attacker's own description of the break
carried on the held route, so that the report says what the route did and not only
that a route exists."* Half of it is done — the description is on the record
(`HeldRoute.description`) and has been since the store was built — and the half the
story is *for* is refused here. An operator reading the block is told a route in
`halt_defeat` with a given probe digest is still open, and is not told what it does.

That is a real loss and it should not be softened into *the digest is enough*. It is
not: two routes in one family are two digests and a reader cannot tell which defect
either is. What makes it the right refusal today is that the fix is the disclosure and
attribution work above, and that work has an owner — a later ticket, on ADR-0070's
terms — rather than a paragraph added to a section because the section exists.

**A reader holding only the artefact still cannot re-derive this section**, and the
section says so. The label on it is *re-derivable*, which is the nearer of ADR-0017's
two and not a comfortable fit: the records these figures follow from are the target
library, which the reader does not hold. No third label was invented, because a third
evidentiary class would have to extend the claim list and that is its own decision.
The section carries a paragraph saying from what, and by whom, it cannot be recomputed.

## Alternatives

- **Neither document carries the block.** Rejected: ADR-0117 §4 decided the report
  gains one, and a target library nothing reports is a suite an operator pays for and
  never reads.
- **Only the report screen carries it.** The option the issue named, and it is not
  available: the screen reads the signed payload and there is no other source. Building
  a second endpoint for it would put an uncheckable block on a page beside checkable
  ones, which is ADR-0070 §1's rejected option.
- **Carry the description too.** Genuinely attractive — it is the half the operator
  asked for — and rejected here on the three reasons above rather than on principle.
  It is a later decision with real work in front of it: what attributes the sentence,
  what label says what it asserts, and what the disclosure pass does with a model's
  prose about somebody else's agent.
- **Move the artefact version.** Rejected on ADR-0088 §7's own test: a version moves
  when an older verifier would re-derive part of a document and report the whole of it
  verified. There is nothing here to re-derive, so an older verifier skips a key and
  checks every figure it knows about, which is what a key beside the others is for.

## Consequences

- `backend/bench/reporting.py` is the record the artefact carries, and
  `HeldRouteLine` has no `description` field — the fence is the type, as it is
  everywhere else in this feature.
- `backend/bench/rendering/_held.py` is section 5c, and `Section.part` now takes `c`.
  Annex IV point 5 holds three sections.
- The golden rendering digest moved, with its own entry in the list
  `test_rendering.py` keeps.
- The build spec's user story 4 is recorded above as unmet, and the ticket that meets
  it is the one that decides what a signed document does with an instrument's prose
  about a held route.
