---
status: accepted
---

# The Agents Rule of Two is a declared property, and its reading is a name

The Agents Rule of Two says an agent should not, within one session and without human
supervision, hold more than two of — **A** processes untrusted input, **B** reaches
private data or sensitive systems, **C** changes state or communicates outward.

#42 selected it beside three families and it is the one row of that table that is not
a family. Nothing is sent to establish it. It is read entirely off what the operator
**declares**, which is the configuration scan's boundary exactly: `scanner.py` says
*the scan reads declarations and sends nothing … a scan that probed an endpoint would
be a measurement wearing a declaration's name.* So it lands in the scan, and this ADR
is about what has to be true of the code for that sentence to stay true once the scan
reports something a reader could mistake for a finding.

## Decision

1. **Four declared fields on `TargetConfig`, tri-state, defaulting to unstated.**
   `processes_untrusted_input`, `reaches_private_data`,
   `changes_state_or_communicates` and `under_human_supervision` are each
   `bool | None`, defaulting to `None`. `None` is *nobody said*, and it is the
   conservative default in the direction that matters here: `False` would put in an
   operator's mouth a claim they did not make, and it is the **profitable** claim —
   three capabilities declared away is a target reported as sitting inside a published
   rule that nothing ever read it against. This is
   [ADR-0005](./0005-no-composite-risk-score.md)'s defect arriving from the other
   side. Its rejected score was gameable by declaring **more**; this one would be
   gameable by declaring **less**, and the answer is the same answer: the reading is a
   name, and no rate, band or `D` is a function of it.
2. **Declared and never inferred.** A, B and C are close to derivable from
   `declared_tools`, and they are not derived: a capability read off a tool name is a
   measurement wearing a declaration's name in the other direction, and a
   contradiction check between the two would be that same inference wearing a
   validator's clothes. No combination of the four is refused.
3. **The three properties are a second closed enumeration, disjoint from `Family`.**
   `contract.AgentCapability` has three members and there is deliberately **no**
   `family_claimed_by` beside it. Each of the three has a family that is its
   near-neighbour — untrusted input beside indirect prompt injection, private data
   beside data leakage, outward action beside scope creep — and a mapping to one would
   let the standing be read off verdicts. That is the alternative #42 refused once so
   it would not be re-argued: built as a family, the rule would have to establish A, B
   and C by attack, which is three families the bench already has, joined, and a view
   over existing measurements presented as a new one. The type is what refuses it, on
   the mechanism [ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md)
   used for the elective tier and
   [ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) one
   level up.
4. **The reading is a name, never a figure.** `scanner.RuleOfTwoStanding` is a
   `StrEnum` with no ordinal and no *pass* or *fail*, on the reasoning ADR-0005 gives
   for `Band`. `scanner.RuleOfTwo` holds three tuples of capability names, a
   supervision name and one derived `standing`, and **no number of any kind**: not a
   rate, not an interval, not a `D`, and — the one this record is a line away from —
   **not a count of the held capabilities**, which two targets could be lined up
   under and ranked. Even the derivation counts nothing: every arm of `standing` tests
   a tuple for emptiness.
5. **Five standings, because absence has more than one meaning.** `not_declared`,
   `partly_declared`, `at_most_two`, `three_under_supervision`, `three_unsupervised`.
   The supervision declaration is part of the record and not an afterthought, because
   an **unsupervised** third property is what makes the shape the one the rule warns
   about: an agent holding all three under human confirmation is not that shape, and
   a scan that read A, B and C without the fourth declaration would report one.
   **Every arm has to be a true sentence**, which decides one ordering: a property
   the operator declares their agent does *not* have is one it cannot hold, so a
   non-empty `not_held` settles the reading at *at most two* whatever went unsaid,
   and `partly_declared` is the reading only where nothing is declared absent and
   something is missing. The alternative printed *the rule cannot be read over this*
   about a declaration it could.
6. **`not_declared` is not a sixth kind of nothing.** It is the same absence a
   control the checklist asks about and the operator did not claim already is —
   nothing was attempted, nobody could not answer, no figure is missing because none
   was ever due. `payload.py`'s five absences (ADR-0035) stay five.
7. **It prints beside the declared controls, and never as a finding.** The record sits
   on `DeclaredSection` — the section that shares no arithmetic with any other — as a
   field of its own and not among the `controls`, so `defeated` cannot select it and
   it has no `broken_by` to carry. It serialises under `declared.rule_of_two` as
   strings and lists of strings only, and it renders in Annex IV section 3 under its
   own heading, with the published rule stated above the line that reads this target
   against it. Every arm of the sentence says that nothing was sent.
8. **The block prints whether or not anything was declared.** A heading that appeared
   only when an operator answered would be indistinguishable from a document made
   before the scan asked — the reasoning ADR-0035 gives for a target report carrying
   the elective request it never made.

## Why not a family

Stated here once so the alternative is refused rather than re-argued.

A family is measured: it has cases with payloads, success conditions, ten attempts
per case, a rate with a Wilson interval, and a `D` the gate reads across three
reference agents. To build the Rule of Two that way, the bench would have to
establish A, B and C **by attack** — and it already attacks all three neighbourhoods.
What it would produce is not a fourth measurement but an arithmetic over three
existing ones, keyed on a rule that is about the agent's *architecture* rather than
about whether a defence held. The conjunction is not even the thing the rule states:
an agent that fails all three families is one whose defences did not hold, which is
what the report already says, and an agent that holds all three properties and
defends every one of them is exactly the shape the rule warns about while measuring
clean. The rule and the six families answer different questions, and joining them
would answer neither.

`GateRule.family_count` therefore does not move, no threshold in `rule.py` moves, and
the gate prints the same six.

## Why the type and not a flag

The shape a reviewer reaches for is a `bool` on the scan — `rule_of_two_violated` —
or the three properties typed as `Family` so the existing join can carry them. Both
put the invariant in the hands of every call site.

A boolean is worse here than it looks, because the interesting reading is not binary:
a target that declared nothing, one that declared two of four, one holding all three
under supervision and one holding all three without it are four different facts, and
a boolean answers for all four the same way — with the one answer that is wrong for
three of them. It is also the shape that gets counted: two booleans over two targets
is a comparison, and a comparison over self-report is the composite score ADR-0005
refused.

Typing A, B and C as `Family` is the sharper mistake. It would make
`declared_and_defeated` able to accept them, and a `ScannedControl`-shaped Rule of
Two would join a declaration against a **verdict** — at which point the standing is a
function of measured attempts, the headline finding grows a row nobody can re-derive
from a case record, and a declaration has become a measurement without a single byte
crossing the wire. So the two enumerations share no member and no function, and the
scanner imports nothing that carries a figure: not `scorer`, not `evaluator`, not
`runstate`, not `assembler`, not `gate`. The import guard the module already had
against a *transport* has a second half now, against a *measurement*, because a
module that cannot send a message can still read one.

## What the scan cannot do

- **It cannot check the declaration.** Everything in the block is the operator's own
  statement about their agent's architecture, and the bench sends nothing that would
  contradict it. A target that under-declares gets *at most two* printed, and nothing
  downstream disagrees. What that buys is nothing: the standing carries no figure, so
  there is no number for the under-declaration to move, and the report says in the
  block itself that this is a declaration.
- **It cannot fail.** `scan()` refuses no combination of the four fields, for the
  reason in decision 2. `RuleOfTwo` does refuse a record whose three sides do not
  partition the rule's three properties exactly once — that is a hand-built record
  claiming a capability is held and unstated at once, which would be a standing read
  over a rule with a different number of properties in it, and it is the guard
  `ScannedControl` already has against a defeat that names no case.
- **It cannot say when.** *Within one session* is in the rule's own wording, and the
  declaration is a property of the target rather than of a session. Nothing here
  measures a session, and the block does not claim to.

## Considered options

**A count of held capabilities in the record or the payload — *two of three*.**
Rejected. It is the one figure this block is a line away from, it ranks two targets
the moment two reports are on one desk, and it is a composite score over self-report,
which is ADR-0005's second defect with the sign flipped. The capabilities are named
instead, so a reader who wants the count does the arithmetic themselves and owns it.

**A boolean `violates_the_rule_of_two`.** Rejected: see above. Four facts, one
answer.

**Defaulting the three capability fields to `False`.** Rejected. It reads as a
declaration the operator did not make, and it is the profitable one.

**Defaulting them to `True`.** Rejected for the same reason with the sign flipped: it
would print a shape the operator never described, in a document that leaves the
building.

**Reporting a partial declaration as *partly declared* even where the answer is
forced.** Rejected, and it was the first draft: reading `unstated` before `not_held`
made a target declaring one property absent and leaving another unsaid print *partly
declared — the rule cannot be read over what it stated*, about a declaration the rule
can be read over. A standing whose sentence is false in a corner is worse than a
standing that is coarse, so the deduction that costs nothing — one property absent
means three cannot be held — is made, and the one that would require reading across
the supervision answer is not. A target that declares only that a human confirms is
`partly_declared`: supervision alone says nothing about what it holds, and treating
one checkbox as a benign standing is the direction this ADR spends its argument
refusing.

**A `Finding` or a `CoverageGap` for `three_unsupervised`.** Rejected on what those
words mean here. A **finding** is a verdict plus its narrative, produced by the
scored layer; there is no verdict, no attempt and no case id behind this. A
**coverage gap** is a published category the bench does not test; this is not a
category the bench fails to test but a property of the target's declared shape.

**An `Article` beside it.** Not decided here. #42's table maps the Rule of Two to
Article 14, and `judge.article_for` is keyed on `Family` — which the Rule of Two is
not, by this ADR. Pairing a label with something that is not a family is #45's
design, and this block prints no article until it exists.

## Consequences

- `TargetConfig` gains four fields, all defaulting to unstated, so every existing
  registration reads as `not_declared` and every existing report gains one block
  saying so.
- The golden rendering digest moves once, on purpose, in the diff that added the
  section-3 block.
- Nothing in the API's `TargetRequest` accepts these fields yet, exactly as nothing
  in it accepts `declared_controls`. The scan reads a `TargetConfig`, and how an
  operator fills one over HTTP is the registration surface's question rather than
  this one's.
- `docs/validation.md` records, in *what has never been validated*, that no real
  operator has ever declared any of this and that the bench cannot check what one
  would say.
- CONTEXT.md gains **declared capability**, kept apart from **declared control** by
  the same discipline that keeps **probe** apart from **case**: one is a defence
  claimed, the other is something the agent can do, and the report prints them in one
  section.
