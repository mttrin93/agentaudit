/**
 * The console's own door: whether an issuer was declared, who is signed in, and
 * what a refusal from the bench's door leaves an operator to do.
 *
 * The decisions are here and the mounting is in `TheDoor.tsx`, for the reason
 * `rail.ts` is not `ConsoleShell.tsx`: these are answerable in node with no DOM and
 * no provider, and a rule that had to be rendered to be checked is a rule nobody
 * checks. The seam the token itself goes through is somewhere else again —
 * `api/http.ts`, one place, under
 * [ADR-0116](../../../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md).
 */

import { createContext, useContext } from 'react'

import type { DoorRefusal } from '../api/bench'

/**
 * The issuer this build was given, or `null` for a console that has none.
 *
 * **An absent key is a console with no sign-in, and that is not the bench being
 * open.** The gate is the API's (ADR-0121): a console that attends no door sends no
 * `Authorization` header, and a bench with a door refuses every one of those
 * requests with a sentence the operator reads. So *unconfigured* here costs a clone
 * nothing and grants it nothing — which is the opposite of the deployed factory,
 * where unconfigured must never mean open and the answer is to refuse to boot.
 *
 * Empty is read as absent rather than passed on. `VITE_CLERK_PUBLISHABLE_KEY=` with
 * nothing after it is what a half-finished setup leaves in a `.env`, and the
 * provider's answer to an empty key is a throw at mount: a console that will not
 * render at all, in place of one that says it has no issuer.
 */
export function issuerDeclaredIn(env: {
  VITE_CLERK_PUBLISHABLE_KEY?: string
}): string | null {
  const declared = env.VITE_CLERK_PUBLISHABLE_KEY?.trim()
  return declared ? declared : null
}

/**
 * What the issuer holds about the person at the console, in the two readings this
 * app has a use for.
 *
 * **They are not the same string and the difference is the point.** `subject` is
 * what the bench records — `backend/identity.py` takes the token's `sub` and
 * nothing else, so that is the name in the signed document. `named` is what a rail
 * prints to a person who is standing there, which is a display name and evidence of
 * nothing. A console that showed only the first would be unreadable; one that showed
 * only the second would let a screen imply the report carries a full name when it
 * carries an opaque id.
 */
export interface Operator {
  named: string
  subject: string
}

/** The shape of the issuer's user this console reads, and no more of it than that. */
export interface IssuedUser {
  id: string
  fullName?: string | null
  username?: string | null
  primaryEmailAddress?: { emailAddress?: string | null } | null
}

/**
 * The signed-in operator, named by the best thing the issuer holds.
 *
 * Full name, username, email, and then the subject itself — in that order, and the
 * last one is why this never answers an empty string. An account can be created with
 * an email and nothing else, and a rail with a blank where a name goes reads as a
 * console that has lost the session rather than as an issuer that was told no name.
 */
export function theOperator(user: IssuedUser): Operator {
  const held = [
    user.fullName,
    user.username,
    user.primaryEmailAddress?.emailAddress,
    user.id,
  ]
  return {
    named: held.find((one) => one?.trim())?.trim() ?? user.id,
    subject: user.id,
  }
}

/**
 * A refusal at the bench's door, as the console shows it: a heading, the verifier's
 * own sentence, and whether signing in again is the thing to do.
 *
 * The sentence is carried and never rewritten. It is the bench's, it names the
 * cause, and a console that paraphrased it would be putting its own words where the
 * refusal's were — the same rule the identity sentence is under (ADR-0123).
 */
export interface Remedy {
  heading: string
  statement: string
  signInAgain: boolean
}

/** What the console says when the bench would not take the session. */
export const SESSION_REFUSED = 'The bench did not take this session'

/** What it says when the bench could not reach the issuer to ask. */
export const ISSUER_UNREACHABLE = 'The bench could not reach the issuer'

/**
 * The refusal, read as something to do about it.
 *
 * **The two kinds do not collapse into one message.** `sign_in_again` is a fact
 * about the session and the way out is the door; `issuer_unreachable` is a fact
 * about the issuer, where signing in again is not the remedy and would fail in
 * exactly the same way — a console that offered it would be sending an operator
 * round a loop to be told the same thing. The seam holds the two apart on the
 * body's shape rather than the status (`api/http.ts`); this holds them apart in
 * what a person is asked to do.
 *
 * `cause` is not branched on. All four of the credential causes have the same
 * remedy — present a session the bench will take — and the sentence is the part
 * that says which of them happened.
 */
export function remedyFor(refusal: DoorRefusal): Remedy {
  return refusal.kind === 'sign_in_again'
    ? { heading: SESSION_REFUSED, statement: refusal.statement, signInAgain: true }
    : {
        heading: ISSUER_UNREACHABLE,
        statement: refusal.statement,
        signInAgain: false,
      }
}

/**
 * The issuer's components, painted out of this console's stylesheet.
 *
 * **Read from the page rather than written down twice.** The issuer's sign-in ships
 * a palette of its own, and a console whose door is a white card in front of a
 * near-black application is a door that looks like somebody else's site. The values
 * could have been copied out of `index.css` as hexes; they are read off the root
 * element's custom properties instead, so the two cannot drift — a token retuned in
 * the stylesheet retunes the sign-in on the same commit, and there is no second
 * list of colours in this repository to forget.
 *
 * The reader is an argument so that this is answerable with no DOM. In the browser
 * it is `getComputedStyle(document.documentElement).getPropertyValue`.
 *
 * **A token the stylesheet does not define is left out, not sent empty.** An empty
 * declaration is one the browser drops, which would leave the issuer's own colour
 * in that one place — a near-black card with one white field in it is worse than a
 * card that is entirely theirs. What is kept is trimmed: a computed custom property
 * comes back with the whitespace its declaration was written with, and these go
 * into a style attribute.
 *
 * Only light is not catered for: the console declares `color-scheme: dark` and has
 * exactly one palette (`index.css`), so the sign-in takes the same one. A console
 * that grew a light theme would grow it here in the same pass, because these names
 * are that stylesheet's and nothing else's.
 */
export function theConsolesPalette(
  token: (name: string) => string,
): Record<string, string> {
  const painted: Record<string, string> = {
    colorBackground: token('--page'),
    colorForeground: token('--ink'),
    colorMutedForeground: token('--quiet'),
    colorPrimary: token('--accent'),
    // The ink a button in `--accent` is lettered in: the darkest surface this
    // stylesheet has, which is what the console's own accent rows are set against.
    colorPrimaryForeground: token('--paper'),
    colorDanger: token('--refusal'),
    colorInput: token('--paper'),
    colorInputForeground: token('--ink'),
    colorNeutral: token('--ink'),
    borderRadius: token('--radius'),
  }
  return Object.fromEntries(
    Object.entries(painted)
      .map(([name, value]) => [name, value.trim()] as const)
      .filter(([, value]) => value !== ''),
  )
}

/**
 * What a screen inside the door can read: who is signed in, whatever the bench last
 * refused, and the two ways out of it.
 *
 * **Deliberately not a token.** The token has exactly one route out of this app and
 * it is `api/http.ts` (ADR-0116); a screen that could read one could send one
 * somewhere else. What a screen gets is a name to print and a refusal to show.
 */
export interface AtTheDoor {
  operator: Operator
  refusal: Remedy | null
  /** Sign out, which is how a session the bench will take is presented. */
  signInAgain: () => void
  /** Put the refusal away. It comes back on the next request that earns it. */
  letItGo: () => void
}

/**
 * The door, as everything inside it sees it. `null` is a console with no issuer.
 *
 * The context is declared here rather than beside the provider because this is the
 * file every consumer already imports for the types on it, and because a hook that
 * answers `null` outside a provider is answerable in node: `TheDoor.tsx` is where a
 * value is put in, and nothing else about it needs a DOM.
 */
export const TheDoorAttended = createContext<AtTheDoor | null>(null)

/**
 * The signed-in operator, or `null` where this console has no issuer.
 *
 * `null` and not a throw: a clone with no issuer renders every screen, so a screen
 * asking who is signed in has to be told *nobody* rather than crash outside a
 * provider that was never mounted.
 */
export function useOperator(): AtTheDoor | null {
  return useContext(TheDoorAttended)
}
