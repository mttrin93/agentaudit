/**
 * `POST /runs`, `GET /runs`, `GET /runs/{id}` and the approval in front of them.
 *
 * Starting a run, watching one, and answering the halt. #14 split `bench.ts` by API
 * area and this is the largest of them, because it is the one route surface an
 * operator drives by hand.
 *
 * **Nothing here throws for a refusal.** A registration the bench refuses is a step
 * the operator has to complete rather than an error the app fell over on (ADR-0007
 * calls it the authorisation guard for exactly that reason), so `startRun` returns
 * one of three outcomes and every one of them carries the sentence the bench wrote.
 * An exception would be caught somewhere far from the screen that has to say what to
 * do next, and the sentence would be lost on the way. What *is* thrown is a fetch
 * that never reached the bench at all, and `startRun` turns that into an outcome too
 * — see `unreachable`.
 *
 * **A start refusal always costs the nonce.** `BenchRuns.start` discards the value
 * from its issued set before it does anything else, so one nonce starts one run and
 * no more — whether that run was refused, and whether the answer ever came back.
 * Every non-registered outcome therefore sends the operator back to the plant step
 * with a value the bench has just issued, and none of them offers a retry of the
 * same body.
 */

import type {
  AdaptiveProgress,
  ApprovalBody,
  AttemptExchange,
  AttestationBody,
  CostBody,
  ElectiveFamilyRun,
  FamilyRun,
  Refusal,
  ReportLocation,
  RuleOfTwoDeclared,
  ScoredProgress,
} from './contracts'
import {
  ANSWER_UNREACHABLE,
  fetched,
  refusalIn,
  refusalRead,
} from './http'


/**
 * The endpoint the bench is being asked to attack, as the operator declares it.
 *
 * `RuleOfTwoDeclared` extended rather than its four fields written again, so that the
 * declarations a registration carries and the declarations the reading route is asked
 * about cannot drift into two shapes with one name.
 */
export interface TargetBody extends RuleOfTwoDeclared {
  name: string
  url: string
  auth_token: string
  agent_type: string
  exposes_tool_calls: boolean
  /**
   * Whether the endpoint carries one turn of a session into the next.
   *
   * Every scripted construction in the library requires it, so a body that leaves
   * it false is a body the fixed multi-turn half of the scored layer is skipped
   * against — before an attempt is spent, and whatever the selection says. Sent as a
   * `boolean` and not the three answers the Rule of Two carries, because the bench
   * reads it as a capability that decides measurability and its absent state is
   * *false*, which is the narrower run (ADR-0041).
   */
  retains_session_state: boolean
  declared_tools: string[]
  sends: number
}

/** Everything a run needs before it may exist, and nothing it can default. */
export interface StartRunBody {
  target: TargetBody
  attestation: AttestationBody
  nonce: string
  cost: CostBody
  note_planted: boolean
  /**
   * Whether the nonce is in the target's configuration.
   *
   * `false` drops the data-leakage family from the plan — its canary *is* this
   * value, and a string nowhere in the target cannot leak — and a run with nothing
   * planted also starts without the proof, since nothing could have echoed. Sent on
   * every request rather than omitted, because the bench's default is the guard and
   * a waiver reached by leaving a field out is a waiver nobody made.
   */
  nonce_planted: boolean
  /**
   * Whether the run may start without the target echoing the planted nonce.
   *
   * The declaration for an agent that planted the value and refuses to repeat it,
   * because its disclosure rule cannot tell a registration check from an attack.
   * The probe is still sent, a missing echo no longer stops the run, and the
   * artefact records control as declared and not proved — while the leakage family,
   * which turns on `nonce_planted` above and not on this, still runs (ADR-0025).
   */
  echo_waived: boolean
}

/**
 * One layer's figure on the consent surface, as `LayerFigurePayload` sends it.
 *
 * `kind` is the whole point of the record: `exact` is a fact and `ceiling` is a
 * bound, and the bench carries the difference in a field rather than in prose so
 * that nothing downstream can present a bound as though it were arithmetic
 * (`budget.py`). `basis` is that arithmetic in words, which is what makes the
 * number checkable rather than believable, and `cost` is already rendered — `≤`
 * and currency and all — because the money is the operator's declaration and this
 * app has no business recomputing it.
 */
export interface LayerFigure {
  calls: number
  kind: string
  basis: string
  cost: string
}

/**
 * The consent surface exactly as the interrupt is holding it.
 *
 * **`total`, `hard_ceiling` and `presented` are on the wire and the run screen
 * renders none of them.** They are typed here rather than dropped from the type
 * because the run screen's first acceptance criterion is the *absence* of a
 * blended number, and an absence is only assertable against a field a test can
 * name (`interrupt.test.ts` scans the view for both figures). The bench builds
 * them as bounds and is right to — ADR-0007's own table prints a bounded total —
 * but the screen shows the two layers and the ceiling each one is enforced
 * against, which is the same disclosure with nothing spanning the layers. See
 * `interrupt.ts`.
 */
export interface RunEstimate {
  scored: LayerFigure
  adaptive: LayerFigure
  total: LayerFigure
  hard_ceiling: LayerFigure
  scored_ceiling: number
  adaptive_ceiling: number
  currency: string
  presented: string[]
}

/**
 * A run that exists and is holding its interrupt.
 *
 * `estimate` is the consent surface the graph is holding, and it arrives here
 * because this is the only response that carries it: `GET /runs/{id}` reports
 * progress and no figures, so the run screen is shown the estimate that came back
 * from the registration that made the run (`interrupt.ts` says how it gets
 * there). `spent` is per layer with no total beside it, which is why it is a map
 * of two counters rather than a number.
 */
export interface RunStarted {
  run_id: string
  status: string
  statement: string
  estimate: RunEstimate
  spent: Record<string, number>
  cases: number
  families_not_run: Record<string, string>
}

/**
 * Where a run has got to, in the two fields this screen reads.
 *
 * The per-layer positions are deliberately absent: progress belongs to the run
 * screen, and a register screen that could read a scored position is a register
 * screen somebody will one day print a total on. What registration needs is the
 * status and the sentence beside it.
 */
export interface RunStanding {
  run_id: string
  status: string
  statement: string
}

/** The named outcome that stopped a run on the wire, and what it is not. */
export interface TransportOutcome {
  failure: string
  statement: string
}

/**
 * One run in flight, reported per layer, as the screen that polls it reads it.
 *
 * `RunStanding` extended rather than restated, so that the register screen's
 * narrow read of this same route stays a narrowing of one type instead of a second
 * description of it. There is no field here that spans the two layers, and this
 * app adds none: calls spent and findings so far live inside `scored` and
 * `adaptive` and nowhere else, so a total would have to be written out in front of
 * the two labels saying what was being added.
 */
export interface RunProgress extends RunStanding {
  scored: ScoredProgress
  adaptive: AdaptiveProgress
  transport: TransportOutcome | null
  report: ReportLocation | null
  recent: AttemptExchange[]
  families: FamilyRun[]
  /**
   * The elective families this run asked for, in a list of their own.
   *
   * Only the requested ones, which is where it differs from `families` above: six
   * rows are always drawn, because a family of the six missing while the run is on
   * another one reads as one this run is not doing, and an elective family nobody
   * asked for is not part of the run at all. Absent from a run made before the tier
   * could be requested, so the screen reads it as the empty list it is.
   */
  elective_families?: ElectiveFamilyRun[]
}

/** What one run's scored layer put on the wire, against the scored ceiling. */
export interface ScoredSpend {
  calls_spent: number
  statement: string
}

/**
 * What one run's adaptive layer put on the wire, against the adaptive ceiling.
 *
 * A second interface rather than one `LayerSpend` read twice, matching the two
 * models the route serves. The two figures are held to two separate ceilings, and
 * a type that accepted either would be a type something could be accumulated
 * through — the widening ADR-0010 asks anyone reaching for it to stop at.
 */
export interface AdaptiveSpend {
  calls_spent: number
  statement: string
}

/**
 * One run on the record: what it was against, when, where it got to, what it spent.
 *
 * A row and never a report. There is no rate here, no band and no verdict — a
 * figure lifted out of a signed report onto a list would arrive without the
 * denominator that was printed beside it. The target is named and its URL is
 * nowhere (ADR-0008).
 */
export interface RunRow {
  run_id: string
  target: string
  /**
   * When the run went on the record — the attestation taken, the estimate
   * declared — which is before the target was asked to echo anything. Not a
   * registration time: registration is the nonce echo, and a declined run never
   * reached one.
   */
  recorded_at: string
  status: string
  statement: string
  scored: ScoredSpend
  adaptive: AdaptiveSpend
}

/**
 * The runs on the record, most recently recorded first.
 *
 * No count and no totals block: the route returns rows and never a summary of
 * them, so there is no field here for a figure spanning two runs or two layers.
 */
export interface RunList {
  runs: RunRow[]
  statement: string
}

/**
 * The status a run settles at when the target never echoed the planted nonce.
 *
 * The echo cannot be checked when the run is started: the probe is itself a call
 * on the operator's endpoint, and ADR-0007 puts the halt *ahead* of registration
 * so that a run has spent nothing by the time it asks for consent. So the failure
 * this screen has to recover from arrives as a run status and not as a response
 * to the registration request, and it is matched by name rather than by reading
 * the statement, because the statement is prose written for a human.
 */
export const REGISTRATION_REFUSED = 'registration_refused'

/**
 * What became of a registration request.
 *
 * `refused` is the bench declining — a nonce it never issued, an incomplete
 * attestation, a declaration it will not accept — and it carries the bench's own
 * words. `unreachable` is no answer at all, which is a different fact and gets a
 * different sentence: the operator has an API to start, not a form to fix.
 */
export type StartOutcome =
  | { kind: 'registered'; run: RunStarted }
  /**
   * The bench said no, in its own sentence and — where it named one — at a field.
   *
   * `fields` is always present and often empty: a refusal about the registration
   * has no input to land on, and the screen shows the statement over the form for
   * it. Where the API's own validation refused a body field, the entry carries the
   * `loc` path the screen names that input by (ADR-0076), so the message reaches
   * the field rather than the top of the page.
   *
   * `Refusal` named rather than its two fields spelled out again here, so that a
   * refusal travels as the one value `refusalRead` returns and the register screen
   * has nothing to reassemble.
   */
  | ({ kind: 'refused' } & Refusal)
  | { kind: 'unreachable'; statement: string }

const UNREACHABLE =
  'the bench did not answer, so it is not known whether it recorded this ' +
  'registration. Treat the nonce as spent: check that the API is running, then ' +
  'plant the value the bench issues next and register again.'

/**
 * Register a target: record the attestation, declare the estimate, and halt.
 *
 * A `202` means the run exists and is holding its interrupt, which is *before*
 * anything has been sent to the target. It does not mean the target echoed the
 * nonce; nothing has asked it yet.
 */
export async function startRun(body: StartRunBody): Promise<StartOutcome> {
  let response: Response
  try {
    response = await fetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return { kind: 'unreachable', statement: `${UNREACHABLE} (${unreachable})` }
  }
  if (response.ok) {
    return { kind: 'registered', run: (await response.json()) as RunStarted }
  }
  return { kind: 'refused', ...(await refusalRead(response)) }
}

/** Where one run has got to, or the reason this app could not find out. */
export async function runStanding(runId: string): Promise<RunStanding> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) {
    throw new Error(
      `the bench has no run ${runId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as RunStanding
}

/**
 * The same route, read wide: the run's position and spend in both layers.
 *
 * Two functions over one route rather than one function two callers narrow, so
 * that the register screen keeps the read it was given. Nothing about this request
 * touches the target — polling a run's standing is a question put to the bench.
 */
export async function runProgress(runId: string): Promise<RunProgress> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) {
    throw new Error(
      `the bench has no run ${runId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as RunProgress
}

/**
 * What became of an answer to an interrupt.
 *
 * `no_longer_waiting` is its own outcome rather than a refusal, because it is the
 * one refusal that has already decided the run: an interrupt is answered once, and
 * a `409` means either that it was answered already or that the hour ran out and
 * the graph was told nobody answered. Either way the run is settled and the screen
 * has a standing to read rather than an answer to retry — offering a retry would be
 * offering to consent to a spend that already happened or already will not.
 */
export type ApprovalOutcome =
  | { kind: 'answered'; run: RunStarted }
  | { kind: 'no_longer_waiting'; statement: string }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

/**
 * Answer one run's interrupt.
 *
 * **This is the only function in this app that can cause a call on the target**,
 * and only ever with a `confirmed: true` that `interrupt.ts` refused to build
 * without an explicit confirmation. A `confirmed: false` goes on the wire too, and
 * that is deliberate: it records the run as *declined* by a person rather than
 * leaving it to time out as *unanswered*, and the bench's own sentence for it says
 * that nothing was sent to the target and nothing was spent.
 */
export async function answerTheInterrupt(
  runId: string,
  body: ApprovalBody,
): Promise<ApprovalOutcome> {
  let response: Response
  try {
    response = await fetch(`/runs/${encodeURIComponent(runId)}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return {
      kind: 'unreachable',
      statement: `${ANSWER_UNREACHABLE} (${unreachable})`,
    }
  }
  if (response.ok) {
    return { kind: 'answered', run: (await response.json()) as RunStarted }
  }
  const statement = await refusalIn(response)
  if (response.status === 409) {
    return { kind: 'no_longer_waiting', statement }
  }
  return { kind: 'refused', statement }
}

/** Where the runs on the record are listed. The path a run is started at, read. */
export const RUNS_PATH = '/runs'

/**
 * The runs this bench has on the record, with calls spent per layer.
 *
 * Takes no run id, because it is not about one run — and it is still under `/runs`
 * rather than under `/bench`, because a list of somebody's runs is about their
 * targets and `/bench` is the prefix whose subject is the instrument (ADR-0018).
 *
 * A read, and a bench that has started nothing answers with no rows rather than
 * with a refusal: a fresh deployment is in exactly that state.
 */
export async function benchRuns(): Promise<RunList> {
  return (await fetched(RUNS_PATH, 'list of runs')) as RunList
}
