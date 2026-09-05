# ADR-0065: A CI attestation is committed prose by a named actor, a declared ceiling answers the halt, and one entrypoint writes the three files

**Status:** accepted (#88, group J / #81)
**Date:** 2026-09-05

## Context

The bench as a step in somebody else's CI needs one thing before any of it can be
built: **a run nobody is sitting in front of.** Three things in this repository refuse
one, and each of them refuses on purpose, so each gets an argument rather than a flag.

- **The attestation asks a human.** `console.attest` reads `input()`, and
  `scripts/console.py` exists as one module precisely so that a `--yes` has only one
  place it could ever be added: *"a consent mechanism with a flag to skip it is a
  convenience feature after all"* (ADR-0007).
- **The approval checkpoint waits for a terminal.** `run_under_approval` presents the
  estimate and halts; with no approver it *stays* halted (ADR-0028). A run that halts
  in a runner halts until the job times out.
- **Nothing writes the three files outside the API.** `report.json`, `report.md` and
  `report.sig` are the verifier's contract (`scripts/verify.py`), and `POST /runs` is
  the only thing that has ever produced them. `scripts/probe_target.py` prints rates
  and writes no artefact.

The temptation in each is a flag. A `--yes`, a `--assume-approved`, a `--sign-if-you-
can`. All three would be the same mistake in three places: a control that a caller
can switch off is a control that measures whether the caller wanted it on.

## Decision

### 1. The attestation moves into the caller's repository, and that is not a weakening

**A CI attestation is committed prose, reviewed in a pull request, made by
`github.actor` against a named target.** `backend/bench/unattended.committed_attestation`
reads a file the caller's own repository holds — the three statements written out in
full, one list item each — and constructs the same `Attestation` a terminal
constructs. What it does not do is *give* the run an attestation: a statement not
written out is passed as not made, and `Attestation.__post_init__` refuses, naming the
statement that was withheld. There is no argument on that constructor, and none was
added to `console.attest`, which still reads `input()` and still gains nothing.

Three properties make this evidence rather than paperwork:

- **The identity is authenticated.** `github.actor` is who GitHub says ran the
  workflow. A name typed at a prompt is who somebody says they are. The CI record is
  the stronger of the two on the one field a liability record turns on.
- **The prose is reviewed.** The statements arrive as a diff somebody approved, in a
  repository with a history, rather than as three keystrokes nobody else saw.
- **The record is unchanged.** `AttestationRecord.of` hashes the endpoint exactly as
  before, the provenance block carries the attestation exactly as before, and the
  Article 12 record is the same record.

**Where the prose lives is the caller's choice, and #88's own proposal is one of the
two.** The issue says the attestation *moves into the workflow file*; this entrypoint
takes a path rather than a format, and the parse is line-oriented — the `target:` key
and the three list items are found in a workflow's YAML exactly as they are found in a
dedicated Markdown file beside it
(`test_the_committed_prose_may_be_the_workflow_file_itself`). So the workflow file is
supported as proposed, and a separate committed file is supported too, because the
property that matters is not which file it is: it is that the statements are written
out somewhere a reviewer read them.

**The trade, stated: a committed attestation is made once and applies to every run of
that workflow, where a terminal one is made per run.** That is real. The compensation
is that changing it is a reviewed diff, and that what it authorises is pinned — which
is the next point, and the one that keeps this honest.

### 2. A committed attestation names its target, and a run against another one is refused

The document carries a `target:` line, and the entrypoint refuses unless the target it
is about to attack is that exact string — the endpoint URL, or the
`package.module:attribute` reference of a served callback (ADR-0059). Without it, a
committed attestation would authorise *a workflow* rather than *a run against a
target*, and a URL swapped into a workflow input in a later commit would point three
approved statements at an endpoint nobody attested to. That is the open-attack-proxy
failure ADR-0007 exists against, arriving through the door this ADR opens, so the door
is fitted with the check before it is opened.

**The whole list item is compared, never a substring of the document.** *We are not in
a position to say "I am authorised to test this endpoint"* contains the first
statement and is its opposite; a check that scanned the file for the wording would
read a refusal as consent. Items are unwrapped across lines and compared with
whitespace collapsed and case folded, because a file nobody can wrap is a file nobody
reviews — and nothing else is normalised, since a word changed is a different
statement, which is the entire point of writing them out.

**What this evidences and what it does not.** It evidences that a named, authenticated
person, in a reviewed commit, stated the three things about *this* endpoint. It does
not evidence that they read them on the day the run happened. A reader of the artefact
cannot tell a committed attestation from a terminal one, and deliberately so: the
record has always been *who, when, against which endpoint hash*, and all three are as
true here. What the artefact does distinguish, as it always has, is whether control of
the endpoint was **proved** or **declared** — and an unattended run against a URL has
nobody to paste a nonce, so it waives that proof and the document says so
(ADR-0007 as amended). A served callback plants its own canary and has it read back,
so it proves control the same way any other run does (ADR-0064).

### 3. A declared ceiling answers the halt, and an estimate over it is declined

`Approve` is `Callable[[BudgetPayload], Approval]` and was written for two
implementations (`approval.py`, `console.terminal_approval`: *"The same halt is
answered by an HTTP request at 6b. Only this function changes; the graph does not."*).
`unattended.ceiling_approval` is the second one. The graph is untouched: the interrupt
still fires, nothing above it spends, and the run still proceeds through the one edge
an answer decides.

- **The estimate is presented into the job log**, the same `presented` lines a
  terminal prints, so a job log and a terminal show identical figures.
- **The comparison is against `hard_ceiling`**, the figure a run may actually not
  exceed — the estimate with every message retried to its transport limit — and not
  against the smaller estimate, which would approve a run permitted to spend past what
  was declared.
- **An estimate over the ceiling is declined, not clamped.** Nothing is trimmed to
  fit: a run that dropped cases to reach a budget would sign a report over a library
  subset nobody chose, and the report would carry a library version that no longer
  describes what was sent (ADR-0058). The run records zero attempts and the step goes
  red with both figures named.
- **A ceiling is declarable in calls, in money, or in both**, and at least one is
  required — a `DeclaredCeiling` with neither is refused at construction, because a
  ceiling with no figure in it is a yes with extra steps.
- **A spend ceiling on a run nobody priced declines.** The bench never invents a price
  (ADR-0007), so a money ceiling on an unpriced run has nothing to compare against.
  It fails closed and says which of the two facts was missing, rather than proceeding
  on a comparison it did not make.

**Why this is not a `--yes`.** A `--yes` answers whatever it is shown. This answers a
figure with a figure, both declared in advance by different mechanisms — the ceiling
in the workflow file, the estimate by the bench's own arithmetic — and the answer can
be *no*. The consent surface is doing the work ADR-0007 built it to do; what changed
is that the party reading it committed their answer beforehand instead of typing it
afterwards.

### 4. One headless entrypoint, and a signing key is an input of it

`scripts/bench.py` takes a target (a URL, or a callback served over the contract by
ADR-0059's shim), the declared inputs, the committed attestation and the ceiling, runs
the suite, and writes `report.json`, `report.md` and `report.sig` into a directory
through `signing.publish_signed`. It is the composition `POST /runs` performs, called
from a `__main__` instead of from a route: the same `admitted_library`, the same
`run_calibration`, the same `api/report.payload_for`, the same `publish_signed`.

**Nothing about the report is re-implemented here**, which is the same rule
`verification.checked` follows: a second assembly would be a second document, and the
two would only have to disagree once for a recipient to receive a report the bench
believes it produced. `payload_for` lives under `backend/api/` because the API path
built it first; importing it from a script is the single definition being reused, and
a copy here would be the drift its own docstring warns against.

**A missing signing key is an error before the first send.** The key is read first —
before the attestation is parsed, before the library is loaded, before a port is bound
— because a factory with no key refuses to boot for exactly this reason (ADR-0020) and
a run that discovered it at the end would have spent an operator's budget on a document
it then refuses (ADR-0017). It exits under its own code, distinct from a refusal: a
workflow missing a secret and an operator declining a spend are different things for
the person reading a red step.

**What this entrypoint does not decide is whether the step passes.** It returns 0 for a
run that completed and wrote its artefact, whatever the rates say. Failing a step on a
declared bar is #90, and putting it here would make the bar a property of the runner
rather than a declared threshold anybody can read (ADR-0003).

### 5. A family whose artefact nobody planted is withdrawn, never sent

`TargetConfig.can_be_planted` reads an undeclared `plants` as *yes*, because reading
it as no would withdraw both plant-dependent families from every endpoint target in
the world (ADR-0061). What is left holding those two families honest for a URL is the
caller's own declaration — `note_planted` and `nonce_planted` at `POST /runs`, a typed
confirmation and a hand-planted nonce at a terminal — and **an unattended run has
nobody to ask**.

So the entrypoint declares for itself what nothing planted, and withdraws it. Without
that, the indirect-injection cases go after a note nobody filed and the leakage cases
go after a nonce that is nowhere in the target; both come back 0.00, and unlike a
terminal run's zero this one is *signed*. That is the exact failure ADR-0024 named —
a clean zero that reads as a defence — arriving in a document that travels.

Two declarations turn it back on, and both are statements about the caller's own
systems rather than switches on a control: `--nonce` (or `AGENTAUDIT_TARGET_NONCE`)
is the value they planted in the target's configuration, which also restores the proof
of control the run would otherwise waive; `--note-planted` is the declaration ADR-0024
already accepts for content the bench cannot see. A **served callback is untouched by
this**: it answers for itself, and a hook it does not implement withdraws its family
as `NotMeasurable` on the case's own record, which is the better of the two readings
and the one ADR-0061 chose.

The same reasoning is why this entrypoint makes the refusal `POST /runs` and
`scripts/probe_target.py` both make about `exposes_tool_calls` with no declared tools:
scope creep is read against that list, and against an empty one every call the target
makes scores as a finding a missing argument manufactured. Unattended, that finding
would be signed and shipped.

## Consequences

- `console.attest` and `console.confirmed` are unchanged. A piped or absent stdin is
  still a no, there is still exactly one `input()` behind the attestation, and the CI
  path does not reach either.
- The three files are now produced on two paths and by one chain. `scripts/verify.py`
  accepts what the entrypoint writes, demonstrated end to end rather than asserted:
  `test_a_headless_run_writes_the_three_files_and_the_verifier_accepts_them` runs the
  suite against a served callback and hands the directory to `verify.main`.
- **A committed attestation is a file in somebody else's repository, and this bench
  cannot see it change.** A caller who edits their staging endpoint's URL and forgets
  the attestation file gets a refusal, which is the safe direction; a caller who edits
  both in one commit has re-attested, which is the whole design.
- The waiver is the cost of an unattended URL target: no nonce is planted, so the
  data-leakage family has no canary and `control_proved` reads *declared, and not
  proved*. A caller who can plant a value out of band passes `--nonce` (or
  `AGENTAUDIT_TARGET_NONCE`) and gets the proof back; a caller using the callback shim
  never loses it.
- #89's action shells out to this entrypoint and hands it a `TargetConfig`'s worth of
  declarations and nothing more specific. #90 decides what makes the step red.

## Alternatives rejected

- **A `--yes` flag, or an `--attested` triple of booleans.** ADR-0007's own words: a
  consent mechanism with a flag to skip it is a convenience feature. Three booleans on
  a command line are the same thing with more typing, and they record nothing a
  reviewer ever saw.
- **An attestation in an environment variable or a repository secret.** Neither is
  reviewed and neither is prose. The evidence here is that somebody approved the
  sentences in a diff; a secret is approved by whoever can write secrets, and nobody
  can read it back to check what was attested.
- **A ceiling that trims the run to fit.** Rejected in the decision above: it produces
  a signed report over a subset nobody chose, which is worse than a red step.
- **Recomputing the estimate and skipping the interrupt.** The halt is the
  human-in-the-loop pattern and a real graph interrupt on purpose (ADR-0007): the run
  does not proceed because it *cannot*, not because a code path chose not to. A CI run
  that bypassed the graph would be a second control flow for the one decision this
  project treats as irreversible.
- **A second `run_calibration`-shaped composition inside the entrypoint.** It would be
  a second definition of what a run is, on the surface where the bench's own gate
  claims there is only one code path to a target.
