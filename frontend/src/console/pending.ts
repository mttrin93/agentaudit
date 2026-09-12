/**
 * The routes the attacker found and nothing has decided, as data: the queue, the
 * selection, the estimate, the halt, and where each route got to.
 *
 * The console's direction is verbs and not metrics, and this page's verb is *decide
 * these*. What it lists is what the adaptive attacker found against somebody's real
 * agent that the fixed suite did not — filed by the run that found it
 * ([ADR-0104](../../../docs/adr/0104-the-pending-store-holds-the-payload-and-the-target-and-it-is-the-one-exception.md)),
 * decided on a surface of its own
 * ([ADR-0105](../../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)),
 * and read here.
 *
 * **Not one figure on this page is a rate, an interval, a band or a `D`.** A pending
 * route is not an attempt and nothing about it reaches a denominator
 * ([ADR-0010](../../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)),
 * and the `D` the bar measures is the *case's* own discriminating power against
 * three agents of known construction — never a reading about the target the route
 * beat ([ADR-0107](../../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md),
 * which is what decides this surface's bar, narrowing
 * [ADR-0012](../../../docs/adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)).
 * So the numbers on this surface are counts of calls and a cost, and there is
 * nowhere in any type below to put anything else. `pending.test.ts` scans the whole
 * built view for one.
 *
 * **Nothing here decides anything and nothing here computes a figure.** Whether a
 * measurement may start is the bench's answer (`MeasureAvailability`), what a
 * measurement costs is the bench's estimate, and what a route was decided as is what
 * the store holds it as. This module is a transformation: it reads the wire, joins
 * two served readings, and refuses to build a request body out of an incomplete
 * declaration. That last one is the only guard it owns, and it is the one that
 * decides whether a pass over three reference agents is paid for.
 *
 * **The attestation is the one this app already has.** `ATTESTATION_STATEMENTS` is
 * the register screen's wording, copied from `registration.py` so that the prompt
 * somebody confirms and the record of what they confirmed cannot drift apart. What
 * this module adds is the consequence a *measurement* has that a target run does
 * not, per statement, and never a second copy of a statement.
 */

import type {
  ApprovalBody,
  MeasureAvailability,
  MeasurementEstimate,
  MeasurementReading,
  PendingRouteQueue,
  StartMeasurementBody,
} from '../api/bench'
import { readFamily } from '../families'
import {
  ATTESTATION_STATEMENTS,
  anyWithheld,
  nothingAttested,
  type Attested,
  type Attesting,
  type Statement,
} from '../register/declarations'

/** What the store holds a route as, in the three words it uses (`RouteState`). */
export const PENDING = 'pending'

export const ADMITTED = 'admitted'

export const REJECTED = 'rejected'

/**
 * The bench's own name for *this library is already held*.
 *
 * Named here because the screen has to tell this refusal from the other four: the
 * others are facts about how the deployment was built and waiting does not answer
 * them, and this one is answered by waiting for whoever holds the lease to give it
 * back. It is the only refusal this screen offers to re-ask about.
 */
export const ALREADY_IN_FLIGHT = 'already_in_flight'

/**
 * The two states a measurement is still going in, in the words its own record keeps.
 *
 * The in-flight pair rather than the five settled ones, because that is the list
 * `MeasurementStatus.in_flight` is written as one level down — and because the two
 * lists fail differently on a status this app does not recognise. Inverting the
 * settled list would poll a stranger for ever; naming the going ones stops, which is
 * the answer that costs nothing and leaves the page's last reading on it.
 */
const IN_FLIGHT = ['awaiting_approval', 'measuring'] as const

/** Whether a measurement in this state is still going, or has stopped for good. */
export function stillMeasuring(status: string): boolean {
  return IN_FLIGHT.some((going) => going === status)
}

// --- the queue, as an operator reads it -----------------------------------------

/**
 * One route on the page: what it did, whose agent it beat, and its answer.
 *
 * `chooseable` is on the row rather than worked out by the screen, because a
 * decided route may never be selected again — its payload went with the decision
 * (ADR-0104 §4), so there is no probe left to measure it with and a second answer
 * would rest on no reading at all. A row that offered the checkbox anyway would be
 * offering a spend the bench refuses.
 *
 * **There is no payload field here and there is nowhere to put one.** The probe is
 * in the store for the surface that measures it; the exception ADR-0104 grants is
 * for measuring a route and never for showing it.
 */
export interface QueueRow {
  /** The key the route is filed under: its family and the digest of its probe. */
  route: string
  family: string
  /** The digest of the probe, and never the probe (ADR-0008). */
  probe: string
  target: string
  description: string
  /** The day it was found, which is what an operator triages on. */
  filed: string
  state: string
  /** The deciding surface's own words, once there is a decision. */
  reason: string
  /**
   * The case record an admitted route became, named as the file it is.
   *
   * Read off the measurement that wrote it and never parsed out of the reason: the
   * reason names the record in prose, and a screen that pulled a filename out of a
   * sentence would be a second definition of a format nothing owns. Empty where no
   * measurement this screen can see wrote one, which is a stated absence and not a
   * guess (spec story 11).
   */
  enteredAs: string
  chooseable: boolean
}

/**
 * The queue as rows, in the order the bench served them.
 *
 * `reading` is the measurement this screen has in view, or `null`. It is joined
 * rather than fetched here, because this module is a transformation and not a
 * client — and the join is by route key, which is the same `family-probe` the
 * store, the memory and the library all de-duplicate on.
 */
export function queueRows(
  queue: PendingRouteQueue,
  reading: MeasurementReading | null,
): QueueRow[] {
  const wrote = new Map(
    (reading?.routes ?? []).map((row) => [row.route, row.entered_as]),
  )
  return queue.routes.map((row) => ({
    route: row.route,
    family: readFamily(row.family),
    probe: row.probe,
    target: row.target,
    description: row.description,
    filed: theDay(row.filed_on),
    state: row.state,
    reason: row.reason,
    enteredAs: wrote.get(row.route) ?? '',
    chooseable: row.state === PENDING,
  }))
}

/**
 * The day out of an instant, and the instant back where it is not one.
 *
 * A date and not a time, because what an operator triages on is *when was this
 * found* and a queue of timestamps to the second reads as a log. Carried through
 * unchanged where the string is not an instant this app recognises: a page that
 * dropped an unfamiliar value would be hiding what the bench actually said.
 */
function theDay(instant: string): string {
  const day = /^(\d{4}-\d{2}-\d{2})/.exec(instant)
  return day === null ? instant : day[1]
}

/**
 * What an empty queue says: a reading about the attacker, and never a blank.
 *
 * A zero here is a reading about the attacker and about the families it worked in,
 * never a reading about the target (ADR-0011) — the sentence `queued.py` already
 * says at the moment a run files nothing, said again at the moment somebody reads
 * the queue it did not add to. An absence is not a reading, and a blank screen is
 * indistinguishable from a bench that failed to answer.
 */
export interface EmptyQueue {
  heading: string
  statement: string
  aside: string
}

export function theEmptyQueue(): EmptyQueue {
  return {
    heading: 'No route is awaiting a decision',
    statement:
      'The adaptive attacker proposed no route that is still waiting on the ' +
      'bar. A zero here is a reading about the attacker and about the families ' +
      'it worked in, never a reading about the target (ADR-0011).',
    aside:
      'A route reaches this queue only from a run against somebody’s own agent, ' +
      'and only where the attacker composed a probe the fixed suite does not ' +
      'hold. A gate run’s routes stay out of it deliberately: this queue is the ' +
      'routes no other surface decides.',
  }
}

// --- whether a measurement may start --------------------------------------------

/** The one control this page offers, and the model a decision is made on. */
export interface MeasureHere {
  available: true
  label: string
  models: string[]
  library: string
  statement: string
}

/**
 * No control, and the named reason there is none.
 *
 * A stated absence where the control would have been, which is the idiom
 * `.citation.uncited` already carries: a missing button with nothing said about it
 * is a screen a reader assumes is broken. `waiting` is the one refusal an operator
 * answers by waiting rather than by redeploying, and it is a field rather than a
 * comparison at the call site so that the screen and this module cannot disagree
 * about which of the five it is.
 */
export interface NoMeasureHere {
  available: false
  heading: string
  refusal: string
  statement: string
  waiting: boolean
}

export type MeasureControl = MeasureHere | NoMeasureHere

const WAIT_FOR_THE_HOLDER =
  ' Your next move is to wait: the lease is exclusive and it is released a moment ' +
  'after the run holding it is decided. Nothing has been sent and nothing has been ' +
  'spent, and every route in this queue is still pending.'

const NOT_FROM_THIS_BENCH =
  ' This is a fact about how this deployment was built rather than about right ' +
  'now, so waiting does not answer it and this page offers no control that would.'

/**
 * The control, or the stated absence of one, read off what the bench said.
 *
 * Read and never inferred. A screen that decided for itself whether to offer the
 * control would be a second policy beside the bench's own, and the two would only
 * have to disagree once to offer a spend that is then refused.
 */
export function measureControl(measure: MeasureAvailability): MeasureControl {
  if (!measure.available) {
    const waiting = measure.refusal === ALREADY_IN_FLIGHT
    return {
      available: false,
      heading: waiting
        ? 'The case library is held by somebody else'
        : 'This bench cannot decide a pending route',
      refusal: measure.refusal,
      statement: `${measure.stated}.${waiting ? WAIT_FOR_THE_HOLDER : NOT_FROM_THIS_BENCH}`,
      waiting,
    }
  }
  return {
    available: true,
    label: 'Measure the selected routes',
    models: measure.models,
    library: measure.library,
    statement: measure.statement,
  }
}

/** The queue, the control over it, and the reading where it holds nothing. */
export interface QueueView {
  rows: QueueRow[]
  control: MeasureControl
  /** The stated absence, or `null` the moment there is a row to say it instead. */
  empty: EmptyQueue | null
  statement: string
}

/** Everything the page draws, from the one response and the measurement in view. */
export function queueView(
  queue: PendingRouteQueue,
  reading: MeasurementReading | null,
): QueueView {
  const rows = queueRows(queue, reading)
  return {
    rows,
    control: measureControl(queue.measure),
    empty: rows.length ? null : theEmptyQueue(),
    statement: queue.statement,
  }
}

// --- the three statements, one at a time ----------------------------------------

/**
 * What deciding a pending route does that a target run does not, per statement.
 *
 * Keyed by the field each statement records, and it is *only* the consequence: the
 * wording is `ATTESTATION_STATEMENTS`' own and is never restated here. A second copy
 * of the three statements is a second thing to keep in step with the record they
 * are written into, and that record is the liability record (ADR-0007).
 */
const FOR_A_MEASUREMENT: Record<keyof Attested, string> = {
  authorised_to_test:
    'The endpoints a measurement attacks are this bench’s own three reference ' +
    'agents — never the target the route was found against. That target is not ' +
    'touched again by anything on this page.',
  not_production:
    'The reference agents are test equipment and never reach a user. What a ' +
    'measurement changes is the case library: a route that clears the bar is ' +
    'written into it as a case record, and that library is the one every run on ' +
    'this bench is measured with.',
  accepts_provider_policy_and_cost:
    'The probes reach your model provider under your credentials, so the policy ' +
    'violations are recorded against your account and the inference is billed to ' +
    'it. Whatever you attested to for the run that found the route authorised ' +
    'none of this.',
}

/** One statement as this page asks it: the record's wording, this consequence. */
export interface MeasurementStatement {
  field: keyof Attested
  wording: string
  consequence: string
  step: number
  of: number
}

/**
 * The three, in the order the record lists them and the page asks them.
 *
 * Built from `ATTESTATION_STATEMENTS` so that the wording is one wording. What
 * would go wrong here is a screen that asked a friendlier version of a statement
 * the bench then recorded in its own words.
 */
export const MEASUREMENT_STATEMENTS: readonly MeasurementStatement[] =
  ATTESTATION_STATEMENTS.map((statement: Statement, index: number) => ({
    field: statement.field,
    wording: statement.wording,
    consequence: FOR_A_MEASUREMENT[statement.field],
    step: index + 1,
    of: ATTESTATION_STATEMENTS.length,
  }))

/**
 * What an operator declares, and the guard over it, shared with the other two walks.
 *
 * Re-exported rather than declared again: this is the third surface that collects
 * the attestation `registration.py` refuses to construct incomplete, and the record
 * is one record. What is this page's own is `FOR_A_MEASUREMENT` above — the
 * consequence beside each statement, which is different here and nowhere else.
 */
export type { Attesting }

export { anyWithheld, nothingAttested }

/**
 * A measurement ready to start, or the reasons it is not one.
 *
 * Two outcomes rather than a body beside a valid flag, so there is no path in this
 * module to the body of a measurement whose statements were not all made, or whose
 * routes nobody chose. The blocked outcome carries what is unfinished; nothing
 * reads its length to decide whether a measurement may start.
 */
export type MeasurementRequest =
  | { kind: 'ready'; body: StartMeasurementBody }
  | { kind: 'blocked'; missing: string[] }

/**
 * What this page would post, or what it is still waiting for.
 *
 * The order of the checks is the order of the walk, so the first thing an operator
 * is told about is the earliest step they have to go back to. Every branch that is
 * not a complete declaration over a non-empty selection returns the blocked outcome
 * and no body: this is the function that decides whether a pass over three
 * reference agents is paid for, per route.
 *
 * **The routes are the operator's own selection and never all of them.** A queue
 * that drained itself would be an unbounded spend authorised once (ADR-0105, the
 * spec's *Out of scope*), so an empty selection is blocked here as well as at the
 * bench.
 */
export function measurementRequest(
  attesting: Attesting,
  routes: readonly string[],
): MeasurementRequest {
  const missing: string[] = []

  if (routes.length === 0) {
    missing.push(
      'no route is selected. A measurement is per route — the three reference ' +
        'agents, once each — so the routes are chosen by whoever reads the queue ' +
        'and never defaulted to all of them',
    )
  }
  if (attesting.price_per_call.trim() && !attesting.currency.trim()) {
    // `CallPrice`'s own guard, held here so the operator meets it as an unfinished
    // step rather than as a 422: an amount with a currency the bench chose is a
    // figure the operator did not state.
    missing.push(
      'a price per call needs the currency it is in, or declare the measurement ' +
        'not priced',
    )
  }
  if (anyWithheld(attesting) || missing.length) {
    return { kind: 'blocked', missing }
  }
  const priced = attesting.price_per_call.trim()
  return {
    kind: 'ready',
    body: {
      attestation: { ...attesting.attested },
      cost: {
        price_per_call: priced ? priced : null,
        currency: priced ? attesting.currency.trim() : '',
      },
      routes: [...routes],
    },
  }
}

// --- the estimate, before anything is sent ---------------------------------------

/** What deciding one route costs, in the units the operator already reads. */
export interface RouteFigure {
  route: string
  family: string
  target: string
  /** The calls this route costs measured on its own. Exact, and `basis` is why. */
  calls: number
  basis: string
  cost: string
}

/**
 * The whole of what the halt puts in front of a person.
 *
 * One layer and therefore one figure and one ceiling: the adaptive layer is
 * switched off for an admission run, so there is no bound to add to this and no
 * second number anywhere on the halt (ADR-0010, ADR-0058). The figure is rendered
 * beside the ceiling it is enforced against, which is the run screen's own
 * arrangement and the enforced limit (ADR-0007).
 *
 * `statement` is the bench's own sentence and is not composed here: it is where the
 * rows adding up to more than the total is explained, and an explanation this app
 * wrote would be a second account of an arithmetic the bench owns.
 */
export interface EstimateView {
  perRoute: RouteFigure[]
  models: string[]
  /** The total, as it is read. A string, because a figure and a bound are read the
   * same way and only one of them has a `≤` in front of it. */
  calls: string
  ceiling: string
  cost: string
  statement: string
}

/** The estimate this measurement is holding, per route, off the bench's own figures. */
export function measurementEstimateView(
  estimate: MeasurementEstimate,
): EstimateView {
  return {
    perRoute: estimate.per_route.map((one) => ({
      route: one.route,
      family: readFamily(one.family),
      target: one.target,
      calls: one.calls,
      basis: one.basis,
      cost: one.cost,
    })),
    models: estimate.models,
    calls: `${estimate.calls}`,
    ceiling: `≤ ${estimate.ceiling}`,
    cost: estimate.cost,
    statement: estimate.statement,
  }
}

// --- while it goes ---------------------------------------------------------------

/** Where one route has got to, and what it ended as. */
export interface ProgressRow {
  route: string
  target: string
  description: string
  /** Prose, because it is read and never branched on. `state` is the field a
   * caller branches on. */
  where: string
  state: string
  reason: string
  enteredAs: string
}

/**
 * Where the measurement has got to, one route at a time.
 *
 * Per route rather than per measurement, because the action is minutes long and the
 * operator selected the routes one at a time (spec story 10). The rows are carried
 * and never recomputed: what a route is, is what the store holds it as, and a screen
 * that decided a state for itself would be a screen disagreeing with the disk.
 */
export function progressRows(reading: MeasurementReading): ProgressRow[] {
  return reading.routes.map((row) => ({
    route: row.route,
    target: row.target,
    description: row.description,
    where: row.where,
    state: row.state,
    reason: row.reason,
    enteredAs: row.entered_as,
  }))
}

/** One model's pass, as a bar and the word that says which state it is in. */
export interface ModelBar {
  model: string
  state: string
  attempted: number
  of: number
  /** What this pass is, in words. Beside the length and never instead of it: a bar
   * at nothing is a pass waiting to be paid for or a pass that will never run, and
   * nothing on this page may be carried by a length alone (`GateCards.Keys`). */
  reading: string
}

const PASS_READINGS: Record<string, string> = {
  waiting: 'waiting — nothing sent on this model yet',
  measuring: 'measuring against the three agents',
  measured: 'measured',
  unmeasured: 'did not run — this model was never measured',
}

/**
 * One bar per model, in the order the models are measured — one of them here.
 *
 * The question an operator watching this actually has, and the one `progressRows`
 * cannot answer: the action is minutes long, so *how far in* is a fact about the
 * pass and not about any route in it. One pass, because this surface declares one
 * model (ADR-0107 §4); a list all the same, because the record carries the models
 * it was measured on and this reads what it carries.
 *
 * **The counts are carried and never recomputed.** `attempted` and `of` are the
 * record's own — attempts made against the attempts the declared rule asked for —
 * and a screen that divided them into a percentage would be a figure this surface
 * does not carry. The share is a length the component draws; the numbers beside it
 * are counts of attempts, which is what `progressRows` means by reading the disk
 * rather than deciding a state.
 *
 * An unknown state is passed through as its own word rather than mapped to a
 * default: a fifth `ModelPassState` should read as itself on the page, not as
 * whichever of the four sorted first.
 */
export function modelBars(reading: MeasurementReading): ModelBar[] {
  return reading.passes.map((pass) => ({
    model: pass.model,
    state: pass.state,
    attempted: pass.attempted,
    of: pass.of,
    reading: PASS_READINGS[pass.state] ?? pass.state,
  }))
}

// --- the halt, answered on the page ----------------------------------------------

/** The status a measurement holds while it waits on a person, and on nothing else. */
export const AWAITING_APPROVAL = 'awaiting_approval'

/**
 * The one path to a `confirmed: true` on a measurement's interrupt.
 *
 * `confirmed` is compared against `true` rather than tested for truthiness, on
 * `gateConfirmation`'s reasoning: a truthy-looking value spending somebody's
 * inference budget and writing into their case library is the failure to guard
 * against. The status is checked here as well, so a measurement that has
 * already been answered cannot be answered twice from a page left open.
 */
export function measurementConfirmation(
  status: string,
  confirmed: boolean,
  reason: string = '',
): { kind: 'ready'; body: ApprovalBody } | { kind: 'withheld'; missing: string[] } {
  const missing: string[] = []
  if (status !== AWAITING_APPROVAL) {
    missing.push(
      `this measurement is ${status} and is not holding an interrupt, so there is ` +
        'nothing here to confirm: an interrupt is answered once',
    )
  }
  if (confirmed !== true) {
    missing.push(
      'the estimate has not been confirmed. Every route stays pending until it is, ' +
        'and nothing has been sent to a reference agent',
    )
  }
  // No name is asked for or sent, on `gateConfirmation`'s reasoning: who confirmed
  // is the operator the API verified this request as (ADR-0116 §1).
  if (missing.length) {
    return { kind: 'withheld', missing }
  }
  return {
    kind: 'ready',
    body: { confirmed: true, reason: reason.trim() },
  }
}

/**
 * The answer that spends nothing, available at every moment the other one is not.
 *
 * A no is sent rather than withheld and it asks for nothing first: the bench records
 * it as declined by a person, which is a better record than the *unanswered* a
 * closed tab leaves, and its own sentence says that every route the measurement
 * named is still pending, with its payload, and the library it was holding has gone
 * back exactly as it was.
 */
export function measurementDecline(reason: string = ''): ApprovalBody {
  return {
    confirmed: false,
    reason:
      reason.trim() ||
      'declined at the approval interrupt: the estimate was not confirmed',
  }
}
