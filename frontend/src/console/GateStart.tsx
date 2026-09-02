/**
 * The one control on this screen, and the block it sits in.
 *
 * Moved out of `GateScreen.tsx` by #14's split, unchanged. `Block` draws whichever
 * block the reading gave it and `TheStart` is the command block itself — the
 * terminal command, the control that starts a gate run from here (ADR-0021), and the
 * refusal where there is one.
 *
 * **A refusal is drawn, never a missing control.** A screen whose one control is
 * absent is indistinguishable from a bench that cannot run a gate, which is the one
 * thing this block exists to tell apart.
 */

import type {
  GateBlock,
  StartBlock,
} from './gate'
import {
  ALREADY_IN_FLIGHT,
} from './gaterun'

/** One block, in the order the reading gave it. Two kinds, two shapes. */
export function Block({
  block,
  begin,
  going,
  ask,
}: {
  block: GateBlock
  begin: () => void
  going: boolean
  ask: () => void
}) {
  switch (block.kind) {
    case 'outcome':
      // Built by the reading, drawn by nothing: see the note in `GateScreen` on why
      // the last outcome is not on the page. A block with no markup rather than a
      // block filtered out of the list, so `GateBlock` stays exhaustive here and a
      // seventh kind cannot arrive unhandled.
      return null
    case 'start':
      return <TheStart block={block} begin={begin} going={going} ask={ask} />
  }
}

/**
 * The one control that starts a gate run, or the sentence saying why there is none.
 *
 * Where the bench says a gate run may not start here, what stands in the control's
 * place is the reason rather than a disabled button with nothing said about it — and
 * where it may, the button is drawn and greyed while a run this screen started is
 * going. The terminal command this block used to print beside it is in the README
 * and in `scripts/gate.py --help`.
 */
export function TheStart({
  block,
  begin,
  going,
  ask,
}: {
  block: StartBlock
  begin: () => void
  going: boolean
  ask: () => void
}) {
  const start = block.start
  return (
    <section>
      <h2>{block.heading}</h2>

      {start === null ? null : start.available ? (
        <div className="citation">
          {/*
            No heading over the control: the section above it is already named, and
            the button carries the same words the heading did — *Start a gate run*
            twice, four lines apart, read as two things to press.
          */}
          <p>{start.statement}</p>
          <button
            type="button"
            className="primary"
            disabled={going}
            onClick={begin}
          >
            {start.label}
          </button>
          {going ? (
            <p className="aside">
              A gate run started here is going. It holds an exclusive lease on the
              case library while it runs, so this control comes back when that one is
              decided.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="citation uncited">
          <h3>{start.heading}</h3>
          <p>{start.statement}</p>
          <p className="aside">
            The bench’s own name for this: <code>{start.refusal}</code>.
          </p>
          {start.refusal === ALREADY_IN_FLIGHT ? (
            <>
              {/*
                Only this refusal gets a control, and only because only this one is
                answered by waiting. A gate run gives the library back a moment after
                it is decided, and *a moment* is not a number this screen may assume —
                so it re-asks on its own for a minute and then hands the asking over.
                The other three refusals are facts about how this bench was built, and
                a button that re-asked them would be a button that changes nothing.
              */}
              <button type="button" onClick={ask}>
                Ask the bench again
              </button>
              <p className="aside">
                Nothing is started by asking. The lease is released a moment after a
                gate run is decided, and this reads whether it has been.
              </p>
            </>
          ) : null}
        </div>
      )}

    </section>
  )
}
