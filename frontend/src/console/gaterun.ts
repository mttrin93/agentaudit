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
import type { CostFigure } from '../run/interrupt'
import { adaptiveReading, scoredReading, type LayerReading } from '../run/progress'
import {
  ATTESTATION_STATEMENTS,
  type Attested,
  type Statement,
} from '../register/declarations'
import { clausesOf, REFERENCE_AGENTS, type RuleClause } from './gate'

/** The status a gate run holds while it waits on a human, and on nothing else. */
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
 * `asks` is what happens *before* anything is sent, listed on the control itself:
 * an operator about to spend 830 calls of their own and rewrite the library every
 * one of their runs is measured with should be able to read what the next three
 * screens will ask them without pressing anything first.
 */
export interface StartHere {
  available: true
  label: string
  /** The case library this gate run would read and write back to. */
  library: string
  statement: string
  asks: string[]
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

const STARTING_ONE_ASKS = [
  'The three attestation statements, one at a time, recorded against your name — ' +
    'the same three a target run records, and for the same reason: two of them are ' +
    'consequences nobody would infer.',
  'The estimated cost, as two figures against two ceilings, before anything is ' +
    'sent. Declining it spends nothing and writes nothing.',
]

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
    library: start.library,
    statement: start.statement,
    asks: [...STARTING_ONE_ASKS],
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
    'which it starts and stops itself — so this statement is about the bench you ' +
    'are operating rather than about somebody else’s system. It is recorded either ' +
    'way, because a gate run that skipped the attestation would take a path no ' +
    'operator’s run takes.',
  not_production:
    'The reference agents are test equipment and never reach a user. What a gate ' +
    'run changes that is not disposable is the case library: it appends a ' +
    'discrimination reading to every record it reads and marks retired what the ' +
    'rule retires, and that library is the one every run on this bench is ' +
    'measured with.',
  accepts_provider_policy_and_cost:
    'The payloads reach your model provider under your credentials — about 830 ' +
    'calls of them, plus the adjudicator’s against the gold set — so the policy ' +
    'violations are recorded against your account and the inference is billed to ' +
    'it. The next screen shows the two figures before anything is sent.',
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

/** The statements that have not been made, in the wording they were asked in. */
export function withheld(attesting: Attesting): string[] {
  return GATE_RUN_STATEMENTS.filter(
    (statement) => !attesting.attested[statement.field],
  ).map((statement) => statement.wording)
}

/**
 * A gate run ready to start, or the reasons it is not one.
 *
 * Two outcomes rather than a body beside a valid flag, so there is no way to reach
 * the body of a gate run whose statements were not all made.
 */
export type GateRunRequest =
  | { kind: 'ready'; body: StartGateRunBody }
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
  missing.push(
    ...withheld(attesting).map((wording) => `not attested: ${wording}`),
  )
  if (attesting.price_per_call.trim() && !attesting.currency.trim()) {
    // `CallPrice`'s own guard, held here so the operator meets it as an unfinished
    // step rather than as a 422: an amount with a currency the bench chose is a
    // figure the operator did not state.
    missing.push(
      'a price per call needs the currency it is in, or declare the gate run not ' +
        'priced',
    )
  }

  if (missing.length) {
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

export const NO_TOTAL_ON_PURPOSE =
  'These are two figures and there is no third one. The scored layer is ' +
  'arithmetic and exact — every live case at the declared attempts per case, ' +
  'against each of the three agents — and the adaptive layer is a worst case, ' +
  'because an attacker that chooses its own route has no exact cost. A blended ' +
  'number would hide which half of the gate run is spending your budget, and an ' +
  'averaged adaptive figure would invite one to exceed what you agreed to. Each ' +
  'layer is enforced against its own ceiling below it, so neither can borrow what ' +
  'the other did not spend.'

export const NOTHING_HAS_BEEN_SENT =
  'Nothing has been sent and not one case record has been written to. The gate ' +
  'run is holding here — it has this bench’s case library and it has made no call ' +
  '— and the first thing it does after you confirm is plant a nonce in each of ' +
  'the three agents it started.'

export const WHAT_IT_WRITES =
  'Confirming this writes to the case library named above: a discrimination ' +
  'reading appended to every case record the run reads, and a retirement marked ' +
  'on any case the rule retires. Marked and never deleted. Declining writes ' +
  'nothing at all.'

/** `830`, or `≤ 288` when the figure is a bound. */
function rendered(calls: number, kind: string): string {
  return kind === 'ceiling' ? `≤ ${calls}` : `${calls}`
}

/**
 * The two figures, in the order the estimate declares them, and no third figure.
 *
 * `CostFigure` is the interrupt's own shape, reused because one layer's figure
 * beside the ceiling it is enforced against is the same reading whatever is being
 * estimated. What is not reused is the prose: a gate run's scored layer is three
 * agents rather than one target, and its adaptive layer decides nothing about
 * anybody.
 */
export function gateCostFigures(
  estimate: GateRunEstimate,
): readonly CostFigure[] {
  return [
    {
      layer: 'scored',
      label: 'Scored layer — the half that decides the gate',
      calls: rendered(estimate.scored.attempt_calls, estimate.scored.kind),
      kind: estimate.scored.kind,
      basis: estimate.scored.basis,
      cost: estimate.scored.cost,
      ceiling: `≤ ${estimate.scored.attempt_ceiling}`,
      spends:
        `${estimate.scored.cases} live cases at ` +
        `${estimate.scored.attempts_per_case} attempts each, against all three ` +
        'reference agents, plus the one probe that plants a nonce in each. Every ' +
        'figure the decision turns on comes from here.',
    },
    {
      layer: 'adaptive',
      label: 'Adaptive layer — which decides nothing',
      calls: rendered(estimate.adaptive.turn_calls, estimate.adaptive.kind),
      kind: estimate.adaptive.kind,
      basis: estimate.adaptive.basis,
      cost: estimate.adaptive.cost,
      ceiling: `≤ ${estimate.adaptive.turn_ceiling}`,
      spends:
        `Episodes an attacker drives itself, ${estimate.adaptive.episodes_per_family} ` +
        `per family per agent under a cap of ${estimate.adaptive.turns_per_episode} ` +
        'turns. Nothing here is scored, so none of these calls reaches the gate ' +
        'decision.',
    },
  ]
}

/** The whole of what the interrupt puts in front of a person, as data. */
export interface GateInterruptView {
  figures: readonly CostFigure[]
  library: string
  unblended: string
  writesBack: string
  nothingSent: string
}

/** The estimate as the screen shows it: two figures and the sentences beside them. */
export function gateInterruptView(
  estimate: GateRunEstimate,
  library: string,
): GateInterruptView {
  return {
    figures: gateCostFigures(estimate),
    library,
    unblended: NO_TOTAL_ON_PURPOSE,
    writesBack: WHAT_IT_WRITES,
    nothingSent: NOTHING_HAS_BEEN_SENT,
  }
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

/**
 * Where the figures came from, when they came from the run this process just made.
 *
 * Said rather than assumed, because the same view draws the record of a gate run
 * this bench finished before a restart, and *which* reading an operator is looking
 * at is a fact about the figures rather than a detail of the plumbing.
 */
export const FROM_THIS_PROCESS =
  'read off the gate run this bench itself ran, from the process that made the ' +
  'attempts. Nothing here was parsed out of a document.'

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
  statement: string
  families: FamilyReading[]
}

export interface ExcludedBlock {
  kind: 'excluded'
  heading: string
  statement: string
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

const THE_RULE_FIRST =
  'The rule this gate run was decided under, in the bench’s own words and above ' +
  'the answer it gave. Read in this order the outcome below is something you can ' +
  're-derive; read the other way round it is a verdict you would have to trust.'

const READ_OFF_THE_RUN =
  'Every figure below was read off the attempts this gate run just made, in the ' +
  'process that made them. Nothing here was parsed out of a document.'

const NOTHING_COMBINES_THEM =
  'Six families, six lines, and nothing that adds two of them. A mean of these ' +
  'discrimination scores would read as a figure about the bench and it is not one: ' +
  'the counts the rule is decided on are counts of families, and each score belongs ' +
  'to the family it was measured on.'

const EXCLUDED_IS_NOT_A_FAIL =
  'A family excluded here was not scored a fail and was not force-passed. Its ' +
  'rates were measured and are recorded, and they decide nothing in either count.'

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

/** What a family that decided something reads: the verdict, then what it turned on. */
function decidedReads(figures: FamilyFigures): string {
  const intervals = figures.intervals_separate
    ? 'intervals disjoint'
    : 'intervals overlap'
  const ordering = figures.monotonic
    ? 'monotonic'
    : `${figures.inversions} inversion${figures.inversions === 1 ? '' : 's'}`
  const verdict = figures.passes ? 'passes' : 'does not pass'
  return `${verdict} · ${intervals} · ${ordering}`
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
      heading: 'The rule this gate run was decided under',
      statement: THE_RULE_FIRST,
      clauses: clausesOf(reading.rule),
    },
    {
      kind: 'decision',
      heading: 'What it answered under that rule',
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
      heading: 'Each family, with the figures its line turned on',
      statement: `${READ_OFF_THE_RUN} ${NOTHING_COMBINES_THEM}`,
      families: decision.families.map((figures) =>
        familyReading(figures, barredIn(decision, figures.family), reading.rule),
      ),
    },
  ]
  if (decision.excluded.length) {
    blocks.push({
      kind: 'excluded',
      heading: 'Families excluded from the counts',
      statement: EXCLUDED_IS_NOT_A_FAIL,
      excluded: decision.excluded.map((family) => ({
        label: family.family,
        value: family.stated,
      })),
    })
  }
  const written = reading.written
  if (written !== null) {
    blocks.push({
      kind: 'written',
      heading: 'What it wrote back to the case library',
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
