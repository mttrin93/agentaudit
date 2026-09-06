/**
 * The forms driven by the keyboard, and a refusal driven onto a field.
 *
 * **A third spec beside the walkthrough, because these claims are about the form and
 * not about a run.** `walkthrough.spec.ts` drives the whole path once with the
 * pointer and proves the joins; what is asserted here is the surface underneath it —
 * that Enter advances a step, that a dead primary button says what it is waiting for,
 * that a `422` naming a field reaches that field, and that Enter in the settings
 * screen's number boxes sends. None of the four is observable in node: `npm test`
 * runs with no DOM by the spec's own choice, so a unit test can hold the sentence and
 * the field name and nothing can hold the rendering of either.
 *
 * **The fourth is here rather than beside the other settings tests for exactly that
 * reason.** `settings.test.ts` reads the component's source and can say the form has
 * a submit handler; whether the browser ever *runs* it is a question about implicit
 * submission and the number of fields that block it, and only a browser answers it.
 * It was answering *no* until #120, on the one screen the handler was written for.
 *
 * **No run is started and nothing is sent to anybody's endpoint.** The first two
 * tests never leave the first step. The third completes the walk against the real
 * bench — a nonce is issued, because the value on the screen has to be the bench's —
 * and then intercepts `POST /runs` with the refusal the API's own validation would
 * send. The registration never reaches the bench, so no run exists for the
 * walkthrough's `afterEach` to answer and no target is called.
 *
 * **The refusal is a `422` in FastAPI's own shape**, `detail` as a list of `loc` and
 * `msg`, and it is stubbed rather than provoked. Provoking one would mean posting a
 * body the screen's own guard refuses to build — `registrationRequest` holds the
 * rules the API holds, deliberately (`declarations.ts`) — so the only honest way to
 * see this path is to answer with what the API answers with. That the shape is the
 * API's is asserted in `bench.test.ts` against the same fixture.
 */

import { expect, test, type Page } from '@playwright/test'

import { servedTarget } from './served.ts'

/** Who this spec attests as, on a registration that is never posted. */
const IDENTITY = 'the keyboard spec'

/**
 * The field the stubbed refusal names, and the id the input under it carries.
 *
 * One string in both roles, which is the whole of ADR-0076: the `loc` path the API
 * refuses at *is* the name of the input, so this constant can be sent on the wire
 * and looked up in the DOM without anything in between translating it.
 */
const REFUSED_FIELD = 'body.cost.price_per_call'

const REFUSED_MSG = 'a price per call is a decimal, and this is not one'

/**
 * A second field on the same step, so that a refusal can name two.
 *
 * ADR-0077 is about which of two marks goes when one of them is corrected, and a
 * refusal naming one field cannot show it: the rule that retires the whole refusal
 * and the rule that retires one mark agree exactly while there is only one. Both of
 * these are drawn by the endpoint step, so both are on screen at once.
 */
const ALSO_REFUSED_FIELD = 'body.target.name'

const ALSO_REFUSED_MSG = 'a target needs a name that is not blank'

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

test('a step the walk may leave is left by pressing Enter in it', async ({ page }) => {
  await completeTheEndpointStep(page)

  // In a text field, which is where implicit submission is a thing an operator
  // expects: the URL is typed and the walk goes on without the hand leaving the
  // keyboard. Nothing here clicks Continue.
  await page.getByPlaceholder('https://staging.example/agent').press('Enter')

  await expect(page.getByRole('heading', { name: 'Plant the nonce' })).toBeVisible()
})

test('a step the walk may not leave says what it is waiting for, over the button', async ({
  page,
}) => {
  await page.goto('/#/register')
  await expect(page.getByRole('heading', { name: 'The endpoint' })).toBeVisible()

  const primary = page.getByRole('button', { name: 'Continue' })
  await expect(primary).toBeDisabled()
  // The three unmade statements and the unrecorded name, in the wording the
  // registration guard refuses in — and above the button rather than anywhere else,
  // which is the arrangement the gate walk already uses.
  const reasons = page.locator('ul.blocked')
  await expect(reasons.locator('li')).toHaveCount(4)
  await expect(reasons).toContainText('an attestation has to record who made it')
  await expect(reasons).toContainText('not attested: I am authorised to test this')
  // Bound to the button, so a reader who never sees the list is told the same thing
  // on reaching the control it is about.
  await expect(primary).toHaveAttribute(
    'aria-describedby',
    (await reasons.getAttribute('id')) ?? '',
  )

  // And the list goes when the conditions do. A reason left standing over an enabled
  // button is worse than no reason at all.
  await completeTheEndpointStep(page)
  await expect(primary).toBeEnabled()
  await expect(reasons).toHaveCount(0)
})

/**
 * The whole walk, up to the press that posts a registration the API will refuse.
 *
 * The `detail` is the caller's, in FastAPI's own shape, because the two specs below
 * differ in exactly one thing: how many fields the refusal names. Everything before
 * the press is the same three steps, and a second copy of them would be three steps
 * to keep in step with the screen rather than one.
 */
async function registerAndBeRefused(
  page: Page,
  detail: readonly { loc: readonly string[]; msg: string }[],
): Promise<void> {
  const served = servedTarget()
  await completeTheEndpointStep(page)
  await page.getByPlaceholder('the name the report will call this target').fill(served.name)
  await page.getByPlaceholder('https://staging.example/agent').fill(served.target_url)
  await page.getByPlaceholder('leave empty for a run you have not priced').fill('tuppence')
  await page.getByRole('button', { name: 'Continue' }).click()

  // The value the bench issues, declared planted. Nothing is planted anywhere: the
  // registration below never reaches the bench, so nothing will ever ask for it.
  await page.getByRole('button', { name: 'Issue a nonce' }).click()
  await expect(page.locator('p.nonce')).not.toBeEmpty()
  await page.getByRole('checkbox', { name: /in the target’s system prompt/ }).check()
  await page.getByRole('button', { name: 'Continue' }).click()

  await page.getByRole('radio', { name: /answers in text only/ }).check()
  await page.route('**/runs', (route) => route.fulfill({ status: 422, json: { detail } }))
  await page.getByRole('button', { name: 'Register the target' }).click()
}

test('a 422 naming a field marks that field and says why under it', async ({ page }) => {
  await registerAndBeRefused(page, [
    { loc: ['body', 'cost', 'price_per_call'], msg: REFUSED_MSG },
  ])

  // Back on the step that draws the field, which is two steps behind where the
  // registration was posted from: a message bound to an input the operator cannot
  // see is the page-level block this replaced.
  await expect(page.getByRole('heading', { name: 'The endpoint' })).toBeVisible()
  const refused = page.locator(`[id="${REFUSED_FIELD}"]`)
  await expect(refused).toHaveAttribute('aria-invalid', 'true')
  await expect(refused).toBeFocused()
  // The sentence the API wrote, under the field it wrote it about, and cited by the
  // field so that a screen reader announces the two together.
  const said = page.locator(`[id="${REFUSED_FIELD}.refused"]`)
  await expect(said).toHaveText(REFUSED_MSG)
  await expect(refused).toHaveAttribute('aria-describedby', `${REFUSED_FIELD}.refused`)
  // And the bench's own sentence is still over the form: a refusal names a field or
  // it does not, and either way it says what happened to the registration.
  await expect(page.locator('section.refusal')).toContainText(REFUSED_MSG)
})

test('a corrected field loses its mark, and the last mark takes the sentence with it', async ({
  page,
}) => {
  await registerAndBeRefused(page, [
    { loc: ['body', 'cost', 'price_per_call'], msg: REFUSED_MSG },
    { loc: ['body', 'target', 'name'], msg: ALSO_REFUSED_MSG },
  ])

  const price = page.locator(`[id="${REFUSED_FIELD}"]`)
  const name = page.locator(`[id="${ALSO_REFUSED_FIELD}"]`)
  const sentence = page.locator('section.refusal')
  await expect(price).toHaveAttribute('aria-invalid', 'true')
  await expect(name).toHaveAttribute('aria-invalid', 'true')
  await expect(sentence).toContainText(REFUSED_MSG)

  // ADR-0077: a mark is retired by the edit and not by the value, so this asserts
  // nothing about whether `0.02` is a price the API would now take. It is an edit,
  // and the bench is the only thing that decides what it thinks of the new one.
  await price.fill('0.02')
  await expect(price).not.toHaveAttribute('aria-invalid')
  await expect(price).not.toHaveAttribute('aria-describedby')
  await expect(page.locator(`[id="${REFUSED_FIELD}.refused"]`)).toHaveCount(0)

  // And only that one. The other field was refused about a value that has not
  // changed, and the sentence stands while any mark it arrived with is standing.
  await expect(name).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator(`[id="${ALSO_REFUSED_FIELD}.refused"]`)).toHaveText(
    ALSO_REFUSED_MSG,
  )
  await expect(sentence).toContainText(REFUSED_MSG)

  // The last mark takes the sentence with it: nothing on this screen is still
  // refused, so there is nothing left for the block over the form to be about.
  await name.fill('a name this spec never posts')
  await expect(name).not.toHaveAttribute('aria-invalid')
  await expect(page.locator(`[id="${ALSO_REFUSED_FIELD}.refused"]`)).toHaveCount(0)
  await expect(sentence).toHaveCount(0)
})

test('Enter in one of the settings screen’s number boxes sends what it now reads', async ({
  page,
}) => {
  await page.goto('/#/settings')
  // The three whole numbers, and it is the *three* that make this a test rather than
  // a formality: a form with no submit control implicitly submits only when exactly
  // one field blocks implicit submission, and a `type="number"` is such a field. So
  // the handler this form has been given cannot fire on the screen it is on unless
  // the form also has a default button.
  const numbers = page.locator('form.tuning input[type="number"]')
  await expect(numbers.first()).toBeVisible()
  expect(await numbers.count()).toBeGreaterThan(1)

  // Nothing is typed, so no settling timer is pending and the only thing that can
  // send is the keypress. A test that changed a value first would pass on the 400ms
  // debounce and prove nothing about Enter.
  const sent = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' && request.url().includes('/bench/settings'),
  )
  await numbers.first().press('Enter')
  await sent
})
