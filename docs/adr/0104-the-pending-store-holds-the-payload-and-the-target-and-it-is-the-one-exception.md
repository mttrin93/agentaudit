---
status: accepted
---

# The pending store holds the payload and the target, and it is the disclosure posture's one deliberate exception

Every store this repository has is designed to hold as little as it can get away with.
[ADR-0008](./0008-repo-disclosure-posture.md) says why: a payload cannot be
unpublished, so the working part of an attack is withheld wherever prose would carry
the finding as well. `precedent/findings.sqlite` was built to that rule and says so in
as many words — *prose and never payload text*. It also carries no target identity at
all, and that is a second decision with a second argument:
[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) generalises the judge's
blinding to *precedent carries no target identity to anything blinded*, on the
reasoning that accumulate enough entries and a failure pattern identifies a target on
its own.

`docs/specs/pending-routes.md` proposes a fourth store, `pending/routes.sqlite`, which
holds both. The route the adaptive layer found against a customer's agent is filed with
**the probe that beat it** and **whose agent it beat**. Those are precisely the two
things the two records above refuse, and the spec is explicit that the difference has
to be argued rather than assumed.

This record is the argument. It is not a loophole in ADR-0008 and it does not amend it:
both of those refusals stand exactly as written for the stores they were written about.
What is decided here is that one new store, whose whole purpose is a decision that has
not happened yet, holds two fields the others may not — and that the reasons it may are
properties of *this* store that no other store in the repository has.

## The problem the refusals produce

A route the attacker found against somebody's real agent is the most interesting output
the bench can produce, and today it reaches one printed line and is gone. It cannot go
into `precedent/`, which holds prose; it cannot go into `decisions/routes.sqlite`,
which holds what the gate *measured* and has nothing to hold for a route nothing
measured; and it cannot stay on the run record, which is a record of a run that ended.
Both correct stores refuse it for good reasons and there is no third.

So the choice is not between a careful store and a careless one. It is between a store
that holds these two fields and **discarding the finding**, which is what the bench
does now and what `docs/validation.md` records under *what has never been validated*.

## Decision

### 1. The pending store holds the payload, and a description is not a probe

`pending/routes.sqlite` carries the probe text of a route awaiting a decision.

**A route that cannot be re-run cannot be measured later.** The decision this record is
waiting for is the cross-model bar —
[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md), `D`
against three reference agents on two models — and that bar is decided by *sending the
probe*. A prose description of a route is a thing a person can read; it is not a thing
a reference agent can be attacked with. Filing the description and dropping the probe
produces a queue of routes that can be triaged and never decided, which is the present
failure with a database in front of it.

This is the case ADR-0008's amendment already draws the line for and lands on the other
side of. The amendment's test is transferability: a payload ships **committed** when the
situation is the mechanism, and is **withheld** when its wording is the working part.
An adaptive route that beat a real agent is the canonical withheld case — the amendment
names it, *a successful adaptive route against the hardened agent is the case this
posture exists for* — and nothing here publishes one. `pending/` is git-ignored, like
`precedent/` and `decisions/` before it. **The exception is not to what may be
published; it is to what may be kept.**

### 2. The pending store holds the target's identity, and a queue you cannot attribute is a queue you cannot triage

The record carries the name of the target the route was found against.

The queue's whole purpose is that a person looks at it and decides which routes are
worth paying to measure. Three routes filed against three different agents and three
filed against one are different situations and call for different decisions, and a page
that cannot say which is which asks the operator to spend an inference budget blind.
The operator triaging this queue is the same person who registered the target and
attested to the run — the identity is not a disclosure to them, it is their own record
of their own run.

**ADR-0011's argument does not reach this store, and that is a fact about the argument
rather than a convenience.** The rule there is *precedent carries no target identity to
anything blinded*, and it exists because the attacker and the judge are measuring
instruments that must not know which agent they face. The pending store is read by no
instrument. It is not a tool result, it is not consulted by `retrieve_precedent`, it
reaches no prompt, and nothing that reads it is producing a number. The aggregation
hazard ADR-0011 names — accumulate enough entries and a failure pattern identifies a
target on its own — is an argument about a store that *grows*; this one is emptied by
the decision each record is waiting for.

### 3. Five mitigations, and they are the terms the exception is granted on

Each one is a property of this store that `precedent/` does not have, and each is the
reason a refusal that binds `precedent/` does not bind here.

1. **Short-lived by design.** A record exists between the run that found the route and
   the decision that measures it. It is not memory, it is a work queue.
2. **Single-purpose.** One reader, one writer, one question. It is not a general store
   that a second feature will later find convenient.
3. **Read by no instrument.** Nothing blinded reads it, nothing scored reads it, and no
   figure is computed from it. This is what disarms ADR-0011.
4. **Never exported.** No report, no signed artefact and no API response outside the
   queue's own page carries a pending route's payload or its target.
5. **Emptied by the decision it waits for.** A decided record has no payload —
   §4 — so the store's steady state is the routes still awaiting a decision and
   nothing else.

The five are not a rhetorical list. A change that breaks any of them reopens this
record rather than being a change to the store, and the sharpest one is 4: an export of
this queue is a working exploit against a named agent leaving the machine it was found
on.

### 4. The payload is emptied by the decision, and the type is what empties it

State is `pending`, `admitted` or `rejected`, and the payload is a field the last two do
not have — a decided record has no payload to read, enforced by the type rather than by
every caller remembering to null a column.

This is mitigation 5 made mechanical, and it is the reason it is a decision rather than
a hope. A convention that says *clear the payload when you decide* is a convention with
one forgetful call site between it and a store of live exploits with no expiry. The
same reasoning [ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)
decision 2 and [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)
use: the prohibition is carried by the type, so violating it means widening one, which
is a visible act.

### 5. One location, git-ignored as a directory, and no environment override

`pending/routes.sqlite`, through the `DatabaseStore` seam, following
[ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md)
decision 6 and the pattern `/precedent/`, `/decisions/`, `/runs/` and `/checkpoints/`
already follow. A **directory** rather than a file name, for the reason the other three
are directories: SQLite writes `-wal` and `-shm` sidecars, and a journal holding the
payload of a route that beat a named customer's agent must not be what the ignore rule
missed. That reason is stronger here than anywhere it has been applied before, because
here the sidecar holds both of the two fields this record is about.

**No environment override of the path.** A configurable path is a path that can be
configured into a tracked directory, and the operator who does it will have done it to
solve a different problem.

## The local consequence: the identity boundary

The exception is granted to one store, and the way it stays granted to one store is that
the identity has nowhere else to go.

`remember` receives the route key and the counts
([ADR-0032](./0032-the-admission-memory-holds-the-measurement.md)); `enter` receives the
case ([ADR-0033](./0033-an-admitted-route-is-written-into-the-library.md)). Neither
learns whose agent the route came from, and — the half that survives a refactor —
**neither has a field that could hold it.** `DecidedRoute` carries a `RouteKey`,
`Conditions`, readings, the attacker's prose and a case id, and nothing on it names a
target; a written `.toml` record has no such field either.

So the boundary is not a rule about what a caller passes. It is a shape: the identity
exists in the pending store and nowhere downstream of it, and the pending store is the
one place a decision deletes. The bench keeps the disclosure posture on both sides of
the exception, and the exception is a compartment rather than a leak.

## Considered options

**File the pending route into `precedent/findings.sqlite`.** Rejected, and rejecting it
is most of what this record is for. It would require ADR-0008's *prose and never payload
text* and ADR-0011's no-target-identity rule to be relaxed **for a store that is read by
a blinded instrument**, which is the one place neither can be relaxed: `retrieve_precedent`
serves that store to the attacker, and an attacker that could read a target's name has
lost the label-blindness ADR-0011's whole discrimination check rests on. The
alternative's cost is not a widened schema, it is a falsification test that stops
falsifying. A separate store is how the exception stays bounded to a reader that is not
an instrument.

**A prose-only pending record — description, criterion, route key, no payload.**
Rejected on §1, and it is the tempting one because it needs no exception at all. It
produces a queue that can be read and cannot be decided: the bar is measured by sending
the probe, and a route whose probe is gone can only be re-derived by an attacker
rediscovering it, which is the loop this spec exists to close. The honest version of
this option is *keep discarding the routes and write down that you saw them*, which is
worth strictly less than the printed line it replaces, because it looks like a queue.

**Hold the payload but not the target — take the exception once instead of twice.**
Rejected. The two fields are refused by two different ADRs for two different reasons,
and the reason for the target is the one that does not survive contact with this store:
ADR-0011's rule is about what reaches a blinded instrument, and nothing here is one.
Dropping it would buy no posture — the payload, the harder of the two, is already
kept — and would cost the queue the only column an operator can triage on. An exception
argued for one field and taken for one field is not tidier than an exception argued for
two; it is the same exception with a page that does not work.

**Encrypt the payload at rest, or hash it and keep the text elsewhere.** Rejected as
mitigation theatre at this scope. The key would live beside the database on the same
single-tenant disk, so the threat it addresses — someone who can read the file — is not
addressed. The five mitigations are about *lifetime and reach*, which are the properties
that actually differ from `precedent/`, and adding a lock that opens with the key next
to it would make the record read as more protected than it is.

**Keep discarding the route: no store, no exception.** Rejected, and it is the status
quo. It is the option that keeps the disclosure posture perfectly and keeps
`docs/validation.md`'s zero: no route has ever been written into the library by a run,
and the adaptive fraction has never had a non-zero reading. A posture that is preserved
by never producing the evidence the bench exists to produce is a posture that has
stopped being a trade-off.

## Consequences

- `pending/` joins `/precedent/`, `/decisions/`, `/runs/` and `/checkpoints/` in
  `.gitignore`, with the ignore rule's comment saying — as the others' do — what the
  directory holds and which record decided it. This one's comment has to say that it
  holds a working probe and a target's name, because that is the fact a reader of the
  ignore file most needs.
- This is the first place in the repository where a target's identity is written to
  disk beside a working payload. The `docs/validation.md` line under *what has never
  been validated* gains its counterpart: the disclosure posture now has exactly one
  stated exception, and it is bounded by the five properties above rather than by care.
- Any later feature that wants to read this store — an export, a metric, a second
  consumer, a retention policy that lets records age instead of being decided — is a
  change to mitigations 2, 3, 4 or 5 and reopens this record. That is the intended cost
  of writing them down as terms.
- ADR-0008 and ADR-0011 are unchanged. Neither decided anything about a store that did
  not exist when it was written, and this record does not put words in either of them.
