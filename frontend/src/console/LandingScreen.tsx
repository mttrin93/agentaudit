/**
 * The console's front door: what this instrument is, and the three things it does.
 *
 * The root used to redirect to the registration form, which asked an engineer for
 * an endpoint before telling them what would be done to it. This screen says what
 * the bench is in one paragraph, offers the three errands the console exists for —
 * register a target, run the gate, check an artefact — and then lists what this
 * bench has already done.
 *
 * **The cards carry no figure, and none of them starts anything from here.** Each
 * is a name, what that screen does, and a link to it. A gate run attacks all three
 * reference agents, spends about 830 calls and writes back to the case library; it
 * is started on the gate screen, where the rule, the write-back and the two figures
 * are on the page beside it (ADR-0021). An operation with three attestation
 * statements and a spend in front of it does not belong on the screen somebody
 * lands on.
 *
 * **The bench's own gate citation is not on this screen any more, and this screen
 * reads no route for it.** It used to be here, drawn so that an absence was as
 * visible as a pass; it is on the gate screen, in that same idiom, beside the rule
 * it was decided under and the document it wrote. A citation read apart from its
 * rule is an outcome a reader cannot check, and the front door's answer about
 * validation is now that there is a gate and one link to it. The cost is real and
 * it is the one to watch: a bench that has never passed its gate no longer says so
 * on the screen an engineer lands on.
 *
 * **The runs on the record** are read from `GET /runs`, so that a run whose URL
 * nobody kept is still reachable. Each row carries calls spent in two columns — the
 * scored layer's and the adaptive layer's — set side by side in two hues and
 * **never added into a third figure**: the two are enforced against two separate
 * ceilings, and a single number would say what a run cost without saying which half
 * of it cost that (ADR-0007, ADR-0010). There is no totals row on this screen and
 * the view model has no field for one.
 *
 * **The last region is the six families**, one sentence each: what the failure *is*,
 * the agent doing the thing, with no figure anywhere in it. An operator meets
 * `indirect prompt injection` on four screens before anything on any of them says what
 * one is, and this is where it is said.
 *
 * **Where the security questionnaire was.** That region answered a questionnaire out of
 * the most recent signed report — a family per question, its rate over that family's
 * own denominator, its interval and confidence — and it is the block this project
 * points at, against the displaced default of a questionnaire filled in from
 * recollection for a reader who cannot check a line of it (ADR-0001). It is off this
 * screen and not out of the bench: `questionnaire.ts` still builds it, its tests still
 * hold every claim in it, and a rate with its interval beside it is what the report
 * screen is for. This screen now reads exactly one route, `GET /runs`.
 *
 * The view models are `landing.ts` and `runs.ts`, and they are where the wording
 * lives; this file is markup and is driven by hand, as every screen in this app is.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { readFamily } from '../families'
import { benchArtefacts, benchRuns, type ArtefactList, type RunList } from '../api/bench'
import {
  WHAT_THIS_CONSOLE_DOES,
  WHAT_THIS_INSTRUMENT_IS,
  type ConsoleDoes,
  THE_FAMILIES,
} from './landing'
import {
  runsReading,
  type AdaptiveColumn,
  type RunsReading,
  type ScoredColumn,
} from './runs'
import { artefactsReading, type ArtefactsReading } from './artefacts'

/** What the second region is holding: the runs, or why it could not read them. */
interface HeldRuns {
  list: RunList | null
  unavailable: string
}

const NO_LIST_YET: HeldRuns = { list: null, unavailable: '' }

/** What the artefacts region is holding: the list, or why it could not read it. */
interface HeldArtefacts {
  list: ArtefactList | null
  unavailable: string
}

const NO_ARTEFACTS_LIST_YET: HeldArtefacts = { list: null, unavailable: '' }

export function LandingScreen() {
  const [runs, setRuns] = useState<HeldRuns>(NO_LIST_YET)
  const [signed, setSigned] = useState<HeldArtefacts>(NO_ARTEFACTS_LIST_YET)

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

  /*
   * The artefacts, on their own state and deliberately not on the runs' state.
   *
   * A list of runs an operator can navigate by is worth having whether or not the
   * artefacts could be read, and one failure state across the two would take the list
   * down with them — the same reason the questionnaire that used to be here held its
   * own.
   */
  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const list = await benchArtefacts()
        if (current) {
          setSigned({ list, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setSigned({ list: null, unavailable: `${unknown}` })
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
        <h1>AgentAudit: an adversarial bench</h1>
      </header>

      <section>
        <h2>The instrument</h2>
        <p>{WHAT_THIS_INSTRUMENT_IS}</p>
      </section>

      <section>
        <h2>What this console does</h2>
        <div className="does">
          {WHAT_THIS_CONSOLE_DOES.map((card) => (
            <Card card={card} key={card.path} />
          ))}
        </div>
      </section>

      <section>
        {/*
          The heading and then the runs.

          Two paragraphs stood here. One said what the two columns are and why they are
          never added — which the rows say by being two columns with two headings and no
          third; the reason they are not added is `runs.ts`'s to hold, and it holds it
          where the columns are built. The other pointed at the signed artefacts screen,
          which is a row in the rail on the left of this page and a card two sections
          above it.
        */}
        <h2>Your runs</h2>

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

      <section>
        {/*
          The artefacts, in the shape the runs above them are in.

          A summary and not the artefacts screen: the target, when the run went on the
          record, the one line naming how its three checks settled, and the two links a
          reader wants — the report a recipient may already hold, and the run it came
          from. The three results one by one, the two claims and the three files a
          verifier saves are on the signed artefacts screen, which is a rail row and a
          card at the top of this page.
        */}
        <h2>Your artefacts</h2>

        {signed.unavailable ? (
          <div className="citation uncited" role="alert">
            <h3>This bench did not answer for its artefacts</h3>
            <p>{signed.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that has signed nothing: what is unknown
              here is what it would have listed, so nothing below should be read as{' '}
              <em>none</em>.
            </p>
          </div>
        ) : signed.list === null ? (
          <p className="aside">Reading the artefacts on the record…</p>
        ) : (
          <Artefacts reading={artefactsReading(signed.list)} />
        )}
      </section>

      {/*
        The six families, each in a sentence, where the questionnaire region was.

        That region answered a questionnaire out of the most recent signed report — a
        family per question, its rate over its own denominator, its interval and its
        confidence — and it was the block this project points at. It is gone from this
        screen and not from the bench: `questionnaire.ts` still builds it and its tests
        still hold every claim about it, and the report screen is where a reader meets a
        rate with its interval beside it.

        What is here instead is what this page was missing: an operator meets
        `indirect prompt injection` on four screens before anything says what one is.
        Six sentences, no figure in any of them, and the names read as words.
      */}
      <section>
        <h2>The families</h2>
        <dl className="said">
          {THE_FAMILIES.map((one) => (
            <div key={one.family}>
              <dt>
                {readFamily(one.family)}
                {/*
                  A switch drawn on and not a switch. These six are the library the
                  bench ships and every run attacks all of them, so there is nothing
                  here to turn off — a real control that refused to move would be a
                  worse lie than a mark that never claimed to be one. `role="img"` with
                  a label, because it is a picture of a state and not a checkbox: a
                  keyboard never lands on it and a screen reader reads the words.
                */}
                <span className="switch on" role="img" aria-label="on by default" />
              </dt>
              <dd>{one.says}</dd>
            </div>
          ))}
        </dl>
      </section>
    </main>
  )
}

/**
 * The artefacts on the record, or the stated fact that there are none.
 *
 * The runs' own shape — an ordered list of blocks, no table, nothing summarising the
 * column — because these are the same runs seen from the other end: one that finished
 * and was signed. The order is the route's, most recent first, and nothing is filtered:
 * an artefact whose signature did not verify is the one an engineer most needs to see,
 * and its own line says how it settled.
 */
function Artefacts({ reading }: { reading: ArtefactsReading }) {
  if (!reading.listed) {
    return (
      <div className="citation uncited">
        <h3>No signed artefact on the record</h3>
      </div>
    )
  }
  return (
    <ol className="runs">
      {reading.artefacts.map((artefact) => (
        <li className="run" key={artefact.id}>
          <h3>
            <Link to={artefact.reportPath}>{artefact.target}</Link>
          </h3>
          <p className="standing">
            Signed for the run recorded {artefact.recordedAt}
          </p>
          <p className="consequence">{artefact.verification.heading}</p>
          <p className="aside">
            <code>{artefact.id}</code> —{' '}
            <Link to={artefact.runPath}>the run</Link>
          </p>
        </li>
      ))}
    </ol>
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
  // With no runs, the heading and nothing under it. It carried the record's own
  // sentence — nothing registered in this process, a fact about the bench and not about
  // any target, register one and it appears here — which is three clauses under a
  // heading that says the whole of it. `RunsReading.statement` is still built and still
  // tested.
  if (!reading.listed) {
    return (
      <div className="citation uncited">
        <h3>No runs on the record</h3>
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
 * One errand, with the control that starts it.
 *
 * A `Link` and not a `button`, styled as the control it is: it navigates, and a
 * button that navigates is a control a keyboard and a screen reader are told the
 * wrong thing about.
 *
 * All three take the same treatment. The filled one used to be the lead card's alone,
 * which left the other two outlined in the same hairline every block on the page is
 * edged with — three doors, one of them drawn as a door. `lead` still says which errand
 * comes first, and the order of the cards is where a reader sees it.
 */
function Card({ card }: { card: ConsoleDoes }) {
  return (
    <div className="card">
      <h3>{card.name}</h3>
      <p>{card.does}</p>
      <Link className="act" to={card.path}>
        {card.act}
      </Link>
    </div>
  )
}
