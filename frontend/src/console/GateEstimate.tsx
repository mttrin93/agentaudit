/**
 * The two figures, and the confirmation in front of them.
 *
 * Moved out of `GateScreen.tsx` by #14's split, unchanged. The halt an operator
 * answers: the scored layer exact, the adaptive layer a ceiling, the bounded total
 * and the hard ceiling that is the figure actually enforced (ADR-0007). Nothing here
 * adds a figure and nothing averages one.
 *
 * **Declining is an answer.** It goes on the wire as `confirmed: false` so the run
 * is recorded as declined by a person rather than left to time out as unanswered.
 */

import type {
  GateInterruptView,
} from './gaterun'

/**
 * The estimate, as two figures against two ceilings, before anything is sent.
 *
 * Two blocks rather than a table, because a table of two numeric columns has a
 * footer and a footer is where somebody puts a total. The response's own bounded
 * total is not on it at all: what an operator reads instead is each layer beside the
 * ceiling it is enforced against, which is the enforced limit (ADR-0007).
 *
 * **The two figures, the box and the two buttons — and no prose between them.** The
 * record's own `statement`, the sentence about there being no third figure, the
 * library path, what confirming writes and what has not been sent yet were all here
 * and are all gone. Every one of them is still on the wire, where an auditor reading
 * the gate run reads them. What decides whether anything is spent is unchanged and is
 * not prose: `gateConfirmation` builds a body only from an explicit yes on a halted
 * gate run, and the two controls say which is which — *Decline — spend nothing*, and
 * *Confirm and run the gate*.
 */
export function TheEstimate({
  view,
  confirmed,
  setConfirmed,
  confirm,
  decline,
  busy,
}: {
  view: GateInterruptView
  confirmed: boolean
  setConfirmed: (given: boolean) => void
  confirm: () => void
  decline: () => void
  busy: boolean
}) {
  return (
    <section>
      <h2>What this gate run will cost</h2>
      <dl className="figures">
        {view.figures.map((figure) => (
          <div className="figure" key={figure.layer}>
            <dt>{figure.label}</dt>
            <dd>
              <span className="calls">{figure.calls}</span>
              {/*
                The unit, said rather than left to be inferred: the big number is a
                count of calls, and beside a currency in the next span it was read
                as money by somebody who had every reason to.
              */}
              <span className="unit">calls</span>
              <span className="money">{figure.cost}</span>
              <span className="kind">{figure.kind}</span>
            </dd>
            <dd>{figure.basis}</dd>
            <dd>{figure.spends}</dd>
            <dd className="kind">
              enforced against this layer’s own ceiling of {figure.ceiling}
            </dd>
          </div>
        ))}
      </dl>
      <label className="declaration">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
        />
        <span className="wording">
          I have read both figures and I confirm this gate run
        </span>
      </label>

      <footer className="walk">
        <button type="button" onClick={decline} disabled={busy}>
          Decline — spend nothing
        </button>
        <button
          type="button"
          className="primary"
          onClick={confirm}
          disabled={busy || !confirmed}
        >
          {busy ? 'Confirming…' : 'Confirm and run the gate'}
        </button>
      </footer>
    </section>
  )
}
