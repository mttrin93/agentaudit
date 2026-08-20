/**
 * The operator's screen: the declared rule, the last outcome, and the command.
 *
 * It answers one question — when was this instrument last validated, and how do I do
 * it again — and it answers the first half before the second, because the rule is
 * what makes the answer re-derivable. The blocks are `gate.ts`'s sequence and this
 * file maps over it in order, so *the rule above the outcome* and *the write-back
 * before the command* are properties of a value a test reads rather than of markup
 * nobody checks.
 *
 * **There is no button here.** Not one element on this screen starts a gate run, and
 * there is no route on this bench that would take one: a gate run is the whole
 * admitted library against all three reference agents on the operator's own provider,
 * behind a terminal that asks the three attestation statements one at a time and
 * treats an absent or piped answer as a refusal (ADR-0007, PLAN.md §8). So the
 * console prints the command instead, on its own line and with nothing around it, and
 * `gate.test.ts` reads this file to assert the absence.
 *
 * **The document is named rather than linked, and that is a deferral rather than a
 * preference.** The citation carries the path the gate run wrote itself to; this
 * bench serves no route that hands the document over, so a hyperlink here would be a
 * link to nothing — worse than a path an operator can open in the repository they are
 * standing in. Serving it needs either a route or a decision recorded outside this
 * screen, and neither exists yet.
 *
 * **The idiom is the console's own.** One reading column, `.citation` and
 * `.citation.uncited` for the outcome and for the absence of one, labelled uncoloured
 * facts, and the reference agents in one hue's three ordered steps — identity and
 * order, never judgement. No outcome, no threshold and no agent is coloured by how
 * good it is: a colour scale over a pass and a fail is the severity scale the report
 * exists to refuse, and it does not arrive here by the back door.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { benchGate, type BenchGate } from '../api/bench'
import {
  gateScreen,
  WHAT_THIS_SCREEN_ANSWERS,
  type CommandBlock,
  type ConsequenceBlock,
  type GateBlock,
  type OutcomeBlock,
  type RuleBlock,
} from './gate'
import type { GateReading } from './landing'
import { CONSOLE_PATH } from './rail'

/** What this screen is holding: the rule and the citation, or why it has neither. */
interface Held {
  bench: BenchGate | null
  unavailable: string
}

const NOTHING_YET: Held = { bench: null, unavailable: '' }

export function GateScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const bench = await benchGate()
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
        <p className="eyebrow">AgentAudit — the bench’s own certification</p>
        <h1>The gate: the rule, the last outcome, and the command</h1>
        <p className="steps">
          {WHAT_THIS_SCREEN_ANSWERS}{' '}
          <Link to={CONSOLE_PATH}>What this bench is</Link> says the rest.
        </p>
      </header>

      {held.unavailable ? (
        <section>
          <h2>This bench did not answer for its own gate</h2>
          <div className="citation uncited" role="alert">
            <h3>Neither the rule nor the citation could be read</h3>
            <p>{held.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that cites no gate run: what is unknown
              here is what it would have said, and nothing on this page should be
              read as either answer. The command below is unchanged either way — it
              is how a gate run is started, not something this bench told us.
            </p>
          </div>
        </section>
      ) : held.bench === null ? (
        <section>
          <p className="aside">Reading the declared rule and this bench’s citation…</p>
        </section>
      ) : (
        gateScreen(held.bench).map((block) => (
          <Block block={block} key={block.kind} />
        ))
      )}
    </main>
  )
}

/** One block, in the order the reading gave it. Four kinds, four shapes. */
function Block({ block }: { block: GateBlock }) {
  switch (block.kind) {
    case 'rule':
      return <TheRule block={block} />
    case 'outcome':
      return <TheOutcome block={block} />
    case 'consequence':
      return <TheConsequence block={block} />
    case 'command':
      return <TheCommand block={block} />
  }
}

/**
 * The declared rule, printed in the bench's own words, and the three agents it is
 * put to.
 *
 * A list of the rule's own clauses rather than a paragraph about them: the text is
 * `GateRule.stated()` split at its line breaks, so a threshold moved in `rule.py`
 * moves here and nothing on this screen can claim a bar the gate was not held to.
 */
function TheRule({ block }: { block: RuleBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <p>{block.statement}</p>
      <ul className="clauses">
        {block.clauses.map((clause) => (
          <li className={clause.under ? 'under' : undefined} key={clause.line}>
            {clause.line}
          </li>
        ))}
      </ul>

      <h3>The three agents it is put to</h3>
      <div className="agents">
        {block.agents.map((agent) => (
          <div className={`agent ${agent.accent}`} key={agent.name}>
            <p className="agent-name">{agent.name}</p>
            <p className="kind">{agent.built}</p>
          </div>
        ))}
      </div>
      <p className="aside">{block.agentsStatement}</p>
    </section>
  )
}

/** What the last gate run answered, or the stated absence of one, in one region. */
function TheOutcome({ block }: { block: OutcomeBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <Citation reading={block.reading} />
    </section>
  )
}

/**
 * What a gate run writes and what it spends, before the command that starts one.
 *
 * A list of consequences and not a warning box: every line of it is a fact about
 * what the run does, and an operator reading them is deciding whether to spend their
 * own budget and change the library every one of their runs is measured with.
 */
function TheConsequence({ block }: { block: ConsequenceBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <p className="consequence">{block.statement}</p>
      <ul>
        {block.writes.map((write) => (
          <li key={write}>{write}</li>
        ))}
      </ul>
    </section>
  )
}

/**
 * The command, on its own line with nothing around it, and what it is the only way
 * to do.
 *
 * A `pre` rather than a `code` inside a sentence, so that selecting the line selects
 * the command and nothing else. There is no copy button and no control of any kind
 * here: what starts a gate run is a terminal, and the console's contribution to that
 * invariant is to offer nothing.
 */
function TheCommand({ block }: { block: CommandBlock }) {
  return (
    <section>
      <h2>{block.heading}</h2>
      <pre className="command">{block.command}</pre>
      {block.statements.map((statement) => (
        <p key={statement}>{statement}</p>
      ))}
    </section>
  )
}

/**
 * The citation, or the stated absence of one, in the same region either way.
 *
 * The front door's idiom, deliberately: dashed and drawn without the rows a citation
 * would have filled when there is nothing cited, because an empty outcome in a solid
 * box is read as a gate the bench failed. Nothing here is coloured by outcome.
 */
function Citation({ reading }: { reading: GateReading }) {
  return (
    <div className={reading.cited ? 'citation' : 'citation uncited'}>
      <h3>{reading.heading}</h3>
      {reading.cited ? (
        <>
          <dl className="at">
            {reading.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p>
            The gate run wrote itself down at <code>{reading.document.path}</code>,
            named as the path it is: this bench serves no route that hands the
            document over, and a link to nothing would be worse than a path.
          </p>
          <p className="aside">{reading.document.statement}</p>
        </>
      ) : (
        <p>{reading.statement}</p>
      )}
      <p className="aside">{reading.aboutTheBench}</p>
    </div>
  )
}
