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
 * **`refusalIn` never throws and never invents.** It reads the sentence the bench
 * wrote and, where there is none, says so in as many words: a refusal presented as
 * an empty string would be a screen with nothing to tell the operator to do next.
 */

export const REFUSED_WITHOUT_A_REASON =
  'the bench refused this registration and returned no reason with it. Nothing ' +
  'was sent to the target. Plant the value the bench issues next and register ' +
  'again.'

/**
 * The sentence the bench sent with its refusal.
 *
 * FastAPI puts a raised `HTTPException`'s message in `detail` as a string, and
 * its own body-validation errors in the same field as a list of objects. Both are
 * read here rather than only the first, because the second is what arrives when
 * this app posts a field the API's models reject — and a screen that showed
 * "refused, no reason given" for it would be hiding the one message that says
 * which field.
 */
export async function refusalIn(response: Response): Promise<string> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    return REFUSED_WITHOUT_A_REASON
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((problem) => {
        const { loc, msg } = problem as { loc?: unknown[]; msg?: string }
        const where = Array.isArray(loc) ? loc.join('.') : ''
        return where ? `${where}: ${msg ?? ''}` : `${msg ?? ''}`
      })
      .join('; ')
  }
  return REFUSED_WITHOUT_A_REASON
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
