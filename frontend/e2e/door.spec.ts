/**
 * The door, in a browser: a bench that refuses an unauthenticated caller, a console
 * that signs an operator in, and a request that reaches the bench with the session on
 * it.
 *
 * **The one claim `walkthrough.spec.ts` cannot make.** That suite drives a `NO_DOOR`
 * bench and asserts the honest doorless reading of every screen — the sentence naming
 * nobody, on the register screen and in the signed artefact. What it cannot reach is a
 * verified subject, because a verified subject needs a real session from a real issuer
 * and CI has no account. So this file exists and it is opt-in
 * ([ADR-0125](../../docs/adr/0125-the-doored-walkthrough-is-opt-in-and-an-absent-test-user-is-a-printed-skip.md));
 * `door-user.ts` says what it reads.
 *
 * **Started by `playwright.door.config.ts`.** `npm run e2e` does not run it: that
 * config ignores this file, this one runs nothing else, and the difference between
 * them is what the two servers are declared with.
 *
 * **What this deliberately does not do is a run.** The operator's whole path is
 * already walked end to end, once, in `walkthrough.spec.ts`, and walking it a second
 * time with a token on the requests would be thirty-one more calls to assert a header.
 * What is asserted here is the seam the door is: refused without a session, admitted
 * with one, named on the screen that collects the attestation, and same-origin on the
 * wire.
 *
 * **No credential reaches this file.** The password is read from the environment and
 * typed into the issuer's own field; nothing is logged, nothing is asserted against
 * it, and the one sentence this suite prints names variables rather than values.
 */

import { expect, test } from '@playwright/test'

import { doorUser } from './door-user.ts'

/**
 * What a bench with no door records against every request it serves
 * (`app.NOBODY_VERIFIED`), written out here for the reason `walkthrough.spec.ts`
 * writes it out: a spec that imported the console's copy would be asserting the
 * console against itself. This one asserts its *absence* — a doored console that
 * showed this sentence would be promising a recipient a name nothing verified while
 * the bench was about to record a subject.
 */
const NOBODY_VERIFIED = 'an operator this bench did not verify'

const user = doorUser(process.env)

// The documented skip. Read from the environment here rather than imported from the
// config, so that the reason a reporter prints is this file's own and so that the
// file says, on its first line of behaviour, what it needs.
test.skip(!user.declared, user.declared ? '' : user.statement)

/**
 * Sign in through the issuer's own component, with the field names it mints.
 *
 * The console does not draw this form — `<ClerkProvider>` does (`TheDoor.tsx`) — so
 * the selectors are the issuer's and not this app's. They are the two inputs a
 * password-first flow has, reached by `name` because that is the attribute the
 * provider's markup commits to across its themes.
 */
async function signIn(page: import('@playwright/test').Page): Promise<void> {
  if (!user.declared) return
  await page.goto('/')
  await page.locator('input[name="identifier"]').fill(user.emailAddress)
  await page.getByRole('button', { name: /continue/i }).click()
  await page.locator('input[name="password"]').fill(user.password)
  await page.getByRole('button', { name: /continue/i }).click()
}

test('a request with no session is refused, in the shape every refusal here takes', async ({
  request,
}) => {
  // Through the app's own origin, which is the proxy a deployment's rewrites are
  // (`vercel.json`, `vite.config.ts`) — so what is refused is the request the console
  // makes and not one aimed straight at the bench.
  const refused = await request.get('/bench/settings')
  expect(refused.status()).toEqual(401)
  // The cause as a field beside the sentence, which is ADR-0121 decision 4's shape:
  // `absent` is no token presented, and it is the reading a browser that has not
  // signed in yet earns.
  const { detail } = (await refused.json()) as {
    detail: { refusal: string; statement: string }
  }
  expect(detail.refusal).toEqual('absent')
  expect(detail.statement).not.toEqual('')
  // And the challenge, which is only ever on the four refusals about a credential.
  expect(refused.headers()['www-authenticate']).toEqual('Bearer')
})

test('a signed-in operator is named at the console and recorded by the bench', async ({
  page,
}) => {
  if (!user.declared) return

  // Every request the app makes after the door is attended, with the two facts this
  // ticket is about: it carries the session, and it is same-origin with the console.
  // Collected rather than asserted inside the handler so that a failure names the
  // request rather than failing in a listener nobody awaited.
  const BENCH = /^\/(bench|runs|artefacts|nonces|report|gate-runs|pending-routes)\b/
  const asked: { url: string; authorized: boolean }[] = []
  page.on('request', (sent) => {
    // Matched on the path and never on the origin, which is what makes the origin
    // assertion below worth making: a bundle that had learned an absolute Cloud Run
    // URL would be collected here and would fail there, where filtering by origin
    // first would have quietly collected nothing.
    if (!BENCH.test(new URL(sent.url()).pathname)) return
    asked.push({ url: sent.url(), authorized: !!sent.headers()['authorization'] })
  })

  await signIn(page)

  // The rail names whoever is signed in — the display name, which is evidence of
  // nothing and is what a person standing there reads (`console/door.theOperator`).
  await expect(page.locator('p.operator-name')).not.toBeEmpty()

  // And the screen that collects the attestation names who will be *recorded*, which
  // is the subject and not the display name. The doorless sentence must not be on
  // this screen: it is the exact string `walkthrough.spec.ts` asserts is there when
  // the bench verified nobody, and the two suites are the two readings of one claim.
  await page.goto('/#/register')
  await expect(page.getByRole('heading', { name: 'The endpoint' })).toBeVisible()
  const attesting = page.locator('div.attesting-as')
  await expect(attesting).toContainText('Attesting as')
  await expect(attesting.locator('code')).not.toBeEmpty()
  await expect(page.getByText(NOBODY_VERIFIED)).toHaveCount(0)

  // The network check the acceptance criteria ask for, off the requests the app
  // actually made: same-origin with the console — not a Cloud Run URL and not a
  // second port — and every one of them carrying the header. The base is the
  // console's own origin.
  expect(asked.length).toBeGreaterThan(0)
  const base = new URL(page.url()).origin
  for (const sent of asked) {
    expect(new URL(sent.url).origin, sent.url).toEqual(base)
    expect(sent.authorized, `${sent.url} carried no Authorization header`).toBe(true)
  }
})
