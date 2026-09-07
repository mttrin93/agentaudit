---
status: accepted
---

# An episode whose instrument broke is a failed episode, and the run is still measured

On 2026-09-07 a gate run measured twenty live cases and nine elective ones against three reference agents — 1143 scored calls, 0.58 USD, the whole of what the operator confirmed — and then raised out of the adaptive layer and wrote **nothing**. No `[[history]]` block, no document, no record, no citation. The immediate cause was #166 and is fixed on its own terms; this ADR is about the second fact, which no fix to `propose_case` touches: an exception in the layer that decides nothing had the run that decides everything at its mercy.

[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) carries the boundary in the type — an `AdaptiveEpisode` is not an `Attempt`, and the adaptive layer reaches the scored side through exactly one edge. A traceback respects no type. [ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md) decided the same question for the narrative instruments, where `JudgeFailed` and `ReplyUnfinished` used to settle a whole run `failed` with its attempts stranded on `RunState`. This is that decision, one layer over, and it inherits its discipline rather than restating it.

## Decision

**An episode whose own instrument broke is recorded as `FAILED` with the instrument's reason, the layer runs the rest of its episodes, and the run stands on its scored layer.**

1. **`EpisodeOutcome.FAILED` is not `CENSORED`, and the distinction is load-bearing in one direction.** A censored episode is an attacker that stopped on the turn cap; a failed episode is *no observation at all*. Reading a provider hanging up as censored would make it look like a hardened agent holding — the one direction [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md)'s reading table cannot tolerate being wrong in, since *hardened mostly censored* is half of what licenses **the attacker works and the hardening is real**. Reading it as broken would credit the attacker with a break nothing verified.

2. **The outcome and the reason are paired by an invariant.** A failed episode carries a reason and a completed one carries none, checked in `__post_init__`, because an outcome and a reason that can disagree are two readings of one fact. The text is the instrument's own rather than this layer's paraphrase: what an operator meeting it needs is which instrument broke and what it said.

3. **A failed episode enters no denominator.** `breaks_for` skips it, so its family is not added to that agent's families and cannot be counted as censored. A family whose episodes all failed on one agent simply leaves `scope`, and if that empties the scope `measure` raises `NoFamiliesInScope`, which every caller already prints as a stated refusal rather than a zero.

4. **The catch is three named types and no wider**: `TargetUnreachable`, `AttackerUnavailable` and `ReplyUnfinished` — the target on the wire, the attacker's own model, and that model answering with a tool call the token cap cut off. That is the whole of what this layer talks to besides the case record it was handed, and each breaks outside this repository, which is what makes an episode that met one an absent observation rather than a defect. **None of the three is a provider's own exception class, and that is not incidental**: `AttackerUnavailable` is declared at the attacker seam, and `completion.attacker_completion_for` translates `OpenAIError` into it once. A layer that named `openai.OpenAIError` would put that SDK in the import closure of everything reaching the layer, and `test_verify.py` asserts the verifier reaches no network and reads no credential — the invariant caught exactly that on the first full run of the suite after this change. `ReplyUnfinished` is *not* translated and surfaces as itself, because it is already this bench's own named failure and `test_unfinished_replies.py` holds that a truncated tool call is a named failure and not a decision. A bare `except Exception` would turn every future bug in the layer into a run that quietly attacked nothing and published `A_break` over whatever survived, which is PLAN §10's failure mode arriving from the opposite side; ADR-0050 keeps a test that a `MemoryError` from the judge's seat still stops the run, and the counterpart test is here.

5. **A failed episode prints where the others print**, with its reason on the line, and is filed on the run state as well as returned — the run state is what the report and `/runs` read, so an episode recorded only in a return value would be a failure the document does not carry.

## Why not record nothing and let the run continue

The cheap version: swallow the exception, run on, publish the episodes that worked. It reproduces the defect this ADR is named against in a quieter form. `A_break` would then be a difference over families that happen to have survived, printed with the declared denominator beside it, and a reader could not tell a run where the layer worked from one where half of it fell over. *The layer did not run* is already a distinct reading from an empty tuple (ADR-0058); *this episode has no reading* has to be a third, for the same reason.

## Why not persist the scored layer before the adaptive layer starts

It would also have saved the 0.58 USD, and it buys the wrong thing. The document is one artefact over both layers, and writing the scored half first means either a document that is complete only sometimes or two write-backs and a window in which the library cites a run that has not finished. ADR-0050's precedent is the opposite of partial: nothing partial survives, and the reading says so. A failed episode inside a whole document is the shape this project already chose.

## Considered options

- **Retry the failed episode.** A retried episode is a second search from a fresh context, so it is a different episode with the same budget spent twice, and `k` is declared. It also cannot be bounded honestly: a provider that is down stays down for the length of the run.
- **Fail the whole layer on the first failed episode.** Simpler to state and it throws away the episodes that worked, which are real observations of the attacker.
- **Count a failed episode as censored and note it in prose.** Rejected in §1: the number is what a reader acts on, and the prose would be arguing against the figure printed beside it.
- **Catch `Exception` and record every failure as an instrument failure.** Rejected in §4. It is the same trade ADR-0050 refused, and the cost is that a defect becomes invisible exactly when it matters.

## Consequences

- **A run can now report a complete gate decision beside an adaptive section that is missing episodes**, and both facts print. That is a genuinely new document shape, and the sentence a reader needs — *no reading was taken, and this is why* — is on the episode's own line.
- **`A_break`'s scope can shrink without any statement that the attacker found nothing.** Four families in scope is already the number ADR-0011 says cannot demonstrate a difference at `p = 0.500`; three or two says less, and the run prints the scope it had.
- **The two named types are a maintenance obligation.** A third instrument added to this layer with its own failure mode will fail loudly and correctly until it is named here, which is the behaviour ADR-0050 chose deliberately over a handler that would have absorbed it.
- **What is not fixed:** the money already spent when an instrument breaks mid-run. The scored layer is paid for before the adaptive layer starts, and this decision keeps its results rather than recovering its cost.

Cross-references: [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the boundary a traceback does not respect), [ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md) (the same decision for the narrative instruments, and the discipline this inherits), [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (the reading table, and why censored is not a free reading to give away), [ADR-0058](./0058-the-console-selects-layers-and-constructions.md) (why *the layer did not run* is its own reading), #166 (the defect that reached it first), #167 (this ticket).
