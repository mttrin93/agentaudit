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
    declared_tools: ['send_email', '  issue_refund  ', ''],
    price_per_call: '0.002',
    currency: 'USD',
    note_planted: true,
    nonce: NONCE,
    nonce_planted: true,
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
        declared_tools: ['send_email', 'issue_refund'],
        sends: 3,
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

    expect(outcome).toEqual({ kind: 'refused', statement: refusal })
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
