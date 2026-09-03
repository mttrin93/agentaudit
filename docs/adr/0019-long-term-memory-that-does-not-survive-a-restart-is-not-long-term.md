---
status: accepted
amended_by: 0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md
---

# Long-term memory that does not survive a restart is not long-term memory

> **Amended by [ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md).**
> One of the six points below was reversed rather than kept: the store is a SQLite
> database, not a JSON document. The *condition* point 3 states is what licensed the
> change — the claim rests on the interface and the lifetime, not on the backend's
> brand, and both are unchanged — and the dependency it weighed arrived anyway, for
> the checkpointer, in a package that ships a `BaseStore` too. Points 1, 2, 4, 5 and 6
> stand as written and are what ADR-0029 is measured against. The two passages
> affected are marked where they appear; nothing here is deleted, because what this
> file claimed was true when it was written and is why ADR-0029 exists.

Phase 6a builds the precedent store, and PLAN §10 answers a requirement with it in as many words:

> **Short-term and long-term memory** — Short-term: the run state carried in the graph — position, findings, budget… **Long-term: the precedent store, phase 6a** — LangGraph Store over deterministic findings with a retrieval node, feeding remediation…

LangGraph ships `BaseStore` and `InMemoryStore`, both available in the pinned version, and `InMemoryStore` is the one every quickstart uses. It holds its contents in a dictionary. Building the store on it would satisfy every sentence in that table row — LangGraph Store, deterministic findings, retrieval node, feeds remediation — and would still not be long-term memory, because nothing in it would outlive the process that wrote it.

The two halves of that answer would then be the same half twice. Run state is per-run **by design**: position, findings so far, budget spent, discarded when the run ends. A precedent store that is per-process is the same lifetime wearing a different name, and the requirement would be met on paper by a rename.

**Decision.**

1. **The precedent store is durable across process restarts.** A finding written by one run is readable by the next one, in a new process, after a reboot.
2. **`InMemoryStore` is a test double and never the store a run uses.** It is the right thing for a unit test and it may not be the production backend.
3. **Backed by a file.** If no durable backend is available without a dependency out of proportion to a single tenant's findings, a small `BaseStore` implementation over JSON is the honest answer — the claim rests on the **interface** and the lifetime, not on the backend's brand. *[Amended by [ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md): the durable backend became available without a dependency — `langgraph-checkpoint-sqlite`, installed for the checkpointer, ships a SQLite `BaseStore` — so the condition resolved the other way. Still one file, still the interface and the lifetime.]*
4. **Durability is tested across a restart, and that test is the whole content of the claim.** Write, drop the store object, construct a new one against the same location, read the finding back.
5. **The namespace is single-tenant and says so**, so cross-tenant isolation is a visible absence rather than an assumed presence. It is a named P1 blocker for user two, not a silent one.
6. **Precedent is user data and is never committed.** The store's location is ignored by git, on the disclosure posture of [ADR-0008](./0008-repo-disclosure-posture.md): findings describe someone else's agent failing.

## Why this is a decision and not an implementation detail

Because the alternative is available, cheaper, and would let the project claim something it had not built — and because the claim is one of four medium optional tasks the submission rests on. A store that loses everything on restart, described as long-term memory, is the same category of error as a bench that reports a rate for a family it could not measure: the artefact is well-formed, the label is wrong, and the reader has no way to tell.

There is also a plainer reason, independent of any requirement. **Precedent's only value is cumulative.** `suggest_remediation` informed by the findings of one run is remediation advice derived from the transcript in front of it — which is what it would have produced with no store at all. The store earns its place at run two and every run after, and a per-process store never reaches run two.

## What durability does not buy, stated so it is not assumed

- **It does not make precedent evidence.** Nothing retrieved from the store enters a rate, an interval, a discrimination score, a band or the gate decision. It reaches `suggest_remediation` and nothing else.
- **It does not relax the blinding constraints, and it sharpens why they exist.** [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) requires that `retrieve_precedent` feed `suggest_remediation` only and **never reach `assess_finding`**, and it is also why the store holds deterministic findings rather than judged ones. [ADR-0013](./0013-adjudication-is-a-third-instrument.md) already extends the same prohibition to `adjudicate` — "it reads no precedent and no prior finding… phase 6a cannot reach it without widening one" — which is the stronger of the two, because `adjudicate` is the instrument κ is measured on. Neither prohibition is new here. What is new is that phase 6a is the first time either has code to bite on, so both gain **import-level tests** in the pattern `test_layer_ordering.py` already uses. A store that persists is a store whose contents accumulate, so a leak into either component would contaminate more with every run rather than less.
- **It does not un-blind the attacker, and that constraint gets stricter as the store grows.** `retrieve_precedent` strips target identity before the attacker sees anything ([ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md)). With one run's findings, identity stripping is a formality; with many runs' findings, precedent becomes a corpus in which an attacker could recognise a target by its failure pattern. Durability is what makes the stripping load-bearing rather than decorative.

## Considered options

- **`InMemoryStore`, documented as ephemeral.** Cheapest, and it fails the claim. If the store is ephemeral then PLAN §10's table row is wrong, and the honest repair would be to withdraw the long-term-memory claim rather than to footnote it away. Withdrawing it costs one of four medium optional tasks; building a durable store costs a file.
- **Add a database-backed Store — `langgraph-checkpoint-sqlite`, Postgres.** `langgraph.checkpoint.sqlite` is not currently installed. A dependency, a schema and a lifecycle for a single tenant's findings is out of proportion now, and it is the right answer at P1 when cross-tenant isolation arrives and brings a real query surface with it. Revisit there, with the isolation requirement in hand rather than guessed at. *[Revisited earlier and for a different reason — [ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md). The dependency stopped being one, because [ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) installed the package for the approval checkpointer and it ships `langgraph.store.sqlite.SqliteStore` beside the saver; the schema became the package's; the lifecycle stayed one file in one ignored directory. Postgres is still deferred to P1 on exactly this paragraph's reasoning.]*
- **Keep precedent in the case records, which are already durable data files.** Rejected on what the two things are. The case library is the **instrument** — public, versioned by a digest, the same for every user. A finding is about **someone else's agent** and can never be public. Putting them in one place would conflate the thing being measured with the thing measuring, and would put user data inside the digest the library's version is computed over, so a finding would change the library version.
- **Rebuild precedent from the run records on each start.** Plausible, since runs are recorded. Rejected as a store that is really a cache with extra steps: it makes the retrieval path depend on every historical run document being present and parseable, and it answers "is this durable?" with "only as long as nobody prunes the reports."

## Consequences

- One module implementing `BaseStore` over a file, or a durable backend dependency if one turns out to be proportionate. Either way the retrieval node depends on the interface.
- A restart test, which is the acceptance criterion for the claim rather than a nicety.
- `retrieve_precedent` and `suggest_remediation` gain real inputs; the attacker's tool stops reading a stub.
- Cross-tenant isolation stays a named P1 blocker, and the single-tenant namespace is the place a reader can see it.
- The store's location is git-ignored, and the repository never carries a finding about a real target.
- **The value of the store cannot be demonstrated inside one run**, so any showcase of remediation quality needs two runs against the same target. Worth knowing before someone tries to demo it in one.

Cross-references: [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (precedent feeds remediation only, and holds deterministic findings), [ADR-0013](./0013-adjudication-is-a-third-instrument.md) (adjudication reads no precedent — the constraint this gives teeth to), [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (identity stripping, which durability makes load-bearing), [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) (the store over deterministic findings), [ADR-0008](./0008-repo-disclosure-posture.md) (why findings are never committed).
