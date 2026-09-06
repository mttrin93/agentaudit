/**
 * Whether this screen is still being told anything, and what it says out loud.
 *
 * The run screen polls every two seconds for the minutes a run takes, and nothing on
 * it distinguished a slow run from a dead poll: the figures on screen are the last
 * ones that arrived either way, and a frozen figure reads exactly like a run that has
 * not moved. What is asserted here is the rule that tells those apart, and the one
 * that decides what the polite region announces — including the part that matters
 * most, that it is not something new every tick.
 */

import { describe, expect, it } from 'vitest'

import {
  STALLED_AFTER_SECONDS,
  announcement,
  liveness,
  type Liveness,
} from './liveness'

/** A moment to count from, so every reading below is arithmetic and not a clock. */
const NOW = Date.parse('2026-03-04T14:03:12Z')

const SECOND = 1000

describe('whether the poll is still being answered', () => {
  it('is answering while the answers keep arriving', () => {
    const live = liveness({ answeredAt: NOW - 2 * SECOND, now: NOW, inFlight: true })
    expect(live.kind).toBe('answering')
    // The stamp is the clock time of the last answer, so a figure on screen can be
    // dated by somebody who was not watching it arrive.
    expect(live.stamp).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('has nothing to date before the first answer arrives', () => {
    const live = liveness({ answeredAt: null, now: NOW, inFlight: true })
    expect(live.kind).toBe('waiting')
    expect(live.stamp).toBe('')
  })

  it('is stalled once the silence passes the declared span', () => {
    const live = liveness({
      answeredAt: NOW - STALLED_AFTER_SECONDS * SECOND,
      now: NOW,
      inFlight: true,
    })
    expect(live.kind).toBe('stalled')
    expect(live.silentFor).toBe(STALLED_AFTER_SECONDS)
  })

  it('is not stalled one second before that span is up', () => {
    const live = liveness({
      answeredAt: NOW - (STALLED_AFTER_SECONDS - 1) * SECOND,
      now: NOW,
      inFlight: true,
    })
    expect(live.kind).toBe('answering')
  })

  it('is settled rather than stalled once the run has stopped', () => {
    // The poll stops itself when a run stops, so the last answer is as old as the
    // reader has had the screen open — and it is the final one rather than a stale
    // one. A run that ended an hour ago is not a bench that has gone quiet.
    const live = liveness({
      answeredAt: NOW - 3600 * SECOND,
      now: NOW,
      inFlight: false,
    })
    expect(live.kind).toBe('settled')
  })
})

describe('what the polite region announces', () => {
  const answering = (at: number): Liveness =>
    liveness({ answeredAt: at, now: NOW, inFlight: true })

  it('says the phase the run is in', () => {
    expect(announcement('Running', answering(NOW - SECOND))).toContain('Running')
  })

  it('says the same thing on every tick of one phase', () => {
    // The whole of *polite, and never one per tick*: a live region announces when its
    // text changes, so a sentence carrying a stamp or a count of seconds would read
    // the run out every two seconds for as long as it lasts.
    const first = announcement('Running', answering(NOW - SECOND))
    const later = announcement('Running', answering(NOW - 3 * SECOND))
    expect(later).toBe(first)
  })

  it('says the bench has stopped answering, in place of the phase', () => {
    const stalled = liveness({
      answeredAt: NOW - STALLED_AFTER_SECONDS * SECOND,
      now: NOW,
      inFlight: true,
    })
    const said = announcement('Running', stalled)
    expect(said).not.toBe(announcement('Running', answering(NOW - SECOND)))
    expect(said).toMatch(/not answering|stopped answering/)
    // And not the stamp, which moves the moment an answer arrives: what the region
    // announces is the state, and the time the figures were last dated is read off
    // the screen rather than out loud.
    expect(said).not.toContain(stalled.stamp)
  })

  it('has nothing to say about a run whose standing has not been read yet', () => {
    expect(announcement(null, liveness({ answeredAt: null, now: NOW, inFlight: true })))
      .toBe('')
  })
})
