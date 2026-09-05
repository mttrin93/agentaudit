---
status: accepted
---

# A post-patch re-run is its own record, and a proven fix is a claim about one case

**#115, group K / #109.**

## Context

The bench writes a fix for every explained failure and then discards it
([ADR-0069](./0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)),
and even where it reaches a reader
([ADR-0070](./0070-a-signed-document-may-carry-a-remediation.md)) it is a *suggestion*:
nothing has tried it. Two things arrived that make trying it possible.
[ADR-0059](./0059-a-callback-target-is-served-over-the-contract.md) serves a user's own
function over the message contract on an ephemeral loopback port and tears it down, so
the bench can re-serve a target without a third party redeploying anything, and
[ADR-0071](./0071-a-finding-points-at-a-file-the-bench-read.md) established that in one
circumstance — the composite Action of
[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) — the
bench and the code are in the same place, with a file and a line it verified.

So the loop is available: change the file, re-serve the entrypoint, re-attempt the case,
see whether the verdict flips. **And it is the most dangerous thing this bench does.**
It writes to a filesystem it was handed rather than one it owns, and it executes what it
wrote. Every decision below exists because one of those two is true.

This ADR is #115's half of the decision epic #109 proposed jointly for #115 and #116.
**#116's half is deliberately not written here**: which label a fix carries on the two
surfaces, what the screen shows of a diff, and where either sits in the document are
decisions this ticket did not make and this ADR does not record. CLAUDE.md's rule is
that no ADR is edited to say something it did not decide, so #116 writes its own rather
than appending to this one. The epic's table of four ADRs is already stale — #114 landed
ADR-0071, a fifth — and this is the second place it is out by one.

## Decision

### 1. The patch goes into a throwaway copy, and there is no repository in it

`throwaway.throwaway_checkout(checkout, workspace=…)` copies the caller's checkout into
a run-scoped directory, hands back the copy, and removes it. **The original is never
opened for writing**, which is ADR-0071 §5's read-only invariant unrelaxed: that module
says whether there is a checkout to copy, and this one copies it.

The shape is
[ADR-0063](./0063-one-run-scoped-namespace-dropped-wholesale.md)'s, applied to a working
tree rather than to somebody's vector store, and it is copied deliberately. The
workspace name is **derived once** from the run id (`workspace_for`, `proof-<id>`, and a
run id that could not be a directory name is refused rather than sanitised), it reaches
every operation **as an argument**, and it is dropped **wholesale**. Deleting what this
bench remembers writing would need a manifest, the manifest is a second copy of the
truth, and its failure mode is a half-patched tree with nobody told.

**The copy contains no `.git`.** The constraint is *never committed*, and the mechanism
for it is not discipline: there is no repository in the copy to make a branch, a stash
or a commit in, and the caller's own object store is never within reach of the write.
The copy also contains no `__pycache__`, and that one is correctness — a stale `.pyc`
beside a patched source is a file the interpreter is entitled to load *instead of* the
patch, and a loop that re-ran the unpatched module and reported the case fixed would be
the worst answer this mechanism could give.

**Symlinks are copied as links rather than followed.** Following them would let a
checkout with a link to `/` be copied for as long as the disk lasted. Keeping them is
safe because containment is decided on the **resolved** path at the moment of writing,
which is ADR-0071 §5's rule applied to the write side.

**`Throwaway` refuses a root it would not have named.** The record `apply_patch` takes
is not a `Path`, so the only way to address a directory with the patch writer is to
build one of these, and a record whose root is not named the way `workspace_for` names
one — prefix and grammar, and named for its own workspace — raises at construction.
That is a *name*, and a name is exactly as strong as the claim *this directory is
called what this module calls its copies*: it is stated as such rather than overstated,
because what it stops is the accident — a caller reaching for `apply_patch` with the
record they happen to be holding — and it is deliberately the proof that survives being
pickled, passed and reconstructed, which a private token would not.

### 2. What a patch may be, and where it comes from

**A whole file, and never a diff.** A unified diff is applied by a program that resolves
its own paths and creates its own files, and a bench that shelled out to one would have
handed the decision about *where a write lands* to something outside the module whose
whole purpose is to hold that decision. A whole file is written by one `write_text` into
a path this module resolved itself. The diff a reader is shown is computed from the two
versions rather than being the instruction (#116).

**One file, and it is the file the anchor points at.** `Patch.for_anchor` is the
constructor with a story about where the path came from: an anchored `SourceAnchor` is a
file the bench opened inside that checkout and verified a line of. All five of ADR-0071
§3's absences are refused, because a patch to one of them is a write with no target. It
is also the only file the re-serve knows how to execute, so a patch to a second file
would be a write with no re-serve behind it.

**Refused, each with a named reason, before the write.** Absolute paths and `..`
segments; anything resolving outside the copy; a file that is not already there — **a
patch replaces and never creates**, because a file the caller did not hand over is not
part of what is being tested, and a mechanism that could add one could add a module the
re-serve would then import; anything that is not a regular file; and either side over
`MAX_PATCHED_FILE_BYTES` (4 MiB, ADR-0071's figure and its argument, applied to the
write). `PatchRefusal` is a closed set for the reason every closed set here is one.

**And no model writes it.** `Remediation.fix` is prose about what to change and it stays
prose. A `Patch` is a value its caller constructs, `proving.py` and `throwaway.py` import
no `judge`, `narration`, `remediation` or `adjudication`, and an import-level test holds
that. This is ADR-0071 §6's sentence honoured rather than quietly dropped — *the tempting
version of the patching ticket is the one that hands a model a file to look at, and it
would be one import*. A model that wrote code into a copy of somebody's repository and
then executed it would be a **fourth instrument**, and #64's precedent applies without
amendment: there is no gold set for *what to change in a stranger's code*, so the answer
is not κ, it is not doing it until there is a decision that says how. That decision is
not this one.

**The re-served revision never lands in the bench's own module table, and the copy is
never on `sys.path`.** The patched file
is executed under a name synthesised from the workspace and unregistered in a `finally`,
so nothing importing that file's real dotted name can find the patched revision. This is
a process holding the signing key and the operator's tokens. Everything the patched
module imports resolves the ordinary way, to the unpatched originals, so exactly one
revision of exactly one file is under test — the only claim the anchor licenses. Putting
the copy on the path instead would let a patched revision of *any* module in that tree be
found by anything importing it for the rest of this process, which is the same hazard the
synthesised name closes, arriving by the other door. The cost is stated rather than worked
around: an entrypoint whose module uses a **relative** import is one this loop cannot
execute, and a re-run it cannot execute is `NOT_RE_ATTEMPTED` — a named reading, and not a
claim about the fix.

**Why the four ways of failing to re-attempt are one reading, and where the fifth thing
goes.** A reader of a report can act on *this fix was not tested*; they cannot act on a
traceback from a build they did not run, and a document about somebody's code is not
where an exception from their runner travels (ADR-0008). So the exception goes to
`LOGGER`, on the machine that raised it — ADR-0059 §2's answer for a callback that raises
on the wire, one storey up — and so does a copy that survived its own drop, which is the
one path on which something of this bench's is still on the operator's disk.

### 3. The copy is dropped from one `finally`, over eight endings

Not a line at the end of the happy path: the runs that end badly are exactly the runs
that would leave a patched copy of somebody's repository on their runner. The list is
the decision, and each member is held by a test in
`backend/tests/test_throwaway_checkout.py`.

| How it ended | What still drops the copy |
|---|---|
| A clean finish | the `finally`, on the ordinary path |
| The patch was refused — `PatchRefused` | the `finally`; nothing was written and the copy goes anyway |
| The patched module would not load | the `finally`; the patch landed and the re-serve never reached a port |
| The re-serve never bound a port | the `finally` |
| The patched target outlived its retry policy — `TargetUnreachable` | the `finally` |
| A raise after the re-attempt landed | the `finally`; a verdict route that fell over with the reply in hand |
| A cancellation | `finally` and not `except Exception`: a `KeyboardInterrupt` passes straight through a clause written for the other seven |
| The copy itself failed partway | the directory is created before the copy is made, so a half-copied tree is still a tree to remove |

**The drop never raises.** It runs in a `finally` that is very often unwinding the
exception that is the run's actual answer, and a cleanup that raised there would cost the
operator the more important of the two (ADR-0063 §2). Both are kept: the original
propagates and the failure comes back as a string in the operating system's own words,
on `Throwaway.drop_error`.

**And `prove_patch` itself never raises for anything but a cancellation.** A run reaching
the proof loop has already spent the operator's inference budget and holds every figure
it will ever report; an exception escaping here would end that run over the one thing in
it that decides nothing — `source_anchor.anchor_for`'s argument, one field along. A
`BaseException` is not caught: a cancellation is the operator asking for the run to stop.

### 4. A post-patch attempt is not an `Attempt`, and the invariant is a type

A re-run is made against a **different target revision**. Counting it would put two
revisions under one name and one denominator, which is
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)'s error
committed a second time in a new place, and it would happen the way ADR-0010 describes:
the arithmetic stays valid, the population changes, and no test fails.

So `PostPatchAttempt` is its own record, and it is ADR-0010's shape applied a second
time rather than a rule written down somewhere.

- **It cannot be constructed from an `Attempt` and an `Attempt` cannot be constructed
  from it.** There is no converter, no `of`, and no widened signature.
- **It carries none of the four fields that make an attempt countable** — no `index`,
  because there is no *ten of these*; no `verdict_class`, because nothing groups it by
  how it was decided; no `transform`, because no breakdown is published over it; and
  **no `verdict`**, because a verdict is the scored quantity and a record holding one is
  a record something will eventually divide by. What it carries instead is
  `PostPatchOutcome`, a closed set of four answering a different question.
- **`RunState` gains no third list and the proof loop takes no `RunState`.** mypy runs
  with `warn_unused_ignores`, so `test_proving.py`'s `# type: ignore[arg-type]` on
  `RunState.record` is accepted *only because* the call is a type error: widen that
  signature and the type check goes red on that line before any assertion does, which is
  the order #115 asked for. `PatchProof` refuses an `Attempt` at runtime as well —
  `NotAPostPatchAttempt`, which is `judge.NotAScoredAttempt` pointing the other way, for
  a caller who silenced the type checker.
- **Its own counter.** `PatchProof.post_patch_calls` counts what the re-run put on the
  wire, retries included, and it is not in `RunState.spent`. A third `Layer` member would
  put this spend inside a ceiling declared for the scored suite and make it addable to
  the other two, which is the blending
  [ADR-0007](./0007-canary-nonce-as-proof-of-control.md) exists to prevent. **The ceiling
  is the construction rather than a declared number**: `prove_patch` re-attempts one case
  exactly once, so the most it can spend is one attempt's worth of sends.
- **A judged case is not re-decided.** An adjudicator's agreement is measured over the
  scored layer against a gold set of that layer's transcripts
  ([ADR-0013](./0013-adjudication-is-a-third-instrument.md)), and a proof is not the place
  to spend a reading nothing has validated. It is a named outcome rather than a silent
  skip, because a reader of a judged family's finding has to be able to tell *not proven*
  from *not tried*.
- **The success condition and nothing else decides the re-run**, which is the same
  deterministic reading the scored attempt got, so that *flipped* means what it meant the
  first time (ADR-0004).

### 5. A flipped case is not a fixed family

`n = 30` per family ([ADR-0003](./0003-gate-decision-rule-and-sample-size.md)). A patch
that defeats `indirect-injection-001`'s exact payload while leaving the family open is
overfitting to the test, and it is the failure mode a proof loop *invites*. **The only
claim this mechanism makes is per-case**, and it is made in three places at once:

- **In the type.** `PatchProof` holds one patch and one re-attempt. There is no list to
  count, no `successes`, no `n`, and no arithmetic over which a proof rate could be
  computed.
- **In the prose.** `PostPatchAttempt.stated()` is the sentence both surfaces print, and
  the flipped one says the claim is about this one case and *deliberately not about its
  family* — that a family is measured over thirty attempts against every live case in it,
  and that re-running one is the operator's to ask for. That cost is theirs to choose
  because it is their money.
- **In the import graph.** Nothing that computes a figure or writes one into an artefact
  reaches `proving` or `throwaway`: `scorer.py`, `assembler.py`, `gate.py`, `bar.py`,
  `calibration.py`, `runstate.py` and the serialisers are walked transitively by
  `test_proving.py`.

### 6. The reference agents are a fixture and nothing else

Epic #109 says it and this records it: **there is no fix-testing against the reference
agents as a feature.** They are the only target in CI whose source can be patched, so
this loop can be driven red against something that is not a mock of itself, and
`controls.InputCheck` is what the suite's fixture checkout is patched to hold. Nothing
about a reference agent's patched re-run is printed, reported or signed.

## Consequences

- **Two new modules and no new call site.** `throwaway.py` writes to a filesystem;
  `proving.py` holds the records and the loop. `prove_patch` has no caller in
  `scripts/bench.py` yet, and that is the honest state: §2 says a patch is the operator's
  own code rather than a model's, so the surface that supplies one and the surface that
  reports the result are both #116's. Landing the mechanism first is what makes the
  invariants cheap — ADR-0010's retrofit cost is the argument, and it applies to the
  ticket order as well as to the type.
- **Nothing writes into a rate, and there is no field one could arrive in.** A
  post-patch attempt has no verdict, `PatchProof` has no denominator, and the walls above
  are import-level (D13, [ADR-0006](./0006-overrides-never-change-a-measured-rate.md)).
- **No route for the adaptive layer.** An `AdaptiveEpisode` has no `Finding`, so it has
  no anchor and no patch, and no signature widened to accept both (ADR-0010).
- **No severity and no composite.** An outcome is not a rank, nothing orders proofs, and
  nothing counts how many cases were flipped (D3, D12).
- **Nothing is published yet**, so no payload key, no rendering, no screen field, and
  `ARTEFACT_VERSION` does not move. #116 adds the surface and pays for what it adds.

## No reading moved

No rate, interval, band, `D`, κ or admission reading is touched, and **no tripwire
moves**: `GOLDEN_ONE_FAMILY` stays `3ae88fadb9c1…` because no document gained a
character, and the library digest stays `c515a89956cd`, eighteen records — no case record
is edited here and no variant is admitted, which needs a person at a tty (ADR-0052 §5).

## Alternatives

**Patch the checkout in place and revert afterwards.** Rejected under decision 1. It is
the delete-what-we-wrote design ADR-0063 already rejected at a different scale, and its
failure mode is worse here: a revert that failed leaves somebody's working tree modified,
and a run that was cancelled mid-patch leaves it modified with nobody told.

**Apply a unified diff with `patch(1)` or a library.** Rejected under decision 2. The
program resolves its own paths and creates its own files, which moves the decision about
where a write lands outside the one module that exists to hold it.

**Let the remediation instrument write the patch.** Rejected under decision 2, and it is
the tempting version of this ticket. It would be a fourth instrument making unverifiable
claims about somebody else's code, upstream of a write and an execution rather than of a
sentence, and #64's precedent about unvalidated instruments applies without amendment.
The refusal is an import wall rather than a review, for ADR-0071 §6's reason.

**Give `PostPatchAttempt` a `Verdict` and keep it in a separate list.** Rejected under
decision 4. It is one field away from being groupable with attempts, and the list it sits
in is not what a future consumer will look at — the record's shape is.

**Run the whole family after a patch and report a post-patch rate.** Rejected under
decision 5. It is thirty attempts of the operator's money per family, it needs a ceiling
and a consent figure of its own, and it is the claim an operator should be choosing to
buy rather than one a report loop spends on their behalf.

**A third `Layer` member for the proof loop's spend.** Rejected under decision 4. A
`Layer` is a counter the budget enforces and the consent surface prints; a third one
would make this spend addable to the other two and would put it inside a ceiling declared
for something else.

**Re-serve the patched target in a child process.** Considered and not taken. The bench
already imports and executes the caller's callback in this interpreter (ADR-0059), and a
patch does not widen that exposure *given decision 2* — what runs is still the operator's
own code. A subprocess would be the right answer the day a model writes the patch, and
that is the same decision as writing it.
