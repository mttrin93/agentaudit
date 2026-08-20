/**
 * The security questionnaire, answered one family at a time from recorded attempts.
 *
 * This is the block the whole project points at. An engineer asked how they know
 * their agent is safe answers today with a hand-filled questionnaire, written from
 * recollection under commercial pressure, for a reader who cannot check a line of
 * it (ADR-0001). What this block puts in its place is the same questions answered
 * out of a signed report: a **family** that answers each question, its rate over
 * **that family's own denominator**, the interval around it, the confidence the
 * interval is stated at, and what the family **does not test**.
 *
 * **Every answer is one family, and nothing here spans two.** There is no total, no
 * average, no weighting and no rank; no field on any record below could hold one,
 * and the answers are a list of independent records rather than rows of a table
 * whose footer somebody fills in. A "% secure" number, a posture score or a
 * severity scale over *holds* / *weak* / *fails* is precisely the badge the report
 * exists to refuse — it was designed once, and ADR-0005 records the four reasons it
 * was thrown away, the second of which is that it added measured behaviour to
 * untested self-report. A questionnaire is the document most likely to be read for
 * one number, so this is the block most in need of not having one.
 *
 * **Four answers, and three of them are three different kinds of nothing.** They
 * are the load-bearing distinction in this module and they are carried by the type:
 *
 * * *answered* — attempts were made and the rate is published, beside its counts.
 * * *withheld* — attempts were made and the rate is **not** published, because the
 *   instrument that decided the family read below the declared κ floor against the
 *   gold set (ADR-0015). Not a rate of zero, and not a family that held.
 * * *not measurable* — the bench tried and could not measure it: a precondition was
 *   unmet before the first attempt, so there is no denominator at all. **Never a
 *   zero** — a zero would report an untested control as a defended one.
 * * *not tested* — a published risk category the bench never attempts, with the
 *   reason it does not. It carries a `category` and no `family`, because the bench
 *   has no family here; the gap is the reader's to disclose rather than to discover.
 *
 * None of the last three has a `rate`, a `counts`, an `interval` or a `confidence`
 * field, so there is nowhere in this module for a `0.00` to be printed for a
 * question nobody answered.
 *
 * **The three kinds of family answer are read through `report.ts` rather than
 * re-derived.** `familyAnswers` already reads the payload into that union and
 * formats each figure beside the counts it came from; this module asks it the
 * question a questionnaire asks and adds nothing arithmetic on the way. No rate is
 * computed here, no interval is computed here, and the coverage limits are the
 * payload's own (`CoverageLimit`).
 *
 * **It names the run it is drawn from.** One run, one target, measured once —
 * because a questionnaire answered from several runs at once would be answered from
 * an average of them, and there is no such quantity in this bench. The run is named
 * with a link to its own report, so a reader can check every answer here against the
 * artefact a recipient would verify.
 *
 * **It reads no new route.** The runs on the record say which runs completed, each
 * run's own record says where its report is served, and the report is the payload
 * the report screen already reads (`reportPayload`). Nothing was added to the API
 * for this block.
 */

import type {
  CoverageGap,
  MeasuredSection,
  RunList,
  RunRow,
  TargetReport,
} from '../api/bench'
import {
  familyAnswers,
  type CoverageLimit,
  type FamilyAnswer,
} from '../report/report'

import { reportPath } from './rail'

export const WHAT_THIS_BLOCK_ANSWERS =
  'These are the questions an enterprise security questionnaire asks, answered ' +
  'from attempts that were made against a target rather than from recollection. ' +
  'Each answer names the family that answers it, the successes over the attempts ' +
  'they were counted from, the interval around the rate, the confidence that ' +
  'interval is stated at, and what that family does not test. Every interval is a ' +
  'Wilson interval around the rate of one family, at the confidence printed beside ' +
  'it.'

export const ONE_FAMILY_PER_ANSWER =
  'Every answer below is one family over that family’s own denominator. Nothing ' +
  'here is added, averaged, weighted or ranked across families: the six families ' +
  'measure six different things, and a figure over them would be the composite ' +
  'this bench refuses (ADR-0005). There is no posture figure, no single number ' +
  'over the six and no severity scale — a reader who wants one number will build ' +
  'it out of whatever is on the page, so this page offers none.'

export const NO_SIGNED_REPORT_YET =
  'No run on this bench has produced a signed report, so there is nothing to ' +
  'answer a questionnaire from. A stated absence rather than an answer: no ' +
  'question below has been answered either way, and none of them is *not tested*, ' +
  '*not measurable* or a rate of zero. Register a target, and the answers appear ' +
  'here drawn from that run.'

export const DRAWN_FROM_ONE_RUN =
  'Every answer below is drawn from this one run’s signed report — the most recent ' +
  'run on this bench that produced one. It is one target measured once: nothing ' +
  'here is an average over runs, nothing is carried forward from an earlier run, ' +
  'and the report it came from is linked so that each answer can be checked ' +
  'against the artefact a recipient verifies.'

const WITHHELD_ON_A_QUESTIONNAIRE =
  'Write this as *withheld*. The attempts were made and the rate is on the run; it ' +
  'is not published, because the instrument that decided this family read below ' +
  'the declared κ floor against the gold set, and a figure whose evidentiary ' +
  'strength cannot be stated is worse than no figure (ADR-0015). It is not a rate ' +
  'of zero, it is not a family that held, and it is not a family the bench could ' +
  'not measure.'

const NOT_MEASURABLE_ON_A_QUESTIONNAIRE =
  'Write this as *not measurable*, and never as a zero. The bench tried and could ' +
  'not: a precondition for measuring this family was unmet before the first ' +
  'attempt, so no attempt was spent and there is no denominator here at all. A ' +
  'zero would report an untested control as a defended one. It is also not a ' +
  'category the bench never tests — this one it tests, and on this target it could ' +
  'not.'

const NOT_TESTED_ON_A_QUESTIONNAIRE =
  'Write this as *not tested*, with the reason beside it. This bench has no family ' +
  'here and never attempts one, so the boundary of the claim is part of the claim ' +
  'and a questionnaire that leaves it out over-claims by omission. It is not a ' +
  'family the bench tried and could not measure, and it is not a rate of zero: ' +
  'nothing was attempted, and nothing here is a defect.'

/**
 * What each family answers, in the words a questionnaire puts the question in.
 *
 * Six families, six questions, and the question is a sentence about the reader's own
 * agent rather than the family's identifier — an engineer pasting evidence into a
 * customer's template is matching on the question and not on this bench's
 * vocabulary. A family this screen has no question for **falls through as itself**,
 * for the same reason an unfamiliar run status does in `runs.ts`: a seventh family
 * added to the bench appears here on the day it exists rather than silently
 * dropping out of a questionnaire.
 */
const QUESTIONS: Record<string, string> = {
  indirect_prompt_injection:
    'Can content the agent retrieves make it act on instructions its operator ' +
    'never gave it?',
  scope_creep:
    'Can the agent be induced to use tools, or reach systems, outside the task it ' +
    'was given?',
  wrongful_commitment:
    'Can the agent be made to commit its operator to something it has no ' +
    'authority to commit them to?',
  data_leakage:
    'Can the agent be made to disclose what is inside its own configuration or ' +
    'context?',
  halt_defeat:
    'Does the agent stop when its operator tells it to stop, and stay stopped?',
  disclosure_denial:
    'Does the agent disclose that it is an AI system when it is asked directly?',
}

/** The question this family answers, or the family itself when there is none. */
function questionFor(family: string): string {
  return QUESTIONS[family] ?? family
}

/**
 * One question this bench answered, with the rate beside the counts it came from.
 *
 * Every figure on this record belongs to the one family named on it. `counts` is
 * not decoration: a rate without its denominator is the figure this project exists
 * to stop being pasted into a customer's document, so the two travel together and
 * there is no field here that carries one without the other.
 */
export interface AnsweredQuestion {
  kind: 'answered'
  /** The family that answers the question, under the name the payload gives it. */
  family: string
  question: string
  /** Successes over attempts — this family's own denominator, in words. */
  counts: string
  rate: string
  interval: string
  /** The confidence this family's own interval is stated at. Never another's. */
  confidence: string
  band: string
  /** What that band does and does not say, in ADR-0014's wording via `report.ts`. */
  bandReads: string
  /**
   * What this family's cases test one case *within*, and what they do not test.
   *
   * The payload's own coverage notes (ADR-0002), carried unedited. A family
   * answered on a questionnaire with nothing beside it reads as a cleared category,
   * which is the over-claim this whole block is meant to prevent.
   */
  limits: CoverageLimit[]
}

/** A family whose rate the report may not publish, and the reading that barred it. */
export interface WithheldQuestion {
  kind: 'withheld'
  family: string
  question: string
  reason: string
  stated: string
  note: string
}

/**
 * A family the bench tried to measure on this target and could not.
 *
 * No rate, no counts, no interval, no confidence and no band — there is no field on
 * this record that a zero could be written into.
 */
export interface NotMeasurableQuestion {
  kind: 'not_measurable'
  family: string
  question: string
  reason: string
  stated: string
  note: string
}

/**
 * A published risk category this bench never tests, with the reason it does not.
 *
 * `category` and deliberately **no `family` and no `question`**: the bench has no
 * family here, so there is no question of its own to answer and nothing that could
 * be mistaken for a family that was measured. The discriminating field is the one a
 * test asserts on.
 */
export interface NotTestedCategory {
  kind: 'not_tested'
  category: string
  reason: string
  stated: string
  note: string
}

/**
 * One answer, in four shapes, and only one of them carries a rate.
 *
 * Four members of one union rather than one record with optional fields, for the
 * reason `report.ts` keeps three: an optional `rate` is a rate a renderer prints
 * `0.00` into the day somebody forgets to check the flag beside it.
 */
export type QuestionnaireAnswer =
  | AnsweredQuestion
  | WithheldQuestion
  | NotMeasurableQuestion
  | NotTestedCategory

/**
 * The run these answers come from, named so a reader can go and check them.
 *
 * The run's own id and target, when it went on the record, and the path to its
 * report screen. Nothing measured is on this record: it says *which* run, and every
 * figure lives on the answer it belongs to.
 */
export interface DrawnFrom {
  runId: string
  /** The operator's own name for the endpoint. Never the endpoint (ADR-0008). */
  target: string
  /** Carried exactly as the record holds it, for the reason `runs.ts` gives. */
  recordedAt: string
  /** Where that run's report is, at the path the rail builds. */
  path: string
  statement: string
}

/** The questionnaire, its answers, and the one run they were all drawn from. */
export interface Questionnaire {
  drawnFrom: DrawnFrom
  /** One answer per family the report answered, then every category never tested. */
  answers: QuestionnaireAnswer[]
  answered: string
  oneFamilyPerAnswer: string
}

/** The status a run reaches when the bench has a report to serve for it. */
export const COMPLETED = 'completed'

/**
 * The runs that may have a signed report, most recently recorded first.
 *
 * A filter and never a sort: the route decided which run is the most recent one,
 * and a screen that re-ordered the rows would be a second opinion on it. *May*
 * rather than *does*, because completing and being signed are two facts — a
 * completed run on a bench with no signing key has finished and has nothing to
 * serve, which is why the caller reads each run's own record for where its report
 * is instead of building a path from the id (ADR-0020 is why that is rare rather
 * than why it is impossible).
 *
 * Nothing is counted here and nothing is summarised: rows in, rows out.
 */
export function theRunsToDrawFrom(list: RunList): RunRow[] {
  return list.runs.filter((row) => row.status === COMPLETED)
}

/** That run, named, with the path to the report these answers came out of. */
export function drawnFrom(row: RunRow): DrawnFrom {
  return {
    runId: row.run_id,
    target: row.target,
    recordedAt: row.recorded_at,
    path: reportPath(row.run_id),
    statement: DRAWN_FROM_ONE_RUN,
  }
}

/**
 * The confidence one family's interval is stated at, off that family's own entry.
 *
 * Found by name in the section the entry lives in, so the figure printed beside a
 * rate is the confidence *that* rate was computed at and never a neighbour's. The
 * declared rule states one confidence for the whole run and the entries carry it
 * per family; this reads the family's own, because that is the record the rate is
 * on. A family with no entry gets a stated absence rather than an invented number.
 */
function confidenceOf(measured: MeasuredSection, family: string): string {
  const entry =
    measured.deterministic.find((one) => one.family === family) ??
    measured.judged.find((one) => one.family === family)
  return entry === undefined
    ? 'the confidence this interval is stated at is not on this record'
    : `${(entry.interval_confidence * 100).toFixed(0)}%`
}

/** One family's answer, as the question it answers. */
function answerFor(
  answer: FamilyAnswer,
  measured: MeasuredSection,
): QuestionnaireAnswer {
  const question = questionFor(answer.family)
  if (answer.kind === 'withheld') {
    return {
      kind: 'withheld',
      family: answer.family,
      question,
      reason: answer.reason,
      stated: answer.stated,
      note: WITHHELD_ON_A_QUESTIONNAIRE,
    }
  }
  if (answer.kind === 'not_measurable') {
    return {
      kind: 'not_measurable',
      family: answer.family,
      question,
      reason: answer.reason,
      stated: answer.stated,
      note: NOT_MEASURABLE_ON_A_QUESTIONNAIRE,
    }
  }
  const figures = answer.figures
  return {
    kind: 'answered',
    family: answer.family,
    question,
    counts: figures.counts,
    rate: figures.rate,
    interval: figures.interval,
    confidence: confidenceOf(measured, answer.family),
    band: figures.band,
    bandReads: figures.bandReads,
    limits: figures.limits,
  }
}

/** A category the bench never tests, with the reason it does not. */
function neverTested(gap: CoverageGap): NotTestedCategory {
  return {
    kind: 'not_tested',
    category: gap.category,
    reason: gap.reason,
    stated: gap.stated,
    note: NOT_TESTED_ON_A_QUESTIONNAIRE,
  }
}

/**
 * One signed report, read as the answers to a questionnaire.
 *
 * The families first, in the order the payload carries them — **not sorted by
 * rate**, because an ordering by severity is a rank across families and a rank is
 * the composite ADR-0005 refuses arriving as a layout decision. Then the categories
 * the bench never tests, which are not families and are last because they are the
 * boundary of everything above them rather than an item in it.
 */
export function questionnaire(report: TargetReport, from: DrawnFrom): Questionnaire {
  return {
    drawnFrom: from,
    answers: [
      ...familyAnswers(report.measured).map((answer) =>
        answerFor(answer, report.measured),
      ),
      ...report.coverage_gaps.map(neverTested),
    ],
    answered: WHAT_THIS_BLOCK_ANSWERS,
    oneFamilyPerAnswer: ONE_FAMILY_PER_ANSWER,
  }
}
