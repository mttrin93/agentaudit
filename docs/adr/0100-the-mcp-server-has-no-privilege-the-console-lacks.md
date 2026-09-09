---
status: accepted
---

# The MCP server has no privilege the console lacks

Every surface this bench has so far was reached by somebody who could be held to what
they asked for. A human walks the register screen and answers the declared-controls
checklist; a runner executes a composite step a reviewer approved into the caller's
own repository ([ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md)).
The privileges of those surfaces were scoped for that reader. The MCP server's caller
is a model, in a context window a stranger's text can reach — a tool surface reached
by a model is a surface where a prompt can ask for anything the surface can do, and
the asking costs nothing.

The usual defence is to make each tool careful: descriptions that say what the tool is
for, arguments that refuse the dangerous shapes, prose in a system prompt about what
not to do. All of it is text, addressed to the same reader the attack is addressed to,
and this bench exists because that reader is not reliably persuaded. The bench's own
six families are the evidence: a surface whose only protection is wording is a surface
this project would find a break in.

## Decision

**Every MCP tool is a translation of a route that already exists, and the package holds
nothing that could run, score or sign.**

1. **Four tools, and behind each of them only routes that already exist.**
   `approve_run` is `POST /runs/{id}/approval`, `run_status` is this run's row of
   `GET /runs`, `run_report` is `GET /report/{id}` compacted
   ([ADR-0101](./0101-a-compact-reading-may-drop-prose-and-never-a-label.md)), and
   `start_run` is `POST /runs` — preceded by `POST /nonces` where the declaration file
   carries no nonce, which is the register walk's own two steps and not a third thing
   the tool does. A fifth tool is a fifth route or it is not a tool: something with no
   route behind it is bench work wearing an MCP name, and it has no far side to be
   refused on.

2. **The package imports no module of `backend/bench/`.** Not the scorer, not the
   judge, not the assembler, not the library. What it may import from `backend/` is the
   wire contracts it decodes into. This is the wall, and it is the whole of the claim:
   a package that cannot name a bench module cannot start a run inside itself, cannot
   reach a figure that was not returned to it over the wire, and cannot be widened by
   accident in a diff whose reviewer was thinking about a tool description.

3. **It holds no key, no lease, no case library and no process.** No signing key
   material, no case-library lease (the lease is a gate run's and never a target run's,
   so this surface cannot meet `LibraryBusy` at all), no spawned API. The server
   assumes a running app and says so plainly when there is none; process lifetime is
   the operator's.

4. **Every rule a tool appears to enforce is enforced on the far side of the route.**
   The consent seam is the example that matters. `start_run` stops at the estimate and
   `approve_run` is a second call — but a caller that skipped the first tool and called
   the second would still be refused, because the refusal lives in the approval route
   and not in the tool that fronts it
   ([ADR-0007](./0007-canary-nonce-as-proof-of-control.md), and
   [ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) for the
   checkpoint that holds it). The tool boundary is where the seam is *legible*; it is
   nowhere the seam is *held*.

5. **A capability the console lacks is bench work under its own ADR, and never a tool.**
   Registration stays in the browser; `proving.prove_patch` stays uncalled in the run
   path; no revision enters a payload. Each of those is a real want and each is a change
   to the bench, which means an ADR of its own and a route both surfaces reach. What is
   refused here is the shortcut where a capability arrives on the newest surface first
   because that surface is the one currently being written.

## Considered options

**Embedding the bench in-process.** The obvious shape, and the fastest: import
`run_suite`, skip HTTP, return the payload directly. It fails on ownership. The server
would then hold the case-library lease, the signing key and the process lifetime of a
run that outlives any single tool call, and it would become a second way to run the
bench — one that has to be kept in step with the first for ever, on every rule the API
enforces about consent, ceilings, attestation and withholding. Two implementations of
*what a run is allowed to do* is the arrangement where the newer one quietly acquires
the privileges the older one refuses, because nobody diffs them.

**A privileged tool for gate runs.** `/bench/gate` is about the instrument and not
about a target ([ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)),
and a tool that could start one would let a model spend the bench's own validation
budget — the budget that buys the discriminating power every published rate is read
against. The spend is the objection, not the gate's mechanics: the operator's inference
budget is theirs to authorise per run, and the bench's validation budget is not
something any caller of this surface has standing to commit.

**Careful tool descriptions instead of a wall.** Rejected on the reasoning above. A
description is text in the same window as the attack. The import wall is to be checked
by `ast` over the package's own files, and fails in CI rather than in review.

**A read-only mode, with the privileges behind a flag.** A flag is a thing that can be
set, and the setting would be argued for by whoever wanted the capability rather than
by whoever wanted the wall. A privilege this package does not contain cannot be enabled
in a config file.

## Consequences

- **The first run against a new target still needs the browser.** The register walk asks
  the declared-controls checklist and the four Rule of Two questions
  ([ADR-0092](./0092-the-rule-of-two-is-declared-on-the-register-walk-and-the-reading-is-the-backends.md)),
  and this surface reads a declaration that already exists rather than issuing one. That
  is a cost, and it is the cost of the decision rather than an oversight to fix later.
- **An import-level test lands with the package and holds the wall**, on the reasoning
  the bench already uses for `proving.py`: a wall nobody can see from the file they are
  editing is a wall somebody widens by accident. It walks `backend/mcp/` and asserts no
  file names `backend.bench`.
- **A tool that turns out to need bench behaviour is a signal that the scope was wrong**,
  not a licence to reach past the wall. The route comes first, on the API, where the
  console reaches it too.
- **What is not claimed:** that the tools are safe to expose to an untrusted model. They
  are exactly as safe as the routes behind them, which were scoped for an operator with
  the endpoint and its token — which is what the declaration file already gives the
  agent. The claim is narrower and load-bearing: this surface adds no privilege, so the
  question of what a model may do to this bench is answered in one place.
