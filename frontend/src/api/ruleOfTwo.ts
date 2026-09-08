/**
 * `POST /rule-of-two` — what the published rule makes of four declarations.
 *
 * Its own module because it is its own area: not a run, not the bench, and not a
 * registration. The register walk asks the four questions and shows the reading back
 * while they are being answered, so that the one person who could act on a standing
 * — by changing what their agent *is* rather than what defends it — sees it before
 * the run rather than in a document a recipient reads
 * ([ADR-0092](../../../docs/adr/0092-the-rule-of-two-is-declared-on-the-register-walk-and-the-reading-is-the-backends.md)).
 *
 * **Nothing here derives a standing, and nothing here may.** The five arms and the
 * ordering between them live in `backend/bench/scanner.py`, which is the one place
 * they exist: ADR-0038 decision 5 records getting that ordering wrong on its first
 * draft — reading *unstated* before *not held* printed *the rule cannot be read over
 * this* about a declaration it could be read over — and a second copy in this
 * language would be that bug waiting to be reintroduced where no gold arm tests for
 * it. So this module posts four answers and renders two strings, and
 * `ruleOfTwo.test.ts` greps this app's own source for the five names.
 *
 * **The route sends nothing to anybody.** It records no run, spends no nonce and
 * reaches no target, which is why a screen may ask it once per answer.
 */

import type { RuleOfTwoDeclared } from './contracts'

/** Where a candidate declaration is read. Exported so a test can name it. */
export const RULE_OF_TWO_PATH = '/rule-of-two'

/**
 * What the rule makes of one declaration: the standing's name, and the sentence.
 *
 * Two fields and no third. There is nowhere here for a figure to arrive — in
 * particular not a count of the capabilities held, which is the one number this block
 * is a line away from and the number that ranks two targets the moment two of them
 * are on one desk (ADR-0038, decision 4).
 *
 * `stated` is the report's own prose and carries `scanner.NOT_A_MEASUREMENT`, so a
 * screen showing the reading cannot show it without the line saying nothing was sent
 * to establish it.
 */
export interface RuleOfTwoRead {
  standing: string
  stated: string
}

/**
 * Read four answers against the published rule. Sends nothing to the target.
 *
 * Throws where the bench did not answer, and the caller shows nothing: a reading
 * that could not be read is one an operator never sees, rather than an error over a
 * form that registers perfectly well without it. The four declarations are the
 * operator's either way — the fieldset holds no step (ADR-0092, decision 2).
 */
export async function readRuleOfTwo(
  declared: RuleOfTwoDeclared,
): Promise<RuleOfTwoRead> {
  const response = await fetch(RULE_OF_TWO_PATH, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(declared),
  })
  if (!response.ok) {
    throw new Error(
      `the bench did not read this declaration against the Agents Rule of Two ` +
        `(HTTP ${response.status}), so there is no standing to show. The four ` +
        `answers are still declared and the registration is not held by them.`,
    )
  }
  return (await response.json()) as RuleOfTwoRead
}
