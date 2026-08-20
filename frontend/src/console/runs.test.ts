/**
 * What the run list must show, and the one figure it must never show.
 *
 * Five claims, each a way this could quietly go wrong rather than a restatement of
 * the view's shape. That a row carries what an operator needs to find a run again
 * and a link to it. That the two layers' figures are never blended — not per run,
 * not down a column, not as an average — asserted over a payload whose figures are
 * chosen so that no such quantity could appear by coincidence. That a run nobody
 * answered shows zero in both layers with its standing named, so an abandoned run
 * stays distinguishable from a cheap one. That the two columns are distinguished by
 * layer, in a hue *and* in words. And that a bench with no runs says so rather than
 * drawing an empty table.
 *
 * The blend test is the one that matters in a year. A totals column is the most
 * natural thing in the world to add to a table of two numbers, and the moment it
 * exists an adaptive quantity has been added to a scored one (ADR-0010). Every
 * number and every string anywhere in the view is scanned for it, so a `reduce`
 * added later fails here rather than in review.
 */

import { describe, expect, it } from 'vitest'

import type { RunList, RunRow } from '../api/bench'
import { runPath } from './rail'
import { NO_RUNS_YET, runsReading, type RunReading } from './runs'

const SPENT_IN_THE_SCORED_LAYER =
  'calls the scored layer put on the wire for this run, held to the scored ' +
  'layer’s own ceiling'

const SPENT_IN_THE_ADAPTIVE_LAYER =
  'calls the adaptive layer put on the wire for this run, held to the adaptive ' +
  'layer’s own ceiling'

const NOTHING_ON_THE_WIRE =
  'nothing: this layer put no call on the operator’s endpoint. A fact about the ' +
  'wire, checkable against the endpoint, and not a measurement of the target'

/**
 * Three runs, with per-layer spends chosen so that no blend of them could appear
 * by accident.
 *
 * The figures a row is allowed to show are `{181, 96, 37, 8, 0}`. Every quantity a
 * reader could construct out of them is outside that set: 277 and 45 per run, 218
 * and 104 down the two columns, 322 over everything, and the means 138.5 and 22.5.
 * The same trick the report fixture plays with its three published rates, for the
 * same reason — an absence asserted against figures that could coincide is an
 * absence nobody checked.
 *
 * The third run is the one nobody answered: zero in both layers, and its own
 * standing.
 */
const LISTED: RunList = {
  statement: 'one row per run, with calls spent in two figures',
  runs: [
    row({
      run_id: 'e5f4d3c2-b1a0-4c3d-8e7f-6a5b4c3d2e1f',
      target: 'staging-assistant',
      recorded_at: '2026-08-19T09:38:37.512345+00:00',
      status: 'completed',
      statement: 'the run finished and its report is served',
      scored: 181,
      adaptive: 96,
    }),
    row({
      run_id: '11112222-3333-4444-5555-666677778888',
      target: 'sandbox-router',
      recorded_at: '2026-08-18T22:04:01.000001+00:00',
      status: 'aborted',
      statement: 'the run stopped on its own ceiling',
      scored: 37,
      adaptive: 8,
    }),
    row({
      run_id: '99990000-1111-2222-3333-444455556666',
      target: 'never-answered',
      recorded_at: '2026-08-17T07:15:59.900000+00:00',
      status: 'unanswered',
      statement:
        'the approval interrupt was never answered, so the run never started. ' +
        'Nothing was sent',
      scored: 0,
      adaptive: 0,
    }),
  ],
}

const NOTHING_LISTED: RunList = { statement: 'no rows', runs: [] }

/** One row as the route serves it, with each layer's own sentence beside it. */
function row(of: {
  run_id: string
  target: string
  recorded_at: string
  status: string
  statement: string
  scored: number
  adaptive: number
}): RunRow {
  return {
    run_id: of.run_id,
    target: of.target,
    recorded_at: of.recorded_at,
    status: of.status,
    statement: of.statement,
    scored: {
      calls_spent: of.scored,
      statement: of.scored ? SPENT_IN_THE_SCORED_LAYER : NOTHING_ON_THE_WIRE,
    },
    adaptive: {
      calls_spent: of.adaptive,
      statement: of.adaptive ? SPENT_IN_THE_ADAPTIVE_LAYER : NOTHING_ON_THE_WIRE,
    },
  }
}

/** The rows of a reading that listed some, or a failure saying it listed none. */
function rowsOf(list: RunList): RunReading[] {
  const reading = runsReading(list)
  if (!reading.listed) {
    throw new Error('this reading listed no runs')
  }
  return reading.runs
}

/** Every number anywhere in the view, which is every figure it can show. */
function everyNumber(node: unknown): number[] {
  if (typeof node === 'number') {
    return [node]
  }
  if (Array.isArray(node)) {
    return node.flatMap(everyNumber)
  }
  if (node && typeof node === 'object') {
    return Object.values(node).flatMap(everyNumber)
  }
  return []
}

/**
 * Every string anywhere in the view except the timestamps.
 *
 * The timestamps are left out because they are digits around a decimal point and
 * nothing else: `22:04:01.000001` holds the text `22.5`-shaped fragments by
 * accident, so a scan for an average that read the clock would fail on the hour a
 * run started rather than on an average somebody printed.
 */
function everyString(node: unknown, key = ''): string[] {
  if (typeof node === 'string') {
    return key === 'recordedAt' ? [] : [node]
  }
  if (Array.isArray(node)) {
    return node.flatMap((item) => everyString(item))
  }
  if (node && typeof node === 'object') {
    return Object.entries(node).flatMap(([name, value]) => everyString(value, name))
  }
  return []
}

describe('the runs on the record', () => {
  it('carries the target, when it was recorded, its standing and a link to the run', () => {
    const rows = rowsOf(LISTED)

    expect(rows.map((there) => there.target)).toEqual([
      'staging-assistant',
      'sandbox-router',
      'never-answered',
    ])
    expect(rows.map((there) => there.standing)).toEqual([
      'Completed',
      'Aborted',
      'Unanswered',
    ])
    expect(rows[0].recordedAt).toBe('2026-08-19T09:38:37.512345+00:00')
    expect(rows[0].statement).toBe('the run finished and its report is served')

    // Each row links to the run it names, at the path the rail builds.
    for (const there of rows) {
      expect(there.path).toBe(runPath(there.id))
      expect(there.path).toContain(there.id)
    }
    expect(rows.map((there) => there.id)).toEqual(
      LISTED.runs.map((served) => served.run_id),
    )
  })

  it('reports calls spent in two figures per run, one per layer', () => {
    const rows = rowsOf(LISTED)

    expect(rows.map((there) => there.scored.calls)).toEqual([181, 37, 0])
    expect(rows.map((there) => there.adaptive.calls)).toEqual([96, 8, 0])
    expect(rows[0].scored.statement).toBe(SPENT_IN_THE_SCORED_LAYER)
    expect(rows[0].adaptive.statement).toBe(SPENT_IN_THE_ADAPTIVE_LAYER)
  })

  it('keeps the order the bench listed them in, most recent first', () => {
    expect(rowsOf(LISTED).map((there) => there.recordedAt)).toEqual(
      LISTED.runs.map((served) => served.recorded_at),
    )
  })
})

describe('the two layers are never blended into a third figure', () => {
  it('shows no sum, no column total and no average anywhere', () => {
    const reading = runsReading(LISTED)
    const shown = new Set(everyNumber(reading))

    expect(shown).toEqual(new Set([181, 96, 37, 8, 0]))

    const spends = LISTED.runs.map((served) => [
      served.scored.calls_spent,
      served.adaptive.calls_spent,
    ])
    const perRun = spends.map(([scored, adaptive]) => scored + adaptive)
    const columns = [
      spends.reduce((so_far, [scored]) => so_far + scored, 0),
      spends.reduce((so_far, [, adaptive]) => so_far + adaptive, 0),
    ]
    const everything = [perRun.reduce((so_far, run) => so_far + run, 0)]

    for (const blended of [...perRun, ...columns, ...everything]) {
      if (blended === 0) {
        // A run that spent nothing sums to nothing, which is a figure a row is
        // allowed to show. Every other blend is not.
        continue
      }
      expect(shown.has(blended)).toBe(false)
    }

    // And the averages, which would arrive as text rather than as a number.
    const prose = everyString(reading).join(' ')
    for (const run of perRun) {
      if (run !== 0) {
        expect(prose).not.toContain(`${run / 2}`)
      }
    }
  })

  it('holds the two figures in two named fields and never in a list', () => {
    const [first] = rowsOf(LISTED)

    // Structural, and this is the assertion that matters: there is no field for a
    // total to be printed in, and no array of layers for anything to reduce.
    expect(Object.keys(first).sort()).toEqual([
      'adaptive',
      'id',
      'path',
      'recordedAt',
      'scored',
      'standing',
      'statement',
      'target',
    ])
    expect(Object.keys(first.scored).sort()).toEqual([
      'accent',
      'calls',
      'layer',
      'statement',
    ])
    for (const value of Object.values(first)) {
      expect(Array.isArray(value)).toBe(false)
    }
  })
})

describe('a run that expired unanswered', () => {
  it('shows zero in both layers with its standing named, not a blank', () => {
    const abandoned = rowsOf(LISTED)[2]

    expect(abandoned.scored.calls).toBe(0)
    expect(abandoned.adaptive.calls).toBe(0)
    expect(abandoned.standing).toBe('Unanswered')
    expect(abandoned.standing).not.toBe('Declined')

    // The zero is said in words as well, so it is read as nothing on the wire
    // rather than as a layer that ran and found nothing.
    expect(abandoned.scored.statement).toContain('no call on the operator’s endpoint')
    expect(abandoned.adaptive.statement).toContain(
      'no call on the operator’s endpoint',
    )
  })

  it('is named for what it is, and a state this app does not know is carried through', () => {
    const named = runsReading({
      statement: 'one row',
      runs: [
        row({
          run_id: 'a',
          target: 't',
          recorded_at: '2026-08-19T09:38:37+00:00',
          status: 'a_state_this_app_has_never_seen',
          statement: 'something new',
          scored: 1,
          adaptive: 1,
        }),
      ],
    })

    expect(named.listed && named.runs[0].standing).toBe(
      'a_state_this_app_has_never_seen',
    )
  })
})

describe('the two columns are distinguished by layer', () => {
  it('gives each its own accent and its own name in words', () => {
    const [first] = rowsOf(LISTED)

    expect(first.scored.accent).toBe('scored')
    expect(first.adaptive.accent).toBe('adaptive')
    expect(first.scored.accent).not.toBe(first.adaptive.accent)

    // Redundant with the accent, so nothing here is carried by hue alone.
    expect(first.scored.layer).toBe('Scored layer')
    expect(first.adaptive.layer).toBe('Adaptive layer')
    expect(first.scored.layer).not.toBe(first.adaptive.layer)
  })
})

describe('a bench with no runs on the record', () => {
  it('states the absence rather than drawing an empty table', () => {
    const reading = runsReading(NOTHING_LISTED)

    expect(reading.listed).toBe(false)
    expect(reading.statement).toBe(NO_RUNS_YET)
    expect('runs' in reading).toBe(false)

    // No figure of any kind, so there is no zero to be read as a measurement.
    expect(everyNumber(reading)).toEqual([])
  })
})
