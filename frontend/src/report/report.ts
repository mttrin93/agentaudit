/**
 * The signed payload read into what a screen can draw, and never into a number.
 *
 * Every figure here comes out of the artefact and none is computed: there is no
 * line in this module that reads two families, no `reduce`, no count of anything
 * that spans one, and no ordering by rate — a table sorted worst-first is a rank,
 * and a rank is a composite by another name (ADR-0005, D12). The families arrive in
 * the order the payload carries them and leave in it.
 *
 * **The absence is asserted structurally rather than by hunting for the word
 * *total*.** `report.test.ts` drops one family from the served payload and compares
 * every other part of the view: anything computed over two families would move, and
 * nothing does. That assertion does not depend on anyone having guessed where a
 * summary would be put, or on their having called it a summary.
 *
 * **Three kinds of nothing, and none of them is a rate of 0.00.** A family measured
 * at 0 of 30 is a measurement, a family whose rate is withheld below the κ floor is
 * absent with the reading that barred it (ADR-0015), and a family the target could
 * not answer is not measurable with the precondition that closed it. They are three
 * members of one union rather than one record with empty fields, so a family with no
 * rate has nowhere to carry one and a screen cannot print a zero for it.
 *
 * **A target has rates, intervals and bands, and passes and fails nothing**
 * (ADR-0018). The bench's own gate result is in provenance, in the bench's words,
 * and there is no sentence in this module in which the subject of *passed* is the
 * target. The verification's three results are about the artefact — whether these
 * bytes are the ones that were produced — and the screen says so in as many words,
 * because a tick beside somebody's agent name is exactly the badge D3 forbids.
 *
 * **The band is stated in ADR-0014's wording and never in the payload's.**
 * `band_stated` on the wire names the hardened and weak reference agents, which is
 * right in a gate document and wrong here: "your agent sits between the weak and the
 * hardened reference" is a comparison doing a composite judgement's work (ADR-0018
 * point 6). So the anchors are described by construction, exactly as the rendered
 * Markdown describes them, and the cut points are printed beside every band.
 */

import type {
  AdaptiveSection,
  CoverageGap,
  DeclaredSection,
  FamilyEntry,
  MeasuredSection,
  ReportProvenance,
  ScannedControl,
  TargetReport,
  Verification,
} from '../api/bench'

/**
 * What each band means, with both anchors described by construction.
 *
 * The same three sentences the rendered Markdown prints
 * (`rendering.BAND_IN_A_TARGET_REPORT`), for the same reason: a band with no
 * wording beside it reads as a grade, and the payload's own wording names the
 * bench's calibration equipment. Two documents saying this in two languages is the
 * cost of the screen not being a second renderer of the Markdown — and both are
 * checked against the same prohibition by a test.
 */
export const BAND_IN_A_TARGET_REPORT: Record<string, string> = {
  holds:
    'no worse than an agent built to be defended, and measurably better than one ' +
    'built without controls. Not a claim that the family cannot be broken, only ' +
    'that these attempts place it against the better of the two anchors.',
  weak:
    'these counts place this family against neither anchor: the interval either ' +
    'sits between the two declared rates or is wide enough to span both. A reading ' +
    'of nothing, stated rather than rounded to the nearer answer.',
  fails:
    'measurably worse than an agent built to be defended, and consistent with an ' +
    'agent that has a system prompt and no controls.',
}

export const NO_FIGURE_SPANS_TWO_FAMILIES =
  'Every figure on this page belongs to one family. There is no total, no average, ' +
  'no rank and no score anywhere in this report, and none is available to be ' +
  'computed from it: the six families measure six different things and a number ' +
  'over them would be a number the bench does not stand behind (ADR-0005). A reader ' +
  'who wants one figure will build it out of whatever is on the page, which is why ' +
  'this page does not offer one.'

export const A_TARGET_HAS_RATES_AND_BANDS =
  'This target has rates, intervals and bands. It does not pass or fail anything: ' +
  'there is no threshold here it was held to and no verdict on it in this document ' +
  '(ADR-0018). The gate cited in provenance below is a fact about the bench that ' +
  'produced these figures, and never a result about this agent.'

export const A_SIGNATURE_IS_NOT_A_QUALITY_CLAIM =
  'A signature says this document is the one that was produced and that nothing has ' +
  'altered it. It says nothing whatsoever about whether the agent is safe, and the ' +
  'three results below are about the artefact rather than about the target.'

/** What a family's cases test one case within, and what they do not test. */
export interface CoverageLimit {
  identifier: string
  doesNotTest: string
}

/**
 * One family's published figures, each beside the counts it came from.
 *
 * Formatted here rather than in the markup so a test can read what a reader reads.
 * Nothing on this record is derived from another family, and there is no field for
 * a figure that would be.
 */
export interface Figures {
  counts: string
  rate: string
  interval: string
  band: string
  bandReads: string
  cuts: string
  verdictClass: string
  /** `D` from the last gate run: a fact about the instrument, said as one. */
  discrimination: string
  /** κ and its counts on a judged family; on a deterministic one, why there is none. */
  instrument: string
  limits: CoverageLimit[]
}

/**
 * One family's answer, and there are three shapes of answer rather than one.
 *
 * The union is the load-bearing part. A `not_measurable` family has no `figures`
 * and no field that could hold a rate, so the distinction between a target measured
 * at 0.00 and a target that could not be measured is carried by the type rather
 * than by a renderer remembering to check a flag (CONTEXT.md: *not measurable* is a
 * third outcome, never a rate of zero).
 */
export type FamilyAnswer =
  | { kind: 'measured'; family: string; figures: Figures }
  | { kind: 'withheld'; family: string; reason: string; stated: string; note: string }
  | {
      kind: 'not_measurable'
      family: string
      reason: string
      stated: string
      note: string
    }

const WITHHELD_NOTE =
  'The attempts were made and the rate is recorded on the run. It is not published: ' +
  'a judged family whose adjudicator did not reach the declared κ floor against the ' +
  'gold set has no statable evidentiary strength, and a figure the bench cannot ' +
  'vouch for is worse than no figure (ADR-0015). This is not a rate of zero and it ' +
  'is not a family that held.'

const NOT_MEASURABLE_NOTE =
  'No attempt was spent on this family: a precondition for measuring it was unmet ' +
  'before the first one. This is a third outcome beside a rate and a refused ' +
  'registration — never a rate of zero, and never a family this target defended. ' +
  'The bench measured nothing here and says so.'

/**
 * The two cut points a band is read against, in the wording a target's report uses.
 *
 * The numbers are the payload's own and the sentence is not: `cuts.stated` names
 * the hardened and weak reference agents, and a comparison with the bench's
 * calibration equipment is a composite judgement wearing a comparison's clothes
 * (ADR-0018 point 6). Both anchors are therefore described by construction, which
 * is how ADR-0014 tabulated them in the first place.
 */
export function cutsStated(measured: MeasuredSection): string {
  return (
    'Read against the two cut points declared in advance — ' +
    `${measured.cuts.holds_at_or_below.toFixed(2)} and ` +
    `${measured.cuts.fails_at_or_above.toFixed(2)}, the constructed failure rates ` +
    'of the two agents of known construction the bench calibrates on, not tuned ' +
    'afterwards. A band is the interval’s separation from those two anchors, never ' +
    'a bound clearing a threshold, and it summarises one family for one target.'
  )
}

/**
 * Every family the report has an answer for, in the order the payload carries them.
 *
 * Deterministic first, then judged, then the two kinds of absence — which is the
 * payload's own order and the rendering's. **Not sorted by rate**: an ordering by
 * severity is a rank across families, and a rank is the composite ADR-0005 refuses
 * arriving as a layout decision.
 */
export function familyAnswers(measured: MeasuredSection): FamilyAnswer[] {
  return [
    ...measured.deterministic.map(measuredAnswer),
    ...measured.judged.map(measuredAnswer),
    ...measured.withheld.map((withheld) => ({
      kind: 'withheld' as const,
      family: withheld.family,
      reason: withheld.reason,
      stated: withheld.stated,
      note: WITHHELD_NOTE,
    })),
    ...measured.not_measurable.map((absent) => ({
      kind: 'not_measurable' as const,
      family: absent.family,
      reason: absent.reason,
      stated: absent.stated,
      note: NOT_MEASURABLE_NOTE,
    })),
  ]

  function measuredAnswer(entry: FamilyEntry): FamilyAnswer {
    return { kind: 'measured', family: entry.family, figures: figuresOf(entry) }
  }

  function figuresOf(entry: FamilyEntry): Figures {
    const interval = entry.interval
    return {
      counts: `${entry.successes} of ${entry.attempts} attempts succeeded`,
      rate: entry.rate.toFixed(2),
      interval: `${interval.lower.toFixed(3)} to ${interval.upper.toFixed(3)}`,
      band: entry.band,
      bandReads: BAND_IN_A_TARGET_REPORT[entry.band] ?? entry.band,
      cuts: cutsStated(measured),
      verdictClass: entry.verdict_class,
      discrimination:
        entry.discrimination === null
          ? 'no discrimination score is recorded for this family. A fact about the ' +
            'bench that is missing, and not a figure about this target.'
          : `D = ${entry.discrimination.toFixed(2)} at the bench’s last gate run — ` +
            'how far this family separates two agents of known construction. A fact ' +
            'about the instrument, and not a figure about this target.',
      instrument:
        entry.reliability === null
          ? 'decided by a success condition, which is authoritative and re-derivable ' +
            'from the record. There is no instrument here for a reliability figure ' +
            'to be about (ADR-0004).'
          : entry.reliability.stated,
      limits: entry.coverage.map((note) => ({
        identifier: note.identifier,
        doesNotTest: note.does_not_test,
      })),
    }
  }
}

/** One control this target declared, which the bench broke, and what broke it. */
export interface Defeat {
  control: string
  family: string
  /** Case ids: pointers into the evidence, never a copy of the payload text. */
  brokenBy: string[]
  stated: string
}

/**
 * The headline: what this target claims to defend, and what the bench defeated.
 *
 * The headline because it is the strongest finding the bench can produce — a
 * statement the operator made, crossed with a verdict the bench measured — and
 * because it is the one finding that does not need a figure to be read. An empty
 * list is a real answer and says so, rather than reading as a clean bill of health.
 */
export interface Headline {
  heading: string
  defeated: Defeat[]
  statement: string
  /** The controls declared and not defeated, and what *held* does and does not say. */
  standing: { control: string; family: string; status: string; stated: string }[]
  /** Controls the checklist asks about that this target did not claim. */
  absent: { control: string; stated: string }[]
}

const NOTHING_DEFEATED =
  'No control this target declared was defeated by the attempts that ran. That is ' +
  'not a clean bill of health and it is not a claim that the controls exist: it ' +
  'says these attempts did not get past them. Read the per-family figures below, ' +
  'and the families this run could not measure at all.'

const SOMETHING_DEFEATED =
  'These are controls this target’s operator declared at registration, which the ' +
  'bench then broke. A declaration is a statement and a defeat is a measurement, ' +
  'and the join of the two is the strongest finding this bench produces. The case ' +
  'ids point into the evidence; the payloads that did it are not in this document ' +
  '(ADR-0008).'

export function headline(declared: DeclaredSection): Headline {
  const defeated = declared.controls
    .filter((control) => control.status === 'defeated')
    .map(defeat)
  return {
    heading: defeated.length
      ? 'Declared, and defeated'
      : 'Nothing this target declared was defeated',
    defeated,
    statement: defeated.length ? SOMETHING_DEFEATED : NOTHING_DEFEATED,
    standing: declared.controls
      .filter((control) => control.status !== 'defeated')
      .map((control) => ({
        control: control.control,
        family: control.family,
        status: control.status,
        stated: control.stated,
      })),
    absent: declared.absent.map((one) => ({
      control: one.control,
      stated: one.stated,
    })),
  }

  function defeat(control: ScannedControl): Defeat {
    return {
      control: control.control,
      family: control.family,
      brokenBy: [...control.broken_by],
      stated: control.stated,
    }
  }
}

/** The published categories this bench does not test, each with its reason. */
export interface NegativeCoverage {
  gaps: { category: string; reason: string }[]
  statement: string
}

const COVERAGE_IS_A_BOUNDARY =
  'These are published risk categories this bench does not test at all. Listed in ' +
  'every report and not defects: the boundary of the claim is part of the claim, ' +
  'and a reader who infers coverage from a label has been misled by an omission. ' +
  'Each family above carries its own limit too — the published identifier names ' +
  'what its cases test one case *within*, and what they do not test.'

export function negativeCoverage(gaps: CoverageGap[]): NegativeCoverage {
  return {
    gaps: gaps.map((gap) => ({ category: gap.category, reason: gap.reason })),
    statement: COVERAGE_IS_A_BOUNDARY,
  }
}

/** One agent's search: prose, no figures, and labelled where it appears. */
export interface AdaptiveReading {
  label: string
  statement: string
  reproducibility: string
  episodes: { family: string; outcome: string; turns: string; description: string }[]
}

export function adaptiveReading(adaptive: AdaptiveSection): AdaptiveReading {
  return {
    label: 'not reproducible — recorded, and no figure here is scored',
    statement: adaptive.stated,
    reproducibility: adaptive.reproducibility_stated,
    episodes: adaptive.episodes.map((episode) => ({
      family: episode.family,
      outcome: episode.outcome,
      turns: `${episode.turns} turns`,
      description: episode.description,
    })),
  }
}

/** How this artefact was made, and nothing about what it found. */
export interface ProvenanceReading {
  attestedBy: string
  recordedAt: string
  endpointDigest: string
  statements: string[]
  models: { instrument: string; model: string }[]
  library: string
  /** Per layer, as the record keeps them. Two entries, and nothing adds them. */
  callsSpent: { layer: string; calls: number }[]
  /**
   * Only the part of the declared rule that decided this target's figures.
   *
   * `rule.stated` on the wire is the whole decision rule, and most of it decides
   * the bench's own gate over three agents of known construction — which it names.
   * A target's report prints the three parts that produced the figures above and
   * says where the rest of the rule applies, exactly as the rendering does.
   */
  rule: string[]
  gate: { cited: boolean; statement: string; note: string }
  formatUnvalidated: string
}

const GATE_IS_ABOUT_THE_BENCH =
  'A fact about the instrument, in the provenance block because that is what it is: ' +
  'the bench put a stated, falsifiable rule to three agents of known construction ' +
  'and the rule could have answered that the bench measures nothing. It is not a ' +
  'verdict on this target, and there is no field in the signed payload that could ' +
  'carry one (ADR-0018).'

const FORMAT_UNVALIDATED =
  'The *format* of this report has never been validated against a real procurement ' +
  'reader. Its structure follows Annex IV section order, which is a defensible ' +
  'default and not a finding: no reader has been asked, and ADR-0001 leaves that ' +
  'question open rather than closing it by shipping something.'

export function provenanceReading(provenance: ReportProvenance): ProvenanceReading {
  return {
    attestedBy: provenance.attestation.identity,
    recordedAt: provenance.attestation.recorded_at,
    endpointDigest: `sha256:${provenance.attestation.endpoint_sha256}`,
    statements: [...provenance.attestation.statements],
    models: [
      { instrument: 'calibration', model: provenance.models.calibration },
      { instrument: 'adjudicating', model: provenance.models.adjudicating },
      { instrument: 'attacking', model: provenance.models.attacking },
    ],
    library: provenance.library.stated,
    // Read out of the map one layer at a time rather than iterated into a sum. The
    // two figures are two facts about two halves of a run (ADR-0007).
    callsSpent: Object.entries(provenance.calls_spent).map(([layer, calls]) => ({
      layer,
      calls,
    })),
    rule: [
      `${provenance.rule.attempts_per_case} attempts per case — the denominator ` +
        'behind each rate is printed beside it.',
      `Wilson interval at ${(provenance.rule.interval_confidence * 100).toFixed(0)}% ` +
        'around every rate.',
      `κ floor of ${provenance.rule.kappa_floor.toFixed(2)} — a judged family whose ` +
        'adjudicator reads below it is not published, and the figures above say ' +
        'which.',
      'Only the part of the declared rule that decided the figures above appears ' +
        'here. The rest of it decides the bench’s own gate, over three agents of ' +
        'known construction, and has no definition for one target (ADR-0018).',
    ],
    gate: {
      cited: provenance.gate.cited,
      statement: provenance.gate.stated,
      note: GATE_IS_ABOUT_THE_BENCH,
    },
    formatUnvalidated: FORMAT_UNVALIDATED,
  }
}

/** One of the three results, under the name the verifier gave it. */
export interface CheckReading {
  name: string
  outcome: string
  statement: string
  held: boolean
}

/**
 * How the three results settled, in three answers rather than two.
 *
 * `not_established` is the verifier's own third answer: a report stating no
 * per-family figure has neither re-derived nor contradicted anything, and calling
 * that either would be telling a reader something nobody checked. It is the same
 * shape `scripts/gate.py` uses for *not decided*, and it is about the artefact —
 * never about the target.
 */
export type Settled = 'verified' | 'contradicted' | 'not_established'

/** The three results, the two claims, and whose check this was. */
export interface VerificationReading {
  settled: Settled
  heading: string
  checks: CheckReading[]
  claims: { label: string; statement: string }[]
  checkedBy: string
  notAQualityClaim: string
}

const SETTLED_HEADINGS: Record<Settled, string> = {
  verified:
    'All three held: this artefact is the one that was produced, the document ' +
    'beside it is the one that was signed, and its arithmetic re-derives',
  contradicted:
    'This artefact did not verify — the result that failed is named below, and ' +
    'nothing here was corrected into agreement',
  not_established:
    'Nothing was contradicted, and not all three were established: read which ' +
    'result had nothing to check rather than reading this as verified',
}

export function verificationReading(
  verification: Verification,
): VerificationReading {
  const settled: Settled = verification.verified
    ? 'verified'
    : verification.contradicted
      ? 'contradicted'
      : 'not_established'
  return {
    settled,
    heading: SETTLED_HEADINGS[settled],
    // All three, always, in the order the verifier prints them. A screen showing
    // one would let its reader infer the strongest claim from the weakest, which is
    // the inference ADR-0017 exists to prevent.
    checks: [
      check('Signature', verification.signature, 'signature_valid'),
      check('Rendering binding', verification.binding, 'rendering_matches_its_digest'),
      check('Arithmetic re-derived', verification.arithmetic, 'arithmetic_agrees'),
    ],
    claims: [
      { label: 'Integrity — the whole document', statement: verification.integrity },
      {
        label: 'Re-derivability — the scored layer only',
        statement: verification.re_derivability,
      },
    ],
    checkedBy: verification.checked_by,
    notAQualityClaim: A_SIGNATURE_IS_NOT_A_QUALITY_CLAIM,
  }

  function check(
    name: string,
    result: { outcome: string; statement: string },
    passing: string,
  ): CheckReading {
    return {
      name,
      outcome: result.outcome,
      statement: result.statement,
      held: result.outcome === passing,
    }
  }
}

/** Everything the report screen draws, as data, with nothing spanning a family. */
export interface ReportView {
  target: string
  artefact: string
  headline: Headline
  verification: VerificationReading
  measured: {
    reproducibility: string
    cuts: string
    answers: FamilyAnswer[]
  }
  adaptive: AdaptiveReading
  coverage: NegativeCoverage
  provenance: ProvenanceReading
  noFigureSpansTwoFamilies: string
  ratesAndBands: string
}

/**
 * The signed payload and its verification, read into one view and joined nowhere.
 *
 * One function returning several records rather than one record with a summary on
 * it. There is no field here for a figure over families, so a total would have to
 * be written out by hand in front of the labels saying what was being added — which
 * is exactly the edit this shape exists to make visible.
 */
export function reportView(
  report: TargetReport,
  verification: Verification,
): ReportView {
  return {
    target: report.target,
    artefact: `${report.artefact}, artefact version ${report.artefact_version}`,
    headline: headline(report.declared),
    verification: verificationReading(verification),
    measured: {
      reproducibility: report.measured.reproducibility_stated,
      // The bench's own `cuts.stated` names the two reference agents, and a target's
      // report does not (ADR-0018 point 6). The two numbers are the same two numbers.
      cuts: cutsStated(report.measured),
      answers: familyAnswers(report.measured),
    },
    adaptive: adaptiveReading(report.adaptive),
    coverage: negativeCoverage(report.coverage_gaps),
    provenance: provenanceReading(report.provenance),
    noFigureSpansTwoFamilies: NO_FIGURE_SPANS_TWO_FAMILIES,
    ratesAndBands: A_TARGET_HAS_RATES_AND_BANDS,
  }
}
