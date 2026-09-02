/**
 * `GET /artefacts` — what this bench has published, and whether each still verifies.
 *
 * Its own module in #14's split by API area. The smallest of them, and it stays its
 * own module rather than folding into `report.ts` because the two answer different
 * questions: a report is one document a reader was given, and this is the list a
 * deployment holds.
 */

import type {
  Verification,
} from './contracts'
import {
  fetched,
} from './http'


/** Where every signed artefact this bench has produced is listed. */
export const ARTEFACTS_PATH = '/artefacts'

/**
 * One of the three files an artefact is, under the name a verifier reads it by.
 *
 * The filename is the recipient's contract and not decoration: `scripts/verify.py`
 * is handed a directory and told nothing else, so a client that saves these three
 * responses under the names they arrive with has a directory that verifies.
 */
export interface ArtefactFile {
  filename: string
  path: string
  holds: string
}

/**
 * One signed artefact on the record, with the reading over its three files.
 *
 * There is no field here that marks the three results as good or bad, no band, no
 * rate and no verdict: an artefact is a document about a target, and a figure
 * lifted out of one onto a list would arrive without the denominator that was
 * printed beside it.
 */
export interface ArtefactRow {
  run_id: string
  target: string
  recorded_at: string
  files: ArtefactFile[]
  verification: Verification
}

/**
 * Every signed artefact the bench has produced, and nothing computed over them.
 *
 * No count and no totals block: the route returns rows and never a summary of
 * them. `verify_command` is on the list rather than on each row because the
 * verifier takes a directory and not a run id — one command, whatever artefact was
 * saved into it.
 */
export interface ArtefactList {
  artefacts: ArtefactRow[]
  statement: string
  verify_command: string
}

/**
 * The signed artefacts this bench has produced, each with its three results.
 *
 * A read, and a bench that has signed nothing answers with no rows rather than
 * with a refusal: a fresh deployment is in exactly that state. Every row carries
 * the whole reading the per-run verification route serves — three outcomes by
 * name, both claims, and whose check it is — because a row showing one result
 * would be a reader inferring the other two (ADR-0017).
 */
export async function benchArtefacts(): Promise<ArtefactList> {
  return (await fetched(ARTEFACTS_PATH, 'list of signed artefacts')) as ArtefactList
}
