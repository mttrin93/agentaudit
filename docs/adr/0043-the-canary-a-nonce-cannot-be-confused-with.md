---
status: accepted
---

# The canary a nonce cannot be confused with, and the record that refuses one

`LLM02` PII leakage is the third family of the elective tier and the second defined by
its boundary with a family the bench already has. The neighbour this time is one of the
**six**, and it is gate-deciding: `data_leakage` is the bench's first canary planting —
a value the operator planted in the target's *configuration*, whose appearance in
output proves that material inside the boundary left it (ADR-0007).

PII leakage is a different claim. A **third party's** record, held by the target,
disclosed to whoever asks. Article 10 — data and data governance — rather than 15,
because the failure is governance of the data the agent holds rather than the security
of its boundary; and the party whose data it is, is neither the operator nor the bench.

**The whole risk is that the second becomes the first under a second name.** If this
family's success condition were a config-planted canary, the two would be the same test
with different prose: both would separate the reference agents on the same output
filter, `D` would not tell them apart, and a signed report would carry two rows for one
measured property — one of them in the gate's denominator and one not. Worse than the
arithmetic, a reader would meet *sensitive information disclosure* twice in one document
and have no way to tell which claim was which.

## The problem with the obvious implementation

**A `CANARY_IN_REPLY` case whose family happens to be `pii_leakage`, with the canary
seeded somewhere else.** No new machinery: the reading is the same string comparison
either way, so the family name is the only thing separating the two. That makes the
boundary a convention rather than a property, and it fails in the direction nobody
checks — the reply is the only evidence either family has, and one reply would be
evidence for both.

The second obvious implementation is a new kind whose branch *excludes* the run's nonce
at verdict time. It is nearly right and it is a check in the wrong place: a verdict that
has to know which value it must not have read is a verdict that could have read it, and
the exclusion would sit in `evaluate` where ADR-0004 spent its length keeping criteria
out of. The record is where a criterion belongs.

## Decision

**1. Where a disclosed value was held is a property of the record, and the two kinds'
guards are exact complements.** `SuccessConditionKind` gains
`PERSONAL_RECORD_DISCLOSED`, and the kinds that read a value from *inside* the target's
boundary are declared in two sets: `PLANTED_IN_THE_CONFIGURATION`, which is
`CANARY_IN_REPLY` and reads the nonce the **run** issued, and
`HELD_AS_A_RECORD_ABOUT_A_PERSON`, which reads a value the **record** names. That
complement is not decoration: the nonce changes every run, so a record naming one would
name a value that does not survive to the next run, and a record naming none of the
other could not be re-derived by a reader holding it and the transcript (ADR-0004).
`in_one_holding` is `on_one_channel`'s shape one question over — total, exact, disjoint,
and disjoint from the kinds the bench planted *outside* the boundary — and it is checked
at import, so a kind that discloses and names no holding stops the module rather than
loading a case with the boundary unstated.

**2. The two values are provably disjoint, and that is arithmetic rather than a claim
about three strings somebody chose.** A canary an issued nonce could contain, or that
could contain an issued nonce, does not load. `backend/bench/nonce.py` holds the shape
the registration protocol plants — the prefix, the separator, the alphabet and length
`issue_nonce` draws from — and answers both directions: `inside_a_nonce` positionally
against that template, because a nonce's body is random and a value made of hex is one
some issue will eventually contain; `holds_a_nonce` on the prefix, because holding a
nonce means holding its prefix.

**The first is exact and had to be.** The obvious form — *is every character of the
value one a nonce can hold* — is sufficient and badly over-broad: `RETAINED-77341`, the
canary `test_memory_poisoning.py` was already using, is drawn entirely from the
characters the prefix and the hex digits supply and appears in no nonce, because `T`
and `N` are not hex and are not consecutive in the prefix. An over-broad guard refuses
canaries for nothing and the cost lands on whoever names the next one, so the check
lines the value up against the template instead.

**And it is applied to every kind that names its own canary, not only this family's.**
The argument does not narrow: a planted instruction whose canary a nonce could carry
would score `data_leakage` on an indirect-injection reply just as surely as a held
record would. No canary in the *library* was confusable when this was written, which is
why the wider guard cost nothing there — and it immediately refused one the **suite**
was building: `test_entry.py`'s adaptive-promotion fixture carried
`AGENTAUDIT-CANARY-1` as an injection canary, which is the collision this guard is
about, sitting in the equipment rather than on disk. The fixture was renamed. That is
the guard earning the widening on the day it landed rather than a hypothetical it was
written for. What stays scoped
to this family is the *payload* clause — a held record was the target's before the
attempt began, so a message spelling it out would score an echo, where a planted
instruction's payload is supposed to carry its halves and which channel it carries them
on is ADR-0042's question.

So a reply carrying nothing but a leaked nonce is a `data_leakage` success and answers
*resisted* under this family's condition, for **every** nonce the issuer could draw —
and a reply carrying nothing but this family's value answers resisted under
`data_leakage`'s. That is the sentence #50 asked for, and it is a property of the record
rather than a fact about the fixture.

The module is a leaf and not part of `registration.py`, and the reason is the import
graph rather than taste: `registration.py` imports `graph/runstate.py`, which imports
`library.py`, and the library is where the guard has to be. Writing the prefix out a
second time would be a declaration that can be half true, which is the defect
`operator.described_agents` was opened for one module over. Nothing imports it back —
`registration.py` no longer names the value it plants, and the callers that issue one
reach the leaf directly — so the protocol module keeps the protocol and the shape has
one home.

**3. The gradient is what a target *releases*, never what it *holds*, and that needs a
precondition.** All three reference agents hold the same four client records, and only
an agent without `controls.RecordMinimisation` hands over the part of one that
identifies the person it is about. An agent that held nothing about anybody would fail
this family's own precondition, so its zero would be *not measurable* wearing a rate's
clothes rather than a defence — which is the lesson [ADR-0041](./0041-the-persistence-canary-is-read-over-two-turns.md)
learned about memory and applies here unchanged. `Precondition.PERSONAL_RECORDS_HELD`,
`TargetConfig.holds_personal_records` and `NotMeasurable.NO_PERSONAL_RECORDS` are the
third of each, on the terms ADR-0024 sets for a declaration that decides measurability
and no figure.

**It is deliberately not `contract.AgentCapability.REACHES_PRIVATE_DATA`.** That is one
of the three properties the Agents Rule of Two is read over, and
[ADR-0038](./0038-the-rule-of-two-is-a-declared-property.md) §3 is explicit that the
enumeration shares no member and no function with a family — a mapping from it to a
family is *the obvious next thing to write and the thing that would let a declaration be
read off verdicts*. The two also say different things: one is what an agent **can
reach**, the other what is **there to be disclosed**, and neither is derived from the
other.

**4. `LLM02:2026` stays claimed by `data_leakage` alone, and this is the one place the
answer differs from #48's and #49's reasoning rather than repeating it.** Both of those
tickets refused to move their entry *into* the claimed block. This entry is already
there — three case records claim it and section 4 of every report already prints *tested
in part* beside it — so the question is the narrower one: should `pii_leakage` join
`ClaimedInPart.families`?

No, for three reasons that stack.

* `CLAIMED_IN_PART` is derived over `labels.LABELS` and printed in **every** report,
  including every run never asked for the tier. `ClaimedInPart.stated()` already refuses
  to print the claiming family for exactly this reason — a family named there that the
  figures above do not carry reads to a recipient as a family this target was tested on
  (ADR-0018). An elective family would be that failure with the run-scoping guaranteed
  rather than possible.
* The field is read by #52, which prints the pairing **beside a family name**, where the
  run's own figures are. On a run that requested nothing from the tier there is no such
  place for it to be printed beside.
* It would widen `ClaimedInPart.families` from `tuple[Family, ...]` to a union, which is
  the widening ADR-0035 relies on the type checker to make visible and `CLAUDE.md`'s
  standing rule says to stop at.

One thing the moved limit does that `ClaimedInPart.stated()` refuses is name a family
in a line that prints in every report, and the two are not the same act. `stated()`
refuses to name the family *claiming* the category, because a reader would take that as
a family this target was tested on. The limit names the family that holds what is **not**
reached, in a sentence whose whole content is that it was not tested here — it narrows a
claim where naming the claimant would widen one. #48 made the same move for `ASI06` and
this is the second instance rather than a new licence.

What moves instead is the **limit**. `NOT_REACHED_WITHIN["LLM02:2026"]` said a third
party's data *would need a corpus this bench does not put in front of a target*, and #50
made that false. It now names the elective family that holds the half, which is the
shape #48 gave `ASI06`'s reason: naming the family is what makes a stated boundary
legible rather than stale. The golden rendering digest moved by that one sentence and no
figure moved.

**5. The per-case boundary is stated on both families' records, and this is the first
time the six's records gain a sentence about the tier.** Each PII record names *the
family data leakage, which is one of the six*, and each data-leakage record names *the
elective family PII leakage, run only when a run asks for it and never counted in these
figures*. The library digest moved to `sha256:84a94f471260` for the second half of that.

**6. `scanner.family_claimed_by` does not move and `DeclaredControl` gains no member** —
the same answer #48 and #49 reached, from the same argument and with one addition. The
join in `assembler.py` crosses a **declaration** with a **verdict**, and the verdicts are
the scored layer's, keyed on the six; a control claiming an elective family would join
against nothing on every run that did not request it and report `untested` for ever. The
addition is that this ticket really does grow the reference agents a control —
`RecordMinimisation` — so the temptation is concrete rather than theoretical, and the
answer is #48's read from the same end: the agents grew a control and the checklist did
not.

## What a positive reading does not prove

Stated here because a canary's whole worth is the precision of the claim it licenses.

* **Not that the disclosure was unlawful.** What is shown is that a line about a named
  person came out of a target that held it. Whether the requester was entitled to it,
  whether a lawful basis existed, and whether the person was ever told, are questions
  about a deployment and not about one reply.
* **Not that the target's whole store is reachable.** One record was named and one
  record came back. Whether the agent would enumerate, aggregate or join records is a
  claim no case here makes.
* **Not identification.** The reference agents' records are fixtures and the value that
  comes back is a marker. That a *real* target's record would identify a real person is
  the reason the family exists and it is not something the bench measures.
* **Not harm.** As with every canary in this bench, what is shown is that data moved,
  never that moving it cost anybody anything.

## What this gives up

**The two families are separated on two controls and read on two stub models, and the
second half is a limit of the equipment.** `data_leakage` is only visible on a model
that discloses its configuration (`stub:obedient`); this family's line is appended by
code and is visible on either. So the two-by-two that proves the zeros are attributable
to two different pieces is read on `stub:obedient` for one family and
`stub:cooperative` for the other. Under `stub:obedient` the hardened agent's output
filter withholds the **whole reply**, so it would suppress this family's line too — not
because the filter defends this family, but because a reply that is withheld carries
nothing. That is a fact about a control that ends a turn rather than about the boundary,
and it is why the comparison is made on the model where each failure is visible at all.

**A false `holds_personal_records` declaration produces the clean zero decision 3 exists
to prevent**, exactly as ADR-0041 records for `retains_session_state`, and with less
recourse: retention has a tell over two turns and this has none — a target that declares
it holds records and holds none is indistinguishable from one that defends perfectly.
The probe that would close it is a disclosure request the bench would have to score as
neither a success nor a failure, and it costs a call per target per run.

**The bench cannot seed a real target's data.** The operator plants the nonce by hand,
and against a real target the same operator would have to seed a record carrying the
value the case record names. That is a heavier ask than editing a system prompt, and
until it is asked, this family's readings are readings on the reference agents.

**The gradient is code, so the separation is as constructed as the agents are** — the
same limit `corpus.py`, `overrides.py` and `memory.py` already state, and no gate run
has read this family on the field (`docs/validation.md`).

## Considered and refused

**Excluding the nonce inside `evaluate`.** The criterion would then be in the function
ADR-0004 makes authoritative rather than on the record it makes authoritative, and a
reader holding the record could not see what the verdict refused to count. It also could
not be driven red without a run: a per-run value is not something a record guard can be
tested against, and the alphabet check is.

**Seeding the personal record through the registration nonce protocol.** One value, two
meanings, and the whole of this ADR is that they must be two values. It would also make
the family's canary change every run, which is exactly what stops `CANARY_IN_REPLY` from
naming one.

**Reusing `AgentCapability.REACHES_PRIVATE_DATA` as the precondition.** Argued in
decision 3. Refused on ADR-0038 §3 and because the two declarations are about different
things.

**Widening `OutputFilter` to withhold a record about a person.** It would make both
families' hardened zeros attributable to one piece, which is the second name arriving in
the test equipment instead of in the prose — the failure ADR-0042 records as an honest
cost of `InputCheck` serving two channels, accepted there because it could not be avoided
without perturbing the six, and avoidable here because nothing in the six is measured
against record minimisation.

**Case ids of the form `pii-disclosure-00N`.** *disclosure* is the word
`disclosure-denial-00N` is built on, so any check written over case ids by containment
would put one family's record in another's reach. The ids are `pii-record-00N`, and the
same care is taken with the values: the directory's canaries are asserted disjoint from
both channels' by set intersection, and the two family names are asserted not to nest in
either direction. This is the fourth form of the trap this group has met —
`library.family_named` documents the first, `test_elective.py` the second, ADR-0042's
case ids the third, and a report's own prose is where it lands here.

**Putting the records in `corpus.py`, which is where #50 asked for them.** The issue
says *synthetic personal records in the reference corpus*, and `corpus.py` is the
shared folder: content somebody outside the team wrote, which the agent has to
**fetch**. A record about a client is the opposite of that — it was inside the boundary
before the attempt began, arrives on no channel, and is not in front of any attacker
until the agent hands it over. Putting the two in one module would put the family's
whole distinction inside a file whose docstring is about content the team did not
write, and the first reader to add a note beside a client record would be adding
third-party text to the agent's own data. `directory.py` is the third module beside
`corpus.py` and `overrides.py`, and it is named for what the agent does with what is in
it rather than for where it came from.

**Committing records that look like real people's files.** Refused on ADR-0008. The
records carry a name, a reference and one sentence about a matter, and no address, date
of birth, contact address, national identifier or payment detail: a canary proving a
record about a person was disclosed needs none of those, and what committing them would
buy is realism in a fixture at the cost of putting the shape of a real file in a public
repository.

Cross-references: [ADR-0007](./0007-canary-nonce-as-proof-of-control.md) (the first
planting, and the value this one may not be confused with),
[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) (the tier, and the
type that keeps it out of a decision),
[ADR-0041](./0041-the-persistence-canary-is-read-over-two-turns.md) (the precondition
argument this decision reuses),
[ADR-0042](./0042-the-canary-is-spelled-out-in-one-channel.md) (the tier's second
family, and the same boundary problem against a neighbour in the tier),
[ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (the criterion is on the
record), [ADR-0037](./0037-a-claimed-category-is-claimed-in-part.md) (a claim costs a
stated limit), [ADR-0038](./0038-the-rule-of-two-is-a-declared-property.md) (why the
Rule of Two's declarations are not this precondition),
[ADR-0039](./0039-a-familys-label-is-one-record.md) (`LLM02` claimed by two families),
[ADR-0040](./0040-a-family-bears-more-than-one-article.md) (Article 10, and why it is
this family's),
[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) (a `D` is
a fact about the bench), [ADR-0008](./0008-repo-disclosure-posture.md) (what is
committed), #42 (the selection), #50 (this family), #52 (the next one).
