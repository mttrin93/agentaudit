# Spec — The MCP server, and the agent that drives the bench through it

**Scope:** a fourth delivery surface for a run, beside the console, the CLI and the Action. No new bench behaviour.

**A surface and not a capability.** [The signed report](./signed-report-and-delivery.md) built the API and the three screens; [ADR-0066](../adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) built the Action, which is the same bench reached from a runner with the caller's checkout on disk. This spec adds a third way to reach it — a coding agent, in the operator's own repository, at a moment of the operator's choosing — and it is deliberately not a fourth way to *run* anything: every tool below is a translation of a route that already exists, and a tool that needed bench behaviour the console cannot reach is out of scope by construction.
**Governing documents:** [PLAN.md](../../PLAN.md) · [CONTEXT.md](../../CONTEXT.md) · [ADR-0007](../adr/0007-canary-nonce-as-proof-of-control.md) · [ADR-0050](../adr/0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md) · [ADR-0066](../adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) · [ADR-0069](../adr/0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md) · [ADR-0073](../adr/0073-two-labels-on-a-fix-and-no-third.md)
**Vocabulary:** every term below is defined in `CONTEXT.md`. A **run**, a **finding** and an **attempt** mean exactly what they already mean. Two words this spec adds are not bench vocabulary and never enter one: a **tool** is an MCP tool exposed to a client, and a **declaration file** is a committed file in the operator's repository. Neither is a **case**, and neither is an input to any figure.

---

## Problem Statement

The bench can be reached by a human at a browser and by a runner on a push, and not by the one consumer best placed to act on what it finds.

The engineer this project exists for now works with a coding agent inside their own repository. That agent holds the two things every other surface has to be told: which commit is checked out, and what the code at that commit does. The bench holds the third — what the agent under test failed at, and the control that would have stopped it. Nothing connects them. The operator reads a finding in a browser tab, and retypes it.

Three specific gaps, and they are not the same gap.

**The report's prose is aimed at a procurement reader, and the loop it could close is a development loop.** `ReportedFinding` carries `reason` and `fix` — *what went wrong* and *what to change*, the two sentences [ADR-0069](../adr/0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md) separated. In a repository, beside the code, those are a change request. In a browser, they are a paragraph somebody copies.

**A commit is the one identifier the artefact does not carry, and the only one that matters to a reviewer.** No field of the signed payload names a revision, and adding one would be a change to a signed artefact rather than a change to a delivery surface. But an agent in the checkout already knows it. The join is free, and it exists nowhere.

**The Action is push-shaped, and iteration is not.** [ADR-0066](../adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md)'s surface runs when a push happens. An engineer changing a system prompt wants to ask the bench a question before the push, and today's answer is *open the console and walk the register screen again*.

## Solution

Expose four tools over the API that already exists, and put the declaration in a file instead of in a chat.

An **MCP server** speaks to a running AgentAudit API over HTTP. It is a translation layer: it holds no bench, no case library, no signing key and no lease, and it starts no process. Everything it enforces is enforced on the far side of a route — which is the property that makes it safe to hand to a model, because a tool that cannot exceed the console's privilege cannot be argued into exceeding it.

A **declaration file**, `agentaudit.toml`, committed at the operator's repository root, carries what the Action already takes as inputs: the endpoint or callback, the target's name and agent type, `exposes-tool-calls`, the declared tools, `note-planted`, the target's planted nonce, the identity, the currency and price, and paths to the attestation and bar files — defaulting to the `.github/agentaudit-*` paths the Action defaults to. One declaration, two surfaces, reviewed in a pull request. This is not a convenience: `POST /runs` takes the whole declaration on every start and there is no stored target to reference, so the alternative is a questionnaire answered in a chat transcript, where a half-answer becomes a declared control the operator never meant to claim and every `attributed_cause` in the report is read against it.

The **consent gate is a separate tool call**. `start_run` returns the estimate and the two ceilings and stops, holding the interrupt; the model relays the figure; the operator says yes; the model calls `approve_run`. Nothing about [ADR-0007](../adr/0007-canary-nonce-as-proof-of-control.md) is relaxed for a caller that happens to be a model, and a run that could approve its own spend is a run whose ceiling is a comment.

The **report a tool returns is compact and keeps every label**. The signed payload is written for a reader who has only the document; a caller that can fetch the document does not need its caveats inlined four times. So the tool returns the figures, the two sentences, and every closed-set member — `findings.reading`, `reproducibility`, `fix_standing.reading`, `source_anchor.reading`, `withheld`, the attempts-per-case warning — and hands back URLs for the payload, the rendering and the signature rather than their contents. A compact reading may drop prose. It may never drop a label: the prose restates what a label already carries, and the label is the part a caller can branch on.

## User Stories

### Driving a run from the repository

1. As an engineer with a coding agent, I want to start a run against my declared target without leaving my editor, so that asking the bench a question costs me a sentence rather than a browser walk.
2. As an engineer, I want the run's declaration to live in a committed file, so that what my agent claimed about itself is reviewed in a pull request rather than retyped per run.
3. As an engineer, I want one declaration read by both the Action and the MCP server, so that a push-time run and an on-demand run are measuring the same declared target.
4. As an engineer, I want to be shown the estimate and both ceilings before anything is sent, so that a model triggering a run cannot spend my inference budget without my seeing the figure.
5. As an engineer, I want approval to be a separate call I authorise, so that no prompt, framing or tool description can turn starting a run into paying for one.
6. As an engineer, I want to poll a run's progress with its per-layer spend, so that a run that is minutes long is legible while it happens.

### What the agent is handed

7. As an engineer, I want each finding's *what went wrong* and *what to change* returned as fields, so that my coding agent can act on them without parsing a rendered document.
8. As an engineer, I want the case id, family, transform and attributed cause beside them, so that the control the failure is read against travels with the failure.
9. As an engineer, I want the commit joined by my own agent rather than by the bench, so that the artefact stays a claim about a target and not a claim about a revision it never read.
10. As an engineer, I want a fix returned with its standing, so that a suggestion my reviewer acts on is never mistaken for a change this bench proved ([ADR-0073](../adr/0073-two-labels-on-a-fix-and-no-third.md)).
11. As an engineer, I want the artefact URLs returned rather than the artefact, so that the signed document is fetched deliberately and is not summarised into a context window by accident.

### What a compact reading may not do

12. As a bench engineer, I want every closed-set member in the findings section to survive into the compact reading, so that summarising drops sentences and never facts.
13. As a bench engineer, I want a run whose narrative instruments broke to return that reading and the instrument's message, so that a caller is never told a target had no failures when the truth is that the judge was unreadable ([ADR-0050](../adr/0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md)).
14. As a bench engineer, I want a run below the declared attempts-per-case to say so in the compact reading, so that a rate a model quotes carries the rule it was measured at.
15. As a bench engineer, I want no tool to compute a figure the payload does not carry, so that the prohibition every other surface keeps is kept by this one ([ADR-0006](../adr/0006-overrides-never-change-a-measured-rate.md)).

### When it goes wrong

16. As an engineer, I want an unreachable API to say so plainly, so that a missing server is not reported to me as a bench with no findings.
17. As an engineer, I want a run that halted without producing an estimate to be a named error, so that `NeverPresented` reaches me as a stated failure rather than as a run that never answers. The case-library lease is deliberately not on this list: `LibraryBusy` is raised in `api/gate_runs.py` and nowhere else, so a target run never takes the lease and this surface cannot meet it.
18. As an engineer, I want a withheld attestation statement to name which one, so that a refused start is actionable without opening the console.
19. As an engineer, I want a run that ended declined, unanswered or aborted to be distinguishable from one that completed, so that an absent report has a reason attached.
20. As an engineer, I want a request for the report of an unsigned run to carry the refusal's own reason, so that the word *signed* means one thing on this surface too.

## Implementation Decisions

**Four tools, and each is one route.** `start_run` (`POST /nonces` when the file carries none, then `POST /runs`), `approve_run` (`POST /runs/{id}/approval`), `run_status` (`GET /runs`, this run's row), `run_report` (`GET /report/{id}`, compacted). A fifth tool is a fifth route, and a tool without a route behind it is bench work wearing an MCP name.

**The server holds no bench object.** It imports no module of `backend/bench/`, and an import-level test holds that — the same shape the wall between `proving.py` and the narrative instruments already has. What it may import from `backend/` is the wire contracts it decodes into, and nothing that could run, score or sign.

**The compact reading is built in one function, from the payload and nothing else.** No second source, no recomputation, no default for a field the payload did not carry. It is the one place a label could be dropped, which is why it is one place.

**`start_run` never approves and `approve_run` never starts.** Two tools rather than one with a `confirm` argument: an argument defaulting either way is a consent decision made by whoever wrote the default, and the whole point of the seam is that the decision is the operator's ([ADR-0007](../adr/0007-canary-nonce-as-proof-of-control.md)).

**The declaration file is read, never written.** No tool edits `agentaudit.toml`, issues a declaration on the operator's behalf, or fills a field it found empty — except the nonce, which is fetched from `POST /nonces` when absent and returned to the caller to plant, exactly as the register walk does. A surface that could write a declaration is a surface that could declare a control.

**No `git` in the server, and no revision in any payload.** The commit is the caller's to supply. This is the decision that keeps the artefact what [ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) says it is — a claim about a target — rather than a claim about a revision the bench never read.

**Two ADRs, and this spec does not stand in for them.** *The MCP server has no privilege the console lacks* is a decision with alternatives that lost, and so is *a compact reading may drop prose and never a label*. Both are argued above in their local form; the decisions themselves, their alternatives and why the alternatives lost are recorded in [ADR-0100](../adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md) and [ADR-0101](../adr/0101-a-compact-reading-may-drop-prose-and-never-a-label.md), per `CLAUDE.md` — a decision belongs in an ADR, not in a paragraph appended to a neighbouring one.

## Testing Decisions

**The tools are exercised against the real app.** Through FastAPI's `TestClient` over `create_app`, not against recorded fixtures, so a route signature or payload field that moves breaks the MCP tests in CI rather than in somebody's chat. Recorded fixtures would make this surface exactly as current as the day somebody last refreshed them.

**The label-preservation rule is a walk, not a list.** A test walks the findings section of a served payload and asserts that every closed-set member it finds is present in the compact reading. A hand-written list of fields to check is a list that stops checking the day a member is added — which is the failure mode `WithheldProse` and `FindingsReading` were made closed sets to prevent.

**All four readings of `narrations` are tested at the tool boundary.** Particularly `instruments_broke`, whose evidence already exists: a run against a declared target returned `judge_unreadable` after the narrative model answered `reads_as` with two exposure values. A compact reading that turned that into an empty findings list would be the bug this story is written from.

**The consent seam is tested by trying to bypass it.** A test asserts that no argument to `start_run` reaches a confirmed run, and it is driven red by adding one.

**Every new test is driven red once, for the right reason, before it is committed.** `CLAUDE.md`'s standing rule.

## Out of Scope

- **Registration.** The register walk asks the declared-controls checklist and the four Rule of Two questions, and it stays in the console. The MCP server reads a declaration that already exists; the first run against a new target still needs the browser.
- **A commit in the signed payload.** Argued above as the decision that keeps the artefact's subject stable. If a revision ever belongs in the artefact it is a change to `payload.py` under its own ADR, and the MCP server is not the reason to make it.
- **Generating a patch or a code snippet.** `Remediation.fix` stays prose ([ADR-0069](../adr/0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)), and `throwaway.Patch` stays the operator's own code (ADR-0072 §2). The coding agent on the far side of the tool writes the change — which is the division those ADRs already chose, reached by a consumer that can honour it.
- **Driving the proof loop.** `proving.prove_patch` has no caller in the run path today. Wiring it is its own scope, and doing it through a tool call first would give this surface a privilege the console lacks.
- **Elicitation-based approval.** The client-native prompt is a better experience than a relayed estimate and depends on client support this design does not require. The seam is unchanged if it is added later.
- **Unattended loops.** A run that self-approves under a pre-declared ceiling is a real want and a different consent argument. Nothing here forecloses it; nothing here builds it.
- **Gate runs.** `/bench/gate` is about the instrument, not a target ([ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)). A tool that could start one would let a model spend the bench's own validation budget.
- **Starting the API.** The server assumes a running app and says so when there is none. Process lifetime is the operator's.

## Further Notes

**The compact reading is the first place this project summarises its own report, and it is worth being nervous about it.** Fourteen ADRs argue that a figure without its qualification is the badge D3 forbids. The defence here is structural rather than editorial — labels survive, prose does not, and a walk over the payload enforces it — but the failure mode to watch for is a caller that reads the numbers and never fetches the document. That is a property of the consumer, not of this surface, and the honest thing to record now is that this spec cannot prevent it.

**A model is a new kind of reader and the sentences were not written for it.** Every `stated` field in the payload is composed for a human who has only the document. Nothing here rewords them, and the compact reading drops most of them. Whether an agent acting on `reason` and `fix` alone acts *well* is unmeasured, and the bench has no instrument that would measure it — the same honesty [ADR-0019](../adr/0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md) applies to the precedent store's own value.
