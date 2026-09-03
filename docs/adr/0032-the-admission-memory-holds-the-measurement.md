---
status: accepted
---

# The admission memory holds the measurement, and the gate decides it again

The admission gate decides one proposed route against a declared threshold and writes
nothing. `adaptive/promotion.py` is explicit about it — "Nothing is written. The
admitted case is *returned*", and "A refused promotion returns no case at all … a
refusal is a discard, and a discard has no record" — and `scripts/swap.py` prints the
consequence at the end of every swap run.

So a route the attacker discovers, proposes, and the gate refuses on the cross-model
bar is rediscovered next run, re-proposed, and **re-measured against three reference
agents on two underlying models**, at the operator's cost, for the same answer. The
`RejectionKind` counts behind the refusal are computed and thrown away, when
[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) calls
exactly those counts a finding in its own right: "direct evidence that a route the
attacker found was a property of one model rather than of the agents' defences."

Remembering them is obviously worth doing and is not the interesting part. The
interesting part is that **the admission gate is the single edge the adaptive layer
reaches the scored side by** ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)),
and a memory at that edge means a *past* run can change what a *present* run reports.
Get that wrong and the failure is silent and expensive: a route the current declared
threshold would admit reported as refused, or worse, one it would refuse reported as
admitted, from a file nobody looked at.

This ADR is mostly about that.

## Decision

1. **The memory holds the measurement and never the decision.** What is stored is the
   counts the three reference agents returned — `AdmissionReading`s — and `promote`
   decides them again, under the current declared rule and the current arithmetic, on
   every run that reads them. No verdict, no rate, no interval, no `D`, no bar and no
   threshold is in the file.
2. **The key is the route**: the family, and a `sha256` of the probe that actually ran.
   Never the probe (ADR-0008) and never the case id, which `proposal.py` mints as
   `adaptive-{family}-{uuid4}` per proposal. The type is `RouteKey` and not `Route`,
   because CONTEXT.md's **route** is "the sequence of probes that worked" and this is
   the identity of the *one* probe a `ProposedRoute` carries — `propose_case` drafts a
   case from the probe that actually ran, so a route reaches admission as a single
   payload. Naming the type after the key rather than after the route is what keeps
   this ticket from quietly narrowing a load-bearing term; CONTEXT.md is unchanged.
3. **A record is served only when it is this run's measurement.** `Conditions` — the
   underlying models, a digest of the criterion, and the denominator — is compared
   before anything is served, and the `RejectionKind` the measuring run reached is
   stored beside the counts as a tripwire.
4. **A conclusion the current arithmetic no longer reaches is re-measured, not
   reconciled.** Where the re-derivation disagrees with the stored `RejectionKind`, the
   answer is `Stale` and the route is measured again.
5. **Its own database**, at `decisions/routes.sqlite`, git-ignored as a directory. Not
   a table in `precedent/findings.sqlite`
   ([ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md)
   decision 6).
6. **The connection belongs to the batch**, and the SQLite-opening machinery is shared
   with the precedent store rather than copied: `backend/bench/store.py`.
7. **Only a decision about the route is remembered.** `RejectionKind.UNREAD` and
   `NOT_MEASURED` are refused at the write.
8. **Nothing here writes to the case library.** Remembering an admission is not
   admitting; #40 is the ticket that takes an admitted route onward.

ADR-0029 is not amended. Its decisions 2, 6 and 7 are honoured and its shared parts are
reused; nothing it decided is reversed here.

## Why the threshold is not in the file, and what that buys

The obvious shape for this store is a cache of decisions: route → *refused,
cross-model*. It is also the shape that has to be invalidated when the declared
threshold moves, and "invalidate the cache when `GateRule` changes" is a rule somebody
has to remember — which is the same class of thing ADR-0003 refuses when it says a
threshold written inline "is a threshold that can be quietly moved at hour 30 to make a
run pass."

So the file holds counts. This is not a new argument; it is `AdmissionReading`'s own,
one level out:

> Counts and not a rate, and certainly not a stored `D`. A rate is
> `successes / attempts` and an interval is a function of both, so recording the
> derived numbers would let a record carry a `D` that its own counts contradict — and
> admission is the one place in the bench where the number decides whether a case may
> ever reach a user.

And it is why `AdmissionRecord` sits on a case record at all: "admission is evidence
rather than an assertion: a reader with this block and `backend/bench/admission.py` can
re-derive the decision that let the case in."

Three things follow, and they are the whole of the reproducibility answer.

- **A moved `discrimination_floor` or `interval_confidence` needs no invalidation**, in
  the sense that there is no cached answer to invalidate. The remembered counts are
  re-decided under the rule this run applies. A memory that had cached *admitted* and
  been read under a raised floor would have admitted what the declared bar refuses;
  this one cannot, because it does not know the word.
- **A moved arithmetic needs none either.** If `kind_of`, `AdmissionOutcome.admitted`,
  `scorer.discrimination` or the Wilson interval changes — a bug fixed, a rule
  clarified — the remembered counts are decided by the *new* code. Nothing is replayed.
- **A run answered from memory is reproducible from the same inputs every other
  admission is reproducible from.** Give a reader the row and
  `backend/bench/admission.py` and they get the answer the run printed. That is the
  same property ADR-0003 requires of the gate and ADR-0012's discards already had.

What remains, therefore, is a much smaller question than cache invalidation: **are
these counts a measurement this run could have taken?**

## The invalidation rules, and why there are exactly four

A remembered measurement is served only if all four hold. Each is a test, and each was
driven red on purpose.

**The models must be the models this run measures on.** A reading is a reading *on a
model*, and the sharpest case is the one
[ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md) already named:
a gate run on a stub model measures **the field** not at all, so a cross-model bar met
on `stub:obedient` and `stub:cooperative` is not met on two provider models. That is
not hypothetical — the only reading of this bar `docs/validation.md` records was taken
on exactly those two stubs. A memory that answered a paid run from them would report a
bar cleared against hardcoded replies as a bar cleared against the field. The same
comparison covers the plainer case of a swap that changed its second model.

**The criterion must be the same criterion.** The stored digest covers the success
condition, the judged condition, the verdict class and the preconditions — everything
about the proposed case that decides what a verdict *means* or whether the case can run
at all. The payload is not in it because the payload is the key, and the case id cannot
be in it because it is a fresh uuid per proposal. `proposed_from` copies the criterion
off whichever objective the episode was working on, so the same probe under a different
objective is a different measurement and is treated as one.

**The denominator must be the rule's denominator.** `attempts_per_case` is the one field
of `GateRule` that changes what a count *is* rather than what a threshold does with it,
and it is also the one field a console may set ([ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md)).
Recomputing a rate at one `n` under a rule that declares another is precisely what
`GateRule.NOT_A_GATE_RESULT` exists to say aloud, and a memory that did it quietly would
be worse than no memory.

**The stored conclusion must be the one the current code reaches.** This is the tripwire,
and it is what catches everything the three conditions above cannot see — a threshold
that moved, an arithmetic that was fixed, a hand-edited row, a database restored from
somewhere else. On a disagreement the record is not repaired and not deleted: this module
has no standing to choose between two thresholds, so the route is measured again. Note
that the tripwire makes the *conservative* choice on a moved threshold, which the
counts-only design did not strictly require — re-deciding would have been defensible —
because a changed declared bar is the moment a reviewer is least willing to take an old
measurement on trust, and the cost of being conservative is one admission run after a
once-in-a-project event.

Two further refusals, which are about what is worth remembering rather than about
staleness:

**`UNREAD` and `NOT_MEASURED` are not remembered.** `RejectionKind`'s own docstrings
draw the line: `UNREAD` is "a run that did not happen the way the bar needs it to, and
it is not evidence about the route", `NOT_MEASURED` is "no reading exists, so nothing
about this proposal has been measured". Remembering either would be remembering that a
measurement did not happen, and then answering a later run with it. `ABOUT_THE_ROUTE`
is a frozenset rather than a predicate so that a sixth `RejectionKind` has to be
classified rather than defaulting into the memory.

**A lookup does not write.** A stale record stays as the run that measured it left it,
on the reasoning that keeps a retired case on disk: it is evidence of what was measured.
The run that supersedes it is the run that replaces it, and `remember` is idempotent by
the key.

## Where the store went, and why not the precedent store's file

ADR-0029 decision 6 is "one database, one concern", and its consequences left this
ticket the reasoning rather than only the rule:

> **#39 gets its own database.** The gate's decisions are scored-side state, and this
> file is adaptive-layer memory that ADR-0004 and ADR-0013 keep two instruments away
> from by an import test. Sharing one file would put a scored reader and precedent
> behind one path, one ignore rule and one set of migrations, and the first question a
> reviewer would have to answer is whether the separation still holds. Its own file
> makes that question not arise.

Taken as written. `decisions/routes.sqlite`, its own git-ignored directory, its own
namespace `("agentaudit", "admission")` — two elements and no tenant, ADR-0019 point 5
restated for the same reason ADR-0029 point 4 restated it.

There is a second reason ADR-0029 gave and it applies here too: `precedent/` is
git-ignored user data that nothing prunes. So is `decisions/`. Neither is a place to put
the other's growth.

**What is shared is the machinery, and it had to be.** ADR-0029's decision 2 cost two
functions — `_enable_wal` and `_migrated` — whose whole justification is a measurement:
without them, six threads against one cold database failed 14 runs in 20, and eight
processes released from a barrier lost 8 batches. A second copy of a fix like that is
the one thing that must not happen, because the copy that is not being exercised is the
copy that rots. So `backend/bench/store.py` holds `DatabaseStore` — the location, the
pragma, the schema under `BEGIN IMMEDIATE`, the read that does not create the file, and
`NoVectorIndex` — and `PrecedentDatabase` and `DecisionDatabase` are subclasses whose
whole body is where their file goes.

The subclasses are not decoration. A field annotated with one refuses an `InMemoryStore`
before a test has to, which is ADR-0019 point 2's mechanism and is what
`DurablePrecedents.store` and `DecidedRoutes.store` both rest on. And two types rather
than one shared type is what keeps the reviewer's question from arising: neither
concern's store can be handed to the other by accident.

`default_path` is a classmethod reading a module constant rather than a class attribute,
so that `conftest.py`'s redirection still lands. This is behaviour-preserving for the
precedent store, and the whole of its existing suite is what says so.

## Who owns the connection

[ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) and ADR-0029 reached
opposite answers for stated reasons, and this store is on ADR-0029's side of the line
for ADR-0029's reason rather than by inheritance.

The question ADR-0028 answered was *which thread owns the connection*, and the answer
was *none of them — the object does*, because an `ApprovalRun` is a thing with a
lifetime: it is constructed, it halts, it waits up to an hour, and **something else
answers it**. The connection has to outlive the call that made it.

`DECIDED_ROUTES` is the other shape entirely. It is a module-level object constructed at
import and never closed — the default argument of `cross_model_bar` — and giving it a
connection would build precisely the process-wide global ADR-0028 refused, on the
grounds that "a module-level connection is a global with a lifetime nobody closes." A
route lookup has no rendezvous in it: there is no second thread for anything to be the
answer to. One `get` per proposal and one `put` per measured route, each complete inside
one call.

Three things fall out, exactly as they did for precedent: the path stays the authority
and the object holds no state, so two store objects against one file cannot disagree and
`conftest.py` can redirect the suite by patching one attribute; `check_same_thread`
stays at its strict default; and the cost is a connection and two `SELECT`s per batch
against traffic of a handful of operations per run.

**#61 goes next on this question and inherits an answer rather than a discovery.** It
makes `BenchRuns`' run records durable, and run records are the third shape: they are
written by the run thread and read by the API thread while the run is still going, which
is nearer to ADR-0028's rendezvous than to this one. The reasoning to apply, in order —
does the state have a lifetime longer than the call that writes it, and is there a
second reader who is not the writer? If yes to both, ADR-0028's answer. If no,
`DatabaseStore` already exists and is measured under contention, and a subclass of it is
about eight lines.

## What this does to `docs/validation.md`

**One claim changes shape and it is worth being exact about it.** The 2026-08-19 entry
records the cross-model bar's only reading: "4 proposal(s) decided, 4 of them facing the
cross-model bar … cross-model rejection: 4". Every one of those four was measured in the
run that printed them, because this memory did not exist. From now on a run's rejection
counts can include counts an *earlier* run measured, so the count alone no longer says
what the run in front of the reader paid for.

That is answered where it happens rather than by a caveat. `Consultation.stated()` prints
how many proposals were put to the bar, how many were answered from memory, and how many
routes were measured, and every remembered decision prints the date its counts were taken
and the models they were taken on. It goes into the cross-model section of the swap
document and into the terminal output, in the same block as the counts rather than in a
section of its own — a figure a reader has to cross-reference to qualify is a figure that
will be quoted unqualified.

**Reproducibility is unchanged where it was claimed and unchanged where it was not.**
ADR-0010 already scopes it: the gate decision is reproducible from its recorded inputs;
the adaptive section is recorded rather than re-derivable. This memory reaches neither
of those. It reaches the admission gate, whose decision is a pure function of counts and
the declared rule and stays exactly as re-derivable as it was — the counts simply come
from a file this time and the file says which run took them. And it reaches the report's
admission block, which is not a scored figure at all.

**Nothing here can enter a scored number** and an import test says so in the one
direction that could break it: no module producing a rate, an interval, a band, a `D` or
a κ may reach `backend/bench/decided.py`. The memory reads the admission arithmetic —
that is what re-deriving a decision *is* — so the wall cannot be symmetric, and the
asymmetry is the point. The file is machine-local and git-ignored, so an instrument that
read it would be an instrument whose result depended on the machine.

The judge's and the adjudicator's walls against the precedent store
([ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md),
[ADR-0013](./0013-adjudication-is-a-third-instrument.md)) are unmodified and still pass;
both are also in the list above, so neither can reach this store either.

## Considered options

- **Cache the decision.** The shape everybody reaches for. Rejected on the section above:
  it is the shape that has to be invalidated when the declared threshold moves, and the
  cost of getting that wrong is a route admitted or refused against a bar nobody
  applied. Storing counts removes the failure mode instead of guarding it.
- **Store the decision *and* the counts, and trust the decision.** Cheaper to read, and
  it is what the ticket's wording suggests. Rejected because the stored answer would
  then be load-bearing, and a row whose answer disagreed with its own numbers would be
  believed. The answer *is* stored — as `decided_as` — and is deliberately not the
  answer: it is the tripwire, which is the strongest use available for it.
- **Fingerprint the whole `GateRule` and invalidate on any change.** Considered, and it
  is what `library.py`'s `_versioned` does for a case record — digest everything, exclude
  deliberately. Rejected as answering the wrong question: every field of `GateRule`
  except `attempts_per_case` is a threshold applied *to* counts, so re-deciding is exact
  and a fingerprint would only force a re-measurement the arithmetic does not need. The
  tripwire then catches the case where re-deciding lands somewhere new, which is the
  case worth being conservative about.
- **A `gate_implementation_version` constant, bumped by hand.** Rejected on the standing
  objection to hand-kept version strings — `library.py` records it — "a version string
  somebody forgets to raise on the run where it mattered." The tripwire needs nobody to
  remember anything.
- **Fingerprint the three reference agents' prompts too.** Sound: change what *hardened*
  means and every stored reading is about different equipment. Rejected for now, and the
  exposure is stated rather than closed: `bench` does not import `targets`, so the digest
  would have to be supplied by the caller, and the same exposure already exists for the
  decay series `ADR-0022` reads over — a `GateReading` stored on a case record is
  compared across gate runs with nothing fingerprinting the agents either. Being stricter
  here than the series that decides retirement would be strictness in the wrong place.
  The honest mitigation is that a reference agent's prompt is versioned by the
  repository and changing one invalidates published readings anyway, which is a
  conversation, not a cache miss.
- **Key by the case record's whole digest.** Rejected in one line: the case id is in it
  and is a fresh uuid per proposal, so the key would never be hit twice — which is the
  defect.
- **Key by the attacker's prose description.** Rejected: the model writes it, so two
  descriptions of one route are two keys and one description of two routes is one key.
- **A table in `precedent/findings.sqlite`.** Rejected above, on ADR-0029 decision 6.
- **A JSON document, as the precedent store was.** Rejected on ADR-0029's arithmetic,
  which applies unchanged and more strongly: the access pattern here is a lookup *by
  route*, which is the pattern that ADR named as the reason the document was the wrong
  shape.
- **Write the admitted case into the library while we are here.** Rejected as #40's
  ticket, and deliberately: entry is still a human's action, and the writer is the piece
  the first proposal that clears will need. Remembering an admission is not admitting.
- **Deduplicate proposals rather than routes.** Rejected: `docs/validation.md` records
  one run proposing four cases "all describing the same route in prose", and the count's
  unit is stated there — "the count's unit is the proposal, because a proposal is what
  admission decides." So a route is *measured* once per run and every proposal of it is
  still decided and still counted.

## Consequences

- `backend/bench/decided.py`, and `backend/bench/store.py` extracted from
  `backend/bench/adaptive/precedent.py` with no behaviour moved. `uv.lock` does not move.
- **`AdmissionReading` gains `stored()` and `read()`.** Three callers read those six
  fields — a case record's `[admission]` block, an entry of its decay series, and this
  memory's rows — and they were three copies of the same six lines. One pair of methods
  on the type, in the house pattern `Precedent.stored`/`read` already uses, and the
  coercions live where the defensive caller needs them. `adjudicator` is the field that
  would have gone missing quietly, so it has a round-trip test: a reading whose
  instrument was dropped reads as one a success condition decided, which is the
  inference ADR-0004 forbids making from anything but the record.
- **Durability is proved twice**, as it is for the precedent store: once by dropping the
  memory object and rebuilding it against the same path, and once by dropping the whole
  interpreter and reading the row back from a subprocess. ADR-0019 point 4 says *in a
  new process*, and only the second says it.
- `ReadingOutcome.counts` and `AdmissionOutcome.counts` recover the `AdmissionReading`s a
  decision was made over. Lossless, because `Rate` already carries its successes and its
  denominator — "3 successes in 30 attempts and 100 in 1000 are the same number and not
  the same evidence" — so an admission decision can be reduced back to its measurement
  and re-derived from either end. Nothing else in the bench needed that; this store is
  built on it.
- **`AdmissionRecord.admitted_on` is the day the reference agents were run**, not the day
  the record was read back. `recall` has no `today` argument for that reason: a caller
  able to supply one could date a year-old measurement to this morning. #40 files the
  record this produces, so the date it carries is the date its evidence was taken.
- **`cross_model_bar` grows a `Measure` seam.** `measure_on` is its only implementation.
  It exists because the assertion this ticket owes is about an admission run that did
  *not* happen, and a call nobody can observe is not assertable.
- **A remembered decision says so on the promotion's own lines**, not only in the
  memory's block. `Promotion.stated` prints *promoted* or *discarded* and says nothing
  about where its counts came from, so a reader of that list could not tell a decision
  the run paid for from one it read back — `Consultation.reported` pairs the two lists
  and refuses a pairing that has lost an element, because mislabelling one promotion is
  the specific harm.
- **An operator who wants a route re-measured deletes `decisions/`**, or its row. There
  is no flag, and adding one would be adding a way to spend money by accident on the
  same footing as the way to save it. The directory is disposable by construction: it
  holds nothing that is not a re-measurable fact about the bench's own equipment.
- The import-graph walk that three test modules now need moved to `conftest.py`, and the
  two copies of it went with it.
- **#40 inherits a de-duplication surface and a shape to file.** A route it is about to
  write into the library is one this memory has a row for, keyed by family and probe
  digest, holding the counts and the date; `Remembered.promotion.case` is the case
  record with the `AdmissionRecord` that would let it in, already dated by the
  measurement. What it must not do is treat the memory as the record of what is *in* the
  library: this store says what was decided, the library says what was admitted, and
  ADR-0029's "one database, one concern" applies to that distinction too.

Cross-references:
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the one
edge this sits on, and the rates it may not touch),
[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) (the bar,
and why a discard is a finding),
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the declared rule this
re-derives against),
[ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md) (a reading is a
reading on a model, and a stub measures the field not at all),
[ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md)
(one database one concern, and the connection),
[ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) (the opposite answer
about who owns a connection, and why it is opposite),
[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
(durability across a restart, and the single-tenant namespace),
[ADR-0008](./0008-repo-disclosure-posture.md) (why the probe is a digest and the file is
never committed).
