/**
 * The three screens the spec asks for, inside the console shell, behind a front door.
 *
 * Register carries the nonce and the three attestations; the run screen carries the
 * interrupt that blocks on both figures and then progress per layer; the report
 * screen carries the finding, the verification status and the absence of a total.
 * They are routes rather than a single stateful page because registration hands off
 * by navigating: a run has an id on the bench the moment it is registered, and a
 * screen reached by URL is a screen an operator can come back to — which is the
 * whole reason the run screen can be sat on for the hour the interrupt waits, and
 * the reason a report is a link somebody can return to after the run is over.
 *
 * **The shell is a pathless layout route, so no path moves.** `ConsoleShell`
 * renders the rail and the top bar around an `<Outlet />`, and the children below
 * it keep the exact paths this app has always served — which is what a report link
 * already sitting in somebody's inbox depends on. The patterns are the constants in
 * `console/rail.ts`, the same ones the rail builds its links from, so the rail and
 * the router cannot disagree about where a screen is, and `rail.test.ts` asserts
 * their literal values.
 *
 * **The root is a screen rather than a redirect.** It used to send an arriving
 * engineer straight to the registration form, which asked for an endpoint before
 * saying anything about the instrument that would attack it — and a deployment on a
 * live URL had nothing to serve at its root but a form. The landing screen answers
 * it: what this bench is, and the gate run it last passed.
 *
 * The catch-all is inside the shell as well: a mistyped path is somewhere to be
 * lost with the rail still on screen, rather than a dead end.
 */

import { Link, Route, Routes } from 'react-router-dom'

import { ConsoleShell } from './console/ConsoleShell'
import { ArtefactsScreen } from './console/ArtefactsScreen'
import { GateScreen } from './console/GateScreen'
import { LandingScreen } from './console/LandingScreen'
import { SettingsScreen } from './console/SettingsScreen'
import {
  ARTEFACTS_PATH,
  CONSOLE_PATH,
  GATE_PATH,
  REGISTER_PATH,
  REPORT_PATTERN,
  RUN_PATTERN,
  SETTINGS_PATH,
} from './console/rail'
import { RegisterScreen } from './register/RegisterScreen'
import { ReportScreen } from './report/ReportScreen'
import { RunScreen } from './run/RunScreen'

export default function App() {
  return (
    <Routes>
      <Route element={<ConsoleShell />}>
        <Route path={CONSOLE_PATH} element={<LandingScreen />} />
        <Route path={REGISTER_PATH} element={<RegisterScreen />} />
        <Route path={GATE_PATH} element={<GateScreen />} />
        <Route path={ARTEFACTS_PATH} element={<ArtefactsScreen />} />
        <Route path={SETTINGS_PATH} element={<SettingsScreen />} />
        <Route path={RUN_PATTERN} element={<RunScreen />} />
        <Route path={REPORT_PATTERN} element={<ReportScreen />} />
        <Route path="*" element={<NoSuchScreen />} />
      </Route>
    </Routes>
  )
}

/** A path no screen answers, said inside the shell rather than instead of it. */
function NoSuchScreen() {
  return (
    <main className="screen">
      <h1>No such screen</h1>
      <p>
        The console's front door is at <Link to={CONSOLE_PATH}>/</Link>,
        registration at <Link to={REGISTER_PATH}>/register</Link>, the bench's own
        gate at <Link to={GATE_PATH}>/gate</Link>, the signed artefacts at{' '}
        <Link to={ARTEFACTS_PATH}>/artefacts</Link> and what the bench is set to at{' '}
        <Link to={SETTINGS_PATH}>/settings</Link>. A run is at
        <code> /runs/&lt;id&gt;</code>, and its report at
        <code> /runs/&lt;id&gt;/report</code>.
      </p>
    </main>
  )
}
