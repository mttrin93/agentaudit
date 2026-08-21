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
 * learned it too late. **Then the way to run one** — the control this bench offers,
 * where it can, and the stated reason where it cannot.
 *
 * **The order is asserted, not merely intended.** This module returns the blocks as
 * a sequence and the component maps over it, so *above* is a property of the value a
 * test can read rather than of markup nobody checks. A screen that put the outcome
 * first would fail in `gate.test.ts`.
 *
 * **One control, and this screen is where it is.** A gate run is the whole live
 * library against all three reference agents, about 830 calls on the operator's own
 * provider and a write-back to every case record. `PLAN.md` §8 kept it on the
 * command line and ADR-0021 reversed that, so the start block carries the one
 * affordance that starts one — where the bench says it can, and a stated refusal
 * where it cannot. The terminal path is unchanged and is still the one that writes a
 * dated document; it is documented in the README and in `scripts/gate.py --help`,
 * which is where somebody at a terminal already is, rather than on this screen.
 *
 * **What the control is is still text here.** The blocks this module returns carry
 * no callback and no handler — `available` is a boolean and everything beside it is
 * a sentence — so the affordance is described by a value a test can read and driven
 * by the component. What it may never grow is a second one: `gate.test.ts` pins the
 * one field named for something that happens, and any other fails there.
 *
 * **This screen's own figures still come from the citation, and nothing is ever
 * parsed.** The per-family rates and each family's `D` of the *cited* gate run are
 * in the **gate run record** the citation names, and the citation carries none of
 * them (ADR-0023), so this screen shows what the citation carries and names where
 * the rest is. The figures for a gate run started here come from the run itself, in
 * memory, and are rendered by `gaterun.ts` — which is why this module's scan for
 * document-only figures still holds: a screen that read the bench's own prose output
 * would break on a rewording, and after ADR-0023 it has a `.json` to point at
 * instead of a reason to try.
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
 * construction, and not one of them has a rate beside it — those are in the record
 * the citation names, and a coloured figure beside a name is the severity scale the
 * report exists to refuse (spec §75).
 */

import type { BenchGate, DeclaredRule } from '../api/bench'
import type { StartControl } from './gaterun'
import { gateReading, type GateReading } from './landing'

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
  clauses: RuleClause[]
  agents: ReferenceAgent[]
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
 * The control this bench may offer, or the stated reason it offers none.
 *
 * This block used to carry the terminal command beside the control, with three
 * paragraphs on how the two entry points differ. The command is in the README and in
 * `scripts/gate.py --help`, which is where somebody at a terminal already is; on this
 * screen it was a second door explained at length beside the one door being used.
 * What the two entry points have in common — the same three attestation statements,
 * the same two figures, neither answerable by anything that is not a person — is
 * enforced by the guard that builds the body and by the bench that refuses an
 * incomplete one, and it is those, not this prose, that make it true.
 */
export interface StartBlock {
  kind: 'start'
  heading: string
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

export type GateBlock = RuleBlock | OutcomeBlock | ConsequenceBlock | StartBlock

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
  'A gate run is not a read: it spends, and it writes to the library every user run ' +
  'is measured with.'

/** What a gate run writes and what it spends, with every number read off the rule. */
function whatItWrites(rule: DeclaredRule): string[] {
  return [
    'It appends a discrimination reading to every case record it reads — the ' +
      'counts, the model, the date, whether the family was fit to report, and ' +
      'whether the run measured the field at all — so the score is re-derivable ' +
      'from the record rather than a number somebody computed once.',
    `It marks retired any case the rule retires: below the declared floor of ` +
      `${rule.retirement_floor.toFixed(2)} on two consecutive gate runs on the same ` +
      'model, with the date and the final reading. Two readings of one model and ' +
      'never the last two of the series, because a model swap moves the score and a ' +
      'change of instrument is not the passage of time. Marked and never deleted, ' +
      'because a case the field caught up with is evidence that the field moved.',
    'It writes the run down three times and none of them is a summary of another: a ' +
      'dated document for a person, the same run as fields for a program, and the ' +
      'citation this bench carries from then on — into the provenance block of every ' +
      'report it signs. The last one replaces whatever was cited before it, whatever ' +
      'this run answers: the citation is what the bench last put itself through and ' +
      'not the best answer it ever got, so a run that fails takes a passing citation ' +
      'off this bench and says so. The curated history is written by hand and reads ' +
      'those records; these are the run itself.',
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
      heading: 'The rule',
      clauses: clausesOf(bench.rule),
      agents: [...REFERENCE_AGENTS],
    },
    {
      kind: 'outcome',
      heading: 'The last outcome',
      reading: gateReading(bench.citation),
    },
    {
      kind: 'consequence',
      heading: 'What a gate run writes',
      statement: IT_IS_NOT_A_READ_ONLY_ACTION,
      writes: whatItWrites(bench.rule),
    },
    {
      kind: 'start',
      heading: 'Starting one',
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
