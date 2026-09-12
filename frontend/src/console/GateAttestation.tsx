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
import { AttestingAs } from '../attesting'
import { Blocked, STILL_UNDECLARED } from '../blocked'

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
  const held = busy || !made || (last && missing.length > 0)
  /**
   * What is holding the forward control, where anything this screen can say holds it.
   *
   * The statement's own tick is not in here and cannot be: it is the one control on
   * the screen, directly above the button, and a line reading *not attested* under
   * the box the operator has not ticked says nothing they cannot see. What the guard
   * refuses in is the rest of the declaration, and it is only knowable on the last
   * step, where the body is built.
   */
  const reasons = last ? missing : []
  return (
    <section>
      {/* A form, so that Enter in the price field below does what the primary
          button does — the register walk's own arrangement, for the same reason and on
          the same footer (#120). Nothing here spends anything: the forward control
          reaches the estimate, and the halt in front of the spend is the screen after
          this one (ADR-0007). */}
      <form
        onSubmit={(event) => {
          // Prevented for the reason `RegisterScreen`'s is: the browser's own submit
          // would reload the console and take the declaration with it.
          event.preventDefault()
          if (!held) {
            forward()
          }
        }}
      >
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
            <AttestingAs />
            <label className="priced">
              Price per call
              <input
                value={attesting.price_per_call}
                onChange={(event) => declare({ price_per_call: event.target.value })}
                placeholder="leave empty for a gate run you have not priced"
              />
              <span className="aside">
                What one call costs you, on your own provider.
              </span>
            </label>
          </>
        ) : null}

        {/* The register walk's own list, out of the module both walks draw it from
            (`blocked.tsx`), and cited by the button below rather than only sitting
            over it. Only on the last step: the earlier ones are held by their own
            statement and the tick beside it is the whole of what is missing. */}
        <Blocked reasons={reasons} />

        <footer className="walk">
          <button type="button" onClick={back} disabled={busy}>
            {step === 0 ? 'Not now' : 'Back'}
          </button>
          <button
            type="submit"
            className="primary"
            disabled={held}
            aria-describedby={reasons.length ? STILL_UNDECLARED : undefined}
          >
            {last
              ? busy
                ? 'Starting…'
                : 'See what it will cost'
              : 'Continue'}
          </button>
        </footer>
      </form>
    </section>
  )
}
