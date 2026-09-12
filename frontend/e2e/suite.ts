/**
 * How a browser suite runs here, and the two servers it runs against — written once,
 * because there are two configs and only one answer.
 *
 * `playwright.config.ts` drives a bench with no door and `playwright.door.config.ts`
 * drives one with a door (ADR-0125). Everything else about them is the same, and
 * *the same* has to be a shared value rather than a claim in two docstrings: a
 * timeout retuned in one file and not the other is two suites with different
 * patience, and nothing would say so.
 *
 * So the knobs are `HOW_IT_RUNS` and the servers are two functions, each taking the
 * one thing its caller decides. What is left in a config is what that config is: which
 * spec files, and what the two servers are declared with.
 */

import type { PlaywrightTestConfig } from '@playwright/test'

import { API_PORT, API_PORT_VARIABLE, APP_PORT } from './served.ts'

/**
 * One entry of a config's `webServer`, which is what both server functions build.
 *
 * Taken off the config type rather than imported by name: `@playwright/test` exports
 * `PlaywrightTestConfig` and not the element type of that field, and a hand-written
 * copy of the shape would be a second declaration of somebody else's interface.
 */
type OneServer = Extract<
  NonNullable<PlaywrightTestConfig['webServer']>,
  readonly unknown[]
>[number]

/** Where the app is served, and so what `baseURL` is. */
export const APP = `http://127.0.0.1:${APP_PORT}`

/** Where the bench is served, and so what Vite proxies to. */
export const API = `http://127.0.0.1:${API_PORT}`

/**
 * The reading both suites take: no retries, one worker, and how long each is given.
 *
 * **No retries, here or in CI.** A walkthrough that passes on the second attempt is a
 * walkthrough nobody can read a result off, and the run it drives is deterministic by
 * construction: a stub model and every wait an assertion on state the bench has
 * published rather than a sleep. If this goes red intermittently the fix is in the
 * test, and a retry would hide the evidence for it.
 *
 * **One worker.** The bench refuses to change its declared inputs while a run is in
 * flight (`PUT /bench/settings/*` answers `409`), which is ADR-0007 working: two
 * walkthroughs against one bench would fight over the settings the estimate was built
 * from. So the specs run one after another, and a second *walkthrough* would not be
 * allowed parallelism however many specs sit beside it.
 *
 * **The timeout is longer than the walk needs and shorter than a hang.** The run
 * itself is four scored calls and one adaptive turn and finishes in under a second
 * once it is confirmed; what this covers is a dev server compiling the app on the
 * first request, and a `uv run` of the verifier at the end.
 */
export const HOW_IT_RUNS = {
  testDir: './e2e',
  // The suffix, stated rather than left to the default. Playwright's default
  // `testMatch` takes `.test.ts` as well, and `e2e/` now holds one — `door-user.ts`
  // is a function over a dict and is covered in vitest (`vite.config.ts`). Left at
  // the default, either runner would pick that file up, find no `test()` in it and
  // fail on a file that is already green somewhere else.
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI ? 'list' : 'line',
  use: { baseURL: APP },
} as const satisfies PlaywrightTestConfig

/**
 * The bench, served by `harness.py` from the repository root.
 *
 * Which bench it is — `NO_DOOR`, or the deployed reading of the factory — is not
 * decided here and not decided by an argument: the harness reads
 * `AGENTAUDIT_E2E_ISSUER_JWT_KEY` out of the environment Playwright passes it and says
 * so on the line it prints (`harness.declared_door`). Nothing about a key is written
 * in a config, which is what keeps a key out of a commit.
 *
 * **The readiness probe is `/bench/settings`, and on a doored bench it answers
 * `401`.** That is *up*, and Playwright reads it as up: its check accepts 2xx, 3xx and
 * the 400-403 band, which exists for exactly this — a server that is answering and
 * refusing is not a server that has not bound yet.
 */
export function theBench(): OneServer {
  return {
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
  }
}

/**
 * The console, served by Vite, with the issuer its caller declares.
 *
 * **The publishable key is the argument because it is the whole difference between
 * the two suites.** An empty string is a console that attends no door: every screen
 * renders, and no request carries an `Authorization` header (`console/door.ts`,
 * ADR-0121). A key is a console that mounts `<ClerkProvider>` and signs somebody in.
 *
 * It is declared here rather than left to whether the developer running this happens
 * to have a key in `frontend/.env` — a suite that passed in CI and showed a sign-in
 * screen on the laptop of anybody who had done the setup would be a suite whose result
 * depends on a gitignored file. An empty value wins over the file, which is Vite's own
 * precedence: `VITE_`-prefixed variables already in the environment are applied after
 * the `.env` files are read.
 *
 * **It is inlined into the bundle by the server this declares it to**, exactly as it
 * is in a deployment — which is the Vercel trap `docs/deployment.md` records, met here
 * as a build-time argument rather than as something set afterwards.
 *
 * `--host 127.0.0.1` and not Vite's default. Its default is `localhost`, which
 * resolves to both `::1` and `127.0.0.1` on a GitHub runner and is not guaranteed to
 * be bound on the one a config probes — a CI run of this job timed out waiting 120
 * seconds for a dev server that was already up. The address the app is served on and
 * the address the test asks for are one constant, and now they are one address family
 * too.
 */
export function theConsole(publishableKey: string): OneServer {
  return {
    command: `npm run dev -- --host 127.0.0.1 --port ${APP_PORT} --strictPort`,
    url: APP,
    env: { AGENTAUDIT_API: API, VITE_CLERK_PUBLISHABLE_KEY: publishableKey },
    reuseExistingServer: false,
    // Piped for the reason the bench's is: a webServer that failed silently is
    // indistinguishable from one that was slow, and that is the failure this line
    // was added after.
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120_000,
  }
}
