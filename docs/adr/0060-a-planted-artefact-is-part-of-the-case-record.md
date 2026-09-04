# ADR-0060: A planted artefact is part of the case record, and is versioned by being on it

**Status:** accepted (#83, group J / #81)
**Date:** 2026-09-05

## Context

Two of this bench's families do not attack with the message they send. Indirect
prompt injection's payload is a colleague's ordinary morning request; memory
poisoning's planting turn asks for a document to be opened. Everything adversarial
is in what the target *fetched*. A case in these families **is** a piece of content.

The case record did not carry that content. `indirect-injection-001.toml` held the
payload and `planted_canary = "NOTE-PROCESSED-44120"`; the note that produces the
canary — the override line, the invoice reference, the errand after it — lived in
`backend/targets/reference/corpus.py`, in the reference agents' own source. Three
consequences followed, and the record's own header comment stated the first one:

> The canary below is the reference agents' planted note reaching the bench's side of
> the wire. The two are written out separately, as the echo probe is, because a target
> does not read the bench's source. **If they drift apart the trivial agent stops
> executing anything and the suite says so.**

1. **One fact was written twice**, in two files, and a test watched them for drift.
2. **Nothing but a reference agent could be planted with an injection case.** An
   operator told at registration to plant "a third-party note" was being asked to
   write the attack themselves, and a note of their own invention would have the
   family run against an attack whose canary can never appear — a clean zero that
   reads like a defence. `GET /bench/notes` closed the hole by serving the reference
   agents' source over an API, which is the same two copies with a route in front.
3. **A note-side variant was not expressible.** #73 recorded that the override line
   is target-side equipment, so a variant of an indirect case could not be a
   transform of its base's payload — the payload is not where the attack is.

## Decision

**1. A `[planted_artefact]` block is part of the case record.** `Case` gains
`planted_artefact: PlantedArtefact | None`, holding `where` (`PlantedIn`), the `key`
the content is filed under, the `body`, the two halves of the canary, and `fires_on`
for a dormant instruction's subject.

**2. It is present on exactly the cases whose instruction arrives in content the
target fetched** — `CARRIED_BY_FETCHED_CONTENT`, which is
`canary_instruction_executed` and `retained_instruction_executed` — and absent on
every other case, refused by `Case.__post_init__` in either wrong combination. A case
whose canary is the registration nonce carries none: that value is issued per run and
planted *inside* the target's boundary (ADR-0007). A direct override carries none: its
instruction is in the payload (ADR-0042).

The set rather than one kind, because the same argument makes both records
incomplete, and because a hardcoded pair is how the third planting arrives as an edit
to this ADR rather than as a record (#48, #50, and #81's own objection to a hardcoded
hook set).

**3. The canary is written once, as two halves, and the join is derived.**
`PlantedArtefact.executed_line` is a property; `load_case` derives
`success_condition.planted_canary` from it, and **refuses a record that also writes
`planted_canary`**. That refusal is the whole of what this ADR buys: the drift a test
used to watch for is not caught, it is unrepresentable.

The two halves stay separate on the record and the body spells them out in two
places. A field holding the joined string, interpolated into the body, would make a
target that quoted the whole note back while refusing it reproduce the join — and
every refusal that described the attack would score as a success. `PlantedArtefact`
refuses a body containing the join, and refuses one that does not spell out each
half separately.

**4. `corpus.py` reads the library instead of restating it.** The reference agents'
shared folder is assembled from the committed library's planted artefacts plus
`DELIVERY_NOTE` — the one note that instructs nobody, which is not a case, has no
verdict, no admission and no decay series, and is the control that makes the canary
mean obedience rather than retrieval.

**5. The artefact is versioned by being on the record.** `_versioned` is built from
`dataclasses.fields`, so a field added to `Case` is versioned unless somebody
deliberately adds it to `RUN_RECORD_FIELDS`. Nothing was written to make this true and
nothing was undone (#72 makes the same argument). Two runs that planted different
content cannot report one library version.

**6. The record's own fetching turn has to name the content it plants.**
`corpus.fetched` matches a message against the key, so a record filed under a word its
own turn never says is a case whose attempt retrieves something else and answers a
clean zero. Likewise a dormant instruction's subject has to be raised by the scored
turn — the constant `MARCH_RETAINER` used to sit beside the note for exactly this
reason, and now the fact is one record's.

## The reference agents read the bench's source, and that is bounded

`contract.py` says there is deliberately no in-process branch for the reference
agents, *"they are reached over this same path, so the gate exercises the code a
user's run exercises"*, and the case header's argument for two copies was *"a target
does not read the bench's source"*.

**This ADR makes the reference agents read it, and nothing else changes.** The three
agents are fixtures the bench ships in order to measure itself; their constructed
rates are the band cut-points (ADR-0014). Nothing about a user's target moves: it is
still reached only by `send_message` over HTTP, still reads none of this, and the
shim of ADR-0059 still serves rather than branches. `corpus.CASES` is the repository's
committed `backend/cases/`, deliberately **not** a deployed library a mount could
replace — a folder that changed with what somebody mounted would move the cut-points
under reports already signed against them.

What the reference agents obey is still code (`agent.py`), still keyed off a line
written out beside the body, and still not a model's temperament. The only change is
where that line and that body are written down.

## No reading moved

Stated explicitly because #73 recorded that changing this equipment would move every
plain indirect-injection reading.

**The seven note bodies are byte-identical to the ones `corpus.py` held**, as are
their executed lines and their `Standing` records — asserted against the pre-change
module during the move. The shared folder holds the same seven notes in the same
shape, `fetched` answers the same note for the same message, and the three reference
agents therefore produce the same replies. No `D`, no rate, no interval, no band and
no `[[history]]` block in the library moves, and no admission reading is invalidated.

**The library digest moved**, from `31cacb9d69ec` to `81ff91682cfc`, on #65's
precedent: the shape of a `Case` changed, and three records are in the diff as well —
each gaining its `[planted_artefact]` block and giving up the `planted_canary` line
the block's two halves now derive. The count is still eighteen, which is what says no
case was written. `test_corpus_isolation.test_the_library_version_did_not_move` is the
designed tripwire and this is the designed answer; it is updated with the reason and
never loosened.

The three elective memory-poisoning records gained the same block. They are outside
the eighteen and outside that digest, and their readings are unmoved for the same
reason.

## Disclosure

ADR-0008 as amended, and the case header already said it: both halves of this case are
committed and public, and the note is *"the published kind an input check is written
for rather than a phrasing this project discovered"*. Moving it from one committed file
to another committed file publishes nothing new, and `GET /bench/notes` already served
the bodies. What would be new is payload text in a **signed artefact** or in a **CI
log**, and that is refused where it arises (#89).

## Alternatives

- **Keep two copies and keep the drift test.** Rejected: it is the status quo, it
  leaves the operator unable to plant anything, and a test that two files agree is a
  test that can only fail after somebody has already made the mistake.
- **Store the joined canary on the record and interpolate it into the body.** Rejected
  in decision 3: it destroys the composition defence, which is the soundness argument
  every planting in these families rests on.
- **Serve the artefact from a route and leave the record naming only the canary.**
  Rejected: that is `GET /bench/notes` today, and it is two copies with an API in
  front. The route stays, and now reads the record.
- **Require the block on `canary_instruction_executed` alone.** Rejected in decision
  2: memory poisoning's notes are the same kind of content planted in the same place,
  and a rule written for one kind is a rule the second kind arrives as an exception to.

## Consequences

- `Case` has a new field and eighteen-plus-three records are in the digest's diff.
- `backend/bench/entry.py`'s TOML writer emits the block, and stops writing
  `planted_canary` where there is one — a writer that emitted both would produce
  records `load_case` refuses, which the round trip already guarantees it notices.
- `scripts/console.py` and `backend/api/app.py:notes_to_plant` read the **record**,
  the retrieval word the operator is told to file under included — a screen that named
  one note while printing another would send the operator to file content under words
  the case's payload never says.
- **No two records may file content under one key.** `fetched` answers the first
  match, so a second record under one key is content no message can retrieve. Refused
  in `corpus._planted`, where the library can be seen.
  Neither imports `corpus.py` any more, and `notes_to_plant` matches nothing: the
  body and the canary come off one record. Its `unpaired` list survives with a
  narrower meaning — a live case in the family whose record plants nothing.
- The three named note constants and the twelve prefix/reference constants are gone
  from `corpus.py`; callers that need the halves ask `corpus.planted(key)`.
- **What #84 gets.** `PlantedIn.RETRIEVED_CONTENT` is the seam its `Plant` extends:
  a second member arrives with the hook that can put something somewhere else, and the
  precondition it wants to check is `case.planted_artefact is not None` plus the
  target's declared hooks. Nothing here reaches `send_message`, nothing here is an
  `Attempt`, and no counter moved — this is a property of a record, not of a run.
