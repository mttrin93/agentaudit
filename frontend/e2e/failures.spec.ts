/**
 * The failures section, drawn in a browser from a served artefact.
 *
 * **A second spec beside the walkthrough, because the walkthrough cannot reach this
 * reading.** `harness.py` deletes every model variable before the factory runs, so the
 * bench that walk drives declares no narrative instrument, writes no sentence, and its
 * document holds the reading that says so — which the walkthrough asserts and which is
 * the honest end-to-end proof of the *absence*. The reading with blocks in it needs a
 * document a judge and a remediation tool wrote, and that is a document a walk with no
 * models and no credential cannot produce. Rather than declare a model, this serves the
 * artefact the unit tests already read — `served.fixture.ts`, produced by the bench's
 * own serialiser — over the two routes the report screen fetches.
 *
 * **So it is a render assertion and nothing more, and the file says so rather than
 * implying otherwise.** It proves what no other test in this repository proves: that
 * the blocks are on the page, that a fix informed by nothing says so where a reader
 * looks, and that the two sentences arrive under the questions they answer. It proves
 * nothing about the bench, and it is deliberately not a second walkthrough: no run is
 * started, no attestation is made, no case is sent, and nothing here signs anything.
 *
 * **Two routes are intercepted and no more.** The run's own record, because the screen
 * reads where the artefact is from it rather than from a path it builds, and the
 * artefact itself. The probes and the exchanges are left to answer `404` from the real
 * bench, which is the ordinary state of a run this process never made and the state the
 * screen already draws nothing for.
 *
 * **The artefact is loaded through the dev server rather than imported here**, and the
 * reason is a project boundary rather than a preference. `tsconfig.node.json` covers
 * this directory and resolves like Node; `tsconfig.app.json` covers `src` and resolves
 * like a bundler. A spec that imported across that line would make every relative
 * import in `src/api` fail for want of a file extension — configuration bought by a
 * test, which is the shape of change `vite.config.ts` spends its first paragraph
 * arguing against. So the browser asks Vite for the module, which is a thing Vite is
 * already serving, and what comes back is the same frozen artefact `report.test.ts`
 * reads. The shape below is what this spec reads off it and no more: an e2e assertion
 * against a key that moved should fail where a reader can see which key it was.
 */

import { expect, test } from '@playwright/test'

const FIXTURE = '/src/report/served.fixture.ts'

/** The part of the frozen artefact this spec reads off the wire, and no more. */
interface ServedFindings {
  findings: {
    findings: {
      case_id: string
      reason: string
      fix: string
      informed_by: string[]
      informed_by_stated: string
      withheld: string[]
      source_anchor: { location: string | null; stated: string }
      fix_standing: { reading: string; diff: string; stated: string }
    }[]
  }
}

const RUN = 'a-run-this-bench-never-made'

const WHERE = `/report/${RUN}`

/**
 * The run's own record, cut to what the report screen reads off it.
 *
 * Written as the JSON it goes over the wire as rather than typed against
 * `RunProgress`: what is asserted here is a rendering, and a stub carrying every field
 * of a run that was never made would be a fixture claiming to be a run. The screen
 * reads three things — where the artefact is, the sentence for a run with no artefact,
 * and the per-family counts — and those three are here.
 */
const PROGRESS = {
  statement: 'this run has a report',
  families: [],
  report: {
    path: WHERE,
    rendering: `${WHERE}/rendering`,
    signature: `${WHERE}/signature`,
    verification: `${WHERE}/verification`,
    statement: 'the artefact, its rendering and its signature',
  },
}

test('a failure, its fix, and what informed it, are on the report screen', async ({
  page,
}) => {
  // Entered at the app's own root first, so the module below is asked of the dev
  // server that is already serving it.
  await page.goto('/')
  const SERVED = (await page.evaluate(
    async (path) => (await import(path)).SERVED as unknown,
    FIXTURE,
  )) as ServedFindings

  await page.route(`**/runs/${RUN}`, (route) => route.fulfill({ json: PROGRESS }))
  await page.route(`**${WHERE}`, (route) => route.fulfill({ json: SERVED }))

  // Behind the `#`, which is where every screen in this app lives: the dev server
  // proxies `/runs` and `/report` wholesale to the bench, so a *document* request for
  // one of them is answered by the API rather than by the app (`vite.config.ts`). The
  // walkthrough reaches this screen by clicking the run's own link; this spec has no
  // run to click from, so it asks for the same address.
  await page.goto(`/#/runs/${RUN}/report`)

  const failures = page.locator('section').filter({
    has: page.getByRole('heading', { level: 2, name: 'Failures and fixes' }),
  })
  // The reading's own name is not drawn, and the standing sentences under a finding
  // are not either: this screen carries the figures and the blocks, and the sentences
  // travel in the artefact a recipient reads
  // ([ADR-0115](../../docs/adr/0115-the-report-screen-carries-the-figures-and-the-artefact-carries-the-sentences.md)).
  // What this spec asks of the page is therefore what the page draws; every sentence
  // it stopped drawing is asserted over the reading in `report.test.ts`, against the
  // same served fixture, and none of them left the payload.
  await expect(failures.getByText('explained', { exact: true })).toHaveCount(0)
  // And the two standing claims about what is under it: a model wrote these sentences
  // and would not write them again, and no figure above came from any of them. One
  // line where `A_MODEL_WROTE_THESE_SENTENCES` and two paragraphs beside it stood —
  // the same claims, consolidated, and the constants are still built and still tested
  // in `report.test.ts`. Asked for as the claims rather than as the sentence, because
  // it is the screen's own wording and this spec is not its copy editor.
  const asserts = failures.locator('p.asserts')
  await expect(asserts).toContainText('would not write the same ones again')
  await expect(asserts).toContainText('no figure above was measured from any of them')

  // Grouped by family and collapsed to begin with: n = 30 per family, so a flat list
  // is unreadable at exactly the moment it matters most. Two families in this
  // document, and the summary carries the family name and no count of what is inside.
  const leakage = failures.locator('details.family').filter({
    has: page.getByRole('heading', { level: 3, name: 'data leakage' }),
  })
  await expect(failures.locator('details.family')).toHaveCount(2)
  await expect(leakage.locator('.finding').first()).toBeHidden()

  await leakage.getByRole('heading', { level: 3, name: 'data leakage' }).click()

  // The two sentences, each under the question it answers, because two instruments
  // wrote them and neither answers the other's (ADR-0069).
  const [alone] = SERVED.findings.findings
  const first = leakage.locator('.finding').first()
  // The case, as the finding's own heading: the fix's label sits in the same line
  // beside it, so the id is asked for as the heading it starts rather than as an
  // element whose whole text it is.
  await expect(
    first.getByRole('heading', { level: 4, name: /^data-leakage-001/ }),
  ).toBeVisible()
  await expect(first.getByText('what went wrong')).toBeVisible()
  await expect(first.getByText(alone.reason)).toBeVisible()
  await expect(first.getByText('what to change')).toBeVisible()
  await expect(first.getByText(alone.fix)).toBeVisible()

  // **Proven or proposed, and no third label**, which is the one word on this block a
  // reader must not have blurred: *proven* means the bench patched a copy of the
  // caller's own checkout, re-served the target and re-attempted the case, and
  // *proposed* means it could not be tested — a plain hosted endpoint can only ever
  // carry the second, because the bench cannot restart somebody else's server
  // (ADR-0001, ADR-0073). It stays on the screen where the sentence under it does
  // not, because the sentence over the section says a fix reads proven only where the
  // bench re-attempted the case, and a word that points at has to be on the page.
  await expect(first.locator('.fix-label')).toHaveText(alone.fix_standing.reading)

  // A family whose fix the disclosure rule replaced is still a family with a block:
  // the case is on the screen and so is the sentence standing where the withheld one
  // was, which is the payload's own and says what happened (ADR-0070 §2c). Nothing
  // that was withheld is anywhere on this page.
  const denial = failures.locator('details.family').filter({
    has: page.getByRole('heading', { level: 3, name: 'disclosure denial' }),
  })
  await denial.getByRole('heading', { level: 3, name: 'disclosure denial' }).click()
  const [, , quoted] = SERVED.findings.findings
  await expect(denial.getByText(quoted.fix)).toBeVisible()
  await expect(
    denial.getByRole('heading', { level: 4, name: new RegExp(`^${quoted.case_id}`) }),
  ).toBeVisible()
  expect(quoted.withheld).toEqual(['fix'])

  // And no severity anywhere, in any of the words a reviewer UI would use for one.
  // #109 names this as out of scope precisely because every UI this borrows from has
  // one, and promptfoo's is the one already refused on the record (D3, D12).
  const drawn = ((await failures.textContent()) ?? '').toLowerCase()
  for (const graded of ['critical', 'severity', 'high risk', 'score']) {
    expect(drawn).not.toContain(graded)
  }
})
