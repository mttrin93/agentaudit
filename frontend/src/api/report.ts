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


/**
 * What a family is labelled with: the entries it claims, and the articles it bears.
 *
 * The whole record and both sentences over it, because the payload carries both and
 * a screen that rebuilt the sentence would be a second copy of a legal mapping in
 * TypeScript — one that can disagree with the signed document nobody would notice.
 * `bears_stated` and `claims_stated` are `labels.bears_stated` and
 * `labels.claims_stated`, which is the one rendering every reader of a label uses
 * (ADR-0040 decision 7, ADR-0044). Whole sentences, naming the Act and the two
 * published lists, so this app prints a rendering rather than appending its own
 * words to a fragment — and each claimed entry carries the title its stored copy
 * transcribes rather than a paraphrase (ADR-0036).
 *
 * The lists are typed because a recipient matching `ASI01:2026` against a published
 * list wants the identifier as a key rather than out of prose; the order inside
 * `articles` is declared and never sorted — the first is the duty the family's
 * failure principally bears on, so a surface with room for one shows `articles[0]`.
 */
export interface FamilyLabel {
  agentic: string[]
  llm: string[]
  articles: string[]
  bears_stated: string
  claims_stated: string
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
  /**
   * The counts, per construction, this family's rate was pooled from.
   *
   * Typed because it is on the wire, on the same terms as `band_stated` above: a
   * renamed key upstream has to fail `tsc` against the served fixture rather than
   * arrive as `undefined` in a browser. The figure above is one rate over every
   * variant the family sent, and what pooling costs is that it depends on the mix —
   * so the mix travels with it (ADR-0055). **Drawing it is not this screen's yet:**
   * the console's own reading of the mix arrives with the selection that produced it
   * (#79), and the signed Markdown already prints it beneath every family's rate.
   */
  variants: VariantCount[]
  reliability: ReliabilityFigure | null
  label: FamilyLabel
}

/**
 * One construction's contribution to a family's pooled rate. Counts, and no rate.
 *
 * No interval and no band per variant, deliberately: an interval invites a band, and
 * a band is a summary of a family against two anchors the gate decided nothing about
 * a slice on (ADR-0014, ADR-0055).
 */
export interface VariantCount {
  transform: string
  transform_stated: string
  successes: number
  attempts: number
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
  /** The duty this family still bears, which withholding a rate does not alter. */
  label: FamilyLabel
}

/** A family the target could not answer. Three fields, and none of them is a rate. */
export interface NotMeasurableFamily {
  family: string
  reason: string
  stated: string
  /** Borne whether or not anything was measured — a property of the family. */
  label: FamilyLabel
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
  /**
   * What a reader comparing two of these documents is owed, in the artefact's own
   * wording: each family's figure is one rate over every construction the run sent,
   * so **two runs are comparable only at equal library version and equal selection**
   * (ADR-0055). Typed because it is on the wire; the screen's own reading of the mix
   * arrives with the selection that produced it (#79).
   */
  variants_stated: string
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
 * One failure as the signed document reports it (ADR-0070 §2a).
 *
 * **Every field is a string, a name off a closed set, or an id**, and that is the
 * type-level half of what keeps this section out of the arithmetic: there is no
 * numeric property here for a later edit to lift off and read against a rate, and no
 * field a severity could arrive in (D3, D12, ADR-0005, ADR-0006).
 *
 * **What is not here has nowhere here to arrive.** No payload text, no reply, no tool
 * trace, no precedent prose and no `Narrative.confidence`: the disclosure answer is
 * made at `assembler.ReportedFinding.of`, one record before the wire, and what the
 * screen may show is what survived it. A sentence that reproduced the case's own
 * payload arrives as a statement that it was withheld, with `withheld` naming which of
 * the two it was — and the finding keeps its case id, its family and its attributed
 * cause, because those are the three facts a reader can check against the record
 * (ADR-0008 as amended, ADR-0070 §2b and §2c).
 */
export interface ReportedFinding {
  case_id: string
  family: string
  /** The published identifier this case tests one case within (ADR-0002). */
  external_id: string
  /** What a reader of this finding is exposed to, off the judge's closed set. */
  exposure: string
  /** The declaration state this failure is read against, off a closed set of three. */
  attributed_cause: string
  /** The control that claims this family, or `null` where none does (ADR-0068). */
  control_claiming: string | null
  transform: string
  /**
   * The attributed cause as a whole sentence, `Attribution.stated()`.
   *
   * Carried and never rebuilt from the three fields above, on `bears_stated`'s own
   * terms: a screen that assembled the sentence would be a second copy of a reading
   * the signed document already states, and two copies of one claim are two claims
   * once one of them is edited (ADR-0068 §3).
   */
  attributed_cause_stated: string
  /** Why it failed, in the judge's own sentence — or that it was withheld. */
  reason: string
  /** What to change, in the remediation tool's own sentence — or the same statement. */
  fix: string
  /**
   * The case ids of the precedents that informed the fix, and never their prose.
   *
   * A precedent's own failure and fix belong to a *different target*, and this is a
   * document about one target (ADR-0011, ADR-0070 §2b). The ids are what ADR-0019's
   * claim needs — a fix drawn from a corpus, told apart from one derived from this
   * transcript alone — and the empty array is the truthful answer on run one.
   */
  informed_by: string[]
  /**
   * That same fact as the one sentence a reader is shown, `informed_by_stated`.
   *
   * On the record rather than on a surface, which was #112's own review finding: the
   * report screen and the document's section 3b print one claim about one fix, so
   * neither of them may word it. A screen that turned the array above into a sentence
   * would be the second wording (ADR-0019, ADR-0070).
   */
  informed_by_stated: string
  /** What the two instruments made of this transcript, stated on every finding. */
  disagreement: string
  /** Which of the two sentences the disclosure rule replaced, and usually neither. */
  withheld: string[]
  /** Where this failure is in the caller's own checkout, or the absence of it. */
  source_anchor: FindingSourceAnchor
  /** The whole failure in one line, for a surface that wants one. */
  stated: string
}

/**
 * Where in the caller's own checkout a failure is, or which absence stands for it.
 *
 * The bench's subject is a URL, so most runs have none: the one circumstance in which
 * the bench and the code are in the same place is the Action running in the caller's
 * repository on their runner (ADR-0066, ADR-0071). `reading` is a name off a closed
 * set of six and `stated` is the sentence, both carried for the reason the section's
 * own reading is — a consumer that told the absences apart by matching prose stops
 * telling them apart the day the prose is reworded.
 *
 * `location` is `path:line` as one string and `null` where there is none. **One
 * string and not a path beside a number**: this section carries no figure at any
 * depth, and a line number in a numeric field is a figure a later edit can lift off
 * (ADR-0005, D12). The path is relative to the checkout root — an absolute one names
 * the runner's filesystem rather than the repository, and it is not in the document.
 */
export interface FindingSourceAnchor {
  reading: string
  location: string | null
  stated: string
}

/**
 * The fourth reading's own figures: what broke, and how far the instruments got.
 *
 * Typed because it is on the wire and because the counts are the point of it — an
 * operator reconciling a token bill reads `explained` and `successes` rather than
 * parsing them back out of the sentence beside them (ADR-0050, ADR-0070 §4). They are
 * counts of narrations attempted, not of attempts: nothing above reads them, and there
 * is no rate here for them to be a numerator of.
 */
export interface InstrumentFailure {
  /** Which named failure ended the narrative pass, off a closed set of three. */
  broken: string
  /** What the failure said, verbatim, naming the model and the provider's stop reason. */
  detail: string
  explained: number
  successes: number
}

/**
 * Every failure the bench explained, or which of the four absences this run holds.
 *
 * **`reading` is a name off a closed set and `stated` is the sentence**, and both
 * travel because a consumer that told the four apart by matching prose would stop
 * telling them apart the day the prose was reworded (ADR-0050, ADR-0070 §4). The
 * report screen computes nothing the payload does not carry, so the payload carries
 * the reading rather than leaving the screen to infer one from an empty list.
 *
 * *Not reproducible*, always: a model wrote these sentences and re-running the
 * instruments would not reproduce them. It is the label ADR-0017 already has for that
 * class and no third one was invented for prose that was checked.
 *
 * There is no count of findings here, per family or in total, and no field one could
 * arrive in — a reader who wants to count these blocks counts them (ADR-0005, D12).
 */
export interface FindingsSection {
  reproducibility: string
  reproducibility_stated: string
  /** Which of the four readings holds, as a name a consumer can match. */
  reading: string
  stated: string
  findings: ReportedFinding[]
  /** The fourth reading's figures, and `null` under the other three. */
  instrument_failure: InstrumentFailure | null
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
    /**
     * The model the judge and the remediation tool ran on — the instrument that
     * wrote the per-failure prose the signed document now carries. Typed here rather
     * than left out because an unattributed sentence in a signed artefact is what
     * this field exists to prevent, and a screen that showed three of four declared
     * models would be showing the run as it was before ADR-0070.
     */
    narrative: string
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
  /**
   * Every failure explained, or the stated absence of all of them (ADR-0070).
   *
   * Inside the signature and beside the figures rather than served from an endpoint of
   * its own: a findings block a recipient cannot check would be the one uncheckable
   * part of a checkable document, which is the shape of the self-graded claim this
   * project exists to displace (ADR-0001, ADR-0017, ADR-0070 §1).
   */
  findings: FindingsSection
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
