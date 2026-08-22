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
 * **The last region is the security questionnaire**, answered out of the attempts
 * of the most recent run that produced a signed report: a family per question, its
 * rate over that family's own denominator, its interval and confidence, and what
 * that family does not test. It is the block this whole project points at — the
 * displaced default is a questionnaire filled in from recollection, under
 * commercial pressure, for a reader who cannot check a line of it (ADR-0001).
 * **Nothing in it spans two families** — no total, no average, no rank, no posture
 * figure — and the three kinds of nothing stay three, because a family the bench
 * could not measure printed as a zero is an untested control reported as a defended
 * one (`questionnaire.ts`).
 *
 * **It reads no new route.** The runs on the record say which runs completed, each
 * run's own record says where its report is served, and the report is the payload
 * the report screen already reads. Nothing was added to the API for this region,
 * and the path to a report is never built here — it is read off the run, so this
 * screen cannot go looking somewhere the bench does not serve.
 *
 * The two regions that read a route hold their own state, deliberately not one
 * between them: a list of runs an operator can navigate by is worth having whether
 * or not a report could be read out of one of them, and one failure state across
 * the two would take the list down with the answers.
 *
 * The view models are `landing.ts`, `runs.ts` and `questionnaire.ts`, and they are
 * where the wording lives; this file is markup and is driven by hand, as every
 * screen in this app is.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { readFamily } from '../families'
import {
  benchRuns,
  reportPayload,
  runProgress,
  type RunList,
} from '../api/bench'
import {
  WHAT_THIS_CONSOLE_DOES,
  WHAT_THIS_INSTRUMENT_IS,
  type ConsoleDoes,
} from './landing'
import {
  drawnFrom,
  NO_SIGNED_REPORT_YET,
  ONE_FAMILY_PER_ANSWER,
  questionnaire,
  theRunsToDrawFrom,
  WHAT_THIS_BLOCK_ANSWERS,
  type AnsweredQuestion,
  type Questionnaire,
  type QuestionnaireAnswer,
} from './questionnaire'
import { ARTEFACTS_PATH } from './rail'
import {
  runsReading,
  TWO_COLUMNS_NEVER_ONE,
  type AdaptiveColumn,
  type RunsReading,
  type ScoredColumn,
} from './runs'

/** What the second region is holding: the runs, or why it could not read them. */
interface HeldRuns {
  list: RunList | null
  unavailable: string
}

const NO_LIST_YET: HeldRuns = { list: null, unavailable: '' }

/**
 * What the last region is holding: the answers, or which kind of nothing it has.
 *
 * Three empty fields and not one, because *no run has produced a signed report* and
 * *the bench did not answer* are two different facts, and neither is an answer to a
 * question on the block. A single `unavailable` would report the first as the
 * second, which is a bench that looks broken to an operator whose bench is merely
 * new.
 */
interface HeldAnswers {
  answers: Questionnaire | null
  /** Why there is no report to answer from, when there is none. */
  none: string
  unavailable: string
}

const NO_ANSWERS_YET: HeldAnswers = { answers: null, none: '', unavailable: '' }

export function LandingScreen() {
  const [runs, setRuns] = useState<HeldRuns>(NO_LIST_YET)
  const [asked, setAsked] = useState<HeldAnswers>(NO_ANSWERS_YET)

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

  /**
   * The most recent run that produced a signed report, read for its answers.
   *
   * Walked most-recent-first rather than assuming the newest completed run has an
   * artefact, because completing and being signed are two facts: the run's own
   * record is what advertises where its report is, and a run with none says why in
   * its own words. In practice the walk stops at the first candidate — a bench with
   * no signing key refuses to boot (ADR-0020) — so this is a fallback rather than a
   * loop that runs.
   */
  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const list = await benchRuns()
        for (const row of theRunsToDrawFrom(list)) {
          const progress = await runProgress(row.run_id)
          if (progress.report === null) {
            continue
          }
          const payload = await reportPayload(progress.report.path)
          if (current) {
            setAsked({
              answers: questionnaire(payload, drawnFrom(row)),
              none: '',
              unavailable: '',
            })
          }
          return
        }
        if (current) {
          setAsked({ answers: null, none: NO_SIGNED_REPORT_YET, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setAsked({ answers: null, none: '', unavailable: `${unknown}` })
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
        <h2>Your runs</h2>
        <p>{TWO_COLUMNS_NEVER_ONE}</p>
        <p className="steps">
          The artefact a completed run left behind, with its three verification
          results named individually and the three files a recipient checks, is on{' '}
          <Link to={ARTEFACTS_PATH}>the signed artefacts screen</Link>.
        </p>

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
        <h2>The security questionnaire, answered from attempts</h2>
        <p>{WHAT_THIS_BLOCK_ANSWERS}</p>
        <p>{ONE_FAMILY_PER_ANSWER}</p>

        {asked.unavailable ? (
          <div className="citation uncited" role="alert">
            <h3>This bench did not answer for the report these answers come from</h3>
            <p>{asked.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench with no signed report, and not an answer
              to any question below: what is unknown here is what it would have
              answered, so nothing is <em>not tested</em>, <em>not measurable</em> or
              a rate of zero on the strength of this.
            </p>
          </div>
        ) : asked.none ? (
          <div className="citation uncited">
            <h3>No run on this bench has produced a signed report</h3>
            <p>{asked.none}</p>
          </div>
        ) : asked.answers === null ? (
          <p className="aside">Reading the most recent signed report…</p>
        ) : (
          <Answers questionnaire={asked.answers} />
        )}
      </section>
    </main>
  )
}

/**
 * The answers, and the one run every one of them was drawn from.
 *
 * A stack of blocks and never a table, for the reason the report screen's families
 * are: a table of rates wants a footer, and the footer is where a reader is handed
 * the figure across six families that this bench does not stand behind (ADR-0005).
 * The blocks reuse the report screen's own `.family` idiom, uncoloured — no band,
 * no rate and no answer here is tinted, because a colour scale over *holds*, *weak*
 * and *fails* is the severity scale the report exists to refuse.
 */
function Answers({ questionnaire: asked }: { questionnaire: Questionnaire }) {
  const from = asked.drawnFrom
  return (
    <>
      <div className="citation">
        <h3>Drawn from one run</h3>
        <dl className="at">
          <div>
            <dt>target</dt>
            <dd>{from.target}</dd>
          </div>
          <div>
            <dt>recorded</dt>
            <dd>{from.recordedAt}</dd>
          </div>
          <div>
            <dt>run</dt>
            <dd>
              <code>{from.runId}</code>
            </dd>
          </div>
        </dl>
        <p>
          <Link to={from.path}>Read the signed report these answers came out of</Link>
        </p>
        <p className="aside">{from.statement}</p>
      </div>

      <div className="families">
        {asked.answers.map((answer) => (
          <TheAnswer answer={answer} key={keyFor(answer)} />
        ))}
      </div>
    </>
  )
}

/** One answer per family, and per category the bench never tests. */
function keyFor(answer: QuestionnaireAnswer): string {
  return answer.kind === 'not_tested'
    ? `not_tested-${answer.category}`
    : `${answer.kind}-${answer.family}`
}

/**
 * One question, in four shapes.
 *
 * Three of the four carry no figure at all and are drawn without the place a figure
 * would go — dashed, with the reason where the rate would have been — because the
 * surest way for *withheld*, *not measurable* or *not tested* to be read as a zero
 * is to be drawn in the same box with an empty number in it.
 */
function TheAnswer({ answer }: { answer: QuestionnaireAnswer }) {
  if (answer.kind === 'answered') {
    return <Answered answer={answer} />
  }
  if (answer.kind === 'not_tested') {
    return (
      <div className="family absent">
        <h3>{answer.category}</h3>
        <p className="at">not tested — {answer.reason}</p>
        <p>{answer.stated}</p>
        <p className="aside">{answer.note}</p>
      </div>
    )
  }
  return (
    <div className="family absent">
      <h3>{readFamily(answer.family)}</h3>
      <p>{answer.question}</p>
      <p className="at">
        {answer.kind === 'withheld' ? 'rate not published' : 'not measurable'} —{' '}
        {answer.reason}
      </p>
      <p>{answer.stated}</p>
      <p className="aside">{answer.note}</p>
    </div>
  )
}

/**
 * One question this bench answered, with the rate beside its own denominator.
 *
 * The counts are set beside the rate and not under it: a figure an engineer pastes
 * into a customer's document travels as far as the line it is on, and a rate that
 * leaves its denominator behind is the over-claim this block replaces.
 */
function Answered({ answer }: { answer: AnsweredQuestion }) {
  return (
    <div className="family">
      <h3>{readFamily(answer.family)}</h3>
      <p>{answer.question}</p>
      <p>
        <span className="calls">{answer.rate}</span>
        <span className="kind">{answer.counts}</span>
      </p>
      <p>
        Interval: <strong>{answer.interval}</strong> at {answer.confidence}{' '}
        confidence, around this family’s rate and no other’s.
      </p>
      <p>
        Band: <strong>{answer.band}</strong> — {answer.bandReads}
      </p>
      {answer.limits.map((limit) => (
        <p className="aside" key={limit.identifier}>
          {limit.identifier}: these cases test one case within it. They do not test{' '}
          {limit.doesNotTest}.
        </p>
      ))}
    </div>
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
 * One errand, with the control that starts it.
 *
 * A `Link` and not a `button`, styled as the control it is: it navigates, and a
 * button that navigates is a control a keyboard and a screen reader are told the
 * wrong thing about. The lead card takes the filled treatment because it is the one
 * errand an operator with nothing registered can usefully do, which is a fact about
 * the order of the work rather than about the colour.
 */
function Card({ card }: { card: ConsoleDoes }) {
  return (
    <div className="card">
      <h3>{card.name}</h3>
      <p>{card.does}</p>
      <Link className={card.lead ? 'act lead' : 'act'} to={card.path}>
        {card.act}
      </Link>
    </div>
  )
}
