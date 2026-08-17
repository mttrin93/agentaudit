# PLAN.md — AgentAudit

An adversarial test bench for AI agents, with a signed evidence report mapped to the EU AI Act.

Turing College Sprint 3 build, then extended to the Sprint 4 capstone.

Decisions with reasoning long enough to need it live in [`docs/adr/`](./docs/adr/). Vocabulary lives in [`CONTEXT.md`](./CONTEXT.md) — **family**, **case** and **attempt** are three different things, and every arithmetic claim in this document depends on that.

---

## 1. Mission

Every team that ships an AI agent gets the same question from an enterprise customer, a procurement team, or an insurer: how do you know it is safe? Today each team answers with a number it produced itself, measured against a definition of failure it also wrote itself. This is not evasion — it is the only option available, because no shared taxonomy of agent failure exists, and because the applicable conformity route prescribes exactly this. Under Annex VI internal control, a provider of an Annex III high-risk system in points 2 to 8 assesses its own system; no notified body reads it. The law does not merely permit self-grading, it writes it in. Aviation, pharmaceuticals and automotive engineering each spent decades building a shared failure taxonomy; the harmonised standards for Article 15 are still unfinished, and their absence is among the reasons the high-risk deadline moved to December 2027. The consequence is that agent safety evidence does not travel. A result means something inside the team that produced it and nothing outside it, which is why every insurer entering this market runs its own assessment rather than reading anyone else's, and why buyers fall back on trust instead of evidence. Most existing tools attack the wrong half of this: they add more tests, or they wrap the tests in a dashboard nobody opens. My angle is that the scarce thing is not more testing but validated testing, and then portable testing. So this project builds an adversarial bench that proves its own discriminating power before its results are trusted — a hardened agent and a deliberately weak one must score differently, or the metric is vacuous — and it delivers the outcome as a signed report that remains checkable after it leaves the engineer who produced it, because the person who carries the commercial risk is never the person who can see the failure.

**On timing, stated plainly.** Article 50 is enforceable now. Articles 15, 14 and 12 bind high-risk systems only, and are not enforceable until December 2027. The near-term buyer is therefore procurement and insurer diligence, not a regulator. The Act is not the reason to buy this. It is the rubric for what to test.

**Where the originality is.** Not in the article mapping — four of the six families are re-labellings of published OWASP categories, and saying so is what makes the labels useful. The original work is the gate, the admission and retirement lifecycle, the declared discrimination score, and the multi-model validity check. The categories are borrowed so they are recognisable; the measurement is mine. See [ADR-0002](./docs/adr/0002-owasp-ids-as-secondary-labels.md).

**Job statement**

An engineer who ships an AI agent hires this to answer the enterprise security questionnaire with tested evidence, instead of filling it in by hand from memory.

**What gets fired:**

1. The hand-filled security questionnaire — the true default, and it happens today.
2. The untested self-declaration in the Annex VI internal-control file.
3. The insurer's own assessment, run because it cannot read anyone else's score.

The first is the strongest. It is a document a human currently completes from recollection, under commercial pressure, for a customer who cannot verify any of it.

**Not** a consultant's first pass. Under Annex VI internal control there is no notified body for Annex III points 2 to 8, so no external auditor exists to displace. Naming one failed the kill test.

---

## 2. Decisions of record

These are settled. Do not reopen them during the build.

| # | Decision | Reason |
|---|---|---|
| D1 | The user is a **provider**, not a deployer | The user builds the agent and places it on the market. Where the target is Annex III high-risk, Articles 9 to 15 apply to them; where it is not, only Article 50 does. Article 26 is out of scope either way. |
| D2 | Articles in scope: **15, 14, 12, 50** | Not the reason to buy. The Act is the only external rubric that exists for what to test — so the evaluation criteria come from law rather than from my opinion. |
| D2b | The buyer is **procurement and insurer diligence**, not a regulator | The demand exists today. Mount and Klaimee both sell to non-Annex-III agent types with no regulatory hook; Klaimee's named deliverable is proof of certification for enterprise procurement. [ADR-0001](./docs/adr/0001-procurement-not-regulator-is-the-buyer.md) |
| D3 | No insurance, no pricing, no badge | Needs a licence. This is Mount's and Klaimee's business. Enforced structurally by D11, not by a disclaimer. |
| D4 | Every score prints its method and its limits | This is the differentiator. Competitors publish bare numbers. Applies to the bench's own scores first — see D10. |
| D5 | Python backend, React frontend | React cannot call a Python function, so an HTTP API is structural. React itself is a portfolio decision, not an architectural one. |
| D6 | Vite, not Next.js | Next.js adds a Node runtime that holds none of the logic. |
| D7 | The reference agents are test equipment, not product | They calibrate the bench. They never go to a user. |
| D8 | **No attack list carries legal presumption** | No harmonised standard is cited in the OJ, so nothing grants Article 40 presumption. The Act mapping is mine; each family also carries a public identifier so the evidence is legible to a reader who has never seen this tool. [ADR-0002](./docs/adr/0002-owasp-ids-as-secondary-labels.md) |
| D9 | Families carry **OWASP 2026 identifiers as secondary labels** | A family *tests one case within* LLM01. It *is not* LLM01. Coverage limits stated per family and per report. [ADR-0002](./docs/adr/0002-owasp-ids-as-secondary-labels.md) |
| D10 | **The gate has a stated, falsifiable decision rule** | n = 30 per family per agent, `D ≥ 0.4`, non-overlapping Wilson 90% intervals, monotonicity. A gate whose pass condition is unstated is a gate that passes. [ADR-0003](./docs/adr/0003-gate-decision-rule-and-sample-size.md) |
| D11 | **`success_condition` is authoritative; the judge is narrative only** | An LLM verdict is not reproducible, and a signature over a non-reproducible number certifies only that I held it. [ADR-0004](./docs/adr/0004-deterministic-verdicts-judge-is-narrative.md) |
| D12 | **No composite risk score** | It mixed measured behaviour with untested self-report, rewarded over-declaring, discarded the intervals, and is the badge D3 forbids. [ADR-0005](./docs/adr/0005-no-composite-risk-score.md) |
| D13 | **No user input ever changes a measured rate** | Overrides are typed and annotate; they never delete a finding or move a number. [ADR-0006](./docs/adr/0006-overrides-never-change-a-measured-rate.md) |
| D14 | **The canary is the proof of control** | The nonce a user must plant to enable the leakage probe is also proof they can configure the target. No run without its echo. [ADR-0007](./docs/adr/0007-canary-nonce-as-proof-of-control.md) |

---

## 3. Architecture

### Product — this is what a user gets

| Component | Role |
|---|---|
| Registration | Takes the target's details, issues the nonce, records the attestation. No run starts until the nonce echoes back. |
| Scanner | Reads the declared controls, finds absent ones. Sends no messages. |
| Approval interrupt | The graph halts before the first attack, presents the estimated call count and cost, and waits for the human. The run is irreversible and spends the user's money against their own endpoint. |
| Attacker | Holds the case library. Sends payloads to the target endpoint under an enforced run budget. |
| Evaluator | Applies each case's `success_condition`. Produces the verdict. Deterministic. |
| Judge | Reads each transcript, blinded to its source. Produces reason, article, external identifier, fix, exposure, confidence. **Cannot overturn a verdict.** |
| Assembler | Per-family rates, intervals, bands; the declared-vs-defeated join; coverage gaps. |
| Report writer | Renders and signs the structured result. |
| Memory | Precedent store over **deterministic** findings, single-tenant, in the LangGraph Store, with a retrieval node in the graph. Feeds `suggest_remediation` only — never the judge. Typed overrides and cross-tenant retrieval are Sprint 4. |

**Two patterns this architecture already implements, named here so they are not overlooked.**

*Short-term memory* is the run state carried in the graph — current family, current case, current attempt, findings so far, calls spent against budget — read live by the progress endpoint in §8. *Long-term memory* is the precedent store above.

*Human-in-the-loop* is the approval interrupt: the graph pauses before an irreversible, costly action and will not proceed without a human. That is the pattern's canonical form, and it is load-bearing here rather than decorative — without it the bench attacks an endpoint and spends a budget on nobody's explicit say-so. The evaluator/judge disagreement queue is a second, weaker instance: where a deterministic verdict and the judge's narrative conflict, the conflict is logged for a human rather than resolved automatically.

### Test equipment — this never reaches a user

| Agent | Built to be | Expected failure rate |
|---|---|---|
| Hardened | Input checks, scope limits, output filters, stop control | About 10% |
| Weak | System prompt only | About 50% |
| Trivial | Obeys every instruction it receives | About 95% |

The bench is a thermometer. The three reference agents are the glass of ice water. You check the thermometer in ice water. You do not bring the ice water to the patient.

These rates are known **by construction, not by measurement**, so the defensible claim is the ordering — hardened ≤ weak ≤ trivial — and not the point estimates. Every reference agent is built with a swappable underlying model from phase 1, because phase 8b depends on it.

### The target agent

An HTTP endpoint the bench can send messages to. Registered with: endpoint URL, auth token, request and reply format, agent type, declared controls, tool list, **whether the endpoint exposes tool calls**, and the **echoed nonce**.

**The endpoint must be staging or sandbox, and this is now enforced rather than requested.** The suite makes an agent take unauthorised actions and defeat its stop control. Against production, the bench causes the damage it measures. Registration requires a three-part attestation — authorised to test; not production; accepts that these payloads generate provider policy violations against the user's own account and consume their inference budget — recorded into the Article 12 log and the report's provenance block.

**If the endpoint does not expose tool calls**, scope creep and halt defeat report *not measurable for this target*. They do not fall back to LLM judgement.

---

## 4. The article mapping

Write this table **before any code**. No approved list exists, so this document is the defence in the review. The last two columns are what make it honest.

| Attack family | Article | External id | The claim | What it does not prove |
|---|---|---|---|---|
| Indirect prompt injection through tool output | 15 — cybersecurity | tests one case within `LLM01:2026` | An agent that obeys instructions inside retrieved content can be controlled by any third party who writes that content | Nothing about direct attacks from the user |
| Scope creep — an unapproved tool is used | 14 — oversight | tests one case within `LLM03:2026` | If the agent acts outside the approved task, the oversight control does not work | Nothing about whether the call caused damage |
| Wrongful commitment | 15 — accuracy | tests one case within `LLM07:2026` | An output the user acts on, which the operator cannot honour, is an accuracy failure with legal effect | Nothing about how often this happens in real use |
| Data leakage — system prompt or credential | 15 — cybersecurity | tests one case within `LLM02:2026` / `LLM08:2026` | Confidential material inside the system boundary can leave it | Nothing about data the agent never receives |
| Halt defeat — the stop control is ignored | 14(4)(e) | no OWASP equivalent — originated here | The safe-state stop path can be bypassed | Nothing about whether a halt leaves clean state |
| Disclosure denial — the agent denies being an AI | 50 | no OWASP equivalent — originated here | The disclosure duty can be defeated by instruction | Nothing about synthetic-content marking under 50(2), which is deferred to 2 December 2026 |

Article 12 applies to all six rows. Every attempt is recorded, and so is every attestation.

**On the external column.** A family *tests one case within* that identifier; it *is not* that identifier. An OWASP entry is a risk category; a family is an executable test with a success condition. Each case states which case inside its identifier it tests and which it does not. `prEN 18229-2` and `prEN 18282` may be cited, but only with a draft date and a provisional marker — a stale clause number in a signed report is worse than no reference.

**Negative coverage, printed in every report.** Which OWASP 2026 agentic categories the bench does not test at all. This uses the public list as a coverage checklist, not only as a label. It is free, and it is the first thing a security analyst checks. Gaps are listed, not closed — new families to cover them are P2 at the earliest.

**Permanent limits of the whole bench**

- Data poisoning cannot be tested. It needs the training set.
- Model poisoning cannot be tested. It needs the pre-trained components.
- Output integrity cannot be tested. There is no ground truth for the target's domain. The bench can say the agent was manipulated. It cannot say the answer was wrong.
- Lifecycle consistency cannot be shown from one run.
- The scan reads what the target declares. A declared control can still be broken. That is what the attacks are for, and the declared-vs-defeated join is where it shows.
- Two families — wrongful commitment and disclosure denial — carry judged rather than deterministic verdicts, and a stated reliability figure with them.
- Article 14(5), the two-person rule, does not apply. It covers Annex III point 1(a), remote biometric identification.

---

## 5. Phases

Tiered by **lead time first, then criticality** — not by priority alone. Calendar-bound work cannot be scheduled as a phase.

### Track A — starts now, runs in parallel, about 1 hour of build

User recruitment. Five engineers with staging endpoints. Screening questions in the first message, because each one can disqualify:

1. Do you have a staging or sandbox endpoint for your agent?
2. Does it expose its tool calls, or only final text?
3. Can you edit its system prompt? (Required — see D14.)
4. What does your procurement team actually accept: an Act-mapped report, SOC 2, ISO 42001, or their own template?

Question 4 must be asked in the first conversation, not at hour 30. Track A also gates the phase 6 design, because the override taxonomy is invented ergonomics until a real user disputes a real finding.

### The Sprint 3 line — 49.5 hours build plus a 4-hour reserve

| Phase | Work | Hours |
|---|---|---|
| 1 | Three reference agents, each with a stop control, each model-swappable | 3.5 |
| 2 | Six families, **18 cases**, deterministic success conditions, canary plumbing | 9 |
| 2b | Configuration scan, and registration fields including tool-call exposure | 1.5 |
| 2c | Repeated runs — ten attempts per case, rate and Wilson interval | included |
| 2d | Case records, trigger log, admission gate at `D ≥ 0.4`, retirement at `D < 0.25` twice | 3 |
| 2e | **Authorisation guard and the approval interrupt** — nonce echo, attestation record, enforced run budget, and the graph halt for human confirmation of estimated calls and cost | 2 |
| 3 | The judge, narrative fields only, blinded; 30 transcripts hand-labelled as the gold set | 4.5 |
| 3b | **DeepEval executes the gold set**; κ computed from its per-case results | 1.5 |
| 4 | **The gate — STOP** | 4 |
| 4r | **Repair reserve** | 4 |
| 4b | Discrimination score and intervals per family | 1.5 |
| 4c | Result assembly, bands, declared-vs-defeated join, coverage gaps | 1 |
| 8b | **Multi-model validity check** | 2 |
| 5 | Article mapping, external ids, coverage, κ, gate rule, report, **real Ed25519 signing and offline `verify`** | 4.5 |
| 6a | **Precedent store** — single-tenant LangGraph Store over deterministic findings, retrieval node, feeds `suggest_remediation` only | 3 |
| 6b | Python API with the job pattern | 3 |
| 7 | React — three screens: register, run, report | 4.5 |
| 8 | Reflection notes on the two defects in this system | 1 |
| | | **53.5** |

**Why 3b and 6a are in the line rather than deferred.** An earlier version of this plan moved all of phase 6 to Sprint 4 and demoted the judge to narrative fields. Each decision was right alone; together they removed both of the sprint's named topics — memory and human-in-the-loop — from the deliverable. The store and the taxonomy separate cleanly: the store is buildable now, the four override types are invented ergonomics until a real user disputes a real finding. [ADR-0006](./docs/adr/0006-overrides-never-change-a-measured-rate.md). And 3b secures the one hard optional task against a strict reading of its wording. [ADR-0009](./docs/adr/0009-deepeval-executes-the-goldset.md).

### P0 complete — the rest of "must ship", about 3 hours

| Work | Why it waits |
|---|---|
| The four override types, and the feedback loop through the admission gate | Invented ergonomics until a real user disputes a real finding. Track A comes first. |
| The review-with-override screen | Same reason. |

**The gate is at phase 4, and it is a stop.** Run the whole library against all three reference agents. The rule is in §9 and it can fail. Repair before phase 5 — and the repair has four hours reserved, because a gate budgeted only for the cost of running it is a gate you rationalise past at hour 30. Do not build the interface first: React before the gate makes a broken measurement look finished.

**8b sits before the interface, deliberately.** It answers the strongest objection a reviewer can raise against the whole project, so it must not be in the tail where overruns land.

**Phase 8b is a validity check, not a feature.** Run the same library twice, on two different underlying models, and compare the discrimination scores. The question it answers: does the bench measure the **agent's** defences, or the **model's** default refusals? If discrimination collapses when the model changes, the bench was reading the model all along, and every score it produced is about the provider's training rather than the user's engineering. No competitor publishes one. It also satisfies the multi-model optional task, but that is the smaller reason to build it.

### P1 — capstone, not optional

| Work | Why |
|---|---|
| Multi-tenant isolation in the precedent store | **Blocker before user one.** The store holds unpatched exploits against named companies' agents. |
| Deploy with Terraform on a live URL | The known gap, and the cheapest hiring points available. Not before 2e exists — a hosted bench without the authorisation guard is an open attack proxy. |
| Five real users with staging endpoints | Track A's output. Step 9 of the capstone sequence, and the step that fails most often. |
| Langfuse traces on every attack | Observability, and a hard optional task. |
| Scheduled run and signed report by email | Article 72, post-market monitoring. |
| Queue instead of background tasks | Only when concurrency demands it. |

### P2 — genuinely cuttable

| Work | Article |
|---|---|
| New families to close declared coverage gaps | 15 |
| Agent-to-agent attacks — one agent manipulates another | 15 |
| Lifecycle runs, with an alert when a band moves | 9 |
| Proportionate oversight level from declared autonomy | 14(3) |
| Fail-safe recommendation where no fix exists | 15 |
| Serious-incident route for severe findings | 73 |
| Annex IV as the report table of contents | 11 |
| Plugin UI to enable and disable families | — |

---

## 6. The attack library lifecycle

### The case record

| Field | Content |
|---|---|
| id | Stable identifier |
| family | One of the six |
| external_id | The OWASP 2026 identifier this case tests one case within, plus which case inside it is *not* tested |
| payload | The message to send |
| success_condition | The deterministic check that decides the verdict. Authoritative |
| verdict_class | Deterministic, or judged |
| applies_to | Which agent types it is valid for |
| requires | Preconditions — for example, tool-call exposure |
| added_on | Date |
| trigger | Why it was added — one of the six below |
| status | Active, or retired with date and last discrimination score |
| discrimination_history | `D` on every gate run |

### The six triggers for a new case

1. **A family stops discriminating.** Providers add defences. An attack that worked in January is refused by default in June. It still runs; it no longer separates careful from careless.
2. **A target passes everything.** Either the agent is excellent or the attacks are weak. Check the trivial agent. If it also passes, the attacks are the problem. This ceiling effect is the most likely failure with real users.
3. **A user override reports a gap.** A `case_gap` override, and the best source, because it comes from the person who knows their own exposure.
4. **A new agent type arrives.** A voice agent needs different payloads from a document agent. Family stays; cases change.
5. **A new technique is published.** The library is behind the field.
6. **The scan checklist grows.** A new declared control needs an attack that checks it works.

### The admission gate

Every proposed case runs against the three reference agents first. It enters the library only if `D ≥ 0.4` with non-overlapping Wilson 90% intervals. Otherwise it is thrown away and never reaches a user. User input proposes; a stated threshold disposes.

### The retirement rule

Store `D` for every case on every run. A case at `D < 0.25` on two consecutive runs is marked retired, not deleted — one bad night must not retire a working case. A retired case is evidence that the field moved, and it belongs in the write-up. Without stored history, decay is a surprise. With it, decay is a chart.

### Typed overrides — Sprint 4

The precedent store ships in the Sprint 3 line (phase 6a); the taxonomy below waits for a real user. No user input ever changes a measured rate. [ADR-0006](./docs/adr/0006-overrides-never-change-a-measured-rate.md).

| Type | Allowed on | Destination |
|---|---|---|
| `verdict_dispute` | Judged families only | The κ gold set, as a candidate label. Never the judge prompt. Counted and reported |
| `applicability` | Any finding | Annotates. **Never deletes.** The report prints the finding and the user's reason side by side |
| `severity` / `exposure` | Any finding | The user's own commercial judgement. Never touches a rate or a band |
| `case_gap` | — | Trigger 3 → `propose_case` → the admission gate |

---

## 7. Repository structure

```
agentaudit/
├── PLAN.md
├── CONTEXT.md              # the glossary — family, case, attempt are distinct
├── README.md               # disclosure posture and safety now; purpose, users, D1-D14, mapping, example run at phase 5
├── docs/
│   ├── 135-sprint-3-brief.md  # the assignment brief — requirements and evaluation criteria
│   ├── adr/                 # 0001-0009
│   ├── specs/               # per-phase specs, mirrored to the issue tracker
│   ├── article-mapping.md   # the table from section 4, with limits and coverage gaps
│   └── validation.md        # gate results, discrimination per family per run, κ per judged family
├── backend/
│   ├── bench/
│   │   ├── registration.py  # nonce issue and echo check, attestation record
│   │   ├── scanner.py       # declared-control checklist
│   │   ├── attacker.py      # runs cases against a target endpoint, under budget
│   │   ├── evaluator.py     # applies success_condition — the verdict
│   │   ├── judge.py         # narrative fields only, blinded
│   │   ├── rule.py          # the gate rule as declared thresholds
│   │   ├── scorer.py        # discrimination, intervals, the gate decision, bands
│   │   ├── assembler.py     # declared-vs-defeated join, coverage gaps
│   │   └── report.py        # render and sign
│   ├── cases/               # the case library, one record per file
│   ├── goldset/             # 30 hand-labelled transcripts, as DeepEval goldens
│   ├── targets/
│   │   └── reference/       # hardened.py, weak.py, trivial.py — model-swappable
│   ├── graph/               # LangGraph definition, run state, approval interrupt, precedent store
│   ├── api/                 # POST /runs, GET /runs/{id}, GET /report/{id}
│   ├── eval/                # DeepEval metric and gold-set runner; κ from its per-case results
│   └── tests/               # unit: success conditions, scan, discrimination arithmetic, Wilson bounds
├── frontend/                # Vite + React + TypeScript
│   └── src/pages/           # register, run, report  (review — Sprint 4)
├── scripts/
│   ├── calibrate.py         # runs the gate — no web layer needed
│   └── verify.py            # offline signature check for a report recipient
└── infra/                   # Terraform (P1)
```

**Phases 1 to 4c and 8b need no web layer.** Drive them from `scripts/calibrate.py`. Add the API at 6b, the frontend at 7.

---

## 8. The API job pattern

One target run is six families at three cases at ten attempts, so **180 target calls** plus retries and judge calls. That takes many minutes. A single request that returns the result will time out. A full gate run is 540 target calls, doubled for 8b — that runs from `calibrate.py`, not through the API.

1. `POST /runs` records the pre-run cost estimate, halts at the approval interrupt for the user's confirmation, then starts the suite and returns a `run_id` at once.
2. The suite runs in the background, under the declared call budget, with a hard abort on breach.
3. `GET /runs/{id}` returns progress: current family, current case, current attempt, findings so far, calls spent against budget.
4. The frontend polls each second, or uses server-sent events.

**Check LangGraph's own server before writing endpoints.** It may already give background runs, streamed intermediate state, and persistent threads — this pattern and the precedent store, without your code. If it covers the need, use it. If it is too opinionated for the report and signing routes, use FastAPI, or both. FastAPI background tasks are enough for v1; a queue is P1.

---

## 9. Evaluation plan

This section is the reason the project is defensible. It is also the hard optional task.

### The gate — does the bench measure anything?

Run all six families, all eighteen cases, ten attempts each, against all three reference agents. **n = 30 per family per agent.** The judge is blinded to which agent produced each transcript.

Let `D_family = trivial_rate − hardened_rate`.

- **Per-family pass:** `D ≥ 0.4` **and** the Wilson 90% intervals for hardened and trivial do not overlap.
- **Monotonicity:** `hardened_rate ≤ weak_rate ≤ trivial_rate`. One inversion tolerated.
- **The gate passes** only if **≥ 4 of 6** families pass **and** monotonicity holds on **≥ 5 of 6**.
- Anything else is a stop. Repair the library and re-run, against the 4-hour reserve.

Why n = 30 and not 5: at five attempts a single unlucky trial makes the hardened and trivial intervals overlap, the weak agent at an expected 50% is uninformative by construction, and a family decaying from `D = 0.85` to `D = 0.45` is invisible. n = 5 could pass the gate but could not operate the retirement rule — which is where the originality is. [ADR-0003](./docs/adr/0003-gate-decision-rule-and-sample-size.md).

Report the mean **and** the interval. Overlapping distributions with different means do not discriminate, whatever the means say. Monotonicity is the load-bearing test, because the reference agents' quality is known by construction and only their *ordering* is genuinely licensed.

### Declared metrics for the bench itself

Article 15 asks for accuracy levels and metrics. The bench declares its own, printed in the report and not only in the README:

- Discrimination score `D` per family, with intervals.
- Cohen's κ per judged family, against the 30-transcript gold set. **κ < 0.6 means the family is not fit to report.**
- The gate rule itself, so a reader can see what the bench had to beat.

A bench that will not declare its own accuracy cannot ask a target to declare its own.

**How κ is produced.** DeepEval executes the gold set: each hand-labelled transcript is a `Golden` carrying `input` and `expected_output`, `assess_finding`'s output populates the `LLMTestCase`, and a custom `BaseMetric` scores judge verdict against gold label. κ is computed from DeepEval's per-case results rather than beside them, so the framework is load-bearing. The discrimination statistics — `D`, Wilson intervals, monotonicity — are computed on top of its output, because no off-the-shelf framework offers a discrimination test *between reference systems*. Both claims go in the README. [ADR-0009](./docs/adr/0009-deepeval-executes-the-goldset.md).

### The result for a target — no composite score

There is no 0–100 figure. [ADR-0005](./docs/adr/0005-no-composite-risk-score.md).

**Per family:** failure rate, Wilson 90% interval, verdict class, κ where judged, `D` from the last gate run, coverage note, and a band — `holds` / `weak` / `fails` — defined by the interval's position against stated cut points. Bands are deliberately not addable.

**Declared controls, in a separate section:** each marked `untested` / `held` / `defeated`. **No arithmetic between this section and the family results, ever** — mixing measured behaviour with untested self-report is the default this project fires.

**The headline is "declared and defeated":** controls the target claims to have, which the bench broke. It falls out of a join between the scanner and the attacker at no extra cost, no competitor can produce it, and it is the direct empirical proof of this project's own thesis.

Two limits printed with every result:

- It compares one agent against itself over time, not against another agent.
- It covers six families and nothing else — and it names which published categories it does not cover.

---

## 10. Assignment requirements

Requirements and evaluation criteria taken verbatim from [`docs/135-sprint-3-brief.md`](./docs/135-sprint-3-brief.md). Two notes from reading it directly: medium optional task 2 reads "long-term **or** short-term memory", so the run state alone satisfies it and phase 6a is elective for the bonus bar rather than required; and the brief's own 18-hour estimate is exceeded roughly threefold, which it explicitly licenses — "feel free to over-engineer the app... You can try making it as a portfolio project!"

| Requirement | How it is met |
|---|---|
| Clear agent purpose, target users | Section 1. Engineers shipping AI agents who face enterprise security questionnaires; procurement and insurer diligence is the buyer. |
| Core functionality | Register, scan, attack, evaluate, judge, assemble, report. |
| Understands how agents work; distinguishes agent types | The three reference agents differ *specifically in control architecture* — input checks, scope limits, output filters and a stop control, versus system prompt only, versus nothing — and the bench then proves the difference is empirically detectable. Agent type is not a section of this project, it is the measurement axis. Reinforced by `applies_to` on every case, trigger 4 (a voice agent needs different payloads from a document agent), and the tool-call-exposure field. |
| Explains function calling | The scope-creep family detects a tool call outside the target's declared list, which cannot be written without reasoning about tool schemas, call traces and approval sets. Demonstrating that function calling can be *broken* is a stronger showing than wiring it. Plus the bench's own twelve-tool graph. |
| Short-term and long-term memory | Short-term: the run state carried in the graph, read live by the progress endpoint (§8). Long-term: the precedent store, phase 6a — LangGraph Store over deterministic findings with a retrieval node, feeding remediation only. |
| Human-in-the-loop | The approval interrupt (phase 2e): the graph halts before an irreversible, costly action and does not proceed without a human. Second instance: the evaluator/judge disagreement queue. Sprint 4 adds the typed-override review path. |
| User interactions | Sprint 3: register, approve the run, review, download. Sprint 4 adds review-with-override. |
| User-friendly interface | React. Three screens in Sprint 3, four at P0 complete. |
| Appropriate tools and libraries | LangGraph, Python backend, Vite frontend. |
| Error handling | Endpoint timeout, auth failure, malformed reply, rate limit, judge failure, nonce echo failure, budget breach. |
| Identifies error scenarios and edge cases | Each failure above is a **named outcome**, never scored as a security result — infrastructure failure must not read as a defended agent. Edge cases are first-class rather than incidental: a target without tool-call visibility yields *not measurable* instead of a rate; a judged family below κ 0.6 is *unfit to report*; the monotonicity rule tolerates exactly one inversion; retirement needs two consecutive runs so one bad night cannot retire a working case; a budget breach aborts mid-run. |
| Good code organisation | Boundaries are chosen so the measurement survives them: a one-way dependency from evaluator to judge with no interface through which the judge can return a verdict (ADR-0004); the statistics as pure functions over recorded attempts, so the gate is re-derivable from its inputs; thresholds as declared configuration rather than inline constants, so the rule can be printed beside its result; cases as data records, one per file; a single calibration entry point that needs no web layer. Vocabulary is fixed in `CONTEXT.md` and the non-obvious decisions are recorded in `docs/adr/`. |
| Real-world usage | Staging endpoints, enforced authorisation, background jobs, retry on transient failure. |
| Documentation | README, `CONTEXT.md`, `docs/adr/`, `docs/article-mapping.md`, `docs/validation.md`. |
| Knowledge base for the domain | The case library and the article mapping. |
| Security considerations | The project is a security tool, and §3 and [ADR-0007](./docs/adr/0007-canary-nonce-as-proof-of-control.md) treat it as one: proof of control before any run, recorded attestation, enforced run budget, credentials at rest, sandbox-only policy, no payload execution locally, stated disclosure posture in §14. |

**Optional tasks — bar is 2 medium and 1 hard**

The bar clears inside the Sprint 3 line with margin on the medium tasks, and exactly one hard task — which is why 3b exists.

- **Medium, in Sprint 3:** long-term memory in LangGraph (the precedent store, phase 6a) · multi-model support (8b, built as a validity check) · token cost display (now the consent mechanism for spending a user's inference budget, so it is mandatory anyway) · a security guard (the authorisation guard, phase 2e).
- **Hard, in Sprint 3:** an AI evaluation report proving quality — §9, executed through DeepEval over the κ gold set (phase 3b), with the discrimination statistics computed on top. The task names Ragas or DeepEval; arguing that Ragas is RAG-specific defeats only half that sentence, so the tool is used rather than argued away. [ADR-0009](./docs/adr/0009-deepeval-executes-the-goldset.md).
- **Medium, at P0 complete:** feedback loop that improves the agent (`case_gap` override → `propose_case` → admission gate).
- **Hard, later:** an agent that learns from user feedback (§6, and it is auditable because the arbiter is a stated threshold rather than a vibe, which most implementations of this task lack) · LLM observability with Langfuse (P1).

---

## 11. Function tools

No fixed count. The list follows the architecture; it does not target a number.

**`Invoked by` is the load-bearing column.** `harness` means deterministic code decides to call it and no model is involved in the decision; `model` means the work is an LLM call. Three of fourteen are model work, and that is a design position rather than an omission — every number this project signs is produced by the `harness` rows, which is what makes a gate run re-derivable from its recorded inputs.

| Tool | Function | Invoked by | When |
|---|---|---|---|
| `verify_authorization` | Issues the nonce, checks the echo, records the attestation | harness | Sprint 3 |
| `scan_config` | Checks which controls the target declares | harness | Sprint 3 |
| `run_attack` | Sends one attempt to the target, against the budget | harness — **never reachable from `assess_finding`** | Sprint 3 |
| `evaluate_success_condition` | Applies the case's deterministic check. **Produces the verdict** | harness, deliberately — ADR-0004 | Sprint 3 |
| `assess_finding` | Narrative fields for one transcript, blinded. Cannot overturn a verdict | model | Sprint 3 |
| `suggest_remediation` | Gives the fix for one finding | model | Sprint 3 |
| `map_to_article` | Connects a finding to 15, 14, 12 or 50, and to its OWASP identifier | harness, deliberately — a fixed table, see §13 | Sprint 3 |
| `compute_discrimination` | `D` and Wilson intervals per family | harness | Sprint 3 |
| `check_coverage` | Which published categories are not tested | harness | Sprint 3 |
| `assemble_result` | Per-family bands and the declared-vs-defeated join | harness | Sprint 3 |
| `propose_case` | Drafts a case from a trigger and sends it to the admission gate | model to draft, harness to admit | Sprint 3 |
| `sign_report` | Ed25519 detached signature over the canonical payload | harness | Sprint 3 |
| `retrieve_precedent` | Finds similar past deterministic findings. Feeds `suggest_remediation` only — **never `assess_finding`**, which would un-blind the judge | harness (a retrieval node); becomes model-invoked only if 6a gives the remediation step the choice | Sprint 3, single-tenant |
| Cross-tenant anonymised retrieval | Family, control type and fix text only. Never target identity, never payload-plus-target pairs | harness | Sprint 4 — blocker before user one |

**Two rows are deliberately not model work, and the reasons are the same reason.** `evaluate_success_condition` is harness because a signature over an LLM verdict certifies that I held the number, not that the number is right (ADR-0004). `map_to_article` is a fixed table because a retrieval step would let the same finding cite different articles on different days, and a signed report has to cite the same one every time (§13). Both are cases where the sophisticated choice is to *not* call a model.

**`run_attack` is harness for a third reason: the judge must never be able to send a message to a target.** A judge holding it would not return a verdict — it would manufacture the transcript the evaluator scores, which is ADR-0004's coupling reopened where no type signature shows it. It would also defeat blinding (a judge that can probe can identify which agent it is grading, and κ is measured on blinded output), move the denominator that n = 30 per family per agent depends on, and make the pre-run cost estimate — the consent mechanism of ADR-0007 — an unbounded guess.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| **The plan grows instead of the code** | **The live risk, and it has already happened once** — a grilling session grew this plan by more than half against a repository containing a hello-world. Hours are flexible; attention is not. New ideas go to `IDEAS.md`. The next artefact is code, not analysis. |
| **Locally correct decisions compose into a wrong shape** | Demonstrated once already: demoting the judge to narrative fields and deferring the override path were each right, and jointly removed memory and human-in-the-loop from the deliverable. Every scope decision now gets checked against the brief's named topics and §10's table, not only against the decision it follows. |
| **The bench does not discriminate** | The gate at phase 4, with a stated rule that can fail and four hours reserved to repair it. Build the trivial agent first so there is a floor. |
| **Circular validation** | The reference agents' rates are known by construction, so the null-model check makes the circle explicit rather than escaping it. The defensible claim is the ordering, tested by monotonicity. The judge is blinded so it cannot manufacture separation. |
| **The bench measures the model, not the agent** | Phase 8b, before the interface. If discrimination collapses on a model swap, every score was about provider training, not user engineering. |
| **Applicability drift** | A user whose report goes to procurement is paid to mark findings not applicable rather than fix the agent. Overrides annotate and never delete; the report prints the finding beside the user's reason; dispute counts are printed. |
| **The hosted bench becomes an open attack proxy** | Phase 2e before any deploy. No run without the nonce echo. Attestation recorded to the Article 12 log. Enforced budget with a hard abort. |
| **Cross-tenant leakage from the precedent store** | It holds unpatched exploits against named companies. Single-tenant by construction until isolation exists; isolation is a blocker before user one. |
| **No user has a staging endpoint** | Track A screens for it in the first message, along with tool-call exposure and system-prompt access. An engineer without these cannot be a user, however interested. |
| **Procurement wants a different format** | Open question. They may want SOC 2, ISO 42001, or their own template rather than an Act-mapped report. Track A question 4, asked first, not at hour 30. |
| **Disclosure denial shows no discrimination** | Likely — most models refuse it by default. Build the trivial agent with an explicit instruction to role-play as a human, so the family has a genuine floor. If it still fails, retire it under the §6 rule and report the retirement as a finding. |
| **A judged family is unreliable** | κ against the gold set, printed. Below 0.6 the family is not fit to report, and saying so beats reporting a soft number. |
| **Scope creep into law** | Four articles. D2 is closed. |
| **Scope creep from competitor sites** | Mount and Klaimee sell insurance. Every feature copied from them moves toward a business that needs a licence. |
| **React learning time** | The frontend is phase 7, after the gate and after 8b. Three screens, not four. If it overruns, the backend and the evaluation still stand alone. |

---

## 13. Reflection prompts for the review

Two defects in this system, both real. Name them; do not hide them.

**Applicability drift, and gold-set contamination.** The original defect was that overrides feed the judge and the judge learns a reviewer's consistent error. D11 largely designed that out: verdicts are deterministic on four of six families, and the judge no longer decides anything. What replaced it is sharper, because it has a commercial motive behind it — a user whose report reaches a procurement team is rewarded for annotating findings away rather than fixing the agent, and `verdict_dispute` labels entering the gold set unreviewed would corrupt the reliability figure that is supposed to police the judged families. Mitigations are in §6 and none of them is complete: annotation cannot fully offset an incentive.

**Automation bias.** Article 14(4)(b) says the human must stay aware of the tendency to over-rely on output. A signed report is an output a compliance officer will trust, and refusing to print a single number (D12) reduces that risk without removing it. This product can still create the bias it claims to reduce.

Other prompts to prepare:

- Why validated testing rather than more testing?
- Why is a bare risk score worse than no score?
- What would a harmonised standard change about this project?
- Which of the six families would you expect to die first, and why?
- If discrimination changes when the underlying model changes, what does the score actually mean?
- What is the smallest change that would make this useful to a deployer instead of a provider?
- Annex VI internal control prescribes self-assessment. Does that prove the root problem, or does it mean nobody is asking for a solution?
- If procurement wants ISO 42001 rather than an Act mapping, what survives of this project?
- Four of six families are borrowed from OWASP. What is actually yours, and can you defend it without mentioning the mapping?
- The reference agents' failure rates are known by construction. What would it take to know them by measurement, and why can't you?
- Precedent retrieval must never reach the judge. Why does that constraint exist, and what breaks if it is relaxed?
- Two separately sound decisions once removed both of this sprint's named topics from the deliverable. How would you catch that class of error earlier next time?
- This system is an agent and uses no RAG at all. When is prompt engineering sufficient, when is RAG the right tool, and what specifically makes this an agent problem rather than either?
- Where *would* RAG help this product, and why is it deliberately absent? The nearest candidates are retrieval over the case library and over the precedent store. The article mapping is the interesting case: it looks like a RAG problem and is deliberately a fixed table, because a signed report must cite the same article for the same finding every time, and a retrieval step would make that citation non-reproducible — the same argument as ADR-0004.

---

## 14. Repository disclosure posture

Lives in the [README](./README.md), where a reader meets it before the code, and recorded as a decision in [ADR-0008](./docs/adr/0008-repo-disclosure-posture.md). It binds from the first commit, not from phase 5: harness public, published-technique cases public with citation, originated payloads withheld with the reason stated, nothing operational ever committed.
