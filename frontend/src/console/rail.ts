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
 * prefix would break every one already sent. There is no path in this module that
 * the app did not already serve before the shell existed.
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
 * **Nothing here carries a figure.** A destination has a name and a line saying
 * what it answers, and no rate, no band, no total and no colour standing in for a
 * verdict. The rail is where a reader would most easily be handed a number that
 * spans two families, so it is built out of a type that has nowhere to put one.
 */

/** Where registration lives, unchanged: the path this app has always served. */
export const REGISTER_PATH = '/register'

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

/** What the top bar says when the console is on its way to a destination. */
export const THE_CONSOLE = 'The operator console'

/** What it says on a path no screen answers, rather than saying nothing at all. */
export const NOT_A_SCREEN = 'Not a screen this console has'

/**
 * One place the rail can send you, and what it answers when you get there.
 *
 * `answers` is a sentence about the screen and never about a result: the rail
 * describes the console, and every figure in this application belongs to the
 * screen that measured it.
 */
export interface Destination {
  /** The path, built here so no component invents one. */
  path: string
  name: string
  /** What this screen answers, for a reader who has not been there yet. */
  answers: string
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
  answers: string
}

/**
 * The console's standing destinations.
 *
 * One, today, and the shell is the reason there can be more: a screen added to
 * this list is a screen the rail names, and nothing else has to change. The three
 * screens the console already had are not all here, because two of them are a
 * run's and a run is not somewhere the console always goes.
 */
const STANDING: readonly (Place & { path: string })[] = [
  {
    path: REGISTER_PATH,
    name: 'Register a target',
    answers:
      'Describe the endpoint, plant the nonce, and make the three attestations ' +
      'one at a time.',
  },
]

/** What a run's two screens are called in the rail. */
const RUN_SCREEN: Place = {
  name: 'The run',
  answers:
    'The approval interrupt while it holds, then where the run has got to, one ' +
    'layer at a time.',
}

const REPORT_SCREEN: Place = {
  name: 'Its report',
  answers:
    'The signed artefact, its three verification results, and one family at a ' +
    'time. A run with no report says so in the bench’s own words.',
}

/** Where a path is, as the few cases the console can be in. */
type Whereabouts =
  | { kind: 'root' }
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
  if (path === '/') {
    return { kind: 'root' }
  }
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
  return { path, name: place.name, answers: place.answers, current }
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
    case 'root':
      return THE_CONSOLE
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
