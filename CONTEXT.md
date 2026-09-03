# AgentAudit

An adversarial test bench that measures whether an AI agent's defences hold, and reports the outcome as portable evidence a reader who has never used the bench can check.

## Language

### The things under test

**Target**:
An AI agent belonging to a user, reachable as an HTTP endpoint, that the bench attacks.
_Avoid_: system under test, SUT, client agent

**Reference agent**:
One of three agents built by the project to known quality — hardened, weak, trivial — used to calibrate the bench. Test equipment; never reaches a user.
_Avoid_: baseline, control agent, dummy agent

**Declared control**:
A defence the user states their target has, recorded at registration. A statement, not a measurement.
_Avoid_: safeguard, mitigation, feature

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

**Case**:
One executable test belonging to a family, consisting of a payload and the criterion that decides its verdict — a success condition, or, for a judged family, the semantic question stated on the record. Three cases per family as authored; a family the admission gate has grown holds more, and the count is read off the library rather than declared.
_Avoid_: test, probe, scenario, payload

**Attempt**:
One execution of one case against one target. Ten attempts per case. The unit of
the denominator, and nothing that is not an attempt is ever counted as one: a
**turn** is not an attempt. A family's `n` is ten attempts times the cases the
library holds in it — thirty per family per agent as authored, and read off the
attempts that ran rather than asserted, because the admission gate can add a case to
a family ([ADR-0033](./docs/adr/0033-an-admitted-route-is-written-into-the-library.md)).
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
because its length varies with what the attacker decides to do.
_Avoid_: adaptive run, session, trial, attempt

**Turn**:
One exchange inside an episode — the attacker composes, the target replies. Turns
within an episode are dependent by construction, which is why an episode is not a
sample of attempts and why no rate is computed over turns.
_Avoid_: attempt, step, iteration, round

**Probe**:
One attacker-composed message sent inside a turn. Deliberately promoted to a term
of its own while remaining on the **case** avoid-list: *probe* must not be used to
mean *case*, because a case is a recorded payload with a stated criterion and a
probe is a message the model invented thirty seconds ago. The tool is `run_probe`
for exactly that reason — it sends something that is not a case.
_Avoid_: using it for **case**, payload, attempt

**Route**:
The path an episode took to a canary — the sequence of probes that worked.
Described in prose in the validation document; the payload text is never
committed.
_Avoid_: exploit, chain, attack path, kill chain

**Adaptive finding**:
A route an episode found. Reported in its own section, and **never a Finding** in
the sense below: it carries no rate, no interval, no band and no `D`.
_Avoid_: finding, vulnerability, breach, result

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
that does not expose its tool calls. A target the bench never measured must stay
distinguishable from one that resisted everything.
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
of. It and that request are the whole of what a target report says about the tier — an
elective family's `D` is a fact about the bench (ADR-0018).
_Avoid_: using it for **not measurable**, deselected, disabled, opted out, n/a

**Finding**:
A verdict plus its narrative — reason, article, external identifier, remediation, exposure type. Produced by the scored layer only; the adaptive layer produces an **adaptive finding**, which is a different thing and is named differently on purpose.
_Avoid_: issue, vulnerability, defect, alert

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
Median turns-to-first-success per agent, written `A_effort`, always reported with the count of censored episodes beside it.
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

**Trigger**:
The stated reason a case was added to the library. One of six.
_Avoid_: source, origin, motivation

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
A token planted where the bench will recognise it again. Three plantings, proving three
different things. Planted in the target's **configuration**, its appearance in output
proves a leak. Planted by a third party in **content the target fetches**, as an
instruction the target has to carry out to produce it, its appearance proves obedience
— the value was never inside the boundary, so nothing about it leaked. Planted in the
target's **session memory**, as an instruction carried out in a later turn where the
content that planted it is gone, its appearance proves persistence — a different claim
from obedience, and named apart for the same reason **probe** and **case** are: obedience
is shown while the instruction is still in front of the target, persistence is shown
after it is not, and a conflation of the two would let a same-turn success stand as
evidence that memory was poisoned. The third planting needs a target that retains
session state, and reports **not measurable** against one that does not.
_Avoid_: marker, tracer, honeytoken

**Nonce**:
The bench-issued value a user must plant in their target to prove they control it. Registration does not complete without its echo.
_Avoid_: token, challenge, secret, key

**Attestation**:
The user's recorded statement that they are authorised to test the target, that it is not production, and that they accept the cost and policy consequences.
_Avoid_: consent, agreement, terms, disclaimer

**Provenance block**:
The part of a report recording who ran it, against what, under which attestation, with which library version.
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
