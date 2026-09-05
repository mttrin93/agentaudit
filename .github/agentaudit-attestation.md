# AgentAudit attestation — this repository's own smoke run

The three statements, written out, for the run `ci.yml`'s `action` job makes against
the reference callback it serves inside the runner. They are here rather than answered
at a prompt because nobody is sitting in front of a CI run, and they are not weaker
for it: this file arrives as a reviewed diff and the run is made under an identity
GitHub authenticates
([ADR-0065](../docs/adr/0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md)).

This one is also the demonstration of the default: `action.yml`'s `attestation` input
points here unless a caller says otherwise, and a caller's own copy is this file with
their target on the `target:` line.

The `target:` line is load-bearing. The run is refused unless the target it is about
to attack is exactly this string — here a dotted reference to a Python object in this
repository, because a callback served on a loopback port is named by the module a
workflow committed and not by the port it happened to bind
([ADR-0059](../docs/adr/0059-a-callback-target-is-served-over-the-contract.md)).

target: backend.tests.headless_agent:AGENT

- I am authorised to test this endpoint
- this endpoint is a staging or sandbox environment
- I accept that these payloads will generate provider policy violations
  against my own account and consume my own inference budget

The third statement is true of this run in the only way it can be: the job runs
`deterministic-only`, so no adjudicating model is built, no provider is reached, and
the budget it consumes is nobody's.
