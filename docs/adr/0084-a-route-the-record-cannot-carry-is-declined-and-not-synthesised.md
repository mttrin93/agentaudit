---
status: accepted
---

# A route the record cannot carry is declined, and not synthesised

`proposal.proposed_from` copies the objective's success condition off the case it was handed, which is what keeps a proposal deterministic: the attacker found a new *payload* and not a new definition of a break (ADR-0004). For two success-condition kinds that copy makes the record unbuildable. `CANARY_INSTRUCTION_EXECUTED` and `RETAINED_INSTRUCTION_EXECUTED` say the attack arrives in content the target fetched, so ADR-0060 requires the record to carry that content — and `proposed_from` set no `planted_artefact`, because the payload it has is `str(self._last.sent.get("message", ""))`, the probe the attacker typed. `Case.__post_init__` refused the pairing, the `ValueError` left the episode, left the layer, left `run_suite`, and ended a gate run whose scored layer had already been paid for: 1143 calls and 0.58 USD on 2026-09-07, written back nowhere (#166, and #167 for the containment).

The invariant is right and the caller was wrong. In indirect prompt injection — and in the elective memory poisoning — a case **is** a piece of content, and a probe is a message.

## Decision

**A route the attacker found and no case record can carry is declined with its reason, recorded on the episode, and proposed to nothing.**

1. **The refusal is `proposal.RouteNotFilable`, raised where the copy happens** and caught by the episode. A dedicated type rather than a `None` return, because the reason has two readers: the attacker, which asked and gets it back as its tool result, and the episode record, which is the only place a route the layer could not file is ever written down.

2. **`AdaptiveEpisode.declined` is a third reading beside a proposal and no proposal at all.** Kept apart from `proposals` because the two say different things: a proposal is a route the gate still has to decide, and a declination is a route nothing will decide because it was never filed. Collapsing them would report a route as awaiting a decision no admission run will ever put.

3. **Nothing about it is scored.** An episode has no denominator (ADR-0010), so a declination cannot become a proportion of anything, and the count of them decides no gate, no band and no admission.

## Why not synthesise the artefact from the probe

This is the fix that looks cheapest and it is the one that would put a false record in the library. Giving the probe text to `planted_artefact` files **a message as fetched content**, which is the distinction ADR-0060 exists to hold: the record would claim the attack arrived through a channel it did not arrive through, and a reader running that case would be running something else. The two invariants that hang off the artefact would then have to be invented to match — the canary is the artefact's own two halves joined, and the content key is named by the turn that fetches, which a probe does not name because the attacker is blinded and never knew it. A record assembled to satisfy three checks rather than to describe what happened is evidence manufactured to clear a bar.

## Why not drop the two families from the adaptive layer

It would remove the crash and lose the reading. The layer opened episodes on indirect prompt injection because there is a deterministic case to give `check_canary` a canary, and the break it found there is real — `A_break` counted it. What cannot be done is *filing* it. Withdrawing the family would throw away a verified observation to avoid an unbuildable record, and would shrink `A_break`'s scope from four families to three, which is the denominator ADR-0011 already calls too small to demonstrate anything.

## Considered options

- **Return `None` and let the caller compose the reason.** The reason then lives at the call site, where the family is known and ADR-0060's argument is not, and a second caller would write a second wording for one fact.
- **Catch `ValueError` in `_propose`.** It would have fixed the crash and hidden every future construction bug behind the same handler. The type is the point: `RouteNotFilable` is a decision this module made, and a `ValueError` out of `Case.__post_init__` is the library refusing something nobody intended.
- **Let the admission gate refuse it instead.** The gate is a run against reference agents on a second model (ADR-0012), so the record has to exist to reach it. There is nowhere to park an unbuildable record: `admission.admitted_library` refuses one whose reading does not clear its bar, and this one cannot even be constructed.
- **A route that can be filed later, once the attacker can plant content.** Left open deliberately, and not decided here — it needs a way to plant content the attacker composed, which is a ticket of its own and probably an ADR of its own.

## Consequences

- **The adaptive layer will report declined routes on indirect prompt injection for as long as it attacks that family**, and on memory poisoning whenever that elective family is requested. That is the honest state and not a defect to suppress: the attacker works there, and the library cannot hold what it finds.
- **`A_break` and `A_effort` are untouched.** Both are measured on episodes and families, and a declination changes neither the outcome of an episode nor its turn count. The route that produced one still counted as a break.
- **The count of proposals a run makes falls in these families to zero**, where before the run ended instead. `provenance of the live library: adaptive 0` therefore stays 0 for a second reason, and a reader comparing runs across 2026-09-05 should read the earlier proposal count against the plant work of that day.
- **What is not claimed:** that a route in these families is worthless. It is unfilable *by this record type*, which is a statement about the library's shape and not about the attack.

Cross-references: [ADR-0060](./0060-a-planted-artefact-is-part-of-the-case-record.md) (why the record has to carry the content), [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the one edge, and why nothing here is scored), [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) (the bar a proposal would have faced), [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (why the success condition is copied rather than composed), [ADR-0008](./0008-repo-disclosure-posture.md) (why a route's description is the only part ever written down), #166 (the defect), #167 (the containment).
