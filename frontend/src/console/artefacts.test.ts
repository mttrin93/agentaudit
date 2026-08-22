/**
 * What the artefact list must say about every artefact on it, and what it may never
 * say instead.
 *
 * Seven claims, each of them a way this screen could quietly stop being evidence.
 *
 * **That all three results render whenever any of them does.** Asserted over an
 * artefact where one result failed, because the row where everything held is the one
 * that cannot go wrong: a screen tempted to draw one mark draws it where something
 * failed. A row with two results would let its reader infer the strongest claim from
 * the weakest, which is the inference ADR-0017 exists to prevent.
 *
 * **That the two claims stay two.** Integrity over the whole document and
 * re-derivability over the **scored layer alone** are two statements about two
 * different things, and the second is why the first is not enough. Asserted as two
 * labelled entries, neither of them the other and neither containing the other, and
 * with the adaptive layer named as recorded rather than reproducible (ADR-0010).
 *
 * **That a failure is named by its own outcome.** *Unsigned* and *signed by a key you
 * did not pin* are different facts about the sender. Asserted by reading three
 * artefacts that failed differently and requiring three different readings — a
 * generic failure mark would make two of them identical.
 *
 * **That the bench says the check is its own.** On every row, because what
 * circulates is a row: a sender's word for their own document is the thing a
 * signature exists to replace.
 *
 * **That no result is carried by colour alone.** There is no accent, hue, tick or
 * badge field anywhere in this view; what a component is given is the outcome's name
 * and a boolean redundant with it, and the component is read to confirm that the
 * name is printed in the element the class draws.
 *
 * **That the three files are offered under the names a verifier already knows.** The
 * filenames come off the wire in the order a verifier reads them, and nothing here
 * composes one: a file offered as `artefact-7f3c.json` is portable evidence a
 * recipient's tooling cannot find.
 *
 * **That nothing here is a figure.** Every leaf of the view is a string or a boolean,
 * so no rate, band, count of artefacts or mark over the three results can be on this
 * screen without this test failing.
 */

import { describe, expect, it } from 'vitest'

import type { ArtefactList, ArtefactRow, Verification } from '../api/bench'

import component from './ArtefactsScreen.tsx?raw'
import { artefactsReading, NO_ARTEFACTS_YET } from './artefacts'

const INTEGRITY =
  'Integrity, for the whole document. A valid signature says these bytes are the ' +
  'ones that were produced and that nothing has altered them — the adaptive section ' +
  'included, since the signature covers the whole payload and leaves no region ' +
  'unprotected (ADR-0017). It says nothing whatsoever about whether the agent is safe.'

const RE_DERIVABILITY =
  'Re-derivability, for the scored layer only. Every figure in the scored sections ' +
  'follows from the recorded attempts, the case records and the rule the payload ' +
  'carries. The adaptive layer is recorded and not reproducible: re-run it and the ' +
  'attacker takes a different path (ADR-0010, ADR-0017).'

const CHECKED_BY =
  'these three results were computed here, by the bench that produced the artefact, ' +
  'over the same bytes this run serves. It is not the check a recipient makes: ' +
  'download the three files and run `uv run python -m scripts.verify` over the ' +
  'directory.'

/** A verification as the route serves one, with the three outcomes handed in. */
function verification(
  signature: string,
  binding = 'rendering_matches_its_digest',
  arithmetic = 'arithmetic_agrees',
): Verification {
  const held =
    signature === 'signature_valid' &&
    binding === 'rendering_matches_its_digest' &&
    arithmetic === 'arithmetic_agrees'
  return {
    artefact: 'agentaudit.target-report',
    artefact_version: 1,
    target: 'the-checkout-agent',
    signature: { outcome: signature, statement: `the signature check: ${signature}` },
    binding: { outcome: binding, statement: `the binding check: ${binding}` },
    arithmetic: {
      outcome: arithmetic,
      statement: `the re-derivation: ${arithmetic}`,
    },
    verified: held,
    contradicted: !held && arithmetic !== 'nothing_to_re_derive',
    integrity: INTEGRITY,
    re_derivability: RE_DERIVABILITY,
    checked_by: CHECKED_BY,
  }
}

/** The three files, exactly as the route offers them. */
function files(runId: string): ArtefactRow['files'] {
  return [
    {
      filename: 'report.json',
      path: `/report/${runId}`,
      holds: 'the canonical JSON payload — the bytes the signature covers',
    },
    {
      filename: 'report.md',
      path: `/report/${runId}/rendering`,
      holds: 'the document a human reads, bound to those bytes by digest',
    },
    {
      filename: 'report.sig',
      path: `/report/${runId}/signature`,
      holds: 'the detached signature over the payload’s bytes',
    },
  ]
}

function row(runId: string, target: string, reading: Verification): ArtefactRow {
  return {
    run_id: runId,
    target,
    recorded_at: '2026-08-19T09:38:37.512345+00:00',
    files: files(runId),
    verification: reading,
  }
}

const VERIFY_COMMAND = 'uv run python -m scripts.verify path/to/the-three-files'

const STATEMENT =
  'one row per signed artefact, each with all three verification results named ' +
  'individually and the two claims stated separately. There is no mark here that ' +
  'combines the three results and no figure over these artefacts.'

/**
 * Three artefacts that failed three different checks, and one that failed none.
 *
 * The list an engineer most needs: one they can send, one no recipient pinning the
 * published key can check, one whose human view was edited after it was bound, and
 * one that was never signed at all.
 */
const LISTED: ArtefactList = {
  artefacts: [
    row('run-1', 'the-checkout-agent', verification('signature_valid')),
    row('run-2', 'the-support-agent', verification('signed_by_another_key')),
    row('run-3', 'the-triage-agent', verification('unsigned')),
    row(
      'run-4',
      'the-billing-agent',
      verification('signature_valid', 'rendering_does_not_match_its_digest'),
    ),
  ],
  statement: STATEMENT,
  verify_command: VERIFY_COMMAND,
}

const EMPTY: ArtefactList = {
  artefacts: [],
  statement: STATEMENT,
  verify_command: VERIFY_COMMAND,
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

/** Every leaf that is not a string, which is where a figure would have to be. */
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

/** Every field name anywhere in the view. */
function fieldsOf(node: unknown): string[] {
  if (Array.isArray(node)) {
    return node.flatMap(fieldsOf)
  }
  if (node && typeof node === 'object') {
    return Object.entries(node).flatMap(([name, value]) => [
      name,
      ...fieldsOf(value),
    ])
  }
  return []
}

/** The listed artefacts, or a failure that names which shape came back. */
function listed(list: ArtefactList) {
  const reading = artefactsReading(list)
  if (!reading.listed) {
    throw new Error('a bench with artefacts read as a bench with none')
  }
  return reading
}

describe('the three verification results', () => {
  it('renders all three on every artefact, including the ones that failed', () => {
    const reading = listed(LISTED)

    expect(reading.artefacts).toHaveLength(4)
    for (const artefact of reading.artefacts) {
      // Three, always three, and in the verifier's own order: the transport's two
      // questions and then the one about the bench.
      expect(artefact.verification.checks.map((check) => check.name)).toEqual([
        'Signature',
        'Rendering binding',
        'Arithmetic re-derived',
      ])
      for (const check of artefact.verification.checks) {
        expect(check.outcome).not.toBe('')
        expect(check.statement).not.toBe('')
      }
    }

    // And the failing rows are on the list rather than filtered off it: the artefact
    // an engineer must not send is the one this screen exists to show.
    const outcomes = reading.artefacts.map(
      (artefact) => artefact.verification.checks[0].outcome,
    )
    expect(outcomes).toContain('signed_by_another_key')
    expect(outcomes).toContain('unsigned')
  })

  /**
   * The word the list carries, which is the only thing on a row that says not to send
   * it.
   *
   * Three outcomes and three different words, asserted as three: a list that named a
   * contradicted artefact the way it names a verified one would be inviting somebody
   * to send the one artefact this screen exists to stop. The word is not a substitute
   * for the three results — those are on the row too, and the test above reads them —
   * it is what survives on a list that prints no sentence.
   */
  it('says how each artefact settled in a word, and never in the same word', () => {
    const [sendable, unpinned, unsigned, altered] = listed(LISTED).artefacts

    expect(sendable.settledInAWord).toBe('Verified')
    expect(unpinned.settledInAWord).toBe('Did not verify')
    expect(unsigned.settledInAWord).toBe('Did not verify')
    expect(altered.settledInAWord).toBe('Did not verify')
    expect(sendable.settledInAWord).not.toBe(unpinned.settledInAWord)

    // And the word never stands alone as the account of what happened: the sentence
    // it was cut down from is still on the row for the artefact's own screen.
    for (const artefact of listed(LISTED).artefacts) {
      expect(artefact.verification.heading).not.toBe('')
      expect(artefact.verification.heading).not.toBe(artefact.settledInAWord)
    }
  })

  it('names a failure by its own outcome rather than by a shared mark', () => {
    const [, unpinned, unsigned, altered] = listed(LISTED).artefacts

    // Three different facts about the sender, and three different names. An engineer
    // told only *did not verify* would go looking for a transport fault instead of
    // asking whose key signed their evidence.
    expect(unpinned.verification.checks[0].outcome).toBe('signed_by_another_key')
    expect(unsigned.verification.checks[0].outcome).toBe('unsigned')
    expect(altered.verification.checks[1].outcome).toBe(
      'rendering_does_not_match_its_digest',
    )
    expect(
      new Set(
        [unpinned, unsigned, altered].map((artefact) =>
          artefact.verification.checks.map((check) => check.outcome).join('/'),
        ),
      ).size,
    ).toBe(3)

    // The other two results on an unpinned artefact still held, and they say so:
    // the document was not altered, it was signed by somebody else's key.
    expect(unpinned.verification.checks[1].held).toBe(true)
    expect(unpinned.verification.checks[2].held).toBe(true)
    expect(unpinned.verification.checks[0].held).toBe(false)
  })

  it('marks a result by name and never by colour alone', () => {
    const reading = listed(LISTED)

    // Nothing in this view names a hue, a tick or a severity, so there is nothing
    // for a component to draw a judgement with. Colour carries identity and order in
    // this console and never a verdict (ADR-0005, spec §75).
    for (const field of fieldsOf(reading)) {
      expect(field).not.toMatch(/accent|colou?r|hue|tick|badge|icon|severity|grade/i)
    }

    // And the component prints the outcome's name inside the element the class draws,
    // so the border only repeats what the words already said.
    expect(component).toContain("check.held ? 'check' : 'check did-not-hold'")
    expect(component).toContain('{check.outcome}')
    expect(component).not.toMatch(/verified \? '[a-z-]*(green|good|pass)/i)
    // And it never branches on `settled`, the one word that collapses the three
    // results: the screen draws them one at a time, so there is nothing for a class
    // to be chosen by.
    expect(component).not.toMatch(/settled/)
  })
})

describe('the two claims', () => {
  it('states them separately, and scopes the second to the scored layer', () => {
    for (const artefact of listed(LISTED).artefacts) {
      const [integrity, reDerivability] = artefact.verification.claims

      expect(artefact.verification.claims).toHaveLength(2)
      expect(integrity.label).toMatch(/whole document/i)
      expect(integrity.statement).toContain('Integrity, for the whole document')
      expect(reDerivability.label).toMatch(/scored layer/i)
      expect(reDerivability.statement).toContain(
        'Re-derivability, for the scored layer only',
      )
      // The adaptive layer is recorded and not reproducible, so re-derivability is
      // not widened to cover it: a valid signature over it is a claim about its
      // bytes (ADR-0010).
      expect(reDerivability.statement).toContain('recorded and not reproducible')

      // Two statements, and neither is the other or a container for it: a row
      // carrying one sentence would be the conflation whatever that sentence said.
      expect(integrity.label).not.toBe(reDerivability.label)
      expect(integrity.statement).not.toBe(reDerivability.statement)
      expect(integrity.statement).not.toContain(reDerivability.statement)
      expect(reDerivability.statement).not.toContain(integrity.statement)
    }
  })

  it('says on every artefact that the bench computed the results', () => {
    const reading = listed(LISTED)

    for (const artefact of reading.artefacts) {
      // Per artefact rather than once at the top, because what circulates is a
      // block: a sender's word for their own document is the thing a signature
      // exists to replace.
      expect(artefact.verification.checkedBy).toBe(CHECKED_BY)
      expect(artefact.verification.checkedBy).toMatch(/by the bench that produced/i)
      expect(artefact.verification.notAQualityClaim).not.toBe('')
    }
    // And the command that makes the answer a recipient's, once, because the
    // verifier is handed a directory and not a run id.
    expect(reading.command).toBe(VERIFY_COMMAND)
    expect(reading.checkedByTheBench).toMatch(/not the check a recipient makes/i)
  })
})

describe('the three files', () => {
  it('offers them under the names a verifier already knows, at the paths that serve them', () => {
    for (const artefact of listed(LISTED).artefacts) {
      expect(artefact.files.map((file) => file.filename)).toEqual([
        'report.json',
        'report.md',
        'report.sig',
      ])
      // The path is the route's, and the id in it is the run's: a client saving the
      // three responses under the names they arrive with has a directory that
      // verifies with nothing in between.
      expect(artefact.files.map((file) => file.path)).toEqual([
        `/report/${artefact.id}`,
        `/report/${artefact.id}/rendering`,
        `/report/${artefact.id}/signature`,
      ])
      for (const file of artefact.files) {
        expect(file.holds).not.toBe('')
      }
    }

    // The command is one line and nothing but the command, because what happens to
    // it is a selection and a paste.
    const reading = listed(LISTED)
    expect(reading.command.split('\n')).toHaveLength(1)
    expect(reading.command).not.toMatch(/^\s|[$>]|\s$/)
    expect(reading.commandStatement).toMatch(/one directory/i)
  })
})

describe('what this list is not', () => {
  it('carries no figure, no count and no mark over the three results', () => {
    const reading = listed(LISTED)

    // Every leaf is a string or a boolean. A rate, a band, a count of artefacts or a
    // score over the three results would be a number, and there is nowhere in this
    // value for one to be (ADR-0005, D12).
    for (const leaf of everyOtherLeaf(reading)) {
      expect(typeof leaf).toBe('boolean')
    }
    for (const field of fieldsOf(reading)) {
      expect(field).not.toMatch(/total|average|mean|count|overall|composite|rank/i)
    }
    // And no sentence says a target passed or failed: an artefact is a document
    // about a target, and a target has rates, intervals and bands (ADR-0018).
    for (const said of everyString(reading)) {
      for (const artefact of reading.artefacts) {
        expect(said).not.toContain(`${artefact.target} passed`)
        expect(said).not.toContain(`${artefact.target} failed`)
      }
    }
  })

  it('states the absence rather than drawing an empty list', () => {
    const reading = artefactsReading(EMPTY)

    if (reading.listed) {
      throw new Error('a bench with no artefacts read as a bench with some')
    }
    expect(reading.statement).toBe(NO_ARTEFACTS_YET)
    expect(reading.statement).toMatch(/no signed artefact/i)
    // The absence names what it is: a run that completed on a bench with no key has
    // no artefact, and that fact lives on the run rather than here.
    expect(reading.statement).toMatch(/no signing key/i)
    // Nothing here is a statement about a target, and there is no row to be empty.
    const held = reading as unknown as Record<string, unknown>
    expect(held.artefacts).toBeUndefined()
    // The command is still shown: how a recipient checks an artefact is true whether
    // or not this bench has produced one.
    expect(reading.command).toBe(VERIFY_COMMAND)
  })
})
