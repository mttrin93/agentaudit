/**
 * The artefacts an engineer can send, and the three files each one is made of.
 *
 * One block per artefact, in the console's own idiom: the reading column and labelled
 * uncoloured facts. Nothing new was invented for this screen; what it adds is one more
 * thing the existing idiom says.
 *
 * **A box says which artefact it is and what to save.** The name, the id and the
 * instant, and the three files as the filenames they will be saved under. The three
 * results, the two claims and the sentence under each of them are in the reading and
 * on no screen: the report screen is the figures and the three files, and what
 * settles whether a document is one to send is a recipient's own run of
 * `scripts/verify`. One box carrying all of it was taller than the window, and a
 * page of four was a document rather than a list of things to send.
 *
 * The command a recipient runs is not on this screen. `reading.command` is still built
 * and still tested, and a recipient is handed a directory rather than this page.
 *
 * **Neither the three results nor the two claims are on this screen.** Every one of
 * them is in the reading, named individually and in the verifier's order, and
 * nothing draws them — no tick, no badge, nothing that reduces three results to one
 * mark (ADR-0005, ADR-0017, spec §75).
 *
 * A box that showed one result and not the other two, or one claim and not the
 * other, would be the inference those decisions exist to prevent. Showing none of
 * them is not that: this is the list you reach a report from, and the name at the
 * head of every box is the link.
 *
 * **Whose check this is, is said where it is acted on.** The bench computed these
 * readings over the bytes it holds, and that is not the check a recipient makes —
 * `checkedBy` says so on every artefact in the reading. This screen is the list a
 * report is reached from.
 *
 * **The files are links because there are routes.** Unlike the gate document, which
 * the gate screen names rather than links, all three of these are served — and each
 * arrives with the filename a verifier reads it by, so a browser saving the three
 * lands them in a directory that verifies with nothing in between. The filename is the
 * link's text for that reason: it is what the saved file will be called.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { benchArtefacts, type ArtefactList } from '../api/bench'

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
              results and claims its clauses are about are on the report each row
              links to.
            */}
            <ul className="artefacts">
              {reading.artefacts.map((artefact) => (
                <li className="artefact" key={artefact.id}>
                  <TheArtefact artefact={artefact} />
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="citation uncited">
            <h3>No signed artefact on the record</h3>
            <p>{reading.statement}</p>
          </div>
        )}
      </section>
    </>
  )
}

/**
 * One artefact: what it is of, where to find it, and the three files it is made of.
 *
 * A name, the id and the instant, and what to save. The three results, the two claims
 * and every sentence under them are on the report: a box that printed the verifier's
 * paragraph under each result, both claims' statements and what each file holds ran
 * past the height of the window on one artefact, and a list of four was a document —
 * the wrong shape for the thing an engineer opens to find the artefact to send.
 *
 * The two claims are not here either. Their labels are their scope — *the whole
 * document*, *the scored layer only* — and scope is the part that must not be inferred
 * (ADR-0010, ADR-0017), which is an argument about the screen a reader takes a figure
 * off: the report, where both are printed in full beside the figures they bound. On a
 * list they were the same two lines under every box.
 *
 * `checkedBy` and `notAQualityClaim` are not printed. Both are still built and still
 * tested on every artefact, and both are on the report the title links to — where a
 * reader who is deciding whether to send this has the figures in front of them, which
 * is where *these are the bench's own readings, not a recipient's check* is the
 * sentence that changes what they do next. Repeated under four boxes on a list it was
 * the longest thing on the page and the thing nobody read twice.
 */
function TheArtefact({ artefact }: { artefact: ArtefactReading }) {
  return (
    <>
      <h3>
        <Link to={artefact.reportPath}>{artefact.target}</Link>
      </h3>
      <p className="aside">
        <code>{artefact.id}</code> — recorded {artefact.recordedAt} —{' '}
        <Link to={artefact.runPath}>the run</Link>
      </p>

      <ul className="files-line">
        {artefact.files.map((file) => (
          <li key={file.filename}>
            <a href={file.path}>
              <code>{file.filename}</code>
            </a>
          </li>
        ))}
      </ul>
    </>
  )
}
