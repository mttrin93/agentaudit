# ADR-0075: A declared gap reaches the signed artefact, and reasoning effort stays a library-level setting

**Status:** accepted (#138, group J / #81)
**Date:** 2026-09-05

## Context

[ADR-0066 §6](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md)
declined three of #89's input table and said why: `scripts/bench.py` does not call
`plan_for`, and it passes no gap record into `payload_for`, so a family switched off
through the Action would be **absent from the signed report with no reason beside
it** — the reading `BenchConfig.families` exists to make unavailable, one document
further on and now under a signature. An action input that produced that is worse
than an action input that does not exist.

This is the ticket that argues the change to what the report says, which is what
ADR-0066 §3 deferred it for.

Three facts frame it. First, the artefact already keeps every other absence apart:
a judged family barred below the κ floor is `withheld`, a family whose precondition
this target could not meet is `not_measurable`, an elective family nobody asked for
is its own block (ADR-0035), and each of the four prints its own sentence rather
than a shared *not tested* (ADR-0004). Second, the caller's own narrowings had **no**
such place: `DeclaredGap` existed, `POST /runs` recorded it, and the only surface
that printed one was that run's own HTTP response. Third, `bar.py` already had a
literal apologising for it — `_NO_REASON` named #138 and told a reader the reason was
in the run's log and not in the document.

## Decision

### 1. The measured section carries a fourth absence, and it is not one of the other three

`MeasuredSection.not_run`, a `not_run` block in the payload, and `_not_run` in the
renderer beside `_withheld` and `_not_measurable`. Five functions for five absences,
on that module's own rule: a family absent because the bench could not read it and one
absent because its caller switched it off are two statements, and one list holding both
would be the renderer deciding they are the same thing.

**A family may be absent for exactly one reason, and that is checked.** A family
carrying a rate and a declared gap, or a declared gap and a `NotMeasurable`, is refused
in `__post_init__` — two answers to *why was nothing attempted* is a reader believing
whichever block was printed first.

**The block is present and empty on a run that narrowed nothing**, and says so in a
sentence. A key that appeared only on narrowed runs would make *this run asked for
everything* and *this artefact predates the block* the same bytes to a recipient. This
is `_elective`'s argument for its own heading, one absence along.

**`ARTEFACT_VERSION` does not move.** A block added where four already stand is the
shape this document has had since ADR-0044 — a family's line is its figures or one of
its absences — and every consumer in the tree reads the section by key. What a version
bump would say is *a later shape is a different shape*, which is a claim about a reader
that cannot find what it is looking for, and no reader here is in that position.

### 2. `DeclaredGap` moves into `backend/bench/`, and `run_status.py` re-exports it

It was declared in `backend/api/run_status.py` because the only surface printing one
was a route. It is now the vocabulary of a signed document, and **no module of
`backend/bench/` imports `backend/api/`** — the artefact reaching up into the routes
for the words its own absences are written in would be the one import that inverts the
two layers.

So `backend/bench/declared_gap.py` holds it and `run_status.py` re-exports the name.
Nothing about the API's vocabulary moved: `from backend.api.run_status import
DeclaredGap` resolves, and the module it resolves into says why it is there.

**Not merged into `measurability.py`.** That module's whole docstring is the argument
that a precondition the bench *checks* and a gap it is *told about* are two types, and
`NotMeasurable.NO_CONFIG_CANARY_PLANT` names `DeclaredGap.NONCE_NOT_PLANTED` in prose
to say so. One module for both would put the distinction inside the file that exists
to draw it.

### 3. The gaps arrive as an argument, and it is required at the artefact's one door

`payload_for` and `artefact_for` take them, and they take them **required**;
`assemble` takes them beside its eight other defaulted section inputs. `RunPlan.gaps`
is what the API path hands over, and `scripts/bench.py` composes its own.

**An argument rather than something read off the run.** A family whose cases were
dropped before the first send made no attempt, so there is nothing on a `TargetRun`
to derive it from: the record it lives on is the run's *plan*. Deriving it inside
`assemble` would mean that function reading a figure out of one section and into
another, which is the property it does not have (ADR-0005).

**Required at `payload_for`, on `DeclaredModels.narrative`'s terms**: an entry point
added later has to state its answer rather than inherit one. What a default would say
is *this run narrowed nothing* — silently false for the whole of `scripts/bench.py`'s
existence, which is exactly the hole this ADR closes. That is the door every producer
of an artefact goes through, and there is no route to a signed document that skips it.

**And defaulted at `assemble`, deliberately.** Every one of that function's section
inputs is defaulted with its own stated absence — no gate citation, no episode, no κ,
no checkout — because it is also called directly, one section at a time, by tests
asserting that section. A ninth required parameter there would buy nothing the door
above does not already hold, and would make each of those call sites state an answer
to a question it is not asking.

### 4. `scripts/bench.py` narrows through `plan_for`, and takes `--families` and `--attempts-per-case`

`plan_for` is the authority on which of the library's cases a run may attempt and why
the rest are out, so a family switched off in a workflow reads exactly as one switched
off in the console. The entrypoint's own two narrowings stay where they are and are
passed to it as **already answered**: `deterministic_subset` keeps the terminal words
`print_target_run` prints, and `withdrawn_for_want_of_a_plant` keys on `Case.requires`
and on whether *this target* answers for its own plantings, which is the distinction
ADR-0061 drew and which `plan_for` — keyed on two family names — does not have.

`OperatorGap.declared` is the translation into the artefact's words. **The two members
that annotate a measured rate raise rather than return.** `PLANTING_UNVERIFIED` and
`NO_STOP_POSITION_RECORDED` sit beside a figure the run did produce, so no family is
absent for them; a `None` there would be the one route by which a withdrawal reaches a
signed document as silence.

**Three refusals, all before the first send.** A family name the bench does not hold —
refused rather than dropped, because a run that quietly covered fewer families would
report the rest as switched off by a caller who did not switch them off. A denominator
below one. And a selection that leaves no case at all: a narrower run is a run, and an
empty one is a signed document about nothing.

**No upper bound on `--attempts-per-case`, and the ceiling is the reason.** The console
bounds it to what its screen can show (`app.ATTEMPTS_RANGE`); a workflow has no screen,
and a number large enough to matter is one the estimate prices and the declared ceiling
declines. A second range in a script would be a bound nobody declared, checked against
a run that already has one. What a run below ten costs is stated in the artefact and not
here: `rule.denominator_stated` writes the caveat and `NOT_A_GATE_RESULT` is the
sentence (ADR-0025, ADR-0027).

### 5. `reasoning-effort` is not an input of the Action, and gets no seam through `console.instruments`

The third of #89's three, and it is **declined on ADR-0025's own argument** rather than
in spite of it. A declared input of a run is recorded so that it can be reviewed; this
one has nowhere in the record to be.

**`console.instruments` builds the adjudicator and the narrator, and the artefact
carries a reasoning effort for neither.** `DeclaredModels` carries
`attacking_reasoning_effort` and nothing else, and its own docstring argues why:
*deliberately not carried for the other two instruments … the adjudicator and the
reference agents are settings of a deployment this bench offers no thinking budget
over*. An effort set through that seam would therefore be a declared input of a run
that the signed artefact has no field for — this ticket's defect, arriving through the
same door one instrument over. Adding the field instead would be the report claiming a
control over somebody's deployment that the bench does not have.

**And where the attacker's effort *is* a declared input, it is already declared at the
level it belongs to.** `completion.declared_reasoning_effort` reads
`AGENTAUDIT_ATTACKER_REASONING_EFFORT`, refuses a level this bench does not offer, and
is read where the attacker's client is built beside the identifier
`report.models.attacking` prints — in one call, so the instrument a run was made with
and the model its provenance names cannot come apart (`app.declared_instrument`). That
is a **deployed** bench: a variable of the process serving `POST /runs`, recorded in
what that process signs.

**A headless run has no reasoning attacker at all today, which is the third reason and
the plainest.** `scripts/bench.py` runs the adaptive layer on `SCRIPTED_ATTACKER`, the
deterministic stand-in, and declares `attacking` as *not declared*: it builds no
attacker client, so it reads no effort and could record none. An action input naming
the attacker's effort would name a setting for an instrument the entrypoint does not
build — a workflow field that changes nothing and prints nowhere, which is worse than
its absence. **Nor does setting the environment variable in a workflow do anything on
this path**, and that is stated here rather than left to be discovered: the day this
entrypoint builds a real attacker is the day it gains the seam and the field together,
and it is not this ticket.

So: it stays a library-level setting, this section is the written note ADR-0066 §6
asked for, and `console.instruments` carries a one-line pointer here.

### 6. What ADR-0066 §3's preamble keeps, and why

The job summary's preamble still prints the withdrawals in `OperatorGap`'s own words.
Its stated reason — *those are absent from the measured section* — no longer holds, and
two remain. The preamble covers **elective** families too, and the measured section is
keyed on the six (ADR-0035). And a page is scrolled: a reader who opens a job summary
meets the preamble first, and a run that dropped two families before sending should not
need a scroll to say so. Nothing is asserted twice as a *figure*; both are the same
withdrawal in the two surfaces' words, which is what those two enumerations are for.

## Consequences

- `bar.py` reads `measured.not_run` beside `not_measurable` and `withheld`, so a
  covered family its caller declared away is red **with the gap's own sentence**
  rather than red with none (ADR-0067). `_NO_REASON` stops naming #138 and now
  describes the one absence this bench does not produce: a family in none of the four
  lists, which is a document whose narrowings were not recorded.
- The rendered document changed, so `GOLDEN_ONE_FAMILY` moved in the same commit as
  the wording that moved it (ADR-0017).
- **This is the one block on the page whose rows carry no discovery count.** Every
  other family row pairs what the search found with what the suite measured, because
  the join is the family and never the figure (ADR-0056); a family here has no case
  left in the run, and `adaptive/layer.objectives_for` picks each family's objective
  out of that same pool — so no episode could have been opened against it and the
  count could only print its own empty answer. A line that can only say *none* says
  nothing, and printing one would suggest the search had been asked.
- **The new block is signed and not verified**, exactly as `not_measurable` and
  `withheld` are: `verification.py` re-derives the wording of the rule and the cut
  points and reads no absence. Making this one list the exception would leave a
  verifier that checks one of four kinds of nothing, which is a worse statement about
  the document than checking none. Whether every absence's `stated` should be
  re-derived is its own ticket and its own argument.
- `scripts/gate.py` takes no setting from any of this. `--attempts-per-case` is the
  entrypoint's and the gate stays on `DECLARED_RULE`, which is ADR-0025's line
  unmoved.
- The two remaining inputs of #89's table exist, and parent #81's packaging question
  is answered in full: every narrowing the Action offers is one the artefact records.

## Alternatives rejected

- **One list of absences with a `kind` field.** Four reasons is four statements, and
  the first thing a consumer does with a discriminated union is filter it wrongly. The
  four separate lists are what make a careless reader's mistake visible.
- **Deriving the gaps inside `assemble` from the library and the attempts.** A family
  with no attempt is indistinguishable from one whose cases were all dropped, so the
  derivation would have to guess which of four reasons applied — a sentence invented
  by the assembler rather than recorded by the run.
- **Defaulting the argument at `payload_for`.** Convenient, and it would let a fifth
  entry point reintroduce exactly this bug in silence. §3 says where the requirement
  lands and why `assemble` is not the same question.
- **Leaving `DeclaredGap` in `backend/api/` and importing it from the assembler.**
  Acyclic today and backwards forever: the layering is the one thing a reader of this
  tree can rely on without reading it.
- **A seam for `reasoning-effort` through `console.instruments`.** §5: it would set an
  instrument setting the artefact cannot record, which is this ticket's own defect.
- **A `reasoning-effort` action input wired to
  `AGENTAUDIT_ATTACKER_REASONING_EFFORT`.** The variable is already settable in a
  workflow's `env:`, so the input would add a second spelling of one declaration and
  no reviewability — and it would name a setting for an instrument this entrypoint
  does not build (§5).
- **Bumping `ARTEFACT_VERSION`.** §1: nothing reads this document positionally, and a
  version that moved for every added block would make the field mean *something was
  added* rather than *this is a different shape*.
