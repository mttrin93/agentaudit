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
  return readName(family)
}

/**
 * A wire name as a screen says it — the underscore becomes a space, and nothing else.
 *
 * `readFamily` above is this function under the name of the one thing it may be called
 * on, and it stays that way: its rule is *called where a family is printed, and nowhere
 * else*, because every `family` field in this app is also a lookup key. This is the
 * same single character changed, for the other closed sets whose members a screen
 * prints — the three **layers** and the seven **transforms** an operator selects, whose
 * names are `single_turn` and `scripted_crescendo` on the wire, in the record and in
 * the signed report.
 *
 * **Not a place to make a name friendlier.** No title case, no expansion, no synonym:
 * an operator reading `fixed multi turn` here and grepping `fixed_multi_turn` in a
 * settings response is looking at the same word. One function rather than two copies of
 * `replace(/_/g, ' ')`, so a screen cannot acquire a second spelling of a member name.
 */
export function readName(name: string): string {
  return name.replace(/_/g, ' ')
}
