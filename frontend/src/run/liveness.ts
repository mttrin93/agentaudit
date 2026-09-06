/**
 * Whether this screen is still being told anything, and what it says about it.
 *
 * Every figure on the run screen is dated: it is what the last answered poll said,
 * and a run that is slow between attempts draws the same unmoving numbers as a poll
 * that stopped being answered. This module is the difference between the two, and
 * ADR-0078 is why it is a module rather than a line — how long is stalled, what the
 * retry does, and why none of this is a fact about the run or the target.
 *
 * **Nothing here can name a target.** A target that stopped answering the bench is a
 * `TransportOutcome`, written into the run's record by the bench under one of seven
 * names (`progress.ts`); what is decided here is whether *this browser* is still
 * being answered by the bench. The two silences are read in the same place on the
 * same screen, so they are computed in two modules with no type in common.
 *
 * **It is a function of two times and a flag, so the screen holds no rule.** The run
 * screen supplies when it was last answered and what time it is now; the span, the
 * words and the stamp are here, and `liveness.test.ts` asserts them with no DOM and
 * no clock.
 */

/**
 * How often the run is asked where it has got to.
 *
 * The frontend polls because the spec says it does. Two seconds because the thing
 * being watched is a position moving through 181 attempts over minutes: often
 * enough that the attempt on screen is the attempt in flight, rare enough that a
 * screen left open is not a load on the bench that is attacking somebody's
 * endpoint.
 *
 * Declared here rather than on the screen because the span below is stated in polls
 * missed, and two numbers that mean each other should not be able to drift apart.
 */
export const POLL_SECONDS = 2

/** How many answers have to go missing before the screen says so. ADR-0078. */
const STALLED_AFTER_POLLS = 6

/**
 * How long the bench may say nothing before this screen stops vouching for what is
 * on it: twelve seconds, which is six polls missed (ADR-0078).
 */
export const STALLED_AFTER_SECONDS = POLL_SECONDS * STALLED_AFTER_POLLS

/**
 * What this screen's conversation with the bench is doing.
 *
 * Four kinds, and the fourth is the one that keeps the other three honest:
 * **settled** is a run that has stopped, whose poll stopped with it on purpose, and
 * which therefore has an old last answer and no silence to report.
 */
export type LivenessKind = 'waiting' | 'answering' | 'stalled' | 'settled'

/** What the screen knows about its own link to the bench. */
export interface Liveness {
  kind: LivenessKind
  /**
   * The clock time of the last answer, or `''` before the first one.
   *
   * The time of day rather than a span, because it is drawn beside figures a reader
   * may have come back to: an absolute stamp dates them for somebody who was not
   * watching, and it does not move on its own (ADR-0078).
   */
  stamp: string
  /** Seconds since the last answer. Zero where there has not been one. */
  silentFor: number
}

/** The sentence a stalled screen says, drawn and announced in the same words. */
export const NOT_ANSWERING =
  'The bench has stopped answering this screen. What is below is the last thing it ' +
  'said, and the run itself is very likely still going.'

/** What the retry offers to do, which is exactly one read and nothing else. */
export const ASK_AGAIN = 'Ask the bench now'

/**
 * The clock time of a moment, as this console writes one.
 *
 * `en-GB` rather than the reader's locale, and the reason is the same one the type
 * stack is pinned for: this is a bench whose screens are read beside each other and
 * quoted into incident notes, and a stamp that is `2:03:12 pm` on one machine and
 * `14:03:12` on the next is a fact that reads two ways.
 */
function clockTime(at: number): string {
  return new Date(at).toLocaleTimeString('en-GB')
}

/** What the screen was last told, and how long ago. */
export function liveness(read: {
  answeredAt: number | null
  now: number
  inFlight: boolean
}): Liveness {
  const { answeredAt, now, inFlight } = read
  if (answeredAt === null) {
    return { kind: inFlight ? 'waiting' : 'settled', stamp: '', silentFor: 0 }
  }
  const silentFor = Math.max(0, Math.floor((now - answeredAt) / 1000))
  const stamp = clockTime(answeredAt)
  // A run that has stopped is settled however old its last answer is: the poll
  // stopped itself, so the silence is this screen's own doing (ADR-0078).
  if (!inFlight) {
    return { kind: 'settled', stamp, silentFor }
  }
  return {
    kind: silentFor >= STALLED_AFTER_SECONDS ? 'stalled' : 'answering',
    stamp,
    silentFor,
  }
}

/**
 * What the polite region says, which changes when the run's phase does and never
 * otherwise.
 *
 * Built from the standing's heading and the liveness *kind* alone — never the stamp,
 * never `silentFor`, never a position. A live region announces when its text changes,
 * so a sentence carrying anything that moves on its own would read the run out loud
 * every two seconds (ADR-0078), and `liveness.test.ts` asserts two different ticks of
 * one phase produce one string.
 *
 * `heading` is the run screen's own `h1` — the run's standing in as few words as will
 * name it — so what is announced is what a reader would see, and `null` before the
 * first answer says nothing rather than guessing.
 */
export function announcement(heading: string | null, live: Liveness): string {
  if (live.kind === 'stalled') {
    return NOT_ANSWERING
  }
  return heading === null ? '' : `${heading}.`
}
