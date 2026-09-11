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

import { useState } from 'react'

import type { EmptyQueue, MeasureControl, QueueRow } from './pending'
import { ADMITTED, REJECTED } from './pending'

/** Every route awaiting a decision, and the ones already decided under them. */
export function TheQueue({
  rows,
  empty,
  selected,
  choose,
}: {
  rows: QueueRow[]
  empty: EmptyQueue | null
  selected: readonly string[]
  choose: (route: string, taken: boolean) => void
}) {
  /* Whose state this is: the screen's, and not the bench's. Hiding a refused route is
     a thing a reader does to a list they are looking at, so it lives here and is gone
     on the next visit — a preference the console stored would be a decision about
     somebody's findings, kept without their asking. */
  const [hiding, setHiding] = useState(false)
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
  const refused = rows.filter((row) => row.state === REJECTED).length
  const shown = hiding ? rows.filter((row) => row.state !== REJECTED) : rows
  return (
    <section>
      <h2>What the attacker found</h2>
      {/*
        A control that hides the refused routes, and never one that deletes them.

        A route that was a property of one model is a finding (ADR-0012), and the queue
        is where that finding is kept — so this takes them off the screen and nothing
        off the record: the rows come back with the button, the bench is not asked
        anything, and a reload shows the queue whole. What an operator is triaging is
        the routes still to decide, and a refused one is not one of them.

        Drawn only where there is something to hide, so the control is never a button
        that does nothing.
      */}
      {refused > 0 ? (
        <p className="asserts">
          <button type="button" onClick={() => setHiding(!hiding)}>
            {hiding
              ? `Show the ${refused} refused route(s)`
              : `Hide the ${refused} refused route(s)`}
          </button>
        </p>
      ) : null}
      {/* The bench's own sentence about the queue is not drawn. It said a pending
          route is not a case, that it becomes one only by clearing the cross-model
          bar, and that nothing here reaches a denominator or a report — which the
          table under it says by being a table of routes with a state column and no
          figure in it (ADR-0010, ADR-0012). `reading.statement` is still built and
          still tested, and the sentence travels with the route on the wire. */}
      {/*
        One row a route, where one block a route stood.

        A block carried the family, the prose, four labelled facts and two sentences,
        and a queue of five put the same six shapes in thirty places. In rows the
        families line up down one edge, the targets down another and the states down a
        third — which is what a queue is read for: picking the ones to measure.

        The two sentences that were identical under every rejected route are one line
        under the table now (below). The gate's own reason stays per route, because it
        is per route, and it is folded: it is the paragraph an operator opens when they
        want to know why *this* one was refused, and six of them unfolded were the page.
      */}
      <div className="table-wrap">
        <table className="routes-queue">
          <thead>
            <tr>
              <th scope="col">family</th>
              <th scope="col">beat</th>
              <th scope="col">found</th>
              <th scope="col">probe</th>
              <th scope="col">state</th>
            </tr>
          </thead>
          {shown.map((row) => (
            <Row
              row={row}
              taken={selected.includes(row.route)}
              choose={choose}
              key={row.route}
            />
          ))}
        </table>
      </div>

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
    <tbody>
      <tr>
        {/* The checkbox lives in the family's own cell: the name an operator triages
            on and the box they tick are one thing to reach for. */}
        <th scope="row">
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
        </th>
        <td>{row.target}</td>
        <td className="when-cell">{row.filed}</td>
        {/* The digest, and never the probe (ADR-0008). */}
        <td className="id-cell">
          <code>{row.probe}</code>
        </td>
        {/* The state carries its own class so the word takes that state's colour —
            identity and never a grade, which is the distinction the stylesheet's
            comment turns on: an admitted route and a refused one are two things that
            happened, not a better and a worse one. */}
        <td className={`state-cell ${row.state}`}>{row.state}</td>
      </tr>
      <tr className="route-said">
        <td colSpan={5}>
          {/* What the route did, in the attacker's own prose. */}
          <p>{row.description}</p>
          {/*
            And why it was decided as it was, folded.

            **The bench's own words, and its own lines.** `AdmissionOutcome.stated()` is
            a record: the case, the decision, the provenance, which bar it faced and how
            many models it required, then one line a model with that model's `D`, its
            two intervals and the cut it was read against. It is written with newlines
            and it was drawn in a paragraph, which collapsed five lines into a wall of
            clauses — the same words, in the shape that makes them unreadable.

            Set in the monospace with its line breaks kept, so each model's reading is a
            line and the decision is the first of them. Not one character is reworded:
            this is the sentence a reader checks a decision against, and a screen that
            shortened it would be a second account of what the bar found (ADR-0012).
          */}
          {row.reason ? (
            <details>
              <summary>why</summary>
              <pre className="reason">{row.reason}</pre>
            </details>
          ) : null}
          {row.state === ADMITTED ? (
            row.enteredAs ? (
              <p className="aside">
                Written into the case library as <code>{row.enteredAs}</code>.
              </p>
            ) : (
              <p className="aside">
                The record this route became is named in the reason, in the deciding
                surface’s own words — a stated absence, and not a filename
                guessed out of a sentence.
              </p>
            )
          ) : null}
        </td>
      </tr>
    </tbody>
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
        <div className="citation deciding">
          {/* The bench's own sentence about what deciding does, and nothing under it.
              The line that stood there named the models and the directory a cleared
              route is written into: the models are on the estimate an operator confirms
              before anything is sent, where the figure they are about is, and the
              directory is a path on the bench's own disk. Neither changes what the
              press does. `control.models` and `control.library` are still read and
              still tested. */}
          <p>{control.statement}</p>
          <button
            type="button"
            className="primary"
            disabled={going || selected.length === 0}
            onClick={begin}
          >
            {control.label}
          </button>
          {/* Nothing where nothing is selected. The line that stood there said a
              measurement is per route and is never defaulted to all of them — an
              argument for why the button is dead, over a table whose first column is
              the checkboxes that enable it. What a reader loses is the *why*: the
              control is greyed and the page no longer says so in words. */}
          {selected.length === 0 ? null : (
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
