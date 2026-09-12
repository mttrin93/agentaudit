/**
 * The browser specs: what starts, in what order, and why they are not retried.
 *
 * Two servers and four specs, and only the first of them is a walkthrough.
 * `walkthrough.spec.ts` drives a real run end to end; `failures.spec.ts` is a render
 * assertion over a served artefact, and it exists because the walkthrough cannot reach
 * the reading it covers — that bench declares no models, so its document says no
 * narrative instrument was declared, and the section with blocks in it needs a document
 * two models wrote. `keyboard.spec.ts` is the register form's own surface — Enter, a
 * dead button's reasons, and a `422` reaching the field it names — and it starts no
 * run at all: its registration is intercepted before it leaves the browser.
 * `liveness.spec.ts` is what a screen says when it changes and what the run screen
 * says while nothing is arriving — the run it watches is one this process never made,
 * answered in the browser and then deliberately left unanswered. No spec starts a run
 * another could see, and the three after the walkthrough intercept the routes they
 * read rather than asking the bench for anything.
 *
 * `harness.py` serves the bench's own API and one set of
 * reference agents on a stub model, in an environment with no trace sink and no model
 * declared; `vite` serves the app and proxies the bench's six prefixes to that API, so
 * the app under test fetches the same same-origin paths it fetches in a deployment
 * (`vite.config.ts`). Playwright starts both, waits for each to answer, and kills both
 * at the end.
 *
 * **`vite dev` rather than `vite preview`, and that is a config fact and not a
 * preference.** The proxy is declared under `server.proxy` and there is no
 * `preview.proxy` beside it, so a previewed build serves the app and answers nothing
 * under `/runs` — the walkthrough would fail on its first fetch. Widening the Vite
 * config to make a second server work is a change bought by a test.
 *
 * **How this suite runs — no retries, one worker, and how long each spec is given —
 * is `e2e/suite.ts`**, which both configs read so that the two cannot drift. What is
 * left here is what this config *is*: the issuerless bench, and the one spec file it
 * does not run.
 */

import { defineConfig } from '@playwright/test'

import { HOW_IT_RUNS, theBench, theConsole } from './e2e/suite.ts'

export default defineConfig({
  ...HOW_IT_RUNS,
  // The doored walkthrough is not this config's. It needs an account at an issuer
  // and this suite must run on a fork with none (`e2e/door-user.ts`, ADR-0125), so
  // it is started by `playwright.door.config.ts` against a bench this one does not
  // serve.
  testIgnore: '**/door.spec.ts',
  // The console under test is the issuerless one, declared: the bench this suite
  // drives is `NO_DOOR` (ADR-0121) and there is no test user to sign in as, so every
  // screen renders, no door is attended, and no request carries an `Authorization`
  // header. `e2e/suite.ts` says why that is an argument rather than a `.env` file.
  webServer: [theBench(), theConsole('')],
})
