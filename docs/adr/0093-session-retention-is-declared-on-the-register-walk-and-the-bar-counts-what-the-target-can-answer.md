---
status: accepted
---

# Session retention is declared on the register walk, and the bar counts what the target can answer

[ADR-0041](./0041-the-persistence-canary-is-read-over-two-turns.md) decided that
session retention is a **registered** property: an endpoint whose operator did not
say it remembers anything is one the bench declines to measure on persistence, rather
than one it reports a clean zero for. `TargetConfig.retains_session_state` has
carried it since, defaulting to `False`, which is the conservative direction.

[ADR-0054](./0054-a-crescendo-is-a-function-of-its-base-case-and-a-halt-outlives-a-turn.md) then made the
capability load-bearing for a second reason. A scripted construction is one attempt
over several turns, and `library.py` refuses a `Case.script` that does not require
`SESSION_RETENTION` — a ladder against a target that answers turn one every time is
a stop signal with no later turn to survive into. So *every* scripted construction in
the library asks for this capability.

Nobody has ever been able to declare it. `TargetRequest` had no field for it, and
neither `scripts/bench.py`, `scripts/attack.py` nor `scripts/probe_target.py` had a
flag, so the only targets that ever declared it were the reference agents, in
`targets/reference/operator.py`. The consequence is that **the fixed multi-turn half
of the scored layer was reachable in a gate run and unreachable against a user's
target** — every scripted case skipped before an attempt was spent, whatever the
operator's construction selection said, and nothing on any screen saying so. This
record closes it, and closes the reading it produced on the run screen.

## Decision

1. **`TargetRequest` gains `retains_session_state`, and `config()` passes it
   through.** A `bool` defaulting to `False`, which is how `TargetConfig` carries it
   — and deliberately *not* the `bool | None` shape ADR-0092 gave the Rule of Two's
   four. Those four are read against a published rule and a wrong default puts a
   claim in an operator's mouth; this one decides whether a construction is
   *attempted*, its absent state has a meaning ADR-0041 already argued for, and the
   narrower run is the safe direction. Silence here is not a claim about the agent,
   it is the bench declining to read a ladder nobody said the target could carry.

2. **The three CLI entry points gain `--retains-session-state`**, and `bench.py`
   forwards it to `serve_callback` for a callback target. Retention is not one of the
   properties the shim reads off a callback — a callback is handed a session id and
   what it does with it is the operator's statement wherever the agent lives
   (ADR-0059 §2) — so it stays a declaration and does not join `url`, `auth_token`,
   `exposes_tool_calls` and `plants`.

3. **The question is asked on the `tools` step of the register walk, as a second
   fieldset under the tool list, and it holds nothing.** ADR-0092 decision 1 applies
   unchanged: the step already asks what the bench will be able to *see* of this
   endpoint, and this is the same kind of question with the same kind of consequence —
   not a rate, but whether a construction is sent at all. Two radios and no third,
   because the field has two meanings and not three, and unanswered posts the `False`
   the API would have defaulted to.

   It does **not** enter `unmetConditions` or `canLeave`, which is where it parts
   company with the tool-visibility question beside it. That one is held because
   neither answer is safe to assume: `false` silently drops two families and `true`
   promises a trace the bench cannot read. Here the unsafe direction does not exist —
   unanswered and *no* produce the same run — so a walk stopped over it would be
   refusing to go on over silence the API accepts. The fieldset says so on screen,
   for the reason ADR-0092 decision 2 gives: a question that refuses nothing reads as
   a field the operator forgot.

4. **A run's family denominator is its plan as this target can answer it.** The row
   on the run screen has always been the plan and never the library, on the argument
   that a bar drawn against cases this run will not attempt can never fill. That
   argument was half-applied. `plan_for` knows the config and not the endpoint — it
   filters on the adjudicator, the planted note, the family switch and the
   construction switch — while the two target-shaped filters run inside the run,
   `applicable` on the agent type and `measurable` on the preconditions, both ahead
   of the first attempt (ADR-0004). A case they withdraw is one no attempt is ever
   spent on, and counting it put `3 / 4` on halt defeat against a target that never
   declared retention, with nothing beside it saying why.

   So `_run_families` applies the same two filters the run applies, over
   `record.target`. The third withdrawal is deliberately not subtracted: the one the
   registration probe makes when a reply contradicts a declaration is read against a
   reply that function cannot see. A row that over-counts there is a bar that stops
   short — the direction this used to fail in everywhere, now the only one left.

## Considered options

**Making the declaration required, like tool-call visibility.** Rejected on decision
3. The two answers are not equally consequential: an unanswered retention question
and a `no` produce the same run, so requiring it buys nothing an operator can act on
and costs a step that refuses a registration the API would accept.

**Three answers, on the Rule of Two's precedent.** Rejected on decision 1. *Not
stated* and *no* are the same run here, and a third state that changes nothing is a
state a reader of the record has to be told to ignore. The Rule of Two's four are
three-valued because a report *prints* the difference; this decides measurability and
prints nothing.

**Deriving retention from something the bench can observe.** Rejected, and it is the
shortcut ADR-0038 §2 names: a capability read off an endpoint's behaviour is a
measurement wearing a declaration's name. The bench sends one registration probe, one
turn, which is exactly the evidence that cannot show whether a *second* turn would
have remembered the first.

**Dropping unmeasurable cases in `plan_for` instead.** Rejected. `plan_for` is called
before the target is registered and prices the estimate an operator confirms; making
it target-aware would either move the two filters out of the run — where ADR-0004 puts
them, ahead of the first attempt and after the probe — or duplicate them. The estimate
staying over the whole plan also errs the safe way: the ceiling an operator confirmed
is never lower than what the run can spend.

**A *skipped* count beside `attempted`, with its reason.** Not taken here. The
withdrawal is already reported where a reader needs it — the report prints the variant
absent rather than at zero, and a family left with nothing reports *not measurable* —
and a third figure on a two-column row is a figure somebody adds to the other two.
Worth reopening if an operator asks why a family's variant list is short.

## Consequences

- A target registered from the console or a script can declare retention, so the
  fixed multi-turn layer is reachable against a user's target for the first time.
  Every scripted construction in the library requires it, so this is the difference
  between that layer running and that layer being skipped.
- `Declarations` gains one `boolean | null` field, defaulted to `null` and posted as
  `false`; `unmetConditions` and `canLeave` are unchanged, and a test asserts that
  negative for every step and every answer.
- The run screen's family denominators drop the cases this target cannot answer, so a
  bar that used to read `3 / 4` and stop reads `3 / 3` and fills. No figure on the
  signed report moves: the report's denominators are the attempts that were made,
  which never counted a skipped case.
- A declaration made here is a claim about somebody's endpoint that the bench cannot
  check, on the terms ADR-0024 already sets for a declaration of this kind. An
  operator who ticks it against a target that in fact keeps no state gets a ladder
  read against turn-one answers — a narrower reading turned into a wrong one, which
  is why the screen says what the answer buys and what it costs.
- `docs/validation.md`'s *what has never been validated* keeps its line about no real
  operator having declared any of this. What changes is that the fixed multi-turn
  layer has now been measured against something other than the reference agents only
  once an operator declares it — worth revisiting when one has.
