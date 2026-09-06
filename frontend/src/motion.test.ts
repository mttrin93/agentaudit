/// <reference types="node" />
/**
 * What this stylesheet is allowed to move, and the promise that it can be stopped.
 *
 * There was no `transition` and no `@keyframes` in `index.css` at all until #122, and
 * the absence was only *partly* worth closing: ADR-0081 draws the line at motion that
 * reports a state change — a hover, a focus, a control going dead — and refuses the
 * motion that announces a screen or asks for attention. This file is the machine-
 * readable half of that decision, and it exists because the failure mode it guards
 * against is one nobody sees on their own machine: **an animation a reader cannot turn
 * off.**
 *
 * It reads the stylesheet as text rather than through a DOM. There is no jsdom here by
 * the spec's own choice (`vite.config.ts`), and none is wanted: what is being asserted
 * is what the file *declares*, and a browser would answer only for the rules that
 * matched the one page it had loaded.
 *
 * **It reads the file rather than importing it, which is the one place this file
 * departs from `settings.test.ts`.** That test reads a component's source through
 * Vite's `?raw`, and the same import here comes back as the empty string: the test
 * runner stubs stylesheets out, so a `.css` import is nothing at all in node whatever
 * query is on the end of it — and an empty string passes two of the three assertions
 * below in silence. `readFileSync` off `import.meta.url` is the version that cannot
 * quietly answer *nothing*, and the reference above is how the one node import in
 * `src/` gets its types without opening node's library to the app.
 */

import { readFileSync } from 'node:fs'

import { expect, test } from 'vitest'

const STYLESHEET = readFileSync(new URL('./index.css', import.meta.url), 'utf8')

/**
 * The properties every `transition` and `transition-property` in the file names.
 *
 * A `transition` shorthand is a comma-separated list whose first token is the
 * property, so the property is the first word of each part. `transition-property` is
 * the same list with the durations left off, and the first word of each part is still
 * the answer.
 */
function whatIsTransitioned(css: string): readonly string[] {
  const named: string[] = []
  for (const [, value] of css.matchAll(/transition(?:-property)?\s*:([^;}]+)/g)) {
    for (const part of value.split(',')) {
      const first = part.trim().split(/\s+/)[0]
      if (first !== undefined && first !== '') {
        named.push(first)
      }
    }
  }
  return named
}

/** The body of the `prefers-reduced-motion: reduce` block, or `''` where there is none. */
function theReducedMotionBlock(css: string): string {
  const opened = css.search(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{/)
  if (opened === -1) {
    return ''
  }
  const from = css.indexOf('{', opened)
  let depth = 0
  for (let at = from; at < css.length; at += 1) {
    if (css[at] === '{') {
      depth += 1
    } else if (css[at] === '}') {
      depth -= 1
      if (depth === 0) {
        return css.slice(from + 1, at)
      }
    }
  }
  return ''
}

test('the stylesheet transitions something, so the guard below is about something', () => {
  // Without this the two tests under it pass on an empty file, which is exactly the
  // state `index.css` was in before #122 — and a guard that is satisfied by the thing
  // it guards against never having happened is not a guard.
  expect(whatIsTransitioned(STYLESHEET).length).toBeGreaterThan(0)
})

test('every transition and every animation can be turned off, by the reader', () => {
  const reduced = theReducedMotionBlock(STYLESHEET)
  expect(reduced).not.toBe('')
  // Over everything, including the pseudo-elements: `.said .tick::after` and
  // `.switch::after` are drawn boxes that a later rule could animate, and a guard
  // that named only elements would not reach them.
  expect(reduced).toMatch(/\*\s*,\s*\*::before\s*,\s*\*::after/)
  // Both kinds, and `!important` on both: a transition declared on a class beats a
  // universal selector on specificity, so a guard without it is a guard that loses.
  expect(reduced).toMatch(/transition-duration:\s*[^;]*!important/)
  expect(reduced).toMatch(/animation-duration:\s*[^;]*!important/)
})

test('nothing transitions a property that moves, resizes or reflows a box', () => {
  // ADR-0081: what may be transitioned is what a state change already changes about a
  // surface's colour — never its geometry. `all` is refused by name because it is a
  // licence to transition whatever a later rule happens to add, geometry included.
  const allowed = new Set(['color', 'background-color', 'border-color', 'opacity'])
  expect([...new Set(whatIsTransitioned(STYLESHEET))].filter((one) => !allowed.has(one))).toEqual(
    [],
  )
})
