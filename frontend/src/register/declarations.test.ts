/**
 * What registration will not do, asserted without a browser.
 *
 * The spec expects these screens to be driven by hand and does not justify a
 * browser-driver harness, so what is automated here is what a person cannot check
 * faster than a test can: that a withheld statement blocks a registration by name
 * rather than by a disabled button, that a target declared to expose its tool calls
 * cannot register without saying which, and that a run whose target never echoed
 * the nonce is recognised as exactly that and not as anything else that stops a
 * run. The rest — whether the page reads like the guard it is — is the part a
 * person does check faster.
 */

import { describe, expect, it } from 'vitest'

import type { RunStanding } from '../api/bench'
import {
  ATTESTATION_STATEMENTS,
  NOTHING_TO_DISCLOSE_WITHOUT_PERSONAL_RECORDS,
  NOT_MEASURABLE_WITHOUT_TOOL_CALLS,
  NO_LADDERS_WITHOUT_SESSION_RETENTION,
  TOOL_TRACE_FAMILIES,
  WALK_STEPS,
  canLeave,
  echoRefusal,
  nothingDeclared,
  registrationRequest,
  unmetConditions,
  withheldStatements,
  type Declarations,
} from './declarations'

/** Everything declared, so that each test can withhold exactly one thing. */
function fullyDeclared(): Declarations {
  return {
    ...nothingDeclared(),
    name: 'staging support agent',
    url: 'https://staging.example/agent',
    auth_token: 'token',
    agent_type: 'customer support',
    identity: 'operator',
    attested: {
      authorised_to_test: true,
      not_production: true,
      accepts_provider_policy_and_cost: true,
    },
    exposes_tool_calls: true,
    declared_tools: ['send_email', 'issue_refund'],
    price_per_call: '0.002',
    nonce: 'AGENTAUDIT-CANARY-0011AABB',
    nonce_planted: true,
  }
}

describe('the three attestations', () => {
  it('are all required, and a withheld one is named in the wording it was asked in', () => {
    for (const withheld of ATTESTATION_STATEMENTS) {
      const declarations = fullyDeclared()
      declarations.attested = { ...declarations.attested, [withheld.field]: false }

      expect(withheldStatements(declarations)).toEqual([withheld.wording])
      const request = registrationRequest(declarations)
      expect(request.kind).toBe('blocked')
      expect(request.kind === 'blocked' && request.missing).toContain(
        `not attested: ${withheld.wording}`,
      )
    }
  })

  it('are three statements and not one agreement', () => {
    // Three fields, so the record shows *what* was attested — and the two
    // consequences a user would never infer are stated beside their own statement
    // rather than bundled under a shared one (ADR-0007).
    expect(ATTESTATION_STATEMENTS).toHaveLength(3)
    expect(new Set(ATTESTATION_STATEMENTS.map((one) => one.field)).size).toBe(3)
    for (const statement of ATTESTATION_STATEMENTS) {
      expect(statement.consequence.length).toBeGreaterThan(0)
    }
  })

  it('are recorded against somebody, so an unnamed attestation registers nothing', () => {
    const declarations = { ...fullyDeclared(), identity: '   ' }

    const request = registrationRequest(declarations)

    expect(request.kind).toBe('blocked')
    expect(request.kind === 'blocked' && request.missing).toContain(
      'an attestation has to record who made it',
    )
  })
})

describe('the tool-visibility declaration', () => {
  it('names the two families that stop being measurable without it', () => {
    expect([...TOOL_TRACE_FAMILIES]).toEqual(['scope creep', 'halt defeat'])
    expect(NOT_MEASURABLE_WITHOUT_TOOL_CALLS).toContain('scope creep')
    expect(NOT_MEASURABLE_WITHOUT_TOOL_CALLS).toContain('halt defeat')
    // Not measurable is the third outcome, and the word this sentence must not
    // reach for is the one it is being told apart from: a family nothing measured is
    // not a family that held. That it is not a rate of zero either is asserted where
    // the figure is — `report.ts`, beside the outcome — and no longer here, since
    // this screen shows no rates at all.
    expect(NOT_MEASURABLE_WITHOUT_TOOL_CALLS).toContain('not measurable')
    expect(NOT_MEASURABLE_WITHOUT_TOOL_CALLS).toContain('rather than as defended')
  })

  it('has to be made: neither answer is defaulted', () => {
    const undeclared = { ...fullyDeclared(), exposes_tool_calls: null }

    const request = registrationRequest(undeclared)

    expect(request.kind).toBe('blocked')
    expect(
      request.kind === 'blocked' &&
        request.missing.some((missing) =>
          missing.includes('tool-call visibility is not declared'),
        ),
    ).toBe(true)
  })

  it('needs the tool list when the calls are visible, or every call is a finding', () => {
    const withoutTools = { ...fullyDeclared(), declared_tools: ['', '  '] }

    const request = registrationRequest(withoutTools)

    expect(request.kind).toBe('blocked')
    expect(
      request.kind === 'blocked' &&
        request.missing.some((missing) =>
          missing.includes('has to declare which tools it has'),
        ),
    ).toBe(true)
  })

  it('carries no tool list for a target whose calls are not visible', () => {
    const blind = {
      ...fullyDeclared(),
      exposes_tool_calls: false,
      declared_tools: ['send_email'],
    }

    const request = registrationRequest(blind)

    expect(request.kind).toBe('ready')
    expect(request.kind === 'ready' && request.body.target).toMatchObject({
      exposes_tool_calls: false,
      declared_tools: [],
    })
  })
})

describe('the session-retention declaration', () => {
  it('says what a target without it is not sent, and never that a family held', () => {
    // The one thing an operator has to be told before answering: what the answer
    // costs. Not a rate and not a family — the families keep their single-turn cases
    // — but the constructions inside them (ADR-0041, ADR-0054).
    expect(NO_LADDERS_WITHOUT_SESSION_RETENTION).toContain('skipped')
    expect(NO_LADDERS_WITHOUT_SESSION_RETENTION).toContain('single-turn')
    expect(NO_LADDERS_WITHOUT_SESSION_RETENTION).not.toContain('zero')
  })

  it('starts unanswered and holds no step, whichever way it is answered', () => {
    expect(nothingDeclared().retains_session_state).toBeNull()

    for (const step of WALK_STEPS) {
      for (const start of [nothingDeclared(), fullyDeclared()]) {
        const held = unmetConditions(step, start)
        for (const answer of [true, false, null]) {
          const declared = { ...start, retains_session_state: answer }
          expect(unmetConditions(step, declared), `${step}/${String(answer)}`).toEqual(
            held,
          )
          expect(canLeave(step, declared)).toBe(canLeave(step, start))
        }
      }
    }
  })

  it('goes on the wire as a boolean, and unanswered is the narrower run', () => {
    // Unlike the four above, silence is not carried as silence: the bench reads this
    // as a capability whose absent state is *false*, and a run that read a ladder
    // against a target nobody said retains anything is the reading ADR-0041 refuses.
    // So the console posts the same `false` the API would have defaulted to.
    for (const [answer, sent] of [
      [true, true],
      [false, false],
      [null, false],
    ] as const) {
      const request = registrationRequest({
        ...fullyDeclared(),
        retains_session_state: answer,
      })

      expect(request.kind).toBe('ready')
      expect(request.kind === 'ready' && request.body.target.retains_session_state).toBe(
        sent,
      )
    }
  })
})

describe('the personal-records declaration', () => {
  it('says what a target without it is not asked, and never that it held', () => {
    // The family is refused rather than measured: a target holding nothing about
    // anybody has nothing for the attack to ask for, and a rate of zero read off one
    // would report it as governing data it was never given (ADR-0043).
    expect(NOTHING_TO_DISCLOSE_WITHOUT_PERSONAL_RECORDS).toContain('not measurable')
    expect(NOTHING_TO_DISCLOSE_WITHOUT_PERSONAL_RECORDS).not.toContain('zero')
    // And it is the tier's family, so the answer moves nothing the six decide.
    expect(NOTHING_TO_DISCLOSE_WITHOUT_PERSONAL_RECORDS).toContain('pii_leakage')
  })

  it('starts unanswered and holds no step, whichever way it is answered', () => {
    expect(nothingDeclared().holds_personal_records).toBeNull()

    for (const step of WALK_STEPS) {
      for (const start of [nothingDeclared(), fullyDeclared()]) {
        const held = unmetConditions(step, start)
        for (const answer of [true, false, null]) {
          const declared = { ...start, holds_personal_records: answer }
          expect(unmetConditions(step, declared), `${step}/${String(answer)}`).toEqual(
            held,
          )
          expect(canLeave(step, declared)).toBe(canLeave(step, start))
        }
      }
    }
  })

  it('goes on the wire as a boolean, and unanswered is the narrower run', () => {
    // The same rule as retention beside it: silence is not carried as silence, it is
    // posted as the `false` the API would have defaulted to, which is the run where
    // the family is refused rather than the one where it reports a clean zero.
    for (const [answer, sent] of [
      [true, true],
      [false, false],
      [null, false],
    ] as const) {
      const request = registrationRequest({
        ...fullyDeclared(),
        holds_personal_records: answer,
      })

      expect(request.kind).toBe('ready')
      expect(
        request.kind === 'ready' && request.body.target.holds_personal_records,
      ).toBe(sent)
    }
  })
})

describe('the nonce', () => {
  it('has to be issued and declared planted before a registration is attempted', () => {
    const unplanted = { ...fullyDeclared(), nonce_planted: false }
    const unissued = { ...fullyDeclared(), nonce: '', nonce_planted: false }

    const first = registrationRequest(unplanted)
    const second = registrationRequest(unissued)

    expect(first.kind === 'blocked' && first.missing.join(' ')).toContain(
      'not declared planted',
    )
    expect(second.kind === 'blocked' && second.missing.join(' ')).toContain(
      'no nonce has been issued',
    )
  })

  it('may be waived, and the waiver is a statement rather than an unticked box', () => {
    // ADR-0007 as amended: an operator who cannot write into their target's
    // configuration may start the run on their declaration alone. What the walk may
    // not do is treat silence as that declaration — leaving the planted box unticked
    // is an unfinished step, and only the waiver itself gets past it.
    const unplanted = { ...fullyDeclared(), nonce_planted: false }
    const waived = { ...unplanted, proof_waived: true }

    const blocked = registrationRequest(unplanted)
    const ready = registrationRequest(waived)
    // The operator this exists for is the one who never issued a value at all:
    // waiving the proof and dropping the family it is the canary for leaves nothing
    // for a nonce to do, so the walk may not go on requiring one.
    const never = registrationRequest({
      ...fullyDeclared(),
      nonce: '',
      nonce_planted: false,
      proof_waived: true,
    })

    expect(blocked.kind).toBe('blocked')
    expect(ready.kind).toBe('ready')
    expect(never.kind).toBe('ready')
    expect(never.kind === 'ready' && never.body.nonce).toBe('')
    // What the bench acts on is the value, not the waiver: it drops the leakage
    // family and records control as unproved on the strength of this field.
    expect(ready.kind === 'ready' && ready.body.nonce_planted).toBe(false)
  })

  it('sends the planted value and the echo waiver on the one plant tick', () => {
    // The case ADR-0024 splits out, now carried by one tick rather than two. The
    // value is in the target and the target may refuse to repeat it — an agent whose
    // disclosure rule is blanket cannot tell a registration check from an attack —
    // so a walk that sent the presence without the waiver would refuse the target
    // for having the defence this bench exists to measure. Both fields still go out,
    // because the bench reads a different thing off each: the family from the first,
    // the guard from the second.
    const planted = registrationRequest({
      ...fullyDeclared(),
      nonce_planted: true,
    })
    // The other waiver relaxes the same guard from the other direction, and it
    // reaches the run through the unplanted nonce as well as this field:
    // `proof_waived = echo_waived or not nonce_planted`.
    const unplantable = registrationRequest({
      ...fullyDeclared(),
      nonce_planted: false,
      proof_waived: true,
    })

    expect(planted.kind === 'ready' && planted.body.nonce_planted).toBe(true)
    expect(planted.kind === 'ready' && planted.body.echo_waived).toBe(true)
    expect(unplantable.kind === 'ready' && unplantable.body.nonce_planted).toBe(false)
    expect(unplantable.kind === 'ready' && unplantable.body.echo_waived).toBe(false)
  })

  it('is refused by name when the target never echoed it, and the bench keeps the words', () => {
    const refused: RunStanding = {
      run_id: 'run-1',
      status: 'registration_refused',
      statement:
        'the nonce was not echoed, so no attempt was made. Registration proves ' +
        'you control the endpoint and nothing runs without it: check that the ' +
        'nonce line is in the target’s configuration and that it reloaded',
    }

    expect(echoRefusal(refused)).toBe(refused.statement)
  })

  it('is not blamed for anything else that stops a run', () => {
    // A run that failed on the wire, aborted on its own ceiling, was declined at
    // the interrupt or is still holding it has not told anybody anything about the
    // echo — and telling an operator to re-plant a planted value would leave the
    // real fault unnamed.
    for (const status of [
      'awaiting_approval',
      'running',
      'declined',
      'unanswered',
      'aborted',
      'failed',
      'completed',
    ]) {
      expect(echoRefusal({ run_id: 'run-1', status, statement: 'not this' })).toBe(
        null,
      )
    }
  })
})

describe('a priced run', () => {
  it('needs the currency it is priced in', () => {
    const uncurried = { ...fullyDeclared(), currency: '' }

    const request = registrationRequest(uncurried)

    expect(request.kind).toBe('blocked')
    expect(request.kind === 'blocked' && request.missing.join(' ')).toContain(
      'needs the currency it is in',
    )
  })

  it('is not the same as an unpriced one, which is a declaration and not a zero', () => {
    const unpriced = { ...fullyDeclared(), price_per_call: '', currency: 'USD' }

    const request = registrationRequest(unpriced)

    expect(request.kind).toBe('ready')
    expect(request.kind === 'ready' && request.body.cost).toEqual({
      price_per_call: null,
      currency: '',
    })
  })
})

describe('what a step is still waiting for', () => {
  it('names the statements and the name that hold the endpoint step', () => {
    const nothing = nothingDeclared()

    const unmet = unmetConditions('target', nothing)

    expect(unmet).toEqual([
      ...ATTESTATION_STATEMENTS.map((one) => `not attested: ${one.wording}`),
      'an attestation has to record who made it',
    ])
  })

  it('is empty on exactly the steps that may be left', () => {
    // The pair is the invariant: a button disabled with nothing beside it is the
    // dead end this exists to close, and a reason printed under an enabled button
    // is a condition the walk does not actually hold.
    for (const step of WALK_STEPS) {
      expect(unmetConditions(step, nothingDeclared()).length > 0).toBe(
        !canLeave(step, nothingDeclared()),
      )
      expect(unmetConditions(step, fullyDeclared()).length > 0).toBe(
        !canLeave(step, fullyDeclared()),
      )
    }
  })

  it('says of the plant step that the value is unissued, or issued and unplanted', () => {
    const unissued = { ...fullyDeclared(), nonce: '', nonce_planted: false }
    const unplanted = { ...fullyDeclared(), nonce_planted: false }

    expect(unmetConditions('plant', unissued).join(' ')).toContain(
      'no nonce has been issued',
    )
    expect(unmetConditions('plant', unplanted).join(' ')).toContain(
      'not declared planted',
    )
    expect(unmetConditions('plant', { ...unplanted, proof_waived: true })).toEqual([])
  })

  it('says of the tool step which of the two declarations is missing', () => {
    const undeclared = { ...fullyDeclared(), exposes_tool_calls: null }
    const listless = { ...fullyDeclared(), declared_tools: ['', '   '] }

    expect(unmetConditions('tools', undeclared).join(' ')).toContain(
      'tool-call visibility is not declared',
    )
    expect(unmetConditions('tools', listless).join(' ')).toContain(
      'has to declare which tools it has',
    )
  })

  it('is the sentence the registration guard would refuse with, and not a second wording', () => {
    // The screen's reason and the guard's refusal are one string, so a condition
    // reworded on the button cannot drift from the one that blocks the post. Held
    // against `registrationRequest` rather than against a literal, because the
    // wording either matches the guard or it does not.
    const nothing = nothingDeclared()
    const request = registrationRequest(nothing)
    const refused = request.kind === 'blocked' ? request.missing : []

    for (const step of WALK_STEPS) {
      for (const condition of unmetConditions(step, nothing)) {
        expect(refused).toContain(condition)
      }
    }
  })
})

describe('the four Rule of Two declarations', () => {
  it('start unstated, because silence is not a denial', () => {
    // Three answers and not two, on every one of them, and the default is the one
    // ADR-0038 decision 1 argues for: a `false` default would put a claim in an
    // operator's mouth, and it is the profitable claim.
    const nothing = nothingDeclared()

    expect(nothing.processes_untrusted_input).toBeNull()
    expect(nothing.reaches_private_data).toBeNull()
    expect(nothing.changes_state_or_communicates).toBeNull()
    expect(nothing.under_human_supervision).toBeNull()
  })

  it('hold no step of the walk, whichever way each of them is answered', () => {
    // **The assertion this fieldset exists to make.** ADR-0038 decision 2 refuses no
    // combination of the four, so an operator who answers none of them still
    // registers — which is why the questions are a fieldset on a step the tool list
    // already holds rather than a fourth step nothing would hold
    // (ADR-0092, decision 1).
    //
    // Every field, every answer, every step: what a step is waiting for does not
    // move when one of these changes, and neither does whether it may be left.
    const fields = [
      'processes_untrusted_input',
      'reaches_private_data',
      'changes_state_or_communicates',
      'under_human_supervision',
    ] as const

    for (const step of WALK_STEPS) {
      for (const start of [nothingDeclared(), fullyDeclared()]) {
        const held = unmetConditions(step, start)
        for (const field of fields) {
          for (const answer of [true, false, null]) {
            const declared = { ...start, [field]: answer }
            expect(unmetConditions(step, declared), `${step}/${field}`).toEqual(held)
            expect(canLeave(step, declared), `${step}/${field}`).toBe(
              canLeave(step, start),
            )
          }
        }
      }
    }
  })

  it('register unanswered, which no other declaration on this walk does', () => {
    // The four left at *not stated* and the registration is ready: the first
    // declaration on the walk an operator can leave wholly unanswered. The screen
    // says so under the fieldset, because otherwise it reads as a field they forgot.
    const unanswered = fullyDeclared()

    expect(unanswered.processes_untrusted_input).toBeNull()
    expect(registrationRequest(unanswered).kind).toBe('ready')
  })

  it('go on the wire as the three answers they were given, and not as booleans', () => {
    // `null` is a value this body carries rather than a field it omits: the API
    // defaults an absent field to `None` too, but a body that dropped *not stated*
    // would make silence indistinguishable from a screen that never asked.
    const request = registrationRequest({
      ...fullyDeclared(),
      processes_untrusted_input: true,
      reaches_private_data: false,
    })

    expect(request.kind).toBe('ready')
    if (request.kind !== 'ready') {
      return
    }
    expect(request.body.target.processes_untrusted_input).toBe(true)
    expect(request.body.target.reaches_private_data).toBe(false)
    expect(request.body.target.changes_state_or_communicates).toBeNull()
    expect(request.body.target.under_human_supervision).toBeNull()
  })
})
