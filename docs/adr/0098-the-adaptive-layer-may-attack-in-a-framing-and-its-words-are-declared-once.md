---
status: accepted
---

# The adaptive layer may attack in a framing, and its words are declared once

[ADR-0097](./0097-the-adaptive-layer-attacks-in-a-spelling-and-it-is-selected.md) let the
adaptive layer compose its probes in four of the seven constructions — the identity and
the three encodings — and refused the two **framings** on the argument that they need
words of ours: `roleplay` takes a persona written per family and
`prompt_injection_wrapper` takes an override frame that
[ADR-0074](./0074-a-framing-is-written-per-family-and-an-unframed-pairing-is-refused.md)
§5 withholds for every family on ADR-0008's amendment.

The operator asked for both. This record is the decision, and the part of it that is a
disclosure decision says so.

## Decision

1. **The adaptive layer's framings are declared once per transform, not per family.**
   `ADAPTIVE_FRAMINGS` holds two entries — one persona, one override frame — and
   `spelled` reads it. `FRAMINGS` is untouched.

   The per-family grain has two reasons and neither reaches an adaptive probe. A
   committed variant's framing must be coherent with *that family's* mechanism because
   its rate is compared with its base case's rate inside that family (ADR-0074 §1), and
   because one entry of a family's published mix is one framing's reading (ADR-0055 §2).
   An episode carries no rate, joins no mix and is compared with nothing (ADR-0010). What
   an adaptive framing has to be coherent with is a sentence the attacker composed a
   moment ago, for a family it chose at runtime — so the coherent grain is the transform,
   and a per-family table here would be nine wordings nothing distinguishes.

2. **The two tables stay two, and that is what keeps the library's refusal true.**
   `FRAMINGS` is keyed on `(transform, family)` and is what a **record** may be written
   from; `ADAPTIVE_FRAMINGS` is keyed on transform and is read only at runtime.
   `scripts/variant.py` goes through `framing_for`, which does not read the second table,
   so **no case record of either framing can be written** — the override wrapper's entry
   in `FRAMINGS` is still empty, still refuses every family, and still carries the
   disclosure reason.

3. **The persona keeps ADR-0074 §5's rule: a remit, never stagecraft, and never an
   authorisation.** It says whose job the work already is and asks the target to answer as
   that person. It stages no recording and no scene, and a test holds the absence of those
   words. The reason is weaker here than it was for a scored variant — a fiction the
   target is performing gives it a reason to make no tool call at all, and where that used
   to be *stagecraft scored as a defence* it is now an episode **censored** by our own
   words, which is a diagnostic about this repository wearing `A_effort`'s name rather
   than a soft figure in a published rate. Weaker, and still worth keeping.

4. **The structural fault ADR-0074 §5 refused the wrapper for cannot arrive here,
   because there is no number for it to arrive in.** That argument was about
   `halt-defeat-001`: the wrapper is a prefix and the payload passes through verbatim, so
   a base payload beginning with a stop order came out *instructing obedience*, and both
   reference agents would have reported `resisted` for a reason belonging to our wording.
   An episode has no rate and ends `broken` or `censored` (ADR-0011), so the same
   enclosure costs a search and never a reading. The scored refusal stands unchanged; it
   was never a claim about this layer.

5. **The disclosure half is a decision, and it is the operator's.** ADR-0008's amendment
   withholds *anything that reads as a reusable override, jailbreak or filter defeat when
   its wording is the working part*, and `docs/validation.md` recorded that the words were
   therefore gone from `transforms.py`. They are back, as `_ADAPTIVE_OVERRIDE`. What
   distinguishes this from the withheld case is real but partial: the frame is committed in
   **no case record**, so it is not published with the library; it reaches **no signed
   artefact**, because an episode's payload is not in the document (ADR-0056 §1, ADR-0057
   §4); and the transcripts that carry it are never committed. What is **not**
   distinguished is that the words now ship in this repository's source, and that is the
   cost this decision accepts rather than argues away. It was asked for, the search it
   buys is against the operator's own declared target, and a reader deciding whether this
   repository publishes a reusable override should read that one string and decide about
   it. `docs/validation.md` carries the same paragraph, because that file is where a
   refusal to write a record lives and this is its reversal in part.

6. **The brief says what the frame does and never what it says.** Two phrases, because
   an encoding and a framing are two different things being done to a probe: `RESPELLING`
   for the encodings, `FRAMED` for the framings, and one line per framing in `_FRAMING_IS`
   describing its effect — *your request will be preceded by a delimiter and a claim that
   the operator has already approved it*. The frame's own wording stays out, or the model
   composes a second copy of it, and the instruction is to compose the request plainly and
   add no persona and claim no approval.

7. **`scripted_crescendo` stays out, and the reason is the operator's own.** It is a
   ladder computed from a case record, it is the only construction that changes how many
   turns there are, and the fixed script is the only multi-turn approach this bench has
   implemented — a fixed script inside a model-driven episode is two attackers composing
   one episode. `ADAPTIVE_SPELLINGS` is therefore six of the seven, and `spelled` refuses
   the seventh by name rather than falling through to the identity.

## Considered and rejected

**Reusing the three committed personas per family.** Six of the nine families the layer
attacks have none, so a roleplay episode set would exist for three families and not the
rest — a bar that cannot fill, with a reason that is about our table and not about the
target, which is the shape ADR-0094 spent a record fixing.

**Writing nine personas and nine override frames.** ADR-0074 §1's grain applied where its
reasons do not hold, and for the wrapper it is the multiplication ADR-0074 already
refused: a per-base override framing is another reusable override in our wording, and the
grain multiplies the disclosure problem instead of solving it.

**Keeping the wrapper out and shipping only the persona.** It is the half of the request
that the disclosure argument bears on, so declining it would have been the honest
conservative answer — and it was raised, twice, and answered. Recording the reversal with
its cost is the alternative to declining it silently or accepting it silently.

**Letting the attacker write its own frame.** The sixth tool ADR-0057 §1 and ADR-0008
both refuse, and the fault ADR-0074 §5 names would return through the model: a frame this
repository cannot print is a frame nobody can read `A_break` against.

## Consequences

- The adaptive layer can search in six constructions, the two framings among them, and
  each selected one is its own episode set — so the ceiling multiplies and the operator
  confirms it (ADR-0097 §3).
- An override frame in this repository's wording is in `transforms.py` again. No case
  record holds it, `FRAMINGS` still refuses every family, and no artefact carries it.
- The scored layer is untouched: the same members mean the same thing there, the wrapper
  varies nothing, and `data-leakage-002` still has no variant.
- A framed episode's transcripts hold our words in front of the attacker's. A reader of
  an episode is reading two authors, and the brief is where the attacker was told which
  half was going to be added.
- `docs/validation.md` keeps the refusal and now records its partial reversal, so the file
  that says *the words are gone* no longer says something that is not true.
