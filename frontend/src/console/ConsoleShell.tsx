/**
 * The console shell: a rail, a top bar, and whichever screen the path names.
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
 */

import { useEffect } from 'react'
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
      <nav className="rail" aria-label="The console">
        <p className="mark">AgentAudit</p>
        <ul>
          {rail.destinations.map((there) => (
            <RailLink there={there} key={there.path} />
          ))}
        </ul>
        {rail.run === null ? null : (
          <>
            <h2 className="rail-heading">The run you are working on</h2>
            <p className="rail-id">
              <code>{rail.run.id}</code>
            </p>
            <ul>
              {rail.run.screens.map((there) => (
                <RailLink there={there} key={there.path} />
              ))}
            </ul>
          </>
        )}
      </nav>

      <div className="console-body">
        <header className="topbar">
          <p className="where">{rail.where}</p>
        </header>
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
