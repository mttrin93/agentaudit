# AgentAudit

An adversarial test bench that measures whether an AI agent's defences hold, and reports the outcome as portable evidence a reader who has never used the bench can check.

## Language

### The things under test

**Target**:
An AI agent belonging to a user, reachable as an HTTP endpoint, that the bench attacks.
_Avoid_: system under test, SUT, client agent

**Callback target**:
A **target** whose operator handed over a function rather than a URL. It is not a
third kind of thing: `serve_callback` wraps the function in an app on an ephemeral
loopback port and the bench reaches it through `send_message` like everything else,
so nothing downstream of registration can tell one from an endpoint somebody deployed
([ADR-0059](./docs/adr/0059-a-callback-target-is-served-over-the-contract.md)). What
the bench does *not* have is a second path in: a callback reached by any route other
than the contract would be the gate no longer exercising the code a user's run
exercises.
_Avoid_: in-process target, local target, embedded agent — each names the thing the
shim deliberately is not

**Reference agent**:
One of three agents built by the project to known quality — hardened, weak, trivial — used to calibrate the bench. Test equipment; never reaches a user.
_Avoid_: baseline, control agent, dummy agent

**Declared control**:
A defence the user states their target has, recorded at registration. A statement, not a measurement.
_Avoid_: safeguard, mitigation, feature

**Declared capability**:
Something the user states their target **can do**, recorded at registration. A
statement, not a measurement — the same footing as a **declared control** and a
different word on purpose: a control is a defence claimed, a capability is a power
claimed, and the two print in one section of a report where one word for both would
make a claimed power read as a claimed defence. Three of them today, and they are the
three properties the Agents Rule of Two is read over — processes untrusted input,
reaches private data or sensitive systems, changes state or communicates outward —
beside the fourth declaration that rule needs, whether a human confirms what the agent
does inside the session. Each is close to a **family** the bench measures and is
deliberately not one: nothing is sent to establish it, so it reaches no rate and has
no verdict. What the rule makes of the four is that target's *standing* — one of
five names and never a figure, in particular never a count of the capabilities held,
because a count is a composite score over self-report
([ADR-0038](./docs/adr/0038-the-rule-of-two-is-a-declared-property.md), ADR-0005).
Each capability is *held*, *declared absent* or *not stated*: three answers, because
silence is not a denial, is reported as silence, and buys nothing.
_Avoid_: using **declared control** for one, bare *capability* — the bench already
uses that word for what a *model* accepts (`capability.py`, temperature and
reasoning effort) — permission, feature, power

**Defeated**:
The status of a declared control that the bench empirically broke. The strongest finding the bench can produce.
_Avoid_: failed, bypassed, broken

### The units of testing

**Family**, **case** and **attempt** are three distinct things, and the distinction
is load-bearing arithmetic. So is the one between a **family** and an **elective
family**.

**Family**:
One of six kinds of failure the bench tests for. A category, not a test. Still six, and
deliberately: a kind of failure the bench can be asked for that is not one of the six is
an **elective family**, which is the term below and a different word on purpose.
_Avoid_: category, class, attack type, vector

**Elective family**:
A kind of failure the bench can be asked to test that is **not** one of the six. Measured
by the **gate** exactly as a **family** is — the three reference agents, a `D`, the same
floor, a **decay series** on each of its cases — and never counted in the gate's
decision ([ADR-0035](./docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
Named apart from **family** for the reason an **episode** is named apart from an
**attempt**: `Family` is the type both of the gate's counts are defined over, so a value
that could be assigned into it would be a family in a denominator ADR-0015 fixed at six.
The distinction is carried by the type and not by a flag, which is why `ElectiveFamily`
is its own closed set. An elective family that has held the floor for three consecutive
gate runs on **the field** becomes *eligible to enter the six*; entry is a
library-version event a human declares before a run, and never something a counter does.
_Avoid_: using **family** for one, seventh family, optional family, extra family

**Label**:
What a **family** is labelled with: the entries it claims on each of the two published
lists and the EU AI Act articles its failure bears on, held as one record per family
([ADR-0039](./docs/adr/0039-a-familys-label-is-one-record.md)). A *secondary* label and
never an identity — a family **tests one case within** an entry and it is not that
entry ([ADR-0002](./docs/adr/0002-owasp-ids-as-secondary-labels.md)). Not the same
claim as a **case**'s identifier, which says which case inside one published entry that
payload tests; neither is derived from the other, and a family whose cases claim no
published entry can still carry a label. An **elective family** carries a label of the
same shape in a table of its own, and an elective label makes no coverage claim: the
entry it names stays listed as untested until a family with cases claims it — and it
reaches no report, because what prints beside a family name in a **signed report** is a
claim about one of the six
([ADR-0044](./docs/adr/0044-a-familys-label-prints-beside-its-figures.md)).
_Avoid_: the family's OWASP number, category, mapping, taxonomy, using it for a
**family assignment** — which is a judgement about a **candidate** and not a record
about a family

**Article**:
An EU AI Act duty a **family**'s failure bears on, from a fixed table this project
wrote before any code (PLAN §4) and never a model's choice
([ADR-0004](./docs/adr/0004-deterministic-verdicts-judge-is-narrative.md)). A family
bears *articles*, plural: four of the nine bear two, and the first is the one the
failure principally bears on, so a reader with room for one prints that rather than
whichever sorted lower ([ADR-0040](./docs/adr/0040-a-family-bears-more-than-one-article.md)).
Article 12 is the exception on both counts — it applies to every family, so it sits on
no family's **label** and on a logged instrument disagreement instead. Nothing that is
not a family bears one: an article printed beside a **declared capability** would put a
legal duty next to a self-declaration in a document whose every other article sits
beside a **verdict**. Printed in the **signed report** beside the family's own figures,
and read off the family's **label** rather than off a **finding**
([ADR-0044](./docs/adr/0044-a-familys-label-prints-beside-its-figures.md)) — so a family
whose rate is withheld still bears its article, and a run made with no narrative
instrument prints the same column as one that explained every success.
_Avoid_: the family's article, the regulation, the clause, compliance requirement

**Case**:
One executable test belonging to a family, consisting of a payload and the criterion that decides its verdict — a success condition, or, for a judged family, the semantic question stated on the record. Three cases per family as authored; a family the admission gate has grown holds more, and so does one holding **variants** — a variant is a case, with its own ten attempts — so the count is read off the library rather than declared ([ADR-0055](./docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
Since [ADR-0051](./docs/adr/0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md)
it also states **how** it attacks: a **transform**, `plain` included, and the case it
transforms if it is a **variant** of one. Eighteen today and every one of them plain.
Its payload is a **sequence of turns** since
[ADR-0053](./docs/adr/0053-a-case-may-be-a-sequence-and-the-verdict-is-read-per-turn.md) —
one for a single-turn case, several for a fixed script, and a script is still one case
reaching one **verdict**. The turns of a scripted escalation are its **rungs**
([ADR-0054](./docs/adr/0054-a-crescendo-is-a-function-of-its-base-case-and-a-halt-outlives-a-turn.md)):
one rung is one turn, so a ladder of four is one **attempt** and not four. Every case
in the library today sends one turn.
_Avoid_: test, probe, scenario, payload

**Attempt**:
One execution of one case against one target. Ten attempts per case. The unit of
the denominator, and nothing that is not an attempt is ever counted as one: a
**turn** is not an attempt — and since ADR-0041 that sentence is arithmetic rather
than caution, because one attempt can be several turns. A memory-poisoning case plants
in one turn and is scored in the next, in one session, and it is still ten attempts
per case; what counts two of them is the budget, which counts calls on the
operator's endpoint and always has. Since
[ADR-0053](./docs/adr/0053-a-case-may-be-a-sequence-and-the-verdict-is-read-per-turn.md)
a **case** may be a fixed script, and then one attempt is that whole script in one
session: the turns of it are dependent on each other by construction and the criterion
is applied to each, with the attempt succeeding on the first turn that meets it. Two
attempts still share no session, which is the property that makes ten of them a sample
rather than a trajectory. A family's `n` is ten attempts times the **live** cases the
library holds in it — counting every admitted **variant** and excluding the retired —
which is thirty per family per agent for the eighteen authored plain records the library
holds today, and it is read off the attempts that ran rather than asserted, because the
admission gate can add a case to a family
([ADR-0033](./docs/adr/0033-an-admitted-route-is-written-into-the-library.md)) and a
variant of one is another case in it
([ADR-0055](./docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
The family's rate is one figure over all of them, and the counts per variant travel
beside it: pooling is legitimate because every variant measures the same failure against
the same criterion, and what it costs is that the figure depends on the variant mix — so
two runs are comparable only at equal library version and equal selection, and the signed
artefact prints that sentence rather than leaving it to be inferred from a hash.
_Avoid_: run, trial, call, iteration

**Run**:
One complete pass over one target, in two layers: the whole library at ten
attempts per case, then the adaptive layer. Only the first layer is scored.
_Avoid_: scan, session, job

**Run state**:
What a run knows about itself while it is happening — position in the library, findings so far, budget spent. The bench's short-term memory.
_Avoid_: context, progress, session data, working set

### The adaptive layer

The second half of a run, where the attacker chooses its own payloads. Nothing
here is scored. These terms exist so that an adaptive quantity can never be
mistaken in prose for a scored one — which is the same reason **family**,
**case** and **attempt** are kept apart.

**Scored layer / Adaptive layer**:
The two halves of a run, separated by who chooses the payload. The scored layer
runs recorded cases and produces every number the bench signs. The adaptive layer
runs an agent and produces none of them.
_Avoid_: phase one/phase two, static/dynamic, fixed suite/free play

**Adaptive attacker**:
The agent that attacks a target by a route of its own choosing, under a turn
budget, label-blind to which target it faces. Its five tools are model-invoked.
_Avoid_: red teamer, fuzzer, autonomous attacker, agentic attacker

**Episode**:
One attacker, one family, one target, one turn budget. The unit of the adaptive
layer, and deliberately not a unit of measurement: an episode has no denominator,
because its length varies with what the attacker decides to do. Its shape is a line
or a **tree** since
[ADR-0057](./docs/adr/0057-a-tree-is-the-harnesss-schedule-and-a-turn-is-still-one-probe.md) —
recorded as the **turn** each turn continued from, empty where it is the line — and
that shape is a shape and never a count: the turn budget is the only figure any
statistic reads off an episode.
_Avoid_: adaptive run, session, trial, attempt

**Branch policy**:
How the harness schedules an episode: how many probes may continue from one turn, and
how many turns stay live before it stops continuing from the oldest of them. The
harness's and never the attacker's — there is no sixth tool, and a model-invoked tool
that chose how wide to search would be one that chose how much of the operator's
endpoint to spend. Declared beside `T` and `k`, printed beside `A_effort`, and the
declared default is the line. A **pruning** rule is a choice about what the attacker is
allowed to forget, so it is stated: pruning by age can discard the branch that was
working, which is the second reading a negative `A_break` has beside a blinding
failure.
_Avoid_: search strategy, beam, the attacker's plan, tree budget

**Turn**:
One exchange inside an episode — the attacker composes, the target replies. **One
probe on the target's wire, wherever it sits in the episode's tree**: branching
multiplies the shapes an episode can take and multiplies nothing the operator pays
for, which is what keeps the turn budget a budget and `A_effort` comparable across a
linear attacker and a branching one (ADR-0057). A branch is not a turn. Turns
within an episode are dependent by construction, which is why an episode is not a
sample of attempts and why no rate is computed over turns.
_Not_: `shim.Turn`, which is the reply shape a **callback target** returns when it can
show its tool calls — a scored-side reply and not a unit of anything. Nothing is
counted in those, and no arithmetic reads both.
_Avoid_: attempt, step, iteration, round, branch

**Probe**:
One attacker-composed message sent inside a turn. Deliberately promoted to a term
of its own while remaining on the **case** avoid-list: *probe* must not be used to
mean *case*, because a case is a recorded payload with a stated criterion and a
probe is a message the model invented thirty seconds ago. The tool is `run_probe`
for exactly that reason — it sends something that is not a case.
_Avoid_: using it for **case**, payload, attempt

**Route**:
The path an episode took to a canary — the sequence of probes that worked, which in
a branching episode is one path from the root and not every turn it took.
Described in prose in the validation document; the payload text is never
committed.
_Avoid_: exploit, chain, attack path, kill chain

**Adaptive finding**:
A route an episode found. Reported in its own section, and **never a Finding** in
the sense below: it carries no rate, no interval, no band and no `D`.
_Avoid_: finding, vulnerability, breach, result

**Discovery count**:
How many **episodes** the adaptive layer broke one **family** with, printed on that
family's row beside what the scored layer measured, and always with the count of the
family's **censored** episodes beside it — two counts, each counted for itself and
neither derived from the other, so an episode that is neither is counted as neither.
A count of episodes and never a rate: it has no denominator, prints as no fraction and
no percentage, sits under no heading shared with a rate, and is a summand of nothing — the pairing is a **view**, so the signed artefact
gains no figure and the count is derived from the episodes it already carries
([ADR-0010](./docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md),
[ADR-0056](./docs/adr/0056-a-discovery-count-shares-a-row-with-a-rate-and-is-a-summand-of-nothing.md)).
A family the attacker never worked in has **no** count rather than a count of zero, and a
family measured *holds* with two discoveries against it is a reading nothing reconciles.
_Avoid_: adaptive rate, breaks, successes, adaptive findings count, episodes broken rate

**Censored**:
The status of an episode that reached the turn cap, or was aborted on budget,
without breaking the target. Distinct from "the target resisted", because the
attacker stopped rather than ran out of ideas.
_Avoid_: failed, timed out, unsuccessful, exhausted

### Measurement

**Success condition**:
The deterministic check that decides whether an attempt succeeded. Authoritative.
Four families have one; the two judged families have none and reach a verdict by
**adjudication** instead.
_Avoid_: assertion, oracle, pass criteria

**Verdict**:
Whether one attempt succeeded. Deterministic for four families; judged for two.
_Avoid_: result, score, outcome, grade

**Adjudication**:
The semantic decision that produces a **verdict** for a judged family. Not a
**reading** and not the judge: an adjudication *is* the verdict, a reading is the
narrative counterpart to one, and they are named apart so that no prose can put
the judge's opinion where a scored quantity belongs — the same reason **probe** and
**case** are kept apart. It is the instrument a judged family's reliability figure
is measured on, and it has no *unclear*: a judged verdict lands in a denominator,
so uncertainty about a transcript is carried by a reading and counted nowhere.
_Avoid_: judging, grading, the judge, reading

**Reading**:
How one transcript looked to the judge — the narrative counterpart to a verdict,
and never a verdict. A separate type for the same reason an **episode** is not an
**attempt**: `Attempt.verdict` is the scored quantity, and a reading that could be
assigned into it is a judge that overturns a verdict in one line nobody reviews.
Where the two differ the disagreement is recorded under Article 12 and neither
instrument is corrected.
_Avoid_: verdict, judgement, opinion, call

**Tool trace**:
What a target did in one turn, in the order it did it — the tool calls it made and
where the operator's stop signal landed among them. The whole of the evidence
behind scope creep and halt defeat, and the second thing `read_tool_trace` reads.
_Avoid_: log, call history, transcript

**Not measurable**:
A family's outcome against a target that cannot answer it — a third outcome
alongside a rate and a refused registration, never a rate of zero. Reached only
by a precondition unmet before any attempt is spent, which today means a target
that does not expose its tool calls, one that does not carry a session from one
turn into the next
([ADR-0041](./docs/adr/0041-the-persistence-canary-is-read-over-two-turns.md)), one
that holds no records about anybody other than its operator
([ADR-0043](./docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)), or one
that cannot be given a **plant** a family needs put in place before its attack turn
([ADR-0061](./docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)). A
target the bench never measured must stay distinguishable from one that resisted
everything.

The last of those is the one that is **not** always this word. A plant is only *not
measurable* where the bench can see the gap, which is a target it served itself from
a user's own function; against a URL the bench cannot see inside a content store, so
an unplanted family there is a **declared gap** — the caller's statement, undetected
here. The two are told apart by whose gap it is and whether the bench detects it, and
never by which family is missing.
_Avoid_: not applicable, skipped, unknown, n/a, zero

**Not requested**:
An **elective family** a run was not asked to test — the fifth of the absences a
report keeps apart, and never a rate of zero. Nothing was attempted, so nobody could
not answer and no case was missing: the tier holds the family and this run did not ask.
The **run** is what is *skipped* — *skipping is never advantageous* is a statement
about runs — and the family is what is *not requested*; the two words are kept apart
because one is about a gate run's scope and the other about a family's outcome in it.
Carried as its own block in the artefact, never inside the measured figures, which are
keyed on the six; printed in the **gate document** for a gate run and in the report's
per-family section for a target run, beside the declared request it is the complement
of. It and that request are the whole of what a target report says about the tier's
**figures** — an elective family's `D` is a fact about the bench (ADR-0018). What may
name one is a *boundary*: the reason beside a published entry that is still listed as
untested, and the stated limit on a **case** whose family tests the other half of an
entry. Both say a family exists and that this run's figures are not keyed on it, which
is the opposite of a coverage claim.
_Avoid_: using it for **not measurable**, deselected, disabled, opted out, n/a

**Finding**:
A verdict plus its narrative — reason, articles, external identifier, remediation, exposure type. Produced by the scored layer only; the adaptive layer produces an **adaptive finding**, which is a different thing and is named differently on purpose.
_Avoid_: issue, vulnerability, defect, alert

**Narrative failure**:
The outcome of a run whose two **narrative instruments** ran and failed — the judge
answered with something that is not a narrative, the remediation tool's answer could
not be read as a fix, or a reply was refused before a parser saw it. A fourth thing a
run's explanation can be, beside *no instrument was declared*, *the target succeeded
at nothing* and a **finding** per succeeded attempt, and it is none of those three:
the instruments were declared, the target succeeded, and no finding survives. It
carries no **finding** at all — findings are all of a target's successes or the
stated absence of all of them — and it moves no **verdict** and no rate: the run
finishes, every figure it measured stands, and the signed report is the report it
would have signed had the judge answered
([ADR-0050](./docs/adr/0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md)).
Not one of the report's absences: nothing in the artefact names it, and what it is an
absence of is the run's explanation.
_Avoid_: no findings, none, empty, judge error, failed run, not measurable

**Deterministic family / Judged family**:
The two classes of family, separated by how a verdict is reached. Judged families carry a reliability figure and a wider stated limit.
_Avoid_: hard/soft family, objective/subjective family

**Gold set**:
Hand-labelled transcripts held as the reference against which a judged family's reliability is measured. Labelled before any user sees the bench.
_Avoid_: ground truth, training set, benchmark, fixtures

**Discrimination score**:
The separation between the trivial and hardened reference agents on one family, written `D`. The bench's declared measure of its own accuracy, computed over attempts.
_Avoid_: sensitivity, power, effect size, separation

**Adaptive separation**:
The adaptive layer's counterpart to `D`, written `A_break`, computed over episodes and families rather than over attempts. Never written `D`, never printed in a `D` column, and it decides nothing.
_Avoid_: D, adaptive discrimination score, adaptive D

**Adaptive effort**:
Median turns-to-first-success per agent, written `A_effort`, always reported with the count of censored episodes beside it. A turn is a probe, so it is median *probes*-to-first-success and comparable across a linear attacker and a branching one — and what breadth costs is depth, which prints beside it (ADR-0057).
_Avoid_: time to break, difficulty, adaptive rate

**Band**:
A family's coarse summary for one target — holds, weak, or fails. Deliberately not addable across families.
_Avoid_: rating, grade, risk level, score

**Coverage gap**:
A published risk category the bench does not test. Listed in every report; not a defect.
_Avoid_: blind spot, limitation, exclusion

**Claimed in part**:
A published category a **family** claims, together with the half of that category the
family does not reach. Not a **coverage gap** and not one of the absences: the category
*is* tested, this far and no further. It exists because a claim is the only thing that
shortens the list of categories nothing reaches, so every claim is a coverage statement
getting wider, and the half it does not cover is declared beside it or the claim does
not load. Printed in every report beside that list, and it names no family — the block
is derived over the library's families and a report is about one target
([ADR-0037](./docs/adr/0037-a-claimed-category-is-claimed-in-part.md)).
_Avoid_: partial coverage, partially tested, mostly covered, gap

### Library lifecycle

**Gate**:
The stop before the bench is trusted: the whole library run against all three reference agents, decided by a stated rule.
_Avoid_: calibration, validation, validate the bench, smoke test, benchmark

**Gate run**:
One execution of the gate. Not a **run**: a run measures a target, a gate run
measures the bench, and no type carries both.
_Avoid_: run, job, validation run, calibration run

**Gate document**:
The dated Markdown a gate run started from the command line leaves behind. Prose,
written for a person, and never parsed to recover a figure.
_Avoid_: gate report, gate log, the gate output

**Gate citation**:
What a report carries about the gate run the bench last made: the outcome, the date,
the library version it was earned at, and the two files that hold the run — the
**gate document** and the **gate run record**. A fact about the bench, never a verdict
about a target. Not *the gate it last passed*: since ADR-0023 a gate run of any outcome
replaces it, so a bench whose last gate run failed cites that, and the citation is what
the instrument last put itself through rather than the best answer it ever got.
_Avoid_: gate result, validation stamp, certification, the gate it passed

**Gate run record**:
The machine-readable form of a gate run's decision, carrying each family's three
reference-agent rates and its discrimination score. Written **into the case library**,
by both entry points, beside the citation that names it — the citation carries the file
name and every reader resolves it there, so a record kept anywhere else is a citation
whose figures nobody can reach (ADR-0023, amended). Since ADR-0023 it is what the
**gate citation** *names* rather than something a reader has to know exists: the
citation carries the address and the record carries the figures, so recovering them
never means parsing the document. The **gate document** links to it.
_Avoid_: sidecar, gate JSON, gate summary, the gate's data

**Admission**:
The check a proposed case must pass against the reference agents before it may ever reach a user. The check and not the filing: a case that has cleared it is **admitted**, and the run that admitted it writes the record into the library ([ADR-0033](./docs/adr/0033-an-admitted-route-is-written-into-the-library.md)). What the admission *memory* holds is what was decided, which is a different thing from what the library holds (ADR-0032).
_Avoid_: approval, review, vetting

**Retirement**:
The status of a case that has stopped discriminating. Marked, never deleted, because it is evidence that the field moved.
_Avoid_: deprecation, removal, archiving

**The field**:
The real models a case's discriminating power is a claim about. Load-bearing since
ADR-0022, in prose and in the `measured_the_field` flag on every stored reading: a
gate run on a stub model — `stub:obedient`, the fixture with hardcoded replies that
exists so the pipeline can be exercised without spending money — measures the field
not at all, so its reading cannot retire anything. "The field moved" is therefore a
claim only a run against the field can make.
_Avoid_: the world, production, real life, the state of the art

**Decay series**:
Every reading one case has ever been given, in the order the gate runs happened, on
the case's own record. One reading per case per **gate run**, counts and never a
stored score. It is only ever appended to (ADR-0006), and the **retirement window** is
a view of its tail rather than the whole of it.
_Avoid_: history, the case's log, the readings, decay chart

**Retirement window**:
The readings the retirement rule is read over: the last two taken on the model of
the case's most recent reading. Not the last two readings of the **decay series** —
`D` is a reading about a case and a model together, so two models are not two
readings of one thing (ADR-0022). Scoping the window is not editing the series; the
readings outside it are kept, printed, and never deleted.
_Avoid_: the last two runs, the recent history, the retirement history

**Provenance**:
Who found a case — `authored`, `adaptive`, `user_gap` or `retrieved` — held as
`discovered_by` on the record, and the field that selects its **admission** bar
([ADR-0012](./docs/adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md),
[ADR-0047](./docs/adr/0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)).
Not a **trigger**, which is *why* the case exists, and the two are deliberately
independent in all but one direction. Not a **provenance block** either, which is the
part of a **signed report** recording who ran it — that is about a run and this is about
a case, and no type carries both.
_Avoid_: origin, discovered_by (in prose), where the case came from

**Trigger**:
The stated reason a case was added to the library. One of seven — PLAN §6's six, plus
*a published corpus was searched*, which was argued into the set rather than stretched
out of *a new technique was published*, because nothing about a row of a published
**corpus** is new and the library was narrow rather than behind **the field**
([ADR-0047](./docs/adr/0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)).
Never provenance, which is *who found it*: a gap a user reported and somebody filled
from a corpus is the third trigger and the fourth provenance, and the two fields exist
to say that without contradiction.
_Avoid_: source, origin, motivation, provenance

**Corpus**:
A published body of third-party material this project *searches* while writing cases,
indexed by meaning and never executed. Named apart from **library** for the reason
**elective family** is named apart from **family**: a library is what a run executes
and what a **library version** is the digest of, so a corpus called a library would be
either a set of run inputs no version covers or a version that moves every time an
index is rebuilt. One today — 33,416 published human/LLM interactions — and it is a
**build-time** instrument: a person queries it, no **run** and no **gate run** opens
it, nothing it returns reaches a rate, a `D`, a κ or a gate decision, and what is
committed is the *record* of the material rather than the material
([ADR-0045](./docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).
Not a **stored copy**, which is a transcription held in the tree; a corpus is fetched,
searched and discarded.
_Avoid_: dataset (for this project's use of it), the case pool, second library,
knowledge base, the index

**Candidate**:
One row a **corpus** search returned, before anybody has judged it. Deliberately not a
**case** and deliberately not labelled: it has no **family**, no verdict, no
**trigger** and no criterion, and it acquires none by being retrieved. The word exists
so that *retrieved* can never be read as *admitted* — the step from a candidate to a
case is a **family assignment**, which is a human judgement about which of the six a
phrasing belongs to, and a published safety taxonomy answers no part of that question. A **canary** is not a
candidate and neither is a **payload**: a candidate is somebody else's published text
that nothing in this bench has yet decided anything about. Once a person has made that
**family assignment** and the payload has cleared **admission**, what exists is a
**case** whose provenance is *retrieved* — so *retrieved case* names that, and is not
available for the thing no judgement has been made about
([ADR-0047](./docs/adr/0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)).
No **case** in the library is one today.
_Avoid_: retrieved case (for a candidate), hit, match, result, proposal

**Family assignment**:
The judgement that one **candidate** belongs to one **family**, and the instrument that
proposes one. Named apart from **label**, which is already spent: a label is the
published entries and articles a *family* carries, one record per family
([ADR-0039](./docs/adr/0039-a-familys-label-is-one-record.md)), so an instrument that
produced *labels* would produce those and this one does not. **An assignment is a
person's**: the instrument proposes, the person's answer is the record, and there is no
constructor that takes one without the other
([ADR-0046](./docs/adr/0046-a-family-assignment-is-proposed-here-and-decided-by-a-person.md)).
It carries a **family** and never a name, and never one of the two judged families —
every case grown from a **corpus** is `deterministic`, so no retrieved phrasing can
reach a κ. The instrument carries a measured agreement figure and a declared floor on
the terms adjudication's κ is held to, and as read on 2026-09-04 it is **below that
floor**: what licenses its use is not the figure but the seam, and its proposals say so
on every line they print (docs/validation.md). **The person travels onto the case
record**: a `retrieved` case carries who assigned its family, and one that names nobody
does not load, because a record with no person on it is the instrument's proposal
wearing a record's type
([ADR-0047](./docs/adr/0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)).
_Avoid_: label, labelling, labeller, classification, tagging, the candidate's family

**Technique**:
The attack one **payload** is an instance of, in a person's words — *the
prompt-marketplace role-swap template*, `DAN` — and the unit a **family** grown from a
**corpus** grows in. It exists because a count is the wrong measure of that growth: a
published corpus holds one phrasing many times, so twenty **cases** can be twenty
denominators' worth of **attempts** at a coverage of one, which raises `n` and nothing
else. So no two `retrieved` cases in one family may name the same technique, refused at
load, and the number of cases a family gains is whatever its distinct techniques support
([ADR-0048](./docs/adr/0048-a-retrieved-family-grows-by-technique-and-not-by-count.md)).

**A judgement and never a derivation.** It is prose rather than a closed set, because a
technique vocabulary is a taxonomy nobody here has validated and every closed set in
this project argues each member in a sentence. It is also not what
`NEAR_DUPLICATE_FLOOR` measures: that figure is a cosine distance between two rows of
one **selection**, and a technique repeating across the whole corpus is invisible to it
— which is the gap this word names. Like the **family assignment** beside it, the person
decides and the record carries the answer.

**Not a transform**, which is the term below and a closed set. A technique is
a judgement about somebody else's published text; a transform is a construction this
bench performs on a payload it already committed, so it is closed against what the code
implements rather than against what the field publishes
([ADR-0051](./docs/adr/0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md)).
One word for both would put an unvalidated judgement and a function over committed bytes
in one reader's sentence.
_Avoid_: attack type, category, cluster, variant, near-duplicate, transform, template
(for the judgement rather than for one instance of it)

**Transform**:
How a **case** attacks — the construction the bench performs on the payload the record
commits. The dimension the library did not have: a record said what it sends and never
how, so `data-leakage-001` and the same request wrapped in base64 were either one record
with two behaviours or two records nothing distinguished. Seven, closed, each argued in a
sentence, and `plain` is a member rather than a silence so that every record states how
it attacks. Deliberately **not** the two adaptive loops the same catalogue names: this is
a field of a **case**, and a scored record may not name what only an **episode** does
(ADR-0010). Named apart from **technique** above, and the argument is there
([ADR-0051](./docs/adr/0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md)).
Six of the seven are a pure function in `backend/bench/transforms.py`, applied when a
**variant**'s record is written and never on the wire; the five that copy a published
technique carry the address it was published at, and `plain` copies nothing from anybody
([ADR-0052](./docs/adr/0052-a-transform-is-a-committed-function-and-no-judged-family-gets-a-variant.md));
the seventh escalates over turns and waits for a payload that is a sequence.
_Avoid_: technique, strategy, enhancement, encoding, wrapper, mutation

**Attack selection**:
Which of the three **layers** a **run** runs — one message in one session, a fixed
script of turns, the adaptive attacker — and which **transforms** inside them. A
declared input the console sets, and the second one that moves a scored denominator:
fewer constructions is a cheaper run and a narrower reading, so a **case** whose
transform is switched off is **not sent** and a **family** left with nothing is reported
as *not run* rather than measured at zero
([ADR-0058](./docs/adr/0058-the-console-selects-layers-and-constructions.md)). It
travels in the signed **artefact** beside the **library version**, because two runs are
comparable only at equal library version and equal selection and a reader holding two
documents can check both halves of that or neither. The adaptive layer is one of the
three and carries no transform: what it would carry are the two loops **transform**
deliberately does not name, so its switch is the whole of the question about it
(ADR-0010).

**Named `AttackSelection` in code**, because *selection* is already spent twice — on the
**corpus** rows a person was shown (the sentence under **technique**) and on
`ElectiveSelection`. In prose the word is this one where a run is the subject, and the
qualifier is there so a reader of the code never has to guess which of the three.
_Avoid_: strategy set, attack config, technique selection, using it for the corpus's
selection

**Variant**:
One **case** carrying a transform, and a record of its own rather than something a run
wraps round a payload at send time — `data-leakage-001-base64` has its own id, its own
**admission**, its own **decay series** and its own place in the **library version**. It
names the case it transforms, and that pointer is provenance and never a payload the
loader fetches: a variant with nothing of its own to send would put the bytes on the wire
in the loader rather than in the library. A **family** is measured by the variants that
exist, so a transform that means nothing for a family is simply a variant nobody wrote
and needs no absence of its own
([ADR-0051](./docs/adr/0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md)).
A family's rate is **pooled** over the variants it holds — one figure, with the
successes and attempts of each variant published beside it so a recipient recomputes the
plain rate, the encoded rate or any subset. Pooling across **families** stays forbidden
(ADR-0005) and no **episode** is ever a summand
([ADR-0010](./docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md),
[ADR-0055](./docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
Never a **technique**, which is already spent on a judgement about a **corpus** row.
_Avoid_: technique, mutation, derived case, child case, using it for **technique**

### Human input

**Approval interrupt**:
The halt before the first attack, where a human sees what the run will cost and consents to it. A run cannot proceed past it unattended.
_Avoid_: confirmation, gate, prompt, checkpoint

**Checkpoint**:
The record on disk that an approval interrupt is waiting, and the state it will
resume with. Promoted to a term of its own while remaining on the **approval
interrupt** avoid-list above, on the same footing as **probe** against **case**:
*checkpoint* must not be used to mean the halt, because the halt is a decision a
human has not yet made and a checkpoint is a row in a file. One is what the bench
asks; the other is what survives a restart while it waits ([ADR-0028](./docs/adr/0028-the-approval-checkpoint-outlives-the-process.md)).
_Avoid_: using it for **approval interrupt**, save point, snapshot, session

**Override**:
A typed annotation a user attaches to a finding. Never changes a measured rate.
_Avoid_: correction, dispute, appeal, exception

**Precedent**:
A past finding or remediation pattern retrievable to inform a new one.
_Avoid_: history, memory, knowledge, prior

### Trust mechanics

**Canary**:
A token the bench will recognise if it comes back. Five of them, proving five different
things, and only four are *planted*. Planted in the target's **configuration**, its appearance in output
proves a leak. Planted by a third party in **content the target fetches**, as an
instruction the target has to carry out to produce it, its appearance proves obedience
— the value was never inside the boundary, so nothing about it leaked. Planted in the
target's **session memory**, as an instruction carried out in a later turn where the
content that planted it is gone, its appearance proves persistence — a different claim
from obedience, and named apart for the same reason **probe** and **case** are: obedience
is shown while the instruction is still in front of the target, persistence is shown
after it is not, and a conflation of the two would let a same-turn success stand as
evidence that memory was poisoned. The third planting needs a target that retains
session state, and reports **not measurable** against one that does not. Spelled out in
**the message the bench itself sends**, as two pieces an instruction has to join, its
appearance proves that an override on the channel the agent is *supposed* to obey
displaced what its operator configured — the same word *obedience* would cover it and
the claim is not the second one, because a check on the user's message says nothing
about a note the agent fetched and the two are counted on two denominators
([ADR-0042](./docs/adr/0042-the-canary-is-spelled-out-in-one-channel.md)). Which channel
carried the instruction is on the **case** record, and a payload cannot be written for
two of them. And **held by the target as a record about a third party** — planted by
nobody, because it was inside the boundary before the attempt began — its appearance
proves that a record about a person was disclosed. That is not the first planting under
another name: the first is material the *operator* placed there and its escape is a
boundary crossed, this is data the target holds about somebody who is neither the
operator nor the bench and its release is governance. The two are told apart by
arithmetic rather than by which family's name is on the record — a value a **nonce** this
bench issues could contain, or that could contain one, does not load — so no reply
carrying one is evidence for the other
([ADR-0043](./docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)).
_Avoid_: marker, tracer, honeytoken

**Planted artefact**:
The hostile content a **case** is attacked *with*, held on that case's own record.
Present on exactly the cases whose instruction arrives in **content the target
fetches** — a case in those families *is* a piece of content, so the **payload** is a
colleague's ordinary message and the attack is what the tool brought back. It carries
the two halves of the **canary** and never the join, so a target that quotes it back
while refusing it reproduces both halves and cannot be scored as one that carried the
instruction out; the joined value is derived and is written nowhere
([ADR-0060](./docs/adr/0060-a-planted-artefact-is-part-of-the-case-record.md)). Not a
**canary** and not a **payload**: the canary is what executing it produces, the payload
is what the bench sends, and this is what somebody else put where the target would find
it. The *act* of putting it there is a **plant** and is not this one.
_Avoid_: note, document, poisoned note, fixture, content

**Plant**:
The *act* of putting an artefact where a family needs it before that family's attack
turn — and, as a closed set, which acts those are: into the target's
**configuration**, or into **content the target fetches**. A **precondition** and
never a turn: it is performed before the run, no **attempt** is recorded for one, and
there is no route by which planting could arrive as a message
([ADR-0061](./docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)). It
sits at a fixed point in the run — attestation, **nonce** issued, plant, registration
probe, run — and it is **off every counter**: not the per-layer spend, not the
**attempt** list a rate is denominated on, not a **send** on the wire, and the
estimate an operator confirms itemises it at zero rather than leaving it out. The
**attestation** is what authorises it, because a plant already touches somebody
else's system; authorised and counted are different questions
([ADR-0062](./docs/adr/0062-planting-is-a-pre-run-step-off-every-counter.md)). A plant
that *fails* is not a withdrawn family: a withdrawal is a hook that does not exist,
and this is one that exists and did not work, so the run stops before its first
attempt and no family is measured. A
target that can be planted is one the bench can put the artefact into: a function
this bench served says so by implementing the hook, and a URL says so through its
operator, which is why the same missing plant is **not measurable** on one surface
and a **declared gap** on the other. The third planting the **canary** entry names —
session memory — is this one under another turn's name, performed by content the
target fetched. Distinct from the **planted artefact**, which is the content itself,
and from the **canary**, which is what carrying its instruction out produces.
_Avoid_: seed, setup, fixture, injection, priming

**Nonce**:
The bench-issued value a user must plant in their target to prove they control it. Registration does not complete without its echo.
_Avoid_: token, challenge, secret, key

**Attestation**:
The user's recorded statement that they are authorised to test the target, that it is not production, and that they accept the cost and policy consequences.
_Avoid_: consent, agreement, terms, disclaimer

**Provenance block**:
The part of a report recording who ran it, against what, under which attestation, with
which library version. Not **provenance**, which is a fact about a **case**.
_Avoid_: metadata, header, audit trail

**Stored copy**:
A committed transcription of one **edition** of a published category list this project
cites — OWASP's agentic list, OWASP's GenAI LLM list — holding each entry's identifier
and title and no judgement about this bench. Named for what it is rather than for what
it is a copy of: it is not the source, it says which edition it copies and where that
reading came from, and its whole value is that a claim the bench prints about an
external standard can be checked against something in the tree instead of against
somebody's memory. An identifier a **case** claims resolves to an entry in a *current*
stored copy or the case does not load, and one that names an edition must name the
stored edition — the 2025 and 2026 editions of the LLM list both carry `LLM07` and it
is two different entries
([ADR-0036](./docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)). A
superseded copy is kept for diagnosis and resolves nothing.
_Avoid_: the list, the standard, the taxonomy, the source, OWASP (for the copy)
