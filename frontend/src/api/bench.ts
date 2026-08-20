/**
 * The bench's HTTP surface as this app is allowed to see it.
 *
 * Three of the seven routes are reachable from here — `POST /nonces`, `POST
 * /runs` and `GET /runs/{id}` — and the field names are the backend's own,
 * `snake_case` and all, because the request body is a contract with
 * `backend/api/app.py` rather than a shape this app is free to choose. A
 * camel-cased mirror would be one rename away from posting a body the API
 * refuses, and the refusal would arrive as a `422` nobody could read.
 *
 * **Nothing here throws for a refusal.** A registration the bench refuses is a
 * step the operator has to complete rather than an error the app fell over on
 * (ADR-0007 calls it the authorisation guard for exactly that reason), so
 * `startRun` returns one of three outcomes and every one of them carries the
 * sentence the bench wrote. An exception would be caught somewhere far from the
 * screen that has to say what to do next, and the sentence would be lost on the
 * way. What *is* thrown is a fetch that never reached the bench at all, and
 * `startRun` turns that into an outcome too — see `unreachable`.
 *
 * **A start refusal always costs the nonce.** `BenchRuns.start` discards the
 * value from its issued set before it does anything else, so one nonce starts one
 * run and no more — whether that run was refused, and whether the answer ever
 * came back. Every non-registered outcome therefore sends the operator back to
 * the plant step with a value the bench has just issued, and none of them offers
 * a retry of the same body.
 */

/** The value the operator plants, the probe that will ask for it, and why. */
export interface NonceIssued {
  nonce: string
  echo_probe: string
  statement: string
}

/** The endpoint the bench is being asked to attack, as the operator declares it. */
export interface TargetBody {
  name: string
  url: string
  auth_token: string
  agent_type: string
  exposes_tool_calls: boolean
  declared_tools: string[]
  sends: number
}

/**
 * The three statements, one field each, beside who made them.
 *
 * Three booleans rather than one `i_agree`, because the record has to show *what*
 * was attested — and the API will not construct an `Attestation` with any one of
 * them withheld.
 */
export interface AttestationBody {
  identity: string
  authorised_to_test: boolean
  not_production: boolean
  accepts_provider_policy_and_cost: boolean
}

/**
 * What one call on this endpoint costs the operator, as the operator states it.
 *
 * `price_per_call: null` is a declaration and not an omission: the run reports
 * *not priced* rather than zero, because an unknown cost and a free run are
 * different facts and only one of them is safe to confirm without reading
 * further.
 */
export interface CostBody {
  price_per_call: string | null
  currency: string
}

/** Everything a run needs before it may exist, and nothing it can default. */
export interface StartRunBody {
  target: TargetBody
  attestation: AttestationBody
  nonce: string
  cost: CostBody
  note_planted: boolean
}

/**
 * A run that exists and is holding its interrupt.
 *
 * `estimate` and `spent` are carried untouched and unread. This app does not
 * render either — the two cost figures are the run screen's subject — and typing
 * them here would be a second description of figures the bench already
 * describes, which is the first place a friendly total gets added.
 */
export interface RunStarted {
  run_id: string
  status: string
  statement: string
  estimate: unknown
  spent: Record<string, number>
  cases: number
  families_not_run: Record<string, string>
}

/**
 * Where a run has got to, in the two fields this screen reads.
 *
 * The per-layer positions are deliberately absent: progress belongs to the run
 * screen, and a register screen that could read a scored position is a register
 * screen somebody will one day print a total on. What registration needs is the
 * status and the sentence beside it.
 */
export interface RunStanding {
  run_id: string
  status: string
  statement: string
}

/**
 * The status a run settles at when the target never echoed the planted nonce.
 *
 * The echo cannot be checked when the run is started: the probe is itself a call
 * on the operator's endpoint, and ADR-0007 puts the halt *ahead* of registration
 * so that a run has spent nothing by the time it asks for consent. So the failure
 * this screen has to recover from arrives as a run status and not as a response
 * to the registration request, and it is matched by name rather than by reading
 * the statement, because the statement is prose written for a human.
 */
export const REGISTRATION_REFUSED = 'registration_refused'

/**
 * What became of a registration request.
 *
 * `refused` is the bench declining — a nonce it never issued, an incomplete
 * attestation, a declaration it will not accept — and it carries the bench's own
 * words. `unreachable` is no answer at all, which is a different fact and gets a
 * different sentence: the operator has an API to start, not a form to fix.
 */
export type StartOutcome =
  | { kind: 'registered'; run: RunStarted }
  | { kind: 'refused'; statement: string }
  | { kind: 'unreachable'; statement: string }

const UNREACHABLE =
  'the bench did not answer, so it is not known whether it recorded this ' +
  'registration. Treat the nonce as spent: check that the API is running, then ' +
  'plant the value the bench issues next and register again.'

const REFUSED_WITHOUT_A_REASON =
  'the bench refused this registration and returned no reason with it. Nothing ' +
  'was sent to the target. Plant the value the bench issues next and register ' +
  'again.'

/** Issue a nonce. One value, one run: the next run needs one planted again. */
export async function issueNonce(): Promise<NonceIssued> {
  const response = await fetch('/nonces', { method: 'POST' })
  if (!response.ok) {
    throw new Error(
      `the bench refused to issue a nonce (HTTP ${response.status}), so there is ` +
        'nothing to plant and no registration to attempt',
    )
  }
  return (await response.json()) as NonceIssued
}

/**
 * Register a target: record the attestation, declare the estimate, and halt.
 *
 * A `202` means the run exists and is holding its interrupt, which is *before*
 * anything has been sent to the target. It does not mean the target echoed the
 * nonce; nothing has asked it yet.
 */
export async function startRun(body: StartRunBody): Promise<StartOutcome> {
  let response: Response
  try {
    response = await fetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (unreachable) {
    return { kind: 'unreachable', statement: `${UNREACHABLE} (${unreachable})` }
  }
  if (response.ok) {
    return { kind: 'registered', run: (await response.json()) as RunStarted }
  }
  return { kind: 'refused', statement: await refusalIn(response) }
}

/**
 * The sentence the bench sent with its refusal.
 *
 * FastAPI puts a raised `HTTPException`'s message in `detail` as a string, and
 * its own body-validation errors in the same field as a list of objects. Both are
 * read here rather than only the first, because the second is what arrives when
 * this app posts a field the API's models reject — and a screen that showed
 * "refused, no reason given" for it would be hiding the one message that says
 * which field.
 */
async function refusalIn(response: Response): Promise<string> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    return REFUSED_WITHOUT_A_REASON
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((problem) => {
        const { loc, msg } = problem as { loc?: unknown[]; msg?: string }
        const where = Array.isArray(loc) ? loc.join('.') : ''
        return where ? `${where}: ${msg ?? ''}` : `${msg ?? ''}`
      })
      .join('; ')
  }
  return REFUSED_WITHOUT_A_REASON
}

/** Where one run has got to, or the reason this app could not find out. */
export async function runStanding(runId: string): Promise<RunStanding> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) {
    throw new Error(
      `the bench has no run ${runId} to report on (HTTP ${response.status})`,
    )
  }
  return (await response.json()) as RunStanding
}
