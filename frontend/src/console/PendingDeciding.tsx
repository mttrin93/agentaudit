/**
 * The three statements, the estimate, and where each route got to.
 *
 * The gate screen's three blocks with this surface's own content: the attestation
 * `registration.py` refuses to construct incomplete, asked one statement per screen;
 * the halt in front of the spend, with the figure beside the ceiling it is enforced
 * against; and progress reported a route at a time, because the action is minutes
 * long and the operator selected the routes one at a time (spec story 10).
 *
 * **Nothing here can start or confirm anything.** Each block reports what is missing
 * and hands the control back: the bodies are built by `measurementRequest` and
 * `measurementConfirmation`, neither of which will build one from an incomplete
 * declaration or from anything but an explicit yes on a halted measurement.
 */

import { AttestingAs } from '../attesting'
import { Blocked, STILL_UNDECLARED } from '../blocked'
import type {
  Attesting,
  EstimateView,
  MeasurementStatement,
  ModelBar,
  ProgressRow,
} from './pending'
import { ADMITTED } from './pending'

/** The three statements, one at a time, in the record's own wording. */
export function TheAttestation({
  statements,
  step,
  attesting,
  declare,
  back,
  forward,
  missing,
  busy,
  routes,
}: {
  statements: readonly MeasurementStatement[]
  step: number
  attesting: Attesting
  declare: (changed: Partial<Attesting>) => void
  back: () => void
  forward: () => void
  missing: string[]
  busy: boolean
  routes: number
}) {
  const statement = statements[step]
  const last = step + 1 === statements.length
  const made = attesting.attested[statement.field]
  const held = busy || !made || (last && missing.length > 0)
  const reasons = last ? missing : []
  return (
    <section>
      <form
        onSubmit={(event) => {
          // Prevented for `TheAttestation`'s reason on the gate screen: the
          // browser's own submit would reload the console and take the declaration
          // with it.
          event.preventDefault()
          if (!held) {
            forward()
          }
        }}
      >
        <h2>
          Statement {statement.step} of {statement.of}
        </h2>
        <p className="aside">
          For the {routes} route(s) you selected, and for no others.
        </p>
        <p className="consequence">{statement.consequence}</p>
        <label className="declaration">
          <input
            type="checkbox"
            checked={made}
            onChange={(event) =>
              declare({
                attested: {
                  ...attesting.attested,
                  [statement.field]: event.target.checked,
                },
              })
            }
          />
          <span className="wording">{statement.wording}</span>
        </label>

        {step === 0 ? (
          <>
            <AttestingAs />
            <label className="priced">
              Price per call
              <input
                value={attesting.price_per_call}
                onChange={(event) => declare({ price_per_call: event.target.value })}
                placeholder="leave empty for a measurement you have not priced"
              />
              <span className="aside">
                What one call costs you, on your own provider.
              </span>
            </label>
          </>
        ) : null}

        <Blocked reasons={reasons} />

        <footer className="walk">
          <button type="button" onClick={back} disabled={busy}>
            {step === 0 ? 'Not now' : 'Back'}
          </button>
          <button
            type="submit"
            className="primary"
            disabled={held}
            aria-describedby={reasons.length ? STILL_UNDECLARED : undefined}
          >
            {last ? (busy ? 'Starting…' : 'See what it will cost') : 'Continue'}
          </button>
        </footer>
      </form>
    </section>
  )
}

/**
 * The estimate, before anything is sent: a row per route, then what is enforced.
 *
 * One layer and therefore one figure and one ceiling — the adaptive layer is
 * switched off for an admission run, so there is nothing to add to this and no
 * second number anywhere on the halt (ADR-0010, ADR-0058). The rows add up to more
 * than the total and the bench's own sentence under them says why; it is served
 * rather than composed here, because an explanation this app wrote would be a second
 * account of an arithmetic the bench owns.
 */
export function TheEstimate({
  view,
  confirmed,
  setConfirmed,
  confirm,
  decline,
  busy,
}: {
  view: EstimateView
  confirmed: boolean
  setConfirmed: (given: boolean) => void
  confirm: () => void
  decline: () => void
  busy: boolean
}) {
  return (
    <section>
      <h2>What deciding these will cost</h2>
      <dl className="figures">
        {view.perRoute.map((figure) => (
          <div className="figure" key={figure.route}>
            <dt>{figure.family}</dt>
            <dd>
              <span className="calls">{figure.calls}</span>
              {/* The unit, said rather than left to be inferred: the big number is
                  a count of calls, and beside a currency it was read as money. */}
              <span className="unit">calls</span>
              <span className="money">{figure.cost}</span>
            </dd>
            <dd>{figure.basis}</dd>
            <dd className="kind">against {figure.target}</dd>
          </div>
        ))}
        <div className="figure" key="all of them">
          <dt>All the routes you selected</dt>
          <dd>
            <span className="calls">{view.calls}</span>
            <span className="unit">calls</span>
            <span className="money">{view.cost}</span>
            <span className="kind">exact</span>
          </dd>
          <dd className="kind">
            enforced against a ceiling of {view.ceiling} calls
          </dd>
          <dd>Measured on {view.models.join(' and ')}.</dd>
        </div>
      </dl>

      {/* The estimate's own sentence about itself is not drawn. It is on the wire and
          in `report.json`, and what an operator needs in front of the spend is the
          figures and the ceiling they are enforced against — the rows are a table and
          a paragraph under them explaining how to add them up was a paragraph read
          past. `THE_ESTIMATE_IS_PER_ROUTE` in `api/app.py` still says it, and
          ADR-0010 and ADR-0058 still argue it. */}

      {/* No form, on the run screen's own reasoning: this is the halt in front of
          the spend, there is no field for Enter to finish, and the one thing a form
          would buy is a keystroke that confirms the spend from the checkbox. */}
      <label className="declaration">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
        />
        <span className="wording">
          I have read the figure and the ceiling, and I confirm this measurement
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
          {busy ? 'Confirming…' : 'Confirm and measure'}
        </button>
      </footer>
    </section>
  )
}

/**
 * Where the measurement has got to, a route at a time, and what the bar said.
 *
 * `where` is prose the bench wrote and this page does not branch on it: what a route
 * *is* is `state`, which is what the store holds it as. The bar's own lines are
 * under the rows — a command-line run prints them, this surface has no terminal, and
 * a decision somebody paid for should be checkable against the sentences the bar
 * wrote rather than only against a status.
 */
export function TheMeasurement({
  rows,
  bars,
}: {
  rows: ProgressRow[]
  bars: ModelBar[]
}) {
  return (
    <section className="measuring">
      <h2>The measurement</h2>
      {/* The status block is not drawn. It repeated the confirmation an operator had
          just given — who confirmed it, that the routes go to the three agents, and
          that the ceiling aborts rather than exceeds — beside rows that say where each
          route is and bars that say how far each model has got. `reading.status` and
          `reading.statement` are still built and still tested, and both travel on the
          wire.

          **The live region moves with it**, onto the rows: this screen reports itself
          as it goes and something has to be the thing a screen reader is told about
          (ADR-0080). The rows are what actually changes — a route's state is the
          progress — so they are the honest live region, and the block that announced
          a sentence that never changed was announcing nothing twice. */}
      <ul className="artefacts routes-queue" role="status">
        {rows.map((row) => (
          <li className="artefact" key={row.route}>
            <h3>{row.target}</h3>
            {/* The attacker's prose is not repeated here. It is on the route's row in
                the queue below, where a reader picking routes needs it; on this card
                the questions are where this one got to and what it was decided as,
                and a paragraph above them pushed both under the fold. */}
            {/* The state alone. `where` says where a route got to, which while a
                pass is running is the one thing the state cannot say — but once a
                route is decided it reads *decided: rejected* over a state that reads
                *rejected*, which is the same word twice under two labels. The bar
                below carries the in-flight reading, so this row keeps the answer and
                drops the commentary. `row.where` is still built and still tested. */}
            <dl className="review">
              <dt>State</dt>
              <dd>{row.state}</dd>
            </dl>
            {row.state === ADMITTED && row.enteredAs ? (
              <p>
                Written into the case library as <code>{row.enteredAs}</code>.
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {/* The bar's own lines are not drawn, and the reason a row carries is not
          drawn beside it: what a route is doing is its state, and the sentences
          under it restated that at length — the bar's reading model by model, and
          the decision's own prose. Both are still built, still tested, and still on
          the wire; the queue below folds the reason behind *why*, which is where a
          reader who wants it goes.

          The bars stay, without a heading over them. They answer the one question
          the rows cannot — how far in a pass is — and the heading was a line of
          chrome over a control that says what it is. */}
      {bars.length ? (
        <ul className="model-passes">
          {bars.map((bar) => (
            <li className={`model-pass ${bar.state}`} key={bar.model}>
              <p className="model-name">
                <span className="name">{bar.model}</span>
                <span className="count">
                  {bar.attempted} / {bar.of}
                </span>
              </p>
              {/* The element and not a div of a computed width: the browser draws the
                  share from the two counts, so no percentage is written down for the
                  figure scan in `pending.test.ts` to find. */}
              <progress value={bar.attempted} max={bar.of} />
              <p className="aside">{bar.reading}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
