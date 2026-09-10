---
status: accepted
---

# A route found against a customer's target faces the single-model bar

[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) §1 sends every adaptive-discovered case to the cross-model bar, and it selects that bar off one field: `Case.discovered_by`. There is exactly one adaptive member, `DiscoveredBy.ADAPTIVE`, and `proposed_from` mints it unconditionally (`backend/bench/adaptive/proposal.py`). So the bar is chosen by *who found the route* and never by *what it was found against* — and those have come apart.

ADR-0012's argument is about a closed loop, and it says so in its own first paragraph: "The attacker discovers a route **by exploiting the three reference agents**. The admission gate then decides whether to admit that route **by testing whether it separates the three reference agents**. Discovery and admission run on the same set, and a case fitted to a set and validated on that same set passes more often than a case written blind." That is `scripts/swap.py`, whose targets *are* the three reference agents. The argument is sound there and nothing here weakens it.

It does not describe the other producer. A **customer run** — the console, `POST /runs`, `scripts/bench.py` — attacks a user's agent, and CONTEXT.md is explicit that a reference agent is not one of those: a **target** is "an AI agent belonging to a user", a **reference agent** is "test equipment; never reaches a user". A route found there was fitted to the customer's target. The reference agents were not in its discovery loop at all, so the selection pressure ADR-0012 exists to counter is not acting on it, and the bar is charging a second model to correct a defect that is not present.

This was foreseen and deliberately deferred. `docs/specs/pending-routes.md` closes its non-goals with it: "A route found against a customer's agent arguably faces selection pressure the reference-agent bar was not built for; that is a question for an ADR of its own and not a value to tune here." This is that ADR.

The cost is not theoretical. `/pending-routes` measures one proposed case against three reference agents on two underlying models, so the second model is half of every admission decision the surface makes — and it is the half that is answering a question about a loop the route never ran in.

**Decision.** Four parts.

1. **A fifth provenance, `DiscoveredBy.ADAPTIVE_ON_TARGET`** — found by the adaptive attacker against a user's target. `ADAPTIVE` narrows to its original meaning, a route found against the three reference agents, and keeps the cross-model bar. Declared **last** in the enum, because the provenance census prints in declaration order and a member inserted above one already counted reorders a line readers of two gate runs compare (`admission.LibraryProvenance.stated`).
2. **`ADAPTIVE_ON_TARGET` faces the single-model bar of [ADR-0003](./0003-gate-decision-rule-and-sample-size.md)**, in its own `bar_for` branch with its own reason. Not joined to `AUTHORED | USER_GAP`: those were never fitted to *anything* measured, and this one was fitted to a target that is not the thing it is graded against. Same answer, third reason, and the branch says so.
3. **The provenance is declared by the caller, never sniffed from the target.** `TargetConfig` describes "a target, reference agent or user agent alike" and deliberately holds no field that tells them apart; a bar selected by inspecting a URL or an agent type would be a bar that moves when somebody renames a fixture. `AttackableTarget` carries it, `run_episode` passes it down, and `proposed_from` takes it as a required argument with no default — the same treatment `broken` has one line above, and for the same reason: it is a fact the record cannot be made honestly without.
4. **`/pending-routes` requires one declared reference model, not two.** The surface only ever decides customer-filed routes, so after (2) every proposal it sees faces a one-model bar and a second pass buys nothing it can spend. `AGENTAUDIT_SECOND_REFERENCE_MODEL` stays declared and stays required by `scripts/swap.py`, which measures a model *pair* by definition (#15).

**ADR-0012 is narrowed, not superseded.** Its §2 — `discovered_by` on every case record, and `docs/validation.md` printing what fraction of the live library the attacker wrote on every gate run — is untouched and now counts five provenances. Its §3, the retirement-rate signal, is untouched and still applies to both adaptive members. Only §1's *scope* moves.

## Considered options

- **Send `ADAPTIVE` to the single-model bar and delete the distinction.** One line, and it was the first proposal. Rejected: it drops the bar for swap-discovered routes, which is the one population ADR-0012 was written about and where its argument is fully intact. Buying a cheaper admission on the customer surface by weakening the bar on the surface that needs it is paying in the wrong currency.
- **Keep the cross-model bar for every adaptive route.** The status quo, and it is not absurd — the model-dependence reading below is real. Rejected on scope: the bar's stated justification does not reach these routes, and a control kept for a reason that does not apply is a cost with no argument behind it. If model-dependence at admission is wanted, it should be decided on its own terms and applied to every provenance, not inherited by one through a definition that no longer fits.
- **Derive the provenance from `TargetConfig`.** No new field, no threading. Rejected: `contract.py` states that the type describes both kinds alike, so the derivation would have to guess from a name, a URL or an `agent_type` — and the admission bar of every future case would then hang on a string nobody thinks of as load-bearing.
- **A boolean on the existing `ADAPTIVE` member rather than a fifth provenance.** Rejected: the census counts provenances, and a population that reports as one member while entering under two different bars is exactly what ADR-0012 §2 exists to make visible. The record must print which bar a case entered under and a reader must be able to tell the two apart.

## Consequences

- **Model-dependence is no longer caught at admission for customer-discovered routes.** This is what is being given up and it should not be softened: a route that separates the three reference agents on one model and would not on another now enters the library, and ADR-0012's "the discard is itself a finding" is no longer available for this population. What remains is after the fact — the retirement-rate signal of §3, and the per-case `D` series every gate run appends to `Case.history`. Detection moves from admission time to the next gate run that reads the case.
- **Deciding a route on `/pending-routes` costs half of what it did.** One pass over three reference agents instead of two, and the estimate the operator confirms halves with it.
- **The `cross_model` rejection bucket can still fill, and only from the swap.** `AdmissionOutcome.cross_model()` is not dead code and its prose stays; on the pending-routes surface it will now always read zero, and the screen should stop offering a line that cannot move there.
- **Nothing already in the library changes.** All 21 live cases are `authored` under `single_model`; no adaptive case has ever been admitted, so there is no record to migrate and no admission to re-decide.
- **The provenance census grows a member**, so `docs/validation.md`'s adaptive-fraction line reports five numbers where it reported four, and a reader comparing two gate runs across this change sees the split appear.
- **A route filed before this change carries no way to say which it was.** `pending/routes.sqlite` holds routes filed by customer runs only, so the backfill is a constant rather than a judgement — but it is a backfill and it has to be written down rather than assumed.
