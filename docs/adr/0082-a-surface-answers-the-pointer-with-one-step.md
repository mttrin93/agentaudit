# ADR-0082: A surface answers the pointer with one step, toward the accent or away

**Status:** accepted (#122, under #119)
**Date:** 2026-09-06

## Context

`frontend/src/index.css` is roughly 212 classes and had four `:hover` rules in it —
`button`, `.act`, and two rail rows. A text field, a selection box, a disclosure
summary and a link inside a paragraph all looked exactly the same under the pointer as
away from it, which on a near-black ground with a hairline palette means a reader
often cannot tell what on a screen is pressable until they press it.

Adding the missing states raises a question the four existing rules had never been
made to answer together, because they do not agree on the face of it: `button:hover`
takes an accent border, `.act:hover` takes an **ink** border, and the rail rows take a
lifted background. Filling that out class by class, each on its own judgement, is how
a stylesheet ends up with eleven hover treatments and no rule — and this file's whole
argument is that the console is one instrument rather than several applications.

The palette also constrains the answer. `--accent` means *chrome* and never data, and
the five chart accents each mean a layer or a reference agent; a hover that borrowed
one of those would say *scored layer* about a summary. And `index.css`'s header, and
#119's rule, both forbid making a screen louder or more decorated.

## Decision

**A surface answers the pointer with exactly one step: toward the accent, or — where
the surface is already in the accent — toward the ink.**

That is one rule, and it turns out to be the rule the four existing hovers were
already following. An outlined button is a hairline, so its edge takes the accent. A
field is an outlined control, so it takes the same. A summary set in ink takes accent
ink. `.act` and the plant note's summary are already the accent, so they go the other
way. The rail is the one deliberate exception and says so at its own rule: a row in a
list of destinations answers with a lift, because the rail marks *where you are* the
same way and the two signals have to be the same vocabulary.

**One step, and never a fill, a lift or a size.** A hover that filled a control would
read as a press; one that moved or grew it would be the decoration #119 forbids and
would also be geometry, which ADR-0081 refuses to transition.

**Hover and focus are drawn differently on purpose.** Focus is the ring
(`:focus-visible`), outside the box and offset from it. Hover is on the box's own edge
or ink. So a reader whose pointer is over the control the keyboard is in sees both at
once and can tell which is which — which a hover that reused the focus ring's own
treatment would have taken away.

## Alternatives

**A background fill on hover, as most component libraries do.** Rejected: on three
surfaces within a few points of each other (`--paper`, `--page`, `--rail`) a fill
strong enough to see is a fill strong enough to read as *pressed*, and this file draws
wells rather than tiles for the same reason.

**Leave it to the browser.** Rejected — the browser's default hover on these controls
on a dark ground is nothing at all.

**Per-class judgement, no rule.** Rejected: it is what produced four hovers that
appeared to disagree, and it has no answer for the next control anybody adds.

## Consequences

- The rule is stated once, at `button:hover` in `index.css`, and every other hover
  rule in the file carries a pointer to it rather than re-arguing it.
- **A control added later has its hover decided already**, and needs a sentence only
  when it is the exception — as the rail is.
- The rule is a colour rule, so everything it produces is inside what ADR-0081 allows
  to be transitioned. The two decisions were taken together and in that order: the
  states first, and only then the 120ms on them.
- Two surfaces are deliberately left to the browser and say so at their own rules: the
  temperature slider, which has no border for a step to be taken on and whose thumb
  the browser draws with `accent-color`, and the declaration checkboxes, which are
  native boxes drawn in the house mint by `accent-color` on the root.
