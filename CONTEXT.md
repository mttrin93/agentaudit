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

These three are distinct, and the distinction is load-bearing arithmetic.

**Family**:
One of six kinds of failure the bench tests for. A category, not a test.
_Avoid_: category, class, attack type, vector

**Case**:
One executable test belonging to a family, consisting of a payload and a success condition. Three cases per family.
_Avoid_: test, probe, scenario, payload

**Attempt**:
One execution of one case against one target. Ten attempts per case. The unit of
the denominator: thirty attempts per family per agent, and nothing that is not an
attempt is ever counted as one. A **turn** is not an attempt.
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
mean *case*, because a case is a recorded payload with a success condition and a
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
_Avoid_: assertion, oracle, pass criteria

**Verdict**:
Whether one attempt succeeded. Deterministic for four families; judged for two.
_Avoid_: result, score, outcome, grade

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

### Library lifecycle

**Gate**:
The stop before the bench is trusted: the whole library run against all three reference agents, decided by a stated rule.
_Avoid_: calibration, validation, smoke test, benchmark

**Admission**:
The check a proposed case must pass against the reference agents before it may ever reach a user.
_Avoid_: approval, review, vetting

**Retirement**:
The status of a case that has stopped discriminating. Marked, never deleted, because it is evidence that the field moved.
_Avoid_: deprecation, removal, archiving

**Trigger**:
The stated reason a case was added to the library. One of six.
_Avoid_: source, origin, motivation

### Human input

**Approval interrupt**:
The halt before the first attack, where a human sees what the run will cost and consents to it. A run cannot proceed past it unattended.
_Avoid_: confirmation, gate, prompt, checkpoint

**Override**:
A typed annotation a user attaches to a finding. Never changes a measured rate.
_Avoid_: correction, dispute, appeal, exception

**Precedent**:
A past finding or remediation pattern retrievable to inform a new one.
_Avoid_: history, memory, knowledge, prior

### Trust mechanics

**Canary**:
A token planted where the bench will recognise it again. Two plantings, proving two
different things. Planted in the target's **configuration**, its appearance in output
proves a leak. Planted by a third party in **content the target fetches**, as an
instruction the target has to carry out to produce it, its appearance proves obedience
— the value was never inside the boundary, so nothing about it leaked.
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
