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
  exchangesReading,
  reportView,
  routeReading,
  type AdaptiveFamilyReading,
  type DiscoveriesReading,
  type EpisodeRouteReading,
  type ExchangesReading,
  type FamilyBreakReading,
  type FamilyExchangeReading,
  type FamilyFindingsReading,
  type FamilyRow,
  type FindingsView,
  type LabelReading,
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
  /** The run's own sentence about why there is no report, carried unedited. */
  noReport: string
  unavailable: string
}

const NOTHING_YET: Held = {
  where: null,
  report: null,
  episodes: null,
  attempts: null,
  counts: {},
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
        <TheReport
          view={view}
          where={held.where}
          episodes={held.episodes}
          attempts={held.attempts}
          counts={held.counts}
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
  counts,
}: {
  view: ReportView
  where: ReportLocation
  episodes: RunEpisodes | null
  attempts: RunAttempts | null
  counts: Record<string, string>
}) {
  return (
    <>
      <section>
        <h2>The scored layer, one family at a time</h2>
        <div className="families per-family">
          {view.rows.map((row) => (
            <TheFamily
              row={row}
              counted={counts[row.family] ?? ''}
              key={`${row.answer.kind}-${row.family}`}
            />
          ))}
        </div>
      </section>

      <TheFailures findings={view.findings} />

      {attempts ? <TheExchanges exchanges={exchangesReading(attempts)} /> : null}

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
 * Each failure the bench explained, and the fix written for it.
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
      <h2>Each failure the bench explained, and the fix written for it</h2>
      {/* Which of the four readings this run holds, as the name the payload carries
          and not only as the sentence under it. A reader telling the four apart by
          prose alone stops telling them apart the day the prose is reworded, which is
          why the artefact carries a name off a closed set at all (ADR-0070 §4) — and
          a reading this app has no shape for reaches the page as itself. */}
      <p className="kind">{findings.reading}</p>
      {/* Who wrote these sentences, above them and not in a legend: a fact carried
          somewhere else is a fact a screenshot loses. */}
      <p className="consequence">{findings.label}</p>
      <p className="aside">{findings.stated}</p>
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
          <h4>{finding.caseId}</h4>
          <p className="kind">
            {finding.identifier} — {finding.exposure}
          </p>
          {/* What this break is read against, in the record's own sentence: whether a
              control claiming this family was declared, and whether it was broken.
              Never rebuilt from the three fields under it (ADR-0068 §3). */}
          <p className="label">{finding.attributedCause}</p>
          {/* Two sentences from two instruments, each under the question it answers,
              because neither answers the other's (ADR-0069). The heading is *what went
              wrong* and not *why it failed*: there is no sentence anywhere in a target
              report in which the target fails anything (ADR-0018). */}
          <p className="ordinal">what went wrong</p>
          <p>{finding.whatWentWrong}</p>
          <p className="ordinal">what to change</p>
          <p>{finding.whatToChange}</p>
          {/* And what informed it, which is the whole point of drawing it here: a
              reader has to be able to tell a fix derived from their own transcript
              from one derived from a corpus, and on run one *nothing informed this* is
              a stated absence rather than blank space (ADR-0019). */}
          <p className="aside">{finding.informedBy}</p>
          {/* Empty except where the disclosure rule replaced a sentence, which the
              sentence standing in its place already says: this is the countable half
              beside it, in the payload's own names (ADR-0070 §2c). */}
          {finding.withheld ? (
            <p className="aside">withheld — {finding.withheld}</p>
          ) : null}
          <p className="aside">{finding.disagreement}</p>
          {/* Where it is, when the bench ran where the code is — an Action in the
              caller's own repository, which is the only place the two are on one disk
              (ADR-0066, ADR-0071). Most runs draw the sentence alone, and it says the
              bench could not see this target's source rather than leaving a gap a
              reader would take for a clean result. The compact `path:line` is drawn
              only where there is one, and it is the payload's own string. */}
          {finding.location ? (
            <p className="location">{finding.location}</p>
          ) : null}
          <p className="aside">{finding.sourceAnchor}</p>
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
 * What a family is labelled with, under the name and above whatever the run made of
 * it.
 *
 * The article first, because it is the claim this project makes and the published
 * entries are a secondary label on somebody else's list (ADR-0002). Both are the
 * payload's own sentences printed verbatim: a screen that rebuilt either from the
 * identifier lists beside them would hold a second copy of a legal mapping in
 * TypeScript, and two copies of one claim are two claims the day one is edited
 * (ADR-0044). Beside the family name and never instead of it — `readFamily` still
 * does one thing, and this is a second column rather than a second vocabulary.
 *
 * Drawn on all three card shapes, the two that carry no figure included: a withheld
 * rate says the evidence behind it cannot be stated and an unmet precondition says
 * nothing was measured, and neither says the duty went away.
 */
function TheLabel({ label }: { label: LabelReading }) {
  return (
    <>
      <p className="label">{label.bears}</p>
      <p className="label">{label.claims}</p>
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
function TheFamily({ row, counted }: { row: FamilyRow; counted: string }) {
  const answer = row.answer
  if (answer.kind === 'withheld') {
    return (
      <div className="family absent">
        <h3>{readFamily(answer.family)}</h3>
        <TheLabel label={answer.label} />
        {/* Why there is no rate here, where the rate would be. What this card does
            not state is the figure with its interval and its band: the attempts were
            made and the measurement is on the run, and what it lacks is a statable
            evidentiary strength (ADR-0006, ADR-0015). It said none of that until now
            — the counts alone read as a family nobody attacked. */}
        <p className="at">{answer.reads}</p>
        {/* And the reading that barred it, in the place and the shape a published
            family carries its κ, because the number that withheld the rate is the
            number a reader came for. Absent entirely where nobody measured one: no
            figure, rather than a κ of zero (ADR-0013). */}
        {answer.kappa ? (
          <ul className="rates">
            <li>
              <span className="who">κ</span>{' '}
              <span className="rate">{answer.kappa.figure}</span>
            </li>
          </ul>
        ) : null}
        {/* Empty where the process no longer holds the run, which is every run after
            a restart. */}
        {counted ? <p className="aside">{counted}</p> : null}
        {answer.kappa ? <p className="aside">{answer.kappa.counts}</p> : null}
        <TheDiscoveries discoveries={row.discoveries} />
      </div>
    )
  }
  if (answer.kind === 'not_measurable') {
    return (
      <div className="family absent">
        <h3>{readFamily(answer.family)}</h3>
        <TheLabel label={answer.label} />
        <p className="at">not measurable — {answer.reason}</p>
        <p>{answer.stated}</p>
        <p className="aside">{answer.note}</p>
        <TheDiscoveries discoveries={row.discoveries} />
      </div>
    )
  }
  const figures = answer.figures
  return (
    <div className="family">
      <h3>{readFamily(answer.family)}</h3>
      <TheLabel label={answer.label} />
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
      <TheDiscoveries discoveries={row.discoveries} />
    </div>
  )
}

/**
 * What the search found in this family, under what the suite measured.
 *
 * **Nothing at all where the search never worked in this family**, which is the
 * empty cell #77 asks for: a card that printed *0 episodes* would say the attacker
 * tried and found nothing, and the same refusal is why a family with no attempts
 * carries no rate.
 *
 * **Not styled as a figure.** The count is drawn in the card's plain aside type and
 * not on the `rate-line`; it takes no tint and no class of its own, and the word
 * beside it is *discoveries* — the idiom `SettingsScreen.tsx` states, *colour
 * carries identity and order and
 * never a judgement*, applied to the one number on this screen a reader could
 * mistake for a worse rate (ADR-0056). The sentence saying an episode has no
 * denominator is on the card rather than in a legend, because a fact carried
 * somewhere else is a fact a screenshot loses.
 */
function TheDiscoveries({
  discoveries,
}: {
  discoveries: DiscoveriesReading | null
}) {
  if (discoveries === null) {
    return null
  }
  return (
    <>
      <p className="aside">
        discoveries — {discoveries.broke}, {discoveries.censored}
      </p>
      <p className="aside">{discoveries.note}</p>
    </>
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
        </div>
      ))}
    </div>
  )
}
