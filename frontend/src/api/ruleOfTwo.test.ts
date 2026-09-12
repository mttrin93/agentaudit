/**
 * That the standing on the register screen came off the wire, and was not derived.
 *
 * ADR-0092 decision 4 leaves this app one way to learn a standing — `POST
 * /rule-of-two` — and two claims about it are worth asserting without a browser:
 * that the four answers reach the route unedited, and that the five standing names
 * appear nowhere in this app's own source. The second is the grep #177 asks for,
 * written as a test so that it covers the file somebody adds next.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { RULE_OF_TWO_PATH, readRuleOfTwo } from './ruleOfTwo'

/** The five standings, in the words `scanner.RuleOfTwoStanding` names them. */
const STANDINGS = [
  'not_declared',
  'partly_declared',
  'at_most_two',
  'three_under_supervision',
  'three_unsupervised',
] as const

function answering(body: unknown) {
  const fetching = vi.fn(async (_path: string, _init?: RequestInit) =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetching)
  return fetching
}

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Every source file of this app, test files and this one's own fixtures aside. */
function appSources(from = 'src'): string[] {
  return readdirSync(from).flatMap((entry) => {
    const path = join(from, entry)
    if (statSync(path).isDirectory()) {
      return appSources(path)
    }
    if (!/\.tsx?$/.test(path) || /\.test\.tsx?$/.test(path)) {
      return []
    }
    return [path]
  })
}

describe('the reading of a candidate declaration', () => {
  it('posts the four answers as they were given, `null` included', async () => {
    // Three answers per question, so the body carries `null` rather than dropping
    // it: a field left out would be read as unstated by the API anyway, and the
    // point of asserting it is that this app is not quietly turning silence into a
    // denial on the way (ADR-0038, decision 1).
    const fetching = answering({ standing: 'at_most_two', stated: 'a sentence' })

    // Awaited rather than dispatched and read: since #248 a request is made through
    // `authed`, which asks the attended door for a token before it fetches, so the
    // call reaches the wire a microtask later than it used to.
    await readRuleOfTwo({
      processes_untrusted_input: true,
      reaches_private_data: false,
      changes_state_or_communicates: null,
      under_human_supervision: null,
    })

    const [path, init] = fetching.mock.calls[0] ?? []
    expect(path).toBe(RULE_OF_TWO_PATH)
    expect(JSON.parse(String(init?.body))).toEqual({
      processes_untrusted_input: true,
      reaches_private_data: false,
      changes_state_or_communicates: null,
      under_human_supervision: null,
    })
  })

  it('is the name and the sentence the bench wrote, edited nowhere', async () => {
    // The prose is the report's own, `NOT_A_MEASUREMENT` and all: a screen that
    // rewrote it would be a screen that could drop the line saying nothing was sent.
    answering({
      standing: 'three_unsupervised',
      stated: 'the whole sentence, unedited',
    })

    expect(
      await readRuleOfTwo({
        processes_untrusted_input: true,
        reaches_private_data: true,
        changes_state_or_communicates: true,
        under_human_supervision: false,
      }),
    ).toEqual({ standing: 'three_unsupervised', stated: 'the whole sentence, unedited' })
  })

  it('is never derived here: no standing is named in this app’s source', () => {
    // The grep ADR-0092 decision 4 asks for, as a test. A file that named one of the
    // five would be a file that could decide which to show, and the arm ordering
    // would then exist twice — in the copy nobody tests against the gold arms.
    for (const path of appSources()) {
      const source = readFileSync(path, 'utf8')
      for (const standing of STANDINGS) {
        expect(source, `${path} names the ${standing} standing`).not.toContain(standing)
      }
    }
  })
})
