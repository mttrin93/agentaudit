/**
 * `GET /pending-routes` and the measurement that decides them — the queue, from a
 * browser.
 *
 * Its own module in #14's split by API area, and a third family beside `runs` and
 * `gateruns` for the reason the backend gives it one: a run produces rates about
 * somebody's agent, a gate run produces a decision about this bench, and deciding a
 * pending route produces a decision about **a case**
 * ([ADR-0105](../../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)
 * §1). No type here is shared with either of the other two beyond the attestation
 * and cost bodies in `contracts.ts`, which are the two things all three entry points
 * genuinely declare.
 *
 * **The field names are the backend's own**, `snake_case` and all, on `bench.ts`'s
 * standing rule: the body is a contract with `backend/api/app.py` and a camel-cased
 * mirror would be one rename away from a `422` nobody can read.
 *
 * **No payload field on any shape in this file, and there is nowhere to put one.**
 * The pending store is the one place in this bench that holds a working probe and a
 * target's identity, and ADR-0104 grants that exception for *measuring* a route and
 * never for showing it. The route serves a digest; this app could not display a
 * probe if a screen asked for one.
 *
 * **A refusal is a first-class answer**, as it is for a gate run: a deployment that
 * ships no reference agents, one that declares a single model and a library a gate
 * run is holding are three different facts, and each of them is a sentence the
 * screen states rather than an exception it falls over on.
 */

import type { ApprovalBody, AttestationBody, CostBody } from './contracts'
import { ANSWER_UNREACHABLE, fetched, refusalIn } from './http'

/** Where the queue is read, and where a measurement over it is started. */
export const PENDING_ROUTES_PATH = '/pending-routes'

/** Where a measurement is started, answered and read. Never under `/gate-runs`. */
export const MEASUREMENTS_PATH = '/pending-routes/measurements'

/**
 * This bench can decide a pending route, and what doing it would cost.
 *
 * `available` is the field the screen branches on and it is a literal on both
 * shapes, so *can* and *cannot* are two facts rather than one record with empty
 * fields — the idiom `MayStart` and `GateCitation` already carry.
 */
export interface MayMeasure {
  available: true
  library: string
  /** The two underlying models, in the order they are measured (ADR-0012). */
  models: string[]
  statement: string
}

/**
 * This bench cannot decide a pending route, and the named reason it cannot.
 *
 * Five names reach this shape and only one of them is answered by waiting: the
 * library being held is a fact about right now, and the other four are facts about
 * how the deployment was built. `stated` carries the holder's own words where the
 * bench put a name on the lease, which is what tells an operator whether their next
 * move is to wait or to redeploy.
 */
export interface MayNotMeasure {
  available: false
  refusal: string
  stated: string
}

export type MeasureAvailability = MayMeasure | MayNotMeasure

/**
 * One route in the queue: what it did, whose agent it beat, and its answer.
 *
 * `probe` is the digest of the probe and never the probe (ADR-0008). `reason` is
 * the deciding surface's own words once there is a decision, and an admitted
 * route's reason names the record it became — a rejected route keeps its row and
 * its reason, because a route that was a property of one model is a finding
 * (ADR-0012).
 */
export interface PendingRouteRow {
  route: string
  family: string
  probe: string
  target: string
  description: string
  filed_on: string
  /** `pending`, `admitted` or `rejected` — the field a screen branches on. */
  state: string
  reason: string
}

/** One measurement on the record: when, where it got to, how many routes. */
export interface MeasurementRow {
  measurement_id: string
  recorded_at: string
  status: string
  statement: string
  routes: number
}

/** The queue, the measurements over it, and whether another may start. */
export interface PendingRouteQueue {
  measure: MeasureAvailability
  routes: PendingRouteRow[]
  measurements: MeasurementRow[]
  statement: string
}

/**
 * What deciding one route costs, in the units the operator already reads.
 *
 * Exact and not a bound: the adaptive layer is switched off for an admission run,
 * so there is one layer, one figure and no second number to add to it (ADR-0010,
 * ADR-0058). `basis` is the arithmetic, served rather than composed here.
 */
export interface RouteEstimate {
  route: string
  family: string
  target: string
  calls: number
  basis: string
  cost: string
}

/**
 * The consent surface for a measurement: the rows, their total, and the ceiling.
 *
 * One layer and therefore one total, added over the routes the operator chose and
 * never over layers. The rows add up to more than the total and the served
 * `statement` says why — the routes ride in one admission run per model, and a
 * registration probe is one per agent per model however many ride with it.
 */
export interface MeasurementEstimate {
  per_route: RouteEstimate[]
  models: string[]
  calls: number
  /** The enforced ceiling: the figure above with every message retried to its
   * transport limit. A measurement may not exceed what it was shown (ADR-0007). */
  ceiling: number
  cost: string
  currency: string
  statement: string
}

/**
 * A measurement recorded and halted in front of its estimate.
 *
 * The estimate arrives once, here, from the request that created the measurement —
 * the division `POST /runs` and `POST /gate-runs` make, and for the same reason:
 * the route that reports progress reports no estimate.
 */
export interface MeasurementStarted {
  measurement_id: string
  status: string
  statement: string
  estimate: MeasurementEstimate
  library: string
}

/** Where one route in a measurement has got to, and what it ended as. */
export interface RouteProgressRow {
  route: string
  target: string
  description: string
  /** Where this route is right now, in words. Read, and never branched on. */
  where: string
  state: string
  reason: string
  /** The case record an admitted route became, named as the file it is. */
  entered_as: string
}

/**
 * Where one measurement has got to, per route, and what the bar said.
 *
 * No estimate here, on `GateRunReading`'s reasoning: the figures were presented
 * once, by the request that created the record, and a second copy served from a
 * progress route is a second thing that could disagree with what was confirmed.
 */
/** One model's pass over the selected routes, and how far into it the run is. */
export interface ModelPassRow {
  model: string
  /** `waiting`, `measuring`, `measured` or `unmeasured` — the pass that did not
   * happen is its own state and not an empty one. */
  state: string
  attempted: number
  of: number
}

export interface MeasurementReading {
  measurement_id: string
  status: string
  statement: string
  recorded_at: string
  models: string[]
  library: string
  routes: RouteProgressRow[]
  /** One pass per model, in the order they are measured. */
  passes: ModelPassRow[]
  /** The bar's own prose, in the order it produced it. A run at a terminal prints
   * these; this surface has no terminal, so they are served. */
  lines: string[]
}

/** The three attestation statements, the declared cost, and the routes chosen. */
export interface StartMeasurementBody {
  attestation: AttestationBody
  cost: CostBody
  /** Never all of them by default: three agents on two models each is money. */
  routes: string[]
}

/**
 * The queue as it stands, with the one fact a screen needs before it draws a
 * control.
 *
 * Read before the control is drawn rather than after it is pressed, on
 * `gateRuns`'s reasoning: a screen that offered *measure* on a deployment shipping
 * no reference agents would be offering an operation the bench refuses, and the
 * refusal it would then show is a fact the screen could have stated first.
 */
export async function pendingRoutes(): Promise<PendingRouteQueue> {
  return (await fetched(PENDING_ROUTES_PATH, 'pending routes')) as PendingRouteQueue
}

/**
 * Start a measurement: record the attestation, declare the estimate, and halt.
 *
 * A `202` means the measurement exists and is holding its interrupt, which is
 * before anything has been sent to a reference agent and while every route it names
 * is still pending. It also means this bench's case library is now held by it — a
 * gate run started from here on is refused by name, and so is a second measurement.
 *
 * The refusals are outcomes rather than exceptions, on `startGateRun`'s reasoning:
 * a bench that ships no reference agents, declares one model, or is holding its
 * library is a state the operator has to be told about in words.
 */
export async function startMeasurement(
  body: StartMeasurementBody,
): Promise<MeasurementOutcome> {
  let response: Response
  try {
    response = await fetch(MEASUREMENTS_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return {
      kind: 'unreachable',
      statement: `${MEASUREMENT_UNREACHABLE} (${unreachable})`,
    }
  }
  if (response.ok) {
    return {
      kind: 'started',
      measurement: (await response.json()) as MeasurementStarted,
    }
  }
  return { kind: 'refused', statement: await refusalIn(response) }
}

/**
 * What became of a request to start one.
 *
 * `refused` carries the bench's own sentence, which is the one that names which of
 * the nine reasons it was. `unreachable` is no answer at all: nothing was started,
 * and the operator has a queue to re-read rather than a form to fix.
 */
export type MeasurementOutcome =
  | { kind: 'started'; measurement: MeasurementStarted }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

const MEASUREMENT_UNREACHABLE =
  'the bench did not answer, so it is not known whether a measurement was ' +
  'started. Read the queue before asking again: a measurement holds the case ' +
  'library while it goes, and a second would be refused rather than queued.'

/**
 * Answer a measurement's interrupt. A `confirmed: true` is the only thing that
 * spends.
 *
 * The same body the other two interrupts take, deliberately: the answer to an
 * interrupt is the consent mechanism itself and there is one of those in this app
 * (ADR-0007). What is not shared is the record it answers — this posts under
 * `/pending-routes`, and a run id here is a `404` rather than an interrupt answered
 * for something else.
 *
 * A `confirmed: false` goes on the wire too, for the reason a declined gate run
 * does: it records the measurement as declined by a person rather than leaving it
 * to time out, and the bench's sentence for it says every route it named is still
 * pending with its payload.
 */
export async function answerTheMeasurementsInterrupt(
  measurementId: string,
  body: ApprovalBody,
): Promise<MeasurementApprovalOutcome> {
  let response: Response
  try {
    response = await fetch(
      `${MEASUREMENTS_PATH}/${encodeURIComponent(measurementId)}/approval`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
  } catch (unreachable) {
    return {
      kind: 'unreachable',
      statement: `${ANSWER_UNREACHABLE} (${unreachable})`,
    }
  }
  if (response.ok) {
    return {
      kind: 'answered',
      measurement: (await response.json()) as MeasurementStarted,
    }
  }
  const statement = await refusalIn(response)
  if (response.status === 409) {
    return { kind: 'no_longer_waiting', statement }
  }
  return { kind: 'refused', statement }
}

/** What became of an answer to a measurement's interrupt. */
export type MeasurementApprovalOutcome =
  | { kind: 'answered'; measurement: MeasurementStarted }
  | { kind: 'no_longer_waiting'; statement: string }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

/**
 * Where one measurement has got to, route by route.
 *
 * Polled while it goes. Nothing about this request touches a reference agent —
 * asking a measurement how it is going is a question put to the bench.
 */
export async function measurementReading(
  measurementId: string,
): Promise<MeasurementReading> {
  const response = await fetch(
    `${MEASUREMENTS_PATH}/${encodeURIComponent(measurementId)}`,
  )
  if (!response.ok) {
    throw new Error(
      `the bench has no measurement ${measurementId} to report on ` +
        `(HTTP ${response.status})`,
    )
  }
  return (await response.json()) as MeasurementReading
}
