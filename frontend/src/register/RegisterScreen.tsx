/**
 * The register screen: the authorisation guard as a walk rather than an error.
 *
 * ADR-0007 makes registration the whole of the bench's authorisation story — the
 * nonce is the proof of control because only somebody who can edit the target's
 * configuration can plant it — and the spec asks for that guard to be "a step I
 * complete rather than an error I hit". So the steps are one at a time and in the
 * order the consequences arrive: describe the endpoint, plant the value, make the
 * three statements one by one, declare what the bench will be able to see, and
 * only then register.
 *
 * **The three statements are three screens, not three checkboxes in a row.** Two
 * of the three are consequences a user would never infer, and ADR-0007 requires
 * them spelled out; a stack of three ticks with one Continue button underneath is
 * the arrangement that gets confirmed without being read.
 *
 * **The nonce echo is checked after this screen, and the screen says so.** The
 * echo probe is a call on the operator's endpoint, and the halt in front of the
 * spend comes first, so a target that does not echo is discovered by the run's
 * own first call — after the interrupt is answered on the run screen. What this
 * screen owns is the recovery: it is reachable as `/register?refused=<run id>`,
 * where it reads the run's status, shows the bench's own sentence about the
 * missing echo, and puts the operator back at the plant step with a value it has
 * just issued.
 *
 * **Every refusal costs the nonce.** `BenchRuns.start` spends the value before it
 * does anything else, so there is no path here that retries the same body: a
 * refusal clears the nonce and walks back to the plant step, which is the only
 * honest retry when one nonce starts one run and no more.
 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import {
  issueNonce,
  runStanding,
  startRun,
  type NonceIssued,
  type StartOutcome,
} from '../api/bench'
import {
  ATTESTATION_STATEMENTS,
  A_DECLARATION_THE_BENCH_CANNOT_VERIFY,
  NOT_MEASURABLE_WITHOUT_TOOL_CALLS,
  declaredTools,
  echoRefusal,
  nothingDeclared,
  registrationRequest,
  type Declarations,
} from './declarations'
import { rememberTheFigures } from '../run/interrupt'

/**
 * The steps, in order, one per screen.
 *
 * The three attestation steps are listed individually rather than generated from
 * a count, so that the flow's shape is readable here and an attestation cannot be
 * added to the record without a step appearing for it.
 */
const STEPS = [
  'target',
  'plant',
  'attest-0',
  'attest-1',
  'attest-2',
  'tools',
  'register',
] as const

type Step = (typeof STEPS)[number]

/**
 * One short title a step, and the title is the whole of the header.
 *
 * They were sentences — *The endpoint, and what it costs to call it*, *What the bench
 * will be able to see* — under an eyebrow naming the app and a screen, over a line
 * counting the steps. Three lines of chrome above a form of four fields. The name of
 * the step is the one thing a heading has to say; what the step is *for* is the prose
 * inside it, which every step already carries.
 */
const STEP_TITLES: Record<Step, string> = {
  target: 'The endpoint',
  plant: 'Plant the nonce',
  'attest-0': 'Attestation 1 of 3',
  'attest-1': 'Attestation 2 of 3',
  'attest-2': 'Attestation 3 of 3',
  tools: 'What the bench will see',
  register: 'Register',
}

const PLANT_STEP = STEPS.indexOf('plant')

const TOOL_TRACE_NOT_MEASURABLE =
  'Both of those families will report not measurable, and the adaptive attacker ' +
  'loses the tool that reads a trace.'

export function RegisterScreen() {
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const [declarations, setDeclarations] = useState<Declarations>(nothingDeclared)
  const [step, setStep] = useState(0)
  const [issued, setIssued] = useState<NonceIssued | null>(null)
  const [refusal, setRefusal] = useState('')
  const [busy, setBusy] = useState(false)

  const declare = useCallback((changed: Partial<Declarations>) => {
    setDeclarations((current) => ({ ...current, ...changed }))
  }, [])

  /**
   * Sent back here by a run whose target never echoed the nonce.
   *
   * The status is read from the bench rather than trusted from the link: a run id
   * in a URL says nothing about what happened to the run, and a screen that
   * announced a missing echo on the strength of a query parameter would announce
   * it for a run that failed on the wire.
   */
  const refused = search.get('refused')
  useEffect(() => {
    if (!refused) {
      return
    }
    let current = true
    void runStanding(refused)
      .then((standing) => {
        if (!current) {
          return
        }
        const missingEcho = echoRefusal(standing)
        setRefusal(
          missingEcho ??
            `run ${standing.run_id} is ${standing.status} and did not stop at ` +
              `registration, so there is nothing here to re-plant: ${standing.statement}`,
        )
        if (missingEcho) {
          setStep(PLANT_STEP)
        }
      })
      .catch((unknown: unknown) => {
        if (current) {
          setRefusal(`${unknown}`)
        }
      })
    return () => {
      current = false
    }
  }, [refused])

  const issue = async () => {
    setBusy(true)
    try {
      const nonce = await issueNonce()
      setIssued(nonce)
      declare({ nonce: nonce.nonce, nonce_planted: false })
      setRefusal('')
    } catch (unusable: unknown) {
      setRefusal(`${unusable}`)
    } finally {
      setBusy(false)
    }
  }

  const request = registrationRequest(declarations)

  const register = async () => {
    if (request.kind !== 'ready') {
      return
    }
    setBusy(true)
    const outcome: StartOutcome = await startRun(request.body)
    setBusy(false)
    if (outcome.kind === 'registered') {
      // The one thing the run screen cannot read from the bench: `GET /runs/{id}`
      // reports progress and no figures, so the estimate the interrupt is holding
      // arrives with this response and nowhere else. Held under the run's own id,
      // for the screen that has to show it before anybody may confirm it.
      rememberTheFigures(sessionStorage, outcome.run.run_id, outcome.run.estimate)
      // A real navigation, and the run id is the whole of what the URL carries:
      // the run exists on the bench, holding its interrupt, and the run screen
      // reads its standing from there rather than from anything this screen chose
      // to hand over.
      void navigate(`/runs/${outcome.run.run_id}`)
      return
    }
    // Refused, and the nonce went with it. Back to the plant step with the
    // bench's own sentence, and nothing else the operator declared is lost.
    setIssued(null)
    declare({ nonce: '', nonce_planted: false })
    setRefusal(outcome.statement)
    setStep(PLANT_STEP)
  }

  const current = STEPS[step]
  return (
    <main className="screen">
      {/*
        The title, and nothing over or under it.

        The eyebrow said *AgentAudit — registration*: the app's name is in the rail on
        every screen and the rail's current row says which screen this is. The line
        under it counted the steps and said that nothing is sent by this screen — the
        count goes with it, and so does the claim, which was standing on all seven
        steps including the one whose button sends. What is *actually* sent, and when,
        is the halt this walk ends at: three attestations and two figures, and no call
        to anybody's endpoint until an operator answers it.
      */}
      <header>
        <h1>{STEP_TITLES[current]}</h1>
      </header>

      {refusal ? (
        <section className="refusal" role="alert">
          <h2>Registration did not complete</h2>
          <p>{refusal}</p>
          <p className="aside">
            Nothing about this is final. Plant a value the bench issues now and
            register again — one nonce starts one run, so the refused one is spent.
          </p>
        </section>
      ) : null}

      {current === 'target' ? (
        <TargetStep declarations={declarations} declare={declare} />
      ) : null}
      {current === 'plant' ? (
        <PlantStep
          declarations={declarations}
          declare={declare}
          issued={issued}
          issue={issue}
          busy={busy}
        />
      ) : null}
      {current.startsWith('attest-') ? (
        <AttestationStep
          index={Number(current.slice('attest-'.length))}
          declarations={declarations}
          declare={declare}
        />
      ) : null}
      {current === 'tools' ? (
        <ToolVisibilityStep declarations={declarations} declare={declare} />
      ) : null}
      {current === 'register' ? (
        <RegisterStep declarations={declarations} request={request} />
      ) : null}

      <footer className="walk">
        <button type="button" onClick={() => setStep(step - 1)} disabled={step === 0}>
          Back
        </button>
        {current === 'register' ? (
          <button
            type="button"
            className="primary"
            onClick={() => void register()}
            disabled={busy || request.kind !== 'ready'}
          >
            {busy ? 'Registering…' : 'Register the target'}
          </button>
        ) : (
          <button
            type="button"
            className="primary"
            onClick={() => setStep(step + 1)}
            disabled={!canLeave(current, declarations)}
          >
            Continue
          </button>
        )}
      </footer>
    </main>
  )
}

/**
 * Whether a step has been completed enough to leave.
 *
 * The attestation steps and the tool-visibility step hold the walk, because both
 * are declarations rather than form fields: a Continue button that stepped past an
 * unmade statement would make the statement optional in practice, whatever the
 * registration guard says about it later.
 */
function canLeave(step: Step, declarations: Declarations): boolean {
  if (step === 'plant') {
    return Boolean(declarations.nonce) && declarations.nonce_planted
  }
  if (step.startsWith('attest-')) {
    const statement = ATTESTATION_STATEMENTS[Number(step.slice('attest-'.length))]
    return (
      declarations.attested[statement.field] && Boolean(declarations.identity.trim())
    )
  }
  if (step === 'tools') {
    return (
      declarations.exposes_tool_calls === false ||
      (declarations.exposes_tool_calls === true &&
        declaredTools(declarations).length > 0)
    )
  }
  return true
}

interface StepProps {
  declarations: Declarations
  declare: (changed: Partial<Declarations>) => void
}

function TargetStep({ declarations, declare }: StepProps) {
  return (
    <section>
      {/*
        The line, without what an unpriced run reports.

        It went on: the price is yours to declare, and a run with none reports its cost
        as *not priced* rather than as zero, because an unknown cost and a free run are
        different facts. That distinction is real and it is kept where it is enforced —
        the estimate prints *not priced* on a run with no price, and the record carries
        no zero for one. It is not something an operator needs told before typing a URL.
      */}
      <p>The endpoint the bench will attack, and the price you pay per call on it.</p>
      <label>
        Name
        <input
          value={declarations.name}
          onChange={(event) => declare({ name: event.target.value })}
          placeholder="the name the report will call this target"
        />
      </label>
      <label>
        URL
        <input
          value={declarations.url}
          onChange={(event) => declare({ url: event.target.value })}
          placeholder="https://staging.example/agent"
        />
      </label>
      <label>
        Bearer token
        <input
          type="password"
          value={declarations.auth_token}
          onChange={(event) => declare({ auth_token: event.target.value })}
        />
      </label>
      <label>
        Agent type
        <input
          value={declarations.agent_type}
          onChange={(event) => declare({ agent_type: event.target.value })}
          placeholder="what kind of agent this is"
        />
      </label>
      <label>
        Sends per message
        <input
          type="number"
          min={1}
          value={declarations.sends}
          onChange={(event) => declare({ sends: Number(event.target.value) })}
        />
        <span className="aside">
          How many times one message may go on the wire to this endpoint. The
          enforced ceiling is built from it, so it is your declaration rather than
          a constant inside the bench — and it is not attempts.
        </span>
      </label>
      <label>
        Price per call
        <input
          value={declarations.price_per_call}
          onChange={(event) => declare({ price_per_call: event.target.value })}
          placeholder="leave empty for a run you have not priced"
        />
      </label>
      <label>
        Currency
        <input
          value={declarations.currency}
          onChange={(event) => declare({ currency: event.target.value })}
        />
        <span className="aside">
          Required when a price is declared. An amount in a currency the bench
          chose is a figure you did not state.
        </span>
      </label>
      <label className="declaration">
        <input
          type="checkbox"
          checked={declarations.note_planted}
          onChange={(event) => declare({ note_planted: event.target.checked })}
        />
        <span>
          A third-party note the indirect-prompt-injection family needs is in place.
          The bench does not serve that content and cannot check it. Declared
          absent, the family is not run and the estimate does not charge for it —
          run without the note it would report a clean zero that reads as a defence
          and is not one.
        </span>
      </label>
    </section>
  )
}

interface PlantProps extends StepProps {
  issued: NonceIssued | null
  issue: () => Promise<void>
  busy: boolean
}

function PlantStep({ declarations, declare, issued, issue, busy }: PlantProps) {
  return (
    <section>
      <p>
        The bench issues a value; you plant it in the target’s system prompt.{' '}
        <strong>
          Registration cannot complete until the target echoes it back.
        </strong>{' '}
        Only somebody who can edit that configuration can plant it, which is what
        makes the echo proof that you control the endpoint rather than a claim about
        it.
      </p>
      {issued ? (
        <>
          <p className="nonce">{issued.nonce}</p>
          <p>{issued.statement}</p>
          <h3>The probe the run will send, verbatim</h3>
          <pre>{issued.echo_probe}</pre>
          <p className="aside">
            The echo is checked by the run’s own first call, which happens after
            you answer the cost interrupt on the next screen — the probe is a call
            on your endpoint, and the halt comes before anything is spent. A target
            that does not answer it with this value is not attempted, and this
            screen is where you come back to.
          </p>
          <label className="declaration">
            <input
              type="checkbox"
              checked={declarations.nonce_planted}
              onChange={(event) => declare({ nonce_planted: event.target.checked })}
            />
            <span>
              This value is in the target’s system prompt and the target has
              reloaded.
            </span>
          </label>
        </>
      ) : (
        <button type="button" onClick={() => void issue()} disabled={busy}>
          {busy ? 'Issuing…' : 'Issue a nonce'}
        </button>
      )}
    </section>
  )
}

interface AttestationProps extends StepProps {
  index: number
}

function AttestationStep({ index, declarations, declare }: AttestationProps) {
  const statement = ATTESTATION_STATEMENTS[index]
  return (
    <section>
      <p className="consequence">{statement.consequence}</p>
      <label className="declaration">
        <input
          type="checkbox"
          checked={declarations.attested[statement.field]}
          onChange={(event) =>
            declare({
              attested: {
                ...declarations.attested,
                [statement.field]: event.target.checked,
              },
            })
          }
        />
        <span className="wording">{statement.wording}</span>
      </label>
      {index === 0 ? (
        <label>
          Who is attesting
          <input
            value={declarations.identity}
            onChange={(event) => declare({ identity: event.target.value })}
            placeholder="recorded against every one of the three statements"
          />
        </label>
      ) : null}
      <p className="aside">
        All three statements are required and each is recorded separately, so the
        record shows <em>what</em> was attested rather than that somebody agreed.
        It is the liability record and the Article 12 record in one artefact
        (ADR-0007).
      </p>
    </section>
  )
}

function ToolVisibilityStep({ declarations, declare }: StepProps) {
  return (
    <section>
      <p>{NOT_MEASURABLE_WITHOUT_TOOL_CALLS}</p>
      <fieldset>
        <legend>Does this target expose its tool calls?</legend>
        <label className="declaration">
          <input
            type="radio"
            name="exposes_tool_calls"
            checked={declarations.exposes_tool_calls === true}
            onChange={() => declare({ exposes_tool_calls: true })}
          />
          <span>
            Yes — a reply carries the calls the agent made, in the order it made
            them, and where a stop signal landed among them.
          </span>
        </label>
        <label className="declaration">
          <input
            type="radio"
            name="exposes_tool_calls"
            checked={declarations.exposes_tool_calls === false}
            onChange={() => declare({ exposes_tool_calls: false, declared_tools: [] })}
          />
          <span>
            No — it answers in text only. {TOOL_TRACE_NOT_MEASURABLE}
          </span>
        </label>
      </fieldset>
      {declarations.exposes_tool_calls === true ? (
        <label>
          The tools this target has, one per line
          <textarea
            rows={6}
            value={declarations.declared_tools.join('\n')}
            onChange={(event) =>
              declare({ declared_tools: event.target.value.split('\n') })
            }
            placeholder={'send_email\nlookup_order\nissue_refund'}
          />
          <span className="aside">{A_DECLARATION_THE_BENCH_CANNOT_VERIFY}</span>
        </label>
      ) : null}
    </section>
  )
}

interface RegisterProps {
  declarations: Declarations
  request: ReturnType<typeof registrationRequest>
}

function RegisterStep({ declarations, request }: RegisterProps) {
  return (
    <section>
      <p>
        Registering records the attestation against a hash of the endpoint, plans
        the run and halts it in front of its cost. Nothing reaches your endpoint
        until you answer that halt on the next screen.
      </p>
      <dl className="review">
        <dt>Target</dt>
        <dd>
          {declarations.name || '—'} at {declarations.url || '—'}
        </dd>
        <dt>Attested by</dt>
        <dd>{declarations.identity || '—'}</dd>
        <dt>Nonce</dt>
        <dd>
          {declarations.nonce || '—'}
          {declarations.nonce_planted ? ' — declared planted' : ' — not planted'}
        </dd>
        <dt>Tool calls</dt>
        <dd>
          {declarations.exposes_tool_calls === null
            ? 'not declared'
            : declarations.exposes_tool_calls
              ? `visible, ${declaredTools(declarations).length} tools declared`
              : `not visible — ${TOOL_TRACE_NOT_MEASURABLE}`}
        </dd>
        <dt>Price per call</dt>
        <dd>
          {declarations.price_per_call
            ? `${declarations.price_per_call} ${declarations.currency}`
            : 'not priced'}
        </dd>
      </dl>
      {request.kind === 'blocked' ? (
        <div className="blocked">
          <h3>Not yet, and this is what is missing</h3>
          <ul>
            {request.missing.map((missing) => (
              <li key={missing}>{missing}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
