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
 * **Things a run can stop on, and none of them is a security result.** A ceiling
 * reached is the budget working and an operator pressing stop is a person deciding
 * (ADR-0007, ADR-0114); both are reported as an **abort**, under that word alone,
 * because which of the two it was is in the sentence the bench settled the run with
 * and not in a heading this module writes. That an episode either one cut short is
 * recorded as **censored** is said there too — the attacker stopped, and a target
 * never given the chance to hold must not read as one that did (ADR-0011) — and
 * this module no longer says it a second time in its own words. A transport failure
 * is reported under its own name of the seven the contract defines, because a
 * timeout is capacity, a rejected token is configuration, a malformed body is a
 * contract breach and a quota is a quota, and one word for all of them sends every
 * one to the same wrong place. None of them is a verdict: there is no name in this
 * module for an episode that resisted, so nothing here can assign one.
 */

import { readFamily, readName } from '../families'
import type {
  AdaptiveProgress,
  AttemptExchange,
  ElectiveFamilyRun,
  FamilyRun,
  RunProgress,
  ScoredProgress,
  TransportOutcome,
} from '../api/bench'
import type { RunEpisodes } from '../api/attempts'
import type { Layer } from './interrupt'
import { AWAITING_APPROVAL } from './interrupt'

/** The scored layer's three units, in the order a position states them. */
export const SCORED_UNITS = ['family', 'case', 'attempt'] as const

/**
 * The adaptive layer's own, which are different things from the scored layer's.
 *
 * Four where the scored layer's are three, and the fourth is not a unit the layer
 * counts in: `schedule` is which of the selected schedules the episode being counted
 * is running under. It is read out in the same idiom because a person watching a run
 * needs it in the same breath — a run that selected both attacks every family under
 * each, and *family, episode and turn* alone cannot say which pass the turn on the
 * screen belongs to (ADR-0099).
 */
export const ADAPTIVE_UNITS = ['family', 'schedule', 'episode', 'turn'] as const

/** One layer's reading, in that layer's own units and figures. */
export interface LayerReading {
  layer: Layer
  title: string
  /** Whether this layer has started, as the bench states it rather than inferred. */
  reached: boolean
  /**
   * The parts this layer's position is stated in, in the order it states them.
   *
   * A list and not a fixed-length tuple, because the two layers state a different
   * number of parts: the scored layer's three are family, case and attempt, and the
   * adaptive layer's four are family, schedule, episode and turn (ADR-0099). What
   * keeps the two from being read against each other is that neither list is built
   * here from the other's — `SCORED_UNITS` and `ADAPTIVE_UNITS` are two constants, and
   * there is no function in this module that takes both layers.
   */
  units: readonly string[]
  /**
   * One value per unit, in the same order, or `null` while the layer has attempted
   * nothing.
   *
   * As long as `units` by construction — the two are built in one expression per layer
   * — and the panel walks the units and indexes this, so a value with no unit above it
   * would be a value nothing on the screen names.
   */
  at: readonly string[] | null
  /**
   * The bench's own sentence about the position, carried unedited.
   *
   * Drawn where there is no position to draw. The run screen shows the units and
   * their values and not this, because against a position the sentence is those
   * values read out in prose; the gate screen shows it for a layer a run has not
   * reached, where it is the only thing to show.
   */
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
    at:
      at === null
        ? null
        : [
            readFamily(at.family),
            // The wire name read as words, like every other member name on these
            // screens: an operator reading `tree jailbreak` here and grepping
            // `tree_jailbreak` in a settings response is looking at the same word.
            readName(at.schedule),
            `${at.episode}`,
            `${at.turn}`,
          ],
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
  /**
   * The state, in as few words as will name it.
   *
   * It is the screen's `h1` and the whole of its header, so it says what the run is
   * doing and stops. These were sentences — *Running, under the ceiling that was
   * confirmed*, *Aborted: the run stopped rather than spend past its ceiling* — each
   * of them a clause of explanation welded to the one word the heading is for, and
   * each of them said again underneath in `statement`, which is the bench's own
   * wording and the one that should carry it. A transport failure keeps its name in
   * the heading, because there the name *is* the state.
   *
   * The interrupt is the exception and it is not a state at all: while a run holds,
   * the screen is the halt, and what it has to say at the top is the question it is
   * asking — *what this run will cost*, which used to be the heading of the section
   * under *Holding at the interrupt*. That the run is holding is what that screen
   * being there means.
   */
  heading: string
  statement: string
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
        heading: 'What this run will cost',
        statement: progress.statement,
        notASecurityResult: '',
        inFlight: true,
      }
    case 'running':
      return {
        kind: 'running',
        name: progress.status,
        heading: 'Running',
        statement: progress.statement,
        notASecurityResult: '',
        inFlight: true,
      }
    case 'aborted':
      return {
        kind: 'aborted',
        name: progress.status,
        // *Aborted*, and not *aborted at the ceiling*: a ceiling is one of two
        // things that abort a run and an operator pressing stop is the other
        // (ADR-0114), so a heading naming the ceiling is wrong on half the runs
        // it is drawn over. Which of the two it was is in the run's own sentence,
        // where the bench writes it.
        heading: 'Aborted',
        statement: progress.statement,
        // Neither the censored episode nor the void-rather-than-smaller sentence is
        // said here any more. The bench settles every abort with both of them in the
        // statement below, and this screen was saying them a second time in its own
        // words — the same fact twice, once from the record and once hardcoded.
        notASecurityResult: '',
        inFlight: false,
      }
    case 'completed':
      return {
        kind: 'completed',
        name: progress.status,
        heading: 'Finished',
        statement: progress.statement,
        notASecurityResult: '',
        inFlight: false,
      }
    case 'declined':
      return {
        kind: 'declined',
        name: progress.status,
        heading: 'Declined',
        statement: progress.statement,
        notASecurityResult: '',
        inFlight: false,
      }
    case 'unanswered':
      return {
        kind: 'unanswered',
        name: progress.status,
        heading: 'Unanswered',
        statement: progress.statement,
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
        heading: 'The nonce was not echoed',
        statement: progress.statement,
        notASecurityResult:
          'A target that did not prove control of itself was not measured. This ' +
          'is not a defence and it is not a finding: no attempt was made.',
        inFlight: false,
      }
    default:
      return {
        kind: 'stopped',
        name: progress.status,
        heading: `Stopped as ${progress.status}`,
        statement: progress.statement,
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
 * How much of the scored layer's planned work has been done.
 *
 * **A share of the work and never a rate.** The two numbers are attempts *made* over
 * attempts *planned* — both counts of what this bench has done — and neither is a
 * reading taken against the target. That is the line
 * [ADR-0110](../../../docs/adr/0110-a-run-may-show-how-much-of-its-own-work-is-done.md)
 * draws through ADR-0005's *no total across them*: what may not be added is the
 * families' **rates**, because a rate has a denominator of its own and a mean over six
 * of them is a figure no family was ever measured at. A count of attempts made has no
 * such denominator, and the run's own completion is the one question this screen
 * exists to answer.
 *
 * **The six alone**, because the two tiers are two closed sets this app concatenates
 * nowhere (ADR-0035 §2). A bar over nine would be a denominator built from both.
 *
 * **The scored layer alone**, because an attempt and a turn are different units and no
 * adaptive quantity may reach a scored one (ADR-0010). The adaptive layer's position is
 * on its own line, in its own units, as it was.
 *
 * Families the plan dropped contribute nothing to either number: their `of` is zero, so
 * a run that is not attacking a family is not a run that is behind on it.
 */
export interface RunShare {
  made: number
  planned: number
  /** The width of the filled part, for the bar. A length, and not a number read. */
  done: string
  /** The same length as a whole percent, which is the only figure of it printed. */
  percent: string
}

/**
 * The share, off the six families' served counts and nothing else.
 *
 * Rounded down to a whole percent for printing: a run at 99.6% of its plan has not
 * finished, and a figure that says *100%* over a bar still moving is the one reading
 * this line must not give.
 */
export function scoredShare(progress: RunProgress): RunShare {
  const made = progress.families.reduce((sum, family) => sum + family.attempted, 0)
  const planned = progress.families.reduce((sum, family) => sum + family.of, 0)
  return {
    made,
    planned,
    done: share(made, planned),
    percent: `${planned === 0 ? 0 : Math.floor((made / planned) * 100)}%`,
  }
}

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
  /**
   * The two counts behind `held` and `broke`, carried and never divided.
   *
   * The row prints how many of this family's attempts the target let through beside
   * how many were made, which is two counts over one denominator and not a rate: a
   * rate arrives on the report with its interval and its band, over a denominator that
   * has stopped moving (ADR-0005). Nothing on this screen divides them, and
   * `progress.test.ts` reads the view for the quotient.
   */
  succeeded: number
  resisted: number
  /**
   * How many of this family's answered attempts the target let through, as a percent.
   *
   * A **per-family** rate over that family's own denominator, which is the shape
   * ADR-0005 prescribes — and a point estimate with no interval beside it, over a
   * denominator that is still moving, which is what makes it a reading of the run and
   * not the measurement
   * ([ADR-0111](../../../docs/adr/0111-the-run-screen-shows-a-live-per-family-rate.md)).
   * The figure a recipient is handed arrives on the report with its Wilson interval,
   * its verdict class and its band.
   *
   * Taken over `attempted` and never over `of`: a rate over the plan would count
   * attempts that have not been made yet as attempts the target held, which is the one
   * direction a live figure must not be wrong in.
   *
   * `—` until an attempt has come back, on `succeeded_attempts`' own terms: a family
   * attempted no times has not been let through zero times, and `0%` is the reading
   * that would say it had.
   */
  rate: string
  /**
   * One cell an attempt, in this family's own plan.
   *
   * `of` cells, each naming what is known about one attempt — answered and held,
   * answered and broken, sent and not yet back, or not yet sent. What is drawn is the
   * **counts**, laid out in that order, and never the sequence the attempts actually
   * ran in: the route serves four counts per family and no per-attempt list, so a
   * strip that interleaved them would be this app inventing an order for a reader to
   * read a pattern off.
   */
  cells: readonly Cell[]
  /**
   * Where this family is in the run, in one word.
   *
   * Read off the counts and off the family the scored layer says it is in, and off
   * nothing else. Not a figure and not a verdict: a family that has finished its plan
   * has not defended anything, which is what `held` and `broke` are beside it for.
   */
  state: FamilyState
}

/** What is known about one attempt, for the cell that stands for it. */
export type Cell = 'held' | 'broke' | 'in flight' | 'not attempted'

/** Where a family is in the run's plan. Never a reading of how it answered. */
export type FamilyState = 'complete' | 'running' | 'queued' | 'not run'

function rateOf(succeeded: number, attempted: number): string {
  return attempted === 0 ? '—' : `${Math.round((succeeded / attempted) * 100)}%`
}

/**
 * The family with an attempt on the wire, or no family at all.
 *
 * The position and the status together, because the position alone is not it: it is
 * the last attempt the scored layer *entered*, and it stays on the reading after the
 * run has settled — so a finished suite would keep one cell in flight forever, and an
 * aborted one would show a cell for the attempt it refused to send.
 *
 * Only `running`. A run holding its interrupt has sent nothing, and every other
 * status is a run that has stopped.
 */
function sending(progress: RunProgress): string {
  return progress.status === 'running' ? (progress.scored.position?.family ?? '') : ''
}

/**
 * One family's attempts as cells, from the counts the route serves and the position.
 *
 * In one order every time — held, broken, in flight, not yet attempted — because that
 * order is the only one the served counts support. The strip is a count made legible
 * and it is deliberately not a timeline.
 *
 * **The in-flight cell comes off the position and never off the counts.** It used to
 * be `attempted - resisted - succeeded`, which is always zero: `attempted` counts the
 * attempts on the record, every attempt on the record carries a verdict, and the
 * route builds `succeeded` by subtracting `resisted` from `attempted` for exactly
 * that reason. So the arithmetic could not produce the cell, and the legend named a
 * colour the strip could never draw.
 *
 * What does know is `RunState.enter`, which moves the scored position *to the attempt
 * about to be sent* — so the family the position names has one attempt on the wire,
 * and no other family has any. `inFlight` is that fact, decided by the caller, and it
 * draws one cell out of the ones still waiting: a suite attacks one attempt at a time,
 * and a second cell would be this screen inventing concurrency the bench has not got.
 */
function cellsFor(
  resisted: number,
  succeeded: number,
  attempted: number,
  of: number,
  inFlight: boolean,
): readonly Cell[] {
  const waiting = Math.max(of - attempted, 0)
  // Only out of what is left: a family whose plan is full has nothing on the wire,
  // and a strip that grew a cell to say otherwise would be longer than the plan.
  const onTheWire = inFlight && waiting > 0 ? 1 : 0
  return [
    ...Array<Cell>(resisted).fill('held'),
    ...Array<Cell>(succeeded).fill('broke'),
    ...Array<Cell>(onTheWire).fill('in flight'),
    ...Array<Cell>(waiting - onTheWire).fill('not attempted'),
  ]
}

/**
 * Which of the four words a family's row carries.
 *
 * *not run* first, because a family with no plan is out of the run whatever the
 * counts say; then *running*, which is the scored layer's own position and not a
 * guess off the counts — a family can have attempts back and be the one in flight,
 * and only the position says so.
 *
 * Both names go through `readFamily` before they are compared, which is the one place
 * in this app a family name is not used as a lookup key. The position's family and a
 * row's family are the same closed set arriving by two routes, and the comparison has
 * to survive either spelling of it: the underscore is the only character between them.
 */
function stateOf(row: FamilyRun | ElectiveFamilyRun, running: string): FamilyState {
  if (row.of === 0) {
    return 'not run'
  }
  if (running !== '' && readFamily(row.family) === readFamily(running)) {
    return 'running'
  }
  if (row.attempted >= row.of) {
    return 'complete'
  }
  return row.attempted === 0 ? 'queued' : 'running'
}

/**
 * The six families as rows, in the order the route served them.
 *
 * The counts are carried and never recomputed — a console that added arithmetic to a
 * served figure would be a second scorer. What is computed here is a width, which is
 * a length and not a number anybody reads.
 */
export function familyRows(progress: RunProgress): readonly FamilyRow[] {
  const running = progress.scored.position?.family ?? ''
  const onTheWire = sending(progress)
  return progress.families.map((family: FamilyRun) => ({
    family: family.family,
    name: readFamily(family.family),
    attempted: family.attempted,
    of: family.of,
    notRun: family.not_run,
    done: share(family.attempted, family.of),
    held: share(family.resisted, family.of),
    broke: share(family.succeeded, family.of),
    succeeded: family.succeeded,
    resisted: family.resisted,
    rate: rateOf(family.succeeded, family.attempted),
    cells: cellsFor(
      family.resisted,
      family.succeeded,
      family.attempted,
      family.of,
      onTheWire !== '' && readFamily(family.family) === readFamily(onTheWire),
    ),
    state: stateOf(family, running),
  }))
}

/**
 * The elective families this run asked for, as rows, in the order the route served
 * them.
 *
 * A second function over the second list and never a widening of the one above: the
 * two lists describe two closed sets, this app concatenates them nowhere, and the
 * screen draws the tier's rows after the six's by mapping twice (ADR-0035 §2,
 * ADR-0094). What they share is the row shape, which holds three widths and no
 * arithmetic the gate reads — a length is not a figure, and the reason `FamilyRow` is
 * safe to share is the same reason nothing on this screen is a rate.
 *
 * Empty for a run that asked the tier for nothing, and empty for a run made before
 * the tier could be asked for: the field is absent on the older one, and both are
 * runs whose figures are the six.
 *
 * `notRun` carries `no_case`, and on this screen it decides one word: the count slot
 * reads `not run` instead of `0 / 30`. The **sentence** is not drawn. It is one
 * paragraph per family over nine families, it is served for one of the reasons a bar
 * can be empty and not the other — a family withdrawn as not measurable against this
 * target reaches this field as an empty string, and the run screen would have said
 * *the library holds none* about it — and the document that has to account for every
 * family is the report (ADR-0095).
 */
export function electiveRows(progress: RunProgress): readonly FamilyRow[] {
  const running = progress.scored.position?.family ?? ''
  const onTheWire = sending(progress)
  return (progress.elective_families ?? []).map((family: ElectiveFamilyRun) => ({
    family: family.family,
    name: readFamily(family.family),
    attempted: family.attempted,
    of: family.of,
    notRun: family.no_case,
    done: share(family.attempted, family.of),
    held: share(family.resisted, family.of),
    broke: share(family.succeeded, family.of),
    succeeded: family.succeeded,
    resisted: family.resisted,
    rate: rateOf(family.succeeded, family.attempted),
    cells: cellsFor(
      family.resisted,
      family.succeeded,
      family.attempted,
      family.of,
      onTheWire !== '' && readFamily(family.family) === readFamily(onTheWire),
    ),
    state: stateOf(family, running),
  }))
}

/**
 * Whether a computed width draws anything at all.
 *
 * `0%` is the length of a family that has not started, and a zero-width segment is
 * not rendered rather than rendered invisibly: where the two verdict colours meet
 * they cross into each other over a few pixels, and the CSS finds that join by
 * asking whether the green segment has a red one after it. A `0%` span sitting in
 * the markup would answer yes and put a red-tinged tip on a bar with no red in it.
 */
export function hasLength(width: string): boolean {
  return parseFloat(width) > 0
}

/**
 * The adaptive layer's last turn, as the screen draws it: one, or none.
 *
 * **A second function over a second read, and the two never meet.** The scored
 * exchange comes off `RunProgress.recent` and this comes off
 * `GET /runs/{id}/episodes`, which is a different route holding a different record —
 * an `AdaptiveEpisode` is not an `Attempt`, and a list this app concatenated would be
 * the one place a turn could be counted as an attempt (ADR-0010).
 *
 * The **last** turn of the **last** episode, on `payloads`' own rule: what a person
 * watching a run wants is where the attacker is now, and the whole route is the
 * episodes screen's business. An episode that sent nothing yields nothing.
 *
 * `reading` is the bench's own word for what the turn was found to be — *broke it*,
 * *no break*, *not checkable* — and never a verdict: an episode has no verdict, and
 * there is no name in this app for an episode that resisted (ADR-0010, ADR-0011).
 */
export interface TurnRow {
  key: string
  name: string
  episode: number
  turn: number
  sent: string
  reply: string
  reading: string
}

export function turns(held: RunEpisodes): readonly TurnRow[] {
  if (!held.held || held.episodes.length === 0) {
    return []
  }
  const at = held.episodes.length - 1
  const episode = held.episodes[at]
  const last = episode.probes.at(-1)
  if (last === undefined) {
    return []
  }
  return [
    {
      key: `${at}/${last.turn}`,
      name: readFamily(episode.family),
      episode: at + 1,
      turn: last.turn,
      sent: last.probe,
      reply: last.reply,
      reading: last.reading,
    },
  ]
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
  /** What the attempt was, for the line over the exchange. All served, none derived. */
  caseId: string
  attempt: number
  name: string
  verdict: string
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
    caseId: one.case_id,
    attempt: one.attempt,
    name: readFamily(one.family),
    verdict: one.verdict,
  }))
}
