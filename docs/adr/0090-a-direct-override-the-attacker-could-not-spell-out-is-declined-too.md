---
status: accepted
---

# A direct override the attacker could not spell out is declined too

[ADR-0084](./0084-a-route-the-record-cannot-carry-is-declined-and-not-synthesised.md)
decided that **a route the attacker found and no case record can carry is declined with
its reason, recorded on the episode, and proposed to nothing** — and named one reason
it happens: `proposal.proposed_from` copies the objective's success condition, and a
condition in `CARRIED_BY_FETCHED_CONTENT` needs a `planted_artefact` a probe cannot
supply.

#173 pointed the layer at the elective tier and found a **second** reason, in the family
the ticket expected to file normally. `direct_prompt_injection` reads
`direct_instruction_executed`, which is in `CARRIED_BY_THE_MESSAGE`, and
`Case._refuse_a_canary_the_wrong_channel_spells_out` requires that kind's payload to
**spell the canary out in two pieces** ([ADR-0042](./0042-the-canary-is-spelled-out-in-one-channel.md)):
a case whose canary could have arrived through content the target fetched is indirect
prompt injection's verdict, and the two families are two denominators. The attacker is
**blinded to the canary** (ADR-0011: *you are not told the value; the bench recognises
it*), so the probe it composed almost never spells out either half — and the record
refused the pairing with a `ValueError` out of `Case.__post_init__`, which left the
episode, left the layer, and ended a run whose scored layer had already been paid for.
That is #166 exactly, in a second family, and the containment ADR-0084 built does not
reach it because its guard reads one set of kinds.

## Decision

**The channel guard is checked in `proposal.proposed_from`, before the record is built,
and a probe that cannot satisfy it is declined as `RouteNotFilable` with its reason.**

1. The refusal is the same type and the same route as ADR-0084's: raised where the copy
   happens, caught by the episode, handed back to the attacker as its tool result and
   recorded on `AdaptiveEpisode.declined`. One kind of answer for one kind of fact — a
   route the layer could not file — rather than a second vocabulary for a second
   invariant.

2. **It is a property of the probe and never of the family.** The check is
   `library.spells_out` over the payload that actually ran, the same predicate
   `Case.__post_init__` applies, so a probe that *did* spell both halves out — the
   attacker having read them off a reply it broke — is filed and faces the bar like any
   other. A blanket refusal keyed on the family would throw that away and would state
   something about `direct_prompt_injection` that is not true of it.

3. **The join is refused on this side too.** A payload holding the whole canary would
   score a target that merely echoed the message, which is the same refusal the record
   makes, and reaching the record to be told so would be the crash this ADR closes.

4. Nothing here is scored. A declination has no denominator (ADR-0010), and the count of
   them decides no gate, no band and no admission.

## Why not synthesise a canary-bearing probe

Because the probe is the evidence. The payload on a proposed case is *the message the
target actually received* — taken off the episode's own record rather than off the
tool's argument, so a case cannot be proposed with a payload the target never saw. To
make the record loadable, the bench would have to write the canary's two halves into
that text, and the case would then carry a payload nobody sent, under a provenance that
says an attacker found it. It is ADR-0084's own argument about the planted artefact,
one field over: a record assembled to satisfy a check rather than to describe what
happened is evidence manufactured to clear a bar.

## Considered options

- **Catch `ValueError` in `_propose`.** Rejected for the second time, on ADR-0084's
  reasoning: it would fix this crash and hide every future construction bug behind the
  same handler. The type is the point.
- **Unblind the attacker to the canary in this family.** It would make routes filable
  and it would make the family's episodes meaningless — an attacker handed the string
  the verdict is read for is running the fixed suite with extra steps, and ADR-0007's
  *one planted value, two roles* becomes one value the attacker was told. Rejected.
- **Withdraw `direct_prompt_injection` from the adaptive layer.** It removes the crash
  and loses the reading: the layer's episodes there are real observations of whether an
  attacker can produce an override this target carries out, and #173 exists to have
  them. ADR-0084 refused the same trade for indirect prompt injection.
- **Let the admission gate refuse it.** There is nothing to hand the gate: the record
  cannot be constructed at all.

## Consequences

- **The adaptive layer files nothing from the elective tier as it stands, and one of
  the three reasons is not the one #173 expected.** Memory poisoning and every other
  content-carried family decline under ADR-0084; direct prompt injection declines under
  this one whenever the probe does not spell the canary out, which is nearly always;
  `pii_leakage` files normally. `docs/validation.md` states all three before the first
  run rather than after it.
- **`A_break` and `A_effort` are untouched**, as in ADR-0084 and for the same reason: a
  declination changes neither an episode's outcome nor its turn count. And under
  [ADR-0089](./0089-a-break-is-over-the-six-and-the-tier-is-read-beside-it.md) no
  elective episode reaches either figure in any case.
- **What is not claimed:** that a route in this family is worthless. It is unfilable *by
  a blinded attacker's probe*, which is a statement about what the record needs and what
  the attacker is allowed to know — and it is the open question ADR-0084 left, arriving
  from the other channel.

Cross-references: [ADR-0084](./0084-a-route-the-record-cannot-carry-is-declined-and-not-synthesised.md)
(the rule this applies), [ADR-0042](./0042-the-canary-is-spelled-out-in-one-channel.md)
(the invariant that refuses the record),
[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (why the attacker does not
know the canary), [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)
(nothing here is scored), #166 (the crash this shape already caused once), #173.
