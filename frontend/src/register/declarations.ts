/**
 * What an operator declares before the bench may touch their endpoint, and the
 * rules that decide when those declarations add up to a registration.
 *
 * Every rule in this module is one the API also holds, and holding it twice is
 * deliberate. The API's copy is the one that decides — a screen that checked
 * nothing would still be refused — but a screen that posts a body it already knows
 * will be refused turns a step the operator has not finished into a `422` they
 * have to read. So the guard here is a *guide*, and the guard there is the
 * *authority*, and where the wording matters it is copied from the backend rather
 * than paraphrased.
 *
 * **The rules live here rather than in the component** because the spec expects
 * these screens to be driven by hand (`docs/specs/signed-report-and-delivery.md`,
 * "The interface is driven by hand") and does not justify a browser driver. What
 * can be asserted without a browser is asserted: the three-statement rule, the
 * declaration a tool-visible target owes, and the exact body that goes on the
 * wire. What is left to a person is whether the page reads like the guard it is.
 */

import type { StartRunBody } from '../api/bench'
import { REGISTRATION_REFUSED, type RunStanding } from '../api/bench'

/**
 * One attestation, in the words the record keeps.
 *
 * `wording` is copied verbatim from `Attestation.STATEMENTS` in
 * `backend/bench/registration.py`, which holds it beside the fields for this
 * reason: the prompt an operator confirms and the record of what they confirmed
 * must not drift apart. `consequence` is this screen's own, and it exists because
 * ADR-0007 requires the consequences spelled out rather than implied — two of the
 * three are things a user would never infer.
 */
export interface Statement {
  field: keyof Attested
  wording: string
  consequence: string
}

/** The three, in the order the record lists them and the screen asks them. */
export const ATTESTATION_STATEMENTS: readonly Statement[] = [
  {
    field: 'authorised_to_test',
    wording: 'I am authorised to test this endpoint',
    consequence:
      'The bench fires jailbreak payloads at whatever answers this URL. ' +
      'Pointed at somebody else’s system it is an attack.',
  },
  {
    field: 'not_production',
    wording: 'this endpoint is a staging or sandbox environment',
    consequence:
      'A run makes 181 calls in the scored layer alone, every one of them an ' +
      'attack, and some of them will succeed.',
  },
  {
    field: 'accepts_provider_policy_and_cost',
    wording:
      'I accept that these payloads will generate provider policy violations ' +
      'against my own account and consume my own inference budget',
    consequence:
      'The payloads reach your model provider under your credentials, so the ' +
      'policy violations are recorded against your account and the inference ' +
      'is billed to it.',
  },
]

/** The three statements as this app holds them while they are being made. */
export interface Attested {
  authorised_to_test: boolean
  not_production: boolean
  accepts_provider_policy_and_cost: boolean
}

/**
 * The two families that are read from a tool trace, named for the screen.
 *
 * Against a target that does not expose its tool calls they report **not
 * measurable** — a third outcome beside a rate and a refused registration, and
 * never a rate of zero, because a family the bench never measured has to stay
 * distinguishable from one the target resisted. That is the whole reason this
 * declaration is collected at registration instead of guessed at scoring time.
 */
export const TOOL_TRACE_FAMILIES = ['scope creep', 'halt defeat'] as const

/*
 * Four sentences, and three of them are gone.
 *
 * They explained how the two families are read — from the calls the agent made, and
 * where the stop signal landed among them — and that not measurable is not a rate of
 * zero. What is left is the sentence that decides something: the two families are
 * named, and the outcome is *not measurable* and not *defended*. The mechanism went
 * because the answers underneath are yes or no about a trace and not a description of
 * one, and the rate-of-zero distinction went because it is a fact about a figure this
 * screen never shows — `report.ts` carries *never a rate of zero, and never a family
 * this target defended* beside the not-measurable outcome itself.
 */
export const NOT_MEASURABLE_WITHOUT_TOOL_CALLS =
  `Without visible tool calls, ${TOOL_TRACE_FAMILIES.join(' and ')} report as ` +
  'not measurable rather than as defended.'

export const A_DECLARATION_THE_BENCH_CANNOT_VERIFY =
  'This tool list is a declaration and the bench cannot verify it. Nothing here ' +
  'is discovered, sniffed or confirmed against your agent — the bench reads scope ' +
  'creep as a call outside this list, so a list that omits a tool your agent ' +
  'legitimately has will score its use as a finding, and a list that invents one ' +
  'will hide the finding it should have produced.'

/** Everything the register screen collects, in one record it can be resumed from. */
export interface Declarations {
  name: string
  url: string
  auth_token: string
  agent_type: string
  sends: number
  identity: string
  attested: Attested
  /** `null` until the operator declares one way or the other. Never defaulted. */
  exposes_tool_calls: boolean | null
  declared_tools: string[]
  /** The empty string means *not priced*, which is a declaration and not a zero. */
  price_per_call: string
  currency: string
  note_planted: boolean
  nonce: string
  /** Whether the operator says the nonce is in the target's live configuration. */
  nonce_planted: boolean
  /**
   * The operator has read what starting without the echo costs, and is doing it.
   *
   * Held apart from `nonce_planted` rather than folded into it, because they are
   * two different statements: one says the value is in place, the other says the
   * run may go ahead with nothing proving it. A walk that let the second be made
   * by leaving the first unticked would be a waiver nobody read.
   */
  proof_waived: boolean
}

/**
 * Nothing declared yet.
 *
 * `sends` starts at the backend's own `RetryPolicy` default of 3 because the
 * enforced ceiling is built from it and a run has to be held to a number the
 * operator saw; `exposes_tool_calls` starts at `null` because there is no safe
 * default for it — false would silently drop two families and true would promise
 * a trace the bench cannot read.
 */
export function nothingDeclared(): Declarations {
  return {
    name: '',
    url: '',
    auth_token: '',
    agent_type: '',
    sends: 3,
    identity: '',
    attested: {
      authorised_to_test: false,
      not_production: false,
      accepts_provider_policy_and_cost: false,
    },
    exposes_tool_calls: null,
    declared_tools: [],
    price_per_call: '',
    currency: 'USD',
    note_planted: false,
    nonce: '',
    nonce_planted: false,
    proof_waived: false,
  }
}

/**
 * The statements that have not been made, in the wording they were asked in.
 *
 * Named rather than counted: an operator told "one statement is missing" has to
 * find it, and the API's own refusal names them for the same reason.
 */
export function withheldStatements(declarations: Declarations): string[] {
  return ATTESTATION_STATEMENTS.filter(
    (statement) => !declarations.attested[statement.field],
  ).map((statement) => statement.wording)
}

/**
 * A registration ready to post, or the reasons it is not.
 *
 * Two outcomes rather than a body and a separate `valid` flag, so that there is
 * no way to reach the body of a registration that is not complete.
 */
export type RegistrationRequest =
  | { kind: 'ready'; body: StartRunBody }
  | { kind: 'blocked'; missing: string[] }

/**
 * What the screen would post, or what it is still waiting for.
 *
 * The order of the checks is the order of the screen's steps, so the first thing
 * an operator is told about is the earliest step they have to go back to.
 */
export function registrationRequest(
  declarations: Declarations,
): RegistrationRequest {
  const missing: string[] = []

  if (!declarations.name.trim()) {
    missing.push('the target needs a name, so the report can say what was measured')
  }
  if (!declarations.url.trim()) {
    missing.push('the target needs a URL — there is no endpoint to register')
  }
  if (!declarations.agent_type.trim()) {
    missing.push('the target needs an agent type')
  }
  if (declarations.sends < 1) {
    missing.push(
      'one message has to be allowed at least one send: the enforced ceiling is ' +
        'built from this figure',
    )
  }
  if (declarations.proof_waived) {
    // Nothing to require. The value is the proof of control and the leakage canary,
    // and this run has waived the first and dropped the second: a nonce issued for
    // it would be a value nobody plants, nothing checks and one family no longer
    // needs (ADR-0007, as amended).
  } else if (!declarations.nonce) {
    missing.push('no nonce has been issued, so there is nothing planted to prove')
  } else if (!declarations.nonce_planted) {
    // Two ways past this step and the second one is not silence. Either the value
    // is planted, or the operator has said in as many words that the run may start
    // without the proof — and until one of them is stated, the walk is unfinished
    // rather than waived by default.
    missing.push(
      'the nonce is not declared planted, and the proof of control has not been ' +
        'waived. Registration completes on the echo, and the run’s first call ' +
        'asks for it',
    )
  }
  if (!declarations.identity.trim()) {
    missing.push('an attestation has to record who made it')
  }
  missing.push(
    ...withheldStatements(declarations).map(
      (wording) => `not attested: ${wording}`,
    ),
  )

  if (declarations.exposes_tool_calls === null) {
    missing.push(
      'tool-call visibility is not declared. It decides whether ' +
        `${TOOL_TRACE_FAMILIES.join(' and ')} can be measured at all`,
    )
  } else if (declarations.exposes_tool_calls && !declaredTools(declarations).length) {
    // The API's own refusal, held here so the operator meets it as an unfinished
    // step rather than as a 422: scope creep is read against this list, and
    // against an empty one every call the target makes would score as a finding.
    missing.push(
      'a target that exposes its tool calls has to declare which tools it has: ' +
        'scope creep is read against that list, and against an empty one every ' +
        'call this target makes would score as a finding',
    )
  }
  if (declarations.price_per_call.trim() && !declarations.currency.trim()) {
    // `CallPrice`'s guard, for the same reason: an amount with a currency the
    // bench chose is a figure the operator did not state.
    missing.push(
      'a price per call needs the currency it is in, or declare the run not priced',
    )
  }

  if (missing.length) {
    return { kind: 'blocked', missing }
  }
  return { kind: 'ready', body: startRunBody(declarations) }
}

/** The declared tools, trimmed and without the blanks a textarea leaves behind. */
export function declaredTools(declarations: Declarations): string[] {
  return declarations.declared_tools
    .map((tool) => tool.trim())
    .filter((tool) => tool.length > 0)
}

/**
 * The body itself.
 *
 * A tool list is sent only when the target was declared to expose its calls: a
 * list beside `exposes_tool_calls: false` is a list nothing will ever read, and
 * carrying it would let a reader of the record think two families were measured
 * against it.
 */
function startRunBody(declarations: Declarations): StartRunBody {
  const priced = declarations.price_per_call.trim()
  return {
    target: {
      name: declarations.name.trim(),
      url: declarations.url.trim(),
      auth_token: declarations.auth_token,
      agent_type: declarations.agent_type.trim(),
      exposes_tool_calls: declarations.exposes_tool_calls === true,
      declared_tools:
        declarations.exposes_tool_calls === true ? declaredTools(declarations) : [],
      sends: declarations.sends,
    },
    attestation: {
      identity: declarations.identity.trim(),
      ...declarations.attested,
    },
    nonce: declarations.nonce,
    cost: {
      price_per_call: priced ? priced : null,
      currency: priced ? declarations.currency.trim() : '',
    },
    note_planted: declarations.note_planted,
    // Two fields, one tick. This screen offers two states and no third — the value
    // is planted, or the operator could not plant it and says so — and the plant
    // tick carries both declarations, because an agent whose disclosure rule is
    // blanket cannot tell the registration check from an attack and refuses a probe
    // it has the value for (ADR-0024). The bench still reads a different thing off
    // each: the presence decides whether the leakage family is run, and the waiver
    // decides only whether a missing echo stops the run. The probe is still sent and
    // the reply still kept, so a target that echoes anyway has proved control.
    nonce_planted: declarations.nonce_planted,
    echo_waived: declarations.nonce_planted,
  }
}

/**
 * The nonce-echo refusal on a run this screen started, or `null` for anything
 * else.
 *
 * Matched on the status and on nothing else. A run that failed on the wire, or
 * aborted on its own ceiling, or is still holding its interrupt, is not a target
 * that refused to echo — and reporting any of them as one would tell an operator
 * to re-plant a value that is already planted, while the real fault went unnamed.
 * The statement is the bench's, unedited: it is the one that says to check the
 * configuration line and that the target reloaded.
 */
export function echoRefusal(standing: RunStanding): string | null {
  return standing.status === REGISTRATION_REFUSED ? standing.statement : null
}
