# Spec — A route found against a customer's agent is kept, decided, and enters the library

**Scope:** the missing half of the promotion loop. A route the adaptive layer finds against somebody's agent survives the run that found it, is measured against the admission bar on a surface of its own, and enters the case library. No change to the arithmetic of the bar; which bar a route faces is [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)'s, and for every route this surface sees it is the single-model one.

**The loop closes for one kind of run and not the other.** [ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md) made an admitted route a `.toml` record the run writes, and `scripts/swap.py` is the one entry point that walks the whole path — consult the memory, measure on the model pair its own routes are held to, decide, remember, write. Its targets are the three reference agents. A **customer run** — the console, `POST /runs`, `scripts/bench.py` — attacks somebody's real agent, and a route found there reaches one printed line and nothing else: *"faces a stated bar, and is not admitted by having been proposed."* It is not stored, not measured, and not recoverable once the run record is gone. The interesting routes are the ones the fixed suite missed against a real target, and those are exactly the ones this bench discards.

**Governing documents:** [PLAN.md](../../PLAN.md) · [CONTEXT.md](../../CONTEXT.md) · [ADR-0008](../adr/0008-repo-disclosure-posture.md) · [ADR-0010](../adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) · [ADR-0011](../adr/0011-the-adaptive-attacker-is-label-blind.md) · [ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) · [ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) · [ADR-0029](../adr/0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md) · [ADR-0032](../adr/0032-the-admission-memory-holds-the-measurement.md) · [ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md) · [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) · [ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)

**Vocabulary:** every term below is defined in `CONTEXT.md`. A **route**, a **proposal**, an **attempt** and an **admission** mean exactly what they already mean. One word this spec adds is not bench vocabulary and never enters a figure: a **pending route** is a proposal filed durably, awaiting a decision it has not had. A pending route is not a **case** — it becomes one only by clearing the bar — and it is not an **attempt**, so nothing about it reaches a denominator ([ADR-0010](../adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)).

> **Delivered — #193 to #199 are merged — and this spec is the record of what was specified and built, not a status page: it is not rewritten.** Its forward-looking sentences are still forward-looking: *"This set of tickets is what would make it a claim about a measurement"* below, and the two promises in **Further Notes** about a non-zero adaptive fraction and about the retirement signal starting to mean something, are what the build made possible rather than what it delivered. What was measured and what was not is in [docs/validation.md](../validation.md) — the header's *Since #200* paragraph, the narrowed entry *No route has ever been written into the library by a run*, and the dated entry at its foot — and that document is the one to read for it.

---

## Problem Statement

A route found against a real agent cannot be decided by the run that found it, and nothing else will ever look at it.

Three facts, and they compose into a dead end.

**The deciding evidence is not available where the discovery happens.** The bar is `D` against the three reference agents ([ADR-0003](../adr/0003-gate-decision-rule-and-sample-size.md), [ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)). A customer run touched one endpoint — the customer's. It holds no reading against a reference agent on any model, let alone two, so the decision is structurally out of its reach. This is not an ordering bug to be fixed by running things later in the same process.

**A proposal has nowhere to live.** `AdaptiveEpisode.proposals` is a field on a run's own record. `precedent/findings.sqlite` cannot take it and says so: it holds *prose and never payload text*, on [ADR-0008](../adr/0008-repo-disclosure-posture.md), and carries no target identity at all, deliberately, because "accumulate enough entries and a failure pattern identifies a target on its own" ([ADR-0011](../adr/0011-the-adaptive-attacker-is-label-blind.md)). `decisions/routes.sqlite` holds what the gate *measured*, keyed by a digest, and by construction has no reading to hold for a route nothing measured. Both correct stores refuse it for good reasons, and there is no third.

**The one surface that walks the path is pointed at the wrong agents.** `scripts/swap.py` decides and writes, and its proposals come from attacking the reference agents — which is the discovery-and-validation-on-one-set hazard [ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) built the cross-model bar around. A route found against a customer's agent was never fitted to the reference agents at all. The bench's best routes arrive by the path with no machinery, and its most suspect ones by the path with all of it.

The consequence is stated plainly in `docs/validation.md` under *what has never been validated*: no route has ever been written into the library by a run, the adaptive fraction has never had a non-zero reading, and "the loop closes" is a claim about a mechanism demonstrated on constructed evidence. This spec is what would make it a claim about a measurement.

## Solution

Give a proposal a durable home, and give the bar a surface of its own.

A **pending route** is a proposal filed at the end of the run that found it, into `pending/routes.sqlite` — its own directory, its own database, git-ignored, on [ADR-0029](../adr/0029-the-precedent-store-is-a-database-and-the-connection-belongs-to-the-batch.md) decision 6's reasoning and the pattern `/precedent/`, `/decisions/`, `/runs/` and `/checkpoints/` already follow. It carries what a decision needs and what triage needs: the route key, the case draft, the payload, the criterion, the attacker's own prose, the target's identity, and its state.

**This store holds two things no other store may — the payload and the target identity — and [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) is the record that decides it.** Read there: why `precedent/`'s two refusals do not extend to a store no instrument reads, and the five mitigations the exception is granted on. The local consequence is the identity boundary below.

**Deciding is its own surface, and not a gate run's second job — [ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md).** A new route family, `/pending-routes`, records an attestation, declares an estimate, halts for approval, then measures the selected routes against the three reference agents on one declared reference model in one action and decides them ([ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md) §4: every route here was found against a customer's target, so a second pass is a call the decision cannot spend). The three reasons it is not folded into `/gate-runs`, each sufficient on its own, are the ADR's: the admission memory's model-pair key, the exclusive library lease ([ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md)), and a gate run producing a decision about *this bench* and nothing else ([ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md)). What it gives up — the operator runs a second thing — is recorded there too.

**The consent mechanism is the one that exists — [ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md) §4.** The attestation `registration.py` refuses to construct incomplete, and the same `PendingApproval` seam `POST /runs` and `POST /gate-runs/{id}/approval` answer; the estimate is declared here because the spend is real and new, and the operator has seen no figure for it whatever they attested to for the run that found the route.

**One code path to the bar.** `cross_model_bar` moves out of `scripts/swap.py` into the backend, and both surfaces call it. It already consults the memory, measures per model, decides per proposal, and remembers what is worth remembering. "There is one code path to a reference agent and this does not add a second."

*Amended by [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md).* "Nothing about the bar changes here" was true when it was written and is no longer. What moved is **which bar a proposal's provenance selects**: a route found against a customer's target is `adaptive_on_target` and faces the single-model bar of [ADR-0003](../adr/0003-gate-decision-rule-and-sample-size.md), while a route found against the three reference agents stays `adaptive` and keeps ADR-0012's cross-model bar. The code path is still one: `cross_model_bar` serves both surfaces, still takes N models and still walks them one at a time, and what this surface hands it is one.

**The identity stops at the decision.** `remember` receives the route key and the counts; `enter` receives the case. Neither learns whose agent the route came from, and neither has a field that could hold it. The identity exists in the pending store and nowhere else, which is the one place a decision deletes.

## User Stories

### A route survives the run that found it

1. As an operator, I want a route the attacker found against my target to be filed when the run ends, so that the interesting output of a run is not a line of printed prose.
2. As an operator, I want to see every pending route on one page with the target it beat, so that I can tell which of them are worth paying to decide.
3. As an operator, I want the attacker's own description beside each one, so that the row says what the route did and not only that a route exists.
4. As an operator, I want a route filed twice to be one record, so that an attacker that rediscovers a path every run does not fill the queue with copies of it.
5. As a bench engineer, I want a route found in a gate run to stay out of this store, so that the routes awaiting a decision are the ones no surface already decides.

### Deciding them

6. As an operator, I want to select pending routes and measure them in one action, so that a decision does not depend on my running two things in the right order.
7. As an operator, I want to attest and then approve an estimate before anything is sent, so that deciding a route cannot spend my inference budget without my seeing the figure.
8. As an operator, I want a route the memory already measured under these conditions to be decided without being re-measured, so that I pay once for an answer ([ADR-0032](../adr/0032-the-admission-memory-holds-the-measurement.md)).
9. As an operator, I want the measurement refused while a gate run holds the library, so that two writers never meet ([ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md)).
10. As an operator, I want progress reported per route while it happens, so that an action that is minutes long is legible.

### What a decision leaves behind

11. As an operator, I want an admitted route written into the library and its row to name the record it became, so that the loop closing is a file I can open.
12. As an operator, I want a rejected route to stay on the page with the gate's own reason, so that a route that was a property of one model is a finding I can read ([ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)).
13. As an operator, I want a decided route's payload gone from the store, so that the live exploits on my disk are only the ones still awaiting a decision.
14. As a bench engineer, I want nothing written by a decision to contain a target's name, so that the memory and the library keep the disclosure posture the pending store is the exception to ([ADR-0008](../adr/0008-repo-disclosure-posture.md), [ADR-0011](../adr/0011-the-adaptive-attacker-is-label-blind.md)).
15. As a bench engineer, I want an admitted route to reach the library through `enter` and no other writer, so that de-duplication against the library on disk stays in one place ([ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md)).

### When it goes wrong

16. As an operator, I want a route whose criterion no longer matches any live case to be refused rather than measured, so that I do not pay to decide a probe nothing can score.
17. As an operator, I want an aborted or declined measurement to leave every route pending, so that a refusal costs me nothing and loses nothing.
18. As an operator, I want a measurement that reached one model and not the second to leave the routes pending and undecided, so that a partial reading never becomes a cross-model admission.

## Implementation Decisions

**Two ADRs first, and they are written.** [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) — this store may hold payload text and target identity where `precedent/` may not, with the argument for why the difference holds. [ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md) — admission measurement is its own surface rather than a gate run's second job, on the memory's model-pair key, the lease, and [ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md). Neither was a paragraph to append to an existing ADR, and neither existing ADR was edited to have decided it.

**`pending/routes.sqlite`, through `DatabaseStore`.** The fourth store on that seam, a git-ignored directory rather than a file name, and one location with no environment override — [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) §5 for why each of the three, and it is the sidecar argument the other ignored directories were created under.

**Keyed on `decided.RouteKey`.** The same family-plus-probe-digest the memory and the library de-duplicate on, so one route is one pending record, one remembered measurement and one library record, and the three agree by construction rather than by convention.

**Filed by the customer-run entry points, not by `run_calibration`.** `run_calibration` is shared with gate runs, so filing there would put reference-agent routes into a queue whose whole purpose is routes no surface decides. The seam is the API's run service and `scripts/bench.py`.

**`cross_model_bar` moves to the backend unchanged in behaviour** ([ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md) §5). A move, not a rewrite: `scripts/swap.py` keeps calling it and its output there must not change. The measured proof is that the swap's own tests pass untouched.

**State is `pending`, `admitted` or `rejected`, and the payload is a field the last two do not have.** Emptied rather than nulled by convention: a record whose state is decided has no payload to read, enforced by the type rather than by every caller remembering ([ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) §4, where it is the fifth mitigation made mechanical).

**The write is `enter`'s, under `enter`'s lease.** This surface hands it admitted cases and takes back an `Entry`, and a route the library already holds is reported as held. No second writer of a `.toml`.

## Testing Decisions

**Each new test driven red once**, on purpose, confirmed to fail for the right reason, and reverted — the standing rule, and the ADR-count of deliberate breaks recorded per commit as [#40](../../issues/40) recorded them.

**The identity boundary is asserted from both ends.** That a decision's `remember` call and `enter` call carry no target name, and that no field on `DecidedRoute` or on a written `.toml` record can hold one. The second is the one that survives a refactor.

**The payload's disappearance is asserted on the store and not on the API.** A decided record read back from `pending/routes.sqlite` has no payload, whatever the route was decided as.

**A gate run's routes are asserted absent.** A gate run start-to-finish leaves the pending store as it found it.

**The lease refusal is asserted in both directions**, as [ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md)'s write already is: a measurement refused while a gate run holds the library, and a gate run refused while this action holds it.

**The memory's saving is asserted as a call count.** A second measurement of a route already remembered under the same conditions sends nothing to any reference agent, which is the whole of what [ADR-0032](../adr/0032-the-admission-memory-holds-the-measurement.md) buys and the one assertion that fails if the consultation is dropped.

**The partial-reading refusal is asserted with a pass that does not happen.** One model read, the other unreachable, and every route still pending afterwards — the shape as it was written, and no longer a state this surface can reach: it declares one model ([ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md) §4), so there is no second pass to lose. The refusal itself stays asserted, on the reachable half — an admission run the equipment could not serve, or one whose agents never registered, decides nothing and leaves every route pending — and the cross-model partial reading stays `cross_model_bar`'s to refuse for `scripts/swap.py`, which measures a pair by definition.

**Approval is asserted as a refusal, not as a flag.** No setting, environment variable or request field on this surface starts a measurement without an attestation and an answered halt.

## Out of Scope

**Any change to the bar.** `D >= 0.4`, Wilson 90% intervals, three agents — [ADR-0003](../adr/0003-gate-decision-rule-and-sample-size.md) and [ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) decide it and this spec measures against it. None of that moved. What did is how many models the bar reads: the question this non-goal reserved — whether a route found against a customer's agent faces selection pressure the reference-agent bar was not built for — is answered by [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md), which is the ADR of its own it asked for.

**A different bar by discovery target.** `promote` reads the bar off `discovered_by`, and when this spec was written every attacker-found route was `adaptive`. [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md) §§1–3 added the field: the provenance is declared by whoever built the target and threaded to the record, so *what a route was found against* is now on it. Still nothing this spec's surface decides — it reads the bar it is handed.

**Automatic measurement.** Nothing decides a pending route without an operator attesting and approving. A queue that drained itself would be an unbounded spend authorised once.

**Retention and expiry.** A pending route stays pending until decided. How long a queue may grow, and whether an old route should be dropped unmeasured, is a policy this spec does not set.

**Cross-tenant isolation.** Single-tenant, like every other store, and named as a P1 blocker in PLAN §11. The namespace carries no tenant segment, for the reason `PRECEDENT_NAMESPACE` and `DECISION_NAMESPACE` carry none: a segment nothing checks looks like isolation and enforces none.

## Further Notes

**What this makes measurable for the first time.** `library_provenance` already counts by provenance and by live/retired, so the adaptive fraction of the library is reportable the moment a record lands — and `docs/validation.md` can print a non-zero reading where today it prints an honest zero and a sentence explaining that the mechanism has only been demonstrated on constructed evidence.

**The retirement signal starts to mean something.** [ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) repair 3 calls adaptive-discovered cases retiring faster than authored ones the fingerprint of overfitting. It has never had adaptive cases to group. Routes found against real agents are the first population that could give it a reading.

**The disclosure posture gets its first deliberate exception, and it should be read as one.** Every other store was designed to hold as little as it could. This one holds a working exploit against a named agent because the alternative is discarding it. The mitigations are that it is short-lived by design, single-purpose, read by no instrument, never exported, and emptied by the decision it waits for — and none of that makes it the same kind of file as `precedent/findings.sqlite`. [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) grants the exception on exactly those five terms, and a change that breaks any of them reopens the record rather than being a change to the store.
