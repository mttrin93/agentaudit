---
status: accepted
---

# Two labels on a fix and no third, and the diff is what a proven one publishes

**#116, group K / #109. The last of the group.**

## Context

[ADR-0069](./0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md)
gave every explained failure exactly one answer to *what to change*.
[ADR-0070](./0070-a-signed-document-may-carry-a-remediation.md) let that answer into a
signed artefact, and #113 put it on the report screen.
[ADR-0071](./0071-a-finding-points-at-a-file-the-bench-read.md) let a finding point at a
file the bench read, in the one circumstance where the bench and the code are in the
same place — the composite Action of
[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md).
[ADR-0072](./0072-a-post-patch-re-run-is-its-own-record.md) built the loop that can
*try* such a fix: patch a throwaway copy of that checkout, re-serve the entrypoint out
of it, re-attempt the one case, and record the outcome as something that is not an
`Attempt`.

And it published none of it. ADR-0072 §4 says in as many words that nothing it built
reaches an artefact, and it left this ticket the three decisions it deliberately did not
make: **which label a fix carries on the two surfaces, what a screen shows of a change,
and where either sits in a document that travels.**

The reason those are one ticket and not three is that they are one hazard. A fix that
was never tested and a fix that was patched, re-served and re-attempted are two
different things; a report that presents them identically has taken the second's
evidence and lent it to the first. That is the hand-filled security questionnaire
[ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md) exists to displace —
an assertion about one's own system with nothing behind it — reproduced inside the tool
built to replace it, and reproduced with more authority because it arrives inside a
document with a signature on it.

**The epic's ADR table is stale by two.** #109 proposed four ADRs for this group; the
group has landed 0068, 0069, 0070, 0071 and 0072, and this is the sixth. ADR-0072
already noted it was out by one; recording it again here is cheaper than an epic that
says something untrue about what it produced.

## Decision

### 1. Two labels, and the third is unrepresentable rather than undocumented

`fix_standing.FixStandingReading` has two members and there is no third:

- **proven** — this bench applied the change to a throwaway copy of the caller's own
  checkout, re-served the target out of it and re-attempted the case, and the case no
  longer succeeds.
- **proposed** — it has not been shown to close its case.

Three mechanisms hold the pair closed, and none of them is a comment asking for it.

`FixStanding.stated()` matches the reading with **no fallback branch**, on
`attacker.verdict_of`'s and `PostPatchAttempt.stated()`'s terms: a third member added
upstream fails `mypy` at that match — *missing return statement* — rather than reaching
a reader wearing a sentence written for one of the other two. The sentence is the whole
of what a reader is handed, so inheriting one is the failure mode worth making
impossible.

*Proven* is **not a value a caller passes.** It is derived by `proving.standing_for`
from a `PatchProof`, and a `PatchProof` is produced by `prove_patch` and by nothing
else. §2 is what that buys.

And **it is not a boolean.** `proven=False` and *we did not test this* are the same bit
and different sentences. A bench that carried the bit would leave every surface to word
the second, and the wording a surface reaches for is the one that reads as *tested and
found wanting*. So the reading travels beside `evidence` — the re-run's own sentence
where there was a re-run, `NO_PATCH_WAS_APPLIED` where there was not — and the three
non-proving outcomes of ADR-0072 stay distinguishable under one label:
`STILL_SUCCEEDS` says the change was applied and did not close the case,
`JUDGED_AND_NOT_RE_DECIDED` says a judged case is not re-decided here, and
`NOT_RE_ATTEMPTED` says the fix is untested rather than tested and found wanting.

**Rejected: a third, middle label.** *Partly proven*, *proven for this payload*,
*likely*. Every one of them is a place an untested change can be filed and read as a
tested one, which is the entire hazard; and the second is worse than the first because
it sounds precise. What the middle state actually wants to express — *we tried and it
did not work* — is a **sentence**, and it has one.

**Rejected: a severity, a rank or a confidence beside the label.** D3, D12 and
[ADR-0005](./0005-no-composite-risk-score.md), named here because every reviewer UI this
design borrows from has a scale in exactly this position and promptfoo's is the one
already refused on the record. It is refused in the markup too: no tint stands for a
label, because a green *proven* and an amber *proposed* is a two-step severity scale
arriving as a colour.

### 2. Which label is reachable is a property of the target, and two refusals hold it

A shim or CI target with a checkout can reach **proven**: patch, re-serve, re-run. A
plain hosted endpoint can reach **proposed** and nothing else, because the bench cannot
restart somebody else's server. That is not a rule anybody has to remember:

1. `standing_for` takes a `PatchProof`. `prove_patch` needs a checkout on disk to copy,
   a file inside it to patch and an entrypoint to re-serve out of the copy — so a target
   that is a URL has no route to one.
2. `assembler.ReportedFinding.__post_init__` refuses a `PROVEN` standing on any finding
   whose `SourceAnchor` reading is not `ANCHORED`. Every other reading is a run with no
   located file (ADR-0071 §3), and an endpoint target always has one of them. This is
   #114's own note — *a finding with no anchor can only ever carry proposed* — made a
   refusal rather than a convention, and it is where a hand-built record is caught.

A third refusal is local: a `FixStanding` labelled proven that names no patched file is
refused at the record's own door, because *proven* means a patch was written and a case
re-run, and a proven standing with no file under it is a claim with no act behind it.

**Where `standing_for` lives is decided by ADR-0072 §4's wall, not by taste.** Nothing
that computes a figure or writes one into an artefact may reach `proving` or
`throwaway` — a post-patch re-run is made against a different target revision, and a
serialiser that could see one is a serialiser that could put one in a denominator. So
`fix_standing.py` holds a record, a sentence and a diff over two strings and imports
neither module, `assembler.py` imports only that, and `standing_for` sits in `proving.py`
on the proof's own side of the wall. **The direction is proof to label and never label
to proof**, and the import test ADR-0072 §4 already installed is what enforces it.

### 3. What a diff publishes, and what it withholds

The change travels as a **unified diff of exactly one file**, computed once by the bench
from the file it read and the contents the operator supplied, with three lines of
context. It reaches the payload, the Markdown document and the screen; a surface never
computes one, which is `api/report.ts`'s standing rule and, for a diff, also the
disclosure answer — what a reader is shown is what this bench decided to publish and
never something a client assembled, because the payload is what a signature covers
([ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md)).

**This is new material about somebody's code in a document that travels, and it is a
real tension with ADR-0071 §4**, which withholds every byte of the file the bench read
and the absolute path along with it. The tension resolves on *who chose*, and the answer
is narrow on purpose:

- ADR-0071 withholds bytes the bench read **uninvited**, on its own initiative, to
  count newlines and verify one line of a report. Nobody asked for their contents to be
  published, so none of them is.
- A patch is material the **operator constructed and handed over** for the express
  purpose of having a proof made, on a run they started, in their own repository, on
  their own runner. The lines it changes are the claim; the three lines of context are
  the least without which those lines are unreadable.
- So the published set is: the lines the change touches, their context, and the path
  **relative to the checkout root**. Never the file, never a second file, never the
  absolute path, and **nothing at all on a run that patched nothing** — which is every
  run this repository's own API serves, since a hosted bench has no checkout to patch
  and `ReportConfig.standings` is empty there by construction.
- A change longer than `MAX_PUBLISHED_DIFF_LINES` publishes **no diff and a stated
  absence**, not half of one. A `Patch` is a whole file (ADR-0072 §2), so a patch that
  rewrote a large module would otherwise put that module into a signed artefact at a
  size nobody reviewed. Half a diff is worse than none: it is a change a reader takes
  for the whole of one, and the missing half is the half its author would want read.
  The label is unchanged by the truncation — what was proven was proven.

**Rejected: the diff on the screen only, and not in the artefact.** It is the reading
the ticket's own wording invites, and it does not survive contact with this codebase:
the report screen draws the signed payload, so *screen only* means either a second
unsigned channel for material about the operator's code — a new surface with none of
ADR-0070's disclosure machinery on it — or a diff the recipient of the document cannot
see. And the second is the worse half: *proven* is an evidentiary claim in a signed
artefact, and a claim whose evidence is withheld from the person the document is for is
exactly the self-graded assertion this whole ticket exists to prevent.

**Rejected: a diff a model wrote, or a patch a model wrote.** ADR-0072 §2 already
settled that a `Patch` is the caller's own code; this adds that the *diff* is likewise
derived and never authored. Both sides of it are files, and the bench subtracts them.

### 4. What *proven* asserts, in the sentence a person reads

The claim is **about one case against one patched revision**: *this case no longer
succeeds*. It is not *this family is closed* and not *your agent is fixed*.

`n = 30` per family ([ADR-0003](./0003-gate-decision-rule-and-sample-size.md)), and a patch that
defeats `indirect-injection-001`'s exact payload while leaving the family open is
overfitting to the test — the failure mode a proof loop invites. Re-running the whole
family with its interval is the real claim, and it is thirty attempts of the operator's
money and theirs to choose (ADR-0072 §5).

That arithmetic reason is carried in prose everywhere the label is:
`PostPatchAttempt.stated()` says it, `FixStanding.stated()` composes with it rather than
rewording it, the document says it once above the blocks in
`WHAT_A_LABEL_ON_A_FIX_ASSERTS`, and the screen draws it under the label rather than in
a legend — a fact carried somewhere else is a fact a screenshot loses.

**And the screen says it under all four readings of the section, not only where there
is a block.** Written app-side, on `A_MODEL_WROTE_THESE_SENTENCES`'s own precedent: it
is a fact about what this section's words mean rather than a fact about any run, and
the reading it matters most on is the common one — a bench attacking a URL, where every
fix on the page is *proposed*. Everything the screen says *about a particular fix* is
still the payload's own wording, character for character.

**And nothing here is a figure.** No count of proven fixes, no proportion of them, no
field one could arrive in. A label is a name off a closed set, a diff is text, and no
rate, band, interval or `D` may read either (D13,
[ADR-0006](./0006-overrides-never-change-a-measured-rate.md)). A reader who wants to
count the proven blocks counts them, exactly as they count the findings.

### 5. The supply surface is a command line, and the file is the caller's own

`scripts/bench.py --fix case-id=path/to/replacement.py`, repeatable, one case per fix.
The entrypoint that resolves the anchor is the only process in this repository holding
both a workspace and an object imported out of it (ADR-0071), so it is the only one that
can patch a copy of the first and re-serve the second — and it is where the supply
surface belongs for the same reason.

`proven_fixes` **never ends the run.** A run reaching it has already spent the
operator's inference budget and holds every figure it will ever report, so a fix that
cannot be read, cannot be applied or names a case that did not succeed is printed and
skipped, and stays *proposed* — `anchor_for`'s argument one field along (ADR-0071 §5).
What it refuses outright it refuses **at the parser**, before a single call goes on the
wire, because that is the only place a refusal is free: a `--fix` with no `=` in it is a
command line the caller mistyped, and a value quietly re-read is a patch applied to a
file nobody named. A case named by two `--fix` values has **neither** change tested and
says so — not *the last one wins*, because two files offered for one case are two
changes and proving one of them would put a label on a change the caller may not have
meant, which is §1's blur arriving through a command line instead of through a word.

### 6. `ARTEFACT_VERSION` does not move

`fix_standing` is an additive key inside a block a recipient already reads, and nothing
is removed, renamed or re-typed: a verifier reading the previous shape reads every field
it read before, checks the same signature and re-derives the same arithmetic. That is
the footing #43 set for the `elective` block, #47 for `claimed_in_part`, #45 for
`edition`, #52 for `label`, ADR-0070 for `findings` and ADR-0071 for `source_anchor`.
Moving the version would make every previously issued artefact read as an older shape to
`verification.py`, which refuses one it does not know — a real cost, paid for a key
nothing needs to have been told about (ADR-0044 §8).

## Consequences

A fix in a signed AgentAudit report now carries evidence or an admission, and the two
cannot be confused: `proven` is unreachable without a checkout the bench copied and a
case that stopped succeeding, and every other fix says, in a sentence, that it was not
tested and why. The bench's own reports — every run its hosted API serves — carry
*proposed* on every finding, which is the honest reading and the common one.

A reader of the document gets the change itself where there was one, fenced, and the
same change on the screen collapsed behind a header carrying the label and the file. A
reader of a document with no proof in it gets one extra sentence and no gap.

The costs are stated. The signed artefact now contains lines of the operator's own
source where they asked for a proof, bounded and relative-pathed, which §3 argues and
which nothing before this ticket did. `ReportedFinding.stated()` is one clause longer,
so the golden rendering digest moved. And a third label remains cheap to add and
expensive to add correctly — the enum, the match, two refusals and this ADR are what
somebody adding one has to get past.

## Alternatives considered

- **A boolean `proven`.** §1: the same bit for two facts, and the surface writes the
  sentence.
- **A third, middle label.** §1: the hazard has a name and it is *the middle state*.
- **Severity, ranking or confidence beside the label.** §1, and D3/D12 refused it
  before this ticket existed.
- **The diff on the screen only.** §3: it means an unsigned side channel or a claim
  whose evidence the recipient cannot see.
- **`standing_for` on the report side, beside the record it builds.** §2: it would
  import a `PatchProof` into the modules that write figures, through ADR-0072 §4's wall.
- **Proving a whole family before saying *proven*.** §4: it is thirty attempts of
  somebody's money, and it is theirs to ask for. The per-case label plus the sentence is
  what this bench can honestly say for free.
