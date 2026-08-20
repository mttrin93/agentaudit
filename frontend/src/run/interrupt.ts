/**
 * The approval interrupt as data: two figures, and the rules that decide when an
 * answer may go on the wire.
 *
 * A run is 181 calls in the scored layer and up to 96 more in the adaptive one,
 * every one of them on the operator's endpoint and their inference spend, so the
 * cost display is a **consent mechanism and not a convenience feature**
 * (ADR-0007). Everything in this module exists to keep the consent honest, and it
 * is a module rather than component state because the spec expects these screens
 * to be driven by hand and does not justify a browser driver: what can be asserted
 * without a browser is what the screen is allowed to show and what it is allowed
 * to send.
 *
 * **Two figures, and nothing that spans them.** The scored layer is arithmetic and
 * exact; the adaptive layer is a ceiling, because an attacker choosing its own
 * route spends unpredictably by construction. `RunEstimate` also carries a bounded
 * total and a bounded hard ceiling — ADR-0007's own table prints both — and this
 * screen renders neither, because the run screen's first criterion is that the two
 * figures arrive unblended and the spec's interface decision is that the interface
 * prints no total. What replaces them is not a smaller disclosure: each layer is
 * shown beside *the ceiling it is enforced against*, and those two ceilings are the
 * enforced limit, because the budget checks them per layer and a layer with room
 * left cannot borrow the other's (`budget.py`, `RunBudget.ceiling`). Nothing an
 * operator is shown with a `≤` in front of it may be exceeded, and nothing shown
 * here is a number this app added up.
 *
 * **The figures come from the registration that made the run, because that is the
 * only response that carries them.** `GET /runs/{id}` reports progress and no
 * estimate — deliberately, per the API's own note that nothing spans the layers
 * there — so the run screen is handed what `POST /runs` returned. The handoff is
 * `sessionStorage` rather than router state so that it survives the reload of a
 * screen a run may sit on for an hour, and it is keyed by run id so that no run is
 * ever shown another run's figures. When this app does not hold them, the screen
 * says so and offers no confirmation at all: a confirmation given against figures
 * nobody read is not consent, and *cannot confirm* is the safe direction for that
 * to fail in.
 */

import type { ApprovalBody, RunEstimate } from '../api/bench'

/** The two halves of a run, in the words the budget counts them in. */
export type Layer = 'scored' | 'adaptive'

/** The status a run holds while it is waiting on a human, and on nothing else. */
export const AWAITING_APPROVAL = 'awaiting_approval'

export const NOTHING_HAS_BEEN_SENT =
  'Nothing has been sent to your endpoint. The run is holding here — not asking ' +
  'here — and the first call it makes is the probe that checks the nonce you ' +
  'planted, which happens after you confirm and not before.'

export const NO_TOTAL_ON_PURPOSE =
  'These are two figures and there is no third one. The fixed suite is arithmetic ' +
  'and exact; the adaptive layer is a worst case, because an attacker that chooses ' +
  'its own route has no exact cost. A blended number would hide which half of the ' +
  'run is spending your budget, and an averaged adaptive figure would invite a run ' +
  'to exceed what you agreed to. Each layer is enforced against its own ceiling ' +
  'below it, so neither can borrow what the other did not spend.'

export const FIGURES_NOT_HELD =
  'This browser is not holding the figures this run was estimated at. They are ' +
  'returned once, by the registration that created the run, and this screen will ' +
  'not confirm a cost it cannot show you: a confirmation given against figures ' +
  'nobody read is not consent. Register the target again to see them — the run ' +
  'holding here records itself as unanswered after an hour, having sent nothing ' +
  'and spent nothing.'

/**
 * One layer's figure, as the interrupt shows it.
 *
 * `calls` and `ceiling` are strings and carry their own `≤`, on `CallFigure`'s
 * reasoning: the epistemic status belongs *in* the number a person reads, not in a
 * column beside it that a narrow screen might drop.
 */
export interface CostFigure {
  layer: Layer
  label: string
  calls: string
  kind: string
  basis: string
  cost: string
  ceiling: string
  /** What this layer does with those calls, in the units it does it in. */
  spends: string
}

/** `181`, or `≤ 96` when the figure is a bound. */
function rendered(calls: number, kind: string): string {
  return kind === 'ceiling' ? `≤ ${calls}` : `${calls}`
}

/**
 * The two figures, in the order ADR-0007's table puts them, and no third figure.
 *
 * Built from the layer records only. `total`, `hard_ceiling` and `presented` are
 * never read here, and `interrupt.test.ts` asserts that none of their numbers and
 * none of their words reaches the view — an absence is only worth claiming if
 * something checks it.
 */
export function costFigures(estimate: RunEstimate): readonly CostFigure[] {
  return [
    {
      layer: 'scored',
      label: 'Fixed suite — the scored layer',
      calls: rendered(estimate.scored.calls, estimate.scored.kind),
      kind: estimate.scored.kind,
      basis: estimate.scored.basis,
      cost: estimate.scored.cost,
      ceiling: `≤ ${estimate.scored_ceiling}`,
      spends:
        'Recorded cases, ten attempts each, plus the one probe that checks your ' +
        'nonce. Every number the bench signs comes from here.',
    },
    {
      layer: 'adaptive',
      label: 'Adaptive layer',
      calls: rendered(estimate.adaptive.calls, estimate.adaptive.kind),
      kind: estimate.adaptive.kind,
      basis: estimate.adaptive.basis,
      cost: estimate.adaptive.cost,
      ceiling: `≤ ${estimate.adaptive_ceiling}`,
      spends:
        'Episodes an attacker drives itself, under a turn cap. Nothing here is ' +
        'scored, so none of these calls reaches a rate.',
    },
  ]
}

/** The whole of what the interrupt puts in front of a person, as data. */
export interface InterruptView {
  figures: readonly CostFigure[]
  /**
   * Why there are two figures and no third one.
   *
   * Named for what it is rather than for what it refuses — a field called
   * `noTotal` would put the word *Total* in the serialised view, which is the
   * string `interrupt.test.ts` scans for. That is a small joke at this screen's
   * expense and it is also the test working: the assertion is over everything the
   * view carries, key names included.
   */
  unblended: string
  nothingSent: string
}

/** The interrupt's own view. Two figures, and the two sentences beside them. */
export function interruptView(estimate: RunEstimate): InterruptView {
  return {
    figures: costFigures(estimate),
    unblended: NO_TOTAL_ON_PURPOSE,
    nothingSent: NOTHING_HAS_BEEN_SENT,
  }
}

/**
 * What a person has declared at the interrupt, and what the bench says about the
 * run they are declaring it against.
 *
 * The status is part of the declaration rather than checked elsewhere, because
 * *an interrupt is answered once*: a confirmation for a run that is already
 * running is consent recorded for a spend that is happening anyway, and one for a
 * run whose hour ran out is consent for a run the graph has already been told
 * nobody authorised.
 */
export interface Confirming {
  status: string
  /** The figures the interrupt presented, or `null` when this app has none. */
  figures: RunEstimate | null
  /** Ticked by hand. Nothing computes it and nothing defaults it to `true`. */
  confirmed: boolean
  identity: string
  reason: string
}

/**
 * A confirmation ready to send, or the reasons it is not one.
 *
 * Two outcomes rather than a body beside a valid flag, in the shape
 * `registrationRequest` already uses: there is no way to reach the body of a
 * confirmation that was not given.
 */
export type ConfirmationRequest =
  | { kind: 'ready'; body: ApprovalBody }
  | { kind: 'withheld'; missing: string[] }

/**
 * The one path to a `confirmed: true`.
 *
 * Every branch that is not a completed, explicit confirmation returns the
 * withheld outcome, and the outcome carries no body: this is the function that
 * decides whether the operator's endpoint is attacked, and the only way to make
 * that decision unmissable in a screen is to make the confirmed body
 * unconstructible without it. `confirmed` is compared against `true` rather than
 * tested for truthiness, on `read_answer`'s reasoning at the other end of the
 * wire — a truthy-looking value spending somebody's inference budget is the
 * failure to guard against.
 */
export function confirmationRequest(declared: Confirming): ConfirmationRequest {
  const missing: string[] = []

  if (declared.status !== AWAITING_APPROVAL) {
    missing.push(
      `this run is ${declared.status} and is not holding an interrupt, so there ` +
        'is nothing here to confirm: an interrupt is answered once',
    )
  }
  if (declared.figures === null) {
    missing.push(FIGURES_NOT_HELD)
  }
  if (declared.confirmed !== true) {
    missing.push(
      'the two figures have not been confirmed. The run stays where it is until ' +
        'they are, and nothing has been sent to the target',
    )
  }
  if (!declared.identity.trim()) {
    missing.push(
      'a confirmation has to record who gave it: the run is charged to whoever ' +
        'confirms it, and the report names them beside the ceiling they confirmed',
    )
  }

  if (missing.length) {
    return { kind: 'withheld', missing }
  }
  return {
    kind: 'ready',
    body: {
      confirmed: true,
      identity: declared.identity.trim(),
      reason: declared.reason.trim(),
    },
  }
}

/**
 * The answer that spends nothing, available at every moment the other one is not.
 *
 * A no is sent rather than withheld, and it asks for nothing first — no identity,
 * no reason, no second click. The bench records it as **declined** and answers with
 * its own sentence saying that nothing was sent to the target and nothing was
 * spent, which is a better record than the *unanswered* a closed tab would leave:
 * nobody said no and nobody said anything are different facts about the same run
 * (`approval.py`). Putting a required field in front of the safe answer would be a
 * consent surface that made declining the harder of the two.
 */
export function declineRequest(identity: string, reason: string): ApprovalBody {
  return {
    confirmed: false,
    identity: identity.trim(),
    reason:
      reason.trim() ||
      'declined at the approval interrupt: the figures were not confirmed',
  }
}

/**
 * The little of `Storage` this app uses, so that the handoff can be tested.
 *
 * A three-method interface rather than the DOM's `Storage`, because these tests
 * run in node and there is no `sessionStorage` there. The screen passes the real
 * one; a test passes a map.
 */
export interface FigureStore {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

const HELD_UNDER = 'agentaudit.estimate.'

/** Keyed by run id, so that no run can ever be shown another run's figures. */
function keyFor(runId: string): string {
  return `${HELD_UNDER}${runId}`
}

/** Hold on to the figures `POST /runs` returned, for the screen that shows them. */
export function rememberTheFigures(
  store: FigureStore,
  runId: string,
  estimate: RunEstimate,
): void {
  store.setItem(keyFor(runId), JSON.stringify(estimate))
}

/**
 * The figures this run was estimated at, or `null` when this app does not hold
 * them.
 *
 * Anything that is not a record with both layers' call counts in it reads as *not
 * held*, and that includes a value some other version of this app wrote: a
 * half-recognised estimate would be a screen showing one figure where there are
 * two, or a blank where there is a number, in front of somebody about to agree to
 * it. `null` is the answer that cannot mislead, because the screen offers no
 * confirmation for it.
 */
export function theFiguresPresented(
  store: FigureStore,
  runId: string,
): RunEstimate | null {
  const held = store.getItem(keyFor(runId))
  if (!held) {
    return null
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(held)
  } catch {
    return null
  }
  return bothLayers(parsed) ? (parsed as RunEstimate) : null
}

/** Whether a parsed value carries both layers' figures. Nothing is filled in. */
function bothLayers(parsed: unknown): boolean {
  if (typeof parsed !== 'object' || parsed === null) {
    return false
  }
  const held = parsed as Record<string, unknown>
  return (
    isFigure(held.scored) &&
    isFigure(held.adaptive) &&
    typeof held.scored_ceiling === 'number' &&
    typeof held.adaptive_ceiling === 'number'
  )
}

function isFigure(figure: unknown): boolean {
  if (typeof figure !== 'object' || figure === null) {
    return false
  }
  const held = figure as Record<string, unknown>
  return (
    typeof held.calls === 'number' &&
    typeof held.kind === 'string' &&
    typeof held.basis === 'string' &&
    typeof held.cost === 'string'
  )
}
