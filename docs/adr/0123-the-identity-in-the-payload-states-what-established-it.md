---
status: accepted
---

# The identity in the payload states what established it, and what it did not

[ADR-0116](./0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
took `identity` off the request body and read it from a verified token instead, and
its cost paragraph is explicit about what that bought and what it did not: the field
"is the subject of a verified session at the identity provider this deployment trusts
— not a legal person, not an employer, and not a claim that the named party was
authorised by their organisation to attest anything", and "the payload's own sentence
for the field has to say so, or this ADR will have bought a stronger-sounding number
rather than a better-founded one."

That sentence does not exist yet. Today the field is one string, and three surfaces
write it: the API behind a door, which now has a verified subject; the Action in a
caller's own repository, which has had `github.actor` since
[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md);
and a terminal, which has whatever was typed after `--identity`. A bench that declared
`NO_DOOR` writes a fourth thing — the sentence
[ADR-0122](./0122-a-bench-with-no-door-records-that-it-verified-nobody.md) chose,
which reads as an unusual username to anybody who meets it in a field of names. A
recipient holding a report cannot tell any of them apart.

This is the failure this project exists to argue against, committed in the project's
own artefact. PLAN.md D4 says every score prints its method and its limits and that it
"applies to the bench's own scores first"; the bench prints a temperature with a
sentence saying whether the absence was the model's or the operator's, a κ with the
transcripts it was counted on, and a library version with the condition under which
two runs may be compared. The one field that names a *person* carries nothing.

## Decision

**The payload's `identity` field carries the name and what established it, in the
field's own value, and the value is produced by a type chosen where the name arrived.**

1. **A name in an attestation is an `AttestedName` and never a `str`.**
   `backend/bench/attested_name.py` holds three frozen types — `VerifiedSubject`, a
   subject off a token the declared issuer signed; `WorkflowActor`, the actor a
   workflow run was started as; and `NameGiven`, a name nothing checked, which is both
   the terminal path and the bench that declared no door. `Attestation.attested_by` is
   one of the three, `Attestation.identity` is a property reading the name back out,
   and `stated()` is what the document prints. The union is `identity.Verification`'s
   shape one layer out and for its reason: a boolean beside a string can be set by
   anybody, and a union can only be narrowed.

2. **The claim is decided where the name arrives, and nowhere else.**
   `api.app.attributed_to` turns the operator the door admitted into a
   `VerifiedSubject`, or — for the operator a bench with no door records — into a
   `NameGiven`. `unattended.committed_attestation` makes a `WorkflowActor`.
   `scripts/console.attest` makes a `NameGiven`. The serialiser has no branch at all:
   it prints `stated()`, so no later change to `payload.py` or to a renderer can
   promote one reading into another.

3. **The sentence travels in the value, and no key is added.** A key beside `identity`
   would change the shape of every artefact already signed, and every document issued
   before today would read as an older shape to a verifier that refuses a version it
   does not know. There is a second reason the value is the right home: a sentence in
   a key of its own is a sentence a renderer can decline to print, and this one exists
   because a reader might otherwise take the field for more than it is. In the value,
   printing the field *is* printing the claim.

4. **Every one of the three sentences ends in the same three refusals**
   (`attested_name.NOT_ESTABLISHED`), the verified one included. Verification moves
   this field from *unchecked* to *checked against one issuer*, which is a real
   improvement and is not identity assurance; the strongest reading this bench can
   print still says it is not a legal person, not an employer, and not a claim of
   organisational authorisation.

5. **`ARTEFACT_VERSION` does not move.** No key was added and no figure changed
   shape. A version-2 verifier re-derives every figure it knows, and the one field it
   never re-derived anything from now says more about itself.

## Alternatives

**`identity_stated` beside `identity`, on the `attacking_temperature_stated` idiom.**
The idiom the payload already uses for a value and the sentence that reads it, and the
first thing to try. Rejected on the ticket's own terms: this document's shape is what
a recipient's verifier reads, and the field carrying a person's name is the one where
the sentence must not be separable from the value. `attacking_temperature` cannot be
misread as a claim about a human being; `identity` is read as exactly that, and the
two halves travelling in two keys is one renderer away from the name arriving without
the limits.

**A boolean — `identity_verified: true` — and prose in the renderer.** Cheapest, and
it is the shape this repository refuses everywhere else: a flag beside a string can be
set by any caller that constructs the record, so *verified* would again be something
somebody typed. It also puts the claim where the type system cannot hold it, and
ADR-0120 §1 had just finished moving a claim about a name out of reach of a caller.

**Prose in the rendering only, with the payload unchanged.** It would satisfy a reader
of `report.md` and nobody else. The payload is the artefact the signature covers and
the thing `scripts/verify.py` reads; a claim about a name that exists only in a
derived view is a claim that the canonical document does not make.

**One sentence for all three surfaces.** Simpler, and false. The Action's name is
checked — by the runner, and by no issuer this deployment declares — and a wording
that called it unverified would understate a real check, while one that called it
verified would print the wrong party's evidence. The distinction is the whole of what
ADR-0116's opening complains about.

## What this costs, stated

**The value at `provenance.attestation.identity` is no longer a bare name.** A
consumer that wanted the subject as a token now reads a sentence that begins with it.
That is the price of §3, and it was weighed against a second key: this field has never
been machine-joined to anything — the run record keeps `attested_by` for that, out of
the artefact — and the readers this document is shaped for are people.

**Section 1 of the report is longer, and says the same thing twice.** The headline
block names who attested and section 2 records the attestation; both print the
payload's string whole, so the three refusals appear twice in a document that already
prints `NOT_A_CLAIM_OF_CONFORMITY` twice for the same reason. Section 1's bullet is
also split in two, because a timestamp trailing a sentence that ends in three refusals
read as a fourth clause of the last one.

**Every artefact this bench produces from now on makes a narrower claim than the one
before it.** That is the intended direction and it is still a cost: a reader comparing
an old report with a new one will find the old one said more about the person who
authorised it than the bench could support.
