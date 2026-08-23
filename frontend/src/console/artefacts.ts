/**
 * Every signed artefact this bench has produced, each with all three of its results.
 *
 * An engineer with several runs behind them has one question here: which of these
 * can I send a customer? The answer worth serving is the one that says **not this
 * one, not yet** — a signature under a key nobody published, a document edited after
 * it was bound — because the alternative is finding out when the recipient runs the
 * script. So this is the list, and every row carries the reading rather than a mark
 * standing in for it.
 *
 * **All three results on every row, always.** A row showing the signature alone
 * would let its reader infer re-derivability from integrity, which is the one
 * inference ADR-0017 exists to prevent. The reading is `verificationReading`, which
 * lives in `report/report.ts` and is now read only here — the report screen shows
 * what was measured and links to the three files, and no screen draws the three
 * results. One wording for them, so nothing has to disagree for a screen to state a
 * property nobody checked.
 *
 * **The two claims stay two.** Integrity is over the whole document;
 * re-derivability is over the **scored layer alone**, because the adaptive layer is
 * recorded and not reproducible and a valid signature over it is a claim about its
 * bytes (ADR-0010, ADR-0017). They arrive as two labelled statements and this module
 * has nowhere to put a third that summarises them.
 *
 * **A failure is named, never marked.** *Unsigned* and *signed by a key you did not
 * pin* are different facts about the sender and they send a reader to different
 * places, so what a row carries is the verifier's own outcome name and its sentence.
 * There is no tick, no badge and no colour on a result anywhere in this module: the
 * only thing a component is given to draw with is `held`, which is redundant with the
 * outcome name beside it (`.check.did-not-hold` in the stylesheet — a border and a
 * name, never a hue standing alone).
 *
 * **It is the bench's own check and every row says so.** `checkedBy` is carried per
 * artefact rather than once at the top, because what circulates is a row: a sender's
 * word for their own document is the thing a signature exists to replace.
 *
 * **The three files are offered under the names a verifier already knows.** The
 * filenames come off the wire — `report.json`, `report.md`, `report.sig` — and nothing
 * here composes one, because `scripts/verify.py` is handed a directory and told
 * nothing else. A file offered under a name of this screen's invention would be
 * portable evidence a recipient's tooling cannot find.
 *
 * **Nothing here is a figure.** No rate, no band, no verdict, no count of artefacts
 * and no mark over the three results: every leaf of this view is a string or a
 * boolean, which is the structural form of *no composite figure* (ADR-0005, D12).
 */

import type { ArtefactList, ArtefactRow } from '../api/bench'
import {
  verificationReading,
  type Settled,
  type VerificationReading,
} from '../report/report'

import { reportPath, runPath } from './rail'
import { recordedIn } from './runs'

export const WHAT_THIS_SCREEN_ANSWERS =
  'Every signed artefact this bench has produced, with the three verification ' +
  'results over each one named individually. An artefact is three files — the ' +
  'canonical payload the signature covers, the document a human reads, and the ' +
  'detached signature — and this screen is where you learn one is still checkable ' +
  'before a customer tells you it is not.'

export const THE_RESULTS_ARE_THE_BENCH_S_OWN =
  'These readings were computed by this bench, over the bytes it holds. They are ' +
  'not the check a recipient makes: run the command below over the three files and ' +
  'the answer is theirs rather than ours.'

export const NO_ARTEFACTS_YET =
  'This bench has produced no signed artefact. A run has to complete before there ' +
  'is a document to send, and a run that completed on a bench with no signing key ' +
  'has no artefact at all — that run is on the list of runs, and its own report ' +
  'route names the absence rather than serving something unsigned. Nothing here is ' +
  'a statement about any target.'

export const SAVE_ALL_THREE_UNDER_THESE_NAMES =
  'Save all three files into one directory under the names they arrive with, then ' +
  'run the command over that directory. It reaches no network, needs no credential ' +
  'and pins the key whose fingerprint this repository’s README publishes — which is ' +
  'what makes this evidence portable rather than a screenshot. A payload with no ' +
  'signature beside it is the part that cannot be checked on its own.'

/** One of the three files, at the path that serves it and under its own name. */
export interface FileReading {
  /** The name a verifier reads it by, off the wire and never composed here. */
  filename: string
  /** Where this bench serves it. A link a browser saves under `filename`. */
  path: string
  /** What is in it, so three files are not read as three copies of one. */
  holds: string
}

/**
 * One signed artefact as this screen shows it.
 *
 * The run it came from is reachable two ways — the run itself and the report screen
 * that renders it — because an engineer who has decided this is the artefact to send
 * usually wants to read it first. Neither link is a figure and neither is a verdict.
 */
export interface ArtefactReading {
  /** The run that produced it, as the bench issued the id. */
  id: string
  /** The operator's own name for the endpoint. Never the endpoint (ADR-0008). */
  target: string
  /**
   * When the run went on the record, as a date and a clock time in UTC.
   *
   * The run list's own reading of the same instant (`runs.recordedIn`), because it is
   * the same instant off the same record: two screens naming one moment in two forms
   * is two moments to the person reading both.
   */
  recordedAt: string
  /** Where that run's screen is. */
  runPath: string
  /** Where its report is rendered. The link a recipient may already hold. */
  reportPath: string
  /** The three files, in the order a verifier reads them. */
  files: FileReading[]
  /**
   * How it settled, in one word, for a list that shows no sentence.
   *
   * Three words and not two: *not established* is its own fact — nothing was
   * contradicted and not all three were proved — and a list that showed it as either
   * of its neighbours would be doing the inference ADR-0017 exists to prevent. It is a
   * word and never a mark, and the sentence behind it is on `verification.heading`,
   * which the artefact's own screen prints.
   */
  settledInAWord: string
  /**
   * The three results, the two claims, and whose check this was.
   *
   * Three outcomes named individually, two claims stated separately, and
   * `checkedBy` on every one of them. Carried per row and drawn by no screen: what
   * settles it for a recipient is their own run of `scripts/verify`.
   */
  verification: VerificationReading
}

/**
 * The three outcomes, each in the shortest words that still name it.
 *
 * *Did not verify* rather than *failed*: what failed is one of three named results,
 * and this word says only that the artefact is not one to send. Which result failed
 * is in the row's own reading and in `scripts/verify` over the three files; no word
 * here stands in for reading it.
 */
const SETTLED_IN_A_WORD: Record<Settled, string> = {
  verified: 'Verified',
  contradicted: 'Did not verify',
  not_established: 'Not established',
}

/**
 * The artefacts, or the stated fact that there are none.
 *
 * Two shapes of one union, as the gate citation and the run list are: a bench that
 * has signed nothing says so in a sentence rather than drawing the head of a list
 * over nothing. The command is on both shapes, because how a recipient checks an
 * artefact is true whether or not this bench has produced one yet.
 */
export type ArtefactsReading =
  | {
      listed: true
      artefacts: ArtefactReading[]
      statement: string
      checkedByTheBench: string
      command: string
      commandStatement: string
    }
  | {
      listed: false
      statement: string
      command: string
      commandStatement: string
    }

/**
 * The signed artefacts on the record, as this screen reads them.
 *
 * The order is the route's — most recently recorded first — and it is not re-sorted
 * here: the bench decided which artefact is the most recent one, and a screen that
 * sorted the rows again would be a second opinion on it. Nothing is filtered either:
 * an artefact whose signature did not verify is the one an engineer most needs to
 * see, so it is on the list with its outcome named.
 */
export function artefactsReading(list: ArtefactList): ArtefactsReading {
  if (list.artefacts.length === 0) {
    return {
      listed: false,
      statement: NO_ARTEFACTS_YET,
      command: list.verify_command,
      commandStatement: SAVE_ALL_THREE_UNDER_THESE_NAMES,
    }
  }
  return {
    listed: true,
    artefacts: list.artefacts.map(artefactReading),
    statement: list.statement,
    checkedByTheBench: THE_RESULTS_ARE_THE_BENCH_S_OWN,
    command: list.verify_command,
    commandStatement: SAVE_ALL_THREE_UNDER_THESE_NAMES,
  }
}

/**
 * One row.
 *
 * The verification is passed whole into `verificationReading`, so the three results,
 * the two claims and the sentence naming whose check it is arrive here in one
 * wording — and a row cannot end up with fewer than three results without that
 * function losing one.
 */
function artefactReading(row: ArtefactRow): ArtefactReading {
  const verification = verificationReading(row.verification)
  return {
    id: row.run_id,
    target: row.target,
    recordedAt: recordedIn(row.recorded_at),
    runPath: runPath(row.run_id),
    reportPath: reportPath(row.run_id),
    files: row.files.map((file) => ({
      filename: file.filename,
      path: file.path,
      holds: file.holds,
    })),
    settledInAWord: SETTLED_IN_A_WORD[verification.settled],
    verification,
  }
}
