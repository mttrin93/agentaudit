---
status: accepted
---

# A run record outlives its process and carries no run, so a recovered halt can be closed and never confirmed

[ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) put the approval
checkpoint on disk and stated, in its own consequences, which half of restart
survival that was:

> **The graph's half of restart survival is done; the API's half is not.** `BenchRuns`
> holds its `RunRecord`s, its `RunState`s and its `PendingApproval` rendezvous in
> memory, so a process that restarts still forgets that a run exists, what target it
> was pointed at and who to hand the answer to.

So the human's experience of a restart was unchanged. They answered, the route raised
`KeyError`, and the body they got back said **no run of that id was started by this
bench** — a false statement about a run this bench had started, halted, estimated and
written a durable checkpoint for. And a `/checkpoints/` directory holding approver
identities grew without bound, because a halt is reachable only by thread id and no
run record carried one.

This ADR is mostly about what a run record may *not* carry, because that question
decides the other two.

## Decision

1. **`RunRecord` and `RecordedRun` both carry the halt's `thread_id`.** ADR-0028 point
   4 made a run nameable and left the name inside `ApprovalRun.__init__`, where a run
   started through the API minted it on the worker thread and never returned it. The
   id is minted in `BenchRuns.start`, derived from the run id, and passed down through
   `run_calibration` and `run_under_approval`.
2. **The durable record carries the declaration and never the measurement.** No
   `RunState`, no `RunPlan`, no `CalibrationResult`, no `SignedArtefact`, no
   `threading.Event`. `RecordedRun.of` is the one place the projection is written and
   `test_run_records.py` asserts the field set whole.
3. **The target is not in it, and its credential especially is not.** What is stored
   is the declared target *name* and a `sha256` of the endpoint. This is the reason
   point 4 reads the way it does.
4. **A recovered halt can be declined and cannot be confirmed.** A no is `DECLINED` in
   full, with the operator's reason. A yes is refused and recorded as `FAILED` with
   `confirmed_by` set — *answered and not run*.
5. **The hour is a deadline in the record, not an `Event.wait()`.**
   `answerable_until` is `recorded_at` plus `approval_wait_seconds`, and
   `RecordedRun.answerable_at` is the one place it is compared with a clock. A halt
   past it is `UNANSWERED`.
6. **A row an earlier process left in flight is reconciled on the way in**, at the
   moment a `BenchRuns` is constructed and again at every read of one: `RUNNING`
   becomes `FAILED`, and an expired halt becomes `UNANSWERED`. Not optional — see
   below. A recovered row is read from the file rather than cached, because the file
   is the authority and the checkpoint database is shared.
7. **No new `RunStatus` member.** The vocabulary already had the words.
8. **A checkpoint is kept exactly as long as the run it belongs to can be answered**,
   and `forget_halt` deletes it when it cannot. Retention is decided by a run record
   and never by a timer.
9. **Its own database**, at `runs/started.sqlite`, git-ignored as a directory, over
   the shared `DatabaseStore` — ADR-0029 decision 6, and its decision 2 for the
   connection.
10. **`records()` still returns `RunRecord`s only.** A recovered row is served by
    `recovered()`, which returns the other type.

ADR-0028 is not amended. Its six decisions stand; what changes is that its stated
remaining work is done, and point 6 of it — `ApprovalState` stays three primitives —
turns out to be what makes any of this possible. ADR-0019 is not amended either.

## ADR-0019's argument, and where it bites here

ADR-0019 point 3 says the durability claim "rests on the **interface** and the
lifetime, not on the backend's brand." ADR-0028 point 6 says the sharper thing, and
it is the sentence this ticket had to answer:

> A real serializer makes widening it more tempting, not less… a checkpoint is not the
> place to discover which of a run's records happen to survive a serializer.

A `RunRecord` is not three primitives. It holds a `RunState` with live counters and
every `AdaptiveEpisode` the run opened; a `CalibrationResult` holding the target's own
replies transcript by transcript; a `SignedArtefact` of canonical bytes; a `RunPlan`
of case records including their payloads; a `threading.Event`; and a `TargetConfig`.
Serialising that is available — most of it is dataclasses of primitives, and the rest
could be made to be. It is refused on four separate grounds, and each one is a
different kind of harm:

- **A second copy of a counter can disagree with the counter.** `ApprovalState`'s
  docstring already refuses to checkpoint whether the suite ran, "because a second
  copy of it here would be a checkpointed field that no reader consults and that can
  disagree with the counters." Calls spent per layer is the figure a ceiling is
  enforced against (ADR-0007). A durable copy of it would be a number a restart could
  serve, and a number nothing had checked against the run.
- **It would put payloads and replies at rest in a fourth place.** A
  `CalibrationResult` is transcripts: the attack that was sent and what somebody
  else's agent said back. ADR-0008 governs where that may live, and the answer has
  never been *wherever a serializer reaches*.
- **It would make a restart's fidelity a property of the round trip.** The exact
  failure ADR-0028 named. A reader of a recovered run would have to know which fields
  came back whole, which came back defaulted, and which came back subtly narrowed —
  and the fields that lose the least on the way through are the ones nobody would
  notice had.
- **It would rebuild a run that had already spent money.** A restored `RunState` with
  counters at 43 calls, handed to a suite that resumes, is a run held to a ceiling
  against a spend it did not make and cannot verify. `BudgetExceeded` exists because
  "a run that stopped early measured fewer attempts than the rate it would report is
  denominated on, so a partial run is void rather than smaller." A resumed partial run
  is that, with the arithmetic looking sound.

So what crosses is a **statement about a run**: that it exists, who authorised it,
what it was estimated at, which halt it is waiting at, until when, and where it got
to. Fifteen fields, all primitives or small frozen records of primitives, and the set
is asserted whole for ADR-0028 point 6's reason rather than checked field by field.

**And a `RunRecord` is not reconstructed from one.** The two registries in `BenchRuns`
are two types and they stay two — the live records are held in a dictionary, recovered
rows are read from the file, and `records()` returns run records only. A single
signature that took either would be the place a recovered row acquired a plausible
plan and a zeroed counter, which is the whole failure mode restated as a type. This is
ADR-0010's discipline about `Attempt` and `AdaptiveEpisode`, borrowed for a different
pair: *if you find yourself widening a signature to accept both, stop.*

## Why a recovered halt cannot be confirmed, and why that is a decision

Point 3 decides point 4, and it is worth being exact about the direction of the
argument, because the tempting reading is that resumption was too hard.

It was not. `ApprovalRun` already resumes a halt from disk with a *new* closure — the
test `test_approval_checkpoints.py` drives is exactly that, and it works precisely
because `ApprovalState` is three primitives and carries no run. Rebuilding a plan is
`plan_for` over the configured library; rebuilding a budget is `RunBudget.declare`;
holding the run to the ceiling that was confirmed is a comparison against two stored
integers, and refusing a rebuild whose library digest has moved is one more. The
machinery is all there.

What is not there is the endpoint. A `TargetConfig` carries `url` and `auth_token`,
and `registration.endpoint_hash` exists because "a live URL that answers jailbreak
payloads is not a thing to write into a document that travels" (ADR-0008). A bearer
token for somebody else's staging agent is worse than the URL: it is a credential, and
this repository has never written one to disk. The trade is therefore not *resumption
versus effort*, it is **resumption versus a credential store**, and a credential store
is not something to acquire as a side effect of a durability ticket.

Three things make the refusal the right side of that trade rather than a shortfall:

- **The estimate is cheap to present again and the run is not.** A fresh run against
  the same target halts in front of the same two figures with nothing spent. What the
  operator loses is a form to fill in; what they would risk is a token at rest.
- **The confirmation would be about a run nobody could check.** ADR-0007's mechanism
  is that nothing exceeds what a human confirmed, and the confirmed figures were built
  from a library and a rule this process re-reads. Every guard against those having
  moved is a guard somebody has to have got right, and the failure is silent: a run
  spending against a ceiling from a different library. A fresh estimate has no such
  guard to get wrong.
- **The direction is the conservative one.** A refused yes costs a request. An honoured
  yes against a stale declaration costs money on somebody's endpoint.

**What the human is told is the whole of the deliverable here.** The refusal names the
run, when the earlier process started it, that this process holds no state for it,
that nothing was sent and nothing was spent — by the halted run *or* by the
confirmation — and that a fresh run will present the same two figures. It is a `409`
rather than a `404` because the run is on the record and it is the answer that could
not be applied, and rather than a `200` because a `RunResponse` is built from a plan
and counters that a recovered run does not have. `GET /runs/{id}` keeps its `404` — the
counters belonged to the run state and did not cross — and its body now names the run
and what the record says instead of denying it.

## Three answers stay three, which is ADR-0028's own argument

ADR-0028 exists because a lost halt "produced… a run nobody was ever asked about. The
one distinction the halt was built to preserve was the one a restart erased." The same
hazard arrives here from the other side, and there are now four things a person can
do to a recovered halt. Each has its own outcome and none may collapse into another:

| What happened | Status | Why not the others |
| --- | --- | --- |
| Nobody answered inside the hour | `UNANSWERED` | Nobody said no, nobody said anything — the outcome the `Event.wait()` reached in the process that is gone |
| Somebody refused it | `DECLINED` | A refusal needs no target and no graph; the run spent nothing either way, and a figure a user refused is evidence the cost display works |
| Somebody confirmed it and it could not start | `FAILED`, statement `CONFIRMED_AND_NOT_RUN` | Answered and not run. `UNANSWERED` would say nobody answered; `DECLINED` would say they refused |
| Its process died mid-suite | `FAILED`, statement `LOST_WITH_ITS_PROCESS` | Not `ABORTED` — a run stopped by its own ceiling is the budget working. Not a partial reading either |

**Rows 3 and 4 are told apart by the statement and not by `confirmed_by`**, and it is
worth being exact about that, because the obvious reading is wrong. A row only reaches
`RUNNING` after somebody confirmed it, and `answer` sets `confirmed_by` before writing
— so a run that died mid-suite carries a confirming identity too, and a reader
branching on that field would see the same value for both. What differs is the one
thing a person needs, and it is in the sentence: `CONFIRMED_AND_NOT_RUN` says nothing
was spent, and `LOST_WITH_ITS_PROCESS` says the spend is unknown and this bench cannot
say how far the run got. That both are `FAILED` is decision 7 working rather than a
loss: a poller's question is *do I keep polling*, and the answer for both is no.

**A lost run cannot read as an answered or an unanswered one**, and what proves it is
that each row is written before the refusal is raised and read back from the database
in the assertion. The fourth row is the one nothing else in the bench had a word for,
and it deliberately does not get one: see below.

## Why no ninth `RunStatus`

The obvious move is a member meaning *lost with its process*. `RunStatus.in_flight`
even invites it — "so that a seventh terminal state is terminal on the day it is added
rather than on the day somebody remembers this list."

Rejected, because a status is what a *poller* branches on, and a poller's branch is
already right. `FAILED` is what this vocabulary keeps for a run that stopped without
being a reading about the target, and it already covers an instrument that could not
be built and an endpoint that could not be reached — both of which, like this, sent
nothing and measured nothing. What differs between them is *why*, and why is
`statement`'s job in every other case in this module.

The cost of a ninth member is not the enum line. It is a `RunStatus` union in
`frontend/src/run/progress.ts`, a label in `frontend/src/console/runs.ts`, and a
vocabulary word in CONTEXT.md — three surfaces asked to learn a distinction that
changes nothing anybody does. The two words that *were* needed, `UNANSWERED` and
`DECLINED`, already existed for exactly this reason, and ADR-0028 is why.

**`ReportRefusal` does gain a member, and it is the same rule rather than an
inconsistency.** `ReportRefusal.LOST_WITH_ITS_PROCESS` is added, because that enum
answers a different question — *why is there no report* — and none of its four
existing members is true of a recovered run: it is not a run nobody started, it is not
in flight, it may well have completed, and its artefact may well have been signed, by
a process that has ended holding the bytes in memory. The rule in both places is *add
a word when no existing word is true, and not when one is*; `FAILED` was already true
and `no_such_run` was already false.

## Why the reconciliation is not optional

`RunStatus.in_flight` calls `RUNNING` still going, and a row left saying so is a run
nothing is driving. Two things follow immediately and neither is a nicety.

`BenchRuns.instrument` and `.cover` refuse an operator while any run is in flight, on
ADR-0007's reasoning — a run awaiting approval was shown an estimate built from those
settings. One row from a killed process would therefore refuse every settings change
for the lifetime of the deployment, on behalf of a process that no longer exists, and
the refusal would name a run id nothing could explain. And a poller would be told to
keep polling.

So it happens at construction, once, and the moved rows are written back so it
survives this process too. The two live in-flight checks stay on `self._runs` and
deliberately do not consult the recovered rows: a recovered halt *cannot* be
confirmed, so a setting changed under it cannot make a confirmation a statement about
a different run — which is the only thing those checks are for.

The reconciliation is also where retention gets its trigger, which is why the two
landed together.

## Retention, and why it is not a sweep

ADR-0028's consequence was plain: "nothing yet prunes it — a halted run's checkpoint
is kept until somebody deletes the file." Nothing *could*. A halt is reachable only by
thread id, and until decision 1 no run record carried one.

The rule is the only one that is knowable from the data: **a checkpoint is kept
exactly as long as the run it belongs to can still be answered.** `forget_halt` runs
when a live run settles, when a recovered halt is answered, at construction for every
row the reconciliation moved out of flight, and **at the first read that observes an
hour running out while this process is up** — which is the case construction cannot
reach, because a halt whose process ended is settled by nobody and nothing wakes to
notice its deadline pass. `BenchRuns._recovered_row` is the one place all four of
those lookups go through, so the reconciliation and the deletion cannot come apart.

A time-based sweep was the alternative and it loses on `lease.py`'s argument, applied
one directory over:

> every rule for deciding that a lease has gone stale is a rule for deciding that a
> gate run which is merely slow has

A halt is promised an hour precisely because "a limit short enough to catch somebody
thinking would be a consent mechanism that answered on their behalf" (ADR-0028), and a
sweep short enough to reclaim an abandoned halt is short enough to delete one somebody
is still reading. The record already knows whether the run is over. Nothing here reads
a clock except the deadline the record itself carries.

`checkpoint_kept` is the observable side, and it is public because retention nothing
can ask about is retention nobody can check. It is deliberately not
`ApprovalRun.paused`: a completed run and a deleted one are both *not paused*, and
only one of them has stopped holding a person's name.

**What this does not prune is `/runs/` itself**, and it is stated rather than absorbed.
A row is small, it is what makes the deletion above possible, and a row deleted is a
run the bench can no longer say anything about — which is the defect this ADR exists
to fix. An operator who wants the directory gone deletes it, as they do `/decisions/`
(ADR-0032), and the difference is worth knowing: `/decisions/` holds re-measurable
facts about the bench's own equipment and this holds the only record that a run
happened at all. A retention policy for it needs a reader to have asked for one.

## Who owns the connection

ADR-0032 handed this ticket a decision procedure rather than an answer, and named run
records as a third shape:

> The reasoning to apply, in order — does the state have a lifetime longer than the
> call that writes it, and is there a second reader who is not the writer? If yes to
> both, ADR-0028's answer.

**Yes to both, and still ADR-0029's answer for the connection.** The two questions are
about the *state*, and they are answered exactly as ADR-0032 predicted: a run record
outlives the call that writes it — that is the whole ticket — and its second reader is
not its writer, since the worker thread writes where the API thread reads. But what
ADR-0028's answer was needed *for* is narrower than either question, and this store
does not need it.

ADR-0028's `ApprovalRun` owns its connection because **one operation spans the wait**.
The graph is invoked, it halts holding a checkpoint, an hour passes, and something else
resumes *the same graph object* through *the same saver*. The connection has to be
alive at both ends of a rendezvous, so no thread can own it and the object must.

Every operation here is a complete `get`, `put` or `search` inside one call. There is
no rendezvous in the store, because the rendezvous is `PendingApproval` and it is
somewhere else — and the fourth bullet of this ticket is that across a restart there
is *no second thread to wake at all*. That is the deciding fact: the run record's
second reader is separated from its writer by a **process boundary**, and a connection
per batch crosses that trivially while a connection per object cannot help with it in
principle, since the object that wrote the row is gone.

`BenchRuns` is also a process-lifetime object held on `app.state`. A connection on it
would be precisely the thing ADR-0028 rejected — "a module-level connection is a
global with a lifetime nobody closes" — and `RECORDED_RUNS` is a module-level object
in the shape `DECIDED_ROUTES` already is, safe for the same reason: it holds a path
and no connection.

Three things fall out, exactly as they did for the other two stores: the path is the
authority and the store object holds no state, so two store objects over one file
cannot disagree and `conftest.py` redirects the suite by patching one attribute;
`check_same_thread` stays at its strict default; and the cost is a connection and two
`SELECT`s per batch against traffic of a handful of operations per run.

**What is shared is `backend/bench/store.py`, and it had to be.** ADR-0029's two
functions, `_enable_wal` and `_migrated`, are justified by a measurement — without
them, six threads against one cold database failed 14 runs in 20. A third copy of a
fix like that is the copy that rots. So `RunDatabase` is eight lines saying where its
file goes, and ADR-0029 decision 6's *one database, one concern* keeps that file out of
`precedent/findings.sqlite` and `decisions/routes.sqlite`: precedent is adaptive-layer
memory two instruments are kept away from by an import test, the gate's decisions are
scored-side state about the bench's own equipment, and these rows are operational
state about this deployment's runs. Sharing one file would put all three behind one
path, one ignore rule and one set of migrations, and the first question a reviewer
would have to answer is whether the separations still hold.

## What is written back, and in what order

Two ordering defects turned up while wiring this, and both were found by breaking a
test on purpose rather than by reading.

**The row goes before the event.** `_execute` used to set `record.finished` and stop;
it now files the row and forgets the halt *first*. A declining request wakes on that
event and reads the record, so `finished` has to mean *the record is complete* rather
than *complete in this process's memory* — otherwise a restart landing between the two
finds a row still saying the run was going, for a run that had ended.

**A recorded run never goes back to being in flight.** One run has two durable
writers: the worker that finishes it, and the request that confirmed it. The request
writes `RUNNING` *after* releasing the graph, because the release has to happen inside
the guard that catches a second answer. A suite short enough to finish in between
would leave the row saying `running` for a run that had completed, and the
reconciliation would then report a finished run as one that stopped part-way.
`RecordedRuns.record` refuses the backward write — and does the check and the write
under one lock, because a `find` followed by a `put` is a read-modify-write and the
read alone would narrow the window rather than close it: the worker's terminal `put`
landing between them reproduces exactly the row the guard exists to prevent. The lock
is the right size for the hazard, which is two threads of one process reaching one
object; two processes never write one run id.

**A recovered halt takes one answer.** The live path gets this from
`PendingApproval.answer`, whose lock makes a confirmation landing in the instant the
wait closes either taken or refused and never both. A recovered halt has no
rendezvous — that is precisely what a restart destroys — so the answer path takes a
lock of its own across the read, the decision and the write. Without it, two requests
reading an answerable row at the same moment would both write and both be told their
answer was recorded: a decline and a confirmation recorded for one halt, which is
ADR-0028's distinction lost in a new way. Its own lock rather than the one guarding the
live records, which should not be held across a write to a file, and the test for it
chooses the interleave rather than racing for it.

**And a recovered row is read from the file every time, never cached.** ADR-0029
decision 2's principle — the file is the authority and the object holds no state —
bites here for a reason the other two stores do not have: ADR-0028 point 3 makes the
checkpoint database *shared*, so two deployments over one volume is a real shape, and a
cached row would be this bench's opinion of a halt the other one may have answered
since. The live records stay a dictionary, because those runs exist because this
process started them.

A third came from a re-cut: the deadline was compared with a clock in two places, and
only one was load-bearing. Breaking `answerable_at` changed nothing any caller could
observe, because the reconciliation had already settled the row by the time it was
asked. There is one comparison now, and `answerable_at` is it.

**`HaltRecovered` says two different things, because two different things happen.** A
halt inside its hour takes the answer, and the refusal says the answer went onto the
record instead of into the graph. A run that is already terminal — past its hour, or
answered once already — takes nothing, and a refusal telling an operator *your answer
was recorded* of a request that was discarded is the same class of false statement this
ADR exists to remove, one branch over. The same correction reached a third route:
`GET /report/{run_id}` was still answering `no_such_run` with "no run of that id was
started by this bench" for a run this bench had on record.

**A write at `start` is not caught and a write at the end is.** At `start` nothing has
been sent to the target, so a store that will not open is a deployment fault the
operator should meet *before* being asked to confirm a spend — the same place
`app.NAMED_BUT_UNUSABLE` puts an unbuildable instrument (ADR-0007). At the end the
suite has already run, so `_filed` catches everything, on `_published`'s argument: a
run marked failed over a storage fault would be reporting bookkeeping as a fact about
somebody's agent. What that costs is stated where it happens — a row that could not be
written stays as the last thing the bench said, so a restart may reconcile a finished
run as one that stopped part-way, which under-claims about a run that completed and
never over-claims about one that did not.

## Considered options

- **Serialise the whole `RunRecord` and resume the run.** The full prize, and the
  reading the ticket's own bullet list invites. Rejected on the four grounds in the
  serializer section, of which the credential is the one that makes it not a matter of
  effort: it needs a `TargetConfig` at rest, and that is a bearer token in a file.
- **Let the confirming request re-supply the target, and verify it against the stored
  `endpoint_hash`.** The strongest of the resumption options, and the one that needs no
  credential store at all: `POST /runs/{id}/approval` would carry a target block the
  way `POST /runs` does, the row's digest would prove it is the same endpoint, and the
  stored ceilings and library digest would answer the stale-declaration objections from
  fields this row already holds for other reasons. Rejected on what it does to the
  route rather than on what it cannot verify. This is the one route in the bench whose
  entire job is to *answer*, and ADR-0007's shape is that the answer is nothing but an
  answer — "a `confirmed: true` field on the start request would be a form, answered by
  whatever composed the request", and a target block on the answer is that sentence
  read backwards. It would also make the one route that cannot cause a call on an
  endpoint into a route that can point the bench at one, which is the property
  `list_the_runs_on_the_record` is careful to state about itself. And what it saves is
  a form: `POST /runs` already takes exactly that target block, presents a fresh
  estimate built from the library this process actually holds, and needs no digest
  comparison to be trusted. Two routes that both point the bench at an endpoint, so
  that one of them need not be called, is the wrong trade — but it is the option to
  revisit first if a reader ever asks for resumption, because it is the one that does
  not need a secret.
- **Store the target and encrypt the credential.** Considered, and it is the honest
  version of the option above. Rejected as out of proportion twice over: a key needs
  somewhere to live that is not beside the ciphertext, and ADR-0020 already establishes
  that this deployment's one secret arrives from the environment and is what makes a
  *report* portable. Adding a second secret, with a rotation story, so that a form does
  not have to be filled in again is the wrong ratio. It is the right answer the day a
  run is expected to survive a deploy *as a run*, which is a queue and P1.
- **Rebuild the run and refuse to resume unless the library digest and the ceiling
  match.** The guarded version, and the guards are real — the digest and both ceilings
  are in the row for other reasons. Rejected because it does not remove the credential
  problem, only the arithmetic one.
- **Keep the record in memory and only persist the thread id.** Cheapest thing that
  makes retention possible, and it fixes nothing a human meets: the route still cannot
  say what happened to the run, which is the defect the ticket was filed about.
- **A ninth `RunStatus`.** Rejected above, on what a status is for.
- **Reconcile lazily, when somebody asks about a run.** Cheaper at boot and it is what
  `answer` and `recovered` do anyway for one row. Rejected as the *only* mechanism,
  because the rows that most need reconciling are the ones nobody asks about: a
  `RUNNING` row left by a killed process refuses every `instrument` call, and nothing
  would ever ask about it by id.
- **A time-based sweep over `/checkpoints/`.** Rejected above, on `lease.py`'s
  argument.
- **Delete the whole checkpoint database when no run is answerable.** Simpler than
  deleting by thread. Rejected because it is only correct while one process owns the
  file, and ADR-0028 point 3 says the database is per process and *shared*: a second
  bench halting a run while the first swept would lose a live halt.
- **A table in `checkpoints/approvals.sqlite`, beside the halts it points at.**
  Tempting, since the two are deleted together. Rejected on ADR-0029 decision 6, and
  on a sharper local reason: the checkpoint database's schema is LangGraph's, and a
  table of ours in it would be a table a dependency's `setup()` walks past.
- **Return a `200` and a `RunResponse` for a recovered halt.** Kindest to a caller.
  Rejected because every field of that response — the estimate, the spend per layer,
  the case count, the families not run — would be a default, and a run described by
  defaults is the reconstruction this whole ADR refuses.

## Consequences

- `backend/api/recorded.py`, `RunRecord.thread_id`, `thread_id` parameters on
  `run_calibration` and `run_under_approval`, `forget_halt` and `checkpoint_kept` in
  `backend/graph/approval.py`, and `/runs/` in `.gitignore`. `uv.lock` does not move.
- **A machine that has run the bench now has a `/runs/` directory**, git-ignored, and
  nothing prunes it. That is the one growth this ticket adds and it is stated above
  rather than left to be found.
- **`/checkpoints/` stops growing without bound**, and the approver identity in a halt
  no longer outlives the run's answerability. ADR-0028's consequence about the
  directory is superseded by decision 8 rather than amended in place.
- **`GET /runs` does not list recovered runs.** It returns `records()`, which is run
  records, and a row is not one. An operator who did not keep the run id cannot find a
  recovered halt through the API — they can answer it, and `GET /runs/{id}` will name
  it, but there is no listing. This is a real gap and it is a route, not a decision:
  serving recovered rows needs a response type that is honest about having no figures,
  which is its own ticket.
- **PLAN §10 and README M2 move again**, and the claim is still partial. The halt is
  durable, the record around it is durable, and a run *itself* still does not survive a
  restart — it cannot be resumed, and its counters are gone. Two agents have now had to
  correct an overclaim in those two places against an ADR's own consequences; the
  wording says which half is which rather than saying *both*.
- **`_execute` takes a fourth argument**, the `RecordedRuns` the run files into, and
  `BenchRuns.__init__` takes it as an injectable default. That is what lets the suite
  hold both ends without patching a module.
- The suite gains a session-scoped and a per-test redirection of the run records, on
  the pattern the other two stores already needed, and for one reason of its own: a
  `BenchRuns` *reconciles* every row it finds, so a test reading the engineer's file
  would settle their halted runs.

Cross-references:
[ADR-0028](./0028-the-approval-checkpoint-outlives-the-process.md) (the halt this
completes, whose point 6 is what makes a recovered graph rebuildable, and whose
consequences filed this ticket),
[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
(the serializer argument, durability across a restart, and the single-tenant
namespace),
[ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md)
(one database one concern, and the connection answer this reaches),
[ADR-0032](./0032-the-admission-memory-holds-the-measurement.md) (the decision
procedure applied here, and the third shape it named),
[ADR-0007](./0007-canary-nonce-as-proof-of-control.md) (the halt, and nothing exceeding
what a human confirmed),
[ADR-0008](./0008-repo-disclosure-posture.md) (why the endpoint is a digest and the
credential is nowhere),
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the
discipline about not widening a signature to accept two kinds of thing).
