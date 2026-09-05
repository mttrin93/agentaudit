# ADR-0066: The Action is a composite step in the caller's own repository, its page is the signed rendering, and the page fails closed

**Status:** accepted (#89, group J / #81)
**Date:** 2026-09-05

## Context

[ADR-0065](./0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md) built the
run nobody is sitting in front of. What is left is packaging, and packaging forces
four decisions that are not packaging: what kind of action this is, what it can reach,
what it leaves behind, and what a caller is pinning when they pin it.

The constraint the epic states, and this ADR is the implementation of: **not a hosted
runner and not a service.** The Action runs in the user's repository, on their runner,
against their staging target, with their keys and their inference budget.

## Decision

### 1. A composite action at `action.yml`, and not the other two

**Not a Docker action.** Docker means publishing an image, pinning it, and asking a
caller to trust a registry — for a tool whose entire install is `uv sync --locked`.
The image would buy hermeticity this project already gets from a lockfile, and would
cost a second supply chain.

**Not a reusable workflow.** A workflow cannot be called from a step. A caller with a
job that already builds their agent would have to restructure it around ours, and the
thing being asked for is one step dropped into a pipeline that exists.

So: a composite action, whose body is the four lines this repository's own CI already
runs — `astral-sh/setup-uv`, `uv sync --locked`, the entrypoint, an upload.

**It installs into `github.action_path`, never the caller's workspace.** The action's
checkout is where the bench lives; the caller's workspace is their project. The one
place the two meet is deliberate and is named: `PYTHONPATH` carries the caller's
workspace so a `--callback` written `package.module:attribute` resolves against *their*
checkout, and `callback-install` runs *their* command in *their* directory against the
bench's virtualenv, because a callback that imports their project needs their project
importable by the one interpreter that will import it.

**What `callback-install` costs is stated where it is offered.** It is the caller's
command in the bench's environment, so it can change what the pinned tag installed.
What the tag still pins after it is the bench and its case library — which is what the
artefact's `LibraryVersion` records and what §4's claim is about; what it no longer
pins is whatever their command touched. That is the caller's own project either way,
and the alternative — a second interpreter, or no callback support in CI at all —
is worse than a named trade.

### 2. Every input reaches the process through the environment, and three of them are secrets

**A `${{ inputs.x }}` interpolated into a `run:` body is the value pasted into a shell
before bash sees it.** A semicolon in an input is a second command, in a step holding
the caller's signing key and their provider key. So every input is bound to an
environment variable in `env:` and referenced as `$VAR`, and the one place a caller's
own text is executed is `callback-install`, which is their command, in their
repository, under their workflow's authorship.

**The endpoint and the bearer token stay out of argv.** `/proc/<pid>/cmdline` is
world-readable and every other process on the runner can read a command line, so
neither is ever a flag: the token has always reached the entrypoint through
`AGENTAUDIT_TARGET_TOKEN`, and this ticket gives the endpoint the same treatment with
`AGENTAUDIT_TARGET_URL` (`bench.URL_ENV`). A staging URL that answers jailbreak
payloads is the same kind of value as the credential for it — the artefact carries only
its hash for that reason — so the two travel the same way. The consequence inside
`scripts/bench.py` is that `--url` and `--callback` are no longer an argparse
mutually-exclusive group: exclusion sees only what was typed, and an
`AGENTAUDIT_TARGET_URL` left over from another job would then decide which of two
things a run attacked. The check moved into `main`, where both are resolved, and it
refuses zero targets and two.

**Three inputs are documented as secrets and one is required.** `endpoint` and `token`
because a bearer token in a workflow file is a bearer token in the git history, and a
URL that answers jailbreak payloads is not a thing to commit; `signing-key` because
ADR-0020 says no key, no boot, and it is `required: true` here for that reason. `nonce`
is a fourth where a caller planted one. `callback` is deliberately **not** a secret: it
is a path in the caller's repository and it belongs in the file where a reviewer sees
it, beside the attestation that names it.

**The first step of the action masks what it was handed.** `::add-mask::` over the
endpoint, the token and the nonce, before any other step runs. The bench prints the
target's URL beside its name — a terminal is a private place and a job log is not — and
a caller who passed the endpoint from somewhere other than their secret store would
otherwise publish it. The artefact hashes the endpoint for the same reason
(`registration.endpoint_hash`); this is the log's half of that.

**Nothing here reaches AgentAudit.** There is no telemetry, no callback home, and the
one network destination in the file is `actions/upload-artifact`, which uploads to the
caller's own workflow run. The two third-party actions are **pinned by commit SHA**,
with the release each SHA belongs to named in a comment — a tag is a pointer somebody
else can move, and these steps run with the caller's secrets in their environment.

### 3. The job summary is the signed rendering, and the page fails closed

**The page is `report.md`, read back off disk, under a preamble.** That document's
sha256 is inside the payload and the signature covers it, so a reader who downloads the
artefact and a reader who scrolls the run's page are reading the same bytes. Composing a
summary out of the result a second time would be a second document with nothing binding
it to the first — the drift `payload_for`'s single caller exists against, one surface
further out.

**What the preamble adds is the two things the rendering cannot hold**: where the three
files went, and the families `bench.withdrawn_for_want_of_a_plant` and
`deterministic_subset` dropped *before* the run. Those are absent from the measured
section rather than present at zero, which is correct in an artefact and unreadable on a
page whose alternative reading is that the family passed. They are printed in
`OperatorGap`'s own long words, because a reader meeting *not run* with no sentence
beside it is a reader guessing which of four answers it was (ADR-0004).

**And `scripts/summary.py` refuses a page that discloses.** ADR-0008 keeps payload text
out of the artefact *by construction* — attempts are not serialised, so the rendering
has no route to a turn — and that argument covers the rendering and does not cover a
file that assembles a page. A line added there later has nothing else standing in its
way, and the surface it would leak onto is the worst one this project has: **a CI log
is world-readable on a public repository, is indexed, and outlives the artefact's
retention window.** So the rule is checked rather than argued. `disclosures` reads the
live library back and names anything the page carries: a whole turn of a live case, or
one of the secrets the run was handed.

- **The whole turn, never a fragment.** A fragment is a phrase the library shares with
  ordinary English, and a guard that fired on those would be switched off within a week.
  The library's shortest turn is two hundred characters, so a whole-turn match is a copy
  and not a coincidence, and no length floor is needed to say so.
- **Named, never quoted.** A disclosure notice that printed the turn would be the
  disclosure, one file further on. The report says `indirect-injection-001 turn 1` and
  `a secret this run was handed (44 characters)`.
- **Refused, not filtered.** A summary with a turn cut out of it is a document somebody
  has to trust the cutter of. The three files are written and signed before the page is
  built, so a refusal costs the page and not the run.
- **`EXIT_DISCLOSED = 6`, and this is not a rate deciding an exit code.** ADR-0065 §4's
  invariant is that no *figure about the target* makes the step red; a control that
  fails closed and returns 0 is a control nobody hears. What a red step says here is
  *the page was refused*, and the artefact is on disk to prove the run itself completed.

### 4. Pinning is the whole of the reproducibility claim, and the trigger is not `push`

**A caller pins the action by tag; the tag pins the bench, which pins the library.**
`LibraryVersion` records that library in the artefact, so a caller on `@main` gets a
different library next month and a report that says so in a field nobody reads. The
README says it in those words: pin the tag, and read the library version in the artefact
when the numbers move.

**The documented triggers are `workflow_dispatch` and `pull_request` on a label, never
`push` on every branch.** The adjudicator runs on the caller's key and the target runs
on the caller's inference budget — the third statement of the attestation they made — and
a bench that runs on every commit spends money on every commit. That is documentation
rather than a mechanism, because the trigger is a property of the caller's workflow and
this action has no way to refuse one; what it can do is default `retention-days` low, keep
`deterministic-only` a first-class input, and say the sentence.

### 5. The bar is #90's, and the seam it gets is an output

The action does not decide whether the job is red on a rate. `report-directory` and
`report-json` are outputs, written **before** the bench runs so a later step can name the
directory even when the step exits non-zero, and the upload is `always()` so a red run is
still evidence. #90 reads the payload at that output and compares it against a threshold
declared in a committed file. Putting the comparison here would make the bar a property
of the runner rather than a threshold anybody can read (ADR-0003).

### 6. Where this differs from #89's input table, and why

#89 lists `families`, `attempts-per-case` and `reasoning-effort` as inputs of the step,
on ADR-0025's argument that a declared input of a run is recorded and so should be
reviewable. **They are not inputs of this action, and no flag was invented for them.**

`scripts/bench.py` does not call `plan_for`, and it passes no gap record into
`payload_for`. A family switched off through this action would therefore be **absent
from the signed report with no reason beside it**, rather than recorded as
`DeclaredGap.FAMILY_SWITCHED_OFF` the way `POST /runs` records it — which is precisely
the reading `BenchConfig.families` exists to make unavailable, one document further on
and now signed. An action input that produced that is worse than an action input that
does not exist. `reasoning-effort` has no seam at all outside `capability.py`: no script
exposes it.

What the action does expose is every narrowing the entrypoint already carries and
already prints: `deterministic-only`, and the plant declarations. Wiring the declared
gaps of a narrowed run through `payload_for` is the ticket that unlocks the other three,
it is the entrypoint's work rather than the packaging's, and it is **#138**.

## Consequences

- `scripts/bench.py` gains `--summary` and `--artifact-name` and one exit code. Nothing
  else about it moved: the same composition, the same attestation, the same ceiling.
- **This repository's CI gains a fourth job, `action`, and it is the disclosure test.**
  It runs `uses: ./` against `backend/tests/headless_agent:AGENT` served in the runner,
  `deterministic-only`, on a signing key generated and masked in the job — so it reaches
  no provider, needs no secret, and spends nothing. A page that carried a turn would
  exit 6 and the job would be red, over the real library and the real rendering rather
  than over a fixture. `scripts/verify.py` then checks what the step uploaded.
- **`.github/agentaudit-attestation.md` exists in this repository**, for that job's own
  run, and doubles as the demonstration of the `attestation` input's default path.
- A caller's `report.md` is now published twice: to an artifact that expires and to a
  page that does not. That asymmetry is one more reason no payload text goes into
  either, and it is stated on the `retention-days` input.
- **The Action cannot see the caller's target and neither can this project.** Nothing in
  `action.yml` sends anything anywhere the caller does not own, and there is no field on
  a run that could carry one back.

## Alternatives rejected

- **A Docker action.** A second supply chain and a registry to trust, for hermeticity a
  lockfile already gives.
- **A reusable workflow.** Cannot be called from a step; forces a caller to restructure
  a job they have.
- **A hosted runner or a service.** The epic's own constraint, and the one that would
  make this project the holder of other people's staging credentials.
- **A summary composed from the run's result.** A second document with nothing binding
  it to the signed one, on the surface where a divergence is most public.
- **Filtering the page instead of refusing it.** A redacted document is one somebody has
  to trust the redactor of, and the guard would then be a thing that can be partly wrong
  quietly rather than wholly wrong loudly.
- **Deciding the step's colour here.** #90, and ADR-0003: a bar in a runner is a
  threshold nobody can read.
- **Pinning the composed actions by tag**, as this repository's own CI does for itself.
  Acceptable inside a repository whose CI holds no secrets; not acceptable in a file that
  runs in a stranger's repository with their signing key in the environment.
