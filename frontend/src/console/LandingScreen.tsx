/**
 * The console's front door: what this instrument is, and whether it was validated.
 *
 * The root used to redirect to the registration form, which asked an engineer for
 * an endpoint before telling them what would be done to it — and before telling
 * them anything about the instrument that was going to measure their agent. This
 * screen answers the second question first: the bench's own gate citation, read
 * from `GET /bench/gate`, which is the same typed citation the provenance block of
 * every signed report carries.
 *
 * **The citation region is where an absence is as visible as a pass.** A bench
 * citing no gate run gets the same heading, the same weight and a sentence in the
 * same place — drawn without the rows a citation would have had, in the idiom the
 * report screen already uses for a family with no rate, because a blank where an
 * outcome goes is read as a gate that failed.
 *
 * **The document is named, and it is named rather than linked.** Every per-family
 * rate and every discrimination score of that gate run is in it, and none of them is
 * on this page: the citation does not carry them, and this screen does not open the
 * document to find them. The path is printed as the path it is because this bench
 * serves no route for it — a hyperlink to something no route answers would be a
 * broken link on the front door, and how the document is served is the gate screen's
 * question rather than this screen's.
 *
 * **There is no button here that starts a gate run**, and no route that would take
 * one. A gate run attacks all three reference agents, spends about 830 calls and
 * writes back to the case library, behind a terminal that asks the three
 * attestation statements one at a time (PLAN.md §8). The console cites it.
 *
 * The view model is `landing.ts` and it is where the wording lives; this file is
 * markup and is driven by hand, as every screen in this app is.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { benchGate, type GateCitation } from '../api/bench'
import {
  gateReading,
  WHAT_THIS_INSTRUMENT_IS,
  WHY_THE_GATE_IS_HERE,
  type GateReading,
} from './landing'
import { REGISTER_PATH } from './rail'

/** What this screen is holding: the citation, or why it could not read one. */
interface Held {
  gate: GateCitation | null
  unavailable: string
}

const NOTHING_YET: Held = { gate: null, unavailable: '' }

export function LandingScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const gate = await benchGate()
        if (current) {
          setHeld({ gate, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setHeld({ gate: null, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  return (
    <main className="screen">
      <header>
        <p className="eyebrow">AgentAudit — the operator console</p>
        <h1>An adversarial test bench, and its own certification</h1>
        <p className="steps">
          Six families of failure, each reported over its own denominator.{' '}
          <Link to={REGISTER_PATH}>Register a target</Link> when you have read what
          this bench has and has not been shown to do.
        </p>
      </header>

      <section>
        <h2>What this instrument is</h2>
        <p>{WHAT_THIS_INSTRUMENT_IS}</p>
      </section>

      <section>
        <h2>Whether it has been validated</h2>
        <p>{WHY_THE_GATE_IS_HERE}</p>

        {held.unavailable ? (
          <div className="citation uncited" role="alert">
            <h3>This bench did not answer for its own gate citation</h3>
            <p>{held.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that cites no gate run: what is unknown
              here is what the bench would have said, and nothing on this page
              should be read as either answer.
            </p>
          </div>
        ) : held.gate === null ? (
          <p className="aside">Reading this bench’s own gate citation…</p>
        ) : (
          <Citation reading={gateReading(held.gate)} />
        )}
      </section>
    </main>
  )
}

/**
 * The citation, or the stated absence of one, in the same region either way.
 *
 * Dashed rather than solid when there is nothing cited, and drawn without the rows
 * a citation would have filled: the absence is a sentence, and the surest way to be
 * read as a failed gate is to be drawn in the same box with an empty outcome in it.
 */
function Citation({ reading }: { reading: GateReading }) {
  return (
    <div className={reading.cited ? 'citation' : 'citation uncited'}>
      <h3>{reading.heading}</h3>
      {reading.cited ? (
        <>
          <dl className="at">
            {reading.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p>
            <code>{reading.document.path}</code>
          </p>
          <p className="aside">{reading.document.statement}</p>
        </>
      ) : (
        <p>{reading.statement}</p>
      )}
      <p className="aside">{reading.aboutTheBench}</p>
    </div>
  )
}
