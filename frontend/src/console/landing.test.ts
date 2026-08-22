/**
 * What the front door must say about the instrument, and what it must never say.
 *
 * Four claims, and each is a way this screen could quietly go wrong rather than a
 * restatement of its shape. That the three facts a reader needs are there — the
 * outcome, the date it was decided, the library version it was earned at. That the
 * three outcomes stay three, because *not decided* is not a polite fail. That a
 * bench citing nothing says so in the same place with the same weight, and offers
 * no empty outcome to be read as a gate it failed. And that every sentence in which
 * something passes or fails has **the bench** as its subject, because what
 * circulates is a screenshot of one region and a caption does not travel with it.
 *
 * The last test is the one that matters most in a year's time: the citation carries
 * no per-family figure, the document does, and the temptation will be to read the
 * document. Every string in the view is scanned for a figure only the document
 * holds, so a parser added later fails here rather than in review.
 */

import { describe, expect, it } from 'vitest'

import type { GateCitation } from '../api/bench'
import {
  A_FACT_ABOUT_THE_BENCH,
  gateReading,
  type GateReading,
} from './landing'

/**
 * The gate run this repository's own bench last passed, as the route serves it.
 *
 * The real citation of 2026-08-19 rather than an invented one, so that the figures
 * in this file are figures the bench actually earned — and so that the fields are
 * the ones `payload.citation` writes.
 */
const CITED: GateCitation = {
  cited: true,
  outcome: 'passed',
  decided_on: '2026-08-19',
  library: { cases: 18, digest: '90a8ebcc3d0c' },
  document: 'docs/gate-runs/gate-2026-08-19T09-38-37Z.md',
  record: 'docs/gate-runs/gate-2026-08-19T09-38-37Z.json',
  stated:
    'the bench passed its own gate on 2026-08-19, against its three agents of ' +
    'known construction, at library version: 18 cases, sha256:90a8ebcc3d0c',
}

const UNCITED: GateCitation = {
  cited: false,
  stated: 'no gate run is cited — this report was produced by a bench whose own ...',
}

/** Every string anywhere in the view, which is everything a reader can be shown. */
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

/** The facts a cited reading carries, as labels against values. */
function facts(reading: GateReading): Record<string, string> {
  if (!reading.cited) {
    return {}
  }
  return Object.fromEntries(reading.facts.map((fact) => [fact.label, fact.value]))
}

describe('the gate run the bench last passed', () => {
  it('states the outcome, the date it was decided and the version it was earned at', () => {
    const reading = gateReading(CITED)

    expect(reading.cited).toBe(true)
    expect(facts(reading)).toEqual({
      outcome: 'passed',
      'decided on': '2026-08-19',
      // The count and the digest, both: eighteen cases does not say *which*
      // eighteen, and the digest is what answers "has the bench changed since?".
      // The count, and no digest: it came off the row (`libraryVersion`).
      'library version': '18 cases',
    })
    expect(reading.heading).toBe('This bench passed its own gate run')
  })

  it('keeps the three outcomes three, and says the bench passed only when it did', () => {
    const headings = ['passed', 'failed', 'not_decided'].map(
      (outcome) => gateReading({ ...CITED, outcome }).heading,
    )

    expect(new Set(headings).size).toBe(3)
    // A fail is a measured claim that the bench does not discriminate; not decided
    // says too little of it was fit for the question to be put. Neither is the
    // other, and neither is a pass.
    expect(headings.filter((said) => /passed/.test(said))).toEqual([
      'This bench passed its own gate run',
    ])
    for (const heading of headings) {
      expect(heading).toMatch(/bench/i)
    }
  })

  it('names both files the citation points at, and reads neither', () => {
    const reading = gateReading(CITED)
    if (!reading.cited) {
      throw new Error('a cited citation read as uncited')
    }

    expect(reading.document.path).toBe(CITED.document)
    // The record is the answer to the question the document could only have been
    // given by parsing it: the same gate run as fields, named beside the prose
    // (ADR-0023). It is an address on this screen and nothing more — no figure
    // arrives from it, which is what the scan below is for.
    expect(reading.record.path).toBe(CITED.record)
    expect(reading.record.path).toMatch(/\.json$/)
    expect(reading.record.statement).toMatch(/discrimination score/)
    // The per-family rates, the per-family `D`, κ and the three reference agents
    // are in that record and are not in the citation. A view that had them would
    // have parsed the bench's own prose output (spec §75: per-family gate figures
    // are out, and the citation names the record rather than carrying it).
    const shown = everyString(reading).join(' ')
    for (const figure of [
      'D =',
      'κ',
      'hardened',
      'weak',
      'trivial',
      'data_leakage',
      'scope_creep',
    ]) {
      expect(shown).not.toContain(figure)
    }
  })
})

describe('a gate run that left no dated document', () => {
  it('says so where the path would be, and still names the record', () => {
    const reading = gateReading({ ...CITED, document: null })
    if (!reading.cited) {
      throw new Error('a cited citation read as uncited')
    }

    // The console's entry point writes the record and no prose (ADR-0021), so the
    // citation carries no file name for one. `path: null` rather than an empty string
    // or a sentence in a path's place: a screen that printed either would be printing
    // a paragraph inside a code element, and the front door claims it prints paths.
    expect(reading.document.path).toBeNull()
    expect(reading.document.statement).toMatch(/started from the console/)
    // And nothing about the outcome is missing: the figures are in the record, which
    // is named exactly as it is for a gate run that also wrote prose.
    expect(reading.record.path).toBe(CITED.record)
    expect(reading.facts).toHaveLength(3)
  })
})

describe('a bench that cites no gate run', () => {
  it('states the absence in the same place, and offers no empty outcome', () => {
    const reading = gateReading(UNCITED)
    if (reading.cited) {
      throw new Error('an uncited citation read as cited')
    }

    // Same place and same weight: both shapes answer with a heading and the same
    // statement about whose fact this is, so an absence is as visible as a pass.
    expect(reading.heading).not.toBe('')
    expect(reading.aboutTheBench).toBe(A_FACT_ABOUT_THE_BENCH)
    expect(reading.statement.length).toBeGreaterThan(80)
    expect(reading.statement).toMatch(/no gate run/i)
    expect(reading.statement).toMatch(/not a gate it failed/i)

    // And nowhere for a screen to draw a blank: no outcome, no date, no library
    // version, no document. A record with empty ones reads as a gate that failed.
    const held = reading as unknown as Record<string, unknown>
    for (const absent of [
      'facts',
      'document',
      'record',
      'outcome',
      'decidedOn',
      'library',
    ]) {
      expect(held[absent]).toBeUndefined()
    }
  })
})

describe('the subject of every sentence here is the bench', () => {
  it('never lets a target be the thing that passed or failed', () => {
    for (const gate of [CITED, { ...CITED, outcome: 'failed' }, UNCITED]) {
      const reading = gateReading(gate)

      // Any sentence in which something passes or fails names the bench. A caption
      // above the region does not travel with a screenshot of it, so the claim
      // about the subject is inside every sentence that makes one (ADR-0018).
      for (const said of everyString(reading)) {
        // Prose rather than every string: `Outcome: passed` is a labelled value
        // under a heading that already names its subject, and a one-word value
        // cannot carry a subject. Anything with a space in it is a sentence.
        if (/\s/.test(said) && /passed|failed|pass or fail/i.test(said)) {
          expect(said).toMatch(/bench/i)
        }
      }
      expect(reading.aboutTheBench).toMatch(/never a verdict about a target/)
      expect(reading.aboutTheBench).toMatch(/rates, intervals and bands/)

      // And no figure about anybody's agent: this screen has no rate, no band and
      // no verdict, and there is nowhere in the type to put one.
      for (const key of Object.keys(reading)) {
        expect(key).not.toMatch(/rate|band|verdict|score|total/i)
      }
    }
  })
})
