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
 * **No retries, here or in CI.** A walkthrough that passes on the second attempt is a
 * walkthrough nobody can read a result off, and the run it drives is deterministic by
 * construction: a stub model, three attempts, and every wait an assertion on state the
 * bench has published rather than a sleep. If this goes red intermittently the fix is
 * in the test, and a retry would hide the evidence for it.
 *
 * **One worker.** The bench refuses to change its declared inputs while a run is in
 * flight (`PUT /bench/settings/*` answers `409`), which is ADR-0007 working: two
 * walkthroughs against one bench would fight over the settings the estimate was built
 * from. So the specs run one after another, and a second *walkthrough* would not be
 * allowed parallelism however many specs sit beside it.
 */

import { defineConfig } from '@playwright/test'

import { API_PORT, API_PORT_VARIABLE, APP_PORT } from './e2e/served.ts'

const APP = `http://127.0.0.1:${APP_PORT}`
const API = `http://127.0.0.1:${API_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  // Longer than the walk needs and shorter than a hang. The run itself is four
  // scored calls and one adaptive turn and finishes in under a second once it is
  // confirmed; what this covers is a dev server compiling the app on the first
  // request, and a `uv run` of the verifier at the end.
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI ? 'list' : 'line',
  use: { baseURL: APP },
  webServer: [
    {
      // From the repository root, which is where `uv` finds the project and where
      // `backend` is importable from.
      command: 'uv run python frontend/e2e/harness.py',
      cwd: '..',
      url: `${API}/bench/settings`,
      env: { [API_PORT_VARIABLE]: String(API_PORT) },
      reuseExistingServer: false,
      // Piped rather than swallowed: the harness refuses to serve when it can still
      // see a trace sink, and a refusal nobody printed would read as a port that
      // never opened.
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 120_000,
    },
    {
      // `--host 127.0.0.1` and not Vite's default. Its default is `localhost`, which
      // resolves to both `::1` and `127.0.0.1` on a GitHub runner and is not
      // guaranteed to be bound on the one this config probes — a CI run of this job
      // timed out waiting 120 seconds for a dev server that was already up. The
      // address the app is served on and the address the test asks for are one
      // constant, and now they are one address family too.
      command: `npm run dev -- --host 127.0.0.1 --port ${APP_PORT} --strictPort`,
      url: APP,
      env: { AGENTAUDIT_API: API },
      reuseExistingServer: false,
      // Piped for the reason the harness's is: a webServer that failed silently is
      // indistinguishable from one that was slow, and that is the failure this line
      // was added after.
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 120_000,
    },
  ],
})
