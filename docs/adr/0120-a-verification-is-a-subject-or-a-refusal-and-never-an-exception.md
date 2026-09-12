---
status: accepted
---

# A verification is a subject or a refusal, and never an exception

[ADR-0116](./0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
decided that `identity` is read from a verified token and that the API declares a
seam rather than importing a provider. It did not decide what that seam's *type*
is, and the type is the part the eight tasks after it have to live with: what a
verifier is handed, what it answers with, and what a call site is able to do with
the answer before it has checked anything.

Three things about this repository make that choice narrower than it looks.

**A refusal on this surface is a value, not a raise.** Every measurement this
bench takes reports its own refusals as prose on a field, because a run that
raised through a paid-for measurement loses the measurement along with the reason.
Authentication is the most tempting place in the codebase to break that rule —
`401` is an exception in most frameworks' idiom — and it is also the worst one,
because the route a console polls every two seconds while the bench is attacking
somebody's endpoint is the route a verifier's exception would surface on.

**An invariant this repository intends to hold is held by a type.** The fence
between held routes and scored ones is classes that structurally cannot hold the
wrong population. The equivalent here is that a name nothing verified must not be
readable, and "remember to check the flag first" is not that.

**The test suite has no account anywhere.** 2090 backend tests run with no
network and no provider, and that is a property worth keeping rather than a
happy accident.

## Decision

**`Verifier.verify(authorization: str | None) -> Operator | Unverified`. Total,
typed, and raising nothing.**

1. **Two types, not one type with a flag.** `Operator` carries `subject` and
   `Unverified` carries `cause` and `reason`. There is no `subject` attribute on
   the refusal, so a call site that reads a name without narrowing the union does
   not typecheck. The invariant that an unverified identity has no name is the
   type's, which is the same construction the scored/held fence uses and is
   chosen for the same reason: a boolean field would have to be remembered at
   three call sites and a union has to be narrowed at all of them.

2. **Nothing raises out of `verify`.** Not a forged token, not a malformed one,
   not a key that will not parse, and not an issuer that cannot be reached. The
   concrete verifier catches broadly and returns `UNAVAILABLE`. The refusal
   travels as prose on `reason`, in the shape every other refusal on this surface
   takes, and turning it into an HTTP status is the API's job at the one place it
   does that — not the verifier's.

3. **Five causes, because two consumers branch and do not merely print.**
   `ABSENT`, `MALFORMED`, `EXPIRED`, `UNTRUSTED`, `UNAVAILABLE`. A console must
   tell an expired session, which it fixes by signing in again, from a signature
   that did not verify, which is somebody at the door; and both must be told from
   a verifier that could not complete the check, which is not a statement about
   the caller's token at all. Reporting an issuer outage as a rejected credential
   would tell an operator their sign-in was refused when nothing of the sort
   happened.

4. **The header's value, not the request.** `verify` takes the string in
   `Authorization` and nothing else. A protocol taking a framework request object
   would make this a FastAPI seam, and every stub in every later task's tests
   would have to build one. The concrete verifier adapts to whatever the library
   wants request-shaped; that adaptation is one small private class.

5. **What is declared and what verifies are two objects.** `declared_issuer`
   reads the environment and returns `Issuer | None`; `ClerkVerifier` takes an
   `Issuer` and checks signatures. Splitting them is what lets the verifier be
   constructed in a test with a locally generated key and no environment at all,
   and it keeps the single environment reader a named function rather than a
   constructor.

6. **The reader says what was declared and never what to do about it.** `None`
   from `declared_issuer` means the environment declared no issuer. Whether that
   is an app with no door or a factory that refuses to boot is the factory's
   decision, and ADR-0116 §2 already made it there. A reader that raised on an
   undeclared issuer would put the deployment's policy inside the environment
   read, where a test that wanted the other reading could not get at it.

## What this costs, stated

**The broad `except` in the concrete verifier hides bugs as well as outages.** A
`TypeError` in this module's own adaptation code comes back as `UNAVAILABLE` with
the exception's text in `reason` — a refusal that reads like an issuer problem and
is not one. It is accepted because the alternative is enumerating a third-party
library's exception surface and being wrong about it the first time it changes,
and the text of the exception does travel in the sentence rather than being
swallowed.

**Five causes is a vocabulary later tasks must not widen casually.** Each member
is there because somebody branches on it. A sixth added for a nicer error message
is a string, and `reason` is where strings go.

**The library's reason table is a thing that changes under us.** The mapping from
the provider's reasons onto the five is exhaustive and a member it does not hold
falls through to `UNAVAILABLE` *and says it was not recognised*, so a provider
upgrade that adds a reason produces a refusal an operator can read as "this bench
no longer understands its library" rather than one that quietly reads as an
outage.

## Alternatives

**Raise, and let a FastAPI exception handler turn it into a 401.** The idiomatic
shape, and one line shorter at the call site. Rejected because it puts a raise on
the path of a run in progress, and because the repository already decided that
refusals are values — a rule that survives everywhere except the one place it is
inconvenient is not a rule. It also makes the seam untestable without a framework:
a stub would have to raise a framework exception to refuse.

**One `Verification` type with `subject: str | None`.** Fewer types, and it reads
fine. Rejected because `verification.subject or "unknown"` typechecks, which is
precisely the record ADR-0116 exists to stop, and nothing but review would catch
it.

**A `bool` and a subject, like the library's own `RequestState`.** Same defect as
above with an extra field to disagree with itself: a state that is signed in with
no payload is representable.

**Take the whole request object.** Would let a verifier read a cookie as well as
a header, which the provider's own helper supports. Rejected for now because the
console attaches a header at one seam by design and a cookie path would be a
second, unasserted way in. A verifier that needs cookies later takes a mapping of
headers; that is a widening of this protocol and an amendment to this ADR, not a
silent change.

**Read the environment in the verifier's constructor.** Collapses two objects into
one and removes a function. Rejected because the test suite would then need an
environment to construct a verifier, and because the single named environment
reader is what `observability.trace_config` and `signing.signing_key` establish as
this repository's shape for exactly this.
