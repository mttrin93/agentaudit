/**
 * The front door's one claim: what this instrument is, and whether it was validated.
 *
 * A console opening on a registration form asks an engineer for an endpoint before
 * telling them what will be done to it, and — worse — before telling them whether
 * the instrument about to measure their agent has ever been shown to measure
 * anything. So the root screen states the bench's own gate citation: the outcome,
 * the date it was decided, and the library version it was earned at, out of the
 * same typed citation the bench already carries into the provenance block of every
 * report it signs (`GET /bench/gate`, ADR-0018).
 *
 * **The subject is the bench, and every sentence here says so.** The gate is a
 * contrast between three agents of known construction; it has no definition for one
 * target, and there is no sentence in this module in which a target passes or fails
 * anything. What circulates is a screenshot of one region, so the claim about the
 * subject travels inside the region rather than sitting in a caption above it.
 *
 * **The absence is a statement, in the same place and with the same weight.** A
 * bench citing no gate run is a fact about the bench, not a blank in a table: this
 * module answers it with a heading and a sentence and with *no* facts and *no*
 * document, so there is nowhere for a screen to draw an empty outcome that a reader
 * would take for a gate the bench failed. Two shapes of one union, for the reason
 * the report's three kinds of nothing are three members of one (`report.ts`).
 *
 * **Both files are named and neither is parsed.** The per-family rates and the
 * per-family `D` of a gate run are not on the citation; what the citation carries
 * are two addresses — the dated document a person reads, and the **gate run
 * record** that holds the same run as fields (ADR-0023). This screen shows what the
 * citation carries and names the rest, in that order: the record first, because it
 * is the one a reader after the arithmetic wants. A screen that read the bench's own
 * prose output would break on a rewording, and the record is why it never has to.
 *
 * **The wording is the console's, and the facts are the citation's.** The citation's
 * own two sentences are written for a provenance block — they say *the figures
 * above* and *this report*, which are true under a report's figures and false on a
 * front door with none — so the sentences here are this screen's and every fact in
 * them is read off the typed citation. That is the same division `report.ts` makes
 * for a band: the payload's wording is right where the payload is read, and a screen
 * that restates it says so.
 *
 * **Nothing here is a figure about a target.** There is no rate, no interval, no
 * band, no verdict and no count of runs in this module, and the type has nowhere to
 * put one.
 */

import type { GateCitation } from '../api/bench'

export const WHAT_THIS_INSTRUMENT_IS =
  'AgentAudit attacks an AI agent you own across six families of failure, at ten ' +
  'attempts per case, and reports each family over its own denominator. It ' +
  'produces rates, intervals and bands per family, and no total over them: the ' +
  'six families measure six different things, and a single figure across them ' +
  'would be one the bench does not stand behind.'

export const WHY_THE_GATE_IS_HERE =
  'Before a rate is worth reading, the instrument that produced it has to have ' +
  'been shown to discriminate. The bench puts a stated, falsifiable rule to three ' +
  'agents of its own construction — one hardened, one weak, one trivial — and that ' +
  'rule can answer that the bench measures nothing. What it last answered is below.'

export const A_FACT_ABOUT_THE_BENCH =
  'This is a fact about the bench and never a verdict about a target. The gate is ' +
  'decided on the contrast between three agents of known construction, so it has ' +
  'no definition for a single agent: a target of yours has rates, intervals and ' +
  'bands, and passes and fails nothing (ADR-0018).'

export const THE_DOCUMENT_IS_NAMED_AND_NEVER_PARSED =
  'The gate run wrote its own document, with every per-family rate and every ' +
  'discrimination score in it, so that a reader can re-derive the outcome rather ' +
  'than trust it. Those figures are in that document and not in this citation: ' +
  'this screen names the document and does not read it.'

export const THE_RECORD_IS_THE_SAME_RUN_AS_FIELDS =
  'The same gate run as fields, written beside the document: each agent’s rate on ' +
  'each family, each family’s discrimination score, and the rule they were decided ' +
  'under. This is where a reader who wants the arithmetic goes, and it is why ' +
  'nothing here parses prose to find it.'

/**
 * Where a gate run's own document is, for a reader who wants the arithmetic.
 *
 * A path and a sentence, and deliberately not a URL: the citation carries where the
 * document was written and this bench serves no route that hands it over, so the
 * console names it. Turning it into a link is the gate screen's question, and it
 * needs a route before it is an answer.
 */
export interface CitedDocument {
  /** The path the citation carries, verbatim. Nothing here opens it. */
  path: string
  statement: string
}

/**
 * Where the same gate run is written down as fields, for the figures the citation
 * does not carry.
 *
 * The **gate run record** the citation names (ADR-0023). The same shape as the
 * document above and deliberately so: two addresses, one sentence each, and this
 * screen opens neither. It is the answer to the question the document could only be
 * given by parsing it — and a parser over a document written for a person is the
 * thing this project refused to write twice.
 */
export interface CitedRecord {
  /** The path the citation carries, verbatim. Nothing here opens it. */
  path: string
  statement: string
}

/** One labelled fact off the citation. Three of them, and none is a measurement. */
export interface CitedFact {
  label: string
  value: string
}

/** A bench citing a gate run: the outcome, the date, and the library version. */
export interface CitedGateReading {
  cited: true
  /** The outcome as a sentence whose subject is the bench. */
  heading: string
  /** Outcome, date and library version, in the order a reader asks for them. */
  facts: CitedFact[]
  record: CitedRecord
  document: CitedDocument
  aboutTheBench: string
}

/**
 * A bench citing no gate run, saying so where the citation would have been.
 *
 * No `facts`, no `record` and no `document`: an uncited bench has no outcome, no
 * date, no library version and nothing written down anywhere, and a shape with empty
 * ones would be read as a gate it failed.
 */
export interface UncitedGateReading {
  cited: false
  heading: string
  statement: string
  aboutTheBench: string
}

export type GateReading = CitedGateReading | UncitedGateReading

/**
 * What each outcome says about the bench, in a sentence naming its subject.
 *
 * Three outcomes and three sentences, because *not decided* is not a polite fail:
 * a fail is a measured claim that the bench does not discriminate, and not decided
 * says too little of the instrument was fit for the question to be put
 * (`scorer.GateOutcome`). Collapsing them would report an undecided instrument as
 * a broken one, or a broken one as merely unmeasured.
 */
const OUTCOME_HEADINGS: Record<string, string> = {
  passed: 'This bench passed its own gate run',
  failed: 'This bench did not pass its own gate run',
  not_decided:
    'This bench’s gate run was not decided — too little of the instrument was fit ' +
    'to report for the question to be put, which is a stop and not a fail',
}

const UNCITED =
  'This bench cites no gate run. Its own discriminating power is unstated here — ' +
  'a stated absence rather than a blank, and not a gate it failed: nothing has ' +
  'been decided either way. Read anything it measures knowing the instrument ' +
  'carries no certification, and run the gate from a terminal before trusting a ' +
  'rate it produces.'

/** The gate run this bench cites, as the front door states it. */
export function gateReading(gate: GateCitation): GateReading {
  if (!gate.cited) {
    return {
      cited: false,
      heading: 'This bench cites no gate run',
      statement: UNCITED,
      aboutTheBench: A_FACT_ABOUT_THE_BENCH,
    }
  }
  return {
    cited: true,
    heading:
      OUTCOME_HEADINGS[gate.outcome] ??
      `This bench’s last gate run is recorded as ${gate.outcome}`,
    facts: [
      { label: 'Outcome', value: gate.outcome },
      { label: 'Decided on', value: gate.decided_on },
      { label: 'Library version', value: libraryVersion(gate.library) },
    ],
    record: {
      path: gate.record,
      statement: THE_RECORD_IS_THE_SAME_RUN_AS_FIELDS,
    },
    document: {
      path: gate.document,
      statement: THE_DOCUMENT_IS_NAMED_AND_NEVER_PARSED,
    },
    aboutTheBench: A_FACT_ABOUT_THE_BENCH,
  }
}

/**
 * The library version a gate run was earned at: the count and the digest, both.
 *
 * A citation saying only *eighteen cases* cannot tell a reader whether the
 * eighteen are the same eighteen, and the digest is what makes "has the bench
 * changed since?" a question with an answer (`library.LibraryVersion`). Composed
 * here because the citation's library block carries the two fields and no sentence
 * of its own.
 */
function libraryVersion(library: { cases: number; digest: string }): string {
  const cases = `${library.cases} ${library.cases === 1 ? 'case' : 'cases'}`
  return `${cases}, sha256:${library.digest}`
}
