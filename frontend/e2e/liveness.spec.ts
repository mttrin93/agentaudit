/**
 * What the console says when it changes screen, and what a polling run says about
 * itself while nothing is arriving.
 *
 * **A fourth spec, and none of it is observable in node.** `npm test` runs with no
 * DOM by the spec's own choice (`vite.config.ts`), so a unit test can hold the rule
 * that decides a title and the rule that decides a poll has stopped answering — both
 * of which have one — and nothing can hold the title a browser actually shows, the
 * element a browser actually focuses, or the block a screen draws when the answers
 * stop arriving.
 *
 * **No run is started and nothing is sent to anybody's endpoint.** The first two
 * tests never leave the registration walk's first two steps. The third never asks
 * the bench for anything: the run it watches is a run this process never made, and
 * `GET /runs/{id}` is answered in the browser with a record of a run in flight —
 * first as a bench that is answering, then as one that has stopped.
 */

import { expect, test, type Page } from '@playwright/test'

/** Who this spec attests as, on a registration that is never posted. */
const IDENTITY = 'the liveness spec'

/** The three statements ticked and the name recorded, which is what holds step one. */
async function completeTheEndpointStep(page: Page): Promise<void> {
  await page.goto('/#/register')
  await expect(page.getByRole('heading', { name: 'The endpoint' })).toBeVisible()
  await page
    .getByPlaceholder('recorded against every one of the three statements')
    .fill(IDENTITY)
  for (const statement of [
    /authorised to test this endpoint/,
    /staging or sandbox environment/,
    /consume my own inference budget/,
  ]) {
    await page.getByRole('checkbox', { name: statement }).check()
  }
}

test('every screen’s title names the screen, and a step of the walk names the step', async ({
  page,
}) => {
  // The four the rail goes to, under the names the rail draws them under. A tab
  // strip truncates from the right, so the screen's own name is what has to be at
  // the left of every one of these.
  for (const [path, name] of [
    ['/#/', 'The bench'],
    ['/#/artefacts', 'Signed artefacts'],
    ['/#/settings', 'Settings'],
  ] as const) {
    await page.goto(path)
    await expect(page).toHaveTitle(`${name} — AgentAudit`)
  }

  // And the walk's step in front of the screen's name, because the registration
  // screen is four screens under one route and the step is the only thing that tells
  // them apart — in a tab strip as much as on the page.
  await page.goto('/#/register')
  await expect(page).toHaveTitle('The endpoint — Register a target — AgentAudit')
  await completeTheEndpointStep(page)
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page).toHaveTitle('Plant the nonce — Register a target — AgentAudit')
})
