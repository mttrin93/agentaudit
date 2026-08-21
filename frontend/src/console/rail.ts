/**
 * The console's rail: its destinations, and which one you are standing on.
 *
 * The three screens this app already has were reachable only by knowing their
 * paths, and one of them — the run screen — is a screen somebody sits on for the
 * hour the approval interrupt waits. So the shell around them needs three things
 * from this module and nothing else: the list of places the console goes, the
 * answer to *where am I*, and one run held on to for as long as the tab is open.
 * The first two are computed from the path alone, which is what makes them
 * testable in node with no DOM and no router: a rail that had to be rendered to
 * be checked would be a rail nobody checks.
 *
 * **The paths are declared here and nowhere else.** `App.tsx` routes on these
 * exact constants, and `rail.test.ts` asserts their literal values, because a
 * report is a link an engineer sends to a customer and a shell that grew a URL
 * prefix would break every one already sent. No path in this module has ever moved:
 * the three the app served before the shell existed are the three it serves now, and
 * the root is the one addition — a screen where there used to be a redirect.
 *
 * **The run in view is a group, not a destination.** `/register` is somewhere the
 * console always goes; a run is somewhere it goes only because you have one. So a
 * run appears in the rail with both of its screens — itself and its report — for
 * as long as this app can name it, which is how you get from the report back to
 * the run you were watching. It is remembered for the session rather than only
 * for the path, because *navigated away from* and *returned to* are the same
 * requirement read twice, and a rail that dropped the run the moment you left it
 * would satisfy only the first half. Remembering one run is not a list of runs:
 * this module holds the run you are working on, and never a count of them.
 *
 * **Nothing here carries a figure.** A destination has a name, a path and the name
 * of a glyph, and no rate, no band, no total and no colour standing in for a
 * verdict. The rail is where a reader would most easily be handed a number that
 * spans two families, so it is built out of a type that has nowhere to put one.
 *
 * **And it does not explain itself.** Every destination used to carry a sentence
 * about what its screen answers; a reader already standing in the console does not
 * need the console described to them in the margin, and the narrow window had been
 * hiding those sentences all along. The field is gone rather than unrendered, so
 * nothing can put the prose back.
 *
 * **The glyph is named here and drawn elsewhere.** `icon` is a closed union, so
 * this module says *which* drawing a destination wants and `railIcons.tsx` is the
 * only place that knows what one looks like. There is no SVG in here for the same
 * reason there is no component: this file is read by a node test with no DOM, and
 * the union is what makes a destination naming an undrawn glyph a `tsc` error
 * rather than an empty box on the page.
 */

/**
 * The console's own front door, and the only path here the app did not serve as a
 * screen before: `/` was a redirect to registration, and it is now the landing
 * screen that says what this instrument is and which gate run it last passed.
 */
export const CONSOLE_PATH = '/'

/** Where registration lives, unchanged: the path this app has always served. */
export const REGISTER_PATH = '/register'

/**
 * The operator's gate screen: the declared rule, the last outcome, the command.
 *
 * `/gate` and not `/bench/gate`, for two reasons. `/bench` is the API's own prefix
 * for the routes whose subject is the instrument, and a screen path that shadowed it
 * would be a document request the dev server proxies to the bench. And the console
 * is deliberately not split into a target-facing and a bench-facing route tree: with
 * no gate verdict anywhere in the application there is nothing for a prefix to keep
 * apart, so the distinction is carried by what the screens say (spec §75).
 */
export const GATE_PATH = '/gate'

/**
 * Where the signed artefacts are listed: the documents an engineer sends out.
 *
 * The same path the API lists them at, on the same terms `/runs` already is: the
 * screens are behind a `#` and no document request ever carries one, so the dev
 * server can proxy the prefix wholesale without shadowing a screen (`main.tsx`,
 * `vite.config.ts`). It is not under `/bench`, because an artefact is a document
 * about somebody's target and `/bench` is the prefix whose subject is the
 * instrument (ADR-0018).
 */
export const ARTEFACTS_PATH = '/artefacts'

/**
 * Where the bench states what it is configured to do: keys, library, models, limits.
 *
 * `/settings` and not `/bench/settings`, for the reason the gate screen is at
 * `/gate`: `/bench` is the API's own prefix for the routes whose subject is the
 * instrument, and a screen path that shadowed it would be a document request the dev
 * server proxies to the bench.
 *
 * `/settings` and deliberately not `/configure`, which is the distinction still
 * worth stating now that the rail's label is the plain word: nothing on this screen
 * changes a setting, and there is no route on this bench that would take one. The
 * screen states what the bench is set to and offers no control that alters it —
 * rotation stays in the environment and configuration stays on the command line
 * (ADR-0020) — so a path promising otherwise would be a promise no route here can
 * keep.
 */
export const SETTINGS_PATH = '/settings'

/** The run screen's route, as `App.tsx` declares it. */
export const RUN_PATTERN = '/runs/:runId'

/** The report screen's route. A link somebody has already sent points here. */
export const REPORT_PATTERN = '/runs/:runId/report'

/** One run's screen, at the path the bench's own run id makes. */
export function runPath(runId: string): string {
  return `/runs/${encodeURIComponent(runId)}`
}

/** One run's report, at the path a recipient may already hold. */
export function reportPath(runId: string): string {
  return `${runPath(runId)}/report`
}

/**
 * What the top bar falls back to when a standing destination cannot be named.
 *
 * It used to be what the root said while it redirected. The root is a screen now,
 * so it is named like every other destination and this is the last resort rather
 * than a state the console is routinely in.
 */
export const THE_CONSOLE = 'The operator console'

/** What it says on a path no screen answers, rather than saying nothing at all. */
export const NOT_A_SCREEN = 'Not a screen this console has'

/**
 * Which glyph a destination wants, as a closed set of names.
 *
 * A name and never a drawing: `railIcons.tsx` switches over this union with no
 * `default`, so the seven members and the seven drawings are counted against each
 * other by the compiler. Widening this without drawing the new one does not
 * compile, which is the whole of the guard — and it is a union rather than a path
 * key so that moving a path can never quietly detach a glyph.
 */
export type RailIcon =
  | 'bench'
  | 'target'
  | 'gate'
  | 'artefacts'
  | 'settings'
  | 'run'
  | 'report'

/**
 * One place the rail can send you.
 *
 * A name, a path and a glyph's name, and nothing that describes the screen: the
 * rail is what a reader navigates by, and every sentence about a screen belongs on
 * the screen.
 */
export interface Destination {
  /** The path, built here so no component invents one. */
  path: string
  name: string
  /** Which glyph goes to the left of the name. Required: every place has one. */
  icon: RailIcon
  /** Whether this is where you are standing now. */
  current: boolean
}

/** The run this rail can reach, with both of its screens. */
export interface RunInView {
  /** The run's id as the bench issued it, decoded out of the path. */
  id: string
  /** The run and its report, in that order, the one you are on marked. */
  screens: Destination[]
  /** Whether this run is the one on screen, or one the rail is holding open. */
  onScreen: boolean
}

/** Everything the shell needs to draw the rail and the top bar. */
export interface Rail {
  /** The console's standing destinations, at most one of them current. */
  destinations: Destination[]
  /** The run you are working on, or `null` when this app knows of none. */
  run: RunInView | null
  /** Where you are, as the top bar's own line. Never empty. */
  where: string
}

/**
 * What a place is called, without its path.
 *
 * A standing destination's path is fixed and a run screen's is made from the
 * run's id, so the path is not part of this: nothing here can carry a pattern
 * like `/runs/:runId` into a link.
 */
interface Place {
  name: string
  icon: RailIcon
}

/**
 * What the landing screen is called, wherever it is named.
 *
 * Exported because two other screens link to it in their own prose, and a link
 * whose text is a literal is a second copy of a name — #103 and #104 moved this
 * one and left both of those saying what the rail had stopped saying. The name
 * lives here once, beside the path, so a rename reaches every sentence that uses
 * it and none can be missed.
 */
export const THE_BENCH = 'The bench'

/**
 * The console's standing destinations.
 *
 * Five, today, and the shell is the reason there can be more: a screen added to
 * this list is a screen the rail names, and nothing else has to change. The three
 * screens the console already had are not all here, because two of them are a
 * run's and a run is not somewhere the console always goes.
 *
 * The landing screen is first because it is what the root serves and what an
 * engineer opening a deployed bench sees before it asks them for an endpoint.
 */
const STANDING: readonly (Place & { path: string })[] = [
  { path: CONSOLE_PATH, name: THE_BENCH, icon: 'bench' },
  { path: REGISTER_PATH, name: 'Register a target', icon: 'target' },
  { path: GATE_PATH, name: 'The gate', icon: 'gate' },
  { path: ARTEFACTS_PATH, name: 'Signed artefacts', icon: 'artefacts' },
  { path: SETTINGS_PATH, name: 'Settings', icon: 'settings' },
]

/** What a run's two screens are called in the rail. */
const RUN_SCREEN: Place = { name: 'The run', icon: 'run' }

const REPORT_SCREEN: Place = { name: 'Its report', icon: 'report' }

/**
 * Where a path is, as the few cases the console can be in.
 *
 * There is no `root` case any more. It existed so that the redirect at `/` did not
 * flash *no such screen* on its way to registration; `/` is a standing destination
 * now, so the root is answered by the same branch as every other screen.
 */
type Whereabouts =
  | { kind: 'standing'; path: string }
  | { kind: 'run'; id: string }
  | { kind: 'report'; id: string }
  | { kind: 'elsewhere' }

const RUN_PATH = /^\/runs\/([^/]+)$/
const REPORT_PATH = /^\/runs\/([^/]+)\/report$/

/** A trailing slash is the same screen, so it is not a different answer. */
function tidy(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, '')
  return trimmed === '' ? '/' : trimmed
}

/**
 * The run's id out of the path, decoded.
 *
 * A segment that is not valid percent-encoding is carried through as it stands
 * rather than thrown over: the bench decides what a run id looks like, and a rail
 * that raised on an unfamiliar one would take the whole shell down with it.
 */
function idIn(segment: string): string {
  try {
    return decodeURIComponent(segment)
  } catch {
    return segment
  }
}

function whereabouts(pathname: string): Whereabouts {
  const path = tidy(pathname)
  const standing = STANDING.find((place) => place.path === path)
  if (standing) {
    return { kind: 'standing', path: standing.path }
  }
  const report = REPORT_PATH.exec(path)
  if (report) {
    return { kind: 'report', id: idIn(report[1]) }
  }
  const run = RUN_PATH.exec(path)
  if (run) {
    return { kind: 'run', id: idIn(run[1]) }
  }
  return { kind: 'elsewhere' }
}

/** The run this path is about, or `null` when it is about no run. */
export function runInPath(pathname: string): string | null {
  const at = whereabouts(pathname)
  return at.kind === 'run' || at.kind === 'report' ? at.id : null
}

function destination(place: Place, path: string, current: boolean): Destination {
  return { path, name: place.name, icon: place.icon, current }
}

/** The run's two screens, with the one you are on marked and both reachable. */
function screensOf(runId: string, at: Whereabouts): Destination[] {
  const here =
    (at.kind === 'run' || at.kind === 'report') && at.id === runId
      ? at.kind
      : null
  return [
    destination(RUN_SCREEN, runPath(runId), here === 'run'),
    destination(REPORT_SCREEN, reportPath(runId), here === 'report'),
  ]
}

/**
 * The rail for one path, plus the run this app is holding open.
 *
 * `remembered` is the run last in view — passed in rather than read here, so that
 * this function stays a function of its arguments. The path wins when it names a
 * run, because what is on screen is never something the rail has to remember.
 */
export function railView(pathname: string, remembered: string | null): Rail {
  const at = whereabouts(pathname)
  const destinations = STANDING.map((place) =>
    destination(
      place,
      place.path,
      at.kind === 'standing' && at.path === place.path,
    ),
  )
  const inPath = runInPath(pathname)
  const runId = inPath ?? remembered
  const run: RunInView | null =
    runId === null
      ? null
      : { id: runId, screens: screensOf(runId, at), onScreen: inPath !== null }
  return { destinations, run, where: whereYouAre(at, destinations) }
}

/** The top bar's line: the name of the place you are standing on. */
function whereYouAre(at: Whereabouts, destinations: Destination[]): string {
  switch (at.kind) {
    case 'standing':
      return destinations.find((there) => there.current)?.name ?? THE_CONSOLE
    case 'run':
      return `Run ${at.id}`
    case 'report':
      return `Run ${at.id} — its report`
    case 'elsewhere':
      return NOT_A_SCREEN
  }
}

/**
 * The little of `Storage` this module uses, so the memory can be tested.
 *
 * Two methods rather than the DOM's `Storage`, because these tests run in node
 * where there is no `sessionStorage`. The shell passes the real one; a test passes
 * a map. Session-scoped on purpose: the run you were watching is a fact about this
 * tab, and a run remembered across a browser restart would be a list of runs
 * assembled by the wrong side of the application.
 */
export interface RailStore {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

const REMEMBERED_UNDER = 'agentaudit.run-in-view'

/** Hold on to the run whose screen is being looked at. */
export function rememberTheRun(store: RailStore, runId: string): void {
  store.setItem(REMEMBERED_UNDER, runId)
}

/**
 * The run last in view, or `null` when this app has not seen one.
 *
 * `null` rather than an empty string, and an empty value reads as `null`: a rail
 * offering a run with no id would be a link to a screen that cannot load, which is
 * worse than a rail with no run in it.
 */
export function theRunLastInView(store: RailStore): string | null {
  return store.getItem(REMEMBERED_UNDER) || null
}
