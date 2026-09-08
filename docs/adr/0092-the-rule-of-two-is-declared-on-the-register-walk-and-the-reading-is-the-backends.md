---
status: accepted
---

# The Rule of Two is declared on the register walk, and the reading printed there is the backend's

[ADR-0038](./0038-the-rule-of-two-is-a-declared-property.md) decided what the four
declarations are, what the five standings mean, and that the block prints beside the
declared controls and never as a finding. It deliberately left one thing open: *how
an operator fills a `TargetConfig` over HTTP is the registration surface's question
rather than this one's.* The consequence of leaving it open is that nobody has ever
been asked. `TargetRequest` has no fields for the four, so every target registered
through the API reads `not_declared` for ever, and the block prints — correctly —
that nobody said anything, because there is no way to say it.

This record answers the registration surface's question. It is about where the four
questions are asked, what is printed back while they are being answered, and which
side of the wire is allowed to say what the answer means.

## Decision

1. **The four are asked on the `tools` step of the register walk, as a ruled
   fieldset under the tool list, and not as a fourth step.**
   `frontend/src/register/declarations.ts` says of `WALK_STEPS` that a step name
   `unmetConditions` could not see *would be a step nothing holds*. Every step on
   that walk is held by something — the three attestations and the identity, the
   planted value or its waiver, the tool-visibility answer. A Rule of Two step is
   held by **nothing**: ADR-0038 decision 2 refuses no combination of the four
   fields, so the walk would gain a screen an operator may leave untouched, which is
   exactly the shape that docstring refuses. A fieldset on a step the tool list
   already holds has no such problem.

   The neighbour is right on meaning too. The `tools` step already asks the operator
   to declare what the bench will be able to **see**; these four ask what their agent
   can **do**. Both are declarations, neither is measured, and CONTEXT.md keeps
   **declared capability** apart from **declared control** for precisely the reason
   they print in one section of a report.

2. **Three radios per question, never a checkbox, and the fieldset says that it
   holds nothing.** A checkbox cannot express `None`, and whichever way it falls it
   writes a claim the operator did not make — in the direction ADR-0038 spends its
   argument on, since `False` is the **profitable** claim. So each of the three
   capabilities gets *held / declared absent / not stated*, and so does the
   supervision question, defaulting to *not stated*; CONTEXT.md already has the three
   words.

   The four fields never enter `unmetConditions` or `canLeave`. That makes this the
   first declaration on the walk an operator can leave wholly unanswered and still
   register, which is correct and which reads on screen as a field they forgot unless
   the fieldset says otherwise. One line does: silence is not a denial, it is
   reported as silence, and it buys nothing.

3. **The reading prints at declaration time, and that is the point rather than the
   risk.** The first instinct is that a live standing teaches an operator which
   answers look bad and invites them to under-declare. ADR-0038 already answers it,
   in *What the scan cannot do*: a target that under-declares gets *at most two*
   printed, "and what that buys is nothing: the standing carries no figure, so there
   is no number for the under-declaration to move." The defence against gaming is
   that the standing is nowhere in the arithmetic — not that the operator is kept
   from seeing it. Concealing the reading protects nothing.

   And showing it buys the one thing this block could ever be good for. The Rule of
   Two is a published rule about an agent's *architecture*: it is the only thing in
   the report an operator could act on by changing what their agent **is** rather
   than what defends it. A standing that first appears in a signed PDF is read by a
   recipient. A standing on the register screen is read by the person who could still
   change the answer.

   `scanner.NOT_A_MEASUREMENT` prints beside it, unedited, and on this screen it
   carries more weight than it does in the report: here the reading appears before a
   single attempt has been made, with no findings anywhere near it to contrast with.
   The arm that most needs it is still the one that reads most like a finding.

4. **No standing is derived in TypeScript. `scanner.py` stays the sole author of the
   derivation, and it is reached through a stateless endpoint.** ADR-0038 decision 5
   fixes an ordering — a non-empty `not_held` settles the reading at *at most two*
   whatever went unsaid, and `partly_declared` is the reading only where nothing is
   declared absent and something is missing — and that ordering is the one piece of
   this the record got **wrong on its first draft**, printing *the rule cannot be
   read over this* about a declaration the rule could be read over. Five sentences
   and an ordering rule, existing in two languages, is that bug waiting to be
   reintroduced in the copy nobody tests against the gold arms. `declarations.ts`
   sets a precedent for copying backend wording verbatim, and it is a precedent about
   three fixed strings.

   So `POST /rule-of-two` takes a candidate declaration of the four fields and
   returns the standing's name and its `stated()` prose, computing nothing of its
   own. It sends nothing to any target, which keeps it inside `scanner.py`'s declared
   boundary: no `scorer`, no `evaluator`, no `assembler`, no `gate`, and no
   transport.

5. **The endpoint reaches the derivation through a four-argument reading, not
   through a fabricated `TargetConfig`.** `read_rule_of_two` takes a target, and the
   endpoint has no target: there is no name, no URL and no token, and a candidate
   declaration is not owed one. Satisfying the signature would mean inventing a
   `TargetConfig` with a blank URL inside a route that never sends anything —
   a target record standing for a target that does not exist.

   So `scanner.rule_of_two_declared` takes the four `bool | None` answers and
   returns the record, and `read_rule_of_two` is written in terms of it. That is one
   derivation with two entry points rather than two derivations: the ordering, the
   partition and the five arms live in one place, and the function that reads a
   registered target is the same function the screen's reading comes out of. The
   alternative shape — widening `read_rule_of_two` to accept either a target or four
   loose booleans — is the widening this codebase refuses elsewhere, and it would put
   a `TargetConfig | tuple[...]` in the signature of the module whose whole claim is
   that it takes a registration and returns a record.

6. **The reading is fetched when an answer changes, and ADR-0038's *not per
   keystroke* is satisfied by the widget.** The fieldset is four radio groups: there
   is no keystroke between answers, one click is one complete answer, and the
   granularity of a change **is** the granularity of a declaration. Fetching on
   *step exit* was the shape first reached for, and on this walk it means never —
   `tools` is the last step, and the thing it exits into is the registration, so a
   reading printed on exit would arrive after the walk it exists to inform is over.
   Four answers to a stateless route that sends nothing to anybody is the whole cost,
   and there is nothing here to debounce.

7. **The report screen stays figure-only.** It is a viewer for the figures, the
   standing is not a figure, and making it the first non-figure on that page is a
   separate decision from this one. The signed document keeps Annex IV section 3,
   which is where a recipient reads it, and this record does not touch it.

8. **`declared_controls` is not carried on the same commit, and it is not free.** It
   is missing from `TargetRequest` for the same reason the four were, so the question
   is fair. Four `bool | None` on a request model and four arguments in `config()`
   is cheap; a *declaration* is not. A declared control is joined against a verdict
   and that join is the report's headline finding — it needs the checklist asked as a
   checklist, a step to be asked on, and prose about what claiming a control the
   attacks then break will print. A field on the wire that no screen fills is a wire
   shape with no author, and the honest half-measure is none. When it lands it goes
   on this same step, beside these four, for decision 1's reason.

## Considered options

**A fourth step on the walk, *What this agent can do*.** Rejected on decision 1: it
would be the one step `unmetConditions` holds with an empty list, and the walk's own
docstring refuses that in as many words. A fieldset is the same four questions
without a screen nothing holds.

**Four checkboxes.** Rejected. It is the shape the widget wants to be and it cannot
express the answer the field is typed for: a box left unticked is *not stated* and
*declared absent* at once, and the reading has to tell those apart on every arm.
ADR-0038's *Defaulting the three capability fields to `False`* is this option under
another name, and it is the profitable direction.

**A standing derived on the screen, from the five names copied over.** Rejected on
decision 4. The saving is one HTTP route; the cost is the arm ordering living twice,
in a language whose copy no gold arm is tested against.

**Printing no reading until the run is over.** Rejected on decision 3. It is the
status quo, and its effect is that the only human who ever sees a standing is the
recipient of a document — never the operator, who is the one person who could act on
it by changing the agent.

**A count beside the reading — *two of three*.** Not reopened. ADR-0038 rejected it
in the record and in the payload, and a count on a screen is the same figure with a
shorter route to a second target's screen. Nothing on this fieldset counts the
capabilities, and the reading it prints is the backend's sentence.

**An `Article` beside the standing.** Still not decided here, and still ADR-0038's
open question: `judge.article_for` is keyed on `Family` and the Rule of Two is not
one.

## Consequences

- `TargetRequest` gains the four fields, `bool | None` defaulting to `None`, and
  `config()` passes them through — so a target registered through the console can
  declare all four, and its signed report's Annex IV section 3 prints a standing
  other than `not_declared` for the first time.
- `POST /rule-of-two` is the first route on this surface whose subject is neither a
  run nor the bench, and it is stateless: it records nothing, spends nothing and
  reads no registry.
- **It is the first `POST` on this bench that writes nothing, and it is admitted by
  name.** Two tests pin the set of not-`GET` routes — `test_api_gate.py` and
  `test_api_settings.py` — on the reasoning that a write nobody declared is either a
  spend or a setting. This route is a `POST` for its body rather than for a change,
  so it lands in that set and has to be named in both. Naming it is the protection
  working: the alternative is widening the filter to *POSTs that store something*,
  which is a judgement the test would then be making about each route instead of an
  equality a reviewer can read.
- `scanner.py` gains one public function and no new import. The five arms, the
  ordering and the partition stay where they are.
- `Declarations` in `declarations.ts` gains four `boolean | null` fields, defaulted
  to `null` by `nothingDeclared()` and put on the wire by `registrationRequest`.
  `unmetConditions` and `canLeave` are unchanged, and a test asserts that negative.
- `docs/validation.md` records under *what has never been validated* that no real
  operator has ever declared any of this. That line is still true the moment this
  lands — what changes is that it is now a fact about operators rather than about
  the console — and it is worth revisiting once one has.
