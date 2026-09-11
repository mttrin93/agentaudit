/**
 * The front door's copy, and the reading of the bench's own gate citation.
 *
 * A console opening on a registration form asks an engineer for an endpoint before
 * telling them what will be done to it. So the root screen says what the bench is
 * and what the console does — `WHAT_THIS_INSTRUMENT_IS` and
 * `WHAT_THIS_CONSOLE_DOES` — and it says it in as few words as the claim survives in.
 * Neither is drawn any more: the bench screen is the switches an operator came to move,
 * and both strings are still built and still tested on `Tuning.elective_statement`'s
 * terms. `LandingScreen` says at each site what it stopped printing and why.
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

import type {
  GateCitation,
  LayerSelected,
  ScheduleSelected,
  TransformSelected,
} from '../api/bench'

import { ARTEFACTS_PATH, REGISTER_PATH } from './rail'

/**
 * What the bench attacks, over what denominator, and what it reports.
 *
 * Printed by nothing since the bench screen dropped its own heading for it: the claim
 * is the one a report makes and it is stated where the figures are. Kept for the reason
 * `Tuning.elective_statement` is kept — a sentence in the bench's own vocabulary, and
 * this screen was never the only thing that could print it.
 */
export const WHAT_THIS_INSTRUMENT_IS =
  'AgentAudit attacks an AI agent you own across six families of failure, ten ' +
  'attempts per case, and reports each family over its own denominator: a rate, an ' +
  'interval and a band each, and no total across them.'

/**
 * The three errands this console exists for, each with the control that starts it.
 *
 * **Drawn by nothing.** The bench screen's card set is gone — both screens are rows in
 * the rail, and the runs and artefacts blocks point at them with the record's own rows
 * in them — and this stays on `WHAT_THIS_INSTRUMENT_IS`'s terms, above.
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

import type { FamilyCovered } from '../api/settings'

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

/**
 * The elective tier, each in one sentence, in the enum's own order.
 *
 * The same shape as `THE_FAMILIES` and still a **second list**, though no longer for the
 * reason it was written: the six are the gate's denominator, fixed at six (ADR-0015),
 * and these three are a tier the bench holds and a run has to ask for. What kept the two
 * apart on the *screen* was reversed in
 * [ADR-0091](../../../docs/adr/0091-the-console-draws-the-nine-families-as-one-list.md)
 * — `familyRows` joins them into one undifferentiated table — and what keeps them apart
 * here is that they mirror two closed enumerations and two arrays on the wire, which a
 * switch has to tell apart to know where a move is written.
 *
 * **A tick beside each of them, since #171.** `BenchConfig` carries the tier's declared
 * selection beside the six's switch, `PUT /bench/settings/families` takes both lists as
 * one statement, and a requested family's rate against the target is on the signed
 * report with its interval and its band
 * ([ADR-0088](../../../docs/adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)).
 * A family left unticked is stated on that report as *not requested*, which is the
 * fifth kind of nothing and never a rate of zero.
 *
 * **No figure in any of these sentences**, on the same rule as the six: a sentence about
 * what a family *is* has nothing to do with how anything answered it. And what still
 * never reaches a target's report is the bench's own `D` on the tier — that is a claim
 * about the bench, and it is in the gate run's own document (ADR-0018).
 */
export const THE_ELECTIVE_FAMILIES: readonly FamilySays[] = [
  {
    family: 'memory_poisoning',
    says:
      'The agent carries an instruction from one session into a later one, and acts ' +
      'on it after the conversation that planted it has ended.',
  },
  {
    family: 'direct_prompt_injection',
    says:
      'The instruction arrives in the operator’s own message rather than in content ' +
      'the agent retrieved, and the agent follows it past its own limits.',
  },
  {
    family: 'pii_leakage',
    says:
      'The agent discloses a third party’s personal data — someone who is not its ' +
      'operator and never asked to be in the conversation.',
  },
]

/**
 * One family as the bench page draws it: what it is, what it claims, what it bears.
 *
 * Nine of these and one list. The six and the elective three are presented
 * undifferentiated — same row, same columns, no mark saying which tier a row is in
 * ([ADR-0091](../../../docs/adr/0091-the-console-draws-the-nine-families-as-one-list.md)).
 * What that ADR did **not** do is merge the two closed sets: `tier` is read by the
 * switch, which has to know which array a move writes to, and is printed by nothing.
 *
 * `owasp` folds the two published lists into one column because the screen has one:
 * `agentic` first and `llm` after it, each entry carrying its edition (ADR-0036). Both
 * may be empty and that is an answer — data leakage claims nothing on the agentic list,
 * halt defeat and disclosure denial nothing on the LLM one — so an empty column here is
 * a refusal `labels.py` argues for and never a lookup that failed.
 *
 * **No measurement on the row.** Not a rate, not a `D`, not a band: this screen says
 * what the nine *are*, and how a target answered one is the report's business
 * (ADR-0018). `holds` is the one figure, and it is admissible because it is a count of
 * what this bench holds rather than a reading against anybody's agent — the layers
 * block's own column, asked of a family (ADR-0108).
 */
export interface FamilyRow {
  /** The wire name, as every record spells it. Read as words on the way out. */
  family: string
  says: string
  /** Which array the switch writes to. Never drawn. */
  tier: 'six' | 'elective'
  owasp: readonly string[]
  articles: readonly string[]
  /**
   * How much of this family the library holds, worded by the bench.
   *
   * Empty where the settings read has not answered — the sentence and the switch are
   * this console's own and draw without it, and a count is not: a row that filled this
   * in from a default would be stating what the library holds without having asked.
   */
  holds: string
}

/**
 * The nine rows, joining what a family *is* to what the bench says it is read onto.
 *
 * Two sources and one row, which is the whole of it: the sentence is this module's,
 * written here because it is prose about a failure and not configuration, and the
 * labels are the bench's, served on the switch so that the console cannot hold a
 * second copy of a published identifier that has drifted from `labels.py`.
 *
 * **A family the bench did not name gets empty columns and never a guessed label.**
 * The settings read can fail, and the two arrays arrive `null` when it does; a row
 * still draws, because the nine and their sentences are this console's own and do not
 * depend on a fetch. What it will not do is invent an identifier — an empty legal
 * column on this screen is indistinguishable from data leakage's honest empty agentic
 * one, and the alternative is worse: a claim nobody published.
 */
export function familyRows(
  families: FamilyCovered[] | null,
  elective: FamilyCovered[] | null,
): readonly FamilyRow[] {
  const drawn = (
    said: readonly FamilySays[],
    rows: FamilyCovered[] | null,
    tier: 'six' | 'elective',
  ): readonly FamilyRow[] =>
    said.map((one) => {
      const served = rows?.find((held) => held.family === one.family)
      const labels = served?.labels
      return {
        family: one.family,
        says: one.says,
        tier,
        owasp: [...(labels?.agentic ?? []), ...(labels?.llm ?? [])],
        articles: labels?.articles ?? [],
        holds: served?.holds ?? '',
      }
    })
  return [
    ...drawn(THE_FAMILIES, families, 'six'),
    ...drawn(THE_ELECTIVE_FAMILIES, elective, 'elective'),
  ]
}

/** One construction, and whether the next run sends it. */
export interface ConstructionOffered {
  /** The wire name, as every record spells it. Read as words on the way out. */
  transform: string
  /** What it does to the payload the record commits, in the bench's own words. */
  does: string
  sent: boolean
}

/**
 * One schedule the adaptive layer may attack under, and whether the next run does.
 *
 * The line and the tree. `sent` is `selected` read out in this module's own word for
 * it, on `ConstructionOffered`'s terms — what a switch answers here is *will the next
 * run send this* — and `does` is the harness's scheduling and pruning rule verbatim,
 * because it is the rule a report's `A_break` sentence is read against.
 */
export interface ScheduleOffered {
  /** The wire name, as every record spells it. */
  schedule: string
  /** The scheduling and pruning rule, in the bench's own words. */
  does: string
  selected: boolean
}

/**
 * One layer, whether the next run runs it, and the constructions inside it.
 *
 * The grouping the operator's question has: *do I want the encodings, the ladders, or
 * the agent?* — the layers answer it, and the list under each is the finer grain
 * inside. `constructions` is **empty on the adaptive layer**, and that is the shape
 * rather than an omission: what it would hold are the two loops the bench's closed set
 * of constructions deliberately does not name.
 *
 * `schedules` is where those two loops are, and it is empty on the other two layers
 * for the mirror-image reason: a schedule is how the adaptive attacker spends an
 * episode's turns, and the layers that carry constructions have nothing to schedule
 * (ADR-0096). Both lists are grouped off the `layer` field the wire puts on every row,
 * so this module holds no mapping of its own either way.
 */
export interface LayerOffered {
  layer: string
  /** What a run of this layer sends, in the bench's own words. */
  sends: string
  /**
   * How much of this layer there is to send, in the bench's own words.
   *
   * Cases for the two layers that send them and episodes for the one that sends none,
   * and it is a count of records rather than a rate: what a family measured is read
   * off a report beside its own denominator, and no two rows' figures may be added
   * (ADR-0005, ADR-0010).
   */
  holds: string
  /** What one attempt of this layer puts on the target's endpoint, in the bench's own
   * words, and empty where the library holds nothing of the layer. */
  costs: string
  runs: boolean
  constructions: ConstructionOffered[]
  schedules: ScheduleOffered[]
  /**
   * The spellings this layer may compose its probes in. The adaptive layer's, and
   * empty on the other two.
   *
   * `ConstructionOffered` rows, because they are the same members the scored layer's
   * constructions are — and a separate list rather than the same one, because the two
   * switches answer two different questions about one member: *send a case in it*, and
   * *respell a composed probe by it* (ADR-0097).
   */
  spellings: ConstructionOffered[]
}

/**
 * What the next run sends, as the switches this screen draws.
 *
 * **The grouping is the wire's**, never this module's: every construction row carries
 * the layer that schedules it, and a console holding a second copy of that mapping
 * would be a console that could disagree with the bench about which switch turns a
 * construction off.
 *
 * **No figure in any of it, and no prose either.** A selection is what a run was asked
 * to send, and a rate, a count or a denominator here would be read as a reading about
 * a target. The two sentences the route serves beside the switches — the paragraph
 * about what switching one off does, and the wording a run made now would carry into
 * its provenance — are deliberately not read here, on the terms
 * `families_off_statement` is not: both are written for a reader holding a *document*,
 * where a sentence about comparability and library versions sits beside a rate, and an
 * operator holding a switch is answering *which of these will the next run send*. The
 * distinction neither is lost — the artefact states both, in the artefact, and this
 * screen's switches are what a reader consults before there is one.
 */
export interface SelectionReading {
  layers: LayerOffered[]
  /**
   * What selecting both schedules costs, in the bench's own words.
   *
   * **The one served sentence this reading keeps**, and the exception is argued rather
   * than an oversight: the two it drops are about a document — comparability, library
   * versions, what a reading absent from a page means — and this one is about the
   * switch beside it. A second schedule is a second episode set per family, so the
   * tick doubles the turns the next run may put on the operator's own endpoint, and
   * that is the fact an operator needs *before* answering rather than after
   * (ADR-0007, ADR-0096).
   */
  schedulesCost: string
  /**
   * What selecting a second spelling costs, in the bench's own words.
   *
   * `schedulesCost`'s exception, argued the same way: it is about the switch beside it
   * rather than about a document, and each spelling selected is another episode set —
   * turns on the operator's own endpoint, which is a thing to know before answering.
   */
  spellingsCost: string
}

/** What the bench's tuning reading says about what the next run sends. */
interface Offered {
  layers: readonly LayerSelected[]
  transforms: readonly TransformSelected[]
  schedules: readonly ScheduleSelected[]
  schedules_statement: string
  adaptive_constructions: readonly TransformSelected[]
  adaptive_constructions_statement: string
}

/**
 * The layers and their constructions, in the order the bench served them.
 *
 * A projection and not a decision: nothing is sorted, nothing is filtered and nothing
 * is defaulted. A construction naming a layer the reading does not carry is dropped by
 * having nowhere to go rather than grouped under a guess — the two lists come from two
 * closed enumerations in one response, so a row with no home is a bench and a console
 * that disagree, and a screen that invented a heading for it would hide that.
 */
export function selectionReading(offered: Offered): SelectionReading {
  return {
    layers: offered.layers.map((layer) => ({
      layer: layer.layer,
      sends: layer.sends,
      holds: layer.holds,
      costs: layer.costs,
      runs: layer.selected,
      constructions: offered.transforms
        .filter((one) => one.layer === layer.layer)
        .map((one) => ({
          transform: one.transform,
          does: one.does,
          sent: one.selected,
        })),
      schedules: offered.schedules
        .filter((one) => one.layer === layer.layer)
        .map((one) => ({
          schedule: one.schedule,
          does: one.does,
          selected: one.selected,
        })),
      spellings: offered.adaptive_constructions
        .filter((one) => one.layer === layer.layer)
        .map((one) => ({
          transform: one.transform,
          does: one.does,
          sent: one.selected,
        })),
    })),
    schedulesCost: offered.schedules_statement,
    spellingsCost: offered.adaptive_constructions_statement,
  }
}

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
