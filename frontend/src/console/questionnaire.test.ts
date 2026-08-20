/**
 * What the questionnaire block must answer, and the several things it must not.
 *
 * Driven from `served.fixture.ts` — the frozen payload the bench's own serialiser
 * produced — because every load-bearing claim here is an **absence**, and an absence
 * asserted against a hand-written stub would be an absence from the stub. That
 * fixture exercises every branch this block has to draw at once: two deterministic
 * families at different bands, one judged family fit to report, one judged family
 * withheld below the κ floor, one family the target could not be measured on, and
 * four published categories the bench never tests.
 *
 * Four assertions are the ones that matter in a year:
 *
 * * **No two families are combined.** Asserted structurally — drop a family from the
 *   payload and every other answer, and everything that is not an answer, is
 *   unchanged — so it does not depend on anyone having guessed where a total would
 *   be put or on their having called it a total. Beside it, the blends this
 *   fixture's figures would produce are looked for as *numbers*, because `0.4` sits
 *   inside the interval bound `0.449` and a substring search would fail on a block
 *   that holds no average at all.
 * * **The three kinds of nothing stay three, and none is a zero.** A family the
 *   bench could not measure, a family whose rate is withheld and a category the
 *   bench never tests are three different facts, and a measured 0 of 30 is a fourth.
 * * **No rate appears without its own denominator.** The counts travel with the rate
 *   on the same record, and the record has nowhere to carry one without the other.
 * * **No answer loses what its family does not test**, asserted against the payload's
 *   own coverage notes rather than against a list retyped here.
 */

import { describe, expect, it } from 'vitest'

import type { RunList, RunRow, TargetReport } from '../api/bench'
import { SERVED } from '../report/served.fixture'
import { reportPath } from './rail'
import {
  drawnFrom,
  NO_SIGNED_REPORT_YET,
  questionnaire,
  theRunsToDrawFrom,
  type AnsweredQuestion,
  type QuestionnaireAnswer,
} from './questionnaire'

/** Words no key anywhere in the block may contain (ADR-0005, D12). */
const FORBIDDEN_IN_A_KEY = [
  'total',
  'average',
  'mean',
  'overall',
  'composite',
  'aggregate',
  'sum',
  'rank',
  'grade',
  'index',
  'posture',
  'score',
]

/**
 * Every blend this fixture's published figures could produce.
 *
 * 21, 6 and 9 successes of 30 attempts each, at rates 0.70, 0.20 and 0.30: 36
 * successes together, 1.2 summed and 0.4 averaged. The same three the report screen
 * is checked against, and for the same reason — the fixture's rates were chosen so
 * that no blend of them could appear by coincidence.
 */
const BLENDS = [36, 1.2, 0.4]

/** Phrases a questionnaire block must never carry, however it got there. */
const NEVER_SAID = [
  '% secure',
  'percent secure',
  'posture score',
  'security score',
  'overall score',
  'risk score',
]

/**
 * The run these answers are drawn from, as `GET /runs` lists it.
 *
 * The completed run of the fixture's own report. Its recorded timestamp holds no
 * digits that could be mistaken for one of the blends above.
 */
const THE_COMPLETED_RUN: RunRow = row({
  run_id: 'e5f4d3c2-b1a0-4c3d-8e7f-6a5b4c3d2e1f',
  target: 'staging support agent',
  recorded_at: '2026-08-19T09:38:37+00:00',
  status: 'completed',
})

const LISTED: RunList = {
  statement: 'one row per run, with calls spent in two figures',
  runs: [
    row({
      run_id: '11112222-3333-4444-5555-666677778888',
      target: 'sandbox-router',
      recorded_at: '2026-08-19T22:04:01+00:00',
      status: 'running',
    }),
    THE_COMPLETED_RUN,
    row({
      run_id: '99990000-1111-2222-3333-444455556666',
      target: 'never-answered',
      recorded_at: '2026-08-17T07:15:59+00:00',
      status: 'unanswered',
    }),
    row({
      run_id: 'aaaabbbb-cccc-dddd-eeee-ffff00001111',
      target: 'older-staging-assistant',
      recorded_at: '2026-08-16T07:15:59+00:00',
      status: 'completed',
    }),
  ],
}

/** One row as the route serves it. No figure here is read by this block. */
function row(of: {
  run_id: string
  target: string
  recorded_at: string
  status: string
}): RunRow {
  return {
    run_id: of.run_id,
    target: of.target,
    recorded_at: of.recorded_at,
    status: of.status,
    statement: 'the run went on the record',
    scored: { calls_spent: 181, statement: 'calls the scored layer put on the wire' },
    adaptive: {
      calls_spent: 96,
      statement: 'calls the adaptive layer put on the wire',
    },
  }
}

/** The block as it reads over the whole served payload. */
function block(report: TargetReport = SERVED) {
  return questionnaire(report, drawnFrom(THE_COMPLETED_RUN))
}

/** Just the answered questions, which are the only ones carrying a rate. */
function answered(report: TargetReport = SERVED): AnsweredQuestion[] {
  return block(report).answers.filter(
    (answer): answer is AnsweredQuestion => answer.kind === 'answered',
  )
}

/** That payload with one measured family taken out, and nothing else touched. */
function without(family: string): TargetReport {
  const copy = structuredClone(SERVED)
  copy.measured.deterministic = copy.measured.deterministic.filter(
    (entry) => entry.family !== family,
  )
  return copy
}

/** Every dotted key path in the block, however deeply nested. */
function keysIn(node: unknown, path = ''): string[] {
  if (Array.isArray(node)) {
    return node.flatMap((value, at) => keysIn(value, `${path}[${at}]`))
  }
  if (node && typeof node === 'object') {
    return Object.entries(node).flatMap(([key, value]) => [
      path ? `${path}.${key}` : key,
      ...keysIn(value, path ? `${path}.${key}` : key),
    ])
  }
  return []
}

/** Every number that appears anywhere in the block, as a number. */
function numbersIn(node: unknown): number[] {
  return [...JSON.stringify(node).matchAll(/\d+(?:\.\d+)?/g)].map((found) =>
    Number(found[0]),
  )
}

/** Every string anywhere in the block, which is everything a reader can be shown. */
function everyString(node: unknown): string[] {
  if (typeof node === 'string') {
    return [node]
  }
  if (Array.isArray(node)) {
    return node.flatMap(everyString)
  }
  if (node && typeof node === 'object') {
    return Object.values(node).flatMap(everyString)
  }
  return []
}

describe('a question this bench answered', () => {
  it('names its family, the counts, the rate, the interval and the confidence', () => {
    const answers = answered()

    expect(answers.map((answer) => answer.family)).toEqual([
      'indirect_prompt_injection',
      'data_leakage',
      'disclosure_denial',
    ])
    // Each question is a sentence about the reader's own agent, not an identifier.
    expect(answers[0].question).toContain('instructions its operator never gave it')

    const [injection] = answers
    expect(injection.counts).toBe('21 of 30 attempts succeeded')
    expect(injection.rate).toBe('0.70')
    expect(injection.interval).toBe('0.551 to 0.816')
    expect(injection.confidence).toBe('90%')
    expect(injection.band).toBe('fails')
    expect(injection.bandReads).toContain('measurably worse')

    // The rate is beside the counts it came from on every answer, always. A rate
    // pasted into a customer's document without its denominator is the over-claim
    // this whole block exists to replace.
    for (const answer of answers) {
      expect(answer.counts).toMatch(/^\d+ of \d+ attempts succeeded$/)
      expect(answer.confidence).toMatch(/^\d+%$/)
      expect(answer.rate).not.toBe('')
    }
  })

  it('carries the coverage limit for its own family, and never loses it', () => {
    // Asserted against the payload's own coverage notes rather than against a list
    // retyped here: an answer that dropped a limit, or took a neighbour's, fails.
    const entries = [...SERVED.measured.deterministic, ...SERVED.measured.judged]

    for (const answer of answered()) {
      const entry = entries.find((one) => one.family === answer.family)
      expect(entry).toBeDefined()
      expect(answer.limits).toEqual(
        entry?.coverage.map((note) => ({
          identifier: note.identifier,
          doesNotTest: note.does_not_test,
        })),
      )
      expect(answer.limits.length).toBeGreaterThan(0)
      for (const limit of answer.limits) {
        expect(limit.doesNotTest).not.toBe('')
      }
    }

    expect(answered()[0].limits).toEqual([
      { identifier: 'LLM01:2026', doesNotTest: 'direct attacks from the user' },
    ])
  })

  it('keeps the payload’s order, and never sorts the answers by rate', () => {
    // A block ordered worst-first is a rank across families, and a rank is the
    // composite ADR-0005 refuses arriving as a layout decision.
    expect(answered().map((answer) => answer.rate)).toEqual(['0.70', '0.20', '0.30'])
  })
})

describe('no answer combines two families', () => {
  it('shows no total, no average, no rank and no key that reads as one', () => {
    const whole = block()

    const named = keysIn(whole).filter((key) =>
      FORBIDDEN_IN_A_KEY.some((word) => key.toLowerCase().includes(word)),
    )
    expect(named).toEqual([])

    const numbers = numbersIn(whole)
    for (const blend of BLENDS) {
      expect(numbers).not.toContain(blend)
    }

    const prose = everyString(whole).join(' ').toLowerCase()
    for (const said of NEVER_SAID) {
      expect(prose).not.toContain(said)
    }
  })

  it('drops nothing else when one family goes, because nothing spans two', () => {
    // The structural half, and the one that would catch a figure nobody named: take
    // a family out of the payload and every other answer is byte-identical, as is
    // everything that is not an answer. Anything computed over two families moves.
    const whole = block()
    const fewer = block(without('data_leakage'))

    expect(fewer.answers).toEqual(
      whole.answers.filter(
        (answer) => !('family' in answer && answer.family === 'data_leakage'),
      ),
    )
    expect(withoutTheAnswers(fewer)).toEqual(withoutTheAnswers(whole))
  })
})

describe('the three kinds of nothing stay three', () => {
  it('answers a family the bench could not measure as not measurable, not zero', () => {
    const [unanswerable] = only('not_measurable')

    expect(unanswerable.kind).toBe('not_measurable')
    expect('family' in unanswerable && unanswerable.family).toBe('halt_defeat')
    expect('reason' in unanswerable && unanswerable.reason).toBe(
      'no_tool_call_visibility',
    )
    // No field on the record could hold a figure, so there is nowhere for a zero.
    for (const field of ['rate', 'counts', 'interval', 'confidence', 'band']) {
      expect(field in unanswerable).toBe(false)
    }
    expect(numbersIn(unanswerable)).not.toContain(0)
    expect(JSON.stringify(unanswerable)).not.toContain('0.00')
    expect('note' in unanswerable && unanswerable.note).toContain('never as a zero')

    // And it is not the category kind either: the bench tests this family.
    expect(unanswerable.kind).not.toBe('not_tested')
    expect('note' in unanswerable && unanswerable.note).toContain(
      'not a category the bench never tests',
    )
  })

  it('reads apart from a family measured at 0 of 30, which is a measurement', () => {
    const nothingSucceeded = structuredClone(SERVED)
    const [first] = nothingSucceeded.measured.deterministic
    first.successes = 0
    first.rate = 0
    first.band = 'holds'
    first.interval = { lower: 0, upper: 0.095 }

    const [measured] = answered(nothingSucceeded)
    const [unanswerable] = block(nothingSucceeded).answers.filter(
      (answer) => answer.kind === 'not_measurable',
    )

    // Thirty attempts were made and none succeeded: that is a rate.
    expect(measured.rate).toBe('0.00')
    expect(measured.counts).toBe('0 of 30 attempts succeeded')
    // The family the bench could not measure has no rate to be confused with it.
    expect(unanswerable.kind).not.toBe(measured.kind)
    expect('rate' in unanswerable).toBe(false)
  })

  it('answers a withheld family as withheld, with the reading that barred it', () => {
    const [withheld] = only('withheld')

    expect('family' in withheld && withheld.family).toBe('wrongful_commitment')
    expect('reason' in withheld && withheld.reason).toBe('kappa_below_floor')
    expect('stated' in withheld && withheld.stated).toContain(
      'below the declared floor of 0.60',
    )
    expect('note' in withheld && withheld.note).toContain('not a rate of zero')
    expect('note' in withheld && withheld.note).toContain('not a family that held')
    for (const field of ['rate', 'counts', 'interval', 'confidence', 'band']) {
      expect(field in withheld).toBe(false)
    }

    // Absent from the families that carry a rate, rather than present with a caveat.
    expect(answered().map((answer) => answer.family)).not.toContain(
      'wrongful_commitment',
    )
  })

  it('answers a category the bench never tests with the reason it does not', () => {
    const categories = only('not_tested')

    expect(
      categories.map((answer) => 'category' in answer && answer.category),
    ).toEqual([
      'data poisoning',
      'model poisoning',
      'output integrity',
      'lifecycle consistency',
    ])
    for (const answer of categories) {
      expect('reason' in answer && answer.reason).not.toBe('')
      // A category and never a family: the bench has no family here, so there is no
      // question of its own and nothing to mistake for something that was measured.
      expect('family' in answer).toBe(false)
      expect('question' in answer).toBe(false)
      expect('rate' in answer).toBe(false)
      expect('note' in answer && answer.note).toContain(
        'not a family the bench tried and could not measure',
      )
    }
  })
})

describe('the run these answers are drawn from', () => {
  it('is named, with a link to the report they came out of', () => {
    const from = block().drawnFrom

    expect(from.runId).toBe(THE_COMPLETED_RUN.run_id)
    expect(from.target).toBe('staging support agent')
    expect(from.recordedAt).toBe('2026-08-19T09:38:37+00:00')
    expect(from.path).toBe(reportPath(THE_COMPLETED_RUN.run_id))
    expect(from.path).toContain(THE_COMPLETED_RUN.run_id)
    expect(from.statement).toContain('one target measured once')
    expect(from.statement).toContain('nothing here is an average over runs')
  })

  it('is the most recent run that may have one, in the route’s own order', () => {
    const candidates = theRunsToDrawFrom(LISTED)

    expect(candidates.map((there) => there.run_id)).toEqual([
      THE_COMPLETED_RUN.run_id,
      'aaaabbbb-cccc-dddd-eeee-ffff00001111',
    ])
    // A run still going and a run nobody answered have no report to draw from.
    for (const candidate of candidates) {
      expect(candidate.status).toBe('completed')
    }
  })

  it('states the absence when no run has produced one', () => {
    expect(theRunsToDrawFrom({ statement: 'no rows', runs: [] })).toEqual([])
    expect(
      theRunsToDrawFrom({ statement: 'one row', runs: [LISTED.runs[0]] }),
    ).toEqual([])
    // A stated absence rather than a block of unanswered questions, and explicitly
    // none of the three kinds of nothing.
    expect(NO_SIGNED_REPORT_YET).toContain('A stated absence rather than an answer')
    expect(NO_SIGNED_REPORT_YET).toContain('not tested')
    expect(NO_SIGNED_REPORT_YET).toContain('not measurable')
    expect(NO_SIGNED_REPORT_YET).toContain('rate of zero')
  })
})

/** The answers of one kind, of which there is at least one in the fixture. */
function only(kind: QuestionnaireAnswer['kind']): QuestionnaireAnswer[] {
  const found = block().answers.filter((answer) => answer.kind === kind)
  expect(found.length).toBeGreaterThan(0)
  return found
}

/**
 * The block with the answers taken out, and nothing else.
 *
 * What is left is everything that must not vary with which families were answered.
 */
function withoutTheAnswers(whole: ReturnType<typeof questionnaire>) {
  const { answers: _answers, ...rest } = whole
  return rest
}
