/**
 * The artefacts an engineer can send, with the three results over each one.
 *
 * One block per artefact, in the console's own idiom: the reading column, labelled
 * uncoloured facts, `.checks` and `.check.did-not-hold` for the three results, the
 * three files as links under the names they arrive with, and `.command` for the line
 * a recipient pastes. Nothing new was invented for this screen; what it adds is one
 * more thing the existing idiom says.
 *
 * **A result is marked by its name and a border, never by a colour alone.** Every
 * check prints the verifier's own outcome — `signature_valid`, `unsigned`,
 * `signed_by_another_key` — in the same element as the class that draws it, so a
 * reader who cannot tell the two surfaces apart reads the same fact. A coloured tick
 * is exactly the badge the report refuses (ADR-0005, spec §75), and there is no
 * element here that reduces the three results to one mark.
 *
 * **All three, always, and the two claims under them.** The order is the verifier's:
 * signature, binding, arithmetic — then integrity over the whole document and
 * re-derivability over the scored layer alone, as two statements. A row that showed
 * one result would let its reader infer the strongest claim from the weakest.
 *
 * **Every row says whose check it is.** The bench computed these readings over the
 * bytes it holds; the command below is what makes the answer a recipient's. Said per
 * artefact rather than once in a footer, because what circulates is one block.
 *
 * **The files are links because there are routes.** Unlike the gate document, which
 * the gate screen names rather than links, all three of these are served — and each
 * arrives with the filename a verifier reads it by, so a browser saving the three
 * lands them in a directory that verifies with nothing in between.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { benchArtefacts, type ArtefactList } from '../api/bench'
import type { CheckReading } from '../report/report'

import {
  artefactsReading,
  type ArtefactReading,
  type ArtefactsReading,
} from './artefacts'

/** What this screen is holding: the artefacts, or why it has none of them. */
interface Held {
  list: ArtefactList | null
  unavailable: string
}

const NOTHING_YET: Held = { list: null, unavailable: '' }

export function ArtefactsScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const list = await benchArtefacts()
        if (current) {
          setHeld({ list, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setHeld({ list: null, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  return (
    <main className="screen">
      {/*
        The name of the screen and nothing over or under it.
        The eyebrow said which app this is on a page inside the app, and the line under
        the title said what the screen answers in five clauses — one of them the way
        back to the bench, which the rail is already showing. Read in order they were a
        title with a title above it and a paragraph below it, and the artefacts were
        below that. `WHAT_THIS_SCREEN_ANSWERS` is still built and still exported.
      */}
      <header>
        <h1>Signed artefacts</h1>
      </header>

      {held.unavailable ? (
        <section>
          <h2>This bench did not answer for its artefacts</h2>
          <div className="citation uncited" role="alert">
            <h3>The list could not be read</h3>
            <p>{held.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that has signed nothing: what is unknown
              here is what it would have listed, and nothing on this page should be
              read as either answer.
            </p>
          </div>
        </section>
      ) : held.list === null ? (
        <section>
          <p className="aside">Reading the signed artefacts on the record…</p>
        </section>
      ) : (
        <TheArtefacts reading={artefactsReading(held.list)} />
      )}
    </main>
  )
}

/**
 * The artefacts, or the stated fact that there are none, and then the command.
 *
 * An unordered list rather than a table, for the reason the run list is one: a table
 * of results grows a column that summarises them, and a stack of blocks has nowhere
 * to put one.
 */
function TheArtefacts({ reading }: { reading: ArtefactsReading }) {
  return (
    <>
      {/*
        No heading over the list. `Signed artefacts` at the head of the page said it,
        and a second heading saying it again in the bench's voice put a line between the
        title and the first thing under it. The section below keeps its own heading,
        because what it holds is not artefacts.
      */}
      <section>
        {reading.listed ? (
          <>
            {/*
              The route's sentence about the list is not printed over it.
              Six clauses, and every one of them a thing the list shows by being the
              list: three results per row named individually, two claims stated apart,
              three files under the names a verifier reads, no combined mark, no figure,
              and a run that was never signed absent because it has no artefact. A
              paragraph asserting all six sat between the heading and the first
              artefact. `reading.statement` is still built and still tested, and the
              claims the last two clauses are about are on every row below.
            */}
            <ul className="artefacts">
              {reading.artefacts.map((artefact) => (
                <li className="artefact" key={artefact.id}>
                  <TheArtefact artefact={artefact} />
                </li>
              ))}
            </ul>
            <p className="aside">{reading.checkedByTheBench}</p>
          </>
        ) : (
          <div className="citation uncited">
            <h3>No signed artefact on the record</h3>
            <p>{reading.statement}</p>
          </div>
        )}
      </section>

      <section>
        <h2>How a recipient checks one</h2>
        <pre className="command">{reading.command}</pre>
        <p>{reading.commandStatement}</p>
      </section>
    </>
  )
}

/** One artefact: what it is of, its three results, its two claims, its three files. */
function TheArtefact({ artefact }: { artefact: ArtefactReading }) {
  return (
    <>
      <h3>
        <Link to={artefact.reportPath}>{artefact.target}</Link>
      </h3>
      <p className="standing">Signed for the run recorded {artefact.recordedAt}</p>
      <p className="aside">
        <code>{artefact.id}</code> — <Link to={artefact.runPath}>the run</Link>
      </p>

      <p className="consequence">{artefact.verification.heading}</p>
      <dl className="checks">
        {artefact.verification.checks.map((check) => (
          <TheCheck check={check} key={check.name} />
        ))}
      </dl>

      <h4>The two claims this artefact carries, printed together</h4>
      <dl className="review">
        {artefact.verification.claims.map((claim) => (
          <div key={claim.label}>
            <dt>{claim.label}</dt>
            <dd>{claim.statement}</dd>
          </div>
        ))}
      </dl>

      <h4>The three files, under the names a verifier reads them by</h4>
      <ul className="files">
        {artefact.files.map((file) => (
          <li key={file.filename}>
            <a href={file.path}>
              <code>{file.filename}</code>
            </a>{' '}
            — {file.holds}
          </li>
        ))}
      </ul>

      <p className="aside">{artefact.verification.checkedBy}</p>
      <p className="aside">{artefact.verification.notAQualityClaim}</p>
    </>
  )
}

/**
 * One of the three results: its name, its outcome, and the verifier's sentence.
 *
 * The outcome is printed in the same element the class draws, so the fact is carried
 * by words and the border only repeats it. *Unsigned* and *signed by a key you did
 * not pin* are different facts about the sender, and one cross would show them
 * identically — which is why there is no cross.
 */
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
