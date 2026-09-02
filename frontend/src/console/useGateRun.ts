/**
 * The gate screen's state, so that the screen itself is markup.
 *
 * ADR-0021 lets the console start a gate run, and everything the browser has to hold
 * to do that is here: what this bench cites, whether another gate run may start, the
 * run this screen started, and where it has got to. #14 lifted it out of
 * `GateScreen.tsx`, which now draws it and decides nothing.
 *
 * **Three absences are three different sentences**, and keeping them apart is the
 * reason this holds three pieces of state rather than one. A bench that did not
 * answer for its gate, a bench that holds no record of one, and a screen that has not
 * read yet are three facts, and none of them is a gate that failed — a single failure
 * field would report the first as the second and put a broken bench on the page.
 *
 * **`held.start` is the bench's answer and never this hook's.** Whether another gate
 * run may start depends on a lease on the library that no browser can see, so it is
 * asked — and asked again at the one moment it can have changed, when a run this
 * hook was watching stops. `ourRunIsGoing` is the separate, smaller fact this hook
 * does own: that a run *it* started is still going.
 */

import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import type {
  ApprovalBody,
  BenchGate,
  GateRunReading,
  GateRunStart,
  GateRunStarted,
} from '../api/bench'
import {
  answerTheGateRunsInterrupt,
  benchGate,
  benchGateRecord,
  gateRunReading,
  gateRuns,
  startGateRun,
} from '../api/bench'
import {
  gateScreen,
} from './gate'
import type {
  Attesting,
  DecidedRun,
  StartControl,
} from './gaterun'
import {
  ALREADY_IN_FLIGHT,
  gateConfirmation,
  gateRunRequest,
  nothingAttested,
  startControl,
  stillGoing,
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

/**
 * The gate screen's state: three reads, one gate run, and the halt in front of it.
 *
 * Ten `useState`, three `useEffect` and the six functions between them, lifted out of
 * `GateScreen` by #14's split so that the screen is markup and this is behaviour. The
 * seam already existed in this directory — `gaterun.ts` holds the pure logic with
 * `gaterun.test.ts` beside it — and this is the piece that could not go there, because
 * it is the part that talks to the bench and remembers what it said.
 *
 * **The three reads are three effects on purpose.** A bench that answered for its rule
 * and its citation and not for its last gate run has said most of what the screen is
 * for, and one failure state across the two would take the rule down with the figures.
 * Each read has its own state and its own stated absence, and none of the absences is
 * a gate that failed.
 *
 * **What comes back is the screen's whole state, setters included.** The boundary is
 * state against markup, not a narrowing: every declaration below moved verbatim, and a
 * hook that had folded the screen's inline handlers into verbs of its own would have
 * been a rewrite rather than a move. That folding is the obvious next change and it is
 * deliberately not this one.
 *
 * **Nothing here can start a gate run on a guess.** `start` re-asks `gateRunRequest`
 * rather than trusting the disabled state — it is the one line in this screen that can
 * begin 830 calls and a write-back — and `answer` is the only other write.
 */
export function useGateRun() {
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
   *
   * **Kept under the React Compiler: the poll below.** Two `useEffect` dependency
   * arrays name this, one of them the `POLL_SECONDS` loop, so an unmemoised reader
   * has this screen polling a bench that holds a library lease several times a
   * second. Compiled, the compiler hoists this clear out of the component — it
   * closes over nothing — which is stabler than `useCallback` and not less; skipped,
   * it does neither. See `vite.config.ts` for why that asymmetry decides it.
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

  return {
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
  }
}
