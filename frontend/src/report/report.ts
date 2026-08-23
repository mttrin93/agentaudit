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
 * (ADR-0018). There is no sentence in this module in which the subject of *passed*
 * is the target: a tick beside somebody's agent name is exactly the badge D3
 * forbids.
 *
 * **The provenance block and the negative-coverage list are not read here.** What
 * made the artefact — the attestation, the models, the rule, the library version,
 * the calls each layer spent, the bench's own gate — and the risk categories this
 * bench does not test are in `report.json` and in the `report.md` a recipient
 * reads, which is where they travel. This module reads the figures.
 *
 * **`reportView` reads the payload and nothing else.** The three results over a
 * run's three files are not in it — `verificationReading` below is read by the
 * signed-artefacts console, which is the screen that asks whether a document
 * checks out. The report screen shows what was measured; the sender's own word for
 * their own document is the thing a signature exists to replace, and the check a
 * recipient makes is `scripts/verify` over the three files.
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
  FamilyEntry,
  MeasuredSection,
  TargetReport,
  Verification,
} from '../api/bench'

/**
 * What each band means, with both anchors described by construction.
 *
 * Read by the questionnaire block (`console/questionnaire.ts`), which answers a
 * security questionnaire in sentences and needs one beside every band. The report
 * screen prints the band as the word it is; what the word means is in the
 * `report.md` a recipient reads. The payload's own `band_stated` names the bench's
 * calibration equipment and neither of them uses it: "your agent sits between the
 * weak and the hardened reference" is a comparison doing a composite judgement's
 * work (ADR-0018 point 6), so both anchors are described by construction.
 */
export const BAND_IN_A_TARGET_REPORT: Record<string, string> = {
  holds:
    'no worse than an agent built to be defended, and measurably better than one ' +
    'built without controls. Not a claim that the family cannot be broken.',
  weak:
    'against neither anchor: the interval sits between the two declared rates, or ' +
    'is wide enough to span both. A reading of nothing, stated as one.',
  fails:
    'measurably worse than an agent built to be defended, and consistent with an ' +
    'agent that has a system prompt and no controls.',
}

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
  /** The confidence the interval was computed at, beside the interval. */
  intervalAt: string
  band: string
  bandReads: string
  verdictClass: string
  /**
   * κ and the counts it was measured over, on a judged family.
   *
   * `null` on a deterministic one, where there is no adjudicator for a reliability
   * figure to be about (ADR-0004) — and the card says *deterministic* beside it, so
   * the absence is not a missing number.
   */
  kappa: { figure: string; counts: string } | null
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
  | { kind: 'withheld'; family: string; reason: string; stated: string }
  | {
      kind: 'not_measurable'
      family: string
      reason: string
      stated: string
      note: string
    }

const NOT_MEASURABLE_NOTE =
  'No attempt was spent here: a precondition was unmet before the first one. A ' +
  'third outcome beside a rate and a refused registration — never a rate of zero, ' +
  'and never a family this target defended.'

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
      // The payload's own line, carried for the questionnaire block that answers in
      // sentences. The report card prints the named reason and no paragraph: the
      // sentence saying it again is in the report.md a recipient reads.
      stated: withheld.stated,
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
      intervalAt: `${(entry.interval_confidence * 100).toFixed(0)}% Wilson`,
      band: entry.band,
      bandReads: BAND_IN_A_TARGET_REPORT[entry.band] ?? entry.band,
      verdictClass: entry.verdict_class,
      // Assembled from κ's own counts rather than lifted from the payload's
      // sentence: the figure goes on the card's figure line and the counts under
      // it, and neither is prose a reader has to parse to find the number.
      kappa:
        entry.reliability === null
          ? null
          : {
              figure: entry.reliability.kappa.toFixed(2),
              counts:
                `${entry.reliability.agreements} of ` +
                `${entry.reliability.transcripts} gold-set transcripts agreed, ` +
                `declared floor ${entry.reliability.floor.toFixed(2)}`,
            },
      limits: entry.coverage.map((note) => ({
        identifier: note.identifier,
        doesNotTest: note.does_not_test,
      })),
    }
  }
}

/** One episode of the search: what it proposed in that family, and over how long. */
export interface AdaptiveEpisodeReading {
  outcome: string
  turns: string
  /**
   * What the attacker proposed, in its own prose.
   *
   * The payload's `description` is the description `propose_case` was given — the
   * only part of a route ever written down outside a run — or, where an episode
   * proposed nothing, the record's own line saying so (ADR-0008).
   */
  proposed: string
}

/**
 * One family the search worked in, with its episodes under it.
 *
 * Grouped by family because that is the question this section answers — *what did
 * the adaptive layer propose against each family* — and the scored side above is
 * read the same way. **Grouped and never joined**: `broke` is the payload's own
 * `families_broken` membership, the turn counts stay on the episodes that spent
 * them, and nothing here is added to anything (ADR-0010).
 *
 * **An episode that reads identically to one already under this family is dropped.**
 * Two searches that ended the same way after the same number of turns and proposed
 * nothing derive the same line from the record, and the same sentence printed twice
 * reads as a second finding rather than as a second search. What is dropped is a
 * repeated *reading*, never a distinguishable one: an episode differing in its
 * outcome, its turns or what it proposed is a line of its own. The episodes
 * themselves are in `report.json`, where each is its own record.
 */
export interface AdaptiveFamilyReading {
  family: string
  /** Whether the search broke this family. Recorded, and not a scored verdict. */
  broke: boolean
  episodes: AdaptiveEpisodeReading[]
}

/**
 * One agent's search: what it proposed per family, under one label.
 *
 * The label is the whole of the section's standing prose. The payload's own
 * `stated` and `reproducibility_stated` said the same thing at four times the
 * length — *not reproducible*, and *nothing here may be read against the sections
 * above* — and they are still in `report.json` and in the `report.md` a recipient
 * reads. What a route was is described and never quoted, here as there (ADR-0008).
 */
export interface AdaptiveReading {
  label: string
  families: AdaptiveFamilyReading[]
}

export function adaptiveReading(adaptive: AdaptiveSection): AdaptiveReading {
  const broken = new Set(adaptive.families_broken)
  const families: AdaptiveFamilyReading[] = []
  for (const episode of adaptive.episodes) {
    // First appearance in the payload's order, and never sorted by what an episode
    // found: an ordering by outcome is a rank, and this layer is not scored.
    let reading = families.find((one) => one.family === episode.family)
    if (reading === undefined) {
      reading = {
        family: episode.family,
        broke: broken.has(episode.family),
        episodes: [],
      }
      families.push(reading)
    }
    const line = {
      outcome: episode.outcome,
      turns: `${episode.turns} ${episode.turns === 1 ? 'turn' : 'turns'}`,
      proposed: episode.description,
    }
    const alreadySaid = reading.episodes.some(
      (said) =>
        said.outcome === line.outcome &&
        said.turns === line.turns &&
        said.proposed === line.proposed,
    )
    if (!alreadySaid) {
      reading.episodes.push(line)
    }
  }
  return {
    label: 'not reproducible — recorded, and no figure here is scored',
    families,
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

/**
 * What a signature is not, printed with the three results wherever they are read.
 *
 * A tick beside somebody's agent name is the badge D3 forbids, and the nearest
 * thing to one a verifier produces is three results that all held.
 */
export const A_SIGNATURE_IS_NOT_A_QUALITY_CLAIM =
  'A signature says nothing whatsoever about whether the agent is safe. These three ' +
  'results are about the artefact, not about the target.'

/**
 * The three results, the two claims, and whose check this was.
 *
 * Read by the signed-artefacts console (`console/artefacts.ts`), where a reader is
 * asking whether a document checks out before they send it. Three results, always
 * all three, because one of them alone lets a reader infer the strongest claim from
 * the weakest (ADR-0017).
 */
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
  /** One answer per family, in the payload's order and never sorted by rate. */
  answers: FamilyAnswer[]
  adaptive: AdaptiveReading
}

/**
 * The signed payload read into one view, and joined nowhere.
 *
 * One function returning several records rather than one record with a summary on
 * it. There is no field here for a figure over families, so a total would have to
 * be written out by hand in front of the labels saying what was being added — which
 * is exactly the edit this shape exists to make visible.
 */
export function reportView(report: TargetReport): ReportView {
  return {
    target: report.target,
    answers: familyAnswers(report.measured),
    adaptive: adaptiveReading(report.adaptive),
  }
}
