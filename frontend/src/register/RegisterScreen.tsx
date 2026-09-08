/**
 * The register screen: the authorisation guard as a walk rather than an error.
 *
 * ADR-0007 makes registration the whole of the bench's authorisation story — the
 * nonce is the proof of control because only somebody who can edit the target's
 * configuration can plant it — and the spec asks for that guard to be "a step I
 * complete rather than an error I hit". So the steps are one at a time and in the
 * order the consequences arrive: describe the endpoint, plant the value, make the
 * three statements, declare what the bench will be able to see, and only then
 * register.
 *
 * **The three statements are one screen, and each of them keeps its own
 * consequence.** They were three screens, on the argument that a stack of three
 * ticks under one Continue button is the arrangement that gets confirmed without
 * being read. What ADR-0007 requires is the consequences spelled out, and three
 * screens were one way to buy that rather than the only one: here the three are
 * numbered, ruled apart, and each tick sits under the paragraph that says what
 * ticking it costs. Nothing is folded into a summary and no statement borrows
 * another's prose — what went is the two Continue presses between them, which
 * proved nothing about whether the prose above them had been read.
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

import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import {
  benchSettings,
  issueNonce,
  notesToPlant,
  readRuleOfTwo,
  runStanding,
  startRun,
  type FieldRefusal,
  type Refusal,
  type NoteToPlant,
  type NonceIssued,
  type RuleOfTwoRead,
  type StartOutcome,
} from '../api/bench'
import {
  ATTESTATION_STATEMENTS,
  A_DECLARATION_THE_BENCH_CANNOT_VERIFY,
  NOTHING_HERE_HOLDS_THIS_STEP,
  NOT_MEASURABLE_WITHOUT_TOOL_CALLS,
  NOT_STATED,
  RULE_OF_TWO_DECLARATIONS,
  THE_AGENTS_RULE_OF_TWO,
  TOOL_TRACE_FAMILIES,
  WALK_STEPS,
  canLeave,
  echoRefusal,
  nothingDeclared,
  registrationRequest,
  unmetConditions,
  type Declarations,
  type Step,
} from './declarations'
import { rememberTheFigures, rememberWhoAttested } from '../run/interrupt'
import { useArrivalFocus, useScreenTitle } from '../console/announce'
import { REGISTER_A_TARGET } from '../console/rail'
import { Blocked, STILL_UNDECLARED } from '../blocked'

/*
 * The steps and the rule that decides when one may be left are `WALK_STEPS` and
 * `unmetConditions` in `declarations.ts`, beside the guard that refuses the
 * registration in the same sentences. What is here is what each step is called and
 * what it draws.
 */

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
  tools: 'What the bench will see',
}

/*
 * Two steps fewer, and one of them was a page and not a declaration.
 *
 * **The review step is gone.** It restated what the four screens before it had just
 * been told and offered a button. What it was standing in front of is not the spend:
 * registration records the attestation and plans the run, and the halt in front of the
 * estimate is on the next screen and is where nothing has been sent yet (ADR-0007).
 * The submit moved onto the last step of the walk.
 *
 * **The three attestations are no longer their own page**, and they are still asked.
 * They sit at the foot of the endpoint step, where the URL they are about is: the page
 * is gone, the walk is two screens shorter, and nothing is asserted on an operator's
 * behalf. The alternative — a console that sent three statements nobody made — is the
 * one thing ADR-0007 is written to prevent, and the honest version of removing the
 * *record* is a change to what every artefact this bench signs asserts rather than a
 * change to a walk.
 */

const PLANT_STEP = WALK_STEPS.indexOf('plant')

/** Nothing refused, which is what this screen holds until the bench says otherwise. */
const NOTHING_REFUSED: Refusal = { statement: '', fields: [] }

/**
 * A refusal that named no field, which is every refusal that is not the API's own
 * validation: a bench that could not be reached, a run whose standing could not be
 * read, a nonce this bench never issued.
 */
function said(statement: string): Refusal {
  return { statement, fields: [] }
}

/**
 * The refusal left standing once the operator has edited one of the fields it names.
 *
 * ADR-0077: the edit retires the mark, not the value — nothing here re-validates, and
 * a field whose posted value is no longer in the box is a field this screen has no
 * standing to keep `aria-invalid` on. Per field, because a `422` naming three is three
 * statements, and the two the operator has not answered yet cost a spent nonce to see
 * again. The last one out takes the sentence with it: *registration did not complete*
 * is true of a post whose refusals have all been answered.
 *
 * Returns the refusal it was given where nothing matched — a keystroke in a field
 * nothing was refused about is not a state change, and the memo sites below are not
 * invalidated by one. Which is also what happens to the five names in `FIELDS` no
 * control on this walk carries an `id` for: an entry no edit can match holds the
 * sentence until the next nonce is issued, and ADR-0077 says why that is the reading
 * rather than a stuck screen.
 */
function retire(refusal: Refusal, field: string): Refusal {
  const fields = refusal.fields.filter((one) => one.field !== field)
  if (fields.length === refusal.fields.length) {
    return refusal
  }
  return fields.length === 0 ? NOTHING_REFUSED : { ...refusal, fields }
}

/**
 * Every input on this walk, named by the path the API would refuse it at.
 *
 * ADR-0076: the `id` of an input is the `loc` path a `422` carries for it, joined
 * with dots and shortened nowhere — so `FIELDS.url` below is both the DOM name and
 * the wire name, and a refusal reaching this screen finds its input by the string
 * it arrived with. Listed in one place because these strings are a contract with
 * `backend/api/app.py`'s models: a field renamed there is renamed here, and a
 * refusal about a name nothing draws is drawn over the form instead of lost.
 *
 * **The last eight are declarations rather than fields, and they are listed anyway.**
 * A tick and a set of radios carry no `id` a message could be hung under, but the
 * API can refuse any of them, and `stepShowing` below has to know which step to send
 * the operator to. Listing them is what keeps that routing matching *these* strings
 * exactly rather than a prefix of them.
 */
const FIELDS = {
  name: 'body.target.name',
  url: 'body.target.url',
  auth_token: 'body.target.auth_token',
  agent_type: 'body.target.agent_type',
  sends: 'body.target.sends',
  declared_tools: 'body.target.declared_tools',
  identity: 'body.attestation.identity',
  price_per_call: 'body.cost.price_per_call',
  currency: 'body.cost.currency',
  exposes_tool_calls: 'body.target.exposes_tool_calls',
  note_planted: 'body.note_planted',
  nonce: 'body.nonce',
  nonce_planted: 'body.nonce_planted',
  echo_waived: 'body.echo_waived',
  processes_untrusted_input: 'body.target.processes_untrusted_input',
  reaches_private_data: 'body.target.reaches_private_data',
  changes_state_or_communicates: 'body.target.changes_state_or_communicates',
  under_human_supervision: 'body.target.under_human_supervision',
} as const

/**
 * Which step draws which field, for the walk to be sent back to it.
 *
 * Beside `FIELDS` and `STEP_TITLES` rather than inside `stepShowing` below, for the
 * reason they are up here: it is a table of names and not a computation, one row per
 * step, and a `Record<Step, …>` will not compile the day a fourth step is added
 * without saying where its fields are.
 *
 * `target` is empty and is the default — every field this table does not name is on
 * it, and listing them would be a second copy of `FIELDS` to keep in step with the
 * first.
 */
const STEP_DRAWING: Record<Step, readonly string[]> = {
  tools: [
    FIELDS.declared_tools,
    FIELDS.exposes_tool_calls,
    // The Rule of Two fieldset, at the foot of the same step. It holds nothing on
    // the walk, and the API can still refuse one of the four — so the walk goes back
    // to *this* step for one, which is the whole of what this table is for. Like the
    // tick and the tool radios above, a radio carries no `id` for the sentence to be
    // hung under; the refusal shows over the form, where it already was.
    FIELDS.processes_untrusted_input,
    FIELDS.reaches_private_data,
    FIELDS.changes_state_or_communicates,
    FIELDS.under_human_supervision,
  ],
  plant: [FIELDS.nonce, FIELDS.nonce_planted, FIELDS.echo_waived],
  target: [],
}

/**
 * The step that draws a refused field, so the walk can go back to it.
 *
 * A message bound to an input two steps back is a message nobody reads: this walk
 * is one step at a time, so a `422` naming a field lands on a screen the operator
 * is not on unless the walk returns to it. The default is the endpoint step because
 * that is where every field the table above does not name is drawn, and a name the
 * API grows that this file has not met still sends the operator to the start of the
 * walk with the bench's own sentence over it rather than nowhere.
 *
 * **Every name is matched whole**, which is ADR-0076's *nothing translates* read one
 * step on: a `startsWith('body.nonce')` here would silently claim the next field the
 * API names under that prefix, and claim it for the step this walk happens to draw
 * the nonce on today.
 */
function stepShowing(field: string): Step {
  return WALK_STEPS.find((step) => STEP_DRAWING[step].includes(field)) ?? 'target'
}

/** The id of the sentence under a field, derived from the field's own name. */
function saidAt(field: string): string {
  return `${field}.refused`
}

/** What a control is given while the API is refusing it, and when it is not. */
interface Marks {
  id: string
  'aria-invalid'?: true
  'aria-describedby'?: string
}

/**
 * One field of this walk: its label, the control, and what the API said about it.
 *
 * **The mark and the message are one thing to add and not two.** `aria-invalid` is
 * the state and `aria-describedby` is the sentence, which is the pair a screen reader
 * announces on reaching the field — the whole of what #120 asked for, since a
 * page-level block leaves the reader to map a `loc` path onto a form by hand. They
 * used to be two independent edits at every field, ten controls over: an input that
 * got the attributes and no message would point `aria-describedby` at an id nothing
 * renders, which is a dangling reference a screen reader resolves to nothing and
 * which nothing in the types or the tests could catch. Here the id, the attributes
 * and the message are all derived from the one `field` string, in one place, and a
 * call site cannot be handed the first without the second.
 *
 * **The control is the caller's, drawn from the marks it is handed.** An input, a
 * select, a number box and a textarea are four different controls with four different
 * sets of attributes, and a component that took them all as props would be a second
 * copy of the DOM. So the child is a function of the marks: what to spread, and the
 * caller spreads it on whatever it draws.
 *
 * `aside` is the line some fields carry under the message — what a bearer token is
 * for, what a send is — taken as a prop rather than left to the child so that the
 * bench's own sentence stays directly under the control it is about.
 */
function Field({
  label,
  field,
  refusals,
  aside,
  children,
}: {
  label: ReactNode
  field: string
  refusals: readonly FieldRefusal[]
  aside?: ReactNode
  children: (marks: Marks) => ReactNode
}) {
  const refused = refusals.find((one) => one.field === field)
  return (
    <label>
      {label}
      {children(
        refused
          ? { id: field, 'aria-invalid': true, 'aria-describedby': saidAt(field) }
          : { id: field },
      )}
      {/* Nothing at all where nothing was refused: an empty block reserved against a
          message that has not arrived is a form that looks like it is holding
          something. */}
      {refused ? (
        <span className="field-refused" id={saidAt(field)}>
          {refused.msg}
        </span>
      ) : null}
      {aside}
    </label>
  )
}

/*
 * What a target that answers in text only costs, on the summary and not on the answer.
 *
 * Back under the *No* radio, and only there. It was on the review step, which is
 * gone with the rest of that page — and a declaration whose consequence is stated
 * nowhere is one an operator makes without knowing what it costs. It names the two
 * families rather than pointing at them, because there is nothing beside it for
 * *those families* to refer to.
 */
const TOOL_TRACE_NOT_MEASURABLE =
  `${TOOL_TRACE_FAMILIES.join(' and ')} will report not measurable, and the ` +
  'adaptive attacker loses the tool that reads a trace.'

export function RegisterScreen() {
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const [declarations, setDeclarations] = useState<Declarations>(nothingDeclared)
  const [step, setStep] = useState(0)
  const [issued, setIssued] = useState<NonceIssued | null>(null)
  /**
   * The refusal this screen is holding: the sentence, and the fields it named.
   *
   * **One state and not two.** A `422` that names a field still has a statement, and
   * a refusal about the registration as a whole names no field at all — so the two
   * are always set together. Held as two `useState`s they were not: a later refusal
   * that named nothing left the previous one's marks standing on inputs, and the
   * operator was shown a sentence about this registration beside `aria-invalid` about
   * the one before it. There is no setter here that can move one without the other.
   *
   * **It is no longer true that they are always cleared together, and ADR-0077 says
   * why.** A refusal only ever moves toward nothing: a new one replaces it whole, and
   * `retire` above narrows it a field at a time as the operator answers the marks,
   * until the empty one is `NOTHING_REFUSED` and the sentence goes with the last mark.
   * The state that invariant was written to forbid — this refusal's sentence beside
   * the previous one's marks — needs a *widening* move that is not a replacement, and
   * there is none.
   */
  const [refusal, setRefusal] = useState<Refusal>(NOTHING_REFUSED)
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

  /**
   * **Kept under the compiler: eighteen cache slots.** This one's stake is render
   * cost, not cadence — it feeds no dependency array. It is a prop, handed to all
   * seven step components below, and compiled those components key **eighteen**
   * cache slots on it. The state that makes it earn its place is the asymmetric one:
   * the compiler skips per *function*, so the parent can be skipped while the
   * children compile, and that is exactly the state this file was in until the
   * `finally` clause in `issue` came out. A `declare` rebuilt by a skipped parent
   * invalidates all eighteen on every keystroke in the form, with nothing on the
   * wire changed and nothing looking different.
   */
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
          said(
            missingEcho ??
              `run ${standing.run_id} is ${standing.status} and did not stop at ` +
                `registration, so there is nothing here to re-plant: ${standing.statement}`,
          ),
        )
        if (missingEcho) {
          setStep(PLANT_STEP)
        }
      })
      .catch((unknown: unknown) => {
        if (current) {
          setRefusal(said(`${unknown}`))
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
      setRefusal(NOTHING_REFUSED)
    } catch (unusable: unknown) {
      setRefusal(said(`${unusable}`))
    }
    // Cleared after the `try`, and deliberately not in a `finally`: the React
    // Compiler does not lower a `finally` clause and skips the whole enclosing
    // component when it meets one, which is this component — the one in this file
    // holding state, and the one whose memo site above is load-bearing.
    //
    // The two shapes are the same behaviour *here*, and the qualification is the
    // point: control reaches this line on both paths because neither arm returns
    // and neither rethrows, and the `catch` arm is a single state setter that cannot
    // throw. A `finally` would also survive a throwing `catch`; this does not. So
    // nothing may be added to either arm that leaves early or can throw — put it
    // here instead.
    //
    // Unguarded, and it has to be: `npm test` runs in node with no DOM by the
    // spec's own choice, so there is no seam from which to observe `busy` clearing
    // after a refusal, and buying jsdom to get one is what #18 forbids.
    setBusy(false)
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
      // And who attested it. The interrupt has no field asking again, and the bench
      // writes `confirmed by <name>` when the answer arrives.
      rememberWhoAttested(sessionStorage, outcome.run.run_id, declarations.identity)
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
    // A bench that never answered named no field and cannot have: there is no
    // response to have named one in. `said` is the refusal with the empty list,
    // and the walk resumes at the plant step like any refusal that named nothing.
    if (outcome.kind !== 'refused') {
      setRefusal(said(outcome.statement))
      setStep(PLANT_STEP)
      return
    }
    // Narrowed once, and read off the narrowed value from here down. The refused
    // arm *is* a `Refusal`, so the sentence and the fields reach the state as the
    // one value they were read out of the response as, rather than being taken
    // apart here and put back together in `setRefusal`. The `kind` tag rides along
    // into state and nothing reads it there — deliberately, because stripping it
    // would be the reassembly this is removing.
    setRefusal(outcome)
    // Where the API named a field, the walk goes to the step that draws it and puts
    // the keyboard on it, instead of to the plant step. Both are true of a refusal —
    // the nonce is spent either way and the sentence above says so — but a message
    // bound to an input the operator cannot see is the page-level block this
    // replaced. Where no field was named there is nothing to go to, and the plant
    // step is where the walk resumes.
    const named = outcome.fields[0]?.field
    if (named === undefined) {
      setStep(PLANT_STEP)
      return
    }
    setStep(WALK_STEPS.indexOf(stepShowing(named)))
    // After the step it is on has been drawn. The input does not exist until then,
    // and a focus call against a screen that has not rendered moves nothing.
    setFocusOn(named)
  }

  /**
   * The step, said in the tab strip and read out on arrival.
   *
   * **Above the `focusOn` effect below, and that is the whole of why it is here**
   * rather than beside `current`. A refusal that names a field walks back to the step
   * drawing it *and* puts the keyboard on the field, so on that one render both this
   * arrival and that effect want the keyboard — and the later of the two is the one
   * that keeps it. The field is the more specific answer: it is the thing the bench
   * refused, and the heading it is under is one Shift-Tab away.
   */
  const arriving = STEP_TITLES[WALK_STEPS[step]]
  useScreenTitle(REGISTER_A_TARGET, arriving)
  const heading = useArrivalFocus(arriving)

  /**
   * The field the keyboard is owed, once the step drawing it is on screen.
   *
   * A name rather than a boolean, so that a second refusal about a second field
   * moves the focus again — and cleared by the effect that spends it, so that
   * nothing steals the keyboard back on the next render.
   *
   * **Below the arrival above, and it stays below it.** Both want the keyboard on the
   * render a refusal walks the walk back on, and React runs effects in the order they
   * are declared, so the later one keeps it. That is this one, deliberately — the
   * field is what the bench refused (ADR-0079) — and `e2e/keyboard.spec.ts` fails if
   * the two are swapped.
   */
  const [focusOn, setFocusOn] = useState<string | null>(null)
  useEffect(() => {
    if (focusOn === null) {
      return
    }
    document.getElementById(focusOn)?.focus()
    setFocusOn(null)
  }, [focusOn, setFocusOn])

  const current = WALK_STEPS[step]
  const last = current === WALK_STEPS[WALK_STEPS.length - 1]
  /**
   * What is holding the primary button, in the words it will be refused in.
   *
   * The step's own conditions everywhere but the last step, where the button is the
   * registration and is held by the whole guard rather than by this step.
   */
  const held = last
    ? request.kind === 'blocked'
      ? request.missing
      : []
    : unmetConditions(current, declarations)
  return (
    <main className="screen">
      {/*
        The title, and nothing over or under it.

        The eyebrow said *AgentAudit — registration*: the app's name is in the rail on
        every screen and the rail's current row says which screen this is. The line
        under it counted the steps and said that nothing is sent by this screen — the
        count goes with it, and so does the claim, which was standing on every step
        including the one whose button sends. What is *actually* sent, and when,
        is the halt this walk ends at: three attestations and two figures, and no call
        to anybody's endpoint until an operator answers it.
      */}
      <header>
        <h1 ref={heading} tabIndex={-1}>
          {arriving}
        </h1>
      </header>

      {/* Assertive (ADR-0080): the operator pressed *Register the target* and the
          bench refused it. A refusal that names a field also takes the keyboard to
          that field (#120); one that names none moves nothing, and then this is the
          only thing that says the press was answered at all. */}
      {refusal.statement ? (
        <section className="refusal" role="alert">
          <h2>Registration did not complete</h2>
          <p>{refusal.statement}</p>
          <p className="aside">
            Nothing about this is final. Plant a value the bench issues now and
            register again — one nonce starts one run, so the refused one is spent.
          </p>
        </section>
      ) : null}

      {/*
        A form, so that Enter does what Enter does on a form.

        There was none, and a walk of four fields where the primary button is the
        only way forward is a walk a keyboard cannot finish without reaching for the
        pointer. The button below is the form's submit and the step decides what
        submitting means — the next step, or the registration — so implicit
        submission is the same press by the same rule, including the rule that a
        disabled primary submits nothing.
      */}
      <form
        /*
          Where a refused field stops being refused, and the only place it can happen.

          One handler for the whole walk rather than a callback threaded through four
          step components to ten `Field` call sites, and it is ADR-0076 paying for
          itself a second time: the `id` of an input *is* the `loc` path the API
          refuses it at, so a change event arriving here already carries the name of
          the field it changed in the vocabulary the refusal arrived in. Nothing
          translates, and an id no standing refusal names is a no-op (ADR-0077).
        */
        onChange={(event) => {
          const edited = event.target
          if (edited instanceof HTMLElement) {
            setRefusal((standing) => retire(standing, edited.id))
          }
        }}
        onSubmit={(event) => {
          // Always, and before anything else: a form that reached the browser's own
          // submit would reload the app and lose every declaration on it.
          event.preventDefault()
          if (last) {
            void register()
            return
          }
          if (canLeave(current, declarations)) {
            setStep(step + 1)
          }
        }}
      >
        {current === 'target' ? (
          <>
            <TargetStep
              declarations={declarations}
              declare={declare}
              kinds={kinds}
              notes={notes}
              refusals={refusal.fields}
              unpaired={unpaired}
            />
            {/* The three statements, at the foot of the screen that names the endpoint
                they are about rather than on a page of their own. */}
            <AttestationStep
              declarations={declarations}
              declare={declare}
              refusals={refusal.fields}
            />
          </>
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
        {current === 'tools' ? (
          <ToolVisibilityStep
            declarations={declarations}
            declare={declare}
            refusals={refusal.fields}
          />
        ) : null}

        {/*
          Why the button below is grey, immediately above the button — the list and
          the citation both out of `blocked.tsx`, which is where the arrangement and
          its reasons are written down, and which the gate walk draws too.

          On the last step the reasons are the registration guard's own, because that
          is what disables the button there: the walk may be complete step by step and
          still be missing a URL, and the operator is owed the field and not the step.
        */}
        <Blocked reasons={held} />

        <footer className="walk">
          <button
            type="button"
            onClick={() => setStep(step - 1)}
            disabled={step === 0}
          >
            Back
          </button>
          <button
            type="submit"
            className="primary"
            disabled={busy || held.length > 0}
            aria-describedby={held.length ? STILL_UNDECLARED : undefined}
          >
            {last
              ? busy
                ? 'Registering…'
                : 'Register the target'
              : 'Continue'}
          </button>
        </footer>
      </form>
    </main>
  )
}

interface StepProps {
  declarations: Declarations
  declare: (changed: Partial<Declarations>) => void
}

/** A step that draws fields the API can refuse, and what it refused about them. */
interface RefusableProps extends StepProps {
  refusals: readonly FieldRefusal[]
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
  refusals,
}: RefusableProps & { kinds: readonly string[] }) {
  if (kinds.length === 0) {
    return (
      <Field label="Agent type" field={FIELDS.agent_type} refusals={refusals}>
        {(marks) => (
          <input
            {...marks}
            value={declarations.agent_type}
            onChange={(event) => declare({ agent_type: event.target.value })}
            placeholder="what kind of agent this is"
          />
        )}
      </Field>
    )
  }
  return (
    <Field label="Agent type" field={FIELDS.agent_type} refusals={refusals}>
      {/* No empty row over the kinds. The list is the kinds, one of them is chosen
          from the moment it arrives, and there is no state in which this field is
          showing a word the declaration does not hold. */}
      {(marks) => (
        <select
          {...marks}
          value={declarations.agent_type}
          onChange={(event) => declare({ agent_type: event.target.value })}
        >
          {kinds.map((kind) => (
            <option value={kind} key={kind}>
              {kind}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}

function TargetStep({
  declarations,
  declare,
  kinds,
  notes,
  refusals,
  unpaired,
}: RefusableProps & {
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
      <Field label="Name" field={FIELDS.name} refusals={refusals}>
        {(marks) => (
          <input
            {...marks}
            value={declarations.name}
            onChange={(event) => declare({ name: event.target.value })}
            placeholder="the name the report will call this target"
          />
        )}
      </Field>
      <Field label="URL" field={FIELDS.url} refusals={refusals}>
        {(marks) => (
          <input
            {...marks}
            value={declarations.url}
            onChange={(event) => declare({ url: event.target.value })}
            placeholder="https://staging.example/agent"
          />
        )}
      </Field>
      <Field
        label="Bearer token"
        field={FIELDS.auth_token}
        refusals={refusals}
        aside={
          /*
            The one field on this step that said nothing about itself, which is the one
            field that is somebody's secret. What it is for is not guessable from its
            name: it is the header on every call the bench makes, and it is the header
            on every call to a reference agent too, because there is one code path
            (`contract.py`). Empty is a real answer — an endpoint that needs no
            credential is a normal endpoint on a laptop — and the bench sends the header
            either way rather than branching on it.
          */
          <span className="aside">
            Sent as <code>Authorization: Bearer …</code> on every call to this
            endpoint. Leave it empty if yours needs no credential.
          </span>
        }
      >
        {(marks) => (
          <input
            {...marks}
            type="password"
            value={declarations.auth_token}
            onChange={(event) => declare({ auth_token: event.target.value })}
            placeholder="the credential your endpoint expects, if it expects one"
          />
        )}
      </Field>
      <AgentType
        declarations={declarations}
        declare={declare}
        kinds={kinds}
        refusals={refusals}
      />
      <Field
        label="Sends per message"
        field={FIELDS.sends}
        refusals={refusals}
        aside={
          /* Without the rest: that the enforced ceiling is built from this figure
             rather than from a constant, and that a send is not an attempt. Both are
             true and both are enforced — `sends` is what the ceiling is computed from,
             and `CONTEXT.md` keeps the two words apart — and the estimate is where an
             operator meets the ceiling this number produced. */
          <span className="aside">
            How many times one message may go on the wire to this endpoint.
          </span>
        }
      >
        {(marks) => (
          <input
            {...marks}
            type="number"
            min={1}
            value={declarations.sends}
            onChange={(event) => declare({ sends: Number(event.target.value) })}
          />
        )}
      </Field>
      <Field label="Price per call" field={FIELDS.price_per_call} refusals={refusals}>
        {(marks) => (
          <input
            {...marks}
            value={declarations.price_per_call}
            onChange={(event) => declare({ price_per_call: event.target.value })}
            placeholder="leave empty for a run you have not priced"
          />
        )}
      </Field>
      <Field
        label="Currency"
        field={FIELDS.currency}
        refusals={refusals}
        aside={
          /* Without the reason. That an amount in a currency the bench chose is a
             figure the operator did not state is the argument for the field existing,
             and the field exists. */
          <span className="aside">Required when a price is declared.</span>
        }
      >
        {(marks) => (
          <input
            {...marks}
            value={declarations.currency}
            onChange={(event) => declare({ currency: event.target.value })}
          />
        )}
      </Field>
      {/*
        The family, named over the box.
        Every other field on this form says what it is in two or three words and then
        explains itself; this one opened on a sentence with the family's name in the
        middle of its second clause. An operator scanning the form for what the run
        will do to their agent met a paragraph before they met a subject.
      */}
      <h3 className="field-name">Indirect prompt injection</h3>
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
      {/* *The nonce* rather than *this same value*: the lines that introduced the
          value are gone from this step, and a sentence whose subject was one of them
          now points at nothing. */}
      <p>
        The data-leakage family attacks the nonce, and a reply carrying it is a leak.
      </p>
      {issued ? (
        <>
          <p className="nonce">{issued.nonce}</p>
          <p>{issued.statement}</p>
          <label className="declaration">
            <input
              type="checkbox"
              checked={declarations.nonce_planted}
              onChange={(event) =>
                declare({
                  nonce_planted: event.target.checked,
                  // Planting it retracts the waiver. Leaving both standing would let
                  // a run go out declaring the value planted *and* unplantable,
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
        </>
      ) : (
        <button type="button" onClick={() => void issue()} disabled={busy}>
          {busy ? 'Issuing…' : 'Issue a nonce'}
        </button>
      )}
      {/* Outside the branch above, because the operator who most needs it is the one
          who has not issued a value and is not going to: an offer that only appears
          after the button is pressed is an offer to undo a step rather than to skip
          it. Hidden once the value is declared planted, when there is nothing left
          to waive. */}
      {declarations.nonce_planted ? null : (
        <WaiveTheProof declare={declare} waived={declarations.proof_waived} />
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

/**
 * The three statements, on one page, each under the consequence of making it.
 *
 * An ordered list rather than three sections, because that is what it is: three
 * statements in the order the record lists them, numbered so that somebody who has
 * ticked the first can see how many are left. The name is asked for above them
 * rather than beside one of them, since it is recorded against all three and a field
 * sitting under the first would read as belonging to the first.
 */
function AttestationStep({ declarations, declare, refusals }: RefusableProps) {
  return (
    <section>
      <Field label="Who is attesting" field={FIELDS.identity} refusals={refusals}>
        {(marks) => (
          <input
            {...marks}
            value={declarations.identity}
            onChange={(event) => declare({ identity: event.target.value })}
            placeholder="recorded against every one of the three statements"
          />
        )}
      </Field>
      <ol className="attestations">
        {ATTESTATION_STATEMENTS.map((statement) => (
          <li key={statement.field}>
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
          </li>
        ))}
      </ol>
    </section>
  )
}

function ToolVisibilityStep({ declarations, declare, refusals }: RefusableProps) {
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
          {/*
            One fact: the reply carries the calls. *In the order it made them* and
            *where a stop signal landed among them* both went — what the two families
            do with the trace is the paragraph over the question, and the answer to
            *does this target expose its tool calls* is yes or no and not a
            specification of the trace.
          */}
          <span>Yes — a reply carries the calls the agent made.</span>
        </label>
        <label className="declaration">
          <input
            type="radio"
            name="exposes_tool_calls"
            checked={declarations.exposes_tool_calls === false}
            onChange={() => declare({ exposes_tool_calls: false, declared_tools: [] })}
          />
          <span>No — it answers in text only.</span>
        </label>
        {declarations.exposes_tool_calls === false ? (
          // The consequence, back under the answer that carries it. It used to live on
          // the review step, which is gone: a declaration whose cost is stated nowhere
          // is a declaration an operator makes without knowing what it buys.
          <p className="aside">{TOOL_TRACE_NOT_MEASURABLE}</p>
        ) : null}
      </fieldset>
      {declarations.exposes_tool_calls === true ? (
        <Field
          label="The tools this target has, one per line"
          field={FIELDS.declared_tools}
          refusals={refusals}
          aside={<span className="aside">{A_DECLARATION_THE_BENCH_CANNOT_VERIFY}</span>}
        >
          {(marks) => (
            <textarea
              {...marks}
              rows={6}
              value={declarations.declared_tools.join('\n')}
              onChange={(event) =>
                declare({ declared_tools: event.target.value.split('\n') })
              }
              placeholder={'send_email\nlookup_order\nissue_refund'}
            />
          )}
        </Field>
      ) : null}
      {/* The four declarations, at the foot of the step that already asks what the
          bench will be able to *see*. These ask what the agent can *do*: both are
          declarations, neither is measured, and CONTEXT.md keeps declared capability
          apart from declared control for the reason they print in one section
          (ADR-0092, decision 1). */}
      <RuleOfTwoFieldset declarations={declarations} declare={declare} />
    </section>
  )
}

/**
 * What this agent can do, read against a published rule while it is being declared.
 *
 * **Four questions, three answers each, and no checkboxes** (ADR-0092, decision 2).
 * The local consequence is the third radio on every group: an answer the operator has
 * not given is a state this fieldset can be in and can be left in.
 *
 * **Nothing here holds the step**, and the fieldset says so out loud, because a form
 * that asks four questions and refuses nothing reads as four fields the operator
 * forgot. `unmetConditions` names none of them.
 *
 * **The reading is fetched and never derived** (`api/ruleOfTwo.ts` says why). What is
 * local to this call site is where it prints: under the fieldset, in the bench's own
 * words with `NOT_A_MEASUREMENT` in them, which on *this* screen does more work than
 * it does in the report — here the arm that reads most like a finding prints before a
 * single attempt exists to contrast it with.
 *
 * **Its own state, and not the walk's.** The reading is not a declaration: it is what
 * the bench makes of one, so it does not belong in the record a registration is posted
 * from. Held here, mounted with the step, and gone when the operator walks back — and
 * asked for again on the four answers they walk forward with.
 */
function RuleOfTwoFieldset({ declarations, declare }: StepProps) {
  const [read, setRead] = useState<RuleOfTwoRead | null>(null)
  /*
   * One request per answer, which is this fieldset's own granularity.
   *
   * There is no keystroke here to debounce — four radio groups, and one click is one
   * complete answer — and *on step exit* was the shape first reached for and means
   * never on this walk: `tools` is the last step, and what it exits into is the
   * registration, so a reading printed on exit would arrive after the walk it exists
   * to inform (ADR-0092, decision 6). The route is stateless, records nothing and
   * sends nothing to anybody, so four requests is the whole cost.
   *
   * The four values are named one by one rather than handed over as
   * `ruleOfTwoDeclared(declarations)`, and the reason is the dependency array: an object rebuilt on every render is a new dependency on every
   * render, which is a request per render. The literal is `RuleOfTwoDeclared`, so a
   * field renamed on the wire shape is a type error here and not a dropped answer.
   */
  useEffect(() => {
    let current = true
    void readRuleOfTwo({
      processes_untrusted_input: declarations.processes_untrusted_input,
      reaches_private_data: declarations.reaches_private_data,
      changes_state_or_communicates: declarations.changes_state_or_communicates,
      under_human_supervision: declarations.under_human_supervision,
    })
      .then((reading) => {
        if (current) {
          setRead(reading)
        }
      })
      .catch(() => {
        // Nothing to say and nothing to do. A reading the bench could not serve is
        // one an operator never sees, rather than an error over a step that holds
        // none of these four and registers perfectly well without the sentence.
      })
    return () => {
      current = false
    }
  }, [
    declarations.processes_untrusted_input,
    declarations.reaches_private_data,
    declarations.changes_state_or_communicates,
    declarations.under_human_supervision,
  ])
  return (
    <section className="rule-of-two">
      <h2>What this agent can do</h2>
      <p>{THE_AGENTS_RULE_OF_TWO}</p>
      <p className="aside">{NOTHING_HERE_HOLDS_THIS_STEP}</p>
      {RULE_OF_TWO_DECLARATIONS.map((asked) => (
        <fieldset key={asked.field}>
          <legend>{asked.question}</legend>
          {/* Three answers, in one order on all four questions: what is declared,
              what is declared absent, and the silence that is neither. */}
          {[
            { answer: true, wording: asked.held },
            { answer: false, wording: asked.absent },
            { answer: null, wording: NOT_STATED },
          ].map(({ answer, wording }) => (
            <label className="declaration" key={String(answer)}>
              <input
                type="radio"
                name={asked.field}
                checked={declarations[asked.field] === answer}
                onChange={() => declare({ [asked.field]: answer })}
              />
              <span>{wording}</span>
            </label>
          ))}
        </fieldset>
      ))}
      {/* Nothing until the bench has answered. A heading with no sentence under it
          would be a reading the operator is waiting for, and the one thing this block
          must not do is look like a result that is still being computed. */}
      {read ? (
        <p className="standing" role="status">
          {/* The name, and then the sentence. Both, because they are two different
              things to a reader: the sentence is what this target's shape means, and
              the name is the word `declared.rule_of_two.standing` carries in the
              signed payload — so the operator reads here the same word the recipient
              of the document will. Neither is edited and neither is chosen: they came
              off the wire together (ADR-0092, decision 4). */}
          <code>{read.standing}</code> — {read.stated}
        </p>
      ) : null}
    </section>
  )
}

