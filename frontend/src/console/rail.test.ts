/**
 * What the shell must not change, and what the rail must say.
 *
 * The shell is a prefactor: three screens that worked before it existed have to
 * work after it, at the same paths, with the same view models behind them. Two of
 * its claims are a person's to check by looking — whether the prose still sets in
 * one reading column, whether the rail is usable at a narrow width — and this file
 * asserts neither. What is asserted is what a person cannot check faster than a
 * test can: that the paths are the literal paths a report link already sent to a
 * customer points at; that the rail names exactly one place as the one you are
 * standing on, including on the paths where the answer is none of them; and that
 * the run you were watching is still offered after you have walked away from it,
 * which is the difference between leaving a screen and losing it.
 *
 * The rail is also where a reader would most easily be handed a number that spans
 * two families, so the last test scans the whole view for a figure of any kind.
 * There is deliberately nowhere in `Rail` to put one.
 */

import { describe, expect, it } from 'vitest'

import {
  NOT_A_SCREEN,
  REGISTER_PATH,
  REPORT_PATTERN,
  RUN_PATTERN,
  THE_CONSOLE,
  railView,
  rememberTheRun,
  reportPath,
  runInPath,
  runPath,
  theRunLastInView,
  type Destination,
  type Rail,
  type RailStore,
} from './rail'

/** A `sessionStorage` that runs in node, which is where these tests run. */
function aStore(): RailStore {
  const held = new Map<string, string>()
  return {
    getItem: (key) => held.get(key) ?? null,
    setItem: (key, value) => {
      held.set(key, value)
    },
  }
}

/** Every place the rail offers, on one path: destinations and a run's screens. */
function everywhere(rail: Rail): Destination[] {
  return [...rail.destinations, ...(rail.run?.screens ?? [])]
}

describe('the paths the shell may not move', () => {
  it('is the three paths this app served before there was a shell', () => {
    // A report is a link somebody sent to a customer last month. `App.tsx` routes
    // on these constants, so a prefix invented for the shell fails here first.
    expect(REGISTER_PATH).toBe('/register')
    expect(RUN_PATTERN).toBe('/runs/:runId')
    expect(REPORT_PATTERN).toBe('/runs/:runId/report')
    expect(runPath('run-1')).toBe('/runs/run-1')
    expect(reportPath('run-1')).toBe('/runs/run-1/report')
  })

  it('leads back to the run it was built from, whatever its id looks like', () => {
    const awkward = 'run/1 2%'
    expect(runInPath(runPath(awkward))).toBe(awkward)
    expect(runInPath(reportPath(awkward))).toBe(awkward)
    const rail = railView(reportPath(awkward), null)
    expect(rail.run?.id).toBe(awkward)
    expect(rail.run?.screens.map((screen) => runInPath(screen.path))).toEqual([
      awkward,
      awkward,
    ])
  })
})

describe('the rail names where you are', () => {
  it('lists every destination and marks the one you are standing on', () => {
    const offered = railView('/nowhere-at-all', null).destinations
    expect(offered.length).toBeGreaterThan(0)
    for (const there of offered) {
      const rail = railView(there.path, null)
      expect(rail.destinations.map((d) => d.path)).toEqual(
        offered.map((d) => d.path),
      )
      expect(rail.destinations.filter((d) => d.current)).toEqual([
        { ...there, current: true },
      ])
      expect(rail.where).toBe(there.name)
    }
  })

  it('still lists them on a path no screen answers, and marks none', () => {
    const nowhere = railView('/nowhere-at-all', null)
    expect(nowhere.destinations.length).toBeGreaterThan(0)
    expect(nowhere.destinations.some((d) => d.current)).toBe(false)
    expect(nowhere.where).toBe(NOT_A_SCREEN)
    // The root is on its way somewhere rather than nowhere, so it does not say
    // that the console has no such screen while it redirects.
    const root = railView('/', null)
    expect(root.destinations.some((d) => d.current)).toBe(false)
    expect(root.where).toBe(THE_CONSOLE)
  })

  it('marks one place and never two, wherever you are', () => {
    const paths = [
      '/',
      REGISTER_PATH,
      `${REGISTER_PATH}/`,
      runPath('run-1'),
      reportPath('run-1'),
      '/nowhere-at-all',
    ]
    for (const path of paths) {
      const marked = everywhere(railView(path, 'run-1')).filter((d) => d.current)
      expect(marked.length).toBeLessThan(2)
      expect(railView(path, 'run-1').where).not.toBe('')
    }
  })
})

describe('a run is somewhere you can leave and come back to', () => {
  it('keeps the run reachable from its own report, and the report from it', () => {
    const onTheRun = railView(runPath('run-1'), null)
    expect(onTheRun.run?.onScreen).toBe(true)
    expect(onTheRun.run?.screens.map((s) => [s.path, s.current])).toEqual([
      ['/runs/run-1', true],
      ['/runs/run-1/report', false],
    ])
    expect(onTheRun.where).toBe('Run run-1')

    const onTheReport = railView(reportPath('run-1'), null)
    expect(onTheReport.run?.screens.map((s) => [s.path, s.current])).toEqual([
      ['/runs/run-1', false],
      ['/runs/run-1/report', true],
    ])
    expect(onTheReport.where).toBe('Run run-1 — its report')
  })

  it('still offers the run you were watching after you have left it', () => {
    // The run screen is the screen an approval interrupt is answered on, and it
    // can be sat on for an hour. A rail that dropped the run the moment you
    // walked to the register screen would be a rail you cannot walk back on.
    const away = railView(REGISTER_PATH, 'run-1')
    expect(away.run?.id).toBe('run-1')
    expect(away.run?.onScreen).toBe(false)
    expect(away.run?.screens.map((s) => s.path)).toEqual([
      '/runs/run-1',
      '/runs/run-1/report',
    ])
    expect(away.run?.screens.some((s) => s.current)).toBe(false)
  })

  it('prefers the run on screen to the run it remembers', () => {
    const rail = railView(runPath('run-2'), 'run-1')
    expect(rail.run?.id).toBe('run-2')
    expect(rail.run?.screens.map((s) => s.path)).toEqual([
      '/runs/run-2',
      '/runs/run-2/report',
    ])
  })

  it('offers no run at all when this app has never seen one', () => {
    const store = aStore()
    expect(theRunLastInView(store)).toBeNull()
    expect(railView(REGISTER_PATH, theRunLastInView(store))).toMatchObject({
      run: null,
    })
    rememberTheRun(store, 'run-1')
    expect(theRunLastInView(store)).toBe('run-1')
    // A run with no id is not a run: linking to it would be a rail offering a
    // screen that cannot load, which is worse than a rail with no run in it.
    rememberTheRun(store, '')
    expect(theRunLastInView(store)).toBeNull()
    expect(railView(REGISTER_PATH, theRunLastInView(store))).toMatchObject({
      run: null,
    })
  })
})

describe('the rail carries no figure', () => {
  it('has no number in it anywhere, and no digit in its own prose', () => {
    // A rate, a total, a count of runs: a rail is where a reader would most
    // easily be handed one, and a figure spanning two families is the thing this
    // application refuses to print (ADR-0005). Every place the rail offers is a
    // name and a sentence about a screen.
    const rail = railView(reportPath('run-1'), 'run-1')
    const numbers = JSON.stringify(rail, (_key, value: unknown) =>
      typeof value === 'number' ? 'A FIGURE' : value,
    )
    expect(numbers).not.toContain('A FIGURE')
    for (const place of everywhere(rail)) {
      expect(place.name).not.toMatch(/\d/)
      expect(place.answers).not.toMatch(/\d/)
    }
  })
})
