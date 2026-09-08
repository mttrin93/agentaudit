/**
 * Everything under `/bench` — the gate this bench cites, its settings, its tuning
 * and the notes an operator has to plant.
 *
 * One module in #14's split by API area because they are one thing from the app's
 * side: what this bench *is*, as opposed to what a run did. The gate citation, the
 * signing keys, the loaded library, the declared models and ceilings, and the two
 * routes that change them.
 *
 * **A citation is read and never constructed here.** `CitedRecord` is `HeldRecord`
 * or `UnheldRecord`, and the second is a bench whose gate record this deployment
 * does not hold — which is a fact to print, not a gap to fill in (ADR-0023).
 */

import type {
  DeclaredRule,
  GateCitation,
  GateDecided,
} from './contracts'
import {
  fetched,
  refusalIn,
} from './http'


/** Where the bench's own gate citation is read. About the bench, not about a run. */
export const BENCH_GATE_PATH = '/bench/gate'

/**
 * The bench's own certification: the rule it is held to, then what it answered.
 *
 * Two fields, and the order is the response's own. The rule is declared
 * configuration and a fact about the bench whether or not a gate run was ever
 * made; the citation is what the last one answered and is one of two shapes. So
 * the rule is not nested inside the citation — an uncited bench is held to the
 * same bar — and the citation is nested rather than flattened so that it stays the
 * identical block the signed provenance carries (ADR-0018).
 */
export interface BenchGate {
  rule: DeclaredRule
  citation: GateCitation
}

/**
 * The rule this bench is held to, and the gate run it cites under it.
 *
 * The only read in this module whose subject is the instrument rather than a
 * target, and it takes no run id because it is not about a run. What it answers
 * with is the gate run this bench last made: ADR-0023 reversed ADR-0021 on that,
 * so a bench that has passed its own gate says so here without a deployment
 * editing a configuration, and a bench whose last gate run failed says *that*.
 * Reading a gate run and starting one are still two operations on two routes.
 *
 * **Starting a gate run is not here, and is nowhere under `/bench`.** The four
 * functions below post to and read `/gate-runs`, which is its own route family for
 * the reason a gate run is its own record: a run produces rates about somebody's
 * target, a gate run produces a decision about this bench (ADR-0018, ADR-0021). The
 * only writes on the prefix are the two settings routes further down — the
 * instruments the next run is set with, and the families it covers (ADR-0025, as
 * amended by #57).
 */
export async function benchGate(): Promise<BenchGate> {
  return (await fetched(BENCH_GATE_PATH, 'gate citation')) as BenchGate
}

/** Where the record the citation names is opened. The figures, one level down. */
export const BENCH_GATE_RECORD_PATH = '/bench/gate/record'

/**
 * The gate run record this bench holds, whole, as the run that earned it wrote it.
 *
 * `rule` above `decision`, because that is the order the record is in on disk and on
 * every other carrier of a gate result: an outcome read with no bar beside it is a
 * verdict somebody trusted (ADR-0003).
 */
export interface RecordedGateRun {
  decided_at: string
  /** The dated Markdown this record sits beside, or `null` for a console gate run. */
  document: string | null
  record: string
  rule: DeclaredRule
  decision: GateDecided
  recorded: string
}

/** The record is here, and every per-family figure of that gate run with it. */
export interface HeldRecord {
  held: true
  run: RecordedGateRun
  stated: string
}

/**
 * No record here, with the reason and the file name it was looked for under.
 *
 * Four nothings in one shape: no library to hold a record, no gate run cited at all,
 * a record written beside its document somewhere this bench was not given, or a file
 * that would not parse. None of them is a failed gate and none is an empty outcome —
 * what the last gate run answered is on `GET /bench/gate` and is unaffected.
 */
export interface UnheldRecord {
  held: false
  record: string | null
  stated: string
}

export type CitedRecord = HeldRecord | UnheldRecord

/**
 * Open the record the citation names, for the figures the citation does not carry.
 *
 * A second request against a second path, deliberately: `GET /bench/gate` stays
 * byte-identical to the provenance block of every signed report, with no per-family
 * figure added on the way to a screen (ADR-0023). This is the pointer on it being
 * followed, and it reads the record rather than the dated document — a figure
 * recovered from prose would break on a rewording.
 *
 * It answers rather than refusing where the record is not held, so a caller that
 * needs to say *which* record this bench does not have can. `held` is the field to
 * branch on.
 */
export async function benchGateRecord(): Promise<CitedRecord> {
  return (await fetched(BENCH_GATE_RECORD_PATH, 'gate run record')) as CitedRecord
}

/** Where this bench states what it is configured to do. A reader, and only that. */
export const BENCH_SETTINGS_PATH = '/bench/settings'

/**
 * The key an artefact this bench produces will be signed by, or the absence of one.
 *
 * `holds_a_key: false` is a bench that declared it does not sign, which is a
 * sentence rather than an empty fingerprint: there is no `fingerprint` field on that
 * shape, so nothing here can be drawn as a key whose name failed to load.
 */
export type WillBeSignedBy =
  | { holds_a_key: true; fingerprint: string; stated: string }
  | { holds_a_key: false; stated: string }

/**
 * The key a verification of this bench's artefacts is run against.
 *
 * Never absent, because there is always an answer: a deployment that declared no pin
 * verifies against the committed public half whose fingerprint the README publishes.
 * `declared` is which of the two, so *rotated* and *said nothing* are two facts
 * rather than one a reader has to recognise a fingerprint to tell apart.
 */
export interface VerifiedAgainst {
  fingerprint: string
  declared: boolean
  stated: string
}

/**
 * The two key identifiers, and they are two facts.
 *
 * The same pair `SignatureResult` keeps apart: a bench signing with a key nobody
 * published verifies against the published one and reports `signed_by_another_key`
 * on every report it produces. A screen naming one of them would show that bench as
 * correctly configured (ADR-0017).
 */
export interface SigningKeys {
  will_be_signed_by: WillBeSignedBy
  verified_against: VerifiedAgainst
  statement: string
}

/**
 * The case library this bench is loaded with: the live version, and what retired.
 *
 * The version is over the cases a run scores, so it is comparable by eye with the
 * version the gate citation carries. The retired count sits beside it and is never
 * folded into it: a retired case is marked and kept, and their sum is a case count
 * nothing runs.
 */
export interface LoadedLibrary {
  live: { cases: number; digest: string }
  stated: string
  retired: number
  /**
   * The kinds of agent the live half has cases for, sorted, off the records.
   *
   * What a screen may *offer*, and never a set to be inside of: an agent type is the
   * operator's own word for their own agent, and a kind the library has no case for is
   * a skip per case with its reason on it rather than a refused registration.
   */
  agent_types: string[]
  kept: string
  statement: string
}

/** One of the four model settings: the instrument, its model, what it decides. */
export interface ModelSetting {
  instrument: string
  identifier: string
  declared: boolean
  decides: string
  /**
   * What this instrument is set to think at, or the stated absence of a setting.
   *
   * The row was the model and not what the model was set to, so a reader saw which
   * model the adjudicator runs on and not the conditions it ran under. One of the
   * four statements a provenance block keeps apart for the attacker, and a stated
   * absence for the three rows this bench holds no thinking budget on. Never a
   * blank, and the response's own sentence rather than one composed here.
   */
  effort: string
}

/**
 * The scored layer's ceiling, in the scored layer's own units.
 *
 * Attempts over cases. No field here shares a unit with the adaptive ceiling below,
 * which is what makes the two unaddable rather than merely un-added.
 */
export interface ScoredCeiling {
  layer: 'scored'
  attempts_per_case: number
  registration_probes_per_target: number
  declared_in: string
  statement: string
}

/** The adaptive layer's ceiling, in turns over episodes over families. */
export interface AdaptiveCeiling {
  layer: 'adaptive'
  turns_per_episode: number
  episodes_per_family: number
  families: number
  turns_per_target: number
  declared_in: string
  statement: string
}

/**
 * The two ceilings, one field each, and no third field anywhere.
 *
 * Two differently-shaped records rather than two numbers, so there is no name here
 * under which a sum could be written: each layer is enforced against its own
 * counter, and a layer with room left cannot spend the other's unspent allowance
 * (ADR-0007, ADR-0010).
 */
export interface LayerCeilings {
  scored: ScoredCeiling
  adaptive: AdaptiveCeiling
  statement: string
}

/**
 * What this bench is configured to do, as it is currently loaded.
 *
 * Five fields and not one of them a measurement. There is nothing here that spans
 * two families, nothing that spans two layers, no severity scale and no composite
 * figure — and nothing that could be posted back, because the route that serves this
 * has no sibling that writes.
 */
export interface BenchSettings {
  statement: string
  signing: SigningKeys
  library: LoadedLibrary
  models: ModelSetting[]
  ceilings: LayerCeilings
  tuning: Tuning
}

/** What one family is read onto: two published lists, and the articles it bears. */
export interface FamilyLabelled {
  /** Entries of the OWASP agentic list. Empty is an answer, not a missing lookup. */
  agentic: string[]
  /** Entries of the OWASP GenAI LLM list, on the same terms. */
  llm: string[]
  /** EU AI Act articles, primary first and never sorted (ADR-0040). */
  articles: string[]
}

/**
 * One failure family, whether the next run covers it, and what it is read onto.
 *
 * The label rides on the switch because the bench page prints the two in one row, and
 * it is served rather than held here because a second copy of a published identifier
 * in TypeScript is the drift `labels.py` exists to prevent — ADR-0036's edition tag
 * being exactly what a hand copy loses.
 */
export interface FamilyCovered {
  family: string
  covered: boolean
  labels: FamilyLabelled
}

/**
 * One layer, whether the next run runs it, and what a run of it sends.
 *
 * Three of them: one message in one session, a fixed script of turns, and the
 * model-driven attacker. `sends` is the bench's own sentence about the layer, so a
 * screen states what switching it off costs rather than paraphrasing it.
 */
export interface LayerSelected {
  layer: string
  selected: boolean
  sends: string
}

/**
 * One construction, the layer that schedules it, and whether the next run sends it.
 *
 * `layer` is read off the wire and never derived here: which switch turns a
 * construction off is the bench's answer (`selection.layer_of`), and a console holding
 * a second copy of that mapping would be a console that could disagree with it.
 *
 * `does` is what the construction does to the payload a record commits — an operation
 * on text and never an attack somebody published — in the bench's own words.
 */
export interface TransformSelected {
  transform: string
  layer: string
  selected: boolean
  does: string
}

/**
 * One adaptive schedule, the layer that switches it, and whether the next run
 * attacks under it.
 *
 * Two of them — the line and the tree — and they are what the adaptive box holds
 * where the other two layers hold constructions: the layer names no construction, so
 * until the bench had this switch the layer's own tick was the whole of what there
 * was to ask about it.
 *
 * **Selecting both is two episode sets per family and not one wider search**, so the
 * second tick doubles the layer's ceiling. `does` is the scheduling and pruning rule
 * in the bench's own words, because it is the rule `A_break` is read against, and
 * `layer` is read off the wire for `TransformSelected`'s reason: the grouping is the
 * bench's answer and a console holding a second copy of it could disagree.
 */
export interface ScheduleSelected {
  schedule: string
  layer: string
  selected: boolean
  does: string
}

/** One model this console offers as the attacker, and what it is for. */
export interface ModelChoice {
  identifier: string
  decides: string
  chosen: boolean
}

/**
 * One reasoning effort this console offers, and whether the next run is on it.
 *
 * A closed list and not a range, because it is one. Served empty for a model with no
 * such setting, so a form cannot draw a control whose every value the route refuses.
 */
export interface EffortChoice {
  level: string
  chosen: boolean
}

/** What a setting may be. The range the route enforces, so the form offers no other. */
export interface Bounds {
  low: number
  high: number
}

/**
 * The declared inputs of the next run: what they are set to, and what they may be.
 *
 * The one part of the settings response that is a control. Every field here changes
 * what the **next** run measures rather than how it looks, and every one of them is
 * printed in the report of every run made under it — which is the condition ADR-0025
 * admits them on. A run in flight keeps what it was started with, and a change is
 * refused while one is going.
 *
 * **Five of the six bound a layer that is scored on nothing; `attempts_per_case` is
 * the scored denominator.** `attempts_warning` is the bench's own sentence about the
 * difference and the screen prints it rather than paraphrasing it.
 */
export interface Tuning {
  attacker_models: ModelChoice[]
  temperature: number | null
  /**
   * The range a temperature may be set in, or `null` when there is no setting.
   *
   * `null` when the chosen attacker accepts no temperature, on the same terms
   * `reasoning_efforts` is served empty: a form drawing a slider against a reasoning
   * model offers a control whose every value the route refuses. Served state and not
   * a guess — the capability table is declared once in the bench and this console
   * reads its answer rather than holding a copy of it.
   */
  temperature_bounds: Bounds | null
  /** What leaving it undeclared means, on a model that has the setting. */
  temperature_absent: string
  /** What a run made now would print about its sampling, in the record's own words. */
  temperature_stated: string
  /** The levels the chosen model accepts. Empty when it has no such setting. */
  reasoning_efforts: EffortChoice[]
  reasoning_effort: string | null
  reasoning_effort_absent: string
  /** What a run made now would print in its provenance, in the record's own words. */
  reasoning_effort_stated: string
  turns_per_episode: number
  turns_bounds: Bounds
  episodes_per_family: number
  episodes_bounds: Bounds
  attempts_per_case: number
  attempts_bounds: Bounds
  attempts_per_family: number
  declared_attempts_per_case: number
  attempts_warning: string
  families: FamilyCovered[]
  families_off_statement: string
  /**
   * The elective tier and whether each of it is requested, in the enum's own order.
   *
   * A second array rather than three more rows in `families`, because the bench holds
   * two closed sets and the six are the denominator the gate is decided over (ADR-0015,
   * ADR-0035). The console draws all nine as one undifferentiated table (ADR-0091);
   * that is a presentation and it did not merge these two — `PUT
   * /bench/settings/families` takes them as one statement of two lists, and a switch
   * has to know which of them it writes to.
   */
  elective_families: FamilyCovered[]
  /**
   * What requesting one buys and what it does not, in the bench's own words.
   *
   * Served and drawn by nothing since ADR-0091, on `families_off_statement`'s terms:
   * the bench's own sentence is still built and still tested, and the screen that used
   * to print it above the tier's own heading no longer has one.
   */
  elective_statement: string
  layers: LayerSelected[]
  transforms: TransformSelected[]
  schedules: ScheduleSelected[]
  /**
   * The spellings the adaptive layer may compose its probes in, and which it does.
   *
   * `TransformSelected` rows, because they are `Transform` members — four of the
   * seven, the ones whose construction needs no words of ours — and a second list
   * rather than more rows on `transforms`: the same member means two different things
   * in the two lists, a case sent in base64 and scored on its own attempts, and a
   * probe the attacker composed being respelled on its way out.
   */
  adaptive_constructions: TransformSelected[]
  /**
   * What selecting a second spelling buys and what it costs, in the bench's words.
   *
   * Read and drawn, on `schedules_statement`'s terms: each spelling is its own episode
   * set, so the tick is turns on the operator's own endpoint.
   */
  adaptive_constructions_statement: string
  /**
   * What selecting both schedules buys and what it costs, in the bench's own words.
   *
   * Read and drawn, unlike the two sentences below it: those are written for a reader
   * holding a document, and this is what the operator's second tick costs in turns on
   * their own endpoint before they tick it.
   */
  schedules_statement: string
  /** What switching a construction off does, and what it does not. */
  selection_off_statement: string
  /** What a run made now would print in its provenance about what it sent. */
  selection_stated: string
  statement: string
}

/** The six settings, as the console sends them. All six every time. */
export interface Tune {
  attacker_model: string
  temperature: number | null
  /**
   * One of the levels the reading offered, or `null` for nothing declared.
   *
   * Sent every time, like every other field here: a request that left it out would
   * clear a declared effort the bench is holding, because this `PUT` is the whole
   * statement of how the instruments are set.
   */
  reasoning_effort: string | null
  turns_per_episode: number
  episodes_per_family: number
  attempts_per_case: number
}

/**
 * The bench's own configuration, read.
 *
 * A read and nothing else. This module has no function that posts anywhere under
 * `/bench` and the API has no route that would take one: rotation stays in the
 * environment and configuration stays on the command line, because the factory reads
 * its key from one place and refuses to boot without it (ADR-0020).
 */
export async function benchSettings(): Promise<BenchSettings> {
  return (await fetched(BENCH_SETTINGS_PATH, 'bench settings')) as BenchSettings
}

export const BENCH_TUNING_PATH = '/bench/settings/tuning'

/**
 * Set the declared inputs of the next run, and read back what the bench now holds.
 *
 * The first of the two writes under `/bench` (ADR-0025, as amended by #57 — the second
 * is `coverFamilies` below). All six settings go every time, because a caller that
 * could send the turn budget without restating the attacker model could leave a bench
 * naming one instrument in a report while another attacked.
 *
 * The answer is the whole settings reading, so the screen renders what was stored
 * rather than what it hoped it sent. A `409` is the bench refusing while a run is
 * going, and its detail names the runs — thrown like every other failure here, and
 * the screen shows the sentence.
 */
export async function tuneBench(asked: Tune): Promise<BenchSettings> {
  const response = await fetch(BENCH_TUNING_PATH, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(asked),
  })
  if (!response.ok) {
    throw new Error(
      `the bench did not take these settings: ${await refusalIn(response)}`,
    )
  }
  return (await response.json()) as BenchSettings
}

export const BENCH_FAMILIES_PATH = '/bench/settings/families'

/**
 * Set which families the next run covers, and read back what the bench now holds.
 *
 * The second write under `/bench` (ADR-0025, as amended by #57), and its own statement
 * rather than a field on the tuning request: that one is *how the instruments are set*
 * and takes all six settings every time; this is *what the next run covers*, sent from
 * a different screen. An empty `families` is refused — a run covering no family attacks
 * nothing.
 *
 * **Both lists every time, because they are one statement.** `elective` is the tier
 * this run asks for beside the six it attacks, and a request that omitted it would
 * clear whatever the bench is holding — this `PUT` is the whole statement of what the
 * next run covers, on the terms `tune` and `select` are. Unlike `families` it may be
 * empty: no elective family requested is the six and only the six, which is what every
 * run asked for before #171
 * ([ADR-0088](../../../docs/adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)).
 *
 * Two arrays and never one of nine: the six are the denominator the gate is decided
 * over (ADR-0015) and the tier is a second closed set, so a name in the wrong array is
 * a `422` from the route rather than a family landing in the other tier's counts.
 */
export async function coverFamilies(
  families: string[],
  elective: string[],
): Promise<BenchSettings> {
  const response = await fetch(BENCH_FAMILIES_PATH, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ families, elective }),
  })
  if (!response.ok) {
    throw new Error(`the bench did not take these families: ${await refusalIn(response)}`)
  }
  return (await response.json()) as BenchSettings
}

export const BENCH_SELECTION_PATH = '/bench/settings/selection'

/**
 * Set what the next run sends, and read back what the bench now holds.
 *
 * The third write under `/bench` (ADR-0025 as amended by #79, ADR-0058), and its own
 * statement rather than a field on either of the other two: that one is *how the
 * instruments are set*, the families one is *what the next run covers*, and this is
 * *how it attacks what it covers*.
 *
 * All three lists go every time, because they are one statement — a request that sent
 * the layers alone would leave the constructions declared by an earlier one, and the
 * three together are what decides whether anything is sent at all. The schedules are
 * the adaptive layer's two halves of it: an empty list of either is refused, because a
 * layer running under no schedule, or composing in no spelling, is what the layer's own
 * switch already says (ADR-0096, ADR-0097). A spelling the bench cannot respell a
 * composed probe by is refused by name.
 *
 * A selection under which nothing would be scored is refused rather than widened: the
 * run would measure nothing and still spend a registration probe per target. A `409`
 * is the bench refusing while a run is going, and the screen shows the sentence.
 */
export async function selectConstructions(
  layers: string[],
  transforms: string[],
  schedules: string[],
  adaptiveConstructions: string[],
): Promise<BenchSettings> {
  const response = await fetch(BENCH_SELECTION_PATH, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      layers,
      transforms,
      schedules,
      adaptive_constructions: adaptiveConstructions,
    }),
  })
  if (!response.ok) {
    throw new Error(`the bench did not take this selection: ${await refusalIn(response)}`)
  }
  return (await response.json()) as BenchSettings
}

export const BENCH_NOTES_PATH = '/bench/notes'

/**
 * One note the indirect prompt injection family attacks with, to be planted.
 *
 * The `canary` is not a value to plant. It is what executing the instruction in the
 * body adds to a reply, and the note is written so that the two halves of it are in
 * the body and the join is not: a target that quotes the whole note back while
 * refusing it reproduces both halves and never the join. Shown so an operator can
 * see what the bench will be looking for, never as something to paste.
 */
export interface NoteToPlant {
  case: string
  key: string
  body: string
  canary: string
}

/**
 * What has to be in place before the injection family measures anything.
 *
 * No readiness field, and there is nothing here that could be one: whether the
 * content is actually where this target retrieves it is the operator's declaration
 * at registration, which the bench cannot check. `unpaired` names live cases this
 * bench holds no content for, so a short list cannot read as a complete one.
 */
export interface NotesToPlant {
  notes: NoteToPlant[]
  unpaired: string[]
  stated: string
}

/**
 * The content the injection family needs planted, read.
 *
 * Its own request rather than a field on the settings response, because the subject
 * is different: the settings are what this instrument is configured to do, and this
 * is content an operator has to put somewhere before one family of a run means
 * anything. A register screen that could not read it is a register screen that still
 * registers — the declaration is the operator's either way.
 */
export async function notesToPlant(): Promise<NotesToPlant> {
  return (await fetched(BENCH_NOTES_PATH, 'notes to plant')) as NotesToPlant
}
