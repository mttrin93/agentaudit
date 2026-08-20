/**
 * The bench's HTTP surface as this app is allowed to see it.
 *
 * Eight of the eleven routes are reachable from here — `POST /nonces`, `POST
 * /runs`, `POST /runs/{id}/approval`, `GET /runs`, `GET /runs/{id}`, `GET
 * /bench/gate`, `GET /artefacts` and the two under `/report/{id}` the report
 * screen reads — and the field names are the backend's own,
 * `snake_case` and all, because the request body is a contract with
 * `backend/api/app.py` rather than a shape this app is free to choose. A
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
 */
export type GateCitation =
  | {
      cited: true
      outcome: string
      decided_on: string
      library: { cases: number; digest: string }
      document: string
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
 * gate run's per-family rates and its per-family `D` are in its document and are
 * in no response this app reads (spec §75).
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
 * target, and it takes no run id because it is not about a run. There is no
 * counterpart that starts a gate run: one is 830-odd calls against three
 * reference agents behind a terminal consent flow (PLAN.md §8), so the console
 * cites it, prints the command, and the CLI stays the only entry point. This
 * module has no function that posts anywhere under `/bench` and the API has no
 * route that would take one.
 */
export async function benchGate(): Promise<BenchGate> {
  return (await fetched(BENCH_GATE_PATH, 'gate citation')) as BenchGate
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