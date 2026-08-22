/**
 * That a family reads as words on a screen and stays an identifier in the record.
 *
 * The assertion worth having is not that one string becomes another — it is that
 * nothing else does. A helper that title-cased, expanded or prettified a family name
 * would put a word on the screen that is in no document this bench signs, and the
 * vocabulary is arithmetic here rather than decoration.
 */

import { describe, expect, it } from 'vitest'

import { readFamily } from './families'

describe('a family as the screen says it', () => {
  it('is the wire name with its underscores opened out, and nothing else', () => {
    expect(readFamily('indirect_prompt_injection')).toBe('indirect prompt injection')
    expect(readFamily('halt_defeat')).toBe('halt defeat')
    // Not title-cased, not expanded, not renamed: an operator greps the record for
    // the word they read here, so the two differ by one character or the screen has
    // introduced a family the bench does not have.
    expect(readFamily('scope_creep')).toBe('scope creep')
    expect(readFamily('scope_creep').toLowerCase()).toBe(readFamily('scope_creep'))
  })

  it('leaves a name with nothing to open out exactly as it came', () => {
    // A seventh family arriving under a one-word name appears as itself rather than
    // through a mapping this file would have to be edited to know about.
    expect(readFamily('probity')).toBe('probity')
    expect(readFamily('')).toBe('')
  })

  it('is never a case id, which keeps the hyphens the record gave it', () => {
    // Called on a family and not on the identifiers beside it: a case id is the row
    // in the library and is grepped as it is written.
    expect(readFamily('scope-creep-002')).toBe('scope-creep-002')
  })
})
