---
status: accepted
amends: 0021-the-console-may-start-a-gate-run.md
---

# A gate run updates the citation it earned, and the record is what that citation points at

[ADR-0021](./0021-the-console-may-start-a-gate-run.md) reversed `PLAN.md` §8 and let
the console start a gate run. In its own *What this gives up* it recorded two things
it would not do, and it recorded them as shut rather than ajar:

> **The bench does not start citing the gate run it just made.** The citation on
> `GET /bench/gate` is what the deployment declared, and it stays that. Whether a
> completed gate run should update it is a question this ADR deliberately does not
> answer — it is the same open question as `deployed_bench()` declaring no citation at
> all, and it belongs to whoever owns that.

and, in its considered options:

> **Let the gate run update the bench's cited gate on completion.** Tempting, and out
> of scope: the citation is carried into the provenance block of every signed report,
> so a bench that started citing a run it made of itself would be changing what its
> artefacts claim. It is a decision with its own ADR, and this one does not leave the
> door ajar.

This is that ADR. It amends ADR-0021 on those two points and on nothing else: every
one of ADR-0021's six conditions stands, its cost list stands, and the reversal here
is bounded by them rather than a loosening of them. **Two questions are now answered.**

1. **The gate run record is the machine-readable form of the citation.** The
   `RecordedGateRun` that #84 writes beside the dated document stops being a sidecar
   nothing points at, and becomes what a **gate citation** names. A reader holding a
   report's provenance block reaches each reference agent's rate and each family's
   `D` without parsing prose.
2. **A gate run updates `ReportConfig.gate`.** The bench cites the gate run it made
   rather than one wired in by hand — on both entry points — and `deployed_bench()`
   reads that citation off the library it booted with, or states the absence.

## Why ADR-0021 left them shut, and why they are open now

**The first was shut because the only available answer was a parser.** #75 dropped
the three reference agents' rates and each family's `D` from the console rather than
recover them out of the dated Markdown, and that was right: a figure parsed out of a
document written for a person breaks on a rewording, and the rewrite that broke it
would be a screen quietly reporting a wrong `D` rather than a screen that failed.
ADR-0021 could not point the citation at anything, because the only other rendering
of a gate run was prose. #84 built the second rendering. So the question is open for a
reason that has nothing to do with taste: **the thing to point at now exists.**

**The second was shut because of what the citation is carried inside.** ADR-0021's
words are worth quoting exactly — *"a bench that started citing a run it made of
itself would be changing what its artefacts claim"* — because that is still true and
this decision does not deny it. What has changed is which of two claims is worse. The
citation the deployment declared is a claim nobody re-checks: it names a document, a
date and a library digest, and nothing in the system compares any of them with the
library the bench is actually running. A deployment that added a case, ran a gate and
redeployed goes on citing the gate run before it, and no surface can tell. Meanwhile
`deployed_bench()` declared no citation at all, so the honest deployment — the one
nobody hand-edited — read as an instrument with no certification even where it had
passed. Four tickets in a row declined to close that, each correctly, because closing
it *is* this decision.

So the door ADR-0021 held shut was holding shut a state that is worse than the one
behind it: a citation that can be right only by somebody remembering, on an artefact
that travels.

## Decision

**One.** A gate run writes its **gate citation** into the case library it wrote its
readings back to. `bench/cited.py` is the whole of that mechanism: `gate-run.json`
beside the case records, holding the citation in the shape `payload.citation` already
serialises it into every signed provenance block.

**Two.** The citation is **rendered off the `RecordedGateRun`** and never composed
beside it. `citation_of` reads the outcome, the date, the library version, the
document's name and the record's own name off the record and computes nothing. The
document, the record and the citation are therefore three renderings of one reading of
one `GateResult`: the record carries the string the document prints, and the citation
is taken off the record. Disagreement is unrepresentable rather than unobserved.

**Three.** `GateCitation` gains one field, `record`, which is the record's own file
name — carried on `RecordedGateRun` so that the writer and the citation cannot name
two different files. `write_the_record` takes a directory and composes the path from
that field.

**Four.** `deployed_bench()` reads the citation off the library it reads its cases
from: the mounted volume where one is mounted, the image's admitted library otherwise.
Cases and citation out of one directory, so the claim and the cases it is a claim
about cannot come apart. A library recording no gate run states the absence.

**Five.** Both entry points update the citation, under the lease. The command-line
gate run writes it inside the `holding_the_library` block it already holds; the
console gate run writes it in `_write_back`, inside the same lease as the readings.
**The difference between them is stated and tested, and it is one restart.** A console
gate run also reaches the running process, through `gate_runs.Cites` — a `GateCitation`
in, nothing out — because the process that made the gate run is right there. A
command-line gate run cannot update a process it is not in, so its citation takes
effect at the next boot, which is the same shape as ADR-0021's *the library a running
process holds is the one it booted with*.

Both halves of that difference are asserted rather than described. The console's half
is `test_a_console_gate_run_updates_the_gate_this_bench_cites`, over the route, the
`ReportConfig` and the library at once. The command line's half is
`test_a_citation_written_from_a_terminal_reaches_this_process_at_its_next_boot`: a
citation written into a mounted library leaves a running bench citing nothing and the
next boot citing it. The gate screen states the same difference in the operator's
words, above the control that starts one.

**Six.** A console gate run now writes its record too, into the library, under a dated
name. This closes ADR-0021's own complaint that the two entry points leave different
traces: the trace is now the same record in a different directory. It has no document
to sit beside, so `document` is **`None`** on the record and `null` on the wire — a
typed absence rather than a sentence in a field a reader would follow as a path. The
words for the absence live where they are read (`GateCitation.stated()`, and the two
console screens' own two shapes), which is the same division the report screen makes
for a family with no rate: a field that is sometimes a file name and sometimes a
paragraph is one that the first consumer to guess wrong prints inside a `<code>`
element.

### What a gate run that did not pass does to the citation

**A gate run of any outcome replaces the citation, and the replacement is announced.**

The two obvious answers are both wrong and are rejected here by name.

- **Leave the passing citation in place.** Then a bench that has just measured its own
  discriminating power and found it wanting goes on carrying *passed* into the
  provenance block of every report it signs. The library digest in the citation and the
  library the bench is running would diverge, detectably and unstated. It is the
  flattering direction, which is the direction [ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)
  says a wrong field survives review in — nobody in the chain has a motive to object.
- **Clear the citation to nothing.** Then `UNCITED_GATE` says *no gate run is cited —
  this bench's own discriminating power is unstated here* about a bench whose
  discriminating power was stated an hour ago and was too low. An uncited instrument
  and a failed one are two different facts; this answer prints the wrong one.

So the citation is **what the bench last put itself through, and not the best answer it
ever got** — which is what `CitedGate` already said in the API layer before anything
was reversed: *"this model is not only the passing one: a bench whose gate failed or
was not decided cites it here in the same shape."* This decision makes the code match
that sentence.

The word in the criterion is *silently*, and that is where the work is:

- The outcome is a field every surface branches on, so a failed citation reads
  *failed* on the report, on `GET /bench/gate`, on the gate screen and on the landing
  screen. Three sentences, one per outcome, already exist for that reason.
- `cite` returns what it displaced. The terminal prints it; the console gate run
  carries it on its own record and serves it. A replacement that took a **pass** off
  the bench gets its own extra sentence — `Replaced.displaced_a_pass`.
- Nothing is deleted. Only the pointer moves. Every gate run's record survives where
  it was written, so the displaced citation's evidence is still on disk and the
  replacement says so.

`test_cited.py::test_a_failing_gate_run_replaces_a_passing_citation_and_names_what_it_took`
is the enforcement, from both ends: the resulting citation reads *failed*, and the
sentence names the date, the outcome and the record it displaced.

### What does not change

- **No new composite figure and no cross-family aggregate.** The record's per-family
  figures stay per-family. The citation carries exactly one number — the library's case
  count — and a test walks the serialised citation asserting that no value on it is any
  family's `D`, their sum or their mean ([ADR-0005](./0005-no-composite-risk-score.md)).
- **The per-family figures still do not travel on a report.** The citation names the
  record; it does not carry it. `hardened`, `weak` and `trivial` appear in the file it
  points at and in no user's report, which is ADR-0018 point 6 and is asserted by
  `test_rendering.py` over the rendered document — an assertion this work tripped once
  and had to reword the citation's own sentence to satisfy.
- **Nothing reads a figure by parsing Markdown.** `cited.py` imports no renderer and no
  script, has one reader in it, and never names a `.md` in its code. #84's invariant —
  the dated document's content is unchanged — is untouched: nothing in this work writes
  to the document, and the record was already the thing written beside it.
- **A gate run is still not a run.** `GateRunRecord` and `RunRecord` still never appear
  in one signature. The one new edge from the gate-run side onto the bench a run is
  measured with is `Cites`, which takes a `GateCitation` — provenance, not a decision —
  and returns nothing. `BenchRuns.cite` is the one named writer on `BenchConfig`, and
  the record stays frozen and replaced rather than mutated.
- **The gate screen and the landing screen still cite a fact about the bench.** They
  gained an address, not a verdict, and the sentences whose subject is the bench are
  unchanged (ADR-0018).

## What this gives up

**The citation is now something a gate run can get wrong, and it used to be something
only a person could.** A hand-declared citation was checked by whoever typed it. One
written by the run that earned it is written by code, on a volume nobody reviews —
which is ADR-0021's *the write-back leaves the review path*, arriving at the artefact
layer. The mitigation is that the citation is rendered off the record rather than
composed, so the class of error available is narrower; it is not zero.

**A failing gate run now degrades every later report, immediately and without a
human in the loop.** That is the decision working. It is still a real cost: an
operator who ran a gate run to investigate something has, by running it, changed what
this bench's artefacts claim. There is no *dry run* and this ADR does not add one — a
gate run with a flag that suppressed the citation would be the flag that lets a
failure go unrecorded, and the argument against it is ADR-0021's argument against
`--yes`.

**The citation and the record can still be separated by a filesystem.** The citation
names a file name, not a URL. On a laptop the record is in `docs/gate-runs/` beside
its document and a reader has the repository; on a deployment a console gate run's
record is in the mounted library and a reader has the volume. A recipient holding only
the signed payload has the *name* of a file they may not be able to fetch. Serving it
is a route, and a route is a decision this ADR does not take: what it fixes is that
the address exists and is machine-readable, which is what made the figures
unreachable before.

**The repository's own library does not start citing anything today.** Its last
passing gate run — 2026-08-19 — predates #84's record writer, so there is no record
for a citation to point at and no honest way to manufacture one: transcribing the
document into a record by hand is the second arithmetic this whole arrangement exists
instead of. `deployed_bench()` therefore still states the absence until the next gate
run, and then stops. A hand-declared fallback was considered and rejected — it is
precisely the *wired in by hand* that decision 2 exists to remove, and a constant
naming a library digest is a constant that goes stale silently.

**A console gate run's records accumulate in the library and nothing prunes them.**
One dated `.json` per gate run, beside the case records, for ever. That is the
append-only posture on purpose — the citation moving is a change of pointer and never a
loss of the runs before it, which is ADR-0006's shape — but it is a directory that
grows without a bound and without a rule for when a record stops being worth keeping.
The command-line path has the same property in `docs/gate-runs/`, where a person
reviews the diff; on a mounted volume nobody does. Pruning is a decision with a
retention question in it and is not taken here.

**One name is now overloaded in a way this does not fix.** `GateRunRecord` (the
console's in-memory record) and `RecordedGateRun` (the written record a citation names)
are a near-homonym, and this decision makes the second one more prominent. Renaming
either is deliberately out of scope; the vocabulary side is being handled separately.

## Considered options

- **Carry the per-family figures on the citation itself.** The most direct reading of
  *the citation reaches the record*, and rejected on ADR-0018 point 6: the record names
  `hardened`, `weak` and `trivial`, and a table of three agents' rates beside a
  customer's agent name invites *your agent scored between the weak and the hardened
  reference*, which is a composite judgement wearing a comparison's clothes. A pointer
  travels; a table does not have to.
- **Keep the citation as declared configuration and add a second, discovered one.**
  Two citations, and every surface choosing between them. The choice is the decision,
  and pushing it to the reader means every screen makes it differently — which is how
  a screen comes to state a gate result no artefact carries.
- **Keep the last *passing* gate run as the citation, and record failures elsewhere.**
  This is the phrase the ticket's own criterion uses, and it is the stale-pass option
  in better clothes: a bench that failed its gate would still carry *passed* into every
  report, with the failure filed somewhere a reader of the report never looks.
- **Clear the citation on a failure.** Rejected above: an uncited instrument and a
  failed one are two facts, and this prints the wrong one about the more serious of
  them.
- **Put the citation in a store of its own rather than in the library.** A row in a
  table, or a file under a path of its own. Rejected on the same reasoning as ADR-0021
  condition 4 and ADR-0006: a citation is a claim about a library at a version, and one
  kept anywhere but with the cases is one that can drift from them — and the drift is
  invisible, because both halves still look fine on their own.
- **Have `GET /bench/gate` read the citation off the library on every request.** Then
  the route needs no wiring and a command-line gate run would take effect at once. It
  also makes a route a filesystem reader on the hot path, gives `/bench` a way to
  disagree with the `ReportConfig` a report is signed against, and would mean two
  requests during a gate run's write could see two answers. The route stays a read of
  the record the process holds; the record moves through one named writer.
- **Hold the citation on `BenchGateRuns` and have the report layer ask it.** Rejected:
  that is a function of the gate-run registry being consulted by the run pipeline,
  which is exactly the direction ADR-0021 condition 2 keeps closed. The edge runs the
  other way — from the gate run to the bench, carrying provenance — and it is one
  callable wide.

## Consequences

- **ADR-0021's cost list is two items shorter, and it should be read with this file.**
  *A console gate run leaves no dated document* is still true; *the two paths leave
  different traces* is not, because both now leave a record. *The bench does not start
  citing the gate run it just made* is reversed. Everything else on that list stands,
  including the one that matters most: consent moved from *unavailable* to *enforced*.
- **#84's two files became three renderings.** `gate_record.py`'s docstring says so,
  and `RecordedGateRun` names its own file for a third reader that did not exist when
  it was written.
- **`ReportConfig.gate` stays declarable.** A caller may still hand one in — most of the
  test suite does — and what changed is the default for a deployment that declared
  nothing. A bench under test does not have to have run a gate to have a citation.
- **The gate screen's write-back block gained a line, and it is above the control.**
  An operator learns that a gate run replaces what this bench cites *before* pressing
  the thing that starts one, which is the ordering that block already existed to
  enforce.
- **A declined gate run cites nothing.** The citation is written from the write-back,
  and the write-back happens only from a decision the run reached — so a run refused at
  the interrupt leaves the citation exactly as it found it, asserted over the file
  rather than over a sentence.
- **The route function was renamed.** `cite_the_gate_run_this_bench_last_passed`
  became `cite_the_gate_run_this_bench_last_made`, because the old name is the
  stale-pass reading in an identifier and this decision rejects it. The path is
  unchanged.
- **`CONTEXT.md`'s two entries moved.** *Gate citation* now carries what the record is
  called as well as the document; *gate run record* is what the citation points at
  rather than what a reader has to know to go looking for.

Cross-references: [ADR-0021](./0021-the-console-may-start-a-gate-run.md) (the decision
this amends, its six conditions, and the two questions it recorded as shut),
[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) (the
citation as provenance, the words that are not available for a target, and point 6 on
naming the equipment), [ADR-0005](./0005-no-composite-risk-score.md) (no composite,
which the record's six per-family scores are the shape most likely to grow),
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the declared rule, served
above the outcome so a citation is re-derivable),
[ADR-0006](./0006-overrides-never-change-a-measured-rate.md) (append-only evidence, and
why nothing here is deleted),
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the
type-level discipline the one new edge is narrowed by),
[ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md) (the deployment
boundary `deployed_bench` sits on).
