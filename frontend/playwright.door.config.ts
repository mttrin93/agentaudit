/**
 * The same two servers, with the door up: a bench that verifies every request and a
 * console that has an issuer to sign in to.
 *
 * **A second config and not a project inside the first one.** A Playwright project
 * selects tests; it does not select servers. The two suites differ in what the two
 * `webServer`s are started with — one bench declares `NO_DOOR` and the other declares
 * an issuer, one console is built with no publishable key and the other with one —
 * and `webServer` is a property of the config. So the division is here, and
 * `playwright.config.ts` ignores `door.spec.ts` for the same reason this one runs
 * nothing else.
 *
 * **It is opt-in, and everything else about it follows from that**
 * ([ADR-0125](../docs/adr/0125-the-doored-walkthrough-is-opt-in-and-an-absent-test-user-is-a-printed-skip.md)).
 * The door needs an account at an issuer and a test user in it; a clone, a fork and CI
 * have none. So the four variables are read here before
 * anything starts: with them, two servers and a suite; without them, no servers at
 * all and a suite that skips with the sentence naming what to export. A config that
 * started the servers anyway would fail in the harness — a deployed factory with no
 * issuer refuses to boot (ADR-0116 §2) — and a webServer that never answered reads as
 * a timeout rather than as a missing variable.
 *
 * Everything about *how* a browser suite runs here — no retries, one worker, the two
 * servers and how long each is given — is `e2e/suite.ts`, which both configs read.
 * This file differs in what it declares to the console and in the spec it runs, and
 * in nothing else, and now that is a fact about the code rather than a claim in a
 * docstring.
 *
 * The ports are that file's, so the two suites cannot run at the same time. They are
 * two readings of one bench and there is no reason to; `--strictPort` makes the
 * attempt a refusal naming the port rather than a walkthrough that quietly drove the
 * other one's console.
 */

import { defineConfig } from '@playwright/test'

import { doorUser } from './e2e/door-user.ts'
import { HOW_IT_RUNS, theBench, theConsole } from './e2e/suite.ts'

/**
 * Read at config time, because the console's server is declared from it.
 *
 * `door.spec.ts` reads the environment again rather than importing this constant: a
 * spec that imported a config's value would be a spec that could not be run under any
 * other config, and the reading is a pure function of the environment both times.
 */
const user = doorUser(process.env)

// Printed once (ADR-0125 decision 3), because a skip is only documented if somebody
// reads the document. Playwright's reporters print `2 skipped` and not the annotation
// behind it, and a line saying two tests were skipped is exactly as informative as a
// line saying two passed.
if (!user.declared) {
  console.log(user.statement)
}

export default defineConfig({
  ...HOW_IT_RUNS,
  // This file and nothing else, which is the other half of `playwright.config.ts`'s
  // `testIgnore`.
  testMatch: '**/door.spec.ts',
  // No servers when there is no test user: the suite skips, and skipping is not
  // something to spend two server startups and a refusal-to-boot on. The bench reads
  // the issuer's PEM out of this process's environment itself (`e2e/suite.ts`).
  webServer: user.declared ? [theBench(), theConsole(user.publishableKey)] : [],
})
