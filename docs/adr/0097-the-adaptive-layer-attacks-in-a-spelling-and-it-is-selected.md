---
status: accepted
---

# The adaptive layer attacks in a spelling, and it is selected

The scored layer attacks in seven constructions and the adaptive layer attacked in one:
the attacker's own words, as it composed them. So a target that refuses a plain request
and answers the same request in base64 was a difference this bench could **measure** in
its scored layer, per case and per attempt, and could not **search for** in its adaptive
one. deepteam's multi-turn attacks take a `turn_level_attacks` list for exactly this
reason (its docs describe a random sample enhancing about half the turns of an episode),
and [ADR-0096](./0096-the-adaptive-schedule-is-selected-and-both-schedules-are-two-episodes.md)
had just built the shape a second adaptive selection lands in.

## Decision

1. **A spelling is a `Transform`, and `ADAPTIVE_SPELLINGS` is the four that can be
   one.** `plain`, `base64`, `rot13` and `leetspeak`. Their functions add nothing of
   ours to a probe — they respell the attacker's own words — and `transforms.spelled`
   is their entry point, beside `applied` and never through it: that one takes a
   committed payload and asks `framing_for` first, because a *record* of a variant is a
   pairing this repository has written down.

   The other three are refused by name, for two different stated reasons.
   `prompt_injection_wrapper` and `roleplay` need a **framing** — one prefix written per
   family, coherent with the mechanism that family tests — and `FRAMINGS` is the whole
   of which pairings exist (ADR-0074 §1): the wrapper's mapping is deliberately empty,
   because a record of it would ship a reusable override frame in this repository's
   wording and ADR-0008's amendment withholds that (ADR-0074 §5), and the persona is
   written for three families and no others. A probe composed at runtime has no record,
   so framing it here would mean inventing words outside that table. And
   `scripted_crescendo` is not a spelling at all: it is a ladder computed from a case
   record, it changes how many turns there are, and a fixed script inside a model-driven
   episode is two attackers composing one episode.

2. **The harness respells; the attacker composes plainly and is told.** `spelled` is
   applied at `_Episode._probe`, the one place a probe goes on the wire, so the
   transcript records what the endpoint actually read — which is the evidence a proposed
   route has to reproduce (ADR-0010) — while the episode log shows the attacker its own
   words. The brief gains one line naming the spelling and telling the model not to
   encode anything itself: a model composing for a target that reads base64 without
   knowing would compose blind, and one that encoded its own probe would have it encoded
   twice. `plain` is the identity and the line is conditional, so a plain episode's
   brief is byte-identical to the one this layer has always sent (`_continuation`'s
   rule, ADR-0057).

3. **One spelling per episode, and each selected spelling is its own episode set.**
   ADR-0096 decision 3's arithmetic, over the second selection: `k` episodes per family
   per schedule **per spelling**, so `episode_count` multiplies and `turn_ceiling`
   multiplies with it, and the estimate's basis names both — `× 2 schedules (…) × 2
   spellings (plain, base64)`. The alternative, and the one deepteam takes, is a random
   sample enhancing some turns of one episode: rejected because it makes an episode a
   mixture nobody can reproduce from the record, and because randomness inside a route
   is the thing `ProposedRoute` exists to remove. An episode is composed in one spelling
   throughout, and what a reader compares is two episode sets.

4. **`AttackSelection.adaptive_constructions`, refused at the door.** The fourth switch
   and the adaptive layer's second, defaulting to `plain` alone on the schedules'
   reason: it is the spelling every reading this bench has published was taken under,
   and a spelling switched on by default would be an episode set nobody asked for. An
   empty set is refused, a member outside `ADAPTIVE_SPELLINGS` is refused with the
   sentence saying which of the two reasons applies, and the route turns both into a
   `422`. It reaches the budget through `AdaptiveBudget.under`, which is still the one
   join and now carries both halves.

5. **The console draws it in the adaptive box, under the schedules.** A second footer
   list behind the word *Spellings*, grouped off the `layer` field the wire puts on every
   row, and a separate list from `transforms` rather than more rows on it: **the same
   member means two different things in the two lists** — a case sent in base64 and
   scored on its own attempts, and a composed probe respelled on its way out — so one
   list would put a switch for the second where a console reads the first. The sentence
   under the switches says each spelling is its own episode set, and why the list is
   four members and not seven.

6. **The document says which spellings were composed in, in its own key.** ADR-0096
   §8's rule, applied again: `selection.adaptive_constructions` and
   `adaptive_constructions_stated` sit beside the schedules' pair, `stated()` is
   untouched, and the artefact version does not move — a key beside the others, carrying
   no figure, whose sentence a version-2 verifier skips while re-deriving every figure it
   knows. The verifier checks the new sentence when the key is there and rebuilds the
   selection with `DECLARED_ADAPTIVE_CONSTRUCTIONS` when it is not, because an artefact
   issued before this change was a run composed plainly. The adaptive block names the
   spellings beside the schedules, for the reason it names the schedules: `A_effort`'s
   median over episodes composed in two spellings is a median over two searches.

## Considered and rejected

**deepteam's shape — a random spelling on about half the turns.** §3. It buys turn-level
variety at the cost of a route nobody can reproduce and an `A_effort` median over
episodes that were each a mixture.

**Recording the spelling on `AdaptiveEpisode`.** ADR-0096's rejected option, and the same
answer: the run-level selection is where *what was asked for* belongs, and the trace is
already in the record — the transcripts carry the respelled probe, which is what went on
the wire. Worth reopening if a reader has to sort a run's episodes by spelling without
reading them.

**Extending `FRAMINGS` so the framing constructions could be selected too.** It is
writing new attack content per family, which is ADR-0074's subject and not this one's —
and for the override wrapper it is precisely the frame ADR-0008's amendment withholds.

**Letting the attacker choose its own spelling through a tool.** The sixth tool ADR-0057
§1 and ADR-0008 both refuse. A model-invoked choice of construction is a model-invoked
choice about what the operator's endpoint is sent, and the harness's choice can be
printed where the model's cannot.

## Consequences

- The adaptive layer can search in base64, rot13 and leetspeak for the first time, and a
  run that selects two spellings puts twice the adaptive turns on the operator's
  endpoint — priced before the interrupt, in a basis that names them.
- Nothing about the scored layer moves. The same members mean the same thing there, and
  the seven constructions' rates, variant breakdowns and denominators are untouched.
- An episode's transcripts now hold a respelled probe where the log holds the plain one.
  A reader comparing the two is reading the harness's own construction, which is the
  thing the brief told the attacker about.
- `docs/validation.md`'s standing line is unchanged and gains nothing: no gate run has
  been decided under any spelling but the attacker's own words, and the discrimination
  readings this bench publishes are `plain`'s.
