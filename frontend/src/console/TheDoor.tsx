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
 * issuer to reconcile and no redirect route to add.
 *
 * **Where the sign-in is drawn depends on the fragment, and that is the issuer's
 * doing rather than a choice made here.** Arriving at `/` or `/#/`, the card below
 * renders in place, in this console's colours. Arriving at a screen —
 * `/#/runs/<id>`, `/#/register` — the issuer's client decides it is not mounted at
 * its own sign-in URL and sends the browser to the hosted portal, which comes back
 * to the whole URL it left, fragment included. Measured in a browser on all four
 * paths, not assumed.
 *
 * Declaring `signInUrl="/"` on the provider does stop the trip out — and the
 * redirect it does instead is to `/#/`, with the screen the operator asked for
 * dropped from the `redirect_url` it builds. Losing the run somebody followed a
 * link to is worse than a page in somebody else's palette, so it is not declared.
 * Either way no screen of the console renders while nobody is signed in, and the
 * fragment survives the round trip, which is what an expiry mid-run needs.
 *
 * **The reasoning is in `door.ts` and the wiring is here** — see that file's own
 * first paragraph for why. What is left here is a provider, a memo and two pieces
 * of markup.
 *
 * A build that declares no key mounts none of this and renders `children` as they
 * are, which `door.ts:issuerDeclaredIn` says what to make of.
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

/**
 * How the issuer's components are dressed: this console's colours, and one heading
 * of theirs taken off the page.
 *
 * The heading is removed rather than restyled because of what it says. It is the
 * application's name as the issuer's dashboard holds it, over a screen that already
 * carries an `<h1>` naming the instrument — two top-level headings on one screen,
 * the second of them a name configured somewhere this repository cannot see. The
 * line under it still says what the card is for, in a verb.
 */
function dressed() {
  return {
    variables: painted(),
    elements: { headerTitle: { display: 'none' } },
  }
}

/** The console's colours, read off the root element the stylesheet paints. */
function painted(): Record<string, string> {
  const computed = getComputedStyle(document.documentElement)
  return theConsolesPalette((token) => computed.getPropertyValue(token))
}

export function TheDoor({ children }: { children: ReactNode }) {
  /*
   * Once. It reads the computed style of the root element, and a fresh object on
   * every render is the issuer's components re-applying an appearance that cannot
   * have changed: the stylesheet is a build artefact and this console has one
   * palette.
   */
  const appearance = useMemo(() => dressed(), [])
  const issuer = issuerDeclaredIn(import.meta.env)
  if (issuer === null) {
    return children
  }
  return (
    <ClerkProvider publishableKey={issuer} appearance={appearance}>
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
        // Back to where they were standing, hash and all. The default is the
        // issuer's `afterSignOutUrl`, which is `/` — and `/` is the landing
        // screen, so signing in again on the run screen would come back to a
        // console that had lost the run. That is the interruption story 8 asks
        // for read backwards.
        signInAgain: () => void clerk.signOut({ redirectUrl: window.location.href }),
        letItGo: () => setRefusal(null),
      }}
    >
      {children}
    </TheDoorAttended>
  )
}
