---
status: accepted
---

# A finding points at a file the bench read, and says so plainly when it could not

A file and a line is the first thing every reviewer UI this project borrows its findings section from prints, and it is the one thing this bench structurally could not know. **A target is a URL.** `TargetConfig` is a name, a url, a token, an `agent_type` and two declarations, and `send_message` is the only path to one; there is no source tree anywhere in the picture and there has not been one since the contract was written. The reviewer UIs are not doing something cleverer — their subject line is a *working tree*, not a service.

[ADR-0066](./0066-the-action-is-a-composite-step-in-the-callers-own-repository.md) changed that for exactly one population and nothing else does. The composite Action runs in the caller's own repository, on their runner, with their checkout on disk and a `--callback` the bench imported out of it. That is the only circumstance in which the bench and the code are in the same place, and the only alternative source of a checkout would be asking a user to upload their repository to this bench — which is not a thing this project should offer.

So the anchor exists *sometimes*, and most of this ADR is about the times it does not.

## 1. It is a **source anchor**, and never the bare noun

**Decision.** The record is `SourceAnchor`, the module is `bench/source_anchor.py`, the payload key is `source_anchor` and the screen field is `sourceAnchor`. The word *anchor* alone is not used for it anywhere.

*Anchor* is already load-bearing in this codebase and has been since [ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md): the two reference agents' constructed rates are the anchors a band is read against, `frontend/src/report/report.ts` describes both of them by construction, and `test_assembler.py` names them a dozen times. A second unqualified *anchor* meaning a file path would put two different subjects under one word in one report — a band is anchored to an **agent**, a finding is anchored to a **file** — and CONTEXT.md's terms are load-bearing arithmetic rather than synonyms.

The alternative was to rename the band anchors, which would touch ADR-0014, the band vocabulary, the screen and every test that reads it, in order to free a word for a field most reports do not carry. The qualifier is cheaper and it is also more accurate.

## 2. The anchor is evidence, and it is evidence of the entrypoint

**Decision.** The anchor is the definition site of the object the bench served — the file and line the interpreter reports for the caller's `--callback` — verified against the checkout before it is published. It is **not** a claim about which line caused the failure, and the sentence the record prints says so.

Two things are refused here, and they are refused for the same reason.

**A model is not asked where the bug is.** A model asked to invent a plausible filename for a repository it cannot read would be a fourth **instrument** producing unverifiable claims about somebody else's code, and #64's precedent applies without amendment: no unvalidated instrument sits upstream of anything a reader relies on. The fix for an instrument like that is not κ — there is no gold set for *which line of a stranger's repository is at fault* — it is refusing to print one. This is the same argument [ADR-0068](./0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md) made about the attributed cause, arriving one field along.

**And the bench does not infer one either.** It has no mapping from a defeated control to a statement: `family_claimed_by` is 1:1 over four controls and says nothing about code, and a heuristic that walked the checkout looking for the word `filter` would be a guess with a filename attached to it, which is worse than no filename. What the bench genuinely knows is which object answered the messages, so that is what it points at — and because a reader who took the line as an accusation would be reading a claim the bench never made, `SourceAnchor.stated()` states which of the two claims it is making, in the sentence, on the page.

**One anchor per run, not one per finding.** It is a fact about where the run was made rather than about any one failure, so it is resolved once at the entrypoint and passed once into `reported_findings`. A per-finding anchor would be a field inviting exactly the inference above.

## 3. The absence is a reading, and it is the ordinary case

**Decision.** `SourceAnchorReading` is a closed set of six — one located reading and five named absences — carried in the payload beside a sentence, and printed on both surfaces under all six.

`payload.py`'s three-kinds-of-nothing rule governs this. Three populations exist: the reference agents and a shim or CI target, which have a checkout; and a plain hosted endpoint, which can never have one. The five absences are *the bench never had a checkout*, *there was a checkout and this target is an endpoint*, *the object names no source the interpreter can point at*, *the file resolved outside the checkout*, and *the file could not be read*. They are five different facts about a run and a reader holding only the document has to be able to tell them apart, exactly as they must for the four readings of `narrations` ([ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md), [ADR-0070](./0070-a-signed-document-may-carry-a-remediation.md) §4).

**None of them may render as blank, and none of them may read as a clean result.** An unanchored finding says *the bench could not see this target's source* — a fact about where the bench ran, and deliberately not a sentence about the code. A block that simply had no location line would read as a failure nobody could place; a document that omitted the whole idea would leave a reader of a hosted run unable to tell that anchoring was even possible. So the section carries a standing paragraph above the blocks saying what a location means and why most runs have none, which is why the digest of a rendering with **no findings in it at all** moved with this ticket.

The reading travels as a **name** and not only as a sentence, for the reason every closed set in this codebase does: a consumer telling six readings apart by matching prose stops telling them apart the day the prose is reworded.

## 4. What may be published about a user's own code, and what may not

This is new material, and [ADR-0008](./0008-repo-disclosure-posture.md) and ADR-0070 govern it. A path is not neutral: an internal repository layout, a customer name in a directory, a product nobody has announced, and a runner's home directory are all things a path can carry into a signed artefact that travels.

**Published.** A path **relative to the checkout root**, in POSIX form, and a line number — as one string, `path:line`.

**Withheld, each for its own reason.**

- **The absolute path.** It names the runner's filesystem and the workspace's own name rather than the repository, and that is somebody's machine rather than the subject of this document. The relative path is the part that is *about* the code; the prefix is about where it happened to be unpacked.
- **A path that resolved outside the checkout.** Not trimmed, not published relative to something else — refused, and the refusal is its own reading. A file outside the workspace is not part of what the caller handed over.
- **Every byte of the file itself.** The bench opens the file to count its newlines and publishes none of it. A signed report is not a place a caller's source code travels, and a *snippet* around the line — which is what a reviewer UI would print here — is exactly the reproduction ADR-0070 §2 withholds one field over.
- **A line number as a number.** The findings section carries no figure at any depth (ADR-0005, D12), so the line travels inside the `path:line` string. A line number is a position rather than a measurement, and this is the form that stops it being mistaken for one or lifted into an arithmetic that has no business reading it (D13, [ADR-0006](./0006-overrides-never-change-a-measured-rate.md)).

## 5. The checkout is read, and this ticket does not write to it

**Decision.** Nothing in `bench/source_anchor.py` opens a file for writing, creates one, or executes one. Its whole effect on somebody else's filesystem is one `stat` and a bounded read of one file.

Patching is #109's sixth sub-issue and must not arrive here by accident. Stated as a decision rather than left as a property of today's code, because the module that resolves a path is precisely where a patch writer would be tempted to live.

The security properties are enforced rather than documented, and each is held by a test that was driven red against the guard removed:

- **Containment is decided on the resolved path.** Both the checkout root and the candidate are `resolve`d before comparison, so a symlink *inside* the workspace pointing at `/etc/passwd` is outside it. A named-path comparison would be defeated by a link, and a repository is a thing a caller can put links in.
- **A bounded read.** At most `MAX_ANCHORED_FILE_BYTES` — four mebibytes — is read to verify the line, and a larger file is reported unreadable. There is no bound on what a checkout contains, and no optional line of a report is worth streaming a gigabyte for on somebody else's runner.
- **The line is verified, not asserted.** A checkout that moved under a long-running process, or a module imported from a `.pyc` whose source was replaced, would otherwise publish a line that is not there. Verifying it is what makes the anchor evidence rather than a report of one.
- **A relative filename is refused rather than placed.** `python foo.py` produces a relative `co_filename`, and resolving one uses *this process's* working directory — which in the Action is the bench's own checkout and not the caller's. Resolving it could place a file inside a root it has no relation to, so an unlocatable name is one of the five absences.
- **A blank `--checkout` is no checkout.** The action interpolates an input, so an unset one arrives as an empty string, and `Path("")` is `.` — which would point the reader at whatever directory the process happened to be in.
- **Nothing raises.** Every way of failing to find a file is a reading. A `FileNotFoundError` escaping here would end a run that has already spent an operator's inference budget, over the one thing in the report that decides nothing.

**And the checkout is declared, not discovered.** `scripts/bench.py` takes `--checkout` and the composite Action passes `github.workspace` into it on the command line. It is a path rather than a secret, so it belongs where a reviewer of the workflow file can see which directory the bench was pointed at — the same reasoning that puts `callback` in the workflow and the endpoint in a secret (ADR-0066).

## 6. Nothing about the anchor reaches an instrument

**Decision.** No module that puts a question to a model may import `source_anchor`, and an import-level test holds it over `judge.py`, `narration.py`, `remediation.py` and `adjudication.py`.

[ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) blinds the adjudicator to which target it is reading, because a judge told whose agent it is scoring has a reason to score it differently. A repository path un-blinds it *more thoroughly than a target name would*: it carries an organisation, a product and a directory layout, and it would arrive attached to the transcript the model is being asked to rule on. So the anchor is resolved on the report side, after every verdict is decided, and the wall is an import rather than a review — the tempting version of the patching ticket is the one that hands a model a file to look at, and it would be one import.

## Consequences

- `ReportedFinding` gains one field, defaulted to `NOT_RUN_WHERE_THE_CODE_IS`. Every run this repository's API serves publishes that reading, because a hosted bench never has a checkout — the honest answer is the default rather than an omission.
- `GOLDEN_ONE_FAMILY` moves for the sixteenth time, and it moves on a document with no findings in it: the standing paragraph is what changed, which is the point of putting the explanation above the blocks.
- **Nothing here writes into a rate**, and there is no field one could arrive in: a reading is a name, a location is a string, and the whole record is prose about one verdict (D13, ADR-0006).
- **No route for the adaptive layer.** An `AdaptiveEpisode` has no `Finding`, so it has no anchor, and no signature widened to accept both ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)).
- **No severity and no composite.** A location is not a rank, the blocks are not ordered by it, and nothing counts how many findings have one (D3, D12).
- #115 patches a **throwaway copy** of the checkout; the read path here is the one that says whether there is a checkout to copy, and the invariant in §5 is what #115 must not quietly relax. #116 prints *proven* or *proposed* beside a fix, and the anchor is what a diff on that screen is attached to — a fix with no anchor is one this bench could not have tested, which is the same population §3 already names.
