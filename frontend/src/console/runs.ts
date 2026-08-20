/**
 * The runs on the record, as two columns that never become one.
 *
 * An operator who registered a target last week has a run id in a URL they did not
 * keep. This is the list that gets them back to it: the target, when the run went
 * on the record, where it got to, and what it spent — in **two figures, one per
 * layer**, because each layer is enforced against its own ceiling and a blended
 * number would hide which half of the run consumed the budget (ADR-0007).
 *
 * **There is no third figure and nowhere to put one.** The two spends live in two
 * named fields of two different types, and deliberately not in a list of layers: a
 * list is a thing a component reduces, and one `reduce` in a table footer is the
 * whole of how a scored figure and an adaptive one get added together (ADR-0010).
 * `ScoredColumn` and `AdaptiveColumn` differ in the one field that decides which
 * accent they are drawn in, so neither can be passed where the other is expected
 * and no helper can be written that takes either. Nothing in this module adds,
 * averages or counts anything — not across the two layers of one run, and not down
 * a column of runs.
 *
 * **A zero is a fact about the wire, and it is said in words.** A run nobody
 * answered spent nothing in both layers, and that is what makes an abandoned run
 * distinguishable from a cheap one — so the figure is a zero and never a blank, and
 * the sentence beside it says *no call reached the endpoint* rather than leaving a
 * reader to decide whether the layer ran and found nothing. That is a count of
 * calls and not the rate of zero CONTEXT.md forbids; the distinction is carried by
 * the sentence the route wrote, which is read off the payload here.
 *
 * **The standing is named, and it is named for every run.** Eight states, and the
 * two that most need keeping apart are *declined* — a human refused the estimate —
 * and *unanswered* — nobody ever saw it. An unrecognised state falls through as
 * itself rather than as nothing, so a ninth added to the bench appears on this
 * screen on the day it exists.
 *
 * **No figure here is about a target.** No rate, no interval, no band, no verdict:
 * those belong to the report the run produced, where they are printed beside the
 * denominator they were computed over. A list is where a reader is most easily
 * handed a measurement without one.
 */

import type { RunList, RunRow } from '../api/bench'

import { runPath } from './rail'

export const TWO_COLUMNS_NEVER_ONE =
  'One row per run, with calls spent in two figures — the scored layer’s and the ' +
  'adaptive layer’s. They are not added, because the two layers are held to two ' +
  'separate ceilings and neither can borrow the other’s budget: a single figure ' +
  'would say what a run cost without saying which half of it cost that. There is ' +
  'no total here, no average, and no figure spanning two runs.'

export const NO_RUNS_YET =
  'This bench has no runs on the record. Nothing has been registered against it ' +
  'in this process, which is a fact about the bench and not about any target — ' +
  'register one and it appears here with what it spent, one layer at a time.'

/** What the scored layer of one run spent, as its own column. */
export interface ScoredColumn {
  /** The layer, in words. The label a reader reads, never inferred from a hue. */
  layer: string

  /**
   * Which of the two accents this column is drawn in.
   *
   * A declared identity rather than a colour, because the palette lives in the
   * stylesheet: `--scored` and `--adaptive` are two hues stepped at matched
   * lightness so that the boundary between the two figures is visible, and the
   * accent is **redundant with `layer` above** so nothing on this screen is carried
   * by hue alone. Colour carries identity here and never a judgement — no band,
   * rate or verdict is coloured anywhere in this console (ADR-0005).
   */
  accent: 'scored'

  /** Calls this layer put on the wire. Its own figure, added to nothing. */
  calls: number

  /** What that figure is, in the route's own words. */
  statement: string
}

/**
 * What the adaptive layer of one run spent, as its own column.
 *
 * A second type rather than the same one twice, and the discriminating field is
 * `accent`: a function written to take a `ScoredColumn` cannot be handed this, so
 * there is no signature in this module that accepts either layer and therefore
 * none that could add them.
 */
export interface AdaptiveColumn {
  layer: string
  accent: 'adaptive'
  calls: number
  statement: string
}

/** One run as a row: how to get back to it, and what each layer of it spent. */
export interface RunReading {
  /** The run's id, as the bench issued it. */
  id: string
  /** Where this run's screen is. Built from the id so no component invents one. */
  path: string
  /** The operator's own name for the endpoint. Never the endpoint. */
  target: string
  /**
   * When the run went on the record, carried exactly as the record holds it.
   *
   * Not reformatted: the record's timestamp is UTC with its offset on it, and a
   * console that rendered it in the reader's locale would be showing a different
   * instant from the one the bench will quote back.
   */
  recordedAt: string
  /** Where the run got to, named. Never a blank and never a colour. */
  standing: string
  /** The record's own sentence for that standing. */
  statement: string
  scored: ScoredColumn
  adaptive: AdaptiveColumn
}

/**
 * The run list, or the stated fact that there is nothing on it.
 *
 * Two shapes of one union, as the gate citation is (`landing.ts`): a bench with no
 * runs says so in a sentence, rather than drawing the head of a table over nothing.
 */
export type RunsReading =
  | { listed: true; runs: RunReading[]; statement: string }
  | { listed: false; statement: string }

/**
 * What each of the record's states is called on this screen.
 *
 * *Declined* and *unanswered* are two entries and not one, because they are two
 * facts: a human read the estimate and refused it, or a human never saw it. So are
 * *aborted* and *failed* — a run stopped by its own ceiling is the budget working,
 * and a run stopped on the wire is not a result at all (`runs.RunStatus`).
 */
const STANDINGS: Record<string, string> = {
  awaiting_approval: 'Awaiting approval',
  declined: 'Declined',
  unanswered: 'Unanswered',
  running: 'Running',
  completed: 'Completed',
  registration_refused: 'Registration refused',
  aborted: 'Aborted',
  failed: 'Failed',
}

/** The standing, named — and an unfamiliar one carried through as itself. */
function standingOf(status: string): string {
  return STANDINGS[status] ?? status
}

/**
 * The runs on the record, as this screen reads them.
 *
 * The order is the route's — most recently recorded first — and it is not re-sorted
 * here: the bench decided which run is the most recent one, and a screen that
 * sorted the rows again would be a second opinion on it.
 */
export function runsReading(list: RunList): RunsReading {
  if (list.runs.length === 0) {
    return { listed: false, statement: NO_RUNS_YET }
  }
  return {
    listed: true,
    runs: list.runs.map(runReading),
    statement: TWO_COLUMNS_NEVER_ONE,
  }
}

/**
 * One row.
 *
 * The two spends are read out one field name at a time — `row.scored.calls_spent`
 * and then `row.adaptive.calls_spent` — and never iterated, for the reason
 * `report.ts` reads the provenance block's calls-spent map one layer at a time
 * rather than reducing it: the moment the two figures are in a sequence together,
 * summing them is one method call away.
 */
function runReading(row: RunRow): RunReading {
  return {
    id: row.run_id,
    path: runPath(row.run_id),
    target: row.target,
    recordedAt: row.recorded_at,
    standing: standingOf(row.status),
    statement: row.statement,
    scored: {
      layer: 'Scored layer',
      accent: 'scored',
      calls: row.scored.calls_spent,
      statement: row.scored.statement,
    },
    adaptive: {
      layer: 'Adaptive layer',
      accent: 'adaptive',
      calls: row.adaptive.calls_spent,
      statement: row.adaptive.statement,
    },
  }
}
