# ADR-0061: A plant is a precondition the bench can check, so a missing hook is `NotMeasurable` and not a `DeclaredGap`

**Status:** accepted (#84, group J / #81)
**Date:** 2026-09-05

## Context

Two families need an artefact in place before their attack turn. Data leakage
extracts the registration nonce the operator planted in the target's *configuration*
(ADR-0007); indirect prompt injection — and the elective memory-poisoning tier —
needs third-party content in what the target *retrieves*. `POST {message,
session_id}` cannot put either there.

So the plant has been a sentence. `plan_for` reads two booleans, `note_planted` and
`nonce_planted`, and withdraws the family when either is false —
`DeclaredGap.NOTE_NOT_PLANTED` and `NONCE_NOT_PLANTED`. When either is *true*,
nothing checks it, and `OperatorGap.PLANTING_UNVERIFIED` says so in the operator's
own words: *"the bench cannot see your content store, so that the note is planted and
that the payload's wording retrieves it are both your statement rather than something
measured here"*. ADR-0024 accepted that trade out loud — *"that guard moves from a
mechanism to a sentence"*.

This bench now has three ways to say *not run*, and they are told apart by **whose
gap it is and whether the bench detects it**:

| Type | Whose gap | Detected here | Where |
|---|---|---|---|
| `NotMeasurable` | the target's capability | **yes**, from the record and the declaration | `bench/measurability.py` |
| `DeclaredGap` | the caller's setup | no | `api/run_status.py` |
| `OperatorGap` | the operator's setup, at a terminal | no | `scripts/probe_target.py` |

ADR-0059 added a fourth surface: `serve_callback` wraps a user's Python object in a
FastAPI app and yields a plain `TargetConfig`. **On that surface the bench holds the
object.** A served target either implements a planting hook or does not, and that is
readable before a single message is sent — the same argument `exposes_tool_calls_of`
already makes about tool-call visibility, over a different property.

ADR-0060 put the content itself on the case record, so there is now something
definite to plant: `PlantedArtefact` carries the `key`, the `body` and the canary's
two halves.

## Decision

**1. A plant is a `Precondition`, and it lives in the machinery `Precondition`
already has.** `Case.requires` carries it, `unmet_preconditions` asks it before an
attempt is spent, `runnable` and `not_measurable_families` and `plan_for` gain no new
branch. That last clause is the argument for this design in one sentence: the bench
already knows how to withdraw a family for something the target cannot do, name the
reason, and refuse to print a rate of zero, and a plant is that kind of thing.

**2. One `Precondition` member per plant, not one `PLANT_HOOK`.** `Plant`, a closed
`StrEnum` in `library.py`, has `CONFIG_CANARY` and `RETRIEVED_CONTENT`; `Precondition`
gains `CONFIG_CANARY_PLANT` and `RETRIEVED_CONTENT_PLANT`, and `Plant.precondition`
is the join. *Which* hook is missing has to reach the report, because "implement a
hook" is not an instruction anybody can carry out: the two hooks are written in two
different places by two different people, and `NotMeasurable.stated()` prints the
name of the one to write.

**3. `PlantedIn` stays, and is the subset of `Plant` a record may carry.** The two
enumerations spell their shared member the same way and `PlantedIn.plant` is the
lookup. They are not merged, because `Plant.CONFIG_CANARY` has no counterpart a
record may name — the nonce is issued per run, so a record naming it would name a
value that changes (ADR-0007) — and a merged enumeration would make
`where = "config_canary"` a thing a record could say and something would have to
refuse it.

**4. Two members and not three, and a member is a record rather than a branch.**
CONTEXT.md names a session-memory planting; the case that needs it arrives with #48,
and a member no case requires is vocabulary nobody can drive red. What makes a third
member cheap is that everything about a `Plant` is read off the member: its
precondition from its value, its hook name from `shim.hook_name`, its withdrawal
sentence from `stated()`, and its reason from `REFUSED_FOR`, which is asserted total.
`_PLANT_HAS_A_PRECONDITION` runs at import, and
`test_plant_precondition.py` asserts each join over the whole enumeration. So #48 and
#50 add a member, a protocol and their records — the objection #81 raised against a
hardcoded pair.

Two things a new member still costs prose. `Plant.stated()` and
`NotMeasurable.stated()` are sentences a person writes, because the wording round a
gap is not derivable from a member's name. The second **spells the hook out** rather
than interpolating `hook_name`, so that the sentence reads as English; the test asserts
the name appears in it, which is what keeps the two spellings one fact.
`Plant.stated()` has no production caller in this ticket — the operator-facing copy
that prints it is #85's setup step and #87's console line, and it is written here
because the issue asks for it beside the member it belongs to.

**5. A shim declares its hooks from what it implements, at construction.**
`declared_plants` reads the callback with `hasattr`/`callable` and `serve_callback`
puts the answer on `TargetConfig.plants`. There is no parameter for it, on ADR-0059
§2's terms: a target that could be *told* it plants would be ADR-0024's sentence
again, on the one surface where the bench can check instead. It is read once, before
the run — a hook discovered missing halfway through a family is a family
half-measured, and the attempts already spent came back resisted against content that
was never planted.

**6. `TargetConfig.plants` has three states, and the third is the whole of the
decision.** A member present is *can*; a member absent from a set is *cannot*, which
withdraws the family; and `None` is **this target does not answer for its own
plantings**, which is every target that is a URL. `can_be_planted` returns `True` for
`None`, and `plan_for`'s two `DeclaredGap` members decide for those targets exactly
where ADR-0024 left them. Two surfaces, two truthful answers, and no third type: a
gap the bench *detects* is `NotMeasurable`, and a gap it can only be told about is a
`DeclaredGap`.

**7. Every record declares the plantings it needs, and the committed library
declares no others.** `Case._refuse_a_plant_the_record_does_not_require` reads the
need off two facts the record already carries — a success-condition kind in
`PLANTED_IN_THE_CONFIGURATION`, and the `where` of a `PlantedArtefact` — and never
off the family, so a case that moves families cannot change which planting it asks
for. Nine records are in the diff: three data-leakage, three indirect-injection,
three memory-poisoning.

The refusal on the record runs **one way**. A case that needs a planting and does not
declare it is the fault with teeth — it is attempted against a target that cannot be
planted and comes back a clean zero that reads as a defence. A case declaring a
planting it does not need costs only coverage, and is caught over the committed
library instead, by
`test_every_committed_case_asks_for_exactly_the_plantings_it_needs`. Both directions
as a record refusal was written and withdrawn: it makes a fixture built by
`replace`-ing another case's success condition unrepresentable, which is how most of
this suite's cases are built, and the property it buys is one no library record can
reach.

## Consequences

- A user whose callback implements neither hook is measured on the four families that
  need no planting and told, per family, which hook to write. Their report carries a
  named absence and not a zero — `payload.py`'s three-kinds-of-nothing rule covers
  this without amendment, because the new reasons are `NotMeasurable` members and
  that section already prints the reason that closes the gap.
- The two `DeclaredGap` members are untouched, and so is `OperatorGap`. Nothing about
  an endpoint run changes: an endpoint target's `plants` is `None`, every case in the
  library is still measurable against one, and the caller's declaration still decides.
- Nothing here writes into a scored rate. A shim declaring fewer hooks changes which
  families are *attempted* and never what an attempt measures — ADR-0006, and
  ADR-0024's own wording: *this is a precondition of measurement, not an input to
  one*. The adaptive layer is not involved at any point (ADR-0010).
- **No plant arrives as an attempt.** A hook is a method on a user's object; the
  served app still has one route, and nothing in the bench calls a hook yet.
  `test_no_planting_hook_is_reachable_over_the_wire` asserts that against the app's
  own routes, so a route added for a planting fails there whatever it answers.
- #85, #86 and #87 have what they need: the vocabulary, the hook names, the protocols
  spelling out their signatures, and a `TargetConfig` that already says which
  plantings this target can be given. What none of them may do is call a hook from
  inside `send_message`.

## No reading moved

**The library digest moved**, from `81ff91682cfc` to `c515a89956cd`, on #65's, #72's
and #83's precedent. Nine records are in the diff and each gained one entry in
`requires`; the count is still eighteen in the six and three in the tier, which is
what says no case was written and no payload edited. `requires` is a precondition and
never an input to a measurement, so no `D`, rate, interval, band or `[[history]]`
block moves and no admission reading is invalidated.
`test_corpus_isolation.test_the_library_version_did_not_move` is the designed
tripwire and this is the designed answer: it is updated with the reason and never
loosened. `GOLDEN_ONE_FAMILY` does not move — no rendered document changed.

## Alternatives

**A fourth type, `PlantHookMissing`.** Rejected: the table above is not four rows
long because there are four vocabularies, it is three rows long because there are
three answers to *whose gap is it and can the bench see it*. A missing hook answers
those two questions the same way `NO_TOOL_CALL_VISIBILITY` does.

**Keep the plant a `DeclaredGap` on every surface.** Rejected: on the served surface
the bench can check, and a bench that declines to check what it can see is the soft
answer ADR-0004 refuses arriving under a different name. It would also mean a served
run whose caller said *planted* and whose callback had no hook spends thirty attempts
against a value that is nowhere in the target and reports a clean zero.

**One `Precondition.PLANT_HOOK` for both plantings.** Rejected under decision 2: the
report would name a gap nobody could act on, and the two hooks are not one gap.

**Merge `PlantedIn` into `Plant`.** Rejected under decision 3.

**Declare the plantings as `serve_callback` parameters.** Rejected under decision 5:
it reintroduces the operator's word on the one surface that does not need it, and it
would let a target declare a hook it does not have — which fails at run time, halfway
through a family.
