/// <reference types="node" />
/**
 * The dev server, the proxy that keeps the API's deployed surface unchanged, and
 * the test runner.
 *
 * **The cross-origin problem is solved in dev tooling rather than in the API.**
 * `create_app` installs no CORS middleware, and adding one would be a change to
 * the deployed surface — a header the bench sends to every caller forever — bought
 * to make one developer's browser happy. So the dev server proxies the seven
 * prefixes this app calls to the API instead, and the app fetches same-origin paths
 * with no base URL anywhere in it. In a deployment the built assets are served
 * from the same origin as the API and the same paths keep working, which is the
 * second reason to prefer this: the fetch code has no dev-only branch in it.
 *
 * The proxied prefixes are named one by one rather than proxying everything, so
 * that a route this app has no business calling does not silently start working
 * through it. `/rule-of-two` is the newest and the narrowest: one stateless route
 * that reads four declarations against a published rule, records nothing and sends
 * nothing to anybody, which the register walk calls while an operator is still
 * answering the questions (ADR-0092). `/runs` can be proxied wholesale, screens and all, because the
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
 * **The tests here run in node, and the one browser test does not run here.**
 * `vitest` covers the logic behind the screens — the guard rules, the body that goes
 * on the wire, and what the app makes of a refusal — and none of that needs a DOM,
 * so there is still no jsdom environment: it would be a dependency bought so that a
 * test could assert on markup nobody reads. What changed with #19 is that there are
 * now tests that read the markup a person reads, and they drive a real browser
 * rather than a simulated one: `playwright.config.ts`, `frontend/e2e/`, and
 * `npm run e2e`. It is a separate runner with a separate config because it needs two
 * servers and a browser download, and `include` below keeps the two apart by
 * construction: a `.test.ts` is vitest's wherever it sits, and the `.spec.ts` files
 * under `e2e/` are Playwright's. The suffix and not the directory, because `e2e/`
 * now holds one of each — `door-user.ts` decides whether the doored walkthrough runs
 * at all and is a function over a dict, so it is covered where a function over a
 * dict is covered rather than by starting two servers to ask.
 *
 * **The dev server below is what that walkthrough serves the app with**, and the
 * proxy is why. A previewed build would answer nothing under `/runs`: the seven
 * prefixes are proxied for `server` and there is no `preview.proxy` beside them,
 * and adding one to make a test's life easier is the shape of change this docstring
 * spends its first paragraph arguing against.
 *
 * **The React Compiler is on, and it is not the Babel plugin.**
 * `@vitejs/plugin-react` 6 carries the compiler as its own `compiler` option and
 * runs it through `oxc-transform-react` — the Rust port — rather than through
 * Babel: this plugin version has no `babel` option at all to hang
 * `babel-plugin-react-compiler` off. So `compiler: true` plus that optional peer
 * dependency installed is the whole enablement. The peer is pinned to an exact
 * version rather than a caret, because `src/compiler.test.ts` asserts the shape of
 * the code this compiler emits and a compiler that emitted a different shape would
 * fail it.
 *
 * **The compiler skips, per function, in silence** — a function it cannot compile
 * is left alone, the build stays green, and the optimisation is simply not there.
 * So *enabled* and *compiling this file* are two facts and only the second one buys
 * anything. The second one is asserted rather than assumed:
 * `src/compiler.test.ts` runs the compiler's own transform over every source this
 * app ships and fails on a file that comes back with a diagnostic or without the
 * cache from `react/compiler-runtime`. The first build with the compiler on had one
 * such file, so this is not a hypothetical.
 *
 * **That skip is also why three `useCallback`s survive here.** The compiler does
 * memoise all three — checked, by compiling each one with the `useCallback` taken
 * out — but it does so only where it compiles, and a `useCallback` is ordinary
 * React that holds either way. Two of the three feed a `useEffect` that starts a
 * two-second poll, where losing the memo restarts the poll on every render and puts
 * extra HTTP on a bench that is mid-run; that is a change to what the backend sees,
 * which is the one thing this work may not do. Each call site says which case it
 * is and nothing more; the argument they share is this paragraph.
 *
 * **The Rules-of-React lint that the compiler's safety story leans on is oxlint's,
 * not ESLint's.** `.oxlintrc.json` names all twenty of oxlint's React-compiler
 * rules at `error`, and the app passes them with nothing suppressed; four were
 * already errors through the `correctness` category. The division of labour is
 * worth knowing: **lint owns the rules the compiler assumes, and the test above
 * owns whether the compiler actually ran.** No lint rule catches the syntax that
 * caused the one skip, which is why both exist.
 */

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const BENCH = process.env.AGENTAUDIT_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react({ compiler: true })],
  server: {
    proxy: {
      '/nonces': BENCH,
      '/rule-of-two': BENCH,
      '/runs': BENCH,
      '/report': BENCH,
      '/artefacts': BENCH,
      '/bench': BENCH,
      '/gate-runs': BENCH,
      '/pending-routes': BENCH,
    },
  },
  test: {
    environment: 'node',
    // The two trees this runner owns, and the suffix is what divides it from
    // Playwright's rather than the directory: a `.test.ts` is answerable in node and
    // a `.spec.ts` drives a browser. `e2e/` holds both — the suites, and the readers
    // the suites are configured from — so it is included here by suffix and
    // Playwright is pinned to the other suffix in both of its configs.
    include: ['src/**/*.test.ts', 'e2e/**/*.test.ts'],
  },
})
