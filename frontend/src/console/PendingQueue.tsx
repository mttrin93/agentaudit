/**
 * The queue itself: one block per route, the selection, and the control over it.
 *
 * The console's idiom — the reading column, labelled uncoloured facts, a stated
 * absence where a control would have been. Nothing new was invented for this page;
 * what it adds is one more thing that idiom says.
 *
 * **A row says what the route did, and never the probe it did it with.** The
 * attacker's own prose, the target it beat, the day it was filed, the digest of the
 * probe — and no payload, because the exception ADR-0104 grants the pending store is
 * for measuring a route and never for showing it.
 *
 * **A decided row keeps its place and loses its checkbox.** A rejected route is a
 * finding in its own right (ADR-0012) and an admitted one names the record it
 * became, so neither is dropped from the page a decision was started from. What they
 * lose is the affordance: a decided route's payload went with its decision, so there
 * is nothing left to measure it with.
 */

import type { EmptyQueue, MeasureControl, QueueRow } from './pending'
import { ADMITTED, REJECTED } from './pending'

/** Every route awaiting a decision, and the ones already decided under them. */
export function TheQueue({
  rows,
  empty,
  selected,
  choose,
  statement,
}: {
  rows: QueueRow[]
  empty: EmptyQueue | null
  selected: readonly string[]
  choose: (route: string, taken: boolean) => void
  statement: string
}) {
  if (empty !== null) {
    return (
      <section>
        <h2>{empty.heading}</h2>
        {/* Polite, and a `citation` rather than a `refusal`: this is a reading the
            page arrived at, and not the answer to anything anybody pressed
            (ADR-0080). Nothing here is an error and nothing is a blank. */}
        <div className="citation" role="status">
          <p>{empty.statement}</p>
          <p className="aside">{empty.aside}</p>
        </div>
      </section>
    )
  }
  return (
    <section>
      <h2>What the attacker found</h2>
      <p className="aside">{statement}</p>
      <ul className="artefacts routes-queue">
        {rows.map((row) => (
          <li className="artefact" key={row.route}>
            <Row
              row={row}
              taken={selected.includes(row.route)}
              choose={choose}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

/** One route: what it did, whose agent it beat, and what became of it. */
function Row({
  row,
  taken,
  choose,
}: {
  row: QueueRow
  taken: boolean
  choose: (route: string, taken: boolean) => void
}) {
  return (
    <>
      <h3>
        {row.chooseable ? (
          <label className="declaration">
            <input
              type="checkbox"
              checked={taken}
              onChange={(event) => choose(row.route, event.target.checked)}
            />
            <span className="wording">{row.family}</span>
          </label>
        ) : (
          row.family
        )}
      </h3>
      <p>{row.description}</p>
      <dl className="review">
        <dt>Beat</dt>
        <dd>{row.target}</dd>
        <dt>Found</dt>
        <dd>{row.filed}</dd>
        <dt>Probe</dt>
        {/* The digest, and never the probe (ADR-0008). */}
        <dd>
          <code>{row.probe}</code>
        </dd>
        <dt>State</dt>
        <dd>{row.state}</dd>
      </dl>
      {row.reason ? <p className="aside">{row.reason}</p> : null}
      {row.state === ADMITTED ? (
        row.enteredAs ? (
          <p>
            Written into the case library as <code>{row.enteredAs}</code>.
          </p>
        ) : (
          <p className="aside">
            The record this route became is named in the reason above, in the
            deciding surface’s own words. This page has not read the measurement
            that wrote it — a stated absence, and not a filename guessed out of a
            sentence.
          </p>
        )
      ) : null}
      {row.state === REJECTED ? (
        <p className="aside">
          Kept on this page rather than dropped: a route that was a property of one
          model is a finding, and its reason above is the gate’s own.
        </p>
      ) : null}
    </>
  )
}

/**
 * The one control this page offers, or the stated reason there is none.
 *
 * A refusal is drawn, never a missing control: a page whose one control is absent is
 * indistinguishable from a bench that cannot decide a route, which is the one thing
 * this block exists to tell apart. Only the held library gets a control beside it,
 * because it is the only one of the five that waiting answers.
 */
export function TheControl({
  control,
  selected,
  begin,
  going,
  holding,
  ask,
}: {
  control: MeasureControl
  selected: readonly string[]
  begin: () => void
  /** Whether the control is greyed: an operator part-way through the walk that
   * starts a measurement is not offered a second one. */
  going: boolean
  /** Whether a measurement this page started is actually on the wire, which is a
   * different fact and the only one that may say a lease is held. */
  holding: boolean
  ask: () => void
}) {
  return (
    <section>
      <h2>Deciding them</h2>
      {control.available ? (
        <div className="citation">
          <p>{control.statement}</p>
          <p className="aside">
            Measured on {control.models.join(' and ')}, against three reference
            agents of known construction. A route that clears the bar is written
            into <code>{control.library}</code>.
          </p>
          <button
            type="button"
            className="primary"
            disabled={going || selected.length === 0}
            onClick={begin}
          >
            {control.label}
          </button>
          {selected.length === 0 ? (
            <p className="aside">
              Nothing is selected. A measurement is per route — three reference
              agents on two models each — so the routes are chosen here and never
              defaulted to all of them.
            </p>
          ) : (
            <p className="aside">
              {selected.length} route(s) selected. Nothing is sent until the three
              statements are made and the estimate is confirmed.
            </p>
          )}
          {holding ? (
            <p className="aside">
              A measurement started here is going. It holds an exclusive lease on the
              case library while it runs, so this control comes back when that one
              has answered.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="citation uncited">
          <h3>{control.heading}</h3>
          <p>{control.statement}</p>
          <p className="aside">
            The bench’s own name for this: <code>{control.refusal}</code>.
          </p>
          {control.waiting ? (
            <>
              <button type="button" onClick={ask}>
                Ask the bench again
              </button>
              <p className="aside">
                Nothing is started by asking. The lease is released a moment after
                the run holding it is decided, and this reads whether it has been.
              </p>
            </>
          ) : null}
          {control.waiting ? null : (
            <p className="aside">
              Nothing has been sent and nothing has been spent: every route below
              that is awaiting a decision is still awaiting one.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
