/**
 * Who the bench will record this attestation against, over the three statements, on
 * every walk that collects them.
 *
 * **It names rather than asks.** The name on the record is the subject of the session
 * the API verified the request as ([ADR-0116](../../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
 * §1), so there is nothing here for anybody to type and nothing they could type that
 * would change it. What the field it replaced was for — saying that one name is
 * recorded against all three statements and not against the first one — this line
 * still says, and it now says it about a name nobody can mistype.
 *
 * **That it cannot be changed is left to the absence of a field rather than stated.**
 * The line named the session, the subject, the three statements and then said nothing
 * here could change it; a screen offering nothing to change is already saying the
 * last part, and a sentence that runs past one line is one an operator scans instead
 * of reads. The subject is still printed in full — it is the string the artefact
 * carries, and an operator checking a signed report against the console needs the
 * whole of it.
 *
 * **One component and not three sentences**, on `blocked.tsx`'s reasoning and in the
 * same place for the same reason: the register walk, the gate walk and the
 * pending-routes walk all open on this, and three copies of a sentence about what a
 * signed document will carry would only have to disagree once.
 *
 * **The doorless reading is the one to get right.** A clone built with no issuer
 * renders every screen and signs nobody in (`console/door.ts`), and the bench it
 * reaches records `NOBODY_VERIFIED` — a sentence and not a name
 * ([ADR-0122](../../docs/adr/0122-a-bench-with-no-door-records-that-it-verified-nobody.md)).
 * So that build prints the sentence itself, with no *attesting as* in front of it:
 * a screen that dressed it up as a display name would be promising a verified
 * operator where the artefact will say there was none, which is the failure this
 * bench exists to argue against committed on its own consent screen.
 *
 * *Three* is written out rather than counted off `ATTESTATION_STATEMENTS`, because it
 * is prose and `{count}` in the middle of a sentence reads as a bug. The count is not
 * free to drift: `declarations.test.ts` asserts the record has exactly three, and a
 * fourth statement is an ADR before it is a string.
 */

import { useOperator, whoIsAttesting } from './console/door'

export function AttestingAs() {
  const who = whoIsAttesting(useOperator())
  if (!who.verified) {
    return (
      <div className="attesting-as">
        <p className="consequence">
          This console was built with no issuer, so nobody is signed in and nothing
          established who is at it. The bench records{' '}
          <strong>{who.recorded}</strong> against every one of the three statements.
        </p>
      </div>
    )
  }
  return (
    <div className="attesting-as">
      <p className="consequence">
        Attesting as <strong>{who.named}</strong>, recorded as{' '}
        <code>{who.recorded}</code> against all three statements.
      </p>
    </div>
  )
}
