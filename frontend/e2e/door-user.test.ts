/**
 * What the doored walkthrough reads out of the environment, and what it does when it
 * is not there.
 *
 * A `.test.ts` under `e2e/` and so vitest's, not Playwright's — the division
 * `vite.config.ts` states: the `.spec.ts` files drive a browser, and this one
 * answers a dict. It is here rather than under `src/` because the module it covers is
 * test equipment and belongs beside the suite that reads it, and it is covered at all
 * because the reading it makes is the one that decides whether a suite ran or was
 * skipped — a function that got that wrong would leave a doored run reporting green
 * without having signed anybody in.
 */

import { describe, expect, it } from 'vitest'

import { DOOR_VARIABLES, doorUser } from './door-user.ts'

const EXPORTED = {
  AGENTAUDIT_E2E_CLERK_PUBLISHABLE_KEY: 'pk_test_nothing',
  AGENTAUDIT_E2E_ISSUER_JWT_KEY: '-----BEGIN PUBLIC KEY-----',
  AGENTAUDIT_E2E_CLERK_USER: 'walkthrough@example.test',
  AGENTAUDIT_E2E_CLERK_PASSWORD: 'not-a-real-password',
}

describe('the test user the doored walkthrough signs in as', () => {
  it('is declared when all four values are exported', () => {
    const read = doorUser(EXPORTED)
    expect(read.declared).toBe(true)
    if (!read.declared) return
    expect(read.publishableKey).toEqual('pk_test_nothing')
    expect(read.emailAddress).toEqual('walkthrough@example.test')
    expect(read.password).toEqual('not-a-real-password')
  })

  it('is undeclared on a clone that exported none of them, and says which', () => {
    const read = doorUser({})
    expect(read.declared).toBe(false)
    if (read.declared) return
    expect(read.missing).toEqual([...DOOR_VARIABLES])
    for (const variable of DOOR_VARIABLES) {
      expect(read.statement).toContain(variable)
    }
  })

  it('names the one that is missing when the other three are there', () => {
    const { AGENTAUDIT_E2E_CLERK_PASSWORD: _omitted, ...three } = EXPORTED
    const read = doorUser(three)
    expect(read.declared).toBe(false)
    if (read.declared) return
    expect(read.missing).toEqual(['AGENTAUDIT_E2E_CLERK_PASSWORD'])
  })

  it('reads a blank value as unset, the way every other reader here does', () => {
    const read = doorUser({ ...EXPORTED, AGENTAUDIT_E2E_CLERK_USER: '   ' })
    expect(read.declared).toBe(false)
    if (read.declared) return
    expect(read.missing).toEqual(['AGENTAUDIT_E2E_CLERK_USER'])
  })

  it('never puts the password in the sentence it prints', () => {
    const read = doorUser({ ...EXPORTED, AGENTAUDIT_E2E_CLERK_PUBLISHABLE_KEY: '' })
    expect(read.declared).toBe(false)
    if (read.declared) return
    expect(read.statement).not.toContain('not-a-real-password')
  })
})
