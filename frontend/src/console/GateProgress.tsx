/**
 * A gate run in flight, and the same figures once it has stopped.
 *
 * Two blocks and nothing else since #14 split the cards they are drawn from into
 * `GateCards.tsx`: `TheGateRun` for a run this screen started and is watching,
 * `TheLastDecided` for the last one this bench decided. Both end in the same
 * `Decided` block, because they are the same decision from two carriers and a
 * difference between the two renderings would be a difference nobody meant.
 */
import type {
  GateRunReading,
} from '../api/bench'
import {
  Decided,
  SHOWN,
} from './GateDecision'
import type {
  DecidedRun,
} from './gaterun'
import {
  ANSWER_KEYS,
  answeringRows,
  decidedView,
  familyRows,
  gateProgress,
  payloads,
  progressKeys,
} from './gaterun'
import {
  FamilyAnswer,
  FamilyBar,
  Keys,
  Layer,
  Payload,
} from './GateCards'

/**
 * A gate run in flight, then what it decided under the rule.
 *
 * While it goes: one block per layer, in that layer's own units, and no figure that
 * spans them. When it is decided: the outcome, then each family's figures — in that
 * order because the sequence `decidedView` returns is in that order, less the rule
 * block this screen no longer prints.
 */
export function TheGateRun({ reading }: { reading: GateRunReading }) {
  // The same three blocks `TheLastDecided` drops, for the reasons it gives.
  const decided = decidedView(reading).filter((block) => SHOWN.has(block.kind))
  return (
    <>
      <section>
        <h2>Where it has got to</h2>
        {/*
          Without the served sentence.

          `reading.statement` is one paragraph of running prose — what was decided,
          who confirmed it, how many readings were appended, where the records are,
          which run this one displaces, the digest — above the figures an operator
          opened this screen to read. Every fact in it is a labelled field on a block
          below or on the report the run signs, and a reader who has to parse a
          paragraph to find a figure that is drawn under it is reading it twice. The
          sentence stays on the wire, where the record and the report both use it.
        */}
        <div className="layers">
          {gateProgress(reading).map((layer) => (
            <Layer layer={layer} key={layer.layer} />
          ))}
        </div>

        {/*
          Two readings of the same six families, side by side: how far each has got,
          and how each is answering.

          Two columns because they are two readings of the same six, in the same
          order: the left says *how much of the work is done* in one bar a family, the
          right says *how it is going* in one bar an agent. Both are drawn against the
          same denominators, so no length on the right can outrun the one for the same
          family on the left.
        */}
        <div className="watching">
          <div className="progress">
            <h3>How far each family has got</h3>
            <Keys keys={progressKeys(reading)} />
            {familyRows(reading).map((row) => (
              <FamilyBar row={row} key={row.family} />
            ))}
          </div>
          <div className="answering">
            <h3>How each family is answering</h3>
            <p className="legend">
              {ANSWER_KEYS.map((key) => (
                <span className="key" key={key.answer}>
                  <span className={`swatch ${key.accent}`} aria-hidden="true" />
                  {key.answer}
                </span>
              ))}
            </p>
            {answeringRows(reading).map((row) => (
              <FamilyAnswer row={row} key={row.family} />
            ))}
          </div>
        </div>

        {/* The call it is on, under both, at the width of the page: an exchange is a
            paragraph of somebody's traffic and it reads badly in half a column. */}
        <div className="payloads">
          <h3>The last call</h3>
          {payloads(reading).length === 0 ? (
            <p className="aside">
              Nothing has come back yet. The exchange appears here as it does.
            </p>
          ) : (
            payloads(reading).map((one) => <Payload one={one} key={one.key} />)
          )}
        </div>
      </section>

      {decided.map((block) => (
        <Decided block={block} key={block.kind} />
      ))}
    </>
  )
}

/**
 * What the last gate run this bench finished decided, read on arrival.
 *
 * The same figures the watch shows, from the same route, so this is not a second
 * reading of anything — it is that run's own decision, read once, so that closing
 * the tab does not lose what the gate measured.
 *
 * **Without the sentence saying where the figures came from.** It headed the
 * decision with a paragraph about the plumbing — read off the record, parsed out of
 * no document, recomputed nowhere — above the figures themselves. The blocks below
 * carry their own labels and their own decided date, and what the reading is read
 * off is the same route either way.
 *
 * **Without the declared-rule block.** This screen does not restate the declared
 * rule any more — a gate run's own copy would put seven clauses back above the
 * figures somebody opened this page to read. The rule a run was decided under is
 * printed whole on the report that run signs, beside those figures.
 *
 * **And without what it wrote back.** The library it appended to, how many readings,
 * which cases were retired and which got none is a record of a write, not a reading of
 * a gate: the run's own document holds it, `gaterun.test.ts` still reads the block, and
 * the case library is where somebody checks that the write happened.
 *
 * **And without the list of exclusions.** Not because an exclusion may go unsaid —
 * ADR-0015 asks it to name the family, the reason *and* the figure that caused it, and
 * that is exactly what an excluded family's own card says, dashed, in the row with the
 * other five. The list below repeated it a second time, away from the figures it is
 * about, which is the reading ADR-0015 wanted moved onto the card in the first place.
 */
export function TheLastDecided({ decided }: { decided: DecidedRun }) {
  const blocks = decidedView(decided).filter((block) => SHOWN.has(block.kind))
  return (
    <>
      {blocks.map((block) => (
        <Decided block={block} key={block.kind} />
      ))}
    </>
  )
}
