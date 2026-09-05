/**
 * The wire shapes more than one API area names, and the reason every one of them is
 * `snake_case`.
 *
 * `bench.ts` was 2024 lines and 131 exports, most of them wire interfaces. #14 split
 * it by API area, and this is the module that made that possible: a shape two areas
 * both name is defined once, here, and every area module imports it. It imports
 * nothing itself, which is what keeps the areas from importing each other.
 *
 * **The field names are the backend's own, `snake_case` and all, because the request
 * body is a contract with `backend/api/app.py` rather than a shape this app is free
 * to choose.** A camel-cased mirror would be one rename away from posting a body the
 * API refuses, and the refusal would arrive as a `422` nobody could read. This is the
 * module that rule is about, so it is written here rather than only in the barrel.
 *
 * **An estimate is two figures and neither is a total.** The scored layer is exact,
 * the adaptive layer is a ceiling, and nothing in this app adds them: a fact plus a
 * bound is a bound, and a total presented as exact is a figure nobody agreed to
 * (ADR-0007). The types carry that distinction, which is why `ScoredProgress` and
 * `AdaptiveProgress` are two interfaces and not one with a flag.
 */

/**
 * One thing the API refused, and the field it refused it at.
 *
 * `field` is the `loc` path joined with dots and edited on the way in no other way
 * — `body.cost.price_per_call` and not `price_per_call` — because that string is
 * also the `id` of the input the screen marks invalid (ADR-0076). A path that was
 * shortened here would be a name the DOM and the wire agree on only until somebody
 * changed the shortening rule.
 */
export interface FieldRefusal {
  field: string
  msg: string
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

/** Where a finished run's three files are served, once there are three. */
export interface ReportLocation {
  path: string
  rendering: string
  signature: string
  /** The three results over those three files, for a caller with no shell. */
  verification: string
  statement: string
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
