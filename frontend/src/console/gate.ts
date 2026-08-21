/**
 * The operator's screen for one question: when was this instrument last validated,
 * and how do I do it again?
 *
 * Two blocks, in an order that is the content rather than the layout. **The way to
 * run one** — the control this bench offers, where it can, and the stated reason
 * where it cannot. **Then what the last gate run answered**, or the stated absence
 * of one, at the foot of the page: the component renders a run's own figures between
 * the two, so the outcome sits under the arithmetic it was decided on.
 *
 * **The declared rule is not printed here any more, and neither are the three
 * agents it is put to.** This screen led with the whole of `GateRule.stated()` and
 * the three reference agents under it — seven clauses and three named constructions
 * before the reader reached the outcome. It is an operator's screen for one errand,
 * and the errand was underneath the specification of the instrument. The rule is
 * still declared where it was always decided, in `rule.py`, still carried on the
 * wire in `BenchGate.rule`, still printed whole on the signed report beside the
 * figures it was measured against, and `clausesOf` below is what prints it there.
 * What came off this screen is the restatement, not the rule.
 *
 * **The order of what is left is asserted, not merely intended.** This module
 * returns the blocks as a sequence and the component renders them in it, so *above*
 * is a property of the value a test can read rather than of markup nobody checks. A
 * screen that put the outcome back over the control, or a clause of the rule back on
 * the page, fails in `gate.test.ts`.
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

/** What the last gate run answered, in the front door's own wording. */
export interface OutcomeBlock {
  kind: 'outcome'
  heading: string
  reading: GateReading
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

export type GateBlock = OutcomeBlock | StartBlock

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

/**
 * The way to start one, then the outcome.
 *
 * A sequence and not two fields, so that the order a reader meets them in is a
 * property of this value that a test can read rather than markup nobody checks.
 *
 * The control is first because it is the errand: an operator opens this screen to
 * run a gate, and the outcome of the last one was standing between them and the one
 * button on the page. The outcome goes to the foot, where the figures it was decided
 * on are — the component puts a run's own blocks between the two, so *below the
 * control* and *under its own arithmetic* are the same place.
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
      kind: 'start',
      heading: 'Starting one',
      start,
    },
    {
      kind: 'outcome',
      heading: 'The last outcome',
      reading: gateReading(bench.citation),
    },
  ]
}

/**
 * The rule's own lines, as the rule prints them.
 *
 * Kept, and exported, though this screen no longer prints them: `gaterun.ts` reads
 * the rule a finished gate run was decided under, and the signed report prints it
 * whole beside the figures. Split and never rewritten, wherever it is read.
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
