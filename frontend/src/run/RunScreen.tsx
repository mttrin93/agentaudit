/**
 * The run screen: an interrupt that blocks, and then progress read per layer.
 *
 * Two things live here because they are two halves of one moment. Until somebody
 * answers, this screen *is* the halt — the graph is paused at a real `interrupt()`
 * against a checkpointer and the run cannot proceed, so the screen has nothing to
 * show but the two figures and the two answers to them. After a yes it is the
 * window on a run that takes minutes, polling `GET /runs/{id}` and reporting the
 * scored layer and the adaptive layer separately.
 *
 * **The screen holding rather than merely asking is the whole content of the
 * control** (spec, §31). So the confirmation is not a checkbox at the foot of a
 * form somebody scrolls past: it is the only screen there is while a run is
 * waiting, and the button that sends the run to the target is unreachable until
 * `confirmationRequest` says every part of the confirmation was given. That
 * function is the one path to a `confirmed: true`, and the button re-asks it on the
 * click as well as for the disabled state — a disabled button is a hint, and this
 * is not a place for hints.
 *
 * **Declining is always the easier answer.** It needs no second click and it is sent
 * rather than withheld: the bench records the run as *declined* by a person, which is
 * a better record than the *unanswered* a closed tab leaves behind, and answers with
 * its own sentence saying that nothing was sent to the target and nothing was spent.
 * Neither answer asks for anything typed any more — this screen has no fields on it,
 * and the name both answers are recorded under is the one that attested the
 * registration, carried from it in `sessionStorage`.
 *
 * **Nothing on this screen adds the layers up.** The figures come from
 * `interrupt.ts` and the readings from `progress.ts`, and neither builds a value
 * that spans the two; the two panels below are side by side and carry two spends,
 * two positions in two sets of units, and no third number. A blended figure would
 * hide which half of the run is spending the operator's budget (ADR-0007), and an
 * adaptive quantity that reached a scored one would be the invariant ADR-0010 is
 * about.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  REGISTRATION_REFUSED,
  answerTheInterrupt,
  runProgress,
  type ApprovalBody,
  type RunEstimate,
  type RunProgress,
} from '../api/bench'
import {
  FIGURES_NOT_HELD,
  confirmationRequest,
  declineRequest,
  interruptView,
  whoAttested,
  theFiguresPresented,
  type ConfirmationRequest,
} from './interrupt'
import {
  adaptiveReading,
  familyRows,
  hasLength,
  payloads,
  scoredReading,
  standing,
  stillGoing,
  type FamilyRow,
  type LayerReading,
  type PayloadRow,
  type Standing,
} from './progress'
// The two verdict colours and the two words beside them, from the one place they are
// declared. A second copy here would be a second answer to *which green is resisted*,
// and the two would only have to disagree once.
import { ANSWER_KEYS } from '../console/gaterun'

const POLL_SECONDS = 2
/**
 * How often the run is asked where it has got to.
 *
 * The frontend polls because the spec says it does. Two seconds because the thing
 * being watched is a position moving through 181 attempts over minutes: often
 * enough that the attempt on screen is the attempt in flight, rare enough that a
 * screen left open is not a load on the bench that is attacking somebody's
 * endpoint.
 */

export function RunScreen() {
  const { runId = '' } = useParams()
  const [progress, setProgress] = useState<RunProgress | null>(null)
  const [unavailable, setUnavailable] = useState('')
  const [refused, setRefused] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)

  /**
   * The figures this run was estimated at, read once from the handoff.
   *
   * Once rather than on every render, and never re-read after an answer: what a
   * person confirmed has to be what they were looking at, and a value that could
   * change under the control would make the confirmation about something else.
   */
  const [figures] = useState<RunEstimate | null>(() =>
    theFiguresPresented(sessionStorage, runId),
  )

  const read = useCallback(async (): Promise<RunProgress | null> => {
    try {
      const now = await runProgress(runId)
      setProgress(now)
      setUnavailable('')
      return now
    } catch (unknown: unknown) {
      setUnavailable(`${unknown}`)
      return null
    }
  }, [runId])

  useEffect(() => {
    let current = true
    let timer: ReturnType<typeof setInterval> | undefined
    const tick = async () => {
      const now = await read()
      // Stopped for good, so stop asking: a run that ended is a run whose screen
      // has nothing left to learn from the bench.
      if (current && now && !stillGoing(now.status) && timer !== undefined) {
        clearInterval(timer)
      }
    }
    timer = setInterval(() => void tick(), POLL_SECONDS * 1000)
    void tick()
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [read])

  /**
   * The name the confirmation is recorded under, from the registration that made
   * this run. No screen asks for it again.
   */
  const identity = whoAttested(sessionStorage, runId)

  const request: ConfirmationRequest = confirmationRequest({
    status: progress?.status ?? '',
    figures,
    confirmed,
    identity,
    // No field asks for one. A decline carries `declineRequest`'s own sentence and a
    // confirmation carries none, which is what a screen with no reason box means.
    reason: '',
  })

  const answer = async (body: ApprovalBody) => {
    setBusy(true)
    const outcome = await answerTheInterrupt(runId, body)
    setBusy(false)
    setRefused(outcome.kind === 'answered' ? '' : outcome.statement)
    await read()
  }

  const confirm = () => {
    // Asked again on the click. The disabled state is a courtesy; this is the
    // check, and it is the only line in this app that can put a `confirmed: true`
    // on the wire.
    if (request.kind !== 'ready') {
      return
    }
    void answer(request.body)
  }

  const at = progress === null ? null : standing(progress)
  return (
    <main className="screen">
      {/*
        The heading, and nothing over or under it.

        The eyebrow said *AgentAudit — run*: the app's name is in the rail and the
        rail's current row says which screen this is. The line under it carried the
        run's id and the poll interval — the id is in the address bar of the page it
        addresses, and the interval is a fact about this client, not about the run.
        What the run is doing is the heading, and the section under it says it again
        in the bench's own words.
      */}
      <header>
        <h1>{at === null ? 'Reading the run' : at.heading}</h1>
      </header>

      {unavailable ? (
        <section className="refusal" role="alert">
          <h2>The bench did not say where this run is</h2>
          <p>{unavailable}</p>
        </section>
      ) : null}

      {refused ? (
        <section className="refusal" role="alert">
          <h2>That answer was not taken</h2>
          <p>{refused}</p>
        </section>
      ) : null}

      {at?.kind === 'holding' ? (
        <TheInterrupt
          figures={figures}
          request={request}
          confirmed={confirmed}
          setConfirmed={setConfirmed}
          busy={busy}
          confirm={confirm}
          decline={() => void answer(declineRequest(identity, ''))}
        />
      ) : null}

      {at !== null && progress !== null && at.kind !== 'holding' ? (
        <Progress at={at} progress={progress} runId={runId} />
      ) : null}

      {progress?.status === REGISTRATION_REFUSED ? (
        <p>
          <Link to={`/register?refused=${encodeURIComponent(runId)}`}>
            Re-plant the nonce and register again
          </Link>
        </p>
      ) : null}
    </main>
  )
}

interface InterruptProps {
  figures: RunEstimate | null
  request: ConfirmationRequest
  confirmed: boolean
  setConfirmed: (confirmed: boolean) => void
  busy: boolean
  confirm: () => void
  decline: () => void
}

/**
 * The halt, as the screen a run cannot get past on its own.
 *
 * The two figures come first because they are what is being consented to, and the
 * control is underneath them rather than beside them: the order is the argument.
 * When this app is not holding the figures there is no control at all — only the
 * sentence saying why, and the answer that spends nothing.
 */
function TheInterrupt({
  figures,
  request,
  confirmed,
  setConfirmed,
  busy,
  confirm,
  decline,
}: InterruptProps) {
  const view = figures === null ? null : interruptView(figures)
  return (
    <>
      <section>
        {/*
          The two figures, and nothing over them.

          *What this run will cost, before any of it is spent* was the `h2` here,
          under an `h1` saying the run was holding at its interrupt. It is the `h1`
          now — a screen that shows two numbers and takes a yes has one thing to say
          at the top, and that the run is holding is what the screen being here at
          all means. Three paragraphs went with the heading: the bench's own sentence
          about the halt, this screen's sentence saying nothing has been sent, and the
          one saying why there is no third figure. The `FIGURES_NOT_HELD` alert stays,
          because it is the only thing that explains a screen with no figures and no
          confirmation on it.
        */}
        {view === null ? (
          <p role="alert">{FIGURES_NOT_HELD}</p>
        ) : (
          <dl className="figures">
            {view.figures.map((figure) => (
              <div className="figure" key={figure.layer}>
                <dt>{figure.label}</dt>
                <dd>
                  <span className="calls">{figure.calls} calls</span>
                  <span className="money">{figure.cost}</span>
                  <span className="kind">{figure.kind}</span>
                  <span className="aside">{figure.basis}</span>
                  {/* What the calls are and what the limit is, in one paragraph:
                      the two were a line apart and they are one thought — this is
                      what this layer spends, and this is what it may not exceed. */}
                  <span className="aside">
                    {figure.spends} Enforced against this layer alone:{' '}
                    {figure.ceiling} calls. The run aborts rather than exceed it.
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {/*
        The answer, and no heading over it.

        *Your answer* named a section holding one tick and two buttons, under a
        heading that had just said what the figures are. *Who is confirming* went with
        it: the name is the one from the registration that made this run, carried in
        `sessionStorage` beside the figures, so the bench's `confirmed by <name>` is
        still a name and nobody types it twice.
      */}
      <section>
        {view === null ? null : (
          <label className="declaration">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span className="wording">
              I have read both figures and I am spending them. The scored layer will
              attack this endpoint at the exact figure above; the adaptive layer may
              spend up to its ceiling.
            </span>
          </label>
        )}
        <div className="walk">
          <button type="button" onClick={decline} disabled={busy}>
            {busy ? 'Answering…' : 'Decline — send nothing, spend nothing'}
          </button>
          {view === null ? null : (
            <button
              type="button"
              className="primary"
              onClick={confirm}
              disabled={busy || request.kind !== 'ready'}
            >
              {busy ? 'Answering…' : 'Confirm both figures and start the run'}
            </button>
          )}
        </div>
      </section>
    </>
  )
}

/**
 * The run in flight or the run that stopped, per layer.
 *
 * The standing comes first — what the run is doing, or the named thing that
 * stopped it — and the two panels under it are two panels rather than one table
 * with a total row, which is the arrangement a total gets added to.
 */
function Progress({
  at,
  progress,
  runId,
}: {
  at: Standing
  progress: RunProgress
  runId: string
}) {
  /*
   * The standing's own status word and sentence are not drawn.
   *
   * They were the two lines under the heading — *running*, and *confirmed by X: the
   * suite is running in the background, under the ceiling that was confirmed* — which
   * is the heading again, plus the name of whoever answered the interrupt and the
   * promise the interrupt already made.
   *
   * What is kept is everything the heading does *not* say: the run's own sentence
   * when it differs from the standing's, which is how a transport failure reports
   * where the run was when the endpoint stopped answering; the episode a ceiling cut
   * short; and the sentence saying the stop was not a result about the target. The
   * section is drawn only when one of them has something in it.
   */
  const alsoSaid = progress.statement === at.statement ? '' : progress.statement
  const anythingElse = alsoSaid || at.episode !== null || at.notASecurityResult
  return (
    <>
      {anythingElse ? (
        <section>
          {alsoSaid ? <p className="aside">{alsoSaid}</p> : null}
          {at.episode ? (
            <p className="consequence">
              The episode: <strong>{at.episode.outcome}</strong>. {at.episode.note}
            </p>
          ) : null}
          {at.notASecurityResult ? (
            <p className="aside">{at.notASecurityResult}</p>
          ) : null}
        </section>
      ) : null}

      <section>
        <h2>Where the run has got to, one layer at a time</h2>
        <div className="layers">
          <LayerPanel reading={scoredReading(progress.scored)} />
          <LayerPanel reading={adaptiveReading(progress.adaptive)} />
        </div>

        {/*
          The same two readings the gate screen draws while a gate run goes, over one
          target instead of three agents: how far each family has got, and how each is
          answering. Both are drawn against the same denominator — this run's plan, one
          family at a time — so no length on the right can outrun the one for the same
          family on the left, and what is left of either bar is what has not been
          attempted yet.
        */}
        <div className="watching">
          <div className="progress">
            <h3>How far each family has got</h3>
            {/* One key, because one target made these attempts. It earns its line
                anyway: nothing on this bench is carried by hue alone, and it holds
                the six rows here level with the six beside them. */}
            <p className="legend">
              <span className="key">
                <span className="swatch scored" aria-hidden="true" />
                attempted
              </span>
            </p>
            {familyRows(progress).map((row) => (
              <FamilyBar row={row} key={row.family} />
            ))}
          </div>
          <div className="answering">
            <h3>How each family is answering</h3>
            <p className="legend">
              {ANSWER_KEYS.map((key) => (
                <span className="key" key={key.answer}>
                  <span className={`swatch ${key.accent}`} aria-hidden="true" />
                  {key.answer}
                </span>
              ))}
            </p>
            {familyRows(progress).map((row) => (
              <FamilyAnswer row={row} key={row.family} />
            ))}
          </div>
        </div>

        {/* The call it is on, under both columns and at the width of the page: an
            exchange is a paragraph of somebody's traffic and it reads badly in half
            a column. */}
        <div className="payloads">
          <h3>The last call</h3>
          {payloads(progress).length === 0 ? (
            <p className="aside">
              Nothing has come back yet. The exchange appears here as it does.
            </p>
          ) : (
            payloads(progress).map((one) => <Payload one={one} key={one.key} />)
          )}
        </div>
      </section>

      {progress.report ? (
        <section>
          {/*
            The three artefacts, as three links and their names.

            `report.statement` is not drawn: it named the three files and said what
            `scripts/verify.py` does with a directory containing them, which is a
            paragraph above a list of exactly those three links. The sentence is still
            on the wire and the report screen is where it is read.
          */}
          <h2>The report</h2>
          <p className="consequence">
            <Link to={`/runs/${runId}/report`}>Read the report</Link> — the finding,
            the per-family figures and whether the artefact verifies.
          </p>
          <ul>
            <li>
              <a href={progress.report.path}>the signed payload</a>
            </li>
            <li>
              <a href={progress.report.rendering}>the rendered view</a>
            </li>
            <li>
              <a href={progress.report.signature}>the detached signature</a>
            </li>
          </ul>
        </section>
      ) : null}
    </>
  )
}

/**
 * One family, and how much of its work is done: one bar over its own denominator.
 *
 * The count beside the name is the two figures the bar is drawn from, so the length
 * is checkable rather than believable. A family the plan dropped has no bar at all —
 * an empty track over a denominator of zero reads as one that has not started yet,
 * and this one is never going to.
 */
function FamilyBar({ row }: { row: FamilyRow }) {
  return (
    <div className="family-bar">
      <p className="family-name">
        <span className="name">{row.name}</span>
        <span className="count">
          {row.notRun ? 'not run' : `${row.attempted} / ${row.of}`}
        </span>
      </p>
      {/* The empty track is drawn for a family that is not run as well, so the six
          rows here and the six beside them stay level with each other. Which of the
          two kinds of empty it is, is the word in the slot above — `not run` rather
          than `0 / 30` — and the reason is under both columns, said once. */}
      <div className="track">
        <span className="segment scored" style={{ width: row.done }} />
      </div>
    </div>
  )
}

/**
 * One family, and how it is answering: one bar, green into red, over the same
 * denominator.
 *
 * The one place this screen colours a verdict, which is why the two colours are named
 * in words above the six. It is a live reading of a run and not a measurement: what is
 * left of the bar is what has not been attempted yet, and the rate — with its interval
 * and its band — is on the report the run signs (ADR-0005).
 *
 * No figure beside the name. The slot to its right holds `20 / 30` on the bar to the
 * left, and a second pair of numbers in the same place meaning something else is a
 * fraction a reader would read as that one.
 */
function FamilyAnswer({ row }: { row: FamilyRow }) {
  return (
    <div className="family-bar">
      <p className="family-name">
        <span className="name">{row.name}</span>
      </p>
      {/*
        Only the segments that have a length. Where both are there the CSS crosses one
        colour into the other, and it finds the join by asking whether the green has a
        red after it — a `0%` span left in the markup would answer yes.
      */}
      <div className="track">
        {hasLength(row.held) ? (
          <span className="segment resisted" style={{ width: row.held }} />
        ) : null}
        {hasLength(row.broke) ? (
          <span className="segment succeeded" style={{ width: row.broke }} />
        ) : null}
      </div>
    </div>
  )
}

/**
 * One attempt: what the bench sent, and what the target answered.
 *
 * The two halves are set apart the way an exchange reads — the attack, then the reply
 * — and nothing here is coloured by its verdict: *succeeded* and *resisted* are the
 * two answers this bench counts, and a green one beside a red one is the severity
 * scale ADR-0005 exists to refuse. Which it was is in the bar above, where the two
 * words are printed beside the two colours.
 */
function Payload({ one }: { one: PayloadRow }) {
  return (
    <div className="payload">
      <div className="turn sent">
        <Speaker />
        <p className="bubble">{one.sent}</p>
      </div>
      <div className="turn reply">
        <p className="bubble">{one.reply}</p>
        <Speaker />
      </div>
    </div>
  )
}

/**
 * One speaker's mark: the same drawing on both turns, in that turn's own colour.
 *
 * The same glyph deliberately. Both ends of this exchange are agents — the bench's
 * attacker and the target answering it — and drawing them as two different creatures
 * would say something about the pair that is not true. What differs is which side of
 * the card the turn sits on, which is the order the two happened in: the attack, then
 * the answer to it.
 *
 * Hand-drawn at 16px in `currentColor`, the rail's own idiom, so the colour comes off
 * the stylesheet and no dependency arrives to draw one glyph.
 */
function Speaker() {
  return (
    <svg
      className="speaker"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="8" cy="1.9" r="0.85" />
      <path d="M8 2.75V4.6" />
      <rect x="3" y="4.6" width="10" height="8.4" rx="2.2" />
      <path d="M1.4 8.2v2.2M14.6 8.2v2.2" />
      <path d="M6.3 8.1v1.3M9.7 8.1v1.3" />
      <path d="M6.5 11.3h3" />
    </svg>
  )
}

/** One layer, in that layer's own units. Never a row in a shared table. */
function LayerPanel({ reading }: { reading: LayerReading }) {
  return (
    <div className="layer">
      <h3>{reading.title}</h3>
      {reading.at === null ? (
        <p className="at">not started</p>
      ) : (
        <dl className="at">
          {reading.units.map((unit, index) => (
            <div key={unit}>
              <dt>{unit}</dt>
              <dd>{reading.at?.[index]}</dd>
            </div>
          ))}
        </dl>
      )}
      {/*
        The bench's sentence about the position is not drawn here, and the `dl` above
        is the reason: *family wrongful_commitment, case wrongful-commitment-003,
        attempt 10: the position the scored layer has reached* is the three values
        beside it, read out in prose. The field stays on the reading because the gate
        screen draws it where there is no position to draw — a layer the run has not
        reached says so in a sentence, and there the sentence is the only thing there
        is.
      */}
      <p>
        <strong>{reading.callsSpent} calls</strong> spent in this layer.
      </p>
    </div>
  )
}
