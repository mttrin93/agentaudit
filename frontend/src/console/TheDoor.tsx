/**
 * The console's door, mounted once around everything.
 *
 * **The shell is the boundary and there is no guard on a screen.** Signed out, the
 * whole console is the issuer's hosted sign-in; signed in, the app renders exactly
 * as it did, at the paths it has always served. Per-screen guards were the
 * alternative and they are the shape that goes wrong quietly: a screen added next
 * year without one is a screen that is open, and nothing fails. The
 * [spec](../../../docs/specs/the-authenticated-operator.md) says the same in one
 * line, and [ADR-0116](../../../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
 * is the decision behind it.
 *
 * **Hash routing is why this needs no callback route.** Every document request this
 * app serves is for `/` (`main.tsx`), so there is no server-rendered path for the
 * issuer to reconcile and no redirect route to add — and a session that expires on
 * the run screen comes back to the run screen, because the fragment never left the
 * browser.
 *
 * **The reasoning is in `door.ts` and the wiring is here**, the way `rail.ts` is not
 * `ConsoleShell.tsx`: what is answerable with no DOM is answered in node, and what
 * is left in this file is a provider, a memo and two pieces of markup.
 *
 * **No key declared is the console this repository has always been.** A clone with
 * no issuer account renders every screen and attends no door, which means no
 * `Authorization` header at all — the reading `api/http.ts` and ADR-0121 both call
 * declared-open. That is not this file letting somebody past a gate: the gate is
 * the API's, and a bench with a door refuses a headerless request with a sentence
 * this shell then shows. What it buys is that `npm run e2e`, `npm run dev` against
 * a `NO_DOOR` bench, and a contributor with no account all still work.
 */

import { useMemo, useState, type ReactNode } from 'react'
import { ClerkProvider, SignedIn, SignedOut, SignIn, useClerk, useUser } from '@clerk/clerk-react'

import { attendTheDoor, type DoorRefusal } from '../api/bench'
import {
  issuerDeclaredIn,
  remedyFor,
  theConsolesPalette,
  theOperator,
  TheDoorAttended,
  type Remedy,
} from './door'

/** The console's colours, read off the root element the stylesheet paints. */
function painted(): Record<string, string> {
  const computed = getComputedStyle(document.documentElement)
  return theConsolesPalette((token) => computed.getPropertyValue(token))
}

export function TheDoor({ children }: { children: ReactNode }) {
  const issuer = issuerDeclaredIn(import.meta.env)
  if (issuer === null) {
    return children
  }
  return (
    <ClerkProvider publishableKey={issuer} appearance={{ variables: painted() }}>
      <SignedOut>
        <TheSignIn />
      </SignedOut>
      <SignedIn>
        <Attending>{children}</Attending>
      </SignedIn>
    </ClerkProvider>
  )
}

/** What this instrument is called, above the one control on the page. */
const SIGN_IN_HEADING = 'AgentAudit'

/**
 * The whole console, signed out.
 *
 * One `<main>` and one heading, because this is a screen like the others and a
 * reader arriving with a keyboard or a screen reader should find it the same way.
 * The issuer's component brings its own labelled fields inside that.
 */
function TheSignIn() {
  return (
    <main className="screen sign-in">
      <h1>{SIGN_IN_HEADING}</h1>
      <p>
        This bench attacks endpoints somebody is responsible for, and signs a
        document naming who asked it to. Sign in, and that name is the one your
        session was issued under.
      </p>
      <SignIn routing="virtual" />
    </main>
  )
}

/**
 * The door, attended, with the app behind it.
 *
 * **It is attended as this renders, and not from an effect.** A child's effect runs
 * before its parent's, so a door attached in an effect would be attached after the
 * first screen had already fetched — every arrival would answer `401` and show a
 * sign-in notice to somebody who is signed in. Attaching while this renders puts
 * the token in place before any child exists to ask for one. The call is idempotent
 * (`api/http.ts`), which is what makes it safe to run on every render of this
 * component and under StrictMode's double render.
 *
 * **Nothing un-attends it, and that is not a leak.** This subtree unmounts when the
 * session ends, and the door left behind reads `clerk.session` — which is then
 * `null`, so it holds no token and every request goes bare, which is exactly what a
 * console with nobody signed into it should send.
 *
 * **The refusal is held here rather than at the seam**, because it is a fact about
 * the session and not about the request that met it (`api/http.ts`). It is put away
 * by signing in again — this subtree unmounts the moment the session goes, and the
 * state goes with it — or by hand, for the reading it does not apply to.
 */
function Attending({ children }: { children: ReactNode }) {
  const clerk = useClerk()
  const { user } = useUser()
  const [refusal, setRefusal] = useState<Remedy | null>(null)

  const door = useMemo(
    () => ({
      // The session's own token and not the hook's `getToken`, so that this closure
      // is as current as the client is: a session that has gone holds none.
      token: () => clerk.session?.getToken() ?? Promise.resolve(null),
      refused: (turned: DoorRefusal) => setRefusal(remedyFor(turned)),
    }),
    [clerk],
  )
  attendTheDoor(door)

  if (!user) {
    // The session is established and the user record has not arrived yet. Nothing
    // is drawn rather than a rail with an empty name in it.
    return null
  }
  return (
    <TheDoorAttended
      value={{
        operator: theOperator(user),
        refusal,
        signInAgain: () => void clerk.signOut(),
        letItGo: () => setRefusal(null),
      }}
    >
      {children}
    </TheDoorAttended>
  )
}
