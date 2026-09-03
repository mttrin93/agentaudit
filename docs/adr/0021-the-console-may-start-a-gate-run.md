---
status: accepted
amended_by: 0023-a-gate-run-updates-the-citation-it-earned.md
---

# The console may start a gate run, and the command line stops being the only door

> **Amended by [ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md).** Two
> of the costs recorded below were reversed rather than paid: a completed gate run
> *does* now update the citation the bench carries, and both entry points leave a
> machine-readable record. The six conditions of this decision, and every other cost
> on the list, stand. The two paragraphs affected are marked where they appear —
> nothing here is deleted, because what this file claimed was true when it was written
> and is why ADR-0023 exists.

`PLAN.md` §8 put a gate run on the command line and said, in a subordinate clause,
*not through the API*. Issue #75 restated it as an implementation decision — "the
gate is cited, never started" — and #80 built the screen that honours it: the rule,
the last outcome, the write-back, and the command to copy. Its acceptance criteria
included *no button anywhere that starts a gate run*, and its tests assert the
absence over the route table and over the component's own source.

This ADR reverses that. It is a decision of record changed rather than a feature
added, and the reversal is the interesting part: the clause was not an oversight.

**What the command line bought.** Three things, and each of them was load-bearing.

*Consent that cannot be faked.* `scripts/console.attest` asks the three attestation
statements one at a time at a terminal and treats absent or piped input as a
refusal. That single property is what makes "no gate run can be spawned" true by
mechanism rather than by policy: anything that started one unattended — a cron
entry, a CI step, a subprocess from a route — answers *no* three times and spends
nothing. There is no `--yes`, and ADR-0007 is the reason.

*A write-back with an obvious home.* A gate run appends a discrimination reading to
every case record it reads and marks retired what the rule retires. On a laptop or a
build agent the library is the checkout: the writes land in `backend/cases`, they
show up in `git status`, and they are reviewed and committed by the person who ran
the gate. Where the records live is not a question anybody had to answer.

*One writer, by construction.* One person at one terminal cannot start two gate runs
over one library by accident. Overlap was not prevented; it was merely unavailable.

**What made the clause worth revisiting.** The deployment is a live URL with a
console in front of it, and the operator of a deployed bench has no terminal on it.
Every other operator action reached that console during this batch; the gate is the
one that answers *is this instrument trusted*, and leaving it out meant a deployed
bench could be read but never re-validated by the person responsible for it. The
console's own copy said so plainly — it printed a command nobody on that deployment
could run.

**Decision.** A gate run may be started from the console, under six conditions that
are the whole of this decision.

1. **The consent mechanism is reused, never duplicated and never bypassed.** The
   browser collects the three statements one at a time and posts them as the same
   `Attestation` record `registration.py` refuses to construct incomplete; the halt
   in front of the estimate is the same `PendingApproval` seam `POST /runs` answers,
   the same `Approve` type the graph takes, and the same `ApprovalRequest` body.
   **There is no flag, environment variable or configuration setting that lets a
   gate run proceed without a recorded attestation.** That is what ADR-0007 forbids,
   and it is also why the fix is not to spawn `scripts/gate.py` from a route: the
   terminal helper would read the absent input as a refusal, correctly, and the
   temptation would then be to add the flag.

2. **A gate run is its own record and its own route family, and no type, route or
   function accepts both it and a run.** `GateRunRecord` is not `RunRecord`,
   `GateRunStatus` is not `RunStatus` — a run *completes* and has a report; a gate
   run is *decided* and has an outcome — and the four routes are under `/gate-runs`
   rather than under `/runs`. This is ADR-0010's discipline on a new axis and
   ADR-0018's on the same one: a run produces rates about somebody's target, a gate
   run produces a decision about this bench, and there is no arithmetic that turns
   either into the other. A test asserts that no function in the API package names
   both records.

3. **The estimate is presented per layer against that layer's own ceiling, never
   blended.** `ScoredEstimate` counts attempts over cases over agents;
   `AdaptiveEstimate` counts turns over episodes over families over agents; they
   share no numeric field, so a total has nowhere to live. This is the same shape as
   the two layer ceilings on the settings route and the same shape as the run
   screen's interrupt.

4. **The case library a gate run writes to is a declared directory outside the
   image, and a bench without one runs no gate.** A deployment mounts a volume at
   `/var/lib/agentaudit/cases`; the image's own admitted library seeds it once, on
   first boot, if it is empty and never afterwards. The bench reads its library from
   the mount, so a case a gate run retired comes back retired after a redeploy. A
   bench with nothing mounted states that it cannot run a gate rather than writing
   into a filesystem the next release replaces — a decay series that does not
   survive the deployment that produced it is worse than no series, because it looks
   exactly like one.

5. **One writer at a time on one library, refused rather than queued.** A gate run
   takes an exclusive lease — a file in the library's own directory — before it reads
   anything, and gives it back however the run ends. It is a file rather than a lock
   in one process because `scripts/gate.py` writes to the same records: the two
   entry points have to exclude each other and not only themselves. A second gate run
   is refused by name with the holder printed. Nothing waits: 830 calls behind an
   hour of blocking is not a request anybody meant to make. Nothing expires a lease
   either — a timeout short enough to catch a killed run is short enough to unlock a
   library a live one is still writing to — so a lease left behind names its holder
   and is cleared by hand.

6. **The reference agents may be absent, and then the console says so and offers no
   control.** They are test equipment served by a different application and never
   reach a user, so a build that omits them is a legitimate deployment which cannot
   run a gate: there is no contrast to decide one over. The equipment is a seam that
   can be missing rather than an import that fails.

Beside those, one thing the reversal makes possible that the read-only screen could
not have: **the per-family figures come from the completed gate run.** #75 dropped
the three reference agents' rates and each family's `D` from the console rather than
parse them out of the dated Markdown a gate run leaves, and that was right. A gate
run started here has the `GateResult` in memory, so the figures are served from the
process that measured them and no route reads a document.

## What this gives up

**The command line's refusal was a mechanism and what replaces it is a
promise.** At a terminal, a gate run nobody was watching answered no by
construction — the helper could not read consent that was not typed. Over HTTP the
same guarantee rests on a route that will not construct an incomplete
`Attestation` and on a halt that returns no `run_id` a caller can confirm without
having been shown the figures, and both of those are code somebody can change in
one commit. The property has moved from *unavailable* to *enforced*, and enforced
is weaker.

Everything else this spends is smaller and none of it is nothing:

- **The write-back leaves the review path.** A gate run at a terminal put its
  readings in a working tree, where a person read the diff before committing it. A
  gate run from the console writes to a volume nobody reviews. The series is still
  the evidence a retirement is re-derived from and it is still on the case's own
  record, but the human check between measuring and recording is gone.
- **Overlap became possible, and is now prevented by a lease rather than by
  arithmetic.** A mechanism that can refuse can also be got around — by deleting a
  lease file, or by a run killed in a way that leaves one behind and an operator who
  clears it while another process is still writing.
- **A deployed bench can now spend 830 calls from a browser tab.** The estimate, the
  attestation and the halt are the whole of what stands between a curious operator
  and that spend, and this application still has no authentication: until the
  deployment ticket solves that, a public URL would let a stranger start it. The
  console build never depended on that being solved; the deployment does, and one
  more expensive button makes it more urgent rather than less.
- **A console gate run leaves no dated document.** The command-line path writes one
  and a reader compares one gate run with another through it. A console gate run
  returns its figures and holds them in memory, so a bench restarted afterwards has
  the case records but not the run. #84's machine-readable record is where that
  belongs, and until it exists the two paths leave different traces.
- **The bench does not start citing the gate run it just made.** The citation on
  `GET /bench/gate` is what the deployment declared, and it stays that. Whether a
  completed gate run should update it is a question this ADR deliberately does not
  answer — it is the same open question as `deployed_bench()` declaring no citation
  at all, and it belongs to whoever owns that.
- **The library a running process holds is the one it booted with.** A gate run's
  write-back is visible to the next process, not to this one. A retirement therefore
  takes effect at the next restart, which is honest but is not what a reader of the
  settings screen would assume.

## Considered options

- **Leave it on the command line, and give the deployed bench a shell.** The status
  quo, and it is not absurd: `terraform`-deployed infrastructure can be reached with
  a session and the command run there. Rejected because it makes the answer to *is
  this instrument still trusted* available only to whoever holds infrastructure
  credentials, which is a different person from the operator the console is for, and
  because a step that requires a shell is a step that does not happen.
- **Spawn `scripts/gate.py` as a subprocess from a route.** The obvious
  implementation and the one this ADR exists to refuse. The terminal helper reads
  absent or piped input as a refusal, so the spawned run answers no to all three
  statements and spends nothing — which means the change that would make it *work*
  is a flag that lets a gate run proceed without an attestation. That flag is the
  thing ADR-0007 forbids, it would be reachable by anything that can reach the
  binary, and it would be added in the commit that made the feature function rather
  than in the commit that decided to weaken the control.
- **Queue gate runs instead of refusing the second.** A queue would hold the second
  request open across the first run's many minutes, or invent a job record with a
  status of its own — a second progress surface, for the one operation that already
  reports progress per layer. Refusal by name is the answer an operator can act on,
  and PLAN §8 licensed background tasks rather than a queue for exactly this reason.
- **Write the library back to the image's own `backend/cases`.** What a laptop does,
  and it would have worked in every test. On a deployed bench the writes are inside
  the container: the next release replaces them, a retired case comes back live, and
  nothing in the library records that it ever went. Rejected under the same
  reasoning as ADR-0020 — do not produce something that looks like the real thing
  when a prerequisite for the real thing is absent.
- **Take the library location from an environment variable.** Flexible, and it
  would make no module of `backend/api/` an environment reader by accident, which
  ADR-0020 pins to one line. It also makes the durable location changeable by a
  deploy-time variable nobody reviews, and a library that moved silently is a decay
  series split in two. A mount point is the one place a deployment already has to
  say something about storage.
- **Hold the lease in process memory.** Simpler, and enough for two browser tabs. It
  is invisible to `scripts/gate.py`, which writes to the same records, so the one
  overlap that the reversal actually introduces — a console run and a terminal run
  on one library — would be exactly the one it could not see.
- **Let the gate run update the bench's cited gate on completion.** Tempting, and
  out of scope: the citation is carried into the provenance block of every signed
  report, so a bench that started citing a run it made of itself would be changing
  what its artefacts claim. It is a decision with its own ADR, and this one does not
  leave the door ajar. *(That ADR is
  [ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md). It agrees with the
  objection and decides that a citation nobody re-checks is the worse of the two
  claims — and it is the record #84 built that made the alternative available at all.)*

## Consequences

- **`PLAN.md` §8's sentence changed**, and it now says where a gate run runs from
  rather than where it does not. The claim it made was true when it was written and
  is why this file exists.
- **#80's four assertions were turned around rather than deleted.** Two in
  `test_api_gate.py` — which route may start a gate run, and that `/bench` is still
  read-only in every method — and two in `frontend/src/console/gate.test.ts`, which
  now pin the *one* control the screen adds and refuse a second one. An absence that
  became a presence is worth more as a pinned presence than as a deleted test.

  *Corrected by #57*: read the second of those two as *what `/bench` does in every
  method*. Read-only in every method stopped being true at
  [ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md), and it was already
  untrue of `PUT /bench/settings/families`, which predates both records. The
  assertion is now `test_only_the_two_settings_routes_write_under_the_bench_prefix`
  and it names every pair on the prefix, so it is not weakened — and the claim this
  record owns, that **no gate run moved under `/bench`**, is unaffected either way.
- **A bench that declared its own configuration runs no gate unless it says so.**
  `create_app` takes the gate-run bench as a second argument, so the operation that
  spends 830 calls and rewrites the library is not something a deployment acquires by
  omission — and every bench in the test suite is unchanged.
- **Four refusals, each by name**: no reference agents, no writable library, no
  adjudicating instrument, already in flight. Two are facts about how the deployment
  was built and two are about this moment, and a console that could not tell them
  apart would offer *try again later* to somebody whose build ships no equipment.
- **A gate run with no adjudicator is refused before it spends.** Without one the two
  judged families are not fit to report and are excluded, which leaves four fit
  families and a gate that cannot be decided (ADR-0015) — 830 calls to reach an
  answer that was arithmetic before the first one was sent. Same discipline as *no
  adjudicator, no judged family*, one level up.
- **The terminal path is unchanged except that it now takes the lease.** Same
  command, same three statements, same document, same exit codes; it refuses to start
  where a console gate run is holding the library, and says who holds it.
- **CONTEXT.md's `gate run` entry covers both paths.** It was written for one and
  would have been wrong for the other: what a gate run leaves behind is a dated
  document from the command line and a gate run record on the bench that ran it.

Cross-references: [ADR-0007](./0007-canary-nonce-as-proof-of-control.md) (the
attestation, the estimate as a consent mechanism, and the prohibition this decision
is bounded by), [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)
(two layers never blended, and the type-level discipline this applies to a new
axis), [ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)
(why a gate run and a run are two records with no field between them),
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the declared rule, served
above the decision so the outcome is re-derivable),
[ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) and
[ADR-0016](./0016-retirement-declines-on-a-family-unfit-to-report.md) (what the gate
is decided over, and what the write-back may and may not retire),
[ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md) (the deployment
boundary, the one environment reader, and *do not produce something that looks like
the real thing*), [ADR-0008](./0008-repo-disclosure-posture.md) (why no payload text
reaches a response or a document).
