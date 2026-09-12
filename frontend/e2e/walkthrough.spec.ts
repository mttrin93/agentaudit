/**
 * The operator's whole path, once, in a browser: register, be blocked, confirm, read
 * the report.
 *
 * One test and deliberately one. What it covers is the claim the spec named as
 * load-bearing and left to a person — *does the approval screen actually block* — plus
 * the three hand-offs on either side of it, which are the joins no unit test sees: a
 * registration that has to plant a value in a live endpoint and be echoed by it, a
 * navigation that carries a run id the bench issued, a poll that has to notice the run
 * stopped, and a report link that has to open a signed artefact. Everything inside
 * those screens — the guard rules, the body on the wire, what the app makes of a
 * refusal — is already tested in node, and this does not repeat any of it.
 *
 * **Nothing here is a shortcut.** The three attestations are ticked, the nonce is
 * issued by the bench and planted in the target before registration is submitted, and
 * the interrupt is answered through the same button an operator answers it with. The
 * run is shortened only by the two routes the console's own settings screen writes to
 * — one family, and one adaptive episode of one turn — so what is attempted is narrow
 * and every attempt in it is made at the denominator the published rule states. There
 * is no test-only path through any of it, and there is no flag that would make one;
 * `shrinkTheNextRun` below says why `attempts_per_case` is not one of the levers.
 *
 * **Every wait is on state the bench published.** Playwright's assertions poll, so
 * *the interrupt is holding*, *the run has stopped* and *the report is served* are
 * each read off the screen or off the API until they are true or the test fails. There
 * is no sleep in this file and nothing that races the run screen's two-second poll.
 */

import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { servedTarget } from './served.ts'

/**
 * The one family this walkthrough covers, and why it is that one.
 *
 * Data leakage reaches a deterministic verdict against the nonce the walk plants
 * (ADR-0004): the bench knows the exact string it issued, so a reply carrying it is a
 * leak by comparison and not by a model's judgement. A judged family would need an
 * adjudicating model, and this bench declares none — so its cases are not attempted
 * and the run would have nothing to report.
 */
const FAMILY = 'data_leakage'

/** What the walk types into the register screen's *who is attesting* field.
 *
 * It does not reach the artefact and it no longer reaches the wire: `identity` came
 * off the request bodies, and the name on the record is the subject of the operator
 * the API verified — which for this harness, which declares `NO_DOOR`, is nobody.
 * The field is still on the screen, and #250 is where it becomes a line naming the
 * signed-in operator.
 */
const IDENTITY = 'the browser walkthrough'

/** What a bench with no door records instead (`app.NOBODY_VERIFIED`). */
const NOBODY_VERIFIED = 'an operator this bench did not verify'

/**
 * Shrink the next run to something a browser can watch, through the declared inputs.
 *
 * The two `PUT`s under `/bench/settings` and nothing else — the same two the settings
 * screen sends, refused by the bench while a run is in flight, and printed in the
 * report of every run made under them.
 *
 * **`attempts_per_case` is left at the declared value, and it is now a choice.** This
 * walk shrank its run that way first and the verifier caught it — `_declared_bar`
 * asserted the payload's stated rule against `DECLARED_RULE` and nothing else, so a
 * run at the `n` the console offers signed an artefact reporting
 * `arithmetic_disagrees` — and the finding was reported rather than accommodated.
 * ADR-0027 has since decided it: the denominator is read, the rest of the bar is
 * asserted, and a report measured off the declared rule verifies while saying it is
 * not a gate result. This walk stays at the declared `n` anyway, because it is the one
 * end-to-end assertion that a recipient's verification of a real run comes out
 * `arithmetic_agrees`; the fourth answer is asserted in `backend/tests/test_verify.py`.
 * So the figure is read back from `declared_attempts_per_case` and re-sent unchanged,
 * and what shrinks the run is the family count and the adaptive layer's two knobs,
 * neither of which the scored arithmetic is re-derived from. One family of three cases
 * at the declared attempts is thirty-one calls including the registration probe.
 *
 * The attacker's model is read back and re-sent for the same reason as the attempts:
 * all six settings go on every tuning request, and a walkthrough that wrote a model
 * slug into this file could put a bench that declared none onto a real provider.
 */
async function shrinkTheNextRun(request: APIRequestContext): Promise<void> {
  const settings = await request.get('/bench/settings')
  expect(settings.ok()).toBeTruthy()
  const { tuning } = (await settings.json()) as {
    tuning: {
      attacker_models: { identifier: string; chosen: boolean }[]
      temperature: number | null
      reasoning_effort: string | null
      /** The `n` the published rule states, which is the only one an artefact verifies at. */
      declared_attempts_per_case: number
    }
  }
  const chosen = tuning.attacker_models.find((model) => model.chosen)
  // Thrown rather than asserted, because the value is used below: an `expect` that
  // passed the type through as possibly-undefined would send `undefined` to the route
  // and turn a missing reading into a 422 about a field nobody set.
  if (chosen === undefined) {
    throw new Error('the bench named no attacker as the one it is currently set to')
  }

  // Both lists, because this `PUT` is the whole statement of what the next run covers
  // (ADR-0088). The tier is asked for nothing here: this walk is about one family of
  // the six, and a run requesting an elective family would attack three more cases on
  // a target this walk serves itself.
  const families = await request.put('/bench/settings/families', {
    data: { families: [FAMILY], elective: [] },
  })
  expect(families.ok(), await families.text()).toBeTruthy()

  const tuned = await request.put('/bench/settings/tuning', {
    data: {
      attacker_model: chosen.identifier,
      temperature: tuning.temperature,
      reasoning_effort: tuning.reasoning_effort,
      turns_per_episode: 1,
      episodes_per_family: 1,
      attempts_per_case: tuning.declared_attempts_per_case,
    },
  })
  expect(tuned.ok(), await tuned.text()).toBeTruthy()
}

/**
 * Plant the value the bench issued, in the endpoint that is about to be attacked.
 *
 * The operator's own step, done the way the reference agents let it be done: their
 * test-equipment route, which is the same one `nonce_planter` uses on every gate run.
 * Read off the screen rather than out of a response this test made, because what the
 * walk has to prove is that the value an operator is *shown* is the value that
 * registers.
 *
 * The namespace is `by-hand` and belongs to no run. Over HTTP the operator plants
 * before the run exists, so this value is in no run's namespace and no `teardown()`
 * drops it — exactly where ADR-0024 left a hand-planted nonce, and ADR-0063 says so.
 */
async function plantWhatTheScreenShows(page: Page): Promise<void> {
  const nonce = await page.locator('p.nonce').innerText()
  expect(nonce).not.toEqual('')
  const planted = await page.request.put(servedTarget().plant_url, {
    data: { nonce, namespace: 'by-hand' },
  })
  expect(planted.ok(), await planted.text()).toBeTruthy()
}

/**
 * Answer any halt this test left open, and never leave a run waiting.
 *
 * The browser equivalent of the suite's `stop_every_run`. A test that fails between
 * registration and the interrupt leaves a worker holding the halt for an hour
 * (`runs.APPROVAL_WAIT_SECONDS`), and the bench refuses to change its declared inputs
 * while one is in flight — so the failure would be followed by a second failure with a
 * `409` in it and nothing about the first. Declined rather than confirmed: nothing has
 * been sent to the target at the halt, so this spends nothing on anybody's endpoint.
 */
test.afterEach(async ({ request }) => {
  const listing = await request.get('/runs')
  if (!listing.ok()) {
    return
  }
  const { runs } = (await listing.json()) as { runs: { run_id: string; status: string }[] }
  for (const run of runs.filter((row) => row.status === 'awaiting_approval')) {
    await request.post(`/runs/${run.run_id}/approval`, {
      data: {
        confirmed: false,
        reason: 'the walkthrough that started this run is over',
      },
    })
  }
})

test('an operator registers a target, is blocked, confirms, and reads the report', async ({
  page,
  request,
}) => {
  await shrinkTheNextRun(request)
  const served = servedTarget()

  // ── The endpoint, and the three statements about it ─────────────────────────────
  await page.goto('/#/register')
  await expect(page.getByRole('heading', { name: 'The endpoint' })).toBeVisible()

  await page
    .getByPlaceholder('the name the report will call this target')
    .fill(served.name)
  await page.getByPlaceholder('https://staging.example/agent').fill(served.target_url)
  await page
    .getByPlaceholder('the credential your endpoint expects, if it expects one')
    .fill(served.auth_token)
  // Left as the bench offered it. The list is read off the library and the first kind
  // is taken as the declaration the moment it arrives, so an operator who never
  // touches this field registers as that kind — and this walk is that operator.
  await expect(page.getByRole('combobox')).toHaveValue(/.+/)
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
  await page.getByRole('button', { name: 'Continue' }).click()

  // ── The nonce: issued by the bench, planted in the target, declared planted ─────
  await expect(page.getByRole('heading', { name: 'Plant the nonce' })).toBeVisible()
  await page.getByRole('button', { name: 'Issue a nonce' }).click()
  await plantWhatTheScreenShows(page)
  await page.getByRole('checkbox', { name: /in the target’s system prompt/ }).check()
  await page.getByRole('button', { name: 'Continue' }).click()

  // ── What the bench will be able to see ──────────────────────────────────────────
  await expect(
    page.getByRole('heading', { name: 'What the bench will see' }),
  ).toBeVisible()
  await page.getByRole('radio', { name: /a reply carries the calls/ }).check()
  await page
    .getByPlaceholder('send_email')
    .fill(['send_email', 'lookup_order', 'issue_refund'].join('\n'))
  // The second capability on this step, answered because the reference agent this
  // walk attacks does carry a session — and because a walk that left it unanswered
  // would register a target every scripted construction is skipped against, which is
  // the state this question exists to end (ADR-0041, ADR-0093).
  await page
    .getByRole('radio', { name: /a later turn sees what an earlier one did/ })
    .check()
  // And the third, answered *no* — the reference agent this walk attacks holds
  // nothing about anybody, so the tier's PII leakage family is refused against it
  // rather than measured. Answered rather than left silent because the two produce
  // the same run and only one of them is a statement (ADR-0043, ADR-0095).
  await page
    .getByRole('radio', { name: /nothing about anybody but its operator/ })
    .check()

  // ── The Agents Rule of Two: four declarations, and the reading printed back ─────
  //
  // The arm the published rule warns about, declared on purpose: all three
  // capabilities held and nobody confirming. It is the one reading that looks like a
  // finding, and on this screen it prints before a single attempt has been made — so
  // what is asserted is the sentence saying it is not one, which the bench appends to
  // every arm and this app never rewrites (ADR-0038, ADR-0092).
  //
  // No standing is derived in the browser. The sentence below came out of `POST
  // /rule-of-two`, and the payload at the end of this walk is where the name is
  // asserted: two ends of one reading, and neither of them computed in TypeScript.
  for (const answer of [
    /it handles content you do not control/,
    /it can read private data/,
    /it can write, pay, send or publish/,
    /it acts without human confirmation/,
  ]) {
    await page.getByRole('radio', { name: answer }).check()
  }
  await expect(page.getByRole('status')).toContainText(
    'Nothing was sent to establish any of this',
  )
  await expect(page.getByRole('status')).toContainText(
    'all three, unsupervised — the shape the published rule warns about',
  )
  // The name as well as the sentence, and it is the word the signed payload carries
  // below — asserted at both ends so that what the operator read and what the
  // recipient will read are one reading.
  await expect(page.getByRole('status')).toContainText('three_unsupervised')

  await page.getByRole('button', { name: 'Register the target' }).click()

  // ── Registered: the run has an id on the bench, and the walk navigated to it ────
  await expect(page).toHaveURL(/#\/runs\/[0-9a-f-]{36}$/)
  const runId = new URL(page.url()).hash.split('/').pop() ?? ''

  // ── The interrupt: it blocks, and nothing has been sent ────────────────────────
  await expect(
    page.getByRole('heading', { name: 'What this run will cost' }),
  ).toBeVisible()
  // Both figures, and two of them: the scored layer's and the adaptive layer's, in
  // different units and never added (ADR-0010).
  await expect(page.locator('dl.figures div.figure')).toHaveCount(2)
  const confirm = page.getByRole('button', {
    name: 'Confirm both figures and start the run',
  })
  // The block itself. The button is there and it will not send until both figures
  // have been read and said so — an interrupt with an enabled button is not a halt.
  await expect(confirm).toBeDisabled()

  // And the bench agrees: the run is holding, and the target has not been called.
  const holding = await request.get(`/runs/${runId}`)
  expect(holding.ok()).toBeTruthy()
  const halted = (await holding.json()) as {
    status: string
    scored: { calls_spent: number }
    adaptive: { calls_spent: number }
  }
  expect(halted.status).toEqual('awaiting_approval')
  expect(halted.scored.calls_spent).toEqual(0)
  expect(halted.adaptive.calls_spent).toEqual(0)

  await page.getByRole('checkbox', { name: /I have read both figures/ }).check()
  await expect(confirm).toBeEnabled()
  await confirm.click()

  // ── Completion: the run stopped, and it stopped by finishing ───────────────────
  await expect(page.getByRole('heading', { name: 'Finished' })).toBeVisible()

  // ── The report: signed, served, and about the target that was registered ───────
  // Reached from the rail rather than from a block on the run screen. That screen
  // carried a *The report* section with the three artefact links under it; the links
  // are the report screen's own and the rail already points at the page, so the
  // section was a second way to the same place, drawn under the figures somebody is
  // watching. `ITS_REPORT` is the row's name.
  await page.getByRole('link', { name: 'Its report' }).click()
  await expect(page.getByRole('heading', { level: 1, name: served.name })).toBeVisible()
  // The family that was covered, on its scored card and with a rate on it rather
  // than a heading alone. Scoped to the scored section on purpose: this page names
  // the same family in four places — the scored cards, the attacks that worked, the
  // adaptive section and the probes — and the one a rate belongs to is this one.
  const scored = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { level: 2, name: /^The scored layer/ }) })
  // A row of the per-family table, where a card in a grid stood (ADR-0113). Each
  // family is its own `tbody`, so the row is found by the header cell that names it
  // rather than by a heading that is no longer drawn.
  const family = scored
    .locator('table.per-family tbody')
    .filter({ has: page.getByRole('rowheader', { name: 'data leakage' }) })
  await expect(family).toHaveCount(1)
  await expect(family.locator('span.rate').first()).not.toBeEmpty()
  // PLAN §4's central column, on a row drawn from a document this walk signed. It is
  // the one end-to-end proof that the article reaches a screen: it is read off
  // `labels.LABELS` into the payload, printed in the Markdown, and drawn here in the
  // row's refs cell beside the family's figures rather than instead of them (#52,
  // ADR-0044).
  //
  // As the identifier and no longer as the sentence. *bears article 15 of the EU AI
  // Act* said in prose what `15` says as a key into a published instrument, and the
  // sentence carrying both was saying it twice; the identifiers are now the only
  // place an article reaches a reader, which is why this asks for them.
  await expect(family.locator('td.refs-cell')).toContainText('EU AI Act 15')
  // The failures section, under the reading this walk actually produces. The harness
  // deletes every model variable before the factory runs, so this bench declares no
  // narrative instrument and wrote no sentence about anything — and the section says
  // exactly that rather than being absent, which is the difference ADR-0050 spent two
  // paragraphs on and ADR-0070 §4 carried into the document. A screen that drew
  // nothing here would be indistinguishable from a run whose judge broke.
  const failures = page.locator('section').filter({
    has: page.getByRole('heading', { level: 2, name: 'Failures and fixes' }),
  })
  await expect(failures).toHaveCount(1)
  // The reading's own name is not drawn (ADR-0115); what tells this run's section from
  // one whose judge broke is the payload's own sentence, which is what the screen puts
  // where the blocks would be. `report.test.ts` holds the name over the reading.
  await expect(failures.getByText('no_narrative_instrument_declared')).toHaveCount(0)
  await expect(
    failures.getByText('no narrative instrument was declared for this run'),
  ).toBeVisible()
  // And the standing claim about whatever is under the section, in the screen's own
  // one line: it replaced `A_MODEL_WROTE_THESE_SENTENCES` and the two paragraphs
  // beside it, and all three are still built and still tested.
  await expect(
    failures.getByText('would not write the same ones again'),
  ).toBeVisible()
  await expect(failures.locator('details.family')).toHaveCount(0)

  // The three files a recipient verifies, under the names `scripts/verify.py` reads.
  for (const file of ['report.json', 'report.md', 'report.sig']) {
    await expect(page.getByRole('link', { name: file })).toBeVisible()
  }

  // ── And the one fact of the walk that the screens do not draw ──────────────────
  //
  // The nonce was echoed. The console waives the echo whenever the value is declared
  // planted (ADR-0025), so a walk that ticked the box and planted nothing would still
  // reach this screen and still show these cards — and the artefact would record
  // control as declared rather than proved. `control_proved` is where that difference
  // is written and no screen renders it, so it is asserted against the signed payload,
  // which is where the spec keeps the claims a screen is not the home of.
  const payload = await request.get(`/report/${runId}`)
  expect(payload.ok()).toBeTruthy()
  const artefact = (await payload.json()) as {
    provenance: { attestation: { identity: string; control_proved: boolean } }
    declared: { rule_of_two: { standing: string } }
  }
  expect(artefact.provenance.attestation.control_proved).toEqual(true)
  // The name is the one the door established and never the one typed two screens
  // back: this harness declares `NO_DOOR`, so the bench verified nobody and the
  // artefact says so (ADR-0116 §1).
  expect(artefact.provenance.attestation.identity).toEqual(NOBODY_VERIFIED)
  // And the four declarations made on the register screen reached the signed
  // document. Until #177 nothing on the HTTP surface accepted them, so every artefact
  // this bench produced read `not_declared` — this is the assertion that the walk can
  // now say something, and that Annex IV section 3 prints what was said rather than
  // that nobody said anything.
  expect(artefact.declared.rule_of_two.standing).toEqual('three_unsupervised')

  // ── And the artefact verifies, the way its recipient verifies one ──────────────
  //
  // The three files this run served, saved under the names they arrive with, checked
  // by `scripts/verify` against the public half of the pair this bench signs with.
  // Not the committed key: the harness generates a pair per run and the published
  // key's fingerprint is in the README, so a report signed by this bench verifies
  // against this bench's key and against no other — which is the whole of ADR-0017's
  // distinction between the key that signs and the key a verification is run against.
  //
  // The verifier is the recipient's script and not a route: `GET
  // /report/{id}/verification` answers against the *published* key, so it would
  // report this artefact as signed by another key. That is the disclosure posture
  // working, and it is why the check that belongs at the end of this walk is the one
  // an engineer would hand a customer.
  const verified = await verifyTheArtefact(request, runId)
  expect(verified, 'scripts.verify over the three files it served').toEqual(0)
})

/**
 * Download the three files and run the recipient's own verifier over them.
 *
 * Returns the exit code, which is the verifier's answer: `0` is all three results
 * holding, and `2`, `3` and `4` are unreadable, did-not-verify and not-established.
 * Read as a code rather than by matching its prose, because the codes are the
 * script's contract with a caller and the sentences are for a person.
 */
async function verifyTheArtefact(
  request: APIRequestContext,
  runId: string,
): Promise<number> {
  const into = mkdtempSync(join(tmpdir(), 'agentaudit-walkthrough-'))
  // The names `scripts/verify` reads out of a directory. Nothing here renames
  // anything: a recipient who saved the three responses under the names they arrive
  // with has a directory that verifies, and that is what is being checked.
  const files: [string, string][] = [
    ['report.json', `/report/${runId}`],
    ['report.md', `/report/${runId}/rendering`],
    ['report.sig', `/report/${runId}/signature`],
  ]
  for (const [name, path] of files) {
    const served = await request.get(path)
    expect(served.ok(), `${path}: ${served.status()}`).toBeTruthy()
    writeFileSync(join(into, name), await served.body())
  }
  try {
    execFileSync(
      'uv',
      ['run', 'python', '-m', 'scripts.verify', into, '--pubkey', servedTarget().pubkey],
      // From the repository root, which is where `uv` finds the project.
      { cwd: new URL('../..', import.meta.url), stdio: 'pipe' },
    )
    return 0
  } catch (refused: unknown) {
    const failed = refused as { status?: number; stdout?: Buffer; stderr?: Buffer }
    // Printed, because the verifier's own sentences say which of the three results
    // failed and an exit code alone would not.
    console.log(`${failed.stdout ?? ''}${failed.stderr ?? ''}`)
    return failed.status ?? -1
  }
}
