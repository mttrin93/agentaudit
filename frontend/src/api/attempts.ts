/**
 * `GET /runs/{id}/episodes` and `GET /runs/{id}/attempts` — what a run made, probe
 * by probe.
 *
 * Its own module in #14's split because it is the one area whose answer can be
 * *absent* rather than empty: a run that was never traced has no probes to show, and
 * `NoProbes` and `NoExchanges` say so by name rather than by an empty list. An empty
 * list and an untraced run look identical on screen and are not the same fact.
 *
 * **An episode is not an attempt** (ADR-0010). These two routes answer separately
 * for that reason, and nothing here adds one to the other.
 */

import type {
  AttemptExchange,
} from './contracts'
import {
  fetched,
} from './http'


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
