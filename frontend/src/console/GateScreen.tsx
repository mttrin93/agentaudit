/**
 * The gate, from a browser: what this bench cites, and the control that runs one.
 *
 * ADR-0021 lets the console start a gate run, and this screen is the whole of what
 * that looks like. Since #14's split it is markup and nothing else: every piece of
 * state, every effect and every request lives in `useGateRun`, and the blocks are
 * components of their own — `GateStart`, `GateAttestation`, `GateEstimate`,
 * `GateProgress`, `GateDecision`. What is left here is the one thing that could not
 * move: the order the blocks appear in, and which of them a stage draws.
 *
 * **Three absences are three different sentences.** A bench that did not answer for
 * its gate, a bench that holds no record of one, and a screen that has not read yet
 * are distinguished on the page, because none of them is a gate that failed and an
 * operator acting on the wrong one acts wrongly.
 *
 * **The control is handed over at every stage** and `going` is what greys it out. It
 * used to be passed only while the stage was idle, which is why it vanished after a
 * run was decided.
 *
 * `railIcons.tsx` explains why a drawing on this screen is `aria-hidden` and why no
 * card loses a fact without it.
 */

import {
  TheAttestation,
} from './GateAttestation'
import {
  TheEstimate,
} from './GateEstimate'
import {
  TheGateRun,
  TheLastDecided,
} from './GateProgress'
import {
  Block,
} from './GateStart'
import {
  useGateRun,
} from './useGateRun'
import {
  GATE_RUN_STATEMENTS,
  gateDecline,
  gateInterruptView,
} from './gaterun'
import { useArrivalFocus, useScreenTitle } from './announce'
import { THE_GATE } from './rail'

export function GateScreen() {
  const {
    answer,
    askTheBench,
    attesting,
    begin,
    blocks,
    busy,
    confirm,
    confirmed,
    held,
    lastly,
    ourRunIsGoing,
    reading,
    refused,
    request,
    setAttesting,
    setConfirmed,
    setStage,
    setStep,
    stage,
    start,
    started,
    step,
  } = useGateRun()

  useScreenTitle(THE_GATE)
  const heading = useArrivalFocus(THE_GATE)
  return (
    <main className="screen">
      <header>
        <h1 ref={heading} tabIndex={-1}>
          {THE_GATE}
        </h1>
      </header>

      {/* Assertive (ADR-0080): the operator pressed the control that starts a gate
          run and nothing started. Everything else on this screen that reports a
          silence is polite, because the rest of it is read rather than pressed. */}
      {refused ? (
        <section className="refusal" role="alert">
          <h2>That was not taken</h2>
          <p>{refused}</p>
          <p className="aside">
            Nothing about this is a gate run that half happened: a refusal at this
            point means nothing was sent and not one case record was written to.
          </p>
        </section>
      ) : null}

      {/* Polite: read on arrival, answering nothing anybody pressed (ADR-0080). */}
      {held.unavailable ? (
        <section>
          <h2>This bench did not answer for its gate</h2>
          <div className="citation uncited" role="status">
            <h3>Neither the rule nor the citation could be read</h3>
            <p>{held.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that cites no gate run: what is unknown
              here is what it would have said, and nothing on this page should be
              read as either answer. The command below is unchanged either way — it
              is how a gate run is started at a terminal, not something this bench
              told us.
            </p>
          </div>
        </section>
      ) : held.bench === null ? (
        <section>
          <p className="aside">
            Reading the declared rule and this bench’s citation…
          </p>
        </section>
      ) : null}

      {stage === 'attesting' ? (
        <TheAttestation
          step={step}
          attesting={attesting}
          declare={(changed) => setAttesting({ ...attesting, ...changed })}
          back={() => {
            if (step === 0) {
              setStage('idle')
              return
            }
            setStep(step - 1)
          }}
          forward={() => {
            if (step + 1 < GATE_RUN_STATEMENTS.length) {
              setStep(step + 1)
              return
            }
            void start()
          }}
          missing={request.kind === 'blocked' ? request.missing : []}
          last={step + 1 === GATE_RUN_STATEMENTS.length}
          busy={busy}
        />
      ) : null}

      {stage === 'estimate' && started !== null ? (
        <TheEstimate
          view={gateInterruptView(started.estimate)}
          confirmed={confirmed}
          setConfirmed={setConfirmed}
          confirm={confirm}
          decline={() => void answer(gateDecline())}
          busy={busy}
        />
      ) : null}

      {/*
        The control, and then a run's own figures under it.

        The control is the errand and it stays at the top: it was under the whole
        decision once, six family cards and the exclusions deep, so a finished gate
        run looked like a screen that had lost its control.

        The last outcome is not drawn. `gateScreen` still builds it second — the
        control above the outcome is a property of that value and `gate.test.ts` reads
        the order off it — and what it says is a heading and four facts about a run
        whose figures are on this page already, under `TheLastDecided`: the same run,
        read off the record rather than off the citation. The citation is the thing a
        report cites, not the thing an operator opens this screen to do.
      */}
      {blocks
        .filter((block) => block.kind === 'start')
        .map((block) => (
          <Block
            block={block}
            begin={begin}
            going={ourRunIsGoing}
            ask={askTheBench}
            key={block.kind}
          />
        ))}

      {stage === 'watching' && reading !== null ? (
        <TheGateRun reading={reading} />
      ) : null}

      {stage === 'watching' ? null : lastly.unavailable ? (
        <section>
          {/* Polite, for the same reason as the block above (ADR-0080). */}
          <h2>The last gate run's figures could not be read</h2>
          <div className="citation uncited" role="status">
            <h3>This bench did not answer for what its last gate run measured</h3>
            <p>{lastly.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that holds no record of one: what is
              unknown here is what the figures were, and not whether there was a gate
              run to have them.
            </p>
          </div>
        </section>
      ) : lastly.none ? (
        <section>
          <h2>No figures for the last gate run</h2>
          <div className="citation uncited">
            <h3>No gate run record here</h3>
            <p>{lastly.none}</p>
            <p className="aside">
              Nothing on this page should be read as a gate that failed or a figure
              of zero. What is absent is a record of a gate run's arithmetic, which is
              not the same thing as a gate run that answered badly.
            </p>
          </div>
        </section>
      ) : lastly.decided === null ? null : (
        <TheLastDecided decided={lastly.decided} />
      )}
    </main>
  )
}
