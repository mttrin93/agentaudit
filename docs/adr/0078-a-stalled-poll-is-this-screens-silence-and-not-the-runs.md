# ADR-0078: A stalled poll is this screen's silence, and not the run's

**Status:** accepted (#121, under #119)
**Date:** 2026-09-06

## Context

The run screen polls `GET /runs/{id}` every two seconds for the minutes a run takes,
and until now it drew whatever the last answered poll said and nothing about the poll
itself. Every figure on it — the position in each layer, the calls spent, the six
family bars — is therefore dated, and nothing on the screen carried the date. A run
that is slow between attempts and a run whose answers stopped arriving are the same
picture: numbers that are not moving.

They are not the same situation, and the second one is invisible in the worst case
rather than the mildest. The screen already reports two kinds of silence and neither
covers this. `transport` is the **target** having stopped answering the bench, under
one of seven names, and the bench is the thing that says so. `unavailable` is a fetch
that came back a failure, which is a poll that *was* answered — with a refusal. A poll
that hangs, a laptop that slept, a tunnel that dropped, a bench that stopped: none of
those produces either, and the screen goes on showing attempt 40 of 181 as though it
had just read it.

So the screen needs to say something about its own link to the bench. The question is
what it may claim, how long it waits before claiming it, and what it offers to do.

## Decision

**The run screen reports its own liveness — waiting, answering, stalled, or settled —
computed from when it was last answered, and it never reports it as a fact about the
run or the target.**

**Twelve seconds, which is six polls missed.** Long enough that a single slow answer,
a garbage collection or a dev server recompiling is not an alarm; short enough that
somebody watching a run notices before they have read the frozen figures as new ones.
One missed poll would cry wolf several times an hour on a working connection, and a
minute is longer than a person will sit in front of unmoving numbers before drawing
their own conclusion — which is the failure this is here to prevent.

**A run that has stopped is settled and can never be stalled.** The poll stops itself
when a run is no longer going (`stillGoing`), on purpose: a finished run has nothing
left to tell this screen. Its last answer is therefore as old as the reader has had
the tab open, and it is the *final* answer rather than a stale one. Reporting that as
silence would be the screen alarming about a thing it did deliberately.

**Retry asks the bench again, and that is the whole of what it does.** It does not
restart the run, re-answer the interrupt, reload the app, or touch the target: there
is nothing to retry on the bench's side, because nothing was sent that failed. It is
the same read the poll makes, made now, and a stalled state that clears is a stalled
state that was about the link.

**The stamp is the time the figures were last answered, and it is drawn rather than
announced.** A reader who was not watching the screen arrive needs to date what is on
it; a screen reader user does not need the time read out every two seconds.

**The polite region announces the phase and never the tick.** The sentence it carries
is a function of the run's standing and the liveness kind, and of nothing that moves
on its own — no stamp, no count of seconds, no attempt number. A live region announces
when its text changes, so a sentence carrying any of those would read the run out
loud every two seconds for as long as it lasts, which is the opposite of what #119
asks a screen for. `liveness.test.ts` asserts the sentence is identical across two
different ticks of one phase.

**None of this is a security result, and the vocabulary keeps it that way.** The four
kinds are about this browser's conversation with the bench. A target that stopped
answering is a `TransportOutcome` with one of seven names on it, written by the bench
into the run's record (ADR-0011); a run stopped at its ceiling is an abort. Neither
can be produced by this module, which has no name for a target and never reads one.

## Consequences

- `frontend/src/run/liveness.ts` is a pure function of `{ answeredAt, now, inFlight }`
  and a formatter, so the rule is asserted in node with no DOM and no clock — the
  screen supplies the two times and holds no rule of its own.
- The run screen keeps a second interval beside the poll, ticking a `now` at the poll's
  own cadence. It has to be separate: the failure being detected is a fetch that never
  returns, and a clock advanced inside the poll's own tick would stop with it.
- `POLL_SECONDS` moves into that module, because the span is declared in polls missed
  and the two numbers should not be able to drift apart.
- **A settled run draws no stamp.** The figures on a run that has stopped are final
  rather than dated: there is no next answer they could be older than, and a time of
  day above them would read as a screen still watching something. The stamp is for the
  screen that is still asking.
- A stalled screen keeps drawing the figures it has. Blanking them would destroy the
  one piece of evidence a reader has about where the run was, and the stamp above them
  is what makes them honest.

## Alternatives rejected

- **A relative stamp that counts up — *answered 8 seconds ago*.** It is the most
  informative line on the screen and it is unusable in a live region: it changes every
  tick by construction, so either the region announces every second or the visible
  line and the announced one disagree. The absolute time is stable, dates the figures
  just as well, and is what a person reads back to a colleague.
- **Treat a stalled poll as a failed run.** It is the same picture from the reader's
  side and it is a different fact entirely: the run is very likely still going. A
  screen that says *this run failed* because it lost contact with the bench would put
  a client-side fault into the operator's account of what the bench did to their
  target, which is the class of error ADR-0011 exists to prevent.
- **Back off the polling once it stalls.** A sound instinct for a server under load
  and wrong here: the bench being polled is one process attacking one endpoint on the
  operator's own say-so, two seconds is already the cadence chosen against that, and a
  screen that quietly polls less is a screen that takes longer to notice the link is
  back. Retry is explicit instead, and the interval is unchanged.
- **A spinner, or motion of any kind, to show the screen is still trying.** #119 is
  explicit that nothing under it makes a screen louder or faster, and a spinner is the
  decoration a reader learns to stop seeing; it also cannot distinguish *waiting for
  the next answer* from *not being answered*, which is the whole distinction.
- **Say nothing and let the operator reload.** What shipped, and it works — for an
  operator who suspects something. The point of the stamp is the operator who does
  not.
