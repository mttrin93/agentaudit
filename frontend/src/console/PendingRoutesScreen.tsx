/**
 * The routes the attacker found, and the one thing an operator does with them.
 *
 * The console's direction is verbs and not metrics, and this page's verb is *decide
 * these*. Markup and nothing else, on the gate screen's division: every piece of
 * state, every effect and every request lives in `usePendingRoutes`, the blocks are
 * components of their own, and what is left here is the order they appear in and
 * which of them a stage draws.
 *
 * **The control is above the queue and the queue is the page.** The errand is to
 * decide these, so the affordance that does it is not underneath the list it acts
 * on — that is the arrangement the gate screen arrived at after a finished gate run
 * looked like a screen that had lost its control.
 *
 * **Three absences are three different sentences.** A bench that did not answer for
 * its queue, a queue that holds nothing, and a page that has not read yet are
 * distinguished, because none of them is a failure and an operator acting on the
 * wrong one acts wrongly: an empty queue is a reading about the attacker (ADR-0011).
 *
 * **Nothing on this page is a rate, an interval, a band or a `D`.** A pending route
 * is not an attempt and reaches no denominator (ADR-0010); the `D` the bar measures
 * belongs to the case and never to the target the route beat (ADR-0012). The value
 * this screen draws has nowhere to put one, and `pending.test.ts` scans it.
 */

import { TheControl, TheQueue } from './PendingQueue'
import {
  TheAttestation,
  TheEstimate,
  TheMeasurement,
} from './PendingDeciding'
import { usePendingRoutes } from './usePendingRoutes'
import { measurementEstimateView, progressRows } from './pending'
import { useArrivalFocus, useScreenTitle } from './announce'
import { PENDING_ROUTES } from './rail'

export function PendingRoutesScreen() {
  const {
    askTheBench,
    attesting,
    begin,
    busy,
    choose,
    confirm,
    confirmed,
    decline,
    held,
    ourMeasurementIsGoing,
    reading,
    refused,
    request,
    selected,
    setAttesting,
    setConfirmed,
    setStage,
    setStep,
    stage,
    start,
    started,
    statements,
    step,
    view,
  } = usePendingRoutes()

  useScreenTitle(PENDING_ROUTES)
  const heading = useArrivalFocus(PENDING_ROUTES)
  return (
    <main className="screen">
      <header>
        <h1 ref={heading} tabIndex={-1}>
          {PENDING_ROUTES}
        </h1>
      </header>

      {/* Assertive (ADR-0080): the operator pressed the control that starts a
          measurement and nothing started. Everything else on this page that reports
          a silence is polite, because the rest of it is read rather than pressed. */}
      {refused ? (
        <section className="refusal" role="alert">
          <h2>That was not taken</h2>
          <p>{refused}</p>
          <p className="aside">
            Nothing about this is a measurement that half happened: a refusal at this
            point means nothing was sent to a reference agent, no case record was
            written, and every route named is still pending with its payload.
          </p>
        </section>
      ) : null}

      {/* Polite: read on arrival, answering nothing anybody pressed (ADR-0080). */}
      {held.unavailable ? (
        <section>
          <h2>This bench did not answer for its queue</h2>
          <div className="citation uncited" role="status">
            <h3>The routes awaiting a decision could not be read</h3>
            <p>{held.unavailable}</p>
            <p className="aside">
              Not the same fact as a queue with nothing in it: what is unknown here
              is what the bench would have listed, and nothing on this page should be
              read as the attacker having found nothing.
            </p>
          </div>
        </section>
      ) : view === null ? (
        <section>
          <p className="aside">Reading the routes awaiting a decision…</p>
        </section>
      ) : null}

      {stage === 'attesting' ? (
        <TheAttestation
          statements={statements}
          step={step}
          attesting={attesting}
          declare={(changed) => setAttesting({ ...attesting, ...changed })}
          back={() => {
            if (step === 0) {
              setStage('idle')
              return
            }
            setStep(step - 1)
          }}
          forward={() => {
            if (step + 1 < statements.length) {
              setStep(step + 1)
              return
            }
            void start()
          }}
          missing={request.kind === 'blocked' ? request.missing : []}
          busy={busy}
          routes={selected.length}
        />
      ) : null}

      {stage === 'estimate' && started !== null ? (
        <TheEstimate
          view={measurementEstimateView(started.estimate)}
          confirmed={confirmed}
          setConfirmed={setConfirmed}
          confirm={confirm}
          decline={decline}
          busy={busy}
        />
      ) : null}

      {view === null ? null : (
        <TheControl
          control={view.control}
          selected={selected}
          begin={begin}
          going={ourMeasurementIsGoing}
          ask={askTheBench}
        />
      )}

      {stage === 'watching' && reading !== null ? (
        <TheMeasurement
          status={reading.status}
          statement={reading.statement}
          rows={progressRows(reading)}
          lines={reading.lines}
        />
      ) : null}

      {view === null ? null : (
        <TheQueue
          rows={view.rows}
          empty={view.empty}
          selected={selected}
          choose={choose}
          statement={view.statement}
        />
      )}
    </main>
  )
}
