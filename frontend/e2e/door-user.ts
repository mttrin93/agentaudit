/**
 * The four values a walkthrough against a bench with a door needs, and the sentence
 * it prints when it has none of them.
 *
 * **This is the one part of the end-to-end walkthrough that cannot be stubbed.** The
 * issuerless suite drives a `NO_DOOR` bench (`harness.py`, ADR-0121) and proves what
 * every screen does when nobody signed in; what it cannot prove is that a signed-in
 * operator reaches the bench at all, because that needs a real session from a real
 * issuer. So the doored suite needs an account, and an account is a thing a clone,
 * a fork and CI do not have.
 *
 * **Absent is a skip that says so, and never a pass.** Decided in
 * [ADR-0125](../../docs/adr/0125-the-doored-walkthrough-is-opt-in-and-an-absent-test-user-is-a-printed-skip.md),
 * which weighs it against the three alternatives and is not re-argued here. The local
 * consequence is this function's shape: `declared: false` carries the names it wanted,
 * `door.spec.ts` skips on it, and `playwright.door.config.ts` prints the sentence —
 * because a reporter prints `2 skipped` and not the annotation behind it.
 *
 * **Nothing here is committed and nothing here is printed.** The values are read from
 * the environment at the moment they are used; `statement` names the *variables* and
 * never their contents, because a skip message is the one line of this suite that
 * reaches a log.
 *
 * The variables are listed in `docs/deployment.md` beside the rest of what a
 * deployment declares.
 */

/** The issuer's publishable key, compiled into the console under test. */
const PUBLISHABLE_KEY = 'AGENTAUDIT_E2E_CLERK_PUBLISHABLE_KEY'

/**
 * The issuer's public key in PEM, which the harness turns into the bench's door.
 *
 * Required here and returned by nothing: it is read by `harness.py`, which Playwright
 * starts with this process's environment. It is checked all the same, because a run
 * that had the console's key and not the bench's would sign an operator in against a
 * bench with no door and assert nothing at all.
 */
const ISSUER_JWT_KEY = 'AGENTAUDIT_E2E_ISSUER_JWT_KEY'

/** The test user's identifier at the issuer. */
const CLERK_USER = 'AGENTAUDIT_E2E_CLERK_USER'

/** That user's password. Never committed, never printed, never in a screenshot. */
const CLERK_PASSWORD = 'AGENTAUDIT_E2E_CLERK_PASSWORD'

/** Every variable the doored walkthrough needs, in the order a skip reports them. */
export const DOOR_VARIABLES = [
  PUBLISHABLE_KEY,
  ISSUER_JWT_KEY,
  CLERK_USER,
  CLERK_PASSWORD,
] as const

/**
 * The doored walkthrough's inputs, or the reason there is no doored walkthrough.
 *
 * A union rather than a nullable object with a `missing` beside it, on the shape
 * `door.ts`'s `WhoIsAttesting` takes: the members that have no meaning in the
 * undeclared reading are absent from it, so a caller cannot read a credential it was
 * not given.
 */
export type DoorUser =
  | {
      declared: true
      publishableKey: string
      emailAddress: string
      password: string
    }
  | { declared: false; missing: string[]; statement: string }

/**
 * What the environment declared about the doored walkthrough.
 *
 * **A blank is unset**, as it is in `identity.declared_issuer` and in
 * `console/door.ts`: a variable cleared by whatever set it has declared nothing, and a
 * half-finished export is the commonest way one arrives.
 *
 * **Three of four is undeclared and names the fourth.** That is the reading this
 * function exists for — a partially configured run is the one that fails obscurely,
 * somewhere inside a sign-in form, and this turns it into a skip that names the
 * variable to export.
 */
export function doorUser(env: Record<string, string | undefined>): DoorUser {
  const read = (name: string): string => env[name]?.trim() ?? ''
  const missing = DOOR_VARIABLES.filter((name) => read(name) === '')
  if (missing.length > 0) {
    return {
      declared: false,
      missing: [...missing],
      statement:
        'the doored walkthrough is skipped: this environment declares no test ' +
        `user at an issuer. Export ${missing.join(', ')} to run it — ` +
        'docs/deployment.md says what each one is.',
    }
  }
  return {
    declared: true,
    publishableKey: read(PUBLISHABLE_KEY),
    emailAddress: read(CLERK_USER),
    password: read(CLERK_PASSWORD),
  }
}
