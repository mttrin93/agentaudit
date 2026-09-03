---
status: accepted
---

# The console may set a run's declared inputs

`/bench` was read-only, and it was read-only on purpose. `SettingsScreen.tsx` said so
in its own docstring — *"there is no control here… no route on this bench would take
one"* — and two tests asserted it from both ends: one over the route table, one over
the component's source. The reason given was
[ADR-0020](./0020-the-signing-key-is-read-from-the-environment.md): the factory reads
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

## `attempts_per_case` is in a different class from the other four, and the screen says so

*Amended by
[ADR-0027](./0027-the-verifier-reads-the-denominator-and-asserts-the-rest-of-the-bar.md)*:
the screen said it and the signed artefact did not,
and a verifier asserted the declared number against every payload — so a run made at
the offer below reported its own arithmetic as disagreeing. ADR-0027 decides what that
verifier is asserting: this number is read, the rest of the bar is asserted, and the
*not a gate result* sentence travels in the document rather than only on the screen.

Four of the five bound a layer that is **scored on nothing**
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

## What did not move

- **The signing key.** Read from the environment by `signing.signing_key` and by no
  route. ADR-0020 is untouched: a key made on demand would boot cleanly and sign every
  report with one nobody has published.
- **The case library.** What was mounted. A gate run rewrites it and that is its own
  `POST` behind its own attestation ([ADR-0021](./0021-the-console-may-start-a-gate-run.md)).
- **The gate citation.** Moves when a gate run earns it and by no other route
  ([ADR-0023](./0023-a-gate-run-updates-the-citation-it-earned.md)).

## Consequences

- The two tests that asserted *no writes under `/bench`* now assert *exactly one, and
  it is this one*. That is the same protection at a different line: a second write
  appearing under the prefix still fails, whatever it is called.
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
