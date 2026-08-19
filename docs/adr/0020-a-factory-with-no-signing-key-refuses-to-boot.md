---
status: accepted
---

# A factory with no signing key refuses to boot

Issue #56 landed `GET /report/{id}` and the two paths beside it, so from PR #69 a run started over HTTP has somewhere to hand its artefact out from. Every acceptance criterion on it passed. The sub-agent that built it flagged one thing it would not decide for itself: `create_app()` called with no configuration builds a `ReportConfig()` with `signing_key=None`, so the command the README publishes —

```
uv run uvicorn backend.api.app:create_app --factory
```

— starts a bench that attempts the whole library against somebody's endpoint, for many minutes, on the operator's money, and then refuses every report it produced as `never_signed`. Nothing is broken. Every route answers, every refusal is named, the measurement is real. What the shipped default cannot do is produce a document that travels, which is the only artefact this project claims to make.

It was right not to decide it. Whether a deployment may run without a key is deployment policy, and the code had no policy to read. This ADR is that policy.

**Decision.** `create_app()` reads `AGENTAUDIT_SIGNING_KEY` through `signing.signing_key` and refuses to boot without it.

1. **Fail loud at startup, not `never_signed` at report time.** The refusal is raised while the app is being built, before a route exists, before a nonce is issued and long before a call reaches a target. `NoSigningKey` propagates out of the factory and `uvicorn` dies with it.
2. **The refusal names the variable and the command that makes a pair.** `signing.signing_key` already says what is absent and how to generate one; `app.NO_KEY_NO_BOOT` adds what booting anyway would have cost. Its type is unchanged, so a deployment already catching `NoSigningKey` catches this one.
3. **Read through `signing.signing_key`, and by nothing else.** There is still exactly one line in this repository that reads `AGENTAUDIT_SIGNING_KEY`. The factory calls it; it does not become a second reader of the environment, and no module of `backend/api/` imports `os` or `dotenv`.
4. **The environment is the default path and not the only one.** A caller that hands in a `BenchConfig` has declared what its bench signs with — including that it signs with nothing, which is what most of the test suite wants and what a bench under test should be able to be without a private key in the shell. A bench that cannot sign stays reachable *by declaration*, and stops being reachable *by omission*.
5. **[ADR-0007](./0007-canary-nonce-as-proof-of-control.md)'s prohibition on environment-read cost figures is untouched.** It is narrowed in what it claims, not lifted: no cost figure, target URL or bearer token is ever defaulted from the environment, the behavioural test that sets `AGENTAUDIT_PRICE_PER_CALL` and asserts a refusal still asserts it, and the import test that would catch a second reader still runs over every module of the API. Only its docstring changed, because the old one had become false in one clause and a green test carrying a false claim is worse than a red one.
6. **The dev path needs a key, and the key is ephemeral.** `uv run python -m scripts.keygen --public /tmp/dev-signing.pub` generates a pair outside the repository and prints the private half once, to be exported in the shell that starts the server. No key, and no committed configuration containing one, enters this repository.

## Why: a report nobody can check is the artefact this project exists to displace

[ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md) names what AgentAudit is sold against, and it is not a regulator:

> The displaced default is the hand-filled security questionnaire — a document a human completes from recollection, under commercial pressure, **for a customer who cannot verify any of it.**

That last clause is the whole product. There is no badge, no score and no declaration of conformity ([ADR-0005](./0005-no-composite-risk-score.md)); what a recipient gets instead is bytes they can check offline, against a key whose fingerprint is published where they can read its history, with the arithmetic re-derived in front of them ([ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md)). Strip the signature and what is left is a document asserting figures on its author's word — which is the questionnaire, produced more expensively.

So the default deployment was shipping the exact failure the project is a refusal of. Not a missing feature: an instrument that measures and cannot testify.

**And the cost is paid before the failure is visible.** This is the part that makes it a startup refusal rather than a warning. An operator plants a nonce, signs three attestations, confirms a call ceiling, and waits out a run that spends their inference budget against their own agent. The bench does everything it promised. The first moment anyone learns the deployment had no key is when they ask for the report — after the money is gone, and with the measurement in a process that will not outlive it. A failure whose earliest possible signal is a refused report is a failure that has to be moved to boot time, because boot time is the last moment at which nothing has been spent.

The same reasoning is why `keygen` does not exist behind a flag on the server, and why nothing generates a key on demand. A key generated at startup would boot cleanly and sign every report with a key nobody has published — a valid signature over unknown provenance, which ADR-0017 spends its length refusing. Between *no report* and *a report signed by an unpublished key*, the second is worse, because the first is legible.

## This is the deployment-level form of a discipline the bench already applies four times

The pattern is not new here. In every case a missing prerequisite produces a *stated refusal* rather than a degraded result that reads like a real one, and in every case the reason is that the degraded result is indistinguishable from a good one at a glance:

- **No nonce, no run.** Registration does not complete without the echo, and the probe that checks it is a call on the operator's endpoint, so the halt is ahead of it ([ADR-0007](./0007-canary-nonce-as-proof-of-control.md)). An unproven target is not attempted at all.
- **No adjudicator, no judged family.** A bench configured without one does not run the judged cases and reports the gap that says why (`runs.py`, [ADR-0013](./0013-adjudication-is-a-third-instrument.md)). A run that discovered at its first judged attempt that it had no instrument would have spent the operator's budget on attempts nothing can score — the same shape of waste as this ADR's, one layer down.
- **No tool trace, no rate.** A target that cannot expose its tool calls yields *not measurable*, never a rate of zero (CONTEXT.md).
- **A family unfit to report supplies no evidence.** It is excluded from the gate decision entirely ([ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md)), and retirement declines on it rather than firing on numbers the report will not print ([ADR-0016](./0016-retirement-declines-on-a-family-unfit-to-report.md)).

Every one of those refusals is inside the bench, decided per run. This one is about the process the bench runs in, and it is the same sentence: **do not produce something that looks like the real thing when a prerequisite for the real thing is absent.** A booting keyless factory is that failure at the only level the project had not yet applied it to — and the level at which it is least visible, because it is configured once by whoever deploys and then never mentioned again.

## Considered options

- **Boot, log a warning, refuse reports as `never_signed`.** The status quo with a log line. Rejected because the warning is read by nobody in the position to act on it: it appears in the server's output at startup and the person who needs it is the operator, hours later, in a client. A degraded mode announced only to the wrong audience is not announced.
- **Boot, and refuse `POST /runs` instead.** Better — nothing gets spent — and still worse than this. The bench would advertise six routes it can serve and one it cannot, so the check lands on the operator's first real request rather than on the deployer's own terminal. The person who can fix a missing environment variable is the person starting the process.
- **Generate a key at startup when none is set.** Boots cleanly, signs everything, and produces valid signatures over unknown provenance — ADR-0017's failure exactly, and the worse of the two because a report signed by an ephemeral key is *harder* to diagnose than one that was never signed. Also invites a rotation story nobody wrote: every restart would be a new signing identity.
- **Read a key from a file, or from a committed default.** Rejected on [ADR-0008](./0008-repo-disclosure-posture.md) and on the plainest form of the disclosure posture: publishing this repository must not publish the ability to forge its reports. No line in this codebase writes a private key to disk, `scripts/keygen` prints it once, and a file-based path would create the first exception.
- **Make the key required on `BenchConfig` itself, so no bench anywhere can lack one.** The strictest answer, and it removes something real: a bench that measures and does not sign is legitimate — it is what the test suite runs, and it is what the two judged families' calibration work needs. `report.py` already has a named, tested state for it. The policy belongs at the deployment boundary, which is the factory.
- **Leave it, and document that a deployment must export the variable.** The option that was in force by default. A documented obligation with no mechanism is a footnote against a silent failure, and the silent failure had already shipped once.

## Consequences

- `create_app()` with no argument raises `NoSigningKey`. Any caller relying on a keyless default breaks loudly, which is the point; the form that hands in a `BenchConfig` is unchanged.
- **The local development path now needs a key**, generated with `scripts.keygen` to a public path outside the repository and exported in the shell. The README's API section carries the two commands. A report signed by a dev key verifies only against that dev public half, via `scripts/verify.py --pubkey`.
- **`.env` stays gitignored and no key is committed.** A deployed instance gets a real key set in its environment, whose public half is the committed one and whose fingerprint the README publishes.
- **The import test that said the API reads no environment now says what is true**: no module of the API is an environment reader of its own. Beside it, a test names the single exception and pins it to `signing.signing_key`, so a second route to the environment fails there. The cost-figure test above them is unchanged.
- `BenchRuns` exposes its `config` read-only, so the boot-time contract is asserted against the bench the factory actually returned rather than against a function nobody proved it called.
- **A deployment can still choose not to sign, and now has to say so in code.** `create_app(BenchConfig(...))` with no key is a supported bench with a stated absence — an explicit decision with an author, which is the difference this ADR is about.

Cross-references: [ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md) (the buyer, and why a report a recipient cannot check is the artefact being displaced), [ADR-0017](./0017-the-signature-covers-the-document-and-carries-two-claims.md) (what the signature claims, and why no key is generated on demand), [ADR-0007](./0007-canary-nonce-as-proof-of-control.md) (the cost-figure environment prohibition, narrowed and intact, and the no-nonce refusal), [ADR-0013](./0013-adjudication-is-a-third-instrument.md) (no adjudicator, no judged family), [ADR-0015](./0015-the-gate-is-decided-over-families-fit-to-report.md) and [ADR-0016](./0016-retirement-declines-on-a-family-unfit-to-report.md) (the unfit-family exclusion this is the deployment-level form of), [ADR-0008](./0008-repo-disclosure-posture.md) (why no private key is ever committed), [ADR-0005](./0005-no-composite-risk-score.md) (no badge, which is why the checkable bytes are the product).
