/**
 * The pending-routes page's state, so that the page itself is markup.
 *
 * The division `useGateRun` made: everything the browser has to hold to read the
 * queue and decide part of it is here, and `PendingRoutesScreen` draws it and
 * decides nothing. The seam beside this one is `pending.ts`, which is the pure
 * transformation with its tests; this is the piece that could not go there, because
 * it is the part that talks to the bench and remembers what it said.
 *
 * **Three absences are three different sentences**, and that is why this holds the
 * queue, the measurement in view and the selection separately. A bench that did not
 * answer for its queue, a bench whose queue is empty, and a page that has not read
 * yet are three facts and none of them is an error — the middle one is a reading
 * about the attacker (ADR-0011) and it is the one an empty screen would destroy.
 *
 * **Whether a measurement may start is the bench's answer and never this hook's.**
 * It depends on a lease on the case library that no browser can see, so it is asked
 * — and asked again at the one moment it can have changed, when a measurement this
 * hook was watching stops.
 *
 * **The measurement in view is read on arrival and not only after one is started.**
 * The bench keeps its measurements in memory for the life of the process, so the
 * most recent one is how a row that was admitted names the record it became after a
 * reload: `entered_as` is on the measurement's progress row, and the queue's own row
 * carries the reason. Joined rather than parsed (`queueRows`).
 */

import { useCallback, useEffect, useState } from 'react'

import type {
  ApprovalBody,
  MeasurementReading,
  MeasurementStarted,
  PendingRouteQueue,
} from '../api/bench'
import {
  answerTheMeasurementsInterrupt,
  measurementReading,
  pendingRoutes,
  startMeasurement,
} from '../api/bench'
import type { Attesting } from './pending'
import {
  ALREADY_IN_FLIGHT,
  MEASUREMENT_STATEMENTS,
  measurementConfirmation,
  measurementDecline,
  measurementRequest,
  nothingAttested,
  queueView,
  stillMeasuring,
} from './pending'

/** How often a measurement in flight is asked where it has got to. */
const POLL_SECONDS = 2

/**
 * How many times *may another start yet* is re-asked after a measurement settles.
 *
 * `useGateRun`'s number and its reasoning: the library's lease is released after the
 * record is settled, and how long after is not a screen's to know — the write into
 * the library and the queue's own decisions land in that gap. Thirty asks two
 * seconds apart is a minute of patience, and past a minute the refusal is somebody
 * else's run holding the library, which is a true answer and belongs on the page.
 */
const LEASE_ASKS = 30

/** What this page is holding: the queue, or the reason it has none of it. */
interface Held {
  queue: PendingRouteQueue | null
  unavailable: string
}

const NOTHING_YET: Held = { queue: null, unavailable: '' }

/**
 * Where the operator is in deciding some of them.
 *
 * Four stages, and the first is the page at rest. A union rather than three
 * booleans because they are exclusive: an operator cannot be reading the statements
 * and confirming the figures at once, and a page that allowed both would have two
 * answers to *what am I consenting to*.
 */
type Stage = 'idle' | 'attesting' | 'estimate' | 'watching'

/** The queue, the selection, one measurement, and the halt in front of it. */
export function usePendingRoutes() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)
  const [stage, setStage] = useState<Stage>('idle')
  const [chosen, setChosen] = useState<readonly string[]>([])
  const [attesting, setAttesting] = useState<Attesting>(nothingAttested)
  const [step, setStep] = useState(0)
  const [started, setStarted] = useState<MeasurementStarted | null>(null)
  const [reading, setReading] = useState<MeasurementReading | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [refused, setRefused] = useState('')
  const [busy, setBusy] = useState(false)

  /**
   * The queue, and whether a measurement may start over it — asked, never inferred.
   *
   * Memoised for `useGateRun`'s reason: two `useEffect` dependency arrays name this
   * and one of them drives a poll, so an unmemoised reader would have this page
   * asking a bench that is holding a library lease several times a second.
   */
  const readTheQueue = useCallback(async () => {
    try {
      return { queue: await pendingRoutes(), unavailable: '' }
    } catch (unknown: unknown) {
      return { queue: null, unavailable: `${unknown}` }
    }
  }, [])

  useEffect(() => {
    let current = true
    const read = async () => {
      const answered = await readTheQueue()
      if (!current) {
        return
      }
      setHeld(answered)
      // The most recent measurement this bench holds, so that an admitted row can
      // name the record it became after a reload. A queue with no measurement over
      // it is the ordinary case and not a failure, so nothing is said about it.
      const recent = answered.queue?.measurements[0]
      if (recent === undefined) {
        return
      }
      try {
        const last = await measurementReading(recent.measurement_id)
        if (current) {
          setReading(last)
        }
      } catch {
        // A measurement the bench will not report on leaves the queue exactly as it
        // is: every row still carries its own state and the deciding surface's own
        // reason, and what is missing is the name of a file. Silent rather than an
        // alarm over a page that is otherwise complete.
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [readTheQueue])

  const measurementId = started?.measurement_id ?? ''

  useEffect(() => {
    if (stage !== 'watching' || !measurementId) {
      return
    }
    let current = true
    let timer: ReturnType<typeof setInterval> | undefined
    const tick = async () => {
      try {
        const now = await measurementReading(measurementId)
        if (!current) {
          return
        }
        setReading(now)
        if (stillMeasuring(now.status)) {
          return
        }
        if (timer !== undefined) {
          clearInterval(timer)
        }
        // Stopped for good, so ask the bench the question this measurement just
        // changed: the queue now holds a decision for every route it answered, and
        // the ones it could not answer are still pending. Asked again rather than
        // assumed, and asked more than once because the lease outlives the status by
        // a moment — only that one refusal is waited out, since the other four are
        // facts about how this bench was built.
        for (let asked = 0; asked < LEASE_ASKS; asked += 1) {
          const answered = await readTheQueue()
          if (!current) {
            return
          }
          setHeld(answered)
          const measure = answered.queue?.measure
          if (
            measure === undefined ||
            measure.available ||
            measure.refusal !== ALREADY_IN_FLIGHT
          ) {
            return
          }
          await new Promise((wait) => setTimeout(wait, POLL_SECONDS * 1000))
        }
      } catch (unknown: unknown) {
        if (current) {
          setRefused(`${unknown}`)
        }
      }
    }
    timer = setInterval(() => void tick(), POLL_SECONDS * 1000)
    void tick()
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [measurementId, stage, readTheQueue])

  const view = held.queue === null ? null : queueView(held.queue, reading)

  /**
   * The routes the operator has selected, narrowed to the ones still selectable.
   *
   * Narrowed here rather than trusted from the checkbox, because the queue is
   * re-read while this page is open: a route somebody else decided between the read
   * and the press is a route this page may not put to the bar, and the bench would
   * refuse it by name. Nothing is silently dropped that a redrawn row does not
   * already show as decided.
   */
  const selected = view === null
    ? []
    : chosen.filter((route) =>
        view.rows.some((row) => row.route === route && row.chooseable),
      )

  const choose = (route: string, taken: boolean) => {
    setChosen((before) =>
      taken
        ? [...before.filter((one) => one !== route), route]
        : before.filter((one) => one !== route),
    )
  }

  /** Read the queue again, on request. A read: nothing here starts anything. */
  const askTheBench = () => {
    void readTheQueue().then(setHeld)
  }

  const begin = () => {
    setRefused('')
    setStep(0)
    setAttesting(nothingAttested())
    setStage('attesting')
  }

  const request = measurementRequest(attesting, selected)

  /**
   * Start the measurement, or refuse to.
   *
   * The guard is asked again here rather than trusted from the disabled state: this
   * is the one line on this page that can send three reference agents on two models
   * per route and write into the case library, and the function that decides it is
   * the one that will not build a body from an incomplete declaration or an empty
   * selection.
   */
  const start = async () => {
    if (request.kind !== 'ready') {
      return
    }
    setBusy(true)
    const outcome = await startMeasurement(request.body)
    setBusy(false)
    if (outcome.kind === 'started') {
      setStarted(outcome.measurement)
      setConfirmed(false)
      setStage('estimate')
      return
    }
    setRefused(outcome.statement)
    setStage('idle')
  }

  const answer = async (body: ApprovalBody) => {
    setBusy(true)
    const outcome = await answerTheMeasurementsInterrupt(measurementId, body)
    setBusy(false)
    if (outcome.kind === 'answered') {
      setStarted(outcome.measurement)
      setRefused('')
      setStage(body.confirmed ? 'watching' : 'idle')
      return
    }
    setRefused(outcome.statement)
  }

  /**
   * Confirm the estimate, through the one guard that can build a yes.
   *
   * Asked again here rather than trusted from the checkbox, for the reason `start`
   * re-asks its own guard: this is the line that spends.
   */
  const confirm = () => {
    const confirmation = measurementConfirmation(
      started?.status ?? '',
      confirmed,
      attesting.identity,
    )
    if (confirmation.kind !== 'ready') {
      return
    }
    void answer(confirmation.body)
  }

  /** The answer that spends nothing, sent rather than withheld. */
  const decline = () => {
    void answer(measurementDecline(attesting.identity))
  }

  /**
   * Whether a measurement this page started is on the wire right now.
   *
   * Read off the reading rather than off the stage alone, so it comes back to
   * `false` the moment the measurement settles while the progress stays on the
   * page: the stage remains `watching` because that is what the operator is looking
   * at, and it is the *measurement* that has stopped, not the page.
   *
   * **`watching` and not `stage !== 'idle'`**, which is the shape this started as
   * and was wrong: an operator part-way through the three statements has started
   * nothing, and the sentence that used to appear beside the greyed control said a
   * lease was being held on the case library. A page may not state a spend-relevant
   * fact that is false. What greys the control while the walk is open is `walking`
   * below, which claims nothing.
   */
  const ourMeasurementIsGoing =
    stage === 'watching' && (reading === null || stillMeasuring(reading.status))

  return {
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
    statements: MEASUREMENT_STATEMENTS,
    step,
    view,
    /** Whether the operator is part-way through starting one. Not a claim that
     * anything has been sent — `ourMeasurementIsGoing` is that claim. */
    walking: stage !== 'idle',
  }
}
