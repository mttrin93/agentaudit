---
status: accepted
---

# The Action reads the committed declaration, and a key declared twice refuses the run

[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) gave
the Action its input table: every claim a run makes about the target arrives as a
workflow input, bound into the environment, and read by `scripts/bench.py`.
[ADR-0100](./0100-the-mcp-server-has-no-privilege-the-console-lacks.md) and
[ADR-0102](./0102-the-declaration-file-carries-the-four-rule-of-two-declarations.md)
gave the MCP server a committed file, `agentaudit.toml`, and deliberately gave it *the
Action's own vocabulary*: `backend/mcp/declaration.py` reads the endpoint, the agent
type, the tool declarations, the plant declarations and the price under the names the
Action already uses.

So the two surfaces agree in shape and are declared from two places. The spec's third
story asks for the other thing — *one declaration read by both the Action and the MCP
server, so that a push-time run and an on-demand run are measuring the same declared
target* (`docs/specs/mcp-server.md` §3). Until that lands, an operator who edits
`declared_tools` in the file and forgets the `declared-tools:` line in the workflow has
two targets with one name, and nothing anywhere says so: scope creep is read against
the list, and the two runs read it against different lists. The signed artefact records
what each run was told, which makes the drift *discoverable* and not *prevented* — and
only by a reader holding both documents.

Teaching the Action to read the file is not a refactor. It is a change to the input
interface, and it forces three decisions: which inputs become file keys, which stay
inputs, and what happens when a caller supplies both.

## Decision

### 1. The reader is one reader, and it moves out of `backend/mcp/`

`declaration.py` moves to `backend/declaration.py`. Both surfaces import it. Nothing
about the module changes except its home and the depth of its links.

**Two readers of one file is the same defect one level down.** A second parse would
have its own idea of what an absent `exposes_tool_calls` means, its own coercion rules,
and its own answer to `declared_tools = "search"` — and the drift would then be between
two readings of one document rather than between two documents, which is harder to see
and no less wrong. The file's shape is settled in exactly one place, and the four
`_flag` / `_tristate` / `_count` / `_words` readers are the settlement.

It lived under `backend/mcp/` because the MCP server got there first, not because the
file is the MCP server's. The wall ADR-0100 states is unchanged and still holds at
import level: `backend/declaration.py` imports `tomllib` and nothing else, so
`backend/mcp/` reaching it reaches no bench module. The wall is one-directional and
always was — `scripts/bench.py` importing *the MCP package* to read a file about a
target would have been the accident worth stopping, and moving the module is how it is
stopped rather than reviewed for.

### 2. What the Action reads from the file: what is claimed about the target

`[target]` — `name`, `url`, `auth_token`, `agent_type`, `exposes_tool_calls`,
`declared_tools`, `retains_session_state`, `holds_personal_records`, the four the
Agents Rule of Two is read over, `sends`, `nonce`, `note_planted`. `[cost]` —
`price_per_call` and `currency`.

These are the keys whose answer is a property of the agent, true of it whoever asks and
however the run was triggered. They are the ones that must not differ between a
push-time run and an on-demand one, because every `attributed_cause` in the report is
read against them.

**Six of them the Action could not state at all before this.** The four Rule of Two
declarations, `retains_session_state` and `holds_personal_records` have no input in
`action.yml`; the last two have flags on `scripts/bench.py` that nothing exposes, and
the four have neither. A target audited only through the Action therefore reads
`not_declared` for all four in Annex IV section 3 for ever — which is, exactly,
[ADR-0092](./0092-the-rule-of-two-is-declared-on-the-register-walk-and-the-reading-is-the-backends.md)'s
defect surviving on the one surface that had not been looked at. Reading the file
closes it without inventing four more workflow inputs, and it closes it in the
direction ADR-0102 already argued for: a declaration that is committed and reviewed
rather than typed.

`sends` reaches `TargetConfig.retry` the way `TargetRequest` builds it, and an absent
key puts no ceiling on the wire at all rather than a number this reader chose — the
sentence `Declaration.sends` already carries.

**`nonce_planted` and `echo_waived` are not read.** They are the MCP surface's consent
seam, between `start_run` and `approve_run`, and the Action has no such seam: nobody
pastes a value into a system prompt inside a runner, which is why an unattended run
against a URL with no nonce waives its proof of control in `bench.WAIVED` and says so
in the artefact. Reading two waiver flags out of a file into a run nobody is watching
would be a waiver made once, in a commit, for every future run — the shape ADR-0007's
`echo_waived` was written against.

### 3. What stays a workflow input, in three groups

**Where the target is served from, and what runs it.** `callback`, `callback-install`,
`signing-key`, `openrouter-api-key`. A callback is `package.module:attribute` resolved
against the runner's own checkout and served on a loopback port this process bound; it
is a fact about the pipeline, not about the agent, and the file's reader refuses one by
name for that reason (`DeclarationRefusal.NOT_AN_ENDPOINT`). The two keys are secrets
of the caller's build, not declarations about the target.

**A file with a `url` and a workflow with a `callback` is two targets, and the
entrypoint already says so.** The MCP server refuses a declaration with no `url`, so a
file shared with that surface has one; a caller who then audits a *callback* through
the Action has declared two addresses under one name, and `bench.main`'s existing
*this run has no target, or two* refusal stops it. That is the right answer rather than
a gap: the committed attestation names one target and authorises a run against that
one. A caller with both is a caller with two targets, and two declarations is what they
need.

**Who attests, and to what.** `identity` and `attestation`.
[ADR-0065](./0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md) decided that
a CI attestation is committed prose naming the target it authorises, made by an
identity the runner authenticated — `github.actor`, *the stronger of the two on the one
field a liability record turns on*. The file's `[attestation]` table is three booleans
and a string. Reading them here would let a workflow attest by copying a line, under a
name nobody checked, and would replace an authenticated actor with a committed one. The
Action does not read `[attestation]` at all; the MCP server, whose operator is a person
in front of a client and not a runner, keeps it.

**What this run does, in this pipeline.** `bar`, `max-calls`, `max-spend`, `families`,
`attempts-per-case`, `adjudicator-model`, `deterministic-only`, `artifact-name`,
`retention-days`, `upload`, `summary`. None is a claim about the target and none can
drift against one: two workflows may legitimately run different subsets, at different
ceilings, against one declared agent — a nightly run of all six and a per-PR run of
three is a sensible thing to have, and neither run is lying about what it audited,
because a family switched off reaches the artefact as **not run** with the reason
beside it (ADR-0075).

### 4. Both given is refused — neither the file nor the input wins

A key that is declared in `agentaudit.toml` and also passed as a workflow input stops
the run before anything is sent, naming every key declared twice.
`bench.EXIT_DOUBLY_DECLARED = 7`.

**Precedence in either direction is a silent lie about a reviewed document.** If the
input wins, the committed file — the artefact of a pull request, the thing a reviewer
approved — is not what was audited, and the review approved a fiction. If the file
wins, the workflow line a maintainer added last week did nothing, and the next person
to debug the run reads it as the answer. In both cases the report is correct, the two
documents disagree, and no reader holding one of them can tell. Refusing is the only
answer with no silent case: it costs a red step on the first run after a caller adopts
the file, and it buys the guarantee that every key in a signed report has exactly one
home.

**So the moved inputs default to empty in `action.yml`, and the defaults live in the
entrypoint.** `name: target`, `agent-type: assistant` and `currency: USD` were defaults
written into the action's input table, and a default is indistinguishable from a value
a caller typed by the time a composite step sees it. Left there, every caller who
committed a file would collide on three keys they never wrote. The defaults are
`scripts/bench.py`'s already — `--name target`, `--agent-type assistant`,
`--currency USD` — so nothing about a run with no file changes, and *given* now means
given.

**Values the Action takes from the file are not masked, and this is a consequence
rather than an oversight.** The mask step covers the inputs, which is where ADR-0066 §2
says an endpoint, a token and a nonce belong: a URL that answers jailbreak payloads is
not a thing to commit. A caller who commits one anyway has published it, and the
`::add-mask::` of a value already in the git history protects nothing. The input path
is unchanged and remains the documented one; what the file's copies of those three keys
buy is that a caller who *has* committed them does not have to state them twice, and
cannot state them twice differently.

### 5. Reading the file is opt-in by path, and a path that is not there is refused

`action.yml` gains one input, `declaration`, defaulting to the empty string. Empty is
today's behaviour exactly: no file is read and the workflow declares the run. A
non-empty path — `agentaudit.toml`, resolved against `github.workspace` — is read, and
if it is not there the run is refused with `DeclarationRefusal.NO_FILE`.

**Not a default of `agentaudit.toml` with a silent fallback.** A default that fell back
to the inputs when the file was missing would make a typo in the path indistinguishable
from a deliberate workflow-declared run: the typo's run has an empty `declared_tools`,
and against an empty list every call the agent makes scores as a finding. That is the
refusal `bench.main` already makes for `--exposes-tool-calls` with no tools, arriving
by a route that bypasses it. Opt-in is one line in a workflow and it says which
document is in charge.

## Considered options

**Precedence to the workflow input, as an override.** Rejected, and it is the
conventional answer — CLI over config file is what most tools do. It is wrong here
because of what the file *is*. A config file is a convenience holding defaults; this
file is a declaration, reviewed in a pull request, and the report's attributions are
read against it. An override of a convenience is a convenience; an override of a
declaration is a run that measured something other than what was approved.

**Precedence to the file.** Rejected for the mirror reason, with one extra: it is the
direction that fails quietly for longer. A workflow input that stopped taking effect
produces no error, no warning and no diff — it produces a `with:` block that reads like
documentation of a run it does not describe.

**Warn on a collision and pick one.** Rejected. A warning in a job log is a warning
nobody reads on the green runs, and the run that matters is the green one: the whole
failure mode here is a report that is correct about a target nobody meant to declare.
This project has the same argument recorded about a summary page that discloses —
*refused, not filtered* (ADR-0066 §3) — and about a bar checked before sending. A
control that fails closed and returns 0 is a control nobody hears.

**Move the whole input table into the file and leave the Action three inputs.**
Rejected on §3. The attestation is the sharp case: it would put ADR-0065's
authenticated actor behind a committed string, one release after that ADR chose the
authenticated one deliberately. The ceilings and the family selection are the broad
case: they describe a run, several different runs may share one declared target, and a
file that fixed them would make the second workflow impossible rather than honest.

**Let `scripts/bench.py` import `backend.mcp.declaration` and leave the module where it
is.** Rejected. It reads in a diff as the Action acquiring a dependency on the MCP
server, which is not true and is the kind of untrue thing that becomes true later. The
move costs three relative links and buys a module whose home says what it is.

**Add `attestation` and `bar` paths to the file, as the spec's §31 sentence asks.**
Rejected, and the spec sentence is amended rather than implemented. Both name files in
the repository the *workflow* runs in; neither is a claim about the target; and no MCP
tool reads either — the MCP surface has no bar and takes its attestation from
`[attestation]`. Two keys read by one of two surfaces, describing that surface's own
checkout, is not one declaration serving both. The Action's defaults already point at
`.github/agentaudit-*`, which is the whole of what the sentence was reaching for.

## Consequences

- `backend/mcp/declaration.py` becomes `backend/declaration.py`. `backend/mcp/server.py`
  and the tests follow it; ADR-0100's and ADR-0102's links inside the module lose a
  `../`. `test_mcp_wall.py` is unchanged and still passes: the module it moved out of
  imports nothing the wall names.
- `scripts/bench.py` gains `--declaration`, one exit code, and the four Rule of Two,
  `sends`, `nonce_planted`-free target construction described in §2. A run with no
  `--declaration` is byte-for-byte the run it was.
- `action.yml` gains `declaration:` and empties the defaults of `name`, `agent-type` and
  `currency`. A caller who passes none of the three gets the same values as before,
  from one file further in.
- **This repository's own `action` CI job reads a declaration.** It commits
  `.github/agentaudit-smoke.toml` and passes `declaration:` to the step, so the reading
  path is exercised by the job that installs the action the way a stranger does — the
  argument that job was created under (ADR-0066 consequences).
- A caller adopting the file mid-life gets a red step naming every key they now declare
  twice, once, and then a workflow with fewer lines in it.
- The Action can now declare the four the Rule of Two is read over, so Annex IV section
  3 of a report from a CI run can print a standing. `docs/validation.md`'s line — that
  no real operator has ever declared any of this — is unchanged and now true of a
  fourth way of saying it.
