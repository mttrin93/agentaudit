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
 * **It is opt-in, and everything else about it follows from that.** The door needs an
 * account at an issuer and a test user in it; a clone, a fork and CI have none, which
 * `e2e/door-user.ts` says at more length. So the four variables are read here before
 * anything starts: with them, two servers and a suite; without them, no servers at
 * all and a suite that skips with the sentence naming what to export. A config that
 * started the servers anyway would fail in the harness — a deployed factory with no
 * issuer refuses to boot (ADR-0116 §2) — and a webServer that never answered reads as
 * a timeout rather than as a missing variable.
 *
 * Everything `playwright.config.ts` decides about *how* a browser suite runs here —
 * no retries, one worker, `vite dev` rather than `vite preview`, and why each — is
 * decided there and not re-argued: this file differs in what it declares to the two
 * processes and in nothing else.
 *
 * The ports are that file's, so the two suites cannot run at the same time. They are
 * two readings of one bench and there is no reason to; `--strictPort` makes the
 * attempt a refusal naming the port rather than a walkthrough that quietly drove the
 * other one's console.
 */

import { defineConfig } from '@playwright/test'

import { doorUser } from './e2e/door-user.ts'
import { API_PORT, API_PORT_VARIABLE, APP_PORT } from './e2e/served.ts'

const APP = `http://127.0.0.1:${APP_PORT}`
const API = `http://127.0.0.1:${API_PORT}`

/**
 * Read at config time, because the servers are declared from it.
 *
 * `door.spec.ts` reads the environment again rather than importing this constant: a
 * spec that imported a config's value would be a spec that could not be run under any
 * other config, and the reading is a pure function of the environment both times.
 */
const user = doorUser(process.env)

// Printed once, because a skip is only documented if somebody reads the document.
// Playwright's reporters print `2 skipped` and not the annotation behind it, and a
// line saying two tests were skipped is exactly as informative as a line saying two
// passed — which is the reading `door-user.ts` exists to prevent.
if (!user.declared) {
  console.log(user.statement)
}

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/door.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI ? 'list' : 'line',
  use: { baseURL: APP },
  // No servers when there is no test user: the suite skips, and skipping is not
  // something to spend two server startups and a refusal-to-boot on.
  webServer: !user.declared
    ? []
    : [
        {
          // The harness reads `AGENTAUDIT_E2E_ISSUER_JWT_KEY` out of the environment
          // Playwright passes it — this process's, plus whatever `env` adds — and
          // serves the deployed reading of the factory rather than `NO_DOOR`
          // (`harness.py`, `declared_door`). Nothing about the key is written here:
          // a config that named its value would be a config that could commit one.
          command: 'uv run python frontend/e2e/harness.py',
          cwd: '..',
          // The same probe the issuerless config uses, and on a doored bench it
          // answers `401`. That is *up*, and Playwright reads it as up: its
          // readiness check accepts 2xx, 3xx and the 400-403 band, which exists for
          // exactly this — a server that is answering and refusing is not a server
          // that has not bound yet.
          url: `${API}/bench/settings`,
          env: { [API_PORT_VARIABLE]: String(API_PORT) },
          reuseExistingServer: false,
          stdout: 'pipe',
          stderr: 'pipe',
          timeout: 120_000,
        },
        {
          command: `npm run dev -- --host 127.0.0.1 --port ${APP_PORT} --strictPort`,
          // The one line that differs from the issuerless config's console, and it
          // is the whole difference: a publishable key, so `<ClerkProvider>` mounts,
          // the console attends a door and `api/http.ts` attaches a token to every
          // request. It is inlined into the bundle at build time here exactly as it
          // is in a deployment, which is the trap `docs/deployment.md` records for
          // Vercel — and the reason it is declared to the server that builds the
          // bundle rather than set anywhere later.
          env: {
            AGENTAUDIT_API: API,
            VITE_CLERK_PUBLISHABLE_KEY: user.publishableKey,
          },
          // Not `${API}` and not a Cloud Run URL: the app fetches same-origin paths
          // and Vite proxies them, which is what the deployment's rewrites do
          // (`vercel.json`) and why no CORS middleware exists to need testing.
          url: APP,
          reuseExistingServer: false,
          stdout: 'pipe',
          stderr: 'pipe',
          timeout: 120_000,
        },
      ],
})
