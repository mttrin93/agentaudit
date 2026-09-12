/**
 * The run screen: an interrupt that blocks, and then progress read per layer.
 *
 * Two things live here because they are two halves of one moment. Until somebody
 * answers, this screen *is* the halt — the graph is paused at a real `interrupt()`
 * against a checkpointer and the run cannot proceed, so the screen has nothing to
 * show but the two figures and the two answers to them. After a yes it is the
 * window on a run that takes minutes, polling `GET /runs/{id}` and reporting the
 * scored layer and the adaptive layer separately.
 *
 * **The screen holding rather than merely asking is the whole content of the
 * control** (spec, §31). So the confirmation is not a checkbox at the foot of a
 * form somebody scrolls past: it is the only screen there is while a run is
 * waiting, and the button that sends the run to the target is unreachable until
 * `confirmationRequest` says every part of the confirmation was given. That
 * function is the one path to a `confirmed: true`, and the button re-asks it on the
 * click as well as for the disabled state — a disabled button is a hint, and this
 * is not a place for hints.
 *
 * **Declining is always the easier answer.** It needs no second click and it is sent
 * rather than withheld: the bench records the run as *declined* by a person, which is
 * a better record than the *unanswered* a closed tab leaves behind, and answers with
 * its own sentence saying that nothing was sent to the target and nothing was spent.
 * Neither answer asks for anything typed any more — this screen has no fields on it,
 * and the name both answers are recorded under is the one that attested the
 * registration, carried from it in `sessionStorage`.
 *
 * **Nothing on this screen adds the layers up.** The figures come from
 * `interrupt.ts` and the readings from `progress.ts`, and neither builds a value
 * that spans the two; the two panels below are side by side and carry two spends,
 * two positions in two sets of units, and no third number. A blended figure would
 * hide which half of the run is spending the operator's budget (ADR-0007), and an
 * adaptive quantity that reached a scored one would be the invariant ADR-0010 is
 * about.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  REGISTRATION_REFUSED,
  answerTheInterrupt,
  runProgress,
  stopTheRun,
  type ApprovalBody,
  type RunEstimate,
  type RunProgress,
} from '../api/bench'
import {
  FIGURES_NOT_HELD,
  confirmationRequest,
  declineRequest,
  interruptView,
  whoAttested,
  theFiguresPresented,
  type ConfirmationRequest,
} from './interrupt'
import {
  adaptiveReading,
  electiveRows,
  familyRows,
  inThePlan,
  payloads,
  scoredReading,
  scoredShare,
  standing,
  stillGoing,
  turns,
  type FamilyRow,
  type LayerReading,
  type PayloadRow,
  type Standing,
  type TurnRow,
} from './progress'
// The adaptive layer's probes, off the route that holds them: a second record, read
// beside the progress and never folded into it (ADR-0010).
import { runEpisodes, type RunEpisodes } from '../api/attempts'
// The two verdict colours and the two words beside them, from the one place they are
// declared. A second copy here would be a second answer to *which green is resisted*,
// and the two would only have to disagree once.
import { ANSWER_KEYS } from '../console/gaterun'
import { useArrivalFocus, useScreenTitle } from '../console/announce'
import { THE_RUN } from '../console/rail'
// Whether this screen is still being told anything, which is a rule and not a line:
// the span, the words and what the retry does are ADR-0078's.
import {
  ASK_AGAIN,
  NOT_ANSWERING,
  NOT_ANSWERING_BRIEFLY,
  POLL_SECONDS,
  announcement,
  liveness,
} from './liveness'

export function RunScreen() {
  const { runId = '' } = useParams()
  const [progress, setProgress] = useState<RunProgress | null>(null)
  const [episodes, setEpisodes] = useState<RunEpisodes | null>(null)
  const [unavailable, setUnavailable] = useState('')
  const [refused, setRefused] = useState('')
  const [busy, setBusy] = useState(false)
  /* The stop's own state, beside the interrupt's and never folded into it: `busy` is
     an answer to the halt going out, and this is a second decision made minutes later.
     A screen that shared one flag would grey the halt's buttons while a stop was in
     flight.

     Two flags and not one, because the press outlives its request. `stopping` is the
     request in flight and clears in milliseconds; `stopped` is the fact that the bench
     took the stop, and it is never unset — the run goes on running until the bench
     reaches its next `authorise_call`, which on a real target is a whole attempt away.
     A screen holding only the first re-armed the button in that gap and asked for the
     press again (ADR-0114). */
  const [stopping, setStopping] = useState(false)
  const [stopped, setStopped] = useState(false)
  const [refusedStop, setRefusedStop] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  /**
   * When the bench last answered this screen, and what time it is now.
   *
   * Two moments rather than a state that says *stalled*, because what stalled means
   * is a rule and the rule is `liveness.ts`'s. `now` is what makes the silence
   * visible at all: nothing arrives while the bench is quiet, so a screen with no
   * clock of its own renders at the moment it stops being told anything and then
   * never again.
   */
  const [answeredAt, setAnsweredAt] = useState<number | null>(null)
  const [clock, setClock] = useState(() => Date.now())

  /**
   * The figures this run was estimated at, read once from the handoff.
   *
   * Once rather than on every render, and never re-read after an answer: what a
   * person confirmed has to be what they were looking at, and a value that could
   * change under the control would make the confirmation about something else.
   */
  const [figures] = useState<RunEstimate | null>(() =>
    theFiguresPresented(sessionStorage, runId),
  )

  /**
   * **Kept under the compiler: the poll below.** This is named in that effect's
   * dependency array, so an unmemoised `read` restarts a two-second poll on every
   * render — cadence the bench feels, not render cost. Compiled, the compiler emits
   * this same cache keyed on `runId`; skipped, it emits nothing and this line is the
   * only thing holding the identity. See `vite.config.ts` for why that matters.
   */
  const read = useCallback(async (): Promise<RunProgress | null> => {
    try {
      const now = await runProgress(runId)
      setProgress(now)
      setUnavailable('')
      /*
        The adaptive layer's probes, read on the same tick and kept apart.

        A second request against a second route, because they are two records: the
        progress reading holds the scored layer's last exchange, and this holds the
        episodes the process is still carrying — committed nowhere, gone at a restart,
        and reaching no artefact (ADR-0008, amended, and the route's own `stated`).
        Nothing merges the two, and an episode that has not started leaves the block
        undrawn rather than empty.

        Its failure is swallowed on purpose: this is the one read on the screen whose
        answer is not load-bearing, and a run whose progress is arriving perfectly well
        should not report itself unavailable because the probes did not.
      */
      void runEpisodes(runId)
        .then(setEpisodes)
        .catch(() => setEpisodes(null))
      // The moment the bench answered, which is what dates every figure below.
      // Recorded on the answer and never on the asking: a poll that never comes back
      // is exactly the failure the stamp is here to make visible.
      setAnsweredAt(Date.now())
      setClock(Date.now())
      return now
    } catch (unknown: unknown) {
      setUnavailable(`${unknown}`)
      return null
    }
  }, [runId])

  useEffect(() => {
    let current = true
    let timer: ReturnType<typeof setInterval> | undefined
    const tick = async () => {
      const now = await read()
      // Stopped for good, so stop asking: a run that ended is a run whose screen
      // has nothing left to learn from the bench.
      if (current && now && !stillGoing(now.status) && timer !== undefined) {
        clearInterval(timer)
      }
    }
    timer = setInterval(() => void tick(), POLL_SECONDS * 1000)
    void tick()
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [read])

  /**
   * The clock this screen reads its own silence against.
   *
   * **A second interval beside the poll, and it has to be a second one.** The failure
   * being watched for is a request that never comes back, so a `now` advanced inside
   * the poll's own tick would stop advancing at exactly the moment it was needed. It
   * asks nothing of anybody: one `Date.now()` at the poll's own cadence.
   *
   * It stops when the poll does. A run that has stopped is settled rather than silent
   * (ADR-0078), and a tab left open on a finished run should not re-render every two
   * seconds for the rest of the day.
   */
  const inFlight = progress === null || stillGoing(progress.status)
  useEffect(() => {
    if (!inFlight) {
      return
    }
    const ticking = setInterval(() => setClock(Date.now()), POLL_SECONDS * 1000)
    return () => clearInterval(ticking)
  }, [inFlight])

  /**
   * The name the confirmation is recorded under, from the registration that made
   * this run. No screen asks for it again.
   */
  const identity = whoAttested(sessionStorage, runId)

  const request: ConfirmationRequest = confirmationRequest({
    status: progress?.status ?? '',
    figures,
    confirmed,
    identity,
    // No field asks for one. A decline carries `declineRequest`'s own sentence and a
    // confirmation carries none, which is what a screen with no reason box means.
    reason: '',
  })

  const answer = async (body: ApprovalBody) => {
    setBusy(true)
    const outcome = await answerTheInterrupt(runId, body)
    setBusy(false)
    setRefused(outcome.kind === 'answered' ? '' : outcome.statement)
    await read()
  }

  const confirm = () => {
    // Asked again on the click. The disabled state is a courtesy; this is the
    // check, and it is the only line in this app that can put a `confirmed: true`
    // on the wire.
    if (request.kind !== 'ready') {
      return
    }
    void answer(request.body)
  }

  /**
   * The second decision this screen can take: stop the suite that is going.
   *
   * It reads the run straight back rather than waiting for the next poll, because the
   * press has to be answered on the screen it was made on — the bench settles the run
   * on its own thread, so what comes back here is the record as it stands and the
   * status arrives with the read after it.
   *
   * A refusal is the bench's own sentence and is drawn rather than thrown: a run that
   * reached its end in the instant this was pressed has moved, which is not an error.
   */
  const stopTheSuite = async () => {
    setStopping(true)
    setRefusedStop('')
    const outcome = await stopTheRun(runId)
    if (outcome.kind === 'answered') {
      // The bench has the flag, and this screen keeps that fact for the rest of the
      // run. What has not happened yet is the run ending: the stop is read where the
      // next call is authorised, so the message already on the wire is answered and
      // recorded first.
      setStopped(true)
    } else {
      setRefusedStop(outcome.statement)
    }
    await read()
    setStopping(false)
  }

  const at = progress === null ? null : standing(progress)
  const live = liveness({ answeredAt, now: clock, inFlight })
  /**
   * What this screen says out loud, and what the tab strip says for a run somebody
   * has backgrounded.
   *
   * The same two words in both places, and neither is a figure: a phase, or that the
   * screen has stopped being told anything. `announce.ts` says why a count has no
   * business in a tab strip, and ADR-0078 why the announcement carries nothing that
   * moves on its own.
   */
  const said = announcement(at === null ? null : at.heading, live)
  useScreenTitle(
    THE_RUN,
    live.kind === 'stalled' ? NOT_ANSWERING_BRIEFLY : (at?.heading ?? 'Reading the run'),
  )
  /*
   * The screen and never the phase. This heading changes when the run changes what
   * it is doing, and a run that finishes under somebody who is reading the panel
   * below it would take the keyboard off what they are reading. So the arrival is
   * the screen — announced once, on the way in — and what the run is doing is said
   * in the live region instead, which announces without moving anything.
   */
  const heading = useArrivalFocus(THE_RUN)
  return (
    <main className="screen">
      {/*
        The heading, and under it the date of everything below it.

        The eyebrow said *AgentAudit — run*: the app's name is in the rail and the
        rail's current row says which screen this is. The line under it carried the
        run's id and the poll interval — the id is in the address bar of the page it
        addresses, and the interval is a fact about this client, not about the run.
        What the run is doing is the heading, and the section under it says it again
        in the bench's own words.

        The stamp that took their place is not a fact about this client either: it is
        when the figures on this screen were last true, which is the one thing a
        reader cannot get from the figures themselves (ADR-0078).
      */}
      <header>
        <h1 ref={heading} tabIndex={-1}>
          {at === null ? 'Reading the run' : at.heading}
        </h1>
      </header>

      {/*
        What the run is doing, said once each time it changes.

        Polite, and off the screen: the heading above says the same thing to anybody
        looking at it, and a second copy in the reading column would be this screen
        saying everything twice. What it buys is the reader who is not looking —
        a run takes minutes, and its phases change while somebody is in another tab
        or reading further down this one.

        It announces on a phase change and never on a tick, which is a property of
        the sentence rather than of this element: `announcement` is built from the
        standing and the liveness kind alone, so the text React writes here is
        identical between two polls of one phase and the region stays silent
        (ADR-0078).
      */}
      <p className="announced" role="status" aria-live="polite">
        {said}
      </p>

      {/* When what is below was last true, for the reader who did not watch it
          arrive. Not on a run that has stopped: those figures are final rather than
          dated, and a time of day over them reads as a screen still watching
          something (ADR-0078). */}
      {live.stamp !== '' && live.kind !== 'settled' ? (
        <p className="answered">Answered at {live.stamp}</p>
      ) : null}

      {/*
        The silence, said where the figures are — and the figures left standing.

        Not a `role="alert"`: the polite region above has already announced it, and
        the same words twice in two politenesses is the screen shouting. It is also
        not a refusal — nothing was refused, and nobody's endpoint did anything. The
        run is very likely still going.
      */}
      {live.kind === 'stalled' ? (
        <section className="stalled">
          <h2>This screen has stopped being answered</h2>
          <p>{NOT_ANSWERING}</p>
          <p>
            <button type="button" onClick={() => void read()}>
              {ASK_AGAIN}
            </button>
          </p>
        </section>
      ) : null}

      {/* Polite, and ADR-0080 is why: nobody pressed anything to produce this. It is
          the poll's own refusal, arriving on a two-second timer that runs whether or
          not a reader is looking at the screen — and it can be here in the first
          paint, where an assertive region announces nothing anyway. */}
      {unavailable ? (
        <section className="refusal" role="status">
          <h2>The bench did not say where this run is</h2>
          <p>{unavailable}</p>
        </section>
      ) : null}

      {/* One of the six that stay assertive (ADR-0080): this is on the screen only
          because an operator answered the interrupt and the bench did not take the
          answer, and it is what they are waiting to be told. */}
      {refused ? (
        <section className="refusal" role="alert">
          <h2>That answer was not taken</h2>
          <p>{refused}</p>
        </section>
      ) : null}

      {at?.kind === 'holding' ? (
        <TheInterrupt
          figures={figures}
          request={request}
          confirmed={confirmed}
          setConfirmed={setConfirmed}
          busy={busy}
          confirm={confirm}
          decline={() => void answer(declineRequest(''))}
        />
      ) : null}

      {at !== null && progress !== null && at.kind !== 'holding' ? (
        <Progress
          at={at}
          progress={progress}
          episodes={episodes}
          stop={stopTheSuite}
          stopping={stopping}
          stopped={stopped}
          refusedStop={refusedStop}
        />
      ) : null}

      {progress?.status === REGISTRATION_REFUSED ? (
        <p>
          <Link to={`/register?refused=${encodeURIComponent(runId)}`}>
            Re-plant the nonce and register again
          </Link>
        </p>
      ) : null}
    </main>
  )
}

interface InterruptProps {
  figures: RunEstimate | null
  request: ConfirmationRequest
  confirmed: boolean
  setConfirmed: (confirmed: boolean) => void
  busy: boolean
  confirm: () => void
  decline: () => void
}

/**
 * The halt, as the screen a run cannot get past on its own.
 *
 * The two figures come first because they are what is being consented to, and the
 * control is underneath them rather than beside them: the order is the argument.
 * When this app is not holding the figures there is no control at all — only the
 * sentence saying why, and the answer that spends nothing.
 */
function TheInterrupt({
  figures,
  request,
  confirmed,
  setConfirmed,
  busy,
  confirm,
  decline,
}: InterruptProps) {
  const view = figures === null ? null : interruptView(figures)
  return (
    <>
      <section>
        {/*
          The two figures, and nothing over them.

          *What this run will cost, before any of it is spent* was the `h2` here,
          under an `h1` saying the run was holding at its interrupt. It is the `h1`
          now — a screen that shows two numbers and takes a yes has one thing to say
          at the top, and that the run is holding is what the screen being here at
          all means. Three paragraphs went with the heading: the bench's own sentence
          about the halt, this screen's sentence saying nothing has been sent, and the
          one saying why there is no third figure. The `FIGURES_NOT_HELD` block stays,
          because it is the only thing that explains a screen with no figures and no
          confirmation on it. It is polite rather than assertive: nothing was refused
          and nobody pressed anything — the handoff simply held nothing for this run,
          which is true before the reader has done a thing (ADR-0080).
        */}
        {view === null ? (
          <p role="status">{FIGURES_NOT_HELD}</p>
        ) : (
          <dl className="figures">
            {view.figures.map((figure) => (
              <div className="figure" key={figure.layer}>
                {/*
                  The layer's name, and what kind of figure it is on the same line.

                  `kind` was the third thing on the line under the number — after the
                  calls and the cost, in the quiet — which put *exact* and *ceiling*
                  where a reader had already passed both figures they qualify. It is
                  the qualifier on everything in the box, so it is at the head of the
                  box, ranged right against the name.

                  The number still carries its own `≤` (`CostFigure`), so nothing here
                  is the only place the epistemic status is said.
                */}
                <dt>
                  <span className="what">{figure.label}</span>
                  <span className="kind">{figure.kind}</span>
                </dt>
                {/* The calls, the money under them, and the basis under that: one
                    figure to a line, so the two boxes' numbers sit at the same height
                    beside each other and a reader compares down a column rather than
                    across a wrapped line. */}
                <dd>
                  <span className="calls">{figure.calls} calls</span>
                  <span className="money">{figure.cost}</span>
                  <span className="aside">{figure.basis}</span>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {/*
        The answer, and no heading over it.

        *Your answer* named a section holding one tick and two buttons, under a
        heading that had just said what the figures are. *Who is confirming* went with
        it: the name is the one from the registration that made this run, carried in
        `sessionStorage` beside the figures, so the bench's `confirmed by <name>` is
        still a name and nobody types it twice.
      */}
      {/*
        No form here, and that is the decision rather than the omission.

        Every other screen that takes input got one (#120), because Enter should
        finish a form. This one is the halt in front of the spend: there is no text
        field for implicit submission to serve, and what a form would buy is a
        keystroke on the tick below that confirms the figures and starts the run.
        A consent interrupt whose primary is one key away from a checkbox is not the
        block ADR-0007 asks for. The two buttons stay `type="button"`.
      */}
      <section>
        {view === null ? null : (
          <label className="declaration">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span className="wording">
              I have read both figures and I am spending them. The scored layer will
              attack this endpoint at the exact figure above; the adaptive layer may
              spend up to its ceiling.
            </span>
          </label>
        )}
        <div className="walk">
          <button type="button" onClick={decline} disabled={busy}>
            {busy ? 'Answering…' : 'Decline — send nothing, spend nothing'}
          </button>
          {view === null ? null : (
            <button
              type="button"
              className="primary"
              onClick={confirm}
              disabled={busy || request.kind !== 'ready'}
            >
              {busy ? 'Answering…' : 'Confirm both figures and start the run'}
            </button>
          )}
        </div>
      </section>
    </>
  )
}

/**
 * The run in flight or the run that stopped, per layer.
 *
 * The standing comes first — what the run is doing, or the named thing that
 * stopped it — and the two panels under it are two panels rather than one table
 * with a total row, which is the arrangement a total gets added to.
 */
function Progress({
  at,
  progress,
  episodes,
  stop,
  stopping,
  stopped,
  refusedStop,
}: {
  at: Standing
  progress: RunProgress
  episodes: RunEpisodes | null
  stop: () => Promise<void>
  stopping: boolean
  stopped: boolean
  refusedStop: string
}) {
  /*
   * The standing's own status word and sentence are not drawn.
   *
   * They were the two lines under the heading — *running*, and *confirmed by X: the
   * suite is running in the background, under the ceiling that was confirmed* — which
   * is the heading again, plus the name of whoever answered the interrupt and the
   * promise the interrupt already made.
   *
   * What is kept is everything the heading does *not* say: the run's own sentence
   * when it differs from the standing's, which is how a transport failure reports
   * where the run was when the endpoint stopped answering, and the sentence saying
   * the stop was not a result about the target. The section is drawn only when one
   * of them has something in it.
   *
   * An abort's censored episode was drawn here too, in this screen's own words. It
   * is not any more: the bench settles every abort with that sentence in the run's
   * statement, so the paragraph was the same fact a second time.
   */
  const alsoSaid = progress.statement === at.statement ? '' : progress.statement
  const anythingElse = alsoSaid || at.notASecurityResult
  return (
    <>
      {anythingElse ? (
        <section>
          {alsoSaid ? <p className="aside">{alsoSaid}</p> : null}
          {at.notASecurityResult ? (
            <p className="aside">{at.notASecurityResult}</p>
          ) : null}
        </section>
      ) : null}

      <section>
        {/*
          The run's own state and where it is, in place of a heading.

          *Where the run has got to, one layer at a time* stood here — a sentence that
          described the two things under it, over a screen whose `h1` already says what
          the run is doing. What a person watching a run wants at the top is the state
          and the position, which is what this line is: the standing's own word with a
          mark beside it, then the scored layer's position, then what that layer has
          spent.

          **What is not in it, and why.** A bar across the whole run, a percentage, a
          count of attempts over every family, one blended call figure and a cost: those
          are a total across families, which this instrument does not have — every
          family is reported over its own denominator and there is no total across them
          (ADR-0005) — and a call count spanning the layers, which hides which half of
          the run is spending (ADR-0007, ADR-0010). Elapsed and remaining are not on the
          wire at all. The per-family figures are the table below, in the columns they
          belong to.
        */}
        <p className={`run-state ${at.kind}`}>
          <span className="dot" aria-hidden="true" />
          {at.name}
          {/*
            The one control on this screen, and only while the run is going.

            **A stop and never a pause** (ADR-0114). It ends the run as an abort: the
            attempts already made stay on the record, each family is reported over what
            was attempted, and there is no resuming it — the estimate confirmed at the
            halt was for a run. Nothing already sent is cancelled; what stops is the
            message after the one on the wire.

            No confirmation on the press. A halt in front of a spend is worth a dialog
            and a halt in front of *not* spending is not — the cost of this one is the
            attempts it does not make.

            The refusal, if the bench refuses, is the bench's own sentence: a run that
            reached its end in the instant this was pressed has moved, and is not an
            error to report as one.
          */}
          {at.kind === 'running' && !stopped ? (
            <button type="button" onClick={() => void stop()} disabled={stopping}>
              {stopping ? 'Stopping…' : 'Stop this run'}
            </button>
          ) : null}
          {/*
            Once the bench has the flag, the control is gone and this stands in its
            place until the run settles. It is not a disabled button: a stop is a stop
            and never a pause, so there is nothing here to press again and nothing to
            un-press — and a greyed-out *Stop this run* reads as a press that did not
            take, which is the thing this whole line exists to stop saying.
          */}
          {at.kind === 'running' && stopped ? (
            <span className="taken">
              Stopping after the message on the wire is answered
            </span>
          ) : null}
        </p>
        {refusedStop ? (
          <p className="aside" role="status">
            {refusedStop}
          </p>
        ) : null}

        {/*
          How much of the scored layer's plan has been done, as a bar and as its two
          counts.

          **The work done, and not a rate.** Attempts made over attempts planned, both
          counts of what this bench has done against the six — see `scoredShare`, and
          ADR-0110, which is where the line through ADR-0005's *no total across them*
          is drawn: what may not be added is the families' rates.

          Drawn in the scored layer's own colour and never in the two verdict colours,
          so the length cannot be read as how the target is answering. That reading is
          the cells in the table, one an attempt.
        */}
        <div className="run-share">
          <div className="track">
            <span
              className="segment scored"
              style={{ width: scoredShare(progress).done }}
            />
          </div>
          <p className="counts">
            <span className="percent">{scoredShare(progress).percent}</span>
            <span>
              {scoredShare(progress).made} / {scoredShare(progress).planned} attempts
            </span>
          </p>
        </div>

        {/*
          The scored layer's position on one line over the table, and the adaptive
          layer's under it.

          Two panels stood here, side by side, each naming its layer's units and the
          calls spent in it. They are the same two readings — `scoredReading` and
          `adaptiveReading`, unchanged — set as lines rather than as boxes: the table
          below is now the thing a person watching a run looks at, and two cards above
          it pushed the six families off the first screenful.

          **Still one reading a layer, and still nothing across them.** The scored
          line carries the scored layer's calls and the adaptive line the adaptive
          layer's, on their own rows in their own units. Nothing here adds them
          (ADR-0007, ADR-0010).
        */}
        <LayerLine reading={scoredReading(progress.scored)} />

        {/*
          The six families as rows of one table, and the elective ones under them.

          Two columns of bars stood here — *how far each family has got*, and *how each
          family is answering* — which is one question a reader asks of one family, in
          two places, with the name written twice. In a table the counts line up down
          their own columns and the attempts themselves are the last column, so what
          has been made and how it went are read across one row.

          **The strip is the run's own order.** `FamilyRow.cells` is built from
          `FamilyRun.answers` — this family's verdicts as they came back — so a cell is
          where its attempt was. It was laid out from the counts while counts were all
          the route served, which put every held cell before every broken one and read
          as two bars filling independently; that was the shape this app made up, and
          the order is the one the bench had all along.

          Not a slope. Attempts are independent by construction, which is what makes
          their quotient a rate rather than a reading of how a target answers being
          attacked repeatedly (CONTEXT.md, ADR-0005).

          **No rate in any row.** Two counts over one denominator — the attempts made,
          and how many of them the target let through — and the quotient of them is a
          measurement that arrives on the report with its interval and its band, over a
          denominator that has stopped moving (ADR-0005).

          **Two lists and nowhere they meet.** `electiveRows` reads the route's second
          list and the two maps stay two maps, so no count here is taken against a
          denominator from the other tier and nothing on the screen is a figure over
          the nine (ADR-0035 §2, ADR-0088).

          **Only the families with a plan.** A family the declarations dropped and a
          requested elective family the library holds no case in are both rows that
          can never fill, and they sat here saying *not run* while the families that
          are running were pushed down the table. `inThePlan` drops the row; what it
          does not drop is the fact, which is on the run record and on the report that
          has to account for all nine (ADR-0015, ADR-0094, ADR-0095).
        */}
        <table className="attempts">
          <thead>
            <tr>
              <th scope="col">family</th>
              <th scope="col" className="figure-cell">
                attempted
              </th>
              <th scope="col" className="figure-cell">
                succeeded
              </th>
              <th scope="col" className="figure-cell">
                rate
              </th>
              <th scope="col" className="attempts-cell">
                attempts
              </th>
              <th scope="col" className="state-cell">
                state
              </th>
            </tr>
          </thead>
          <tbody>
            {/*
              `widest` is the longest plan in the table, and every strip is drawn as a
              share of it: a family of four attempts takes four fifths of the width a
              family of five does, so *one cell = one attempt* holds across the rows
              and not only inside one. Without it the cells were a fixed few pixels and
              the column was mostly empty at every plan this bench actually runs.

              A maximum across both lists and not a denominator built from them: it is
              a length, nothing is added, and no figure is read off it. The two maps
              stay two maps (ADR-0035 §2).
            */}
            {inThePlan(familyRows(progress)).map((row) => (
              <FamilyLine row={row} widest={widestPlan(progress)} key={row.family} />
            ))}
            {inThePlan(electiveRows(progress)).map((row) => (
              <FamilyLine row={row} widest={widestPlan(progress)} key={row.family} />
            ))}
          </tbody>
        </table>

        {/* The two verdict words and the two states of an attempt, named rather than
            left to hue: nothing on this bench is carried by colour alone. */}
        <p className="legend">
          {ANSWER_KEYS.map((key) => (
            <span className="key" key={key.answer}>
              <span className={`swatch ${key.accent}`} aria-hidden="true" />
              {key.answer}
            </span>
          ))}
          <span className="key">
            <span className="swatch in-flight" aria-hidden="true" />
            in flight
          </span>
          <span className="key">
            <span className="swatch waiting" aria-hidden="true" />
            not yet attempted
          </span>
          <span className="unit">one cell = one attempt</span>
        </p>

        {/*
          The last call the scored layer made, under that layer's own table.

          At the width of the page, because an exchange is a paragraph of somebody's
          traffic and it reads badly in half a column.

          **One block a layer, and the types stay two.** This one and the adaptive
          layer's below are both a call this run put on the operator's endpoint; what
          differs is what the call belongs to. The scored one is an **attempt** — the unit of a
          denominator — and carries a case and a verdict; the adaptive one is a **turn**
          inside an episode, which is deliberately not a unit of anything, and carries a
          reading. They arrive on two routes, go through two functions and are drawn by
          two components, so there is no list in this app a turn could be counted in and
          no signature that takes either (CONTEXT.md, ADR-0010). What they share is a
          region of the screen, on ADR-0091's own terms: the presentation joins and the
          types do not. Each block's own label is what names its unit.

          The adaptive block is absent until that layer has sent something. A block
          saying *nothing yet* for the layer that runs last would stand empty under the
          whole of a scored run, and its own line above the table already says where it
          is.
        */}
        <div className="payloads">
          {/* No heading over the blocks. Each of them opens on its own label — `LAST
              CALL` on the attempt and `LAST TURN` on the turn — which says what the
              block is and which layer made it, where a heading over both could only
              name one of the two units. */}
          {payloads(progress).length === 0 ? (
            <p className="aside">
              Nothing has come back yet. The exchange appears here as it does.
            </p>
          ) : (
            payloads(progress).map((one) => <Payload one={one} key={one.key} />)
          )}
        </div>
        <LayerLine reading={adaptiveReading(progress.adaptive)} />

        {/* And that layer's last turn, under the line naming the layer that sent it —
            the scored block above sits under the scored layer's line and its table for
            the same reason. Each block is beside the layer it belongs to, which is what
            keeps the two units apart on the screen as the types keep them apart in the
            app (ADR-0010). */}
        {turns(episodes ?? { held: false, run_id: '', stated: '' }).map((one) => (
          <div className="payloads" key={one.key}>
            <Turn one={one} />
          </div>
        ))}

      </section>

      {/*
        No report section on this screen.

        Three artefact links and a link to the report screen stood here, under a
        heading. They are one press away in the rail — *Signed artefacts* lists every
        artefact this bench has signed, with the same three files and the same
        verification beside each — and this screen is where a run is *watched*: a
        block that appears only once the run is over, at the foot of a page somebody
        has been watching for an hour, is a destination and not a reading.

        `progress.report` is still served and still typed, and `report.statement` is
        still the sentence naming the three files and what `scripts/verify.py` does
        with a directory holding them. Nothing here reads either.
      */}
    </>
  )
}

/**
 * The longest plan in the table, for the strips to be drawn as a share of.
 *
 * A length and not a figure: it sizes a cell and nothing on the screen is read off it.
 * Taken over both lists because the strips share one column and a scale that differed
 * between the six and the tier would put two cell sizes under one heading — which is
 * the one thing *one cell = one attempt* cannot survive.
 */
function widestPlan(progress: RunProgress): number {
  return Math.max(
    0,
    ...familyRows(progress).map((row) => row.of),
    ...electiveRows(progress).map((row) => row.of),
  )
}

/**
 * One family as a row: the counts, the attempts themselves, and where it has got to.
 *
 * Two bars stood here, in two columns, each with the family's name beside it — one for
 * how much of the work was done and one for how it was going. They are one row now,
 * and the counts are read down their own columns instead of off the ends of bars.
 *
 * **The counts are the bench's and this row divides none of them.** *Attempted* is the
 * family's own denominator with the attempts made against it, and *succeeded* is how
 * many of those the target let through. The quotient of the two is a rate, and a rate
 * arrives on the report with its interval and its band, over a denominator that has
 * stopped moving (ADR-0005).
 *
 * A family the plan dropped says `not run` where the fraction goes and draws a strip
 * of nothing: an empty strip over a denominator of zero would read as one that has not
 * started yet, and this one is never going to. **Why** it was not run is not on this
 * screen — one sentence per family over nine families, on a run in flight — and it is
 * in the report, which is the document that has to account for every family
 * (ADR-0035, ADR-0094).
 */
function FamilyLine({ row, widest }: { row: FamilyRow; widest: number }) {
  return (
    <tr>
      <th scope="row">{row.name}</th>
      <td className="figure-cell">
        {row.notRun ? 'not run' : `${row.attempted} / ${row.of}`}
      </td>
      {/* Nothing rather than a zero where no attempt has come back: a family that has
          been attempted no times has not been let through zero times, and `0` in this
          column is a count somebody would read as one. */}
      <td className="figure-cell broke">
        {row.attempted === 0 ? '—' : row.succeeded}
      </td>
      {/*
        The share of this family's answered attempts the target let through — a
        per-family rate over that family's own denominator, which is the shape
        ADR-0005 prescribes, and a point estimate over a denominator that is still
        moving, which is why ADR-0111 calls it a reading of the run. The measurement a
        recipient is handed is on the report, with its Wilson interval, its verdict
        class and its band.

        Nothing sums this column, and there is nothing under it to sum it into: six
        rates over six denominators are six figures, and the one number this project
        exists to refuse is their mean (ADR-0005).
      */}
      <td className="figure-cell broke">{row.rate}</td>
      <td className="attempts-cell">
        {/*
          One cell an attempt, in the four states one attempt can be in, in the order
          the verdicts came back (`FamilyRow.cells`). Each cell carries its state as a
          word for a reader who cannot tell the hues apart — the legend under the
          table names all four.
        */}
        <span
          className="cells"
          style={{ width: widest === 0 ? '0' : `${(row.of / widest) * 100}%` }}
        >
          {row.cells.map((cell, index) => (
            <span
              className={`cell ${cell.replace(' ', '-')}`}
              key={index}
              title={cell}
            />
          ))}
        </span>
      </td>
      <td className={`state-cell ${row.state.replace(' ', '-')}`}>{row.state}</td>
    </tr>
  )
}

/**
 * One attempt: what the bench sent, and what the target answered.
 *
 * The two halves are set apart the way an exchange reads — the attack, then the reply
 * — and nothing here is coloured by its verdict: *succeeded* and *resisted* are the
 * two answers this bench counts, and a green one beside a red one is the severity
 * scale ADR-0005 exists to refuse. Which it was is in the bar above, where the two
 * words are printed beside the two colours.
 */
function Payload({ one }: { one: PayloadRow }) {
  return (
    <div className="payload">
      {/*
        Which attempt this was, over the two turns of it.

        The case, the attempt's number within it, the family it belongs to, and the
        verdict the bench reached — all four served on the exchange and none derived.
        The exchange was drawn with nothing saying which attempt it was, so a reader
        watching a run could not tell the call on the screen from the one before it.

        The verdict is a word at the end of the line and the turns stay uncoloured:
        *succeeded* and *resisted* are the two answers this bench counts, and a green
        turn beside a red one is the severity scale ADR-0005 exists to refuse.
      */}
      <p className="which">
        <span className="of">last call</span>
        <code>{one.caseId}</code>
        <span>attempt {one.attempt}</span>
        <span>{one.name}</span>
        <span className="verdict">verdict: {one.verdict}</span>
      </p>
      {/*
        Who said it, over what they said, rather than a mark beside it.

        Both ends are agents — the bench's attacker and the target answering it — and
        the two words are this project's own for them (CONTEXT.md), so neither turn is
        told from the other by which side of the card it sits on. A reader coming to
        the exchange cold now reads the speaker rather than decoding the layout.
      */}
      <div className="turn sent">
        <p className="who">attacker</p>
        <p className="bubble">{one.sent}</p>
      </div>
      <div className="turn reply">
        <p className="who">target</p>
        <p className="bubble">{one.reply}</p>
      </div>
    </div>
  )
}

/**
 * One turn of an episode: what the attacker composed, and what came back.
 *
 * `Payload`'s shape and not `Payload` itself, which is the split the two records are
 * under: an attempt names a case and carries a verdict, and a turn names an episode and
 * carries a reading — *broke it*, *no break*, *not checkable* — because an episode has
 * no verdict and there is no name in this app for one that resisted (ADR-0011).
 *
 * The probe is the attacker's own words rather than a case the library committed, so
 * what this block shows reaches no artefact and is on no disk: it is held by the
 * process that ran the run and is gone when that process stops (ADR-0008, amended).
 */
function Turn({ one }: { one: TurnRow }) {
  return (
    <div className="payload">
      <p className="which">
        <span className="of">last turn</span>
        <span>episode {one.episode}</span>
        <span>turn {one.turn}</span>
        <span>{one.name}</span>
        {/* Not pushed to the far edge the way an attempt's verdict is: a verdict is a
            word and this is a sentence — the objective's condition was met, or read
            and not met, or carried nothing to read — so it takes its own line at the
            left rather than being ranged right and wrapping into the middle. */}
        <span className="reading">{one.reading}</span>
      </p>
      <div className="turn sent">
        <p className="who">attacker</p>
        <p className="bubble">{one.sent}</p>
      </div>
      <div className="turn reply">
        <p className="who">target</p>
        <p className="bubble">{one.reply}</p>
      </div>
    </div>
  )
}


/**
 * One layer on one line: where it is, in its own units, and what it has spent there.
 *
 * A panel to a layer stood here, side by side. The units and the values are the same
 * reading — a layer's position is its own three or four words and never a row in a
 * table shared with the other layer's (CONTEXT.md, ADR-0010) — set along a line so
 * that the families below start on the first screenful.
 *
 * The bench's sentence about the position is not drawn: *family wrongful_commitment,
 * case wrongful-commitment-003, attempt 10: the position the scored layer has
 * reached* is these values read out in prose. The field stays on the reading because
 * the gate screen draws it where there is no position to draw.
 */
function LayerLine({ reading }: { reading: LayerReading }) {
  return (
    <p className="layer-line">
      <span className="of">{reading.title}</span>
      {reading.at === null ? (
        <span className="at">not started</span>
      ) : (
        reading.units.map((unit, index) => (
          <span className="at" key={unit}>
            <span className="unit">{unit}</span> {reading.at?.[index]}
          </span>
        ))
      )}
      <span className="spent">{reading.callsSpent} calls</span>
    </p>
  )
}
