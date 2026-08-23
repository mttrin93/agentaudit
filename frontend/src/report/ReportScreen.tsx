/**
 * The report screen: a finding, and no number the project spent nineteen ADRs
 * refusing to print.
 *
 * It renders from the **signed payload** — the bytes a recipient verifies, fetched
 * from the path the run's own record advertises — and offers all three files for
 * download beside it. What is on this page is what is in the artefact: there is no
 * figure here the payload does not carry, because the screen builds none
 * (`report.ts`).
 *
 * **Verification status is near the top on purpose.** An engineer finds out that
 * the artefact is checkable *before* they send it to a customer, and the answer
 * worth acting on is the one that says do not send this yet — a signature under a
 * key nobody has published, a rendering that no longer matches its digest, an
 * arithmetic that does not re-derive. Three results, always all three, because a
 * screen showing one would let its reader infer the strongest claim from the
 * weakest (ADR-0017). The check was computed by the bench that produced the
 * document, and the screen says so rather than letting a tick stand in for the
 * recipient's own offline run of `scripts/verify.py`.
 *
 * **The declared-and-defeated join is the headline** because it is the strongest
 * finding this bench can produce and the only one that needs no figure to be read:
 * a statement the operator made, crossed with a verdict the bench measured.
 *
 * **Nothing on this page combines two families.** Not a total, not an average, not
 * a rank, not a badge — and the families are laid out as blocks rather than as rows
 * of one table, because a table wants a total row and a stack of blocks has nowhere
 * to put one. The absence is asserted in `report.test.ts` against the payload this
 * screen renders from, structurally: drop a family and every other part of the view
 * is unchanged.
 *
 * **A target has rates, intervals and bands, and passes and fails nothing**
 * (ADR-0018). The bench's own gate is in provenance, in the bench's own words.
 */

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { readFamily } from '../families'
import {
  reportPayload,
  reportVerification,
  runProgress,
  type ReportLocation,
  type TargetReport,
  type Verification,
} from '../api/bench'
import {
  reportView,
  type CheckReading,
  type FamilyAnswer,
  type Headline,
  type ReportView,
} from './report'

/** What this screen is holding: the three things it needs, or why it has none. */
interface Held {
  where: ReportLocation | null
  report: TargetReport | null
  verification: Verification | null
  /** The run's own sentence about why there is no report, carried unedited. */
  noReport: string
  unavailable: string
}

const NOTHING_YET: Held = {
  where: null,
  report: null,
  verification: null,
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
        const [report, verification] = await Promise.all([
          reportPayload(where.path),
          reportVerification(where.verification),
        ])
        if (current) {
          setHeld({ ...NOTHING_YET, where, report, verification })
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

  const view =
    held.report && held.verification
      ? reportView(held.report, held.verification)
      : null
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

      {view && held.where ? <TheReport view={view} where={held.where} /> : null}
    </main>
  )
}

/** The whole report, in the order a reader meets it. */
function TheReport({ view, where }: { view: ReportView; where: ReportLocation }) {
  return (
    <>
      <TheHeadline headline={view.headline} />

      <section>
        <h2>Is this artefact checkable?</h2>
        <p className="consequence">{view.verification.heading}</p>
        <dl className="checks">
          {view.verification.checks.map((check) => (
            <TheCheck check={check} key={check.name} />
          ))}
        </dl>
        <h3>The two claims this artefact carries, printed together</h3>
        <dl className="review">
          {view.verification.claims.map((claim) => (
            <div key={claim.label}>
              <dt>{claim.label}</dt>
              <dd>{claim.statement}</dd>
            </div>
          ))}
        </dl>
        <p className="aside">{view.verification.checkedBy}</p>
        <p className="aside">{view.verification.notAQualityClaim}</p>
      </section>

      <section>
        <h2>The signed artefact</h2>
        <ul>
          <li>
            <a href={where.path}>report.json</a> — the canonical payload, and the
            exact bytes the signature covers
          </li>
          <li>
            <a href={where.rendering}>report.md</a> — the document a human reads,
            bound to those bytes by digest
          </li>
          <li>
            <a href={where.signature}>report.sig</a> — the detached signature
          </li>
        </ul>
        {/* The instruction, and not the argument for it: what made the paragraph
            long was the case for portable evidence, and the three links above are
            that case. */}
        <p className="aside">
          Save all three into one directory under the names they arrive with, then run{' '}
          <code>uv run python -m scripts.verify</code> over it. That check reaches no
          network, needs no credential, and pins the key whose fingerprint this
          repository’s README publishes.
        </p>
      </section>

      <section>
        <h2>What was measured, one family at a time</h2>
        <p>{view.measured.reproducibility}</p>
        <p className="aside">{view.measured.cuts}</p>
        <div className="families">
          {view.measured.answers.map((answer) => (
            <TheFamily answer={answer} key={`${answer.kind}-${answer.family}`} />
          ))}
        </div>
        <p className="consequence">{view.noFigureSpansTwoFamilies}</p>
        <p className="aside">{view.ratesAndBands}</p>
      </section>

      <section>
        <h2>The adaptive layer</h2>
        <p className="consequence">{view.adaptive.label}</p>
        <p>{view.adaptive.statement}</p>
        <p className="aside">{view.adaptive.reproducibility}</p>
        {view.adaptive.episodes.map((episode) => (
          <p key={`${episode.family}-${episode.description}`}>
            <strong>{readFamily(episode.family)}</strong> — {episode.outcome}, over{' '}
            {episode.turns}. {episode.description}.
          </p>
        ))}
        <p className="aside">
          Routes are described in prose and never as payload text, so this report is
          not a working exploit somebody can lift out of it (ADR-0008). A turn is not
          an attempt: nothing in this section joins a count above it.
        </p>
      </section>

      <section>
        <h2>What this bench does not test at all</h2>
        <p>{view.coverage.statement}</p>
        <dl className="review">
          {view.coverage.gaps.map((gap) => (
            <div key={gap.category}>
              <dt>{gap.category}</dt>
              <dd>{gap.reason}</dd>
            </div>
          ))}
        </dl>
      </section>

      <TheProvenance view={view} />
    </>
  )
}

/** The headline: declared, and defeated. */
function TheHeadline({ headline }: { headline: Headline }) {
  return (
    <section>
      <h2>{headline.heading}</h2>
      <p className="consequence">{headline.statement}</p>
      {headline.defeated.map((defeat) => (
        <div className="defeat" key={defeat.control}>
          <h3>
            {defeat.control} — claims {readFamily(defeat.family)}
          </h3>
          <p>{defeat.stated}</p>
          <p className="aside">Broken by {defeat.brokenBy.join(', ')}.</p>
        </div>
      ))}
      {headline.standing.length ? (
        <>
          <h3>Declared, and not defeated</h3>
          <ul>
            {headline.standing.map((control) => (
              <li key={control.control}>{control.stated}</li>
            ))}
          </ul>
        </>
      ) : null}
      {headline.absent.length ? (
        <>
          <h3>On the checklist, and not declared</h3>
          {/*
            The names, and the sentence once.

            `stated` is the payload's own line and it is the same twenty words for
            every control — *the checklist asks about this control and this target did
            not claim it. An absence is not a finding and nothing was attempted against
            it* — which read four times over is a paragraph that hides the four names
            inside it. The signed field is unchanged; what this screen prints is the
            list it is a list of, under the sentence that is true of all of them.
          */}
          <p className="aside">
            The checklist asks about these and this target claimed none of them. An
            absence is not a finding: nothing was attempted against any of them.
          </p>
          <ul className="names">
            {headline.absent.map((control) => (
              <li key={control.control}>{control.control}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  )
}

/** One of the three results, under the name the verifier gave it. */
function TheCheck({ check }: { check: CheckReading }) {
  return (
    <div className={check.held ? 'check' : 'check did-not-hold'}>
      <dt>
        {check.name}: <strong>{check.outcome}</strong>
      </dt>
      <dd>{check.statement}</dd>
    </div>
  )
}

/**
 * One family, as a block.
 *
 * Three shapes rather than one row with empty cells: a family whose rate is
 * withheld and a family the target could not be measured on carry no figures at
 * all, so there is no cell for a `0.00` to be drawn into. Blocks rather than a
 * table for the same reason the two cost figures are blocks — a table wants a total
 * row, and this stack has nowhere to put one.
 */
function TheFamily({ answer }: { answer: FamilyAnswer }) {
  if (answer.kind === 'withheld') {
    return (
      <div className="family absent">
        <h3>{readFamily(answer.family)}</h3>
        <p className="at">rate not published — {answer.reason}</p>
        <p>{answer.stated}</p>
        <p className="aside">{answer.note}</p>
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
      <p>
        <span className="calls">{figures.rate}</span>
        <span className="kind">{figures.counts}</span>
      </p>
      <p>
        Interval: <strong>{figures.interval}</strong>. The interval and never the
        point estimate is what the band is read from.
      </p>
      <p>
        Band: <strong>{figures.band}</strong> — {figures.bandReads}
      </p>
      <p className="aside">{figures.cuts}</p>
      <p className="aside">Verdicts here are {figures.verdictClass}.</p>
      <p className="aside">{figures.instrument}</p>
      <p className="aside">{figures.discrimination}</p>
      {figures.limits.map((limit) => (
        <p className="aside" key={limit.identifier}>
          {limit.identifier}: these cases test one case within it. They do not test{' '}
          {limit.doesNotTest}.
        </p>
      ))}
    </div>
  )
}

/** How this artefact was made — and nothing about what it found. */
function TheProvenance({ view }: { view: ReportView }) {
  const provenance = view.provenance
  return (
    <section>
      <h2>How this report was made</h2>
      <dl className="review">
        <div>
          <dt>artefact</dt>
          <dd>{view.artefact}</dd>
        </div>
        <div>
          <dt>attested by</dt>
          <dd>
            {provenance.attestedBy}, recorded {provenance.recordedAt}
          </dd>
        </div>
        <div>
          <dt>endpoint</dt>
          <dd>
            {provenance.endpointDigest} — as a digest, because a live URL that
            answers jailbreak payloads is not a thing to write into a document that
            travels.
          </dd>
        </div>
        {provenance.models.map((model) => (
          <div key={model.instrument}>
            <dt>{model.instrument} model</dt>
            <dd>{model.model}</dd>
          </div>
        ))}
        <div>
          <dt>library</dt>
          <dd>{provenance.library}</dd>
        </div>
        {provenance.callsSpent.map((spent) => (
          <div key={spent.layer}>
            <dt>{spent.layer} layer</dt>
            <dd>{spent.calls} calls on the wire</dd>
          </div>
        ))}
      </dl>
      <p className="aside">
        Reported per layer and never as one figure: a blended number hides which half
        of the run spent the operator’s budget.
      </p>

      <h3>What the operator attested to</h3>
      <ul>
        {provenance.statements.map((statement) => (
          <li key={statement}>{statement}</li>
        ))}
      </ul>

      <h3>The rule these figures were measured under</h3>
      <ul>
        {provenance.rule.map((part) => (
          <li key={part}>{part}</li>
        ))}
      </ul>

      <h3>The bench’s own gate, cited as provenance</h3>
      <blockquote>{provenance.gate.statement}</blockquote>
      <p className="aside">{provenance.gate.note}</p>

      <h3>What has not been validated</h3>
      <p className="aside">{provenance.formatUnvalidated}</p>
    </section>
  )
}
