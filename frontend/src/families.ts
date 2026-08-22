/**
 * A family's name as a screen says it, from the name the wire gives it.
 *
 * `Family` is an enum on the bench and its members are identifiers —
 * `indirect_prompt_injection` — which is what every record, document and route
 * carries and what this app joins on. An underscore is how an identifier is spelled
 * and not how a name is read: six of them stacked in a column read as a config file
 * rather than as the six things this bench attacks.
 *
 * **The words only, and never a second vocabulary.** The underscore becomes a space
 * and nothing else happens — no title case, no expansion, no friendlier synonym. The
 * name on the screen is the name in the record with one character changed, so an
 * operator reading `indirect prompt injection` here and grepping
 * `indirect_prompt_injection` in a signed report is looking at the same word.
 * CONTEXT.md's vocabulary is load-bearing arithmetic, and a screen that renames a
 * family is a screen that has invented a seventh.
 *
 * **Called where a family is printed, and nowhere else.** Every `family` field in
 * this app carries the wire name, because those same fields are the keys an answer's
 * question, an exclusion and a confidence are found by. So this is called at the
 * point of print, or by the projection that builds display text out of one — never
 * on the value a lookup will be made with, and never on a case id, a path or a
 * sentence the bench wrote.
 */
export function readFamily(family: string): string {
  return family.replace(/_/g, ' ')
}
