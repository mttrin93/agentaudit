---
status: accepted
---

# A machine credential is verified at the issuer, and the report names a machine

[ADR-0116](./0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
put a door on the API and made `identity` a verified claim.
[ADR-0122](./0122-a-bench-with-no-door-records-that-it-verified-nobody.md) decided what
a bench with no door records.
[ADR-0123](./0123-the-identity-in-the-payload-states-what-established-it.md) made the
field say what established it, with one type per reading.

`backend/mcp/` is the surface none of them settled. It is an HTTP client of this API —
four tools a coding agent calls — and with the door up it is a client that must
authenticate. Until it does, a run started from an editor is recorded as
`NOBODY_VERIFIED`: *an operator this bench did not verify*. That is true and it is the
weakest thing the field can say, on a surface where something stronger is available and
where the interesting fact is not *who* but *what*.

Two facts have to reach the artefact and only one of them is who. The other is that
nobody was at the keyboard. A coding agent calls `approve_run` after relaying an
estimate; the operator's yes is real and it was spoken to the agent, not typed into
this bench. A report that printed *the subject of a verified session at the issuer this
deployment declares* over that run would be making the claim ADR-0116 exists to stop —
a stronger-sounding name rather than a better-founded one — and it would be making it
in the one direction ADR-0123 says this field may never be wrong in.

The provider settles the mechanics on its own. A machine credential is not a signed
document. It is an opaque secret with a prefix (`m2m_`, `mt_`, `ak_`, `oat_`), and the
library posts it to the issuer's verification endpoint under the deployment's secret
key. So ADR-0116 §4's offline argument — the console polls a run every two seconds and
an issuer on that path would put their outage on the critical path of a bench mid-run —
covers session tokens and covers nothing else. #244 recorded that warning when it built
the seam; this is where it lands.

## Decision

**The MCP client authenticates as a machine, the door answers with a type that says so,
and the artefact prints a sentence that claims no person.**

1. **A verification is now three types, not two.** `identity.Machine` sits beside
   `identity.Operator`, both carrying a `subject`, and `Principal = Operator | Machine`
   is what every route on the authenticated surface declares. A sibling and not a
   subclass: a subclass would satisfy `isinstance(x, Operator)` at every site that
   reads a subject, including the one site where the difference is the whole point, and
   ADR-0123 already refused to let a subclass be admitted to the artefact by
   inheriting. A field on `Operator` was refused for ADR-0120's reason — a boolean
   beside a subject can be dropped by a caller who never thought about it.

2. **`attributed_to` gains a fourth reading, and it is the only place that branches.**
   `VerifiedMachine` joins `AttestedName`, built like the other three: a `_claim` over
   the shared base, so the blank refusal, the sentence shape and the limits clause are
   the ones every other reading carries. It prints *the subject of a machine credential
   the issuer this deployment declares verified at its own endpoint. That is the whole
   of what verification established: a credential that issuer holds, current at the
   moment of the request, naming this machine. No person was present, and this field
   names none.* ADR-0123's own argument is the precedent: it refused one sentence for
   all surfaces because that sentence would have been false about the Action, and this
   one would be false about a machine in the same way and in the more flattering
   direction.

3. **Verification of a machine credential is networked, and that is stated rather than
   hidden.** `identity.py` says so in its module docstring, and a test asserts it: one
   verifier, one fixture that refuses every socket, a session token that verifies and a
   machine credential that does not. Nothing was built to avoid it — a local check of
   an opaque secret is not a thing that exists, and caching a verification result would
   mean this bench deciding for itself how long after revocation a credential stays
   good.

4. **A deployment declaring only the public key refuses a machine credential by name.**
   `AGENTAUDIT_ISSUER_JWT_KEY` alone cannot check one, so the refusal is `UNAVAILABLE`
   with a sentence naming `AGENTAUDIT_ISSUER_SECRET_KEY` — made before the library is
   called, because left to the provider it posts the credential under an empty bearer,
   is told no, and reports it as a credential that did not verify. That would tell an
   operator holding a perfectly good credential that their credential is bad. A
   deployment that wants MCP callers declares both variables.

5. **The client reads one variable, checks nothing at construction, and sends nothing
   without it.** `AGENTAUDIT_MACHINE_TOKEN` is read in `mcp.__main__.configured`, where
   `AGENTAUDIT_API` and `AGENTAUDIT_DECLARATION` are read, and is carried into
   `BenchClient` as a required second argument with no default. An absent one is
   `NoCredential` on the first tool call — a stated failure like the other five, naming
   the variable — and never an exit at boot, which would leave a coding agent reading
   `CONNECTION_CLOSED` with nothing behind it. *Unconfigured never means anonymous*,
   which is `NO_ISSUER_NO_BOOT`'s rule at the client end of the same wire.

6. **Two of the four prefixes the provider calls machine tokens are refused by
   name.** `is_machine_token` matches `m2m_`, `mt_`, `oat_` and `ak_`, and only the
   first two name a machine — the library's own `RequestState.to_auth` reads an OAuth
   access token's `subject` into a *user id*, and an API key's into a user or an
   organisation. Taking the library's word for it would print *no person was present*
   over a credential a person holds, which is decision 2's failure with the sign
   flipped and is worse than the thing decision 2 exists to prevent: an overstatement
   that is also false. So the type is read from `get_token_type`, and an `oat_` or
   `ak_` credential is `UNTRUSTED` with a sentence saying this bench admits a console
   session and an MCP machine credential and not a third thing. Not a sixth
   `Unverifiable`: well-formed and not admitted by this deployment is what `UNTRUSTED`
   already means (ADR-0120 §3).

## Alternatives

**Let the MCP client stay anonymous and keep recording `NOBODY_VERIFIED`.** Free, and
honest as far as it goes. It loses the fact worth recording: not that nobody was
verified, but that a machine was. It also makes the doorless reading the one an
operator reaches by doing nothing, on the surface where a run is started by a program.

**Send the credential and record it as a `VerifiedSubject`.** One type fewer and one
sentence fewer. It prints *the subject of a verified session* over a program, which is
the false claim, and it is false in the direction that flatters the document. Rejected
for the reason ADR-0123 rejected one sentence for three surfaces.

**A `machine: bool` on `Operator`, or a prefix match at `attributed_to`.** Both put the
distinction somewhere it can be dropped: a flag a constructor can omit, or a string
comparison against prefixes the provider owns and may extend. The door is the only
place that knows how the credential was checked, so the door is where the type is
chosen.

**A separate machine route, or a header of its own.** It would keep session
verification unambiguously offline by keeping machine callers off the shared path. It
also means two doors, two refusal shapes and a second thing for a route added next year
to be added to — which is exactly the failure ADR-0121 avoided by carrying the door on
the router. The provider already routes on the credential's prefix; a second route here
would be this repository re-implementing that decision.

**Refuse to launch the MCP server with no credential.** It fails earlier, which is
usually better. Not here: the transport does not exist yet at launch, so the failure
reaches the operator as a dead pipe. The three absences this entrypoint can meet — no
bench, no declaration file, no credential — are answered the same way, in the tool
result, for the same reason.

## What this costs, stated

**A deployment that wants MCP callers must declare its issuer's secret key.** The
public key alone was enough for the console and is not enough for this. That is one
more real credential in the deployment's environment, and it is the credential that can
do more than verify.

**Every MCP tool call is behind a network round trip to the issuer.** Four tools, one
call each, and none of them is on the polling path the offline argument was written
for — but a bench whose issuer is unreachable answers `503` to a coding agent that was
about to relay an estimate. The refusal says the check could not be completed and not
that the credential was rejected, which is the distinction `Unverifiable.UNAVAILABLE`
exists for.

**The bench cannot tell which person was at the editor, and now says so in the
artefact.** This is a loss of information relative to a typed name and a gain relative
to a typed name nobody checked. A recipient who wants to know which person approved a
run started over MCP has to ask the operator, and the document no longer implies it
knows.

**A caller holding an OAuth token or a user API key is turned away, not
downgraded.** Either could have been admitted as an `Operator` and printed as a
verified session, which would name a real person. It would also call an API key a
session, and this bench has no reading for *a person's long-lived credential*; the
honest answer while it has none is that such a caller is not one this deployment
admits. A reading for them is a new ADR, not a branch added here.

**A fourth reading is a fourth sentence to keep true.** `attested_name.py` is now four
types and `test_attested_name.py` asserts that no two of them say the same thing about
the checking. The pair that matters is `VerifiedSubject` and `VerifiedMachine`: they
come off the same door, and only one of them is a person.
