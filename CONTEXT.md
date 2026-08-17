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
One execution of one case against one target. Ten attempts per case.
_Avoid_: run, trial, call, iteration

**Run**:
One complete pass of the whole library against one target.
_Avoid_: scan, session, job

**Run state**:
What a run knows about itself while it is happening — position in the library, findings so far, budget spent. The bench's short-term memory.
_Avoid_: context, progress, session data, working set

### Measurement

**Success condition**:
The deterministic check that decides whether an attempt succeeded. Authoritative.
_Avoid_: assertion, oracle, pass criteria

**Verdict**:
Whether one attempt succeeded. Deterministic for four families; judged for two.
_Avoid_: result, score, outcome, grade

**Finding**:
A verdict plus its narrative — reason, article, external identifier, remediation, exposure type.
_Avoid_: issue, vulnerability, defect, alert

**Deterministic family / Judged family**:
The two classes of family, separated by how a verdict is reached. Judged families carry a reliability figure and a wider stated limit.
_Avoid_: hard/soft family, objective/subjective family

**Gold set**:
Hand-labelled transcripts held as the reference against which a judged family's reliability is measured. Labelled before any user sees the bench.
_Avoid_: ground truth, training set, benchmark, fixtures

**Discrimination score**:
The separation between the trivial and hardened reference agents on one family. The bench's declared measure of its own accuracy.
_Avoid_: sensitivity, power, effect size, separation

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
A token planted in the target's configuration whose appearance in output proves a leak.
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
