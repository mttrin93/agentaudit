/**
 * What the console makes of an issuer: whether there is one, who is signed in, and
 * what to do about a request the bench's door turned away.
 *
 * These run in node with no DOM, which is why the decisions live in `door.ts` and
 * not in the component that mounts them. The markup around all of this is the e2e
 * suite's; what is asserted here is the reasoning the component carries out.
 */

import { describe, expect, it } from 'vitest'

import {
  NOBODY_VERIFIED,
  issuerDeclaredIn,
  remedyFor,
  theConsolesPalette,
  theOperator,
  whoIsAttesting,
} from './door'

describe('the issuer, declared or not', () => {
  it('is the publishable key the build was given', () => {
    expect(issuerDeclaredIn({ VITE_CLERK_PUBLISHABLE_KEY: 'pk_test_abc' })).toBe(
      'pk_test_abc',
    )
  })

  it('is nobody where the variable is absent, which is a clone with no account', () => {
    expect(issuerDeclaredIn({})).toBeNull()
  })

  it('is nobody where the variable is there and empty', () => {
    // `VITE_CLERK_PUBLISHABLE_KEY=` in a `.env` is the shape a half-finished setup
    // leaves behind, and an empty string handed to the provider is a crash at mount
    // rather than a console that says it has no issuer.
    expect(issuerDeclaredIn({ VITE_CLERK_PUBLISHABLE_KEY: '   ' })).toBeNull()
  })
})

describe('who is signed in', () => {
  it('is named by the full name the issuer holds, and carries the subject under it', () => {
    expect(
      theOperator({
        id: 'user_2abc',
        fullName: 'Ada Lovelace',
        username: 'ada',
        primaryEmailAddress: { emailAddress: 'ada@example.com' },
      }),
    ).toEqual({ named: 'Ada Lovelace', subject: 'user_2abc' })
  })

  it('falls back through the username to the email, which is what an account with no name has', () => {
    expect(
      theOperator({
        id: 'user_2abc',
        fullName: null,
        username: null,
        primaryEmailAddress: { emailAddress: 'ada@example.com' },
      }).named,
    ).toBe('ada@example.com')
  })

  it('is named by the subject where the issuer holds nothing else, and never by nothing', () => {
    // The subject is the string the bench records against a run, so a console that
    // printed an empty name would be printing something other than the record.
    expect(
      theOperator({
        id: 'user_2abc',
        fullName: '  ',
        username: null,
        primaryEmailAddress: null,
      }).named,
    ).toBe('user_2abc')
  })
})

describe('who the bench will record this attestation against', () => {
  const ADA = {
    operator: { named: 'Ada Lovelace', subject: 'user_2abc' },
    refusal: null,
    signInAgain: () => {},
    letItGo: () => {},
  }

  it('is the display name to read and the subject to record, and they are not one string', () => {
    expect(whoIsAttesting(ADA)).toEqual({
      named: 'Ada Lovelace',
      recorded: 'user_2abc',
      verified: true,
    })
  })

  it('is the bench’s own sentence where this console attends no door', () => {
    // A clone built with no issuer signs nobody in, and the bench it talks to has no
    // door either: what lands in the artefact is `app.NOBODY_VERIFIED` (ADR-0122).
    // A screen that printed a friendlier placeholder here would be promising a name
    // the record will not carry.
    expect(whoIsAttesting(null)).toEqual({
      named: NOBODY_VERIFIED,
      recorded: NOBODY_VERIFIED,
      verified: false,
    })
  })

  it('says nobody was verified in the words the record uses, and not in a word of its own', () => {
    // The string is the backend's, and the two would have to disagree only once for
    // a screen to promise one thing and an artefact to say another. `anonymous` and
    // the empty string are the two ADR-0122 refused, and neither may creep back in
    // as a console-side softening.
    expect(NOBODY_VERIFIED).toBe('an operator this bench did not verify')
    expect(whoIsAttesting(null).verified).toBe(false)
  })
})

describe('what the bench’s door leaves an operator to do', () => {
  const EXPIRED = 'this session ran out — sign in again and the run is where it was.'

  it('offers the way back in for a session the bench would not take', () => {
    expect(
      remedyFor({ kind: 'sign_in_again', cause: 'expired', statement: EXPIRED }),
    ).toEqual({
      heading: 'The bench did not take this session',
      statement: EXPIRED,
      signInAgain: true,
    })
  })

  it('does not offer it for an issuer the bench could not reach', () => {
    // Signing in again is not the thing to do and would fail in the same way. The
    // two readings are held apart at the seam (`api/http.ts`) and they have to stay
    // apart here, or a console shows an outage as a rejected credential.
    const out = remedyFor({
      kind: 'issuer_unreachable',
      statement: 'the bench could not reach the issuer to check this session.',
    })
    expect(out.signInAgain).toBe(false)
    expect(out.heading).not.toBe('The bench did not take this session')
  })

  it('prints the verifier’s sentence whole', () => {
    const said =
      'no token was presented — the bench has a door and this request arrived ' +
      'without a credential.'
    expect(
      remedyFor({ kind: 'sign_in_again', cause: 'absent', statement: said }).statement,
    ).toBe(said)
  })
})

describe('the sign-in, painted in the console’s own colours', () => {
  const PALETTE: Record<string, string> = {
    '--page': '#0a141c',
    '--paper': '#081015',
    '--ink': '#e9f1ef',
    '--quiet': '#86949a',
    '--accent': '#5ce5b2',
    '--refusal': '#ffc4b8',
    '--line': '#253034',
    '--radius': '10px',
  }

  it('takes every colour from the stylesheet rather than repeating one', () => {
    const variables = theConsolesPalette((token) => PALETTE[token] ?? '')
    expect(variables).toEqual({
      colorBackground: '#0a141c',
      colorForeground: '#e9f1ef',
      colorMutedForeground: '#86949a',
      colorPrimary: '#5ce5b2',
      colorPrimaryForeground: '#081015',
      colorDanger: '#ffc4b8',
      colorInput: '#081015',
      colorInputForeground: '#e9f1ef',
      colorNeutral: '#e9f1ef',
      borderRadius: '10px',
    })
  })

  it('trims the space a computed custom property comes back with', () => {
    // `getPropertyValue` can answer with the leading whitespace the declaration was
    // written with, and the issuer's components put these straight into a style
    // attribute.
    const variables = theConsolesPalette((token) =>
      token === '--page' ? ' #0a141c' : (PALETTE[token] ?? ''),
    )
    expect(variables.colorBackground).toBe('#0a141c')
  })

  it('leaves out a token the stylesheet does not define rather than sending an empty one', () => {
    // `getPropertyValue` answers an empty string for a property that is not set,
    // and an empty string handed to the issuer's components is a declaration the
    // browser drops — the component renders in the issuer's own palette with one
    // colour missing rather than in this one.
    const variables = theConsolesPalette((token) =>
      token === '--accent' ? '' : (PALETTE[token] ?? ''),
    )
    expect('colorPrimary' in variables).toBe(false)
    expect(variables.colorBackground).toBe('#0a141c')
  })
})
