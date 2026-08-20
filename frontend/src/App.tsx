/**
 * The three screens the spec asks for, of which one exists.
 *
 * Register is here in full. The run screen is a placeholder that #58 replaces with
 * the interrupt that has to block, and the report screen arrives with #59. They
 * are routes rather than a single stateful page because registration hands off by
 * navigating: a run has an id on the bench the moment it is registered, and a
 * screen reached by URL is a screen an operator can come back to.
 */

import { Link, Navigate, Route, Routes } from 'react-router-dom'

import { RegisterScreen } from './register/RegisterScreen'
import { RunScreen } from './run/RunScreen'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/register" replace />} />
      <Route path="/register" element={<RegisterScreen />} />
      <Route path="/runs/:runId" element={<RunScreen />} />
      <Route
        path="*"
        element={
          <main className="screen">
            <h1>No such screen</h1>
            <p>
              Registration is at <Link to="/register">/register</Link>. The
              report screen arrives with #59.
            </p>
          </main>
        }
      />
    </Routes>
  )
}
