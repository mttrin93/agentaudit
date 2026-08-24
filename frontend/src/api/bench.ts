/**
 * The bench's HTTP surface as this app is allowed to see it.
 *
 * Ten of the bench's routes are reachable from here — `POST /nonces`, `POST
 * /runs`, `POST /runs/{id}/approval`, `GET /runs`, `GET /runs/{id}`, `GET
 * /runs/{id}/episodes`, `GET /bench/gate`, `GET /bench/settings`, `GET /artefacts`
 * and the two under `/report/{id}` the report screen reads — and the field names are
 * the backend's own, `snake_case` and all, because the request body is a contract
 * with `backend/api/app.py` rather than a shape this app is free to choose. A
 * camel-cased mirror would be one rename away from posting a body the API
 * refuses, and the refusal would arrive as a `422` nobody could read.
 *
 * **Nothing here throws for a refusal.** A registration the bench refuses is a
 * step the operator has to complete rather than an error the app fell over on
 * (ADR-0007 calls it the authorisation guard for exactly that reason), so
 * `startRun` returns one of three outcomes and every one of them carries the
 * sentence the bench wrote. An exception would be caught somewhere far from the
 * screen that has to say what to do next, and the sentence would be lost on the
 * way. What *is* thrown is a fetch that never reached the bench at all, and
 * `startRun` turns that into an outcome too — see `unreachable`.
 *
 * **A start refusal always costs the nonce.** `BenchRuns.start` discards the
 * value from its issued set before it does anything else, so one nonce starts one
 * run and no more — whether that run was refused, and whether the answer ever
 * came back. Every non-registered outcome therefore sends the operator back to
 * the plant step with a value the bench has just issued, and none of them offers
 * a retry of the same body.
 */

/** The value the operator plants, the probe that will ask for it, and why. */
export interface NonceIssued {
  nonce: string
  echo_probe: string
  statement: string
}

/** The endpoint the bench is being asked to attack, as the operator declares it. */
export interface TargetBody {
  name: string
  url: string
  auth_token: string
  agent_type: string
  exposes_tool_calls: boolean
  declared_tools: string[]
  sends: number
}

/**
 * The three statements, one field each, beside who made them.
 *
 * Three booleans rather than one `i_agree`, because the record has to show *what*
 * was attested — and the API will not construct an `Attestation` with any one of
 * them withheld.
 */
export interface AttestationBody {
  identity: string
  authorised_to_test: boolean
  not_production: boolean
  accepts_provider_policy_and_cost: boolean
}

/**
 * What one call on this endpoint costs the operator, as the operator states it.
 *
 * `price_per_call: null` is a declaration and not an omission: the run reports
 * *not priced* rather than zero, because an unknown cost and a free run are
 * different facts and only one of them is safe to confirm without reading
 * further.
 */
export interface CostBody {
  price_per_call: string | null
  currency: string
}

/** Everything a run needs before it may exist, and nothing it can default. */
export interface StartRunBody {
  target: TargetBody
  attestation: AttestationBody
  nonce: string
  cost: CostBody
  note_planted: boolean
  /**
   * Whether the nonce is in the target's configuration.
   *
   * `false` drops the data-leakage family from the plan — its canary *is* this
   * value, and a string nowhere in the target cannot leak — and a run with nothing
   * planted also starts without the proof, since nothing could have echoed. Sent on
   * every request rather than omitted, because the bench's default is the guard and
   * a waiver reached by leaving a field out is a waiver nobody made.
   */
  nonce_planted: boolean
  /**
   * Whether the run may start without the target echoing the planted nonce.
   *
   * The declaration for an agent that planted the value and refuses to repeat it,
   * because its disclosure rule cannot tell a registration check from an attack.
   * The probe is still sent, a missing echo no longer stops the run, and the
   * artefact records control as declared and not proved — while the leakage family,
   * which turns on `nonce_planted` above and not on this, still runs (ADR-0025).
   */
  echo_waived: boolean
}

/**
 * One layer's figure on the consent surface, as `LayerFigurePayload` sends it.
 *
 * `kind` is the whole point of the record: `exact` is a fact and `ceiling` is a
 * bound, and the bench carries the difference in a field rather than in prose so
 * that nothing downstream can present a bound as though it were arithmetic
 * (`budget.py`). `basis` is that arithmetic in words, which is what makes the
 * number checkable rather than believable, and `cost` is already rendered — `≤`
 * and currency and all — because the money is the operator's declaration and this
 * app has no business recomputing it.
 */
export interface LayerFigure {
  calls: number
  kind: string
  basis: string
  cost: string
}

/**
 * The consent surface exactly as the interrupt is holding it.
 *
 * **`total`, `hard_ceiling` and `presented` are on the wire and the run screen
 * renders none of them.** They are typed here rather than dropped from the type
 * because the run screen's first acceptance criterion is the *absence* of a
 * blended number, and an absence is only assertable against a field a test can
 * name (`interrupt.test.ts` scans the view for both figures). The bench builds
 * them as bounds and is right to — ADR-0007's own table prints a bounded total —
 * but the screen shows the two layers and the ceiling each one is enforced
 * against, which is the same disclosure with nothing spanning the layers. See
 * `interrupt.ts`.
 */
export interface RunEstimate {
  scored: LayerFigure
  adaptive: LayerFigure
  total: LayerFigure
  hard_ceiling: LayerFigure
  scored_ceiling: number
  adaptive_ceiling: number
  currency: string
  presented: string[]
}

/**
 * A run that exists and is holding its interrupt.
 *
 * `estimate` is the consent surface the graph is holding, and it arrives here
 * because this is the only response that carries it: `GET /runs/{id}` reports
 * progress and no figures, so the run screen is shown the estimate that came back
 * from the registration that made the run (`interrupt.ts` says how it gets
 * there). `spent` is per layer with no total beside it, which is why it is a map
 * of two counters rather than a number.
 */
export interface RunStarted {
  run_id: string
  status: string
  statement: string
  estimate: RunEstimate
  spent: Record<string, number>
  cases: number
  families_not_run: Record<string, string>
}

/**
 * Where a run has got to, in the two fields this screen reads.
 *
 * The per-layer positions are deliberately absent: progress belongs to the run
 * screen, and a register screen that could read a scored position is a register
 * screen somebody will one day print a total on. What registration needs is the
 * status and the sentence beside it.
 */
export interface RunStanding {
  run_id: string
  status: string
  statement: string
}

/** Where the scored layer is: family, case and attempt. */
export interface ScoredPosition {
  family: string
  case_id: string
  attempt: number
}

/**
 * Where the adaptive layer is: family, episode and turn.
 *
 * A second interface rather than a shared one with a layer label, for the reason
 * the API keeps two models: the units differ, and a type that could hold either
 * would let a reader compare an attempt with a turn — the arithmetic CONTEXT.md
 * keeps apart and ADR-0010 forbids.
 */
export interface AdaptivePosition {
  family: string
  episode: number
  turn: number
}

/** What the scored layer has reached, spent and found. Its own figures only. */
export interface ScoredProgress {
  reached: boolean
  statement: string
  position: ScoredPosition | null
  calls_spent: number
  /** `null` while no attempt has come back — absent, and never a rate of zero. */
  succeeded_attempts: number | null
}

/** What the adaptive layer has reached, spent and found. Nothing here is scored. */
export interface AdaptiveProgress {
  reached: boolean
  statement: string
  position: AdaptivePosition | null
  calls_spent: number
  /** Routes episodes found. `null` while no episode has ended, never a zero. */
  adaptive_findings: number | null
}

/** The named outcome that stopped a run on the wire, and what it is not. */
export interface TransportOutcome {
  failure: string
  statement: string
}

/** Where a finished run's three files are served, once there are three. */
export interface ReportLocation {
  path: string
  rendering: string
  signature: string
  /** The three results over those three files, for a caller with no shell. */
  verification: string
  statement: string
}

/** One family's figures, each beside the counts it was derived from. */
export interface FamilyEntry {
  family: string
  verdict_class: string
  successes: number
  attempts: number
  rate: number
  interval: { lower: number; upper: number }
  interval_confidence: number
  band: string
  /**
   * The band in the bench's shared wording, which names its two reference agents.
   *
   * Typed because it is on the wire and **never rendered** — the rendered Markdown
   * refuses it for the same reason (`rendering.BAND_IN_A_TARGET_REPORT`): "your
   * agent sits between the weak and the hardened reference" is a comparison doing a
   * composite judgement's work, and ADR-0018 point 6 keeps the bench's calibration
   * equipment out of a user's report. `report.ts` states the band in ADR-0014's own
   * wording instead, which describes both anchors by construction.
   */
  band_stated: string
  discrimination: number | null
  coverage: CoverageNote[]
  reliability: ReliabilityFigure | null
}

/**
 * What a family's cases test *one case within*, and what they do not test.
 *
 * ADR-0002: a published identifier is a secondary label and never a coverage
 * claim, so the boundary travels beside it and is shown beside the figure it
 * qualifies — a family reported as holding, with nothing next to it, reads as a
 * cleared category.
 */
export interface CoverageNote {
  identifier: string
  tests_one_case_within: string
  does_not_test: string
}

/** κ with the counts it was measured over and the floor it faced. */
export interface ReliabilityFigure {
  kappa: number
  agreements: number
  transcripts: number
  floor: number
  stated: string
}

/**
 * A judged family whose rate this report may not publish, and the reading that
 * barred it.
 *
 * No rate, no interval and no band on this record, and there is nowhere for one:
 * the attempts were made and the rate is on the run, and what it does not have is
 * a statable evidentiary strength (ADR-0015).
 */
export interface WithheldFamily {
  family: string
  reason: string
  floor: number
  kappa: number | null
  agreements: number | null
  transcripts: number | null
  stated: string
}

/** A family the target could not answer. Three fields, and none of them is a rate. */
export interface NotMeasurableFamily {
  family: string
  reason: string
  stated: string
}

/** The two cut points a band is read against, declared in advance. */
export interface BandCuts {
  holds_at_or_below: number
  fails_at_or_above: number
  stated: string
}

/** What the scored layer measured, and the three kinds of absence beside it. */
export interface MeasuredSection {
  reproducibility: string
  reproducibility_stated: string
  cuts: BandCuts
  deterministic: FamilyEntry[]
  judged: FamilyEntry[]
  withheld: WithheldFamily[]
  not_measurable: NotMeasurableFamily[]
}

/** One declared control and what the attacks made of it. Case ids, no counts. */
export interface ScannedControl {
  control: string
  family: string
  status: string
  broken_by: string[]
  not_measurable: string | null
  stated: string
}

/** A control the checklist asks about that this target did not claim. */
export interface AbsentControl {
  control: string
  stated: string
}

/** The declared-and-defeated join: statuses and names, and no figure at all. */
export interface DeclaredSection {
  reproducibility: string
  reproducibility_stated: string
  controls: ScannedControl[]
  defeated: string[]
  absent: AbsentControl[]
}

/** One episode as the adaptive section reports it: prose, and never payload text. */
export interface ReportedEpisode {
  family: string
  outcome: string
  turns: number
  description: string
  stated: string
}

/** One agent's search, carrying its own reproducibility label (ADR-0010). */
export interface AdaptiveSection {
  reproducibility: string
  reproducibility_stated: string
  stated: string
  episodes: ReportedEpisode[]
  families_broken: string[]
}

/** A published risk category the bench does not test at all. Not a defect. */
export interface CoverageGap {
  category: string
  reason: string
  stated: string
}

/**
 * The bench's own gate result, or the stated absence of one.
 *
 * `cited: false` is a sentence and not a blank — an uncited instrument is a fact
 * about the bench. Neither shape carries anything about the target: the bench
 * passed its gate, and the target has rates and bands (ADR-0018).
 *
 * **Two carriers, one shape.** It arrives inside a report's provenance block, and
 * it arrives on its own from `GET /bench/gate` for a screen that is asking about
 * the instrument rather than about a run. The backend writes both through one
 * serialiser (`payload.citation`), so this one type reads both and a test compares
 * them over the same run.
 *
 * **Two addresses and no figures.** `document` is the gate run in prose and
 * `record` is the same gate run as fields, so a reader reaches every per-family
 * figure without parsing a sentence (ADR-0023). Neither of them is a figure, and
 * nothing in this app opens either.
 *
 * **`document: null` is a third fact, not an empty field.** A gate run started from
 * the console leaves the record and no dated prose, so there is no file name to
 * carry — and the figures are in `record` either way. Typed as an absence so that no
 * screen renders a sentence where it expected a path.
 */
export type GateCitation =
  | {
      cited: true
      outcome: string
      decided_on: string
      library: { cases: number; digest: string }
      document: string | null
      record: string
      stated: string
    }
  | { cited: false; stated: string }

/** How this artefact was made — and nothing about what it found. */
export interface ReportProvenance {
  target: string
  attestation: {
    identity: string
    endpoint_sha256: string
    recorded_at: string
    statements: string[]
  }
  models: { calibration: string; adjudicating: string; attacking: string }
  library: { cases: number; digest: string; stated: string }
  /** Per layer, as the record keeps them. Nothing adds these two. */
  calls_spent: Record<string, number>
  gate: GateCitation
  rule: {
    interval_confidence: number
    attempts_per_case: number
    kappa_floor: number
    stated: string
  }
}

/**
 * The signed payload, as the served bytes parse.
 *
 * The field names are the artefact's own because that is what a signature is
 * over: this app parses the document a recipient verifies rather than a shape
 * chosen for a screen. There is no summary field here and no place to add one —
 * a reader who wants a single number will build one out of whatever is on the
 * page, so the page does not offer one (ADR-0005).
 */
export interface TargetReport {
  artefact: string
  artefact_version: number
  target: string
  measured: MeasuredSection
  declared: DeclaredSection
  adaptive: AdaptiveSection
  coverage_gaps: CoverageGap[]
  provenance: ReportProvenance
  rendered_sha256: string | null
  key_id: string | null
}

/** One of the three results: what it found, under its own name, and the words. */
export interface CheckResult {
  outcome: string
  statement: string
}

/**
 * What a verifier makes of one run's three files. Three results, always all three.
 *
 * A response carrying the signature alone would let its reader infer
 * re-derivability from integrity, which is the inference ADR-0017 exists to
 * prevent — so the two claims arrive with the results and are shown with them.
 * `checked_by` says whose check this is, and it is not the recipient's.
 */
export interface Verification {
  artefact: string
  artefact_version: number
  target: string
  signature: CheckResult
  binding: CheckResult
  arithmetic: CheckResult
  verified: boolean
  contradicted: boolean
  integrity: string
  re_derivability: string
  checked_by: string
}

/**
 * One run in flight, reported per layer, as the screen that polls it reads it.
 *
 * `RunStanding` extended rather than restated, so that the register screen's
 * narrow read of this same route stays a narrowing of one type instead of a second
 * description of it. There is no field here that spans the two layers, and this
 * app adds none: calls spent and findings so far live inside `scored` and
 * `adaptive` and nowhere else, so a total would have to be written out in front of
 * the two labels saying what was being added.
 */
export interface RunProgress extends RunStanding {
  scored: ScoredProgress
  adaptive: AdaptiveProgress
  transport: TransportOutcome | null
  report: ReportLocation | null
  recent: AttemptExchange[]
  families: FamilyRun[]
}

/**
 * One probe, in the words the attacker composed and the target received.
 *
 * A **probe** and never a case: a case is a recorded payload with a stated
 * criterion, and this is a message a model invented mid-run (CONTEXT.md). `turn` is
 * the ordinal the bench counted it at and nothing divides by it.
 *
 * `confirmed_the_break` is the bench's derivation and not this app's guess: the
 * canary check reads an episode's last transcript, so a broken episode's break was
 * confirmed after its last probe. It is false on every probe of a censored one.
 */
export interface ProbeAsSent {
  turn: number
  probe: string
  /** What the target said back, in full. Empty for a reply the transport could not read. */
  reply: string
  /**
   * What the target did on this turn, rendered, or `null` from a target that returns
   * no trace. `null` and an empty trace are different answers: one cannot be measured
   * on scope creep or halt defeat at all, the other took no action.
   */
  tool_trace: string | null
  /**
   * What this turn was found to be: broke it, no break, or not checkable.
   *
   * Three answers because two would mislead. Every probe is verified as it comes
   * back, so *no break* is a reading — but a turn whose reply carried nothing the
   * objective's condition reads has no answer at all, and calling that *no break*
   * would describe a defence that was never tested.
   */
  reading: string
  confirmed_the_break: boolean
}

/**
 * Which probe broke one family, or the stated fact that nothing did.
 *
 * A position and never a count: an episode ordinal and a turn, with no field for how
 * many families broke or a proportion of anything. A family broken in two episodes is
 * reported at the first — *when it first worked* is a fact, *how often* would be a rate
 * over episodes that have no denominator (ADR-0010).
 */
export interface FamilyBreak {
  family: string
  broke: boolean
  episode: number | null
  turn: number | null
  probe: string | null
  stated: string
}

/** One episode's outcome, its turn count, and every probe it sent, in order. */
export interface EpisodeProbes {
  family: string
  outcome: string
  turns: number
  probes: ProbeAsSent[]
  stated: string
}

/**
 * The probes one live run's episodes sent, out of the bench's own memory.
 *
 * **Not the signed payload, and it is a different type for that reason.** A
 * `ReportedEpisode` is what the artefact carries — family, outcome, turns and prose
 * — and it has no field a probe could arrive in. This one is served by
 * `GET /runs/{id}/episodes`, held in the process that ran the run, committed
 * nowhere and gone at a restart (ADR-0008, amended). `stated` is the bench's own
 * sentence saying exactly that, and the screen prints it rather than paraphrasing
 * it: a screenshot of the block travels without the paragraph around it.
 */
export interface RunProbes {
  held: true
  run_id: string
  /** One row per family that opened an episode: what broke it, or that nothing did. */
  broke: FamilyBreak[]
  episodes: EpisodeProbes[]
  stated: string
}

/**
 * This run recorded no episode, said in words rather than as an empty list.
 *
 * A run halted at its interrupt, a run nobody approved and a run stopped on the
 * wire all arrive here. An empty list would read as a search that ran and sent
 * nothing, which is a reading about the attacker and is not what happened.
 */
export interface NoProbes {
  held: false
  run_id: string
  stated: string
}

export type RunEpisodes = RunProbes | NoProbes

/**
 * The probes one run's episodes sent, from the process that is holding them.
 *
 * Thrown rather than returned as an outcome, like every other read here: an id this
 * process never started is the answer a restart gives for every earlier run, and the
 * bench's own sentence says so.
 */
export async function runEpisodes(runId: string): Promise<RunEpisodes> {
  return (await fetched(
    `/runs/${encodeURIComponent(runId)}/episodes`,
    'probes this run sent',
  )) as RunEpisodes
}

/**
 * One family's succeeded attempts, with the exchange behind each.
 *
 * Grouped by family because that is the unit a rate is denominated in and the unit
 * the report's cards are read in. **A list and never a figure**: there is no count on
 * this record, and a length taken off `succeeded` would be the numerator of a rate
 * whose denominator is on the report. A family is here only if something in it
 * succeeded, so the absence of a family is not a zero.
 */
export interface FamilyExchanges {
  family: string
  /**
   * How this family's verdicts were reached, off the attempts themselves.
   *
   * Carried so a reader knows which instrument called the attack a success before
   * they read the reply: a deterministic verdict is re-derivable from the text in
   * front of them, a judged one is an adjudicator's reading with a κ of its own
   * (ADR-0004). Never inferred from the family name.
   */
  verdict_class: string
  succeeded: AttemptExchange[]
}

/**
 * The attacks that worked on one live run, out of the bench's own memory.
 *
 * **Not the signed payload, and it is a different type for that reason.** The
 * artefact carries each family's successes over its attempts and no transcript —
 * `document()` is built key by key so an attempt's transcript has nowhere to arrive
 * — and this is served by `GET /runs/{id}/attempts` from the process that made them,
 * committed nowhere and gone at a restart (ADR-0008, amended). `stated` is the
 * bench's own sentence saying exactly that, printed rather than paraphrased: a
 * screenshot of the block travels without the paragraph around it.
 */
export interface RunExchanges {
  held: true
  run_id: string
  families: FamilyExchanges[]
  stated: string
}

/**
 * Nothing in this run's scored layer succeeded, said in words rather than as an
 * empty list.
 *
 * A run halted at its interrupt, a run nobody approved, a run refused at
 * registration and a target that resisted every attempt all arrive here, and only
 * the last is a reading about the target. An empty list would read as the last one
 * whichever it was.
 */
export interface NoExchanges {
  held: false
  run_id: string
  stated: string
}

export type RunAttempts = RunExchanges | NoExchanges

/**
 * The exchanges behind one run's succeeded attempts, from the process holding them.
 *
 * Thrown rather than returned as an outcome, like every other read here: an id this
 * process never started is the answer a restart gives for every earlier run, and the
 * bench's own sentence says so.
 */
export async function runAttempts(runId: string): Promise<RunAttempts> {
  return (await fetched(
    `/runs/${encodeURIComponent(runId)}/attempts`,
    'exchanges behind this run’s successes',
  )) as RunAttempts
}

/**
 * One attempt as evidence: what went out, what came back, and how it was scored.
 *
 * The bench serves the last one and never the log, so this arrives as a list of at
 * most one and *nothing has come back yet* is the empty list rather than a null.
 *
 * `verdict` is the attacker's point of view, which is the sense this whole bench
 * counts in: *succeeded* is the attack working.
 */
export interface AttemptExchange {
  family: string
  case_id: string
  agent: string
  attempt: number
  sent: string
  reply: string
  verdict: string
  verdict_class: string
  status_code: number
  sends: number
}

/**
 * How far one family has got against this target, and how it is answering.
 *
 * The counts are the bench's and this app divides none of them: `resisted` and
 * `succeeded` partition `attempted`, and a screen draws each against `of`, which is
 * the family's own denominator on this run's plan. What fills as the run goes is a
 * length; the rate that is a measurement arrives on the report with its interval and
 * its band beside it (ADR-0005).
 *
 * `not_run` is the reason a family is out of the plan, or empty. A family the caller's
 * declarations dropped has a denominator of zero, and a zero over zero drawn as an
 * empty bar would read as one that has not started yet.
 */
export interface FamilyRun {
  family: string
  attempted: number
  of: number
  resisted: number
  succeeded: number
  not_run: string
}

/** What one run's scored layer put on the wire, against the scored ceiling. */
export interface ScoredSpend {
  calls_spent: number
  statement: string
}

/**
 * What one run's adaptive layer put on the wire, against the adaptive ceiling.
 *
 * A second interface rather than one `LayerSpend` read twice, matching the two
 * models the route serves. The two figures are held to two separate ceilings, and
 * a type that accepted either would be a type something could be accumulated
 * through — the widening ADR-0010 asks anyone reaching for it to stop at.
 */
export interface AdaptiveSpend {
  calls_spent: number
  statement: string
}

/**
 * One run on the record: what it was against, when, where it got to, what it spent.
 *
 * A row and never a report. There is no rate here, no band and no verdict — a
 * figure lifted out of a signed report onto a list would arrive without the
 * denominator that was printed beside it. The target is named and its URL is
 * nowhere (ADR-0008).
 */
export interface RunRow {
  run_id: string
  target: string
  /**
   * When the run went on the record — the attestation taken, the estimate
   * declared — which is before the target was asked to echo anything. Not a
   * registration time: registration is the nonce echo, and a declined run never
   * reached one.
   */
  recorded_at: string
  status: string
  statement: string
  scored: ScoredSpend
  adaptive: AdaptiveSpend
}

/**
 * The runs on the record, most recently recorded first.
 *
 * No count and no totals block: the route returns rows and never a summary of
 * them, so there is no field here for a figure spanning two runs or two layers.
 */
export interface RunList {
  runs: RunRow[]
  statement: string
}

/**
 * The answer to one run's interrupt. A `confirmed: true` is the only thing that
 * spends.
 *
 * `reason` is carried on a no as well as a yes, because a declined run is a result
 * about the estimate: a figure somebody refused is the one piece of evidence that
 * the cost display is doing its job (`approval.py`).
 */
export interface ApprovalBody {
  confirmed: boolean
  identity: string
  reason: string
}

/**
 * The status a run settles at when the target never echoed the planted nonce.
 *
 * The echo cannot be checked when the run is started: the probe is itself a call
 * on the operator's endpoint, and ADR-0007 puts the halt *ahead* of registration
 * so that a run has spent nothing by the time it asks for consent. So the failure
 * this screen has to recover from arrives as a run status and not as a response
 * to the registration request, and it is matched by name rather than by reading
 * the statement, because the statement is prose written for a human.
 */
export const REGISTRATION_REFUSED = 'registration_refused'

/**
 * What became of a registration request.
 *
 * `refused` is the bench declining — a nonce it never issued, an incomplete
 * attestation, a declaration it will not accept — and it carries the bench's own
 * words. `unreachable` is no answer at all, which is a different fact and gets a
 * different sentence: the operator has an API to start, not a form to fix.
 */
export type StartOutcome =
  | { kind: 'registered'; run: RunStarted }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

const UNREACHABLE =
  'the bench did not answer, so it is not known whether it recorded this ' +
  'registration. Treat the nonce as spent: check that the API is running, then ' +
  'plant the value the bench issues next and register again.'

const REFUSED_WITHOUT_A_REASON =
  'the bench refused this registration and returned no reason with it. Nothing ' +
  'was sent to the target. Plant the value the bench issues next and register ' +
  'again.'

/** Issue a nonce. One value, one run: the next run needs one planted again. */
export async function issueNonce(): Promise<NonceIssued> {
  const response = await fetch('/nonces', { method: 'POST' })
  if (!response.ok) {
    throw new Error(
      `the bench refused to issue a nonce (HTTP ${response.status}), so there is ` +
        'nothing to plant and no registration to attempt',
    )
  }
  return (await response.json()) as NonceIssued
}

/**
 * Register a target: record the attestation, declare the estimate, and halt.
 *
 * A `202` means the run exists and is holding its interrupt, which is *before*
 * anything has been sent to the target. It does not mean the target echoed the
 * nonce; nothing has asked it yet.
 */
export async function startRun(body: StartRunBody): Promise<StartOutcome> {
  let response: Response
  try {
    response = await fetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return { kind: 'unreachable', statement: `${UNREACHABLE} (${unreachable})` }
  }
  if (response.ok) {
    return { kind: 'registered', run: (await response.json()) as RunStarted }
  }
  return { kind: 'refused', statement: await refusalIn(response) }
}

/**
 * The sentence the bench sent with its refusal.
 *
 * FastAPI puts a raised `HTTPException`'s message in `detail` as a string, and
 * its own body-validation errors in the same field as a list of objects. Both are
 * read here rather than only the first, because the second is what arrives when
 * this app posts a field the API's models reject — and a screen that showed
 * "refused, no reason given" for it would be hiding the one message that says
 * which field.
 */
async function refusalIn(response: Response): Promise<string> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    return REFUSED_WITHOUT_A_REASON
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((problem) => {
        const { loc, msg } = problem as { loc?: unknown[]; msg?: string }
        const where = Array.isArray(loc) ? loc.join('.') : ''
        return where ? `${where}: ${msg ?? ''}` : `${msg ?? ''}`
      })
      .join('; ')
  }
  return REFUSED_WITHOUT_A_REASON
}

/** Where one run has got to, or the reason this app could not find out. */
export async function runStanding(runId: string): Promise<RunStanding> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) {
    throw new Error(
      `the bench has no run ${runId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as RunStanding
}

/**
 * The same route, read wide: the run's position and spend in both layers.
 *
 * Two functions over one route rather than one function two callers narrow, so
 * that the register screen keeps the read it was given. Nothing about this request
 * touches the target — polling a run's standing is a question put to the bench.
 */
export async function runProgress(runId: string): Promise<RunProgress> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) {
    throw new Error(
      `the bench has no run ${runId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as RunProgress
}

/**
 * What became of an answer to an interrupt.
 *
 * `no_longer_waiting` is its own outcome rather than a refusal, because it is the
 * one refusal that has already decided the run: an interrupt is answered once, and
 * a `409` means either that it was answered already or that the hour ran out and
 * the graph was told nobody answered. Either way the run is settled and the screen
 * has a standing to read rather than an answer to retry — offering a retry would be
 * offering to consent to a spend that already happened or already will not.
 */
export type ApprovalOutcome =
  | { kind: 'answered'; run: RunStarted }
  | { kind: 'no_longer_waiting'; statement: string }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

const ANSWER_UNREACHABLE =
  'the bench did not answer, so it is not known whether it recorded this ' +
  'decision. Read the run’s standing before answering again: an interrupt is ' +
  'answered once, and if this one was taken the run is already under way.'

/**
 * Answer one run's interrupt.
 *
 * **This is the only function in this app that can cause a call on the target**,
 * and only ever with a `confirmed: true` that `interrupt.ts` refused to build
 * without an explicit confirmation. A `confirmed: false` goes on the wire too, and
 * that is deliberate: it records the run as *declined* by a person rather than
 * leaving it to time out as *unanswered*, and the bench's own sentence for it says
 * that nothing was sent to the target and nothing was spent.
 */
export async function answerTheInterrupt(
  runId: string,
  body: ApprovalBody,
): Promise<ApprovalOutcome> {
  let response: Response
  try {
    response = await fetch(`/runs/${encodeURIComponent(runId)}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return {
      kind: 'unreachable',
      statement: `${ANSWER_UNREACHABLE} (${unreachable})`,
    }
  }
  if (response.ok) {
    return { kind: 'answered', run: (await response.json()) as RunStarted }
  }
  const statement = await refusalIn(response)
  if (response.status === 409) {
    return { kind: 'no_longer_waiting', statement }
  }
  return { kind: 'refused', statement }
}


/**
 * The signed payload for one run, parsed from the bytes the route serves.
 *
 * Fetched from the path the run's own record advertises rather than from a path
 * this app builds, so the screen cannot go looking somewhere the bench does not
 * serve. What arrives is the artefact: no envelope, no figure the route added.
 */
export async function reportPayload(path: string): Promise<TargetReport> {
  return (await fetched(path, 'signed payload')) as TargetReport
}

/**
 * The three results over that run's three files.
 *
 * Computed by the bench that produced the artefact, which is why `checked_by`
 * travels with them and why the screen prints it: a sender's word for their own
 * document is the thing a signature exists to replace, and what makes this worth
 * showing is the answer that says *do not send this yet*.
 */
export async function reportVerification(path: string): Promise<Verification> {
  return (await fetched(path, 'verification')) as Verification
}

/** Where the bench's own gate citation is read. About the bench, not about a run. */
export const BENCH_GATE_PATH = '/bench/gate'

/**
 * The rule the gate is decided under, every declared threshold of it.
 *
 * `stated` is the whole rule as the gate prints it beside its answer — the same
 * text `scripts/gate.py` writes into its own document — and the fields beside it
 * are the declared record's numbers, so a sentence on a screen that needs one can
 * name it rather than restate it in words. Not one field here is a measurement: a
 * gate run's per-family rates and its per-family `D` are in the record its
 * citation names, and are in no response this app reads (spec §75, ADR-0023).
 *
 * **Every threshold is typed and the screen prints the rule verbatim.** The
 * numbers are carried whole because the rule is a record and half a record invites
 * the next screen to add the other half; what the gate screen renders is `stated`
 * plus the two floors its own sentences name, which is the same division
 * `interrupt.ts` makes over the estimate's fields.
 */
export interface DeclaredRule {
  stated: string
  interval_confidence: number
  attempts_per_case: number
  discrimination_floor: number
  retirement_floor: number
  kappa_floor: number
  gold_transcripts_per_family: number
  tolerated_inversions: number
  family_count: number
  families_required: number
  monotonic_families_required: number
  minimum_fit_families: number
}

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
 * **Nothing under `/bench` is a write, and starting a gate run is not here.** The
 * four functions below post to and read `/gate-runs`, which is its own route
 * family for the reason a gate run is its own record: a run produces rates about
 * somebody's target, a gate run produces a decision about this bench (ADR-0018,
 * ADR-0021).
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

/** Where a gate run is started, listed and read. Its own family, never `/runs`. */
export const GATE_RUNS_PATH = '/gate-runs'

/**
 * This bench can run a gate, and what starting one would do first.
 *
 * `available` is the field the screen branches on and it is a literal on both
 * shapes, so *can* and *cannot* are two facts rather than one record with empty
 * fields — the idiom `GateCitation` already uses for a citation and its absence.
 */
export interface MayStart {
  available: true
  library: string
  statement: string
}

/**
 * This bench cannot run a gate, and the named reason it cannot.
 *
 * Four names on the wire, and two of them are permanent facts about the deployment
 * while two are about right now. The screen states whichever it is told and offers
 * no control either way: *this build ships no reference agents* is not answered by
 * trying again, and *a gate run is already holding the library* is.
 */
export interface MayNotStart {
  available: false
  refusal: string
  stated: string
}

export type GateRunStart = MayStart | MayNotStart

/**
 * One gate run on the record: when, where it got to, what it spent per layer.
 *
 * A row and never a decision. `spent` is two keys and there is no third: the two
 * layers are enforced against separate counters and nothing adds them (ADR-0010).
 */
export interface GateRunRow {
  gate_run_id: string
  recorded_at: string
  status: string
  statement: string
  spent: Record<string, number>
}

/** The gate runs on the record, and whether another may start right now. */
export interface GateRuns {
  start: GateRunStart
  gate_runs: GateRunRow[]
  statement: string
}

/**
 * What a gate run's scored layer will cost, in the units it is declared in.
 *
 * Attempts over cases over agents, exact because it is a multiplication. Not one
 * numeric field here appears on the adaptive figure below: the two layers share no
 * number, so there is no name in this app under which a total could be built.
 */
export interface ScoredEstimate {
  layer: string
  attempt_calls: number
  attempt_ceiling: number
  cases: number
  attempts_per_case: number
  kind: string
  basis: string
  cost: string
  statement: string
}

/**
 * What a gate run's adaptive layer may cost, in the units *it* is declared in.
 *
 * Turns over episodes over families over agents, and a bound rather than a figure:
 * an attacker that chooses its own route has no exact cost, and an average here
 * would invite a gate run to exceed what was agreed to (ADR-0007).
 */
export interface AdaptiveEstimate {
  layer: string
  turn_calls: number
  turn_ceiling: number
  turns_per_episode: number
  episodes_per_family: number
  kind: string
  basis: string
  cost: string
  statement: string
}

/** Two figures, two ceilings, and no third field anywhere on the response. */
export interface GateRunEstimate {
  scored: ScoredEstimate
  adaptive: AdaptiveEstimate
  currency: string
  statement: string
}

/**
 * A gate run recorded and halted in front of its estimate.
 *
 * The estimate arrives once, here, from the request that created the gate run —
 * the same division `POST /runs` makes, because the route that reports progress
 * reports no estimate: nothing on it spans the two layers.
 */
export interface GateRunStarted {
  gate_run_id: string
  status: string
  statement: string
  estimate: GateRunEstimate
  library: string
  agents: string[]
  cases: number
}

/** The three attestation statements and the declared cost, and nothing else. */
export interface StartGateRunBody {
  attestation: AttestationBody
  cost: CostBody
}

/**
 * One reference agent's failure rate on one family, with what it came from.
 *
 * The counts and the interval travel with the value, because a rate with no
 * denominator beside it is a number a reader has to trust.
 */
export interface MeasuredRate {
  agent: string
  value: number
  successes: number
  attempts: number
  lower: number
  upper: number
  stated: string
}

/**
 * One family at one gate run: three rates, its `D`, its ordering, its verdict.
 *
 * There is no band here and no severity. A band summarises one family for one
 * *target* and the subject of a gate run is the bench (ADR-0014, ADR-0018).
 */
export interface FamilyFigures {
  family: string
  rates: MeasuredRate[]
  discrimination: number
  intervals_separate: boolean
  inversions: number
  monotonic: boolean
  passes: boolean
  /**
   * Why this family decided nothing, or null where it decided something.
   *
   * On the family's own line and not only in `GateDecided.excluded`, so nothing
   * here reads as a contribution to the outcome: its rates were measured and are
   * recorded, and they decide nothing in either count (ADR-0015).
   */
  excluded: string | null
  stated: string
}

/** One family barred from the counts, with the reason and the reading behind it. */
export interface ExcludedFamily {
  family: string
  reason: string
  kappa: number | null
  stated: string
}

/** One judged family's κ against the gold set, or the stated absence of one. */
export interface JudgedReliability {
  family: string
  kappa: number | null
  stated: string
}

/**
 * What a gate run decided, and everything needed to re-derive it.
 *
 * Six families at once, which makes this the surface most likely to grow a
 * composite: a mean of six discrimination scores would look like a figure about the
 * bench. There is no field for one, and the counts on it are counts *of families*
 * that the rule declares (ADR-0005, ADR-0003).
 */
export interface GateDecided {
  outcome: string
  families_passing: number
  families_monotonic: number
  fit_families: number
  families: FamilyFigures[]
  excluded: ExcludedFamily[]
  reliability: JudgedReliability[]
  library: { cases: number; digest: string }
  attempts: number
  agents: string[]
  stated: string
  read_from: string
}

/** What a gate run wrote to the case library, and where it wrote it. */
export interface WroteBack {
  library: string
  readings: number
  unread: string[]
  retired: string[]
  stated: string
}

/**
 * Where one gate run has got to, and what it decided if it has.
 *
 * `rule` is above `decision` on the wire as it is on the screen: an outcome read
 * with no bar beside it is a verdict somebody trusted (ADR-0003). Progress is the
 * same two per-layer readings a run reports, because a position is neither a run
 * nor a gate run and the units are the units either way.
 */
export interface GateRunReading {
  gate_run_id: string
  status: string
  statement: string
  rule: DeclaredRule
  scored: ScoredProgress
  adaptive: AdaptiveProgress
  families: FamilyProgress[]
  /**
   * The last attempt only, or empty before the first has come back.
   *
   * A list of one and not a field, because *nothing has come back yet* is a real
   * state and an empty list says it without a null. The route carried five for a
   * while; the sequence of what a run did is on the record it writes, not here.
   */
  recent: AttemptPayload[]
  decision: GateDecided | null
  written: WroteBack | null
}

/**
 * One reference agent's share of one family: how far, and how it is going.
 *
 * Two counts for how far and two for how the attempts made so far were answered. The
 * three arrive in construction order — hardened, weak, trivial — read off the record's
 * own roles rather than off a name.
 *
 * `resisted` and `succeeded` split `attempted` and neither is a rate: they are drawn
 * against `of`, this agent's own denominator, so a bar of them fills as the run goes
 * instead of reading as a finished figure. In the attacker's sense, as everything in
 * this bench is counted — `succeeded` is the attack working, so a trivial agent with a
 * high `succeeded` is the contrast doing its job.
 */
export interface AgentProgress {
  agent: string
  attempted: number
  of: number
  resisted: number
  succeeded: number
}

/**
 * How far one family has got, over its own denominator.
 *
 * Six of these, always, whether a family has started or not. **Neither the count nor
 * the denominator may be added across the six**: a run-wide figure would be a total
 * across six denominators, which is the arithmetic ADR-0005 refuses. And there is no
 * count of verdicts here — how well a family is going is a rate with an interval and
 * a band, and it belongs to the decision.
 */
export interface FamilyProgress {
  family: string
  attempted: number
  of: number
  agents: AgentProgress[]
}

/**
 * One attempt as evidence: the message sent, the reply, and the verdict on it.
 *
 * Served for a gate run because the three agents are this bench's own equipment
 * talking to itself. `verdict` is the attacker's point of view — *succeeded* is the
 * attack working — and `verdict_class` is how that was reached, which the screen
 * prints beside it because a deterministic *resisted* and a judged one are not the
 * same claim (ADR-0004).
 */
export interface AttemptPayload {
  family: string
  case_id: string
  agent: string
  attempt: number
  sent: string
  reply: string
  verdict: string
  verdict_class: string
  status_code: number
  sends: number
}

/**
 * The gate runs on the record, and whether this bench may start another.
 *
 * Read before a control is drawn rather than after one is pressed: a screen that
 * offered a start button on a deployment which ships no reference agents would be
 * offering an operation the bench refuses, and the refusal it would then show is a
 * fact the screen could have stated in the first place.
 */
export async function gateRuns(): Promise<GateRuns> {
  return (await fetched(GATE_RUNS_PATH, 'gate runs')) as GateRuns
}

/**
 * Start a gate run: record the three statements, declare the estimate, and halt.
 *
 * A `202` means the gate run exists and is holding its interrupt, which is before
 * anything has been sent to a reference agent and before one case record has been
 * written to. It also means this bench's case library is now held by it — a second
 * gate run is refused rather than queued, and the refusal names the holder.
 *
 * The refusals are outcomes rather than exceptions, on `startRun`'s reasoning: a
 * bench that ships no reference agents, holds no writable library, has no
 * adjudicating instrument, or is already running a gate is a state the operator has
 * to be told about in words, and an exception would lose the sentence on the way to
 * whatever caught it.
 */
export async function startGateRun(
  body: StartGateRunBody,
): Promise<GateRunOutcome> {
  let response: Response
  try {
    response = await fetch(GATE_RUNS_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return { kind: 'unreachable', statement: `${GATE_RUN_UNREACHABLE} (${unreachable})` }
  }
  if (response.ok) {
    return { kind: 'started', gateRun: (await response.json()) as GateRunStarted }
  }
  return { kind: 'refused', statement: await refusalIn(response) }
}

/**
 * What became of a request to start a gate run.
 *
 * `refused` carries the bench's own sentence, which is the one that says which of
 * the four reasons it was. `unreachable` is no answer at all: nothing was started,
 * and the operator has an API to check rather than a form to fix.
 */
export type GateRunOutcome =
  | { kind: 'started'; gateRun: GateRunStarted }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

const GATE_RUN_UNREACHABLE =
  'the bench did not answer, so it is not known whether a gate run was started. ' +
  'Read the list of gate runs before asking again: one holds the case library ' +
  'while it goes, and a second would be refused rather than queued.'

/**
 * Answer a gate run's interrupt. A `confirmed: true` is the only thing that spends.
 *
 * The same body a run's interrupt takes, deliberately: the answer to an interrupt is
 * the consent mechanism itself and there is one of those in this app (ADR-0007).
 * What is not shared is the record it answers — this posts under `/gate-runs`, and a
 * run id here is a `404` rather than an interrupt answered for something else.
 *
 * A `confirmed: false` goes on the wire too, for the reason a declined run does: it
 * records the gate run as declined by a person rather than leaving it to time out as
 * unanswered, and the bench's own sentence for it says that nothing was sent and not
 * one case record was written to.
 */
export async function answerTheGateRunsInterrupt(
  gateRunId: string,
  body: ApprovalBody,
): Promise<GateApprovalOutcome> {
  let response: Response
  try {
    response = await fetch(
      `${GATE_RUNS_PATH}/${encodeURIComponent(gateRunId)}/approval`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
  } catch (unreachable) {
    return {
      kind: 'unreachable',
      statement: `${ANSWER_UNREACHABLE} (${unreachable})`,
    }
  }
  if (response.ok) {
    return { kind: 'answered', gateRun: (await response.json()) as GateRunStarted }
  }
  const statement = await refusalIn(response)
  if (response.status === 409) {
    return { kind: 'no_longer_waiting', statement }
  }
  return { kind: 'refused', statement }
}

/** What became of an answer to a gate run's interrupt. */
export type GateApprovalOutcome =
  | { kind: 'answered'; gateRun: GateRunStarted }
  | { kind: 'no_longer_waiting'; statement: string }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

/**
 * Where one gate run has got to, per layer, and what it decided if it has.
 *
 * Polled while it goes. Nothing about this request touches a reference agent —
 * asking a gate run how it is going is a question put to the bench.
 */
export async function gateRunReading(gateRunId: string): Promise<GateRunReading> {
  const response = await fetch(
    `${GATE_RUNS_PATH}/${encodeURIComponent(gateRunId)}`,
  )
  if (!response.ok) {
    throw new Error(
      `the bench has no gate run ${gateRunId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as GateRunReading
}

/** Where the runs on the record are listed. The path a run is started at, read. */
export const RUNS_PATH = '/runs'

/**
 * The runs this bench has on the record, with calls spent per layer.
 *
 * Takes no run id, because it is not about one run — and it is still under `/runs`
 * rather than under `/bench`, because a list of somebody's runs is about their
 * targets and `/bench` is the prefix whose subject is the instrument (ADR-0018).
 *
 * A read, and a bench that has started nothing answers with no rows rather than
 * with a refusal: a fresh deployment is in exactly that state.
 */
export async function benchRuns(): Promise<RunList> {
  return (await fetched(RUNS_PATH, 'list of runs')) as RunList
}

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

/** One failure family, and whether the next run covers it. */
export interface FamilyCovered {
  family: string
  covered: boolean
}

/** One model this console offers as the attacker, and what it is for. */
export interface ModelChoice {
  identifier: string
  decides: string
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
 * **Four of the five bound a layer that is scored on nothing; `attempts_per_case` is
 * the scored denominator.** `attempts_warning` is the bench's own sentence about the
 * difference and the screen prints it rather than paraphrasing it.
 */
export interface Tuning {
  attacker_models: ModelChoice[]
  temperature: number | null
  temperature_bounds: Bounds
  temperature_absent: string
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
  statement: string
}

/** The five settings, as the console sends them. All five every time. */
export interface Tune {
  attacker_model: string
  temperature: number | null
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
 * The one write under `/bench` (ADR-0025). All five settings go every time, because a
 * caller that could send the turn budget without restating the attacker model could
 * leave a bench naming one instrument in a report while another attacked.
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
 * The second write under `/bench` (ADR-0025), and its own statement rather than a
 * field on the tuning request: that one is *how the instruments are set* and takes all
 * five settings every time; this is *what the next run covers*, sent from a different
 * screen. An empty list is refused — a run covering no family attacks nothing.
 */
export async function coverFamilies(families: string[]): Promise<BenchSettings> {
  const response = await fetch(BENCH_FAMILIES_PATH, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ families }),
  })
  if (!response.ok) {
    throw new Error(`the bench did not take these families: ${await refusalIn(response)}`)
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

/**
 * One report route, read, with the bench's own refusal carried out of it.
 *
 * The four refusals are named — no such run, in flight, did not complete, never
 * signed — and the name is the part an operator can act on, so a failed fetch
 * raises with the bench's sentence rather than with a status code. There is no
 * partial report to fall back to and none is invented here.
 */
async function fetched(path: string, what: string): Promise<unknown> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(
      `the bench did not serve the ${what} at ${path}: ${await refusalIn(response)}`,
    )
  }
  return await response.json()
}