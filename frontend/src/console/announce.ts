/**
 * What a screen says about itself to somebody who is not looking at it.
 *
 * Two facts about this console are stated nowhere on its screens. The first is which
 * screen you are on: it is a hash router, so a screen change moves no document, and
 * the tab strip and the browser history said `AgentAudit` for all seven of them —
 * `index.html` set the title once and nothing has set it since. The second is what a
 * screen is doing while it is not on top: a run takes minutes, and a run somebody
 * backgrounded is exactly the run whose phase is worth carrying into the tab.
 *
 * **The screen's own name comes first and the app's name last.** A tab strip and a
 * history list both truncate a title from the right, so the part that has to survive
 * the cut is the part that tells the two apart. What a screen is *doing* goes in
 * front of its name for the same reason, one step further: on a run there is nothing
 * more worth reading at a glance than whether it is still running.
 *
 * **What the title carries about a run is its phase and never a figure.** The run
 * screen's counts are per family and per layer and this app adds none of them up
 * (`run/progress.ts`); a number in a tab strip, with the label it was drawn beside
 * left behind on the page, is the one place a reader would take a length for a rate
 * (ADR-0005). So the title carries the standing's heading — the word the screen's
 * own `h1` carries — and nothing that could be read as a score.
 */

import { useEffect, useRef, type RefObject } from 'react'

/** The name in `index.html`'s `<title>`, which every title still ends with. */
export const APP_NAME = 'AgentAudit'

/** Between the parts of a title. An em dash, as the screens set their asides. */
const BETWEEN = ' — '

/**
 * One screen's title: what it is doing, what it is, and what this is.
 *
 * `doing` is optional because most screens are not doing anything — a screen that
 * lists artefacts is the same screen whatever it is showing — and an empty one
 * leaves no dangling separator behind it.
 */
export function screenTitle(name: string, doing = ''): string {
  return [doing, name, APP_NAME].filter((part) => part !== '').join(BETWEEN)
}

/**
 * Set the document's title for as long as this screen is on it.
 *
 * No cleanup that puts the old title back: the next screen sets its own on the
 * render it arrives in, and a restore on the way out would put `AgentAudit` in the
 * tab for one frame between two screens that both have names.
 */
export function useScreenTitle(name: string, doing = ''): void {
  useEffect(() => {
    document.title = screenTitle(name, doing)
  }, [name, doing])
}

/**
 * The heading a screen change puts the keyboard on, and when it takes it.
 *
 * A router that swaps the screen under a reader moves nothing: a screen reader
 * announces nothing, and the next Tab resumes from the top of the document rather
 * than from the screen that just arrived. So the arriving screen's `h1` takes the
 * keyboard, which announces the screen by reading its heading and puts the tab order
 * where the reader is.
 *
 * **What counts as an arrival is the heading's own name, held across mounts.** Each
 * screen is a different component, so a ref inside one cannot tell *this screen has
 * just replaced another* from *this screen is being drawn for the first time*: it is
 * a first render either way. The name last announced is therefore held in the module
 * — one document, one console — and a call whose name differs from it is an arrival.
 *
 * **The first screen of a session does not take the keyboard.** Nobody navigated to
 * it; it is where the address bar landed, and focus belongs at the top of a document
 * somebody has just opened. So the first call records the name and moves nothing.
 *
 * **The step of a walk is an arrival too**, which is what `name` rather than a path
 * buys: the registration walk swaps its whole screen under one route, and a reader
 * who is not told is a reader whose next Tab starts from the document again.
 */
export function useArrivalFocus(name: string): RefObject<HTMLHeadingElement | null> {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    if (announced === name) {
      return
    }
    const first = announced === null
    announced = name
    if (!first) {
      heading.current?.focus()
    }
  }, [name])
  return heading
}

/**
 * The screen this document last announced, or `null` before it announced any.
 *
 * Module state rather than a ref, and the docstring above says why: the question it
 * answers spans two components, because an arrival is one screen replacing another.
 */
let announced: string | null = null
