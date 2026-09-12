---
status: accepted
---

# The doored walkthrough is opt-in, and an absent test user is a printed skip

[ADR-0121](./0121-an-open-bench-is-a-declaration-and-never-a-deployments-default.md)
decided that `frontend/e2e/harness.py` gets an open bench by passing `NO_DOOR`, and
its cost paragraph weighed that against "the alternative in which the e2e walkthrough
needs a provider account in CI" and rejected it. That holds, and it settles the
walkthrough that exists.

It leaves one claim unmade. `walkthrough.spec.ts` proves what every screen does when
the bench verified nobody — the sentence on the register screen, the same sentence in
the signed artefact. It cannot prove the other reading: that a signed-in operator
reaches the bench at all, that the token is on the request, that the request is still
same-origin, and that the name the console shows is the subject the document will
carry. That reading needs a real session from a real issuer, and
[the spec](../specs/the-authenticated-operator.md) calls it out as "the one part of
this that becomes genuinely more awkward". Three ways to make it were available.

- **Require an account in CI.** Rejected for ADR-0121's reason, unchanged: a fork
  cannot run the suite, and a suite a contributor cannot run is a suite that rots.
- **Stub the issuer.** The unit tests already do this — every test in
  `test_api_door.py` declares a stub verifier, which is why the constructor argument
  is a protocol. A browser suite against a stubbed issuer would assert this
  repository's own fake against itself and would stay green through a real issuer
  that had changed its sign-in, which is the one failure a browser is there to catch.
- **Commit a test user.** Not considered further. A credential in a repository is a
  credential that is published.

## Decision

**A second browser suite, opt-in through the environment, which skips out loud when
it is not configured.**

1. **It is a second config and a second suite, not a mode of the first.** A
   Playwright project selects tests and not servers, and the two suites differ in
   exactly what their two servers are declared with: one bench is `NO_DOOR` and one
   declares an issuer, one console is built with no publishable key and one with one.
   So `playwright.door.config.ts` runs `e2e/door.spec.ts` and `playwright.config.ts`
   ignores it. `npm run e2e` is unchanged, needs no account, and stays what CI runs.

2. **The credentials are four environment variables and nothing is committed.** They
   are read by one function, `e2e/door-user.ts`, on `identity.declared_issuer`'s
   shape — blank is unset, and the reading is a union so that a caller cannot read a
   credential it was not given. They carry their own `AGENTAUDIT_E2E_` names rather
   than reusing the deployment's: the harness deletes `AGENTAUDIT_ISSUER_*` before
   the factory runs, deliberately, so that an engineer with a real issuer exported
   does not get a browser run that reaches it. Opting in is a variable that exists
   for nothing else.

3. **Absent is a skip, and the skip prints the sentence naming what to export.**
   Not a pass, and not a failure. Not a pass because a green line is read as
   evidence the door works, and a suite that reported one while signing nobody in
   would be making this bench's own argument against it. Not a failure because the
   ordinary state of a clone, a fork and CI is to have no account, and a suite that
   is red for everybody is a suite people learn to ignore. Playwright's reporters
   print `2 skipped` and not the annotation behind it, so the sentence is printed by
   the config itself — a skip is only documented if somebody reads the document.

4. **The doored suite asserts the seam and does not walk the path again.** Refused
   with no session, admitted with one, the operator named on the screen that
   collects the attestation, and every bench request same-origin and carrying the
   header. The whole operator path is already walked once, issuerless; walking it
   again with a token on it would be thirty-one more calls to assert a header.

## What this costs, stated

**The claim this suite makes is one CI does not check.** Nothing on a green `main`
says a signed-in operator can still reach the bench; what says so is an operator
running `npm run e2e:door` against their own issuer, and the four variables it needs
are written down in [docs/deployment.md](../deployment.md) rather than left to be
rediscovered. That is the same posture the deployment itself is under — no CI job
deploys either half — and it is the honest reading: the alternative was a green line
that meant less than it looked like.

**A skipped suite looks like a passing one to anybody counting lines.** Decision 3's
printed sentence is the whole mitigation, and it is a sentence rather than an
exit code because the two states this has to separate — *skipped* and *ran* — are
both states in which nothing went wrong.
