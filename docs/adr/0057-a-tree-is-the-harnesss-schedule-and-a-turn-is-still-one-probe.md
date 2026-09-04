---
status: accepted
---

# A tree is the harness's schedule, and a turn is still one probe

Linear jailbreaking has been in this bench since #16 under another name: `_Episode.run` composes each probe from what the last one returned, which is what makes it a loop rather than a sequence. #71 names it and asks for the branching form beside it — the attacker may fork, and the harness may prune — and that asks a question about arithmetic rather than about attack quality. Three recorded quantities are defined over a line: the turn budget, `A_effort` (median turns-to-first-success) and `A_break`.

**Decision.** A turn is **one probe sent to the target**, wherever it sits in the tree. Branching is the harness's scheduling of the same `run_probe`; pruning is the harness's, on a stated rule; and the tree is recorded as a parent index per turn, defaulting to the chain.

## 1. No sixth tool, because a tool that chose breadth would choose the spend

*Five tools* is a load-bearing phrase in PLAN §11, CONTEXT.md, the README and [ADR-0008](./0008-repo-disclosure-posture.md)'s *weapon factory* paragraph, and the alternative here would have been a sixth — `branch_from`, or a node argument on `run_probe`. It was rejected on [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)'s boundary rather than on the count: **a model-invoked tool that decided how wide to search would be a model-invoked tool that decided how much of the operator's endpoint to spend.** The layer's whole arrangement is that the model chooses payloads and the harness owns the budget — `check_canary` reports what the harness already found, `_probe` verifies every turn whether or not the attacker thought to ask — and breadth is a budget decision wearing a payload decision's clothes.

So `EpisodeTree.next()` picks the node and `prompt._continuation` tells the attacker which turn its next probe continues from. The model composes a probe as it always did. What it is told is a **turn number**, which indexes a log it is already holding: a brief built from it carries no more about the target than the redacted probe log already carries, so the blinding of [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) is untouched and is still applied at the one call site in `attacker._step`.

The sentence appears **only when the schedule has something to say**. On a line the last entry in the log *is* the node, which is what the brief has always meant, so `_continuation` renders nothing and a linear episode's brief is byte-identical to the one this layer has always sent.

**The node, and nothing else.** Not the depth the turn will sit at, and not which turns the harness has closed. Neither leaks anything about the target, and both were in the first draft — but the attacker does not choose the node, so neither would change what it composes, and a brief carrying them would say more about the schedule than the constraint allows for no gain. They stay on `EpisodeTree`, which is where the report reads them.

## 2. The turn budget does not move, and that is the whole claim

`turns_per_episode` caps the episode, never the branch. A tree spends one turn budget **across** its branches and never alongside them, so:

- `AdaptiveBudget.turn_ceiling` — families × `T` × `k`, the number an operator approves under [ADR-0007](./0007-canary-nonce-as-proof-of-control.md) — is the same figure under any policy, as is the estimate's basis string.
- `A_effort`'s median turns-to-first-success is **median probes-to-first-success**, which is comparable with the linear attacker's number *by construction* and comparable **only** because a turn is a probe. If a branch were ever counted as one turn, the two attackers' `A_effort` figures would silently stop being the same quantity, and nothing would fail.

Both failure modes are held by tests driven red on purpose (`backend/tests/test_tree_jailbreaking.py`): a branch counted as a turn, and a cap that each branch carries — the second being the one that bills the operator three times over for a run they approved once.

**Breadth is bought with depth, and it is stated where `A_effort` is printed.** Eight turns at breadth three reach four turns deep; eight turns on a line reach eight. Two attackers doing different amounts of thinking per turn are being compared on turns, and that is a statement the adaptive block makes out loud in `BranchPolicy.stated()` rather than a caveat a reader has to reconstruct. It prints under **every** policy, the line included: the claim a reader needs is what a turn *is*, and a block that said so only when the search branched would leave the linear reading to be inferred.

The policy is declared on `AdaptiveBudget`, beside `T` and `k`, for the reason those are declared there: breadth is bought out of the same budget, and a schedule widened at hour 30 until the attacker finally found something, then reported as though it had been fixed in advance, is the adaptive layer's version of tuning the gate. **What it does not yet have is a selection path** — no flag, no environment variable and no place in provenance, so today the schedule is declared in the record the run is held to and printed in the adaptive block, and nothing but a caller constructing an `AdaptiveBudget` can change it. Carrying an operator's choice of what runs is #79's, on the terms #71 (c) states, and the branch policy is a declared input of the adaptive layer waiting for the same mechanism `T` already has. **The declared default stays the line.** The reference agents were gated under that schedule, and a bench that quietly changed what its attacker does would invalidate the citation a report carries without a gate run saying so ([ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md)).

## 3. The stated rule, and why the rule is the point

**Scheduling.** The next probe continues from the **shallowest live turn**, ties broken by the **lowest turn number**. A turn is live while it is unpruned and has fewer than `breadth` children. Shallowest rather than deepest because deepest is a line by another name — a depth-first schedule under any breadth continues from the turn it just took and never forks — and ties by number so the schedule is an order rather than a preference, reproducible from the record, which is what lets a reader walk the tree.

**Pruning.** Once more than `frontier_cap` turns are live, the harness stops continuing from the lowest-numbered of them. A rule about **age**, and deliberately not about how well a branch was doing.

That second rule is where this ADR earns its keep. A pruning rule is a choice about what the attacker is allowed to forget, and `A_break` is a diagnostic on the attacker (`discrimination.py`), so **a rule nobody wrote down would make `A_break` a reading about an unrecorded heuristic.** Pruning by age has a cost and the cost is stated rather than hidden: the harness does not judge a branch, so it can and will throw away the one that was working. **A negative `A_break` therefore now has a second reading beside a blinding failure** — a pruning rule that discarded the productive branch — and `BranchPolicy.stated()` says so on the line.

`SeparationReading`'s four rows are **unchanged and were not touched**. `A_break` is families broken on trivial minus families broken on hardened — a difference over families, not over turns — so the tree does not enter it, and the sign test's paired unit is still the family.

## 4. One field, and the chain is the absent one

`AdaptiveEpisode.parents` carries the one-based turn each turn continued from, zero for a root, and is **empty for the linear chain**. `parent_of` reconstructs the chain, so a caller walks a line and a tree the same way, and a linear episode's record is unchanged in value by this ADR. One representation of the chain rather than two — the same refusal [ADR-0056](./0056-a-discovery-count-shares-a-row-with-a-rate-and-is-a-summand-of-nothing.md) §4 makes about a family the search never worked in, and the reason `VariantCounts` refuses zero attempts ([ADR-0055](./0055-a-family-pools-its-variants-and-publishes-the-counts.md) §2).

**Indices are one-based, stable and append-only.** `unverifiable_turns` indexes into `transcripts`, so pruning marks a turn as no longer continuable and **removes nothing**; the record refuses a `parents` whose length does not match its turns, and refuses a parent that is not an earlier turn, which makes the tree acyclic by construction.

**No count and no denominator.** The tree is a shape, and a shape is not a sample: nothing divides by `parents`, `depth` or the pruned set, and `turns` remains the only figure the statistics read.

**No new `EpisodeOutcome`, and none was needed.** An episode is `broken` or `censored` on the same two conditions as before — the evaluator answering `succeeded`, or the attacker stopping on a cap. Pruning is a decision *inside* an episode and never a way for one to end, so nothing was added for `Discoveries.of` and `report.ts`'s `readOutcome` to have to word (ADR-0056 §3). Had a third outcome been needed it would have had to be counted for itself on both surfaces; the honest way to avoid that bill was not to need it.

**Nothing reaches the signed artefact.** `payload._episode` carries the family, the outcome, the turn count and the prose, and it gains no field here: the artefact still holds no adaptive figure, and the tree lives on the record the operator holds beside the transcripts, which are never committed (ADR-0008).

## 5. The tree is in the harness, not in the target's session

Every probe still gets its own session id, exactly as before. The continuation is a line in the **brief**, so a branch is a fact about what the attacker was told and never about what the target remembers — which is what keeps this inside #71's refusal of target-stateful adaptive loops. Crescendo, GOAT and Hydra as loops build state inside one target session and are still out of scope; a tree does not, and the parent index is the whole of what makes it one.

The stand-in branches too, because a branching harness whose only CI attacker is blind to the schedule is a harness whose branching is exercised by nothing. `scripted.py` composes each probe from the node it was given as well as from how many have gone, so a branching episode is a different route rather than the same eight strings in the same order, and its `DESCRIPTION` says so — a route is what a proposed case has to reproduce.

## Considered and rejected

**A branch as a turn.** The reading it produces is *median branches-to-first-success* for one attacker and *median probes-to-first-success* for the other, printed in the same column under the same heading. It also detaches the budget from the endpoint: an episode capped at eight turns could put twenty-four messages on the operator's wire.

**A turn cap per branch.** Same defect, stated as money: the ceiling an operator approved is multiplied by the breadth after they approved it, which is the second ceiling of ADR-0007 set above the first.

**A sixth tool.** §1.

**Pruning on the model's judgement** — the attacker abandons the branch it thinks is dead. It is the version a reader would expect from the published tree-of-attacks work, and it puts an unrecorded heuristic inside the statistic that is supposed to be a reading *about* the attacker. The harness's rule can be printed; the model's cannot.

**A parent index on every episode, chain included.** Two representations of the line, and every existing linear record would have changed value for a field that says what `parent_of` already computes.

**The tree in the signed artefact.** It is a shape with no denominator, in a document that carries no adaptive figure at all by ADR-0056 §1. A recipient who wants the search's shape wants the transcripts, and those do not leave the building.

## Citation

Tree jailbreaking is [deepteam](https://github.com/confident-ai/deepteam)'s name for the technique (Apache-2.0), listed beside linear jailbreaking in its multi-turn attacks and read against [promptfoo's strategy list](https://www.promptfoo.dev/docs/red-team/strategies/), which is where #71 took the catalogue from. Both catalogues attribute the shape to the published *Tree of Attacks with Pruning* line of work; **this repository has not verified that paper's authors, venue or method against the primary source, so it names none of them.** What is cited here is the catalogue entry these two URLs carry, and the scheduling and pruning rules in §3 are **this bench's own**, chosen for the reasons given above rather than reproduced from any paper — which is the only honest way to state them, because they are the rules `A_break` is read against.
