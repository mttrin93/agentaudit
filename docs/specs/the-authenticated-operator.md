# Spec — The authenticated operator

**Scope:** authentication on the HTTP API and the console, and one field of the signed payload that stops being a typed string. No new bench behaviour, no new route, no new figure.

**A gate and a name, and they are one change.** The bench can be reached by anyone holding the Cloud Run URL, and the field that says who authorised an attack on somebody else's endpoint is a text input. Those are the same defect read at two distances: nothing establishes who is at the console, so nothing can put a founded name in the document. This spec closes both with one seam, and [ADR-0116](../adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md) is the decision it builds.
**Governing documents:** [PLAN.md](../../PLAN.md) · [CONTEXT.md](../../CONTEXT.md) · [ADR-0007](../adr/0007-canary-nonce-as-proof-of-control.md) · [ADR-0020](../adr/0020-a-factory-with-no-signing-key-refuses-to-boot.md) · [ADR-0066](../adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) · [ADR-0116](../adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md) · [ADR-0120](../adr/0120-a-verification-is-a-subject-or-a-refusal-and-never-an-exception.md)
**Vocabulary:** every bench term below is defined in `CONTEXT.md` and none of them changes. Three words this spec adds are not bench vocabulary and never enter one: an **operator** is the human or machine principal a request is authenticated as, a **subject** is the identifier an issuer puts on that principal, and an **issuer** is the hosted identity provider a deployment declares. None of them is a **target**, and none of them is an input to any figure.

---

## Problem Statement

The live bench has no door, and the document it signs names whoever typed a name.

**Anyone with the URL can spend the deployment's budget.** `agentaudit-api` on Cloud Run is `--allow-unauthenticated`, which is what lets the browser reach it, and the API has no authentication of its own. Every control on the console is reachable by anyone who has the host — registering a target, confirming an estimate, and through `/gate-runs` the 830-call operation that spends on the bench's own behalf. The approval interrupt is a real control and it is not this one: it stops a run from spending *without somebody confirming the figure*, and says nothing about who that somebody is.

**`identity` is the one field in a signed report that the signature cannot speak to.** `Attestation.identity` is refused when blank and travels into the payload, where a recipient reads it as the name of the person who took responsibility. A signature proves the bench produced the document and that nobody altered it since. It proves nothing about the name inside, because nothing checked the name.

**The repository already draws this distinction and applies it to only one surface.** `backend/bench/unattended.py` calls the Action's identity "`github.actor`, an authenticated identity rather than a name typed at a prompt." Two surfaces write the same field of the same payload; one of them means it. A reader holding a report cannot tell which.

**And the browser path is weaker still at the second gate.** The console carries the registration's name to the confirmation screen in `sessionStorage`. `frontend/src/run/interrupt.ts` records what happens when it does not arrive: "the body goes with an empty identity and the bench's sentence names nobody, which is a worse record and not a blocked one." That was correct while a name was only a string — the function guards the spend, and a missing name is not a reason to make declining easier. It stops being a trade-off once the name is on a token.

## Solution

One authenticated principal per request, declared into the app rather than read out of the environment, with the subject replacing the typed name at the three places a request becomes a record.

**Authentication is a fourth declaration on `create_app`**, beside `config`, `gate_runs` and `pending_routes`, and it behaves exactly as they do. A caller that declares nothing gets an app with no authentication, which is what every test gets today and what keeps `backend/api/` free of an environment reader. A deployment that declares nothing at all gets the deployed reading — and the deployed reading **refuses to boot** without its verification material, on ADR-0020's reasoning: unconfigured must never mean open.

**The environment is read outside `backend/api/`.** A new top-level `backend/identity.py` holds the one function that reads the issuer's settings, in the place and for the reason `backend/observability.py` already does. Two tests assert no module of the API imports `os` or `dotenv`, and both stay green and unedited.

**Verification is offline.** The token's signature is checked against the issuer's public key held in this process. The console polls a run every two seconds; a check that called the issuer would put it on the critical path of a bench mid-run against somebody's endpoint, and an issuer outage would read as the bench failing. A networked key fetch stays as the fallback for a key this process has not seen.

**`identity` comes off three request bodies and comes from the token instead.** `AttestationRequest`, `ApprovalRequest` and the pending-route measurement request lose the field. A caller can no longer name themselves. This is a change to the deployed surface and it is stated as one: a body that still sends `identity` is refused rather than quietly ignored, because a caller who believes they named the attestation and did not is worse off than a caller who is told.

**The console signs in around the shell, and loses a field.** `<ClerkProvider>` wraps the app; signed out, the whole console is the hosted sign-in; signed in, the rail carries the operator's name and the way out. "Who is attesting" stops being an input and becomes a line naming the signed-in operator. There is exactly one place a token is attached to a request — `frontend/src/api/http.ts`, which already owns what the wire means — and the eighteen `fetch(` call sites go through it.

**A machine caller is named as a machine.** `backend/mcp/` is an HTTP client of this API and becomes a client that must authenticate. It presents a machine credential from its own environment, and the identity recorded against a run it starts is that credential's subject rather than a person's name.

## User Stories

### The door

1. As the person paying for this deployment, I want every route to require a signed-in operator, so that a stranger holding the URL cannot spend my provider budget or start a gate run on my account.
2. As the person paying for this deployment, I want a deployment that lost its authentication settings to refuse to boot, so that the gate cannot disappear silently between one redeploy and the next.
3. As a contributor, I want the API to be constructible with authentication declared off, so that the test suite does not need an issuer and the seam stays visible in the constructor.

### The name

4. As a recipient of a signed report, I want the `identity` field to be a verified subject, so that the one field naming a person is founded on the same evidence as the rest of the document.
5. As a recipient, I want the payload to say what verification did and did not establish, so that "verified" is not read as identity assurance it does not provide.
6. As an operator, I want my name carried to the confirmation screen without a text input, so that the record of who authorised a spend cannot be a blank because a browser tab was reopened.
7. As an operator driving the bench from my editor, I want a run started over MCP to be recorded against a machine credential, so that the report does not claim a person confirmed something a tool did.

### When it goes wrong

8. As an operator whose session expired mid-run, I want the console to say so and to let me sign in again without losing the run I am watching, so that an expiry is an interruption and not a lost record.
9. As an operator, I want a request with no token or a bad one refused with a sentence naming what happened, in the shape every other refusal on this surface takes.

## Implementation Decisions

**`backend/identity.py`, new, top-level.** One function returning the declared verification material or `None`, and one type for it. It is the only module in this repository that reads the issuer's environment variables, on `signing.signing_key`'s pattern — one reader, named, so a second route to the environment is a new reader rather than this one.

**`clerk-backend-api` as a runtime dependency, not a group.** Verification runs in the deployed server, so it is a dependency for the same reason `mcp` is one and `ruff` is not. `authenticate_request` with `jwt_key` set is the offline path.

**The verifier is a protocol, not an import, at the API boundary.** `create_app` takes something that turns a request into a subject or a refusal. The concrete implementation is Clerk's; the API knows only the shape. This is what keeps ADR-0116 §3's reversibility real and what lets a test declare a stub with no network and no account.

**Three call sites, not a decorator per route.** `identity` is applied where a request becomes a record — the attestation in `POST /runs`, the approval in both approval routes, and the pending-route measurement. Authentication itself is applied once, as a dependency the router carries, so a route added later is authenticated by construction rather than by remembering.

**`run_state.py`'s `identity=""` is untouched.** It records that an interrupt was never answered. Filling it with the session's subject would put a person's name on a decision they did not make, and ADR-0116 §6 says so.

**The payload gains a sentence, not a field.** No new key in the signed document: the existing `identity` field's own prose says what establishes it and what that does not amount to. A new field would change the shape of every artefact already signed.

**`frontend/src/api/http.ts` gains `authed()`.** A module-level token source, registered once at mount by a component inside `<ClerkProvider>`, so the api modules stay plain functions with no hooks — they run under `environment: 'node'` with no jsdom and that does not change. `frontend/src/console/gate.test.ts` and `settings.test.ts` assert their modules contain no `fetch(` at all; both stay true.

**`VITE_CLERK_PUBLISHABLE_KEY` is set in Vercel before the deploy**, because it is inlined at build time. The Cloud Run `--set-env-vars` set grows and still replaces the whole set on every deploy.

**Out of the API's way: the terminal surfaces.** `scripts/` reaches the bench in-process and never over HTTP. The CLI, `scripts/gate.py` and the Action are unchanged and need no account.

## Testing Decisions

**Every new test is driven red once, for the right reason.** The house rule, and it has a specific shape here: a test that asserts the record names the token's subject must first be made to fail by constructing the record from the body's string, not by an import error.

**The verifier stub is the unit-test seam.** Tests declare a stub that accepts a named subject or refuses, which is why the constructor argument is a protocol. No test reaches an issuer, and the suite keeps running with no account.

**Two assertions carry ADR-0116 §1.** That an authenticated request records the token's subject, and that a body still carrying `identity` is refused. The second is the one that catches a half-done migration.

**One assertion carries §2.** The deployed factory, with the verification material absent from the environment, refuses to boot — beside the existing signing-key assertion and in its shape.

**The two invariant tests stay unedited.** `test_no_module_of_the_api_reads_an_environment_of_its_own` and `test_the_one_environment_value_the_api_needs_is_read_through_signing` are not touched by this work. If either needs editing, the seam is wrong.

**Frontend: `authed()` attaches the header, and a 401 reads as a refusal.** Both in vitest, in node, with no DOM. The Playwright end-to-end walkthrough needs a test user at the issuer — the one part of this that becomes genuinely more awkward, and it is called out rather than discovered.

## Out of Scope

**Per-operator records.** Every signed-in operator sees every run and artefact, as today. Partitioning is a change to the run record, the recorded-runs table and five routes, it needs a stated answer for runs that predate the field, and none of it is required to make `identity` mean something.

**Roles, organisations and permissions.** One authenticated principal, no tiers. A bench where some operators may start a gate run and others may not is a different decision with its own ADR.

**Public report links.** The four routes under `/report/{id}` require authentication like everything else. What travels to a recipient is the three files and `scripts/verify.py`, which is what *portable* has always meant here; the route was never the portable thing.

**The reference repository's MCP-over-OAuth exercise.** `backend/mcp/` authenticates as a client with a machine credential. It does not become an OAuth resource server, and nothing here advertises protected-resource metadata or does dynamic client registration.

**Rotating or provisioning credentials from the console.** Both stay where configuration stays: the environment and the issuer's own dashboard.

## Further Notes

**Why the cost paragraph in ADR-0116 is load-bearing.** This project's whole claim is that a score printed with its method and its limits beats a bare number (D4). A verified `identity` is a better-founded field and it is not identity assurance — it is the subject of a session at one issuer. Printing it as though it were more would be the exact failure this bench exists to argue against, committed in its own document.

**Why the gate and the name ship together.** Either alone is defensible and neither is good. Authentication without the identity change leaves a bench that knows who is signed in and still signs a document naming whoever they typed, which is harder to defend than not knowing. The identity change without authentication is not possible.

**What this does not make safe.** A signed-in operator can still attack an endpoint they are not authorised to attack. The three attestation statements are what address that, and they are unchanged: the nonce is the proof of control (ADR-0007), and no amount of authentication is a substitute for it. This spec establishes who is asking, not what they are entitled to ask about.
