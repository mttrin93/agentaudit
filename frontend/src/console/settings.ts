/**
 * The operator's other screen: what this instrument is set to, and the one thing an
 * operator sets from it.
 *
 * Six blocks, in the order the response serves them, and the order is the content
 * rather than the layout. **The two key identifiers first**, because the question an
 * operator opens this screen with is *which key will sign the thing I am about to
 * send a customer* — and because there are two answers to it and only one of them is
 * that question. **Then the case library**, its live version and the count of what
 * has retired and been kept, so the version here can be held against the one the gate
 * citation carries. **Then the three reference agents**, because the next thing a
 * reader asks about a discrimination score is what it was measured against. **Then
 * the four model settings**, four rows and never one. **Then each layer's ceiling**,
 * two records in two different units. **And last the tuning**, the one block that
 * offers a change rather than stating one (ADR-0025).
 *
 * **The order is asserted, not merely intended.** This module returns the blocks as a
 * sequence and the component maps over it, so *above* is a property of a value a test
 * reads rather than of markup nobody checks — the same division `gate.ts` makes.
 *
 * **Two key identifiers, because they are two facts.** One is the key an artefact
 * will be signed by; the other is the key a verification is run against. They are
 * `SignatureResult.claimed` and `.pinned` seen from the configuration side, and a
 * bench holding a private key nobody has published verifies against the published one
 * and reports `signed_by_another_key` on every report it ever produces. That state is
 * reachable and named, and a screen printing one identifier and calling it *the key*
 * would show such a bench as correctly configured (ADR-0017). Neither is the private
 * half: what arrives is a fingerprint over a public key, and the environment is read
 * by one line of the bench and by no route.
 *
 * **The four model settings are four, and the fourth is a stated absence.** The
 * reference agents' model is what is being measured, the adjudicator's is the
 * instrument measuring it, the adaptive attacker's decides nothing, and the second
 * reference model — the one a swap is measured against — is declared on the command
 * line rather than held by this bench. Stated rather than dropped, because a screen
 * showing three of the four would be the collapse this block exists to make visible
 * (ADR-0012, ADR-0013).
 *
 * **Each layer's ceiling is its own block in its own units.** Attempts over cases on
 * one side, turns over episodes on the other. There is no combined figure anywhere in
 * this module and nowhere to put one: the two ceilings arrive as two differently
 * shaped records, and an attempt is the unit of a denominator while a turn is a
 * spending limit (CONTEXT.md, ADR-0007, ADR-0010).
 *
 * **Nothing in this module changes anything, and the one block that offers a change
 * offers only the tuning.** Every field of every *stating* block is text, a boolean or
 * a declared number and the type has no callback in it, so there is nowhere in those
 * values for a handler to live; the `tuning` block is the exception, it is one block,
 * and what it describes is the form `SettingsScreen.tsx` draws (ADR-0025). Rotation
 * stays in the environment, because the factory reads its key from one place and
 * refuses to boot without it (ADR-0020), and the library stays what was mounted.
 */

import type {
  AdaptiveCeiling,
  BenchSettings,
  Bounds,
  EffortChoice,
  ModelChoice,
  ModelSetting,
  ScoredCeiling,
  Tuning,
  WillBeSignedBy,
} from '../api/bench'
import { REFERENCE_AGENTS, type ReferenceAgent } from './gate'
import type { CitedFact } from './landing'

export const WHAT_THIS_SCREEN_ANSWERS =
  'What this bench is configured to do, as it is currently loaded. It states the ' +
  'key an artefact will be signed by and the key a verification is run against, the ' +
  'case library it holds, the four models behind its instruments and each layer’s ' +
  'own ceiling — and of those it changes none: the signing key is rotated in the ' +
  'environment and the library is what was mounted. What it does set are the ' +
  'declared inputs of the next run (ADR-0025).'

/** The command that generates a signing pair, for an operator who needs one. */
export const KEYGEN_COMMAND =
  'uv run python -m scripts.keygen --public /tmp/dev-signing.pub'

/**
 * One of the two key identifiers, or the stated absence of one.
 *
 * Two shapes of one union, so the bench that declared it does not sign has no
 * fingerprint field to be blank: an empty identifier drawn where a fingerprint goes
 * reads as a key whose name failed to load, which is a different fact from a bench
 * that will produce no signed artefact at all.
 */
export type KeyIdentity =
  | { held: true; label: string; fingerprint: string; stated: string }
  | { held: false; label: string; stated: string }

/** The two key identifiers, kept apart, and the sentence saying why they are two. */
export interface KeysBlock {
  kind: 'keys'
  heading: string
  statement: string
  /** Two, always: what will sign, then what a verification is run against. */
  identities: KeyIdentity[]
  command: string
  /** What the command is for, and why no screen may generate a key. */
  commandStatement: string
}

/** The case library as loaded: the live version, and the retired kept beside it. */
export interface LibraryBlock {
  kind: 'library'
  heading: string
  statement: string
  /** The live count, the digest, and the retired count. Three labelled facts. */
  facts: CitedFact[]
  /** The version in the bench's own words, as a run prints it. */
  stated: string
  /** That a retired case is marked and kept, never deleted. */
  kept: string
}

/** The three agents the discrimination score is measured against, named and ordered. */
export interface AgentsBlock {
  kind: 'agents'
  heading: string
  statement: string
  agents: ReferenceAgent[]
}

/** The four model settings, four rows, each with what it decides. */
export interface ModelsBlock {
  kind: 'models'
  heading: string
  statement: string
  /** Four, and `length` is what a test reads: a collapse is three. */
  models: ModelSetting[]
}

/** One declared number behind one layer's ceiling, with what it is a number of. */
export interface DeclaredFigure {
  label: string
  value: number
  /** What the figure is counted in, so two layers' figures cannot be read as one. */
  of: string
}

/**
 * One layer's ceiling: the limit in that layer's own terms, and the numbers behind it.
 *
 * `limit` is composed from the declared figures of that layer and from no other
 * layer's, so there is no sentence in this module in which a scored figure and an
 * adaptive one appear as one quantity.
 */
export interface Ceiling {
  layer: 'scored' | 'adaptive'
  heading: string
  limit: string
  figures: DeclaredFigure[]
  declaredIn: string
  statement: string
}

/** The two ceilings, two blocks, and no total under them. */
export interface CeilingsBlock {
  kind: 'ceilings'
  heading: string
  statement: string
  /** Exactly two, in the order a run spends them. Never summed. */
  ceilings: Ceiling[]
}

/**
 * One number an operator may set, with the range the route enforces.
 *
 * The three whole numbers, and not the temperature: a temperature is a setting the
 * chosen model may have no setting for at all, so it is its own field on the block
 * beside the reasoning effort rather than a row here with a nullable range. These
 * three are set on every model there is.
 */
export interface TunedNumber {
  /** The field name the route takes, used as the form's own key. */
  name: 'turns_per_episode' | 'episodes_per_family' | 'attempts_per_case'
  label: string
  value: number | null
  low: number
  high: number
  /** What this setting decides, in one line, so no label carries it alone. */
  decides: string
}

/**
 * The one block on this screen that changes anything (ADR-0025).
 *
 * Six settings: the attacker's model, its temperature, its reasoning effort, `T`,
 * `k`, and attempts per case. Each is a declared input of a run — it changes what the next run *measured* —
 * and each is printed in the provenance of every run made under it, which is the
 * condition they are offered on.
 *
 * `warning` is the bench's own sentence about `attempts_per_case`, carried and never
 * paraphrased: five of the six bound a layer that is scored on nothing, and the
 * sixth is the scored denominator the gate is decided at. A block offering the sixth
 * without that sentence would be offering a way to produce a rate that reads like a
 * gate reading.
 */
export interface TuningBlock {
  kind: 'tuning'
  heading: string
  statement: string
  models: ModelChoice[]
  /**
   * The temperature the chosen model accepts, if it accepts one at all.
   *
   * `bounds` is `null` when the chosen attacker takes no temperature, which is the
   * rule `reasoning.levels` follows one field down: a slider drawn against a model
   * that refuses the parameter is a control whose every value the route refuses, and
   * before this the form learned that from the 422 after the operator had moved it.
   *
   * **Four statements about one setting and none of them composed here.** A declared
   * number is `chosen`; *no temperature declared* is `absent`; *this model accepts
   * none* and *no line in the table for this model* are both `stated`, which is the
   * sentence the signed document will print — carried from the response so the screen
   * cannot say one thing while the record says another.
   */
  sampling: {
    bounds: Bounds | null
    chosen: number | null
    absent: string
    decides: string
    stated: string
  }
  /**
   * The reasoning efforts the chosen model accepts, and what an unset one means.
   *
   * `levels` is empty when the chosen attacker has no such setting, which is not the
   * same statement as *no level chosen* — `stated` is the sentence a run made now
   * would print in its provenance, carried from the response rather than composed
   * here, so a screen cannot say one thing while the signed document says another.
   */
  reasoning: {
    levels: EffortChoice[]
    chosen: string | null
    absent: string
    decides: string
    stated: string
  }
  numbers: TunedNumber[]
  /** `n` at the current setting, and the `n` the declared rule reads. */
  attemptsPerFamily: string
  declaredAttemptsPerCase: string
  warning: string
}

export type SettingsBlock =
  | KeysBlock
  | LibraryBlock
  | AgentsBlock
  | ModelsBlock
  | CeilingsBlock
  | TuningBlock

const WILL_SIGN = 'An artefact this bench produces will be signed by'
const IS_VERIFIED_AGAINST = 'A verification of one is run against'

const NO_SCREEN_GENERATES_A_KEY =
  'A key is generated in a terminal and its private half is exported in the shell ' +
  'the server is started from. Nothing on this screen generates one and no route on ' +
  'this bench would take one: a key made on demand would boot cleanly and sign every ' +
  'report with a key nobody has published, which is a valid signature over unknown ' +
  'provenance (ADR-0017, ADR-0020). Rotation invalidates every signature ever issued ' +
  'under the old key, so it is a deliberate act with the published fingerprint ' +
  'updated in the same commit.'

const THE_AGENTS_ARE_WHAT_D_IS_MEASURED_ON =
  'The discrimination score is the separation between the trivial and the hardened ' +
  'agent on one family, so it is a reading about these three and about the model ' +
  'named above them — never a general claim. They are test equipment: no reference ' +
  'agent is ever named in a report about somebody’s target, because “your agent sits ' +
  'between the weak and the hardened one” is a composite judgement wearing a ' +
  'comparison’s clothes. Not one of them carries a figure here: what each scored on ' +
  'each family is in the gate run’s own document.'

const FOUR_AND_NEVER_ONE =
  'Four separate settings, shown separately because they are declared separately. ' +
  'Collapsing any two of them into one would report an instrument’s agreement with ' +
  'itself — a κ measured on the model that produced the transcripts, or a swap that ' +
  'measured run-to-run variation rather than a model change. There is no combined ' +
  'row here, and a setting this bench does not hold says so rather than being left ' +
  'off the list.'

/**
 * The two key identifiers, in the order an operator asks for them.
 *
 * The sentences are the response's own, because both of them are statements about
 * what this bench will do rather than about what this screen shows, and a second
 * wording here would only have to disagree once for an operator to be told their
 * artefacts verify when they do not.
 */
function keyIdentities(
  signs: WillBeSignedBy,
  verifies: { fingerprint: string; stated: string },
): KeyIdentity[] {
  return [
    signs.holds_a_key
      ? {
          held: true,
          label: WILL_SIGN,
          fingerprint: signs.fingerprint,
          stated: signs.stated,
        }
      : { held: false, label: WILL_SIGN, stated: signs.stated },
    {
      held: true,
      label: IS_VERIFIED_AGAINST,
      fingerprint: verifies.fingerprint,
      stated: verifies.stated,
    },
  ]
}

/**
 * The scored layer's ceiling, in attempts over cases.
 *
 * Every number in the sentence is one of this layer's own declared figures, and there
 * is no arithmetic in it: the attempts and the registration probe are stated as the
 * two things they are, because the product is declared per run against the library
 * that run is attempted with and presented at the approval interrupt beside the
 * adaptive figure rather than added to it.
 */
function scoredCeiling(scored: ScoredCeiling): Ceiling {
  const probes = scored.registration_probes_per_target
  return {
    layer: 'scored',
    heading: 'The scored layer',
    limit:
      `the whole live library at ${scored.attempts_per_case} attempts per case, ` +
      `plus ${probes} registration ${probes === 1 ? 'probe' : 'probes'} per target`,
    figures: [
      {
        label: 'Attempts per case',
        value: scored.attempts_per_case,
        of: 'attempts, which is also this layer’s denominator',
      },
      {
        label: 'Registration probes per target',
        value: probes,
        of: 'calls on the operator’s endpoint, inside the ceiling and not beside it',
      },
    ],
    declaredIn: scored.declared_in,
    statement: scored.statement,
  }
}

/**
 * The adaptive layer's ceiling, in turns over episodes over families.
 *
 * The layer's own ceiling and the per-episode cap are both shown, because they are
 * two limits: the cap is the attacker's to enforce as it runs and the ceiling is
 * enforced against the layer's own counter, so a per-family cap is not something a
 * reader has to multiply out themselves.
 */
function adaptiveCeiling(adaptive: AdaptiveCeiling): Ceiling {
  return {
    layer: 'adaptive',
    heading: 'The adaptive layer',
    limit:
      `at most ${adaptive.turns_per_target} turns per target — ` +
      `${adaptive.families} families × k=${adaptive.episodes_per_family} episodes × ` +
      `T=${adaptive.turns_per_episode} turns, every episode running to its cap`,
    figures: [
      {
        label: 'Turns per target, at most',
        value: adaptive.turns_per_target,
        of: 'turns, this layer’s own ceiling against its own counter',
      },
      {
        label: 'Turns per episode (T)',
        value: adaptive.turns_per_episode,
        of: 'turns, the cap the attacker enforces as it runs',
      },
      {
        label: 'Episodes per family (k)',
        value: adaptive.episodes_per_family,
        of: 'episodes, which are not samples of a rate',
      },
      {
        label: 'Families covered',
        value: adaptive.families,
        of: 'families, read off the closed set of them',
      },
    ],
    declaredIn: adaptive.declared_in,
    statement: adaptive.statement,
  }
}

/**
 * The five blocks, in the order the response serves them.
 *
 * A sequence and not five fields, so that the order a reader meets them in is a
 * property of this value: the keys are first because that is the question this screen
 * is opened with, and the two ceilings are last because they are the only block whose
 * point is made by there being two of it.
 */
/*
 * What each control decides, in the fewest words the fact survives in.
 *
 * They were paragraphs, and beside six controls on one form they were the form. What
 * each keeps is the half that changes what an operator types; what came out of each is
 * recorded here, because the argument is still the reason the short line says what it
 * says.
 *
 * **The model:** that the layer it drives is scored on nothing (ADR-0010) — which is
 * the one thing the identifier in the box cannot say. The block's own paragraph, about
 * these being declared inputs printed in every run's provenance and refused mid-run, is
 * `TuningBlock.statement`: served, tested, and printed by nothing.
 *
 * **The temperature:** that blank is the provider's default. What came out was the
 * third case — a model that takes no temperature was never offered the choice — which
 * the form states by drawing no slider at all and printing the response's own sentence
 * where it stood.
 *
 * **The reasoning effort:** that it is a declared input of its own. What came out was
 * why it is not the temperature: two runs of one model at one temperature and different
 * effort are two different instruments. That is an argument for recording it, and the
 * report records it.
 *
 * **T:** that an episode reaching the cap is censored. What came out was that a censored
 * episode is a reading about the attacker and never about the target — which is
 * `EpisodeOutcome`'s own rule and is stated wherever an episode is reported.
 *
 * **k:** that episodes are not samples of a rate. What came out was the consequence,
 * that more of them buy coverage and no precision, which follows from it.
 *
 * **Attempts per case:** that it is the scored denominator and the only setting here
 * that moves a rate. `TuningBlock.warning` — the bench's own sentence about what a run
 * at another number may be called — is untouched and still drawn.
 */
const WHAT_A_REASONING_EFFORT_DECIDES = 'a declared input of its own, beside the model'

const WHAT_A_TEMPERATURE_DECIDES =
  'how varied the probes are \u2014 blank is the provider\u2019s default'

const WHAT_A_TUNED_SETTING_DECIDES: Record<TunedNumber['name'], string> = {
  turns_per_episode: 'T \u2014 an episode that reaches the cap is censored',
  episodes_per_family: 'k \u2014 episodes are not samples of a rate',
  attempts_per_case: 'the scored denominator \u2014 the one setting here that moves a rate',
}

/** What the attacker's model drives, which its identifier cannot say. */
export const WHAT_THE_ATTACKER_DRIVES = 'drives the adaptive layer, scored on nothing'

function tunedNumbers(tuning: Tuning): TunedNumber[] {
  return [
    {
      name: 'turns_per_episode',
      label: 'turns per episode',
      value: tuning.turns_per_episode,
      low: tuning.turns_bounds.low,
      high: tuning.turns_bounds.high,
      decides: WHAT_A_TUNED_SETTING_DECIDES.turns_per_episode,
    },
    {
      name: 'episodes_per_family',
      label: 'episodes per family',
      value: tuning.episodes_per_family,
      low: tuning.episodes_bounds.low,
      high: tuning.episodes_bounds.high,
      decides: WHAT_A_TUNED_SETTING_DECIDES.episodes_per_family,
    },
    {
      name: 'attempts_per_case',
      label: 'attempts per case',
      value: tuning.attempts_per_case,
      low: tuning.attempts_bounds.low,
      high: tuning.attempts_bounds.high,
      decides: WHAT_A_TUNED_SETTING_DECIDES.attempts_per_case,
    },
  ]
}

export function settingsScreen(bench: BenchSettings): SettingsBlock[] {
  return [
    {
      kind: 'keys',
      heading: 'The two keys, and they are two different facts',
      statement: bench.signing.statement,
      identities: keyIdentities(
        bench.signing.will_be_signed_by,
        bench.signing.verified_against,
      ),
      command: KEYGEN_COMMAND,
      commandStatement: NO_SCREEN_GENERATES_A_KEY,
    },
    {
      kind: 'library',
      heading: 'The case library this bench is loaded with',
      statement: bench.library.statement,
      facts: libraryFacts(bench.library),
      stated: bench.library.stated,
      kept: bench.library.kept,
    },
    {
      kind: 'agents',
      heading: 'The three agents the discrimination score is measured against',
      statement: THE_AGENTS_ARE_WHAT_D_IS_MEASURED_ON,
      agents: [...REFERENCE_AGENTS],
    },
    {
      kind: 'models',
      heading: 'The four model settings',
      statement: FOUR_AND_NEVER_ONE,
      models: [...bench.models],
    },
    {
      kind: 'ceilings',
      heading: 'Each layer’s ceiling, and neither borrows the other’s',
      statement: bench.ceilings.statement,
      ceilings: [
        scoredCeiling(bench.ceilings.scored),
        adaptiveCeiling(bench.ceilings.adaptive),
      ],
    },
    {
      kind: 'tuning',
      heading: 'What the next run is made with',
      statement: bench.tuning.statement,
      models: bench.tuning.attacker_models,
      sampling: {
        bounds: bench.tuning.temperature_bounds,
        chosen: bench.tuning.temperature,
        absent: bench.tuning.temperature_absent,
        decides: WHAT_A_TEMPERATURE_DECIDES,
        stated: bench.tuning.temperature_stated,
      },
      reasoning: {
        levels: bench.tuning.reasoning_efforts,
        chosen: bench.tuning.reasoning_effort,
        absent: bench.tuning.reasoning_effort_absent,
        decides: WHAT_A_REASONING_EFFORT_DECIDES,
        stated: bench.tuning.reasoning_effort_stated,
      },
      numbers: tunedNumbers(bench.tuning),
      attemptsPerFamily: `${bench.tuning.attempts_per_family} attempts per family`,
      declaredAttemptsPerCase: `the declared rule reads ${bench.tuning.declared_attempts_per_case}`,
      warning: bench.tuning.attempts_warning,
    },
  ]
}

/**
 * The library's three labelled facts: the live count, the digest, the retired count.
 *
 * The count and the digest both, because a library described only as *eighteen cases*
 * cannot tell a reader whether the eighteen are the same eighteen. The retired count
 * is a third fact beside them and never folded into the first: the two answer
 * different questions, and their sum is a case count nothing runs.
 */
function libraryFacts(library: BenchSettings['library']): CitedFact[] {
  const cases = library.live.cases
  return [
    {
      label: 'Live cases',
      value: `${cases} ${cases === 1 ? 'case' : 'cases'} a run scores`,
    },
    { label: 'Digest', value: `sha256:${library.live.digest}` },
    {
      label: 'Retired and kept',
      value: `${library.retired} ${library.retired === 1 ? 'case' : 'cases'}`,
    },
  ]
}
