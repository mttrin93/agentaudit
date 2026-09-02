/**
 * The three statements, one at a time, and no way past them.
 *
 * Moved out of `GateScreen.tsx` by #14's split, unchanged. The attestation
 * `registration.py` refuses to construct incomplete, asked here one statement per
 * screen so that an operator answers each of them rather than a checkbox meaning all
 * three (ADR-0007).
 *
 * **Nothing here can start a gate run.** It reports what is missing and hands the
 * forward control back; the body is built by `gateRunRequest`, which will not build
 * one from an incomplete declaration.
 */

import type {
  Attesting,
} from './gaterun'
import {
  GATE_RUN_STATEMENTS,
} from './gaterun'

/**
 * The three statements, one at a time, in the record's own wording.
 *
 * One at a time and not three checkboxes in a column: each is recorded separately
 * and two of the three are consequences nobody would infer, so a screen that showed
 * them together would be a screen where they are read as one (ADR-0007). The walk's
 * footer is the register screen's, because it is the same walk.
 *
 * The note under the checkbox — all three required, each recorded separately,
 * nothing sent yet — is gone. That all three are required is enforced by the guard
 * that will not build a body from an incomplete declaration and by the bench that
 * refuses an incomplete one; that nothing has been sent is what *Continue* and *See
 * what it will cost* say by being the only way forward. The register screen keeps
 * its own note, which says a different thing: what the artefact is (ADR-0007).
 */
export function TheAttestation({
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
