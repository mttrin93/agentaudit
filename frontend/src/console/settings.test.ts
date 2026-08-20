/**
 * What the settings screen must state, in what order, and what it may never offer.
 *
 * Seven claims, each of them a way a screen about a configuration goes quietly wrong.
 *
 * **That the two key identifiers stay two.** The strongest test here builds the bench
 * that matters: one signing with a key of its own against a pin it does not match, so
 * every report it produces reads `signed_by_another_key`. Both fingerprints have to be
 * on the screen and they have to be different, because a screen printing one of them
 * and calling it *the key* shows that bench as correctly configured (ADR-0017).
 *
 * **That a bench which signs nothing says so where a fingerprint would be.** Asserted
 * as the absence of the field rather than as an empty one: an empty identifier drawn in
 * the place a fingerprint goes reads as a key that failed to load.
 *
 * **That the four model settings are four.** Asserted as a length, as four distinct
 * instruments, and — the collapse this block exists to catch — as no row whose prose
 * carries another row's model. A screen showing three of the four would read as
 * complete.
 *
 * **That the two layer ceilings are never one figure.** Three ways: exactly two
 * ceilings with two different layers; no numeric leaf anywhere in the view equal to any
 * sum of one scored figure and one adaptive figure; and no field name anywhere that
 * could hold a total. The fixture's declared numbers are chosen so that every one of
 * those cross-layer sums is a number the view does not otherwise contain, which is what
 * makes the scan fail on a total rather than pass by coincidence.
 *
 * **That a retired case is counted and kept.** The count is the payload's and the
 * wording says *kept*; nothing on the screen is the live count plus the retired one,
 * because that is a case count nothing runs.
 *
 * **That every figure in a sentence is read off the wire.** The attempts per case and
 * the turn ceiling are moved on the fixture and the sentences are expected to move with
 * them — a threshold written into the console is a threshold that can disagree with
 * `rule.py` in the flattering direction.
 *
 * **That nothing here changes a setting.** Asserted three ways: no leaf of the view is
 * anything but text, a boolean or a declared number, so there is nowhere for a handler
 * to live; no field is named for an action; and `SettingsScreen.tsx` itself is read and
 * contains no button, no form, no handler and no write.
 */

import { describe, expect, it } from 'vitest'

import type { BenchSettings } from '../api/bench'
import component from './SettingsScreen.tsx?raw'
import {
  KEYGEN_COMMAND,
  settingsScreen,
  type Ceiling,
  type SettingsBlock,
} from './settings'

/**
 * A bench configured with every branch this screen has, and figures chosen to catch a
 * total.
 *
 * The scored layer's seven attempts and one probe against the adaptive layer's five,
 * three, eleven and 165: every sum of one figure from each layer — 12, 10, 18, 172, 6,
 * 4 and 166 — is a number this view does not otherwise contain, and the digest is
 * letters only so that no scan matches a hexadecimal accident.
 */
const CONFIGURED: BenchSettings = {
  statement: 'what this bench is set to, as it is loaded. A read.',
  signing: {
    will_be_signed_by: {
      holds_a_key: true,
      fingerprint: 'sha256:aaaabbbbccccddddeeeeffffaaaabbbbccccddddeeeeffffaaaabbbb',
      stated: 'the key every artefact this bench produces will be signed by.',
    },
    verified_against: {
      fingerprint: 'sha256:ffffeeeeddddccccbbbbaaaaffffeeeeddddccccbbbbaaaaffffeeee',
      declared: false,
      stated: 'the committed public half a recipient would pin.',
    },
    statement:
      'two identifiers and two facts: signing with a key nobody published reads as ' +
      'signed_by_another_key on every report.',
  },
  library: {
    live: { cases: 23, digest: 'aabbccddeeff' },
    stated: 'library version: twenty-three cases, over every field of every record.',
    retired: 2,
    kept: 'retired cases are counted and kept, and never deleted.',
    statement: 'the version is over the cases a run scores.',
  },
  models: [
    {
      instrument: 'the reference agents',
      identifier: 'provider:model-alpha',
      declared: true,
      decides: 'what is being measured, and never the instrument measuring it.',
    },
    {
      instrument: 'the adjudicator',
      identifier: 'provider:model-beta',
      declared: true,
      decides: 'the two judged families, and the one κ is measured on.',
    },
    {
      instrument: 'the adaptive attacker',
      identifier: 'provider:model-gamma',
      declared: true,
      decides: 'nothing that is scored.',
    },
    {
      instrument: 'the second reference model',
      identifier: 'not held by this bench',
      declared: false,
      decides: 'what a swap is measured against, declared on the command line.',
    },
  ],
  ceilings: {
    scored: {
      layer: 'scored',
      attempts_per_case: 7,
      registration_probes_per_target: 1,
      declared_in: 'backend/bench/rule.py',
      statement: 'exact rather than a bound, because a suite of known size is known.',
    },
    adaptive: {
      layer: 'adaptive',
      turns_per_episode: 5,
      episodes_per_family: 3,
      families: 11,
      turns_per_target: 165,
      declared_in: 'backend/bench/adaptive/budget.py',
      statement: 'a worst case, and stated as one.',
    },
    statement:
      'each layer’s ceiling is enforced against that layer’s own counter, so a layer ' +
      'with room left cannot spend the other’s unspent allowance.',
  },
}

/** The same bench, declaring that it does not sign and naming no model. */
const UNSIGNING: BenchSettings = {
  ...CONFIGURED,
  signing: {
    ...CONFIGURED.signing,
    will_be_signed_by: {
      holds_a_key: false,
      stated:
        'this bench holds no signing key, so it will produce no signed artefact: ' +
        'every report is refused by name as never_signed.',
    },
  },
  models: CONFIGURED.models.map((model) => ({
    ...model,
    identifier: 'not declared',
    declared: false,
  })),
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

/** Every leaf that is not a string, which is where a handler would have to hide. */
function everyOtherLeaf(node: unknown): unknown[] {
  if (typeof node === 'string') {
    return []
  }
  if (Array.isArray(node)) {
    return node.flatMap(everyOtherLeaf)
  }
  if (node && typeof node === 'object') {
    return Object.values(node).flatMap(everyOtherLeaf)
  }
  return [node]
}

/** Every number anywhere in the view, which is every figure it can be read for. */
function everyNumber(node: unknown): number[] {
  return everyOtherLeaf(node).filter(
    (leaf): leaf is number => typeof leaf === 'number',
  )
}

/** Every field name anywhere in the view, which is where an action would be named. */
function fieldsOf(node: unknown): string[] {
  if (Array.isArray(node)) {
    return node.flatMap(fieldsOf)
  }
  if (node && typeof node === 'object') {
    return Object.entries(node).flatMap(([field, value]) => [
      field,
      ...fieldsOf(value),
    ])
  }
  return []
}

/** The one block of each kind, so a test can name what it is asserting about. */
function block<K extends SettingsBlock['kind']>(
  blocks: SettingsBlock[],
  kind: K,
): Extract<SettingsBlock, { kind: K }> {
  const found = blocks.find((one) => one.kind === kind)
  if (!found) {
    throw new Error(`the settings screen has no ${kind} block`)
  }
  return found as Extract<SettingsBlock, { kind: K }>
}

/** One layer's ceiling out of the pair, by name. */
function ceiling(blocks: SettingsBlock[], layer: Ceiling['layer']): Ceiling {
  const found = block(blocks, 'ceilings').ceilings.find(
    (one) => one.layer === layer,
  )
  if (!found) {
    throw new Error(`the settings screen has no ${layer} ceiling`)
  }
  return found
}

describe('the order the blocks are read in', () => {
  it('puts the keys first and the two ceilings last, on every bench', () => {
    // The keys first, because *which key will sign the thing I am about to send a
    // customer* is the question this screen is opened with. The ceilings last,
    // because they are the one block whose point is made by there being two of it.
    for (const bench of [CONFIGURED, UNSIGNING]) {
      expect(settingsScreen(bench).map((one) => one.kind)).toEqual([
        'keys',
        'library',
        'agents',
        'models',
        'ceilings',
      ])
    }
  })
})

describe('the two key identifiers', () => {
  it('shows both, as two different facts, on a bench whose keys disagree', () => {
    const keys = block(settingsScreen(CONFIGURED), 'keys')

    expect(keys.identities).toHaveLength(2)
    const [signs, verifies] = keys.identities
    if (!signs.held || !verifies.held) {
      throw new Error('a bench holding both keys read as holding neither')
    }

    // Both fingerprints, and they are the payload's own rather than derived from one
    // another. This bench signs with a key nobody published: every report it produces
    // reads signed_by_another_key, and that is exactly what two identifiers make
    // visible and one hides.
    const held = CONFIGURED.signing.will_be_signed_by
    if (!held.holds_a_key) {
      throw new Error('the fixture stopped holding a signing key')
    }
    expect(signs.fingerprint).toBe(held.fingerprint)
    expect(verifies.fingerprint).toBe(CONFIGURED.signing.verified_against.fingerprint)
    expect(signs.fingerprint).not.toBe(verifies.fingerprint)

    // Two labels, and they say which is which: one is what will sign, the other is
    // what a verification is run against. A single label over both would be the
    // conflation with the fingerprints still separate.
    expect(signs.label).not.toBe(verifies.label)
    expect(signs.label.toLowerCase()).toContain('signed by')
    expect(verifies.label.toLowerCase()).toContain('verification')
    expect(keys.statement.toLowerCase()).toContain('two')

    // And nothing here is a key rather than a name for one. A fingerprint is the one
    // representation of a key a reader is ever shown.
    for (const said of everyString(keys)) {
      expect(said).not.toContain('BEGIN PUBLIC KEY')
      expect(said).not.toContain('BEGIN PRIVATE KEY')
    }
  })

  it('states the absence where a fingerprint would be, on a bench that signs nothing', () => {
    const keys = block(settingsScreen(UNSIGNING), 'keys')
    const [signs, verifies] = keys.identities

    expect(signs.held).toBe(false)
    // No field to be blank: an empty identifier in the place a fingerprint goes is
    // read as a key whose name failed to load, which is a different fact.
    expect((signs as unknown as Record<string, unknown>).fingerprint).toBeUndefined()
    expect(signs.stated).toMatch(/never_signed/)

    // The other identifier is still answered. A bench that signs nothing still
    // verifies against something, and *which key* has an answer either way.
    expect(verifies.held).toBe(true)
  })

  it('prints the command that makes a pair, and says nothing here makes one', () => {
    const keys = block(settingsScreen(CONFIGURED), 'keys')

    // One line, nothing but the command: what happens to it is a selection and a
    // paste, and a `$` pasted with it is a command that fails.
    expect(keys.command).toBe(KEYGEN_COMMAND)
    expect(keys.command.split('\n')).toHaveLength(1)
    expect(keys.command).toMatch(/^uv run python -m scripts\.keygen /)
    expect(keys.command).not.toMatch(/^\s|[$>]|\s$/)

    // And why: a key generated on demand boots cleanly and signs every report with a
    // key nobody has published, which is a valid signature over unknown provenance.
    expect(keys.commandStatement).toMatch(/Nothing on this screen generates one/)
    expect(keys.commandStatement).toMatch(/no route on this bench would take one/)
  })
})

describe('the case library it is loaded with', () => {
  it('counts the retired cases and says they are kept', () => {
    const library = block(settingsScreen(CONFIGURED), 'library')
    const said = everyString(library).join(' ')

    // The live count and the digest both, because a library described only by a count
    // cannot say whether the cases are the same cases.
    expect(said).toContain('23')
    expect(said).toContain(CONFIGURED.library.live.digest)

    // Nothing here is the two added. Twenty-five is a case count nothing runs: the
    // live half is what a run attempts and the retired half is what it no longer does.
    expect(said).not.toMatch(/\b25\b/)

    // And the retired count, stated as kept. Marked, never deleted: a case the field
    // caught up with is evidence that the field moved.
    const retired = library.facts.find((fact) => /retired/i.test(fact.label))
    expect(retired?.label ?? 'no retired fact').toMatch(/retired and kept/i)
    expect(retired?.value ?? 'no retired fact').toContain('2')
    expect(library.kept).toMatch(/never deleted/)
  })
})

describe('the three agents the discrimination score is measured against', () => {
  it('names them in the order construction gives them, with no figure between them', () => {
    const agents = block(settingsScreen(CONFIGURED), 'agents')

    expect(agents.agents.map((agent) => agent.name)).toEqual([
      'hardened',
      'weak',
      'trivial',
    ])
    // One hue in three ordered steps: the accent is one class per agent and never
    // shared, so colour carries identity and order and never a judgement.
    expect(new Set(agents.agents.map((agent) => agent.accent)).size).toBe(3)

    // And not one figure. What each agent scored on each family is in the gate run's
    // document, and a rate beside a name here would be the per-family gate figure the
    // spec dropped rather than parse.
    for (const said of everyString(agents.agents)) {
      expect(said).not.toMatch(/\d/)
    }
  })
})

describe('the four model settings', () => {
  it('are four rows, four instruments, and never one', () => {
    const models = block(settingsScreen(CONFIGURED), 'models').models

    expect(models).toHaveLength(4)
    expect(models.map((model) => model.instrument)).toEqual(
      CONFIGURED.models.map((model) => model.instrument),
    )
    expect(new Set(models.map((model) => model.instrument)).size).toBe(4)
    expect(new Set(models.map((model) => model.identifier)).size).toBe(4)

    // No row carries another row's model. This is the collapse the block exists to
    // catch: an adjudicator scoring transcripts its own model produced reports its
    // agreement with itself, and a screen that showed one identifier under two
    // instruments would say nothing was wrong.
    for (const model of models) {
      for (const other of models) {
        if (other.instrument === model.instrument) {
          continue
        }
        expect(model.decides).not.toContain(other.identifier)
        expect(model.identifier).not.toBe(other.identifier)
      }
    }

    // The setting this bench does not hold is on the list and marked, rather than
    // left off it: a screen showing three of the four would read as complete.
    const absent = models.filter((model) => !model.declared)
    expect(absent).toHaveLength(1)
    expect(absent[0].instrument).toBe('the second reference model')

    // And a bench that named none of them says so on every row.
    const undeclared = block(settingsScreen(UNSIGNING), 'models').models
    expect(undeclared).toHaveLength(4)
    expect(undeclared.every((model) => !model.declared)).toBe(true)
  })
})

describe('each layer’s ceiling', () => {
  it('is two ceilings in two units, with nothing anywhere that adds them', () => {
    const blocks = settingsScreen(CONFIGURED)
    const ceilings = block(blocks, 'ceilings').ceilings

    expect(ceilings.map((one) => one.layer)).toEqual(['scored', 'adaptive'])

    // Each block's numbers are its own layer's, read off the wire.
    expect(ceiling(blocks, 'scored').figures.map((figure) => figure.value)).toEqual([
      7, 1,
    ])
    expect(ceiling(blocks, 'adaptive').figures.map((figure) => figure.value)).toEqual([
      165, 5, 3, 11,
    ])

    // No figure anywhere in the whole view is a sum across the two layers, and no
    // sentence carries one either. The fixture's numbers are chosen so that every one
    // of these sums is absent, which is what makes this fail on a total rather than
    // pass by coincidence.
    const numbers = new Set(everyNumber(blocks))
    const said = everyString(blocks).join(' ')
    for (const here of ceiling(blocks, 'scored').figures) {
      for (const there of ceiling(blocks, 'adaptive').figures) {
        const crossed = here.value + there.value
        expect(numbers.has(crossed)).toBe(false)
        expect(said).not.toMatch(new RegExp(`\\b${crossed}\\b`))
      }
    }

    // And no field named for a total: a combined budget needs somewhere to live, and
    // this is the assertion that fails when somebody gives it a home.
    for (const field of fieldsOf(blocks)) {
      expect(field.toLowerCase()).not.toMatch(
        /total|combined|sum|overall|both|budget/,
      )
    }
  })

  it('says in each layer’s own words that it cannot borrow the other’s allowance', () => {
    const blocks = settingsScreen(CONFIGURED)
    const said = everyString(block(blocks, 'ceilings')).join(' ')

    expect(ceiling(blocks, 'scored').limit).toContain('7 attempts per case')
    expect(ceiling(blocks, 'adaptive').limit).toContain('165 turns per target')
    expect(said).toContain(CONFIGURED.ceilings.statement)
    expect(said).toContain('backend/bench/rule.py')
    expect(said).toContain('backend/bench/adaptive/budget.py')
  })

  it('reads every figure in a sentence off the wire', () => {
    // A threshold written into the console is a threshold that can disagree with
    // `rule.py` in the flattering direction, so both sentences are moved here.
    const moved = settingsScreen({
      ...CONFIGURED,
      ceilings: {
        ...CONFIGURED.ceilings,
        scored: { ...CONFIGURED.ceilings.scored, attempts_per_case: 4 },
        adaptive: { ...CONFIGURED.ceilings.adaptive, turns_per_target: 208 },
      },
    })

    expect(ceiling(moved, 'scored').limit).toContain('4 attempts per case')
    expect(ceiling(moved, 'scored').limit).not.toContain('7 attempts')
    expect(ceiling(moved, 'adaptive').limit).toContain('208 turns per target')
    expect(ceiling(moved, 'adaptive').limit).not.toContain('165 turns')
  })
})

describe('nothing on this screen changes a setting', () => {
  it('offers no handler, no action-shaped field, and no control in the component', () => {
    for (const bench of [CONFIGURED, UNSIGNING]) {
      const blocks = settingsScreen(bench)

      // Every leaf is a string, a boolean or a declared number. There is nowhere in
      // this value for a callback to live, which is what "no control" means at the
      // seam this screen is tested at: a control needs a handler and a handler needs
      // a field.
      for (const leaf of everyOtherLeaf(blocks)) {
        expect(['boolean', 'number']).toContain(typeof leaf)
      }
      // And no field named for something that happens to a setting. Rotation stays in
      // the environment and configuration stays on the command line.
      for (const field of fieldsOf(blocks)) {
        expect(field).not.toMatch(
          /start|launch|submit|click|post|rotate|update|save|write|edit|delete/i,
        )
      }
    }

    // The component itself, read rather than rendered. These screens are driven by
    // hand, so the absence of the affordance is asserted over the source: no button,
    // no form, no handler, no write of any kind, and nothing imported that could post.
    expect(component).toContain('export function SettingsScreen')
    for (const affordance of [
      '<button',
      '<form',
      '<input',
      '<select',
      'onClick',
      'onSubmit',
      'onChange',
      'method:',
      'fetch(',
      'startRun',
      'answerTheInterrupt',
    ]) {
      expect(component).not.toContain(affordance)
    }
  })
})
