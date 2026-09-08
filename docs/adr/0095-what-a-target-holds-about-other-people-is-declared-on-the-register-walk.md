---
status: accepted
---

# What a target holds about other people is declared on the register walk

[ADR-0043](./0043-the-canary-a-nonce-cannot-be-confused-with.md) decided that PII
leakage is read over a record the target holds **about a person**, and that a target
holding none is one the family declines to measure rather than one it reports a clean
zero for. `Precondition.PERSONAL_RECORDS_HELD` carries that, every case of the
family requires it, and `TargetConfig.holds_personal_records` defaults to `False`,
which is the conservative direction.

Nobody has ever been able to declare it. `TargetRequest` had no field for it and none
of the three CLI entry points had a flag, so the only targets that ever declared it
were the reference agents and a callback constructed in a test. The consequence is
exactly the one [ADR-0093](./0093-session-retention-is-declared-on-the-register-walk-and-the-bar-counts-what-the-target-can-answer.md)
closed for session retention, over a second capability and a second family: **the
tier's PII leakage family was measurable in-process and unreachable for every target
this API ever registered.** An operator could switch the family on in the console,
request it on the run, and get three withdrawn cases and an empty bar — and, after
[ADR-0094](./0094-the-seed-is-per-library-directory-and-a-requested-elective-family-with-no-case-is-stated.md),
an empty bar with the wrong sentence under it.

This record closes the declaration, and takes that sentence off the run screen.

## Decision

1. **`TargetRequest` gains `holds_personal_records`, and `config()` passes it
   through.** A `bool` defaulting to `False`, on ADR-0093 decision 1's argument
   unchanged: silence and *no* produce the same run, the absent state has a meaning
   ADR-0043 already argued for, and the narrower run is the safe direction. It is
   deliberately not derived from `reaches_private_data`, one of the four the Agents
   Rule of Two is read over — that is a statement about what the agent can *reach*
   and ADR-0038 §3 keeps it sharing no function with a family; this is a fact about
   what is there to be disclosed, and a family gated on the other would be a family
   gated on the Rule of Two's reading.

2. **The three CLI entry points gain `--holds-personal-records`**, and `bench.py`
   forwards it to `serve_callback`. What a callback holds about other people is not
   something the shim can read off it, so it stays a declaration on ADR-0059 §2's
   terms, exactly as retention does.

3. **The question is asked on the `tools` step, as a third fieldset, and it holds
   nothing.** ADR-0093 decision 3 applies as written: the same kind of question with
   the same kind of consequence — not a rate, but whether a family is asked at all —
   two radios and no third, unanswered posting the `False` the API would have
   defaulted to, and no entry in `unmetConditions` or `canLeave` because the unsafe
   direction does not exist. It sits *above* the Rule of Two's four on the same step,
   because the answer about reaching private data is the one it could be mistaken
   for, and the two questions are next to each other on the screen where the
   difference has to be legible.

4. **The run screen prints no reason a family was not attempted.** ADR-0094 gave a
   requested elective family with no case a sentence under both columns, so that an
   empty bar would not read as a family that had not started. Two things are wrong
   with it now. It is served for *one* of the reasons a bar can be empty — the
   library holding no case — while a family withdrawn as not measurable against this
   target reaches the same field as an empty string, so the one run that most needed
   a reason got either nothing or, when the library gap and the withdrawal coincided,
   a sentence blaming the library for the target's own declaration. And there are
   nine families: one paragraph each is a page of prose about the attempts a run in
   flight is *not* making, above the bars for the ones it is.

   So the row keeps `no_case` and the count slot keeps reading `not run` instead of
   `0 / 30` — which of the two kinds of empty it is stays visible — and the sentence
   comes off the screen. The report is the document that has to account for every
   family, and it already does: `measured.not_run` carries the six's gaps with their
   reasons and `measured.elective_not_measurable` carries the tier's withdrawals with
   theirs, each under its own name.

## Considered options

**Splitting the row's zero-reason into two fields, library gap and withdrawal.**
Rejected here, and it is the fix decision 4 replaces. It makes the row able to print
two sentences where the objection was already that it prints one too many, and it
puts the report's `elective_not_measurable` reasoning in a second place — a screen
and a signed document that would then have to agree.

**Making the declaration required.** Rejected on ADR-0093's argument: an unanswered
question and a `no` produce the same run, so requiring it costs a step that would
refuse a registration the API accepts and buys nothing an operator can act on.

**Reading it off `reaches_private_data`.** Rejected on decision 1. The two are
different statements — what the agent can reach against what is there to be disclosed
— and the shortcut would let a Rule of Two answer decide a family's measurability,
which ADR-0038 §3 exists to prevent.

**Seeding the reference target's records for every run instead.** Rejected: it makes
the bench plant records about invented people in somebody's production-adjacent
system, and ADR-0043's whole point is that the family reads a record the *target*
holds.

## Consequences

- A target registered from the console or a script can declare that it holds records
  about other people, so the tier's PII leakage family is reachable against a user's
  target for the first time. Requesting the family without the declaration still
  produces no attempt — correctly, and now because the operator said so.
- `Declarations` gains one `boolean | null` field, defaulted to `null` and posted as
  `false`, with the same negative asserted for every step and every answer that
  ADR-0093's field asserts.
- The run screen loses one paragraph per requested elective family and keeps the
  `not run` word. Nothing else about the tier's rows moves: the six and the tier are
  still two lists mapped twice, and no length is taken against the other tier's
  denominator (ADR-0035 §2).
- A declaration made here is a claim the bench cannot check, on ADR-0024's terms. An
  operator who ticks it against a target holding nothing about anybody gets a family
  measured on records that are not there, and the screen says what the answer buys
  before they answer it.
- `docs/validation.md`'s *what has never been validated* keeps its line about no real
  operator having declared any of this. The tier's PII leakage family has still never
  been measured against anything but a reference agent — what changed is that it now
  can be.
