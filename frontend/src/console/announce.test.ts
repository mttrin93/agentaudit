/**
 * What a screen's title says, and in what order it says it.
 *
 * The claim is about the tab strip and the history list, both of which truncate a
 * title from the right: what has to survive that cut is the screen, and after it
 * whatever the screen is doing. So the app's name is last on every screen and never
 * the whole of a title, which is the state `index.html` left the console in — seven
 * screens all called `AgentAudit`.
 */

import { describe, expect, it } from 'vitest'

import { APP_NAME, screenTitle } from './announce'

describe('a screen’s title', () => {
  it('names the screen first and the app last', () => {
    expect(screenTitle('Register a target')).toBe('Register a target — AgentAudit')
  })

  it('puts what the screen is doing in front of the screen’s own name', () => {
    expect(screenTitle('The run', 'Running')).toBe('Running — The run — AgentAudit')
  })

  it('leaves no dangling separator where there is nothing to say', () => {
    expect(screenTitle('Settings', '')).toBe(`Settings — ${APP_NAME}`)
  })

  it('is never the app’s name alone, which is what every screen said before', () => {
    for (const title of [screenTitle('The bench'), screenTitle('The run', 'Finished')]) {
      expect(title).not.toBe(APP_NAME)
      expect(title.endsWith(` — ${APP_NAME}`)).toBe(true)
    }
  })
})
