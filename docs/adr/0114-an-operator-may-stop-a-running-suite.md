---
status: accepted
---

# An operator may stop a running suite

[ADR-0007](./0007-canary-nonce-as-proof-of-control.md) puts a halt in front of the
spend: a run is estimated in two figures, nothing reaches the operator's endpoint until
a person confirms them, and the run is then held to the ceiling they confirmed. What it
does not give is a second decision. Once a suite is going, the only things that end it
are the ceiling, a transport failure, or finishing — and a suite is minutes long,
against somebody's own agent, on somebody's own inference budget.

## Decision

**A running suite can be stopped, and a stopped run is an abort.**

1. **The flag is read where the next call is authorised, and nowhere else.**
   `RunState.authorise_call` is the one place a message is cleared before it goes on
   the wire, so a stopped run stops *between* one call and the next. Nothing already
   sent is cancelled: the attempts on the record are attempts the target answered, and
   there is no half-attempt on it. A flag read inside the transport would abandon a call
   already on somebody's endpoint and leave the record missing an attempt that happened.

2. **It is read before the ceiling.** A run stopped in the same instant it would have
   breached is a run somebody stopped; they are two facts about why the spending ended,
   and the reader is owed the one that happened.

3. **Aborted, with its own sentence.** `RunStatus.ABORTED` already means *stopped rather
   than finished* — the budget working in one case, a person deciding in the other — so
   this adds no status. What it adds is the sentence: who ended the run, that the
   families are reported over what was attempted, and that the figures are therefore not
   a gate result. An episode the stop cut short is **censored** on the ceiling's own
   terms (ADR-0011): the attacker stopped, and a target never given the chance to hold
   must not read as one that did.

4. **A stop and never a pause.** The flag is never unset and there is no resuming. The
   estimate an operator confirmed was for a run; a run continued an hour later under
   whatever the settings say by then is a different run, and offering to resume one
   would be spending against a consent given for something else (ADR-0007, ADR-0025).

5. **The route writes no status.** `POST /runs/{id}/stop` sets the flag and answers with
   the record as it stands. The worker settles its own run, because a status written by
   the thread serving the request would race the thread that knows what the run did.

6. **Only a run that is running.** A run still at its interrupt has sent nothing and is
   **declined** by answering the halt; a stop that quietly did that would record a
   refusal of the estimate as an abort of a run. A run that has ended has nothing to
   stop. Both are `409`, and an id this process never held is `404`.

## What this does not decide

That a stopped run's figures may be compared with a complete one's. They may not, and
the run's own statement is where that is said — a partial run is void rather than
smaller, which is `BudgetExceeded`'s own argument and applies unchanged here.

Nor does it give the gate walk or a pending-route measurement a stop. Both are their own
surfaces with their own leases, and neither is a suite somebody watches for minutes.

## The reservation

A stop is a button that ends something expensive, one press, no confirmation. That is
deliberate — a halt in front of a spend is worth a dialog and a halt in front of *not*
spending is not — but it means a mis-press costs the attempts already made, which are
not refundable and not resumable. If that turns out to bite, the answer is a
confirmation on the press and not a resume.
