/**
 * Where a run has got to, read one layer at a time, with nothing that spans them.
 *
 * The scored layer's position is **family, case and attempt**; the adaptive
 * layer's is **family, episode and turn**. Those are six words for six things and
 * not two sets of three synonyms (CONTEXT.md): an attempt is the unit of a
 * denominator and a turn is deliberately not one, because turns inside an episode
 * are dependent by construction and no rate is computed over them. So this module
 * builds one reading per layer, each carrying the units it is counted in, and
 * there is no function here that takes both.
 *
 * **Calls spent are two numbers and never three.** `RunProgress` reports the spend
 * inside `scored` and `adaptive` and nowhere else, and this app adds nothing to
 * that: a blended total hides which half of the run is spending the operator's
 * budget (ADR-0007), and no adaptive quantity may reach a scored one (ADR-0010).
 * `progress.test.ts` asserts the absence by scanning the whole view for the sums
 * it must not contain.
 *
 * **Three things a run can stop on, and none of them is a security result.** A
 * ceiling reached is the budget working, so it is reported as an **abort**, and the
 * episode it cut short is recorded as **censored** — the attacker stopped, and a
 * target that was never given the chance to hold must not read as one that did
 * (ADR-0007, ADR-0011). A transport failure is reported under its own name of the
 * seven the contract defines, because a timeout is capacity, a rejected token is
 * configuration, a malformed body is a contract breach and a quota is a quota, and
 * one word for all of them sends every one to the same wrong place. Neither is a
 * verdict, and `EpisodeOutcome` has exactly one member for the same reason the
 * bench raises `TargetUnreachable` rather than returning it: there is no name in
 * this module for an episode that resisted, so nothing here can assign one.
 */

import type {
  AdaptiveProgress,
  RunProgress,
  ScoredProgress,
  TransportOutcome,
} from '../api/bench'
import type { Layer } from './interrupt'
import { AWAITING_APPROVAL } from './interrupt'

/** The scored layer's three units, in the order a position states them. */
export const SCORED_UNITS = ['family', 'case', 'attempt'] as const

/** The adaptive layer's three, which are three different things. */
export const ADAPTIVE_UNITS = ['family', 'episode', 'turn'] as const

/**
 * How this screen may describe an episode that ended without breaking a target.
 *
 * One member, and the absence of a second is the whole point: an episode stopped
 * by a turn cap or a ceiling is **censored**, and *resisted* is not a value this
 * type can hold. A widened union here is the failure ADR-0011 names — the
 * attacker's exhaustion read as the target's strength — so it is carried by the
 * type rather than by a comment asking for care.
 */
export type EpisodeOutcome = 'censored'

export const CENSORED_NOT_RESISTED =
  'The episode the ceiling cut short is recorded as censored: the attacker ' +
  'stopped, and an episode that was stopped is evidence about the budget rather ' +
  'than about the target. A censored episode carries no rate and joins no count.'

/** How an episode this run was inside is recorded, and the sentence for it. */
export interface EpisodeReading {
  outcome: EpisodeOutcome
  note: string
}

/** The only episode reading this screen can build. */
const CENSORED: EpisodeReading = {
  outcome: 'censored',
  note: CENSORED_NOT_RESISTED,
}

/** One layer's reading, in that layer's own units and figures. */
export interface LayerReading {
  layer: Layer
  title: string
  /** Whether this layer has started, as the bench states it rather than inferred. */
  reached: boolean
  /** The three units this layer's position is counted in. */
  units: readonly [string, string, string]
  /** One value per unit, or `null` while the layer has attempted nothing. */
  at: readonly [string, string, string] | null
  /** The bench's own sentence about the position, carried unedited. */
  statement: string
  /** Calls this layer has put on the wire. Its own figure, added to nothing. */
  callsSpent: number
  callsNote: string
  /** What this layer has found so far, or why that is absent rather than zero. */
  found: string
}

/** The scored layer: family, case, attempt — and a count of verdicts, not findings. */
export function scoredReading(scored: ScoredProgress): LayerReading {
  const at = scored.position
  return {
    layer: 'scored',
    title: 'Scored layer',
    reached: scored.reached,
    units: SCORED_UNITS,
    at: at === null ? null : [at.family, at.case_id, `${at.attempt}`],
    statement: scored.statement,
    callsSpent: scored.calls_spent,
    callsNote:
      'Calls this layer has put on the wire, retries included, and the nonce ' +
      'probe among them. Calls are not attempts, and this figure is this layer’s ' +
      'alone.',
    found:
      scored.succeeded_attempts === null
        ? 'No attempt has come back yet, so the attempts that succeeded are ' +
          'absent rather than zero: a count over an empty population is not a ' +
          'small number, and a zero beside a position in flight would read as a ' +
          'target that resisted something it was never asked.'
        : `${scored.succeeded_attempts} of the attempts recorded so far ` +
          'succeeded. A count of verdicts and not of findings — a finding is a ' +
          'verdict plus its narrative, and the report is where that is written.',
  }
}

/** The adaptive layer: family, episode, turn — and nothing that is scored. */
export function adaptiveReading(adaptive: AdaptiveProgress): LayerReading {
  const at = adaptive.position
  return {
    layer: 'adaptive',
    title: 'Adaptive layer',
    reached: adaptive.reached,
    units: ADAPTIVE_UNITS,
    at: at === null ? null : [at.family, `${at.episode}`, `${at.turn}`],
    statement: adaptive.statement,
    callsSpent: adaptive.calls_spent,
    callsNote:
      'Calls this layer has put on the wire, under its own ceiling. Enforced ' +
      'separately from the scored layer’s, so neither can borrow what the other ' +
      'did not spend.',
    found:
      adaptive.adaptive_findings === null
        ? 'No episode has ended yet, so the routes found are absent rather than ' +
          'zero: a zero here would read as an attacker that ran out of ideas, ' +
          'which is the reading censored exists to keep apart.'
        : `${adaptive.adaptive_findings} episode(s) found a route. An adaptive ` +
          'finding carries no rate, no interval, no band and no D, and it is ' +
          'never added to the scored layer’s count.',
  }
}

/** Which of the run's states this is, in the words the record keeps. */
export type StandingKind =
  | 'holding'
  | 'running'
  | 'completed'
  | 'declined'
  | 'unanswered'
  | 'registration_refused'
  | 'aborted'
  | 'transport'
  | 'stopped'

/**
 * What the run is doing, or what stopped it, under its own name.
 *
 * `name` is the bench's own word — a status, or one of the seven transport
 * failures — carried rather than translated, so that a quota and an outage stay
 * two different things all the way to the screen. `statement` is the bench's
 * sentence, unedited.
 */
export interface Standing {
  kind: StandingKind
  name: string
  heading: string
  statement: string
  /** How an episode this run was inside is recorded. Never anything but censored. */
  episode: EpisodeReading | null
  /** Said out loud whenever what stopped the run is not a fact about the target. */
  notASecurityResult: string
  /** Whether there is any point polling again. */
  inFlight: boolean
}

/** Whether a run in this state is still going, or has stopped for good. */
export function stillGoing(status: string): boolean {
  return status === AWAITING_APPROVAL || status === 'running'
}

/**
 * The run's standing, decided on the transport outcome first and the status after.
 *
 * The transport outcome comes first because it is the more specific fact: a run
 * that stopped on the wire is *failed*, and a screen that read the status alone
 * would report it as a run that stopped for no stated reason while the name of the
 * failure sat unread in the field beside it.
 */
export function standing(progress: RunProgress): Standing {
  if (progress.transport !== null) {
    return transportStanding(progress.transport)
  }
  switch (progress.status) {
    case AWAITING_APPROVAL:
      return {
        kind: 'holding',
        name: progress.status,
        heading: 'Holding at the approval interrupt',
        statement: progress.statement,
        episode: null,
        notASecurityResult: '',
        inFlight: true,
      }
    case 'running':
      return {
        kind: 'running',
        name: progress.status,
        heading: 'Running, under the ceiling that was confirmed',
        statement: progress.statement,
        episode: null,
        notASecurityResult: '',
        inFlight: true,
      }
    case 'aborted':
      return {
        kind: 'aborted',
        name: progress.status,
        heading: 'Aborted: the run stopped rather than spend past its ceiling',
        statement: progress.statement,
        // The one place this screen names an episode's outcome, and the only name
        // it has for one.
        episode: CENSORED,
        notASecurityResult:
          'A ceiling reached is the budget working and it is not a result about ' +
          'the target. The run is void rather than smaller: a suite that stopped ' +
          'early measured fewer attempts than the rate it would report is ' +
          'denominated on.',
        inFlight: false,
      }
    case 'completed':
      return {
        kind: 'completed',
        name: progress.status,
        heading: 'Finished, inside the ceiling that was confirmed',
        statement: progress.statement,
        episode: null,
        notASecurityResult: '',
        inFlight: false,
      }
    case 'declined':
      return {
        kind: 'declined',
        name: progress.status,
        heading: 'Declined: nothing was sent and nothing was spent',
        statement: progress.statement,
        episode: null,
        notASecurityResult: '',
        inFlight: false,
      }
    case 'unanswered':
      return {
        kind: 'unanswered',
        name: progress.status,
        heading: 'Unanswered: the interrupt was never answered',
        statement: progress.statement,
        episode: null,
        notASecurityResult:
          'Nobody said no and nobody said anything, which are different facts ' +
          'about the same run. Either way nothing was sent to the target and ' +
          'nothing was spent.',
        inFlight: false,
      }
    case 'registration_refused':
      return {
        kind: 'registration_refused',
        name: progress.status,
        heading: 'The target did not echo the nonce, so no attempt was made',
        statement: progress.statement,
        episode: null,
        notASecurityResult:
          'A target that did not prove control of itself was not measured. This ' +
          'is not a defence and it is not a finding: no attempt was made.',
        inFlight: false,
      }
    default:
      return {
        kind: 'stopped',
        name: progress.status,
        heading: `The run stopped as ${progress.status}`,
        statement: progress.statement,
        episode: null,
        notASecurityResult:
          'A run that stopped without finishing produced no report and nothing ' +
          'here is a finding about the target.',
        inFlight: false,
      }
  }
}

/** One transport outcome, under its own name and never as a security result. */
function transportStanding(transport: TransportOutcome): Standing {
  return {
    kind: 'transport',
    name: transport.failure,
    heading: `The endpoint stopped answering: ${transport.failure}`,
    statement: transport.statement,
    episode: null,
    notASecurityResult:
      'No attempt is recorded and nothing here is a security result. This is the ' +
      'endpoint, reported under the name of what it did — a timeout is capacity, ' +
      'a rejected token is configuration, a malformed body is a contract breach ' +
      'and a rate limit is a quota. The findings the run had are the findings it ' +
      'still has.',
    inFlight: false,
  }
}

/** Everything the progress half of the screen shows, per layer, as data. */
export interface ProgressView {
  standing: Standing
  scored: LayerReading
  adaptive: LayerReading
}

/**
 * The two layers and the run's standing, built together and joined nowhere.
 *
 * One function returning three records rather than one record with a summary on
 * it: there is no field here for a figure over both layers, so a total would have
 * to be written out by hand in front of the two labels saying what was being
 * added, which is exactly the edit this shape is meant to make visible.
 */
export function progressView(progress: RunProgress): ProgressView {
  return {
    standing: standing(progress),
    scored: scoredReading(progress.scored),
    adaptive: adaptiveReading(progress.adaptive),
  }
}
