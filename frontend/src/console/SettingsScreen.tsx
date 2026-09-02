/**
 * The operator's screen for what this bench is set to. It states; it changes nothing.
 *
 * The blocks are `settings.ts`'s sequence and this file maps over it in order, so
 * *the library above the ceilings* is a property of a value a test reads rather than of
 * markup nobody checks.
 *
 * **There is no control here.** Not one element on this screen writes a setting, and
 * there is no route on this bench that would take one: the signing key is rotated in
 * the environment and the models, the library and the thresholds are chosen on the
 * command line, because the factory reads its key from one place and refuses to boot
 * without it (ADR-0020). So the console offers no affordance at all, and
 * `settings.test.ts` reads this file to assert the absence.
 *
 * **The two key identifiers are not drawn here.** They are still the reading's first
 * block, still two and still never merged — `settings.ts` builds both fingerprints,
 * both sentences and the keygen command, and its test holds them apart. What a
 * recipient pins is published in this repository's README, and what an artefact was
 * signed by is a result on the artefact; a fingerprint on a settings page is a string
 * nobody checks anything against.
 *
 * **The two ceilings are two blocks with a gap between them and no rule underneath.**
 * `.layers` is the interrupt's own layout, chosen there because a stacked pair with a
 * line under it is a table waiting for a total. It is the right shape here for the
 * same reason.
 *
 * **The idiom is the console's own.** One reading column, labelled uncoloured facts,
 * `.family` and `.family.absent` for a block that may have no figure, and the reference
 * agents in one hue's three ordered steps. Colour carries
 * identity and order and never a judgement: no key, no model and no ceiling is
 * coloured by how good it is.
 */

import { useEffect, useRef, useState } from 'react'

import {
  benchSettings,
  tuneBench,
  type BenchSettings,
  type Bounds,
} from '../api/bench'
import {
  settingsScreen,
  type AgentsBlock,
  type CeilingsBlock,
  type LibraryBlock,
  type ModelsBlock,
  type SettingsBlock,
  type TuningBlock,
} from './settings'

/** What this screen is holding: the configuration, or why it has none. */
interface Held {
  bench: BenchSettings | null
  unavailable: string
}

const NOTHING_YET: Held = { bench: null, unavailable: '' }

/** How long a control has to stop moving before what it now reads is sent. */
const SETTLED_MS = 400

export function SettingsScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const bench = await benchSettings()
        if (current) {
          setHeld({ bench, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setHeld({ bench: null, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  return (
    <main className="screen">
      {/*
        The name of the screen and nothing over or under it.
        The eyebrow named the app on a page inside the app; the line under the title
        said what the screen answers and then pointed at the gate, which the rail is
        already pointing at. *Stated here, changed elsewhere* was the title's second
        half and is the first thing every block below says about its own setting.
        `WHAT_THIS_SCREEN_ANSWERS` is still built and still exported.
      */}
      <header>
        <h1>Settings</h1>
      </header>

      {held.unavailable ? (
        <section>
          <h2>This bench did not answer for its own configuration</h2>
          <div className="citation uncited" role="alert">
            <h3>Nothing below could be read</h3>
            <p>{held.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench with nothing configured: what is unknown
              here is what it would have said, and no absence on this page should be
              read as a setting this bench does not hold.
            </p>
          </div>
        </section>
      ) : held.bench === null ? (
        <section>
          <p className="aside">Reading this bench’s own configuration…</p>
        </section>
      ) : (
        settingsScreen(held.bench)
          // The keys are not drawn. They are the first block of the reading and stay
          // there — `settings.test.ts` reads the order off the value — but a fingerprint
          // is not a setting somebody comes to this screen to read: what a recipient
          // pins is published in the README, and what an artefact was signed by is on
          // the artefact. The block, its two sentences and the keygen command were the
          // longest thing on the page and the least often read.
          // Five blocks are built and not drawn. They stay in the reading — its
          // order and its shape are asserted in `settings.test.ts`, and *four model
          // settings and never one* is an invariant a reading of three would break by
          // omission (ADR-0012, ADR-0013). They are off the page because none of them
          // answers a question somebody opens Settings to ask.
          //
          // The keys: a fingerprint here is checked against nothing; what a recipient
          // pins is in the README and what an artefact was signed by is on the
          // artefact. The library: its version prints on every report and in every
          // gate citation, which is where a version is compared. The three reference
          // agents and the four model settings: three of those four are facts about
          // other processes and other scripts, and the fourth — the attacker's model
          // — is set in the form below and read there. What each model *decides* is
          // provenance, and it travels on the artefact rather than on this screen.
          //
          // The two ceilings: the numbers they are computed from are the ones the
          // form sets, and the worst case they multiply out to is shown where it is
          // consented to — at the approval interrupt, before a run sends anything,
          // which is the only place a ceiling figure does any work (ADR-0007).
          .filter(
            (block) =>
              !['keys', 'library', 'agents', 'models', 'ceilings'].includes(
                block.kind,
              ),
          )
          .map((block) => (
            <Block
              block={block}
              key={block.kind}
              // The bench's own answer to the write, straight into what is drawn: a
              // screen that kept its own copy of a setting would show what it sent
              // rather than what was stored.
              onTuned={(bench) => setHeld({ bench, unavailable: '' })}
            />
          ))
      )}
    </main>
  )
}

/** One block, in the order the reading gave it. Five kinds, five shapes. */
function Block({
  block,
  onTuned,
}: {
  block: SettingsBlock
  onTuned: (bench: BenchSettings) => void
}) {
  switch (block.kind) {
    case 'library':
      return <TheLibrary block={block} />
    case 'agents':
      return <TheAgents block={block} />
    case 'models':
      return <TheModels block={block} />
    case 'ceilings':
      return <TheCeilings block={block} />
    case 'tuning':
      return <TheTuning block={block} onTuned={onTuned} />
  }
}

/**
 * The declared inputs of the next run, and the only control on this screen.
 *
 * **Every field here changes what the next run measured**, which is why the block
 * prints the bench's own sentence about that above the form rather than a label per
 * input: an operator setting `T` is choosing what an `A_effort` figure will mean, and
 * an operator setting attempts per case is choosing whether the run is a gate result
 * at all (ADR-0025).
 *
 * The six settings go in one request. A form that could send the turn budget without
 * restating the model would let a bench name one instrument in a report while another
 * attacked, and the request model on the other end takes all six for that reason.
 *
 * The answer is the whole settings reading, so what the screen draws afterwards is
 * what the bench stored — never what this form hoped it sent. A refusal is shown as
 * the bench's own sentence, including the one that says a run is still going: that is
 * a state to wait out rather than an error to work around.
 */
/** Where an untouched temperature slider sits: the middle of its own range.
 *
 * A position and not a declaration. The provider's default is a fact about the
 * provider and this bench does not know it, so the slider cannot start *at* it —
 * what it can do is not claim to: until the control is moved, `shown` reads
 * *not declared* and the request carries `null`.
 */
function provided(bounds: Bounds): number {
  return (bounds.low + bounds.high) / 2
}

/** The temperature as the label states it: the live number, or that none is declared.
 *
 * Read off the form's own state and not off the block, so the label follows the
 * slider. A control whose number lags what it is set to is worse than one with no
 * number on it.
 */
function stated(held: string): string {
  return held === '' ? 'not declared' : held
}

function TheTuning({
  block,
  onTuned,
}: {
  block: TuningBlock
  onTuned: (bench: BenchSettings) => void
}) {
  const chosen = block.models.find((model) => model.chosen)
  const [model, setModel] = useState(chosen?.identifier ?? '')
  // `null` and not `''`: nothing declared is a statement of its own, and it is the
  // one the request carries for an unset control.
  const [effort, setEffort] = useState<string | null>(block.reasoning.chosen)
  // Its own state and not a row in `numbers`, because it is the one setting the
  // chosen model may have no setting for at all: `''` is *not declared* and the
  // request carries `null` for it.
  const [temperature, setTemperature] = useState(
    block.sampling.chosen === null ? '' : `${block.sampling.chosen}`,
  )
  const [numbers, setNumbers] = useState<Record<string, string>>(
    Object.fromEntries(
      block.numbers.map((one) => [one.name, one.value === null ? '' : `${one.value}`]),
    ),
  )
  const [refused, setRefused] = useState('')
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null)

  const read = (name: string) => numbers[name] ?? ''

  /**
   * Send the six settings as they now stand, and draw what the bench answers.
   *
   * There is no confirm step, and the reason there does not need to be one is that
   * nothing here spends anything: these are the settings the *next* run will be
   * started with, and that run has its own attestation and its own halt in front of
   * its own estimate (ADR-0007). The bench refuses a change while a run is going, so
   * a setting cannot move under a run that was already confirmed.
   */
  const send = async (asked: {
    model: string
    effort: string | null
    temperature: string
    numbers: Record<string, string>
  }) => {
    const at = (name: string) => asked.numbers[name] ?? ''
    setRefused('')
    try {
      const bench = await tuneBench({
        attacker_model: asked.model,
        // An untouched slider is `null` and not a zero: *no temperature declared* is
        // a different statement from *sampled at zero*, and the field records which
        // one an operator made. A model that accepts none draws no slider at all and
        // sends the same `null`.
        temperature: asked.temperature === '' ? null : Number(asked.temperature),
        // Sent every time, like every other field: this `PUT` is the whole statement
        // of how the instruments are set, so a request that left it out would clear
        // an effort the bench is holding.
        reasoning_effort: asked.effort,
        turns_per_episode: Number(at('turns_per_episode')),
        episodes_per_family: Number(at('episodes_per_family')),
        attempts_per_case: Number(at('attempts_per_case')),
      })
      onTuned(bench)
    } catch (refusal: unknown) {
      setRefused(`${refusal}`)
    }
  }

  /**
   * Send after the operator stops moving, rather than on every step of a drag.
   *
   * A slider fires a change per increment and a number box one per keystroke, and a
   * request per increment would have the bench answering about settings nobody
   * paused on. The last one wins, which is what a settled control is.
   */
  const settle = (asked: {
    model: string
    effort: string | null
    temperature: string
    numbers: Record<string, string>
  }) => {
    if (pending.current !== null) {
      clearTimeout(pending.current)
    }
    pending.current = setTimeout(() => void send(asked), SETTLED_MS)
  }

  return (
    <section>
      {/* The heading and the block's own paragraph are built and not drawn. It argued why these
          settings may be set here at all — which is ADR-0025's business and the
          commit log's, not a paragraph an operator reads every time they change a
          number. What the page keeps is per-control: each input says what it
          decides, and `block.warning` stays, because that one is not an
          explanation of the screen but a limit on what a run at that setting may
          be called. */}
      <div className="tuning">
        <label>
          <span className="kind">the adaptive attacker</span>
          <select
            value={model}
            onChange={(event) => {
              setModel(event.target.value)
              // A pick is settled the moment it is made — there is nothing to stop
              // moving — so this one does not wait.
              // A model change can carry an effort the new model has no setting
              // for, and the route refuses the pair rather than dropping half of
              // it — so the level is cleared with the model that accepted it, and
              // the reading that comes back says what the new model offers.
              setEffort(null)
              // And the temperature with it, for the same reason in the other
              // direction: a chat model's temperature carried onto a reasoning model
              // is a pair the route refuses rather than half-drops, so it is cleared
              // with the model that accepted it and the reading that comes back says
              // whether the new one has the setting at all.
              setTemperature('')
              void send({
                model: event.target.value,
                effort: null,
                temperature: '',
                numbers,
              })
            }}
          >
            {block.models.map((one) => (
              <option key={one.identifier} value={one.identifier}>
                {one.identifier}
              </option>
            ))}
          </select>
        </label>
        {/* Drawn only where the model has the setting, and the reading says whether
            an empty list means *no such setting* or *no level chosen*. A select and
            not a slider, because the levels are a closed set and not a range. */}
        {block.reasoning.levels.length > 0 ? (
          <label>
            <span className="kind">reasoning effort</span>
            <select
              value={effort ?? ''}
              onChange={(event) => {
                const picked = event.target.value === '' ? null : event.target.value
                setEffort(picked)
                // Settled the moment it is made, like the model pick above: there is
                // nothing to stop moving.
                void send({ model, effort: picked, temperature, numbers })
              }}
            >
              <option value="">not declared</option>
              {block.reasoning.levels.map((one) => (
                <option key={one.level} value={one.level}>
                  {one.level}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {/* What an unset level means, what the setting decides, and the sentence a run
            made now would print are all built and not drawn — the reading keeps them
            and `settings.test.ts` holds them, on the same terms as every other
            per-control sentence on this screen. */}

        {/* What the chosen model is for is built and not drawn: the reading carries
            a line per model, and which model to attack with is a decision made once
            against the four rather than re-read on every visit. It stays on the
            block, where `settings.test.ts` holds it. */}

        {/* Drawn only where the model takes one, which is the reasoning select's own
            rule read the other way round: a slider against a reasoning model is a
            control whose every value the route refuses, and until the response said
            so the form learned it from the 422 after the operator had moved it. The
            sentence saying *why* there is no slider is the response's own and is
            built rather than drawn, on the same terms as every other per-control
            sentence here — `block.sampling.stated`, which is what the signed
            document will print. */}
        {block.sampling.bounds !== null ? (
          <label>
            <span className="kind">
              attacker temperature <strong>{stated(temperature)}</strong>
            </span>
            {/* A slider, and the value beside the label because a track with no
                number on it is a control an operator cannot report. It has no
                "undeclared" position — a range input always has a value — so an
                untouched slider sends `null` and the label says so: *no temperature
                declared* and *sampled at zero* are two different statements and the
                field records which one was made. */}
            <input
              type="range"
              value={
                temperature === '' ? `${provided(block.sampling.bounds)}` : temperature
              }
              min={block.sampling.bounds.low}
              max={block.sampling.bounds.high}
              step={0.1}
              onChange={(event) => {
                setTemperature(event.target.value)
                settle({ model, effort, temperature: event.target.value, numbers })
              }}
            />
          </label>
        ) : (
          // The one sentence on this form that is drawn rather than built, and the
          // reason is that it is not an explanation of the screen: a control that
          // was here a moment ago and is now gone is a silence an operator has to
          // decode, and what they would decode it as is *the console lost the
          // setting*. The response's own words, which are the words the signed
          // provenance block of a run made now would print — never a second wording
          // composed here (ADR-0017).
          <p className="unavailable">{block.sampling.stated}</p>
        )}
        {/* Every control's own sentence — what it decides, and what leaving the
            temperature undeclared means — is built and not drawn. The reading keeps
            them and `settings.test.ts` holds them. */}
        {block.numbers.map((one) => (
          <label key={one.name}>
            <span className="kind">{one.label}</span>
            <input
              type="number"
              value={read(one.name)}
              min={one.low}
              max={one.high}
              step={1}
              onChange={(event) => {
                const typed = { ...numbers, [one.name]: event.target.value }
                setNumbers(typed)
                settle({ model, effort, temperature, numbers: typed })
              }}
            />
          </label>
        ))}

        {/* The scored denominator's caveat, the `n` at this setting and the `n` the
            declared rule reads are all built and not drawn. They are still on the
            response this form reads, still the reason ADR-0025 admits the setting at
            all, and the rule a run was measured at still travels on that run's own
            report beside every rate — so what a run at another number may be called
            is recorded where it is checkable rather than on this screen.

            There is no button either. Nothing here spends anything: these are the
            settings the *next* run starts with, and that run has its own attestation
            and its own halt in front of its own estimate. */}
      </div>

      {refused ? (
        <div className="citation uncited" role="alert">
          <h3>Nothing was changed</h3>
          <p>{refused}</p>
        </div>
      ) : null}
    </section>
  )
}

/** The library as loaded: its live version, and the retired cases kept beside it. */
function TheLibrary({ block }: { block: LibraryBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <dl className="at">
        {block.facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
      <p>{block.stated}</p>
      <p>{block.kept}</p>
      <p className="aside">{block.statement}</p>
    </section>
  )
}

/** The three reference agents, in one hue's three ordered steps and with no figure. */
function TheAgents({ block }: { block: AgentsBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <div className="agents">
        {block.agents.map((agent) => (
          <div className={`agent ${agent.accent}`} key={agent.name}>
            <p className="agent-name">{agent.name}</p>
            <p className="kind">{agent.built}</p>
          </div>
        ))}
      </div>
      <p className="aside">{block.statement}</p>
    </section>
  )
}

/**
 * The four model settings, as four blocks and never as one row.
 *
 * A block each rather than a table, because a table of four models wants a column
 * they can be compared in and there is nothing here to compare: they are four
 * different instruments, and the whole point of the block is that no two of them are
 * one. A setting this bench does not hold is drawn dashed, with the sentence where
 * the identifier would have been.
 */
function TheModels({ block }: { block: ModelsBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <div className="families">
        {block.models.map((model) => (
          <div
            className={model.declared ? 'family' : 'family absent'}
            key={model.instrument}
          >
            <h4>{model.instrument}</h4>
            <p>
              <code>{model.identifier}</code>
            </p>
            <p className="kind">{model.decides}</p>
          </div>
        ))}
      </div>
      {/* The block's own paragraph is built and not drawn. Each row already says
          what its instrument decides, and the paragraph restated the reason the four
          are four — which is a fact about why this screen is shaped this way rather
          than something an operator reads it to find out. It stays on the reading,
          where `settings.test.ts` holds it. */}
    </section>
  )
}

/**
 * The two ceilings, side by side, with nothing under them.
 *
 * `.layers` and not a table: a stacked pair with a rule underneath is a table waiting
 * for a total, and the two figures here are in different units so the total would not
 * even be a quantity. Each block carries its own declared numbers and the record they
 * are declared in.
 */
function TheCeilings({ block }: { block: CeilingsBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <div className="layers">
        {block.ceilings.map((ceiling) => (
          <div className="layer" key={ceiling.layer}>
            <h3>{ceiling.heading}</h3>
            <p>{ceiling.limit}</p>
            <dl className="at">
              {ceiling.figures.map((figure) => (
                <div key={figure.label}>
                  <dt>{figure.label}</dt>
                  <dd>{figure.value}</dd>
                </div>
              ))}
            </dl>
            <p className="kind">{ceiling.statement}</p>
            <p className="aside">
              Declared in <code>{ceiling.declaredIn}</code>
            </p>
          </div>
        ))}
      </div>
      {/* Built and not drawn, for the reason the models block's is. Each ceiling
          already carries its own sentence and its own units; the paragraph argued
          that the two cannot be added, which is a property of the shape and is
          asserted as one in `settings.test.ts` rather than explained on the page. */}
    </section>
  )
}
