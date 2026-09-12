# Spec — A confirmed break the gate refused is kept against the target it beat

**Scope:** the second exit from a confirmed break. A route the adaptive layer finds against somebody's agent and the admission bar refuses is kept in a **target library** — a per-target list, scored on every subsequent run of that target, reported in a section of its own, and retired when the target stops failing it. No rate, interval, band, break score or gate decision changes. The bar is unchanged and is still the only way into the case library.

**A refusal at the bar is not a refusal of the finding.** [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md) sends a route found against a customer's target to the single-model bar and states what that bar asks: whether the route separates three agents of known construction. A route written in the customer's own vocabulary can be a real, evaluator-confirmed defect in a real agent and still separate nothing here, because the reference agents route by scripted phrase and the probe speaks another dialect. Issue #234 measured it — five consecutive rejections at `trivial 0.00`, concentrated in the trace-read families — and one of them recorded a live target running a tool after an explicit stop. That is a defect in somebody's agent, discarded as a weak case.

The bar is right to refuse it. The route is not general, and the case library is the shared instrument. What is wrong is that the refusal is the end of the road.

**The decision:** [ADR-0117](../adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md).

**Governing documents:** [PLAN.md](../../PLAN.md) · [CONTEXT.md](../../CONTEXT.md) · [ADR-0003](../adr/0003-gate-decision-rule-and-sample-size.md) · [ADR-0008](../adr/0008-repo-disclosure-posture.md) · [ADR-0010](../adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) · [ADR-0012](../adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) · [ADR-0014](../adr/0014-band-cut-points-are-the-reference-agents-constructed-rates.md) · [ADR-0016](../adr/0016-retirement-declines-on-a-family-unfit-to-report.md) · [ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) · [ADR-0022](../adr/0022-the-retirement-window-is-two-readings-of-one-model.md) · [ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md) · [ADR-0035](../adr/0035-the-elective-family-tier-is-never-gate-deciding.md) · [ADR-0072](../adr/0072-a-post-patch-re-run-is-its-own-record.md) · [ADR-0088](../adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md) · [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) · [ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md) · [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)

**Vocabulary:** every term below is defined in `CONTEXT.md` and none of them moves. A **case**, an **attempt**, a **route**, an **admission** and a **verdict** mean exactly what they already mean. Two words this spec adds are not bench vocabulary and neither enters a figure keyed on `Family`:

- a **target library** is the set of confirmed routes held against one target, outside the case library and outside its digest;
- a **held route** is one member of it. A held route is scored — it produces attempts and verdicts — but its attempts are counted on a denominator of their own and never on a family's. It is the same separation the elective tier already has ([ADR-0035](../adr/0035-the-elective-family-tier-is-never-gate-deciding.md), [ADR-0089](../adr/0089-a-break-is-over-the-six-and-the-tier-is-read-beside-it.md)), applied one level further out.

---

## Problem Statement

**A confirmed break against a real agent has exactly one exit, and it is the wrong size.** The exit is the case library, whose entrance is the admission bar. The bar asks a question about generality, and generality is not what most customer-discovered routes have. So the bench measures a real defect, proves it with its own evaluator, offers it to a gate that correctly says *"this is not a general case"*, and then deletes it.

**The refusal is also mislabelled today, which is #234.** `RejectionKind.SEPARATED_NOWHERE` reads *"a finding about the case rather than about any model"*. When the reference agents never engaged — `trivial = 0/10`, the floor pinned at zero — nothing was learned about the case at all. #234 fixes the label. It does not give the route anywhere to go, and it is explicit that it does not: *"a true positive recorded as a finding about the probe is worse than no reading."*

**The value of a confirmed break is almost entirely in the second run.** An operator who is told *"your agent ran a tool after a stop signal"* wants one thing next: to change something and be told whether it is closed. The bench can answer that — it has the payload, the criterion, a deterministic evaluator and a post-patch re-run record ([ADR-0072](../adr/0072-a-post-patch-re-run-is-its-own-record.md)) — and it throws away the one artefact the answer needs.

**The tempting repair is the one that breaks the arithmetic.** Scoring held routes inside the six families' rates would be easy and wrong. Held routes are selected *because they already broke this target*, so a family rate computed over them is a rate over a sample chosen on its outcome: it falls with every new finding, it is not comparable between two targets, it is not comparable between two runs of one target as the set grows, and the band's cut-points ([ADR-0014](../adr/0014-band-cut-points-are-the-reference-agents-constructed-rates.md)) were constructed against no such population. The figure would be well-formed and the label would be wrong, which is the failure mode this project names most often.

## Solution

**One approval, two independent answers.** A confirmed break already reaches `/pending-routes` and a person already decides it ([ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md), [ADR-0105](../adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)). That one decision now answers two questions that were always distinct:

1. *Does this route break agents in general?* — the admission bar decides, unchanged, and an admitted route enters the case library exactly as [ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md) writes it.
2. *Does this route still break **your** agent?* — the operator decides, and a held route enters that target's library.

**A route takes one of the two doors and never both.** If the bar admits it, it is in the shared library and every run of every target — including this one — already sends it as a scored attempt in its family. Holding it as well would send the same probe twice and count it on two denominators. So the target library holds precisely the confirmed breaks the bar **refused**, which is the population #234 is about and the population that today is deleted.

**The gate is not the door, and a person is.** A held route faces no `D`, because `D` is a measurement against the three reference agents and the whole point of this population is that those agents cannot read its probe. What it faces instead is what it already passed: an evaluator-confirmed break against the target ([ADR-0106](../adr/0106-a-confirmed-break-files-its-route-and-an-unbroken-episode-proposes-nothing.md)), and a named operator's approval on a surface built for deciding. The claim a held route carries is small enough for that evidence to cover it: **this exact probe produced this exact verdict against this exact agent, and here is whether it still does.**

**Automatic on every run of that target.** Not an option and not a tick-box. A regression suite an operator can forget to select is a regression suite that reports what the operator hoped rather than what is true, and the figure it produces — *"3 of 5 still open"* — means nothing unless the 5 is every route ever held.

**Its own section, its own denominator, and no path into any other figure.** The report gains one block: how many routes are held, how many still break the target, how many are closed. It is not summed into a family rate, `A_break`, the band, the gate decision or the bench's own discrimination score. This is [ADR-0088](../adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)'s distinction applied again — a fact about *this target* belongs in the target's report and a claim about the bench does not follow from it — and the firewall is carried by the type, not by discipline at a call site.

**Retirement, at two clean runs.** A held route that does not break the target on two consecutive runs is closed and stops being sent, matching the two-reading window [ADR-0022](../adr/0022-the-retirement-window-is-two-readings-of-one-model.md) already declares rather than inventing a second number. A closed route is not deleted: the report can still say *"found on 3 March, closed on 19 March"*, which is the sentence the operator paid for. One clean run is a coin-flip on a probabilistic target; the same argument ADR-0022 makes.

**The store holds a payload and a target, and it is the exception already granted.** [ADR-0104](../adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md) argued that exception for `pending/routes.sqlite` on five mitigations, and every one of them holds here for the same reasons: git-ignored directory, no instrument reads it, single-tenant, and the identity never reaches anything blinded. A held route is a decided pending route that did not become a case; the natural home is beside the store that already holds it, and whether it is a second table or a second database is an implementation decision below.

**The shared library's digest does not move.** A target library is keyed to a target and is not loaded by `load_library`. If a held route changed the case library's version, every customer would run a differently-versioned instrument and the gate citation on their report would stop naming a thing that exists.

## User Stories

### A refused break is kept

1. As an operator, I want a confirmed break the bar refused to be held against the target it beat, so that the most interesting output of a run is not deleted by the surface that measured it.
2. As an operator, I want to approve a route into my target's library and send it to the admission bar in the same decision, so that "is this mine" and "is this everyone's" are not two errands.
3. As an operator, I want a route the bar admitted to stay out of my target library, so that one probe is not sent twice and counted twice.
4. As an operator, I want the attacker's own description of the break carried on the held route, so that the report says what the route did and not only that a route exists.

### It is re-tested without being asked

5. As an operator, I want every held route re-sent on every run of that target, so that the count of what is still open is a fact about my agent and not about what I remembered to select.
6. As an operator, I want a held route scored by the same deterministic evaluator as any case, so that "still open" is a verdict and not a judgement.
7. As an operator, I want a run that holds no routes to say so, so that an empty section reads as *nothing has been found yet* rather than as a section that failed to render.

### It never touches the score

8. As a reader of a report, I want held routes reported in their own block with their own denominator, so that a family's rate means the same thing on my report as on anybody else's.
9. As a bench engineer, I want a held route to be unable to reach a family rate, `A_break`, the band or the gate decision by construction, so that the firewall is a property of the type rather than a rule someone must remember.
10. As a reader of two reports for the same target, I want the six family rates to be comparable between them however many routes were held in between, so that a trend line means what it looks like.

### It closes

11. As an operator, I want a held route that fails to break my target twice in a row to stop being sent, so that the cost of a run does not grow forever with the number of things I have already fixed.
12. As an operator, I want a closed route kept in the record with the run that closed it, so that the report can show my fix worked.
13. As an operator, I want a closed route that breaks the target again to be visible as a regression, so that a reopened defect is not silently a new finding.

### When it goes wrong

14. As an operator, I want a held route whose target is gone or unreachable to be reported as unmeasured rather than as closed, so that an absent endpoint never reads as a fix.
15. As an operator, I want a held route whose probe the evaluator can no longer read to be reported as unmeasurable, on the `measurability.checkable` path the adaptive layer already uses, so that a broken criterion is not a clean run toward retirement.

## Implementation Decisions

- **[ADR-0117](../adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md) is the decision this spec builds, and it is written before any code.** What it decides that no ADR decided before is that a scored attempt may exist that never faced the admission bar. [ADR-0035](../adr/0035-the-elective-family-tier-is-never-gate-deciding.md) and [ADR-0088](../adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md) are not amended: this is a second population arriving at a boundary they already drew. `CLAUDE.md`'s rule applies — no ADR is edited to say something it did not decide.
- **A sixth provenance, `DiscoveredBy.TARGET_SPECIFIC`**, declared last in the enum for the reason [ADR-0107](../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md) §1 gives: the provenance census prints in declaration order and a member inserted above one already counted reorders a line readers of two gate runs compare.
- **The held route is its own type and is not a `Case`.** The invariant is carried by the type, the way `AdaptiveEpisode` is not an `Attempt` ([ADR-0010](../adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)). If a signature has to widen to accept both, stop.
- **Its verdicts are its own type too**, so that no aggregation over `Attempt` can pick them up by accident and no per-family counter needs a new exclusion.
- **`load_library` does not read it**, and the library digest is computed over the case library alone. A test asserts the digest is unchanged by the presence of held routes.
- **The key is `decided.RouteKey`** — family plus `sha256` of the probe — scoped to the target, so one route is one held record however many times it is rediscovered ([ADR-0033](../adr/0033-an-admitted-route-is-written-into-the-library.md) §3).
- **Clean-run counting is per held route and lives on the held route**, not derived by scanning run records. [ADR-0019](../adr/0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md) rejected rebuilding a store from run documents for this reason: it makes the state depend on every historical record being present and parseable.
- **The store is git-ignored as a directory**, sidecars included, and a test asks git whether it is — the pattern `precedent.py` already documents.
- **#234 lands first.** The sixth `RejectionKind` is the smaller change, it stops the mislabelling on its own, and its per-family count is what says how large this population actually is.

## Testing Decisions

- **Every new test is driven red once, for the right reason**, per `CLAUDE.md`.
- **An import-level test** that the held-route type cannot reach the family rate aggregation, in the pattern `test_layer_ordering.py` and `test_precedent.py` use for the judge and adjudicator prohibitions.
- **An arithmetic test**: a run with N held routes and a run with zero held routes over the same case library produce identical family rates, an identical `A_break` and an identical band.
- **A retirement test** over three runs: break, clean, clean → closed and not sent on run four; and break, clean, break → still open with the clean run recorded.
- **A reopening test**: a closed route that breaks again is reported as a regression and not as a new finding.
- **A durability test across a restart**, the acceptance criterion [ADR-0019](../adr/0019-long-term-memory-that-does-not-survive-a-restart-is-not-long-term.md) sets for every store here: hold a route, drop the store object, construct a new one against the same location, read the route and its clean-run count back.
- **A double-door test**: a route the bar admits is written to the case library and is *not* held, and the same probe appears in exactly one denominator.
- **A digest test**: holding a route does not change `library_digest`.
- **An unreachable-target test**: held routes against a dead endpoint report unmeasured, and no clean run is counted toward retirement.

## Out of Scope

- **Widening the reference agents' phrase router.** #234 rules it out and the reason stands: a scripted router is what makes a verdict a fact rather than a model's mood. This spec's whole premise is that some routes will never speak that dialect, and the answer is to keep them elsewhere rather than to teach the equipment every customer's vocabulary.
- **Translating a probe into the bench's dialect before measuring it at the bar.** It would rescue real routes and it changes what is being measured — the thing graded would no longer be the thing that broke the target. Its own ADR, on its own evidence.
- **Cross-target learning.** Held routes are per target and nothing generalises from one target's library to another's. [ADR-0011](../adr/0011-the-adaptive-attacker-is-label-blind.md) is why, and it is untouched: nothing in a target library reaches the attacker, the judge or the adjudicator.
- **Steering the adaptive attacker away from routes already held.** A memory that told the attacker what it has already found would be a real improvement and is a different ticket; nothing here changes what the attacker sees.
- **Cross-tenant isolation.** Still the named P1 blocker it is in `precedent.py`, and this store inherits the same single-tenant namespace and the same honesty about it.
- **A held route in the signed artefact's sentences.** The figures belong in the report ([ADR-0115](../adr/0115-the-report-screen-carries-the-figures-and-the-artefact-carries-the-sentences.md)); whether the signed document carries a held-route section is a question for the ADR and not assumed here. [ADR-0119](../adr/0119-a-held-routes-figures-travel-in-the-signed-artefact-and-its-prose-does-not.md) answers it: the figures and the dates are in the signed document, the attacker's own account of each break is not, and **user story 4 above is therefore unmet on every surface** — the ADR records that as a cost rather than closing the story.

## Further Notes

**What this buys, stated so it is not overstated.** It does not make any rate more precise — held routes are a sample chosen on its own outcome and can make no rate more precise, which is exactly why they are fenced. What it buys is the one question a customer asks second: *did my fix work?* The bench can answer it deterministically, and today it cannot answer it at all because it deleted the evidence.

**Why the elective tier is the precedent and not an analogy.** [ADR-0088](../adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md) already decided that a figure can be real, reportable, about the target, and simultaneously barred from the bench's own claims — and it did so by separating two quantities that had been sharing one prohibition. This spec separates a third out of the same pile: a rate over routes selected on their outcome. The fence is the same fence.

**The population this creates is a measurement in its own right.** How many confirmed breaks are refused by the bar, per family, is the number #234's sixth `RejectionKind` starts counting, and once routes are held it becomes a series. A bench whose customer-discovered routes are almost never general is telling the reader something true about the difference between an instrument and a finding.
