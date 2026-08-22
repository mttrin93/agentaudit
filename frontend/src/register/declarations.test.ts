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
  NOT_MEASURABLE_WITHOUT_TOOL_CALLS,
  TOOL_TRACE_FAMILIES,
  echoRefusal,
  nothingDeclared,
  registrationRequest,
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
    // Not measurable is a third outcome and never a rate of zero, and the screen
    // has to say so where the operator declares it rather than in the report.
    expect(NOT_MEASURABLE_WITHOUT_TOOL_CALLS).toContain('not a rate of zero')
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

    expect(blocked.kind).toBe('blocked')
    expect(ready.kind).toBe('ready')
    // What the bench acts on is the value, not the waiver: it drops the leakage
    // family and records control as unproved on the strength of this field.
    expect(ready.kind === 'ready' && ready.body.nonce_planted).toBe(false)
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
