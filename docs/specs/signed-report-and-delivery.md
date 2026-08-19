# Spec — The signed report, and the layer that delivers it

**Scope:** phases 5, 6a, 6b, 7 and 8 of the Sprint 3 line. 16 hours.

**These are the 16 hours [the first spec](./pre-web-bench.md) deliberately carved out.** That one built the bench up to and including its own calibration and stopped, because a number from an unvalidated bench is exactly as trustworthy as the questionnaire it replaces. The gate has since passed twice on the declared models — 2026-08-18 and 2026-08-19, six fit families of six, both runs recorded in [validation.md](../validation.md) — so the precondition every phase below waits on is met. What this spec adds is defined by the two things the first one did not have: **a renderer and a user**.
**Governing documents:** [PLAN.md](../../PLAN.md) · [CONTEXT.md](../../CONTEXT.md) · [ADR-0001 … ADR-0020](../adr/)
**Vocabulary:** every term below is defined in `CONTEXT.md`. **Family**, **case** and **attempt** are three different things; so are **attempt**, **episode** and **turn**. Two more carry weight here that carried none before: a **band** summarises one target and never enters the gate ([ADR-0014](../adr/0014-band-cut-points-are-the-reference-agents-constructed-rates.md)), and a **finding** is what a user is shown.

---

## Problem Statement

The bench works and can prove it, and nobody outside this repository can read the proof.

A gate result is a document in `docs/gate-runs/` and a series of TOML blocks on eighteen case records. It is re-derivable, which is the property the first spec was built to earn — but re-derivable *by someone holding the repository*. The engineer this project exists for cannot run it, and the procurement reader who carries the commercial risk cannot check it. The mission sentence is that agent safety evidence does not travel; the bench currently produces evidence that travels less well than the questionnaire it replaces, because at least a questionnaire can be emailed.

Three specific gaps, and they are not the same gap.

**Nothing signs anything.** `PLAN.md` has claimed "real Ed25519 signing and offline `verify`" since the first commit and no key has ever existed. The word *signed* appears in the mission statement and in no code path. Until it does, "remains checkable after it leaves the engineer who produced it" is an intention.

**There is no user, so there is nothing to report about.** Every run this repository has made was against its own reference agents, which are test equipment and never reach a user. A run against a registered target is a different thing from a gate run, and the report is about the former while every number the bench has produced so far is about the latter. Building the renderer is where that distinction either gets made carefully or gets lost.

**The long-term memory the plan claims does not exist.** The precedent store is one of the four medium optional tasks the project claims, and `retrieve_precedent` — one of the adaptive attacker's five tools — currently reads a stub.

## Solution

Turn one target run into an artefact a stranger can check, and deliver it through the smallest interface that does not lie about it.

A **structured result** already exists: `assembler.py` emits per-family entries and the declared-and-defeated join with no scalar anywhere. Phase 5 adds two things on top and nothing else. First, a **canonical JSON payload** — the artefact, byte-stable by construction — carrying the per-family bands for this target, the declared-and-defeated join, negative coverage against the OWASP 2026 list, a provenance block, and the adaptive section marked as recorded rather than re-derivable. Second, an **Ed25519 signature over that payload**, with a rendered Markdown view bound to it by hash, so the document a human reads cannot be substituted for one a machine verified. `scripts/verify.py` checks all three properties offline: the signature, the binding, and — the part that makes *re-derivable* a property rather than a sentence — the arithmetic, recomputed from the payload and compared against what the payload claims.

The **distinction the renderer exists to protect** is that the gate is a claim about the bench and the report is a claim about a target. A user's run is not a gate run: it produces rates, intervals and bands for their agent, and it produces no gate decision about it. The instrument's own gate result appears in the provenance block as a citation — passed, on this date, at this library version, with a pointer to the run document — and never as a verdict on the reader's agent. A report that blurred those two would be the badge D3 forbids, arrived at by accident rather than by design.

The **precedent store** is then the long-term memory the plan claims, built where it can do no harm: over deterministic findings only, feeding `suggest_remediation` and nothing else, and reached by the adaptive attacker through `retrieve_precedent` with target identity stripped, so that memory cannot become the channel that un-blinds a label-blind attacker.

The **API** exists because one target run is 180 scored calls plus up to 96 adaptive ones and a single request that returns the result would time out. It reports cost and progress **per layer**, because a blended figure hides which half of a run is spending the user's money. The **three screens** are the smallest interface that can register a target, hold a human at the approval interrupt, and show a finding without printing a score the project has argued for fourteen ADRs that it must not print.

## User Stories

### The signed artefact

1. As a report recipient, I want to check a report's signature with a script and no network, so that the evidence is verifiable by someone who does not trust the sender and cannot reach them.
2. As a report recipient, I want the signature to cover the whole document, so that I can detect alteration of any part of it rather than only the part somebody chose to protect.
3. As a report recipient, I want to be told plainly which parts of the document are re-derivable and which are merely recorded, so that a valid signature is not mistaken for a claim that every figure in it is reproducible.
4. As a report recipient, I want the human-readable document bound to the signed payload by hash, so that a doctored rendering cannot travel beside a valid signature.
5. As a report recipient, I want the verifier to recompute the arithmetic from the payload and tell me whether it agrees, so that *re-derivable* is something I checked rather than something the document asserted.
6. As a report recipient, I want to know which key signed a document and where its fingerprint is published, so that a valid signature over an unknown key is not mistaken for provenance.
7. As a bench engineer, I want the private key read from the environment and never committed, so that publishing this repository does not publish the ability to forge its reports.
8. As a bench engineer, I want an unsigned run to be impossible to present as signed, so that the word means one thing.

### What the report says, and what it refuses to say

9. As an engineer shipping an agent, I want per-family rates with their intervals and a band for my target, so that I can see which failure modes my agent has rather than a grade.
10. As an engineer shipping an agent, I want no composite score anywhere in the document, so that nobody in my organisation can quote a number the bench does not stand behind.
11. As a procurement reader, I want the report to state which OWASP 2026 categories the bench does not test at all, so that I can see the boundary of the claim rather than infer coverage from a label.
12. As a procurement reader, I want each family to state the case inside its identifier that it does not test, so that a passed family is not read as a cleared category.
13. As a procurement reader, I want the instrument's own gate result cited in the provenance block with its date and library version, so that I can tell a validated instrument from an asserted one — and I want it stated as a fact about the bench rather than as a verdict on the agent I am assessing.
14. As a procurement reader, I want the declared-and-defeated join printed, so that I can see which controls the vendor declared and which of those the bench defeated.
15. As a procurement reader, I want to be told that the report's *format* has never been validated against a real procurement reader, so that its structure is not mistaken for an industry expectation.
16. As a security analyst, I want a family the target could not be measured on to say so, so that an unmeasurable family is never read as a defended one.
17. As a security analyst, I want a judged family below the κ floor to be absent from the report with the reason stated, so that a number the bench cannot vouch for is not published.
18. As an engineer shipping an agent, I want the adaptive section to describe routes in prose and never as payload text, so that my own report is not a working exploit somebody can lift.

### The precedent store

19. As an engineer shipping an agent, I want remediation advice informed by what the bench has seen before, so that the fix I am handed is not reinvented from one transcript.
20. As a bench engineer, I want the precedent store to hold deterministic findings only, so that precedent never carries a judgement whose reliability is unstated.
21. As a bench engineer, I want precedent unable to reach the judge or the adjudicator by construction, so that the κ figure the judged families depend on cannot be contaminated by a later phase.
22. As a bench engineer, I want the attacker's precedent stripped of target identity, so that long-term memory does not become the channel that un-blinds a label-blind attacker.
23. As a bench engineer, I want the store to survive a process restart, so that "long-term memory" is not a claim with the lifetime of one run.

### Running a target through the API

24. As an engineer shipping an agent, I want to register my target and prove I control it before anything is sent, so that the bench cannot be pointed at somebody else's system.
25. As an engineer shipping an agent, I want the estimated cost as two figures — the fixed suite exactly and the adaptive layer as a ceiling — so that I am agreeing to a number rather than to an average.
26. As an engineer shipping an agent, I want the run to halt until I confirm, so that nothing spends my inference budget without my say.
27. As an engineer shipping an agent, I want a run id back immediately, so that a run that takes many minutes does not depend on a request staying open.
28. As an engineer shipping an agent, I want progress and calls spent reported per layer, so that I can see which half of the run is consuming the budget.
29. As an engineer shipping an agent, I want an aborted adaptive episode recorded as censored, so that my budget running out is never reported as my agent resisting.

### The three screens

30. As an engineer shipping an agent, I want a register screen that walks me through the nonce and the three attestations, so that the authorisation guard is a step I complete rather than an error I hit.
31. As an engineer shipping an agent, I want the approval interrupt to be a screen that blocks, so that confirming the cost is a decision and not a checkbox I scrolled past.
32. As an engineer shipping an agent, I want to watch the run progress by layer, so that a long run is observable while it happens.
33. As an engineer shipping an agent, I want to read the report in the browser and download the signed artefact, so that what I show a customer is the thing that verifies.
34. As an engineer shipping an agent, I want the interface to show verification status on the report screen, so that I find out the artefact is checkable before I send it to a customer.

### The reflection

35. As a reviewer, I want the two defects in this system named rather than hidden, so that the honest limits are part of the deliverable.
36. As a reviewer, I want the defects this sprint discovered added to that list, so that the reflection is current rather than the version written before the bench ran.

## Implementation Decisions

**The signed artefact is canonical JSON, and the rendered document is bound to it by hash.** A signature covers bytes, and a human reads prose, so the two are joined rather than conflated: the payload is serialised with sorted keys and fixed separators, `rendered_sha256` inside the payload is the digest of the Markdown view, and `key_id` names the signing key. Signing the Markdown directly was rejected because it makes byte-stable rendering a permanent obligation and leaves re-derivation to prose parsing; leaving the rendering unbound was rejected because a doctored document beside a valid signature is the failure the signature exists to prevent.

**The signature covers the whole document, and the document carries two claims rather than one.** *Integrity* — this reached you unaltered — is stated for the whole artefact. *Re-derivability* is stated for the scored layer alone, and the adaptive section is marked recorded-and-not-reproducible in the payload and in the rendering. This is `scripts/gate.py`'s existing discipline, which prints both statements together because a run claiming one without the other would be claiming the stochastic half was reproducible by omission. ADR-0010 forbids the adaptive layer from entering a rate, an interval, a discrimination score or the gate decision; it does not require its bytes to be left unprotected, and a security report with an unprotected section would be a worse artefact for a strictly worse reason. Recorded as [ADR-0017](../adr/0017-the-signature-covers-the-document-and-carries-two-claims.md), which also reconciles PLAN §3's architecture diagram: it labels the adaptive layer *never signed* in as many words, which is correct about which numbers the signature vouches for and overstated about which bytes it covers. ADR-0010's own title says never *scored*, the narrower and correct claim.

**The report is about a target; the gate is about the bench.** These are different claims with different denominators and the renderer keeps them apart structurally rather than by wording. A user's run produces per-family rates, intervals and bands, and **no gate decision**: `read_gate` is never called on a target run, and there is no field in the payload that could carry one. The bench's own gate result appears in the provenance block as a citation — outcome, date, library version and digest, and the path of the run document — and is typed as provenance rather than as a result. Recorded as [ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md), which adds the argument this spec only asserted: not one of the four quantities the gate is decided on — `D`, monotonicity, and the two family counts — has a definition when the subject is a single target, so there is no arithmetic that could produce a target gate decision and any such field could only be filled by copying the bench's own result across.

**Report structure is Annex IV section order, and the report says its format is unvalidated.** ADR-0001 records that the format is an open question to be answered by real procurement readers during recruitment rather than assumed. Track A did not run, so no reader has been asked. The structure is therefore a defensible default and is labelled as one, in the document and in `validation.md`; ADR-0001's question stays open rather than being quietly closed by shipping something.

**Key handling: one long-lived key pair, private half from the environment.** The private key is read from `AGENTAUDIT_SIGNING_KEY` and never committed; the public key is committed and its fingerprint published in the README, so a recipient checking a signature is trusting a key published where they can see its history rather than one that arrived with the document. `verify.py` pins the committed public key by default and takes `--pubkey` for another. Ed25519 comes from `cryptography`, added as a dependency. **The API factory refuses to boot without the key**, rather than serving a bench whose every report is refused as `never_signed` after the run has been paid for: a deployment that cannot sign cannot produce the only artefact this project claims to make, so the absence fails at startup where nothing has been spent yet. [ADR-0020](../adr/0020-a-factory-with-no-signing-key-refuses-to-boot.md).

**`scripts/verify.py` is offline and prints three results, not one.** Signature valid; rendered view matches its digest; arithmetic re-derived from the payload agrees with the payload's own figures. The third is the point of the exercise, and it is what makes the verifier a check on the *bench* rather than only on the transport.

**The precedent store is a `BaseStore` over deterministic findings, with a durable backend.** LangGraph's `BaseStore` and `InMemoryStore` are both available in the pinned version, and the store is namespaced single-tenant. `InMemoryStore` alone was rejected: a long-term memory that dies with the process makes the claim false, so the store is backed by a file — a small `BaseStore` implementation over JSON if no durable backend is available without a heavy dependency. [ADR-0019](../adr/0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md). Only deterministic findings enter it, so precedent never carries a verdict whose reliability is unstated.

**Precedent reaches `suggest_remediation` and nothing else, and an import test says so.** Two of these constraints are not this spec's to invent: ADR-0004 already requires that `retrieve_precedent` feed `suggest_remediation` only and **never reach `assess_finding`**, and it is also where the store's deterministic-findings-only shape comes from. The prohibition on reaching `adjudication.adjudicate` is not new either: [ADR-0013](../adr/0013-adjudication-is-a-third-instrument.md) already states that adjudication "reads no precedent and no prior finding" and that "phase 6a cannot reach it without widening one" — and it is the stronger of the two, because `adjudicate` is the instrument κ is measured on. **What this spec adds to both is enforcement.** Phase 6a is the first time either prohibition has code to bite on, so each gains an import-level test rather than resting on a signature nobody is required to leave narrow. `retrieve_precedent` strips target identity before the attacker sees anything, because an attacker that can read *which target* a precedent came from is no longer label-blind (ADR-0011). The constraints are held by signatures and by an import-level test in the pattern the repository already uses, not by a rule somebody has to remember.

**The API is FastAPI, and LangGraph stays where it earns its place.** `fastapi` and `uvicorn` are already declared dependencies; `langgraph_api` and `langgraph_cli` are not installed. More decisively, the scored run is not a graph — it is `run_calibration`, plain Python over recorded attempts — so LangGraph Server has no graph to serve, and giving it one would mean restructuring the measurement to gain a server. PLAN §8 asked for this check and licensed the answer: FastAPI background tasks are enough for v1, a queue is P1. LangGraph keeps the approval interrupt, which is a real `interrupt()` against a checkpointer, and gains the Store.

**Three endpoints, and the two cost figures are never blended.** `POST /runs` records the estimate as the fixed suite exactly and the adaptive ceiling separately, halts at the approval interrupt, and returns a `run_id` at once. `GET /runs/{id}` reports position and calls spent **per layer** — family, case and attempt in the scored layer; family, episode and turn in the adaptive one. `GET /report/{id}` serves the signed payload, with the rendered view alongside it. The frontend polls.

**The interface is three screens and prints no total.** Vite, React and TypeScript, per PLAN §7. Register carries the nonce plant, the three attestations and the tool-visibility declaration. Run is the approval interrupt as a screen that blocks on both figures, then per-layer progress. Report renders from the signed payload and shows verification status, both claims, the negative-coverage list and the declared-and-defeated join. There is no element anywhere in the interface that combines families arithmetically, because D12 and ADR-0005 are properties of the product and not of the backend.

**The reflection notes are documents, and they are current rather than inherited.** PLAN §13's two defects — applicability drift with gold-set contamination, and automation bias — plus the two this sprint measured: `A_break` landing on opposite rows of ADR-0011's reading table across two certified runs of the same declared configuration, and a stub reading sitting in the retirement series on the same footing as a certified one (#43).

## Testing Decisions

**The signature is tested by tampering, not by round-tripping.** A test that signs and verifies proves the library works. The tests that matter alter one byte of the payload, alter the rendered view without updating its digest, present a valid signature made by a different key, and re-derive arithmetic that disagrees with the payload's claim — each must fail verification with its own named outcome, so a recipient learns *which* check failed.

**The report is tested for what it must not contain.** Assertions that no field, no property and no rendered element totals or averages across families; that no gate decision about the target exists anywhere in the payload; that a family below the κ floor is absent with its reason present; that a not-measurable family is distinguishable from a rate of zero; and that no payload text from any case appears in the adaptive section.

**The precedent prohibitions are tested at the import level.** `judge.py` and `adjudication.py` must not be able to reach the store, in the pattern `test_layer_ordering.py` and the crossmodel import tests already use — a test that fails if a future contributor adds the import, rather than a docstring asking them not to.

**The store is tested across a restart**, because that is the whole content of the claim it satisfies.

**The API is tested at the boundary.** That a run cannot start without a completed attestation and an echoed nonce; that nothing is sent before the interrupt is answered; that the two cost figures arrive unblended; that progress reports per layer; and that a budget abort mid-episode records the episode as censored.

**The interface is driven by hand, screen by screen, and the spec expects that.** Three screens inside a 4.5-hour phase do not justify a browser-driver harness, and the screens' load-bearing behaviour — does the approval screen actually block, does the report show a total anywhere — is exactly what a person checks faster than a test does. What *is* automated is the absence of a total, asserted against the payload the screens render from.

**Every new test is driven red once before it is committed**, per the repository's standing rule. A test that has never failed is not known to work.

## Out of Scope

- **The typed override taxonomy, the feedback loop and the review screen.** These wait on a real user disputing a real finding, per ADR-0006, and Track A has not run. `case_gap` into the admission gate is the remaining half of the "agent that learns" task and it waits with them.
- **A writer for a proposal that clears the cross-model bar** (#42). The bar is enforced and nothing has ever cleared it; the missing piece is a coverage claim about a payload nobody authored, which is a decision before it is code.
- **Model-scoping the retirement series** (#43). A stub reading currently sits in the series on the same footing as a certified one. It is named in the reflection notes of this spec and fixed in neither.
- **ADR-0015's repair route for wrongful commitment.** Rewriting the criterion and labelling a fresh gold set is a new instrument honestly measured, and it is not this spec's work.
- **Cross-tenant isolation.** Not applicable before user one, and a P1 blocker when it arrives. The store is namespaced single-tenant and says so.
- **Scheduled runs, email delivery, the queue, Terraform, a live URL and Langfuse.** All P1.
- **The plugin UI of medium optional task 6.** Written off in PLAN §10 for reasons the adaptive layer did not change.
- **New families to close the declared coverage gaps.** P2. Gaps are listed in the report, not closed by it.
- **Any claim of conformity, certification, insurance, pricing or a badge.** Out of scope permanently, per D3 and ADR-0001.

## Further Notes

**The most likely way this spec fails is by producing a report that reads like a grade.** Every individual decision above resists it — no scalar, no badge, bands rather than a score, intervals printed, negative coverage listed, the gate cited as provenance — and none of them is the safeguard. The safeguard is that a reader who wants a single number will construct one from whatever is on the page, so the page must not make it easy. An implementer who finds themselves adding a summary element "just for the overview screen" has found the failure mode, not a gap.

**A signature is not a quality claim and the artefact must not let anyone think it is.** It says this document is the one that was produced and it has not been altered. It says nothing about whether the agent is safe, and the two claims live one line apart in the document — which is precisely why the second claim, the re-derivability one, is printed beside it rather than left implicit. Automation bias is one of the two defects PLAN §13 names, and a signed document is the exact artefact that triggers it.

**The report's format is the weakest part of this spec and it is weak for a stated reason.** ADR-0001 says a real procurement reader must answer it, no reader has been asked, and building to Annex IV is a default rather than a finding. The honest form of that is a label in the document, which this spec requires. The dishonest form is silence, and silence would be indistinguishable from having asked.

**The API and the interface are the smallest thing that does not lie**, and that is a scope decision rather than a compromise. Four hours of React can show a finding, hold a human at a cost interrupt and offer a download. It cannot review, annotate, dispute or compare, and the phases that would are deferred to a user this project does not have.

**Two decisions here exist to protect the numbers the last spec earned.** Precedent's inability to reach the judge or the adjudicator, and the report's inability to carry a gate decision about a target, are both constraints on code that does not exist yet, expressed as types and import tests rather than as guidance — because both would fail silently, and both would fail in the direction that flatters the product.

**Published** as issue #48, broken into twelve tracer-bullet tickets as issues #49 to #60, all linked as sub-issues with native `blocked_by` edges and labelled `ready-for-agent`. Four start immediately — the payload (#49), the precedent store (#52), `POST /runs` (#54) and the reflection notes (#60) — and the frontier moves as blockers close. Phase 5 is a chain (#49 → #50 → #51), because the rendering's digest goes inside the payload before the signature covers it. Work one ticket per fresh context.

**The interface tickets are meant to be driven by hand, one screen at a time**, and #57 to #59 are sized for it: the register screen carries the frontend's existence, the run screen carries the interrupt that has to block, and the report screen carries the absence of a total. That last one is the only screen with an automated assertion behind its main claim, and it is asserted against the payload the screen renders from rather than against the rendering.
