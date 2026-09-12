/**
 * The one seam a token enters through, and the one place a door's refusal leaves.
 *
 * These run in node with no DOM, which is the point of the seam being here rather
 * than in a hook: `vite.config.ts` argues against buying jsdom so that a test can
 * read markup, and the api modules stay plain functions that a node test can call.
 * What is asserted is the wire — the header that goes out, the refusal that comes
 * back — and never a component's rendering of either.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  attendTheDoor,
  authed,
  refusalRead,
  type DoorRefusal,
} from './http'

/** A fetch that answers once, and records what it was called with. */
function answering(status: number, body: unknown, headers: HeadersInit = {}) {
  const fetching = vi.fn(async (_path: string, _init?: RequestInit) =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json', ...headers },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetching)
  return fetching
}

/** The header the seam attached, read off the call the stub recorded. */
function bearerOf(fetching: ReturnType<typeof answering>): string | null {
  const init = fetching.mock.calls[0]?.[1]
  return new Headers(init?.headers).get('Authorization')
}

/** A door holding one token, and a place the refusals it earns are collected. */
function aDoorHolding(token: string | null) {
  const refusals: DoorRefusal[] = []
  attendTheDoor({
    token: () => Promise.resolve(token),
    refused: (refusal) => refusals.push(refusal),
  })
  return refusals
}

afterEach(() => {
  attendTheDoor(null)
  vi.unstubAllGlobals()
})

describe('the token, attached in one place', () => {
  it('goes out as a bearer on a request the attended door holds a token for', async () => {
    const fetching = answering(200, { rule: 'read' })
    aDoorHolding('a-session-token')

    await authed('/bench/settings')

    expect(bearerOf(fetching)).toBe('Bearer a-session-token')
  })

  it('is absent where no door is attended, which is the no-door bench', async () => {
    // The declared-open reading (ADR-0121). Every test in this suite and every
    // clone with no issuer runs here, and a header invented for it would be a
    // token this app does not have.
    const fetching = answering(200, { rule: 'read' })

    await authed('/bench/settings')

    expect(bearerOf(fetching)).toBeNull()
  })

  it('is absent where a door is attended and nobody is signed in', async () => {
    // Signed out is not an error to throw here: the request goes, the bench
    // refuses it at the door, and the sentence it wrote is what the screen shows.
    const fetching = answering(401, {
      detail: { refusal: 'absent', statement: 'no token was presented' },
    })
    aDoorHolding(null)

    await authed('/bench/settings')

    expect(bearerOf(fetching)).toBeNull()
  })

  it('is absent where the door could not mint one, and the request still goes', async () => {
    // The issuer's client mints these over the network. A throw out of the seam
    // would reach the call sites as `unreachable` — *the bench did not answer, so
    // it is not known whether it recorded this* — which would be two false
    // statements about a bench that was never asked.
    const fetching = answering(401, {
      detail: { refusal: 'absent', statement: 'no token was presented' },
    })
    attendTheDoor({
      token: () => Promise.reject(new Error('the issuer could not be reached')),
    })

    expect((await authed('/runs/r1')).status).toBe(401)
    expect(bearerOf(fetching)).toBeNull()
  })

  it('does not displace the method, the body or the caller’s own headers', async () => {
    const fetching = answering(202, { run_id: 'r1' })
    aDoorHolding('a-session-token')

    await authed('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{"target":{}}',
    })

    const init = fetching.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe('{"target":{}}')
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
    expect(bearerOf(fetching)).toBe('Bearer a-session-token')
  })
})

describe('the door’s own refusal, read once and not consumed', () => {
  it('reaches the attended door as a session to sign in again for', async () => {
    const fetching = answering(
      401,
      { detail: { refusal: 'expired', statement: 'this session has expired' } },
      { 'WWW-Authenticate': 'Bearer' },
    )
    const refusals = aDoorHolding('a-stale-token')

    const response = await authed('/runs/r1')

    expect(refusals).toEqual([
      { kind: 'sign_in_again', cause: 'expired', statement: 'this session has expired' },
    ])
    // And the caller still has a body to read. `authed` looked at a clone, so the
    // eighteen call sites read exactly the refusal they would have read before.
    expect((await refusalRead(response)).statement).toBe('this session has expired')
    expect(fetching).toHaveBeenCalledTimes(1)
  })

  it('holds an unreachable issuer apart from a rejected credential', async () => {
    // A `503` is not a statement about the token (ADR-0120). Collapsing the two
    // into one *please sign in* would tell an operator their session was rejected
    // while the issuer was down, and signing in again is not the thing to do.
    const refusals = aDoorHolding('a-good-token')
    answering(503, {
      detail: {
        refusal: 'unavailable',
        statement: 'the issuer’s keys could not be read',
      },
    })

    await authed('/runs/r1')

    expect(refusals).toEqual([
      { kind: 'issuer_unreachable', statement: 'the issuer’s keys could not be read' },
    ])
  })

  it('says nothing to the door about a refusal that is not the door’s', async () => {
    // A `422` is the API's ordinary body validation and a `503` with no refusal in
    // it is somebody else's — a proxy, a cold start. Reporting either as the door
    // would put a sign-in screen over a registration with a bad field in it.
    const refusals = aDoorHolding('a-good-token')
    answering(422, {
      detail: [{ loc: ['body', 'identity'], msg: 'Value error, identity is not a field' }],
    })
    await authed('/runs', { method: 'POST' })

    answering(503, { detail: 'the bench is starting up' })
    await authed('/runs', { method: 'POST' })

    expect(refusals).toEqual([])
  })

  it('is read off a door that declares no interest in refusals', async () => {
    // `refused` is optional so that a caller wanting only the header is not made to
    // supply a sink. What must not happen is a throw out of the seam.
    attendTheDoor({ token: () => Promise.resolve('a-token') })
    answering(401, { detail: { refusal: 'absent', statement: 'no token' } })

    expect((await authed('/runs/r1')).status).toBe(401)
  })
})

describe('one seam, swept', () => {
  it('is the only module under src/api that calls fetch at all', () => {
    // What makes *one place a token is attached* true rather than intended. A
    // nineteenth call site added next year is a request that goes out with no
    // bearer on it, and it would be found in production by a `401` rather than
    // here. The sweep is a glob rather than a roster so that a new area module is
    // covered by being written, not by being remembered.
    const modules = import.meta.glob('./*.ts', { query: '?raw', eager: true }) as Record<
      string,
      { default: string }
    >
    const calling = Object.entries(modules)
      .filter(([path]) => !path.endsWith('.test.ts') && path !== './http.ts')
      .filter(([, source]) => source.default.includes('fetch('))
      .map(([path]) => path)

    expect(calling).toEqual([])
    // And the roster is not empty, which is the way this assertion fails silently:
    // a glob that matched nothing would pass it.
    expect(Object.keys(modules).length).toBeGreaterThan(8)
  })
})

describe('the refusal a caller reads', () => {
  it('takes the sentence out of the door’s object-shaped detail', async () => {
    // The third body shape on this surface: a string from a raised
    // `HTTPException`, a list from body validation, and this object from the door.
    const refusal = await refusalRead(
      new Response(
        JSON.stringify({
          detail: { refusal: 'untrusted', statement: 'this deployment will not accept it' },
        }),
        { status: 401 },
      ),
    )

    expect(refusal.statement).toBe('this deployment will not accept it')
    // No field is named: a door's refusal is about the request and not an input.
    expect(refusal.fields).toEqual([])
  })

  it('still reads the two shapes it read before', async () => {
    const raised = await refusalRead(
      new Response(JSON.stringify({ detail: 'the bench is holding its library' }), {
        status: 409,
      }),
    )
    expect(raised.statement).toBe('the bench is holding its library')

    const validated = await refusalRead(
      new Response(
        JSON.stringify({
          detail: [
            {
              loc: ['body', 'attestation', 'identity'],
              msg: 'Value error, identity is not a field',
            },
          ],
        }),
        { status: 422 },
      ),
    )
    expect(validated.fields).toEqual([
      {
        field: 'body.attestation.identity',
        msg: 'Value error, identity is not a field',
      },
    ])
  })
})
