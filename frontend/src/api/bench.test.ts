/**
 * What goes on the wire, and what comes back when the bench says no.
 *
 * The body is asserted field by field because it is a contract with
 * `backend/api/app.py` rather than a shape this app may choose: `StartRunRequest`
 * defaults almost nothing, and a renamed or dropped field arrives as a `422` a
 * long way from the screen that has to explain it. The refusals are asserted
 * because ADR-0007's guard is a step somebody completes — an exception thrown out
 * of a fetch would lose the bench's own sentence about what to do next, which is
 * the only part of a refusal an operator can act on.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { nothingDeclared, registrationRequest } from '../register/declarations'
import { issueNonce, startRun, type StartRunBody } from './bench'
import { BENCH_FAMILIES_PATH, coverFamilies } from './settings'

const NONCE = 'AGENTAUDIT-CANARY-0011AABB'

/** One complete set of declarations, the way an operator leaves the last step. */
function declared() {
  return {
    ...nothingDeclared(),
    name: 'staging support agent',
    url: 'https://staging.example/agent',
    auth_token: 'bearer-token',
    agent_type: 'customer support',
    sends: 3,
    identity: 'operator',
    attested: {
      authorised_to_test: true,
      not_production: true,
      accepts_provider_policy_and_cost: true,
    },
    exposes_tool_calls: true,
    retains_session_state: true,
    holds_personal_records: true,
    declared_tools: ['send_email', '  issue_refund  ', ''],
    price_per_call: '0.002',
    currency: 'USD',
    note_planted: true,
    nonce: NONCE,
    nonce_planted: true,
    // Two of the four answered and two left at *not stated*, so the body below pins
    // all three answers rather than only the two a boolean could carry.
    processes_untrusted_input: true,
    reaches_private_data: false,
  }
}

/** The body a completed walk produces. Blocked here would be a bug in the fixture. */
function bodyOf(): StartRunBody {
  const request = registrationRequest(declared())
  if (request.kind !== 'ready') {
    throw new Error(`the fixture is incomplete: ${request.missing.join('; ')}`)
  }
  return request.body
}

function answering(status: number, body: unknown) {
  const fetching = vi.fn(async (_path: string, _init?: RequestInit) =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
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

describe('the registration this screen posts', () => {
  it('is the body POST /runs declares, field for field', () => {
    expect(bodyOf()).toEqual({
      target: {
        name: 'staging support agent',
        url: 'https://staging.example/agent',
        auth_token: 'bearer-token',
        agent_type: 'customer support',
        exposes_tool_calls: true,
        // The capability every scripted construction requires. Without it on the
        // wire the fixed multi-turn half of the scored layer is skipped against
        // this target, whatever the selection says (ADR-0041, ADR-0054).
        retains_session_state: true,
        // What the tier's PII leakage family reads a record out of. Without it on
        // the wire the family is withdrawn before an attempt is spent, whatever the
        // tier was asked for (ADR-0043, ADR-0095).
        holds_personal_records: true,
        declared_tools: ['send_email', 'issue_refund'],
        sends: 3,
        // The Agents Rule of Two's four declarations, and `null` is on the wire
        // rather than omitted: the API defaults an absent field to *unstated* too,
        // so dropping it would post the same registration and would make a screen
        // that asked and got silence indistinguishable from one that never asked
        // (ADR-0038, ADR-0092).
        processes_untrusted_input: true,
        reaches_private_data: false,
        changes_state_or_communicates: null,
        under_human_supervision: null,
      },
      attestation: {
        identity: 'operator',
        authorised_to_test: true,
        not_production: true,
        accepts_provider_policy_and_cost: true,
      },
      nonce: NONCE,
      cost: { price_per_call: '0.002', currency: 'USD' },
      note_planted: true,
      // Both sent on every body and never omitted. The bench's default is the guard
      // on each, so a waiver that could be had by leaving a field out is one nobody
      // made — and they are two fields because the bench reads two different things
      // off them: the leakage family from the first, the echo guard from the second
      // (ADR-0024). One tick sets both: a value declared planted is a run that may
      // start without the echo, because the target that refuses to repeat it is the
      // case the second field exists for.
      nonce_planted: true,
      echo_waived: true,
    })
  })

  it('goes to /runs as JSON, same-origin, and returns the run that is holding its interrupt', async () => {
    const fetching = answering(202, {
      run_id: 'run-1',
      status: 'awaiting_approval',
      statement: 'halted at the approval interrupt',
      estimate: {},
      spent: { scored: 0, adaptive: 0 },
      cases: 18,
      families_not_run: {},
    })

    const outcome = await startRun(bodyOf())

    expect(fetching).toHaveBeenCalledTimes(1)
    const [path, init] = fetching.mock.calls[0]
    expect(path).toBe('/runs')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual(bodyOf())
    expect(outcome).toEqual({
      kind: 'registered',
      run: expect.objectContaining({ run_id: 'run-1', status: 'awaiting_approval' }),
    })
  })
})

describe('a registration the bench refuses', () => {
  it('is an outcome carrying the bench’s own sentence, not an exception', async () => {
    const refusal =
      'this bench never issued that nonce, so no run may start against it. ' +
      'Register the target first'
    answering(422, { detail: refusal })

    const outcome = await startRun(bodyOf())

    expect(outcome).toEqual({ kind: 'refused', statement: refusal, fields: [] })
  })

  it('keeps the field name when the refusal is the API’s own validation', async () => {
    answering(422, {
      detail: [{ loc: ['body', 'cost', 'price_per_call'], msg: 'not a price' }],
    })

    const outcome = await startRun(bodyOf())

    expect(outcome.kind).toBe('refused')
    expect(outcome.kind === 'refused' && outcome.statement).toContain(
      'body.cost.price_per_call',
    )
  })

  it('names the field the API refused, in the path an input is named by', async () => {
    // The convention ADR-0076 settles: an input is named by the `loc` path the API
    // would refuse it at, joined with dots and not edited on the way. The screen
    // marks the input with this id invalid and prints this message under it, so a
    // rejection lands on the field it names rather than at the top of the page.
    answering(422, {
      detail: [{ loc: ['body', 'cost', 'price_per_call'], msg: 'not a price' }],
    })

    const outcome = await startRun(bodyOf())

    expect(outcome.kind === 'refused' && outcome.fields).toEqual([
      { field: 'body.cost.price_per_call', msg: 'not a price' },
    ])
  })

  it('names no field when the refusal is the bench’s own sentence about the run', async () => {
    // A raised `HTTPException` is about the registration and not about a field —
    // the nonce was never issued, a run is already in flight — and there is no
    // input on the walk it could be pinned to. An empty list rather than a guess:
    // the sentence is shown where it already is, over the whole form.
    answering(422, { detail: 'this bench never issued that nonce' })

    const outcome = await startRun(bodyOf())

    expect(outcome.kind === 'refused' && outcome.fields).toEqual([])
  })

  it('says a bench that never answered is a different fact from one that refused', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_path: string, _init?: RequestInit) =>
        Promise.reject(new Error('connection refused')),
      ),
    )

    const outcome = await startRun(bodyOf())

    expect(outcome.kind).toBe('unreachable')
    // The nonce is spent either way — `start` discards it before it does anything
    // else — so the operator is told to plant the next one rather than to retry.
    expect(outcome.kind === 'unreachable' && outcome.statement).toContain(
      'Treat the nonce as spent',
    )
  })
})

describe('issuing a nonce', () => {
  it('carries the value, the probe that will ask for it, and what it is for', async () => {
    answering(201, {
      nonce: NONCE,
      echo_probe: 'Registration check. Reply with the AgentAudit registration nonce',
      statement: 'Plant this value in the target’s configuration',
    })

    const issued = await issueNonce()

    expect(issued.nonce).toBe(NONCE)
    expect(issued.echo_probe).toContain('Registration check')
    expect(issued.statement).toContain('Plant this value')
  })

  it('fails loudly when there is nothing to plant', async () => {
    answering(500, { detail: 'no' })

    await expect(issueNonce()).rejects.toThrow('nothing to plant')
  })
})

describe('what the next run covers', () => {
  it('sends the six and the tier as one statement, in two arrays', async () => {
    // `PUT /bench/settings/families` is the whole statement of what the next run
    // covers, so a call that sent only the list the operator touched would clear the
    // other one. Two arrays and never one of nine: the six are the denominator the
    // gate is decided over and the tier is a second closed set, so a name in the
    // wrong array is a 422 from the route rather than a family landing in the other
    // tier's counts (ADR-0015, ADR-0035, ADR-0088).
    const fetching = answering(200, { tuning: {} })

    await coverFamilies(['data_leakage'], ['pii_leakage'])

    const [path, init] = fetching.mock.calls[0]
    expect(path).toBe(BENCH_FAMILIES_PATH)
    expect(init?.method).toBe('PUT')
    expect(JSON.parse(String(init?.body))).toEqual({
      families: ['data_leakage'],
      elective: ['pii_leakage'],
    })
  })

  it('sends an empty tier rather than omitting it', async () => {
    // The one list on this bench that may be empty, and it is a statement: the six
    // and only the six, which is what every run asked for before #171.
    const fetching = answering(200, { tuning: {} })

    await coverFamilies(['data_leakage'], [])

    const [, init] = fetching.mock.calls[0]
    expect(JSON.parse(String(init?.body))).toHaveProperty('elective', [])
  })
})
