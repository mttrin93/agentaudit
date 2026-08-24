/**
 * The front door's copy, and the reading of the bench's own gate citation.
 *
 * A console opening on a registration form asks an engineer for an endpoint before
 * telling them what will be done to it. So the root screen says what the bench is
 * and what the console does — `WHAT_THIS_INSTRUMENT_IS` and
 * `WHAT_THIS_CONSOLE_DOES`, two paragraphs and three cards — and it says it in as
 * few words as the claim survives in.
 *
 * **The citation is read here and drawn by the gate screen.** The outcome, the date
 * it was decided and the library version it was earned at, out of the same typed
 * citation the bench carries into the provenance block of every report it signs
 * (`GET /bench/gate`, ADR-0018). The front door used to draw it and no longer does:
 * a citation is only legible beside the rule it was decided under, and that rule is
 * the gate screen's subject. The reading stayed in this module rather than moving
 * into `gate.ts`, which imports it from here, because it is what a citation *says*
 * and `gate.ts` is what the gate *requires*.
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
 * record** that holds the same run as fields (ADR-0023). The gate screen shows what the
 * citation carries and names the rest, in that order: the record first, because it
 * is the one a reader after the arithmetic wants. A screen that read the bench's own
 * prose output would break on a rewording, and the record is why it never has to.
 *
 * **A gate run started from the console wrote no document, and the reading says so
 * where the path would be.** Two shapes rather than one with an empty `path`, for the
 * same reason an uncited bench gets no `facts`: a blank where a file name goes is a
 * file name a reader goes looking for. The record is there either way, so nothing
 * about the outcome is missing.
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

import { ARTEFACTS_PATH, REGISTER_PATH } from './rail'

export const WHAT_THIS_INSTRUMENT_IS =
  'AgentAudit attacks an AI agent you own across six families of failure, ten ' +
  'attempts per case, and reports each family over its own denominator: a rate, an ' +
  'interval and a band each, and no total across them.'

/**
 * The three errands this console exists for, each with the control that starts it.
 *
 * Copy rather than markup, on the same terms as every other string in this module:
 * the screen is markup driven by hand and the wording is here. `path` is taken off
 * `rail.ts` and never written out, so a card cannot offer a screen at a path the
 * router does not serve.
 *
 * **A card carries no figure**, which is why it is a fixed list of four strings and
 * a flag rather than anything read off a route. There is no count of runs here, no
 * rate, no outcome and nowhere to put one — the front door says what the console
 * does, and every figure in this application belongs to the screen that measured it.
 *
 * **`lead` is the errand to do first, and now only that.** An operator with nothing
 * registered can do exactly one of these three usefully, and that is the one the card
 * set points at — first in the sequence, which is where a reader meets it. The
 * stylesheet used to spend the filled control on it and draws all three alike now, so
 * this flag says which errand comes first and nothing about how it is painted.
 */
export interface ConsoleDoes {
  /** The screen this card opens, off `rail.ts`. */
  path: string
  name: string
  /** What that screen does, in the bench's own vocabulary. */
  does: string
  /** What its control says. */
  act: string
  /** Whether this is the one to do first. */
  lead: boolean
}

export const WHAT_THIS_CONSOLE_DOES: readonly ConsoleDoes[] = [
  {
    path: REGISTER_PATH,
    name: 'Register a target',
    does:
      'Issues the nonce you plant, records the three attestations, then estimates ' +
      'the run in two figures. Nothing reaches your endpoint until you answer the ' +
      'halt.',
    act: 'Register',
    lead: true,
  },
  {
    path: ARTEFACTS_PATH,
    name: 'Check an artefact',
    does:
      'Every artefact this bench has signed, its three checks named one by one — ' +
      'signature, rendering digest, arithmetic — and the command a recipient runs ' +
      'over the bytes themselves.',
    act: 'Open artefacts',
    lead: false,
  },
]

/** One family, and the failure it is the name of. */
export interface FamilySays {
  /** The wire name, as every record spells it. Read as words on the way out. */
  family: string
  says: string
}

/**
 * The six families, each in one sentence, in the enum's own order.
 *
 * A reader meets `indirect prompt injection` on four screens before anything on any of
 * them says what one is. Six sentences, and each says what the failure *is* — the
 * agent doing the thing — rather than what the bench does about it: the denominators,
 * the attempts per case and the three reference agents are the instrument, and they are
 * said once at the top of this page.
 *
 * **Not a second vocabulary.** `questionnaire.ts` words the same six as questions about
 * the reader's own agent, because that is what a questionnaire asks; these are the same
 * six failures stated. Two wordings of one set, and no third — a family added to the
 * bench needs a line here on the day it exists, which is why this is a list beside the
 * enum's order rather than a lookup that silently answers nothing.
 *
 * **No figure in any of them.** Not a rate, not a count, not a floor: a sentence about
 * what a family is has nothing to do with how a target answered it, and a number here
 * would be read as one.
 */
export const THE_FAMILIES: readonly FamilySays[] = [
  {
    family: 'indirect_prompt_injection',
    says:
      'Content the agent retrieved carries instructions its operator never gave, ' +
      'and the agent acts on them.',
  },
  {
    family: 'scope_creep',
    says: 'The agent uses a tool, or reaches a system, outside the task it was given.',
  },
  {
    family: 'wrongful_commitment',
    says:
      'The agent commits its operator to something it has no authority to commit ' +
      'them to.',
  },
  {
    family: 'data_leakage',
    says: 'The agent discloses what is inside its own configuration or context.',
  },
  {
    family: 'halt_defeat',
    says: 'The agent is told to stop, and does not stop or does not stay stopped.',
  },
  {
    family: 'disclosure_denial',
    says: 'The agent is asked whether it is an AI system, and does not say that it is.',
  },
]

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

export const NO_DATED_DOCUMENT_WAS_WRITTEN =
  'That gate run left no dated document: it was started from the console, which ' +
  'writes the record above and no prose. Nothing is missing from the outcome — the ' +
  'figures behind it are in that record — and a gate run started from a terminal ' +
  'writes both.'

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

/**
 * A gate run that wrote no prose, saying so where the document's path would be.
 *
 * The console's own two shapes for the console's own two entry points: a gate run
 * from a terminal writes a dated document and one started from a browser does not
 * (ADR-0021, ADR-0023). `path` is absent rather than empty, for the same reason
 * `UncitedGateReading` has no `facts` — a blank where a path goes is a path a reader
 * goes looking for.
 */
export interface NoCitedDocument {
  path: null
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
  document: CitedDocument | NoCitedDocument
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
    // Lower case, like every other labelled fact in this console — the outcome box's
    // `families passing`, a layer's `family`, `case`, `attempt`. Three capitalised
    // labels in one box read as a different kind of thing than the labels beside them.
    facts: [
      { label: 'outcome', value: gate.outcome },
      { label: 'decided on', value: gate.decided_on },
      { label: 'library version', value: libraryVersion(gate.library) },
    ],
    record: {
      path: gate.record,
      statement: THE_RECORD_IS_THE_SAME_RUN_AS_FIELDS,
    },
    document:
      gate.document === null
        ? { path: null, statement: NO_DATED_DOCUMENT_WAS_WRITTEN }
        : {
            path: gate.document,
            statement: THE_DOCUMENT_IS_NAMED_AND_NEVER_PARSED,
          },
    aboutTheBench: A_FACT_ABOUT_THE_BENCH,
  }
}

/**
 * The library version a gate run was earned at, as the count of cases in it.
 *
 * The digest came off the row. It is what makes "has the bench changed since?" a
 * question with an answer (`library.LibraryVersion`), and it is still on the wire in
 * `citation.library.digest` and still printed on the settings screen, where a reader
 * comparing two libraries is already looking; beside an outcome it was twelve
 * characters of hex that no reader of this row was going to compare.
 */
function libraryVersion(library: { cases: number; digest: string }): string {
  return `${library.cases} ${library.cases === 1 ? 'case' : 'cases'}`
}
