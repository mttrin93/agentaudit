---
status: accepted
---

# A planted canary that will not be echoed is still measurable

[ADR-0007](./0007-canary-nonce-as-proof-of-control.md) fuses two things into one value: the canary the data-leakage family extracts, and the proof that whoever pointed the bench at an endpoint can configure it. The proof is the **echo** — the target is asked, cooperatively, to repeat the planted value, and only somebody who could edit the configuration could have put it there.

`registration.py` already records the tension this creates: the echo probe asks the target to cooperate and the leakage cases try to extract the same value *without* cooperation, "and a target that resists that is well defended — not unregistered. Collapsing the two would make a hardened target unregistrable." Two messages keep them apart. What that does not fix is a target whose disclosure rule is **blanket**: an agent instructed never to reveal its own configuration cannot tell a registration check from an attack, refuses both, and is refused registration for having the defence the bench exists to measure.

ADR-0007's amendment gave that operator a waiver, and the waiver does two things at once because one boolean carried both: the run may start without the echo, **and** the data-leakage family is dropped. Dropping it is right for the case the amendment was written for — an operator who cannot write into the configuration at all, whose canary is nowhere, and whose thirty attempts would come back resisted against an attack that was never possible. It is wrong for the case above. There the canary **is** in the target. The family is measurable. The only thing missing is the cooperative reply.

**Decision.** The two statements are two declarations.

| Declaration | What it decides | What it never decides |
|---|---|---|
| `nonce_planted` | whether the data-leakage family is run — the canary's presence is what makes the family measurable | whether a missing echo stops the run |
| `echo_waived` | whether a missing echo stops the run | whether any family is measured, and what it measures |

`proof_waived` is now derived — `echo_waived or not nonce_planted` — and the registration record is unchanged: `echoed` is still what the endpoint did, `waived` is still what the operator declared, `complete` is still `echoed or waived`, and no field anywhere reads *proved* off a run that only declared it. The probe is still sent on every path, because a target that echoes anyway has proved control whatever was declared.

So the state this ADR adds is `nonce_planted = true, echo_waived = true`: the probe is sent, the reply is kept, a missing echo does not stop the run, **the leakage family runs**, and the artefact says control was declared and not proved — the same sentence a waived run has always carried.

## What this gives up

**Authorisation loses its evidence and keeps only its record.** On this path what stands between the bench and an endpoint nobody owns is the attestation plus the nonce having been issued by this bench — that the caller went through registration, not that they can configure the target. That is weaker than an echo and it is the point of the trade. It is not weaker than the waiver ADR-0007 already accepted; it is the same weakening, now available to an operator who has more control over their target rather than less.

**A leakage rate is measured against a canary whose presence is a declaration.** If the declaration is false, the family reports thirty resisted — the clean zero that reads as a defence and is not one, which is exactly what dropping the family prevented. That guard moves from a mechanism to a sentence, and the compensation is that the sentence is on the artefact permanently rather than in a run's memory.

**What does not move.** A declaration here decides whether a family is *attempted*; it cannot touch what the attempts then measure. No rate, band, interval or `D` is written by an operator's answer, so [ADR-0006](./0006-overrides-never-change-a-measured-rate.md)'s invariant is untouched — this is a precondition of measurement, not an input to one.

## The alternative, and why it was not enough

The other route is a carve-out in the target's own prompt: plant the nonce with explicit permission to echo *that value* on a registration check, and nothing else. It works, it is narrow, and it stays available — but it asks the operator to write an exemption into the control that the data-leakage family is about to attack. The narrower the carve-out the better it holds, and it is still the bench requiring a change to the thing under test in order to test it. Offered as guidance, refused as the only door.
