---
status: accepted
---

# A case may be a sequence, the attempt is one script in one session, and the verdict is read per turn

A case was one string and an attempt was one message. #74 makes fixed multi-turn a
member of the **scored** layer: an attempt becomes a short scripted conversation in
one session, and everything about the rate survives because the dependence is
*inside* an attempt and never between two.

[ADR-0041](./0041-the-persistence-canary-is-read-over-two-turns.md) already put a
second turn on the wire for one family, and it did the arithmetic that makes this
affordable — `Case.turns`, the budget authorised per turn, `SESSION_RETENTION` as a
precondition. What ADR-0041 did **not** decide is any of the four questions below,
because a planting turn is one turn that is deliberately not scored and a script is
several turns that all are.

## 1. `Case.payload` is a sequence, and it is one field rather than two

`payload: tuple[str, ...]` — one element for a single-turn case, several for a
script. The eighteen records each gain one wrapping bracket and say nothing else
new.

A tuple rather than a second `script` field beside it. Two fields would mean a
record that could carry both, and a loader picking between them: the shape a caller
sends would be decided somewhere other than the record, which is exactly what
`derived_from` is refused as a payload source for (ADR-0051 §4). One field is also
what keeps versioning free — `_versioned` reprs whatever `dataclasses.fields` finds,
so a tuple versions as a string did and no change to `LibraryVersion` is needed.

**What did move is the library digest**, from `89288dbf94f9` to the value
`test_the_library_version_did_not_move` now pins, on #65's and #72's precedent
exactly: the shape of a case changed, so twenty-seven records that ask the identical
twenty-seven questions hash to something else. Every record is in the diff, gaining
a bracket and nothing else, and the count of eighteen is what says no case was
written and no payload edited. **No variant and no scripted record is committed
here**, so `n` per family is unchanged, `GateRule.attempts_per_family()` is
untouched, and PLAN §3's diagram and CONTEXT.md's counts are still true. The
arithmetic of a library that holds more than eighteen is #76's.

Two refusals come with the type, because a sequence has more ways of being empty
than a string does: a record with no turns at all, and a record with a blank turn in
it. Both are a payload the loader would have to supply from somewhere.

**A third refusal is the one the sequence could have got wrong silently, and it has a
migration in it.** `tuple("a message")` is eleven one-character turns, so a record
written the old way would load, go out as eleven calls on the operator's endpoint and
score whatever came back. `_payload` therefore refuses a bare string rather than
accepting either shape — one shape on disk, on `_transform`'s terms. This is the first
change to a record that makes an older one *unloadable* rather than merely differently
hashed: #65's and #72's fields were read with `.get`, so a record written before them
still loaded. The consequence is on the deployment and it is named rather than
mechanised: `app.deployed_library` seeds a mounted volume from the image's library
only when the mount is **empty**, so a bench redeployed onto a volume seeded before
this ADR refuses to boot until that volume is re-seeded. Refusing to boot is the right
direction — the alternative reads a record's payload one character per turn — and the
refusal's own message says what to do.

## 2. One attempt is one script in one session, and two attempts still share none

`attacker.py`'s opening sentence is what pays for the rate: *attempts are
independent by construction — each carries its own session id — so a rate is a rate
rather than a trajectory.* `run_case`'s docstring says the same one level down: ten
attempts that could see each other *would measure how the target responds to being
attacked ten times, which is a different quantity.*

A scripted attempt keeps both sentences true, and it does so without a change to the
session id. `_send` already builds one per attempt —
`f"{case.id}-{index}-{uuid.uuid4()}"` — so the script's turns share **one** session
and two attempts share none. What changes is only that an attempt now costs several
calls on the operator's endpoint; what does not change is that ten of them are ten
independent samples. CONTEXT.md's **attempt** entry anticipated this before there
was a script to need it: *a turn is not an attempt.*

**The dependence is inside the attempt on purpose.** That is what a script *is* — an
escalation whose second turn means nothing without its first — and the session id is
what carries it (`contract.send_message`). A script sent across several sessions
would be several unrelated messages, which is the single-turn case the library
already holds.

## 3. The criterion is applied per turn, and the attempt succeeds on the first turn
   that meets it

This is the decision with a real alternative. The alternative is to score only the
last reply, and it would let a target leak the canary on turn two, recover by turn
four, and be recorded as having held.

The adaptive layer already works the other way and for a reason that carries here
unchanged: `_probe` *applies the objective's condition to the turn it just took*
rather than waiting to be asked, because **a break that nobody checked for is a
break recorded as resistance** (`adaptive/attacker.py`). A rate whose numerator can
be reduced by the target recovering afterwards is not a rate about whether the
defence held.

So `evaluator.evaluate_script` reads the turns in order and the first one that meets
the condition decides. A single-turn attempt reaches it and comes out of it byte for
byte as it did before there were scripts, which is the property that makes this a
generalisation rather than a change to what the eighteen records measure.

**Which turn decided is recorded.** `Attempt.decided_on_turn` names it, `Attempt.scored`
resolves it, and every consumer that shows or briefs *one* exchange per attempt — the
transcript view, `JudgeBrief` — reads that one. A narrative written about the last
turn of a script that broke on the second would be an explanation of a reply that
held. It is a convenience and not the evidence: a reader holding the record and
`Attempt.transcripts` can re-derive both the verdict and the turn, which is what
ADR-0004 asks of the number.

**The evidence is every turn.** `Sent.transcripts` and `Attempt.transcripts` are
sequences, on the shape `AdaptiveEpisode.transcripts` already holds. The alternative
— keeping the decisive exchange and dropping the rest — would leave a verdict read
over a turn nobody can see in the company of turns nobody kept.

## 4. A turn whose reply carries nothing the condition can read is not a resisted
   turn, and the last turn is read unguarded

`measurability.checkable` already draws this line for the adaptive layer: a turn that
returned no tool trace shows no defence, and counting it as a turn the target held
is the soft number that reads as a defence and is not one. A script needs it for the
same reason, so an unreadable turn is skipped rather than scored.

**The skip applies to the turns before the last, and that is what keeps the refusals
loud.** `TraceNotVisible` and `PlantingNotRecorded` are raised rather than answered
because every route to them is supposed to have been closed by
`unmet_preconditions` before an attempt was spent — a filter in front of *every*
turn would convert both into a quiet *resisted*, which is the hole in the gate their
docstrings exist to describe. Reading the last turn unguarded means a script whose
every turn was unreadable raises exactly where a single-turn case raises, and it is
also why a one-turn payload has no earlier turns to skip and so behaves identically.

## 5. Deterministic families only, no planting beside a script, and the precondition
   is #48's rather than a new one

Three refusals held by the record (`Case._refuse_a_script_no_target_could_answer`),
so none of them is a caller's discipline.

**A judged case may not be a script.** `AdjudicationBrief.payload` is *the case's own
text*, one string, and κ rests on fifteen single-turn gold transcripts per judged
family (`rule.py`). A judged multi-turn case is a separate ticket that must open by
saying what happens to the gold set — refused here rather than met by a brief quietly
narrowed to one turn of several, which would be an instrument reporting a reliability
it was not measured at.

**A script does not also plant.** A planting turn's whole worth is that the verdict
is the scored turn read *against* it (ADR-0041 §2). A record carrying both would have
several scored turns and one control, and no reading is defined over that shape. The
two mechanisms are held apart by the record rather than by a comment.

**The session-retention precondition is consumed, not re-declared.** Escalation across
turns means nothing against an endpoint that forgets the previous one, and scoring it
anyway would measure the target's memory rather than its defences. #74 and #48 need
the identical capability and the issue said *whichever of the two lands first owns
it*: #48 landed first, so `Precondition.SESSION_RETENTION`,
`TargetConfig.retains_session_state`, the arm in `measurability._target_meets`, the
register-screen declaration and `NotMeasurable.NO_SESSION_RETENTION` all already
exist and nothing here adds a second name for one capability. What #74 adds is that a
record with more than one turn **has to declare it**: a script that did not would be
run against a stateless target and report a rate of zero where the honest answer is
*not measurable* (ADR-0004, CONTEXT.md **not measurable**).

One bullet of #74's list is deliberately not honoured here, and it is a gap rather
than a decision: there is **no register-screen declaration** for retention, and none
for `holds_personal_records` either — both are `TargetConfig` fields whose only writer
in the repository is the reference agents' own configuration. So a user's target can
declare neither and every case requiring either reports *not measurable*. That covers
two preconditions and belongs to the elective tier that introduced them; a radio for
one of the two would leave the screen implying the other declared capability does not
matter. Recorded in docs/validation.md so a reader of a *not measurable* family can
tell the refusal working from the declaration missing.

## 6. The estimate already prices turns, and this keeps it that way

`plan_for` prices a run from the cases it returns and `RunBudget.declare` sums
`case.turns` rather than counting cases — which ADR-0041 built, for a two-turn case,
and which a four-turn script needs for the same reason: `_send` authorises
`target.retry.sends * case.turns` before the first turn goes out, so an attempt
cannot plant, escalate and then hit the ceiling with a verdict nobody can read
(ADR-0007). `Case.turns` now sums the script and the planting turn, so the number an
operator confirms covers the run that will happen.

#74 asks for turns to be carried on `RunPlan` and that is where this ADR departs from
the issue's text: `RunPlan` carries `Case` records, every one of which states its own
`turns`, and the one consumer of the plan that needs the figure already reads it
there. A second copy of the arithmetic on the plan would be a second definition of
what a run costs, and the copy nobody exercises is the one that rots.

## 7. Nothing here touches the adaptive layer

A scripted conversation is chosen before the run starts and read off a record; the
adaptive attacker chooses its next probe from what came back. Same wire, different
half of the tool boundary (PLAN §3), and this ticket adds no model call. The one edge
that crosses is unchanged: `proposed_from` wraps the probe it was given in a
one-element payload, because a probe is one message the attacker composed and a
payload type that can hold a script does not make the adaptive layer able to send
one (ADR-0010).

## Considered and refused

**A second `script` field beside `payload`.** Two fields, a record that can carry
both, and a loader deciding which one the wire sees. Refused in §1.

**Scoring only the last reply.** Refused in §3: it records a target that leaked and
recovered as one that held.

**Filtering every turn through `checkable`, the last one included.** Refused in §4:
it turns two loud refusals into a quiet *resisted*.

**A turn as the unit of the denominator.** Ten attempts of a four-turn script is
forty scored readings, correlated in fours, reported as `n = 40`. Every interval the
gate computes assumes independent samples, so this is the one change in this ticket
that would make a published figure wrong. Refused on the arithmetic alone — CONTEXT.md
has said *a turn is not an attempt* since before there was a script.

**Applying the transform at send time so a script needs no record.** ADR-0051 §1
refused it for the library at large and the reasons hold here: admission would have
nothing to attach to, the decay series would stop being a series about one thing, and
`LibraryVersion` would stop covering what a run sent.

**A precondition of #74's own.** Refused in §5: two names for one declared capability
is the thing #71 asked the two tickets to avoid.
