---
status: accepted
---

# The verifier reads the denominator and asserts the rest of the bar

Two decisions this repository made separately met in a signed document and
contradicted each other.

[ADR-0025](./0025-the-console-may-set-a-runs-declared-inputs.md) admits
`attempts_per_case` as a declared input of the next run, and argues the offer at
length: *"Refusing to offer it was rejected: an operator exploring a new target does
not want 181 calls per target to find out whether the wire works."* `ATTEMPTS_RANGE`
is `(1, 50)`, the range is enforced rather than clamped, and the block that offers
the setting prints *not a gate result* beside it.

`verification._declared_bar` compared the payload's stated `attempts_per_case`
against `DECLARED_RULE.attempts_per_case` unconditionally, and it had its own good
reason: a bar read out of the document is a bar a forger can move, and the check is
what stops a doctored `fails_at_or_above` promoting a band with every other
comparison still agreeing ([ADR-0003](./0003-gate-decision-rule-and-sample-size.md),
[ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md)).

So a run made at the number the console offered signed an artefact that reported
`arithmetic_disagrees` when checked. The bench signed a document and then called it
wrong. Found by #19 while building the browser walkthrough — the first version of
that walk shrank its run that way and its own verify step caught it — reported
rather than fixed, and fixed here (#56).

**This is worse than a wrong status line.** The signature is this project's central
claim, and the third check is the only one that is about the bench rather than the
transport. An artefact that is correctly signed and reports its own arithmetic as
disagreeing teaches its reader that `arithmetic_disagrees` is noise to be ignored,
which is exactly the state in which a real tampering goes unnoticed. It is the
failure shape of a flaky test: a check that cries wolf has been disabled by other
means.

**Decision.** The third check asks two questions about the bar and gives them two
different kinds of answer.

- **The attempts per case is read, not asserted.** It is a declared input the console
  offers, so a payload stating another number may be an operator probing a target
  cheaply. A departure makes the report **not a gate result**, and that is reported:
  `ReDerivationOutcome.AGREES_OFF_DECLARED_RULE`
  (`arithmetic_agrees_not_a_gate_result`), a fourth answer of the third check, whose
  `held` is true and whose `contradicted` is false. Such an artefact verifies, and
  exits `0` under `scripts/verify`.
- **Every other number of the bar is asserted against the declared one**, exactly as
  before: the interval confidence, the κ floor, both band cut points and the wording
  that follows from them. No route offers any of these, so a payload stating another
  number for one of them has been doctored, and it fails as it always did.
- **The sentence is re-derived from the number.** `GateRule.denominator_stated` is
  one wording, carried in the signed payload beside the number
  (`provenance.rule.attempts_per_case_stated`), printed in the rendered document, and
  recomputed by the verifier from the number it sits beside. A document cannot
  therefore carry a non-declared denominator while telling its reader it carries the
  published one.

## The three readings, and what rejected two of them

**(a) The payload's rule equals the declared rule — the behaviour that was there.**
It makes ADR-0025's offer a trap: every use of a setting the console deliberately
exposes produces an artefact the bench itself reports as wrong. And the cost is paid
by the check rather than by the operator, because the reader who sees the outcome
fire on a run nobody tampered with learns to ignore it.

**(b) The payload's rule equals the rule the run was started with.** This is what the
artefact *should* be checkable against, and it is not checkable at all. The rule the
run was started with reaches a recipient through exactly one channel — the payload —
so comparing the payload's rule against the run's rule is comparing the payload
against itself, and it passes for any number a forger writes in both places. A
recipient holding three files and no sender has nothing else to compare against.
What actually protects the number after the fact is the signature, which covers it:
altering it in transit is `signature_invalid`, and that is check 1's answer rather
than check 3's.

**(c) The rule is unconstrained, and a non-declared rule makes the report not a gate
result — chosen, and narrowed.** *Unconstrained* is too much: it would hand a forger
the κ floor and the cut points, which is the whole reason `_declared_bar` exists. The
narrowing is the line between the two: **a number some route offers is stated, and
every other number is asserted.** That line is not a judgement call at the call site
— it is the list of fields `Instrumented` carries, and `attempts_per_case` is the
only member of it that is in `GateRule` at all.

## A doctored rule still fails, and by three different mechanisms

The distinction this ADR draws is between a rule the operator declared and the
document states, and a rule that was altered after the fact. The second still fails:

1. **Altered in transit** — the rule is inside the canonical bytes the signature
   covers, so rewriting `attempts_per_case` without the key is `signature_invalid`.
2. **Altered and re-signed by a forger with the key, keeping the declared wording** —
   the sentence is re-derived from the number, so the two disagree and the outcome is
   `arithmetic_disagrees` at `provenance.rule.attempts_per_case_stated`.
3. **Any other number of the bar** — asserted against the declared value, unchanged.

And a departure cannot promote anything. `attempts_per_case` enters no figure the
verifier recomputes: a rate and its Wilson bounds come from the successes and
attempts printed beside them, and a band comes from the interval and the cut points.
There is no reading of the denominator that makes a family's band better, which is
why reading it costs the check nothing.

## Consequences

- **A report measured off the declared rule says so in three places, and one of them
  is the document.** The payload carries the sentence, the rendering prints it under
  the rule block, and the verifier prints it under the third result — so a reader who
  never saw the console that offered the setting is told, which is what ADR-0025's
  condition 1 asks of every declared input.
- **The golden rendering digest moved**, in the commit that moved the wording
  (`test_rendering.GOLDEN_ONE_FAMILY`). No issued signature depends on it.
- **`ReDerivation.departure` travels on all four outcomes and names only one.** A
  report whose figures disagree, or which states no figure at all, was still measured
  on some denominator and its reader is owed the same sentence; but a disagreement is
  still a disagreement, and the denominator a run was measured on cannot make one
  better or worse.
- **The screen takes a passing set rather than one outcome.** `verificationReading`'s
  third row is held for either agreeing outcome, because drawing an artefact that
  verified as a failed row is the same lesson in miniature.
- **The browser walkthrough could now shrink its run through `attempts_per_case`, and
  deliberately does not.** It is the one end-to-end assertion that a recipient's
  verification of a real run comes out `arithmetic_agrees`, and that is the everyday
  answer worth walking; the fourth answer is asserted in
  `backend/tests/test_verify.py`. What the walk drops is the stale claim that the
  setting *cannot* be used — the finding it reported is closed.
- **`n = 30` is untouched.** ADR-0003's sample size is what the gate is decided at,
  `scripts/gate.py` still reads `DECLARED_RULE` and takes no setting from any
  console, and nothing here makes a run at another `n` comparable to one taken at the
  declared rule. It makes the artefact say so.
