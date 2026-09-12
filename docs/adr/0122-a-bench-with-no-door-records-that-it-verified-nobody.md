---
status: accepted
---

# A bench with no door records that it verified nobody

[ADR-0116](./0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
§1 decided that `identity` comes off the request body and is read from the verified
token at the three places a request becomes a record.
[ADR-0121](./0121-an-open-bench-is-a-declaration-and-never-a-deployments-default.md)
decided that a caller may say deliberately that its bench has no door, and that
`NO_DOOR` is how it says so. Put together they leave a question neither of them
answers, and it has to be answered in the same commit that takes the field off the
wire: **what an app with no door puts in a field that may not be blank.**

It is not a hypothetical app. `Attestation` refuses a blank identity — "an
attestation nobody signed is not a liability record" (`backend/bench/registration.py`)
— and three callers reach `POST /runs` with no door in front of them: the browser
walkthrough's harness, the tests that read what a *deployed* factory answers on a
route, and every test in this suite that declares its own `BenchConfig`. Before this
change each of them sent a name and the record took it. After it, there is no name to
take and the record still has to say something.

## Decision

**An app that declared `NO_DOOR` records one stated sentence — `an operator this
bench did not verify` — as the operator of every request it serves.**

1. **It is a sentence and not a name.** It reads, in a signed report and on a screen,
   as the fact it is: this document was produced by a bench that admitted anybody,
   and nothing established who asked for it. A recipient who reads the field learns
   exactly what the deployment did, which is what ADR-0116's cost paragraph demands of
   this field in the verified case too.

2. **It is one constant, held beside the door.** `app.NOBODY_VERIFIED` is an
   `Operator`, so the six routes that record one declare the same parameter whether
   the bench has a door or not, and the choice between the two is made once, in
   `create_app`, where the other three declarations are made.

## Alternatives

**Keep honouring the body when there is no door.** A bench with no door is the one
deployment where a caller-supplied name could not be checked against anything, so
honouring it there is exactly the defect ADR-0116 closed, with the open door as the
excuse. It would also mean one model that reads a field on some apps and refuses it on
others — the migration this ADR's §1 exists to make impossible to half-do.

**`anonymous`, or the empty string.** `Attestation` refuses the second by
construction, and it should: *nobody answered* and *nobody was named* are different
facts and `run_state.py`'s blank identity is the one place the first is recorded
(ADR-0116 §6). The first is worse than it looks — `anonymous` reads as a kind of user,
and a procurement reader would take it for one, where the sentence tells them the
bench had no lock on its door.

**Refuse the request instead.** An app with no door refusing every route that records
anything would make `NO_DOOR` useless: the browser walkthrough exists to drive the
register-and-confirm walk end to end, and a declaration that cannot start a run is not
the declared-open reading of this bench but a fourth kind of refusal.

**Let the caller declare the name beside `NO_DOOR`.** `create_app(verifier=NO_DOOR,
as_operator="…")` would let the harness keep signing reports in a chosen name. It is a
typed string reaching the field through a second door, one constructor argument away
from the one that was just closed, and the only caller that wants it is a test.

## What this costs, stated

**A report produced by an open bench says less than one produced before this change.**
The walkthrough's artefact used to name *the browser walkthrough*; it now names
nobody, and that is a loss of a string somebody chose. It is not a loss of evidence:
nothing checked that string either, and the sentence that replaces it is the first
true statement this field has carried on that path.

**Two benches now write two different kinds of thing into one field.** A deployment
with a door writes an issuer's subject; one without writes this sentence. They are
told apart by reading them, which is the point, and #247's payload prose is where the
field says what verification established and what it did not.
