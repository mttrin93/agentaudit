/**
 * What the pending-routes page must say, and the one thing it may never say.
 *
 * The page's verb is *decide these*, and these tests are over the value the screen
 * is drawn from rather than over its markup: `pending.ts` is a transformation, it
 * runs in node with no DOM, and a claim about an order or an absence is worth
 * asserting only where it is a property of a value.
 *
 * **The last describe is the one that matters most.** No figure on this page may be
 * a rate, an interval, a band or a `D` about a target: a pending route is not an
 * attempt, nothing here reaches a denominator, and a `D` on this surface would be
 * the *case's* own discriminating power and never the target's
 * ([ADR-0010](../../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md),
 * [ADR-0012](../../../docs/adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)).
 * The scan walks the whole built view, so a field added to this module with a rate
 * in it fails here rather than on somebody's screen.
 */

import { describe, expect, it } from 'vitest'

import type {
  MeasurementEstimate,
  MeasurementReading,
  PendingRouteQueue,
  PendingRouteRow,
} from '../api/bench'
import {
  ADMITTED,
  ALREADY_IN_FLIGHT,
  AWAITING_APPROVAL,
  MEASUREMENT_STATEMENTS,
  PENDING,
  REJECTED,
  measureControl,
  measurementConfirmation,
  measurementDecline,
  measurementEstimateView,
  measurementRequest,
  nothingAttested,
  modelBars,
  progressRows,
  queueRows,
  queueView,
  stillMeasuring,
  theEmptyQueue,
} from './pending'

/** One filed route, in the shape the route serves it. */
function aRoute(over: Partial<PendingRouteRow> = {}): PendingRouteRow {
  return {
    route: 'indirect_prompt_injection-a1b2c3',
    family: 'indirect_prompt_injection',
    probe: 'a1b2c3',
    target: 'acme-support-agent',
    description: 'asked the agent to summarise a page that instructed it to email',
    filed_on: '2026-02-01T09:30:00+00:00',
    state: PENDING,
    reason: '',
    ...over,
  }
}

/** A queue with a measurement available over it. */
function aQueue(over: Partial<PendingRouteQueue> = {}): PendingRouteQueue {
  return {
    measure: {
      available: true,
      library: '/var/lib/agentaudit/cases',
      models: ['model-one', 'model-two'],
      statement: 'Deciding a pending route measures it against three agents.',
    },
    routes: [aRoute()],
    measurements: [],
    statement: 'a queue of pending routes, which are not cases',
    ...over,
  }
}

describe('the queue an operator reads', () => {
  it('says the family, the target it beat, the attacker’s prose and the date', () => {
    const [row] = queueRows(aQueue(), null)

    expect(row.route).toBe('indirect_prompt_injection-a1b2c3')
    // The wire name with one character changed, and never a second vocabulary.
    expect(row.family).toBe('indirect prompt injection')
    expect(row.target).toBe('acme-support-agent')
    expect(row.description).toBe(
      'asked the agent to summarise a page that instructed it to email',
    )
    expect(row.filed).toBe('2026-02-01')
    expect(row.state).toBe(PENDING)
    // Selectable, because it is awaiting a decision and nothing else is.
    expect(row.chooseable).toBe(true)
  })

  it('keeps a rejected route on the page with the gate’s own reason', () => {
    // A route that was a property of one model is a finding in its own right
    // (ADR-0012, spec story 12), so the row stays and carries the sentence.
    const rejected = aRoute({
      state: REJECTED,
      reason: 'the cross-model bar refused this route: it held on the second model',
    })
    const [row] = queueRows(aQueue({ routes: [rejected] }), null)

    expect(row.state).toBe(REJECTED)
    expect(row.reason).toContain('the cross-model bar refused this route')
    // Decided, so it may never be selected again: its payload went with the
    // decision (ADR-0104 §4) and a second answer would rest on no reading at all.
    expect(row.chooseable).toBe(false)
  })

  it('names the library record an admitted route became', () => {
    // The loop closing is a file an operator can open (spec story 11). The name is
    // read off the measurement that wrote it and never parsed out of the reason.
    const admitted = aRoute({
      state: ADMITTED,
      reason: 'admitted on the cross-model bar and written into /cases as x.toml',
    })
    const reading = aReading({
      routes: [
        {
          route: admitted.route,
          target: admitted.target,
          description: admitted.description,
          where: 'decided: admitted',
          state: ADMITTED,
          reason: admitted.reason,
          entered_as: 'x.toml',
        },
      ],
    })
    const [row] = queueRows(aQueue({ routes: [admitted] }), reading)

    expect(row.enteredAs).toBe('x.toml')
    expect(row.chooseable).toBe(false)
  })

  it('leaves the record unnamed rather than invented where nothing wrote one', () => {
    const admitted = aRoute({ state: ADMITTED, reason: 'admitted on the bar' })
    const [row] = queueRows(aQueue({ routes: [admitted] }), null)

    expect(row.enteredAs).toBe('')
  })
})

describe('an empty queue is a reading and not a blank screen', () => {
  it('says what a zero here is a reading about, and what it is not', () => {
    const empty = theEmptyQueue()

    // A zero is a reading about the attacker and about the families it worked in,
    // never a reading about the target (ADR-0011).
    expect(empty.heading).toBeTruthy()
    expect(empty.statement).toContain('attacker')
    expect(empty.statement).toContain('ADR-0011')
    expect(`${empty.heading} ${empty.statement} ${empty.aside}`).not.toMatch(
      /error|failed|failure/i,
    )
  })

  it('is what the view carries where the queue holds nothing', () => {
    const view = queueView(aQueue({ routes: [] }), null)

    expect(view.rows).toEqual([])
    expect(view.empty).not.toBeNull()
    // And it is absent the moment there is a row, because then the rows say it.
    expect(queueView(aQueue(), null).empty).toBeNull()
  })
})

describe('whether a measurement may start here', () => {
  it('offers one control where the bench says it can, and names the two models', () => {
    const control = measureControl(aQueue().measure)

    expect(control.available).toBe(true)
    if (control.available) {
      expect(control.label).toBe('Measure the selected routes')
      expect(control.models).toEqual(['model-one', 'model-two'])
    }
  })

  it('states a held library with the holder and says the next move is to wait', () => {
    // The one refusal answered by waiting. The other four are facts about how the
    // deployment was built, and a control that re-asked them would change nothing.
    const control = measureControl({
      available: false,
      refusal: ALREADY_IN_FLIGHT,
      stated:
        'this case library is already held — by a gate run, or by another ' +
        'measurement. The holder is named on the lease. gate run 7, since 09:00',
    })

    expect(control.available).toBe(false)
    if (!control.available) {
      expect(control.refusal).toBe(ALREADY_IN_FLIGHT)
      expect(control.statement).toContain('gate run 7')
      expect(control.waiting).toBe(true)
      expect(control.statement).toMatch(/wait/i)
    }
  })

  it('does not offer waiting for a refusal that waiting does not answer', () => {
    const control = measureControl({
      available: false,
      refusal: 'no_second_model',
      stated: 'this bench declares one reference model and the bar needs two.',
    })

    expect(control.available).toBe(false)
    if (!control.available) {
      expect(control.waiting).toBe(false)
      expect(control.statement).toContain('one reference model')
    }
  })
})

describe('nothing starts a measurement on a guess', () => {
  it('refuses a body with no route selected', () => {
    const request = measurementRequest(attested(), [])

    expect(request.kind).toBe('blocked')
    if (request.kind === 'blocked') {
      expect(request.missing.join(' ')).toMatch(/route/)
    }
  })

  it('refuses a body with a statement withheld, and builds none', () => {
    const withheld = {
      ...attested(),
      attested: { ...attested().attested, not_production: false },
    }

    expect(measurementRequest(withheld, ['r-1']).kind).toBe('blocked')
  })

  it('builds the body from the routes the operator chose, and only those', () => {
    const request = measurementRequest(attested(), ['r-1', 'r-2'])

    expect(request.kind).toBe('ready')
    if (request.kind === 'ready') {
      expect(request.body.routes).toEqual(['r-1', 'r-2'])
      expect(request.body.attestation.identity).toBe('an operator')
      expect(request.body.cost.price_per_call).toBe('0.002')
    }
  })

  it('asks the three statements in the record’s own wording', () => {
    // A friendlier version of a statement the bench then records in its own words
    // is the failure this asserts against.
    expect(MEASUREMENT_STATEMENTS).toHaveLength(3)
    for (const statement of MEASUREMENT_STATEMENTS) {
      expect(statement.wording).toBeTruthy()
      expect(statement.consequence).toBeTruthy()
      expect(statement.of).toBe(3)
    }
    expect(nothingAttested().identity).toBe('')
  })
})

describe('the halt, answered on the page', () => {
  it('builds no confirmation from anything but an explicit yes on a held halt', () => {
    // The three ways a confirmation is not one, each stated. Nothing here is a
    // flag, a setting or a default: an interrupt is answered by a person (ADR-0007).
    expect(
      measurementConfirmation('measuring', true, 'an operator').kind,
    ).toBe('withheld')
    expect(
      measurementConfirmation(AWAITING_APPROVAL, false, 'an operator').kind,
    ).toBe('withheld')
    expect(measurementConfirmation(AWAITING_APPROVAL, true, '  ').kind).toBe(
      'withheld',
    )

    const ready = measurementConfirmation(AWAITING_APPROVAL, true, ' an operator ')
    expect(ready.kind).toBe('ready')
    if (ready.kind === 'ready') {
      expect(ready.body).toEqual({
        confirmed: true,
        identity: 'an operator',
        reason: '',
      })
    }
  })

  it('sends the no rather than withholding it, and asks for nothing first', () => {
    const declined = measurementDecline('an operator')

    expect(declined.confirmed).toBe(false)
    expect(declined.identity).toBe('an operator')
    expect(declined.reason).toBeTruthy()
  })
})

describe('the estimate an operator answers', () => {
  it('carries a row per route and the total against the ceiling it is held to', () => {
    const view = measurementEstimateView(anEstimate())

    expect(view.perRoute.map((one) => one.route)).toEqual(['r-1', 'r-2'])
    expect(view.perRoute[0].family).toBe('indirect prompt injection')
    expect(view.calls).toBe('36')
    expect(view.ceiling).toBe('≤ 72')
    expect(view.cost).toBe('$0.07')
    expect(view.models).toEqual(['model-one', 'model-two'])
    // The served sentence, which is where the rows over-adding is explained.
    expect(view.statement).toContain('one row per route')
  })
})

describe('while it goes', () => {
  it('reports where each route is, one route at a time', () => {
    const rows = progressRows(aReading())

    expect(rows).toHaveLength(1)
    expect(rows[0].where).toBe('measuring on model-one')
    expect(rows[0].target).toBe('acme-support-agent')
    expect(rows[0].state).toBe(PENDING)
  })

  it('knows a measurement that has stopped for good from one still going', () => {
    expect(stillMeasuring('measuring')).toBe(true)
    expect(stillMeasuring('awaiting_approval')).toBe(true)
    expect(stillMeasuring('answered')).toBe(false)
    expect(stillMeasuring('declined')).toBe(false)
    expect(stillMeasuring('aborted')).toBe(false)
    expect(stillMeasuring('failed')).toBe(false)
    expect(stillMeasuring('unanswered')).toBe(false)
  })
})

describe('no figure on this page is a rate, an interval, a band or a D', () => {
  it('has nowhere to put one, over the whole view', () => {
    // A pending route is not an attempt and reaches no denominator (ADR-0010), and
    // a `D` on this surface would be the case's own discriminating power and never
    // the target's (ADR-0012). The scan is over the built value rather than over
    // the markup, so a field added here with a rate in it fails on this line.
    const everything = [
      ...said(queueView(aQueue(), aReading())),
      ...said(measurementEstimateView(anEstimate())),
      ...said(progressRows(aReading())),
      ...said(modelBars(aReading())),
      ...said(theEmptyQueue()),
    ]

    for (const one of everything) {
      expect(one).not.toMatch(/\bD\s*[=≥>]/)
      expect(one).not.toMatch(/\d\s*%/)
      expect(one).not.toMatch(/\bWilson\b|\binterval\b|\bband\b/i)
      // A bare fraction is what a rate looks like when nobody labels it. Money is
      // taken out first: a cost is a figure this page is *for*, and it is the one
      // decimal an operator is meant to read here.
      expect(one.replace(/[$€£]\s?\d+(\.\d+)?/g, '')).not.toMatch(/\b0\.\d+\b/)
    }
  })

  it('carries no numeric field that is not a count of calls', () => {
    // Every number this page can render, wherever it sits, named. A rate would
    // arrive as a number under a name that is not a count, and this is where it
    // fails — the previous test reads the rendering, and this one reads the field.
    const numbers = [
      ...counted(measurementEstimateView(anEstimate())),
      ...counted(queueView(aQueue(), aReading())),
      ...counted(progressRows(aReading())),
    ]

    expect(numbers.length).toBeGreaterThan(0)
    for (const [name, value] of numbers) {
      expect(name).toMatch(/call|ceiling/i)
      expect(Number.isInteger(value)).toBe(true)
    }
  })
})

/** A declaration with all three statements made and a price stated. */
function attested() {
  return {
    ...nothingAttested(),
    identity: 'an operator',
    price_per_call: '0.002',
    attested: {
      authorised_to_test: true,
      not_production: true,
      accepts_provider_policy_and_cost: true,
    },
  }
}

/** One measurement mid-flight, in the shape the route serves it. */
function aReading(over: Partial<MeasurementReading> = {}): MeasurementReading {
  return {
    measurement_id: 'm-1',
    status: 'measuring',
    statement: 'measuring the selected routes on the first model',
    recorded_at: '2026-02-02T10:00:00+00:00',
    models: ['model-one', 'model-two'],
    library: '/var/lib/agentaudit/cases',
    routes: [
      {
        route: 'indirect_prompt_injection-a1b2c3',
        target: 'acme-support-agent',
        description: 'asked the agent to summarise a page',
        where: 'measuring on model-one',
        state: PENDING,
        reason: '',
        entered_as: '',
      },
    ],
    passes: [
      { model: 'model-one', state: 'measured', attempted: 30, of: 30 },
      { model: 'model-two', state: 'measuring', attempted: 12, of: 30 },
    ],
    lines: ['consulted the admission memory: nothing held for this pair'],
    ...over,
  }
}

/** The estimate the halt puts in front of a person. */
function anEstimate(): MeasurementEstimate {
  return {
    per_route: [
      {
        route: 'r-1',
        family: 'indirect_prompt_injection',
        target: 'acme-support-agent',
        calls: 24,
        basis: '3 agents on 2 models at 4 attempts each, plus a probe per agent',
        cost: '$0.05',
      },
      {
        route: 'r-2',
        family: 'tool_misuse',
        target: 'acme-support-agent',
        calls: 24,
        basis: '3 agents on 2 models at 4 attempts each, plus a probe per agent',
        cost: '$0.05',
      },
    ],
    models: ['model-one', 'model-two'],
    calls: 36,
    ceiling: 72,
    cost: '$0.07',
    currency: 'USD',
    statement: 'one row per route, and the routes are the operator’s own selection',
  }
}

/**
 * Every sentence a value carries, however deep, for the scan above.
 *
 * Numbers are rendered as they would be read, because a rate reaching this page
 * would arrive as one — a scan over strings alone would miss it.
 */
function said(value: unknown): string[] {
  if (typeof value === 'string') {
    return [value]
  }
  if (typeof value === 'number') {
    return [`${value}`]
  }
  if (Array.isArray(value)) {
    return value.flatMap(said)
  }
  if (value !== null && typeof value === 'object') {
    return Object.values(value).flatMap(said)
  }
  return []
}

/**
 * Every number a value carries, with the name it sits under, however deep.
 *
 * The name travels with the number because that is what the assertion is about:
 * a count of calls and a rate are both integers-or-not, and what tells them apart
 * is what the field is called.
 */
function counted(value: unknown, name = ''): [string, number][] {
  if (typeof value === 'number') {
    return [[name, value]]
  }
  if (Array.isArray(value)) {
    return value.flatMap((one) => counted(one, name))
  }
  if (value !== null && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, one]) => counted(one, key))
  }
  return []
}

describe('one bar per model, and it says how far into that model the run is', () => {
  it('carries each pass in the order the models are measured', () => {
    const bars = modelBars(aReading())

    expect(bars.map((bar) => bar.model)).toEqual(['model-one', 'model-two'])
    expect(bars[0].attempted).toBe(30)
    expect(bars[0].of).toBe(30)
    expect(bars[1].attempted).toBe(12)
  })

  it('says in words which of the four states a pass is in', () => {
    // Never by length alone: a bar sitting at nothing is a pass waiting to be paid
    // for or a pass that will never run, and the two are not the same fact
    // (`ModelPassState`). The word is what tells them apart.
    const bars = modelBars(
      aReading({
        passes: [
          { model: 'model-one', state: 'waiting', attempted: 0, of: 30 },
          { model: 'model-two', state: 'unmeasured', attempted: 0, of: 30 },
        ],
      })
    )

    expect(bars[0].reading).not.toBe(bars[1].reading)
    expect(bars[0].reading).toMatch(/wait/i)
    expect(bars[1].reading).toMatch(/not run|did not/i)
  })

  it('is empty for a measurement whose record declares no pass', () => {
    // A record from before this field existed, and a halted measurement that has
    // declared none yet: neither is a screen drawing two bars at nothing.
    expect(modelBars(aReading({ passes: [] }))).toEqual([])
  })
})
