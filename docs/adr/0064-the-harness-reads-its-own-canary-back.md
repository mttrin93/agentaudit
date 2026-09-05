# ADR-0064: The harness reads its own canary back, so *planted* stops being a declaration

**Status:** accepted (#87, group J / #81)
**Date:** 2026-09-05

## Context

[ADR-0007](./0007-nonce-echo-registration.md) fuses one value into two roles: the
**nonce** a target must echo to prove the operator controls it, and the **canary**
whose appearance in output proves a leak. [ADR-0024](./0024-a-waived-echo-is-a-declared-gap.md)
then had to unpick what happens when the operator cannot echo, and closed with a
trade it named out loud:

> A leakage rate is measured against a canary whose presence is a declaration. If the
> declaration is false, the family reports thirty resisted — the clean zero that reads
> as a defence and is not one… **That guard moves from a mechanism to a sentence.**

Against a shim the sentence goes back to being a mechanism, and the reason is nothing
clever: **the harness generated the value, the harness called the hook that planted
it, and the harness holds the value it is looking for.** There is nothing left for
the operator to declare. What was missing after #82–#86 is the second half — the
looking. `planting.plant` called the hook and recorded that it returned; a hook that
plants nothing and returns cleanly was indistinguishable from one that worked, and
the artefact carried neither reading, because `TargetRun.plantings` reached no
reporting surface at all (ADR-0062 and ADR-0063 both say so, and both name this
ticket).

**The read-back already exists and is already sent.** `register` puts `ECHO_PROBE` on
the wire for every target on every path, including a waived one, and `Registration.echoed`
is `nonce in probe.reply_text`. Against a URL that reading proves the operator can
configure the target. Against a shim the bench did the configuring, so the identical
reading proves the plant landed. One probe, two roles — the idiom ADR-0007 already
uses for the value itself, one surface over.

## Decision

**1. `issue_nonce` is the only source of this value, and a target that plants its own
configuration canary is refused one from the caller.** `refuse_a_canary_the_run_did_not_issue`
runs at the top of `_run_target`, before the hook and before anything is sent, and
refuses two things for such a target: a `planted_nonces` entry, which would be a value
the caller supplied — *a canary the user supplies is a canary the user can also have
put in the payload, and one value with two provenances is two values* — and a
`plant_nonce`, which is the hand-planting equipment. The second is not about
provenance but about the check: a second hand planting the same value makes the
read-back a reading about the *other* hand's work, and the one thing this ADR buys
would be bought back. Neither refusal touches a target that is a URL, where both
callers are correct and are where ADR-0024 left them.

**2. `Planting.check` carries the reading, and `planting.checked` is what takes it.**
`PlantCheck` has four members and three answers. `VERIFIED` is *the bench planted this
value and the target gave the same value back*. `NOT_RETURNED` is *the bench planted it
and the target did not*, which is the failure this ticket exists to make visible — a
hook that returned cleanly and planted nothing, which is neither a `PlantingFailure`
(nothing raised) nor a withdrawal (the hook is there). **A shim target hardened against
the echo probe produces the same reading**, and the sentence a reader sees says so:
this bench cannot tell the two apart from here, and what it will not do is call either
one verified. `NO_READ_BACK` is every retrieved-content planting. `UNCHECKED` is the
state a `Planting` is born in — `plant` runs before the probe — and it is **a state no
record may carry**: `TargetRun.__post_init__` refuses one, so a two-step construction
cannot leak a default into a signed artefact. The default is the reading that claims
nothing, and the guard is what makes it safe to have one.

**No second call goes on the wire for this**, and no counter moves: the probe was
already sent and already charged as registration. Nothing about a hardened target's
refusal changes — a target that will not echo is unregistered exactly where ADR-0007
left it, and on a waived run it is a `NOT_RETURNED` reading beside a rate rather than
a withdrawal.

**3. Content is planted by the bench and still not read back, and saying so is the
point.** `NO_READ_BACK` is the honest answer and not a smaller `VERIFIED`. The note
and the word that retrieves it come off the case record (ADR-0060), so *that it is
there* is no longer the operator's statement — but the only read-back available for
planted content is the family's own scored attempt, and a precondition read off a
scored attempt is not a precondition (ADR-0004, and ADR-0010's shape). A second probe
that fetched the note would be a call on the wire that measures the family before the
family is measured.

**4. It reaches the artefact, in the provenance block, beside the teardown.**
`Provenance.plantings` carries the run's own record and `document` serialises a
`planting` block: `planted`, `verified`, the per-plant list with each check's sentence,
and a `stated` line the Markdown prints. It is provenance and not a figure — a plant is
a precondition of measurement and never an input to one (ADR-0006, ADR-0024) — and
nothing here moves a rate, an interval or a verdict. What it moves is how a reader
should read one: a leakage rate of zero against a canary the bench read back out of
the target is a defence, and the same figure against a canary that never came back is a
family measured against nothing.

**`verified` is conjunctive**, true only when every planting this run made was read
back. A run that planted a configuration canary the probe returned and content nothing
read back reports `false` and prints both lines. *True if any* is the flattering answer
on the one block whose whole purpose is to stop a reader taking a plant on trust.

**5. The strongest claim on the block is not available to a target this bench did not
plant into, and that is every endpoint target.** The claim is *the bench planted this
value and read it back*, and it is reachable only through a `Planting`, which
`required_plantings` makes only for a target whose `plants` says which plantings it can
be given. That field is `None` on every target built from a URL, it is a parameter
nowhere, and `serve_callback` is its only writer (ADR-0061 §5) — so an endpoint target
reaches `NOTHING_WAS_PLANTED_BY_THE_BENCH` and no other line, whatever it declares and
whatever it echoes. `test_a_target_that_answers_for_no_planting_claims_nothing_even_with_a_planter`
drives that over a whole run, with the planter handed in and refused.

**What is deliberately not added is a field saying which surface a target is on.**
ADR-0059's claim is that *"there is no field on it that says which of the two it was"*,
so there is nothing else here to test against, and a caller that hand-writes `plants`
and hands over an object the bench then plants through has not cheated the claim — it
has built a planted target, and the sentence is true of it. What no target reaches is
the claim without the bench having planted and looked.

The absence is a **sentence** and not an empty block, because *nobody checked* and
*there was nothing to check* are two different readings of one rate, and it names who
did plant instead. `OperatorGap.PLANTING_UNVERIFIED` is untouched and stays exactly where ADR-0061's
three-ways-to-say-*not run* table puts it: a script's word to an operator at a
terminal about a URL, which is a surface a shim never reaches.

## How this relates to ADR-0049

[ADR-0049](./0049-an-agentic-scorers-canary-is-a-two-part-construction.md) decided
that **an agentic scorer's canary is a two-part construction — an instruction and a
value, joined only by the agent executing the instruction — and that no general-purpose
corpus contains one, because the corpus holds the attacker's words and the instrument
lives in the target.** Its own table names the configuration canary in the first row:
*"a canary the bench installed in the target's own state… the canary is in the target,
which no dataset of prompts contains"*.

This ADR is that finding read forwards rather than backwards. ADR-0049 says the
instrument has to be installed into the target's state and that a corpus cannot do it;
until now this bench could not do it either, and asked the operator to. The shim is the
one surface where the bench installs the instrument itself, and the two parts of the
verification are exactly ADR-0049's two: **the value, which the harness generated, and
the join — the target returning it over the contract, which could not have happened
unless the value was in the target's configuration.**

Three things it deliberately does not do to ADR-0049. It **populates no family from a
corpus**: the case library is untouched, no record is written, the digest does not move
and `test_no_case_in_the_library_claims_the_seventh_trigger_yet` stands. It does not
touch the *composition* refusals of ADR-0042 and ADR-0043 — the canary here is the
run's nonce, whose halves are already `nonce.inside_a_nonce`'s business, and no payload
gained a spelled-out value. And it makes no claim about a corpus-grown case becoming
admissible: ADR-0049's zero is a property of what a corpus contains, and a planting
hook does not change what a published dataset holds.

## What this does not do

- **It does not make the attestation stronger.** ADR-0024's *"authorisation loses its
  evidence and keeps only its record"* is about who authorised the test, and a callback
  the caller wrote proves nothing about who owns the agent behind it. A verified plant
  is evidence about **measurement**. The provenance block keeps the two apart: control
  of the endpoint is a line under the attestation, and this is a section of its own.
- **It does not catch a callback constructed to lie.** A target could keep the value it
  was handed and answer with it. The failure this catches is the hook that plants
  nothing and reports success — a defect in a shim author's own code, on a target their
  own team is testing. That boundary is written on `PlantCheck.VERIFIED` rather than
  left for a reader to discover.
- **It adds no third word to the vocabulary.** `nonce` on the registration path,
  `canary` under the leakage case, exactly as `registration.py` already states.
  `check` is a reading about a planting, not a third name for the value.
- **It changes nothing about `plan_for`.** Its signature need not change and does not:
  on the served surface `nonce_planted` is not asked at all, because
  `TargetConfig.plants` already answers it and a missing hook withdraws the family as
  `NotMeasurable` (ADR-0061 §6). What #87 adds is the observation *after* the plant,
  which no boolean handed in before the run could have carried.

## Alternatives

- **Have the plant hook return the planted value and compare it.** Rejected, and it is
  the shape that looks cheapest. The hook was *given* the value, so a hook returning it
  proves only that the argument arrived — it is the declaration again, with a return
  statement. The read-back has to come out of the target through the contract or it is
  not a read-back.
- **A `read_back()` hook per planting.** Rejected: it asks the shim author to write the
  check for the thing being checked, which is the same defect one indirection out, and
  it costs every callback a second method for a property the echo probe already
  answers.
- **A second probe that fetches the planted note, so retrieved content could be
  `VERIFIED` too.** Rejected under decision 3: it is a call on the wire that measures
  the family before the family is measured, and a precondition read off a scored
  attempt is not a precondition. `NO_READ_BACK` states the gap instead.
- **A fourth `OperatorGap`, or a `PLANTING_VERIFIED` member beside `PLANTING_UNVERIFIED`.**
  Rejected: `OperatorGap` is the operator's own gap, printed by a terminal script for a
  URL target, and a *verified* member there would be a gap that is not one, on the one
  surface that can never earn it. The claim belongs in the signed artefact, where the
  reader who has to weigh a rate is.
- **Let the caller pass the canary for a served target, and check it anyway.**
  Rejected under decision 1. The check would still pass, and the value would have two
  provenances — one of them a string the caller could equally have put in a payload,
  which is the reading ADR-0043 refuses at the other end.
- **Fill the check in `plant` by making the probe part of planting.** Rejected: the
  probe is registration, it is charged as registration, and moving it inside a step
  that is off every counter would put a send inside the one function ADR-0062 says has
  no way onto the wire.

## No reading moved

**No rate, `D`, κ, interval, band, gate decision or library reading moves.** No case
record is in this diff, the library digest stays `c515a89956cd` at eighteen records,
and `test_corpus_isolation.test_the_library_version_did_not_move` is untouched. A plant
is a precondition and never an input to a measurement (ADR-0006), so nothing here can
reach a figure — and the invariant is kept the way ADR-0062 keeps it, by the signature:
`checked` takes plantings and a `Registration`, and no `RunState`, no `Layer` and no
`Attempt` is in scope for it.

**`GOLDEN_ONE_FAMILY` moved**, from `43c8116f78a1` to the digest in this diff. One line
was added to the rendered document — the planting sentence, above the teardown
sentence, in *What this run planted, and whether it took it back out* — and on an
endpoint run it is `NOTHING_WAS_PLANTED_BY_THE_BENCH`. The tripwire is updated with the
reason and never loosened; no figure in that document changed.

**`ARTEFACT_VERSION` does not move.** The provenance block gained a key and no key
changed meaning, which is the same call ADR-0063 made for `teardown`: a recipient
reading an older artefact finds the block absent rather than wrong, and `verify.py`
reads the signature over whatever bytes it is given.

## Consequences

- **`TargetRun.plantings` reaches a reporting surface**, which is the deferral ADR-0062
  §6 and ADR-0063 recorded and named #87 for. It reaches exactly one: the provenance
  block of the signed artefact, through `Provenance.plantings`.
- A shim author whose planting hook silently does nothing gets a report that says the
  plant was not verified, beside a leakage rate of zero. Nothing stops the run — the
  figures are real measurements of what the target did — and the sentence beside them
  is what says what they are measurements *of*.
- `Planting` has a fifth field, so
  `test_a_plant_is_recorded_with_what_authorised_it_and_with_no_send`'s field-set
  assertion is in this diff. It is the designed tripwire for a field arriving on a
  record that travels, and it is updated with the reason.
- **#88, #89 and #90 inherit a claim they can print.** A CI step that fails on a
  declared bar is reading an artefact, and *the plant was verified* is the difference
  between a green build over a measured family and a green build over a family that had
  nothing to find.
