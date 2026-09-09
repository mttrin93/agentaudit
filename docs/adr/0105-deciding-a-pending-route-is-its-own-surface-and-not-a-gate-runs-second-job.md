---
status: accepted
---

# Deciding a pending route is its own surface, and not a gate run's second job

[ADR-0104](./0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md)
gives a route found against a customer's agent somewhere to wait. This record decides
what looks at the queue.

There is an obvious answer and it is wrong. A gate run already attacks the three
reference agents on two models, already holds the case library, already takes an
attestation and already halts for an approved estimate — every piece of machinery
deciding a pending route needs, assembled, paid for and under consent. Folding the
decision into `/gate-runs` looks like reuse: the operator starts one thing, the gate
gets measured, and any pending routes get decided on the way past.

It does not work, for three reasons, and each of them is sufficient on its own. Two of
them are silent failures — a wrong answer rather than an error — which is why this is a
record rather than a routing preference.

## Decision

### 1. Deciding pending routes is its own route family, `/pending-routes`

It records an attestation, declares an estimate, halts for approval, then measures the
selected routes against the three reference agents on two models **in one action** and
decides them.

Its own family for the reason `/gate-runs` is its own family, stated in `backend/api/app.py`
and decided in [ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md):
a run produces rates about somebody's agent, a gate run produces a decision about this
bench, and nothing takes either. Admitting a route is a third kind of fact — a decision
about **a case**, not about a target and not about the bench — and giving it the shape
the other two have is how it stays unmixable with them. No route under `/pending-routes`
takes a gate run id, and no route under `/gate-runs` takes a pending route key.

### 2. The memory is keyed on the model pair, so readings cannot accumulate a gate run at a time

This is the reason that a careful implementer would otherwise discover in production.

The admission memory serves a record **only when it is this run's measurement**
([ADR-0032](./0032-the-admission-memory-holds-the-measurement.md) decision 3), and
`Conditions.models` is a tuple of the underlying models the reference agents ran on,
compared as a whole before anything is served. A gate run runs on **one** configured
model pair, and a gate run that measured a route contributed a reading under that pair.

So the folded design measures a route on gate run *A*, and on gate run *B* — a different
day, possibly a moved second model — finds the stored record's `models` does not match
what it is asking under, answers `Stale`, and measures again. Where the pair is
unchanged the record matches and the route is already fully decided, so the second gate
run adds nothing; where it has moved, every accumulated reading is discarded. **There is
no configuration in which accumulating across gate runs produces a cross-model
measurement that one gate run did not already produce.** The cross-model bar is two
models in one measurement, and one run is where it can be taken.

The alternative is a memory that holds half a measurement — a record keyed on a single
model, assembled later into a pair. That is rejected on ADR-0032's own reasoning:
`remember` replaces rather than appends *because* readings are one run's measurement on
one pair of models, and a record that accumulated them across runs would hold a reading
set matching no run's declared configuration. Half-measurements are the same defect at
finer grain, and they would put the bar's arithmetic behind a join across runs that
nothing validates.

### 3. The library lease is exclusive, so a gate run that also wrote a case would be refused by itself

[ADR-0033](./0033-an-admitted-route-is-written-into-the-library.md) puts the write of an
admitted case inside `enter`, under the library lease, deliberately — the mutual
exclusion is a property of the writer rather than a discipline its callers keep. A gate
run holds that lease for its duration.

A gate run that reached the end of its calibrations and then tried to write an admitted
case would ask for a lease it is holding. That is not a deadlock to be engineered
around; it is the design telling the truth. The lease exists because one writer at a
time may modify a directory of records, and a gate run's whole claim is that it measured
**a library that did not move while it was being measured**. A gate run that grew a case
mid-flight would invalidate the digest it cites in its own result.

Working around it would mean the gate run releasing the lease and retaking it, or `enter`
learning to accept a caller that already holds one. The first breaks the property the
gate result rests on. The second is exactly the widening ADR-0033 declined — *take the
lease in the caller* — one release after declining it.

### 4. The consent mechanism is the one that exists, and the spend is declared here

The attestation is the record `registration.py` refuses to construct incomplete, and the
halt is the same `PendingApproval` seam `POST /runs` and `POST /gate-runs/{id}/approval`
answer. Not a second copy: *a second copy of a consent flow is a second place for it to
be weakened*.

The estimate is declared on this surface and not inherited from anywhere, because the
spend is real and new — three reference agents on two models, per selected route — and
the operator has seen no figure for it. Whatever they attested to for the run that
*found* the route was an estimate for attacking their own agent, made possibly weeks
ago, and it authorised none of this. There is no flag, setting, environment variable or
request field on this surface that starts a measurement without an attestation and an
answered halt.

### 5. `cross_model_bar` moves into the backend and both surfaces call it

`scripts/swap.py` keeps calling it and its behaviour there does not change. A separate
surface must not become a second code path to a reference agent, and the way it does not
is that the bar is one function both entry points call. The measured proof is that the
swap's own tests pass untouched.

## What this gives up

**The operator runs a second thing.** That is the cost, it is the whole cost, and it is
worth naming plainly rather than describing as a benefit.

Someone who wants both the bench gated and their queue drained starts two actions, reads
two estimates, and approves two halts. On a surface whose other decision of record is
[ADR-0021](./0021-the-console-may-start-a-gate-run.md) — the console *may* start a gate
run, reversing PLAN.md §8's command line, because making the operator drop to a shell
was a real cost — adding a second thing to run is a step in the direction that ADR spent
itself arguing against.

It is accepted because the two actions are not two halves of one intention. The gate
asks *does this bench discriminate*; the queue asks *is this route worth keeping*. They
are answered at different cadences by the same person: a gate run is decided when the
library moves, a pending route is decided when the operator has routes worth paying for.
A combined action would make every gate run wait behind a triage decision, and would
make every triage decision cost a full gate.

And two approvals is the honest count. Two spends, separately authorised, is what
[ADR-0007](./0007-canary-nonce-as-proof-of-control.md)'s seam is for; one
approval covering both would be one attestation authorising a spend the operator was
shown half of.

## Considered options

**Fold it into `/gate-runs` and accumulate readings across gate runs.** Rejected on §2,
and it is the option this record exists to refuse. Its appeal is that it spends nothing
new: the reference agents are already being attacked, so measure the pending routes
while they are warm. It fails because the memory's unit is a **pair of models measured
together**, so readings gathered one gate run at a time are `Stale` on arrival where the
pair moved and redundant where it did not — and because §3's lease refusal makes the
write impossible inside the run that would do the measuring. The failure is quiet: the
implementation looks right, the routes stay undecided, and the reason is three fields
deep in `Conditions`.

**Fold it in, and redesign the memory to hold a per-model reading.** Rejected on ADR-0032
decision 3's reasoning. It is the version of the option above that could be made to work,
and the price is that the cross-model bar stops being decided on one measurement and
starts being decided on a join across runs — with an invalidation question at every
field `Conditions` carries, and a stored half-reading whose matching half may never
arrive. A bar that can be assembled from parts taken at different times is a bar whose
`D` nobody can point at a single measurement for.

**Fold it into `/runs` — decide the route in the run that found it.** Rejected, and it is
the spec's own problem statement: a customer run touched one endpoint, the customer's,
and holds no reading against a reference agent on any model. The deciding evidence is
structurally out of that run's reach, and this is not an ordering bug to be fixed by
running things later in the same process. It would also point a customer's attested run
at three agents they never authorised a call to.

**A command-line script only, the way `scripts/swap.py` walks the path today.** Rejected.
It is the cheapest thing that could work, and it is what the bench already has for
reference-agent routes. The queue this decides is populated by *console* runs against
somebody's real agent, so the operator who fills it is the one ADR-0021 decided should
not have to drop to a shell, and the routes carry a target identity the console is the
only surface that shows them. A shell script would also need its own attestation and its
own halt, which is §4's second copy of the consent flow arriving by the back door.

**Drain the queue automatically once a route is filed.** Rejected. It is an unbounded
spend authorised once: every route the attacker rediscovers becomes three agents on two
models, at the operator's cost, with nobody having seen a figure. Nothing decides a
pending route without an operator attesting and approving.

## Consequences

- A fifth thing on this API that spends money, and the second that spends it on the
  bench's own behalf. It carries the same attestation record and the same interrupt seam
  as the other two, and no third consent flow is written.
- `cross_model_bar` lives in the backend with two callers. `scripts/swap.py` is a caller
  rather than the owner, and its tests are the regression check on the move.
- A gate run and a pending-route measurement refuse each other through the library lease,
  in both directions, which is ADR-0033's existing property observed rather than a new
  one added.
- The operator's workflow gains a step. `docs/validation.md`'s line about the loop having
  been demonstrated only on constructed evidence becomes falsifiable by an operator doing
  two things rather than one, which is the trade this record accepts.
- ADR-0018, ADR-0021, ADR-0032 and ADR-0033 are unchanged. Each is read here for what it
  decided; none is edited to have decided this.
