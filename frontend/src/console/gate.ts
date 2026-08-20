/**
 * The operator's screen for one question: when was this instrument last validated,
 * and how do I do it again?
 *
 * Four blocks, in an order that is the content rather than the layout. **The
 * declared rule first**, whole and in the bench's own words, because a pass read
 * with no bar beside it is a verdict somebody trusted and a pass read under the rule
 * is an answer somebody can re-derive — which is the whole of ADR-0003, and the
 * reason those numbers were declared before the code that evaluates them existed.
 * **Then what the last gate run answered**, or the stated absence of one. **Then
 * what a gate run does to the case library**, before anything that starts one,
 * because it is not a read-only action and an operator who learns that afterwards
 * learned it too late. **Then the two ways to run one** — the control this bench
 * offers, where it can, and the command that runs one at a terminal.
 *
 * **The order is asserted, not merely intended.** This module returns the blocks as
 * a sequence and the component maps over it, so *above* is a property of the value a
 * test can read rather than of markup nobody checks. A screen that put the outcome
 * first would fail in `gate.test.ts`.
 *
 * **One control, beside the command and not instead of it.** A gate run is the
 * whole live library against all three reference agents, about 830 calls on the
 * operator's own provider and a write-back to every case record. `PLAN.md` §8 kept
 * it on the command line and ADR-0021 reversed that, so the command block now
 * carries the one affordance that starts one — where the bench says it can, and a
 * stated refusal where it cannot. The command stays: a gate run from a terminal is
 * still the path that writes a dated document, and a deployment that ships no
 * reference agents can run one nowhere but somewhere else.
 *
 * **What the control is is still text here.** The blocks this module returns carry
 * no callback and no handler — `available` is a boolean and everything beside it is
 * a sentence — so the affordance is described by a value a test can read and driven
 * by the component. What it may never grow is a second one: `gate.test.ts` pins the
 * one field named for something that happens, and any other fails there.
 *
 * **This screen's own figures still come from the citation, and the document is
 * still never parsed.** The per-family rates and each family's `D` of the *cited*
 * gate run are in its document and the citation carries none of them, so this
 * screen shows what the citation carries and names the rest. The figures for a gate
 * run started here come from the run itself, in memory, and are rendered by
 * `gaterun.ts` — which is why this module's scan for document-only figures still
 * holds: a screen that read the bench's own prose output would break on a rewording.
 *
 * **The citation is read through the front door's own reading.** `gateReading` is
 * imported rather than reimplemented: the citation's own two sentences are written
 * for a provenance block and both screens restate them, and one restatement in two
 * places is one wording rather than two that would only have to disagree once. It
 * carries the sentence naming whose fact this is, so this module states it once,
 * inside the region a screenshot would take, and never again in a footer.
 *
 * **The three reference agents are named, ordered, and carry no figure.** They are
 * the contrast the gate is decided on, so an operator reading the rule needs to know
 * what it was put to; each takes one step of one hue because they are ordered by
 * construction, and not one of them has a rate beside it — those are in the
 * document, and a coloured figure beside a name is the severity scale the report
 * exists to refuse (spec §75).
 */

import type { BenchGate, DeclaredRule } from '../api/bench'
import type { StartControl } from './gaterun'
import { gateReading, type GateReading } from './landing'

export const WHAT_THIS_SCREEN_ANSWERS =
  'The gate is the stop before this bench is trusted: the whole live library run ' +
  'against three agents of the project’s own construction, decided by a rule stated ' +
  'in advance. This screen is the rule, what the last gate run answered under it, ' +
  'what running another one does to the case library, and the two ways to run one — ' +
  'from here, or from a terminal.'

/** The command that starts a gate run, and the only thing that does. */
export const THE_COMMAND = 'uv run python -m scripts.gate --identity "your name"'

/** One clause of the declared rule, as the gate prints it. */
export interface RuleClause {
  /** The line, verbatim from `GateRule.stated()`. Never composed here. */
  line: string
  /** How deep the clause sits under the line above it, as the rule prints it. */
  under: boolean
}

/** One reference agent: its name, its place in the order, and no figure at all. */
export interface ReferenceAgent {
  name: string
  /** The stylesheet's token for this agent's step of the one hue. */
  accent: string
  /** What it was built to be. Words, because a rate here would be a measurement. */
  built: string
}

/**
 * The declared rule, printed rather than summarised.
 *
 * `clauses` is `rule.stated` split at its own line breaks and nothing else: the
 * text is the bench's, so a threshold moved in `rule.py` moves here and no wording
 * on this screen can claim a bar the gate was not held to. The two floors named in
 * the consequence block below are read off the same record, so the number in a
 * sentence and the number in the rule cannot drift apart.
 */
export interface RuleBlock {
  kind: 'rule'
  heading: string
  statement: string
  clauses: RuleClause[]
  agents: ReferenceAgent[]
  /** What the agents block is, and what it deliberately does not carry. */
  agentsStatement: string
}

/** What the last gate run answered, in the front door's own wording. */
export interface OutcomeBlock {
  kind: 'outcome'
  heading: string
  reading: GateReading
}

/** What a gate run does that is not reading: it writes, and it spends. */
export interface ConsequenceBlock {
  kind: 'consequence'
  heading: string
  statement: string
  /** One consequence per line, each of them a write or a spend. */
  writes: string[]
}

/**
 * The command, the statements beside it, and the control this bench may offer.
 *
 * `command` is one line and nothing but the command — no leading prompt character,
 * no prose wrapped around it — because what an operator does with it is select it
 * and paste it into a terminal, and a `$` pasted with it is a command that fails.
 */
export interface CommandBlock {
  kind: 'command'
  heading: string
  command: string
  statements: string[]
  /**
   * The one control this screen offers, or the stated absence of one.
   *
   * Beside the command rather than instead of it, because they are two entry points
   * and they leave different traces: a gate run from a terminal writes a dated
   * document, and one started here returns its figures and holds them. `null` is
   * neither — it is this app not yet knowing, which is a third state and the only
   * one in which nothing at all is drawn.
   *
   * It carries no callback. `available` is a boolean, the rest is text, and the
   * component holds the handler — so what this module describes is *whether* there
   * is a control and what it says, and a second affordance appearing anywhere in
   * this value fails `gate.test.ts`.
   */
  start: StartControl | null
}

export type GateBlock = RuleBlock | OutcomeBlock | ConsequenceBlock | CommandBlock

const THE_RULE_IS_PRINTED =
  'Printed rather than summarised, and printed above the outcome. The gate’s ' +
  'thresholds were declared before the code that applies them existed, and they are ' +
  'shown here in the bench’s own words so that a pass or a fail can be re-derived ' +
  'rather than trusted. A rule nobody can read is a rule that can be moved.'

const THE_AGENTS_ARE_ORDERED =
  'The three agents the rule is put to, ordered by construction and named without a ' +
  'figure between them. What each of them scored on each family is in the gate run’s ' +
  'document; the citation does not carry it, and this screen does not read it.'

/**
 * The three agents of known construction, in the order construction gives them.
 *
 * Exported because two screens name them and one list is one wording: the gate screen
 * names them as what the rule is put to, and the settings screen names them as what
 * the discrimination score is measured against. Two copies would only have to
 * disagree once for a reader to be told the bench is calibrated against something it
 * is not — and there is no figure in here to disagree about, which is the point.
 */
export const REFERENCE_AGENTS: readonly ReferenceAgent[] = [
  {
    name: 'hardened',
    accent: 'hardened',
    built:
      'built to hold: the defences this bench attacks are in place, and it is the ' +
      'floor of the contrast.',
  },
  {
    name: 'weak',
    accent: 'weak',
    built:
      'built with some of them and not the ones that matter most, so it sits ' +
      'between the other two and orders them.',
  },
  {
    name: 'trivial',
    accent: 'trivial',
    built:
      'built with none: it does as it is told, and it is the ceiling of the ' +
      'contrast.',
  },
]

const IT_IS_NOT_A_READ_ONLY_ACTION =
  'A gate run is not a read. It spends, and it writes to the library every user run ' +
  'is measured with, so this is what it will have done by the time it prints an ' +
  'outcome.'

/** What a gate run writes and what it spends, with every number read off the rule. */
function whatItWrites(rule: DeclaredRule): string[] {
  return [
    'It appends a discrimination reading to every case record it reads — the ' +
      'counts, the model, the date, and whether the family was fit to report — so ' +
      'the score is re-derivable from the record rather than a number somebody ' +
      'computed once.',
    `It marks retired any case the rule retires: below the declared floor of ` +
      `${rule.retirement_floor.toFixed(2)} on two consecutive gate runs, with the ` +
      'date and the final reading. Marked and never deleted, because a case the ' +
      'field caught up with is evidence that the field moved.',
    'It writes a dated document of the run, which is the document the citation ' +
      'above names. The curated history is written by hand and reads those records; ' +
      'this one is the run itself.',
    `It spends, on your own provider: the whole admitted library against all three ` +
      `agents at ${rule.attempts_per_case} attempts per case, and then the ` +
      'adaptive layer under a ceiling and a counter of its own. The terminal ' +
      'presents the two as two figures before anything is sent, never added ' +
      'together, and it takes many minutes rather than seconds.',
    'It asks first, whichever way it is started. The three attestation statements ' +
      'one at a time, then the estimated cost, and answering no to any of them ' +
      'spends nothing and writes nothing.',
    'It holds this bench’s case library while it goes, and one gate run runs at ' +
      'a time on one library: a second is refused rather than queued, because two ' +
      'overlapping runs would decide a retirement off a series missing a reading.',
  ]
}

const TWO_ENTRY_POINTS = [
  'The identity is required and is never defaulted from the environment: it is the ' +
    'liability record for the run, so nothing may pre-answer it. Replace it with ' +
    'yours before running the command.',
  'This command and the control beside it are the two entry points, and they ask ' +
    'the same three attestation statements and present the same two figures before ' +
    'anything is sent. What differs is what they leave: the command writes a dated ' +
    'document of the run, and a gate run started here returns its figures and holds ' +
    'them on the bench.',
  'Neither can be answered by something that is not a person. The terminal reads ' +
    'an absent or piped answer as a refusal, and the browser posts an attestation ' +
    'the bench will not construct with a statement withheld — which is why nothing ' +
    'here spawns the command, and why no flag anywhere lets a gate run proceed ' +
    'without one (ADR-0007, ADR-0021).',
]

/**
 * The rule, then the outcome, then the consequence, then the way to start one.
 *
 * A sequence and not four fields, so that the order a reader meets them in is a
 * property of this value: the two orderings this screen is required to have — the
 * rule above the outcome, the write-back before the way to start one — are asserted
 * here rather than hoped for in markup. The second matters more now that one of
 * those ways is on this screen: an operator who learns about the write-back after
 * pressing a control learned it too late.
 *
 * `start` is what the bench said about whether a gate run may begin here, already
 * read (`gaterun.startControl`). Passed in rather than fetched, because this module
 * is a transformation and not a client — and `null` where this app has not been told
 * yet, which draws no control and no refusal.
 */
export function gateScreen(
  bench: BenchGate,
  start: StartControl | null = null,
): GateBlock[] {
  return [
    {
      kind: 'rule',
      heading: 'The rule this bench is held to',
      statement: THE_RULE_IS_PRINTED,
      clauses: clausesOf(bench.rule),
      agents: [...REFERENCE_AGENTS],
      agentsStatement: THE_AGENTS_ARE_ORDERED,
    },
    {
      kind: 'outcome',
      heading: 'What the last gate run answered under it',
      reading: gateReading(bench.citation),
    },
    {
      kind: 'consequence',
      heading: 'What running one does to the case library',
      statement: IT_IS_NOT_A_READ_ONLY_ACTION,
      writes: whatItWrites(bench.rule),
    },
    {
      kind: 'command',
      heading: 'Starting one: here, or the command that does it',
      command: THE_COMMAND,
      statements: [...TWO_ENTRY_POINTS],
      start,
    },
  ]
}

/**
 * The rule's own lines, as the rule prints them.
 *
 * Split and never rewritten. `under` carries the indentation the declared text uses
 * to hang its clauses off the line above, so the shape survives a list that has no
 * leading whitespace of its own — a clause promoted to a heading by losing two
 * spaces would read as a rule of its own.
 */
export function clausesOf(rule: DeclaredRule): RuleClause[] {
  return rule.stated
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => ({ line: line.trim(), under: /^\s/.test(line) }))
}
