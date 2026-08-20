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
 * what a gate run does to the case library**, before the command, because it is not
 * a read-only action and an operator who learns that after running it learned it too
 * late. **Then the command**, which is the only way to start one.
 *
 * **The order is asserted, not merely intended.** This module returns the blocks as
 * a sequence and the component maps over it, so *above* is a property of the value a
 * test can read rather than of markup nobody checks. A screen that put the outcome
 * first would fail in `gate.test.ts`.
 *
 * **Nothing here starts a gate run, and there is nowhere to put the thing that
 * would.** A gate run is the whole admitted library against all three reference
 * agents, about 830 target calls on the operator's own provider, behind a terminal
 * that asks the three attestation statements one at a time and reads an absent or
 * piped answer as a refusal (ADR-0007, PLAN.md §8). So the console prints the
 * command and offers no affordance: every field of every block here is text, the
 * type has no callback in it, and `GateScreen.tsx` has no button, no form and no
 * write of any kind. The bench's own HTTP surface has no route under `/bench` that
 * is not a read, asserted over its route table in `test_api_gate.py`.
 *
 * **The document is named and never parsed.** Every per-family rate and every
 * per-family `D` of that gate run is in its document, and the citation carries none
 * of them; this screen shows what the citation carries and names the rest. A screen
 * that read the bench's own prose output would break on a rewording, and the
 * machine-readable sidecar that would supply those figures properly is a follow-up.
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
import { gateReading, type GateReading } from './landing'

export const WHAT_THIS_SCREEN_ANSWERS =
  'The gate is the stop before this bench is trusted: the whole admitted library ' +
  'run against three agents of the project’s own construction, decided by a rule ' +
  'stated in advance. This screen is the rule, what the last gate run answered ' +
  'under it, what running another one does to the case library, and the command ' +
  'that starts one.'

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
 * The command, and the statement that it is the only entry point.
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
      'together, and it runs overnight rather than in a browser tab.',
    'It asks first. The three attestation statements one at a time, then the ' +
      'estimated cost, and answering no to any of them spends nothing and writes ' +
      'nothing.',
  ]
}

const ONLY_ENTRY_POINT = [
  'The identity is required and is never defaulted from the environment: it is the ' +
    'liability record for the run, so nothing may pre-answer it. Replace it with ' +
    'yours before running the command.',
  'The terminal is the only entry point. There is no control on this screen that ' +
    'starts a gate run and no route on this bench that would take one, because the ' +
    'consent flow is what makes the spend and the write-back somebody’s decision: ' +
    'an absent or piped answer is read as a refusal, so anything that started a ' +
    'gate run unattended would answer no to all three statements and spend nothing ' +
    '(ADR-0007, PLAN.md §8).',
]

/**
 * The rule, then the outcome, then the consequence, then the command.
 *
 * A sequence and not four fields, so that the order a reader meets them in is a
 * property of this value: the two orderings this screen is required to have — the
 * rule above the outcome, the write-back before the command — are asserted here
 * rather than hoped for in markup.
 */
export function gateScreen(bench: BenchGate): GateBlock[] {
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
      heading: 'The command that starts one',
      command: THE_COMMAND,
      statements: [...ONLY_ENTRY_POINT],
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
function clausesOf(rule: DeclaredRule): RuleClause[] {
  return rule.stated
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => ({ line: line.trim(), under: /^\s/.test(line) }))
}
