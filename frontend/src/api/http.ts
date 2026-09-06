/**
 * How the area modules talk to the bench: one fetch, and one way of reading a
 * refusal.
 *
 * Both of these were private to `bench.ts` before #14 split it by API area. They are
 * exported now because six modules need them, and they are in a module of their own
 * rather than in `contracts.ts` because a contract is a shape and these are conduct.
 * Nothing outside `src/api/` imports this file — `bench.ts` deliberately does not
 * re-export it, so a screen cannot fetch a path the barrel does not list.
 *
 * **`refusalRead` never throws and never invents.** It reads the sentence the bench
 * wrote and, where there is none, says so in as many words: a refusal presented as
 * an empty string would be a screen with nothing to tell the operator to do next.
 */

import type { Refusal } from './contracts'

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
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(
      `the bench did not serve the ${what} at ${path}: ${await refusalIn(response)}`,
    )
  }
  return await response.json()
}
