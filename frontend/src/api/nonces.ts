/**
 * `POST /nonces` — the value the operator plants before a run may start.
 *
 * One route and its answer, kept as its own module by #14's split because it is its
 * own step: the bench issues the value, the operator plants it in the target's
 * configuration, and the run's own registration probe checks that it comes back
 * (ADR-0007). Nothing here starts a run, and a nonce is spent whether the run it
 * was issued for is refused or not.
 */

import { authed } from './http'

/** The value the operator plants, the probe that will ask for it, and why. */
export interface NonceIssued {
  nonce: string
  echo_probe: string
  statement: string
}

/** Issue a nonce. One value, one run: the next run needs one planted again. */
export async function issueNonce(): Promise<NonceIssued> {
  const response = await authed('/nonces', { method: 'POST' })
  if (!response.ok) {
    throw new Error(
      `the bench refused to issue a nonce (HTTP ${response.status}), so there is ` +
        'nothing to plant and no registration to attempt',
    )
  }
  return (await response.json()) as NonceIssued
}
