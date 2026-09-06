/**
 * That the two walks draw one list, and that both of them cite it.
 *
 * The reasons a primary button is dead are the register walk's and the gate walk's
 * alike, and they were two copies of the same `<ul className="blocked">` — of which
 * one carried the id that binds it to its button and one did not. What that costs is
 * not visible in a screenshot: a screen reader in browse mode reads a disabled
 * control and, with no description on it, reads *Continue, dimmed* and nothing else.
 *
 * Asserted over the sources because `npm test` runs in node with no DOM
 * (`vite.config.ts`). `e2e/keyboard.spec.ts` reads the register walk's list and its
 * binding off a real page; what it cannot say is that the *other* walk has them, and
 * that is exactly the half that was missing.
 */

import { describe, expect, it } from 'vitest'

import blocked from './blocked.tsx?raw'
import register from './register/RegisterScreen.tsx?raw'
import gate from './console/GateAttestation.tsx?raw'

/** The two walks with a primary button held by an incomplete declaration. */
const walks: Readonly<Record<string, string>> = {
  './register/RegisterScreen.tsx': register,
  './console/GateAttestation.tsx': gate,
}

describe('the reasons over a dead primary button', () => {
  it('are written in one place', () => {
    expect(blocked).toContain('className="blocked"')
    for (const [path, source] of Object.entries(walks)) {
      expect(source, path).not.toContain('className="blocked"')
    }
  })

  it('are cited by the button on both walks, out of the module that draws them', () => {
    for (const [path, source] of Object.entries(walks)) {
      expect(source, path).toContain('<Blocked reasons=')
      expect(source, path).toContain('aria-describedby={')
      expect(source, path).toContain('STILL_UNDECLARED')
      // The id itself is written in one file. A walk that spelled it out again is a
      // walk that keeps citing it the day the string moves.
      expect(source, path).not.toContain("'still-undeclared'")
    }
  })
})
