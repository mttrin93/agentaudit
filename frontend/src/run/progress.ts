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

import { readFamily } from '../families'
import type {
  AdaptiveProgress,
  AttemptExchange,
  FamilyRun,
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
}

/*
 * `callsNote` and `found` were here, and both are gone.
 *
 * `callsNote` said that calls are not attempts and that the figure is this layer's
 * alone; `found` said what the layer had found so far, or that it was absent rather
 * than zero. Two standing paragraphs under every layer block on two screens, while
 * the run they describe was moving.
 *
 * **What they explained is still true and is carried by the wire, not by prose.**
 * `calls_spent` is per layer and there is no field anywhere that sums the two.
 * `succeeded_attempts` and `adaptive_findings` are `null` — not `0` — until the layer
 * has attempted something, which is the absent-rather-than-zero distinction itself,
 * asserted in `test_api_runs.py`. What is gone from the screens with the prose is the
 * two counts: a run in flight now shows its position and its calls, and what it found
 * is read off the finished run's report.
 */

/** The scored layer: family, case, attempt — and a count of verdicts, not findings. */
export function scoredReading(scored: ScoredProgress): LayerReading {
  const at = scored.position
  return {
    layer: 'scored',
    title: 'Scored layer',
    reached: scored.reached,
    units: SCORED_UNITS,
    at: at === null ? null : [readFamily(at.family), at.case_id, `${at.attempt}`],
    statement: scored.statement,
    callsSpent: scored.calls_spent,
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
    at: at === null ? null : [readFamily(at.family), `${at.episode}`, `${at.turn}`],
    statement: adaptive.statement,
    callsSpent: adaptive.calls_spent,
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

// --- the six families, while the run is going ------------------------------------

/**
 * One family's row: the counts it was served, and the three lengths they draw.
 *
 * The same reading the gate screen draws for a gate run, over one target instead of
 * three agents (`console/gaterun.ts`). Two readings of the same six families, in the
 * same order: how much of the work is done, and how it has been going.
 *
 * **Three lengths against one denominator.** `done` is the share of this family's
 * attempts that have come back, and `held` and `broke` are how those same attempts
 * were answered — all three taken against `of`, so what is left of a bar is what has
 * not been attempted yet. Drawn against the attempts made so far instead, the two
 * verdict lengths would fill the bar from the first verdict onwards: a rate with no
 * denominator, which is the one figure this project exists to stop being read
 * (ADR-0005).
 */
export interface FamilyRow {
  family: string
  name: string
  attempted: number
  of: number
  notRun: string
  done: string
  held: string
  broke: string
}

/**
 * The six families as rows, in the order the route served them.
 *
 * The counts are carried and never recomputed — a console that added arithmetic to a
 * served figure would be a second scorer. What is computed here is a width, which is
 * a length and not a number anybody reads.
 */
export function familyRows(progress: RunProgress): readonly FamilyRow[] {
  return progress.families.map((family: FamilyRun) => ({
    family: family.family,
    name: readFamily(family.family),
    attempted: family.attempted,
    of: family.of,
    notRun: family.not_run,
    done: share(family.attempted, family.of),
    held: share(family.resisted, family.of),
    broke: share(family.succeeded, family.of),
  }))
}

/** A segment's length, and `0%` for a family that has not started or has no cases. */
function share(count: number, of: number): string {
  if (of === 0 || count === 0) {
    return '0%'
  }
  return `${Number(((count / of) * 100).toFixed(4))}%`
}

// --- the last exchange -----------------------------------------------------------

/** One attempt drawn as an exchange: the attack, and the answer to it. */
export interface PayloadRow {
  key: string
  sent: string
  reply: string
}

/**
 * The last attempt the route served, which is one, or none before the first.
 *
 * A list rather than a value, and mapped rather than read at `[0]`, because the empty
 * case is a state the screen draws in words — and because how many the route serves is
 * the route's answer, not this module's assumption about it.
 *
 * Nothing here is a finding. A finding is a verdict plus its narrative and it is
 * written in the report; this is the exchange, and the screen draws it uncoloured.
 */
export function payloads(progress: RunProgress): readonly PayloadRow[] {
  return progress.recent.map((one: AttemptExchange) => ({
    key: `${one.case_id}/${one.attempt}`,
    sent: one.sent,
    reply: one.reply,
  }))
}
