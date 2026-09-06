# ADR-0080: Only what an answer produced alarms; everything else is polite

**Status:** accepted (#122, under #119)
**Date:** 2026-09-06

## Context

Eighteen blocks across the seven screens carried `role="alert"`. They are of two
kinds and the markup did not distinguish them.

The first kind is a block that is on the screen when the screen arrives, or that
arrives on its own afterwards: a bench that did not answer for its runs, its
artefacts, its gate, its own configuration; a report the bench did not serve; a run
whose poll came back a failure; the two estimate figures a screen was handed nothing
for. Nobody pressed anything to produce these. They are what the screen turned out to
say once it had read what it reads, and several of them are in the first paint.

The second kind is a block that exists because an operator did something and the
bench said no: a registration refused, an interrupt answer not taken, a family
switched that the bench would not switch, a setting the bench would not store, a gate
run that did not start.

`role="alert"` is `aria-live="assertive"`: it interrupts whatever a screen reader is
saying to read the block out now. For the second kind that is exactly right — the
reader pressed a control, is waiting to learn what happened to it, and the answer
should not queue behind the paragraph they were on. For the first kind it is wrong
twice over. It interrupts a reader who asked for nothing, and it is unreliable in the
one case it was most often used for: an assertive region that is *already present in
the DOM at first paint* is not an announcement at all in several screen readers,
because nothing changed inside a live region — the region arrived with the document.
So the loudest role in the vocabulary was being spent on the blocks least likely to
be announced by it.

There is a third consideration that the run screen already ran into (ADR-0078): that
screen has a polite region which announces its phase, and a second assertive copy of
a fact already announced politely is the screen saying one thing twice at two
volumes.

## Decision

**A live region alarms only for what an answer to an operator's action produced.
Everything else is `role="status"`.**

The test is not *is this bad news* and not *is this red*. It is: **did a person press
something, and is this block the answer to that press?** A refusal is not
automatically an alert — the run screen's `unavailable` is a refused fetch, and it is
a refused fetch of a poll that runs on a timer with nobody watching it, so it is
polite. A block with no error in it is not automatically a status — but in practice
none of the six that stayed assertive is anything other than a refusal, because a
successful action on these screens changes the screen rather than adding a block to
it.

**Six sites keep `alert`**: the registration refusal, the interrupt answer that was
not taken, the gate run that would not start, the refused family selection, the
refused layer selection, and the refused settings change.

**Ten become `status`**: every *this bench did not answer for …* block on the
landing, artefacts, gate and settings screens, the report's two absences, the run
screen's unavailable poll, and the estimate figures a run screen was handed none of.

**The rename is per site and is not a codemod.** The rule is about how a block came
to be on the screen, which is a fact about the state that gates it and not about its
class, its wording or its colour. Two blocks that are the same `div.citation.uncited`
with the same heading shape sit on opposite sides of this line on the landing screen.

## Alternatives

**Leave them all assertive.** The status quo. Rejected because it makes the console
interrupt a reader for facts nobody asked about, and because on the several blocks
that are in the first paint it does not even buy the interruption — it buys nothing,
loudly.

**Make them all polite.** Simpler, and one rule with no judgement in it. Rejected
because it loses the case the assertive role exists for: an operator who has just
pressed *Register the target* and is not looking at the top of the page has to be
told that nothing was registered, now, and not after whatever they were reading.

**Drop the roles and rely on focus movement.** #120 already moves the keyboard onto a
refused field, and #121 moves it onto an arriving heading. Rejected because neither
covers a refusal that names no field on a screen that did not change: the focus stays
where it was, and without a live region nothing is said at all.

## Consequences

- Ten blocks are announced politely, after whatever is being read finishes, and the
  blocks that were never reliably announced on mount are now in the role that does
  not promise they will be.
- The six that alarm are exactly the six an operator is waiting on. Each is gated on
  a state that only an answer to a request can set, which is what a reviewer should
  check when a seventh is proposed.
- **A new block starts polite.** `role="status"` is the default for anything this
  console adds to a screen; `alert` is the exception a site argues for at its own
  call site by naming the press it answers.
- The run screen's polite region (ADR-0078) is now the same politeness as the blocks
  beneath it, so a phase change and a failed poll no longer compete.
