/**
 * What the interrupt will not show, and what it will not send.
 *
 * The spec expects these screens to be driven by hand and does not justify a
 * browser-driver harness, so what is automated here is what a person cannot check
 * faster than a test can: that no figure or derived value the screen builds
 * combines the two layers, that a confirmed answer is unreachable without an
 * explicit confirmation against figures this app is actually holding, and that the
 * answer which spends nothing is a plain no rather than a second confirmation.
 * Whether the page *reads* like a control that blocks is the part a person checks
 * faster, and it was driven by hand against the real API.
 *
 * The fixture is the shape `POST /runs` returns — `BudgetPayload`, `snake_case`,
 * with the bounded total and the hard ceiling in it, because the criterion is the
 * absence of those two from the view and an absence is only assertable against
 * fields that are really on the wire. Its numbers are chosen so that no blended
 * value could appear by coincidence: the layers are 181 and 96, their total 277,
 * their average 138.5, and the two ceilings 543 and 288 summing to 831.
 */

import { describe, expect, it } from 'vitest'

import type { RunEstimate } from '../api/bench'
import {
  AWAITING_APPROVAL,
  confirmationRequest,
  costFigures,
  declineRequest,
  interruptView,
  rememberWhoAttested,
  whoAttested,
  rememberTheFigures,
  theFiguresPresented,
  type Confirming,
  type FigureStore,
} from './interrupt'

/** The consent surface for one target, exactly as the bench sends it. */
function estimated(): RunEstimate {
  return {
    scored: {
      calls: 181,
      kind: 'exact',
      basis: '18 cases × 10 attempts + 1 registration probe, × 1 target',
      cost: '3.62 USD',
    },
    adaptive: {
      calls: 96,
      kind: 'ceiling',
      basis: '6 families × T=8 × k=2, × 1 target',
      cost: '≤ 1.92 USD',
    },
    total: {
      calls: 277,
      kind: 'ceiling',
      basis:
        '18 cases × 10 attempts + 1 registration probe, × 1 target; plus 6 ' +
        'families × T=8 × k=2, × 1 target',
      cost: '≤ 5.54 USD',
    },
    hard_ceiling: {
      calls: 831,
      kind: 'ceiling',
      basis:
        '543 scored + 288 adaptive, enforced per layer — every message retried ' +
        'to its target’s transport limit (at most 3 sends)',
      cost: '≤ 16.62 USD',
    },
    scored_ceiling: 543,
    adaptive_ceiling: 288,
    currency: 'USD',
    presented: [
      '  Scored layer         181 calls    3.62 USD   exact',
      '  Adaptive layer      ≤ 96 calls   ≤ 1.92 USD   ceiling',
      '  Total              ≤ 277 calls   ≤ 5.54 USD   ceiling — if no message is retried',
      '  Hard ceiling       ≤ 831 calls  ≤ 16.62 USD   ceiling — the limit',
    ],
  }
}

/** Everything declared, so each test can withhold exactly one thing. */
function confirming(): Confirming {
  return {
    status: AWAITING_APPROVAL,
    figures: estimated(),
    confirmed: true,
    identity: 'operator',
    reason: '',
  }
}

/** A `sessionStorage` that runs in node, which is where these tests run. */
function aStore(): FigureStore {
  const held = new Map<string, string>()
  return {
    getItem: (key) => held.get(key) ?? null,
    setItem: (key, value) => {
      held.set(key, value)
    },
  }
}

describe('the two cost figures', () => {
  it('are two, the fixed suite exact and the adaptive layer a ceiling', () => {
    const figures = costFigures(estimated())

    expect(figures).toHaveLength(2)
    expect(figures.map((figure) => figure.layer)).toEqual(['scored', 'adaptive'])
    expect(figures[0]).toMatchObject({ calls: '181', kind: 'exact' })
    // The `≤` is in the number a person reads rather than in a column beside it:
    // an attacker choosing its own route has no exact cost, and an average one
    // would invite a run to exceed what was agreed to.
    expect(figures[1]).toMatchObject({ calls: '≤ 96', kind: 'ceiling' })
  })

  it('carry no number, and no word, that spans the two layers', () => {
    const rendered = JSON.stringify(interruptView(estimated()))

    // The bounded total, the summed hard ceiling, and the average of the two —
    // every figure that could be read as one number for the whole run.
    expect(rendered).not.toContain('277')
    expect(rendered).not.toContain('831')
    expect(rendered).not.toContain('138.5')
    expect(rendered).not.toContain('5.54')
    expect(rendered).not.toContain('16.62')
    // `presented` is the bench's own rendered table and it has a Total row in it.
    // Rendering that list verbatim is the one-line way this screen would acquire
    // a total, so the word itself is asserted absent.
    expect(rendered).not.toContain('Total')
  })

  it('show each layer beside the ceiling that layer alone is enforced against', () => {
    const [scored, adaptive] = costFigures(estimated())

    // Both carry `≤`, because nothing an operator is shown with a `≤` in front of
    // it may be exceeded — and they are two limits rather than one, because the
    // budget checks them per layer.
    expect(scored.ceiling).toBe('≤ 543')
    expect(adaptive.ceiling).toBe('≤ 288')
  })

  it('carry the cost the bench rendered, including “not priced”', () => {
    const unpriced = estimated()
    unpriced.scored.cost = 'not priced'
    unpriced.adaptive.cost = 'not priced'

    const figures = costFigures(unpriced)

    // Never `0.00`: an unknown cost and a free run are different facts, and only
    // one of them is safe to confirm without reading further.
    expect(figures.map((figure) => figure.cost)).toEqual([
      'not priced',
      'not priced',
    ])
  })
})

describe('the confirmation', () => {
  it('is a body only when every part of it was done, and it is confirmed true', () => {
    const request = confirmationRequest(confirming())

    expect(request.kind).toBe('ready')
    expect(request.kind === 'ready' && request.body).toEqual({
      confirmed: true,
      reason: '',
    })
  })

  it('is withheld by anything short of an explicit confirmation', () => {
    const unticked = { ...confirming(), confirmed: false }
    // A truthy value is not a confirmation. The guard at the other end of the wire
    // reads the resume value the same way, and for the same reason: something that
    // merely looks like a yes must not spend somebody's inference budget.
    const truthy = { ...confirming(), confirmed: 1 as unknown as boolean }

    for (const declared of [unticked, truthy]) {
      const request = confirmationRequest(declared)
      expect(request.kind).toBe('withheld')
      expect(request.kind === 'withheld' && request.missing.join(' ')).toContain(
        'the two figures have not been confirmed',
      )
    }
  })

  it('is withheld when this app is not holding the figures to confirm', () => {
    const request = confirmationRequest({ ...confirming(), figures: null })

    expect(request.kind).toBe('withheld')
    expect(request.kind === 'withheld' && request.missing.join(' ')).toContain(
      'not holding the figures',
    )
  })

  it('is withheld for a run that is not holding an interrupt', () => {
    // An interrupt is answered once. A second yes is consent recorded for a spend
    // already under way, and a yes after the wait ran out is consent for a run the
    // graph has already been told nobody authorised.
    for (const status of [
      'running',
      'declined',
      'unanswered',
      'aborted',
      'failed',
      'completed',
      'registration_refused',
    ]) {
      const request = confirmationRequest({ ...confirming(), status })
      expect(request.kind).toBe('withheld')
      expect(request.kind === 'withheld' && request.missing.join(' ')).toContain(
        'is not holding an interrupt',
      )
    }
  })

  it('is not withheld for want of a name, because no field asks for one', () => {
    // The identity requirement came off with the field. What this function guards is
    // the spend — the tick, the figures and the status — and a run held up over a
    // name nobody was asked for would make declining the easier of the two answers.
    const request = confirmationRequest({ ...confirming(), identity: '   ' })

    expect(request.kind).toBe('ready')
  })

  it('sends no name, whatever the screen is holding', () => {
    // The name a registration was attested by is still held in this browser, and it
    // no longer goes on the wire: the operator on the record is the one the API
    // verified the request as, and a body still carrying `identity` is refused
    // (ADR-0116 §1). `toEqual` is the assertion — an extra key fails it.
    const store = aStore()
    rememberWhoAttested(store, 'run-1', '  Matteo Rinaldi  ')

    const request = confirmationRequest({
      ...confirming(),
      identity: whoAttested(store, 'run-1'),
    })

    expect(request.kind === 'ready' && request.body).toEqual({
      confirmed: true,
      reason: '',
    })
  })
})

describe('declining', () => {
  it('is a no on the wire and can never be read as a yes', () => {
    const body = declineRequest('the adaptive ceiling is too high')

    expect(body.confirmed).toBe(false)
    expect(body.reason).toBe('the adaptive ceiling is too high')
  })

  it('asks for nothing first, so the safe answer is never the harder one', () => {
    const body = declineRequest('')

    expect(body.confirmed).toBe(false)
    expect(Object.keys(body).sort()).toEqual(['confirmed', 'reason'])
    // A stated reason either way: a declined run is a result about the estimate,
    // and it is recorded as declined rather than left to time out as unanswered.
    expect(body.reason).toContain('declined at the approval interrupt')
  })
})

describe('the figures handed over by the registration that made the run', () => {
  it('come back for the run they were held for', () => {
    const store = aStore()
    const estimate = estimated()

    rememberTheFigures(store, 'run-1', estimate)

    expect(theFiguresPresented(store, 'run-1')).toEqual(estimate)
  })

  it('carry the name that attested them, and never another run’s', () => {
    const store = aStore()

    rememberWhoAttested(store, 'run-1', 'Matteo Rinaldi')

    expect(whoAttested(store, 'run-1')).toBe('Matteo Rinaldi')
    // The interrupt asks for no name, so an empty one is the answer for a run this
    // browser did not register — not the name of the last run it did.
    expect(whoAttested(store, 'run-2')).toBe('')
  })

  it('are never another run’s figures', () => {
    const store = aStore()
    rememberTheFigures(store, 'run-1', estimated())

    expect(theFiguresPresented(store, 'run-2')).toBeNull()
  })

  it('read as not held when they are not a whole estimate', () => {
    // Half-recognised figures would be a screen showing one number where there are
    // two, in front of somebody about to agree to it. `null` is the answer that
    // cannot mislead, because the screen offers no confirmation for it.
    const store = aStore()
    const { scored } = estimated()

    store.setItem('agentaudit.estimate.torn', JSON.stringify({ scored }))
    store.setItem('agentaudit.estimate.garbage', 'not json at all')
    store.setItem('agentaudit.estimate.nothing', 'null')

    expect(theFiguresPresented(store, 'torn')).toBeNull()
    expect(theFiguresPresented(store, 'garbage')).toBeNull()
    expect(theFiguresPresented(store, 'nothing')).toBeNull()
  })

  it('leave a confirmation unreachable when there are none', () => {
    const store = aStore()

    const figures = theFiguresPresented(store, 'run-nobody-registered')
    const request = confirmationRequest({ ...confirming(), figures })

    expect(figures).toBeNull()
    expect(request.kind).toBe('withheld')
  })
})
