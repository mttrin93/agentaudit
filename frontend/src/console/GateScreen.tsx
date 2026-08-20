/**
 * The operator's screen: the declared rule, the last outcome, and the two ways to
 * run another.
 *
 * It answers one question — when was this instrument last validated, and how do I do
 * it again — and it answers the first half before the second, because the rule is
 * what makes the answer re-derivable. The blocks are `gate.ts`'s sequence and this
 * file maps over it in order, so *the rule above the outcome* and *the write-back
 * before the way to start one* are properties of a value a test reads rather than of
 * markup nobody checks.
 *
 * **There is one control here and it is the one ADR-0021 authorised.** `PLAN.md` §8
 * put a gate run on the command line, this screen printed the command, and a
 * deployed bench had no terminal to run it in. So the command block carries a start
 * control where the bench says a gate run may begin — and a *stated refusal* where
 * it may not: no reference agents shipped, no case library it may write to, no
 * adjudicating instrument, or a gate run already holding the library. The bench
 * decides which; this screen reads the answer and never guesses it.
 *
 * **The consent flow is the register screen's, walked here.** The three attestation
 * statements one at a time, in the record's own wording, then the estimate as two
 * figures against two ceilings before anything is sent. Declining a statement sends
 * nothing at all; declining the estimate sends a `confirmed: false` that records the
 * gate run as declined by a person and leaves the case library byte for byte as it
 * was. There is no path through this file to a `confirmed: true` that
 * `gaterun.gateConfirmation` did not build.
 *
 * **The two writes this screen can make are a gate run's.** It imports
 * `startGateRun` and `answerTheGateRunsInterrupt` and nothing else that posts: it
 * cannot start a run, cannot answer a run's interrupt, and has no `fetch` of its
 * own. `gate.test.ts` reads this file and asserts exactly that, which is the
 * assertion the read-only version of this screen made in the other direction.
 *
 * **Per-family figures come from the gate run, never from a document.** While one is
 * in flight the screen shows progress per layer — family, case and attempt on one
 * side, family, episode and turn on the other — and when it is decided it shows the
 * rule above the outcome and then each family's three rates and its `D`, read off
 * the run that just happened. The *cited* gate run's figures are still only in its
 * document, and this screen still does not read it.
 *
 * **The idiom is the console's own.** One reading column, `.citation` and
 * `.citation.uncited`, `.figures` for the estimate, `.layers` for progress,
 * `.families` for the per-family figures, labelled uncoloured facts, and the three
 * reference agents in one hue's three ordered steps. No outcome is coloured: a pass
 * in green and a fail in red is the severity scale the report exists to refuse.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  answerTheGateRunsInterrupt,
  benchGate,
  gateRunReading,
  gateRuns,
  startGateRun,
  type ApprovalBody,
  type BenchGate,
  type GateRunReading,
  type GateRunStart,
  type GateRunStarted,
} from '../api/bench'
import type { LayerReading } from '../run/progress'
import {
  gateScreen,
  WHAT_THIS_SCREEN_ANSWERS,
  type CommandBlock,
  type ConsequenceBlock,
  type GateBlock,
  type OutcomeBlock,
  type RuleBlock,
} from './gate'
import {
  decidedView,
  gateConfirmation,
  gateDecline,
  gateInterruptView,
  gateProgress,
  gateRunRequest,
  GATE_RUN_STATEMENTS,
  nothingAttested,
  startControl,
  stillGoing,
  type Attesting,
  type DecidedBlock,
  type Fact,
  type FamilyReading,
  type GateInterruptView,
  type StartControl,
} from './gaterun'
import type { GateReading } from './landing'
import { CONSOLE_PATH } from './rail'

/** How often a gate run in flight is asked where it has got to. */
const POLL_SECONDS = 2

/** What this screen is holding: the rule, the citation, and whether one may start. */
interface Held {
  bench: BenchGate | null
  start: GateRunStart | null
  unavailable: string
}

const NOTHING_YET: Held = { bench: null, start: null, unavailable: '' }

/**
 * Where the operator is in starting one.
 *
 * Four stages, and the first is the screen at rest. A union rather than three
 * booleans because they are exclusive: an operator cannot be reading the statements
 * and confirming the figures at once, and a screen that allowed both would have two
 * answers to *what am I consenting to*.
 */
type Stage = 'idle' | 'attesting' | 'estimate' | 'watching'

export function GateScreen() {
  const [held, setHeld] = useState<Held>(NOTHING_YET)
  const [stage, setStage] = useState<Stage>('idle')
  const [attesting, setAttesting] = useState<Attesting>(nothingAttested)
  const [step, setStep] = useState(0)
  const [started, setStarted] = useState<GateRunStarted | null>(null)
  const [reading, setReading] = useState<GateRunReading | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [refused, setRefused] = useState('')
  const [busy, setBusy] = useState(false)

  /**
   * The rule, the citation, and whether a gate run may start — read once, on arrival.
   *
   * Once, because all three are answers only the bench can give and this screen never
   * infers them: a gate run that has just finished here has given the library back,
   * and *whether another may start now* is the bench's answer on the next visit
   * rather than something this screen may assume on its own. What it shows in the
   * meantime is the decision that gate run reached, which is what the operator is
   * looking at.
   */
  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const [bench, runs] = await Promise.all([benchGate(), gateRuns()])
        if (current) {
          setHeld({ bench, start: runs.start, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setHeld({ bench: null, start: null, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  const gateRunId = started?.gate_run_id ?? ''

  useEffect(() => {
    if (stage !== 'watching' || !gateRunId) {
      return
    }
    let current = true
    let timer: ReturnType<typeof setInterval> | undefined
    const tick = async () => {
      try {
        const now = await gateRunReading(gateRunId)
        if (!current) {
          return
        }
        setReading(now)
        // Stopped for good, so stop asking: a gate run that has been decided is one
        // whose screen has nothing left to learn from the bench.
        if (!stillGoing(now.status) && timer !== undefined) {
          clearInterval(timer)
        }
      } catch (unknown: unknown) {
        if (current) {
          setRefused(`${unknown}`)
        }
      }
    }
    timer = setInterval(() => void tick(), POLL_SECONDS * 1000)
    void tick()
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [gateRunId, stage])

  const control: StartControl | null =
    held.start === null ? null : startControl(held.start)

  const begin = () => {
    setRefused('')
    setStep(0)
    setAttesting(nothingAttested())
    setStage('attesting')
  }

  const request = gateRunRequest(attesting)

  const start = async () => {
    // Asked again here rather than trusted from the disabled state: this is the one
    // line in this screen that can begin 830 calls and a write-back, and the guard
    // that decides it is the one that will not build a body from an incomplete
    // declaration.
    if (request.kind !== 'ready') {
      return
    }
    setBusy(true)
    const outcome = await startGateRun(request.body)
    setBusy(false)
    if (outcome.kind === 'started') {
      setStarted(outcome.gateRun)
      setConfirmed(false)
      setStage('estimate')
      return
    }
    setRefused(outcome.statement)
    setStage('idle')
  }

  const answer = async (body: ApprovalBody) => {
    setBusy(true)
    const outcome = await answerTheGateRunsInterrupt(gateRunId, body)
    setBusy(false)
    if (outcome.kind === 'answered') {
      setStarted(outcome.gateRun)
      setRefused('')
      setStage('watching')
      return
    }
    setRefused(outcome.statement)
  }

  const confirm = () => {
    const confirmation = gateConfirmation(
      started?.status ?? '',
      confirmed,
      attesting.identity,
    )
    if (confirmation.kind !== 'ready') {
      return
    }
    void answer(confirmation.body)
  }

  const blocks =
    held.bench === null
      ? []
      : gateScreen(held.bench, stage === 'idle' ? control : null)

  return (
    <main className="screen">
      <header>
        <p className="eyebrow">AgentAudit — the bench’s own certification</p>
        <h1>The gate: the rule, the last outcome, and running another</h1>
        <p className="steps">
          {WHAT_THIS_SCREEN_ANSWERS}{' '}
          <Link to={CONSOLE_PATH}>What this bench is</Link> says the rest.
        </p>
      </header>

      {refused ? (
        <section className="refusal" role="alert">
          <h2>That was not taken</h2>
          <p>{refused}</p>
          <p className="aside">
            Nothing about this is a gate run that half happened: a refusal at this
            point means nothing was sent and not one case record was written to.
          </p>
        </section>
      ) : null}

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
              is how a gate run is started at a terminal, not something this bench
              told us.
            </p>
          </div>
        </section>
      ) : held.bench === null ? (
        <section>
          <p className="aside">
            Reading the declared rule and this bench’s citation…
          </p>
        </section>
      ) : null}

      {stage === 'attesting' ? (
        <TheAttestation
          step={step}
          attesting={attesting}
          declare={(changed) => setAttesting({ ...attesting, ...changed })}
          back={() => {
            if (step === 0) {
              setStage('idle')
              return
            }
            setStep(step - 1)
          }}
          forward={() => {
            if (step + 1 < GATE_RUN_STATEMENTS.length) {
              setStep(step + 1)
              return
            }
            void start()
          }}
          missing={request.kind === 'blocked' ? request.missing : []}
          last={step + 1 === GATE_RUN_STATEMENTS.length}
          busy={busy}
        />
      ) : null}

      {stage === 'estimate' && started !== null ? (
        <TheEstimate
          view={gateInterruptView(started.estimate, started.library)}
          held={started.statement}
          confirmed={confirmed}
          setConfirmed={setConfirmed}
          confirm={confirm}
          decline={() => void answer(gateDecline(attesting.identity))}
          busy={busy}
        />
      ) : null}

      {stage === 'watching' && reading !== null ? (
        <TheGateRun reading={reading} />
      ) : null}

      {blocks.map((block) => (
        <Block block={block} begin={begin} key={block.kind} />
      ))}
    </main>
  )
}

/** One block, in the order the reading gave it. Four kinds, four shapes. */
function Block({ block, begin }: { block: GateBlock; begin: () => void }) {
  switch (block.kind) {
    case 'rule':
      return <TheRule block={block} />
    case 'outcome':
      return <TheOutcome block={block} />
    case 'consequence':
      return <TheConsequence block={block} />
    case 'command':
      return <TheCommand block={block} begin={begin} />
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
 * What a gate run writes and what it spends, before anything that starts one.
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
 * The two ways to run one: the control this bench offers, and the command.
 *
 * The command is a `pre` with nothing around it, so selecting the line selects the
 * command and nothing else. The control is beside it rather than instead of it —
 * they are two entry points that leave two different traces — and where the bench
 * says a gate run may not start here, what stands in its place is the sentence
 * saying why rather than a disabled button with nothing said about it.
 */
function TheCommand({ block, begin }: { block: CommandBlock; begin: () => void }) {
  const start = block.start
  return (
    <section>
      <h2>{block.heading}</h2>

      {start === null ? null : start.available ? (
        <div className="citation">
          <h3>{start.label}</h3>
          <p>{start.statement}</p>
          <ul>
            {start.asks.map((asks) => (
              <li key={asks}>{asks}</li>
            ))}
          </ul>
          <dl className="at">
            <div>
              <dt>writes to</dt>
              <dd>
                <code>{start.library}</code>
              </dd>
            </div>
          </dl>
          <button type="button" className="primary" onClick={begin}>
            {start.label}
          </button>
        </div>
      ) : (
        <div className="citation uncited">
          <h3>{start.heading}</h3>
          <p>{start.statement}</p>
          <p className="aside">
            The bench’s own name for this: <code>{start.refusal}</code>.
          </p>
        </div>
      )}

      <h3>Or from a terminal</h3>
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

/**
 * The three statements, one at a time, in the record's own wording.
 *
 * One at a time and not three checkboxes in a column: each is recorded separately
 * and two of the three are consequences nobody would infer, so a screen that showed
 * them together would be a screen where they are read as one (ADR-0007). The walk's
 * footer is the register screen's, because it is the same walk.
 */
function TheAttestation({
  step,
  attesting,
  declare,
  back,
  forward,
  missing,
  last,
  busy,
}: {
  step: number
  attesting: Attesting
  declare: (changed: Partial<Attesting>) => void
  back: () => void
  forward: () => void
  missing: string[]
  last: boolean
  busy: boolean
}) {
  const statement = GATE_RUN_STATEMENTS[step]
  const made = attesting.attested[statement.field]
  return (
    <section>
      <h2>
        Statement {statement.step} of {statement.of}
      </h2>
      <p className="consequence">{statement.consequence}</p>
      <label className="declaration">
        <input
          type="checkbox"
          checked={made}
          onChange={(event) =>
            declare({
              attested: {
                ...attesting.attested,
                [statement.field]: event.target.checked,
              },
            })
          }
        />
        <span className="wording">{statement.wording}</span>
      </label>

      {step === 0 ? (
        <>
          <label>
            Who is attesting
            <input
              value={attesting.identity}
              onChange={(event) => declare({ identity: event.target.value })}
              placeholder="recorded against every one of the three statements"
            />
          </label>
          <label>
            What one call costs you, on your own provider
            <input
              value={attesting.price_per_call}
              onChange={(event) => declare({ price_per_call: event.target.value })}
              placeholder="leave empty for a gate run you have not priced"
            />
          </label>
        </>
      ) : null}

      {last && missing.length ? (
        <ul className="blocked">
          {missing.map((one) => (
            <li key={one}>{one}</li>
          ))}
        </ul>
      ) : null}

      <p className="aside">
        All three statements are required and each is recorded separately, so the
        record shows <em>what</em> was attested rather than that somebody agreed.
        Nothing has been sent: this screen has made no call and the case library has
        not been touched.
      </p>

      <footer className="walk">
        <button type="button" onClick={back} disabled={busy}>
          {step === 0 ? 'Not now' : 'Back'}
        </button>
        <button
          type="button"
          className="primary"
          onClick={forward}
          disabled={busy || !made || (last && missing.length > 0)}
        >
          {last
            ? busy
              ? 'Starting…'
              : 'See what it will cost'
            : 'Continue'}
        </button>
      </footer>
    </section>
  )
}

/**
 * The estimate, as two figures against two ceilings, before anything is sent.
 *
 * Two blocks rather than a table, because a table of two numeric columns has a
 * footer and a footer is where somebody puts a total. The response's own bounded
 * total is not on it at all: what an operator reads instead is each layer beside the
 * ceiling it is enforced against, which is the enforced limit (ADR-0007).
 */
function TheEstimate({
  view,
  held,
  confirmed,
  setConfirmed,
  confirm,
  decline,
  busy,
}: {
  view: GateInterruptView
  held: string
  confirmed: boolean
  setConfirmed: (given: boolean) => void
  confirm: () => void
  decline: () => void
  busy: boolean
}) {
  return (
    <section>
      <h2>What this gate run will cost</h2>
      <p>{held}</p>
      <dl className="figures">
        {view.figures.map((figure) => (
          <div className="figure" key={figure.layer}>
            <dt>{figure.label}</dt>
            <dd>
              <span className="calls">{figure.calls}</span>
              <span className="money">{figure.cost}</span>
              <span className="kind">{figure.kind}</span>
            </dd>
            <dd>{figure.basis}</dd>
            <dd>{figure.spends}</dd>
            <dd className="kind">
              enforced against this layer’s own ceiling of {figure.ceiling}
            </dd>
          </div>
        ))}
      </dl>
      <p className="aside">{view.unblended}</p>

      <dl className="at">
        <div>
          <dt>writes to</dt>
          <dd>
            <code>{view.library}</code>
          </dd>
        </div>
      </dl>
      <p className="consequence">{view.writesBack}</p>
      <p>{view.nothingSent}</p>

      <label className="declaration">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
        />
        <span className="wording">
          I have read both figures and I confirm this gate run
        </span>
      </label>

      <footer className="walk">
        <button type="button" onClick={decline} disabled={busy}>
          Decline — spend nothing
        </button>
        <button
          type="button"
          className="primary"
          onClick={confirm}
          disabled={busy || !confirmed}
        >
          {busy ? 'Confirming…' : 'Confirm and run the gate'}
        </button>
      </footer>
    </section>
  )
}

/**
 * A gate run in flight, then what it decided under the rule.
 *
 * While it goes: one block per layer, in that layer's own units, and no figure that
 * spans them. When it is decided: the rule, then the outcome, then each family's
 * figures — in that order because the sequence `decidedView` returns is in that
 * order, and an outcome read with no bar beside it is a verdict somebody trusted.
 */
function TheGateRun({ reading }: { reading: GateRunReading }) {
  const decided = decidedView(reading)
  return (
    <>
      <section>
        <h2>Where this gate run has got to</h2>
        <p>{reading.statement}</p>
        <div className="layers">
          {gateProgress(reading).map((layer) => (
            <Layer layer={layer} key={layer.layer} />
          ))}
        </div>
        <p className="aside">
          Two figures and no third: the two layers are held to two separate ceilings,
          so neither can borrow what the other did not spend, and a blended number
          would hide which half is spending the budget.
        </p>
      </section>

      {decided.map((block) => (
        <Decided block={block} key={block.kind} />
      ))}
    </>
  )
}

/** One layer's reading, in that layer's own units. */
function Layer({ layer }: { layer: LayerReading }) {
  return (
    <div className={`layer ${layer.layer}`}>
      <h3>{layer.title}</h3>
      {layer.at === null ? (
        <p>{layer.statement}</p>
      ) : (
        <dl className="at">
          {layer.units.map((unit, position) => (
            <div key={unit}>
              <dt>{unit}</dt>
              <dd>{layer.at?.[position]}</dd>
            </div>
          ))}
        </dl>
      )}
      <p>
        <span className="calls">{layer.callsSpent}</span> calls spent
      </p>
      <p className="aside">{layer.callsNote}</p>
      <p className="aside">{layer.found}</p>
    </div>
  )
}

/** One block of the decision, in the order `decidedView` gave it. */
function Decided({ block }: { block: DecidedBlock }) {
  switch (block.kind) {
    case 'rule':
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
        </section>
      )
    case 'decision':
      return (
        <section>
          <h2>{block.heading}</h2>
          <div className="citation">
            <h3>{block.outcome}</h3>
            <Facts facts={block.facts} />
            <p className="aside">{block.statement}</p>
          </div>
        </section>
      )
    case 'families':
      return (
        <section>
          <h2>{block.heading}</h2>
          <p>{block.statement}</p>
          <div className="families">
            {block.families.map((family) => (
              <FamilyFigure family={family} key={family.family} />
            ))}
          </div>
        </section>
      )
    case 'excluded':
      return (
        <section>
          <h2>{block.heading}</h2>
          <p>{block.statement}</p>
          <Facts facts={block.excluded} />
        </section>
      )
    case 'written':
      return (
        <section>
          <h2>{block.heading}</h2>
          <p className="consequence">{block.statement}</p>
          <Facts facts={block.facts} />
        </section>
      )
  }
}

/** Labelled facts, uncoloured, in the console's own idiom. */
function Facts({ facts }: { facts: Fact[] }) {
  return (
    <dl className="at">
      {facts.map((fact) => (
        <div key={fact.label}>
          <dt>{fact.label}</dt>
          <dd>{fact.value}</dd>
        </div>
      ))}
    </dl>
  )
}

/**
 * One family's three rates, its `D` and its verdict.
 *
 * The agents take the one hue's three ordered steps, which is identity and order and
 * never rank; the `D`, the ordering and the verdict are words and numbers with no
 * colour on them. Nothing here adds two families.
 */
function FamilyFigure({ family }: { family: FamilyReading }) {
  return (
    <div className="family">
      <h3>{family.family}</h3>
      <dl className="at">
        {family.rates.map((rate) => (
          <div key={rate.agent}>
            <dt className={`agent ${rate.accent}`}>{rate.agent}</dt>
            <dd>
              <span className="calls">{rate.rate}</span>
              <span className="kind">
                {rate.counts} {rate.interval}
              </span>
            </dd>
          </div>
        ))}
      </dl>
      <p>{family.discrimination}</p>
      <p className="kind">{family.intervals}</p>
      <p className="kind">{family.ordering}</p>
      <p>{family.verdict}</p>
    </div>
  )
}
