/**
 * Why the primary button is dead, over the button, on both walks that have one.
 *
 * The register walk and the gate walk both refuse to go forward until a declaration
 * is complete, and both say so in the guard's own wording — the strings
 * `unmetConditions` and `gateRunRequest` would refuse in, rather than a sentence a
 * screen invented. Both drew that list themselves, and only one of them bound it to
 * the button it is about: a screen reader in browse mode reading a disabled control
 * would otherwise read *Continue, dimmed* and nothing else, and it did, on the gate.
 *
 * **It sits over the footer rather than under it.** The reader arrives at the button,
 * finds it dead, and the reason is the line their eye has just passed rather than
 * something below the fold or back up the form. That was the register walk's
 * arrangement and its docstring said it was the gate's too, which was true of the
 * position and not of the binding. It is true of both now.
 *
 * **The list and the id it answers to come out of one module.** The id is written
 * down once and exported for the button to cite, rather than typed on both walks: a
 * citation of a string nothing renders is the same dangling reference `Field` is
 * shaped against in `RegisterScreen.tsx`, and there it is unreachable by
 * construction. Here it is one string, and the condition that draws the list is the
 * same list the button is disabled by.
 *
 * A constant rather than a `cited(reasons)` helper: `.oxlintrc.json` warns on a
 * `.tsx` that exports a function beside a component — fast refresh goes for the file
 * — and allows a constant beside one. So the ternary is at the call sites, where it
 * reads off the same array the list is drawn from.
 *
 * **One list a page**, since the id is a constant and not a prop. Both walks draw one
 * over one footer, which is what the id is for; a screen wanting two would want an id
 * per list, and the day that arrives is the day this takes a name.
 */

/** Where the reasons the primary button is dead are written, for the button to cite. */
export const STILL_UNDECLARED = 'still-undeclared'

/**
 * The reasons, or nothing at all where there are none.
 *
 * A reason left standing over an enabled button is worse than no reason at all, so
 * an empty list draws no element rather than an empty one.
 */
export function Blocked({ reasons }: { reasons: readonly string[] }) {
  if (reasons.length === 0) {
    return null
  }
  return (
    <ul className="blocked" id={STILL_UNDECLARED}>
      {reasons.map((one) => (
        <li key={one}>{one}</li>
      ))}
    </ul>
  )
}
