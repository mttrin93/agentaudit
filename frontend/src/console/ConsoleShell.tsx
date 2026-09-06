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

export function ConsoleShell() {
  const { pathname } = useLocation()
  const onScreen = runInPath(pathname)
  /**
   * Where the skip control puts the keyboard: the wrapper the screen renders into.
   *
   * The wrapper and not the screen's own `<main>`, because the `<main>` belongs to
   * whichever screen is on — it arrives through `<Outlet />` and this component has
   * no handle on it. What is landed on is therefore one element outside it, and the
   * next tab stop is the first control in the reading column either way.
   */
  const theScreen = useRef<HTMLDivElement>(null)

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
        onClick={() => theScreen.current?.focus()}
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
      </nav>

      <div className="console-body" ref={theScreen} tabIndex={-1}>
        <Outlet />
      </div>
    </div>
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
