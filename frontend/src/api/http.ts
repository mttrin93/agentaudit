/**
 * How the area modules talk to the bench: one fetch, and one way of reading a
 * refusal.
 *
 * Both of these were private to `bench.ts` before #14 split it by API area. They are
 * exported now because six modules need them, and they are in a module of their own
 * rather than in `contracts.ts` because a contract is a shape and these are conduct.
 * `authed` is the only function in this app that calls `fetch`, and `http.test.ts`
 * sweeps `src/api/` to keep that true — a nineteenth call site would be a request
 * that went out with no bearer on it and would be found in production by a `401`.
 *
 * **One place a token is attached, and the same place a door's refusal leaves**
 * (the spec's frontend seam, under [ADR-0116](../../../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)).
 * The alternative was for each of the area modules' outcome types to gain a case
 * for *not signed in*: eighteen call sites, three route families and every screen
 * that reads one, to carry a fact that is about the session and not about the
 * request. So a door is attended once — by a component inside the issuer's provider,
 * since a token comes from a hook and these modules are plain functions that run
 * under `environment: 'node'` with no jsdom — and it hears about its own refusals
 * through the callback it registered.
 *
 * `bench.ts` re-exports `attendTheDoor` and nothing else from this file. `authed`
 * stays unexported from the barrel for the reason `fetched` always did: a screen
 * that fetched a path of its own would be a route the barrel does not list.
 *
 * **`refusalRead` never throws and never invents.** It reads the sentence the bench
 * wrote and, where there is none, says so in as many words: a refusal presented as
 * an empty string would be a screen with nothing to tell the operator to do next.
 */

import type { Refusal } from './contracts'

/**
 * Why the door turned a request away, in the two readings a console acts on.
 *
 * The API answers a `401` for the four causes that are about the credential
 * presented and a `503` for the one that is not, and it carries the verifier's own
 * sentence in both (`backend/api/app.py:_the_refusal`). The two are held apart here
 * because the remedies are different: a session to sign in for again, against an
 * issuer that could not be reached, where signing in again is not the thing to do
 * and would fail in the same way.
 *
 * `cause` is the wire's own lowercase spelling of `backend.identity.Unverifiable`,
 * carried so a screen can tell *nobody has signed in yet* from *this session ran
 * out* without parsing the sentence. The sentence is still the part an operator
 * reads.
 */
export type DoorRefusal =
  | { kind: 'sign_in_again'; cause: string; statement: string }
  | { kind: 'issuer_unreachable'; statement: string }

/**
 * The door this console goes through: a token for the next request, and somewhere
 * to say that the bench would not take it.
 *
 * `token` answers `null` for a console nobody has signed into, and the request goes
 * anyway: signed out is the bench's refusal to state, not this module's to guess.
 * `refused` is optional because a caller that wants only the header should not have
 * to supply a sink for refusals it will not read.
 */
export interface Door {
  token: () => Promise<string | null>
  refused?: (refusal: DoorRefusal) => void
}

let attending: Door | null = null

/**
 * Attend the door, or stop attending it. Called once at mount, and with `null` to
 * put the module back the way a fresh import finds it.
 *
 * No door attended is the declared-open reading (ADR-0121) seen from this side:
 * every request goes with no `Authorization` on it, which is what every test in
 * this suite and every clone with no issuer runs as. A header invented for that
 * state would be a token this app does not have.
 */
export function attendTheDoor(door: Door | null): void {
  attending = door
}

/**
 * Every request this app makes to the bench, with the operator's token on it.
 *
 * The caller's `init` is passed through untouched apart from one header, so the
 * eighteen call sites read exactly as they did: a method, a body, a
 * `Content-Type`. Where the door holds no token the header is simply absent.
 *
 * **The response comes back unread.** The door's refusal is taken off a `clone()`,
 * because a `Response` body is read once and the caller's own `refusalRead` is the
 * thing that must have it — this seam reports a refusal and never consumes one.
 *
 * **A door that cannot produce a token is not an unreachable bench.** The issuer's
 * client mints these over the network and can fail; letting that throw out of here
 * would surface at the call sites as `unreachable`, whose sentence says the bench
 * did not answer and that it is not known what it recorded. Neither half is true.
 * So the request goes without a header and the bench's own door refuses it, which
 * puts the operator in front of a sentence about signing in.
 */
export async function authed(path: string, init?: RequestInit): Promise<Response> {
  const token = await tokenFromTheDoor()
  const response = await fetch(
    path,
    token
      ? {
          ...init,
          headers: {
            ...Object.fromEntries(new Headers(init?.headers).entries()),
            Authorization: `Bearer ${token}`,
          },
        }
      : init,
  )
  const refused = attending?.refused
  if (refused && (response.status === 401 || response.status === 503)) {
    const refusal = await doorRefusalIn(response.clone())
    if (refusal) {
      refused(refusal)
    }
  }
  return response
}

/** The attended door's token, and `null` for every way there is not one. */
async function tokenFromTheDoor(): Promise<string | null> {
  try {
    return (await attending?.token()) ?? null
  } catch {
    return null
  }
}

/**
 * The door's refusal in a response, or `null` where the refusal is somebody else's.
 *
 * The status alone is not the discriminator. A `503` from a proxy or a cold start
 * is not the issuer being unreachable, and a console that showed a sign-in screen
 * over one would be reporting an outage as a rejected credential. So the body's own
 * shape decides: `detail` an object carrying a `refusal` and a `statement` is this
 * surface's door and nothing else on it answers that way.
 */
async function doorRefusalIn(response: Response): Promise<DoorRefusal | null> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    return null
  }
  const door = theDoorsDetail(detail)
  if (!door) {
    return null
  }
  return response.status === 503
    ? { kind: 'issuer_unreachable', statement: door.statement }
    : { kind: 'sign_in_again', cause: door.refusal, statement: door.statement }
}

/** `detail` read as the door's two strings, or nothing at all. */
function theDoorsDetail(
  detail: unknown,
): { refusal: string; statement: string } | null {
  if (typeof detail !== 'object' || detail === null || Array.isArray(detail)) {
    return null
  }
  const { refusal, statement } = detail as { refusal?: unknown; statement?: unknown }
  if (typeof refusal !== 'string' || typeof statement !== 'string' || !statement.trim()) {
    return null
  }
  return { refusal, statement }
}

export const REFUSED_WITHOUT_A_REASON =
  'the bench refused this registration and returned no reason with it. Nothing ' +
  'was sent to the target. Plant the value the bench issues next and register ' +
  'again.'

/**
 * The refusal the bench sent, read once and read both ways.
 *
 * FastAPI puts a raised `HTTPException`'s message in `detail` as a string, and its
 * own body-validation errors in the same field as a list of objects. Both are read
 * here rather than only the first, because the second is what arrives when this app
 * posts a field the API's models reject — and a screen that showed "refused, no
 * reason given" for it would be hiding the one message that says which field.
 *
 * **The third shape is the door's**: an object carrying the cause a client branches
 * on and the verifier's own sentence. Only the sentence is taken here — the cause
 * reaches the console through `attendTheDoor`, because what to do about an expired
 * session is a fact about the session and not about the request that met it. Read
 * in this function all the same, so that a screen holding a refused response shows
 * the door's words instead of "refused, no reason given".
 *
 * **The two readings come out of one call**, because a `Response` body is read
 * once: a second function that fetched the fields separately would have nothing
 * left to parse. `fields` is empty for a refusal that names none — a raised
 * `HTTPException` is about the registration and not about an input — and a screen
 * with nothing to pin the sentence to shows it over the form, which is where it
 * already was.
 */
export async function refusalRead(response: Response): Promise<Refusal> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    return { statement: REFUSED_WITHOUT_A_REASON, fields: [] }
  }
  if (typeof detail === 'string' && detail.trim()) {
    return { statement: detail, fields: [] }
  }
  const door = theDoorsDetail(detail)
  if (door) {
    // No field is named. A refusal at the door is about the request and not about
    // an input, so it goes over the form the way a raised `HTTPException` does.
    return { statement: door.statement, fields: [] }
  }
  if (Array.isArray(detail) && detail.length) {
    const problems = detail.map((problem) => {
      const { loc, msg } = problem as { loc?: unknown[]; msg?: string }
      return {
        field: Array.isArray(loc) ? loc.join('.') : '',
        msg: msg ?? '',
      }
    })
    return {
      statement: problems
        .map((one) => (one.field ? `${one.field}: ${one.msg}` : one.msg))
        .join('; '),
      // Only the ones that named somewhere. A problem with no `loc` is on the
      // sentence above and belongs to no input.
      fields: problems.filter((one) => one.field !== ''),
    }
  }
  return { statement: REFUSED_WITHOUT_A_REASON, fields: [] }
}

/** The sentence alone, for the callers that have nowhere to put a field name. */
export async function refusalIn(response: Response): Promise<string> {
  return (await refusalRead(response)).statement
}

export const ANSWER_UNREACHABLE =
  'the bench did not answer, so it is not known whether it recorded this ' +
  'decision. Read the run’s standing before answering again: an interrupt is ' +
  'answered once, and if this one was taken the run is already under way.'

/**
 * One report route, read, with the bench's own refusal carried out of it.
 *
 * The four refusals are named — no such run, in flight, did not complete, never
 * signed — and the name is the part an operator can act on, so a failed fetch
 * raises with the bench's sentence rather than with a status code. There is no
 * partial report to fall back to and none is invented here.
 */
export async function fetched(path: string, what: string): Promise<unknown> {
  const response = await authed(path)
  if (!response.ok) {
    throw new Error(
      `the bench did not serve the ${what} at ${path}: ${await refusalIn(response)}`,
    )
  }
  return await response.json()
}
