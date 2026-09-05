# ADR-0067: The bar is per family, declared in the caller's repository, and a withdrawn family is not green

**Status:** accepted (#90, group J / #81)
**Date:** 2026-09-05

## Context

[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) left
one seam open and named it: the Action writes `report-directory` and `report-json`
before the bench runs, uploads on `always()`, and **does not decide whether the job is
red**. This is that decision, and it is a measurement question rather than a YAML one.

Three things constrain it before any design starts.

**There is nothing to threshold, on purpose.**
[ADR-0005](./0005-no-composite-risk-score.md) refuses a composite score and
`payload.py` states the structural half of that refusal — *there is no key at any depth
that reaches across two families, and the structural half of that claim is testable:
drop a family from the result and every other byte of the document is unchanged*. So
`if score < 80: exit 1` is not available, and it is not available by design rather than
by omission.

**A threshold in a runner is a threshold nobody can read.**
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md)'s whole argument is that a
pass condition which is not written down is a pass condition that passes, at hour 30,
with the report phase waiting. A bar compiled into `action.yml` would be exactly that,
one repository further out.

**And the bench's own result and the target's are two different subjects.**
[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md): *the
bench passed its gate, the target has rates, intervals and bands*. A bench that cannot
discriminate produces low rates against everything, which is a green step.

## Decision

### 1. The bar is per family, and it is a band, and it lives in the caller's repository

A committed TOML file — `.github/agentaudit-bar.toml` by convention, named on the
Action's `bar:` input — listing, per family, the **worst band that passes**. Bands
rather than rates because a band is the coarse summary a reader can hold a team to and
a rate wobbles inside one; and because
[ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md) puts
the cut points on the reference agents' constructed rates, which is what makes a band
mean the same thing in two repositories. It is in the caller's repository because that
is where it can be reviewed in a pull request, and because the bar is a statement about
what *that team* will accept and never a fact this bench measured.

**`BEST_FIRST` is an ordering on the bar and never a rank on `Band`.** `Band` is a
`StrEnum` and not an `IntEnum` precisely so that a six-family total is one type change
away from impossible (ADR-0005, D3). The ordering `bar.py` holds is used for exactly one
comparison — *is this family's band at or better than the one this family was declared
at* — which is inside one family, never across two, and produces nothing that can be
summed, averaged or ranked.

**This is not the gate's bar and does not touch it.** The gate turns on `D` and
interval separation between three reference agents, over families of *contrast*, and no
band appears in it — `BandCuts` is a separate type from `GateRule` for that reason. What
this ADR adds is a second, weaker instrument entirely: `DECLARED_BAND_CUTS` decides
which band one target's rate lands in, and the bar decides which bands one team accepts.
Neither number moves the other, and the bar has no route to a gate decision because the
payload has no field that could carry one.

### 2. Every family is named in the file, and a covered family with no band fails the step

**The three ways a run can be green and should not be** all reduce to a family with **no
band**, over which a check that iterates the bands it found passes in silence. So:

- **A covered family with no band fails the step, printing the withdrawal's own
  sentence.** Not a summary of it — `NotMeasurable.stated` and `Withheld.stated` are
  long because a reader meeting *not measured* with no sentence beside it is a reader
  guessing which of four answers it was (ADR-0004).
- **A bar that says nothing about one of the six is refused**, before the run. A team
  that meant to switch a family off says so under `[not_measured]`, **with a reason**,
  and the step prints those exemptions on every outcome including a green one — a build
  that quietly measures half the suite is the failure this whole file exists against.
- **An elective family may not be put on a bar.** The tier reports *a name and never a
  figure* ([ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md)), so
  there is nothing in the artefact a band could be compared against and a bar naming one
  would fail every run for ever.

The enumeration, and what the bar does with each:

| How a family goes unmeasured | Where it is | What the bar does |
| --- | --- | --- |
| `NotMeasurable` — no tool trace, no session retention, no personal records, `NO_CONFIG_CANARY_PLANT`, `NO_RETRIEVED_CONTENT_PLANT` (#84's `REFUSED_FOR`) | `measured.not_measurable`, with `stated` | fails the step, quoting `stated` |
| A judged family withheld below the κ floor, or with no κ at all (ADR-0015) | `measured.withheld`, with `stated` | fails the step, quoting `stated` |
| Dropped before the run — `DeclaredGap.FAMILY_SWITCHED_OFF`, `TRANSFORMS_SWITCHED_OFF`, `OperatorGap.NONCE_NOT_PLANTED` / `NOTE_NOT_PLANTED`, `deterministic_subset` | **absent from the payload entirely** (ADR-0066 §6, #138) | fails the step, saying the artefact carries no reason and where the reason went |
| A family the team switched off in the bar | the bar's `[not_measured]` | not covered; named on every outcome in the team's own words |
| An elective family nobody requested | `elective.not_requested` | not coverable; naming one refuses the bar |
| A plant the bench performed and could not read back (#87's `PlantCheck.NOT_RETURNED`) | `provenance.planting` | **withholds the whole decision** — §4 |

A `Withheld` family is the one entry in that table where the reasonable reader might
expect *cannot decide* instead: κ is an instrument reading. It fails the step because
what the bar is about is the *caller's* declaration — they said they measure this family,
this run did not, and that is theirs to fix by supplying an adjudicator or by switching
the family off in the file. The instrument's own certification is a different question
and it is §3.

### 3. A run whose instrument does not stand is refused, not failed red

The artefact carries the bench's result once, as a `GateCitation` in `Provenance`
([ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md)). The bar **withholds
its decision** — a third answer, on `GateOutcome`'s and `scripts/verify.py`'s own
precedent — when that citation is absent, records an outcome other than `passed`, has
been superseded by a library that grew past it (`moved`, ADR-0033), or was older than
the caller declared when the run was made. A broken instrument is not a finding about
the target, and the two must not arrive as the same exit code.

**The staleness window is the caller's declaration and it is required.** Nothing in this
project measures a gate run's staleness in days: the retirement window is *two readings
of one model* and deliberately not a span of time
([ADR-0022](./0022-the-retirement-window-is-two-readings-of-one-model.md)). So there is
no figure here for the bench to supply, a default would be a number invented on a team's
behalf, and `gate_max_age_days` is a required key rather than an optional one.

**And the age is measured from the run's own attestation timestamp, never from the
clock.** The decision is a function of the artefact and the committed file and of
nothing else, so re-reading an archived report next year answers what it answered on the
day. A bar that changed its mind overnight over bytes nobody touched is a bar nobody can
reproduce, and reproducibility is the property the whole artefact exists to have.

### 4. A plant that did not land withholds the decision, and does not fail one family

`verified` is conjunctive (ADR-0064 §4). A planting hook that plants nothing and reports
success means the family it is a precondition of was attacked with its artefact absent,
and the clean zero that comes back reads as a defence — which is precisely what a bar
must not pass.

**The whole decision is withheld rather than one family failed**, because *which* family
a plant serves is not on the document: a `Planting` carries its `Plant` and its case id,
and no family. The alternative was a `Plant → Family` table in this module, and it was
rejected: it would restate what the case records already say, it would drift from them
silently the first time a case moved, and it would be read against reports produced by
other library versions. A withheld decision is honest at the cost of being coarse; a
table would be precise at the cost of being wrong later.

A run that measured **nothing at all** — no figure for any family, and no absence with a
reason — withholds the decision for the neighbouring reason: that is a run that did not
happen, not a target that held six ways.

**The rest of *a run that did not finish* is answered before the bar is reached.** A
budget breach, an unreachable target and a declined ceiling each already have a named
outcome and a non-zero code out of `scripts/bench.py`, and no artefact is written for
any of them — so the Action's decide step does not run at all (no `always()`, §5) and
the run's own code stands. What the bar's own *could not decide* covers is the same
condition met by hand or by a later step: a report directory that is missing,
unreadable, not this artefact, or a shape from a version this bar does not read.

### 5. Four answers, four exit codes, and two of them are not the bench's

The step's four answers, and where each comes from:

| Answer | Code | Returned by |
| --- | --- | --- |
| Passed the bar | `0` | `scripts/bar.py` |
| **Below the bar** — a family worse than declared, or covered and unmeasured | `1` | `scripts/bar.py` |
| Could not decide — the instrument, or the run | `2` | `scripts/bar.py` |
| Refused before sending — the bar itself is not a bar | `3` | `scripts/bar.py`, called *before the bench runs* |
| Refused before sending — attestation, key, ceiling, target | `2`–`5` | `scripts/bench.py`, unchanged |

**`EXIT_BELOW_THE_BAR` is the first exit code in this project that is a figure about the
target**, and it is deliberately in a different process from the one that measured the
figure. `scripts/bench.py` is untouched by this ticket: a completed run still returns 0
whatever its rates, `EXIT_NOT_REGISTERED` still says nothing was measured, and
`EXIT_DISCLOSED` still says a control failed closed. ADR-0065 §4's invariant — *no rate
decides an exit code of the entrypoint* — therefore survives intact, and the bar is a
second step reading a signed document rather than a branch inside the run.

**The bar file is checked before the run and again after it.** A bar naming five
families is a mistake to catch while it has cost nothing; catching it after the run
would be a step that spent somebody's inference budget on a document nothing was
compared against. That is why *refused before sending* is a real answer of this script
and not only of the entrypoint.

### 6. What the bar deliberately does not do

- **It does not check the signature.** `scripts/verify.py` is the one definition of that
  check and the Action runs it; a second implementation here would be a second verifier,
  which is the drift this project refuses wherever it has one definition of something.
- **It does not read the library, reach a network, or build a model.** It is arithmetic
  over a parsed document and a parsed file.
- **It writes nothing** — not the artefact, not the job summary. The page is the signed
  rendering under a guard that fails closed (ADR-0066 §3), and a decision appended to it
  would be a second document's worth of prose inside the one whose digest is signed.

## Consequences

- `backend/bench/bar.py` holds the arithmetic and `scripts/bar.py` is the entrypoint, on
  the split `verification.py` / `verify.py` already has.
- `action.yml` gains one input (`bar`, defaulted, emptiable) and two steps: a check
  before the bench, and the decision after the upload. There is **no `always()`** on the
  decision: a bench step that already failed has said what happened in its own code.
- **This repository commits its own bar at `.github/agentaudit-bar.toml`**, which decides
  the `action` CI job and doubles as a worked example — the same double duty
  `.github/agentaudit-attestation.md` does. It covers `data_leakage` at `holds` and
  switches the other five off with the reason, because that job is
  `--deterministic-only` against a callback with one planting hook: five of the six
  families genuinely are not measured there, and saying so in the file is what this ADR
  asks of everybody else.
- `docs/examples/agentaudit-bar.toml` is the copyable version, and both are parsed by a
  test — a file offered as the thing to copy is a file that has to load.
- **`bar` defaults to a path rather than to nothing**, so a caller who upgrades from
  #89's action and has no `.github/agentaudit-bar.toml` gets exit 3 before anything is
  sent. Fail-shut is the deliberate direction — the alternative default is a step that
  measures an agent and holds it to nothing — and `bar: ""` turns it off in one line,
  which the example workflow says where a caller reads it.
- **A bar that covers no family parses and passes**, printing six exemptions and the
  reason for each. Refusing it was considered and rejected: a team standing the bench up
  against a target that answers none of the six has a legitimate file to write, and what
  stops it becoming permanent is that every one of those sentences is in a reviewed diff
  and printed on every green step. What is not permitted is silence, which is the
  completeness check.
- A team's bar is a reviewed diff. Loosening a band, or switching a family off, is a
  visible change to a file with a reason field in it, which is the same property the
  committed attestation has and for the same reason (ADR-0065).

## Alternatives rejected

- **A composite score with one threshold.** ADR-0005, and there is no field in the
  artefact to read it off.
- **A bar in rates rather than bands.** A rate wobbles inside a band at n = 30, so a bar
  in rates would go red on noise and be loosened until it went quiet.
- **The bar as inputs of the Action.** A threshold in a runner is a threshold nobody can
  read (ADR-0003), and a `bands: holds,holds,weak` input is a threshold nobody can review
  either.
- **Iterating over the bands the report has.** The bug this whole ticket exists for: it
  is silent for every family that was never measured, which is the family a reader most
  needs to hear about.
- **Defaulting an unnamed family to *anything passes*.** The flattering default, and it
  is what the file's completeness check exists to remove.
- **Failing the step red on a gate citation that does not stand.** *Our bench is broken*
  reported as *your agent regressed*, which ADR-0018 spends its whole argument on.
- **A `Plant → Family` table so an unverified plant fails one family.** §4.
- **A calendar staleness window declared by the bench.** ADR-0022 measures no such thing,
  and a number this project has not measured does not belong in this project's defaults.
- **Deciding the bar inside `scripts/bench.py`.** It would put a rate behind an exit code
  of the run itself, which is exactly the invariant ADR-0065 §4 states, and it would make
  the bar unreadable to anybody holding only the artefact.
