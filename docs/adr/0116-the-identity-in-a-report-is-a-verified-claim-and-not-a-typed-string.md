---
status: accepted
---

# The identity in a report is a verified claim, and not a typed string

`Attestation.identity` is the field that says who authorised an attack on somebody
else's endpoint. It is recorded because "an attestation nobody signed is not a
liability record" (`backend/bench/registration.py`), it is refused when blank, and it
travels into the signed payload (`backend/bench/payload.py`) — where a procurement
reader, an insurer or a customer reads it as the name of the person who took
responsibility for the run.

Today that name is a string typed into a text input. Nothing checks it. An operator
who types `security@acme.example` is recorded as `security@acme.example`, and so is
anyone else who types it. The document is signed, so the recipient can prove the
bench produced it and that nobody altered it since — and the one field in it that
names a *person* is the one field the signature cannot speak to.

This repository already knows the difference and says so in one place.
`backend/bench/unattended.py` describes the Action's identity as "`github.actor`, an
authenticated identity rather than a name typed at a prompt." That sentence is the
whole of this ADR's problem statement: the CI path has had a verified identity since
[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md),
the browser path has not, and both write into the same field of the same payload.
A reader of a report cannot tell which they are holding.

There is a second, smaller version of the same defect on the approval. The console
carries the registration's name forward to the confirmation screen in
`sessionStorage`, and `frontend/src/run/interrupt.ts` states the consequence
plainly: when it is not held "the body goes with an empty identity and the bench's
sentence names nobody, which is a worse record and not a blocked one." That was the
right call while a name was only ever a string — blocking a confirmation over a
missing name makes *declining* the easier answer, and the spend is what that function
guards. It stops being a trade-off once the name is on a token.

## Decision

**Every route on the API is reached by an authenticated operator, and `identity` is
read from the verified token rather than from the request body.**

1. **`identity` comes off the wire.** `AttestationRequest`, `ApprovalRequest` and the
   pending-route measurement request each carry an `identity` field today; all three
   lose it. A caller can no longer name themselves, which is the whole decision: a
   field a caller supplies is a claim, and a field the bench derives from a verified
   signature is a fact. The three records are constructed with the token's subject,
   server-side, at the one place each request becomes a record.

2. **Unconfigured is a refusal, never an open bench.** The deployed factory reads the
   verification material and refuses to boot without it, on
   [ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md)'s
   reasoning applied to a second credential. The failure this prevents is specific
   and silent: a redeploy that dropped the variable would come back serving every
   route to the internet, spending the deployment's own provider budget, with nothing
   on any screen saying the gate was gone. A bench that would not start without a
   signing key and *would* start without its lock has its priorities inverted.

3. **The seam is a declaration, not an environment read.** Authentication is a fourth
   constructor argument on `create_app`, beside the bench, the gate runs and the
   pending routes, and it is declared on exactly their terms: a caller that declares
   nothing gets no authentication, and a deployment that declares nothing at all gets
   the deployed reading — which is the refusal in §2. No module of `backend/api/`
   becomes an environment reader, which two tests assert and which
   [ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md) narrowed
   rather than lifted. The environment is read by a module outside that package, as
   `backend/observability.py` already is and for the same stated reason.

4. **Verification is offline.** The token's signature is checked against the
   instance's public key held in this process, not by asking the issuer. The console
   polls a run every two seconds; a verification that made a network call would put
   the identity provider on the critical path of a bench that is mid-run against
   somebody's endpoint, and an issuer outage would then read as the bench failing.
   A networked key fetch remains the fallback for a key this process has not seen.

5. **A non-human caller is named as one, and is not given a person's name.** The MCP
   server (`backend/mcp/`) is an HTTP client of this API and is now a client that
   must authenticate. It presents a machine credential, and the identity recorded
   against a run it starts is that credential's subject. This is a gain rather than a
   cost: a run started from a coding agent was not started by a person at a browser,
   and `identity` should say so rather than borrow the name of whoever last signed in
   on that laptop.

6. **What stays empty stays empty.** `run_state.py` constructs an `Approval` with
   `identity=""` when an interrupt is never answered. That is unchanged and must not
   be "fixed": it records that *nobody answered*, which is a different fact from
   nobody being named, and filling it with the session's subject would put a person's
   name on a decision they did not make.

## What this costs, stated

**A report's `identity` now means something narrower than it reads.** It is the
subject of a verified session at the identity provider this deployment trusts — not a
legal person, not an employer, and not a claim that the named party was authorised by
their organisation to attest anything. Verification moves the field from *unchecked*
to *checked against one issuer*, which is a real improvement and is not the same as
identity assurance. The payload's own sentence for the field has to say so, or this
ADR will have bought a stronger-sounding number rather than a better-founded one.

**A clone no longer runs with nothing to sign up for.** Before this, `uv sync` and
two commands got a working bench. Now a contributor needs an identity-provider
account and two more values in `.env`, or the API refuses to boot. That is the direct
cost of §2, it was weighed against making *unconfigured* mean *open*, and it lost to
it. The terminal surfaces are unaffected — `scripts/` reaches the bench in-process and
never over HTTP, so the CLI and the Action keep running with no account at all, which
is also why the Action's own identity path is untouched by this decision.

**One provider, named.** This binds the browser surface to a single hosted issuer.
The seam in §3 is what keeps that reversible — a second issuer, or a self-hosted one,
is a different declaration passed to the same constructor argument — but nothing here
pretends the choice is free, and a deployment whose issuer disappears is a deployment
that cannot serve its console until it declares another.

## Alternatives

**Middleware reading the environment at import.** Fewer parts, and it deletes the
invariant that no module of `backend/api/` reads an environment of its own — an
invariant two tests assert and which exists so that a price, a target URL or a bearer
token cannot arrive that way. Trading a stated structural rule for an hour of wiring
is the trade this repository has declined every other time it has been offered.

**Authenticate at the edge and trust a header.** The console is served from a host
that could require a login and forward a claimed identity. Rejected because the API's
own URL is public and answers the same routes: a gate that can be walked around by
addressing the service directly is decoration, and it would put a forgeable header
into the field this ADR exists to make unforgeable.

**Keep `identity` typed, and add authentication only as a gate.** This was
considered and is the cheaper half of the work — nobody unauthenticated can spend the
deployment's budget, and the report is unchanged. Rejected because it leaves the
defect exactly where it was: the bench would then *know* who was signed in and still
sign a document naming whoever they typed, which is harder to defend than not knowing
at all.

**Partition the record per operator.** Each signed-in operator seeing only their own
runs and artefacts is the shape a product eventually wants. Out of scope here and
deliberately: it is a change to the run record and to five routes, it needs a stated
answer for a run whose owner predates the field, and none of it is required to make
`identity` mean something. This ADR gates and names; it does not divide.
