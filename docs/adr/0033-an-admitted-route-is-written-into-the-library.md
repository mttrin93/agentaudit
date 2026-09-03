---
status: accepted
---

# An admitted route is written into the library, and the denominator stops being a constant

[PLAN](../../PLAN.md) §10's hard optional task says the loop closes: "the adaptive
attacker finds a route the fixed suite missed, `propose_case` drafts it, the admission
gate decides at `D ≥ 0.4` … and **the library the next run uses is different because
of it**."

It did not close. `promote` returned a case and put it nowhere —
`adaptive/promotion.py` says so in its own docstring, "Nothing is written. The
admitted case is *returned*" — and `scripts/swap.py` printed the consequence at the
end of every run. No entry point in this repository wrote a case record from scratch:
`scripts/admit.py --write` appends an `[[admission]]` block to a record a human
already authored, and `library.py` reads with `tomllib`, which has no writer at all.
So the library the next run loaded was the library the repository shipped, and the
strongest claim the project makes for "an agent that learns" rested on a step nothing
performed.

[ADR-0032](./0032-the-admission-memory-holds-the-measurement.md) built the memory
this needed first and left the distinction it must not lose: **remembering an
admission is not admitting.** That store says what was *decided*; the library says
what was *admitted*.

This ADR is the write, and the two things the write breaks.

## Decision

1. **The run writes the case.** `backend/bench/entry.py` holds `case_record` — a
   real TOML serialiser for a whole `Case` — and `enter`, which writes each admitted
   case the library does not already hold a route for. `discovered_by = adaptive`
   comes off the record `proposal.py` drafted, so `library_provenance` reports the
   attacker-written fraction of the library the moment a record lands and no new
   field is needed to keep it visible.
2. **A written record is live on the next run, and no quarantine status is added.**
   `CaseStatus` stays `ACTIVE | RETIRED`. **The quarantine is the bar, not a status**
   — argued below.
3. **One route is one record.** The key is `decided.RouteKey`, the family and a
   `sha256` of the probe, looked up against **the library on disk** and never against
   the admission memory. Within one run as well as across runs.
4. **Admission is re-derived off the record before it is written**, and a case that
   does not clear the bar its provenance requires is refused rather than filed.
5. **The write takes the library lease itself**, rather than requiring its caller to
   hold one — the one place this differs from `cited.cite`, and argued below.
6. **The write records the cited gate run as superseded**, on the citation, under the
   same lease. `GateCitation` gains `moved`; nothing else on it changes.
7. **`n` per family is derived and the printed rule stops asserting a constant.**
   `GateRule.attempts_per_family` is gone, `GateRule.stated` no longer says *three
   cases per family, so n = 30*, and each family's denominator prints beside that
   family's rates where the counts already sit.
8. **Nothing here reads a clock.** `entry.py` does not import `datetime`.

## The quarantine is the bar, not a status

A third `CaseStatus` — *admitted but not yet trusted* — is the shape a reviewer
reaches for, and it re-asks a question a declared threshold has already answered,
which is the thing [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)
exists to avoid: the arbiter is a stated number, not somebody's confidence.

A route reaches a record only by clearing the cross-model bar — three reference
agents, two underlying models, `D` over the declared floor, which is
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md)'s *same* floor the gate later
holds the family to. That is a stricter entry test than an authored case faces and
stricter than a human reading a `.toml`. `promote` returns the case already carrying
the `AdmissionRecord` that cleared it, so what `admitted_library` loads next run is a
case the next run executes, with no human between the gate and the library.

What keeps it auditable instead of a status, all of it already built:
`discovered_by = adaptive` on the record; `library_provenance` reporting the adaptive
fraction live and retired; the admission block carrying the readings the decision is
re-derivable from; and **retirement**, which removes a case that stops discriminating
whoever wrote it and is grouped by provenance precisely so that an attacker-authored
library that decays is visible as that (ADR-0012).

## Who takes the lease, and why not the caller

`bench/lease.py` exists for the read-modify-write hazard over a directory of records,
and a case file appearing while a gate run is halfway through reading the library is
that same defect arriving from a new direction. So the write happens under the lease
and a gate run and a write refuse each other by name.

`cited.cite` answers the same question the other way: it does not take the lease, and
`scripts/gate.py` holds one across its whole run. That is right for a gate run, which
reads every record and writes back to every one of them and must not have the library
move under it. It is wrong here, for two reasons:

- **The critical section is exactly this call.** Load what is on disk, decide which
  routes are new, write them, read the version back, record the superseding. There is
  no earlier point the writer depends on the directory not moving from.
- **The one caller today is `scripts/swap.py`, which is not a gate run.** It holds no
  lease, and giving it one across its two calibrations would refuse every gate run
  for the length of a paid run, for a write that happens in its last second.

Putting the lease in the writer also makes the mutual exclusion a property of the
writer rather than of each caller that grows one. A caller that already holds the
lease cannot call `enter`; there is no such caller, and the day there is, the body it
wants is one function down.

## The de-duplication reads the library, not the memory

`proposal.py` mints `id=f"adaptive-{family}-{uuid.uuid4().hex[:8]}"`, a fresh random
id per proposal. Without a key over the route, the same route discovered on two runs
becomes two library records with two ids and one payload, and the family's `n` grows
twice for one route. That is why this ticket sat behind ADR-0032, and it is the
mechanical reason the loop could not simply be closed earlier.

ADR-0032 left the key: `RouteKey`, the family plus a digest of the probe that actually
ran. What it also left was the caution, and it decides the shape here — **the library
is the record of what is in the library.** So `enter` loads every record on disk and
keys them, and the memory is not consulted at all. A route the memory holds a row for
may never have been written anywhere: the row says a threshold decided it, and only
this directory says a record exists.

Three consequences worth stating:

- **Retired records are in the key set.** A retired case is kept and never deleted
  because it is evidence that the field moved (CONTEXT.md), and a rediscovery written
  as a fresh *active* record would un-retire it by the back door, under a new id, with
  the retirement rule's own reading left on a record nothing now runs. So a collision
  with a retired record is reported as one and nothing is written.
- **A route is de-duplicated within one run too.** ADR-0032 measures a route once per
  run and still decides *every proposal* of it, because "the count's unit is the
  proposal" — so one run can hand `enter` four admitted promotions of one route under
  four ids. One record.
- **The unit is a payload and not a description.** Rejected in ADR-0032's own words:
  the model writes the prose, so two descriptions of one route are two keys.

## The write proves its own round trip, and refuses rather than escapes

There was no TOML writer in the tree, so `case_record` is new: every field, both
criterion shapes, the admission block, the decay series and the retirement. Three
decisions about it, each because the failure mode is worse than one bad record.

**The round trip is enforced and not only asserted.** `enter` reads back every record
it writes and removes one that does not load equal. A record `load_case` cannot read
is not one lost case, it is a directory `admitted_library` refuses in its entirety —
a library that stops loading is a bench that stops running.

**A record that does not clear its own bar is refused at the write.** Raised, not
selected — which is the opposite of
[ADR-0031](./0031-a-run-files-its-deterministic-findings-after-it-has-read-them.md)
point 3's choice for judged findings, and the difference is what the condition *is*: a
judged finding arriving at `file_precedent` is a data condition the function is asked
to sort, and a case with no admission block arriving at `enter` is a caller that has
lost its own invariant. `promote` returns a case only when it cleared.

**A value TOML cannot hold literally is refused, not escaped.** A carriage return in
a payload did not come from an author's editor, and a serialiser that rewrote one
would put a record on disk whose payload is not the payload the target was sent.
Multi-line basic strings are the form used, because these are fields a person reads
and a run-written record has to diff against an authored one.

**The blocks a gate run writes come from the functions a gate run writes them with.**
`retirement.history_block` and `retirement.retirement_block`, not copies. A second
copy of a format is the copy that rots, which is ADR-0029's own measurement-backed
argument applied to prose instead of to a pragma. For the same reason
`entry.admission_block` is the single writer of an `[admission]` block, and it takes
the bar, the date and the readings rather than an `AdmissionRecord`, so that
`scripts/admit.py` can keep printing the block for a *rejected* cross-model case —
which is exactly the record `AdmissionRecord.__post_init__` refuses to build.

## The citation is a claim about a version, and the version moved

`library.py`'s digest covers every field of every case except `history` and
`retirement`, excluded deliberately so that a gate run's own write-back does not move
the version a run was made against. **A new case does move it.** So the cited gate run
becomes a pass recorded against a library that no longer exists, and leaving it
standing untouched is the one option that is wrong.

`GateCitation` gains `moved: LibraryMoved | None` — the version the library is at now,
and the ids that entered since — written by `cited.moved_past`, called by the write
under the same lease `cite` is called under and for the same reason: a claim about a
library version has to land inside the critical section the version moved in.

Four things this deliberately is not:

- **It is not a deletion or a clearing.** ADR-0023's *nothing is deleted, only the
  pointer moves* applies unchanged. The outcome, the date, the version the gate run
  was earned at, and the two addresses its figures are recovered through are all still
  the record's own.
- **It is not a figure.** A count, a digest and a list of ids. What the new cases
  would measure is a question only a gate run answers, and this record does not
  pretend to.
- **It is not a caveat a reader has to assemble.** Both versions were already on the
  citation, so a reader *could* have compared two digests. A figure a reader has to
  cross-reference to qualify is a figure that gets quoted unqualified — ADR-0032's
  reasoning about the admission counts, one ticket on — so the sentence is in
  `GateCitation.stated()`, which is what a report carries.
- **It is not permanent.** A gate run decided at the current version supersedes
  nothing, so `cite` clears it. Running the gate is what earns a citation at this
  version, which is the correct remedy and the only one.

`payload.citation` serialises it as `null` and never as a missing key, and `CitedGate`
carries it, because that response is byte-identical to the provenance block of every
signed report and a field dropped on the way to a screen would be dropped in the
flattering direction ([ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)).

## `n` per family becomes derived

A fourth case in one family makes that family `n = 40` while five stay at 30, and the
rule printed `n` as a constant: `f"n = {self.attempts_per_case} attempts per case,
three cases per family, so n = {3 * self.attempts_per_case} per family per agent"`.
That `3 *` was the only place in this bench where the library's shape was asserted
rather than read.

**It is cheaper than it reads, because only the prose asserted it.** Nothing computed
30: `graph/budget.py` is `len(cases) * rule.attempts_per_case`, and every rate row on
a gate record already carries its own `attempts`. So:

- `attempts_per_case` stays declared configuration and does not move. It is the
  per-case denominator, unchanged by a library growing, and it is still the one field
  a console may set ([ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md)).
- `GateRule.attempts_per_family` is gone and `GateRule.stated` states no per-family
  `n` at all. **`rule.py` imports nothing but `dataclass` and stays that way** — it
  has no access to a library and must not be given one, and a test asserts the import
  set rather than trusting it.
- The denominator prints where the counts are: beside each family's rates, in
  `gate.stated_denominator`, counted off the attempts that ran. A family whose three
  agents were not attempted equally has no single `n` and the line says so, rather
  than printing one of the three as though it were the family's.
- **Retirement is unaffected**, and worth checking rather than assuming. The
  docstring on `attempts_per_case` ties n = 30 to the retirement rule being able to
  operate, but retirement reads `D` per case over two consecutive gate runs on one
  model ([ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md)), so
  a family growing raises its own `n` rather than diluting the window.
- **Recorded documents from here on carry different rule text, and past signed
  documents are unaffected** — each carries the text it was signed with, which is the
  point of recording it on the document rather than looking it up
  ([ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md)). One
  test asserted today's rule text appears in the 2026-08-19 gate document; it now
  asserts that it does not, and says why.

**The alternative — couple admission to retirement so the library stays 3 × 6 — is
rejected.** It makes a route that cleared the bar wait for an unrelated case to decay,
which is a queue disguised as a rule. The gate already lives with unequal
denominators, since a family the target could not answer is excluded from the
decision entirely ([ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md)).

## What this does to ADR-0010, stated as four questions

This write sits on ADR-0010's single sanctioned crossing: an admitted route is a
thing the *adaptive* layer proposed, entering the population *scored* attempts are
drawn from. Four questions, each with the assertion that answers it.

**What is an admitted case dated by?** By the measurement. `AdmissionRecord.admitted_on`
is the day the three reference agents were run, and for a route answered from the
admission memory that is a day on an earlier run — ADR-0032 gives `recall` no `today`
argument so that nobody can date a year-old reading to this morning. This module is
the other end of that decision and withholds the same argument: there is no `today`
anywhere in `entry.py` and it does not import `datetime` at all, which a test asserts
structurally rather than by reading a value. `Case.added_on` is the other date and is
the proposal's — added today, on evidence taken earlier, is the honest pair.

**Does a case entering the library move any recorded rate, interval, band, `D` or
κ?** No. Mechanically: every record already on disk is byte-identical after the
write, so no decay series gained a reading and no status line moved. Arithmetically:
this module computes none of those quantities and imports nothing that would let a
caller ask it to. What *does* change is one pointer — the citation now says the
library has moved past the version its gate run was decided at — and that is a
statement about the library, not a figure about a run.

**Are the library's contents now a function of run history?** **Yes, and that is the
honest answer to write down rather than the one to engineer away.** A library that has
admitted a route depends on which routes past runs found, and the adaptive layer is
not reproducible (ADR-0010: "run an adaptive attacker twice and you get two different
numbers"). What is unchanged is what was ever claimed. `LibraryVersion` already exists
because "two runs months apart are comparable or provably not, and *provably not* is
the half that needs a number"; a run records the version it was made against; and a
gate decision stays reproducible from its recorded inputs. What a reader loses is the
ability to reconstruct the library from the repository alone, and that is why the
citation had to say so and why `docs/validation.md` records it under what has never
been validated.

**Can an admitted case re-enter the gate and be admitted twice?** No, on three
counts. The route key blocks a second record for one payload, within a run and across
runs. The key set includes retired records, so a rediscovery cannot un-retire one
under a new id. And `admitted_library` refuses a record whose own reading does not
clear the bar it claims, which is why the write re-derives that decision rather than
trusting the caller.

## Considered options

- **A third `CaseStatus`, quarantining a written case until a gate run has read it.**
  Rejected above: a declared threshold has already decided, and a status would put
  somebody's confidence after it.
- **Leave the write to a human, as `scripts/admit.py --write` does.** This is the
  status quo and it is what ADR-0032 explicitly deferred. Rejected because it is the
  step PLAN §10 claims happens, and a loop that needs a person to copy a record is a
  loop the project should not describe as closing.
- **Take the lease in the caller, as `scripts/gate.py` does.** Rejected above: the
  critical section is one call, and the only caller today would hold the library
  across a paid run.
- **Delete the citation on a write, or clear it to nothing.** Rejected on ADR-0023's
  own reasoning: a citation cleared to nothing states *no gate run is cited* about a
  bench that has measured its own discriminating power, and the record is evidence
  either way. Only the pointer moves.
- **Leave the citation untouched and let a reader compare the two digests.** Rejected:
  both numbers were always there and nothing said what their difference meant. The
  qualification goes on the line with the figure.
- **Fingerprint the whole `GateRule` and re-run the gate automatically on a write.**
  Rejected as the wrong actor: a gate run is 830-odd calls on the operator's provider
  and ADR-0007 makes spending that an explicit human decision. What a write can do is
  say the citation is behind, which is what it does.
- **Couple admission to retirement to keep the library at 3 × 6.** Rejected above.
- **Print the per-family `n` from the library rather than from the counts.** Rejected
  because the figure printed must be the figure the rates were divided by. A family
  the target could not answer on one case has an `n` the library does not predict, and
  a denominator read off the library would then disagree with the fraction beside it.
- **Serialise the record as one-line TOML strings with `\n` escapes.** Simpler and
  exact. Rejected because case records are read by people and a run-written record has
  to diff against an authored one; the multi-line form costs two escapes and a test
  built out of every hazard TOML has.
- **Reuse `AdmissionReading.stored()` for the TOML.** Rejected: that is the JSON shape
  ADR-0032's store writes, and TOML needs text with quoting. What *is* shared is the
  block writer, in the one direction that had two copies.
- **Key the library by the whole case digest.** Rejected in ADR-0032's one line: the
  case id is in it and is a fresh uuid per proposal, so the key would never be hit
  twice.

## Consequences

- `backend/bench/entry.py`; `LibraryMoved` and `GateCitation.moved` in
  `backend/bench/payload.py`; `cited.moved_past`; `gate.stated_denominator`;
  `GateRule.attempts_per_family` removed. `uv.lock` does not move.
- **The one caller is `scripts/swap.py`**, which is where the cross-model bar and the
  promotion loop already live. Its closing paragraph — "Nothing here wrote it to the
  library" — is replaced by what was written, and its own document carries the same
  block. A run that finds the library held by a gate run says so and writes nothing.
- **`entry.admission_block` is the one writer of an `[admission]` block**, and
  `scripts/admit.py`'s own builder is now a call to it. It was written as a second
  copy first and the code review caught it, which is the outcome that argument
  predicts: the copy that is not being exercised is the copy that rots. It takes the
  bar, the date and the readings rather than an `AdmissionRecord` because a rejected
  cross-model outcome is exactly the record `AdmissionRecord.__post_init__` refuses
  to build, and `admit.py` has to be able to print one.
- **Prose asserting the constant is corrected where it sits**, not only where the
  ticket listed it: `AdmissionReading.stored` ("hand-written TOML, not something the
  bench serialises" — it is now), `FamilyRates` ("n = 30 each" — the very type
  `stated_denominator` reads), `gate_record.MeasuredRate`, `CONTEXT.md`'s **case**,
  **attempt** and **admission**, README, PLAN §10 and its phase-4d line and its
  pipeline diagram, `scripts/gate.py`, `scripts/admit.py`, `scripts/calibrate.py`,
  the pre-web-bench spec and the settings screen's own caveat. `scripts/console.py`'s
  "a Wilson interval on `n = 6` has no business printed beside one on `n = 30`" is
  left as it is: it is ADR-0011's argument about two *units* and not a claim about
  any library's shape.
- **`app.py`'s `attempts_per_family` on the settings screen was already derived** from
  `_cases_per_family`, the most cases any family holds. That reading was written when
  three was the only possibility and it now bites: it is the `n` a *full* family is
  measured at, which is the right thing for a screen that is telling an operator what
  they are setting, and not a claim about any particular family's figures.
- **The adaptive fraction of the live library can now be non-zero**, which is the
  series ADR-0012 asked to be printed on every gate run so that a library filling
  with routes fitted to these three agents arrives as a series rather than as a
  surprise. Nothing about that reporting changes; it stops reading zero.
- **`docs/validation.md` gains an entry under what has never been validated**: no
  route has ever been written into the library by a run against real provider models,
  and the eighteen cases on disk are all authored. The mechanism is exercised end to
  end in the suite against stub models.
- **A gate run's own write-back is unaffected.** `retirement.store` appends to records
  it read, under the lease, and the two writers cannot overlap.
- **#61 goes next and touches `backend/api/runs.py`, which this ticket does not.**
  Nothing here is in the API's path: the write is a `bench` module called by a script,
  and `runs.py` is unmodified.

Cross-references:
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (the one
edge this is, and the rates it may not touch),
[ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) (the
bar that is the quarantine, and the provenance series that watches it),
[ADR-0032](./0032-the-admission-memory-holds-the-measurement.md) (the key, the date,
and the caution that the memory is not the library),
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) (the declared rule, and the
n = 30 a three-case family gives),
[ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md) (nothing is deleted,
only the pointer moves),
[ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md) (why a family
growing does not dilute the retirement window),
[ADR-0031](./0031-a-run-files-its-deterministic-findings-after-it-has-read-them.md)
(the other write path, and why this one raises where that one selects),
[ADR-0021](./0021-the-console-may-start-a-gate-run.md) (the lease, and the two entry
points that exclude each other).
