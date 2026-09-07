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
 * **That the tuning form is the only thing here that changes a setting.** Asserted
 * three ways: no leaf of any *stating* block is anything but text, a boolean or a
 * declared number, so there is nowhere outside the one `tuning` block for a handler to
 * live; no field anywhere is named for something that happens to a key or to the
 * library; and `SettingsScreen.tsx` itself is read and reaches `tuneBench` and nothing
 * else on the bench — no run started, no interrupt answered, no nonce issued, no gate
 * run, no `fetch` of its own. The claim used to be that the file contained no write at
 * all, which ADR-0025 ended and this docstring outlived (#57).
 */

import { describe, expect, it } from 'vitest'

import type { BenchSettings } from '../api/bench'
import component from './SettingsScreen.tsx?raw'
import view from './settings.ts?raw'
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
    agent_types: ['assistant', 'document'],
    kept: 'retired cases are counted and kept, and never deleted.',
    statement: 'the version is over the cases a run scores.',
  },
  models: [
    {
      instrument: 'the reference agents',
      identifier: 'provider:model-alpha',
      declared: true,
      decides: 'what is being measured, and never the instrument measuring it.',
      effort: 'no reasoning effort held for this instrument.',
    },
    {
      instrument: 'the adjudicator',
      identifier: 'provider:model-beta',
      declared: true,
      decides: 'the two judged families, and the one κ is measured on.',
      effort: 'no reasoning effort held for this instrument.',
    },
    {
      instrument: 'the adaptive attacker',
      identifier: 'provider:model-gamma',
      declared: true,
      decides: 'nothing that is scored.',
      effort: 'reasoning effort medium — declared, and the value the request carried',
    },
    {
      instrument: 'the second reference model',
      identifier: 'not held by this bench',
      declared: false,
      decides: 'what a swap is measured against, declared on the command line.',
      effort: 'no reasoning effort held for this instrument.',
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
  tuning: {
    attacker_models: [
      {
        identifier: 'openrouter:openai/gpt-4.1-mini',
        decides: 'cheap, and the baseline earlier readings were taken with.',
        chosen: true,
      },
      {
        identifier: 'openrouter:anthropic/claude-haiku-4.5',
        decides: 'cheap, and better at following a multi-step brief.',
        chosen: false,
      },
      {
        identifier: 'not declared',
        decides: 'the deterministic stand-in: eight fixed probes, no spend.',
        chosen: false,
      },
    ],
    temperature: null,
    temperature_bounds: { low: 0, high: 1 },
    temperature_absent: 'no temperature declared — the provider’s own default.',
    temperature_stated:
      'no temperature declared — the provider’s own default, whatever that is. An ' +
      'absence somebody left, and not a number this bench chose on their behalf',
    reasoning_efforts: [
      { level: 'low', chosen: false },
      { level: 'medium', chosen: true },
      { level: 'high', chosen: false },
    ],
    reasoning_effort: 'medium',
    reasoning_effort_absent:
      'no reasoning effort declared — the provider’s own default, and there is no ' +
      'default this bench would make on an operator’s behalf.',
    reasoning_effort_stated:
      'reasoning effort medium — declared, and the value the request carried',
    turns_per_episode: 5,
    turns_bounds: { low: 1, high: 40 },
    episodes_per_family: 3,
    episodes_bounds: { low: 1, high: 10 },
    attempts_per_case: 7,
    attempts_bounds: { low: 1, high: 50 },
    attempts_per_family: 21,
    declared_attempts_per_case: 10,
    attempts_warning:
      'attempts per case is the scored denominator: the gate is decided at the ' +
      'declared rule, where n = 30 per family, and a run at another number is not a ' +
      'gate result.',
    families: [
      { family: 'indirect_prompt_injection', covered: true },
      { family: 'scope_creep', covered: false },
    ],
    families_off_statement:
      'a family switched off is not run: its cases are not attempted, no episode ' +
      'opens against it, and the report states it as not run rather than as a rate ' +
      'of zero.',
    // The tier, in an array of its own for the reason the bench holds two closed
    // sets: the six are the denominator the gate is decided over, and a fixture that
    // put all nine in one array would be modelling a response this bench does not
    // serve (ADR-0015, ADR-0035).
    elective_families: [
      { family: 'memory_poisoning', covered: false },
      { family: 'pii_leakage', covered: true },
    ],
    elective_statement:
      'an elective family is one the bench holds beside the six and a run has to ask ' +
      'for. It reports its rate, its interval and its band like any other family, and ' +
      'it decides nothing: how well this bench discriminates on it is stated in the ' +
      'bench’s own gate document and never on a target’s report.',
    // The selection, on the reading this screen does not draw: the switches are on the
    // front door beside the family switches, and the fields are here because this is
    // one settings response. A block this screen offers no control for still has to be
    // in the fixture, or the scan below is a scan over a narrower response than the
    // route serves.
    layers: [
      { layer: 'single_turn', selected: true, sends: 'one message in one session' },
      { layer: 'adaptive', selected: true, sends: 'the model-driven attacker' },
    ],
    transforms: [
      {
        transform: 'plain',
        layer: 'single_turn',
        selected: true,
        does: 'sent as the record commits it',
      },
    ],
    selection_off_statement:
      'a construction switched off is not sent, and a family whose every ' +
      'construction is off is stated as not run rather than measured at zero.',
    selection_stated:
      'This run sent every construction the library holds, in every layer.',
    statement:
      'these are the declared inputs of a run, printed in the report of every run ' +
      'made under them, and a change is refused while a run is going.',
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
        // Last, and the only block that changes anything: the declared inputs of
        // the next run (ADR-0025). Last because everything above it is what this
        // bench *is*, and a form above them would read as the screen's subject.
        'tuning',
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
    // Read over the blocks that *state* figures and not over the form's own state:
    // `tuning` restates both layers' settings side by side, because that is what
    // setting them requires, and its numbers are the settings themselves rather
    // than figures read off a run. The field-name check below still covers it, so a
    // *named* blend anywhere still fails.
    const stating = blocks.filter((one) => one.kind !== 'tuning')
    const numbers = new Set(everyNumber(stating))
    const said = everyString(stating).join(' ')
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

/**
 * The same bench on a reasoning attacker: no temperature setting to be had.
 *
 * `temperature_bounds` is `null` and `temperature_stated` is the sentence the record
 * would print — the response answering *this model accepts none*, which is not the
 * response's *no temperature declared* and not a fourth thing the console composed.
 */
const ON_A_REASONING_MODEL: BenchSettings = {
  ...CONFIGURED,
  tuning: {
    ...CONFIGURED.tuning,
    temperature: null,
    temperature_bounds: null,
    temperature_stated:
      'this model accepts no temperature \u2014 it samples at the provider\u2019s own ' +
      'default and refuses the parameter, so none was sent. Not the same statement ' +
      'as no temperature declared: the choice was unavailable, not unmade',
  },
}

describe('the temperature the chosen model accepts', () => {
  it('draws the slider from the served bounds and from no range of its own', () => {
    const tuning = block(settingsScreen(CONFIGURED), 'tuning')

    // The range the route enforces, read off the wire. A console holding its own
    // bounds is a form offering a value the route refuses.
    expect(tuning.sampling.bounds).toBe(CONFIGURED.tuning.temperature_bounds)
    expect(tuning.sampling.chosen).toBe(CONFIGURED.tuning.temperature)
    // And no row among the whole numbers is the temperature: it is the one setting a
    // model may have none of, so it is its own field rather than a row with a
    // nullable range.
    expect(tuning.numbers.map((one) => one.name)).toEqual([
      'turns_per_episode',
      'episodes_per_family',
      'attempts_per_case',
    ])
  })

  it('offers no temperature at all for a model that accepts none, and says why', () => {
    const on = block(settingsScreen(ON_A_REASONING_MODEL), 'tuning')

    // The reasoning select's own rule, read the other way round: a slider against a
    // model that refuses the parameter is a control whose every value the route
    // refuses, and before this the form learned that from the 422 after the operator
    // had already moved it (#4).
    expect(on.sampling.bounds).toBeNull()
    // Drawn on the served bounds and on nothing the component decided for itself.
    expect(component).toContain('block.sampling.bounds !== null')
    expect(component).toContain('block.sampling.bounds.low')
    expect(component).toContain('block.sampling.bounds.high')
    // And the reason is drawn where the slider was, in the response's own words: a
    // control that was there a moment ago and is now gone is a silence an operator
    // decodes as a console that lost the setting.
    expect(component).toContain('{block.sampling.stated}')

    // Two statements and never one. *This model accepts none* is a choice nobody was
    // offered and *no temperature declared* is a choice nobody made, and both arrive
    // from the response rather than being composed here: the second is the sentence a
    // signed provenance block will print, and a console wording of its own would
    // only have to disagree with it once (ADR-0017).
    expect(on.sampling.stated).toBe(ON_A_REASONING_MODEL.tuning.temperature_stated)
    expect(on.sampling.absent).toBe(ON_A_REASONING_MODEL.tuning.temperature_absent)
    expect(on.sampling.stated).not.toBe(on.sampling.absent)
    // And the same field on a model that has the setting says the other thing, so
    // neither sentence is a constant this screen prints regardless.
    const chat = block(settingsScreen(CONFIGURED), 'tuning')
    expect(chat.sampling.stated).toBe(CONFIGURED.tuning.temperature_stated)
    expect(chat.sampling.stated).not.toBe(on.sampling.stated)
  })

  it('holds no copy of the capability table and no model name of its own', () => {
    // Which model accepts what is declared once, in `backend/bench/capability.py`,
    // and reaches this screen as served state. A console that named a model or a
    // family here would be a second table, and the two would disagree the first time
    // a provider shipped a variant only one of them had heard of.
    for (const source of [component, view]) {
      for (const restated of [
        'gpt-',
        'openai/',
        'anthropic/',
        'claude-',
        'deepseek',
        'openrouter:',
      ]) {
        expect(source).not.toContain(restated)
      }
    }
  })
})

describe('the effort each instrument is set to', () => {
  it('is stated on every one of the four rows, and never left blank', () => {
    const models = block(settingsScreen(CONFIGURED), 'models').models

    // The row was the model and not what the model was set to, so a reader saw which
    // model the adjudicator runs on and not the conditions it ran under — and two
    // runs of one model at one temperature and different effort are two different
    // instruments (#5).
    expect(models.map((model) => model.effort)).toEqual(
      CONFIGURED.models.map((model) => model.effort),
    )
    for (const model of models) {
      expect(model.effort.trim()).not.toBe('')
    }

    // The one row this bench holds an effort for carries the record's own sentence,
    // and the three it holds none for state that rather than showing a blank.
    const [attacker] = models.filter((model) =>
      model.instrument.includes('adaptive attacker'),
    )
    expect(attacker.effort).toContain('reasoning effort medium')
    expect(models.filter((model) => model.effort === attacker.effort)).toHaveLength(1)
  })
})

describe('nothing on this screen changes a setting', () => {
  it('changes the declared inputs of a run and nothing else on the bench', () => {
    for (const bench of [CONFIGURED, UNSIGNING]) {
      const blocks = settingsScreen(bench)

      // Every leaf of every *stating* block is a string, a boolean or a declared
      // number: there is nowhere in those values for a callback to live, which is
      // what "states and changes nothing" means at the seam this screen is tested
      // at. The tuning block is the exception and it is one block (ADR-0025).
      const stating = blocks.filter((one) => one.kind !== 'tuning')
      for (const leaf of everyOtherLeaf(stating)) {
        expect(['boolean', 'number']).toContain(typeof leaf)
      }
      expect(blocks.filter((one) => one.kind === 'tuning')).toHaveLength(1)

      // And no field anywhere named for something that happens to a *key* or to the
      // library. Rotation stays in the environment, because a key made on demand
      // signs every report with one nobody published (ADR-0017, ADR-0020), and the
      // library is what was mounted.
      for (const field of fieldsOf(blocks)) {
        expect(field).not.toMatch(/rotate|key|sign|library|retire|cite/i)
      }
    }

    // The component itself, read rather than rendered. The form is admitted; what is
    // asserted is that it is the *only* write and that it cannot reach anything else
    // on this bench — no run started, no interrupt answered, no nonce issued, no gate
    // run, and no fetch of its own outside the two named calls.
    expect(component).toContain('export function SettingsScreen')
    expect(component).toContain('tuneBench')
    for (const beyond of [
      'startRun',
      'answerTheInterrupt',
      'issueNonce',
      'startGateRun',
      'fetch(',
      'method:',
    ]) {
      expect(component).not.toContain(beyond)
    }
  })

  it('sends the six settings together, on change, with no confirm step', () => {
    // A caller that could set the turn budget without restating the model would let
    // a bench name one instrument in a report while another attacked, which is why
    // the request takes all six. Asserted over the source, because what this
    // guards is the shape of the call and not what the screen looks like. Six since
    // #5 added the reasoning effort; this list said five until #57 counted it.
    const call = component.slice(component.indexOf('await tuneBench({'))
    // No button an operator can press: these are the settings the *next* run starts
    // with, and that run has its own attestation and its own halt in front of its own
    // estimate (ADR-0007). Nothing on this screen spends anything, so there is
    // nothing here to confirm.
    //
    // The one `<button>` on the file is `hidden`, and the ban is worded to admit
    // exactly that and nothing wider. It is the form's default button and it exists
    // because implicit submission needs one where more than one field blocks the
    // keypress — three number boxes do (#120) — so without it Enter would reach the
    // handler on no screen at all. `hidden` keeps it out of the tab order and out of
    // the accessibility tree: it is a keystroke and not a control, which is why the
    // claim above survives it. A `<button` here without `hidden` is the confirm step
    // this screen must not grow.
    const buttons = component.match(/<button[^>]*>/g) ?? []
    expect(buttons).toEqual(['<button type="submit" hidden>'])
    // `onSubmit` was banned beside it and is not any more, and the claim the ban was
    // making is the one above: no confirm step. The handler this screen has now is
    // not one — it sends the same six settings the settled timer would have sent,
    // 400ms earlier, because a form of number boxes where Enter does nothing is a
    // form a keyboard cannot finish (#120). What would be a confirm step is a
    // control to press, and the lines above still say there is none.
    // And the send is still the one call, on change and on Enter alike: `tuneBench`
    // is reached from `send` and from nowhere else.
    expect(component.match(/tuneBench\(/g) ?? []).toHaveLength(1)
    for (const field of [
      'attacker_model:',
      'temperature:',
      'reasoning_effort:',
      'turns_per_episode:',
      'episodes_per_family:',
      'attempts_per_case:',
    ]) {
      expect(call).toContain(field)
    }
    // The empty box is null and not zero: *no temperature declared* and *sampled at
    // zero* are two different declarations.
    expect(call).toContain("=== '' ? null")
  })

  it('draws the bench’s own caveat about the scored denominator', () => {
    const tuning = block(settingsScreen(CONFIGURED), 'tuning')

    // Carried, never paraphrased: five of the six settings bound a layer that is
    // scored on nothing, and this one moves the number the gate is decided at.
    // The reasoning effort is carried as the closed list the route enforces, with the
    // bench's own sentence beside it: two runs of one model at one temperature and
    // different effort are two different instruments, and the screen may not say one
    // thing about that while the signed document says another (#5).
    expect(tuning.reasoning.levels).toBe(CONFIGURED.tuning.reasoning_efforts)
    expect(tuning.reasoning.chosen).toBe('medium')
    expect(tuning.reasoning.stated).toBe(CONFIGURED.tuning.reasoning_effort_stated)
    expect(tuning.reasoning.absent).toBe(CONFIGURED.tuning.reasoning_effort_absent)
    expect(tuning.reasoning.decides).toContain('two different instruments')

    expect(tuning.warning).toBe(CONFIGURED.tuning.attempts_warning)
    expect(tuning.warning).toContain('not a gate result')
    expect(component).toContain('block.warning')
    // And the n both figures are read at is beside it, at the current setting and at
    // the declared rule, so a reader sees at a glance which one this bench is on.
    expect(tuning.attemptsPerFamily).toContain('21')
    expect(tuning.declaredAttemptsPerCase).toContain('10')
  })
})
