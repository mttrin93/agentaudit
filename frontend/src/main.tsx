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
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'

import App from './App'
import './index.css'

const root = document.getElementById('root')
if (!root) {
  throw new Error('index.html has no #root for the app to mount on')
}

createRoot(root).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>,
)
