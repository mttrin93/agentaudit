/**
 * Where a registered run is handed over to, before the run screen exists.
 *
 * This is a placeholder on purpose and it is a real route rather than a stub
 * function: registration's last act is a navigation, and a navigation to nowhere
 * would leave the handoff untested by the only kind of test this screen gets — a
 * person driving it. The approval interrupt that has to block, and per-layer
 * progress, are #58's subject and deliberately absent here. **There is no control
 * on this page that can answer the interrupt**, which is the safe direction for a
 * placeholder to be wrong in: nothing reaches the operator's endpoint until the
 * screen that shows both cost figures asks them.
 *
 * What it does do is read the run's standing once, so that the handoff shows a run
 * the bench actually holds rather than an id this app carried in a URL. And when
 * that run has settled at a refused registration — the target never echoed the
 * nonce, which cannot be known until after the interrupt is answered — it points
 * back at the register screen, which owns the recovery.
 */

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { REGISTRATION_REFUSED, runStanding, type RunStanding } from '../api/bench'

export function RunScreen() {
  const { runId = '' } = useParams()
  const [standing, setStanding] = useState<RunStanding | null>(null)
  const [unavailable, setUnavailable] = useState('')

  useEffect(() => {
    let current = true
    void runStanding(runId)
      .then((read) => {
        if (current) {
          setStanding(read)
        }
      })
      .catch((unknown: unknown) => {
        if (current) {
          setUnavailable(`${unknown}`)
        }
      })
    return () => {
      current = false
    }
  }, [runId])

  return (
    <main className="screen">
      <header>
        <p className="eyebrow">AgentAudit — run</p>
        <h1>Run {runId}</h1>
      </header>
      <section>
        {unavailable ? <p role="alert">{unavailable}</p> : null}
        {standing ? (
          <>
            <p>
              <strong>{standing.status}</strong>
            </p>
            <p>{standing.statement}</p>
          </>
        ) : null}
        <p className="aside">
          The approval interrupt and per-layer progress arrive with the run screen
          itself. Until then this page only says where the run stands: there is no
          control here that can answer the interrupt, so nothing has been sent to
          the target.
        </p>
        {standing?.status === REGISTRATION_REFUSED ? (
          <p>
            <Link to={`/register?refused=${encodeURIComponent(runId)}`}>
              Re-plant the nonce and register again
            </Link>
          </p>
        ) : null}
      </section>
    </main>
  )
}
