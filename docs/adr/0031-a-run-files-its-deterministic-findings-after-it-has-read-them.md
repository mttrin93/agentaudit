---
status: accepted
amended_by: 0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md
---

# A run files its deterministic findings, and it files them after it has read them

> **Amended by [ADR-0069](./0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md) on
> the unit filed, and on nothing else.** `file_precedent` takes `Narration`s rather
> than `Finding`s, and `Precedent.of` takes the fix as an argument, because a
> precedent is a failure *and* its fix and since that decision no single
> instrument writes both. *When* a run files, *what* it withholds, and the
> one-per-case unit are unchanged.

[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
built a store that outlives the process and said what the store is for: "precedent's
only value is cumulative… the store earns its place at run two and every run after."
[ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md)
made it a database. [ADR-0030](./0030-the-judge-runs-over-the-scored-layers-successes.md)
gave a run findings to file.

Nothing filed them. `DurablePrecedents.record` had callers in `backend/tests/` and
nowhere else, and `scripts/seed_precedent.py` said the consequence in its own
docstring: "that chain has no caller yet, so on every run to date the tool has
answered *nothing has been filed against this family yet*." A store nothing writes to
never reaches run one, so "earns its place at run two" was a claim about a run the
bench had never made. The only entries the store ever held were an operator's typed
sentences, which that script is careful to label as not findings.

**Decision.** A run files the deterministic findings it produced, and five things
about that write are decided rather than left to a call site.

1. **The write is `run_calibration`'s, and it happens once.** `backend/bench/filing.py`
   holds it — `file_precedent(findings, store)` — and `run_calibration` is the only
   caller. There is no per-target write and no write anywhere else in the bench.

2. **The run holds the concrete store; `PrecedentStore` stays read-only.**
   `run_calibration`'s `precedent` parameter is annotated `DurablePrecedents`, so mypy
   strict refuses `RecordedPrecedents` in the one function that writes — the same
   enforcement `DurablePrecedents.store`'s narrow annotation already provides one level
   down, and what ADR-0019 point 2 asks for. `_run_target`, `narrate` and
   `run_adaptive_layer` keep the protocol, which promises no `record` at all, so **the
   narrative pass structurally cannot write the store it is about to read**. Widening
   `PrecedentStore` to carry a write was refused in that protocol's own docstring and is
   refused again here: it would make every read-only stand-in refuse half of what it
   claimed to be, and it would let a test double into a production seam.

3. **Deterministic findings are selected; the refusal is not caught.** `Precedent.of`
   raises `JudgedPrecedent` for a judged verdict on
   [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md)'s terms — such a
   verdict carries a reliability figure and a wider stated limit, and remediation
   informed by one would inherit neither. `file_precedent` reads
   `Finding.verdict_class`, which is copied off the attempt and is never inferred from
   a family name, and reports what it did not file on `Filing.judged`. A `try/except`
   around the write would be a silent partial write, which is the exact failure that
   named exception exists to prevent.

4. **One precedent per case per target, and `Precedent.key` is not extended.** A case
   is attempted ten times (#4), so a target that fails one carries up to ten findings
   of it — ten samples of one failure mode, differing in what the target replied and in
   how the judge paraphrased it. The key is a digest of the record, so it folds the ones
   that came back word for word identical and structurally cannot fold the rest.
   `filing._one_per_case` keeps the first finding of each `(target_name, case_id)`.

5. **The write is last: after every target's narration and after the adaptive layer.**
   Nothing in a run reads what that run filed.

## Why the placement is the decision and not the write

Narration runs per target, and the store is read twice in a run: by
`suggest_remediation` for each finding, and by `retrieve_precedent` for each adaptive
episode. So a naive write path has three observable consequences and all three are bad.

**Target order would decide the corpus.** Filing as each target finishes puts target
*n*'s findings in front of target *n+1*'s remediation. The advice one target gets then
depends on which target ran first — and target order is randomised per family, which
[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) requires for the blinding's
sake. A record whose content depends on a randomisation nobody records is worse than one
written from a smaller corpus.

**A run would hint to itself.** The adaptive layer runs last and
`retrieve_precedent` is one of the attacker's five tools. A run that filed before that
layer would hand its own attacker its own scored findings, and `scripts/seed_precedent.py`
already names what that costs: "`A_break` measured on a run that read seeded precedent is
a reading about the attacker *plus the hint*, which is not the same instrument as the
attacker alone." A run that hints to itself produces a diagnostic that cannot be compared
with any other run's, and it does so without the operator having chosen to seed anything.

**And it would make ADR-0019 wrong in the other direction.** That ADR states plainly
that "the value of the store cannot be demonstrated inside one run, so any showcase of
remediation quality needs two runs against the same target." A within-run write would let
a demo appear to satisfy the long-term-memory claim while measuring nothing across a
process boundary — the same category of error ADR-0019 exists to prevent, arrived at from
the other end.

So the write goes after everything that reads. What one run's instruments saw is the
store as it stood when the run began, and the store's value shows up where ADR-0019 says
it does: at run two.

## What this does not change, and what proves it

**No rate, interval, band, `D` or gate decision can feel this.** The flow is one
direction: `Attempt` → `Finding` → `Precedent` → the store, and back out only to
`suggest_remediation` and `retrieve_precedent`, both of which produce prose.
`TargetRun.rates` divides over `attempts`, which `filing.py` neither reads nor writes.
Going the other way, the only door into the store takes a `Finding`, and a `Finding` is
built by `Finding.of(attempt, narrative)` — so **an `AdaptiveEpisode` cannot become a
precedent**, which is
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)'s
invariant carried by the same type that carries it everywhere else. The demonstration is
`test_filing.py::test_a_run_that_reads_a_stocked_store_measures_what_an_empty_one_measured`:
two runs against one store, the second reading what the first filed, measuring the same
rate over the same denominator.

The one edge from the adaptive layer to the scored side is still `propose_case` into the
admission gate, decided by a declared threshold. Precedent now carries scored findings
into the attacker's reading, which reaches that gate the way anything the attacker
produces reaches it — as a proposal an arbiter decides. That was already true of seeded
precedent; the arbiter is unchanged, and it is a declared number rather than the model's
own confidence.

## Consequences

- **A gate run files nothing**, because a gate run passes no narrator and therefore has
  no findings (ADR-0030). `CalibrationResult.filing` on such a run is two empty tuples,
  and *why* it produced no finding is answered on `TargetRun.narrations` rather than
  restated on the filing. This also means the git-ignored, machine-local store cannot
  grow from a run whose purpose is to measure the bench
  ([ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)).
- **A gate run files nothing, but it now *reads* something, and that is a cost.**
  Neither `scripts/gate.py` nor `api/gate_runs.py` hands the adaptive layer a store, so
  both read `DURABLE_PRECEDENT` — which until now could only hold sentences an operator
  typed. So a gate run's `A_break` can be measured over a corpus nobody chose to put
  there. Nothing the gate *decides* moves: ADR-0010 keeps the adaptive layer out of every
  rate, interval, band and `D`, and `DURABLE_PRECEDENT`'s own docstring is where that is
  argued. What it costs is the **comparability of the diagnostic** — `A_break` over a
  filled store is a reading about the attacker plus that corpus, and two figures are
  comparable only over the same one. The episode record already carries
  `consulted_precedent`, so a run that read the store says so;
  `docs/validation.md` now states that its readings were taken over an empty store, and
  `seed_precedent.py --list` and `--clear` are how an operator sees and resets what is
  there. Making the gate read an empty store instead was available and is **not** taken:
  it would be a second store path chosen by entry point, and the layer separation is what
  is supposed to make the ignored file harmless rather than a rule about who passes what.

- **A run that did not finish files nothing.** The write is the last statement of
  `run_suite`, the body `run_under_approval` will not enter without a yes — so a run
  nobody confirmed files nothing, and a run that stopped on a transport failure or on
  `JudgeFailed` files nothing either. Consistent with *a partial suite is void rather
  than smaller* ([ADR-0007](./0007-canary-nonce-as-proof-of-control.md)): the findings
  of a run with no artefact are not evidence the next run should be advised from.
- **`Remediation.informed_by` is empty on run one and that is the honest answer.** It
  was empty before because nothing had ever been filed; it is empty now because the run
  had nothing to read yet. The two are the same sentence and only one of them is a defect.
- **Accumulation stops being hypothetical, so ADR-0011's redaction becomes
  load-bearing.** ADR-0019 said it: with one run's findings, identity stripping is a
  formality; with many, precedent becomes a corpus in which a failure pattern identifies
  a target. Nothing new is asked of the code — the record has no target field and the
  prose comes from a blinded instrument — but this is the ADR at which that chain starts
  carrying weight.
- **Two runs file at once, and that is already answered.** Every run is its own OS
  thread (`api/runs.py`) and the write lands at the end of each, so two runs finishing
  together are two writers against one database — the hazard ADR-0029 measured and closed
  with `_migrated` and `_enable_wal`. Nothing here adds a lock.
- **`scripts/seed_precedent.py`'s docstring described the absence and now describes the
  code.** Its seeds remain useful for the diagnostic that script exists for, and a
  reader can still tell a typed sentence from a recorded one by its `case_id`.
- **The two terminal entry points print what was filed and what was withheld**
  (`console.precedent_section`), and the API's status sentence carries the count. A
  refusal nobody is handed is a refusal nobody reads.

## Considered and rejected

**Widen `PrecedentStore` with a `record`.** Rejected in that protocol's own docstring
before this ticket existed, and the reason holds: every read-only stand-in would then
refuse half of what its type claimed, and `RecordedPrecedents` would be admissible where
ADR-0019 point 2 forbids it. Holding the concrete type in the one function that writes
costs one annotation and buys the same guarantee from mypy.

**Catch `JudgedPrecedent` around the write.** Rejected on the exception's own reason for
existing. A caught refusal is a silent partial write: the caller believes the finding was
recorded and the store's contents come to depend on which findings were offered rather
than on which were accepted.

**File inside `narrate`, beside the remediation that reads.** Rejected because it is the
placement this ADR spends its middle section refusing, and because `narrate` holds the
read-only protocol on ADR-0004's terms — `suggest_remediation` is the one instrument
allowed a store handle, and giving that seam a write handle would widen the one asymmetry
ADR-0004 is built on.

**File after each target but before the adaptive layer.** The cheapest way to get
cross-run accumulation, and it keeps the remediation ordering problem while adding the
self-hinting one. Rejected on both.

**Put an attempt index on `Finding` so two findings of one case are distinguishable.**
Considered because the collapse is real: `Finding` carries no index, so two findings of
one case whose prose came back identical are one `Precedent.key`. Rejected, because the
collapse is the feature. The store's unit is a failure mode and the case is its identity —
ten attempts of one case against one target are ten samples of one mode, and the store's
retrieval contract is twenty entries, most recent first, with no relevance ranking anyone
could re-derive. Ten paraphrases of one failure would crowd out five other families and
would make the corpus's composition a function of the judge's paraphrase variance. An
index would also weaken the idempotence the ticket asks to keep: `Precedent.key` is what
makes a re-run add nothing, and a key with a per-run coordinate in it is a key that
multiplies one finding into a corpus of copies.

**File every deterministic finding and let the key sort it out.** The literal reading of
the definition of done, and it is what `_one_per_case` was written against. Rejected on
the paragraph above: the key folds only exact duplicates, so what it sorts out is the
case the judge happened to describe twice in the same words.

**File from the report assembler, or from the API layer after the run returns.**
Rejected for the reason ADR-0030 rejected narrating there. The assembler runs after the
run and would put the write behind the artefact rather than inside the run, and an API
layer that filed would mean a run started from a script filed nothing — one behaviour with
two answers depending on which entry point was used.

Cross-references:
[ADR-0019](./0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md)
(what the store is for, and that its value is cumulative),
[ADR-0029](./0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md)
(the backend, and the concurrency this write lands on),
[ADR-0030](./0030-the-judge-runs-over-the-scored-layers-successes.md) (where the findings
come from), [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (deterministic
findings only, and the one instrument allowed a store handle),
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (why no
adaptive result can become a precedent),
[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (the corpus this write starts
accumulating).
