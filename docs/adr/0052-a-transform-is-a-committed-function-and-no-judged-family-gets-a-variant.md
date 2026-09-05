---
status: accepted
extended_by: 0074-a-framing-is-written-per-family-and-an-unframed-pairing-is-refused.md
---

# A transform is a committed function, and no judged family gets a variant

> **Extended — not amended — by
> [ADR-0074](./0074-a-framing-is-written-per-family-and-an-unframed-pairing-is-refused.md),
> on the number of framings and on what §4's prose is carried by.** §3 said each
> framing is this repository's wording, written out once; there are now three
> roleplay framings, one per family, and what each is a claim about is ADR-0074 §4.
> Every other word of §3 stands, the cost it states is unchanged, and §4's paragraph
> about scope creep and halt defeat is now a refusal in code rather than only a
> paragraph. One sentence of §1 is narrowed there and named: *nothing refused* was
> totality over **text**, which still holds, and the five single-turn constructions
> are now partial over the (transform, family) **pairing**.

[ADR-0051](./0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md) made a transform a dimension of the library and left every member of it without an implementation: `Transform.BASE64` named a construction nothing performed. #73 writes the five published single-turn techniques as functions and decides which cases get a variant of them. Four of its decisions are not ADR-0051's and are recorded here; the arithmetic is untouched and stays #76's.

## 1. The module is `transforms.py`, and the functions are pure, total and applied once

#73 asks for `backend/bench/techniques.py`. The word was spent by ADR-0048 on `RetrievedFrom.technique` and ADR-0051 §2 renamed the dimension for that reason, so the module is `backend/bench/transforms.py` and one function performs each member. This is a consequence of a decision already taken rather than a new one, and it is written down only because the issue's own text says otherwise.

**Pure and total.** A string in, a string out; no target, no model, no clock, no randomness, and nothing refused — an empty payload and a payload with no ASCII in it both come back as strings. This is what lets a variant be a record: the payload has to be reproducible from its base case and its member name, and a transform that sampled anything would make `LibraryVersion` a hash over a payload the run did not send, which is the property the rejected send-time design could not have (ADR-0051 §1).

**Applied when the record is written, and never on the wire.** `scripts/variant.py` calls `applied` once and commits the result in the record's `payload`. `attacker._send` still sends `case.payload` and knows nothing about transforms; no module a run reaches imports `transforms.py` at all.

**So the committed text needs its own check, and the check is a test rather than a refusal in the loader.** A payload hand-edited after generation would sit in the library claiming a technique it no longer carries, and nothing at run time would notice. `transforms.mismatched_variants` is what notices — for every variant whose base is in the population, `payload == applied(transform, base.payload)` — and the suite asserts it over the library on disk. It is deliberately **not** a refusal in `load_library`, for two reasons. The loader's contract is that a record's bytes are the record's own, so `derived_from` stays provenance and nothing composes a payload outside the writer (ADR-0051 §4). And a library whose payloads were checked against a function *at load* would stop loading the day somebody improved a transform, where a failing test names the records to regenerate and leaves the library readable. The alternative was considered and it loses on the second point alone: a bench that cannot load its library cannot report that its library is wrong.

**One member has no function, and it is refused rather than defaulted.** `SCRIPTED_CRESCENDO` escalates over a fixed script of turns and `Case.payload` is one string, so `applied` raises and names #74, which owns the payload type. Falling through to the identity would commit a plain payload under a transform's name — the thing `Transform.stated`'s fallback-free match already refuses to allow for an eighth member.

## 2. No judged family gets a variant, and the reason is κ

Disclosure denial and wrongful commitment reach a verdict through `AdjudicationBrief`, whose `payload` is documented as *the case's own text*, and the reliability figure that licenses a judged rate at all rests on `GateRule.gold_transcripts_per_family = 15` hand-labelled transcripts per family — all of them single-turn plain text. A roleplay variant of a judged case would put a payload the gold set has no counterpart for into a κ-bearing denominator, which is the same fault ADR-0047 decision 4 already refuses one record upstream: no retrieved phrasing may reach an adjudicator's κ.

So the refusal is carried where a person would hit it, in `scripts/variant.py`, keyed on `verdict_class` and not on a list of family names — a third family becoming judged then costs nothing. **A judged variant is a separate ticket and it starts by saying what happens to κ**: either the gold set grows transcripts for the transformed payload, or the judged rate it feeds is not the rate the gate reads. Deterministic families only, here and in #74.

This is also why `variant_of` refuses a **retrieved** base. A retrieved payload ships committed because somebody else published it under a licence, and three things travel with it — the row, the licence and the notice (ADR-0047 decision 3, ADR-0008's third amendment). Those are a `[retrieval]` block on *that* record, and a variant of one would be a derivative carrying the payload without the notice. Whether a derivative may carry the block is a decision about attribution and it is not this ticket's.

## 3. The citation is the address the technique was published at, and nothing unverified is cited

ADR-0008's amendment withholds a payload whose wording is the working part, which is a description of all five of these. What lets them ship is the other half of the same ADR — `data-leakage-001` stays public *with its citation*, because republishing what is already published protects nobody — and the field that carries it is `Case.citation`, *where a published technique came from*.

**One address per transform, and it is the module that implements it** in the catalogue #71 names (`deepteam/attacks/single_turn/{base64,rot13,leetspeak,prompt_injection,roleplay}`, Apache-2.0), because the citation has to resolve to something a reader can check against this repository's own function. `Case.citation` is one string, so the paper each technique also appears in is named in the function's docstring instead: `prompt_injection_wrapper` is the goal-hijacking shape of Perez and Ribeiro, *Ignore Previous Prompt* (arXiv:2211.09527), and `roleplay` is persona modulation (Shah, Feuillade-Montixi, Pour, Tagade, Casper and Rando, arXiv:2311.03348). Both were checked against the published record.

**What is not cited is the part that could not be checked.** The three encodings are widely attributed to the obfuscation attacks of *Jailbroken: How Does LLM Safety Training Fail?*, and the paper's own attack list was not verifiable from the sources available while writing this, so no such claim is made anywhere in the code: the encodings cite the catalogue module and nothing else. A citation nobody checked is worse than a bare URL, because it is the one a reader believes.

**What this repository wrote, and what it copied.** Three of the five send words this repository composed rather than a string the catalogue publishes, and saying so is the same discipline as the paragraph above. The catalogue builds its **prompt-injection wrapper** and its **roleplay** frame with a model at run time; a transform here is pure by decision 1, so each framing is written out once, in the function, and it is ours — the published thing being copied is the *construction*, which is what `citation` therefore points at. The **leetspeak** table is narrower than the published one for a related reason: the conventional tables map `l` and `i` both to `1`, so a reader cannot undo them, and nine injective substitutions a person can reverse by hand beat eleven they cannot. What all three cost is stated rather than discovered: such a variant measures *this bench's instance of a published shape*, so a reading that a wrapper bought nothing is a reading about our wrapper, and a defence tuned to the catalogue's exact strings is not what it tested. What is **not** touched in any of the three is the base payload — #73's *no new base payload is written here* holds, because the request inside the frame is the base case's own text, verbatim, and the encodings are substitutions over it.

**And the classification is argued per record.** ADR-0008 requires it stated in the record's header, with the argument, so `scripts/variant.py` requires `--argument` — a file a person wrote — and refuses to write a record without one. A paragraph the script composed would be that argument asserted once, in a script, which is precisely what the amendment says it is not.

## 4. Which cases get a variant, and the three families that get none

The pairing is one variant per transform, over the three data-leakage cases, because that family is the one whose payloads *are* the working part:

| Transform | Base | What the pairing asks |
| --- | --- | --- |
| base64, rot13, leetspeak | `data-leakage-001` | the published extraction request announces itself — *repeat the text above*, *word for word* — and the first reading of this family rested on the hardened agent's input check firing ten times out of ten. Three surface forms of one request ask whether that check reads the surface or the intent. |
| prompt injection wrapper | `data-leakage-002` | a pretext with no override phrasing in it, wrapped in the published override shape. The base case exists because it has nothing for a marker list to match; the variant puts the marker back and measures what the wrapper costs. |
| roleplay | `data-leakage-003` | configuration as one section of a deliverable, asked of a character. The base case's mechanism is that the disclosure is a component of legitimate work; the variant asks whether a persona frame moves it further. |

This **narrows** #73's table, which says *the data-leakage payloads* in the plural and puts the wrapper on two families: one base per transform is enough to answer the question each pairing asks, five readings are five chances for the group to learn something before #74 depends on it, and a second base under the same transform is a variant nobody has been stopped from writing. The narrowing is recorded because it is a narrowing, not because it is a decision the issue took.

**Scope creep and halt defeat get none, and the reason is the interesting part.** `scope-creep-001`'s header says what does the work: *an errand that sounds like the agent's own job and is not, which is why the words carry no override and no published technique — there is nothing here to lift.* Base64 that errand and the agent cannot read the errand: the situational mechanism is destroyed by the wrapper rather than strengthened by it. Halt defeat is the same shape one step further — a stop signal the target cannot read is not a stop signal. And a wrapper or a persona wrapped round either would not be a variant of that case at all; it would replace the mechanism the case exists to test with a different one, which is a new case facing admission on its own terms. So the encodings go where the mechanism is *the words the target must read and act on*, and this is where that is written down (ADR-0051 §5: a transform that means nothing for a family is a variant nobody writes, and needs no absence type).

**Indirect prompt injection gets none either, and that is a finding rather than a choice.** #73's table asks for the encodings and the wrapper on *the note side* of indirect injection. The note is not in the library: `indirect-injection-001`'s payload is a colleague's morning message that carries no attack at all, and the override line lives in the reference agents' corpus (`backend/targets/reference/corpus.py`) as target-side equipment. So `applied(transform, case.payload)` would encode the colleague's message — the one part of that case nothing is defending against — and the variant the table describes cannot be expressed as a record whose payload is a transform of its base's. Making it expressible means transforming a planted note, which is a change to the reference agents rather than to the library, and it would move what every plain indirect-injection reading measured. **No ticket owns that today.** It is stated here so that #74 and #79 do not read the table as a promise the record shape can keep.

## 5. This ADR moves no arithmetic and admits nothing

`n` per family is unchanged, `GateRule.attempts_per_family()` is untouched, PLAN §3's diagram and CONTEXT.md's counts are still true, and the library digest and record count are where #72 left them — `89288dbf94f9`, eighteen — because **no variant record is committed here**.

That is not an omission and it is the honest cost of ADR-0007. A variant enters the library by clearing ADR-0003's single-model bar against the three reference agents, through `scripts/admit.py`, which reaches targets and therefore asks for the three attestation statements and the approval interrupt; `scripts/console.py` treats piped or absent stdin as a **no** rather than as a default, by design, so the measurement is a person's run at a terminal and cannot be performed by an agent on their behalf. Until it happens the five pairings above are proposals: `scripts/variant.py --write` puts a record with no `[admission]` block into `backend/cases/`, where `admitted_library` refuses it and the suite will not load a library holding it, so nothing half-measured can be committed by accident. What clears the bar is committed with its citation; what does not is deleted, and its reading recorded in [docs/validation.md](../validation.md) beside the κ figures — an encoding the hardened agent decodes and refuses exactly as it refuses the plain text has measured that agent's decoder, which is a result worth having either way.

The consequence to carry is [ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md)'s and it has not come due: the gate citation goes stale the moment the first variant is admitted, and a gate run of any outcome replaces it. Nothing here needs a decision, only a run.
