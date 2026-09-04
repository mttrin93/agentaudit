---
status: accepted
---

# The console may set a run's declared inputs

`/bench` was read-only, and it was read-only on purpose. `SettingsScreen.tsx` said so
in its own docstring — *"there is no control here… no route on this bench would take
one"* — and two tests asserted it from both ends: one over the route table, one over
the component's source. The reason given was
[ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md): the factory reads
its signing key from one place and refuses to boot without it, so a screen that could
write a setting is a screen that could sign reports with a key nobody published.

That reason is sound and it covers the signing key. It was carried across, without
argument, to everything else a deployment declares — the models, the library, the
thresholds — and there the argument does not hold in the same way. The consequence
was that an operator could only change `T` by editing an environment variable and
restarting the process, which is not a consent mechanism; it is a deployment step
standing in for one.

**Decision.** One route under `/bench` writes: `PUT /bench/settings/tuning`, taking
the **declared inputs of the next run** — the adaptive attacker's model, its
sampling temperature and its reasoning effort, `T` (turns per episode), `k`
(episodes per family), and `attempts_per_case`. Everything else on that prefix still
only reads.

*Amended by #57*: **two routes under `/bench` write, not one.** The second is
`PUT /bench/settings/families`, taking **the families the next run covers**, and it
predates this record — it arrived with the adaptive layer's own screen (`6aa02df`,
#121) — so the paragraph above was written claiming an exclusivity that was already
false. What is corrected is the count and nothing else: the families route is admitted
on the same four conditions, argued below under *the second write*, and everything
else on the prefix still only reads. Read *one* as *two* throughout, and read the
conditions as the bar both routes clear.

*Amended by #79*: **three routes under `/bench` write.** The third is
`PUT /bench/settings/selection`, taking **which layers the next run runs and which
constructions inside them**, and it is admitted on the same four conditions — argued in
[ADR-0058](./0058-the-console-selects-layers-and-constructions.md), which is where the
decision is recorded rather than here. It is the **second** setting on this prefix that
moves the scored denominator, which is why it needed a record of its own: the section
below argues one scalar, and a selection is not a scalar. ADR-0058 §4 also answers the
question the families amendment below explicitly left open — whether such a setting
should travel in the signed payload — **for the selection and for the selection only**.
Read *two* as *three* throughout.

*Amended by #5*: the reasoning effort joined on exactly these conditions and through
the same seams. It is the attacker's second sampling setting, offered only for a model
the capability table says has one, and refused rather than dropped for a model that
does not — two runs of one model at one temperature and different effort are two
different instruments, so condition 1 is what admits it.

Admitted on four conditions, and each one is enforced rather than intended:

1. **Every setting is printed in the report of every run made under it.** The
   attacker's model, temperature and reasoning effort land in the provenance block
   (`DeclaredModels.attacking`, `.attacking_temperature`,
   `.attacking_reasoning_effort`), `T` and `k` in the adaptive
   section, and the rule travels on every `TargetRun` beside the rate it produced.
   This is the condition that makes the others survivable: a setting that changes what
   a run measured is admissible **because** the artefact says what it was.
2. **A run in flight keeps what it was started with, and a change is refused while one
   is going.** A run awaiting approval has been shown an estimate built from the
   settings it was declared with, and [ADR-0007](./0007-canary-nonce-as-proof-of-control.md)'s
   whole mechanism is that nothing exceeds what a human confirmed. `RunsInFlight` names
   the runs so an operator can wait or decline rather than guess. `409`, not `422`: the
   request is well formed and the bench is the reason.
3. **The model comes from a closed list and the client is built in the same call as the
   identifier.** A slug the provider rejects fails at the first call, which is *after*
   an operator has attested and confirmed a spend — so the list is server-side and the
   route refuses anything else. Building the client beside the identifier is the pairing
   `app.declared_instrument` already makes at boot: a bench cannot name a model that
   never ran.
4. **A setting outside its range is refused, never clamped.** A bench that quietly
   moved a number would run a setting nobody chose and print it as though they had.

## `attempts_per_case` is in a different class from the other five, and the screen says so

*Amended by
[ADR-0027](./0027-the-verifier-reads-the-denominator-and-asserts-the-rest-of-the-bar.md)*:
the screen said it and the signed artefact did not,
and a verifier asserted the declared number against every payload — so a run made at
the offer below reported its own arithmetic as disagreeing. ADR-0027 decides what that
verifier is asserting: this number is read, the rest of the bar is asserted, and the
*not a gate result* sentence travels in the document rather than only on the screen.

*Corrected by #57*: five of the six, not four of the five — #5's amendment added
the reasoning effort to the adaptive side and this sentence four paragraphs down kept
the old count. `Tuning`'s docstring (`app.py:2760`) has read *five of the six, and
the sixth is the scored denominator* since; the class boundary this section is about
is unmoved, and only the arithmetic describing it was.

Five of the six bound a layer that is **scored on nothing**
([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)):
turning `T` up buys the attacker more rope and moves no rate, no band, no `D` and no
gate decision. `attempts_per_case` is the scored denominator —
[ADR-0003](./0003-gate-decision-rule-and-sample-size.md) sets it so that `n = 30` per
family, which is what the Wilson interval, the band, monotonicity and the retirement
rule are all defined against.

Refusing to offer it was rejected: an operator exploring a new target does not want 181
calls per target to find out whether the wire works, and `probe_target.py` already lets
them choose on the command line. What is refused instead is the confusion it could
cause. A run at another number is a real run whose rates carry the rule they were
measured at, and it is **not a gate result**: the block that offers the setting prints
that sentence beside it, `scripts/gate.py` takes no setting from this screen, and the
`n` at the current setting is shown next to the `n` the declared rule reads so an
operator can see at a glance which one this bench is on.

## The second write: which families the next run covers

*Added by #57.* `PUT /bench/settings/families` is the other write on the prefix, and
it is its own route rather than a seventh field on the tuning request because it is a
different statement made from a different screen: that one is *how the instruments are
set* and takes all six settings every time, and this is *what the next run covers*. A
caller sending one has no business restating the other.

It is admitted on the four conditions above, and each one is enforced there too.

1. **What it changed is legible in what the run produced.** A family switched off has
   its cases dropped from the plan, so the run states it as *not run* carrying
   `DeclaredGap.FAMILY_SWITCHED_OFF`'s sentence — *a family that was not asked is not
   a family that held* ([ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md)) —
   rather than as a rate of zero, and the artefact carries a per-family block for
   exactly the families that were measured. This is condition 1 met by an absence
   instead of by a printed field, and the absence is readable **because** nothing in
   the report totals, averages or ranks across families
   ([ADR-0005](./0005-no-composite-risk-score.md), D12): a family switched off cannot move
   a figure that *is* printed. **The limit this leaves, stated:** the signed artefact
   names the families it measured and does not name the reason the rest are missing —
   that sentence travels in the run record and on the screen. **This record does not
   decide whether it should also travel in the payload** — that is a change to the
   payload and wants an ADR of its own; what is written down here is the limit, so
   that a reader is not left to discover it.
2. **A change is refused while a run is going.** `Bench.cover` takes the same lock as
   `Bench.instrument` and raises the same `RunsInFlight`, for the same reason: a run
   awaiting approval was shown an estimate built from the families it was declared
   with, and narrowing them under that halt would make the confirmation a statement
   about a different run (ADR-0007). `409`, not `422`.
3. **The names come from a closed list, resolved server-side before anything is
   stored.** Every name is turned into a `Family` member first and an unknown one is a
   `422` naming the six, so a bench cannot be put on a family the library has no cases
   for. Condition 3's second half — building the client in the same call as the
   identifier — has no analogue here and is not owed one: a family is not an
   instrument, nothing is constructed from the name, so there is no pairing to keep.
4. **An empty selection is refused, never widened.** A run covering no family attacks
   nothing and would still spend a registration probe per target, and a bench that
   read *none* as *all six* would run a coverage nobody chose — which is condition 4's
   own argument about clamping, in the one place this route could have clamped.

## The third write: what the next run sends

*Added by #79, and decided in
[ADR-0058](./0058-the-console-selects-layers-and-constructions.md).* Its own route
rather than a field on either of the other two, on the families route's reasoning: that
one is *what the next run covers* and this is *how it attacks what it covers*. The four
conditions are enforced there too, and one of them is met differently — condition 1 by a
**printed field** rather than by an absence, because `Provenance.selection` carries the
selection into the signed artefact. That is the half the families route could not do and
the reason ADR-0058 exists as a separate record.

**Why this is an amendment and not a new decision.** Nothing about the route moved,
and no condition was relaxed to fit it: the four conditions were the bar the tuning
route was admitted at, the families route already cleared all four, and the record
simply failed to say so. A new ADR would be minuting a decision nobody made. What
#57 changes is that the count is now checked — `test_api_settings.py` and
`test_api_gate.py` name every pair under the prefix, so a *third* write fails and has
to be argued here before it lands.

## What did not move

- **The signing key.** Read from the environment by `signing.signing_key` and by no
  route. ADR-0020 is untouched: a key made on demand would boot cleanly and sign every
  report with one nobody has published.
- **The case library.** What was mounted. A gate run rewrites it and that is its own
  `POST` behind its own attestation ([ADR-0021](./0021-the-console-may-start-a-gate-run.md)).
- **The gate citation.** Moves when a gate run earns it and by no other route
  ([ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md)).

## Consequences

- The tests that asserted *no writes under `/bench`* now assert *exactly these two,
  and no others* — `test_api_settings.py` and `test_api_gate.py`, both over the whole
  route table. That is the same protection at a different line: a **third** write
  appearing under the prefix still fails, whatever it is called, and it fails naming
  the route.

  *Amended by #57*: this bullet said *exactly one, and it is this one*, and a second
  write appearing under the prefix did not fail — the sets had been widened to admit
  the families route and neither the tests' names nor this sentence was. The
  protection was real the whole time and it was a line further out than the record
  claimed. The count is now the thing the tests say they assert.

  *Amended by #79*: **three, and a fourth is what fails.** Both tests failed on
  `PUT /bench/settings/selection` before they were updated to admit it, which is the
  protection working rather than the protection being widened: the route is named in
  each set and the count moved in the same diff as the record that argues it
  (ADR-0058).
- `SettingsScreen.tsx` has a form, and its test now asserts that the form is the only
  write and that it cannot reach anything else on the bench — no run started, no
  interrupt answered, no nonce issued, no gate run, no `fetch` of its own.
- Settings held in a process are lost at a restart, which the environment variables
  they replace were not. That is the shape the run registry already has and the same
  P1 it carries: durability is a queue-and-store change, not a correctness one.
- A temperature is now a declared input with a `None` that means *the provider's own
  default*. `None` and a number are different declarations and the field records which
  one was made; a bench that wrote its own number there would be naming a choice nobody
  made.
