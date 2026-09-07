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
import type { FamilyCovered } from '../api/settings'
import {
  A_FACT_ABOUT_THE_BENCH,
  gateReading,
  type GateReading,
  familyRows,
  selectionReading,
  THE_ELECTIVE_FAMILIES,
  THE_FAMILIES,
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

describe('the six families, said once', () => {
  it('is one short sentence a family, in the enum’s own order', () => {
    expect(THE_FAMILIES.map((one) => one.family)).toEqual([
      'indirect_prompt_injection',
      'scope_creep',
      'wrongful_commitment',
      'data_leakage',
      'halt_defeat',
      'disclosure_denial',
    ])
    // Short, and one sentence: the region is six lines a reader takes in at once, and
    // a paragraph a family is the region this page keeps removing.
    for (const one of THE_FAMILIES) {
      expect(one.says.length).toBeLessThan(110)
      expect(one.says.split('. ')).toHaveLength(1)
      expect(one.says.endsWith('.')).toBe(true)
    }
  })

  it('carries no figure, because a family is not a measurement of one', () => {
    const said = THE_FAMILIES.map((one) => one.says).join(' ')

    // No rate, no count, no floor, and no word that would be read as one: what a
    // family *is* has nothing to do with how a target answered it.
    expect(said).not.toMatch(/[0-9]/)
    expect(said.toLowerCase()).not.toMatch(/rate|attempts|denominator|interval|κ/)
  })
})

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

describe('what the next run sends', () => {
  /**
   * The wire's own answer, in the order and the grouping the bench gave it.
   *
   * Seven constructions and three layers, with `layer` on every construction row,
   * because which switch turns a construction off is the bench's answer and not this
   * console's (`selection.layer_of`).
   */
  const OFFERED = {
    layers: [
      { layer: 'single_turn', selected: true, sends: 'one message in one session' },
      {
        layer: 'fixed_multi_turn',
        selected: true,
        sends: 'a fixed script of turns in one session',
      },
      { layer: 'adaptive', selected: false, sends: 'the model-driven attacker' },
    ],
    transforms: [
      { transform: 'plain', layer: 'single_turn', selected: true, does: 'as committed' },
      { transform: 'base64', layer: 'single_turn', selected: false, does: 'encoded' },
      {
        transform: 'scripted_crescendo',
        layer: 'fixed_multi_turn',
        selected: true,
        does: 'escalated over a fixed script',
      },
    ],
    selection_off_statement:
      'a construction switched off is not sent, and is not measured rather than ' +
      'measured at zero.',
    selection_stated: 'This run sent these constructions and no others: plain.',
  }

  it('groups every construction under the layer the bench says schedules it', () => {
    const reading = selectionReading(OFFERED)

    expect(reading.layers.map((one) => one.layer)).toEqual([
      'single_turn',
      'fixed_multi_turn',
      'adaptive',
    ])
    expect(
      reading.layers.map((one) => one.constructions.map((sent) => sent.transform)),
    ).toEqual([['plain', 'base64'], ['scripted_crescendo'], []])
    // The adaptive layer holds none, and that is the point rather than an omission:
    // what it would hold are the two loops the bench's closed set of constructions
    // deliberately does not name, so the operator's question about it is whether the
    // agent runs at all.
    expect(reading.layers.at(-1)?.constructions).toEqual([])
  })

  it('draws each switch from the bench’s answer and never from a local default', () => {
    const reading = selectionReading(OFFERED)
    const runs = Object.fromEntries(reading.layers.map((one) => [one.layer, one.runs]))

    expect(runs).toEqual({
      single_turn: true,
      fixed_multi_turn: true,
      adaptive: false,
    })
    const [single] = reading.layers
    expect(single.constructions.map((one) => one.sent)).toEqual([true, false])
  })

  it('says a construction switched off is not measured, and carries no figure', () => {
    const reading = selectionReading(OFFERED)

    // The distinction the whole selection exists to keep: a construction that was not
    // sent has no line in any family's mix, so *not measured* is what the screen has
    // to say and *zero* is what it must never let a reader infer.
    expect(reading.caveat).toMatch(/not measured/)
    expect(reading.caveat).not.toMatch(/[0-9]/)
    // And what a run made now would print in its provenance, read off the wire: the
    // artefact's own wording, so an operator narrowing a run sees what a recipient
    // will read.
    expect(reading.stated).toBe(OFFERED.selection_stated)
    // No rate, no count and no denominator in the switches themselves. A selection is
    // what a run was asked to send and never a measurement of anything, and the only
    // two sentences here that may name a figure at all are the bench's own two — the
    // caveat, whose whole job is to say *not* a rate of zero, and the wording the
    // artefact will carry.
    // A digit is not banned here the way it is on the six families' sentences: one
    // construction is *named* `base64`, and a screen renaming it would be a screen
    // whose switch and the record's `transform` field are two different words.
    expect(everyString(reading.layers).join(' ')).not.toMatch(
      /rate|denominator|interval|κ|zero|attempts/,
    )
  })
})


/** One switch as the route serves it, with the label its row prints. */
const covered = (
  family: string,
  agentic: string[],
  llm: string[],
  articles: string[],
): FamilyCovered => ({
  family,
  covered: true,
  labels: { agentic, llm, articles },
})

describe('the nine families the bench page draws as one list', () => {
  it('is the six then the tier, in the two enums’ order and undifferentiated', () => {
    const rows = familyRows(
      THE_FAMILIES.map((one) => covered(one.family, [], ['LLM01:2026'], ['15'])),
      THE_ELECTIVE_FAMILIES.map((one) =>
        covered(one.family, [], ['LLM01:2026'], ['15']),
      ),
    )

    // Nine rows and one list. The tier is not a section of its own on this screen and
    // carries no mark distinguishing it from the six (ADR-0091); what stays two is the
    // pair of arrays, because the switch has to know which one it writes to.
    expect(rows.map((one) => one.family)).toEqual([
      ...THE_FAMILIES.map((one) => one.family),
      ...THE_ELECTIVE_FAMILIES.map((one) => one.family),
    ])
    expect(rows).toHaveLength(9)
    expect(rows.filter((one) => one.tier === 'elective')).toHaveLength(3)

    // Every row is the same shape, so nothing a reader sees says which tier a row is
    // in. `tier` is read by the tick and printed by nothing.
    for (const one of rows) {
      expect(Object.keys(one).sort()).toEqual([
        'articles',
        'family',
        'owasp',
        'says',
        'tier',
      ])
    }
  })

  it('folds the two OWASP lists into the one column the screen has', () => {
    const found = (rows: FamilyCovered[], family: string) =>
      familyRows(rows, []).find((one) => one.family === family)!
    const leakage = found(
      [covered('data_leakage', [], ['LLM02:2026', 'LLM08:2026'], ['15'])],
      'data_leakage',
    )

    // The agentic entries first and the LLM entries after them, each carrying its
    // edition: `LLM06` alone means Excessive Agency under one numbering and Unbounded
    // Consumption under the copy stored today, and a column that dropped the tag would
    // print a claim nobody could resolve (ADR-0036).
    expect(leakage.owasp).toEqual(['LLM02:2026', 'LLM08:2026'])

    const hijack = found(
      [covered('indirect_prompt_injection', ['ASI01:2026'], ['LLM01:2026'], ['15'])],
      'indirect_prompt_injection',
    )
    expect(hijack.owasp).toEqual(['ASI01:2026', 'LLM01:2026'])
  })

  it('draws a family the bench did not name with empty columns, never a guess', () => {
    // The settings read failed, so both arrays are null. The nine still draw — their
    // sentences are this console's own — and the two label columns are empty, which is
    // the only honest thing a screen can print about a claim it has not been told.
    const unread = familyRows(null, null)
    expect(unread).toHaveLength(9)
    expect(unread.every((one) => one.owasp.length === 0)).toBe(true)
    expect(unread.every((one) => one.articles.length === 0)).toBe(true)
    expect(unread.every((one) => one.says.length > 0)).toBe(true)
  })

  it('carries no figure on any row, because a family is not a measurement of one', () => {
    const rows = familyRows(
      THE_FAMILIES.map((one) => covered(one.family, ['ASI01:2026'], [], ['15'])),
      THE_ELECTIVE_FAMILIES.map((one) => covered(one.family, [], [], ['10'])),
    )
    // The same rule the six sentences are held to, over the whole row now that a row
    // carries served data: no rate, no interval, no band, no `D`. An article number
    // and an entry's edition year are the only digits a row is allowed.
    for (const one of rows) {
      expect(one.says).not.toMatch(/\d/)
      expect(Object.keys(one)).not.toContain('rate')
    }
  })
})
