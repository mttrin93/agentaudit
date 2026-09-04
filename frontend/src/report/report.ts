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
 * **The route block is not read from the payload, because the payload does not
 * carry it.** `routeReading` takes what `GET /runs/{id}/episodes` serves — the
 * probes one live run's episodes sent, out of the bench's memory — and it is a
 * separate function over a separate input for exactly that reason: there is no path
 * in this module from a `TargetReport` to a probe, because the artefact has no field
 * one could be in (ADR-0008, amended). What it produces says on itself that it is
 * not part of the signed document.
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
  FamilyLabel,
  FamilyRun,
  MeasuredSection,
  RunAttempts,
  RunEpisodes,
  TargetReport,
  Verification,
  WithheldFamily,
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

/**
 * A family's label as a card prints it: the duty, and the entries it claims.
 *
 * Two strings and not one, because they are two claims of different standing — the
 * article is this project's reading of the Act from a table a model may not choose
 * from, and the identifiers are a secondary label on somebody else's list (ADR-0002,
 * ADR-0044). Both come off the payload's own rendered sentences: a screen that built
 * either from the lists beside them would be a second copy of a legal mapping, and
 * two copies of one claim are two claims once one of them is edited.
 *
 * Carried by every answer shape, including the two that carry no figure. What a
 * family's failure falls under is a property of the family, so a withheld rate and
 * an unmet precondition do not remove it — and a duty that appeared only beside a
 * published rate would read as something the measurement conferred.
 */
export interface LabelReading {
  bears: string
  claims: string
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
  | { kind: 'measured'; family: string; label: LabelReading; figures: Figures }
  | {
      kind: 'withheld'
      family: string
      label: LabelReading
      reason: string
      /**
       * The line that stands where the rate would be, in a reader's words.
       *
       * Rendered off `reason` rather than sliced out of `stated`: the payload's
       * sentence is prose for a recipient of the artefact, and a card that showed the
       * counts of the attempts and nothing else — which is what this one did — left a
       * reader to conclude the family was simply not answered.
       */
      reads: string
      /**
       * The κ that barred the rate, in the shape a published family carries it.
       *
       * `null` where the reason is that nobody measured it: a withheld family has no
       * figure then, and one printed here would be the κ of zero ADR-0013 refuses.
       * Where there is a reading it goes on the card's figure line, because the
       * number that withheld the rate is the number the reader came for.
       */
      kappa: { figure: string; counts: string } | null
      stated: string
    }
  | {
      kind: 'not_measurable'
      family: string
      label: LabelReading
      reason: string
      stated: string
      note: string
    }

/** What every withheld card says before it says why. */
const RATE_NOT_PUBLISHED = 'rate not published'

/**
 * The reason a rate is absent, in a reader's words, keyed by the payload's own name
 * for it. Two entries because `WithheldReason` has two members and they are two
 * different readings; an unnamed one falls back to the bare line rather than to a
 * guess, so a payload from a later field set says *rate not published* and no more.
 */
const WITHHELD_READS: Record<string, string> = {
  kappa_below_floor: `${RATE_NOT_PUBLISHED} — κ is below the declared floor`,
  no_kappa_measured: `${RATE_NOT_PUBLISHED} — no κ was measured against the gold set`,
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
/**
 * The κ that withheld a rate, or nothing where the payload carries no whole reading.
 *
 * Assembled from the fields rather than sliced out of `stated`, on the same terms as
 * a published family's κ: the figure goes where a rate would be and the counts go
 * under it. **All three or none** — a figure whose counts are missing is a number
 * with no denominator, and `cited.the_reliability` drops a reading on the same
 * condition rather than filling one in.
 */
function barringKappa(
  withheld: WithheldFamily,
): { figure: string; counts: string } | null {
  const { kappa, agreements, transcripts } = withheld
  if (kappa === null || agreements === null || transcripts === null) {
    return null
  }
  return {
    figure: kappa.toFixed(2),
    counts: goldSetCounts(agreements, transcripts, withheld.floor),
  }
}

/**
 * The counts a κ was measured over, in one line, wherever a κ is printed.
 *
 * One writer for both cards: the reading that publishes a rate and the reading that
 * withholds one are the same measurement of the same instrument, and two renderings
 * of it would eventually differ in a way a reader would have to reconcile.
 */
function goldSetCounts(
  agreements: number,
  transcripts: number,
  floor: number,
): string {
  return (
    `${agreements} of ${transcripts} gold-set transcripts agreed, ` +
    `declared floor ${floor.toFixed(2)}`
  )
}

/**
 * One label as a card reads it, off the payload's own sentences.
 *
 * A rename and nothing else: both fields are whole sentences the payload carries,
 * and this app adds no word to either. Nothing is derived from `agentic`, `llm` or
 * `articles` — those are on the wire so a recipient can match an identifier as a
 * key, and the sentence a reader reads is the bench's own.
 */
function labelOf(label: FamilyLabel): LabelReading {
  return { bears: label.bears_stated, claims: label.claims_stated }
}

export function familyAnswers(measured: MeasuredSection): FamilyAnswer[] {
  return [
    ...measured.deterministic.map(measuredAnswer),
    ...measured.judged.map(measuredAnswer),
    ...measured.withheld.map((withheld) => ({
      kind: 'withheld' as const,
      family: withheld.family,
      label: labelOf(withheld.label),
      reason: withheld.reason,
      reads: WITHHELD_READS[withheld.reason] ?? RATE_NOT_PUBLISHED,
      kappa: barringKappa(withheld),
      // The payload's own line, carried for the questionnaire block that answers in
      // sentences. The report card prints the named reason and no paragraph: the
      // sentence saying it again is in the report.md a recipient reads.
      stated: withheld.stated,
    })),
    ...measured.not_measurable.map((absent) => ({
      kind: 'not_measurable' as const,
      family: absent.family,
      label: labelOf(absent.label),
      reason: absent.reason,
      stated: absent.stated,
      note: NOT_MEASURABLE_NOTE,
    })),
  ]

  function measuredAnswer(entry: FamilyEntry): FamilyAnswer {
    return {
      kind: 'measured',
      family: entry.family,
      label: labelOf(entry.label),
      figures: figuresOf(entry),
    }
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
              counts: goldSetCounts(
                entry.reliability.agreements,
                entry.reliability.transcripts,
                entry.reliability.floor,
              ),
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
  /**
   * How the episode ended, in words a reader does not need the statistics for.
   *
   * `censored` is the record's word and it is a right-censored observation: the
   * attacker did not break the family within its turn cap, and nothing was learnt
   * about what one more turn would have done. A card printing that word says *the
   * search was cut off* to a reader who knows the term and nothing at all to one who
   * does not — and *no break* would say the opposite of the truth, because it reads
   * as a defence that held. So the card says `out of turns`, which is what happened,
   * and `report.json` keeps the word a statistician needs.
   */
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

/** The episode outcomes this bench records, mapped to the words a card prints. */
const OUTCOMES_IN_PLAIN_WORDS: Readonly<Record<string, string>> = {
  censored: 'out of turns',
}

/**
 * One outcome as a card says it, or the record's own word where there is nothing
 * to gain by rewording it.
 *
 * A lookup and not a rewrite: an outcome this map has no entry for is printed as the
 * payload wrote it, so a seventh outcome added upstream reaches the screen as itself
 * rather than as whatever a fallthrough decided it was.
 */
function readOutcome(outcome: string): string {
  return OUTCOMES_IN_PLAIN_WORDS[outcome] ?? outcome
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
      outcome: readOutcome(episode.outcome),
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

/**
 * What the route block says about itself, printed with it wherever it is read.
 *
 * The point of the block rather than decoration. Everything above it on this screen
 * is read out of the signed payload and travels with the artefact; this is read out
 * of the bench's memory and travels nowhere — so a reader who screenshots it has to
 * be told, on the same page, that what they are holding is not part of the document
 * a recipient verifies (ADR-0008, amended).
 */
export const NOT_PART_OF_THE_ARTEFACT =
  'Read from the live run in this bench’s memory. Not part of the signed ' +
  'artefact and not covered by its signature, committed to no file, and gone once ' +
  'the process stops. A copy of a probe that worked is a copy of a working exploit.'

/** One probe, numbered as it was sent, and whether the break followed it. */
export interface ProbeReading {
  /** `probe 3` — the ordinal the bench counted, and nothing that is a total. */
  at: string
  probe: string
  /**
   * Whether the break was confirmed after this probe.
   *
   * The bench's own derivation, carried and never recomputed: the canary check
   * reads an episode's last transcript, so this is the last probe of a broken
   * episode and there is nothing else it could honestly be. A censored episode
   * marks nothing.
   */
  confirmedTheBreak: boolean
  /** What the mark means, in words, so no colour has to carry it alone. */
  marked: string
  /** What the target said back, in full, and the empty string for a reply nothing read. */
  reply: string
  /**
   * What the target did on this turn, or the empty string from a target that returns
   * no trace. Two of the four deterministic families are decided on this and nothing
   * else, so it is drawn beside the reply rather than a screen away.
   */
  toolTrace: string
  /**
   * What this turn was found to be, in the bench's own words: broke it, no break, or
   * not checkable. Carried rather than derived here — the reading is the bench's.
   */
  reading: string
}

/**
 * Which probe broke one family, or the stated fact that nothing did.
 *
 * The question the route block is opened for, answered before the sequence a reader
 * would otherwise have to read end to end. A position and never a count: `at` names an
 * episode and a turn, and there is no field on this reading a total could live in.
 */
export interface FamilyBreakReading {
  family: string
  broke: boolean
  /** `episode 2, turn 9` — where it first worked, or the empty string if it never did. */
  at: string
  /** The probe that did it, or the empty string. */
  probe: string
  /** The row in words: what broke it, or which silence this is. */
  stated: string
}

/** One episode, in the order it ran, with its probes under it. */
export interface EpisodeRouteReading {
  family: string
  outcome: string
  turns: string
  probes: ProbeReading[]
  /** The episode's own line about its outcome, carried from the bench unedited. */
  stated: string
  /**
   * Why this episode shows no probe, or empty where it shows some.
   *
   * An episode with no probe is one that spent its decisions without composing a
   * message — a reading about the attacker — and an empty list under a heading
   * would read as one the bench declined to show.
   */
  sentNothing: string
}

/**
 * The route this run's own attacker took, or the stated reason there is none.
 *
 * A union rather than a record with an empty list on it, for the reason
 * `FamilyAnswer` is one: *no episode was recorded* and *an episode sent no probe*
 * are two different facts, and only the second is about the search. The bench
 * answers in the same two shapes, and neither of them is an empty 200.
 *
 * **Episodes are not grouped by family here, and that is deliberate.** The adaptive
 * section above groups, because the question it answers is what the search proposed
 * per family. The question this one answers is what was sent, and a route is a
 * sequence: episodes stay in the order they ran and probes in the order they went.
 */
export type RouteReading =
  | {
      kind: 'held'
      note: string
      /** One row per family that opened an episode, before the sequence itself. */
      broke: FamilyBreakReading[]
      episodes: EpisodeRouteReading[]
    }
  | { kind: 'absent'; note: string; stated: string }

const THE_BREAK_WAS_CONFIRMED_AFTER_THIS_PROBE = 'the break was confirmed after this'

const NOTHING_WAS_SENT =
  'this episode sent no probe: the attacker spent its decisions without composing ' +
  'one, which is a reading about the attacker and not about the agent'

/**
 * The probes one run's episodes sent, read into what the block draws.
 *
 * Nothing is counted, added or sorted: the turn count is the episode's own figure
 * formatted, the probes keep the numbering the bench gave them, and there is no
 * field on this reading for a figure over two episodes or two families to live in
 * (ADR-0005, ADR-0010).
 */
export function routeReading(served: RunEpisodes): RouteReading {
  if (!served.held) {
    return { kind: 'absent', note: NOT_PART_OF_THE_ARTEFACT, stated: served.stated }
  }
  return {
    kind: 'held',
    note: NOT_PART_OF_THE_ARTEFACT,
    broke: served.broke.map((family) => ({
      family: family.family,
      broke: family.broke,
      at:
        family.episode === null || family.turn === null
          ? ''
          : `episode ${family.episode}, turn ${family.turn}`,
      probe: family.probe ?? '',
      stated: family.stated,
    })),
    episodes: served.episodes.map((episode) => ({
      family: episode.family,
      outcome: episode.outcome,
      turns: `${episode.turns} ${episode.turns === 1 ? 'turn' : 'turns'}`,
      stated: episode.stated,
      sentNothing: episode.probes.length ? '' : NOTHING_WAS_SENT,
      probes: episode.probes.map((probe) => ({
        at: `probe ${probe.turn}`,
        probe: probe.probe,
        confirmedTheBreak: probe.confirmed_the_break,
        marked: probe.confirmed_the_break
          ? THE_BREAK_WAS_CONFIRMED_AFTER_THIS_PROBE
          : '',
        reply: probe.reply,
        // Empty string rather than null, so the component has one absence to draw
        // and not two. Which absence it was is the bench's sentence to make, and it
        // makes it in `reading`.
        toolTrace: probe.tool_trace ?? '',
        reading: probe.reading,
      })),
    })),
  }
}

/**
 * What one family attempted, in the words the published cards use for it.
 *
 * **For the cards that publish no rate.** A withheld family's rate is absent from the
 * artefact by design — `Withheld` has no field for one, and no field for the counts
 * either — but the attempts were made and the measurement is on the run (ADR-0006
 * keeps a measured rate measured). So the counts are read off the run's own progress,
 * out of this process's memory, exactly as the exchanges below are: what a card gains
 * is the numerator and the denominator, and what it still does not state is the rate
 * with the interval and the band that would make it a published figure (ADR-0015).
 *
 * Keyed by family and never joined to the answers: `reportView` reads the payload and
 * nothing else, and a counts line threaded into it would be the one edge that lets a
 * figure from outside the artefact into a reading of the artefact.
 */
export function attemptCounts(families: FamilyRun[]): Record<string, string> {
  const counted: Record<string, string> = {}
  for (const family of families) {
    // A family the declarations dropped attempted nothing, and `0 of 0` drawn on a
    // card reads as a family that resisted everything.
    if (family.attempted === 0) {
      continue
    }
    counted[family.family] =
      `${family.succeeded} of ${family.attempted} attempts succeeded`
  }
  return counted
}

/** One exchange as the block draws it: what went out, what came back, how it read. */
export interface ExchangeReading {
  /** `attempt 3` — the ordinal the bench counted, and nothing that is a total. */
  at: string
  caseId: string
  sent: string
  reply: string
  /** The transport's own answer, so a reply nobody could read is not a silent one. */
  answered: string
}

/**
 * One family's succeeded attempts, under the family they were made in.
 *
 * `verdictClass` is carried rather than derived, on the record's own reasoning: a
 * deterministic success is re-derivable from the text beside it and a judged one is
 * an adjudicator's reading, and the one thing nothing may do is work that out from
 * the family name (ADR-0004).
 */
export interface FamilyExchangeReading {
  family: string
  verdictClass: string
  exchanges: ExchangeReading[]
}

/**
 * The attacks that worked, read into what the block draws, or the stated absence.
 *
 * The same two shapes `RouteReading` has and for the same reason: a run where nothing
 * succeeded answers in words, because an empty list would read as a target that
 * resisted everything when it may be a run nobody approved.
 *
 * **Nothing here is counted.** There is no field on this reading for a length, a
 * total or a proportion: the rate is on the cards above with its own denominator and
 * its own interval, and a figure derived here would be the same measurement taken a
 * second way (ADR-0005, ADR-0006).
 */
export type ExchangesReading =
  | { kind: 'held'; note: string; families: FamilyExchangeReading[] }
  | { kind: 'absent'; note: string; stated: string }

/**
 * The exchanges behind one run's successes, read into what the block draws.
 *
 * Grouped as the response grouped them and re-sorted nowhere: the families arrive in
 * the library's own order so this block and the cards above line up row for row, and
 * the attempts within one arrive in the order they were made.
 */
export function exchangesReading(served: RunAttempts): ExchangesReading {
  if (!served.held) {
    return { kind: 'absent', note: NOT_PART_OF_THE_ARTEFACT, stated: served.stated }
  }
  return {
    kind: 'held',
    note: NOT_PART_OF_THE_ARTEFACT,
    families: served.families.map((family) => ({
      family: family.family,
      verdictClass: family.verdict_class,
      exchanges: family.succeeded.map((one) => ({
        at: `attempt ${one.attempt}`,
        caseId: one.case_id,
        sent: one.sent,
        reply: one.reply,
        answered: `HTTP ${one.status_code}`,
      })),
    })),
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
      check('Signature', verification.signature, ['signature_valid']),
      check('Rendering binding', verification.binding, [
        'rendering_matches_its_digest',
      ]),
      // Two passing outcomes on the third check and one of them carries a sentence:
      // a run at an `attempts_per_case` the console offered re-derives, and it is not
      // a gate result (ADR-0025, ADR-0027). The distinction is in the outcome and in
      // the statement beside it; drawing it as a failed row would tell a reader that
      // an artefact which verified did not, and teach them the row is noise.
      check('Arithmetic re-derived', verification.arithmetic, [
        'arithmetic_agrees',
        'arithmetic_agrees_not_a_gate_result',
      ]),
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
    passing: string[],
  ): CheckReading {
    return {
      name,
      outcome: result.outcome,
      statement: result.statement,
      held: passing.includes(result.outcome),
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
