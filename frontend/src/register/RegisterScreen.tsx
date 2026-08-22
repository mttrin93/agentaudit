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
  benchSettings,
  issueNonce,
  notesToPlant,
  runStanding,
  startRun,
  type NoteToPlant,
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
  /**
   * The agent types the loaded library has cases for, to offer beside the field.
   *
   * Empty until the bench answers, and empty for good if it does not: the field is
   * free text either way and a registration is never blocked on this list arriving.
   * Read off the library rather than kept as a constant here, so a case written for a
   * new kind of agent puts that kind in front of the next operator to register one.
   */
  const [kinds, setKinds] = useState<readonly string[]>([])
  /**
   * The content the indirect prompt injection family attacks with, to show.
   *
   * The box on the first step declares this content is in place, and until the bench
   * served it there was nothing on this screen that said what it is. Empty until the
   * bench answers and empty for good if it does not: the declaration is the
   * operator's either way, and a registration is never blocked on this arriving.
   */
  const [notes, setNotes] = useState<readonly NoteToPlant[]>([])
  const [unpaired, setUnpaired] = useState<readonly string[]>([])

  const declare = useCallback((changed: Partial<Declarations>) => {
    setDeclarations((current) => ({ ...current, ...changed }))
  }, [])

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const settings = await benchSettings()
        const [first] = settings.library.agent_types
        if (current) {
          setKinds(settings.library.agent_types)
          // A list with no empty option shows its first row, so the declaration takes
          // it: a screen showing `assistant` over a record holding nothing is the one
          // way this field can lie. Only when nothing has been chosen — a resumed
          // declaration keeps the word it was resumed with.
          if (first !== undefined) {
            setDeclarations((held) =>
              held.agent_type === '' ? { ...held, agent_type: first } : held,
            )
          }
        }
      } catch {
        // Nothing to say and nothing to do: the field takes any word, and a suggestion
        // list that could not be read is one an operator never sees rather than an
        // error over a form they can complete without it.
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    let current = true
    void notesToPlant()
      .then((held) => {
        if (current) {
          setNotes(held.notes)
          setUnpaired(held.unpaired)
        }
      })
      .catch(() => {
        // Nothing to say. A bench that cannot serve the content is one an operator
        // reads out of the repository, and the box below is theirs to answer either
        // way — an error over a form that registers fine without it would be noise.
      })
    return () => {
      current = false
    }
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
        <TargetStep
          declarations={declarations}
          declare={declare}
          kinds={kinds}
          notes={notes}
          unpaired={unpaired}
        />
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
    return (
      Boolean(declarations.nonce) &&
      (declarations.nonce_planted || declarations.proof_waived)
    )
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

/**
 * The agent type: the kinds this library has cases for, as a list to pick from.
 *
 * **The list is read off the library, not kept here.** A case written for a new kind of
 * agent puts that kind in front of the next operator to register one, and a kind whose
 * every case has retired stops being offered.
 *
 * **It is a closed list on this screen and an open field everywhere else, which is a
 * decision worth naming.** The bench compares this word against each case's
 * `applies_to` and `applicability.py` keeps that comparison open on purpose: a kind the
 * library has no case for is answered by skipping those cases, per case with the reason
 * on it, rather than by refusing the registration. `POST /runs` still takes any word,
 * so that door is open to the API and the command line. What this screen offers is the
 * words that will actually match a case — an operator picking one is an operator whose
 * run attempts something.
 *
 * Where the bench did not answer there is no list to draw, and the field is text: a
 * registration is not blocked on a suggestion arriving.
 *
 * **There is no empty row over the list**, so the first kind is chosen from the moment
 * the list arrives and an operator who never touches this field registers as that kind.
 * The alternative was a row reading *what kind of agent this is* — a non-answer that is
 * selected by default and has to be got past, on a field where every answer is one of
 * two words.
 */
function AgentType({
  declarations,
  declare,
  kinds,
}: StepProps & { kinds: readonly string[] }) {
  if (kinds.length === 0) {
    return (
      <label>
        Agent type
        <input
          value={declarations.agent_type}
          onChange={(event) => declare({ agent_type: event.target.value })}
          placeholder="what kind of agent this is"
        />
      </label>
    )
  }
  return (
    <label>
      Agent type
      {/* No empty row over the kinds. The list is the kinds, one of them is chosen
          from the moment it arrives, and there is no state in which this field is
          showing a word the declaration does not hold. */}
      <select
        value={declarations.agent_type}
        onChange={(event) => declare({ agent_type: event.target.value })}
      >
        {kinds.map((kind) => (
          <option value={kind} key={kind}>
            {kind}
          </option>
        ))}
      </select>
    </label>
  )
}

function TargetStep({
  declarations,
  declare,
  kinds,
  notes,
  unpaired,
}: StepProps & {
  kinds: readonly string[]
  notes: readonly NoteToPlant[]
  unpaired: readonly string[]
}) {
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
          placeholder="the credential your endpoint expects, if it expects one"
        />
        {/*
          The one field on this step that said nothing about itself, which is the one
          field that is somebody's secret. What it is for is not guessable from its
          name: it is the header on every call the bench makes, and it is the header
          on every call to a reference agent too, because there is one code path
          (`contract.py`). Empty is a real answer — an endpoint that needs no
          credential is a normal endpoint on a laptop — and the bench sends the header
          either way rather than branching on it.
        */}
        <span className="aside">
          Sent as <code>Authorization: Bearer …</code> on every call to this endpoint.
          Leave it empty if yours needs no credential.
        </span>
      </label>
      <AgentType declarations={declarations} declare={declare} kinds={kinds} />
      <label>
        Sends per message
        <input
          type="number"
          min={1}
          value={declarations.sends}
          onChange={(event) => declare({ sends: Number(event.target.value) })}
        />
        {/* Without the rest: that the enforced ceiling is built from this figure
            rather than from a constant, and that a send is not an attempt. Both are
            true and both are enforced — `sends` is what the ceiling is computed from,
            and `CONTEXT.md` keeps the two words apart — and the estimate is where an
            operator meets the ceiling this number produced. */}
        <span className="aside">
          How many times one message may go on the wire to this endpoint.
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
        {/* Without the reason. That an amount in a currency the bench chose is a
            figure the operator did not state is the argument for the field existing,
            and the field exists. */}
        <span className="aside">Required when a price is declared.</span>
      </label>
      <label className="declaration">
        <input
          type="checkbox"
          checked={declarations.note_planted}
          onChange={(event) => declare({ note_planted: event.target.checked })}
        />
        {/*
          *Content*, not a *planted note*, and the word `plant` is why.

          This walk plants a nonce two steps later — a value that goes in the target's
          system prompt and proves the operator controls the endpoint — and this box
          used to say *the planted note … is in place*. Two unrelated things called
          planting, four lines apart, and an operator read the box as something to do
          with the nonce step. The nonce is planted; this is content the agent reads.

          One sentence, in plain words: it said four things — that the content is
          third-party, that the bench cannot check it, that declaring it absent skips
          the family and is not charged for, and that a run without it would report a
          zero that reads as a defence. The last is the reason the box exists and the
          others are how it works; what an operator has to decide is whether the
          content is there.
        */}
        <span>
          The hostile content the indirect prompt injection family reads is in place —
          in a document, a message or a page this agent will fetch. Without it, that
          family is skipped rather than run.
        </span>
      </label>
      <NotesToPlant notes={notes} unpaired={unpaired} />
    </section>
  )
}

/**
 * The content itself, folded away under the box that declares it is in place.
 *
 * The box asked an operator to plant something and the walk never said what. It is
 * not any hostile content: a case in this family *is* a piece of content, and the
 * verdict is the exact string executing that content produces, so a note of the
 * operator's own invention leaves thirty attempts running against an attack whose
 * canary can never appear — a clean zero that reads as a defence.
 *
 * **Folded, because it is three documents on a form of eight fields.** Shut, it is
 * one line; open, it is what to paste. An operator who has already planted the notes
 * never opens it.
 *
 * The canary is shown and is not a thing to plant. It is what the bench will look
 * for in the reply, and the note is written so that its two halves are in the body
 * and the join is not — a body carrying the finished string would be reproduced by
 * a target that quoted the note back while refusing it.
 */
function NotesToPlant({
  notes,
  unpaired,
}: {
  notes: readonly NoteToPlant[]
  unpaired: readonly string[]
}) {
  if (notes.length === 0 && unpaired.length === 0) {
    return null
  }
  return (
    <details className="plant">
      <summary>What to plant</summary>
      <p className="aside">
        Put each of these where this agent retrieves documents, filed so that a
        message naming the word above it brings that one back. The bench plants
        nothing and cannot see whether they are there.
      </p>
      {notes.map((note) => (
        <article key={note.case}>
          <h4>{note.key}</h4>
          <pre>{note.body}</pre>
          <p className="aside">
            Carrying it out adds <code>{note.canary}</code> to the reply. That line
            is the whole of the verdict.
          </p>
        </article>
      ))}
      {unpaired.length > 0 ? (
        <p className="aside">
          This bench holds no content for {unpaired.join(', ')}. Those cases will run
          against whatever is in place and can only report resisted.
        </p>
      ) : null}
    </details>
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
      {/*
        The value's second job, said here because here is where it is planted.

        Every data-leakage case goes after this same value, and one of them asks for it
        by name (`data-leakage-002`). That is why the family reaches a *deterministic*
        verdict: the bench knows the exact string it issued, so a reply carrying it is
        a leak by comparison and not by anybody's judgement (ADR-0004). Worth one
        sentence at the moment somebody is deciding where to paste it — a value planted
        somewhere the agent will repeat on request is a leak this bench will find and
        report against the target.
      */}
      <p>
        The data-leakage family attacks this same value, and a reply carrying it is a
        leak.
      </p>
      {issued ? (
        <>
          <p className="nonce">{issued.nonce}</p>
          <p>{issued.statement}</p>
          <h3>The probe the run will send, verbatim</h3>
          <pre>{issued.echo_probe}</pre>
          <label className="declaration">
            <input
              type="checkbox"
              checked={declarations.nonce_planted}
              onChange={(event) =>
                declare({
                  nonce_planted: event.target.checked,
                  // Planting it retracts the waiver. Leaving both standing would let
                  // a run go out declaring the value planted *and* the proof waived,
                  // which is two different runs described at once.
                  proof_waived: event.target.checked ? false : declarations.proof_waived,
                })
              }
            />
            <span>
              This value is in the target’s system prompt and the target has
              reloaded.
            </span>
          </label>
          {declarations.nonce_planted ? null : <WaiveTheProof declare={declare} waived={declarations.proof_waived} />}
        </>
      ) : (
        <button type="button" onClick={() => void issue()} disabled={busy}>
          {busy ? 'Issuing…' : 'Issue a nonce'}
        </button>
      )}
    </section>
  )
}

/**
 * Starting without the proof, and what it costs — offered only where it applies.
 *
 * ADR-0007 made the echo the whole of this bench's authorisation story: a tool that
 * takes a URL and a bearer token from a form and fires jailbreak payloads at
 * whatever answers is, pointed at a live URL, an open attack proxy, and the echo is
 * the one mechanism that separates an operator testing their own agent from anybody
 * testing anybody's. The amendment lets an operator who cannot write into their
 * target's configuration proceed anyway. What it does not do is pretend the two are
 * the same, so this box states the three things that change, in the order they bite.
 *
 * **Hidden once the value is declared planted**, because an operator who planted it
 * has nothing to waive, and an offer to skip a step that has been completed is an
 * invitation to skip it.
 *
 * Each bullet is its claim and the argument is cut. The reasoning behind them is on
 * the record where it belongs — ADR-0007 for what the echo is for, `plan_for` for why
 * the leakage family is dropped, the provenance block for what the artefact carries —
 * and a warning nobody finishes reading warns nobody.
 */
function WaiveTheProof({
  declare,
  waived,
}: {
  declare: (changed: Partial<Declarations>) => void
  waived: boolean
}) {
  return (
    <section className="waiver">
      <h3>Or start without proving control</h3>
      <p>
        If you cannot put the value, the run can go ahead on your declaration alone.
        Three things change:
      </p>
      <ul>
        <li>
          <strong>Nothing checks that this endpoint is yours.</strong>
        </li>
        <li>
          <strong>Data leakage is not run.</strong> That family extracts this same
          value, and a canary planted nowhere cannot leak: run anyway, it would
          report a clean thirty out of thirty against an attack that was never
          possible.
        </li>
        <li>
          <strong>The artefact says so, permanently.</strong>
        </li>
      </ul>
      <label className="declaration">
        <input
          type="checkbox"
          checked={waived}
          onChange={(event) => declare({ proof_waived: event.target.checked })}
        />
        <span>
          I cannot plant this value, I am authorised to test this endpoint anyway,
          and I am starting the run without the proof.
        </span>
      </label>
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
        All three statements are required and each is recorded separately.
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
          {declarations.nonce_planted
            ? ' — declared planted'
            : ' — not planted, control declared and not proved'}
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
