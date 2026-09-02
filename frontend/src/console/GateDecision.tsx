/**
 * The decision block: the gate's answer, the facts under it, and one card per
 * family.
 *
 * Moved out of `GateScreen.tsx` by #14's split, unchanged. It is a module of its own
 * because it is the one part of this screen drawn from a *decided* gate run and from
 * nothing else — `TheGateRun` draws it under a run this screen is watching, and
 * `TheLastDecided` draws the same thing under a run this bench merely remembers.
 * One block, two carriers, and neither of them is allowed a different rendering of
 * the same decision.
 *
 * **`SHOWN` is what may be drawn and the omission is deliberate.** `gaterun.ts`
 * builds more blocks than this screen prints; a block reaching here that is not in
 * that set is not drawn rather than drawn badly.
 */

import {
  readFamily,
} from '../families'
import type {
  DecidedBlock,
  Fact,
  FamilyReading,
} from './gaterun'

/**
 * Which of a decision's blocks this screen draws, and it is not all of them.
 *
 * One set for both readings of a decision — the run being watched and the last one on
 * the record — because they are the same decision drawn twice and a block dropped from
 * one and kept in the other would be a difference nobody meant. Every block is still
 * built and still tested; three of them are read somewhere else, and each one's reason
 * is on `TheLastDecided`.
 */
export const SHOWN: ReadonlySet<DecidedBlock['kind']> = new Set(['decision', 'families'])

/** One block of the decision, in the order `decidedView` gave it. */
export function Decided({ block }: { block: DecidedBlock }) {
  switch (block.kind) {
    case 'rule':
      return (
        <section>
          <h2>{block.heading}</h2>
          <p>{block.statement}</p>
          <ul className="clauses">
            {block.clauses.map((clause) => (
              <li className={clause.under ? 'under' : undefined} key={clause.line}>
                {clause.line}
              </li>
            ))}
          </ul>
        </section>
      )
    case 'decision':
      return (
        <section>
          <h2>{block.heading}</h2>
          <div className="citation">
            {/*
              The outcome and its figures, and no sentence about the plumbing.

              `block.statement` is the record's own line saying every figure here was
              read off the attempts the run made and parsed out of no document. True,
              and it is a claim about how this response is built rather than about what
              was decided — which is what the box is for. It stays on the wire, where an
              auditor reading the gate run reads it, and the route's tests are what hold
              it true.
            */}
            <h3>{block.outcome}</h3>
            <Facts facts={block.facts} />
          </div>
        </section>
      )
    case 'families':
      return (
        <section>
          {/*
            Without the standing sentence. *Six families, six lines, and nothing that
            adds two of them* said what the layout already is: six cards with no
            seventh figure anywhere and nowhere to put one. It is still on the block,
            where `gaterun.test.ts` reads it beside the assertion that no sum or mean
            of the six appears in the view.
          */}
          <h2>{block.heading}</h2>
          <div className="families per-family">
            {block.families.map((family) => (
              <FamilyFigure family={family} key={family.family} />
            ))}
          </div>
        </section>
      )
    case 'excluded':
      return (
        <section>
          <h2>{block.heading}</h2>
          <Facts facts={block.excluded} />
        </section>
      )
    case 'written':
      return (
        <section>
          <h2>{block.heading}</h2>
          <p className="consequence">{block.statement}</p>
          <Facts facts={block.facts} />
        </section>
      )
  }
}

/** Labelled facts, uncoloured, in the console's own idiom. */
export function Facts({ facts }: { facts: Fact[] }) {
  return (
    <dl className="at">
      {facts.map((fact) => (
        <div key={fact.label}>
          <dt>{fact.label}</dt>
          <dd>{fact.value}</dd>
        </div>
      ))}
    </dl>
  )
}

/**
 * One family's three rates on their own line, its `D`, and what that line reads.
 *
 * The agents take the one hue's three ordered steps, which is identity and order and
 * never rank; the `D`, the span and the verdict are words and numbers with no colour
 * on them. **Nothing here adds two families**, and the axis is 0 to 1 rather than
 * fitted to these three rates, so no dot's position means anything about another
 * card.
 *
 * The plot is decoration only in the sense that removing it removes no fact: every
 * figure it draws is printed beside it in words, the counts each rate came from are
 * on the same line, and the whole card still reads with the plot unseen. A screen
 * reader gets the rates, the `D` and the line's verdict and skips the drawing, which
 * is why the drawing carries `aria-hidden`.
 */
export function FamilyFigure({ family }: { family: FamilyReading }) {
  return (
    <div className={family.set_aside ? 'family set-aside' : 'family'}>
      <h3>{readFamily(family.family)}</h3>
      <div className="rate-line">
        <ul className="rates">
          {family.rates.map((rate) => (
            <li key={rate.agent}>
              <span className="who">{rate.agent}</span>{' '}
              <span className="rate">{rate.rate}</span>
            </li>
          ))}
        </ul>
        <p className="score">
          <span className="kind">D</span> <span className="calls">{family.score}</span>
        </p>
      </div>

      <div className="plot" aria-hidden="true">
        <span
          className="span"
          style={{ left: family.from, width: family.width }}
        />
        {family.rates.map((rate) => (
          <span
            className={`dot ${rate.accent}`}
            key={rate.agent}
            style={{ left: rate.at }}
          />
        ))}
      </div>

      {/*
        Which dot is which, and no figure beside them. `span = D 0.30` was the third
        printing of `D` on one card — the number above, the bar under it, and then the
        pair in words — and the one a reader had to parse to find out it said nothing
        the other two had not.
      */}
      <p className="legend">
        <span>
          {family.rates.map((rate) => (
            <span className="key" key={rate.agent}>
              <span className={`dot ${rate.accent}`} aria-hidden="true" />
              {rate.agent}
            </span>
          ))}
        </span>
      </p>
      <p className="kind">{family.reads}</p>
    </div>
  )
}
