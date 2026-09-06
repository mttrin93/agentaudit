# ADR-0077: A mark is retired by the edit, and the last mark takes the sentence

**Status:** accepted (#158, follow-up to #120)
**Date:** 2026-09-06

## Context

ADR-0076 got the API's sentence to the field it is about: a `422` names a `loc` path,
the path is the input's `id`, and the input drawn under it carries `aria-invalid` and
an `aria-describedby` pointing at the message. What that change did not say is when
any of it stops being true.

It stopped being true immediately and stayed on screen. `setRefusal(NOTHING_REFUSED)`
fired in exactly one place — `issue()`, where a new nonce is drawn — so the operator
read the message, corrected the field, and the red border and the sentence survived
the correction. A screen went on asserting a refusal about a value that was no longer
on it, which is worse than the page-level block ADR-0076 replaced: that block at least
never pointed at anything.

Retiring the mark walks into an invariant this codebase wrote down on purpose. A
`Refusal` is one state — `statement` and `fields` together — and both the type in
`api/contracts.ts` and the `useState` in `RegisterScreen.tsx` say why: held as two
states they drifted, and the operator was shown a sentence about *this* registration
beside `aria-invalid` about the one before it. Clearing one field's mark while the
page-level sentence stands is a state that invariant, read literally, forbids.

So the question is not *how* to clear a mark. It is what a mark and a sentence are
claims about, and therefore what retires each of them.

## Decision

**A mark is retired by the operator editing the field it is on, and by nothing else.
When the last mark of a refusal goes, the sentence goes with it.**

Three parts, and each is a claim the screen can actually keep.

**The edit retires it, not the value.** Nothing here re-validates. The screen does not
decide that `0.02` is a price the API would take — the API decides that, on the next
post, and `declarations.ts` already says why the guard here is a guide and the guard
there is the authority. What the screen knows for certain is narrower and sufficient:
the API refused a value, and that value is no longer the one in the box. The claim
`aria-invalid` makes is about a body that no longer exists, so it comes off. An
implementation that waited for the new value to look right would be a third copy of
the backend's validation, drifting from both.

**Per field, because the refusal is per field.** Correcting the price says nothing
about the name. A `422` naming three fields is three statements that happen to have
arrived in one response, and retiring all three on the first keystroke would cost the
operator two messages they still need — expensive here in particular, because every
refusal spends the nonce (`RegisterScreen`, *every refusal costs the nonce*). Getting
those two messages back means planting a fresh value and posting again.

**The sentence is retired by the last mark.** *Registration did not complete* is true
of the post, and the post it is true of is the one whose refusals are still standing.
Once none of them are, the sentence is the last thing on screen still asserting
something about a body the operator has finished editing. A refusal that named **no**
field is untouched by all of this: there is nothing on the form to correct, so its
sentence stands until the next post, which is rule 3 below still applying where it is
the only rule that can.

**This weakens the written invariant, and the new one is stated here.** *Set together
and cleared together* is no longer true and is not what was worth protecting. What was
worth protecting is that the screen never mixes two registrations. The invariant is
now:

> A refusal is one value with one setter, and it only ever moves toward nothing. A
> new refusal replaces it whole; the operator's edits narrow it, field by field, until
> the empty one is `NOTHING_REFUSED` and the sentence goes too. No path sets the
> sentence without its fields or the fields without their sentence.

The state ADR-0076's invariant existed to forbid — one refusal's sentence beside the
previous one's marks — is still unreachable, because the only widening move is a
wholesale replacement and there is still no setter that can move one half.

## Consequences

- The retirement is one delegated `onChange` on the register screen's `<form>`, which
  reads `event.target.id`. That is ADR-0076 paying for itself a second time: the `id`
  *is* the wire path, so a change event carries the name of the field it changed in
  the vocabulary the refusal arrived in, and nothing translates. The alternative was a
  `correct` callback threaded through four step components to ten `Field` call sites.
- An id the standing refusal does not name is a no-op, and the handler returns the
  refusal it was given rather than a new equal one — so a keystroke in an unrefused
  field is not a render, and the compiled memo sites in that file are not invalidated.
- `Field` is unchanged. It draws what the refusal says, and it has never decided how
  long the refusal lives.
- The e2e case in `frontend/e2e/keyboard.spec.ts` names **two** fields, because a
  refusal naming one cannot tell the three rules apart: with a single mark, retiring
  that mark and retiring the whole refusal are the same observable screen.

## Alternatives rejected

- **Editing any refused field clears the whole refusal, sentence and marks together.**
  It honours the old invariant exactly and needs no new one, which is a real argument
  and the reason this was close. It loses on price: the other marks are messages that
  cost a spent nonce to see again, and it discards them on evidence — one keystroke in
  one box — that says nothing whatever about the fields it clears.
- **Nothing is retired until the next post**, which is what shipped. Defensible if the
  marks are read as *what the bench refused*, a historical fact. Nothing on the screen
  offers that reading, and `aria-invalid` is not available for it: the attribute has a
  meaning in the accessibility tree — *this value is not acceptable now* — and a
  screen reader announcing it over a corrected field is being told something false.
- **Re-validate on edit and retire the mark when the value looks acceptable.** The
  most informative rule and the only one that can be wrong in the operator's face: the
  screen would be asserting the API will accept a value it has not been shown, using a
  copy of rules the API owns. `declarations.ts` keeps a copy of those rules already,
  deliberately and as a *guide*; spending it on a claim about a specific refused value
  is where that arrangement stops being safe.
- **Retire the mark on blur rather than on the first keystroke.** Fewer state changes,
  and it holds the mark up while a half-typed value is on screen, which reads as the
  screen refusing what is being typed. The mark is about the posted value, and the
  posted value stops being on screen at the first keystroke.
