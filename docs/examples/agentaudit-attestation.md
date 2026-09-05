# AgentAudit attestation

The three statements this repository makes before the bench touches the endpoint
below. They are written out here rather than answered at a prompt because no human is
sitting in front of a CI run — and they are not weaker for it: this file arrives as a
reviewed diff, and the run is made under an identity GitHub authenticates
([ADR-0065](../adr/0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md)).

The `target:` line is load-bearing. The run is refused unless the endpoint it is about
to attack is exactly this string, so pointing the bench somewhere else means editing
this file — which is a reviewed diff too, and that is the whole point.

target: https://staging.example.com/agent/messages

- I am authorised to test this endpoint
- this endpoint is a staging or sandbox environment
- I accept that these payloads will generate provider policy violations
  against my own account and consume my own inference budget

Deleting a statement does not make the run proceed without it: the attestation is
refused, naming the statement that was withheld, and nothing is sent.
