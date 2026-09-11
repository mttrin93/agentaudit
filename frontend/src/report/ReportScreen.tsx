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
 * **Each failure is on this page, and it did not used to be.** Under the scored
 * cards: a card says a family's rate, and the blocks under it say what one break in it
 * was read against, what went wrong, what to change, and what informed the fix. Every
 * sentence is the signed payload's own — the section is inside the signature, and this
 * screen writes not one word into it (ADR-0070, `report.ts`). Grouped by family and
 * collapsed, with no count on a summary line, no severity word and no ordering that
 * stands in for one (D3, D12).
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
  runAttempts,
  runEpisodes,
  runProgress,
  type ReportLocation,
  type RunAttempts,
  type RunEpisodes,
  type TargetReport,
} from '../api/bench'
import {
  attemptCounts,
  WHAT_THIS_SECTION_IS,
  exchangesReading,
  reportView,
  routeReading,
  type AdaptiveFamilyReading,
  type EpisodeRouteReading,
  type ExchangesReading,
  type FamilyBreakReading,
  type FamilyExchangeReading,
  type FamilyFindingsReading,
  type FamilyRow,
  type FindingsView,
  type ElectiveFigures,
  type LabelReading,
  type ReportView,
  type RouteReading,
} from './report'
import { useArrivalFocus, useScreenTitle } from '../console/announce'
import { ITS_REPORT } from '../console/rail'

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
  /**
   * The exchanges behind this run's succeeded attempts, or `null`.
   *
   * Held apart from `report` on the same reasoning as `episodes`, and from
   * `episodes` because they are two layers: these are attempts of the scored suite
   * and those are turns of a search, and a field holding both would be the one
   * addition ADR-0010 exists to prevent.
   *
   * `null` is *this app did not get an answer*. The bench saying nothing succeeded is
   * a `NoExchanges`, and the block prints the bench's own sentence for it.
   */
  attempts: RunAttempts | null
  /**
   * What each family attempted, keyed by family, out of the run's own progress.
   *
   * For the cards that publish no rate. The artefact carries no counts for a withheld
   * family — `Withheld` has no field for a rate and none for the counts either — and
   * the attempts were still made, so the numerator and the denominator are read from
   * the same memory the exchanges are. Held in its own field for the reason they are:
   * `reportView` reads the payload and nothing else, and a counts line threaded into
   * it would be the edge that lets a figure from outside the artefact into a reading
   * of the artefact.
   */
  counts: Record<string, string>
  /**
   * Whether the run this page addresses produced no report.
   *
   * A flag and not the run's sentence. It used to carry the statement and draw it in
   * a refusal box, which put the whole of why the run stopped — a ceiling, a stop, a
   * transport failure — on the screen a reader opened to read a *report*. The run's
   * own screen is where that sentence belongs and is where this page sends them.
   */
  noReport: boolean
  unavailable: string
}

const NOTHING_YET: Held = {
  where: null,
  report: null,
  episodes: null,
  attempts: null,
  counts: {},
  noReport: false,
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
            setHeld({ ...NOTHING_YET, noReport: true })
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
        const attempts = await theExchanges(runId)
        if (current) {
          setHeld({
            ...NOTHING_YET,
            where,
            report,
            episodes,
            attempts,
            counts: attemptCounts(progress.families),
          })
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
  useScreenTitle(ITS_REPORT, view ? view.target : 'Reading the report')
  // The screen and not the target: the heading is the target's name once the
  // document arrives, and a heading that took the keyboard when it did would move
  // it under a reader who is already reading the report.
  const heading = useArrivalFocus(ITS_REPORT)
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
        <h1 ref={heading} tabIndex={-1}>
          {view ? view.target : 'Reading the report'}
        </h1>
      </header>

      {/* Both blocks below are polite (ADR-0080). Neither is the answer to a press:
          this screen reads a report on arrival, so whichever of the two is true is
          true before the reader has done anything on it. */}
      {held.unavailable ? (
        <section className="refusal" role="status">
          <h2>The bench did not serve this report</h2>
          <p>{held.unavailable}</p>
          <p>
            The run itself is at <Link to={`/runs/${runId}`}>its own screen</Link>,
            which says where it got to.
          </p>
        </section>
      ) : null}

      {/*
        One sentence, and no box around it.

        A run that did not finish has nothing to show here and nothing partial is
        drawn in its place — half a report reads as a finished one — but that is a
        reason to say little, not a reason to say it loudly. What stood here was a
        red refusal panel carrying the run's whole statement, which is where the run
        stopped and why, on the screen somebody opened to read the document. The
        sentence that survives is the one fact this page has: there is no report, and
        the run's own screen says why.
      */}
      {held.noReport ? (
        <p className="aside" role="status">
          This run produced no report —{' '}
          <Link to={`/runs/${runId}`}>the run&rsquo;s own screen</Link> says why.
        </p>
      ) : null}

      {view && held.where ? (
        <TheReport
          view={view}
          where={held.where}
          episodes={held.episodes}
          attempts={held.attempts}
        />
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

/**
 * The exchanges behind the successes, or nothing, on the same terms as the probes.
 *
 * The other read whose absence is ordinary: an attempt's transcript lives in the
 * process that made it, so every run from before a restart answers `404` — the
 * disclosure posture working rather than a fault — and the figures on this page are
 * unaffected either way.
 */
async function theExchanges(runId: string): Promise<RunAttempts | null> {
  try {
    return await runAttempts(runId)
  } catch {
    return null
  }
}

/** The whole report, in the order a reader meets it. */
function TheReport({
  view,
  where,
  episodes,
  attempts,
}: {
  view: ReportView
  where: ReportLocation
  episodes: RunEpisodes | null
  attempts: RunAttempts | null
}) {
  return (
    <>
      <section>
        <h2>The scored layer</h2>
        {/*
          Six families as rows of one table, where six cards in a grid stood.

          **The figures line up down their own columns.** A reader of this section is
          comparing one family against the next on the rate, the interval and the band,
          and in a grid of cards each of those began at a different depth in a different
          box. The prose each family carries — the counts, the coverage limits, what the
          search found — is under its own row rather than beside the figures, because it
          is read one family at a time and they are read down a column.

          **A table that wants no total row, and has none.** That was the argument for
          cards and it is answered by the table rather than avoided by it: six rates
          over six denominators are six figures, nothing here sums a column, and there
          is no cell for a sum to be drawn into (ADR-0005).

          **The three answers stay three shapes.** A withheld family and one the target
          could not be measured on carry no figures at all, so their rows say so across
          the figure columns rather than drawing an empty cell a reader would take for a
          zero — which is the same refusal the cards were built on, kept.
        */}
        {/* The scroll box the table sits in when the window is narrower than its
            columns want — see `.table-wrap`. */}
        <div className="table-wrap">
          <table className="per-family">
          <thead>
            <tr>
              <th scope="col">family</th>
              <th scope="col" className="figure-cell">
                fail
              </th>
              <th scope="col" className="rate-cell">
                rate
              </th>
              <th scope="col" className="figure-cell">
                interval
              </th>
              <th scope="col" className="band-cell">
                band
              </th>
              <th scope="col" className="refs-cell">
                refs
              </th>
            </tr>
          </thead>
          {view.rows.map((row) => (
            <TheFamily row={row} key={`${row.answer.kind}-${row.family}`} />
          ))}
          {/*
            And the elective families this run asked for, in the same table.

            **Two arrays and two maps, as everywhere else in this app.**
            `ElectiveReading.measured` is its own list and nothing concatenates it into
            `rows`: the six are what the gate's denominator is fixed at (ADR-0015), the
            tier decides nothing (ADR-0035), and no figure here is taken against a
            denominator from the other list. What merges is the table, on ADR-0091's own
            terms and recorded in
            [ADR-0113](../../../docs/adr/0113-the-report-screen-draws-the-tier-in-the-per-family-table.md):
            an elective family's rate against this target is a fact about this target,
            reported with its interval and its band like any other family (ADR-0088),
            and a reader comparing it with the six was reading two tables to do it.

            Nothing in a row says which list it came from, and nothing sums either.
          */}
          {view.elective.measured.map((one) => (
            <TheElectiveFamily one={one} key={one.family} />
          ))}
          </table>
        </div>
      </section>

      <TheFailures findings={view.findings} />

      {attempts ? <TheExchanges exchanges={exchangesReading(attempts)} /> : null}

      <section>
        <h2>The adaptive layer</h2>
        {/* At the size the same claim takes under *failures and fixes*: it is a
            standing fact about what this section's figures are not, read once, and it
            was set larger than the blocks it qualifies. `.asserts` is that treatment
            and this is its second user. */}
        <p className="asserts">{view.adaptive.label}</p>
        {view.adaptive.families.length ? (
          /* The same table the scored layer is read in, so the two sections line up
             down one edge and a reader moves between them without relearning the
             shape. What differs is every column but the first: an episode counts in
             turns and ends in an outcome, and neither is an attempt, a rate or a band
             (CONTEXT.md, ADR-0010). There is no figure here to read against the table
             above, which is what the line over this section says. */
          <div className="table-wrap">
            <table className="per-family searches">
              <thead>
                <tr>
                  <th scope="col">family</th>
                  <th scope="col" className="figure-cell">
                    turns
                  </th>
                  <th scope="col" className="outcome-cell">
                    episode
                  </th>
                  {/* What the search proposed in this family, which is what the
                      section is for and what the cards never printed: the description
                      `propose_case` was given, or the record's own line where an
                      episode proposed nothing. Described and never quoted — a route
                      that beat a target is a working exploit (ADR-0008). */}
                  <th scope="col">proposed</th>
                </tr>
              </thead>
              {view.adaptive.families.map((family) => (
                <TheSearch family={family} key={family.family} />
              ))}
            </table>
          </div>
        ) : (
          <p className="aside">
            No episode of the search is recorded against this target, which is a
            reading about the attacker and not about the agent.
          </p>
        )}
      </section>

      {episodes ? <TheRoute route={routeReading(episodes)} /> : null}

      {/*
        No elective tier section.

        It carried the payload's sentence about the request, a card per requested family
        and a line per family nobody asked for — three paragraphs of *not requested* on
        the common run, which is every run that asked for none of the tier. The measured
        families are rows of the table above now (ADR-0113); the absences and the
        bench's sentences about them are in `report.json` and in the `report.md` a
        recipient reads, which is the document that has to account for every family
        (ADR-0094). `ElectiveReading` is unchanged and still tested whole.
      */}
      {/* The three files under the names a verifier already knows, and nothing
          beside them: what a recipient does with them is `scripts/verify` over the
          directory they land in, and the signed-artefacts screen is the list every
          artefact this bench has produced is reached from. */}
      <section>
        <h2>The signed artefact</h2>
        {/* Three names on one line, because they are three files of one thing: a
            recipient saves all three into one directory and runs `verify` over it, and
            a stacked list read as three separate downloads to choose between. The
            names are the ones the verifier already knows. */}
        <ul className="artefact-files">
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
 * Failures and fixes: each failure the bench explained, and the fix written for it.
 *
 * The heading is the screen's and the signed document keeps its own —
 * `rendering/_explained.py` titles the same material *each failure the bench explained,
 * and the fix written for it*, and a title in the artefact is bytes a digest covers.
 * Shortening one does not shorten the other, and neither says anything the other does
 * not.
 *
 * **The section this screen did not have.** It showed rates, intervals, bands, labels
 * and the coverage limits, and it showed no failure — so an engineer looking at their
 * own run learnt how often their agent broke and never once why. What is drawn here is
 * the same material section 3b of the signed document carries, read from the payload
 * this page already holds (ADR-0070).
 *
 * **Nothing on it is computed.** Every sentence is the artefact's own, printed as it
 * stands; `report.ts` holds that as an identity against the payload, which for this
 * section is also the disclosure answer — what may be shown is what
 * `assembler.ReportedFinding.of` passed, and the payload text, the reply, the tool
 * trace, the precedents' own prose and the judge's confidence are withheld one record
 * before the wire (ADR-0008 as amended, ADR-0070 §2).
 *
 * **Grouped by family and collapsed by default**, which is the one layout decision
 * here: `n = 30` per family means a flat list is unreadable at exactly the moment it
 * matters most. The summary is the family name and nothing else — a count beside it
 * would be a figure this document deliberately does not carry, and there is no
 * ordering of one block against another, no severity word and no tint that stands for
 * one (D3, D12, ADR-0005). Every reviewer UI this borrows from has a severity scale
 * and promptfoo's is the one already refused on the record (#109).
 *
 * **It says which of the four readings holds, under all four.** A section that read
 * the same whether the instruments broke or were never declared would put ADR-0050's
 * own collapse back on the page, one layer along from where ADR-0070 §4 removed it.
 */
function TheFailures({ findings }: { findings: FindingsView }) {
  return (
    <section>
      <h2>Failures and fixes</h2>
      {/*
        Which of the four readings this run holds, as the name the payload carries.

        `findings.reading` is a name off a closed set, and ADR-0070 §4 put it on the
        screen so a reader tells the four apart by that name rather than by prose that
        could be reworded — which is also how a reading this app has no shape for
        reaches the page as itself.

        It was taken off for a pass on this section's length, on the grounds that the
        blocks say it on the one reading that has them and the payload's sentence says
        it on the three that do not. Both are prose, and the line above still claims
        the section says which reading holds under all four — so what the removal cost
        was exactly the guarantee the ADR was making. Dropping it again is a decision
        to record in an ADR rather than in this comment.
      */}
      <p className="kind">{findings.reading}</p>
      {/* One line where three paragraphs stood: who wrote these sentences, that no
          figure above came from them, and what the label on a fix asserts. The three
          the screen no longer prints are `A_MODEL_WROTE_THESE_SENTENCES`,
          `WHAT_A_LABEL_ON_A_FIX_ASSERTS` and the payload's own `stated` — all three
          still built, still tested, and the payload's still travelling in the artefact
          a recipient reads. */}
      <p className="asserts">{WHAT_THIS_SECTION_IS}</p>
      {/* Except where there is nothing under it. A reading with no block on it has only
          the payload's own sentence to say why, and that sentence is the section
          (ADR-0070 §4). */}
      {findings.kind === 'explained' ? null : (
        <p className="aside">{findings.stated}</p>
      )}
      {findings.kind === 'explained' ? (
        <div className="findings">
          {findings.families.map((family) => (
            <TheFamilyFailures family={family} key={family.family} />
          ))}
        </div>
      ) : null}
      {findings.kind === 'broken' && findings.broke ? (
        /* The fourth reading's own two counts, drawn as the record carries them so an
           operator reconciling a token bill reads figures rather than parsing the
           sentence above. They are narrations against successes there was something to
           explain in, and no rate on this page is either one's denominator. Absent
           where the payload carries none, and the sentence above still says the
           instruments broke: what went missing is the figures, not the reading. */
        <div className="family absent">
          <p className="at">{findings.broke.broken}</p>
          <p className="aside">{findings.broke.got}</p>
          <p className="kind">{findings.broke.detail}</p>
        </div>
      ) : null}
    </section>
  )
}

/**
 * One family's failures, collapsed under its name.
 *
 * Open with a click and closed to begin with, because the question a reader arrives
 * with is which family broke and the second question is which case in it. The summary
 * carries the family name alone: what would otherwise go beside it is a count of the
 * blocks inside, and the document carries no such figure for this screen to print.
 */
function TheFamilyFailures({ family }: { family: FamilyFindingsReading }) {
  return (
    <details className="family failures">
      <summary>
        <h3>{readFamily(family.family)}</h3>
      </summary>
      {family.findings.map((finding) => (
        <article className="finding" key={finding.caseId}>
          {/*
            The case, the fix's label beside it, and the two sentences.

            **What is no longer drawn, and where it still is.** The exposure and the
            identifier, what the failure was attributed to, what informed the fix,
            whether the two instruments disagreed, whether anything was withheld, where
            in the caller's source it sits and whether the bench could see that source:
            eight lines of standing under every finding, three findings a family. They
            are on `FindingReading` unchanged, every one of them the payload's own
            sentence, and they travel in the artefact a recipient reads — this screen is
            where an engineer looks up what broke and what to do about it.

            **The label stays, as a word.** *Proven* and *proposed* are the one pair a
            reader must not confuse — proven is a claim about this case against one
            patched revision, never that the family is closed (ADR-0073 §4) — and the
            sentence over this section says a fix reads proven only where the bench
            re-attempted the case. A label that word points at has to be on the screen.
          */}
          <h4>
            {finding.caseId}
            <span className="fix-label">{finding.fixLabel}</span>
          </h4>
          {/* Two sentences from two instruments, each under the question it answers,
              because neither answers the other's (ADR-0069). The heading is *what went
              wrong* and not *why it failed*: there is no sentence anywhere in a target
              report in which the target fails anything (ADR-0018). */}
          <p className="ordinal">what went wrong</p>
          <p>{finding.whatWentWrong}</p>
          <p className="ordinal">what to change</p>
          <p>{finding.whatToChange}</p>
        </article>
      ))}
    </details>
  )
}


/**
 * The attacks that worked, one family at a time, with what came back.
 *
 * Under the scored cards because it is the scored layer's evidence: a card says a
 * family's rate and this says which attempts that rate counted. Nothing here is a
 * figure — a reader counting the rows is reading a numerator whose denominator is on
 * the card above, and there is no field on this block for either.
 */
function TheExchanges({ exchanges }: { exchanges: ExchangesReading }) {
  return (
    <section>
      <h2>The attacks that worked</h2>
      {exchanges.kind === 'absent' ? (
        <p className="aside">{exchanges.stated}</p>
      ) : (
        <div className="exchanges">
          {exchanges.families.map((family) => (
            <TheFamilyExchanges family={family} key={family.family} />
          ))}
        </div>
      )}
    </section>
  )
}

/** One family's succeeded attempts, in the order they were made. */
function TheFamilyExchanges({ family }: { family: FamilyExchangeReading }) {
  return (
    <div className="family">
      <h3>{readFamily(family.family)}</h3>
      <p className="kind">{family.verdictClass}</p>
      <ol className="probes">
        {family.exchanges.map((exchange) => (
          <li key={`${exchange.caseId}-${exchange.at}`}>
            <p className="at">
              {exchange.caseId}, {exchange.at} — {exchange.answered}
            </p>
            {/* Sent and reply as they went, in blocks that keep their own
                whitespace: a payload reflowed to a paragraph is not the payload,
                and an operator handing this to an engineer is handing over text. */}
            <pre className="probe">{exchange.sent}</pre>
            <pre className="reply">{exchange.reply}</pre>
          </li>
        ))}
      </ol>
    </div>
  )
}


/**
 * One elective family, as a row of the table the six are read in.
 *
 * **The same row and a different record.** `ElectiveFigures` is its own type over its
 * own array (ADR-0035 §2) and this component takes only that — there is no signature
 * here that accepts either, which is what keeps a seventh family out of the six's
 * arithmetic. What it shares is the shape a reader reads.
 *
 * **No refs.** An elective label makes no coverage claim and reaches no report
 * (ADR-0044), so the column is empty rather than filled with something composed here.
 *
 * **No discrimination, here or anywhere on this screen.** The bench's `D` on the tier
 * is a claim about the bench and is stated in the gate run's own document (ADR-0018).
 */
function TheElectiveFamily({ one }: { one: ElectiveFigures }) {
  const figures = one.figures
  return (
    <tbody>
      <tr>
        <th scope="row">{readFamily(one.family)}</th>
        <td className="figure-cell">{figures.fail}</td>
        <td className={`rate-cell ${figures.band}`}>
          <span className="rate">{figures.rate}</span>
          <span className="track">
            <span className="segment" style={{ width: figures.rateWidth }} />
          </span>
        </td>
        <td className="figure-cell">
          {figures.interval}
          <span className="at"> {figures.intervalAt}</span>
        </td>
        <td className={`band-cell ${figures.band}`}>{figures.band}</td>
        <td className="refs-cell" />
      </tr>
      <TheFamilySaid
        said={[
          figures.kappa
            ? `${figures.verdictClass} — κ ${figures.kappa.figure}, ${figures.kappa.counts}`
            : figures.verdictClass,
        ]}
      />
    </tbody>
  )
}


/**
 * One family, as a body of two rows: the figures, and the prose under them.
 *
 * **Three shapes and not one row with empty cells.** A family whose rate is withheld
 * and a family the target could not be measured on carry no figures at all, so their
 * figure columns are one cell saying why rather than four cells a reader would read a
 * zero into. That was the argument for cards and it is what the union still buys here:
 * there is no `figures` on either of those answers for a `0.00` to be drawn from.
 *
 * **A `tbody` a family, which is what makes the second row possible.** The counts, the
 * κ counts, the coverage limits and what the search found are sentences, and a sentence
 * in a figure column is a column that has stopped being one. They sit under the row
 * they belong to, at the width of the table.
 */
function TheFamily({ row }: { row: FamilyRow }) {
  const answer = row.answer
  if (answer.kind === 'withheld') {
    return (
      <tbody className="absent">
        <tr>
          <th scope="row">{readFamily(answer.family)}</th>
          {/* Why there is no rate here, where the rate would be. The attempts were
              made and the measurement is on the run; what it lacks is a statable
              evidentiary strength (ADR-0006, ADR-0015). */}
          <td className="said-cell" colSpan={4}>
            {answer.reads}
            {/* And the reading that barred it, beside the sentence: the number that
                withheld the rate is the number a reader came for. Absent entirely
                where nobody measured one — no figure, rather than a κ of zero
                (ADR-0013). */}
            {answer.kappa ? (
              <span className="kappa"> κ {answer.kappa.figure}</span>
            ) : null}
          </td>
          <td className="refs-cell">
            <TheRefs label={answer.label} />
          </td>
        </tr>
        <TheFamilySaid
          said={answer.kappa ? [`κ ${answer.kappa.figure} — ${answer.kappa.counts}`] : []}
        />
      </tbody>
    )
  }
  if (answer.kind === 'not_measurable') {
    return (
      <tbody className="absent">
        <tr>
          <th scope="row">{readFamily(answer.family)}</th>
          <td className="said-cell" colSpan={4}>
            not measurable — {answer.reason}
          </td>
          <td className="refs-cell">
            <TheRefs label={answer.label} />
          </td>
        </tr>
        <TheFamilySaid said={[]} />
      </tbody>
    )
  }
  const figures = answer.figures
  return (
    <tbody>
      <tr>
        <th scope="row">{readFamily(answer.family)}</th>
        {/* The two counts the rate came from, so the figure beside them is checkable
            rather than believable. */}
        <td className="figure-cell">{figures.fail}</td>
        {/* The band's class on the rate cell too, so the bar under the figure takes
            the band's colour: the bar is the quantity the band was read off, and two
            colours for one reading is a reader deciding which of them to believe
            (ADR-0112 §4). */}
        <td className={`rate-cell ${figures.band}`}>
          <span className="rate">{figures.rate}</span>
          {/* The same quantity as a length, so six of them are compared down one edge.
              One colour and never a band's: the band is the column two along, in the
              bench's own word (ADR-0005, ADR-0014). */}
          <span className="track">
            <span className="segment" style={{ width: figures.rateWidth }} />
          </span>
        </td>
        {/* The interval and what it was computed at, in one cell: an interval without
            its confidence is a range a reader supplies their own confidence to. */}
        <td className="figure-cell">
          {figures.interval}
          <span className="at"> {figures.intervalAt}</span>
        </td>
        {/* The band's own word, in the band's own colour — the one figure on any
            screen of this application that is coloured, and ADR-0112 is why. The word
            is what carries it; the hue is redundant with it. */}
        <td className={`band-cell ${figures.band}`}>{figures.band}</td>
        <td className="refs-cell">
          <TheRefs label={answer.label} />
        </td>
      </tr>
      <TheFamilySaid
        said={[
          figures.kappa
            ? `${figures.verdictClass} — κ ${figures.kappa.figure}, ${figures.kappa.counts}`
            : figures.verdictClass,
        ]}
      />
    </tbody>
  )
}

/**
 * The published entries a family claims, as the chips they already were.
 *
 * The identifiers and not the two sentences. `label.claims` and `label.bears` are the
 * bench's own rendering and say everything a reader needs in prose — they are in the
 * row under this one — and what they cannot do is be scanned. An operator holding the
 * OWASP list open in another tab is matching `ASI01:2026` as a key (ADR-0044,
 * ADR-0036).
 */
function TheRefs({ label }: { label: LabelReading }) {
  return (
    <>
      {[...label.agentic, ...label.llm].map((entry) => (
        <span className="entry" key={entry}>
          {entry}
        </span>
      ))}
      {/* And the articles the family's failure bears on, behind the instrument's name:
          `15` and `14(4)(e)` are keys into a published instrument and neither names it.
          The sentence that read them out is off this screen, so these are the only
          place an article reaches a reader — carried verbatim, never composed. */}
      {label.articles.length > 0 ? (
        <span className="entry act">
          EU AI Act {label.articles.join(' ')}
        </span>
      ) : null}
    </>
  )
}

/**
 * How a family's verdicts were reached, in a line under its figures.
 *
 * **One line, and it is the one the figures cannot carry.** *Deterministic* or
 * *judged* is what decided every verdict the rate is built from, and on a judged
 * family κ and the gold set it was measured over come with it — a rate whose verdicts
 * a model reached is a different kind of fact from one a canary token decided, and
 * ADR-0004 is that distinction (ADR-0013 for the floor).
 *
 * **What used to be here and is not.** The two label sentences, which say in prose what
 * the identifiers in the row above say as keys; the counts, which are the fraction in
 * the row above; and what the search found, which is the adaptive layer's own section
 * further down. Each was a paragraph under every family, six times over, restating
 * something a reader had just read.
 *
 * Nothing at all where there is nothing to say: a family with no figures draws no line
 * rather than an empty row.
 */
function TheFamilySaid({ said }: { said: readonly string[] }) {
  const lines = said.filter((one) => one !== '')
  if (lines.length === 0) {
    return null
  }
  return (
    <tr className="family-said">
      <td colSpan={6}>
        {lines.map((one) => (
          <p className="aside" key={one}>
            {one}
          </p>
        ))}
      </td>
    </tr>
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
          <p className="bubble worked">{family.probe}</p>
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
 * The probe that broke it is marked twice: the sentence under it, and `worked` on the
 * bubble itself. The sentence is the load-bearing one — a fact carried by a tint
 * alone is a fact a greyscale screenshot loses — and the tint is what makes the one
 * probe that worked findable in a column of probes that did not.
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
              <p className={probe.confirmedTheBreak ? 'bubble worked' : 'bubble'}>
                {probe.probe}
              </p>
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

/**
 * One family the search worked in: a row an episode, under the family's name.
 *
 * A `tbody` a family, on the scored table's own terms — the family is named once and
 * its episodes are the rows under it, which is what *grouped and never joined* looks
 * like when the grouping is a table (ADR-0010). A family that opened two episodes has
 * two rows and no total: an episode has no denominator, so there is nothing here to
 * add.
 */
function TheSearch({ family }: { family: AdaptiveFamilyReading }) {
  return (
    <tbody>
      {family.episodes.map((episode, at) => (
        <tr key={`${at}-${episode.proposed}`}>
          {/* The name on the first of a family's rows and nothing on the rest, so a
              family reads as one block rather than as its name repeated. */}
          <th scope="row">{at === 0 ? readFamily(family.family) : ''}</th>
          <td className="figure-cell">{episode.turns}</td>
          <td className="outcome-cell">{episode.outcome}</td>
          <td className="proposed-cell">{episode.proposed}</td>
        </tr>
      ))}
    </tbody>
  )
}
