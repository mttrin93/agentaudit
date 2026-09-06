# ADR-0081: Motion reports a state change, and a reader can stop all of it

**Status:** accepted (#122, under #119)
**Date:** 2026-09-06

## Context

`frontend/src/index.css` had no `transition` and no `@keyframes` in it — 2,600 lines
and not one moving thing. That is not an oversight to be corrected wholesale. The
file's own header says why: the screens carry three attestations, a halt before
anything is spent, and statements about what this bench cannot measure, and *"prose
that is skimmed is prose that was not read."* A console that slides, fades and pulses
is a console that is skimmed.

But the same audit (#122) found the opposite failure beside it: roughly 212 classes
and four `:hover` rules. Most interactive surfaces answered the pointer with nothing
at all — a field, a summary, a link in a paragraph, a selection box all looked exactly
the same under the pointer as away from it. Adding those states is what raises the
question, because a state that appears instantly and a state that appears over a tenth
of a second are the same information and read very differently: the second one tells a
reader that *this* surface is the one that changed, and the instant one leaves them to
find it.

So the question is not *may this console move* but *which motion is a fact and which
is decoration* — and, once anything moves at all, what a reader who cannot tolerate
motion is given.

## Decision

**Motion reports a state change and nothing else.** A hover, a focus, a control going
dead, a thing opening: those are transitions, at 120ms. Everything else is refused —
nothing enters, nothing fades in on arrival, nothing pulses, nothing draws attention
to itself, and there is no `@keyframes` in this file.

**Only colour is transitioned, never geometry.** The transitioned properties are
`color`, `background-color`, `border-color` and `opacity`, and that list is enforced
rather than intended: `frontend/src/motion.test.ts` reads the stylesheet and fails on
any other property. Geometry is where decorative motion lives — a thing that grows,
slides or lifts is a thing announcing itself — and a colour that moves is the same
surface saying it changed.

**`transition: all` is refused by name.** It is not a shorthand for the four above; it
is a licence for whatever property a later rule happens to add, geometry included. A
policy that has to be re-argued at every future edit is not a policy.

**120ms.** Long enough to be seen as a change rather than a repaint, short enough that
a pointer moving down a list of six families is never waiting for the last row to
finish. It is one number in one place, because a console whose surfaces answer at
different speeds reads as several applications.

**All of it stops for `prefers-reduced-motion: reduce`**, over `*`, `*::before` and
`*::after`, with `!important` on both `transition-duration` and `animation-duration`.
The universal selector and the `!important` are both load-bearing: a transition
declared on a class outranks a universal rule on specificity, so a guard without
`!important` is a guard that loses every argument it has. The pseudo-elements are
named because several drawn boxes in this file are pseudo-elements — the tick's
checkmark, the switch's knob — and a guard that reached only elements would leave
them moving.

**The guard is tested, and the test refuses to be vacuous.** `motion.test.ts` asserts
first that something is transitioned at all, because the other two assertions pass on
a stylesheet with no motion in it — which is the state this file was in yesterday, and
a guard satisfied by the absence of the thing it guards is not a guard.

## Alternatives

**Leave the stylesheet still.** Rejected, but narrowly, and only once the hover and
focus states of #122 existed: a 120ms transition on a property that never changes buys
nothing, and this decision would have been premature before them.

**Transition `transform` too, for the switch knob and the disclosure markers.**
Rejected for now. It is the first thing a decorative edit would reach for, the switch
is a `role="img"` rather than a control (it is drawn beside a statement, not pressed),
and the disclosure triangle is the browser's own. Nothing on any screen is waiting on
it.

**Honour reduced motion by omitting motion entirely on those machines, per rule.**
Rejected: it means every future rule that moves anything has to remember to add its
own opt-out, and the one that forgets is invisible to everybody who is not affected by
it. One block at the end of the file that turns everything off is the only version of
this that stays true.

## Consequences

- `frontend/src/motion.test.ts` is a stylesheet test with no DOM, and it is the only
  place the policy is machine-checked. A future rule that transitions `transform`,
  `width` or `all` fails `npm test`, and the failure names the property.
- The reduced-motion block sits at the end of `index.css` on purpose, so that it is
  after everything it is turning off, and so that a reader looking for it finds it
  where a reader looks.
- **This ADR does not license entrance or attention motion at any duration.** #119's
  rule is that nothing under it makes a screen louder, faster or more decorated, and
  a fade-in is all three.
