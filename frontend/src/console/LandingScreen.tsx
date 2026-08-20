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
 * **The second region is the runs on the record**, read from `GET /runs`, so that a
 * run whose URL nobody kept is still reachable. Each row carries calls spent in two
 * columns — the scored layer's and the adaptive layer's — set side by side in two
 * hues and **never added into a third figure**: the two are enforced against two
 * separate ceilings, and a single number would say what a run cost without saying
 * which half of it cost that (ADR-0007, ADR-0010). There is no totals row on this
 * screen and the view model has no field for one.
 *
 * The two regions read two routes and hold two pieces of state, deliberately not
 * one: a bench that answered for its gate citation and not for its runs has said
 * one of the two things, and a single failure state would lose the half that
 * arrived.
 *
 * The view models are `landing.ts` and `runs.ts` and they are where the wording
 * lives; this file is markup and is driven by hand, as every screen in this app is.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  benchGate,
  benchRuns,
  type GateCitation,
  type RunList,
} from '../api/bench'
import {
  gateReading,
  WHAT_THIS_INSTRUMENT_IS,
  WHY_THE_GATE_IS_HERE,
  type GateReading,
} from './landing'
import { REGISTER_PATH } from './rail'
import {
  runsReading,
  TWO_COLUMNS_NEVER_ONE,
  type AdaptiveColumn,
  type RunsReading,
  type ScoredColumn,
} from './runs'

/** What this screen is holding: the citation, or why it could not read one. */
interface Held {
  gate: GateCitation | null
  unavailable: string
}

const NOTHING_YET: Held = { gate: null, unavailable: '' }

/** What the second region is holding: the runs, or why it could not read them. */
interface HeldRuns {
  list: RunList | null
  unavailable: string
}

const NO_LIST_YET: HeldRuns = { list: null, unavailable: '' }

export function LandingScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)
  const [runs, setRuns] = useState<HeldRuns>(NO_LIST_YET)

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

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const list = await benchRuns()
        if (current) {
          setRuns({ list, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setRuns({ list: null, unavailable: `${unknown}` })
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

      <section>
        <h2>Your runs</h2>
        <p>{TWO_COLUMNS_NEVER_ONE}</p>

        {runs.unavailable ? (
          <div className="citation uncited" role="alert">
            <h3>This bench did not answer for its runs</h3>
            <p>{runs.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench with no runs on the record: what is
              unknown here is what it would have listed, so nothing below should be
              read as <em>none</em>.
            </p>
          </div>
        ) : runs.list === null ? (
          <p className="aside">Reading the runs on the record…</p>
        ) : (
          <Runs reading={runsReading(runs.list)} />
        )}
      </section>
    </main>
  )
}

/**
 * The runs on the record, or the stated fact that there are none.
 *
 * An ordered list rather than a table, and that is the load-bearing choice: a table
 * of two numeric columns has a footer, and a footer is where a total goes. A list
 * of runs has no footer to put one in, so the two figures stay two figures — the
 * same argument the interrupt's two cost figures are set as two blocks on
 * (`.figures` in the stylesheet).
 */
function Runs({ reading }: { reading: RunsReading }) {
  if (!reading.listed) {
    return (
      <div className="citation uncited">
        <h3>No runs on the record</h3>
        <p>{reading.statement}</p>
      </div>
    )
  }
  return (
    <ol className="runs">
      {reading.runs.map((run) => (
        <li className="run" key={run.id}>
          <h3>
            <Link to={run.path}>{run.target}</Link>
          </h3>
          <p className="standing">
            {run.standing} — recorded {run.recordedAt}
          </p>
          <p className="aside">
            <code>{run.id}</code>
          </p>
          <p className="aside">{run.statement}</p>
          <div className="spends">
            <Spend column={run.scored} />
            <Spend column={run.adaptive} />
          </div>
        </li>
      ))}
    </ol>
  )
}

/**
 * One layer's spend, in its own hue and under its own name.
 *
 * The union rather than one shared column type, so that this component is the only
 * place in the app that has seen both — and all it does with them is draw them
 * apart. The accent is a class name and the colour is the stylesheet's, and the
 * layer is written out in words beside it so the distinction survives a reader who
 * cannot see the two hues apart.
 */
function Spend({ column }: { column: ScoredColumn | AdaptiveColumn }) {
  return (
    <div className={`spend ${column.accent}`}>
      <p className="layer-name">{column.layer}</p>
      <p className="calls">{column.calls}</p>
      <p className="kind">{column.statement}</p>
    </div>
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
