---
status: accepted
---

# No user input ever changes a measured rate

Once verdicts became deterministic ([ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md)), the human override lost its target. If a canary token planted in the system prompt appeared in the output, the leak happened — there is nothing to disagree with on four of six families. The originally named defect ("the precedent store sends overrides back into the judge, and the judge learns the reviewer's consistent error") shrank to narrative fields on two judged families, and a different, sharper defect took its place: a user whose report goes to a procurement team has a **commercial incentive** to mark findings not applicable rather than to fix the agent. The admission gate stops weak cases entering the library; nothing stopped strong findings being annotated into irrelevance.

**Decision.** The invariant is absolute: **no user input ever changes a measured rate.** Overrides are typed, and each type has one destination.

| Type | Allowed on | Destination |
|---|---|---|
| `verdict_dispute` | judged families only | the κ gold set, **as a candidate label — never the judge prompt.** Disputes improve the measurement instead of corrupting it, and are counted and reported |
| `applicability` | any finding | **annotates, never deletes.** The report prints the finding and the user's reason side by side; the reader decides |
| `severity` / `exposure` | any finding | the user's own commercial judgement, recorded; never touches a rate or a band |
| `case_gap` | — | `propose_case` → **admission gate at `D ≥ 0.4` against the reference agents** |

## Consequences

- The "learns from user feedback" claim becomes precise: **user input proposes, a quantitative gate disposes.** Most implementations of that pattern have no arbiter at all; this one has a stated threshold from [ADR-0003](./0003-gate-decision-rule-and-sample-size.md).
- The first named defect is restated as **applicability drift** plus **gold-set contamination**. Mitigations: overrides annotate rather than delete; the gold set is labelled before any user dispute reaches it, and disputes enter only as candidates; dispute counts are printed in the report. Naming the smaller, sharper defect is more credible than keeping one that has been designed out.
- **Precedent store isolation.** Cross-tenant retrieval returns anonymised remediation patterns only — family, control type, fix text. Never target identity, never payload-plus-target pairs. Findings stay inside their own tenant. The store otherwise holds unpatched exploits against named companies' agents and would surface one customer's live vulnerabilities in another customer's session. The store is single-tenant by construction until multi-tenant isolation exists, and that isolation is a **blocker before the first real user**, not a later refinement.

## The store ships before the taxonomy

The reasoning above justifies deferring the **override taxonomy** — four types is invented ergonomics until a real user disputes a real finding. It does not justify deferring **memory itself**, and treating the two as one unit removed long-term memory from the deliverable as a side effect. They separate cleanly:

- **Now:** a single-tenant precedent store in the LangGraph Store, over **deterministic** findings, with a retrieval node in the graph. Keyed on family, external identifier and declared-control type, with payload text available for semantic match. It feeds `suggest_remediation` only — never `assess_finding`, per [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md).
- **Later, after real users:** the four override types, the review-with-override screen, and cross-tenant anonymised retrieval.

**Deterministic findings, not judged ones.** Precedent over judged findings would be precedent over the least reliable material in the system — propagating low-confidence findings into remediation advice, from a store that starts nearly empty because only two families feed it. "Similar past finding" is a meaningful claim only where the finding is reproducible, which is exactly what a deterministic verdict provides.

The store must be a genuine Store-backed retrieval step in the graph. A keyed dictionary lookup is a database wearing a memory costume, and it does not demonstrate the thing it is there to demonstrate.
