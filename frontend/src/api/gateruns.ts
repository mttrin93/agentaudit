/**
 * `GET /gate-runs`, `POST /gate-runs` and the approval in front of one — the bench
 * proving itself, from a browser.
 *
 * Its own module in #14's split by API area. The console may start a gate run
 * (ADR-0021) and this is the whole of what it may say to do it: an attestation, a
 * price, and an answer to the halt. A gate run is not a run — different record,
 * different status, different routes — and no type here is shared with one beyond
 * the attestation and cost bodies in `contracts.ts`, which are the two things both
 * entry points genuinely declare.
 *
 * **The refusal is a first-class answer.** `MayNotStart` carries the bench's own
 * sentence, so a deployment that ships no reference agents offers no control rather
 * than failing when one is pressed.
 */

import type {
  AdaptiveProgress,
  ApprovalBody,
  AttestationBody,
  CostBody,
  DeclaredRule,
  GateDecided,
  ScoredProgress,
} from './contracts'
import {
  ANSWER_UNREACHABLE,
  fetched,
  refusalIn,
} from './http'


/** Where a gate run is started, listed and read. Its own family, never `/runs`. */
export const GATE_RUNS_PATH = '/gate-runs'

/**
 * This bench can run a gate, and what starting one would do first.
 *
 * `available` is the field the screen branches on and it is a literal on both
 * shapes, so *can* and *cannot* are two facts rather than one record with empty
 * fields — the idiom `GateCitation` already uses for a citation and its absence.
 */
export interface MayStart {
  available: true
  library: string
  statement: string
}

/**
 * This bench cannot run a gate, and the named reason it cannot.
 *
 * Four names on the wire, and two of them are permanent facts about the deployment
 * while two are about right now. The screen states whichever it is told and offers
 * no control either way: *this build ships no reference agents* is not answered by
 * trying again, and *a gate run is already holding the library* is.
 */
export interface MayNotStart {
  available: false
  refusal: string
  stated: string
}

export type GateRunStart = MayStart | MayNotStart

/**
 * One gate run on the record: when, where it got to, what it spent per layer.
 *
 * A row and never a decision. `spent` is two keys and there is no third: the two
 * layers are enforced against separate counters and nothing adds them (ADR-0010).
 */
export interface GateRunRow {
  gate_run_id: string
  recorded_at: string
  status: string
  statement: string
  spent: Record<string, number>
}

/** The gate runs on the record, and whether another may start right now. */
export interface GateRuns {
  start: GateRunStart
  gate_runs: GateRunRow[]
  statement: string
}

/**
 * What a gate run's scored layer will cost, in the units it is declared in.
 *
 * Attempts over cases over agents, exact because it is a multiplication. Not one
 * numeric field here appears on the adaptive figure below: the two layers share no
 * number, so there is no name in this app under which a total could be built.
 */
export interface ScoredEstimate {
  layer: string
  attempt_calls: number
  attempt_ceiling: number
  cases: number
  attempts_per_case: number
  kind: string
  basis: string
  cost: string
  statement: string
}

/**
 * What a gate run's adaptive layer may cost, in the units *it* is declared in.
 *
 * Turns over episodes over families over agents, and a bound rather than a figure:
 * an attacker that chooses its own route has no exact cost, and an average here
 * would invite a gate run to exceed what was agreed to (ADR-0007).
 */
export interface AdaptiveEstimate {
  layer: string
  turn_calls: number
  turn_ceiling: number
  turns_per_episode: number
  episodes_per_family: number
  kind: string
  basis: string
  cost: string
  statement: string
}

/** Two figures, two ceilings, and no third field anywhere on the response. */
export interface GateRunEstimate {
  scored: ScoredEstimate
  adaptive: AdaptiveEstimate
  currency: string
  statement: string
}

/**
 * A gate run recorded and halted in front of its estimate.
 *
 * The estimate arrives once, here, from the request that created the gate run —
 * the same division `POST /runs` makes, because the route that reports progress
 * reports no estimate: nothing on it spans the two layers.
 */
export interface GateRunStarted {
  gate_run_id: string
  status: string
  statement: string
  estimate: GateRunEstimate
  library: string
  agents: string[]
  cases: number
}

/** The three attestation statements and the declared cost, and nothing else. */
export interface StartGateRunBody {
  attestation: AttestationBody
  cost: CostBody
}

/** What a gate run wrote to the case library, and where it wrote it. */
export interface WroteBack {
  library: string
  readings: number
  unread: string[]
  retired: string[]
  stated: string
}

/**
 * Where one gate run has got to, and what it decided if it has.
 *
 * `rule` is above `decision` on the wire as it is on the screen: an outcome read
 * with no bar beside it is a verdict somebody trusted (ADR-0003). Progress is the
 * same two per-layer readings a run reports, because a position is neither a run
 * nor a gate run and the units are the units either way.
 */
export interface GateRunReading {
  gate_run_id: string
  status: string
  statement: string
  rule: DeclaredRule
  scored: ScoredProgress
  adaptive: AdaptiveProgress
  families: FamilyProgress[]
  /**
   * The last attempt only, or empty before the first has come back.
   *
   * A list of one and not a field, because *nothing has come back yet* is a real
   * state and an empty list says it without a null. The route carried five for a
   * while; the sequence of what a run did is on the record it writes, not here.
   */
  recent: AttemptPayload[]
  decision: GateDecided | null
  written: WroteBack | null
}

/**
 * One reference agent's share of one family: how far, and how it is going.
 *
 * Two counts for how far and two for how the attempts made so far were answered. The
 * three arrive in construction order — hardened, weak, trivial — read off the record's
 * own roles rather than off a name.
 *
 * `resisted` and `succeeded` split `attempted` and neither is a rate: they are drawn
 * against `of`, this agent's own denominator, so a bar of them fills as the run goes
 * instead of reading as a finished figure. In the attacker's sense, as everything in
 * this bench is counted — `succeeded` is the attack working, so a trivial agent with a
 * high `succeeded` is the contrast doing its job.
 */
export interface AgentProgress {
  agent: string
  attempted: number
  of: number
  resisted: number
  succeeded: number
}

/**
 * How far one family has got, over its own denominator.
 *
 * Six of these, always, whether a family has started or not. **Neither the count nor
 * the denominator may be added across the six**: a run-wide figure would be a total
 * across six denominators, which is the arithmetic ADR-0005 refuses. And there is no
 * count of verdicts here — how well a family is going is a rate with an interval and
 * a band, and it belongs to the decision.
 */
export interface FamilyProgress {
  family: string
  attempted: number
  of: number
  agents: AgentProgress[]
}

/**
 * One attempt as evidence: the message sent, the reply, and the verdict on it.
 *
 * Served for a gate run because the three agents are this bench's own equipment
 * talking to itself. `verdict` is the attacker's point of view — *succeeded* is the
 * attack working — and `verdict_class` is how that was reached, which the screen
 * prints beside it because a deterministic *resisted* and a judged one are not the
 * same claim (ADR-0004).
 */
export interface AttemptPayload {
  family: string
  case_id: string
  agent: string
  attempt: number
  sent: string
  reply: string
  verdict: string
  verdict_class: string
  status_code: number
  sends: number
}

/**
 * The gate runs on the record, and whether this bench may start another.
 *
 * Read before a control is drawn rather than after one is pressed: a screen that
 * offered a start button on a deployment which ships no reference agents would be
 * offering an operation the bench refuses, and the refusal it would then show is a
 * fact the screen could have stated in the first place.
 */
export async function gateRuns(): Promise<GateRuns> {
  return (await fetched(GATE_RUNS_PATH, 'gate runs')) as GateRuns
}

/**
 * Start a gate run: record the three statements, declare the estimate, and halt.
 *
 * A `202` means the gate run exists and is holding its interrupt, which is before
 * anything has been sent to a reference agent and before one case record has been
 * written to. It also means this bench's case library is now held by it — a second
 * gate run is refused rather than queued, and the refusal names the holder.
 *
 * The refusals are outcomes rather than exceptions, on `startRun`'s reasoning: a
 * bench that ships no reference agents, holds no writable library, has no
 * adjudicating instrument, or is already running a gate is a state the operator has
 * to be told about in words, and an exception would lose the sentence on the way to
 * whatever caught it.
 */
export async function startGateRun(
  body: StartGateRunBody,
): Promise<GateRunOutcome> {
  let response: Response
  try {
    response = await fetch(GATE_RUNS_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return { kind: 'unreachable', statement: `${GATE_RUN_UNREACHABLE} (${unreachable})` }
  }
  if (response.ok) {
    return { kind: 'started', gateRun: (await response.json()) as GateRunStarted }
  }
  return { kind: 'refused', statement: await refusalIn(response) }
}

/**
 * What became of a request to start a gate run.
 *
 * `refused` carries the bench's own sentence, which is the one that says which of
 * the four reasons it was. `unreachable` is no answer at all: nothing was started,
 * and the operator has an API to check rather than a form to fix.
 */
export type GateRunOutcome =
  | { kind: 'started'; gateRun: GateRunStarted }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

const GATE_RUN_UNREACHABLE =
  'the bench did not answer, so it is not known whether a gate run was started. ' +
  'Read the list of gate runs before asking again: one holds the case library ' +
  'while it goes, and a second would be refused rather than queued.'

/**
 * Answer a gate run's interrupt. A `confirmed: true` is the only thing that spends.
 *
 * The same body a run's interrupt takes, deliberately: the answer to an interrupt is
 * the consent mechanism itself and there is one of those in this app (ADR-0007).
 * What is not shared is the record it answers — this posts under `/gate-runs`, and a
 * run id here is a `404` rather than an interrupt answered for something else.
 *
 * A `confirmed: false` goes on the wire too, for the reason a declined run does: it
 * records the gate run as declined by a person rather than leaving it to time out as
 * unanswered, and the bench's own sentence for it says that nothing was sent and not
 * one case record was written to.
 */
export async function answerTheGateRunsInterrupt(
  gateRunId: string,
  body: ApprovalBody,
): Promise<GateApprovalOutcome> {
  let response: Response
  try {
    response = await fetch(
      `${GATE_RUNS_PATH}/${encodeURIComponent(gateRunId)}/approval`,
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
    return { kind: 'answered', gateRun: (await response.json()) as GateRunStarted }
  }
  const statement = await refusalIn(response)
  if (response.status === 409) {
    return { kind: 'no_longer_waiting', statement }
  }
  return { kind: 'refused', statement }
}

/** What became of an answer to a gate run's interrupt. */
export type GateApprovalOutcome =
  | { kind: 'answered'; gateRun: GateRunStarted }
  | { kind: 'no_longer_waiting'; statement: string }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

/**
 * Where one gate run has got to, per layer, and what it decided if it has.
 *
 * Polled while it goes. Nothing about this request touches a reference agent —
 * asking a gate run how it is going is a question put to the bench.
 */
export async function gateRunReading(gateRunId: string): Promise<GateRunReading> {
  const response = await fetch(
    `${GATE_RUNS_PATH}/${encodeURIComponent(gateRunId)}`,
  )
  if (!response.ok) {
    throw new Error(
      `the bench has no gate run ${gateRunId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as GateRunReading
}
