/**
 * The report screen: the two layers' figures, and no number the project spent
 * nineteen ADRs refusing to print.
 *
 * It renders from the **signed payload** — the bytes a recipient verifies, fetched
 * from the path the run's own record advertises — and offers all three files for
 * download beside it. What is on this page is what is in the artefact: there is no
 * figure here the payload does not carry, because the screen builds none
 * (`report.ts`).
 *
 * **The figures are the page.** Each family is a card that opens with its rate and
 * its band, with the interval, `κ` and the verdict class on one monospace line under
 * them and the counts beneath — the idiom the gate screen's per-family cards already
 * use.
 *
 * **`D` is not one of them.** It is the separation between two agents of known
 * construction at the bench's own gate: a property of the instrument, and ADR-0018
 * keeps the bench's calibration equipment out of a target's report. The API declines
 * to hand a gate decision to the assembler for exactly that reason
 * (`api/report.py`), so the field on the wire is `null` on every target report — a
 * figure that was always going to read *not recorded*, next to numbers that are
 * about the target.
 *
 * **The adaptive layer is read per family too**, because that is the question the
 * section answers — what the search proposed against each family, over how many
 * turns, and whether it broke it. Grouped and never joined: a turn is not an
 * attempt and no count here meets a count above it (ADR-0010).
 *
 * **The probes are on this page, and they are the one thing on it that is not in
 * the artefact.** Under the adaptive section, fed by `GET /runs/{id}/episodes` and
 * never by the payload: the report says an episode broke the objective in ten turns
 * and the operator asked what was sent. It is read out of the bench's memory, is
 * covered by no signature, is committed nowhere and is gone when the process stops,
 * and the block says all four in the sentence above the probes rather than in a note
 * under them (ADR-0008, amended). A screenshot of it is a copy of a working exploit,
 * which is the trade that amendment makes and states.
 *
 * **The three results are not on this page.** They were: a signature, a rendering
 * binding and a re-derivation, printed near the top so an engineer learned the
 * artefact was checkable before sending it on. They are still read into every row of
 * the signed-artefacts list (`console/artefacts.ts`), and no screen draws them: what
 * settles whether a document is one to send is a recipient's own `scripts/verify`
 * over the three files this page links to. A sender's word for their own document is
 * the thing a signature exists to replace (ADR-0017).
 *
 * **The declared-and-defeated join is not on this page either.** It is in
 * `report.json` and in the `report.md` a recipient reads, which is where the join
 * travels; this screen is a viewer for the figures.
 *
 * **Nothing on this page combines two families.** Not a total, not an average, not
 * a rank, not a badge — and the families are laid out as cards rather than as rows
 * of one table, because a table wants a total row and a grid of cards has nowhere
 * to put one. The absence is asserted in `report.test.ts` against the payload this
 * screen renders from, structurally: drop a family and every other part of the view
 * is unchanged.
 *
 * **A target has rates, intervals and bands, and passes and fails nothing**
 * (ADR-0018). What made the artefact — the attestation, the models, the rule, the
 * library version, the calls each layer spent, the bench's own gate — and the risk
 * categories this bench does not test are in `report.json` and in the `report.md` a
 * recipient reads. They are not on this page; the figures are.
 */

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { readFamily } from '../families'
import {
  reportPayload,
  runEpisodes,
  runProgress,
  type ReportLocation,
  type RunEpisodes,
  type TargetReport,
} from '../api/bench'
import {
  reportView,
  routeReading,
  type AdaptiveFamilyReading,
  type EpisodeRouteReading,
  type FamilyBreakReading,
  type FamilyAnswer,
  type ReportView,
  type RouteReading,
} from './report'

/** What this screen is holding: the things it needs, or why it has none of them. */
interface Held {
  where: ReportLocation | null
  report: TargetReport | null
  /**
   * The probes this run's own episodes sent, or `null`.
   *
   * Held apart from `report` because it comes from somewhere else and means
   * something else: the report is the signed artefact, fetched from the path the run
   * advertises, and this is a read of the bench's own memory that no document
   * carries. A screen that kept them in one field would be a screen one refactor
   * away from drawing a probe out of the artefact (ADR-0008, amended).
   *
   * `null` is *this app did not get an answer*, which is not the same as the bench
   * saying it holds no episode — that answer is a `NoProbes`, and the block prints
   * the bench's own sentence for it.
   */
  episodes: RunEpisodes | null
  /** The run's own sentence about why there is no report, carried unedited. */
  noReport: string
  unavailable: string
}

const NOTHING_YET: Held = {
  where: null,
  report: null,
  episodes: null,
  noReport: '',
  unavailable: '',
}

export function ReportScreen() {
  const { runId = '' } = useParams()
  const [held, setHeld] = useState<Held>(NOTHING_YET)

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        // Where the artefact is comes from the run's own record rather than from a
        // path this app builds, so the screen cannot go looking somewhere the bench
        // does not serve — and a run with no report says why in its own words.
        const progress = await runProgress(runId)
        if (progress.report === null) {
          if (current) {
            setHeld({ ...NOTHING_YET, noReport: progress.statement })
          }
          return
        }
        const where = progress.report
        const report = await reportPayload(where.path)
        // Fetched after the artefact and allowed to fail on its own: the figures are
        // the page, and a bench that has forgotten this run's episodes — a restart,
        // which is the state the probes are meant to be in — is not a reason to
        // refuse a reader the report.
        const episodes = await theProbes(runId)
        if (current) {
          setHeld({ ...NOTHING_YET, where, report, episodes })
        }
      } catch (unknown: unknown) {
        if (current) {
          setHeld({ ...NOTHING_YET, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [runId])

  const view = held.report ? reportView(held.report) : null
  return (
    <main className="screen">
      {/*
        The target, and nothing over or under it.

        The eyebrow named the app the rail names on every screen, and the line under it
        carried the run's id — which is in the address bar of the page it addresses —
        and the artefact's name and version. That last is the only fact of the three
        this page was the sole home of, so it moved to *How this report was made*,
        which is where a reader looking for what this document is goes.
      */}
      <header>
        <h1>{view ? view.target : 'Reading the report'}</h1>
      </header>

      {held.unavailable ? (
        <section className="refusal" role="alert">
          <h2>The bench did not serve this report</h2>
          <p>{held.unavailable}</p>
          <p>
            The run itself is at <Link to={`/runs/${runId}`}>its own screen</Link>,
            which says where it got to.
          </p>
        </section>
      ) : null}

      {held.noReport ? (
        <section className="refusal" role="alert">
          <h2>This run has no report</h2>
          <p>{held.noReport}</p>
          <p>
            Nothing partial is shown in its place: half a report reads as a finished
            one. <Link to={`/runs/${runId}`}>Watch the run</Link>.
          </p>
        </section>
      ) : null}

      {view && held.where ? (
        <TheReport view={view} where={held.where} episodes={held.episodes} />
      ) : null}
    </main>
  )
}

/**
 * The probes, or nothing, and never an exception this screen falls over on.
 *
 * The one read on this page whose absence is ordinary. The episodes live in the
 * process that ran the run, so a bench that has restarted answers `404` for every
 * earlier run — which is the disclosure posture working rather than a fault — and
 * the report itself is unaffected either way.
 */
async function theProbes(runId: string): Promise<RunEpisodes | null> {
  try {
    return await runEpisodes(runId)
  } catch {
    return null
  }
}

/** The whole report, in the order a reader meets it. */
function TheReport({
  view,
  where,
  episodes,
}: {
  view: ReportView
  where: ReportLocation
  episodes: RunEpisodes | null
}) {
  return (
    <>
      <section>
        <h2>The scored layer, one family at a time</h2>
        <div className="families per-family">
          {view.answers.map((answer) => (
            <TheFamily answer={answer} key={`${answer.kind}-${answer.family}`} />
          ))}
        </div>
      </section>

      <section>
        <h2>The adaptive layer, and what it proposed per family</h2>
        <p className="consequence">{view.adaptive.label}</p>
        {view.adaptive.families.length ? (
          <div className="families per-family">
            {view.adaptive.families.map((family) => (
              <TheSearch family={family} key={family.family} />
            ))}
          </div>
        ) : (
          <p className="aside">
            No episode of the search is recorded against this target, which is a
            reading about the attacker and not about the agent.
          </p>
        )}
      </section>

      {episodes ? <TheRoute route={routeReading(episodes)} /> : null}

      {/* The three files under the names a verifier already knows, and nothing
          beside them: what a recipient does with them is `scripts/verify` over the
          directory they land in, and the signed-artefacts screen is the list every
          artefact this bench has produced is reached from. */}
      <section>
        <h2>The signed artefact</h2>
        <ul>
          <li>
            <a href={where.path}>report.json</a>
          </li>
          <li>
            <a href={where.rendering}>report.md</a>
          </li>
          <li>
            <a href={where.signature}>report.sig</a>
          </li>
        </ul>
      </section>
    </>
  )
}

/**
 * One family, as a card that opens with its figures.
 *
 * Three shapes rather than one row with empty cells: a family whose rate is
 * withheld and a family the target could not be measured on carry no figures at
 * all, so there is no cell for a `0.00` to be drawn into. Cards rather than a table
 * for the same reason the two cost figures are blocks — a table wants a total row,
 * and this grid has nowhere to put one.
 */
function TheFamily({ answer }: { answer: FamilyAnswer }) {
  if (answer.kind === 'withheld') {
    return (
      <div className="family absent">
        <h3>{readFamily(answer.family)}</h3>
        <p className="at">rate not published — {answer.reason}</p>
      </div>
    )
  }
  if (answer.kind === 'not_measurable') {
    return (
      <div className="family absent">
        <h3>{readFamily(answer.family)}</h3>
        <p className="at">not measurable — {answer.reason}</p>
        <p>{answer.stated}</p>
        <p className="aside">{answer.note}</p>
      </div>
    )
  }
  const figures = answer.figures
  return (
    <div className="family">
      <h3>{readFamily(answer.family)}</h3>
      <div className="rate-line">
        <p className="score">
          <span className="calls">{figures.rate}</span>
        </p>
        <p className="score">
          <span className="kind">band</span> <strong>{figures.band}</strong>
        </p>
      </div>
      <ul className="rates">
        <li>
          <span className="who">interval</span>{' '}
          <span className="rate">{figures.interval}</span>{' '}
          <span className="who">{figures.intervalAt}</span>
        </li>
        {figures.kappa ? (
          <li>
            <span className="who">κ</span>{' '}
            <span className="rate">{figures.kappa.figure}</span>
          </li>
        ) : null}
        <li>
          <span className="who">verdicts</span>{' '}
          <span className="rate">{figures.verdictClass}</span>
        </li>
      </ul>
      <p className="aside">{figures.counts}</p>
      {figures.kappa ? <p className="aside">{figures.kappa.counts}</p> : null}
    </div>
  )
}

/**
 * One family the search worked in: its episodes, and what each proposed.
 *
 * The turn count is the card's figure and it is the only number on it — a turn is
 * not an attempt, so there is nothing here to read against the cards above.
 */
function TheRoute({ route }: { route: RouteReading }) {
  return (
    <section>
      <h2>The probes this run sent</h2>
      {/* The sentence is the block, not a footnote on it: everything else on this
          page is in the artefact and this is not, so a reader who screenshots the
          probes has the disclaimer in the same picture. */}
      <p className="consequence">{route.note}</p>
      {route.kind === 'absent' ? (
        <p className="aside">{route.stated}</p>
      ) : (
        <>
          {/* What broke each family, before the sequence a reader would otherwise
              have to read end to end. Rows and never a count of them. */}
          <div className="broke-by-family">
            {route.broke.map((family) => (
              <TheFamilyBreak family={family} key={family.family} />
            ))}
          </div>
          <div className="route">
            {route.episodes.map((episode, at) => (
              <TheEpisode episode={episode} key={`${at}-${episode.family}`} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}

/**
 * One family, and the probe that broke it — or which silence it is.
 *
 * The probe is drawn in full rather than summarised: *which one worked* is the fact
 * this row exists to carry, and a truncated payload is not one a reader can act on.
 * A family nothing broke prints the bench's own sentence, because *every turn read
 * and none of them a break* and *no turn could be read at all* are different facts
 * and only the first is about the agent.
 */
function TheFamilyBreak({ family }: { family: FamilyBreakReading }) {
  return (
    <div className={family.broke ? 'family' : 'family absent'}>
      <h3>{readFamily(family.family)}</h3>
      {family.broke ? (
        <>
          <p className="broke">broke it — {family.at}</p>
          <p className="bubble">{family.probe}</p>
        </>
      ) : (
        <p className="kind">{family.stated}</p>
      )}
    </div>
  )
}

/**
 * One episode's probes, numbered, in the order they went on the wire.
 *
 * The turn count is the card's one figure and it is the episode's own — a turn is not
 * an attempt, so there is nothing here to read against the cards above (ADR-0010).
 * The break is marked in a sentence rather than by a colour or a badge: which probe
 * worked is the fact this block was asked for, and a fact carried by a tint is one a
 * greyscale screenshot loses.
 */
function TheEpisode({ episode }: { episode: EpisodeRouteReading }) {
  return (
    <div className="family">
      <h3>{readFamily(episode.family)}</h3>
      <div className="rate-line">
        <p className="score">
          <span className="calls">{episode.turns}</span>
        </p>
        <p className="score">
          <span className="kind">episode</span> <strong>{episode.outcome}</strong>
        </p>
      </div>
      {episode.probes.length ? (
        <ol className="probes">
          {episode.probes.map((probe) => (
            <li key={probe.at}>
              <p className="ordinal">
                {probe.at} — {probe.reading}
              </p>
              <p className="bubble">{probe.probe}</p>
              {/* The reply, because a probe without one is unreadable: *censored* is
                  a fact about the attacker, and only the text that came back tells a
                  target that refused from one that was never asked the right thing. */}
              <p className="ordinal">reply</p>
              <p className="bubble reply">{probe.reply}</p>
              {probe.toolTrace ? (
                <>
                  <p className="ordinal">what it did</p>
                  <p className="bubble reply">{probe.toolTrace}</p>
                </>
              ) : null}
              {probe.confirmedTheBreak ? (
                <p className="broke">{probe.marked}</p>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="aside">{episode.sentNothing}</p>
      )}
      <p className="kind">{episode.stated}</p>
    </div>
  )
}

function TheSearch({ family }: { family: AdaptiveFamilyReading }) {
  return (
    <div className="family">
      <h3>{readFamily(family.family)}</h3>
      {family.episodes.map((episode, at) => (
        <div key={`${at}-${episode.proposed}`}>
          <div className="rate-line">
            <p className="score">
              <span className="calls">{episode.turns}</span>
            </p>
            <p className="score">
              <span className="kind">episode</span> <strong>{episode.outcome}</strong>
            </p>
          </div>
          <p className="aside">Proposed: {episode.proposed}.</p>
        </div>
      ))}
      <p className="kind">
        {family.broke
          ? 'the search broke this family — recorded, and scored nowhere'
          : 'the search did not break this family'}
      </p>
    </div>
  )
}
