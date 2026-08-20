/**
 * The three screens the spec asks for.
 *
 * Register carries the nonce and the three attestations; the run screen carries the
 * interrupt that blocks on both figures and then progress per layer; the report
 * screen carries the finding, the verification status and the absence of a total.
 * They are routes rather than a single stateful page because registration hands off
 * by navigating: a run has an id on the bench the moment it is registered, and a
 * screen reached by URL is a screen an operator can come back to — which is the
 * whole reason the run screen can be sat on for the hour the interrupt waits, and
 * the reason a report is a link somebody can return to after the run is over.
 */

import { Link, Navigate, Route, Routes } from 'react-router-dom'

import { RegisterScreen } from './register/RegisterScreen'
import { ReportScreen } from './report/ReportScreen'
import { RunScreen } from './run/RunScreen'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/register" replace />} />
      <Route path="/register" element={<RegisterScreen />} />
      <Route path="/runs/:runId" element={<RunScreen />} />
      <Route path="/runs/:runId/report" element={<ReportScreen />} />
      <Route
        path="*"
        element={
          <main className="screen">
            <h1>No such screen</h1>
            <p>
              Registration is at <Link to="/register">/register</Link>. A run is at
              <code> /runs/&lt;id&gt;</code>, and its report at
              <code> /runs/&lt;id&gt;/report</code>.
            </p>
          </main>
        }
      />
    </Routes>
  )
}
