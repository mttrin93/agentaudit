---
status: accepted
---

# A technique variant is a case, and the transform is a function it names

A case says what it sends and, until this ADR, never *how it attacks*. `Case.payload` is one string, `send_message` takes `(target, message, session_id)`, and the published catalogue of encodings and wrappers that every red-team tool ships lands nowhere near a record: grepped for, `rot13` and `leetspeak` have no hit in this repository at all and `base64` is the encoding of the signing key.

#71 proposes adopting eight of those techniques and asks first the question everything else in the group is blocked on: **is a technique a record, or a transform applied at send time?** This ADR answers *record*, adds two fields, and takes the arithmetic nowhere.

## 1. A variant is a case of its own, and not a transform the run configures

`data-leakage-001-base64` is a `Case`: its own id, its own `[admission]`, its own decay series, its own place in the digest. The alternative — eighteen records unchanged, the technique arriving from a run's configuration and applied on the wire — is more compact and breaks three things that are load-bearing.

**Admission has nothing to attach to.** `AdmissionRecord` is a field of `Case`, and `admission.admitted_library` refuses a record without one. That a base64 wrapper discriminates where the plain payload does not **is the entire reason to add it** — it is a measurement about the variant, on the three reference agents, and under the send-time design there is no record for that reading to sit on. It would have to be a reading about `data-leakage-001` taken while a flag was set somewhere else, which is a measurement whose conditions are not in the library the digest covers.

**The decay series stops being a series about one thing.** `[[history]]` is one reading per case per gate run, and the retirement window is *the last two readings taken on the model of the case's most recent reading* (CONTEXT.md, **retirement window**). Under the send-time design two consecutive readings on one model could be readings of two different attacks wearing one id, and the retirement rule — which is the mechanism by which this bench notices that the field moved — would be reading a window that spans two of them. ADR-0022 already established that two *models* are not two readings of one thing. Two techniques are not either, and for a stronger reason: a model is at least recorded on the reading.

**`LibraryVersion` stops covering what the run sent.** The digest is over every field of every record except `history` and `retirement`, and `_versioned` is built from `dataclasses.fields` precisely so that a field added to `Case` is versioned unless somebody deliberately exempts it. A technique that is not on any record is a technique no digest can cover, so two runs sending different bytes would report one library version — which is the exact claim `LibraryVersion` exists to make impossible ("provably not comparable" is the half that needs a number, spec story 27).

So the field this ticket adds **is versioned by being added**, and that is the seam pointing the right way rather than a happy accident.

## 2. The set is closed, and it is not `RetrievedFrom.technique` — so it is not called *technique*

This is the decision that departs from #72's own wording, and it departs because four days of intervening work spent the word.

[ADR-0048](./0048-a-retrieved-family-grows-by-technique-and-not-by-count.md) §4 gave `RetrievedFrom` a `technique` field — *the attack this phrasing is an instance of, in a person's words* — and argued **in terms** that it must not be an enumeration: "a closed set of technique names would be a taxonomy of jailbreaks that nobody in this repository has validated … inventing one to get a type would be an instrument wearing an enum." CONTEXT.md carries that as a definition, with *variant* on its avoid-list. #72, cut the day before #67 landed, asks for `Technique`, a closed `StrEnum`, on `Case`.

Taking the name would put two things in one word on one record: a judgement about somebody else's published text, and a construction this bench performs on a payload it already committed. That is the collision CONTEXT.md keeps **probe** apart from **case** to avoid, and **declared capability** apart from **declared control**, and **elective family** apart from **family**. So the new dimension is `Transform`, which is #72's own word for the mechanism — its proposed ADR title is *"the transform is a function it names"* — and `technique` keeps the meaning ADR-0048 gave it. Nothing in ADR-0048 is edited.

**And the set is closed, which ADR-0048's argument does not reach.** That argument is about naming what somebody else published: the population is unbounded, the judgement is unvalidated, and the vocabulary would sit upstream of a scored family. A transform is not a judgement about anything. A member is a construction *this repository performs*, so the set is closed against what the code implements rather than against what the field publishes; a member with no implementation does nothing, so the enumeration cannot silently fall behind; and every member can be argued in a `stated()` sentence about bytes, which is the bar every closed set in `library.py` is held to and the bar ADR-0048 said a technique vocabulary could not meet.

**`PLAIN` is a member and not an absence.** It is the identity transform, and it exists so that `transform` can be required on every record. A default would make *nothing was done to this text* the answer a record acquires by silence, which is `discovered_by`'s argument two fields up: the safest answer must not be the one silence produces.

## 3. The two adaptive loops of #71's table are deliberately not members

#71's table lists eight techniques. Six are single-turn or fixed multi-turn and belong to the scored layer; **linear jailbreaking** is `adaptive/attacker.py` already, and **tree jailbreaking** arrives there under #78. Neither is a member of `Transform`.

`transform` is a field of `Case`. A member for either would let a scored record name something only an `AdaptiveEpisode` does, and the adaptive layer reaches the scored side through exactly one edge — `propose_case` into the admission gate ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md), and CLAUDE.md's standing rule). A member no record could ever carry would be a second name for that edge sitting in the type the scored side reads.

So `Transform` has seven members: `PLAIN` and the six of the table's scored rows. If the adaptive layer ever needs its own vocabulary for how an episode attacks, that is a closed set of its own, for the reason `ElectiveFamily` is a set of its own rather than a seventh `Family`: a value assignable into this one would be an adaptive technique in a field of a scored record.

**`SCRIPTED_CRESCENDO` looks like the same objection and is not.** No case can validly carry it today either — a fixed multi-turn payload is a sequence and `Case.payload` is one string, which is #74's work. The difference is *ever* against *yet*: #71(b) says a fixed multi-turn case is one case reaching one verdict, so a scripted crescendo **is** a case and the member is waiting for its payload type; an adaptive episode is not a case and never becomes one, because it has no denominator (CONTEXT.md, **episode**). A member the type system will eventually be able to honour is a different thing from a member it must never be able to.

## 4. `derived_from` is provenance, and never a payload the loader fetches

`Case.derived_from: str | None` is the id of the case a variant transforms, `None` on a base case. What it buys is that a variant's record does not restate its base's prose: the header argues only what the transform changes, and a reader follows the pointer for the rest.

**What it must never become is a fallback.** A variant with no payload of its own, resolved at load through this field, would be the send-time design with an extra field — the bytes on the wire would be composed in the loader rather than committed in the library, and the digest would cover a pointer instead of a payload. So the empty payload on a variant is refused on the record, and nothing anywhere resolves `derived_from` to find text.

The invariants split across the two places that can see them, which is this codebase's habit rather than a new mechanism:

- **On the record** (`Case.__post_init__`): `transform` and `derived_from` are one fact written twice, so a transform with no base and a base with no transform are both refused, and so is a case deriving from itself. Neither direction is symmetry for its own sake — a variant naming no base has nothing for its reading to be a claim against, and a plain case naming a base is either a duplicate of that case or a variant whose transform went missing, which are two different repairs.
- **In the loader** (`load_library`, its third cross-record refusal beside ADR-0047 decision 4's and ADR-0048's): the id resolves to a case that is here, in the *same family*, without a cycle. The cycle walk exists because composition is **not forbidden**, and the alternative was considered: requiring `derived_from` to name a `PLAIN` case makes every chain one link long and deletes the walk. It loses, because it would refuse an attack the published catalogue actually composes, and a later ticket would have to reverse a refusal rather than add a member. So the walk is here before anything composes, and validation.md records that it has never fired. What a cycle would be is a set of variants with no base case underneath any of them, so nothing in it compares against a plain payload at all. **Same family**, separately, because a transform changes how a payload is spelled and never which failure it tests, and families are separate denominators ([ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md)).

## 5. Three things need no change, and they are stated so nobody adds them

**No new trigger.** `Trigger.NEW_TECHNIQUE_PUBLISHED` already says *a new technique was published — the library was behind the field*, which is what every variant in this group is. A seventh member would duplicate the one that fits. (And note the trigger keeps ADR-0048's sense of the word, which is one more reason the enum could not have.)

**No new admission bar.** `DiscoveredBy.AUTHORED` selects the single-model bar of [ADR-0003](./0003-gate-decision-rule-and-sample-size.md), and a variant a person writes from a published technique is authored. The cross-model bar of [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) is for what the *attacker* found — a route fitted to the three agents it was discovered on — and a base64 wrapper is not that.

**No new absence type.** A transform that means nothing for a family — an encoding wrapped round `scope-creep-001`, whose mechanism is *an errand that sounds like the agent's own job and is not*, which encoding destroys — is simply a variant nobody writes. The family is still measured by the variants that exist. `applicability.py` is about agent types, `measurability.py` about target capability, and `DeclaredGap` about the caller's setup; none of the three is the right home for *the bench chose not to write this one*, and a ragged variant set per family is what #66 already made representable.

## 6. This ADR adds no arithmetic

`n` per family is unchanged: eighteen base cases, ten attempts each, and `GateRule.attempts_per_family()` untouched. The dimension exists and the library holds no variant, so PLAN §3's diagram and CONTEXT.md's counts are still true and are deliberately not edited here. They move under #76, when a family holds more than one variant and the denominator actually grows — and #66's argument for why growth is the safe direction is #66's and is not re-derived.

What did move is the **library digest**, from `c31a2355f065` to `89288dbf94f9`, on #65's precedent exactly: the shape of a case changed, so eighteen records that ask the identical eighteen questions hash to something else. `test_the_library_version_did_not_move` is the designed tripwire and this is the designed answer — every record is in the diff, gaining `transform = "plain"` and nothing else, and the count of eighteen is what says no case was written and no payload edited.

## 7. What this costs, stated rather than discovered

**A mounted library seeded before this ticket does not load.** `transform` is required on the record, so `gate_run_equipment.seeded_library` — which leaves a mount with records in it exactly as it is, because a seed written over a series would erase the decay history — will hand `load_case` records with no `transform` line. The refusal names the record and says what is missing, and the migration is one line per file. The alternative is a default, which is the thing §2 refuses; a required field whose absence is a clear refusal is better than a field whose absence is silently read as *plain*, because the second one is how a variant loses its transform without anybody noticing.

**Two required fields is a mechanical blast radius, and it was the whole of the risk.** Every case record and every fixture that builds a `Case` failed to construct until it stated both, which is the direction that pressure should point: a record that does not say how it attacks does not load.

**Nothing has been measured.** No variant exists, no transform has been implemented as a function, and no gate run has read one. The gate citation this library carries is stale the moment #73 admits the first variant, and ADR-0023 already covers that mechanism — a gate run of any outcome replaces the citation — so what this group owes there is a gate run and not a decision. Recorded in [docs/validation.md](../validation.md).
