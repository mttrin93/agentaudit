---
status: accepted
---

# A trace carries the shape of a run and never its content

A run is 180 scored calls plus retries and judge calls, plus up to 96 adaptive calls;
a gate run is around 830. When a family comes back all-zero the operator has two
explanations — the target defended, or the instrument misfired — and nothing on the
record tells them which. [docs/validation.md](../validation.md) answers that question
for the bench as a whole, once, at gate time. It cannot answer it for the run in
front of you.

**And there was a latent version of it already in the tree.** `langsmith` is in
`uv.lock` today, pulled in transitively by `langchain-core`, and its tracing switches
on from the environment alone — one variable and an API key, no code change. Nothing
in this repository set those variables and, until this ADR, nothing stopped them. So
the state was not *no observability*; it was observability that a stray environment
variable turns on, shipping whatever it likes to a third party, with no allowlist in
front of it.

## Decision

Six parts, and the second is the one the other five exist to protect.

1. **The sink is LangSmith, over OTLP, while the only targets are reference agents.**
   It is the native sink for a LangGraph application, `langsmith` is already in the
   lock, and [PLAN.md](../../PLAN.md) D7 calls the three reference agents test
   equipment that never goes to a user — so a trace of a run today concerns this
   project's own payloads against this project's own agents. There is no third
   party's agent in it to leak.

2. **That holds under a condition, and the condition is written here so it can be
   checked rather than remembered.** [ADR-0008](./0008-repo-disclosure-posture.md)
   says transcripts are never committed and a payload whose wording is the working
   part is withheld, because a payload cannot be unpublished. That argument is about
   somebody else's agent, and it becomes live the moment one arrives: Track A's five
   engineers with staging endpoints. **Before the first target that is not a
   reference agent, the sink is revisited** — moved to something the operator runs,
   or the exposure accepted in writing by whoever accepts it. The revisit is cheap by
   construction: the sink is a url in the environment and one module knows what is on
   the far end of it.

3. **What may be emitted is a declared field allowlist, not a redaction pass.**
   `observability.Field` enumerates every attribute a span may carry: the run id or
   gate run id; family, case id and attempt index; episode index and turn; which
   graph node ran; calls spent per layer; the verdict and its class; the retry count
   and the error class; the three instruments' model identifiers; and the endpoint
   hash. Everything else is excluded by not being on the list. A denylist over trace
   content goes stale the first time somebody adds a node, and the failure direction
   is irreversible.

4. **The default LangGraph tracer is rejected.** It captures inputs and outputs
   verbatim, so the first traced run would send the attack payloads, the target's
   replies and the target's `auth_token` to a third party. Emission is plain
   OpenTelemetry spans carrying allowlisted attributes, exported to an OTLP endpoint.

5. **The inherited switches are neutralised at startup rather than merely unused.**
   `disable_inherited_tracing` sets every variable in
   `observability.INHERITED_TRACING_VARIABLES` to `false` at the top of
   `run_calibration` and at the top of `create_app`, and says which ones it turned
   off. A guard that works only because nobody set the variable is not a guard.

6. **A trace is neither the Article 12 log nor the authority for any figure**, and it
   is never a run's dependency. Those three are argued below.

The configuration follows [ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md)'s
shape and not its severity: read from the environment through one function,
`observability.trace_config`, outside `backend/api/`; and **absent means tracing is
off**, not a refusal to boot. A signing key is what makes a report portable. A trace
sink is a convenience, and a bench that would not start without a debugging tool has
its priorities inverted.

## This reverses an earlier decision on the same question

The ticket was first written for a self-hosted Langfuse, on the grounds that a leak
of trace content should reach a machine the operator owns rather than a third party.
The trade — infrastructure now against exposure that does not exist yet — was called
the other way, deliberately, and the cost of calling it that way is stated rather
than absorbed: **with a self-hosted sink a leak is recoverable, and with a hosted one
it is not.** The allowlist was one of two controls and is now the only one. Every
requirement in it is load-bearing in a way it was not before, and none of it may be
softened for convenience. That is why point 3 has a test asserting the emitted set is
*exactly* the declared list, in both directions, rather than a test asserting that
nothing obviously bad appears.

## Three things a trace is not

**Not the Article 12 log.** `Article.RECORD_KEEPING` is a compliance obligation and
part of the evidence chain — `registration.py` puts the liability record and the
Article 12 record in one artefact deliberately. A trace is a debugging aid pointed at
a sink the operator can delete. So the Article 12 log does not move, does not thin
out, and gains no dependency on the tracer: **tracing may sample and the Article 12
log may not**, and with the tracer off every attempt is still recorded. A test runs
the same case three ways — tracing off, tracing on, sampled to nothing — and compares
the recorded attempts.

**Never the authority for a figure.** Calls spent, rates, intervals and bands come
from the run, and if a trace disagrees with the run the run is right and the trace is
a bug. No number in a report, on `/runs`, or in a gate decision is read back out of
the sink. That is [ADR-0006](./0006-overrides-never-change-a-measured-rate.md) and
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)
applied to a new writer, not a new rule. It has no behavioural test — there is no
route that would fail — so it is held where it can be: `observability.WRITERS` is the
whole of what a consumer may import, nothing on it returns what was emitted, and a
test walks every module that imports the emitter and asserts it took nothing else.

**Never a run's dependency.** A sink that is down, slow or misconfigured must not
fail, stall or alter a run. Every function in the module swallows its own failures
and logs them locally. The one exception is deliberate and is the reason the guards
are drawn where they are: **the allowlist check runs outside them.** A key that is
not a `Field` is a bug in a call site and has to be raised in the face of whoever
wrote it; a sink that is unreachable must not be. A bench that lost 180 paid calls
because a container was restarting would be a bench whose observability cost more
than it explained.

## Three properties of the implementation that carry the decision

- **The tracer provider is private to the module.** `set_tracer_provider` is called
  nowhere in this repository. A global provider is a sink that any library in the
  process can find, and the allowlist would then be a property of this module's call
  sites rather than of the exporter. Because the provider is private, the allowlist
  holds for everything that reaches the sink.
- **No exception is ever recorded on a span, and no status carries a description.**
  `TargetUnreachable`'s message contains the endpoint url (`contract.py`), and both
  `record_exception` and a status description are emitted verbatim. A failure is an
  `ERROR_CLASS` attribute — the named `TargetFailure` — and a bare error status. The
  class is the part that tells a reader which job they have: a timeout is capacity, a
  rejected token is configuration.
- **Span names are a closed set too.** A name is emitted data as much as an attribute
  is, and a name assembled from a case id or a target's name would be the allowlist
  bypassed through the one part of a span nobody thinks of as a field.

## Two places this departs from the ticket, and why

**The adaptive layer's units are on the allowlist.** #112's admitted list enumerates
family, case and attempt, which are the *scored* layer's units. The adaptive layer's
are episode and turn (`EpisodePosition`), and reusing `ATTEMPT_INDEX` for an episode
ordinal is precisely the merge ADR-0010 forbids: it would put an ordinal where a
denominator goes, in the one surface with no type to stop it. So `EPISODE_INDEX` and
`TURN` are their own fields, and a test asserts neither appears on the other layer's
spans.

**Token counts are absent, and absent rather than zero.** The admitted list names
call counts *and token counts* per layer. Calls are emitted, from `RunState.spent`,
which is the figure the two ceilings are enforced against. Tokens are not, because
nothing in the bench measures one: the target contract returns `{reply, tool_trace}`
with no usage, and `completion.py` discards the usage the provider returns. A token
field populated here would be a figure whose only source was the sink — which is
exactly what *never the authority for a figure* forbids, arrived at from the other
direction. The bench learns to count tokens first, in the run, where a report can
print them and a reader can check them; then the trace carries what the run holds.
This is the same reasoning the README already gives for optional task M1, and it is
why a field that could only ever read zero is not on the allowlist: a declared field
nothing writes tells a reader a trace carries something it does not.

## Considered options

- **The LangSmith LangGraph integration, as documented.** One environment variable
  and no code. Rejected: it sends prompts and replies verbatim, which is the single
  outcome this decision exists to prevent. Its convenience is exactly the convenience
  of having no allowlist.
- **The LangSmith client's own input/output masking.** The stated fallback if the
  OTLP path had turned out to be unavailable. It is a worse shape because masking is
  a denylist, and the OTLP ingest is documented and current, so it was not taken.
- **A field allowlist with an escape hatch — prompts behind a flag.** The flag is the
  failure. A field allowlist with an escape hatch is a denylist wearing a hat, and
  the run on which somebody sets the flag is the run that cannot be unpublished.
- **A self-hosted sink now.** The reversed decision, above. Revisited before the
  first non-reference target, which is the condition rather than a follow-up nicety.
- **Refuse to boot with no sink configured**, on ADR-0020's pattern. Rejected: that
  ADR's argument is that a bench which measures and cannot testify has shipped the
  failure the project is a refusal of. A bench that measures and cannot be debugged
  has not. The prerequisite is not of the same kind, so neither is the refusal.
- **Emit through the global OpenTelemetry provider.** Conventional, and it would let
  any auto-instrumentation in the process contribute spans to this exporter — which
  is the allowlist becoming a property of call sites rather than of the sink.

## Consequences

- `opentelemetry-api`, `-sdk` and `-exporter-otlp-proto-http` are direct dependencies
  rather than transitive ones. `langsmith` stays transitive and is imported nowhere.
- **A deployment turns tracing on with `AGENTAUDIT_TRACE_ENDPOINT`** and, for a hosted
  sink, `AGENTAUDIT_TRACE_API_KEY`; `AGENTAUDIT_TRACE_PROJECT` files the trace and
  `AGENTAUDIT_TRACE_SAMPLE` traces a fraction of runs. With none of them set the
  bench boots, runs and reports exactly as before.
- **A run over HTTP traces under the id its record already holds**; a terminal run has
  no record, so `scripts/console.traced_run` mints an id and prints it, and a trace
  nobody can look up is not emitted as an anonymous one.
- **One module names the sink**, asserted over the source of every other module of
  the bench and its scripts — including comments, because a header name or a
  documentation link is a way of naming a sink that no import test would see.
- **Moving to a sink the operator runs is a url.** Point 2's revisit costs a change of
  environment variable and, if the new sink wants different headers, one method.

Cross-references: [ADR-0008](./0008-repo-disclosure-posture.md) (the disclosure
posture this trades against, and the condition under which it becomes live),
[ADR-0006](./0006-overrides-never-change-a-measured-rate.md) and
[ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) (no
figure comes from anywhere but the run, and the two layers are never blended),
[ADR-0007](./0007-canary-nonce-as-proof-of-control.md) and
[ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md) (the endpoint hash, and
why an identity is kept out of what an instrument sees),
[ADR-0018](./0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md) (why a
run id and a gate run id are two fields),
[ADR-0020](./0020-a-factory-with-no-signing-key-refuses-to-boot.md) (the
configuration shape, and the refusal this one deliberately does not copy).
