/**
 * `GET /report/{id}` and its verification — the signed document as this app reads it.
 *
 * Its own module in #14's split by API area, and the widest set of wire shapes in the
 * app: a target report is the artefact a procurement reader acts on, so every figure
 * on it has a type here rather than being read out of loose JSON.
 *
 * **Nothing here computes a figure.** Every number the report screen shows is a
 * number the payload already carries, printed beside the counts it came from — the
 * same rule the renderer is held to (ADR-0005, D12). A type that held a total would
 * be an invitation to compute one.
 */

import type {
  GateCitation,
  Verification,
} from './contracts'
import {
  fetched,
} from './http'


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

/** How this artefact was made — and nothing about what it found. */
export interface ReportProvenance {
  target: string
  attestation: {
    identity: string
    endpoint_sha256: string
    recorded_at: string
    statements: string[]
  }
  models: {
    calibration: string
    adjudicating: string
    attacking: string
    /** The attacker's sampling temperature, or `null` for two different absences. */
    attacking_temperature: number | null
    /**
     * Which of the three the null is — nobody declared one, or the model accepts
     * none. The number field cannot carry the difference, so the document states
     * it and this app prints the statement rather than interpreting the value.
     */
    attacking_temperature_stated: string
    /** The level the attacker was told to think at, or `null` for three absences. */
    attacking_reasoning_effort: string | null
    /**
     * Which of the four the reading is — the model has no such setting, none was
     * declared, or this bench holds no capability line for the model at all. Two runs
     * of one model at one temperature and different reasoning effort are two
     * different instruments, so the document states the difference and this app
     * prints the statement rather than interpreting the value.
     */
    attacking_reasoning_effort_stated: string
  }
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
