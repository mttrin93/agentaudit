/**
 * The rail's eight glyphs, drawn here and named in `rail.ts`.
 *
 * The view model says *which* glyph a destination wants and this file is the only
 * place that knows what one looks like. That split is the point: `rail.ts` is a
 * module a node test reads with no DOM, and a `<path d="…">` in it would be markup
 * in the one file the console's paths are declared in.
 *
 * **The `switch` is exhaustive and that is the guard.** `RailIcon` is a closed
 * union, every arm returns, and there is no `default` — so a destination naming a
 * glyph nobody drew fails `tsc -b` rather than rendering an empty box, and a glyph
 * added to the union with no drawing fails in the same place. A path-keyed lookup
 * would have been a `Record<string, …>` that a renamed path silently misses; a
 * union the compiler counts cannot be missed.
 *
 * **Hand-written SVG, and no fourth dependency.** This app has three — `react`,
 * `react-dom`, `react-router-dom` — and eight 16px line drawings are not worth a
 * fourth that would arrive with several hundred it does not draw. Everything is
 * stroked in `currentColor` at one weight, which is what makes the rail's existing
 * three-way current-marking — the weight, the ink, the rule down the side — reach
 * the glyph for free: `.rail li.current a` sets the colour and the drawing follows.
 *
 * **Every glyph is decorative.** `aria-hidden` and `focusable="false"`, with no
 * title and no label: the name beside it is already the link's accessible text, and
 * a glyph that announced itself would make every destination say its name twice.
 */

import type { ReactElement } from 'react'

import type { RailIcon } from './rail'

/**
 * The sheet `artefacts` and `report` are both drawn on.
 *
 * Shared rather than written twice, because the seal is meant to be the only
 * difference between those two glyphs and a page that drifted by a tenth of a unit
 * would make it two differences.
 */
const PAGE = <rect x="3.5" y="1.75" width="9" height="12.5" rx="1" />

/** One destination's glyph, at the size and baseline the stylesheet sets. */
export function RailGlyph({ icon }: { icon: RailIcon }) {
  return (
    <svg
      className="glyph"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {drawing(icon)}
    </svg>
  )
}

/**
 * What each glyph is, in strokes.
 *
 * No `default` arm, deliberately: with every member of the union returning, the
 * end of this function is unreachable, and a member that stops returning makes it
 * reachable — which is the error. Adding an arm is the only way to add a glyph.
 */
function drawing(icon: RailIcon): ReactElement {
  switch (icon) {
    // A flask: this is a test bench, and the bench is what the landing screen is
    // about.
    case 'bench':
      return (
        <>
          <path d="M5.9 2h4.2" />
          <path d="M6.5 2v3.6L3.4 14h9.2L9.5 5.6V2" />
          <path d="M4.8 10.4h6.4" />
        </>
      )
    // A target's rings, for the screen where one is registered: one circle inside
    // another, and the dot they are both centred on.
    case 'target':
      return (
        <>
          <circle cx="8" cy="8" r="5.75" />
          <circle cx="8" cy="8" r="2.5" />
          <circle cx="8" cy="8" r="0.85" fill="currentColor" stroke="none" />
        </>
      )
    // A barrier: two posts, a bar across them, and the stripes that say it is
    // down. The stop before the bench is trusted.
    case 'gate':
      return (
        <>
          <rect x="1.4" y="5.6" width="13.2" height="2.9" rx="0.7" />
          <path d="M4 8.5v5.9M12 8.5v5.9" />
          <path d="M5.4 8.5 8 5.6M9 8.5 11.6 5.6" />
        </>
      )
    // A branching path with a node on each end: a route, and the queue of them is
    // the routes the attacker found that the fixed suite did not. The fork is the
    // whole of the glyph — what a pending route *is*, is a way through that nobody
    // wrote down.
    case 'routes':
      return (
        <>
          <path d="M2.6 13.4 7 9l0-3.4" />
          <path d="M7 5.6 10.4 2.2" />
          <path d="M7 9h4.2l2.2 2.2" />
          <circle cx="11.4" cy="1.6" r="1.4" />
          <circle cx="14" cy="12.2" r="1.4" />
          <circle cx="1.9" cy="14.1" r="1.4" />
        </>
      )
    // A page with a seal in the lower corner: the documents this bench has signed.
    // The seal is the whole difference from `report`.
    case 'artefacts':
      return (
        <>
          {PAGE}
          <path d="M6 5h4M6 7.4h2.4" />
          <circle cx="9.7" cy="10.9" r="1.9" />
          <path d="M8.45 12.3 7.85 14l1.85-.8 1.85.8-.6-1.7" />
        </>
      )
    // A gear, for the screen that states what the bench is set to. Argued about in
    // #104 and kept: it is the glyph every reader knows, and the screen's own prose
    // is where "it changes none of them" is said.
    case 'settings':
      return (
        <>
          <circle cx="8" cy="8" r="4.75" />
          <circle cx="8" cy="8" r="1.75" />
          <path d="M8 3.25V1.5M8 12.75v1.75M3.25 8H1.5M12.75 8h1.75" />
          <path d="M11.36 4.64 12.6 3.4M4.64 11.36 3.4 12.6M4.64 4.64 3.4 3.4M11.36 11.36 12.6 12.6" />
        </>
      )
    // A pulse line: the run, which is the one screen in this console that moves
    // while you sit on it.
    case 'run':
      return <path d="M1.5 8.5h2.9l2-4.6 2.6 8.2 2-3.6h2.5" />
    // A page with ruled lines and no seal: a run's report, read rather than sent.
    case 'report':
      return (
        <>
          {PAGE}
          <path d="M6 5h4M6 8h4M6 11h2.4" />
        </>
      )
  }
}
