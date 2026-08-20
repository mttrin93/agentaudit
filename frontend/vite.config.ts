/// <reference types="node" />
/**
 * The dev server, the proxy that keeps the API's deployed surface unchanged, and
 * the test runner.
 *
 * **The cross-origin problem is solved in dev tooling rather than in the API.**
 * `create_app` installs no CORS middleware, and adding one would be a change to
 * the deployed surface — a header the bench sends to every caller forever — bought
 * to make one developer's browser happy. So the dev server proxies the five
 * prefixes this app calls to the API instead, and the app fetches same-origin paths
 * with no base URL anywhere in it. In a deployment the built assets are served
 * from the same origin as the API and the same paths keep working, which is the
 * second reason to prefer this: the fetch code has no dev-only branch in it.
 *
 * The proxied prefixes are named one by one rather than proxying everything, so
 * that a route this app has no business calling does not silently start working
 * through it. `/runs` can be proxied wholesale, screens and all, because the
 * screens are behind a `#` and no document request ever carries one (`main.tsx`).
 * `/bench` is the one prefix whose subject is the instrument rather than a run: the
 * landing screen reads the gate citation from it, and there is nothing under it that
 * starts anything. `/artefacts` is proxied on the same terms as `/runs`: the screen
 * that lists them sits at the same path behind the `#`, and everything under it is a
 * read. `/gate-runs` is the one prefix through which this app can start something
 * that spends on the bench's own behalf — a gate run, its own route family and not a
 * run (ADR-0021) — and it is named separately for that reason: it is not reachable
 * by proxying `/bench`, and it should not become reachable by widening one.
 *
 * **The tests run in node and there is no browser here.** The spec expects these
 * screens to be driven by hand, and three screens do not justify a browser-driver
 * harness. What is automated is the logic behind them — the guard rules, the body
 * that goes on the wire, and what the app makes of a refusal — and none of that
 * needs a DOM. A jsdom environment would be a dependency bought so that a test
 * could assert on markup nobody reads.
 */

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const BENCH = process.env.AGENTAUDIT_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/nonces': BENCH,
      '/runs': BENCH,
      '/report': BENCH,
      '/artefacts': BENCH,
      '/bench': BENCH,
      '/gate-runs': BENCH,
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
