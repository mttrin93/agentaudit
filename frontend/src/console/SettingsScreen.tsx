/**
 * The operator's screen for what this bench is set to. It states; it changes nothing.
 *
 * The blocks are `settings.ts`'s sequence and this file maps over it in order, so
 * *the keys above the ceilings* is a property of a value a test reads rather than of
 * markup nobody checks.
 *
 * **There is no control here.** Not one element on this screen writes a setting, and
 * there is no route on this bench that would take one: the signing key is rotated in
 * the environment and the models, the library and the thresholds are chosen on the
 * command line, because the factory reads its key from one place and refuses to boot
 * without it (ADR-0020). So the console prints the command that makes a key pair and
 * offers no affordance, and `settings.test.ts` reads this file to assert the absence.
 *
 * **Two key identifiers, side by side and never merged.** The key an artefact will be
 * signed by and the key a verification is run against are two blocks, each with its
 * own fingerprint and its own sentence. A bench that will sign nothing is drawn
 * dashed and without the row a fingerprint would have filled — `.citation.uncited`'s
 * idiom, for the reason it exists: an empty value in a solid box is read as a value
 * that failed to load.
 *
 * **The two ceilings are two blocks with a gap between them and no rule underneath.**
 * `.layers` is the interrupt's own layout, chosen there because a stacked pair with a
 * line under it is a table waiting for a total. It is the right shape here for the
 * same reason.
 *
 * **The idiom is the console's own.** One reading column, labelled uncoloured facts,
 * `.family` and `.family.absent` for a block that may have no figure, the reference
 * agents in one hue's three ordered steps, `.command` for a command. Colour carries
 * identity and order and never a judgement: no key, no model and no ceiling is
 * coloured by how good it is.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { benchSettings, type BenchSettings } from '../api/bench'
import { GATE_PATH } from './rail'
import {
  settingsScreen,
  WHAT_THIS_SCREEN_ANSWERS,
  type AgentsBlock,
  type CeilingsBlock,
  type KeysBlock,
  type LibraryBlock,
  type ModelsBlock,
  type SettingsBlock,
} from './settings'

/** What this screen is holding: the configuration, or why it has none. */
interface Held {
  bench: BenchSettings | null
  unavailable: string
}

const NOTHING_YET: Held = { bench: null, unavailable: '' }

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
      <header>
        <p className="eyebrow">AgentAudit — what this instrument is set to</p>
        <h1>Settings: stated here, changed elsewhere</h1>
        <p className="steps">
          {WHAT_THIS_SCREEN_ANSWERS}{' '}
          <Link to={GATE_PATH}>The gate</Link> says what the bench last answered
          under its own rule.
        </p>
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
        settingsScreen(held.bench).map((block) => (
          <Block block={block} key={block.kind} />
        ))
      )}
    </main>
  )
}

/** One block, in the order the reading gave it. Five kinds, five shapes. */
function Block({ block }: { block: SettingsBlock }) {
  switch (block.kind) {
    case 'keys':
      return <TheKeys block={block} />
    case 'library':
      return <TheLibrary block={block} />
    case 'agents':
      return <TheAgents block={block} />
    case 'models':
      return <TheModels block={block} />
    case 'ceilings':
      return <TheCeilings block={block} />
  }
}

/**
 * The two key identifiers, each in its own block with its own fingerprint.
 *
 * Two and never one. A bench that will sign nothing is drawn dashed and without the
 * row a fingerprint would have filled, so there is nothing on the screen for a reader
 * to mistake for a key that failed to load.
 */
function TheKeys({ block }: { block: KeysBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <div className="families">
        {block.identities.map((identity) => (
          <div
            className={identity.held ? 'family' : 'family absent'}
            key={identity.label}
          >
            <h4>{identity.label}</h4>
            {identity.held ? (
              <p>
                <code>{identity.fingerprint}</code>
              </p>
            ) : null}
            <p className="kind">{identity.stated}</p>
          </div>
        ))}
      </div>
      <p className="aside">{block.statement}</p>

      <h3>Making a pair, and why nothing here does it for you</h3>
      <pre className="command">{block.command}</pre>
      <p>{block.commandStatement}</p>
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
      <p className="aside">{block.statement}</p>
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
      <p className="aside">{block.statement}</p>
    </section>
  )
}
