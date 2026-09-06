/**
 * That an input's refusal mark and its message are one edit and not two.
 *
 * `npm test` runs in node with no DOM by the spec's own choice (`vite.config.ts`),
 * so what a screen *renders* is asserted in a browser — `e2e/keyboard.spec.ts` drives
 * a `422` onto a field and reads the mark, the message and the binding between them
 * off the page. What that spec cannot say is that the *next* field somebody adds will
 * carry both. It asserts one field.
 *
 * So this reads the screen's source, which is where that claim lives. The failure it
 * guards is an input marked `aria-invalid` with `aria-describedby` pointing at an id
 * nothing renders: a dangling reference a screen reader resolves to nothing, green in
 * every test because the field it happened to a nobody drove a refusal onto. It is
 * unreachable while the mark and the message are one component — the attributes and
 * the message are derived from one string in one place, and there is no way to be
 * handed the first without the second.
 *
 * Asserted over the text rather than by rendering, and the text is enough because the
 * claim *is* textual: it is that this file writes those attributes in exactly one
 * place. A rendering test would prove it of the fields drawn today.
 */

import { describe, expect, it } from 'vitest'

import screen from './RegisterScreen.tsx?raw'

/** How many times a string occurs in the screen's source. */
function occurrences(text: string, what: string): number {
  return text.split(what).length - 1
}

/**
 * The body of the one component that may mark an input refused, sliced out of the
 * file so that the assertions below can say *and nowhere else*.
 *
 * From its declaration to the first line that closes a top-level block, which is how
 * every function in this file ends: a `}` in the first column.
 */
function fieldComponent(): string {
  const from = screen.indexOf('function Field(')
  expect(from, 'RegisterScreen no longer declares a `Field` component').toBeGreaterThan(
    -1,
  )
  const to = screen.indexOf('\n}\n', from)
  const body = screen.slice(from, to)
  // The slice is the component and stops at it. A `}` in the first column ends every
  // top-level block in this file, so a slice carrying a second declaration is one
  // that ran past the end of this one — and every assertion below would then be
  // about more of the file than it says it is, silently.
  expect(body, 'the field component was sliced past its own end').not.toMatch(
    /\nfunction |\nconst |\ninterface /,
  )
  return body
}

describe('the mark on a refused input and the message under it', () => {
  it('are written in one place, and that place is the field component', () => {
    const field = fieldComponent()
    // One mark and one message block in the whole screen. Two would mean a field
    // that can be given one of them. Matched as the code that writes them rather
    // than as the words, which the prose around them also uses.
    for (const written of ["'aria-invalid': true", 'className="field-refused"']) {
      expect(occurrences(screen, written), written).toBe(1)
      expect(occurrences(field, written), written).toBe(1)
    }
  })

  it('cite one id, derived once, on both ends of the binding', () => {
    const field = fieldComponent()
    // Twice: the attribute that points at the message, and the message that answers
    // to it. Both inside the component, so neither can be written without the other.
    // The declaration is `saidAt(field: string)` and is not one of the two.
    expect(occurrences(screen, 'saidAt(field)')).toBe(2)
    expect(occurrences(field, 'saidAt(field)')).toBe(2)
  })

  it('are the only way an input on this walk is given an id', () => {
    // The id of an input is the `loc` path a `422` carries for it (ADR-0076), and it
    // is derived from the field name inside the component that also draws the
    // message. An `id` written at a call site is an input that can be refused with
    // nothing under it to say why.
    const outside = screen.replace(fieldComponent(), '')
    expect(outside).not.toMatch(/\bid=\{FIELDS\./)
    expect(outside).not.toMatch(/\bid="body\./)
  })
})
