---
status: accepted
---

# The canary is spelled out in one channel, and the record says which

`LLM01` direct prompt injection is the second family of the elective tier and the
first that is defined by its boundary with a family the bench already has. Every
indirect-injection case on disk states that bound in its own `not_tested`, in these
words: it *does not test a direct instruction override in the user's own message*.
This family is the other half of that sentence.

The two halves are one published entry — `LLM01:2026` — and they are two attacks. A
direct override arrives through the channel an agent is *supposed* to take
instructions from; a planted one arrives through content the agent fetched, written
by somebody the agent has no reason to obey. Different channels have different
defences in front of them: an input check that refuses a user's override says nothing
about a note the agent retrieved, and a retrieval filter says nothing about what the
user typed. One denominator over both would report the mean of two defences as though
it were one, which is the arithmetic #42 refuses in as many words.

So the family exists to keep the sentence true, and the whole risk is that the two
blur.

## The problem with the obvious implementation

**A `CANARY_INSTRUCTION_EXECUTED` case whose family happens to be
`direct_prompt_injection`.** No new machinery: the reading is the same string
comparison either way, so the family name is the only thing separating the two. That
makes the boundary a convention rather than a property, and it fails in the direction
nobody checks — a payload written for one family loads happily under the other, and
the first time it happens the two families share a denominator with nothing raising.
It also makes `CANARY_INSTRUCTION_EXECUTED`'s own docstring false, which says the
instruction was planted *in content it fetched*.

The second obvious implementation is a guard keyed on the family. It is nearly right,
and it puts the check in the one place ADR-0004 spent its length keeping criteria out
of: the family is a label a reader recognises, and the criterion is the thing that
decides.

## Decision

**1. The channel an instruction arrived through is a property of the record, and the
two kinds' guards are exact complements.** `SuccessConditionKind` gains
`DIRECT_INSTRUCTION_EXECUTED`, and `PLANTED_BY_THE_BENCH` — the kinds whose verdict
reads a canary the bench planted outside the boundary — splits into
`CARRIED_BY_THE_MESSAGE` and `CARRIED_BY_FETCHED_CONTENT`. One predicate is read over
both: *does this payload spell the canary out, joined or in two pieces?* A direct
case's payload has to, a fetched-content case's payload has to not, and both refuse
the join. **No payload loads under both**, which is what makes "a case cannot satisfy
both families' conditions" a property rather than a claim.

The positive half is the one that matters. It is easy to say what an indirect case's
payload must not carry; saying what a direct case's payload *must* carry is what
stops a case whose canary could have reached the reply through some other channel
from being scored as an override the user sent.

**2. Composition does the same work here that it does for the other two plantings.**
The message spells out a prefix and, separately, a reference; joining them is what
carrying the instruction out *is*. So a target that quotes the override back while
refusing it reproduces both halves and never the join, and a refusal that describes
the attack cannot be scored as one that carried it out. The reference agents
recognise an override by the two halves being asked for, which is why the override
text lives on the **case record** and not in the fixture: an override *is* the
payload, unlike a note, which is content the agent fetches.

**3. There is no precondition, and that is a difference from `ASI06` rather than an
omission.** Memory poisoning needs a later turn and reports
`NotMeasurable.NO_SESSION_RETENTION` against a target without one
([ADR-0041](./0041-the-persistence-canary-is-read-over-two-turns.md)). A direct
override needs only that the target reads the message it is sent, which every target
the bench can register does — registration does not complete without the nonce echo.
So this family is measured against a target with no tool-call visibility and no
session retention, and its figure is a rate rather than a third outcome.

**4. `scanner.family_claimed_by` does not move, and `DeclaredControl` gains no
member.** The issue asks for this decided here rather than in the diff, and the
answer is neither of the two it offers.

The join in `assembler.py` crosses a **declaration** with a **verdict**, and the
verdicts it reads are the scored layer's — which are keyed on the six. A target report
says which elective families the run was not asked for and nothing else about the
tier's figures (ADR-0035, ADR-0018), so a control claiming an elective family would
join against nothing on every run that did not request it and report `untested` for
ever — precisely the failure `family_claimed_by`'s closed match with no fallback
exists to prevent. Widening the function to return a tuple, or adding a fifth member
to the checklist, both arrive at that same place; the second also grows
`CONTROL_CHECKLIST`, which is trigger 6 and prints a new row in every target's scan
section for a control claiming a family those figures are not keyed on.

`DeclaredControl.INPUT_CHECK` therefore keeps claiming `indirect_prompt_injection`
alone. What an operator declares when they claim an input check is a defence on the
message channel *and* on the retrieval channel; what the bench joins it against is the
family in the six. This is the decision #48 made for `MemoryHygiene`, read from the
other end: the reference agents grew a control and the checklist did not.

**5. `published.NOT_REACHED_WITHIN["LLM01:2026"]` does not move, and the case records
do.** The limit reads *the direct half is tested by none of the six families*, which
is exactly true and stays true — it was written by #45 with the tier already
declared, and `NOT_REACHED_WITHIN`'s own docstring says so: *`LLM01`'s limit is the
direct override every indirect-injection case already excludes in its own note …
stating the boundary is what stops the claim from quietly covering the selection.*
The entry does not move to a wider claim either, for the reason #48 gave for `ASI06`:
`claimed_in_part` is derived over the library and printed in **every** report, so a
claim there would widen a coverage statement on runs that were never asked for the
family.

What does move is the *per-case* half of the same disclosure. Each indirect record's
`not_tested` now names the family that holds the bound — *the elective family direct
prompt injection*, run only when a run asks for it and never counted in these figures
— which is the shape #48 gave `ASI06`'s reason, where naming the elective family is
what makes an entry still listed as untested legible rather than stale.

## What a positive reading does not prove

Stated here because a canary's whole worth is the precision of the claim it licenses.

* **Not that the agent's configuration was replaced.** What is shown is that a line
  the message asked for came back. Whether anything else the agent was configured with
  stopped applying is a claim this reading does not reach.
* **Not obedience to a third party.** A target that carries out an override its
  operator typed may still refuse every instruction in a document it fetched. That is
  the other family's denominator and it is measured there.
* **Not that a privileged channel was reached.** The bench sends one message on one
  endpoint. `direct-override-003` writes a system frame *inside* a message; an
  override that genuinely arrives on a system or developer channel is out of reach
  from one endpoint, and the record says so.
* **Not harm.** As with every canary in this bench, what is shown is that an
  instruction ran, never that running it cost anybody anything.

## What this gives up

**The two families' hardened zeros are attributable to the same removable piece, and
against these three agents their figures move together.** `controls.InputCheck` is
run twice in the hardened agent — once by `before_model` on the user's message and
once by `before_content` on what a tool brought back — so removing it flips both
families, and neither reading is evidence about the other's defence being separate.
That is a true fact about the *test equipment* rather than about the families: a
small agent really does have one deny-list in front of two channels, and a report
about a real target joins a declared input check against the family in the six.

What it costs is that the reference agents cannot exhibit a target that defends one
channel and not the other, so nothing here demonstrates the independence the family
boundary is argued from. What it does **not** cost is the boundary itself, which is
carried by the channel, the record and the denominator: no payload loads under both
kinds, the two channels' canaries are disjoint, and neither channel produces the
other's line. Splitting `InputCheck` into two named pieces would buy the
demonstration and is refused below.

**The gradient is code, so the separation is as constructed as the agents are.** The
same limit `corpus.py`, `tools.py` and `memory.py` already state: the stub models are
deterministic text and will not obey an override on demand, and the bench measures
architecture rather than a model's temperament. What a run on the field would add is
whether a *model* under those agents changes the answer, and no gate run has been
made (`docs/validation.md`).

## Considered and refused

**A guard keyed on `case.family` rather than on the success-condition kind.** It
reads the family to decide a criterion, which is the inference spec story 18 and
ADR-0004 refuse: the verdict class and the criterion are read off the record, and the
family is a label. Keying on the kind also keeps one dispatch vocabulary — the same
sets `SuccessCondition.__post_init__` already reads.

**Splitting `controls.InputCheck` into a message check and a content check.** It
would make each family's hardened zero attributable to a piece of its own, which is
the demonstration the section above says is missing. Refused for now on ADR-0035's
discipline: the tier must not perturb the six, and this would change the hardened
agent's declared architecture, `ALL_CONTROLS`, and the attribution every existing
indirect-injection test is written against — a change to the equipment the six are
calibrated on, made for an elective family, before a single gate run has read either.
It is the right change to make with a gate run behind it and it is named here so the
next ticket that wants it has the argument rather than the idea.

**A `direct` flag on `SuccessCondition` beside the canary.** A flag says a case is
special and leaves the channel to be worked out somewhere; the kind is what every
reader already dispatches on, and the record has to be re-derivable by a reader
holding it and the transcript (ADR-0004).

**Naming the family `prompt_injection` and treating the existing one as its indirect
case.** It would make `LLM01` one denominator, which is the thing the bound was
written to prevent, and it would retire a family in the six to accommodate an
elective one — a library-version event with an ADR of its own, arrived at sideways.

**Case ids of the form `direct-injection-001`.** `"direct-injection-001"` is a
substring of `"indirect-injection-001"`, so any containment check over case ids would
resolve one family's record into the other's. The ids are `direct-override-00N`, and
the same care is taken with the canaries: the two channels' values are asserted
disjoint by set intersection and never by containment. This is the third form of the
trap `library.family_named` already documents and `test_elective.py` already asserts.

Cross-references: [ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md)
(the tier, and the type that keeps it out of a decision),
[ADR-0041](./0041-the-persistence-canary-is-read-over-two-turns.md) (the tier's first
family, and the same boundary against the same neighbour),
[ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md) (the criterion is on
the record), [ADR-0037](./0037-a-claimed-category-is-claimed-in-part.md) (a claim
costs a stated limit), [ADR-0039](./0039-a-familys-label-is-one-record.md) (`LLM01`
claimed by two families, and why `ClaimedInPart.families` is a tuple),
[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) (a `D`
is a fact about the bench), [ADR-0005](./0005-no-composite-risk-score.md) (nothing the scan
reads reaches a number), #42 (the selection), #49 (this family), #50 (the next one).
