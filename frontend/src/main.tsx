/**
 * The app's mount, and the one routing decision worth explaining.
 *
 * **The screens live in the fragment, because the API owns the paths.** The bench
 * serves `GET /runs/{id}`, and a browser-history router would give the run screen
 * the same URL: a reload on it would fetch JSON from the API rather than this app,
 * and in a deployment where both are served from one origin the collision is
 * permanent rather than a dev-server quirk. A `HashRouter` puts every screen after
 * a `#`, which no server ever sees, so the app can keep fetching the API's real
 * paths — `/nonces`, `/runs`, `/runs/{id}` — with no prefix invented for it and no
 * route of the bench's shadowed by a screen.
 *
 * **The door is outside the router, because it is not a route.** Signed out, there
 * is no screen and so no path to be at; signed in, the router mounts and every
 * screen is where it was. Hash routing earns its keep a second time here — the
 * fragment never reaches a server, so the issuer has nothing to reconcile and the
 * app needs no callback route added for it. What the door is and what it does with
 * a console that declares no issuer is `console/TheDoor.tsx`.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'

import App from './App'
import { TheDoor } from './console/TheDoor'
import './index.css'

const root = document.getElementById('root')
if (!root) {
  throw new Error('index.html has no #root for the app to mount on')
}

createRoot(root).render(
  <StrictMode>
    <TheDoor>
      <HashRouter>
        <App />
      </HashRouter>
    </TheDoor>
  </StrictMode>,
)
