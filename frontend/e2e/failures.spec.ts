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
    has: page.getByRole('heading', { level: 2, name: /^Each failure the bench/ }),
  })
  // Which of the four readings this is, as the name the payload carries and not only
  // as the sentence: a page that told the four apart by prose alone would stop telling
  // them apart the day the prose was reworded (ADR-0070 §4).
  await expect(failures.getByText('explained', { exact: true })).toBeVisible()
  await expect(failures.locator('.consequence')).toHaveText(/^not reproducible/)

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
  const [alone, reused] = SERVED.findings.findings
  const first = leakage.locator('.finding').first()
  await expect(first.getByText('data-leakage-001', { exact: true })).toBeVisible()
  await expect(first.getByText('what went wrong')).toBeVisible()
  await expect(first.getByText(alone.reason)).toBeVisible()
  await expect(first.getByText('what to change')).toBeVisible()
  await expect(first.getByText(alone.fix)).toBeVisible()
  // What this break is read against, in the record's own sentence.
  await expect(
    first.getByText('the operator declared output_filter'),
  ).toBeVisible()

  // **The assertion this spec exists for.** #113's own red: a failure with no
  // informing precedent still says so on the screen. On run one the honest answer is
  // that nothing informed the fix, and it renders as a stated absence rather than as
  // blank space — which is the precedent store's claim about itself made checkable by
  // a reader (ADR-0019).
  await expect(first.getByText(alone.informed_by_stated)).toBeVisible()
  expect(alone.informed_by).toEqual([])

  // And the other half of that claim: a fix written with earlier findings in front of
  // it names them, so a reader can tell it from one derived from this transcript
  // alone. The sentence is the record's own and this app writes no second wording of
  // it, which was #112's own review finding.
  const second = leakage.locator('.finding').nth(1)
  await expect(second.getByText(reused.informed_by_stated)).toBeVisible()
  expect(reused.informed_by).toEqual(['data-leakage-001', 'data-leakage-002'])

  // A sentence the disclosure rule replaced is on the page as the statement that it
  // was withheld, with its finding kept beside it: the case id, the family and the
  // attributed cause are the three facts a reader can check against the record
  // (ADR-0070 §2c). Nothing that was withheld is anywhere on this page.
  const denial = failures.locator('details.family').filter({
    has: page.getByRole('heading', { level: 3, name: 'disclosure denial' }),
  })
  await denial.getByRole('heading', { level: 3, name: 'disclosure denial' }).click()
  const [, , quoted] = SERVED.findings.findings
  await expect(denial.getByText('withheld — fix')).toBeVisible()
  await expect(denial.getByText(quoted.fix)).toBeVisible()
  await expect(denial.getByText(quoted.case_id, { exact: true })).toBeVisible()
  expect(quoted.withheld).toEqual(['fix'])

  // Where the failure is, when the bench ran where the code is — the line every
  // reviewer UI this section borrows from leads with, and the one thing the bench
  // could not know until the Action put it in the caller's own repository (ADR-0066,
  // ADR-0071). The compact `path:line` and the sentence that says what it is: the
  // definition site of the object that answered, and not a claim about which line is
  // at fault. Both are the payload's own strings and this app words neither.
  await expect(first.getByText('app/agent.py:61', { exact: true })).toBeVisible()
  await expect(first.getByText(alone.source_anchor.stated)).toBeVisible()

  // What the two labels mean, above the blocks and on the page under every reading —
  // including the common one, where the bench attacked a URL and every fix is
  // *proposed*. #116's third item: what *proven* asserts, spelled out where a reader
  // is, and not in a legend a screenshot loses (ADR-0073 §4).
  await expect(
    failures.getByText(/^Every fix below carries one of two labels/),
  ).toBeVisible()

  // **Proven or proposed, and no third label.** The word is the load-bearing part of
  // this block: *proven* means the bench patched a copy of the caller's own checkout,
  // re-served the target and re-attempted the case, and *proposed* means it could not
  // be tested — a plain hosted endpoint can only ever carry the second, because the
  // bench cannot restart somebody else's server. Blurring them would put an untested
  // assertion in front of a procurement reader under the word *proven* (ADR-0001,
  // ADR-0073).
  await expect(first.locator('.change > .label')).toHaveText(
    alone.fix_standing.reading,
  )
  await expect(first.getByText(alone.fix_standing.stated)).toBeVisible()
  // What it asserts, beside it rather than in a legend: one case against one patched
  // revision, and never that the family is closed (ADR-0003, ADR-0072 §5).
  expect(alone.fix_standing.stated).toContain('deliberately not about its family')

  // The change, collapsed and expandable, with the label on the header beside the
  // file and the line — the one convention worth taking from the reviewer UIs this
  // borrows from, and none of the others.
  const change = first.locator('details.diff')
  await expect(change.locator('pre')).toBeHidden()
  await change.locator('summary').click()
  await expect(change.locator('pre')).toHaveText(alone.fix_standing.diff)

  // And a fix nobody could test carries no change to expand and says why in words —
  // not a gap a reader would take for a clean result.
  await expect(second.locator('.change > .label')).toHaveText('proposed')
  await expect(second.locator('details.diff')).toHaveCount(0)

  // And no severity anywhere, in any of the words a reviewer UI would use for one.
  // #109 names this as out of scope precisely because every UI this borrows from has
  // one, and promptfoo's is the one already refused on the record (D3, D12).
  const drawn = ((await failures.textContent()) ?? '').toLowerCase()
  for (const graded of ['critical', 'severity', 'high risk', 'score']) {
    expect(drawn).not.toContain(graded)
  }
})
