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
 * **Declining is always the easier answer.** It needs no identity, no reason and no
 * second click, and it is sent rather than withheld: the bench records the run as
 * *declined* by a person, which is a better record than the *unanswered* a closed
 * tab leaves behind, and answers with its own sentence saying that nothing was sent
 * to the target and nothing was spent.
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
  theFiguresPresented,
  type ConfirmationRequest,
} from './interrupt'
import {
  adaptiveReading,
  scoredReading,
  standing,
  stillGoing,
  type LayerReading,
  type Standing,
} from './progress'

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
  const [identity, setIdentity] = useState('')
  const [reason, setReason] = useState('')

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

  const request: ConfirmationRequest = confirmationRequest({
    status: progress?.status ?? '',
    figures,
    confirmed,
    identity,
    reason,
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
      <header>
        <p className="eyebrow">AgentAudit — run</p>
        <h1>{at === null ? 'Reading the run' : at.heading}</h1>
        <p className="steps">
          Run {runId}
          {at?.inFlight ? ` — asked again every ${POLL_SECONDS} seconds` : null}
        </p>
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
          held={at.statement}
          request={request}
          confirmed={confirmed}
          setConfirmed={setConfirmed}
          identity={identity}
          setIdentity={setIdentity}
          reason={reason}
          setReason={setReason}
          busy={busy}
          confirm={confirm}
          decline={() => void answer(declineRequest(identity, reason))}
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
  /** The bench's own sentence about the halt, carried unedited. */
  held: string
  request: ConfirmationRequest
  confirmed: boolean
  setConfirmed: (confirmed: boolean) => void
  identity: string
  setIdentity: (identity: string) => void
  reason: string
  setReason: (reason: string) => void
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
  held,
  request,
  confirmed,
  setConfirmed,
  identity,
  setIdentity,
  reason,
  setReason,
  busy,
  confirm,
  decline,
}: InterruptProps) {
  const view = figures === null ? null : interruptView(figures)
  return (
    <>
      <section>
        <h2>What this run will cost, before any of it is spent</h2>
        {/* The bench's own account of the halt, above this screen's. */}
        <p>{held}</p>
        {view === null ? (
          <p role="alert">{FIGURES_NOT_HELD}</p>
        ) : (
          <>
            <p>{view.nothingSent}</p>
            <dl className="figures">
              {view.figures.map((figure) => (
                <div className="figure" key={figure.layer}>
                  <dt>{figure.label}</dt>
                  <dd>
                    <span className="calls">{figure.calls} calls</span>
                    <span className="money">{figure.cost}</span>
                    <span className="kind">{figure.kind}</span>
                    <span className="aside">{figure.basis}</span>
                    <span className="aside">{figure.spends}</span>
                    <span className="aside">
                      Enforced against this layer alone: {figure.ceiling} calls. The
                      run aborts rather than exceed it.
                    </span>
                  </dd>
                </div>
              ))}
            </dl>
            <p className="aside">{view.unblended}</p>
          </>
        )}
      </section>

      <section>
        <h2>Your answer</h2>
        {view === null ? null : (
          <>
            <label>
              Who is confirming
              <input
                value={identity}
                onChange={(event) => setIdentity(event.target.value)}
                placeholder="recorded against the ceiling this run is held to"
              />
            </label>
            <label className="declaration">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              <span className="wording">
                I have read both figures and I am spending them. The scored layer
                will attack this endpoint at the exact figure above; the adaptive
                layer may spend up to its ceiling.
              </span>
            </label>
          </>
        )}
        <label>
          Why, if you are declining
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="a figure somebody refused is evidence the display works"
          />
        </label>
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
        {request.kind === 'withheld' ? (
          <div className="blocked">
            <h3>The run is still holding, and this is why</h3>
            <ul>
              {request.missing.map((missing) => (
                <li key={missing}>{missing}</li>
              ))}
            </ul>
          </div>
        ) : null}
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
  return (
    <>
      <section>
        <p>
          <strong>{at.name}</strong>
        </p>
        <p>{at.statement}</p>
        {/*
          The run's own sentence as well, when the standing's is a different one:
          a transport failure carries the named outcome, and the run carries where
          it was when the endpoint stopped answering. Neither is the other.
        */}
        {progress.statement === at.statement ? null : (
          <p className="aside">{progress.statement}</p>
        )}
        {at.episode ? (
          <p className="consequence">
            The episode: <strong>{at.episode.outcome}</strong>. {at.episode.note}
          </p>
        ) : null}
        {at.notASecurityResult ? (
          <p className="aside">{at.notASecurityResult}</p>
        ) : null}
      </section>

      <section>
        <h2>Where the run has got to, one layer at a time</h2>
        <div className="layers">
          <LayerPanel reading={scoredReading(progress.scored)} />
          <LayerPanel reading={adaptiveReading(progress.adaptive)} />
        </div>
        <p className="aside">
          Two positions in two sets of units, and two figures for what has been
          spent. There is no third figure here: an attempt and a turn are not the
          same thing, so nothing on this screen adds them.
        </p>
      </section>

      {progress.report ? (
        <section>
          <h2>The report</h2>
          <p>{progress.report.statement}</p>
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
          <p className="aside">
            All three, saved under the names they arrive with: a payload without the
            signature beside it is the part that cannot be checked on its own.
          </p>
        </section>
      ) : null}
    </>
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
      <p>{reading.statement}</p>
      <p>
        <strong>{reading.callsSpent} calls</strong> spent in this layer.
      </p>
    </div>
  )
}
