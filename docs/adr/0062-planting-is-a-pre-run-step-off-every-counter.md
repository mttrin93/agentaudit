# ADR-0062: Planting is a pre-run step, off every counter, and never through `send_message`

**Status:** accepted (#85, group J / #81)
**Date:** 2026-09-05

## Context

An **attempt** is the unit of the denominator, a **send** is one message on the wire,
and both are counted. `RunState.authorise_call` and `record_call` take a `Layer` and a
number of sends, and the budget refuses a call the declared ceiling does not cover
(ADR-0007). **A plant is neither**, and nothing in this bench said so until now.

ADR-0061 gave the vocabulary: `Plant`, its `Precondition`, `TargetConfig.plants`, and
two protocols — `plant_config_canary(canary)` and `plant_retrieved_content(key, body)`
— spelling out hooks that *nothing called*. This decides what calls them, when, and
what may not move when they do.

The cheap implementation of a plant is a message. `PUT /reference/{agent}/nonce` is
already a second route on the reference app for exactly this reason, and it exists
*outside* `POST /messages` rather than as a special first turn. The same instinct at
the shim would be a planting turn through `send_message`, and then three things follow
at once:

- the plant is a `Transcript`, so it has a `sends`, so it is charged to a `Layer`, so
  it moves an operator's confirmed estimate for a call that attacks nothing;
- the plant is a turn in a session, so a target with session state has seen the canary
  *arrive in conversation* — which is the memory-poisoning planting (#48) wearing the
  configuration planting's name, and CONTEXT.md separates those three precisely so
  that cannot happen silently;
- and there is a route by which an attempt could plant, which is the one thing that
  makes the leakage family's arithmetic unreadable: a canary planted by the attack it
  is measuring.

The precedent is already in the tree and is the shape this generalises.
`calibration.plant_nonce` — the test-equipment stand-in for the human who edits their
own target's configuration — is already called from `_run_target` between the nonce
being issued and the registration probe, and is already charged to nothing. What it
cannot do is read a case record, answer for a target that says which plantings it can
be given, or fail in a way anybody can act on.

## Decision

**1. `plant(...)` runs from the harness, before the run, and takes no `RunState`.**
`backend/bench/planting.py` holds it; `calibration._run_target` calls it. Not "takes
one and does not charge it" — **takes none**, so there is no counter in scope to move.
The invariant is carried by the type, which is the standing rule's own shape: *if you
find yourself widening a signature to accept both, stop* (ADR-0010). The module names
no counter at all — no `RunState`, no `Layer`, no `Attempt`, no `Transcript`, no
`send_message` — and `test_the_planting_module_names_no_counter_and_no_way_onto_the_wire`
asserts that over its import graph, because a name is a route.

**2. The counters a plant stays off, and what holds each one.** They are enumerated
here rather than left to a reader to find, because *off every counter* is only a claim
if the list is written down:

| Counter | Where | What holds it |
|---|---|---|
| Per-layer spend | `RunState.spent`, through `authorise_call` / `record_call` | no `RunState` in the signature; no `Layer` named in the module |
| Attempts — the denominator | `RunState.attempts`, `RunState.record` | `plant` constructs no `Attempt`; `Planting` is a different type with no `sends` and no `Transcript` |
| Adaptive episodes | `RunState.episodes` | the plant is in the scored half's setup and the adaptive layer runs strictly after the suite (ADR-0010) |
| Scored and adaptive position | `RunState.position`, `episode_position` | the same absence: both are moved through `RunState` |
| Sends on the wire | `Transcript.sends`, set by `send_message` | the hook is a method on the operator's object; the served app has one route and a hook is not on it (`test_no_planting_hook_is_reachable_over_the_wire`, ADR-0061) |
| The declared ceiling and the estimate | `RunBudget.declare`, `REGISTRATION_PROBES_PER_TARGET + attempts` | `PLANTING_CALLS = 0`, itemised — decision 5 |
| Provider tokens and cost | `UsageLedger`, `ModelUsage` | a plant reaches no model, and `plant` takes no `Completion` and no `UsageSink` |
| The trace's call figures | `Field.CALLS_SCORED` / `CALLS_ADAPTIVE` | read off `RunState.spent`, so held by the first row |
| Every published rate | `TargetRun.rates`, `scorer.py` | computed over `attempts`, so held by the second row |

**3. A planting call is authorised by the attestation, and by nothing else.**
`plant` takes an `Attestation` and it is a required argument for the reason
`register`'s is: a plant writes into the operator's own configuration or content
store, so there is no point in this flow at which the bench may touch their systems
without one. **Authorised and counted are different questions**, and this is the one
place in the bench that answers the first *yes* and the second *no*. That is also why
the attestation comes first in the ordering: a plant is already an act on somebody
else's system, and it happens before the probe rather than after it.

What is recorded is `Planting` — the planting, the record that asked for it, and the
`AttestationRecord` that authorised it — carried on `TargetRun.plantings`. It holds no
`Layer`, no `sends` and no `Transcript`, so a reporting surface that reached for it
would find nothing a rate could be denominated on. It holds no artefact body either:
the content is on the case record, and a signed artefact is not a place for payload
text (ADR-0008, ADR-0060).

**4. The ordering, stated once: attestation → nonce issued → plant → registration
probe → run.** The probe is after the plant because the echo is what proves the plant
landed (#87). The attestation is first for decision 3's reason. `_run_target` is where
this is spelled out, and `applicable` moved above the plant so that a run does not
file content into somebody's store for a case its agent type was never written for.

**5. A plant that does not happen stops the run before the first attempt, under its
own named outcome — and a withdrawal is not one of them.** `PlantingFailure` has three
members, and every one of them is a target that *said it could be planted* and was
not: `NO_PLANTER` (the run holds no object to plant with), `HOOK_MISSING` (the object
handed in is not the one that was served), `HOOK_RAISED` (the hook exists and threw).
`PlantingFailed` carries the member and propagates out of `run_calibration`.

A failed plant is deliberately **not** a withdrawn family. Withdrawal is for a hook
that does not exist — `NotMeasurable`, through `unmet_preconditions`, and the run
finishes and measures the families that need no planting (ADR-0061). This is a hook
that exists and did not work. A reader who cannot tell those apart cannot act on
either: one of them writes a hook and the other fixes the hook they wrote.

`NO_PLANTER` is a refusal rather than a skip, and that is the sharp one. The cases
that asked for the planting are `runnable` against this target — `can_be_planted` said
yes — so a run that quietly planted nothing would spend every one of their attempts
against a value that is nowhere and print the clean zero that reads as a defence,
which is the failure ADR-0061 exists to make impossible.

**6. The estimate itemises the plant at zero.** `PLANTING_CALLS = 0`, a `RunBudget.planting`
figure, a line in the table an operator confirms and a key in `BudgetPayload` so the
terminal and the browser show the same figures. A line reading zero rather than a line
that is absent: the pre-run estimate already itemises the registration probe, and a
planting step missing from the table would leave a reader to decide for themselves
whether it had been priced in somewhere they could not see. The figure is a literal
and not arithmetic over the run — there is nothing a caller can pass that makes it
non-zero — which is what makes the line a statement of the invariant rather than a
reading of it, and makes the number the tripwire for a plant that ever became a send.

**7. What is planted is read off the records, and off nothing else.**
`required_plantings` walks the cases that will actually be attempted and reads two
facts: the preconditions each record declares, and `TargetConfig.plants`. The
configuration canary is planted **once** however many cases need it — one nonce per
run, one planted value in two roles (ADR-0007) — and retrieved content once per
record, from `PlantedArtefact`'s own `key` and `body` (ADR-0060). Nothing reads the
family, so a case that moved families cannot change which planting it asks for.

**And this is the one place ADR-0061 §4's *no `if` anywhere moves* gains an
exception.** The arguments a hook takes are not derivable from a member's name — one
takes the run's nonce, the other takes a record's `key` and `body` — so
`planting._request_for` has one arm per member. It is a `match` with no fallback arm,
in the house style `Plant.stated` and `TargetFailure.stated` already use, so a third
member fails the type check there rather than defaulting onto one of the two shapes
and planting the wrong thing. `Plant`'s own docstring is amended to say so; one
branch, in one named place, guarded by the type checker, is what #48 and #50 cost
here.

**A target whose `plants` is `None` is planted by nobody.** That is every target that
is a URL: it does not answer for its own plantings, its operator plants by hand, and
`plan_for`'s `NOTE_NOT_PLANTED` / `NONCE_NOT_PLANTED` decide for it exactly where
ADR-0024 left them. An endpoint run performs no act of its own here, and
`TargetRun.plantings` is empty for one — a fact, not a missing field.

**8. The hook name moves to `Plant.hook`, and `shim.hook_name` delegates to it.**
ADR-0061 §4 put the derivation in `shim.py`, where the reader was the shim. The reader
is now also the harness, and `shim.py` builds a FastAPI app and imports the reference
agents' own modules — so a harness that had to import it in order to spell
`plant_config_canary` would put the shim and a web server in the import graph of every
run, endpoint runs included. `shim.hook_name` keeps the name ADR-0061 gave it and
returns `plant.hook`; there is still exactly one spelling. This is more of what §4
asked for, not less: the precondition, the sentence, the reason and now the hook are
all read off the member.

**9. The caller hands the object over, because the caller is the only thing that
holds it.** `run_calibration` gains `planters: Mapping[str, Planter] | None`, keyed by
target name, beside the `planted_nonces` it already has for the same reason.
`serve_callback` yields a plain `TargetConfig` and nothing more specific (ADR-0059), so
the object with the hooks on it stays with the caller. It is the *object* that is
handed over and not a function, because which hooks it has is already recorded on
`TargetConfig.plants` and read once, at construction (ADR-0061 §5).

## Consequences

- Nothing about an endpoint run changes. A URL target's `plants` is `None`, nothing is
  planted, no counter moves, and the operator's declaration still decides through
  `plan_for`. The `plant_nonce` stand-in is untouched and still runs where it did.
- A served target that declares a hook is now **planted by the bench**, which is what
  #87 will check the echo of. `test_callback_shim`'s raising-callback test hands its
  object over as the planter, because a served leakage target that nobody plants is
  now a refusal rather than a silent zero.
- **Nothing here writes into a scored rate.** A plant changes which families can be
  *attempted* and never what an attempt measures — ADR-0006, and ADR-0024's own
  wording: *this is a precondition of measurement, not an input to one*. The adaptive
  layer is not involved at any point (ADR-0010).
- **No second transport.** `contract.py` is untouched, `send_message` is still the one
  path to a target, and the shim's served app still has one route.
- **`TargetRun.plantings` reaches no reporting surface yet, and that is deliberate.**
  It is the record decision 3 requires, and the thing that will read it is #87 — the
  echo that proves the plant landed. Nothing in `payload.py`, `assembler.py` or the
  rendered report is touched here, so no signed artefact changes shape.
- **`PlantingFailed` is unreachable from the API today**, because a URL target's
  `plants` is `None` and `required_plantings` returns nothing for one, so no planting
  is attempted on that surface at all. `api/runs.py` would settle such a run under its
  general *the run stopped rather than produced a result* arm. Giving the named
  outcome its own arm belongs with the surface that can raise it — the headless run
  and the Action, #88 and #89 — rather than as a branch nothing can reach.
- #86 has its seam: `plant` is the one place a planting is performed, `Planting` is the
  record of what was, and a `teardown()` belongs beside them rather than inside
  `send_message`. #87 has its seam too: the value handed to `plant_config_canary` is
  the run's own registration nonce, and the probe that follows is where its echo is
  read.

## The namespace half is #86's, and this ADR deliberately does not decide it

#81 proposes one ADR for #85 and #86 — *planting is a pre-run step into a run-scoped
namespace, off every counter*. Only the first half is decided here, on purpose. There
is no `teardown()` in this diff and no namespace to drop; an ADR that decided the
shape of one would be recording a decision nothing in the tree carries out, which is
the opposite of what an ADR is for. #86 writes its own — *one run-scoped namespace,
dropped wholesale* — and it is not blocked on this one beyond the hook call it now has
to scope. What #86 may not do is amend this ADR to say something it did not decide.

## No reading moved

No rate, interval, band, `D`, κ or admission reading is touched, and the library
digest does not move: no case record is edited in this diff, and the eighteen and the
three are the same eighteen and three. `PLANTING_CALLS = 0` is a new figure and not a
changed one — it is added to the estimate an operator confirms and adds nothing to
either ceiling, so no run's `scored_ceiling` or `adaptive_ceiling` changes and no
confirmed estimate is invalidated. `GOLDEN_ONE_FAMILY` does not move; no rendered
document changed.

## Alternatives

**A planting turn through `send_message`, as the first turn of the session.** Rejected
under Context: it is charged, it is a turn a stateful target remembers, and it is a
route by which an attempt could plant.

**A second route on the served app — the shim's own `PUT /plant`.** Rejected. It is
what the reference server does and it is right *there*, because that server is test
equipment the suite operates as an operator would. On the shim it would be a second way
in to a surface whose one security property is that it has one (ADR-0059 §2), and it
would put the operator's own configuration behind a loopback URL and a bearer token for
no gain: the harness already holds the object the hook is on.

**`plant(run_state, ...)`, charging nothing.** Rejected under decision 1. It is the
widening ADR-0010 asks anyone who reaches for it to stop at, and it makes the invariant
a property of the body rather than of the signature — reviewable once, and not
thereafter.

**A failed plant as a `DeclaredGap` or a withdrawn family.** Rejected under decision 5:
a hook that does not exist and a hook that threw are two different jobs for the person
reading the run, and collapsing them sends both to the wrong place.

**Leave the plant out of the estimate, since it costs nothing.** Rejected under
decision 6: an absent line is not the same statement as a line reading zero, and the
zero is the tripwire.

**Fold the planter into `TargetConfig`.** Rejected. `TargetConfig` is a description of
a target that crosses an interrupt, is written into a run record and is compared
between runs; a live Python object on it would be none of those things, and it would
give a URL target a field that can only ever be empty.
