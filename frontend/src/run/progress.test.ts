/**
 * What progress says about each layer, and the three things it must never say.
 *
 * Driven from the shape `GET /runs/{id}` actually returns — `RunProgress`,
 * `snake_case`, positions as the API's two models and a `null` where a figure is
 * absent rather than zero. What is asserted here is the arithmetic and the
 * vocabulary: that the scored layer is read in families, cases and attempts and
 * the adaptive one in families, episodes and turns; that no value the screen builds
 * spans the two; that an episode a ceiling cut short is censored and never
 * resistance; and that a transport failure appears under its own name rather than
 * as a result about the target. Whether the two panels *read* as two is a person's
 * job, and it was driven by hand against the real API.
 *
 * The numbers are chosen so no blend could appear by coincidence: 181 and 40 calls
 * spent (221 together, 110.5 averaged), 13 attempts succeeded beside 6 adaptive
 * findings (19 together).
 */

import { describe, expect, it } from 'vitest'

import type { RunProgress } from '../api/bench'
import {
  ADAPTIVE_UNITS,
  SCORED_UNITS,
  adaptiveReading,
  progressView,
  scoredReading,
  standing,
  stillGoing,
} from './progress'

/** A run in flight, well into its scored layer and not yet past it. */
function inTheScoredLayer(): RunProgress {
  return {
    run_id: 'run-1',
    status: 'running',
    statement: 'confirmed by operator: the suite is running in the background',
    scored: {
      reached: true,
      statement:
        'family data leakage, case leak-002, attempt 4: the position the scored ' +
        'layer has reached',
      position: { family: 'data leakage', case_id: 'leak-002', attempt: 4 },
      calls_spent: 181,
      succeeded_attempts: 13,
    },
    adaptive: {
      reached: true,
      statement:
        'family scope creep, episode 2, turn 5: the position the adaptive layer ' +
        'has reached. Nothing in this layer is scored',
      position: { family: 'scope creep', episode: 2, turn: 5 },
      calls_spent: 40,
      adaptive_findings: 6,
    },
    transport: null,
    report: null,
  }
}

/** A run holding its interrupt: neither layer has attempted anything. */
function holdingItsInterrupt(): RunProgress {
  return {
    run_id: 'run-2',
    status: 'awaiting_approval',
    statement: 'awaiting approval: nothing has been sent to the target',
    scored: {
      reached: false,
      statement: 'the scored layer has attempted nothing',
      position: null,
      calls_spent: 0,
      succeeded_attempts: null,
    },
    adaptive: {
      reached: false,
      statement: 'the run has not reached the adaptive layer',
      position: null,
      calls_spent: 0,
      adaptive_findings: null,
    },
    transport: null,
    report: null,
  }
}

describe('the scored layer', () => {
  it('is read in families, cases and attempts', () => {
    const reading = scoredReading(inTheScoredLayer().scored)

    expect(reading.units).toEqual(['family', 'case', 'attempt'])
    expect(reading.at).toEqual(['data leakage', 'leak-002', '4'])
    // The bench's own sentence, carried rather than paraphrased.
    expect(reading.statement).toContain('attempt 4')
  })

  it('reports its position and its own calls, and counts nothing', () => {
    const counted = scoredReading(inTheScoredLayer().scored)
    const none = scoredReading(holdingItsInterrupt().scored)

    // The two standing paragraphs came off this reading: what the layer had found,
    // and that calls are not attempts. What is left is a position, a spend and the
    // bench's own sentence — and no count of verdicts anywhere in it, which used to
    // be a number in prose.
    expect(Object.keys(counted)).toEqual([
      'layer',
      'title',
      'reached',
      'units',
      'at',
      'statement',
      'callsSpent',
    ])
    expect(counted.callsSpent).toBe(inTheScoredLayer().scored.calls_spent)
    // A layer that has attempted nothing still says so by having no position, which
    // is the absent-and-not-zero distinction the prose used to spell out.
    expect(none.at).toBeNull()
  })
})

describe('the adaptive layer', () => {
  it('is read in families, episodes and turns', () => {
    const reading = adaptiveReading(inTheScoredLayer().adaptive)

    // Three different things from the scored layer's three: an episode has no
    // denominator and a turn is not an attempt.
    expect(reading.units).toEqual(['family', 'episode', 'turn'])
    expect(SCORED_UNITS).not.toEqual(ADAPTIVE_UNITS)
    expect(reading.at).toEqual(['scope creep', '2', '5'])
  })

  it('carries no count of routes found, and no position before it starts', () => {
    const counted = adaptiveReading(inTheScoredLayer().adaptive)
    const none = adaptiveReading(holdingItsInterrupt().adaptive)

    // The routes-found count is off this reading, along with the sentence saying it
    // carried no rate, no interval, no band and no D. Nothing in the value is that
    // count now — asserted over every string, so it cannot come back in a sentence.
    const said = Object.values(counted).join(' ')
    expect(said).not.toContain('found a route')
    expect(said).not.toContain(
      `${inTheScoredLayer().adaptive.adaptive_findings} episode`,
    )
    expect(none.at).toBeNull()
    expect(none.reached).toBe(false)
  })
})

describe('the two layers together', () => {
  it('are reported side by side with nothing that spans them', () => {
    const view = progressView(inTheScoredLayer())
    const rendered = JSON.stringify(view)

    expect(view.scored.callsSpent).toBe(181)
    expect(view.adaptive.callsSpent).toBe(40)
    // The sum of the spends, their average, and the sum of the two counts: every
    // figure that would be one number for the whole run.
    expect(rendered).not.toContain('221')
    expect(rendered).not.toContain('110.5')
    expect(rendered).not.toContain('19')
  })
})

describe('a budget abort', () => {
  it('is shown as an abort, and its episode as censored', () => {
    const aborted: RunProgress = {
      ...inTheScoredLayer(),
      status: 'aborted',
      statement:
        'the adaptive layer has spent 8 of a declared 8 calls, and the next ' +
        'message needs up to 3 more: refusing it rather than spend past the ' +
        'estimate the operator confirmed. An episode the ceiling cut short is ' +
        'recorded as censored, never as resisted',
    }

    const reading = standing(aborted)

    expect(reading.kind).toBe('aborted')
    expect(reading.name).toBe('aborted')
    expect(reading.episode?.outcome).toBe('censored')
    expect(reading.episode?.note).toContain('censored')
    expect(reading.episode?.note).toContain('the attacker stopped')
    // This screen's own words about the abort, checked apart from the bench's
    // statement — which says "censored, never as resisted" and would satisfy a
    // search for the word by containing the sentence that forbids it.
    const ours = [reading.heading, reading.notASecurityResult, reading.episode?.note]
    for (const said of ours) {
      expect(said).not.toContain('resisted')
      expect(said).not.toContain('defended')
    }
    expect(reading.notASecurityResult).toContain('not a result about the target')
    expect(reading.statement).toBe(aborted.statement)
  })

  it('is the only standing that names an episode outcome at all', () => {
    // Nothing else this screen can draw has an episode reading on it, so there is
    // no branch where an episode acquires a second outcome — and `EpisodeOutcome`
    // has no second member for one to be spelled with.
    for (const status of [
      'awaiting_approval',
      'running',
      'completed',
      'declined',
      'unanswered',
      'registration_refused',
      'failed',
    ]) {
      const reading = standing({ ...inTheScoredLayer(), status })
      expect(reading.episode).toBeNull()
    }
  })
})

describe('a transport failure', () => {
  const failures = [
    'timeout',
    'auth_rejected',
    'malformed_reply',
    'rate_limited',
    'unavailable',
    'unreachable',
    'refused',
  ]

  it('is shown under its own name and never as a security result', () => {
    for (const failure of failures) {
      const stopped: RunProgress = {
        ...inTheScoredLayer(),
        status: 'failed',
        statement: `https://staging.example/agent after 3 sends: ${failure}`,
        transport: {
          failure,
          statement: `${failure} — what the endpoint did. No attempt is recorded`,
        },
      }

      const reading = standing(stopped)

      // One of seven names rather than one word for all of them: a timeout is
      // capacity, a rejected token is configuration, a malformed body is a
      // contract breach and a rate limit is a quota.
      expect(reading.kind).toBe('transport')
      expect(reading.name).toBe(failure)
      expect(reading.heading).toContain(failure)
      expect(reading.statement).toBe(stopped.transport?.statement)
      expect(reading.notASecurityResult).toContain('nothing here is a security result')
      expect(reading.inFlight).toBe(false)
    }
  })

  it('is read before the status, so the named outcome is not lost to “failed”', () => {
    const stopped: RunProgress = {
      ...inTheScoredLayer(),
      status: 'failed',
      statement: 'the run stopped',
      transport: { failure: 'rate_limited', statement: 'rate limit — 429 on every send' },
    }

    expect(standing(stopped).name).toBe('rate_limited')
  })
})

describe('what is worth polling', () => {
  it('is a run that is holding or running, and nothing that has stopped', () => {
    expect(stillGoing('awaiting_approval')).toBe(true)
    expect(stillGoing('running')).toBe(true)
    for (const status of [
      'completed',
      'declined',
      'unanswered',
      'registration_refused',
      'aborted',
      'failed',
    ]) {
      expect(stillGoing(status)).toBe(false)
    }
  })

  it('holds at the interrupt with nothing sent, and says which state that is', () => {
    const reading = standing(holdingItsInterrupt())

    expect(reading.kind).toBe('holding')
    expect(reading.inFlight).toBe(true)
    expect(reading.statement).toContain('nothing has been sent')
  })
})
