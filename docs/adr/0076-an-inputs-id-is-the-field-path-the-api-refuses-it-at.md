# ADR-0076: An input's id is the field path the API refuses it at

**Status:** accepted (#120, sub-issue of #119)
**Date:** 2026-09-06

> **Amended by [ADR-0077](./0077-a-mark-is-retired-by-the-edit-and-the-last-mark-takes-the-sentence.md)
> on how long a mark lasts, and on nothing else.** This ADR says what names an input
> and got the message to it; it left open when either stops being drawn, and the
> answer shipped as *never, until the next post*. ADR-0077 retires a mark when the
> operator edits the field it is on, and the sentence when the last mark goes.
> Everything here stands and is used by it — the retirement reads `event.target.id`
> off one delegated handler precisely because the DOM name is the wire name.

## Context

The console posts one body it did not choose the shape of. `POST /runs` takes
`StartRunRequest`, and `bench.ts` says why every field on the way there is
`snake_case`: the body is a contract with `backend/api/app.py` rather than a shape
this app is free to name, and a camel-cased mirror would be one rename away from
posting a body the API refuses.

When the API does refuse one, FastAPI answers `422` with a `detail` list, and each
entry carries the path it refused at — `['body', 'cost', 'price_per_call']` — beside
the message. `http.refusalIn` already read that list rather than only the string form
of `detail`, and for the stated reason: a screen showing *refused, no reason given*
would be hiding the one message that says which field.

It then threw the path away. The entries were joined into one sentence and the
sentence was drawn in the page-level `.refusal` block at the top of the register
screen, which left the operator to map `body.cost.price_per_call` onto a form by
hand — on a walk that is three steps deep, where the field in question may be two
steps behind the button they pressed. There was no `aria-invalid` and no
`aria-describedby` anywhere in `frontend/src/`, so a screen reader was told nothing
at all. #120 asked for the message to reach the field, and left open the question
this ADR answers: **what names an input, such that a `loc` path finds it.**

## Decision

**The `id` of an input is the `loc` path the API would refuse it at, joined with
dots and shortened nowhere.** `body.target.url`, `body.cost.price_per_call`,
`body.attestation.identity`. One string is the DOM name and the wire name, so a
refusal that arrives naming a field finds the input by the string it arrived with,
and `document.getElementById(field)` is the whole of the lookup.

Three things follow, and they are the reason the convention is worth stating rather
than being a detail of one screen.

**Nothing translates.** There is no table from wire path to field name, no prefix
stripped, no `body.` removed on the way in. A translation is a third thing to keep
correct, and the failure it produces is silent: a rule that stopped matching would
leave a refusal about a real field landing on no input, which is the state this
change exists to end and is indistinguishable from it.

**The path is carried whole, so `FieldRefusal` is a wire shape.** It lives in
`api/contracts.ts` with the other shapes more than one area names, not in `http.ts`,
because a screen has to be able to see it — `bench.ts` deliberately does not
re-export `http.ts`, and the type a screen reads a refusal through cannot be behind
that line. `refusalRead` returns the sentence and the fields from one read of the
body, because a `Response` body is read once and a second function fetching the
fields separately would have nothing left to parse.

**A refusal that names no field still has a sentence, and it is still drawn.** A
raised `HTTPException` — the nonce was never issued, a run is already in flight — is
about the registration and not about an input, and `fields` is empty for it. The
page-level block does not go away; what changes is that a refusal which *did* name a
field now also reaches that field. Both are shown, because the sentence says what
happened to the registration and the field says where.

**The walk goes to the step that draws the named field, and puts the keyboard on
it.** This is the local consequence of the convention on the one screen that is a
walk, and `RegisterScreen.stepShowing` is where it is written. A message bound to an
input two steps back is a message nobody reads, so the id being resolvable is not
sufficient on its own — the step drawing it has to be on screen. A field this screen
does not draw at all sends the operator to the start of the walk with the bench's own
sentence over it, rather than nowhere.

## Consequences

- `FIELDS` in `RegisterScreen.tsx` lists every one of these strings in one place, and
  they are a contract with `backend/api/app.py`'s models exactly as the body's field
  names are: a field renamed there is renamed here. The failure of getting it wrong
  is a refusal drawn over the form instead of under the input, which is where the
  console was before this ticket — a degradation and not a break.
- Ids with dots in them are valid HTML and are looked up with
  `getElementById` / `[id="…"]` rather than with a `#` selector, which would need the
  dots escaped. The Playwright spec uses the attribute form for that reason.
- The message element's id is derived from the field's: `body.cost.price_per_call`
  and `body.cost.price_per_call.refused`, so `aria-describedby` needs no second
  registry either.
- Nothing about the backend changes. This is a convention on the client for reading
  what the API already sends, and the API is free to grow a field the console does
  not draw — that refusal is drawn over the form, which is where every refusal was
  drawn until now.

## Alternatives rejected

- **A lookup table from `loc` path to a field name of the screen's own choosing.**
  The extra indirection buys shorter ids and a silent failure mode: the table drifts,
  and what a reader sees is a message that vanished rather than an error.
- **Stripping the leading `body.`.** Cosmetic — the ids read a little better — and it
  is a rule, which means it is a rule that can be applied inconsistently. It also
  makes `body`, `query` and `path` refusals collide the day the API refuses at one of
  the other three.
- **Reporting the refusal only at the field, dropping the page-level block.** A
  refusal names a field or it does not, and the ones that do not are the ones about
  the run. Removing the block would leave those with nowhere to be drawn.
- **A `name` attribute rather than an `id`.** `name` is for what a native form
  submission would post, and this app posts JSON it builds itself (`startRunBody`).
  Using it here would suggest the form's fields are the request's fields, which is
  true of their *paths* and not of the mechanism.
