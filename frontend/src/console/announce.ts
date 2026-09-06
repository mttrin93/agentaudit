/**
 * What a screen says about itself to somebody who is not looking at it.
 *
 * Two facts about this console were stated nowhere on its screens: which screen you
 * are on, and — while a run takes minutes — what that screen is doing. It is a hash
 * router, so a screen change moves no document: nothing announced one, nothing moved
 * the keyboard onto one, and `index.html` set one `<title>` that all seven screens
 * kept. **ADR-0079** decides what the announcement is, what counts as an arrival, and
 * why a run's title carries a phase and never a figure.
 *
 * What is here is the consequence: one pure function the tab strip is built from, and
 * two hooks a screen calls. `announce.test.ts` holds the first in node;
 * `e2e/liveness.spec.ts` holds the two hooks in a browser, which is the division
 * `vite.config.ts` sets out.
 */

import { useEffect, useRef, type RefObject } from 'react'

/** The name in `index.html`'s `<title>`, which every title still ends with. */
export const APP_NAME = 'AgentAudit'

/** Between the parts of a title. An em dash, as the screens set their asides. */
const BETWEEN = ' — '

/**
 * The screen this document last announced, or `null` before it announced any.
 *
 * Module state rather than a ref, and ADR-0079 says why: an arrival is one screen
 * replacing another, and each screen is a different component, so the question spans
 * two of them. Written and read only inside the effect below — never during a render
 * — so it is not state React draws from and the compiler has nothing to memoise
 * around it.
 */
let announced: string | null = null

/**
 * One screen's title: what it is doing, what it is, and what this is.
 *
 * `doing` is optional because most screens are not doing anything — a screen that
 * lists artefacts is the same screen whatever it is showing — and an empty one leaves
 * no dangling separator behind it.
 */
export function screenTitle(name: string, doing = ''): string {
  return [doing, name, APP_NAME].filter((part) => part !== '').join(BETWEEN)
}

/**
 * Set the document's title for as long as this screen is on it.
 *
 * No cleanup that puts the old title back (ADR-0079): the next screen sets its own on
 * the render it arrives in, and a restore on the way out would put `AgentAudit` in
 * the tab for one frame between two screens that both have names.
 */
export function useScreenTitle(name: string, doing = ''): void {
  useEffect(() => {
    document.title = screenTitle(name, doing)
  }, [name, doing])
}

/**
 * The heading a screen change puts the keyboard on, and when it takes it.
 *
 * ADR-0079: the arriving screen's `h1` takes focus, an arrival is the heading's own
 * name rather than a route, and the first screen of a session moves nothing.
 *
 * The local consequence, for a screen calling this: **pass the name of the screen and
 * not what its heading currently reads.** The run screen's heading changes when the
 * run changes phase and the report screen's becomes the target's name when the
 * document arrives; a key that followed either would take the keyboard off whatever
 * the reader was reading, mid-screen. The registration walk is the opposite case and
 * passes its step, because there the step *is* the screen.
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
