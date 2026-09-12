/**
 * The console shell: a rail, and whichever screen the path names.
 *
 * It is a layout route rather than a component each screen renders, which is the
 * whole of why nothing that worked yesterday stops working: the register, run and
 * report screens are `<Outlet />` here, unedited, at the paths they have always
 * been served at, with their own view models untouched. The shell adds no state to
 * them and reads none of theirs.
 *
 * **What it adds is a way back.** The run screen is the screen the approval
 * interrupt is answered on, and it can be sat on for an hour; before this there
 * was no way off it that did not lose it, because the only way back was a URL
 * somebody had to have kept. The rail holds the run you are working on for the
 * session, so leaving it is walking away rather than closing it. Nothing about the
 * run itself lives here — the figures are still in `sessionStorage` under the run's
 * own id and the position still comes from `GET /runs/{id}` on every poll, so a
 * screen re-entered is a screen that asks the bench again.
 *
 * **The rail is a nav and the screen is a main.** Each screen brings its own
 * `<main className="screen">`, which is what keeps the prose in one reading column
 * inside the frame, so this file contributes a wrapper and no second `main`.
 *
 * **The operator is at the foot of the rail, and so is the way out.** The shell is
 * where the door's two facts belong, for the reason the shell is the boundary at
 * all: they are true on every screen and no screen owns them. The name printed is
 * the display name the issuer holds and not the subject the bench records — the two
 * are pulled apart in `door.ts`, and which one a *document* carries is ADR-0123's.
 * Where this console has no issuer there is nothing at the foot of the rail, which
 * is the clone the repository has always had.
 *
 * **A refusal at the bench's door is shown here and not on the screen that met it.**
 * Being signed out is a fact about the session; a screen's own refusal is about the
 * request it made. So it sits above the screen, once, instead of every area module
 * growing an outcome for *not signed in* — and the screen underneath keeps whatever
 * it was showing, which is what lets an expiry mid-run be an interruption rather
 * than a lost run.
 *
 * **And it is skippable.** The rail is seven destinations before the reading column
 * on every screen, which a keyboard reader pays for every time they arrive at a
 * screen they have already chosen. The control that skips it is the first thing in
 * the document, drawn only while it has the keyboard, and `e2e/keyboard.spec.ts`
 * holds all three claims — first stop, past the rail, and a rail worth skipping.
 */

import { useEffect, useRef } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import {
  railView,
  rememberTheRun,
  runInPath,
  theRunLastInView,
  type Destination,
} from './rail'
import { RailGlyph } from './railIcons'
import { useOperator, type AtTheDoor, type Remedy } from './door'

export function ConsoleShell() {
  const { pathname } = useLocation()
  const onScreen = runInPath(pathname)
  /**
   * The wrapper the screen renders into, which is where the skip control lands.
   *
   * The wrapper and not the screen's own `<main>`: the `<main>` belongs to whichever
   * screen is on — it arrives through `<Outlet />` and this component has no handle on
   * it — so what is landed on is one element outside it. The next tab stop is the
   * first control in the reading column either way.
   */
  const wrapper = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Written as you arrive, so the way back exists before you decide to leave.
    if (onScreen !== null) {
      rememberTheRun(sessionStorage, onScreen)
    }
  }, [onScreen])

  /*
   * The remembered run is read here rather than held in state, because it is not
   * this component's state: it changes when the path changes, and the path
   * changing is already a render. State would need a `setState` inside the effect
   * that writes it, which is a second render for a value the path already knows.
   */
  const remembered = onScreen ?? theRunLastInView(sessionStorage)
  const rail = railView(pathname, remembered)
  const door = useOperator()
  return (
    <div className="console">
      {/*
        The rail, skipped.

        **A button and not an `<a href="#…">`, and the router is why.** Every screen
        in this app lives in the fragment (`main.tsx`), so a link to a fragment id is
        a link to a route that does not exist: the browser would set the hash, the
        `HashRouter` would read it as a path, and the skip control would navigate off
        the screen it was supposed to take the reader into. Moving the focus in code
        is the only way to skip a rail in a hash-routed app.

        It is drawn only while it has the keyboard — `.skip` in `index.css` — because
        a control whose whole subject is the tab order has nothing to say to a reader
        using a pointer, and the first thing on every screen should be the screen.
      */}
      <button
        type="button"
        className="skip"
        onClick={() => wrapper.current?.focus()}
      >
        Skip to the screen
      </button>

      <nav className="rail" aria-label="The console">
        <p className="mark">
          Agent<span>Audit</span>
        </p>
        <ul>
          {rail.destinations.map((there) => (
            <RailLink there={there} key={there.path} />
          ))}
        </ul>
        {rail.run === null ? null : (
          <>
            <h2 className="rail-heading">The run you are working on</h2>
            <ul>
              {rail.run.screens.map((there) => (
                <RailLink there={there} key={there.path} />
              ))}
            </ul>
          </>
        )}

        {door === null ? null : (
          <div className="rail-operator">
            <h2 className="rail-heading">Signed in</h2>
            <p className="operator-name">{door.operator.named}</p>
            <button type="button" className="quiet" onClick={door.signInAgain}>
              Sign out
            </button>
          </div>
        )}
      </nav>

      <div className="console-body" ref={wrapper} tabIndex={-1}>
        {door?.refusal ? (
          <TheDoorsRefusal remedy={door.refusal} door={door} />
        ) : null}
        <Outlet />
      </div>
    </div>
  )
}

/**
 * What the bench's door said, and the one thing there is to do about it.
 *
 * `role="alert"` and not a polite region: the operator pressed something and the
 * bench turned the request away, and the screen underneath is unchanged — nothing
 * else on the page says the press was answered at all.
 *
 * **The verifier's sentence is printed whole**, which is the same rule the identity
 * sentence in a report is under (ADR-0123): it is the bench's account of why, it
 * names the cause, and a console with its own words in that place would be
 * answering for a refusal it did not make.
 *
 * The way back in is offered for one of the two readings and not the other, and
 * `remedyFor` in `door.ts` is where that is decided — signing in again against an
 * issuer the bench cannot reach fails in exactly the same way.
 */
function TheDoorsRefusal({ remedy, door }: { remedy: Remedy; door: AtTheDoor }) {
  return (
    <section className="refusal" role="alert">
      <h2>{remedy.heading}</h2>
      <p>{remedy.statement}</p>
      <p className="aside">
        {remedy.signInAgain ? (
          <button type="button" onClick={door.signInAgain}>
            Sign in again
          </button>
        ) : null}
        <button type="button" className="quiet" onClick={door.letItGo}>
          Put this away
        </button>
      </p>
    </section>
  )
}

/**
 * One destination, marked when it is the one you are standing on.
 *
 * The glyph is inside the `<Link>` rather than beside it, so the whole of what a
 * reader points at is the link — and it is decorative, so this stays a link whose
 * accessible name is exactly the destination's name.
 */
function RailLink({ there }: { there: Destination }) {
  return (
    <li className={there.current ? 'current' : undefined}>
      <Link to={there.path} aria-current={there.current ? 'page' : undefined}>
        <RailGlyph icon={there.icon} />
        {there.name}
      </Link>
    </li>
  )
}
