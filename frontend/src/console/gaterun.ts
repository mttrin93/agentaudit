/**
 * Starting a gate run from the console, as data: the three statements, the two
 * figures, the per-layer progress, and the decision under the rule.
 *
 * `PLAN.md` §8 put a gate run on the command line and the console printed the
 * command. [ADR-0021] reverses that, and everything in this module exists to make
 * the reversal cost nothing that mattered: **the consent flow is the one this app
 * already has**, and it is reused rather than rewritten. The three statements are
 * `ATTESTATION_STATEMENTS` — the wording copied from `Attestation.STATEMENTS` in
 * `backend/bench/registration.py`, which holds it beside the fields so that the
 * prompt somebody confirms and the record of what they confirmed cannot drift
 * apart — and this module adds only the consequences a *gate run* has that a
 * target run does not.
 *
 * **One statement at a time, and no way to reach a body without all three.** The
 * shape is `registrationRequest`'s and `confirmationRequest`'s: two outcomes, and
 * the ready one carries the body while the blocked one carries the reasons. There
 * is no path in this module to a request with a statement withheld, which is the
 * same guarantee the API holds one level down by refusing to construct an
 * `Attestation` that is not complete. Declining anything sends nothing.
 *
 * **Two figures against two ceilings, and never a third.** `GateRunEstimate`
 * carries the scored layer's calls in attempts over cases and the adaptive layer's
 * in turns over episodes, and the two share no numeric field — so there is nothing
 * here to add, which is a stronger claim than a rule against adding. Each is shown
 * beside the ceiling it is enforced against, which is exactly what the run screen's
 * interrupt shows and for the same reason (ADR-0007, ADR-0010).
 *
 * **Progress is the run screen's own two readings.** `scoredReading` and
 * `adaptiveReading` are imported rather than reimplemented: a position is neither a
 * run nor a gate run, and the units are family/case/attempt and
 * family/episode/turn either way. Nothing in this module adds the two spends.
 *
 * **The rule is above the decision, and that is a property of a sequence.** The
 * decided view is an ordered list of blocks and the component maps over it, so
 * *above* is something a test reads rather than something markup promises. An
 * outcome read with no bar beside it is a verdict somebody trusted (ADR-0003).
 *
 * **The per-family figures come from the gate run and no composite is built from
 * them.** Six discrimination scores arrive at once, which makes this the one screen
 * in the console where a mean would look like a figure about the bench. There is no
 * field for one here, no total, no severity scale and no coloured outcome: the only
 * colour is the three reference agents' own hue in its three ordered steps, which
 * carries identity and order and never judgement.
 */

import type {
  ApprovalBody,
  DeclaredRule,
  ExcludedFamily,
  FamilyFigures,
  GateDecided,
  GateRunEstimate,
  GateRunReading,
  GateRunStart,
  StartGateRunBody,
  WroteBack,
} from '../api/bench'
import { readFamily } from '../families'
import type { CostFigure } from '../run/interrupt'
import { adaptiveReading, scoredReading, type LayerReading } from '../run/progress'
import {
  ATTESTATION_STATEMENTS,
  type Attested,
  type Statement,
} from '../register/declarations'
import { clausesOf, REFERENCE_AGENTS, type RuleClause } from './gate'

/** The status a gate run holds while it waits on a human, and on nothing else. */
/**
 * The bench's own name for *a gate run is going, so another may not start*.
 *
 * Named here because the console has to tell this refusal from the other three: the
 * first three are facts about how the bench was built and waiting does not answer
 * them, and this one is answered by waiting a moment. It is the only refusal the
 * screen re-asks about.
 */
export const ALREADY_IN_FLIGHT = 'already_in_flight'

export const AWAITING_APPROVAL = 'awaiting_approval'

/** The status a gate run settles at once it has been decided under the rule. */
export const DECIDED = 'decided'

/** The states a gate run does not leave, in the words its own record keeps. */
export const SETTLED = [
  'decided',
  'declined',
  'unanswered',
  'not_a_gate_run',
  'aborted',
  'failed',
] as const

/** Whether a gate run in this state is still going, or has stopped for good. */
export function stillGoing(status: string): boolean {
  return !SETTLED.some((settled) => settled === status)
}

// --- the control, where there may be one ----------------------------------------

/**
 * The one control this screen adds, and what pressing it starts.
 *
 * It used to carry `asks` and `library`: two lines listing what the next three
 * screens would ask, and the path a gate run writes back to. The walk itself is
 * those screens — the three statements one at a time and the estimate against its
 * ceilings, each answered before a call is made — and the path is on the estimate
 * the walk puts up, where an operator is deciding whether to send. What is left is
 * the label, and the bench's own sentence about starting one.
 */
export interface StartHere {
  available: true
  label: string
  statement: string
}

/**
 * No control, and the named reason there is none.
 *
 * A stated absence in the place the control would have been, which is the idiom
 * `.citation.uncited` and `.family.absent` already carry: a missing button with
 * nothing said about it is a screen a reader assumes is broken.
 */
export interface NoStartHere {
  available: false
  heading: string
  refusal: string
  statement: string
}

export type StartControl = StartHere | NoStartHere

const NO_CONTROL_HERE =
  'There is no way to start a gate run from this bench, and this is the reason ' +
  'rather than a button that would fail. The command below runs one wherever the ' +
  'three reference agents are shipped and a case library can be written to.'

/**
 * The control, or the stated absence of one, read off what the bench said.
 *
 * Read and never inferred. A screen that decided for itself whether to offer the
 * control would be a second policy beside the bench's own, and the two would only
 * have to disagree once to offer an operation that is then refused.
 */
export function startControl(start: GateRunStart): StartControl {
  if (!start.available) {
    return {
      available: false,
      heading: 'This bench cannot run a gate',
      refusal: start.refusal,
      statement: `${start.stated} ${NO_CONTROL_HERE}`,
    }
  }
  return {
    available: true,
    label: 'Start a gate run',
    statement: start.statement,
  }
}

// --- the three statements, one at a time ----------------------------------------

/**
 * What a gate run does that a target run does not, per statement.
 *
 * Keyed by the field each statement records, and it is *only* the consequence: the
 * wording is `ATTESTATION_STATEMENTS`' own and is never restated here. A second
 * copy of the three statements is a second thing to keep in step with the record
 * they are written into, and the record is the liability record (ADR-0007).
 */
const FOR_A_GATE_RUN: Record<keyof Attested, string> = {
  authorised_to_test:
    'The endpoints a gate run attacks are this bench’s own three reference agents, ' +
    'so this statement is about the bench you are operating rather than about ' +
    'somebody else’s system.',
  not_production:
    'The reference agents are test equipment and never reach a user. What a gate ' +
    'run changes is the case library: it appends a discrimination to every record ' +
    'it reads and marks retired what the rule retires, and that library is the one ' +
    'every run on this bench is measured with.',
  accepts_provider_policy_and_cost:
    'The payloads reach your model provider under your credentials so the policy ' +
    'violations are recorded against your account and the inference is billed to it.',
}

/** One statement as this screen asks it: the record's wording, this consequence. */
export interface GateStatement {
  field: keyof Attested
  wording: string
  consequence: string
  /** Which of the three this is, and how many there are, for the walk. */
  step: number
  of: number
}

/**
 * The three, in the order the record lists them and the screen asks them.
 *
 * Built from `ATTESTATION_STATEMENTS` so that the wording is one wording. A test
 * asserts the equality rather than the presence: what would go wrong here is a
 * screen that asked a friendlier version of a statement the bench then recorded in
 * its own words.
 */
export const GATE_RUN_STATEMENTS: readonly GateStatement[] =
  ATTESTATION_STATEMENTS.map((statement: Statement, index: number) => ({
    field: statement.field,
    wording: statement.wording,
    consequence: FOR_A_GATE_RUN[statement.field],
    step: index + 1,
    of: ATTESTATION_STATEMENTS.length,
  }))

/** What the operator has declared so far, and who is declaring it. */
export interface Attesting {
  identity: string
  attested: Attested
  /** The empty string means *not priced*, which is a declaration and not a zero. */
  price_per_call: string
  currency: string
}

/** Nothing declared yet. No statement is made and no price is assumed. */
export function nothingAttested(): Attesting {
  return {
    identity: '',
    attested: {
      authorised_to_test: false,
      not_production: false,
      accepts_provider_policy_and_cost: false,
    },
    price_per_call: '',
    currency: 'USD',
  }
}

/** Whether any of the three statements has not been made. */
export function anyWithheld(attesting: Attesting): boolean {
  return GATE_RUN_STATEMENTS.some(
    (statement) => !attesting.attested[statement.field],
  )
}

/**
 * A gate run ready to start, or the reasons it is not one.
 *
 * Two outcomes rather than a body beside a valid flag, so there is no way to reach
 * the body of a gate run whose statements were not all made.
 */
export type GateRunRequest =
  | { kind: 'ready'; body: StartGateRunBody }
  /**
   * Blocked, with the unfinished steps that have something to say — and `missing`
   * may be empty.
   *
   * A withheld statement is the case that says nothing: the operator is looking at
   * the box, and a line under it repeating the sentence beside it was the walk
   * restated inside itself. It still blocks, which is what `kind` is for. Nothing
   * reads `missing.length` to decide whether a gate run may start — `start()` asks
   * this function again and refuses on anything that is not `ready`.
   */
  | { kind: 'blocked'; missing: string[] }

/**
 * What this screen would post, or what it is still waiting for.
 *
 * The order of the checks is the order of the walk, so the first thing an operator
 * is told about is the earliest step they have to go back to. Every branch that is
 * not a complete declaration returns the blocked outcome and no body: this is the
 * function that decides whether 830 calls are spent and a library is rewritten.
 */
export function gateRunRequest(attesting: Attesting): GateRunRequest {
  const missing: string[] = []

  if (!attesting.identity.trim()) {
    missing.push(
      'an attestation has to record who made it: the gate run is charged to ' +
        'whoever attests it, and the case records it writes carry the run that ' +
        'wrote them',
    )
  }
  if (attesting.price_per_call.trim() && !attesting.currency.trim()) {
    // `CallPrice`'s own guard, held here so the operator meets it as an unfinished
    // step rather than as a 422: an amount with a currency the bench chose is a
    // figure the operator did not state.
    missing.push(
      'a price per call needs the currency it is in, or declare the gate run not ' +
        'priced',
    )
  }

  // A statement withheld blocks and prints nothing. The walk will not let an
  // operator past an unticked box, so this is not a state they can be sitting in and
  // wondering about; what it stops is a body built from an incomplete declaration by
  // any other path, which is what this function is for.
  if (anyWithheld(attesting) || missing.length) {
    return { kind: 'blocked', missing }
  }
  const priced = attesting.price_per_call.trim()
  return {
    kind: 'ready',
    body: {
      attestation: { identity: attesting.identity.trim(), ...attesting.attested },
      cost: {
        price_per_call: priced ? priced : null,
        currency: priced ? attesting.currency.trim() : '',
      },
    },
  }
}

// --- the estimate, per layer, before anything is sent ---------------------------

/** `830`, or `≤ 288` when the figure is a bound. */
function rendered(calls: number, kind: string): string {
  return kind === 'ceiling' ? `≤ ${calls}` : `${calls}`
}

/**
 * The two figures, in the order the estimate declares them, and no third figure.
 *
 * `CostFigure` is the interrupt's own shape, reused because one layer's figure
 * beside the ceiling it is enforced against is the same reading whatever is being
 * estimated. What is not reused is the prose under each: a gate run's scored layer
 * is three agents rather than one target, and its adaptive layer decides nothing
 * about anybody.
 *
 * The labels are the layer names and nothing else. They carried their standing
 * gloss — *the half that decides the gate*, *which decides nothing* — on a screen
 * whose question is what two numbers will cost, where which layer decides the gate
 * is not what is being answered. That the adaptive layer decides nothing is
 * ADR-0010, and it is carried by the type, by `AdaptiveEpisode` never being an
 * `Attempt`, and by the rule the gate prints saying so — never by a label.
 */
export function gateCostFigures(
  estimate: GateRunEstimate,
): readonly CostFigure[] {
  return [
    {
      layer: 'scored',
      label: 'Scored layer',
      calls: rendered(estimate.scored.attempt_calls, estimate.scored.kind),
      kind: estimate.scored.kind,
      basis: estimate.scored.basis,
      cost: estimate.scored.cost,
      ceiling: `≤ ${estimate.scored.attempt_ceiling}`,
      spends:
        `${estimate.scored.cases} live cases at ` +
        `${estimate.scored.attempts_per_case} attempts each, against all three ` +
        'reference agents, plus the one probe that plants a nonce in each.',
    },
    {
      layer: 'adaptive',
      label: 'Adaptive layer',
      calls: rendered(estimate.adaptive.turn_calls, estimate.adaptive.kind),
      kind: estimate.adaptive.kind,
      basis: estimate.adaptive.basis,
      cost: estimate.adaptive.cost,
      ceiling: `≤ ${estimate.adaptive.turn_ceiling}`,
      spends:
        `Episodes an attacker drives itself, ${estimate.adaptive.episodes_per_family} ` +
        `per family per agent under a cap of ${estimate.adaptive.turns_per_episode} ` +
        'turns.',
    },
  ]
}

/** The whole of what the interrupt puts in front of a person, as data. */
export interface GateInterruptView {
  figures: readonly CostFigure[]
}

/** The estimate as the screen shows it: two figures and the sentences beside them. */
export function gateInterruptView(
  estimate: GateRunEstimate,
): GateInterruptView {
  return { figures: gateCostFigures(estimate) }
}

/**
 * The one path to a `confirmed: true` on a gate run's interrupt.
 *
 * `confirmed` is compared against `true` rather than tested for truthiness, on the
 * same reasoning as the run interrupt's: a truthy-looking value spending somebody's
 * inference budget and rewriting their case library is the failure to guard against.
 */
export function gateConfirmation(
  status: string,
  confirmed: boolean,
  identity: string,
  reason: string = '',
): { kind: 'ready'; body: ApprovalBody } | { kind: 'withheld'; missing: string[] } {
  const missing: string[] = []
  if (status !== AWAITING_APPROVAL) {
    missing.push(
      `this gate run is ${status} and is not holding an interrupt, so there is ` +
        'nothing here to confirm: an interrupt is answered once',
    )
  }
  if (confirmed !== true) {
    missing.push(
      'the two figures have not been confirmed. The gate run stays where it is ' +
        'until they are, and nothing has been sent and nothing written',
    )
  }
  if (!identity.trim()) {
    missing.push(
      'a confirmation has to record who gave it: the gate run is charged to ' +
        'whoever confirms it',
    )
  }
  if (missing.length) {
    return { kind: 'withheld', missing }
  }
  return {
    kind: 'ready',
    body: { confirmed: true, identity: identity.trim(), reason: reason.trim() },
  }
}

/**
 * The answer that spends nothing, available at every moment the other one is not.
 *
 * A no is sent rather than withheld and it asks for nothing first: the bench records
 * it as declined by a person, which is a better record than the *unanswered* a
 * closed tab leaves, and its sentence says that nothing was sent and not one case
 * record was written to.
 */
export function gateDecline(identity: string, reason: string = ''): ApprovalBody {
  return {
    confirmed: false,
    identity: identity.trim(),
    reason:
      reason.trim() ||
      'declined at the approval interrupt: the figures were not confirmed',
  }
}

// --- while it goes ---------------------------------------------------------------

/**
 * Where the gate run has got to, one layer at a time, and nothing that spans them.
 *
 * The run screen's two readings, imported. There is no function here that takes
 * both layers and no figure built from the pair: the scored layer's calls and the
 * adaptive layer's are two numbers held to two ceilings, and this app adds nothing
 * to what the bench reported (ADR-0007, ADR-0010).
 */
export function gateProgress(reading: GateRunReading): readonly LayerReading[] {
  return [scoredReading(reading.scored), adaptiveReading(reading.adaptive)]
}

// --- how far it has got, per family, and the payloads behind the last calls -----

/** One agent's share of a family's bar: its two counts, and the width to draw. */
export interface FamilySegment {
  agent: string
  /**
   * The stylesheet's token for this agent's step of the ramp. Order, not rank.
   *
   * Read off the one list the console names the agents by, the same way a rate's mark
   * is (`accentFor`), so the swatch in the legend and the segment in the bar cannot
   * come out two colours for the one agent.
   */
  accent: string
  attempted: number
  of: number
  /**
   * How much of the family's bar this agent has done, as a CSS width.
   *
   * Geometry and not a figure. The share is never printed: a percentage beside a
   * family name is read as a rate, and a rate needs an interval and a band beside it
   * that progress cannot have (ADR-0005). Four decimal places because three
   * segments of one bar have to add up to the bar.
   */
  width: string
}

/** One family's progress: the two counts it was served, and its three segments. */
export interface FamilyRow {
  family: string
  attempted: number
  of: number
  segments: readonly FamilySegment[]
}

/**
 * The families as rows, in the order the route served them.
 *
 * The counts are carried, never recomputed: a console that added its own arithmetic
 * to a served figure would be a second scorer. What is computed here is the width of
 * a segment, which is a length and not a number anybody reads.
 *
 * A share is taken against the *family's* denominator rather than the agent's, so the
 * three segments of a row fill that row together — the bar is the family's progress
 * and the segments are who did which part of it.
 */
export function familyRows(reading: GateRunReading): readonly FamilyRow[] {
  return reading.families.map((family) => ({
    family: family.family,
    attempted: family.attempted,
    of: family.of,
    segments: family.agents.map((agent) => ({
      agent: agent.agent,
      accent: accentFor(agent.agent),
      attempted: agent.attempted,
      of: agent.of,
      width: share(agent.attempted, family.of),
    })),
  }))
}

/** A segment's length, and `0%` for a family that has not started or has no cases. */
function share(attempted: number, of: number): string {
  if (of === 0 || attempted === 0) {
    return '0%'
  }
  return `${Number(((attempted / of) * 100).toFixed(4))}%`
}

/** One mark in the panel's legend: an agent, and the accent its segments take. */
export interface ProgressKey {
  agent: string
  accent: string
}

/**
 * What the three colours are, once for the panel and never once per row.
 *
 * Six bars share three colours, so six legends would be the same three words five
 * times over. The keys are read off the rows themselves rather than off
 * `REFERENCE_AGENTS`, so the legend can only ever name the agents this run is drawing
 * and in the order it draws them — the equipment's own order, never inferred from a
 * name — and a swatch cannot take a colour no segment takes.
 *
 * Empty where no family was served: three marks above an empty panel would say this
 * run has three agents and no families.
 *
 * What keeps the ramp from reading as a grade is the name printed beside every mark —
 * the marks are in construction order and each is redundant with its agent's own
 * word, so no reader is left inferring an order from hue.
 */
export function progressKeys(reading: GateRunReading): readonly ProgressKey[] {
  const [first] = familyRows(reading)
  if (first === undefined) {
    return []
  }
  return first.segments.map((segment) => ({
    agent: segment.agent,
    accent: segment.accent,
  }))
}

/** One attempt as the screen reads it: the exchange, the verdict, and where from. */
export interface PayloadRow {
  /** Stable while the list grows: one attempt of one case against one agent. */
  key: string
  sent: string
  reply: string
  /** The attacker's point of view, in the bench's own word. Never coloured. */
  verdict: string
  /** How that verdict was reached: `deterministic` or `judged` (ADR-0004). */
  how: string
  where: string
  wire: string
}

/**
 * The last attempt the route served, which is one, or none before the first.
 *
 * A list rather than a value, and mapped rather than read at `[0]`, because the empty
 * case is a state the screen draws in words — and because how many the route serves is
 * the route's answer, not this module's assumption about it.
 *
 * Nothing here is a finding. A finding is a verdict plus its narrative and it is
 * written in the report; this is the verdict, the exchange behind it, and the two
 * facts about the wire that tell calls from attempts.
 */
export function payloads(reading: GateRunReading): readonly PayloadRow[] {
  return reading.recent.map((one) => ({
    key: `${one.agent}/${one.case_id}/${one.attempt}`,
    sent: one.sent,
    reply: one.reply,
    verdict: one.verdict,
    how: one.verdict_class,
    where: `${one.agent} · ${one.case_id} · attempt ${one.attempt}`,
    wire: `HTTP ${one.status_code} · ${one.sends} ${one.sends === 1 ? 'send' : 'sends'}`,
  }))
}

// --- what it decided -------------------------------------------------------------

/** One labelled fact, uncoloured, in the console's own idiom. */
export interface Fact {
  label: string
  value: string
}

/** One reference agent's rate on one family: the value, its counts, its interval. */
export interface AgentRate {
  agent: string
  /** The stylesheet's token for this agent's step of the one hue. Order, not rank. */
  accent: string
  rate: string
  counts: string
  interval: string
  /**
   * Where this rate sits on the family's own 0-to-1 line, as a CSS percentage.
   *
   * Computed here rather than in markup, because it is arithmetic over a measured
   * rate and this module is where the figures are read. A plot is the one place a
   * rate can be misread by being drawn, so the number that positions the dot is a
   * value a test can assert rather than an expression inside a `style` attribute.
   */
  at: string
}

/**
 * One family's line: three rates on a line, its `D`, and what the line reads.
 *
 * **The plot is one family's three rates and never two families' anything.** The
 * axis is 0 to 1 — the whole range a failure rate can take — so the three dots are
 * comparable to each other and to the floor, and to nothing on another card. There
 * is no second axis, no shared scale across the six and no ordering of the cards by
 * score: a reader who wants the six ranked has to do it themselves, and the bench
 * does not hand them a ranking it does not stand behind (ADR-0005).
 *
 * **`span` is `D` drawn rather than a second figure.** The bar runs from the
 * hardened rate to the trivial one, which is what `D` is by definition — trivial
 * minus hardened — so the drawing and the number are the same measurement twice and
 * cannot disagree.
 */
export interface FamilyReading {
  family: string
  rates: AgentRate[]
  /** `D` as the bare figure, or an em dash where this family decided nothing. */
  score: string
  /** `span = D 0.83 · ≥ 0.40`, the figure beside the bar it had to clear. */
  span: string
  /** Where the span bar starts, as a CSS percentage. */
  from: string
  /** How long the span bar is, as a CSS percentage. `D` at the plot's scale. */
  width: string
  /**
   * What the line reads, in one sentence: the verdict, then what it turned on.
   *
   * Or, for a family the decision set aside, the exclusion and its reading —
   * ADR-0015 asks the exclusion to name the family, the reason *and* the figure
   * that caused it, and this is that line on the family's own card rather than only
   * in a sibling list.
   */
  reads: string
  /** Whether this family decided nothing. Drawn, so a reader cannot miss it. */
  set_aside: boolean
  verdict: string
  /** The bench's own line for this family, carried unedited. */
  stated: string
}

export interface RuleBlockRead {
  kind: 'rule'
  heading: string
  statement: string
  clauses: RuleClause[]
}

export interface DecisionBlock {
  kind: 'decision'
  heading: string
  /** `passed`, `failed` or `not_decided` — a word, and never a colour. */
  outcome: string
  facts: Fact[]
  statement: string
}

export interface FamiliesBlock {
  kind: 'families'
  heading: string
  /** The one claim this block may not drop, and `gaterun.test.ts` guards it. */
  statement: string
  families: FamilyReading[]
}

export interface ExcludedBlock {
  kind: 'excluded'
  heading: string
  excluded: Fact[]
}

export interface WrittenBlock {
  kind: 'written'
  heading: string
  statement: string
  facts: Fact[]
}

export type DecidedBlock =
  | RuleBlockRead
  | DecisionBlock
  | FamiliesBlock
  | ExcludedBlock
  | WrittenBlock

/**
 * The no-composite claim, and the one sentence this screen may not lose.
 *
 * Six discrimination scores arrive at once, which makes this the surface most
 * likely to grow a mean of them — and a mean would read as a figure about the
 * bench, which is the thing ADR-0005 refuses. The view model has no field for one
 * and `gaterun.test.ts` asserts both halves: that no combined figure appears, and
 * that the block says so.
 */
const NOTHING_COMBINES_THEM =
  'Six families, six lines, and nothing that adds two of them.'

const THE_RULE_FIRST =
  'Above the answer it gave, so the outcome below is one you can re-derive rather ' +
  'than a verdict you would have to trust.'

/** The accent for one agent, from the one list the console names them by. */
function accentFor(agent: string): string {
  return REFERENCE_AGENTS.find((known) => known.name === agent)?.accent ?? ''
}

/** A measured rate as a position on the plot's own 0-to-1 axis. */
function at(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/** The rate one named agent read, out of the three the family carries. */
function rateOf(figures: FamilyFigures, agent: string): number | null {
  return figures.rates.find((rate) => rate.agent === agent)?.value ?? null
}

/**
 * Why a family decided nothing, as its own card says it.
 *
 * Built from the exclusion the decision recorded and the floor it was read against,
 * so the reading that barred the family is on the line that says it was barred. The
 * bench's own whole sentence is still on the card as `stated`; this is the short
 * form, and it is short by dropping words rather than by dropping the figure.
 */
function setAsideReads(barred: ExcludedFamily, floor: number): string {
  const because =
    barred.reason === 'not_measurable'
      ? 'this family could not be measured'
      : barred.kappa === null
        ? 'no κ was measured'
        : `κ = ${barred.kappa.toFixed(2)} is below the ${floor.toFixed(2)} floor`
  return (
    `excluded — ${because} · the bench cannot vouch for this family, so no D of ` +
    'its own decides anything here'
  )
}

/**
 * What the line reads: the two conditions the per-family rule turns on.
 *
 * The verdict is not in it. `D` and the floor it had to clear are printed side by
 * side above — `span = D 0.30 · ≥ 0.40` — so a family that did not pass says so in
 * the two figures rather than in a word. `FamilyReading.verdict` still carries the
 * word for a caller that wants it.
 */
function decidedReads(figures: FamilyFigures): string {
  const intervals = figures.intervals_separate
    ? 'intervals disjoint'
    : 'intervals overlap'
  const ordering = figures.monotonic
    ? 'monotonic'
    : `${figures.inversions} inversion${figures.inversions === 1 ? '' : 's'}`
  return `${intervals} · ${ordering}`
}

/**
 * One family's card, off its figures and the exclusion the decision recorded for it.
 *
 * `barred` is required rather than defaulted, on the same terms as the record's own
 * `excluded` field: a family whose exclusion this view forgot would be drawn as a
 * family that decided something, which is the one mistake this card can make and it
 * would be silent.
 */
function familyReading(
  figures: FamilyFigures,
  barred: ExcludedFamily | null,
  rule: DeclaredRule,
): FamilyReading {
  const hardened = rateOf(figures, 'hardened')
  const trivial = rateOf(figures, 'trivial')
  const span =
    hardened === null || trivial === null
      ? { from: '0%', width: '0%' }
      : {
          from: at(Math.min(hardened, trivial)),
          width: at(Math.abs(trivial - hardened)),
        }
  const aside = barred !== null
  return {
    family: figures.family,
    rates: figures.rates.map((rate) => ({
      agent: rate.agent,
      accent: accentFor(rate.agent),
      rate: rate.value.toFixed(2),
      counts: `${rate.successes}/${rate.attempts}`,
      interval: `[${rate.lower.toFixed(3)}, ${rate.upper.toFixed(3)}]`,
      at: at(rate.value),
    })),
    score: aside ? '—' : figures.discrimination.toFixed(2),
    span: aside
      ? 'span = D — · excluded'
      : `span = D ${figures.discrimination.toFixed(2)} · ≥ ${rule.discrimination_floor.toFixed(2)}`,
    from: span.from,
    width: span.width,
    reads: aside ? setAsideReads(barred, rule.kappa_floor) : decidedReads(figures),
    set_aside: aside,
    verdict: figures.passes ? 'passes' : 'does not pass',
    stated: figures.stated,
  }
}

/**
 * What the gate run decided, as an ordered sequence with the rule first.
 *
 * A sequence and not five fields, so that the one ordering this screen is required
 * to have — the declared rule above the decision — is a property of the value a
 * test can read rather than of markup nobody checks.
 *
 * Returns nothing at all where the gate run has not been decided: there is no
 * half-decision to draw, and a screen that rendered an empty outcome block would be
 * showing a gate run that failed something.
 */
/**
 * The exclusion this decision recorded for one family, or `null` where it decided.
 *
 * Read off `GateDecided.excluded` rather than off the family's own `excluded` mark,
 * because the mark is the reason alone and the card prints the reading behind it.
 * The two cannot disagree: the record fills both from one exclusion (ADR-0015,
 * `gate_record.gate_decided`).
 */
function barredIn(decision: GateDecided, family: string): ExcludedFamily | null {
  return decision.excluded.find((barred) => barred.family === family) ?? null
}

/**
 * A gate run's decision, from whichever carrier holds it.
 *
 * Narrower than `GateRunReading` on purpose: what `decidedView` needs is the rule,
 * the decision and the write-back, and a gate run this bench finished before a
 * restart has all three in its **record** and no progress to report. Typed as the
 * three fields rather than as the reading, so the record can be drawn by the same
 * view without a fake status being invented for it.
 */
export interface DecidedRun {
  rule: DeclaredRule
  decision: GateDecided | null
  written: WroteBack | null
}

export function decidedView(reading: DecidedRun): DecidedBlock[] {
  const decision = reading.decision
  if (decision === null) {
    return []
  }
  const blocks: DecidedBlock[] = [
    {
      kind: 'rule',
      heading: 'The rule applied',
      statement: THE_RULE_FIRST,
      clauses: clausesOf(reading.rule),
    },
    {
      kind: 'decision',
      heading: 'The outcome',
      outcome: decision.outcome,
      facts: [
        { label: 'families passing', value: `${decision.families_passing}` },
        { label: 'families monotonic', value: `${decision.families_monotonic}` },
        { label: 'families fit to report', value: `${decision.fit_families}` },
        { label: 'attempts recorded', value: `${decision.attempts}` },
        { label: 'agents', value: decision.agents.join(', ') },
        {
          label: 'library version',
          value: `${decision.library.cases} cases, sha256:${decision.library.digest}`,
        },
      ],
      statement: decision.read_from,
    },
    {
      kind: 'families',
      heading: 'Each family',
      statement: NOTHING_COMBINES_THEM,
      families: decision.families.map((figures) =>
        familyReading(figures, barredIn(decision, figures.family), reading.rule),
      ),
    },
  ]
  if (decision.excluded.length) {
    blocks.push({
      kind: 'excluded',
      heading: 'Excluded from the counts',
      excluded: decision.excluded.map((family) => ({
        label: readFamily(family.family),
        value: family.stated,
      })),
    })
  }
  const written = reading.written
  if (written !== null) {
    blocks.push({
      kind: 'written',
      heading: 'What it wrote back',
      statement: written.stated,
      facts: [
        { label: 'library', value: written.library },
        { label: 'readings appended', value: `${written.readings}` },
        {
          label: 'cases retired',
          value: written.retired.length ? written.retired.join(', ') : 'none',
        },
        {
          label: 'cases with no reading',
          value: written.unread.length
            ? written.unread.join(', ')
            : 'none — every case that ran has a reading',
        },
      ],
    })
  }
  return blocks
}
