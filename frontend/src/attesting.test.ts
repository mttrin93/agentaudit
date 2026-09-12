/**
 * That no walk on this console asks anybody to type the name it attests under.
 *
 * Three surfaces collect the attestation — a run's registration, a gate run and a
 * measurement over the pending routes — and all three used to open with a text input
 * labelled *who is attesting*. The name is the subject of the session the API
 * verified the request as (ADR-0116 §1), so a field for it is a field whose value
 * nothing reads: the walks stopped sending it in #246 and stopped asking for it here.
 *
 * **This is a test that something is gone, and that is why it reads the source.**
 * `npm test` runs in node with no DOM (`vite.config.ts`), so the markup itself is the
 * e2e suite's to assert. What a browser test cannot say is *and there is no second
 * one*: a fourth walk, or an input added back to one of these three, is caught here
 * and would be caught nowhere else until a `422` naming a field that is not a field
 * reached an operator mid-registration.
 *
 * The three files are named rather than globbed. A glob would go quietly green the
 * day one of them is renamed, and these are the three screens the decision is about.
 *
 * **What is not covered here or anywhere: what a signed-in operator sees.** Every
 * assertion below is about the absence, and the one rendering assertion this change
 * has is the walkthrough's, which runs the issuerless console against a `NO_DOOR`
 * bench (`playwright.config.ts`) and so reads the doorless line. Driving the other
 * branch needs a test user at the issuer, which the spec called out as the awkward
 * part and which #252 is where it is bought. The verified line has been read by a
 * person and by nothing else.
 */

import { describe, expect, it } from 'vitest'

import gate from './console/GateAttestation.tsx?raw'
import pending from './console/PendingDeciding.tsx?raw'
import register from './register/RegisterScreen.tsx?raw'
import { NOBODY_VERIFIED, whoIsAttesting } from './console/door'

/** The three walks that collect the attestation, each with its own screen. */
const WALKS = {
  'the register walk': register,
  'the gate walk': gate,
  'the pending-routes walk': pending,
}

describe('the name an attestation is recorded under', () => {
  it('is asked for on none of the three walks', () => {
    for (const [walk, source] of Object.entries(WALKS)) {
      // The label, the placeholder and the declaration key, each of which was on all
      // three of these screens and is on none of them now.
      expect(source, `${walk} still asks who is attesting`).not.toContain(
        'Who is attesting',
      )
      expect(source, `${walk} still offers the field's placeholder`).not.toContain(
        'recorded against every one of the three statements',
      )
      expect(source, `${walk} still declares an identity`).not.toContain('identity:')
    }
  })

  it('is drawn from the door on all three, out of one component', () => {
    // Not three sentences. The wording of what the bench will record is one wording,
    // for `GATE_RUN_STATEMENTS`' reason: three copies would only have to disagree
    // once for two screens to promise different things about one field.
    for (const [walk, source] of Object.entries(WALKS)) {
      expect(source, `${walk} draws no name at all`).toContain('<AttestingAs')
    }
  })

  it('is the bench’s own sentence on a console with no issuer', () => {
    // The case the e2e suite runs as (`playwright.config.ts`), and the one a screen
    // could most easily get wrong by printing a placeholder where a name would go.
    expect(whoIsAttesting(null).recorded).toBe(NOBODY_VERIFIED)
  })
})
