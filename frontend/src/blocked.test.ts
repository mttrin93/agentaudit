/**
 * That the two walks draw one list, and that both of them cite it.
 *
 * The reasons a primary button is dead are the register walk's and the gate walk's
 * alike, and they were two copies of the same `<ul className="blocked">` — of which
 * one carried the id that binds it to its button and one did not. What that costs is
 * not visible in a screenshot: a screen reader in browse mode reads a disabled
 * control and, with no description on it, reads *Continue, dimmed* and nothing else.
 *
 * **One walk draws it now.** The register walk's list restated its own screen — three
 * unticked boxes and the field above them — and came off at the operator's request;
 * `RegisterScreen.tsx` says so where it stood, and says what the lost citation costs a
 * reader who cannot see the boxes. So what is asserted here is narrower than it was:
 * the module is still the one place a list is written, and the walk that draws one
 * still cites it. Nothing here holds the register walk to drawing one.
 *
 * Asserted over the sources because `npm test` runs in node with no DOM
 * (`vite.config.ts`). `e2e/keyboard.spec.ts` reads a list and its binding off a real
 * page.
 */

import { describe, expect, it } from 'vitest'

import blocked from './blocked.tsx?raw'
import register from './register/RegisterScreen.tsx?raw'
import gate from './console/GateAttestation.tsx?raw'

/**
 * The walks with a primary button held by an incomplete declaration.
 *
 * Both are held; `drawing` below is the one that says why on the screen.
 */
const walks: Readonly<Record<string, string>> = {
  './register/RegisterScreen.tsx': register,
  './console/GateAttestation.tsx': gate,
}

/** The walks that draw the list, and therefore owe it a citation. */
const drawing: Readonly<Record<string, string>> = {
  './console/GateAttestation.tsx': gate,
}

describe('the reasons over a dead primary button', () => {
  it('are written in one place', () => {
    expect(blocked).toContain('className="blocked"')
    for (const [path, source] of Object.entries(walks)) {
      expect(source, path).not.toContain('className="blocked"')
    }
  })

  it('are cited by the button on the walk that draws them', () => {
    for (const [path, source] of Object.entries(drawing)) {
      expect(source, path).toContain('<Blocked reasons=')
      expect(source, path).toContain('aria-describedby={')
      expect(source, path).toContain('STILL_UNDECLARED')
      // The id itself is written in one file. A walk that spelled it out again is a
      // walk that keeps citing it the day the string moves.
      expect(source, path).not.toContain("'still-undeclared'")
    }
  })

  it('are never cited by a walk that draws none', () => {
    // The dangling half of the same pair: an `aria-describedby` naming an id no
    // element on the page carries resolves to nothing, which is worse than the
    // silence it was meant to fill.
    for (const [path, source] of Object.entries(walks)) {
      if (path in drawing) {
        continue
      }
      expect(source, path).not.toContain('<Blocked reasons=')
      expect(source, path).not.toContain('STILL_UNDECLARED')
    }
  })
})
