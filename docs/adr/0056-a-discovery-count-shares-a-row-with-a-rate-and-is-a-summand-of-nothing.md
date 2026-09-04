---
status: accepted
---

# A discovery count shares a row with a rate, and is a summand of nothing

Until this ADR the two layers of a run met nowhere on the page. The scored layer's rates are section 4 of the target report and the adaptive layer's episodes are section 5b, `AdaptiveSection` refuses in as many words to count anything, and a reader who wanted to know whether the search broke a family the suite reported as holding had to hold two sections in their head at once.

#71 (b) asks for the second half of that reading: **a family's row shows what the adaptive layer found beside what the scored layer measured.** That is the most useful pairing this document can make and the most dangerous one it can print, because it puts an adaptive number and a scored rate a few pixels apart at the exact place a reader is most likely to add them. [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) permits it — its rule is that no adaptive result may write into a **scored rate**, not that the two may never appear together — and what this ADR decides is what forbids the addition. The answer is *the types and the layout*, never a caption.

## 1. The two may share a row, and the row is a view rather than a figure

The count a reader wants is **already derivable from what is already signed**. Every `ReportedEpisode` in the artefact carries its family and its outcome, so counting the episodes of one family is arithmetic a recipient can do with the bytes in their hand. The document does not have to do it, and the artefact therefore **gains no figure at all** — which is the interesting claim of this change and the one that is asserted structurally: drop the whole adaptive section from a result and every other byte of the payload is unchanged (`backend/tests/test_payload.py`).

So `AdaptiveSection`'s standing refusal survives intact. It still carries episodes and nothing derived from them arithmetically, `families_broken` is still a set of names, and the counting happens in the two places the row is **drawn** — `rendering/_measured.py` and `frontend/src/report/report.ts` — from data those surfaces are handed rather than from a field somebody added upstream.

**Two places and not three.** #71 (b) named the console's family blocks as a third, and they are not one: `GateCards.tsx` and `GateDecision.tsx` draw the *gate's* per-family blocks, which are about the bench and carry `D`, monotonicity and the two family counts against three reference agents (ADR-0018). No target's episodes reach them, so there is no row there to pair. The report screen is the only place a **target's** family row is drawn, and the third site named in the ticket is the same one. What moves is the rendered document's digest, which ADR-0017 already scopes: only the serialisation has to be byte-stable, so *the rendering may change and arrive with a new digest*.

## 2. `FamilyEntry` gains no field, and that is the whole of the type-level prohibition

A field on the scored entry is the one shape that makes the addition easy to write. `entry.rate.successes + entry.adaptive_discoveries` type-checks, means nothing, and would move the bench's headline figure with no test failing — which is the failure mode ADR-0010 describes for recording adaptive turns as `Attempt`s, one level up. CLAUDE.md's standing rule is exactly this case: *if you find yourself widening a signature to accept both, stop.*

So the pairing lives in a **view type** that holds the two readings in two fields:

- `rendering/_measured.Discoveries` carries **one string** and nothing arithmetical. The count reaches the renderer already worded — *2 episodes broke this family, and 1 stopped out of turns* — and the ints it is built from die inside `Discoveries.of`. There is no numeric attribute anywhere for anybody to lift off, so under `mypy --strict` the addition is an error at the call site rather than a line that type-checks.
- `report.ts`'s `FamilyRow` pairs a family's `answer` with its `discoveries`, and `DiscoveriesReading` is three strings for the same reason. `tsc` is what enforces it.

`FamilyEntry` and `VariantBreakdown` are untouched, and both refusals now have a test that fails when somebody adds the field: the breakdown's keys are `Transform` members and an `AdaptiveEpisode` has no transform ([ADR-0055](./0055-a-family-pools-its-variants-and-publishes-the-counts.md) §2), and `test_payload.py` reads `FamilyEntry`'s own annotations.

**One field and not two.** A second field holding the same count as a number, for a caller that wanted to lay the row out itself, would undo the paragraph above at the first call site that reached for it. The censored count is inside the sentence for the same reason.

## 3. The layout carries the rest, because a caption cannot

A count of episodes beside a rate over attempts is two different denominators in one row, and CONTEXT.md's **episode** entry says why the second one has none: *an episode has no denominator, because its length varies with what the attacker decides to do.* Four consequences, all of them checked:

- **No fraction and no percentage.** The row may not print `2/6`, `33%`, or any denominator at all. A denominator would be a claim that the six were a sample, and turns within an episode are dependent by construction.
- **No shared heading.** The rate line names *attempts* and the discovery line names *episodes*, and the discovery line does not contain the word *attempt*. Two headings that could be read as one unit are the addition, drawn.
- **The censored count travels beside the broken one, and each is counted for itself.** An attacker that ran out of turns is not a target that held (CONTEXT.md, **censored**), and a row printing only the breaks would say the search finished. Neither count is derived by subtracting the other: an episode whose outcome is a third thing is counted as neither, on the terms `report.ts`'s `readOutcome` already states — *an outcome this map has no entry for is printed as the payload wrote it*.
- **No total row, and no tint.** The screen draws the count in the card's quiet aside type, off the figure line, with no colour of its own — the idiom `SettingsScreen.tsx` states, *colour carries identity and order and never a judgement*. This is the one number on that page a reader could mistake for a worse rate, so what marks it is the word and never a hue.

The word is **discoveries**, matching CONTEXT.md's **adaptive finding** — *reported in its own section, and never a Finding*. Not *breaks*, not *successes*, and never *adaptive rate*.

## 4. A family the search never worked in has no count, and not a count of zero

The same refusal a family with no attempts makes by having no rate at all, and the same one `discrimination` makes by reading *not read* rather than `0.00`: a bench whose attacker never worked in a family must stay distinguishable from one whose attacker worked there and found nothing. `Discoveries.of` **refuses** no episodes rather than wording them, so that absence has one representation — the family missing from the mapping the row looks itself up in — and not two; `VariantCounts` refuses zero attempts for the same reason (ADR-0055 §2). `familyRows` sets the cell to `null` on the same lookup.

The two surfaces then differ in one way, deliberately. **The screen draws nothing** — an empty cell beside a rate, which is what #77 asked for. **The document states the absence in words** and prints no number: *no episode of the search is recorded against this family — not a count of zero, because this layer records what one attacker did, and a family it never worked in is a fact about the attacker rather than about this target.* The signed document is the surface that travels to somebody with no other way to learn what ran, so it may not be the surface that says less than the payload it is a view of; the screen sits beside the payload, the run and the probes.

## 5. The join is the family, and never the figure

A family whose rate is withheld below the κ floor and a family whose precondition was unmet are both families an attacker may have broken, and for such a family the count is the **only** reading the row has. So the pairing is keyed on the family alone: the document appends the same sentence to each withheld and each unmeasurable family, and the screen draws the cell on all three card shapes. Keying it on *families that carry a figure* would drop the count exactly where it is the only thing there is to say.

## 6. When the two disagree, nothing reconciles them — that is the row's whole value

A family measured `holds` with two adaptive discoveries against it is not a contradiction to be resolved. It is the reading this bench exists to be able to produce: PLAN §3's second trigger is *a target passed everything — either the agent is excellent or the attacks are weak*, and an adaptive success is the only available evidence that distinguishes the two, because it distinguishes them by demonstration.

**No code may reconcile it.** The band is not downgraded, the rate is not annotated, no line marks the row as inconsistent, and nothing is recomputed. The document asserts this as *nothing else on the page moves*: rendered with the search and without it, every other line of the family's block is byte-identical, and on the screen the paired `answer` is the answer computed with no search at all. What the two readings mean together is the reader's judgement, and the honest form of the row is to print both and interpret neither.

The route from an adaptive finding to a scored figure is unchanged and is still the only one: `propose_case` into the admission gate, decided by a declared threshold. A row is not an edge.

## Considered and rejected

**A field on `FamilyEntry`, with a caption saying not to add it.** §2. The caption is not in the type system, and the sum would be one line at one call site with no test failing.

**A discovery *rate* — episodes broken over episodes run.** It has a denominator that looks like the rate's and is not one: an episode is not a sample of attempts, its length varies with what the attacker decides to do, and two runs of the same attacker against the same target produce different denominators. Printing it beside a rate over a fixed suite would invite exactly the comparison ADR-0010 exists to prevent. `A_break` and `A_effort` are the adaptive layer's own statistics, they belong to their own block, and they decide nothing (ADR-0011).

**A figure in the artefact, so the two surfaces read it rather than count it.** It would be one more signed number that adds nothing — the episodes are already there with their families and their outcomes — and it would put an adaptive count inside the `measured` block, where the next reader to write a total would find it already waiting. Counting in the view costs two implementations of one sum and buys the structural assertion in §1.

**A shared table with a column each**, which is the shape #71 (b) asked for in as many words — *the Markdown table gains a column whose header names episodes*. There is no per-family table in this document and there has not been since the family blocks were written: a table wants a total row, and this grid has nowhere to put one. Cards, and one row per family, for the same reason ADR-0005 refuses a composite: what is not representable is not printed by accident.
