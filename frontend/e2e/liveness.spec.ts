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
  // The rail's own destinations, under the names it draws them under. A tab
  // strip truncates from the right, so the screen's own name is what has to be at
  // the left of every one of these.
  for (const [path, name] of [
    ['/#/', 'The bench'],
    ['/#/pending-routes', 'Routes to decide'],
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

test('a step of the walk arrives with the keyboard on its own heading', async ({
  page,
}) => {
  await page.goto('/#/register')
  const first = page.getByRole('heading', { name: 'The endpoint', level: 1 })
  await expect(first).toBeVisible()
  // Nobody navigated to this one — it is where the address bar landed — so the
  // keyboard is where a freshly opened document puts it, and not on the heading.
  await expect(first).not.toBeFocused()

  await completeTheEndpointStep(page)
  await page.getByRole('button', { name: 'Continue' }).click()

  // The step swaps the whole screen under one route. The heading of the one that
  // arrived is what a screen reader reads out and where the next Tab starts from.
  await expect(page.getByRole('heading', { name: 'Plant the nonce', level: 1 })).toBeFocused()
})

test('a screen reached from the rail arrives with the keyboard on its heading', async ({
  page,
}) => {
  await page.goto('/#/settings')
  await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible()

  await page.getByRole('link', { name: 'Signed artefacts' }).click()

  await expect(
    page.getByRole('heading', { name: 'Signed artefacts', level: 1 }),
  ).toBeFocused()
})

/** The run this spec watches. The bench this process talks to never made one. */
const RUN = 'a-run-this-spec-never-started'

/**
 * A run in flight, cut to what the run screen reads off it.
 *
 * Written as the JSON it goes over the wire as rather than typed against
 * `RunProgress` — the spec directory resolves like Node and `src` like a bundler, so
 * a spec that imported across that line would need configuration bought by a test
 * (`failures.spec.ts` says the same thing at length). What is asserted below is a
 * rendering, and this is the record that renders.
 */
const RUNNING = {
  run_id: RUN,
  status: 'running',
  statement: 'the suite is running against the target',
  scored: {
    reached: true,
    statement: 'the scored layer is on its fortieth attempt',
    position: { family: 'wrongful_commitment', case_id: 'wc-003', attempt: 40 },
    calls_spent: 41,
    succeeded_attempts: 2,
  },
  adaptive: {
    reached: false,
    statement: 'the adaptive layer has not started',
    position: null,
    calls_spent: 0,
    adaptive_findings: null,
  },
  transport: null,
  report: null,
  recent: [],
  families: [
    {
      family: 'wrongful_commitment',
      attempted: 40,
      of: 181,
      resisted: 38,
      succeeded: 2,
      // The verdicts in the order they came back, which is what the strip draws one
      // cell an attempt from: two got through, and where they did is a fact the
      // record keeps rather than one this screen arranges.
      answers: [
        ...Array<string>(20).fill('resisted'),
        'succeeded',
        ...Array<string>(15).fill('resisted'),
        'succeeded',
        ...Array<string>(3).fill('resisted'),
      ],
      not_run: '',
    },
  ],
}

test('a poll that stops being answered says so, over the figures it last read', async ({
  page,
}) => {
  // Answered, and then not. The hung state is a request that never comes back rather
  // than one that fails: a failure is a poll that *was* answered — with a refusal —
  // and the screen has said so since it was written. What nothing on it could say is
  // this: the answers stopped, and the figures below are as old as the silence.
  let answering = true
  await page.route(`**/runs/${RUN}`, async (route) => {
    if (answering) {
      await route.fulfill({ json: RUNNING })
    }
  })

  await page.goto(`/#/runs/${RUN}`)
  await expect(page.getByRole('heading', { name: 'Running', level: 1 })).toBeVisible()
  // The figures are dated on the screen that draws them, so a reader who came back to
  // the tab can tell how old they are without watching one arrive.
  const dated = page.locator('p.answered')
  await expect(dated).toHaveText(/Answered at \d{2}:\d{2}:\d{2}/)
  // And the phase in the tab strip, which is what a run somebody backgrounded has.
  await expect(page).toHaveTitle('Running — The run — AgentAudit')

  answering = false
  const stalled = page.locator('section.stalled')
  // Twelve seconds of silence, plus the tick that notices it.
  await expect(stalled).toBeVisible({ timeout: 30_000 })
  await expect(stalled).toContainText('stopped answering this screen')
  // Including in the tab of the reader who is not looking at it, which is the whole
  // point of putting a run's phase there.
  await expect(page).toHaveTitle('Not answering — The run — AgentAudit')
  // And the figures are still there: they are the only evidence of where the run had
  // got to, and the stamp above them is what keeps them honest.
  //
  // Asked of the family's own row rather than of the page. This run is one family, so
  // the fraction the bar over the table draws and the fraction in the row are the same
  // two numbers in two places — the bar's is the scored layer's, the row's is this
  // family's, and they coincide only because there is one family here.
  await expect(
    page.locator('table.attempts tbody tr').filter({ hasText: 'wrongful commitment' }),
  ).toContainText('40 / 181')

  // The offer is one read, made now. Nothing here restarts a run or touches a target.
  const again = page.getByRole('button', { name: 'Ask the bench now' })
  await expect(again).toBeVisible()
  answering = true
  await again.click()
  await expect(stalled).toHaveCount(0)
})
