/**
 * The operator's screen: the way to run a gate, and what the last one measured.
 *
 * It answers one question — when was this instrument last validated, and how do I do
 * it again — and the control comes first, because starting one is the errand. The
 * blocks are `gate.ts`'s sequence and this file maps over it in order, so *the control
 * above the outcome* is a property of a value a test reads rather than of markup
 * nobody checks. The outcome block itself draws nothing: the citation's four facts are
 * about the same run whose figures are on this page already.
 *
 * **There is one control here and it is the one ADR-0021 authorised.** `PLAN.md` §8
 * put a gate run on the command line, this screen printed the command, and a
 * deployed bench had no terminal to run it in. So the start block carries a start
 * control where the bench says a gate run may begin — and a *stated refusal* where
 * it may not: no reference agents shipped, no case library it may write to, no
 * adjudicating instrument, or a gate run already holding the library. The bench
 * decides which; this screen reads the answer and never guesses it.
 *
 * **The consent flow is the register screen's, walked here.** The three attestation
 * statements one at a time, in the record's own wording, then the estimate as two
 * figures against two ceilings before anything is sent. Declining a statement sends
 * nothing at all; declining the estimate sends a `confirmed: false` that records the
 * gate run as declined by a person and leaves the case library byte for byte as it
 * was. There is no path through this file to a `confirmed: true` that
 * `gaterun.gateConfirmation` did not build.
 *
 * **The two writes this screen can make are a gate run's.** It imports
 * `startGateRun` and `answerTheGateRunsInterrupt` and nothing else that posts: it
 * cannot start a run, cannot answer a run's interrupt, and has no `fetch` of its
 * own. `gate.test.ts` reads this file and asserts exactly that, which is the
 * assertion the read-only version of this screen made in the other direction.
 *
 * **Per-family figures come from the gate run, never from a document.** While one is
 * in flight the screen shows progress per layer — family, case and attempt on one
 * side, family, episode and turn on the other — and when it is decided it shows the
 * rule above the outcome and then each family's three rates and its `D`, read off
 * the run that just happened.
 *
 * **And they survive the tab being closed, and a restart.** The last gate run this
 * bench finished is read on arrival from `GET /gate-runs/{id}`; where this process
 * ran none, the pointer on the citation is followed to `GET /bench/gate/record`,
 * which opens the record the gate run itself wrote. Same decision, same shape, and
 * the provenance sentence says which of the two a reader is looking at. What neither
 * reaches is a record this bench was not given — a terminal gate run writes it beside
 * its dated document — and that is a stated absence rather than an error: the
 * citation still says what the last gate run answered.
 *
 * **The idiom is the console's own.** One reading column, `.citation` and
 * `.citation.uncited`, `.figures` for the estimate, `.layers` for progress,
 * `.families.per-family` for the per-family cards, labelled uncoloured facts, and
 * the three reference agents in one hue's three ordered steps. No outcome is
 * coloured: a pass in green and a fail in red is the severity scale the report
 * exists to refuse, and the one plot on this screen draws a family's own three rates
 * on a fixed nought-to-one axis — every figure in it is printed beside it in words,
 * which is why the drawing is `aria-hidden` and why the card loses no fact without
 * it.
 */

import { useCallback, useEffect, useState } from 'react'

import {
  answerTheGateRunsInterrupt,
  benchGate,
  benchGateRecord,
  gateRunReading,
  gateRuns,
  startGateRun,
  type ApprovalBody,
  type BenchGate,
  type GateRunReading,
  type GateRunStart,
  type GateRunStarted,
} from '../api/bench'
import { readFamily } from '../families'
import type { LayerReading } from '../run/progress'
import {
  gateScreen,
  type StartBlock,
  type GateBlock,
} from './gate'
import {
  ALREADY_IN_FLIGHT,
  decidedView,
  gateConfirmation,
  gateDecline,
  gateInterruptView,
  gateProgress,
  gateRunRequest,
  familyRows,
  payloads,
  progressKeys,
  answeringRows,
  ANSWER_KEYS,
  GATE_RUN_STATEMENTS,
  nothingAttested,
  startControl,
  stillGoing,
  type Attesting,
  type DecidedBlock,
  type FamilyAnswers,
  type FamilyRow,
  type PayloadRow,
  type ProgressKey,
  type DecidedRun,
  type Fact,
  type FamilyReading,
  type GateInterruptView,
  type StartControl,
} from './gaterun'

/** How often a gate run in flight is asked where it has got to. */
const POLL_SECONDS = 2

/**
 * How many times *may another start yet* is re-asked after a gate run settles.
 *
 * The library's lease is released after the run is marked decided, and how long after
 * is not this screen's to know: the write-back to eighteen case records, the
 * retirement decisions and the citation all land in that gap. Thirty asks two seconds
 * apart is a minute of patience, where five was ten seconds and ran out on a real
 * gate run — which left a refusal on the page that had stopped being true.
 *
 * Bounded, and the bound is not a failure: past a minute the refusal is somebody
 * else's terminal run holding the library, which is a true answer and belongs on the
 * screen. The control beside it re-asks, so no wait is ever the last word.
 */
const LEASE_ASKS = 30

/** What this screen is holding: the rule, the citation, and whether one may start. */
interface Held {
  bench: BenchGate | null
  start: GateRunStart | null
  unavailable: string
}

const NOTHING_YET: Held = { bench: null, start: null, unavailable: '' }

/**
 * The figures of the last gate run, from whichever carrier this bench still holds.
 *
 * Three empty fields and not one, because *this bench holds no record of it*, *the
 * bench did not answer* and *nothing has been read yet* are three different facts
 * and none of them is a gate that failed. A single field would report the first as
 * the second, which is a bench that looks broken to an operator whose bench is
 * merely mounted without a file.
 */
interface Lastly {
  decided: DecidedRun | null
  /** Why there are none, where there are none. */
  none: string
  unavailable: string
}

const NOT_READ_YET: Lastly = {
  decided: null,
  none: '',
  unavailable: '',
}

/**
 * Where the operator is in starting one.
 *
 * Four stages, and the first is the screen at rest. A union rather than three
 * booleans because they are exclusive: an operator cannot be reading the statements
 * and confirming the figures at once, and a screen that allowed both would have two
 * answers to *what am I consenting to*.
 */
type Stage = 'idle' | 'attesting' | 'estimate' | 'watching'

export function GateScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)
  const [stage, setStage] = useState<Stage>('idle')
  const [attesting, setAttesting] = useState<Attesting>(nothingAttested)
  const [step, setStep] = useState(0)
  const [started, setStarted] = useState<GateRunStarted | null>(null)
  const [reading, setReading] = useState<GateRunReading | null>(null)
  const [lastly, setLastly] = useState<Lastly>(NOT_READ_YET)
  const [confirmed, setConfirmed] = useState(false)
  const [refused, setRefused] = useState('')
  const [busy, setBusy] = useState(false)

  /**
   * The rule, the citation, and whether a gate run may start — asked, never inferred.
   *
   * All three are answers only the bench can give, and this screen never works one
   * out for itself: *whether another gate run may start now* depends on a lease on
   * the library that this browser cannot see, and the citation depends on what the
   * last one decided. So they are read, and they are read **again at the one moment
   * they can all have changed** — when a gate run this screen was watching stops.
   * Before this, the control was read once on arrival and never again, which is a
   * gate run that finishes and leaves the screen looking like a bench that still
   * holds its own library until somebody reloads.
   *
   * Asked again rather than assumed: a settled gate run is not proof that the next
   * one may start. The library may have been taken by a terminal run in the
   * meantime, and `POST /gate-runs` would refuse a control this screen had drawn on
   * its own authority.
   */
  const readTheBench = useCallback(async () => {
    try {
      const [bench, runs] = await Promise.all([benchGate(), gateRuns()])
      return { bench, start: runs.start, unavailable: '' }
    } catch (unknown: unknown) {
      return { bench: null, start: null, unavailable: `${unknown}` }
    }
  }, [])

  useEffect(() => {
    let current = true
    const read = async () => {
      const answered = await readTheBench()
      if (current) {
        setHeld(answered)
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [readTheBench])

  /**
   * The last gate run this bench decided, read on arrival so its figures survive a
   * reload.
   *
   * Its own state and its own effect, deliberately not folded into the one above: a
   * bench that answered for its rule and its citation and not for this has said
   * most of what this screen is for, and one failure state across the two would take
   * the rule down with the figures. The rows arrive most recent first, so the first
   * settled one is the last gate run this bench finished.
   *
   * **Two carriers, in that order.** `GET /gate-runs` lists what this process ran,
   * and its figures are the freshest thing there is. Where it ran nothing, the
   * pointer on the citation is followed instead — `GET /bench/gate/record` opens the
   * record the gate run itself wrote, which is how figures survive a restart. Both
   * are the same decision in the same shape; only the provenance sentence differs,
   * and it is shown.
   *
   * **What neither reaches is a record this bench was not given.** A gate run at a
   * terminal writes its record beside its dated document, in the directory that run
   * was handed, and a bench mounted with the library alone never sees it. That is a
   * stated absence here and not an error: the citation above still says what the last
   * gate run answered.
   */
  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const runs = await gateRuns()
        const settled = runs.gate_runs.find((row) => !stillGoing(row.status))
        if (settled !== undefined) {
          const decided = await gateRunReading(settled.gate_run_id)
          if (decided.decision !== null) {
            if (current) {
              setLastly({ decided, none: '', unavailable: '' })
            }
            return
          }
        }
        // Nothing this process ran, so follow the pointer on the citation instead.
        const cited = await benchGateRecord()
        if (!current) {
          return
        }
        setLastly(
          cited.held
            ? {
                // `written: null` because a record does not carry one: what a gate
                // run wrote back to the library is reported by the process that
                // wrote it, and this is the decision as the run filed it.
                decided: {
                  rule: cited.run.rule,
                  decision: cited.run.decision,
                  written: null,
                },
                none: '',
                unavailable: '',
              }
            : { decided: null, none: cited.stated, unavailable: '' },
        )
      } catch (unknown: unknown) {
        if (current) {
          setLastly({ decided: null, none: '', unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  const gateRunId = started?.gate_run_id ?? ''

  useEffect(() => {
    if (stage !== 'watching' || !gateRunId) {
      return
    }
    let current = true
    let timer: ReturnType<typeof setInterval> | undefined
    const tick = async () => {
      try {
        const now = await gateRunReading(gateRunId)
        if (!current) {
          return
        }
        setReading(now)
        if (stillGoing(now.status)) {
          return
        }
        // Stopped for good, so stop asking *this* route: a decided gate run has
        // nothing left to say about itself.
        if (timer !== undefined) {
          clearInterval(timer)
        }
        /*
         * And ask the bench the two questions whose answers this run just changed:
         * the citation it now carries (ADR-0023 — a gate run started here becomes the
         * one this bench cites, without a restart) and whether another may start,
         * which is true again now that the library has been given back. Without this
         * the control stays gone and the outcome stays stale until a reload.
         */
        /*
         * Asked more than once, because the lease outlives the status by a moment.
         * `why_not` refuses while `held_by(library)` is true, and the library is
         * given back just after the run is marked decided — so a single read here
         * lands on `already_in_flight` and leaves the screen showing a refusal that
         * stopped being true a second later. Only that one refusal is waited out:
         * the other three are facts about how this bench was built, and waiting does
         * not answer them.
         */
        for (let asked = 0; asked < LEASE_ASKS; asked += 1) {
          const answered = await readTheBench()
          if (!current) {
            return
          }
          setHeld(answered)
          const start = answered.start
          if (start === null || start.available || start.refusal !== ALREADY_IN_FLIGHT) {
            return
          }
          await new Promise((wait) => setTimeout(wait, POLL_SECONDS * 1000))
        }
      } catch (unknown: unknown) {
        if (current) {
          setRefused(`${unknown}`)
        }
      }
    }
    timer = setInterval(() => void tick(), POLL_SECONDS * 1000)
    void tick()
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [gateRunId, stage, readTheBench])

  const control: StartControl | null =
    held.start === null ? null : startControl(held.start)

  /*
   * Whether this screen has a gate run of its own under way.
   *
   * Read off the reading rather than off the stage alone, so the control comes back
   * the moment the run is decided while the progress and the decision stay on the
   * page: the stage remains `watching` because that is what the operator is looking
   * at, and it is the *run* that has stopped, not the screen.
   *
   * This is not the screen deciding whether another may start — that answer is the
   * bench's, and it is `held.start`. This only greys out the one control while a run
   * this screen started is going, which is a fact the screen owns.
   */
  const ourRunIsGoing =
    stage !== 'idle' && (reading === null || stillGoing(reading.status))

  /** Read the bench again, on request. A read: nothing here starts anything. */
  const askTheBench = () => {
    void readTheBench().then(setHeld)
  }

  const begin = () => {
    setRefused('')
    setStep(0)
    setAttesting(nothingAttested())
    setStage('attesting')
  }

  const request = gateRunRequest(attesting)

  const start = async () => {
    // Asked again here rather than trusted from the disabled state: this is the one
    // line in this screen that can begin 830 calls and a write-back, and the guard
    // that decides it is the one that will not build a body from an incomplete
    // declaration.
    if (request.kind !== 'ready') {
      return
    }
    setBusy(true)
    const outcome = await startGateRun(request.body)
    setBusy(false)
    if (outcome.kind === 'started') {
      setStarted(outcome.gateRun)
      setConfirmed(false)
      setStage('estimate')
      return
    }
    setRefused(outcome.statement)
    setStage('idle')
  }

  const answer = async (body: ApprovalBody) => {
    setBusy(true)
    const outcome = await answerTheGateRunsInterrupt(gateRunId, body)
    setBusy(false)
    if (outcome.kind === 'answered') {
      setStarted(outcome.gateRun)
      setRefused('')
      setStage('watching')
      return
    }
    setRefused(outcome.statement)
  }

  const confirm = () => {
    const confirmation = gateConfirmation(
      started?.status ?? '',
      confirmed,
      attesting.identity,
    )
    if (confirmation.kind !== 'ready') {
      return
    }
    void answer(confirmation.body)
  }

  /*
   * The control is handed over at every stage, and `going` is what greys it out.
   *
   * It used to be passed only while the stage was `idle`, which is why it vanished:
   * the stage stays `watching` after a run is decided — that is what keeps the
   * progress and the decision on the page — so the command block was handed `null`
   * and drew nothing at all. Not a disabled button, not a refusal, not the control
   * that re-asks: nothing. A screen whose one control is absent is indistinguishable
   * from a bench that cannot run a gate, which is the one thing this block exists to
   * tell apart.
   */
  const blocks =
    held.bench === null ? [] : gateScreen(held.bench, control)

  return (
    <main className="screen">
      <header>
        <h1>The gate</h1>
      </header>

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

      {held.unavailable ? (
        <section>
          <h2>This bench did not answer for its gate</h2>
          <div className="citation uncited" role="alert">
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
          decline={() => void answer(gateDecline(attesting.identity))}
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
          <h2>The last gate run's figures could not be read</h2>
          <div className="citation uncited" role="alert">
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

/** One block, in the order the reading gave it. Two kinds, two shapes. */
function Block({
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
function TheStart({
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

/**
 * The three statements, one at a time, in the record's own wording.
 *
 * One at a time and not three checkboxes in a column: each is recorded separately
 * and two of the three are consequences nobody would infer, so a screen that showed
 * them together would be a screen where they are read as one (ADR-0007). The walk's
 * footer is the register screen's, because it is the same walk.
 *
 * The note under the checkbox — all three required, each recorded separately,
 * nothing sent yet — is gone. That all three are required is enforced by the guard
 * that will not build a body from an incomplete declaration and by the bench that
 * refuses an incomplete one; that nothing has been sent is what *Continue* and *See
 * what it will cost* say by being the only way forward. The register screen keeps
 * its own note, which says a different thing: what the artefact is (ADR-0007).
 */
function TheAttestation({
  step,
  attesting,
  declare,
  back,
  forward,
  missing,
  last,
  busy,
}: {
  step: number
  attesting: Attesting
  declare: (changed: Partial<Attesting>) => void
  back: () => void
  forward: () => void
  missing: string[]
  last: boolean
  busy: boolean
}) {
  const statement = GATE_RUN_STATEMENTS[step]
  const made = attesting.attested[statement.field]
  return (
    <section>
      <h2>
        Statement {statement.step} of {statement.of}
      </h2>
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
          <label>
            Who is attesting
            <input
              value={attesting.identity}
              onChange={(event) => declare({ identity: event.target.value })}
              placeholder="recorded against every one of the three statements"
            />
          </label>
          <label>
            What one call costs you, on your own provider
            <input
              value={attesting.price_per_call}
              onChange={(event) => declare({ price_per_call: event.target.value })}
              placeholder="leave empty for a gate run you have not priced"
            />
          </label>
        </>
      ) : null}

      {last && missing.length ? (
        <ul className="blocked">
          {missing.map((one) => (
            <li key={one}>{one}</li>
          ))}
        </ul>
      ) : null}

      <footer className="walk">
        <button type="button" onClick={back} disabled={busy}>
          {step === 0 ? 'Not now' : 'Back'}
        </button>
        <button
          type="button"
          className="primary"
          onClick={forward}
          disabled={busy || !made || (last && missing.length > 0)}
        >
          {last
            ? busy
              ? 'Starting…'
              : 'See what it will cost'
            : 'Continue'}
        </button>
      </footer>
    </section>
  )
}

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
function TheEstimate({
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

/**
 * A gate run in flight, then what it decided under the rule.
 *
 * While it goes: one block per layer, in that layer's own units, and no figure that
 * spans them. When it is decided: the outcome, then each family's figures — in that
 * order because the sequence `decidedView` returns is in that order, less the rule
 * block this screen no longer prints.
 */
function TheGateRun({ reading }: { reading: GateRunReading }) {
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
function TheLastDecided({ decided }: { decided: DecidedRun }) {
  const blocks = decidedView(decided).filter((block) => SHOWN.has(block.kind))
  return (
    <>
      {blocks.map((block) => (
        <Decided block={block} key={block.kind} />
      ))}
    </>
  )
}

/**
 * One family's progress: its name, its two counts, and one bar in three segments.
 *
 * The bar is the family's, and the three segments are which agent did which part of
 * it. They take the three agent accents, whose documented job is identity and order —
 * hardened, weak, trivial, cool to warm, by construction and never by result — which
 * is why a bar of them says *how far* and cannot be read as *how well*. There is no
 * percentage anywhere on the row: the share is the width and never a figure.
 */
function FamilyBar({ row }: { row: FamilyRow }) {
  return (
    <div className="family-bar">
      <p className="family-name">
        <span className="name">{readFamily(row.family)}</span>
        <span className="count">
          {row.attempted} / {row.of}
        </span>
      </p>
      <div className="track">
        {row.segments.map((segment) => (
          <span
            className={`segment ${segment.accent}`}
            style={{ width: segment.width }}
            key={segment.agent}
          />
        ))}
      </div>
    </div>
  )
}

/**
 * Which colour is which agent, once above the six bars.
 *
 * **The mark is the thing it labels.** A length of track and not a dot, for the reason
 * the stylesheet gives beside `.dot`: a legend whose mark is not the mark on the
 * drawing has to be decoded instead of read.
 *
 * **And every mark carries its agent's name.** Three colours in an order with nothing
 * beside them are read as three grades, which is the severity scale ADR-0005 exists to
 * refuse. The word beside each mark is what says which agent it is; the hue only says
 * which of three, and nothing here is carried by hue alone.
 */
function Keys({ keys }: { keys: readonly ProgressKey[] }) {
  if (keys.length === 0) {
    return null
  }
  return (
    <p className="legend">
      {keys.map((key) => (
        <span className="key" key={key.agent}>
          <span className={`swatch ${key.accent}`} aria-hidden="true" />
          {key.agent}
        </span>
      ))}
    </p>
  )
}

/**
 * One family, and how it is answering: one bar, green then red, over its denominator.
 *
 * The same row as the bar beside it, answering the other question — so the two counts
 * are the family's and the length of each is taken against the same 90 the left bar
 * fills. What is left of the bar is what has not been attempted yet, which is what
 * keeps a length here from reading as a finished figure.
 *
 * **The one place this app colours a verdict**, which is why the two colours are named
 * in words above the six. And it is a live reading of a run, not a measurement: a third
 * of a family's attempts are against an agent built to fail, so the red has a floor
 * that is nothing to do with a target. The rate that *is* a measurement is per family
 * per agent with its interval and its band beside it, on the report the run signs
 * (ADR-0005).
 */
function FamilyAnswer({ row }: { row: FamilyAnswers }) {
  return (
    <div className="family-bar">
      {/* The name and no figure beside it. The slot to its right holds `17 / 90` on
          the bar to the left — what has been attempted, out of what will be — and a
          second pair of numbers in the same place, meaning something else, is a
          fraction a reader would read as that one. */}
      <p className="family-name">
        <span className="name">{readFamily(row.family)}</span>
      </p>
      <div className="track">
        <span className="segment resisted" style={{ width: row.held }} />
        <span className="segment succeeded" style={{ width: row.broke }} />
      </div>
    </div>
  )
}

/**
 * One attempt: what the bench sent, and what the agent answered.
 *
 * The two halves are set apart the way an exchange reads — the attack, then the
 * reply — and the verdict is a line of words under them. Nothing here is coloured by
 * its verdict: *succeeded* and *resisted* are the two answers this bench counts, and
 * a green one beside a red one is the severity scale ADR-0005 exists to refuse.
 */
function Payload({ one }: { one: PayloadRow }) {
  return (
    <div className="payload">
      <div className="turn sent">
        <Speaker />
        <p className="bubble">{one.sent}</p>
      </div>
      <div className="turn reply">
        <p className="bubble">{one.reply}</p>
        <Speaker />
      </div>
    </div>
  )
}

/**
 * One speaker's mark: the same drawing on both turns, in that turn's own colour.
 *
 * The same glyph deliberately. Both ends of this exchange are agents — the bench's
 * attacker and the target answering it — and drawing them as two different creatures
 * would say something about the pair that is not true. What differs is which side of
 * the card the turn sits on, which is the order the two happened in: the attack, then
 * the answer to it. The colour is redundant with that side, and the line under both
 * names the agent that was being attacked.
 *
 * Hand-drawn at 16px in `currentColor`, the rail's own idiom, so the colour comes off
 * the stylesheet and no fourth dependency arrives to draw one glyph. Decorative:
 * `aria-hidden`, because the speaker is named in words on the line beside it.
 */
function Speaker() {
  return (
    <svg
      className="speaker"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="8" cy="1.9" r="0.85" />
      <path d="M8 2.75V4.6" />
      <rect x="3" y="4.6" width="10" height="8.4" rx="2.2" />
      <path d="M1.4 8.2v2.2M14.6 8.2v2.2" />
      <path d="M6.3 8.1v1.3M9.7 8.1v1.3" />
      <path d="M6.5 11.3h3" />
    </svg>
  )
}

/** One layer's reading, in that layer's own units. */
function Layer({ layer }: { layer: LayerReading }) {
  return (
    <div className={`layer ${layer.layer}`}>
      <h3>{layer.title}</h3>
      {layer.at === null ? (
        <p>{layer.statement}</p>
      ) : (
        <dl className="at">
          {layer.units.map((unit, position) => (
            <div key={unit}>
              <dt>{unit}</dt>
              <dd>{layer.at?.[position]}</dd>
            </div>
          ))}
        </dl>
      )}
      <p>
        <span className="calls">{layer.callsSpent}</span> calls spent
      </p>
    </div>
  )
}

/**
 * Which of a decision's blocks this screen draws, and it is not all of them.
 *
 * One set for both readings of a decision — the run being watched and the last one on
 * the record — because they are the same decision drawn twice and a block dropped from
 * one and kept in the other would be a difference nobody meant. Every block is still
 * built and still tested; three of them are read somewhere else, and each one's reason
 * is on `TheLastDecided`.
 */
const SHOWN: ReadonlySet<DecidedBlock['kind']> = new Set(['decision', 'families'])

/** One block of the decision, in the order `decidedView` gave it. */
function Decided({ block }: { block: DecidedBlock }) {
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
function Facts({ facts }: { facts: Fact[] }) {
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
function FamilyFigure({ family }: { family: FamilyReading }) {
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
