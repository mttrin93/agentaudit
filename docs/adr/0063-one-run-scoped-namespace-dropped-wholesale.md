# ADR-0063: One run-scoped namespace, dropped wholesale, so no run leaves the store poisoned

**Status:** accepted (#86, group J / #81)
**Date:** 2026-09-05

## Context

ADR-0062 made planting a pre-run step: `planting.plant` calls the operator's hooks
before the registration probe, authorised by the attestation and charged to nothing.
What it did not decide is **where the plant goes**, and so what it takes to get it
back out. That half was left open on purpose — there was no `teardown()` in that diff
and an ADR deciding a namespace nothing created would have recorded a decision nothing
carries out. This is the other half, and it is not an amendment to ADR-0062: nothing
there is edited to say something it did not decide.

A plant writes into somebody's vector store, content folder or system prompt. **The
bench must be able to take it all back out, and the way to be able to is to have put
it all in one place.** The alternative is *delete what we wrote*, which needs a
manifest — a second copy of what was planted, held in this harness, going stale — and
which leaves a poisoned document behind the moment one delete of many fails. A
partial, silent failure is the worst shape this could have: the run's figures are
unaffected either way, so nobody rereading the report has any reason to go looking.

The reference agents already had the small version of the same defect.
`create_reference_app` held `nonces: dict[str, str]`, one slot per agent, for the life
of the process: a second run's registration overwrote the first's planted value and
nothing ever removed either. That is test equipment demonstrating the opposite of the
contract the user-facing hooks are about to be held to.

## Decision

**1. One namespace per run, `run-<id>`-shaped, derived and never stored.**
`planting.namespace_for(run_id)` returns `run-` plus the run id, and
`run_calibration` derives it once at the top of the run — from `TracedRun.id` where
the caller holds a run record, and from `planting.anonymous_run_id()` where it does
not, which in practice is this suite. It is **one per run and not one per target**:
what it scopes is *this run's writes into somebody's store*, and a namespace per
target would be a list of things to drop again.

The value reaches every hook **as an argument** — `plant_config_canary(namespace,
canary)`, `plant_retrieved_content(namespace, key, body)`, `teardown(namespace)` —
and is stored on the shim between the two calls by nothing. A shim that remembered it
is a shim whose teardown can run against a namespace a *later* run created, which is
the one way this mechanism could delete somebody else's data rather than its own. A
run id that could not be a namespace is **refused rather than sanitised**
(`namespace_for` accepts letters, digits, dot, dash and underscore): a name quietly
rewritten on the way in is a name `teardown()` may not recognise on the way out.

**2. `teardown()` runs on every exit path, from a `finally` on the run.** Not a line
at the end of the happy path — the runs that end badly are exactly the runs that leave
somebody's store holding what this bench put in it. The list is the decision, and each
member is held by a test in `backend/tests/test_run_namespace.py`:

| How the run ended | What still drops the namespace |
|---|---|
| A clean finish | the `finally`, on the ordinary path |
| The approval checkpoint declined (ADR-0028) | the `finally` is outside `run_under_approval`; nothing was planted and the namespace is dropped anyway |
| A plant that raised — `PlantingFailed` (ADR-0062 §5) | the `finally`; a half-finished plant is the case that most needs it |
| A raise inside the run *after* a plant landed | the `finally`; the second target's failure does not strand the first target's plant |
| A `TargetUnreachable` that outlived the retry policy | the `finally`; the plant is ahead of the registration probe, so it landed before the target was ever reached |
| A budget breach mid-run — `BudgetExceeded` (ADR-0007) | the `finally` |
| A cancellation | `finally` and not `except Exception`: a `KeyboardInterrupt` is not caught anywhere on the way out and the drop happens as it passes |
| A registration that never completed | the run returns normally having measured nothing, and the plant that preceded the probe is dropped |

**Every planter is asked, not only the ones something was planted through.** A plant
that raised halfway through a target's requests left the earlier ones in place, and a
teardown that visited only the targets whose plant *finished* would leave exactly
those behind. A wholesale drop of a namespace that was never created is a shim
author's no-op — it is stated in the hook contract — so the safe direction is to ask
everybody, and the alternative is the harness deciding per exit path whether cleanup
applies, which is a branch that goes wrong on the path nobody tests.

**`teardown` never raises.** It is called from a `finally` that is very often
unwinding the exception that is the run's actual answer. A cleanup that raised there
would replace the reason the run ended with the reason its cleanup failed, and the
operator would lose the first to learn the second. Both are kept: the original
propagates and the teardown comes back as a record. That guarantee is **one wrapper
and not one per call site** — `planting.drop_namespace` — because the drop is reached
two ways: as a method found on the operator's object, and as a plain callable where
the equipment is over HTTP. A second copy beside the second caller is a second place
for the guarantee to be forgotten, and `scripts/attack.py` goes through the same
wrapper for that reason.

**3. A teardown that failed is a named outcome, and it reaches the artefact.**
`TeardownFailure` has two members — `HOOK_MISSING` and `HOOK_RAISED` — and there is
deliberately no `NO_PLANTER`: a run holding no object to tear down planted nothing
with one either, and *nothing to drop* is not a failure to drop it. `Teardown` carries
the namespace, whose planter it was, the member and the operator's own error text, and
travels on `CalibrationResult.teardowns`. **`error` is only ever the operator's own
words**: `HOOK_MISSING` carries none, because no call was made and there is nothing of
theirs to quote, and `TeardownFailure.stated()` already says the whole of it.

**The run's numbers are unaffected and that is exactly why the report has to say it.**
Every attempt was made, every verdict stands, no rate, interval, band or `D` moves —
so a reader comparing figures would never find out on their own that this bench left
content in their store. Silence here is the one failure mode that costs somebody
something after the run is over. So `Provenance.teardown` sits in the provenance
block, which is where *how this was made* lives, and section 2 of the rendering
prints one line whichever way it went.

**The namespace travels only when the drop failed.** On a run that cleaned up there is
nothing for a reader to do with the name, and it is derived from the run id — an
identifier the signed artefact does not otherwise carry (ADR-0018). On a run that did
not, the name is the whole of what makes the sentence actionable: it is what the
operator types to find what is still in their store. The **error text is the
operator's own words**, which is the one place in this bench where an exception's
message travels into a document. ADR-0008 keeps payloads and replies out of an
artefact that leaves the building; this is neither. It is the operator's cleanup code
failing against the operator's own store, in a document written for them, and a fixed
sentence in its place — ADR-0059 §2's answer for a callback that raises *on the wire*
— would leave them with a poisoned store and no idea why.

**And a run that planted nothing says so.** `planting.NOTHING_WAS_PLANTED`, printed
rather than omitted, on `PLANTING_CALLS = 0`'s reasoning: a document that said nothing
about the cleanup leaves a reader deciding for themselves whether this bench put
something in their store and did not take it out.

**4. A shim with plant hooks and no `teardown()` is refused at construction.**
`serve_callback` raises `PlantsWithNothingToDropIt` before a port is bound, and
**refused is not withdrawn**. Withdrawal is the answer for a family the shim cannot
support — no hook, `NotMeasurable`, the run carries on and measures the rest
(ADR-0061). This callback *can* support the family; what it cannot do is clean up
afterwards, and a bench that quietly measured it would be trading an operator's store
for a rate they never agreed to pay that for. The check is on the **pair** and not on
teardowns as such: a callback with no planting hooks needs none, which is the ordinary
case and is served exactly as it was before.

What this asks of a shim author is one sentence in the hook contract, and it is
`DropsItsNamespace`'s docstring: *the namespace is yours to create and yours to drop,
and nothing outside it is ours.*

**5. The reference agents get the same shape, and so does `PlantNonce`.** The app's
nonce store becomes `dict[str, dict[str, str]]` — namespace, then agent — `PUT
/reference/{agent}/nonce` takes the namespace in its body, and `DELETE
/reference/namespaces/{namespace}` drops one run's plants wholesale. A message reads
the most recent *live* namespace holding a value for that agent, so a dropped
namespace can never answer for one that was not, which is the property the drop exists
to have.

`PlantNonce` widens from `(target, nonce)` to `(target, nonce, namespace)` and gains
`DropNamespace` beside it, wired through `run_calibration` and called from the same
`finally` the shim teardowns are. The namespace is an **argument** and not a value the
planter was built with, for decision 1's reason — a planter holding one between the
plant and the drop is a planter whose drop can run against a later run's namespace.
`console.interactive_planter` accepts it and prints nothing: a person who pasted two
lines into a system prompt takes them out by deleting them, and a name nobody can act
on is an instruction with no action.

The equipment's own `Teardown` carries `target_name=None` and so never reaches a
target's artefact. It is test equipment, and a target's signed document is not the
place to report on the bench's fixtures.

## Consequences

- **Nothing about an endpoint run changes.** A URL target's `plants` is `None`, no
  planter is handed over, `teardown_all` visits nobody, and the artefact prints
  `NOTHING_WAS_PLANTED`. The operator's hand-planted nonce is in no namespace and no
  teardown touches it, exactly where ADR-0024 left it.
- **A plant stays off every counter, and so does a teardown.** ADR-0062 §2 enumerates
  ten and what holds each; every one of them is held here by the same absence.
  `teardown` takes no `RunState`, no `Layer`, no `Case` and no `Attestation`; it
  constructs no `Attempt` and no `Transcript`; it reaches no model and no
  `UsageLedger`; `PLANTING_CALLS` stays `0` and no ceiling moves. The hook is a method
  on the operator's object and the served app still has one route, so there is no way
  onto the wire — `test_the_planting_module_names_no_counter_and_no_way_onto_the_wire`
  walks the import graph of `planting.py` and the teardown lives in that module.
- **Nothing here writes into a scored rate.** A teardown happens after every verdict
  is reached and changes none of them; a refusal at construction changes which
  families are *attempted* and never what an attempt measures (ADR-0006, ADR-0010).
- **`GOLDEN_ONE_FAMILY` moves**, for the thirteenth recorded time, because section 2
  of the rendering gains a subsection: *What this run planted, and whether it took it
  back out*. The tripwire is updated in the same diff as the wording that moved it,
  with this as the reason, and it is not loosened.
- **`ARTEFACT_VERSION` does not move.** `teardown` is an additive key in the
  provenance block; no key is removed, renamed or re-typed, and a verifier reading the
  previous shape reads every field it read before. That is the footing #43 set for the
  `elective` block, #47 for `claimed_in_part`, #45 for `edition` and #79 for
  `selection`.
- **`TargetRun.plantings` still reaches no reporting surface**, and it now carries the
  namespace each plant went into. What reads it is #87.
- **#87 has its seams.** The hooks take `namespace` first; the value handed to
  `plant_config_canary` is still the run's own registration nonce and the probe after
  it is still where the echo is read; `Planting.namespace` says where it went.

## No reading moved

No rate, interval, band, `D`, κ or admission reading is touched. **The library digest
does not move** and stays `c515a89956cd`: no case record is edited in this diff, and
the eighteen and the three are the same eighteen and three. No variant is admitted
here — that needs a person at a tty (ADR-0052 §5). `PLANTING_CALLS` stays `0`, no
`scored_ceiling` or `adaptive_ceiling` changes, and no confirmed estimate is
invalidated. The one tripwire that moves is `GOLDEN_ONE_FAMILY`, above, and it moves
because a document gained a line and for no other reason.

## Alternatives

**Delete what we wrote, item by item.** Rejected under Context. It needs a manifest to
be correct, the manifest is a second copy of what was planted and it goes stale, and
its failure mode is a poisoned document nobody hears about. Dropping a namespace is
one call whose failure is total and visible.

**A namespace per target rather than per run.** Rejected under decision 1. It buys
nothing — the thing being scoped is a run's writes — and it turns one drop into a list
of drops, which is the design this ADR exists to reject at a smaller scale.

**Store the namespace on the shim at plant time and let `teardown()` read it.**
Rejected under decision 1. It is one field away from a teardown that runs against a
namespace a later run created, and the failure would be a shim deleting live data
rather than its own.

**Withdraw the plant-dependent families from a shim with no `teardown()`, rather than
refusing the shim.** Rejected under decision 4. Withdrawal is what a *missing
capability* reads as, and this shim has the capability; a reader who cannot tell the
two apart cannot act on either. It would also mean the bench silently declining to
measure a family the operator wrote a hook for, with the reason buried in an absence.

**Raise out of `teardown()` when the drop fails.** Rejected under decision 2. It runs
in a `finally` that is usually carrying the run's real answer out, and replacing that
answer with a cleanup error costs the operator the more important of the two.

**Keep the failure off the artefact and log it.** Rejected under decision 3. The
operator is the only person who can act on a poisoned store, the report is what they
read, and a log line on a runner nobody keeps is the silence this decision is against.

**Print the namespace in the document on every run.** Rejected under decision 3. It is
derived from the run id, which the signed artefact does not otherwise carry
(ADR-0018), and on a run that cleaned up there is nothing to do with it.

**Leave the reference agents' `nonces` as they were, since they are test equipment.**
Rejected under decision 5. The equipment is what the suite and the gate exercise the
protocol through, and equipment demonstrating the opposite of the contract is where a
regression in the contract goes unnoticed.
